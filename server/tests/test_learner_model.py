"""Tests for the Learner Model: tracking recurring misconceptions and
demonstrated understanding across attempts.

The rules themselves live in app/learner_model.py and are measured, not just
asserted, by scripts/eval_learner_model.py. These tests pin the behaviour that
measurement depends on.
"""

from __future__ import annotations

import pytest
from app import learner_model
from app.db import build_engine, create_tables
from app.diagnosis.base import Candidate
from app.flow import submit_answer, update_learner_model
from app.models import Attempt, Learner, LearnerMisconception, QuizSession
from sqlmodel import Session, select


def _record(db, learner_id, misconception_id):
    return db.exec(
        select(LearnerMisconception).where(
            LearnerMisconception.learner_id == learner_id,
            LearnerMisconception.misconception_id == misconception_id,
        )
    ).first()


def test_misconception_tracked_on_wrong_answer(settings, library):
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        from app.diagnosis import build_diagnoser
        diagnoser = build_diagnoser(settings, library)

        learner = Learner(name="Student1")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        queue = ["PO_VAR_01"]
        quiz = QuizSession(learner_id=learner.id, topic="variables", problem_queue=queue, cursor=0)
        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        feedback = submit_answer(
            db, library, settings, diagnoser, quiz, "9 9", "linked"
        )
        assert not feedback.is_correct
        assert len(feedback.diagnosis) > 0
        top_id = feedback.diagnosis[0].misconception_id

        # Check LearnerMisconception record
        record = db.exec(
            select(LearnerMisconception).where(
                LearnerMisconception.learner_id == learner.id,
                LearnerMisconception.misconception_id == top_id,
            )
        ).first()
        assert record is not None
        assert record.status == "active"
        assert record.times_seen == 1
        assert record.consecutive_correct == 0


def test_recurring_misconception_increments_and_detects_relapse(settings, library):
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student2")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        problem = library.problem("PO_VAR_02")
        candidates = [Candidate(misconception_id="VAR_KEEPS_FIRST_VALUE", score=0.9)]

        # 1. First occurrence
        update_learner_model(db, learner.id, problem, is_correct=False, ranked=candidates)
        rec = db.exec(
            select(LearnerMisconception).where(
                LearnerMisconception.learner_id == learner.id,
                LearnerMisconception.misconception_id == "VAR_KEEPS_FIRST_VALUE",
            )
        ).first()
        assert rec.times_seen == 1
        assert rec.status == "active"

        # Resolve it the way the system does, through evidence.
        for problem_id in ("PO_VAR_04", "PO_VAR_14"):
            update_learner_model(
                db, learner.id, library.problem(problem_id), is_correct=True, ranked=[],
                phase="reassess", targeted_id="VAR_KEEPS_FIRST_VALUE",
            )
        db.refresh(rec)
        assert rec.status == "resolved"

        # 2. Second occurrence (relapse!)
        update_learner_model(db, learner.id, problem, is_correct=False, ranked=candidates)
        db.refresh(rec)
        assert rec.times_seen == 2
        assert rec.status == "active"  # flipped back from resolved to active!
        assert rec.resolved_at is None
        assert rec.relapses == 1


def test_the_same_problem_answered_right_twice_does_not_resolve(settings, library):
    """Answering one question correctly twice is one piece of evidence, not two.

    This is the behaviour the brief singles out: a correct follow-up answer is
    not proof that learning happened. The old rule resolved a belief after two
    correct answers in a row and would have passed on the same problem twice.
    """
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student3")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        problem = library.problem("PO_VAR_02")
        candidates = [Candidate(misconception_id="VAR_KEEPS_FIRST_VALUE", score=0.9)]
        update_learner_model(db, learner.id, problem, is_correct=False, ranked=candidates)

        for _ in range(4):
            update_learner_model(db, learner.id, problem, is_correct=True, ranked=[])

        rec = _record(db, learner.id, "VAR_KEEPS_FIRST_VALUE")
        assert rec.status != "resolved"
        assert rec.consecutive_correct == 1  # one distinct problem, however often


def test_two_targeted_retests_resolve_the_belief(settings, library):
    """The retest is what the system can actually lean on.

    Its problems are chosen because they test the diagnosed belief, so each
    correct answer is worth a full point and two of them clear the bar.
    """
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student4")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        belief = "VAR_KEEPS_FIRST_VALUE"
        update_learner_model(
            db, learner.id, library.problem("PO_VAR_02"),
            is_correct=False, ranked=[Candidate(misconception_id=belief, score=0.9)],
        )
        assert _record(db, learner.id, belief).status == "active"

        update_learner_model(
            db, learner.id, library.problem("PO_VAR_04"), is_correct=True, ranked=[],
            phase="reassess", targeted_id=belief,
        )
        assert _record(db, learner.id, belief).status == "improving"

        update_learner_model(
            db, learner.id, library.problem("PO_VAR_14"), is_correct=True, ranked=[],
            phase="reassess", targeted_id=belief,
        )
        rec = _record(db, learner.id, belief)
        assert rec.status == "resolved"
        assert rec.resolved_at is not None
        assert rec.consecutive_correct == 2


def test_one_right_answer_does_not_clear_every_belief_it_touches(settings, library):
    """PO_VAR_04 tests three beliefs. The learner got it right for one reason.

    Splitting the credit is what stops a single lucky answer from clearing a
    learner's whole model at once.
    """
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student5")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        problem = library.problem("PO_VAR_04")
        for belief in ("VAR_KEEPS_FIRST_VALUE", "ASSIGN_COMPARES"):
            update_learner_model(
                db, learner.id, problem, is_correct=False,
                ranked=[Candidate(misconception_id=belief, score=0.9)],
            )

        update_learner_model(db, learner.id, problem, is_correct=True, ranked=[])

        for belief in ("VAR_KEEPS_FIRST_VALUE", "ASSIGN_COMPARES"):
            rec = _record(db, learner.id, belief)
            assert rec.status == "improving"
            # Three beliefs on the problem, so a third of a point each.
            assert rec.evidence_against == pytest.approx(1 / 3, abs=1e-3)


def test_a_belief_that_comes_back_is_counted_not_just_flagged(settings, library):
    """A learner who relapses five times is not the same as one who relapsed once."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student6")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        belief = "VAR_KEEPS_FIRST_VALUE"
        wrong = [Candidate(misconception_id=belief, score=0.9)]
        retests = ("PO_VAR_04", "PO_VAR_14")

        for _ in range(2):
            update_learner_model(
                db, learner.id, library.problem("PO_VAR_02"), is_correct=False, ranked=wrong
            )
            for problem_id in retests:
                update_learner_model(
                    db, learner.id, library.problem(problem_id), is_correct=True, ranked=[],
                    phase="reassess", targeted_id=belief,
                )
            assert _record(db, learner.id, belief).status == "resolved"

        update_learner_model(
            db, learner.id, library.problem("PO_VAR_02"), is_correct=False, ranked=wrong
        )
        rec = _record(db, learner.id, belief)
        assert rec.status == "active"
        assert rec.relapses == 2
        assert rec.returned is True
        assert rec.evidence_against == 0.0  # the slate is wiped, not carried over


def test_a_standing_can_be_explained_by_the_evidence_behind_it(settings, library):
    """"Why is this resolved?" has to be answerable with rows, not a shrug."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student7")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        belief = "VAR_KEEPS_FIRST_VALUE"
        update_learner_model(
            db, learner.id, library.problem("PO_VAR_02"), is_correct=False,
            ranked=[Candidate(misconception_id=belief, score=0.9)],
        )
        for problem_id in ("PO_VAR_04", "PO_VAR_14"):
            update_learner_model(
                db, learner.id, library.problem(problem_id), is_correct=True, ranked=[],
                phase="reassess", targeted_id=belief,
            )

        trail = learner_model.evidence_for(db, learner.id, belief)
        assert [row.direction for row in trail] == ["for", "against", "against"]
        assert [row.problem_id for row in trail] == ["PO_VAR_02", "PO_VAR_04", "PO_VAR_14"]

        # The derivation is pure: the same rows give the same answer, and that
        # answer is what the cached row says.
        assert learner_model.derive_standing(trail).status == "resolved"
        assert learner_model.derive_standing(list(reversed(trail))).status == "resolved"
        assert _record(db, learner.id, belief).status == "resolved"


def test_a_diagnosis_the_model_is_unsure_of_is_not_evidence(settings, library):
    """Below the unknown threshold the diagnoser is saying it does not know.

    Recording a belief on the back of that would build a learner model out of
    the diagnoser's noise.
    """
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student8")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        update_learner_model(
            db, learner.id, library.problem("PO_VAR_02"), is_correct=False,
            ranked=[Candidate(misconception_id="VAR_KEEPS_FIRST_VALUE", score=0.2)],
            unknown_threshold=0.5,
        )
        assert _record(db, learner.id, "VAR_KEEPS_FIRST_VALUE") is None
        assert learner_model.evidence_for(db, learner.id, "VAR_KEEPS_FIRST_VALUE") == []


def test_learner_history_endpoint(client):
    # 1. Create learner
    res = client.post("/learners", json={"name": "HistoryStudent"})
    assert res.status_code == 201
    lid = res.json()["id"]

    # 2. Start session and submit an answer
    session_res = client.post("/sessions", json={"learner_id": lid, "topic": "variables"})
    assert session_res.status_code == 201
    sid = session_res.json()["session_id"]

    client.post(
        f"/sessions/{sid}/answer",
        json={"student_response": "5 10 5", "student_explanation": "testing history"}
    )

    # 3. Get history
    hist_res = client.get(f"/learners/{lid}/history")
    assert hist_res.status_code == 200
    data = hist_res.json()

    assert data["learner"]["name"] == "HistoryStudent"
    assert data["summary"]["total_attempts"] == 1
    assert len(data["timeline"]) == 1
    assert len(data["topic_mastery"]) == 1
    assert data["topic_mastery"][0]["topic"] == "variables"


def test_the_evidence_behind_a_belief_is_servable(client, library):
    """The UI has to be able to show why a belief stands where it does."""
    learner_id = client.post("/learners", json={"name": "EvidenceStudent"}).json()["id"]
    session = client.post("/sessions", json={"learner_id": learner_id, "topic": "variables"}).json()

    # Answer the way one of the problem's own misconceptions makes people
    # answer, so the diagnoser has something to be confident about. The queue
    # is shuffled, so the problem has to be read back rather than assumed.
    asked = client.get(f"/sessions/{session['session_id']}").json()["problem"]["problem_id"]
    problem = library.problem(asked)
    belief, wrong_answer = next(iter(problem.predicted_outputs.items()))

    step = client.post(
        f"/sessions/{session['session_id']}/answer",
        json={"student_response": wrong_answer, "student_explanation": f"because {belief}"},
    ).json()

    beliefs = client.get(f"/learners/{learner_id}/history").json()["beliefs"]
    assert beliefs, "a wrong answer with a diagnosis should leave a belief behind"
    belief_id = beliefs[0]["misconception_id"]
    assert beliefs[0]["evidence_needed"] > 0

    trail = client.get(f"/learners/{learner_id}/beliefs/{belief_id}/evidence")
    assert trail.status_code == 200
    rows = trail.json()
    assert [row["direction"] for row in rows] == ["for"]
    assert rows[0]["problem_id"] == step["problem"]["problem_id"]
    assert rows[0]["session_id"] == session["session_id"]

    # A belief the learner never showed has an empty trail, not a 404.
    empty = client.get(f"/learners/{learner_id}/beliefs/NOT_A_BELIEF/evidence")
    assert empty.status_code == 200 and empty.json() == []
    assert client.get("/learners/999999/beliefs/X/evidence").status_code == 404


def test_the_verdict_is_what_the_evidence_says(settings, library):
    """The retest used to be thrown away and a status written over the top.

    stages.py never called the learner model: it computed a verdict from the
    retest and assigned it. Now the retest answers go in as evidence and the
    verdict is read back off the standing, so the screen and the history
    cannot disagree.
    """
    from app import stages

    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="VerdictStudent")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        belief = "VAR_KEEPS_FIRST_VALUE"
        quiz = QuizSession(
            learner_id=learner.id,
            topic="variables",
            problem_queue=["PO_VAR_02"],
            cursor=0,
            state="verdict",
            confirmed_misconception_id=belief,
            retest_total=2,
            retest_cursor=2,
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        initial = Attempt(
            session_id=quiz.id, learner_id=learner.id, problem_id="PO_VAR_02",
            phase="initial", student_response="wrong", student_explanation="because",
            is_correct=False, diagnosis=[{"misconception_id": belief, "score": 0.9}],
        )
        db.add(initial)
        for problem_id in ("PO_VAR_04", "PO_VAR_14"):
            db.add(Attempt(
                session_id=quiz.id, learner_id=learner.id, problem_id=problem_id,
                phase="reassess", student_response="right", student_explanation="got it",
                is_correct=True, diagnosis=[{"misconception_id": belief, "score": 0.0}],
            ))
        db.commit()
        db.refresh(initial)

        # The learner model has to know the belief was seen before the retest
        # can count as evidence against it.
        update_learner_model(
            db, learner.id, library.problem("PO_VAR_02"), is_correct=False,
            ranked=[Candidate(misconception_id=belief, score=0.9)],
        )

        result = stages.build_result_step(db, library, settings, quiz, initial)

        assert result.verdict == "resolved"
        assert _record(db, learner.id, belief).status == "resolved"

        trail = learner_model.evidence_for(db, learner.id, belief)
        assert [row.direction for row in trail] == ["for", "against", "against"]
        # Targeted retests, so each is worth a full point rather than a share.
        assert [row.weight for row in trail[1:]] == [1.0, 1.0]
        assert [row.phase for row in trail[1:]] == ["reassess", "reassess"]


def test_a_failed_retest_leaves_the_belief_standing(settings, library):
    """Getting the retest wrong is evidence the belief is still there."""
    from app import stages

    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="RelapseStudent")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        belief = "VAR_KEEPS_FIRST_VALUE"
        quiz = QuizSession(
            learner_id=learner.id, topic="variables", problem_queue=["PO_VAR_02"],
            cursor=0, state="verdict", confirmed_misconception_id=belief,
            retest_total=2, retest_cursor=2,
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        initial = Attempt(
            session_id=quiz.id, learner_id=learner.id, problem_id="PO_VAR_02",
            phase="initial", student_response="wrong", student_explanation="because",
            is_correct=False, diagnosis=[{"misconception_id": belief, "score": 0.9}],
        )
        db.add(initial)
        db.add(Attempt(
            session_id=quiz.id, learner_id=learner.id, problem_id="PO_VAR_04",
            phase="reassess", student_response="right", student_explanation="ok",
            is_correct=True, diagnosis=[{"misconception_id": belief, "score": 0.0}],
        ))
        db.add(Attempt(
            session_id=quiz.id, learner_id=learner.id, problem_id="PO_VAR_14",
            phase="reassess", student_response="wrong again", student_explanation="still",
            is_correct=False, diagnosis=[{"misconception_id": belief, "score": 0.8}],
        ))
        db.commit()
        db.refresh(initial)

        update_learner_model(
            db, learner.id, library.problem("PO_VAR_02"), is_correct=False,
            ranked=[Candidate(misconception_id=belief, score=0.9)],
        )

        result = stages.build_result_step(db, library, settings, quiz, initial)

        assert result.verdict == "active"
        rec = _record(db, learner.id, belief)
        assert rec.status == "active"
        assert rec.evidence_against == 0.0  # the wrong retest wiped the credit
        assert any("more points of evidence" in reason.text for reason in result.reasons)
