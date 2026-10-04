"""What we think a learner believes, and why.

The learner model used to be mutated in place from two places that disagreed.
flow.update_learner_model resolved a belief after two correct answers in a
row; the verdict block in stages.py wrote a status straight from retest
performance and stored the retest count in the same column. `status` therefore
meant whatever the last writer thought it meant, and `consecutive_correct`
meant two different things depending on which path touched it.

Here evidence is recorded as it arrives and the standing is derived from all
of it. That buys three things in-place mutation could not:

  one rulebook     flow and stages append evidence; neither decides status.
  an audit trail   "why is this resolved?" is a query over the rows behind it,
                   which is the explainability the brief asks for.
  evaluability     derive_standing is pure, so scripts/eval_learner_model.py
                   replays prefixes of the same evidence the live system used
                   and measures the shipped rulebook rather than a restatement.

The rule, in one sentence: a belief is resolved once RESOLVE_WEIGHT of
evidence-against has accumulated across at least RESOLVE_PROBLEMS distinct
problems, with no sign of the belief since.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, select

from .data import SLIP_ID, Problem
from .models import LearnerMisconception, MisconceptionEvidence

# A targeted retest is worth a full point, so the two retests the flow serves
# are exactly enough to resolve a belief - if both are answered correctly, on
# two different problems. Incidental correct answers are worth 1/N and take
# proportionally more of them, which is the point: they are weaker evidence.
RESOLVE_WEIGHT = 2.0
RESOLVE_PROBLEMS = 2

FOR = "for"
AGAINST = "against"


@dataclass
class Standing:
    """Where a belief stands after all the evidence so far."""

    status: str = "active"  # active | improving | resolved
    times_seen: int = 0
    relapses: int = 0
    evidence_against: float = 0.0
    problems_against: set[str] = field(default_factory=set)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    resolved_at: datetime | None = None


def derive_standing(rows: list[MisconceptionEvidence]) -> Standing:
    """Replay evidence in order and return where the belief stands.

    Pure on purpose: no database, no clock, no settings. Same rows in, same
    answer out. The evaluation depends on that, and so does being able to
    explain a verdict by pointing at the rows that produced it.
    """
    standing = Standing()
    for row in sorted(rows, key=lambda r: (r.created_at, r.id or 0)):
        if standing.first_seen is None:
            standing.first_seen = row.created_at
        standing.last_seen = row.created_at

        if row.direction == FOR:
            standing.times_seen += 1
            if standing.status == "resolved":
                # It came back. Counted, not just flagged: a learner who
                # relapses five times is not the same as one who relapsed once.
                standing.relapses += 1
            standing.status = "active"
            standing.resolved_at = None
            standing.evidence_against = 0.0
            standing.problems_against = set()
            continue

        # Answering the same question correctly twice is not two pieces of
        # evidence. This is what stops "two in a row" from meaning anything on
        # its own, which is the assumption the brief explicitly rules out.
        if row.problem_id in standing.problems_against:
            continue
        standing.problems_against.add(row.problem_id)
        standing.evidence_against += row.weight

        if (
            standing.evidence_against >= RESOLVE_WEIGHT
            and len(standing.problems_against) >= RESOLVE_PROBLEMS
        ):
            standing.status = "resolved"
            standing.resolved_at = row.created_at
        else:
            standing.status = "improving"

    return standing


def against_weight(
    problem: Problem,
    phase: str,
    misconception_id: str,
    targeted_id: str | None = None,
) -> float:
    """What one correct answer is worth as evidence against one belief.

    A retest problem is chosen because it tests the belief that was diagnosed,
    so getting it right speaks directly to *that* belief: a full point. Every
    other belief the same problem happens to test is incidental, and shares
    the point out among them - the learner got it right for one reason, not
    for all of them. Without that split a targeted retest would clear beliefs
    it was never aimed at.
    """
    if phase == "reassess" and targeted_id is not None and misconception_id == targeted_id:
        return 1.0
    tested = [m for m in problem.applicable_misconceptions if m != SLIP_ID]
    return 1.0 / len(tested) if tested else 1.0


def record(
    db: Session,
    *,
    learner_id: int,
    misconception_id: str,
    problem_id: str,
    direction: str,
    phase: str = "initial",
    weight: float = 1.0,
    attempt_id: int | None = None,
    session_id: int | None = None,
    at: datetime | None = None,
) -> MisconceptionEvidence:
    """Append one piece of evidence. Does not commit - recompute does."""
    row = MisconceptionEvidence(
        learner_id=learner_id,
        misconception_id=misconception_id,
        problem_id=problem_id,
        direction=direction,
        phase=phase,
        weight=weight,
        attempt_id=attempt_id,
        session_id=session_id,
    )
    if at is not None:
        row.created_at = at
    db.add(row)
    return row


def evidence_for(db: Session, learner_id: int, misconception_id: str) -> list[MisconceptionEvidence]:
    return list(
        db.exec(
            select(MisconceptionEvidence)
            .where(
                MisconceptionEvidence.learner_id == learner_id,
                MisconceptionEvidence.misconception_id == misconception_id,
            )
            .order_by(MisconceptionEvidence.created_at.asc(), MisconceptionEvidence.id.asc())
        ).all()
    )


def recompute(db: Session, learner_id: int, misconception_id: str) -> Standing:
    """Derive the standing from evidence and refresh the cached row.

    The only writer of learner_misconceptions. Callers append evidence and
    then call this; nobody decides a status by hand.
    """
    db.flush()  # evidence added in this transaction has to be visible to the read
    rows = evidence_for(db, learner_id, misconception_id)
    standing = derive_standing(rows)

    cached = db.exec(
        select(LearnerMisconception).where(
            LearnerMisconception.learner_id == learner_id,
            LearnerMisconception.misconception_id == misconception_id,
        )
    ).first()

    if cached is None:
        if not rows:
            return standing
        cached = LearnerMisconception(learner_id=learner_id, misconception_id=misconception_id)

    cached.status = standing.status
    cached.times_seen = standing.times_seen
    cached.consecutive_correct = len(standing.problems_against)
    cached.evidence_against = round(standing.evidence_against, 4)
    cached.relapses = standing.relapses
    cached.returned = standing.relapses > 0
    if standing.first_seen is not None:
        cached.first_seen = standing.first_seen
    if standing.last_seen is not None:
        cached.last_seen = standing.last_seen
    cached.resolved_at = standing.resolved_at

    db.add(cached)
    db.commit()
    return standing


def observe_answer(
    db: Session,
    *,
    learner_id: int,
    problem: Problem,
    is_correct: bool,
    diagnosed_id: str | None,
    phase: str = "initial",
    attempt_id: int | None = None,
    session_id: int | None = None,
    at: datetime | None = None,
) -> list[str]:
    """Turn one graded answer into evidence, and refresh what it touched.

    A wrong answer is evidence *for* the belief it was diagnosed to. A correct
    answer is evidence *against* every belief that problem tests - weighted,
    so an incidental right answer does not clear three beliefs at once.

    `diagnosed_id` does double duty: on a wrong answer it is the belief blamed,
    and on a correct retest it is the belief the retest was aimed at, which is
    the one that earns the full point. `at` backdates the evidence, which only
    the backfill needs: live answers happen now.

    Returns the beliefs whose standing was recomputed, for the caller to log
    or show. Beliefs with no evidence yet are not conjured into existence by a
    correct answer: there is nothing to be right about.
    """
    touched: list[str] = []

    if not is_correct:
        if diagnosed_id and diagnosed_id != SLIP_ID:
            record(
                db,
                learner_id=learner_id,
                misconception_id=diagnosed_id,
                problem_id=problem.problem_id,
                direction=FOR,
                phase=phase,
                weight=1.0,
                attempt_id=attempt_id,
                session_id=session_id,
                at=at,
            )
            touched.append(diagnosed_id)
    else:
        for m_id in problem.applicable_misconceptions:
            if m_id == SLIP_ID:
                continue
            # Only beliefs this learner has actually shown. A correct answer
            # is not evidence against a belief they were never suspected of.
            if not evidence_for(db, learner_id, m_id):
                continue
            record(
                db,
                learner_id=learner_id,
                misconception_id=m_id,
                problem_id=problem.problem_id,
                direction=AGAINST,
                phase=phase,
                weight=against_weight(problem, phase, m_id, diagnosed_id),
                attempt_id=attempt_id,
                session_id=session_id,
                at=at,
            )
            touched.append(m_id)

    for m_id in touched:
        recompute(db, learner_id, m_id)
    return touched
