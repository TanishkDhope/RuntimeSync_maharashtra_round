"""The quiz state machine. The backend owns the flow (brief s6, s9).

This milestone implements Ask -> Check -> Diagnose. The intervention,
reassessment and probe steps are deliberately absent; they slot in as extra
`step` values without changing anything here structurally.
"""

from __future__ import annotations

import random
from collections import Counter

from sqlalchemy import update
from sqlmodel import Session, select

from .checking import check_predict_output
from .config import Settings
from .data import Library, Problem
from .diagnosis.base import Candidate, Diagnoser
from .models import Attempt, LearnerMisconception, QuizSession
from .runner import run_write_code
from .schemas import (
    AskStep,
    AttemptTimelineOut,
    DiagnosisCandidate,
    FeedbackStep,
    LearnerHistoryOut,
    LearnerMisconceptionOut,
    LearnerOut,
    LearnerSummaryOut,
    ProblemOut,
    Progress,
    SummaryAttempt,
    SummaryMisconception,
    SummaryStep,
    TestCaseOut,
    TopicMasteryOut,
)

TOP_N = 3
_PREFERRED_SPLITS = ("train", "validation")


class FlowError(Exception):
    """A request that does not fit the current state of the session."""


# --- problem selection ------------------------------------------------------

def choose_problems(
    library: Library,
    topic: str,
    count: int,
    seen_problem_ids: set[str],
    rng: random.Random | None = None,
    *,
    serve_write_code: bool = True,
) -> list[str]:
    """Pick `count` problems for a session.

    A run should show both question types, so one slot is reserved for a
    write_code problem and placed last. Some topics (variables, functions)
    have no write_code problems at all, in which case the run is all
    predict_output. When `serve_write_code` is false (the default config,
    SERVE_WRITE_CODE) they are left out entirely: grading them runs student
    code, and the runner still has no memory cap or network block.

    Within each type, prefers problems the learner has not seen, and the
    train/validation splits so the test split stays clean for evaluating the
    model. Falls back to seen problems only when there are not enough fresh
    ones.
    """
    rng = rng or random.Random()
    pool = library.problems_for_topic(topic)
    if not serve_write_code:
        pool = [p for p in pool if p.item_type != "write_code"]
    if not pool:
        raise FlowError(f"no problems for topic {topic!r}")

    predict = _ordered(pool, "predict_output", seen_problem_ids, rng)
    write = _ordered(pool, "write_code", seen_problem_ids, rng)

    # Reserve the last slot for a write_code item when the topic has one.
    write_slots = 1 if write and count > 1 else 0
    chosen = predict[: count - write_slots]
    chosen += write[:write_slots]

    # Short on predict_output items: top up with whatever is left.
    if len(chosen) < count:
        taken = set(chosen)
        for problem_id in predict + write:
            if len(chosen) == count:
                break
            if problem_id not in taken:
                chosen.append(problem_id)
                taken.add(problem_id)
    return chosen


def _ordered(
    pool: list[Problem],
    item_type: str,
    seen_problem_ids: set[str],
    rng: random.Random,
) -> list[str]:
    """Problem ids of one type, best candidates first."""

    def tier(problem: Problem) -> int:
        unseen_penalty = 0 if problem.problem_id not in seen_problem_ids else 2
        split_penalty = 0 if problem.split in _PREFERRED_SPLITS else 1
        return unseen_penalty + split_penalty

    matching = [p for p in pool if p.item_type == item_type]
    rng.shuffle(matching)
    matching.sort(key=tier)
    return [p.problem_id for p in matching]


# --- steps ------------------------------------------------------------------

def start_session(
    db: Session,
    library: Library,
    settings: Settings,
    learner_id: int,
    topic: str,
) -> AskStep:
    seen = set(
        db.exec(select(Attempt.problem_id).where(Attempt.learner_id == learner_id)).all()
    )
    queue = choose_problems(
        library,
        topic,
        settings.session_length,
        seen,
        serve_write_code=settings.serve_write_code,
    )

    quiz = QuizSession(learner_id=learner_id, topic=topic, problem_queue=queue, cursor=0)
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return _ask_step(library, quiz)


def current_step(db: Session, library: Library, settings: Settings, quiz: QuizSession):
    """Rebuild whatever step the session is sitting on. Used to resume."""
    if quiz.state == "done" or quiz.cursor >= len(quiz.problem_queue):
        return build_summary(db, library, settings, quiz)
    if quiz.state == "feedback":
        attempt = _latest_attempt(db, quiz)
        if attempt is not None:
            return _feedback_step(library, settings, quiz, attempt)
    # "grading" means a submission is in flight or crashed mid-flight; either
    # way the problem is still the thing to show.
    return _ask_step(library, quiz)


def _grade(
    library: Library,
    settings: Settings,
    diagnoser: Diagnoser,
    quiz: QuizSession,
    student_response: str,
    student_explanation: str,
) -> tuple[bool, list[dict] | None, list[Candidate]]:
    """Check the answer and, when it is wrong, diagnose it. No database work."""
    problem = library.problem(quiz.problem_queue[quiz.cursor])

    test_results: list[dict] | None = None
    if problem.item_type == "write_code":
        if not settings.serve_write_code:
            # Belt and braces: choose_problems already filtered these out, so
            # reaching here means a queue built before the setting changed.
            raise FlowError(
                "write_code answers are not graded in this configuration "
                "(SERVE_WRITE_CODE is off)"
            )
        is_correct, test_results = run_write_code(
            problem, student_response, settings.run_timeout_seconds
        )
    else:
        is_correct = check_predict_output(problem, student_response)

    ranked: list[Candidate] = []
    if not is_correct:
        ranked = diagnoser.rank(problem, student_response, student_explanation)[:TOP_N]
    return is_correct, test_results, ranked


def submit_answer(
    db: Session,
    library: Library,
    settings: Settings,
    diagnoser: Diagnoser,
    quiz: QuizSession,
    student_response: str,
    student_explanation: str,
) -> FeedbackStep:
    if quiz.state == "done":
        raise FlowError("this session is finished")
    if quiz.state == "feedback":
        raise FlowError("this answer was already graded; continue to the next problem")
    if quiz.cursor >= len(quiz.problem_queue):
        raise FlowError("no problem is waiting for an answer")

    # Claim the answer slot before doing any work. Two quick clicks both pass
    # the state checks above, and without this both would write an attempt
    # (review 3.9). Whoever flips asking -> grading owns this submission.
    claimed = db.exec(
        update(QuizSession)
        .where(QuizSession.id == quiz.id, QuizSession.state == "asking")
        .values(state="grading")
    )
    db.commit()
    if claimed.rowcount != 1:
        db.refresh(quiz)
        raise FlowError("this answer is already being graded")

    try:
        is_correct, test_results, ranked = _grade(
            library, settings, diagnoser, quiz, student_response, student_explanation
        )
        
        problem = library.problem(quiz.problem_queue[quiz.cursor])

        if not is_correct and ranked and settings.llm_api_key:
            from .rerank import rerank_candidates
            ranked = rerank_candidates(settings, library, problem, student_response, student_explanation, ranked)

        scores = [c.score for c in ranked]
        if not is_correct and (not scores or scores[0] < settings.unknown_threshold) and settings.llm_api_key:
            from .generation import generate_misconception
            import hashlib
            
            new_desc = generate_misconception(settings, problem, student_response, student_explanation)
            new_id = f"LLM_GEN_{hashlib.sha256(new_desc.encode()).hexdigest()[:8]}"
            
            m = library.add_generated_misconception(new_id, new_desc, problem.topic)
            diagnoser.add_misconception(m)
            
            ranked = diagnoser.rank(problem, student_response, student_explanation)[:TOP_N]

    except Exception:
        # Hand the slot back, or the session is wedged in "grading" and the
        # learner can neither answer nor move on.
        db.exec(
            update(QuizSession)
            .where(QuizSession.id == quiz.id, QuizSession.state == "grading")
            .values(state="asking")
        )
        db.commit()
        db.refresh(quiz)
        raise

    attempt = Attempt(
        session_id=quiz.id,
        learner_id=quiz.learner_id,
        problem_id=problem.problem_id,
        phase="initial",
        student_response=student_response,
        student_explanation=student_explanation,
        is_correct=is_correct,
        diagnosis=[
            {"misconception_id": c.misconception_id, "score": c.score} for c in ranked
        ],
        # Recorded now, so reopening this attempt later cannot relabel it with
        # whatever DIAGNOSER happens to be set to then (review 3.1).
        diagnoser=diagnoser.name,
        test_results=test_results,
    )
    quiz.state = "feedback"
    db.add(attempt)
    db.add(quiz)
    db.commit()
    db.refresh(attempt)
    db.refresh(quiz)

    update_learner_model(
        db,
        learner_id=quiz.learner_id,
        problem=problem,
        is_correct=is_correct,
        ranked=ranked,
        unknown_threshold=settings.unknown_threshold,
    )

    return _feedback_step(library, settings, quiz, attempt)


def advance(db: Session, library: Library, settings: Settings, quiz: QuizSession):
    """Move past the graded answer to the next problem, or to the summary."""
    if quiz.state == "asking":
        raise FlowError("answer the current problem first")
    if quiz.state != "done":
        quiz.cursor += 1
        quiz.state = "done" if quiz.cursor >= len(quiz.problem_queue) else "asking"
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
    return current_step(db, library, settings, quiz)


# --- step builders ----------------------------------------------------------

def _problem_out(problem: Problem) -> ProblemOut:
    """Never leaks correct_output, predicted_outputs or reference_solution."""
    test_cases = (
        [TestCaseOut(call=tc.call) for tc in problem.test_cases]
        if problem.item_type == "write_code"
        else None
    )
    return ProblemOut(
        problem_id=problem.problem_id,
        item_type=problem.item_type,
        topic=problem.topic,
        problem_text=problem.problem_text,
        test_cases=test_cases,
    )


def _ask_step(library: Library, quiz: QuizSession) -> AskStep:
    problem = library.problem(quiz.problem_queue[quiz.cursor])
    return AskStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        problem=_problem_out(problem),
    )


def _feedback_step(
    library: Library,
    settings: Settings,
    quiz: QuizSession,
    attempt: Attempt,
) -> FeedbackStep:
    problem = library.problem(attempt.problem_id)
    # The diagnoser that actually produced this diagnosis, not the one
    # configured right now (review 3.1).
    name = attempt.diagnoser or settings.diagnoser
    candidates = []
    for row in attempt.diagnosis or []:
        misconception = library.misconception(row["misconception_id"])
        candidates.append(
            DiagnosisCandidate(
                misconception_id=misconception.misconception_id,
                description=misconception.description,
                topic=misconception.topic,
                confusable_group=misconception.confusable_group,
                score=row["score"],
            )
        )

    scores = [c.score for c in candidates]
    return FeedbackStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        problem=_problem_out(problem),
        student_response=attempt.student_response,
        student_explanation=attempt.student_explanation,
        is_correct=attempt.is_correct,
        correct_output=problem.correct_output,
        test_results=attempt.test_results,
        diagnoser=name,
        diagnoser_is_real_model=name in ("model", "ollama"),
        diagnosis=candidates,
        unknown=bool(scores) and scores[0] < settings.unknown_threshold,
        tied=is_tied(scores, settings.probe_gap),
        top_two_gap=round(scores[0] - scores[1], 4) if len(scores) > 1 else None,
        probe_gap=settings.probe_gap,
        has_next=quiz.cursor + 1 < len(quiz.problem_queue),
    )


def is_tied(scores: list[float], probe_gap: float) -> bool:
    """Whether the top two candidates are too close to call (brief s6.4).

    Exact equality is the wrong test for a real model: cosine similarities are
    floats and are essentially never equal, so an exact-equality check means
    the differentiation notice fires for the stub and then silently never
    fires again once a trained model is switched on (review 2.9). The gap
    against PROBE_GAP is the condition the probe step triggers on.
    """
    if len(scores) < 2:
        return False
    return (scores[0] - scores[1]) < probe_gap


def single_top_misconception(diagnosis: list[dict], probe_gap: float = 0.0) -> str | None:
    """The belief the diagnoser actually put first, or None if it did not.

    When the top two scores are within `probe_gap` the diagnoser has not
    chosen between them, and taking the first of the list would turn list
    order into a finding. The stub does exactly this on write_code answers,
    where every candidate scores the same.

    `probe_gap` defaults to 0.0, which keeps the old exact-tie behaviour for
    callers that have no settings to hand.
    """
    if not diagnosis:
        return None
    if is_tied([row["score"] for row in diagnosis], probe_gap) or (
        len(diagnosis) > 1 and diagnosis[0]["score"] == diagnosis[1]["score"]
    ):
        return None
    return diagnosis[0]["misconception_id"]


def build_summary(
    db: Session, library: Library, settings: Settings, quiz: QuizSession
) -> SummaryStep:
    attempts = db.exec(
        select(Attempt).where(Attempt.session_id == quiz.id).order_by(Attempt.id)
    ).all()

    rows: list[SummaryAttempt] = []
    tally: Counter[str] = Counter()
    undiagnosed = 0
    for attempt in attempts:
        problem = library.problem(attempt.problem_id)
        top = single_top_misconception(attempt.diagnosis or [], settings.probe_gap)
        if top:
            tally[top] += 1
        elif not attempt.is_correct:
            undiagnosed += 1
        rows.append(
            SummaryAttempt(
                problem_id=attempt.problem_id,
                topic=problem.topic,
                item_type=problem.item_type,
                is_correct=attempt.is_correct,
                top_misconception=top,
            )
        )

    return SummaryStep(
        undiagnosed_count=undiagnosed,
        session_id=quiz.id,
        topic=quiz.topic,
        total=len(quiz.problem_queue),
        correct_count=sum(1 for a in attempts if a.is_correct),
        attempts=rows,
        misconception_counts=[
            SummaryMisconception(
                misconception_id=mid,
                description=library.misconception(mid).description,
                times=times,
            )
            for mid, times in tally.most_common()
        ],
    )


def _latest_attempt(db: Session, quiz: QuizSession) -> Attempt | None:
    return db.exec(
        select(Attempt)
        .where(Attempt.session_id == quiz.id)
        .order_by(Attempt.id.desc())
        .limit(1)
    ).first()


def update_learner_model(
    db: Session,
    learner_id: int,
    problem: Problem,
    is_correct: bool,
    ranked: list[Candidate],
    unknown_threshold: float = 0.5,
) -> None:
    """Updates learner misconceptions and tracks demonstrated understanding across attempts."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    if not is_correct:
        scores = [c.score for c in ranked]
        top = ranked[0] if (scores and scores[0] >= unknown_threshold) else None
        if top and top.misconception_id != "SLIP":
            m_id = top.misconception_id
            record = db.exec(
                select(LearnerMisconception).where(
                    LearnerMisconception.learner_id == learner_id,
                    LearnerMisconception.misconception_id == m_id,
                )
            ).first()

            if record is None:
                record = LearnerMisconception(
                    learner_id=learner_id,
                    misconception_id=m_id,
                    status="active",
                    times_seen=1,
                    consecutive_correct=0,
                    first_seen=now,
                    last_seen=now,
                )
                db.add(record)
            else:
                record.times_seen += 1
                record.consecutive_correct = 0
                record.last_seen = now
                # Relapse detection: if previously resolved, mark returned = True
                if record.status == "resolved" or record.returned:
                    record.returned = True
                record.status = "active"
                record.resolved_at = None
                db.add(record)
            db.commit()
    else:
        # Correct answer: demonstrated understanding!
        # Check if learner previously held any of the applicable misconceptions for this problem
        for m_id in problem.applicable_misconceptions:
            record = db.exec(
                select(LearnerMisconception).where(
                    LearnerMisconception.learner_id == learner_id,
                    LearnerMisconception.misconception_id == m_id,
                )
            ).first()
            if record is not None and record.status in ("active", "improving"):
                record.consecutive_correct += 1
                if record.consecutive_correct >= 2:
                    record.status = "resolved"
                    record.resolved_at = now
                else:
                    record.status = "improving"
                db.add(record)
        db.commit()


def build_learner_history(
    db: Session,
    library: Library,
    learner_id: int,
) -> LearnerHistoryOut:
    """Aggregates misconception status, topic mastery, and attempt history for a learner."""
    from .models import Learner

    learner = db.get(Learner, learner_id)
    if learner is None:
        raise FlowError(f"no learner {learner_id}")

    attempts = list(
        db.exec(
            select(Attempt)
            .where(Attempt.learner_id == learner_id)
            .order_by(Attempt.created_at.desc())
        ).all()
    )

    sessions = list(
        db.exec(
            select(QuizSession)
            .where(QuizSession.learner_id == learner_id)
        ).all()
    )

    records = list(
        db.exec(
            select(LearnerMisconception)
            .where(LearnerMisconception.learner_id == learner_id)
            .order_by(LearnerMisconception.last_seen.desc())
        ).all()
    )

    # 1. Summary
    total_attempts = len(attempts)
    correct_attempts = sum(1 for a in attempts if a.is_correct)
    accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0.0

    active_count = sum(1 for r in records if r.status == "active")
    improving_count = sum(1 for r in records if r.status == "improving")
    resolved_count = sum(1 for r in records if r.status == "resolved")
    recurring_count = sum(1 for r in records if r.times_seen >= 2)

    summary = LearnerSummaryOut(
        total_sessions=len(sessions),
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        accuracy_percent=round(accuracy, 1),
        active_count=active_count,
        improving_count=improving_count,
        resolved_count=resolved_count,
        recurring_count=recurring_count,
    )

    # 2. Misconceptions
    misconceptions_out: list[LearnerMisconceptionOut] = []
    for r in records:
        try:
            m = library.misconception(r.misconception_id)
            desc = m.description
            topic = m.topic
        except KeyError:
            desc = f"Misconception {r.misconception_id}"
            topic = None

        misconceptions_out.append(
            LearnerMisconceptionOut(
                misconception_id=r.misconception_id,
                description=desc,
                topic=topic,
                status=r.status,
                times_seen=r.times_seen,
                is_recurring=r.times_seen >= 2,
                returned=bool(r.returned),
                consecutive_correct=r.consecutive_correct,
                first_seen=r.first_seen,
                last_seen=r.last_seen,
                resolved_at=r.resolved_at,
            )
        )

    # 3. Topic Mastery
    topic_attempts: dict[str, list[Attempt]] = {}
    for a in attempts:
        try:
            prob = library.problem(a.problem_id)
            t = prob.topic
        except KeyError:
            t = "unknown"
        topic_attempts.setdefault(t, []).append(a)

    topic_mastery: list[TopicMasteryOut] = []
    for t, atts in topic_attempts.items():
        if t == "unknown":
            continue
        tot = len(atts)
        cor = sum(1 for a in atts if a.is_correct)
        acc = (cor / tot * 100) if tot > 0 else 0.0
        active_in_topic = sum(
            1 for m in misconceptions_out
            if m.status == "active" and m.topic == t
        )
        topic_mastery.append(
            TopicMasteryOut(
                topic=t,
                total_attempts=tot,
                correct_attempts=cor,
                accuracy_percent=round(acc, 1),
                active_misconceptions_count=active_in_topic,
            )
        )
    topic_mastery.sort(key=lambda tm: tm.topic)

    # 4. Attempt Timeline
    timeline: list[AttemptTimelineOut] = []
    for a in attempts:
        try:
            prob = library.problem(a.problem_id)
            topic = prob.topic
            item_type = prob.item_type
            problem_text = prob.problem_text
        except KeyError:
            topic = "unknown"
            item_type = "unknown"
            problem_text = ""

        diag_id = None
        diag_desc = None
        if a.diagnosis:
            top_diag = a.diagnosis[0]
            diag_id = top_diag.get("misconception_id")
            if diag_id:
                try:
                    diag_desc = library.misconception(diag_id).description
                except KeyError:
                    diag_desc = diag_id

        timeline.append(
            AttemptTimelineOut(
                id=a.id or 0,
                session_id=a.session_id,
                problem_id=a.problem_id,
                phase=a.phase,
                topic=topic,
                item_type=item_type,
                problem_text=problem_text,
                student_response=a.student_response,
                student_explanation=a.student_explanation,
                is_correct=a.is_correct,
                top_misconception=diag_id,
                diagnosed_misconception_id=diag_id,
                diagnosed_description=diag_desc,
                created_at=a.created_at,
            )
        )

    return LearnerHistoryOut(
        learner=LearnerOut(
            id=learner.id or 0,
            name=learner.name,
            created_at=learner.created_at,
        ),
        summary=summary,
        beliefs=misconceptions_out,
        attempts=timeline,
        misconceptions=misconceptions_out,
        topic_mastery=topic_mastery,
        timeline=timeline,
    )

