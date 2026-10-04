"""New stage flow functions: Probe, Explain, Retest, Verdict.

Imported by flow.py to keep file size manageable.
"""

from __future__ import annotations

from sqlmodel import Session, select

from .checking import check_predict_output, normalise_output
from .config import Settings
from .data import Library, Problem
from .diagnosis.base import Diagnoser
from .models import Attempt, LearnerMisconception, QuizSession
from .schemas import (
    ExplanationOut,
    InterventionStep,
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
    TestCaseOut,
    VerdictReason,
)

PROBE_PROBLEM_PREFIX = "__probe__"
RETEST_COUNT = 2


class FlowError(Exception):
    """Re-exported here to avoid circular import — flow.py's version is the real one."""


def _problem_out(problem: Problem) -> ProblemOut:
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


def _graded_dict(attempt: Attempt, problem: Problem) -> dict:
    return {
        "problem": _problem_out(problem).model_dump(),
        "student_response": attempt.student_response,
        "student_explanation": attempt.student_explanation,
        "is_correct": attempt.is_correct,
        "correct_output": problem.correct_output,
        "test_results": attempt.test_results,
    }


def _diagnosis_dict(attempt: Attempt, library: Library, probe_gap: float, unknown_threshold: float) -> dict:
    candidates = []
    for row in attempt.diagnosis or []:
        try:
            m = library.misconception(row["misconception_id"])
            candidates.append({
                "misconception_id": m.misconception_id,
                "description": m.description,
                "topic": m.topic,
                "confusable_group": m.confusable_group,
                "score": row["score"],
            })
        except KeyError:
            pass
    scores = [c["score"] for c in candidates]

    def is_tied(scores, gap):
        return len(scores) >= 2 and (scores[0] - scores[1]) < gap

    return {
        "diagnoser": attempt.diagnoser,
        "diagnoser_is_real_model": attempt.diagnoser in ("model", "ollama"),
        "candidates": candidates,
        "tied": is_tied(scores, probe_gap),
        "unknown": bool(scores) and scores[0] < unknown_threshold,
        "probe_gap": probe_gap,
    }


def _initial_attempt_for(db: Session, quiz: QuizSession) -> Attempt | None:
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


# ---- PROBE -----------------------------------------------------------------

def transition_to_probe(db, library, settings, quiz, attempt):
    """Generate/select a probe question and transition to 'probe' state."""
    from .generation import generate_probe_problem

    top_ids = [row["misconception_id"] for row in (attempt.diagnosis or [])[:2]]
    if len(top_ids) < 2:
        confirmed_id = top_ids[0] if top_ids else None
        quiz.confirmed_misconception_id = confirmed_id
        quiz.state = "explain"
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        return build_intervention_step(library, settings, quiz, attempt)

    problem = library.problem(quiz.problem_queue[quiz.cursor])

    bank_probe = find_bank_probe(library, top_ids, problem.topic, set(quiz.problem_queue))
    if bank_probe:
        probe_problem, predictions, probe_problem_id = bank_probe
        source, executed, independent_check = "bank", True, True
    else:
        generated = generate_probe_problem(settings, library, problem, top_ids[0], top_ids[1])
        if not generated:
            quiz.confirmed_misconception_id = attempt.diagnosis[0]["misconception_id"]
            quiz.state = "explain"
            db.add(quiz)
            db.commit()
            db.refresh(quiz)
            return build_intervention_step(library, settings, quiz, attempt)

        probe_text = generated["problem_text"]
        correct_output = generated["correct_output"]
        executed, independent_check = False, False

        try:
            import subprocess, sys, os, tempfile
            from .runner import screen_student_code
            if screen_student_code(probe_text) is None:
                with tempfile.TemporaryDirectory(prefix="relearn-probe-") as wd:
                    safe_env = {k: v for k, v in os.environ.items()
                                if k in ("SYSTEMROOT", "COMSPEC", "PATHEXT", "PATH", "NUMBER_OF_PROCESSORS")}
                    script = (
                        "import io, sys\n"
                        "buf = io.StringIO()\n"
                        "_r = sys.stdout\n"
                        "sys.stdout = buf\n"
                        "try:\n"
                        f"    exec(compile({probe_text!r}, '<probe>', 'exec'))\n"
                        "except Exception as e:\n"
                        "    sys.stdout = _r; print(repr(e))\n"
                        "else:\n"
                        "    sys.stdout = _r; print(buf.getvalue(), end='')\n"
                    )
                    sp = subprocess.run(
                        [sys.executable, "-c", script],
                        capture_output=True, text=True, timeout=5.0, env=safe_env,
                    )
                    if sp.returncode == 0:
                        correct_output = sp.stdout.rstrip()
                        executed = True
                        independent_check = True
        except Exception:
            pass

        import hashlib
        probe_problem_id = f"{PROBE_PROBLEM_PREFIX}{hashlib.sha256(probe_text.encode()).hexdigest()[:8]}"
        predictions = generated["predictions"]
        source = "llm"

        from .data import Problem as DataProblem
        probe_problem = DataProblem(
            problem_id=probe_problem_id,
            item_type="predict_output",
            topic=problem.topic,
            problem_text=probe_text,
            correct_output=correct_output,
            reference_solution=None,
            test_cases=(),
            applicable_misconceptions=tuple(top_ids),
            predicted_outputs=predictions,
            split="generated",
        )
        library.problems[probe_problem_id] = probe_problem

    quiz.probe_problem_id = probe_problem_id
    quiz.state = "probe"
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    return ProbeStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        graded=_graded_dict(attempt, problem),
        diagnosis=_diagnosis_dict(attempt, library, settings.probe_gap, settings.unknown_threshold),
        probe=ProbeQuestion(
            problem=_problem_out(probe_problem),
            candidates=list(predictions.keys())[:2],
            predictions=predictions,
            source=source,
            executed=executed,
            independent_check=independent_check,
        ),
    )


def find_bank_probe(library, top_ids, topic, exclude_ids):
    for problem in library.problems.values():
        if problem.problem_id in exclude_ids:
            continue
        if problem.item_type != "predict_output" or problem.topic != topic:
            continue
        preds = problem.predicted_outputs or {}
        if top_ids[0] in preds and top_ids[1] in preds and preds[top_ids[0]] != preds[top_ids[1]]:
            return problem, {top_ids[0]: preds[top_ids[0]], top_ids[1]: preds[top_ids[1]]}, problem.problem_id
    return None


def build_probe_step(library, settings, quiz):
    """Rebuild probe step from session state (for current_step resume)."""
    problem = library.problem(quiz.problem_queue[quiz.cursor])
    pid = quiz.probe_problem_id
    if not pid:
        raise Exception("session is in probe state but has no probe_problem_id")
    try:
        probe_problem = library.problem(pid)
    except KeyError:
        raise Exception(f"probe problem {pid!r} not found (server restart clears generated probes)")
    source = "llm" if pid.startswith(PROBE_PROBLEM_PREFIX) else "bank"
    predictions = probe_problem.predicted_outputs or {}
    return ProbeStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        graded={},
        diagnosis={},
        probe=ProbeQuestion(
            problem=_problem_out(probe_problem),
            candidates=list(predictions.keys())[:2],
            predictions=predictions,
            source=source,
            executed=source == "bank",
            independent_check=source == "bank",
        ),
    )


def submit_probe_answer(db, library, settings, diagnoser, quiz, student_response, student_explanation):
    """Grade probe answer and move to explain state."""
    if quiz.state != "probe":
        raise Exception("this session is not waiting for a probe answer")
    if not quiz.probe_problem_id:
        raise Exception("no probe problem set for this session")
    try:
        probe_problem = library.problem(quiz.probe_problem_id)
    except KeyError:
        raise Exception("probe problem not found (server may have restarted)")

    initial = _initial_attempt_for(db, quiz)
    if initial is None:
        raise Exception("initial attempt not found")

    is_correct = check_predict_output(probe_problem, student_response)
    predictions = probe_problem.predicted_outputs or {}
    matched = None
    norm = normalise_output(student_response)
    for m_id, pred in predictions.items():
        if normalise_output(pred) == norm:
            matched = m_id
            break

    probe_outcome = {
        "student_response": student_response,
        "real_output": normalise_output(probe_problem.correct_output or ""),
        "predictions": predictions,
        "matched": matched,
    }
    confirmed_id = matched or (initial.diagnosis[0]["misconception_id"] if initial.diagnosis else None)

    pa = Attempt(
        session_id=quiz.id,
        learner_id=quiz.learner_id,
        problem_id=quiz.probe_problem_id,
        phase="probe",
        student_response=student_response,
        student_explanation=student_explanation,
        is_correct=is_correct,
        diagnosis=[{"misconception_id": confirmed_id, "score": 1.0}] if confirmed_id else [],
        diagnoser=diagnoser.name,
    )
    db.add(pa)
    quiz.confirmed_misconception_id = confirmed_id
    quiz.state = "explain"
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    return build_intervention_step(library, settings, quiz, initial, probe_outcome=probe_outcome)


# ---- EXPLAIN ---------------------------------------------------------------

def build_intervention_step(library, settings, quiz, attempt, probe_outcome=None):
    from .generation import generate_explanation
    confirmed_id = quiz.confirmed_misconception_id
    if not confirmed_id:
        raise Exception("no confirmed misconception for explanation")
    try:
        m = library.misconception(confirmed_id)
    except KeyError:
        raise Exception(f"misconception {confirmed_id!r} not found")

    problem = library.problem(quiz.problem_queue[quiz.cursor])
    explanation_text = generate_explanation(
        settings, problem, confirmed_id, m.description,
        attempt.student_response, attempt.student_explanation,
    )
    return InterventionStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        graded=_graded_dict(attempt, problem),
        diagnosis=_diagnosis_dict(attempt, library, settings.probe_gap, settings.unknown_threshold),
        probe_outcome=probe_outcome,
        misconception=MisconceptionRef(
            misconception_id=m.misconception_id,
            description=m.description,
        ),
        explanation=ExplanationOut(text=explanation_text, source="llm"),
        trace=None,
    )


# ---- RETEST ----------------------------------------------------------------

def transition_to_retest(db, library, settings, quiz):
    from .generation import generate_retest_problems
    confirmed_id = quiz.confirmed_misconception_id
    if not confirmed_id:
        raise Exception("no confirmed misconception for retest")
    problem = library.problem(quiz.problem_queue[quiz.cursor])
    try:
        m = library.misconception(confirmed_id)
    except KeyError:
        raise Exception(f"misconception {confirmed_id!r} not found")

    retest_problems = generate_retest_problems(
        settings, library, problem, confirmed_id, m.description, count=RETEST_COUNT
    )
    import hashlib
    rt_ids = []
    for rp in retest_problems:
        rt_id = f"__rt__{hashlib.sha256(rp['problem_text'].encode()).hexdigest()[:8]}"
        rt_ids.append(rt_id)
        from .data import Problem as DataProblem
        rt_prob = DataProblem(
            problem_id=rt_id,
            item_type="predict_output",
            topic=rp["topic"],
            problem_text=rp["problem_text"],
            correct_output=rp["correct_output"],
            reference_solution=None,
            test_cases=(),
            applicable_misconceptions=(confirmed_id,),
            predicted_outputs={confirmed_id: rp.get("misconception_prediction", "")},
            split="generated",
        )
        library.problems[rt_id] = rt_prob

    if not rt_ids:
        rt_ids = pick_retest_from_bank(library, confirmed_id, set(quiz.problem_queue), RETEST_COUNT)

    if not rt_ids:
        quiz.state = "verdict"
        quiz.retest_total = 0
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        initial = _initial_attempt_for(db, quiz)
        if initial is None:
            raise Exception("initial attempt not found")
        return build_result_step(db, library, settings, quiz, initial)

    quiz.probe_problem_id = "::".join(rt_ids)
    quiz.retest_cursor = 0
    quiz.retest_total = len(rt_ids)
    quiz.state = "retest"
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return build_retest_ask_step(library, settings, quiz, db)


def pick_retest_from_bank(library, confirmed_id, exclude_ids, count):
    results = []
    for prob in library.problems.values():
        if prob.problem_id in exclude_ids or prob.item_type != "predict_output":
            continue
        if confirmed_id in prob.applicable_misconceptions:
            results.append(prob.problem_id)
            if len(results) >= count:
                break
    return results


def build_retest_ask_step(library, settings, quiz, db):
    rt_ids = [rid for rid in (quiz.probe_problem_id or "").split("::") if rid]
    if quiz.retest_cursor >= len(rt_ids):
        quiz.state = "verdict"
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        initial = _initial_attempt_for(db, quiz)
        if initial is None:
            raise Exception("initial attempt not found for verdict")
        return build_result_step(db, library, settings, quiz, initial)

    rt_problem_id = rt_ids[quiz.retest_cursor]
    try:
        rt_problem = library.problem(rt_problem_id)
    except KeyError:
        raise Exception(f"retest problem {rt_problem_id!r} not found")

    return ReassessAskStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        problem=_problem_out(rt_problem),
        reassess={"index": quiz.retest_cursor + 1, "total": quiz.retest_total},
    )


def submit_retest_answer(db, library, settings, diagnoser, quiz, student_response, student_explanation):
    if quiz.state != "retest":
        raise Exception("this session is not in retest state")
    rt_ids = [rid for rid in (quiz.probe_problem_id or "").split("::") if rid]
    if quiz.retest_cursor >= len(rt_ids):
        raise Exception("all retest questions already answered")

    rt_problem_id = rt_ids[quiz.retest_cursor]
    try:
        rt_problem = library.problem(rt_problem_id)
    except KeyError:
        raise Exception(f"retest problem {rt_problem_id!r} not found")

    is_correct = check_predict_output(rt_problem, student_response)
    confirmed_id = quiz.confirmed_misconception_id
    model_check = None
    if confirmed_id and not is_correct:
        try:
            ranked = diagnoser.rank(rt_problem, student_response, student_explanation)
            rank_pos = next((i + 1 for i, c in enumerate(ranked) if c.misconception_id == confirmed_id), None)
            if ranked:
                model_check = ModelCheckOut(
                    misconception_id=confirmed_id,
                    rank=rank_pos or len(ranked) + 1,
                    score=ranked[0].score,
                )
        except Exception:
            pass

    ra = Attempt(
        session_id=quiz.id,
        learner_id=quiz.learner_id,
        problem_id=rt_problem_id,
        phase="reassess",
        student_response=student_response,
        student_explanation=student_explanation,
        is_correct=is_correct,
        diagnosis=[{"misconception_id": confirmed_id, "score": model_check.score if model_check else 0.0}] if confirmed_id else [],
        diagnoser=diagnoser.name,
    )
    db.add(ra)
    db.flush()

    graded = ReassessGraded(
        problem=_problem_out(rt_problem),
        student_response=student_response,
        student_explanation=student_explanation,
        is_correct=is_correct,
        correct_output=rt_problem.correct_output,
    )

    quiz.retest_cursor += 1
    is_last = quiz.retest_cursor >= len(rt_ids)
    if is_last:
        quiz.state = "verdict"
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    if is_last:
        initial = _initial_attempt_for(db, quiz)
        if initial is None:
            raise Exception("initial attempt not found for verdict")
        return build_result_step(db, library, settings, quiz, initial)

    return ReassessStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        index=quiz.retest_cursor,
        total=quiz.retest_total,
        graded=graded,
        model_check=model_check,
    )


# ---- VERDICT ---------------------------------------------------------------

def build_result_step(db, library, settings, quiz, initial):
    confirmed_id = quiz.confirmed_misconception_id
    if not confirmed_id:
        raise Exception("no confirmed misconception for verdict")
    try:
        m = library.misconception(confirmed_id)
    except KeyError:
        raise Exception(f"misconception {confirmed_id!r} not found")

    retest_attempts = list(
        db.exec(
            select(Attempt).where(
                Attempt.session_id == quiz.id,
                Attempt.phase == "reassess",
            )
        ).all()
    )
    total = len(retest_attempts)
    correct = sum(1 for a in retest_attempts if a.is_correct)
    still_in_reasoning = any(
        any(d.get("misconception_id") == confirmed_id for d in (a.diagnosis or []))
        and not a.is_correct
        for a in retest_attempts
    )

    if total == 0:
        verdict = "improving"
        reasons = [
            VerdictReason(text="No retest questions were available.", ok=False),
            VerdictReason(text="Explanation was shown.", ok=True),
        ]
    elif correct == total and not still_in_reasoning:
        verdict = "resolved"
        reasons = [
            VerdictReason(text=f"All {total} retest questions answered correctly.", ok=True),
            VerdictReason(text="Reasoning no longer matches the diagnosed misconception.", ok=True),
        ]
    elif correct > 0 or not still_in_reasoning:
        verdict = "improving"
        reasons = [
            VerdictReason(text=f"{correct} of {total} retest questions correct.", ok=correct > 0),
            VerdictReason(text="Some evidence of improvement.", ok=True),
        ]
    else:
        verdict = "active"
        reasons = [
            VerdictReason(text=f"Only {correct} of {total} retest questions correct.", ok=False),
            VerdictReason(text="Misconception still appears in answers and reasoning.", ok=False),
        ]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    record = db.exec(
        select(LearnerMisconception).where(
            LearnerMisconception.learner_id == quiz.learner_id,
            LearnerMisconception.misconception_id == confirmed_id,
        )
    ).first()
    old_status = record.status if record else None
    if record is None:
        record = LearnerMisconception(
            learner_id=quiz.learner_id,
            misconception_id=confirmed_id,
            status=verdict,
            times_seen=1,
            consecutive_correct=correct,
            first_seen=now,
            last_seen=now,
        )
        db.add(record)
    else:
        record.last_seen = now
        if verdict == "resolved":
            record.status = "resolved"
            record.resolved_at = now
            record.consecutive_correct = correct
        elif verdict == "improving":
            record.status = "improving"
            record.consecutive_correct = correct
        else:
            if record.status == "resolved":
                record.returned = True
            record.status = "active"
            record.consecutive_correct = 0
        db.add(record)
    db.commit()

    return ResultStep(
        session_id=quiz.id,
        progress=Progress(index=quiz.cursor + 1, total=len(quiz.problem_queue)),
        verdict=verdict,
        reasons=reasons,
        record={
            "misconception_id": confirmed_id,
            "description": m.description,
            "from": old_status,
            "to": verdict,
        },
        has_next=quiz.cursor + 1 < len(quiz.problem_queue),
    )
