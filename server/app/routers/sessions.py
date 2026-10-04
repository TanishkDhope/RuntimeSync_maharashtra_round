"""Quiz sessions. Every response is a `step`; the frontend just renders it."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from .. import flow
from .. import stages
from ..deps import DbDep, DiagnoserDep, LibraryDep, SettingsDep
from ..models import Learner, QuizSession
from ..schemas import AnswerIn, ProbeAnswerIn, RetestAnswerIn, SessionCreate, Step

# Starlette renamed this constant; getattr keeps both versions working and
# keeps the deprecation warning out of the test output.
UNPROCESSABLE = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", None
) or status.HTTP_422_UNPROCESSABLE_ENTITY

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _load(db, session_id: int) -> QuizSession:
    quiz = db.get(QuizSession, session_id)
    if quiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no session {session_id}")
    return quiz


@router.post("", response_model=Step, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    db: DbDep,
    library: LibraryDep,
    settings: SettingsDep,
):
    if db.get(Learner, payload.learner_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no learner {payload.learner_id}")

    known = {topic for topic, _ in library.topic_counts()} | {"mixed"}
    if payload.topic not in known:
        raise HTTPException(
            UNPROCESSABLE,
            f"unknown topic {payload.topic!r}; expected one of {sorted(known)}",
        )

    try:
        return flow.start_session(db, library, settings, payload.learner_id, payload.topic)
    except flow.FlowError as exc:
        raise HTTPException(UNPROCESSABLE, str(exc)) from exc


@router.get("/{session_id}", response_model=Step)
def read_session(session_id: int, db: DbDep, library: LibraryDep, settings: SettingsDep):
    """The step this session is sitting on, so a page refresh resumes it."""
    return flow.current_step(db, library, settings, _load(db, session_id))


@router.post("/{session_id}/close", response_model=Step)
def close_session(session_id: int, db: DbDep, library: LibraryDep, settings: SettingsDep):
    """End a session early and hand back the summary it froze on.

    Nothing is destroyed: the attempts stay, history keeps showing them, and
    the session itself stays readable at its summary. Closing one that has
    already finished just returns that summary again.
    """
    quiz = _load(db, session_id)
    flow.close_session(db, quiz)
    return flow.current_step(db, library, settings, quiz)


@router.post("/{session_id}/answer", response_model=Step)
def answer(
    session_id: int,
    payload: AnswerIn,
    db: DbDep,
    library: LibraryDep,
    settings: SettingsDep,
    diagnoser: DiagnoserDep,
):
    try:
        return flow.submit_answer(
            db,
            library,
            settings,
            diagnoser,
            _load(db, session_id),
            payload.student_response,
            payload.student_explanation,
        )
    # A refused reason is a problem with what was submitted, not with the
    # state of the session, so it answers 422 and the client can show the
    # message against the reason field. Must precede the FlowError arm.
    except flow.ReasonRejected as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
        ) from exc
    except flow.FlowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/{session_id}/next", response_model=Step)
def next_step(session_id: int, db: DbDep, library: LibraryDep, settings: SettingsDep):
    try:
        return flow.advance(db, library, settings, _load(db, session_id))
    except flow.FlowError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


# --- New endpoints for Probe, Retest ----------------------------------------

@router.post("/{session_id}/probe", response_model=Step)
def answer_probe(
    session_id: int,
    payload: ProbeAnswerIn,
    db: DbDep,
    library: LibraryDep,
    settings: SettingsDep,
    diagnoser: DiagnoserDep,
):
    """Submit an answer to the probe question."""
    quiz = _load(db, session_id)
    try:
        return stages.submit_probe_answer(
            db, library, settings, diagnoser, quiz,
            payload.student_response, payload.student_explanation,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/{session_id}/retest", response_model=Step)
def answer_retest(
    session_id: int,
    payload: RetestAnswerIn,
    db: DbDep,
    library: LibraryDep,
    settings: SettingsDep,
    diagnoser: DiagnoserDep,
):
    """Submit an answer to the current retest question."""
    quiz = _load(db, session_id)
    try:
        return stages.submit_retest_answer(
            db, library, settings, diagnoser, quiz,
            payload.student_response, payload.student_explanation,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
