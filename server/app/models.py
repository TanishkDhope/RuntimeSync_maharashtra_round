"""Database tables (brief s8, subset).

Only the tables this milestone needs. learner_misconceptions, probes and
candidate_misconceptions belong to the intervention, reassessment and probe
paths, which are not built yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Learner(SQLModel, table=True):
    __tablename__ = "learners"
    __table_args__ = (UniqueConstraint("name", name="uq_learners_name"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=80)
    created_at: datetime = Field(default_factory=_now)


class QuizSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learners.id", index=True)
    topic: str = Field(max_length=40)
    # asking -> waiting for an answer | feedback -> answer graded, awaiting
    # continue | done -> queue exhausted
    state: str = Field(default="asking", max_length=20)
    problem_queue: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cursor: int = Field(default=0)
    started_at: datetime = Field(default_factory=_now)


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id", index=True)
    learner_id: int = Field(foreign_key="learners.id", index=True)
    problem_id: str = Field(max_length=40)
    # initial | probe | reassess -- only "initial" is produced this milestone
    phase: str = Field(default="initial", max_length=20)
    student_response: str
    student_explanation: str
    is_correct: bool
    # [{"misconception_id": str, "score": float}], empty when the answer was right
    diagnosis: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    test_results: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
