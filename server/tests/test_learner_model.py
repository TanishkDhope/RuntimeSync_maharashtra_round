"""Tests for the Learner Model: tracking recurring misconceptions and demonstrated understanding."""

from __future__ import annotations

from app.db import build_engine, create_tables
from app.diagnosis.base import Candidate
from app.flow import submit_answer, update_learner_model
from app.models import Learner, LearnerMisconception, QuizSession
from sqlmodel import Session, select


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

        # Manually resolve it
        rec.status = "resolved"
        db.add(rec)
        db.commit()

        # 2. Second occurrence (relapse!)
        update_learner_model(db, learner.id, problem, is_correct=False, ranked=candidates)
        db.refresh(rec)
        assert rec.times_seen == 2
        assert rec.status == "active"  # flipped back from resolved to active!
        assert rec.resolved_at is None


def test_demonstrated_understanding_promotes_to_improving_and_resolved(settings, library):
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = Learner(name="Student3")
        db.add(learner)
        db.commit()
        db.refresh(learner)

        problem = library.problem("PO_VAR_02")
        candidates = [Candidate(misconception_id="VAR_KEEPS_FIRST_VALUE", score=0.9)]

        # Start with active misconception
        update_learner_model(db, learner.id, problem, is_correct=False, ranked=candidates)
        rec = db.exec(
            select(LearnerMisconception).where(
                LearnerMisconception.learner_id == learner.id,
                LearnerMisconception.misconception_id == "VAR_KEEPS_FIRST_VALUE",
            )
        ).first()
        assert rec.status == "active"

        # 1st correct answer on a problem testing this misconception
        update_learner_model(db, learner.id, problem, is_correct=True, ranked=[])
        db.refresh(rec)
        assert rec.consecutive_correct == 1
        assert rec.status == "improving"

        # 2nd consecutive correct answer -> promotes to resolved!
        update_learner_model(db, learner.id, problem, is_correct=True, ranked=[])
        db.refresh(rec)
        assert rec.consecutive_correct == 2
        assert rec.status == "resolved"
        assert rec.resolved_at is not None


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
