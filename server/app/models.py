"""Database tables (brief s8, subset).

Only the tables this milestone needs. learner_misconceptions, probes and
candidate_misconceptions belong to the intervention, reassessment and probe
paths, which are not built yet.

create_all() creates missing tables but never alters existing ones, so adding
a column here does not reach a database that already has the table. During the
hackathon the fix is to delete server/relearn.db and let it be rebuilt; a
longer-lived database would need Alembic.
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
    # Logical pointer rather than a foreign key: probes already reference the
    # session and a two-way FK creates an avoidable SQLite DDL cycle.
    active_probe_id: int | None = Field(default=None)
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
    # Which diagnoser produced `diagnosis`: stub | model | ollama. Recorded per
    # attempt, because DIAGNOSER can change between runs and a stub result must
    # never be relabelled "trained model" when an old session is reopened.
    diagnoser: str = Field(default="stub", max_length=20)
    test_results: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    # What the guardrail decision model made of student_explanation, or None
    # when the check was off or could not run (app/guardrails.py). Recorded so
    # the quality thresholds can be chosen from real sessions rather than by
    # eye; only the injection score acts on anything today.
    reason_guardrail: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


class Probe(SQLModel, table=True):
    """A persisted diagnostic question and its server-only predictions."""

    __tablename__ = "probes"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id", index=True)
    problem_id: str | None = Field(default=None, max_length=40)
    topic: str = Field(max_length=40)
    program: str
    actual_output: str
    candidate_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    candidate_predictions: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    source: str = Field(max_length=12)  # bank | gemini
    result_status: str | None = Field(default=None, max_length=12)
    submitted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
