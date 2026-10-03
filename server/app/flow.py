"""The quiz state machine. The backend owns the flow (brief s6, s9).

This milestone implements Ask -> Check -> Diagnose. The intervention,
reassessment and probe steps are deliberately absent; they slot in as extra
`step` values without changing anything here structurally.
"""

from __future__ import annotations

import random
from collections import Counter

from sqlmodel import Session, select

from .checking import check_predict_output
from .config import Settings
from .data import Library, Problem
from .diagnosis.base import Candidate, Diagnoser
from .models import Attempt, QuizSession
from .runner import run_write_code
from .schemas import (
    AskStep,
    DiagnosisCandidate,
    FeedbackStep,
    ProblemOut,
    Progress,
    SummaryAttempt,
    SummaryMisconception,
    SummaryStep,
    TestCaseOut,
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
) -> list[str]:
    """Pick `count` problems for a session.

    A run should show both question types, so one slot is reserved for a
    write_code problem and placed last. Some topics (variables, functions)
    have no write_code problems at all, in which case the run is all
    predict_output.

    Within each type, prefers problems the learner has not seen, and the
    train/validation splits so the test split stays clean for evaluating the
    model. Falls back to seen problems only when there are not enough fresh
    ones.
    """
    rng = rng or random.Random()
    pool = library.problems_for_topic(topic)
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
    queue = choose_problems(library, topic, settings.session_length, seen)

    quiz = QuizSession(learner_id=learner_id, topic=topic, problem_queue=queue, cursor=0)
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return _ask_step(library, quiz)


def current_step(db: Session, library: Library, settings: Settings, quiz: QuizSession):
    """Rebuild whatever step the session is sitting on. Used to resume."""
    if quiz.state == "done" or quiz.cursor >= len(quiz.problem_queue):
        return build_summary(db, library, quiz)
    if quiz.state == "feedback":
        attempt = _latest_attempt(db, quiz)
        if attempt is not None:
            return _feedback_step(library, settings, quiz, attempt)
    return _ask_step(library, quiz)


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

    problem = library.problem(quiz.problem_queue[quiz.cursor])

    test_results: list[dict] | None = None
    if problem.item_type == "write_code":
        is_correct, test_results = run_write_code(
            problem, student_response, settings.run_timeout_seconds
        )
    else:
        is_correct = check_predict_output(problem, student_response)

    ranked: list[Candidate] = []
    if not is_correct:
        ranked = diagnoser.rank(problem, student_response, student_explanation)[:TOP_N]

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
        test_results=test_results,
    )
    quiz.state = "feedback"
    db.add(attempt)
    db.add(quiz)
    db.commit()
    db.refresh(attempt)
    db.refresh(quiz)

    return _feedback_step(library, settings, quiz, attempt, diagnoser_name=diagnoser.name)


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
    diagnoser_name: str | None = None,
) -> FeedbackStep:
    problem = library.problem(attempt.problem_id)
    name = diagnoser_name or settings.diagnoser
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
        tied=len(scores) > 1 and scores[0] == scores[1],
        has_next=quiz.cursor + 1 < len(quiz.problem_queue),
    )


def single_top_misconception(diagnosis: list[dict]) -> str | None:
    """The belief the diagnoser actually put first, or None if it did not.

    When the top two scores are equal the diagnoser has not chosen between
    them, and taking the first of the list would turn list order into a
    finding. The stub does exactly this on write_code answers, where every
    candidate scores the same.
    """
    if not diagnosis:
        return None
    if len(diagnosis) > 1 and diagnosis[0]["score"] == diagnosis[1]["score"]:
        return None
    return diagnosis[0]["misconception_id"]


def build_summary(db: Session, library: Library, quiz: QuizSession) -> SummaryStep:
    attempts = db.exec(
        select(Attempt).where(Attempt.session_id == quiz.id).order_by(Attempt.id)
    ).all()

    rows: list[SummaryAttempt] = []
    tally: Counter[str] = Counter()
    undiagnosed = 0
    for attempt in attempts:
        problem = library.problem(attempt.problem_id)
        top = single_top_misconception(attempt.diagnosis or [])
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
