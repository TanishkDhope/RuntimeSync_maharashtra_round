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
from .models import Attempt, QuizSession
from .models import Probe
from .probes import create_probe, match_probe_answer, needs_probe
from .runner import run_write_code
from .schemas import (
    AskStep,
    DiagnosisCandidate,
    FeedbackStep,
    ProbeOut,
    ProbeResult,
    ProbeResultStep,
    ProbeStep,
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
    if quiz.state == "probing" and quiz.active_probe_id:
        probe = db.get(Probe, quiz.active_probe_id)
        if probe:
            return _probe_step(quiz, probe)
    if quiz.state == "probe_result" and quiz.active_probe_id:
        probe = db.get(Probe, quiz.active_probe_id)
        if probe:
            return _probe_result_step(quiz, probe)
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
) -> FeedbackStep | ProbeStep:
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

    candidate_ids = [c.misconception_id for c in ranked[:2]]
    if not is_correct and needs_probe([c.score for c in ranked], settings.probe_gap):
        seen = set(db.exec(select(Attempt.problem_id).where(Attempt.learner_id == quiz.learner_id)).all())
        draft = create_probe(library, settings, problem, candidate_ids, seen)
        if draft is not None:
            probe = Probe(
                session_id=quiz.id,
                problem_id=draft.problem_id,
                topic=draft.topic,
                program=draft.program,
                actual_output=draft.actual_output,
                candidate_ids=candidate_ids,
                candidate_predictions=draft.predictions,
                source=draft.source,
            )
            quiz.state = "probing"
            db.add(probe)
            db.commit()
            db.refresh(probe)
            quiz.active_probe_id = probe.id
            db.add(quiz)
            db.commit()
            db.refresh(quiz)
            return _probe_step(quiz, probe)
    return _feedback_step(library, settings, quiz, attempt)


def submit_probe(db: Session, library: Library, settings: Settings, quiz: QuizSession, response: str):
    if quiz.state != "probing" or not quiz.active_probe_id:
        raise FlowError("a probe is not waiting for an answer")
    probe = db.get(Probe, quiz.active_probe_id)
    if probe is None or probe.submitted_at is not None:
        raise FlowError("this probe was already submitted")
    status, misconception_id = match_probe_answer(probe.candidate_predictions, response)
    # A probe is an Attempt phase, keeping history in the existing table.
    db.add(Attempt(
        session_id=quiz.id, learner_id=quiz.learner_id, problem_id=probe.problem_id or f"probe-{probe.id}",
        phase="probe", student_response=response, student_explanation="diagnostic probe",
        is_correct=False, diagnosis=([{"misconception_id": misconception_id, "score": 1.0}] if misconception_id else []),
        diagnoser="probe",
    ))
    from .models import _now
    probe.submitted_at = _now()
    probe.result_status = status
    quiz.state = "probe_result"
    db.add(probe)
    db.add(quiz)
    db.commit()
    db.refresh(probe)
    db.refresh(quiz)
    return _probe_result_step(quiz, probe)


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


def _probe_step(quiz: QuizSession, probe: Probe) -> ProbeStep:
    return ProbeStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        probe=ProbeOut(id=probe.id, problem_id=probe.problem_id or f"generated-{probe.id}", topic=probe.topic,
                       problem_text=probe.program, candidate_count=len(probe.candidate_ids)),
    )


def _probe_result_step(quiz: QuizSession, probe: Probe) -> ProbeResultStep:
    # Do not leak candidate identities or outputs; the probe only reports the
    # strength of its evidence until a future Explain stage is built.
    status = probe.result_status or "uncertain"
    messages = {
        "confirmed": "Your response provided additional evidence about your reasoning.",
        "uncertain": "Your response did not distinguish the competing explanations.",
        "ambiguous": "Your response matched more than one possible explanation.",
    }
    return ProbeResultStep(
        session_id=quiz.id, progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        result=ProbeResult(status=status, display_message=messages[status]),
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
