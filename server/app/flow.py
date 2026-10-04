"""The quiz state machine. The backend owns the flow (brief s6, s9).

Implements the full learning loop:
  Ask -> Check -> Diagnose -> Probe (if tied) -> Explain -> Retest -> Verdict -> Next problem
"""

from __future__ import annotations

import random
from collections import Counter

from sqlalchemy import update
from sqlmodel import Session, select

from . import learner_model
from .checking import check_predict_output
from .config import Settings
from .data import Library, Problem
from .diagnosis.base import Candidate, Diagnoser
from .guardrails import check_reason
from .models import Attempt, LearnerMisconception, QuizSession
from .runner import run_write_code
from .schemas import (
    AskStep,
    AttemptTimelineOut,
    DiagnosisCandidate,
    ExplanationOut,
    FeedbackStep,
    InterventionStep,
    LearnerHistoryOut,
    LearnerMisconceptionOut,
    LearnerOut,
    LearnerSummaryOut,
    MisconceptionRef,
    ModelCheckOut,
    ProblemOut,
    Progress,
    ProbeQuestion,
    ProbeStep,
    ReassessAskStep,
    ReassessGraded,
    ReassessStep,
    ResultStep,
    SummaryAttempt,
    SummaryMisconception,
    SummaryStep,
    TestCaseOut,
    TopicMasteryOut,
    VerdictReason,
)

TOP_N = 3
# How many candidates the LLM reranker gets to choose between. Reranking a
# list already cut to TOP_N capped accuracy at the retriever's top-3: when the
# right belief sat at rank 4 it was never on the ballot, and the reranker
# answered "none of these", which sent a well-covered error down the
# generation path. Scoped candidate sets are 3-5 long, so this cap only bites
# on the fall back to the whole library.
RERANK_POOL = 10
_PREFERRED_SPLITS = ("train", "validation")


class FlowError(Exception):
    """A request that does not fit the current state of the session."""


class ReasonRejected(FlowError):
    """The stated reason was refused by the guardrail (app/guardrails.py).

    A FlowError subclass so existing handlers still turn it into a 409 with
    the message shown to the learner, but distinguishable for a router that
    wants to answer 422 instead.
    """


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
    from . import stages
    if quiz.state == "done" or quiz.cursor >= len(quiz.problem_queue):
        return build_summary(db, library, settings, quiz)
    if quiz.state == "feedback":
        attempt = _latest_attempt(db, quiz)
        if attempt is not None:
            return _feedback_step(library, settings, quiz, attempt)
    if quiz.state == "probe":
        return stages.build_probe_step(library, settings, quiz)
    if quiz.state == "explain":
        initial = stages._initial_attempt_for(db, quiz)
        if initial is not None:
            return stages.build_intervention_step(library, settings, quiz, initial)
    if quiz.state == "retest":
        return stages.build_retest_ask_step(library, settings, quiz, db)
    if quiz.state == "verdict":
        initial = stages._initial_attempt_for(db, quiz)
        if initial is not None:
            return stages.build_result_step(db, library, settings, quiz, initial)
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
    """Check the answer and, when it is wrong, diagnose it. No database work.

    Returns the diagnoser's full candidate list, not the top TOP_N: the
    reranker downstream needs the whole ballot. Trimming for display is the
    caller's last step.
    """
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
        ranked = diagnoser.rank(problem, student_response, student_explanation)
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
    if quiz.state == "probe":
        raise FlowError("a probe question is waiting for an answer; use the probe endpoint")
    if quiz.state in ("explain", "retest", "verdict"):
        raise FlowError(f"session is in {quiz.state!r} stage; complete the current stage first")
    if quiz.cursor >= len(quiz.problem_queue):
        raise FlowError("no problem is waiting for an answer")

    # Guardrail the stated reason before claiming the slot, so a refused
    # submission leaves the session in "asking" and the learner can edit and
    # resubmit. Checking after the claim would burn the attempt.
    verdict = check_reason(
        settings,
        library.problem(quiz.problem_queue[quiz.cursor]),
        student_response,
        student_explanation,
    )
    if verdict is not None and verdict.rejection:
        raise ReasonRejected(verdict.rejection)

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
            ranked = rerank_candidates(
                settings,
                library,
                problem,
                student_response,
                student_explanation,
                ranked[:RERANK_POOL],
            )

        scores = [c.score for c in ranked]
        if not is_correct and (not scores or scores[0] < settings.unknown_threshold) and settings.llm_api_key:
            from .generation import generate_misconception
            import hashlib

            new_desc = generate_misconception(settings, problem, student_response, student_explanation)
            new_id = f"LLM_GEN_{hashlib.sha256(new_desc.encode()).hexdigest()[:8]}"

            m = library.add_generated_misconception(new_id, new_desc, problem.topic)
            diagnoser.add_misconception(m)

            ranked = diagnoser.rank(problem, student_response, student_explanation)

        # Trim for display only, once every reranking step has had the full
        # ballot to work from.
        ranked = ranked[:TOP_N]

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
        reason_guardrail=verdict.as_row() if verdict else None,
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
        attempt_id=attempt.id,
        session_id=quiz.id,
    )

    return _feedback_step(library, settings, quiz, attempt)


def advance(db: Session, library: Library, settings: Settings, quiz: QuizSession):
    """Move past the current step to the next one in the flow.

    After a correct answer or unknown-diagnosis (no LLM configured), moves directly
    to the next problem.  After a wrong answer with a diagnosis, triggers the
    full Probe -> Explain -> Retest -> Verdict loop.
    """
    from . import stages
    if quiz.state == "asking":
        raise FlowError("answer the current problem first")

    if quiz.state == "feedback":
        attempt = _latest_attempt(db, quiz)
        if attempt is None or attempt.is_correct:
            return _advance_to_next(db, library, settings, quiz)

        scores = [row["score"] for row in (attempt.diagnosis or [])]
        has_diagnosis = bool(scores) and scores[0] >= settings.unknown_threshold
        if not has_diagnosis or not settings.llm_api_key:
            return _advance_to_next(db, library, settings, quiz)

        if is_tied(scores, settings.probe_gap) and len(attempt.diagnosis) >= 2:
            return stages.transition_to_probe(db, library, settings, quiz, attempt)
        else:
            confirmed_id = attempt.diagnosis[0]["misconception_id"]
            quiz.confirmed_misconception_id = confirmed_id
            quiz.state = "explain"
            db.add(quiz)
            db.commit()
            db.refresh(quiz)
            return stages.build_intervention_step(library, settings, quiz, attempt)

    if quiz.state == "explain":
        return stages.transition_to_retest(db, library, settings, quiz)

    if quiz.state == "retest":
        # /next is called after a reassess result step: serve next retest ask
        return stages.build_retest_ask_step(library, settings, quiz, db)

    if quiz.state == "verdict":
        return _advance_to_next(db, library, settings, quiz)

    if quiz.state != "done":
        return _advance_to_next(db, library, settings, quiz)

    return current_step(db, library, settings, quiz)


def close_session(db: Session, quiz: QuizSession) -> None:
    """End a session early, keeping everything it recorded.

    Marking it done is the whole operation. The attempts stay, and so does what
    the learner model took from them: history is built from those rows, not
    from the session's state, so a closed session still shows up in the ledger
    and still opens on its own summary. It just stops counting as open, which
    frees the learner to start a fresh one.
    """
    quiz.state = "done"
    # Transient per-question fields; leaving them set would describe a probe or
    # retest that is no longer running.
    quiz.probe_problem_id = None
    quiz.confirmed_misconception_id = None
    quiz.retest_cursor = 0
    quiz.retest_total = 0
    db.add(quiz)
    db.commit()
    db.refresh(quiz)


def _advance_to_next(db: Session, library: Library, settings: Settings, quiz: QuizSession):
    """Move the cursor to the next problem (or to done)."""
    quiz.cursor += 1
    quiz.state = "done" if quiz.cursor >= len(quiz.problem_queue) else "asking"
    quiz.probe_problem_id = None
    quiz.confirmed_misconception_id = None
    quiz.retest_cursor = 0
    quiz.retest_total = 0
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


def _initial_attempt(db: Session, quiz: QuizSession) -> Attempt | None:
    """The first (initial phase) attempt for the current cursor position."""
    problem_id = quiz.problem_queue[quiz.cursor]
    return db.exec(
        select(Attempt)
        .where(
            Attempt.session_id == quiz.id,
            Attempt.problem_id == problem_id,
            Attempt.phase == "initial",
        )
        .order_by(Attempt.id.asc())
        .limit(1)
    ).first()


def update_learner_model(
    db: Session,
    learner_id: int,
    problem: Problem,
    is_correct: bool,
    ranked: list[Candidate],
    unknown_threshold: float = 0.5,
    *,
    attempt_id: int | None = None,
    session_id: int | None = None,
    phase: str = "initial",
    targeted_id: str | None = None,
) -> None:
    """Record what this answer says about the learner's beliefs.

    Thin on purpose. The rules live in app/learner_model.py, which both this
    and the verdict path in stages.py go through, so there is one definition
    of what "resolved" means instead of two that disagreed.

    A diagnosis below `unknown_threshold` is not evidence of anything: the
    diagnoser is saying it does not know, and recording a belief on the back
    of that would manufacture a learner model out of noise.

    `targeted_id` is the belief a retest was aimed at. A correct answer
    carries no diagnosis, so without it a retest would look like any other
    right answer and earn only its incidental share of the credit.
    """
    diagnosed = targeted_id
    if not is_correct and ranked and ranked[0].score >= unknown_threshold:
        diagnosed = ranked[0].misconception_id
    elif not is_correct:
        diagnosed = None

    learner_model.observe_answer(
        db,
        learner_id=learner_id,
        problem=problem,
        is_correct=is_correct,
        diagnosed_id=diagnosed,
        phase=phase,
        attempt_id=attempt_id,
        session_id=session_id,
    )


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
                relapses=r.relapses,
                consecutive_correct=r.consecutive_correct,
                evidence_against=round(r.evidence_against, 2),
                evidence_needed=learner_model.RESOLVE_WEIGHT,
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

