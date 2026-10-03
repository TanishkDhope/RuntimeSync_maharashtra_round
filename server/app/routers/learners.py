"""Learners. No authentication (brief s8): a name is the whole identity."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..deps import DbDep
from ..models import Learner
from ..schemas import LearnerCreate, LearnerOut

router = APIRouter(prefix="/learners", tags=["learners"])


@router.get("", response_model=list[LearnerOut])
def list_learners(db: DbDep) -> list[Learner]:
    return list(db.exec(select(Learner).order_by(Learner.name)).all())


@router.post("", response_model=LearnerOut, status_code=status.HTTP_201_CREATED)
def create_learner(payload: LearnerCreate, db: DbDep) -> Learner:
    """Returns the existing learner when the name is already taken, so typing
    the same name twice resumes rather than erroring."""
    existing = db.exec(select(Learner).where(Learner.name == payload.name)).first()
    if existing is not None:
        return existing

    learner = Learner(name=payload.name)
    db.add(learner)
    db.commit()
    db.refresh(learner)
    return learner


@router.get("/{learner_id}", response_model=LearnerOut)
def get_learner(learner_id: int, db: DbDep) -> Learner:
    learner = db.get(Learner, learner_id)
    if learner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no learner {learner_id}")
    return learner
