"""Regression tests for the issues in CODEBASE_REVIEW.md.

One test per fixed finding, named after it, so a later change that reopens one
of them fails here rather than on a projector.
"""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.config import Settings
from app.data import load_library
from app.flow import choose_problems, is_tied, single_top_misconception

from .conftest import DATA_DIR


def _learner(client, name="Ada"):
    response = client.post("/learners", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _session(client, learner_id, topic="variables"):
    response = client.post("/sessions", json={"learner_id": learner_id, "topic": topic})
    assert response.status_code == 201
    return response.json()


# --- 2.9: the tie that fires for a real model -------------------------------

def test_is_tied_uses_the_probe_gap_not_exact_equality():
    """Cosine scores are never exactly equal, so an exact-equality tie check
    silently stops firing the moment a trained model is switched on."""
    assert is_tied([0.71, 0.66], 0.1) is True, "a 0.05 gap is within PROBE_GAP"
    assert is_tied([0.71, 0.55], 0.1) is False, "a 0.16 gap is a clear winner"
    assert is_tied([0.9, 0.9], 0.1) is True
    assert is_tied([0.9], 0.1) is False, "one candidate cannot tie"
    assert is_tied([], 0.1) is False


def test_a_close_but_unequal_pair_is_reported_as_tied():
    """The exact scores the old check would have let through."""
    diagnosis = [
        {"misconception_id": "A", "score": 0.7123},
        {"misconception_id": "B", "score": 0.7119},
    ]
    assert single_top_misconception(diagnosis, probe_gap=0.1) is None
    # With no gap configured, only exact equality counts as unresolved.
    assert single_top_misconception(diagnosis, probe_gap=0.0) == "A"


def test_the_feedback_step_shows_the_numbers_behind_the_tie(client, library):
    learner = _learner(client)
    step = _session(client, learner["id"])
    feedback = client.post(
        f"/sessions/{step['session_id']}/answer",
        json={"student_response": "nonsense", "student_explanation": "a guess"},
    ).json()

    assert feedback["probe_gap"] == pytest.approx(0.1)
    if len(feedback["diagnosis"]) > 1:
        gap = feedback["diagnosis"][0]["score"] - feedback["diagnosis"][1]["score"]
        assert feedback["top_two_gap"] == pytest.approx(gap, abs=1e-4)
        assert feedback["tied"] is (gap < feedback["probe_gap"])


# --- 3.1: the diagnoser is recorded per attempt -----------------------------

def test_an_old_attempt_keeps_the_diagnoser_that_produced_it(client, library):
    """Switching DIAGNOSER must not relabel a stub result "trained model"."""
    learner = _learner(client)
    step = _session(client, learner["id"])
    session_id = step["session_id"]

    feedback = client.post(
        f"/sessions/{session_id}/answer",
        json={"student_response": "nonsense", "student_explanation": "a guess"},
    ).json()
    assert feedback["diagnoser"] == "stub"

    # Pretend the config was flipped to the trained model and the page
    # refreshed. The stored attempt must still say "stub".
    client.app.state.relearn.settings.diagnoser = "model"
    resumed = client.get(f"/sessions/{session_id}").json()

    assert resumed["diagnoser"] == "stub"
    assert resumed["diagnoser_is_real_model"] is False


# --- 3.9: two quick clicks ---------------------------------------------------

def test_a_second_submission_for_the_same_problem_is_refused(client):
    learner = _learner(client)
    step = _session(client, learner["id"])
    body = {"student_response": "nonsense", "student_explanation": "a guess"}

    first = client.post(f"/sessions/{step['session_id']}/answer", json=body)
    second = client.post(f"/sessions/{step['session_id']}/answer", json=body)

    assert first.status_code == 200
    # The router maps FlowError on /answer to 409 Conflict.
    assert second.status_code == 409
    history = client.get(f"/learners/{learner['id']}/history")
    if history.status_code == 200:  # the endpoint is not built yet
        assert len(history.json()["attempts"]) == 1


def test_a_failed_grading_does_not_wedge_the_session(client, monkeypatch):
    """The slot is claimed before grading, so a crash must hand it back."""
    from app import flow

    learner = _learner(client)
    step = _session(client, learner["id"])
    body = {"student_response": "nonsense", "student_explanation": "a guess"}

    def boom(*args, **kwargs):
        raise RuntimeError("diagnoser exploded")

    monkeypatch.setattr(flow, "_grade", boom)
    with pytest.raises(RuntimeError):
        client.post(f"/sessions/{step['session_id']}/answer", json=body)
    monkeypatch.undo()

    # The same problem is still answerable.
    recovered = client.post(f"/sessions/{step['session_id']}/answer", json=body)
    assert recovered.status_code == 200
    assert recovered.json()["step"] == "feedback"


# --- write_code is off by default (1.2, 1.3 made unreachable) ---------------

def test_write_code_problems_are_not_served_by_default(library):
    """SERVE_WRITE_CODE defaults to false, so no answer reaches the runner."""
    assert Settings(data_dir=str(DATA_DIR)).serve_write_code is False

    for topic in ("mixed", "lists", "strings", "functions"):
        chosen = choose_problems(
            library, topic, 5, set(), random.Random(0), serve_write_code=False
        )
        assert chosen, topic
        assert all(
            library.problem(pid).item_type == "predict_output" for pid in chosen
        ), topic


def test_with_write_code_off_a_submitted_write_code_answer_is_refused(tmp_path):
    """A queue built while the setting was on must not be gradable after it
    is turned off."""
    settings = Settings(
        diagnoser="stub",
        data_dir=str(DATA_DIR),
        database_url=f"sqlite:///{tmp_path / 'wc.db'}",
        session_length=3,
        serve_write_code=True,
    )
    real_get_settings = config.get_settings
    app = main.create_app()
    app.dependency_overrides[real_get_settings] = lambda: settings

    import app.main as main_module

    original = main_module.get_settings
    main_module.get_settings = lambda: settings
    try:
        with TestClient(app) as client:
            learner = _learner(client, name="WriteCode")
            step = _session(client, learner["id"], topic="lists")
            session_id = step["session_id"]

            while step["step"] == "ask" and step["problem"]["item_type"] != "write_code":
                client.post(
                    f"/sessions/{session_id}/answer",
                    json={"student_response": "x", "student_explanation": "y"},
                )
                step = client.post(f"/sessions/{session_id}/next").json()
                if step["step"] == "summary":
                    pytest.skip("this run drew no write_code problem")

            # Now the operator turns write_code off mid-session.
            client.app.state.relearn.settings.serve_write_code = False
            refused = client.post(
                f"/sessions/{session_id}/answer",
                json={"student_response": "def f():\n    return 1", "student_explanation": "y"},
            )
            assert refused.status_code == 409
            assert "SERVE_WRITE_CODE" in refused.json()["detail"]
    finally:
        main_module.get_settings = original


# --- 3.10: /health says more than "a key is set" ----------------------------

def test_health_reports_the_prompts_and_thresholds_in_force(client):
    body = client.get("/health").json()

    assert body["llm_configured"] is False
    assert body["llm_reachable"] is None, "nothing configured means nothing to reach"
    assert "No LLM configured" in body["llm_detail"]
    assert body["serve_write_code"] is True  # the test fixture turns it on
    assert body["unknown_threshold"] == pytest.approx(0.5)
    assert body["probe_gap"] == pytest.approx(0.1)
    assert "query_prompt" in body and "doc_prompt" in body


def test_the_shipped_env_example_sets_the_prompts_training_used():
    """An empty QUERY_PROMPT against a prompt-trained model is a silent
    accuracy loss, so .env.example must carry the real values (review 2.2)."""
    text = (DATA_DIR.parent / "server" / ".env.example").read_text(encoding="utf-8")
    assert 'QUERY_PROMPT="task: classification | query: "' in text
    assert 'DOC_PROMPT="title: none | text: "' in text


def test_the_shipped_env_example_has_no_connection_string(library):
    """Review 1.1: no credentials in a committed file, ever again."""
    text = (DATA_DIR.parent / "server" / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("DATABASE_URL=") or line.startswith("SUPABASE_URL="):
            assert "@" not in line, f"a credential is committed: {line.split('=')[0]}"
    assert "DATABASE_URL=sqlite:///./relearn.db" in text


# --- 3.2: a new column reaches an existing database -------------------------

def test_a_new_column_is_added_to_an_existing_sqlite_database(tmp_path):
    """create_all() never alters a table, so without this every insert fails
    against a database made before the column existed (review 3.2)."""
    import sqlite3

    from app.db import add_missing_columns, build_engine

    path = tmp_path / "old.db"

    # The `attempts` table exactly as it shipped before `diagnoser` existed,
    # with a row in it - a populated table is what makes ADD COLUMN need a
    # default value.
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE attempts ("
        " id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL,"
        " learner_id INTEGER NOT NULL, problem_id VARCHAR(40) NOT NULL,"
        " phase VARCHAR(20) NOT NULL, student_response VARCHAR NOT NULL,"
        " student_explanation VARCHAR NOT NULL, is_correct BOOLEAN NOT NULL,"
        " diagnosis JSON, test_results JSON, created_at DATETIME NOT NULL)"
    )
    old.execute(
        "INSERT INTO attempts VALUES (1, 1, 1, 'PO_VAR_01', 'initial', 'x', 'y',"
        " 0, '[]', NULL, '2026-01-01 00:00:00')"
    )
    old.commit()
    old.close()

    settings = Settings(data_dir=str(DATA_DIR), database_url=f"sqlite:///{path}")
    engine = build_engine(settings)
    added = add_missing_columns(engine)

    assert "attempts.diagnoser" in added

    check = sqlite3.connect(path)
    assert [row[0] for row in check.execute("select diagnoser from attempts")] == [
        "stub"
    ], "the existing row keeps its data and gets the default"
    assert check.execute("select student_response from attempts").fetchone()[0] == "x"
    check.close()

    assert add_missing_columns(engine) == [], "running it again changes nothing"


# --- 3.3: the stub respects the train-split library -------------------------

def test_the_ranked_library_is_train_split_only():
    library = load_library(DATA_DIR)
    assert len(library.ranked_misconceptions()) == 49
    assert all(m.split == "train" for m in library.ranked_misconceptions())
    assert len(library.misconceptions) == 61
