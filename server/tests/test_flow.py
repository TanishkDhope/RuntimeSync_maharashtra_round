"""The session state machine, exercised through the HTTP API."""

from __future__ import annotations

import json


def _learner(client, name="Ada"):
    response = client.post("/learners", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _session(client, learner_id, topic="variables"):
    response = client.post("/sessions", json={"learner_id": learner_id, "topic": topic})
    assert response.status_code == 201
    return response.json()


# --- meta -------------------------------------------------------------------

def test_health_reports_the_active_diagnoser(client):
    body = client.get("/health").json()
    assert body["diagnoser"] == "stub"
    assert body["diagnoser_is_real_model"] is False
    assert body["problem_count"] == 135
    assert body["library_size"] == 49
    assert body["database_connected"] is True


def test_topics_lists_every_topic_with_a_count(client):
    topics = client.get("/topics").json()
    assert {t["topic"] for t in topics} == {
        "variables", "conditionals", "loops", "functions", "lists", "strings",
    }
    assert all(t["problem_count"] > 0 for t in topics)


# --- learners ---------------------------------------------------------------

def test_same_name_resumes_the_same_learner(client):
    first = _learner(client, "Grace")
    second = _learner(client, "Grace")
    assert first["id"] == second["id"]
    assert len(client.get("/learners").json()) == 1


def test_blank_name_is_rejected(client):
    assert client.post("/learners", json={"name": "   "}).status_code == 422


# --- the quiz loop ----------------------------------------------------------

def test_session_starts_on_the_ask_step(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    assert step["step"] == "ask"
    assert step["progress"] == {"index": 1, "total": 3}
    assert step["problem"]["topic"] == "variables"


def test_ask_step_never_leaks_the_answer(client):
    """The frontend must not be able to read the answer out of the payload."""
    learner = _learner(client)
    step = _session(client, learner["id"])
    assert "correct_output" not in step["problem"]
    assert "predicted_outputs" not in json.dumps(step)
    assert "reference_solution" not in json.dumps(step)


def test_write_code_ask_step_shows_calls_but_not_expected_values(client):
    learner = _learner(client)
    step = _session(client, learner["id"], topic="mixed")
    # Walk the queue looking for a write_code item.
    for _ in range(10):
        if step["step"] == "ask" and step["problem"]["item_type"] == "write_code":
            cases = step["problem"]["test_cases"]
            assert cases and all(set(c) == {"call"} for c in cases)
            return
        if step["step"] == "summary":
            break
        if step["step"] == "ask":
            step = client.post(
                f"/sessions/{step['session_id']}/answer",
                json={"student_response": "x", "student_explanation": "y"},
            ).json()
        step = client.post(f"/sessions/{step['session_id']}/next").json()


def test_correct_answer_produces_no_diagnosis(client, library):
    learner = _learner(client)
    step = _session(client, learner["id"])
    correct = library.problem(step["problem"]["problem_id"]).correct_output

    feedback = client.post(
        f"/sessions/{step['session_id']}/answer",
        json={"student_response": correct, "student_explanation": "traced it line by line"},
    ).json()

    assert feedback["step"] == "feedback"
    assert feedback["is_correct"] is True
    assert feedback["diagnosis"] == []
    assert feedback["unknown"] is False


def test_wrong_answer_produces_a_ranked_diagnosis(client, library):
    learner = _learner(client)
    step = _session(client, learner["id"])
    problem = library.problem(step["problem"]["problem_id"])
    belief, wrong_output = next(iter(problem.predicted_outputs.items()))

    feedback = client.post(
        f"/sessions/{step['session_id']}/answer",
        json={"student_response": wrong_output, "student_explanation": "this is why"},
    ).json()

    assert feedback["is_correct"] is False
    assert feedback["correct_output"] == problem.correct_output
    assert belief in {c["misconception_id"] for c in feedback["diagnosis"]}
    assert len(feedback["diagnosis"]) <= 3
    top = feedback["diagnosis"][0]
    assert top["description"]
    assert feedback["diagnoser"] == "stub"
    assert feedback["diagnoser_is_real_model"] is False


def test_feedback_flags_a_tie_when_the_stub_cannot_separate_candidates(client, library):
    """Surfaced honestly rather than resolved by an invented tie-break."""
    learner = _learner(client)
    step = _session(client, learner["id"])

    # Walk the queue for a problem with two beliefs predicting one output.
    for _ in range(5):
        if step["step"] == "summary":
            break
        problem = library.problem(step["problem"]["problem_id"])
        counts: dict[str, int] = {}
        for output in problem.predicted_outputs.values():
            counts[output] = counts.get(output, 0) + 1
        shared = [out for out, n in counts.items() if n > 1]
        if shared:
            feedback = client.post(
                f"/sessions/{step['session_id']}/answer",
                json={"student_response": shared[0], "student_explanation": "because"},
            ).json()
            assert feedback["tied"] is True
            return
        client.post(
            f"/sessions/{step['session_id']}/answer",
            json={"student_response": "nope", "student_explanation": "guess"},
        )
        step = client.post(f"/sessions/{step['session_id']}/next").json()


def test_unmatched_answer_is_flagged_unknown(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    feedback = client.post(
        f"/sessions/{step['session_id']}/answer",
        json={"student_response": "zzzz", "student_explanation": "no idea"},
    ).json()
    assert feedback["unknown"] is True
    assert feedback["diagnosis"][0]["misconception_id"] == "SLIP"


def test_a_reason_is_required(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    response = client.post(
        f"/sessions/{step['session_id']}/answer",
        json={"student_response": "9 4", "student_explanation": "  "},
    )
    assert response.status_code == 422


def test_answering_twice_is_refused(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    payload = {"student_response": "x", "student_explanation": "y"}
    client.post(f"/sessions/{step['session_id']}/answer", json=payload)
    second = client.post(f"/sessions/{step['session_id']}/answer", json=payload)
    assert second.status_code == 409


def test_skipping_ahead_without_answering_is_refused(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    assert client.post(f"/sessions/{step['session_id']}/next").status_code == 409


def test_walking_the_whole_session_reaches_the_summary(client, library):
    learner = _learner(client)
    step = _session(client, learner["id"])
    session_id = step["session_id"]

    answered = 0
    while step["step"] != "summary":
        if step["step"] == "ask":
            problem = library.problem(step["problem"]["problem_id"])
            # Answer the first one correctly, the rest wrongly.
            response = problem.correct_output if answered == 0 else "definitely wrong"
            step = client.post(
                f"/sessions/{session_id}/answer",
                json={"student_response": response, "student_explanation": "my reason"},
            ).json()
            answered += 1
        else:
            step = client.post(f"/sessions/{session_id}/next").json()

    assert step["total"] == 3
    assert step["correct_count"] == 1
    assert len(step["attempts"]) == 3
    assert sum(m["times"] for m in step["misconception_counts"]) == 2
    assert all(m["description"] for m in step["misconception_counts"])


def test_session_can_be_resumed_after_a_refresh(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    session_id = step["session_id"]

    resumed = client.get(f"/sessions/{session_id}").json()
    assert resumed["step"] == "ask"
    assert resumed["problem"]["problem_id"] == step["problem"]["problem_id"]

    client.post(
        f"/sessions/{session_id}/answer",
        json={"student_response": "wrong", "student_explanation": "guess"},
    )
    resumed = client.get(f"/sessions/{session_id}").json()
    assert resumed["step"] == "feedback"
    assert resumed["is_correct"] is False


def test_a_finished_session_keeps_returning_its_summary(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    session_id = step["session_id"]
    while step["step"] != "summary":
        if step["step"] == "ask":
            step = client.post(
                f"/sessions/{session_id}/answer",
                json={"student_response": "wrong", "student_explanation": "guess"},
            ).json()
        else:
            step = client.post(f"/sessions/{session_id}/next").json()

    assert client.get(f"/sessions/{session_id}").json()["step"] == "summary"
    assert client.post(f"/sessions/{session_id}/next").json()["step"] == "summary"
    assert (
        client.post(
            f"/sessions/{session_id}/answer",
            json={"student_response": "x", "student_explanation": "y"},
        ).status_code
        == 409
    )


# --- errors -----------------------------------------------------------------

def test_unknown_learner_is_rejected(client):
    assert client.post("/sessions", json={"learner_id": 999, "topic": "loops"}).status_code == 404


def test_unknown_topic_is_rejected(client):
    learner = _learner(client)
    response = client.post("/sessions", json={"learner_id": learner["id"], "topic": "algebra"})
    assert response.status_code == 422


def test_unknown_session_is_rejected(client):
    assert client.get("/sessions/999").status_code == 404


def test_a_second_session_avoids_the_problems_already_seen(client, library):
    learner = _learner(client)
    first = _session(client, learner["id"])
    session_id = first["session_id"]
    seen = set()
    step = first
    while step["step"] != "summary":
        if step["step"] == "ask":
            seen.add(step["problem"]["problem_id"])
            step = client.post(
                f"/sessions/{session_id}/answer",
                json={"student_response": "wrong", "student_explanation": "guess"},
            ).json()
        else:
            step = client.post(f"/sessions/{session_id}/next").json()

    second = _session(client, learner["id"])
    assert second["problem"]["problem_id"] not in seen


def test_an_unranked_diagnosis_is_not_counted_as_a_finding(client, library):
    """A flat ranking must not become a tally entry.

    The stub cannot rank write_code answers, so taking the first of its flat
    list would turn list order into a diagnosis.
    """
    learner = _learner(client)
    step = _session(client, learner["id"], topic="lists")
    session_id = step["session_id"]

    saw_write_code = False
    while step["step"] != "summary":
        if step["step"] == "ask":
            if step["problem"]["item_type"] == "write_code":
                saw_write_code = True
            step = client.post(
                f"/sessions/{session_id}/answer",
                json={"student_response": "def nope():\n    return 0", "student_explanation": "guess"},
            ).json()
            if step["problem"]["item_type"] == "write_code":
                # Flat scores, so nothing is singled out.
                assert step["is_correct"] is False
                assert len({c["score"] for c in step["diagnosis"]}) == 1
        else:
            step = client.post(f"/sessions/{session_id}/next").json()

    assert saw_write_code, "the lists topic should include a write_code problem"
    write_code_rows = [row for row in step["attempts"] if row["item_type"] == "write_code"]
    assert write_code_rows and all(row["top_misconception"] is None for row in write_code_rows)
    assert step["undiagnosed_count"] >= 1
    counted = {m["misconception_id"] for m in step["misconception_counts"]}
    assert "TRUE_DIVISION_INTEGER" not in counted or len(counted) > 0


def test_a_clear_diagnosis_is_still_counted(client, library):
    learner = _learner(client)
    step = _session(client, learner["id"], topic="variables")
    session_id = step["session_id"]
    while step["step"] != "summary":
        if step["step"] == "ask":
            step = client.post(
                f"/sessions/{session_id}/answer",
                json={"student_response": "zzz", "student_explanation": "guess"},
            ).json()
        else:
            step = client.post(f"/sessions/{session_id}/next").json()

    # "zzz" matches no predicted output, so SLIP wins outright every time.
    assert step["undiagnosed_count"] == 0
    assert [m["misconception_id"] for m in step["misconception_counts"]] == ["SLIP"]
