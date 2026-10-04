"""Learners. No authentication (brief s8): a name is the whole identity."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import delete, select

from .. import flow, graph, learner_model
from ..deps import DbDep, LibraryDep
from ..models import Attempt, Learner, LearnerMisconception, MisconceptionEvidence, QuizSession
from ..schemas import (
    BeliefGraphOut,
    EvidenceOut,
    LearnerCreate,
    LearnerHistoryOut,
    LearnerOut,
    OpenSessionOut,
)

router = APIRouter(prefix="/learners", tags=["learners"])


def _is_open(quiz: QuizSession) -> bool:
    """Mirrors `flow.current_step`: a session is finished once it is marked done
    or its queue has run out, whatever state it was left sitting in."""
    return quiz.state != "done" and quiz.cursor < len(quiz.problem_queue)


def _open_sessions(db, learner_ids: list[int]) -> dict[int, QuizSession]:
    """The newest unfinished session per learner, in one query."""
    if not learner_ids:
        return {}
    rows = db.exec(
        select(QuizSession)
        .where(QuizSession.learner_id.in_(learner_ids), QuizSession.state != "done")
        .order_by(QuizSession.started_at.desc(), QuizSession.id.desc())
    ).all()
    newest: dict[int, QuizSession] = {}
    for quiz in rows:
        if _is_open(quiz):
            newest.setdefault(quiz.learner_id, quiz)
    return newest


def _out(learner: Learner, open_session: QuizSession | None) -> LearnerOut:
    return LearnerOut(
        id=learner.id,
        name=learner.name,
        created_at=learner.created_at,
        open_session=(
            None
            if open_session is None
            else OpenSessionOut(
                id=open_session.id,
                topic=open_session.topic,
                state=open_session.state,
                started_at=open_session.started_at,
            )
        ),
    )


@router.get("", response_model=list[LearnerOut])
def list_learners(db: DbDep) -> list[LearnerOut]:
    learners = list(db.exec(select(Learner).order_by(Learner.name)).all())
    open_sessions = _open_sessions(db, [learner.id for learner in learners])
    return [_out(learner, open_sessions.get(learner.id)) for learner in learners]


@router.post("", response_model=LearnerOut, status_code=status.HTTP_201_CREATED)
def create_learner(payload: LearnerCreate, db: DbDep) -> LearnerOut:
    """Returns the existing learner when the name is already taken, so typing
    the same name twice resumes rather than erroring."""
    existing = db.exec(select(Learner).where(Learner.name == payload.name)).first()
    if existing is not None:
        return _out(existing, _open_sessions(db, [existing.id]).get(existing.id))

    learner = Learner(name=payload.name)
    db.add(learner)
    db.commit()
    db.refresh(learner)
    return _out(learner, None)


@router.get("/{learner_id}", response_model=LearnerOut)
def get_learner(learner_id: int, db: DbDep) -> LearnerOut:
    learner = db.get(Learner, learner_id)
    if learner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no learner {learner_id}")
    return _out(learner, _open_sessions(db, [learner_id]).get(learner_id))


@router.delete("/{learner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_learner(learner_id: int, db: DbDep) -> Response:
    """Remove a learner and everything recorded for them.

    Unlike closing a session, this really does destroy: the sessions, the
    attempts, and the learner model built from them all go. It is the only way
    to get history off the books, which is why the UI asks first.

    Deleting a learner who is already gone is not an error - the caller wanted
    them gone, and they are.
    """
    learner = db.get(Learner, learner_id)
    if learner is not None:
        # Children first: both tables point at learners.id.
        db.exec(delete(Attempt).where(Attempt.learner_id == learner_id))
        db.exec(delete(MisconceptionEvidence).where(MisconceptionEvidence.learner_id == learner_id))
        db.exec(delete(LearnerMisconception).where(LearnerMisconception.learner_id == learner_id))
        db.exec(delete(QuizSession).where(QuizSession.learner_id == learner_id))
        db.delete(learner)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{learner_id}/beliefs/{misconception_id}/evidence",
    response_model=list[EvidenceOut],
)
def belief_evidence(learner_id: int, misconception_id: str, db: DbDep) -> list[EvidenceOut]:
    """Why this belief stands where it does.

    The standing is derived from these rows, so this is the whole answer, in
    order. An empty list means the learner has never shown the belief - not
    that it was cleared.
    """
    if db.get(Learner, learner_id) is None:
        raise HTTPException(status_code=404, detail=f"no learner {learner_id}")
    return [
        EvidenceOut(
            problem_id=row.problem_id,
            direction=row.direction,
            phase=row.phase,
            weight=round(row.weight, 3),
            session_id=row.session_id,
            attempt_id=row.attempt_id,
            created_at=row.created_at,
        )
        for row in learner_model.evidence_for(db, learner_id, misconception_id)
    ]


@router.get("/{learner_id}/graph", response_model=BeliefGraphOut)
def belief_graph(learner_id: int, db: DbDep, library: LibraryDep) -> BeliefGraphOut:
    """The learner's beliefs and what sits next to them.

    Their own neighbourhood, not the whole library: beliefs they have shown
    plus one hop. Empty nodes mean nothing has been diagnosed yet, which is a
    fine state, not an error.
    """
    if db.get(Learner, learner_id) is None:
        raise HTTPException(status_code=404, detail=f"no learner {learner_id}")
    return graph.build_belief_graph(db, library, learner_id)


@router.get("/{learner_id}/history", response_model=LearnerHistoryOut)
def get_learner_history(learner_id: int, db: DbDep, library: LibraryDep) -> LearnerHistoryOut:
    try:
        return flow.build_learner_history(db, library, learner_id)
    except flow.FlowError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

