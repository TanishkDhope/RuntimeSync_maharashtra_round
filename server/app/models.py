"""Database tables (brief s8).

create_all() creates missing tables but never alters existing ones, so a new
column here would not reach a database that already has the table. db.py's
add_missing_columns() closes that gap on SQLite by issuing ADD COLUMN for
anything new; Postgres and Supabase still need real migrations or a rebuild.
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
    # continue | probe -> waiting for probe answer | explain -> showing explanation
    # retest -> running retest questions | verdict -> final verdict shown
    # done -> queue exhausted
    state: str = Field(default="asking", max_length=20)
    problem_queue: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cursor: int = Field(default=0)
    started_at: datetime = Field(default_factory=_now)
    # Probe / explain / retest / verdict tracking
    probe_problem_id: str | None = Field(default=None, max_length=40)
    confirmed_misconception_id: str | None = Field(default=None, max_length=60)
    retest_cursor: int = Field(default=0)
    retest_total: int = Field(default=0)


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


class LearnerMisconception(SQLModel, table=True):
    """Where a belief stands, derived from misconception_evidence.

    Every column below is a cache. app/learner_model.py recomputes the row
    from the evidence whenever a new piece arrives; nothing else may write it.
    It exists so the history endpoint can answer without replaying evidence on
    every request, not because it is the truth.
    """

    __tablename__ = "learner_misconceptions"
    __table_args__ = (
        UniqueConstraint("learner_id", "misconception_id", name="uq_learner_misconception"),
    )

    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learners.id", index=True)
    misconception_id: str = Field(index=True, max_length=60)
    # active | improving | resolved
    status: str = Field(default="active", max_length=20)
    times_seen: int = Field(default=1)
    # Distinct problems testing this belief answered correctly since it last
    # showed up. Named for history; it has never been a streak of answers.
    consecutive_correct: int = Field(default=0)
    returned: bool = Field(default=False)
    # How many times the belief came back after being called resolved. The
    # boolean above cannot tell one relapse from five.
    relapses: int = Field(default=0)
    # How much evidence-against has accumulated since the belief last showed.
    # Reaching learner_model.RESOLVE_WEIGHT is what makes a belief resolved.
    evidence_against: float = Field(default=0.0)
    first_seen: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = Field(default=None)


class MisconceptionEvidence(SQLModel, table=True):
    """One observation bearing on whether a learner holds a belief.

    The learner model used to be mutated in place from two code paths with
    different rules, so `status` meant whatever the last writer thought it
    meant. These rows are the facts; the status is derived from them. That is
    what makes the model auditable ("why is this resolved?" is a query) and
    evaluable (the evaluation replays prefixes of this table).
    """

    __tablename__ = "misconception_evidence"

    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learners.id", index=True)
    misconception_id: str = Field(index=True, max_length=60)
    attempt_id: int | None = Field(default=None, foreign_key="attempts.id")
    session_id: int | None = Field(default=None, foreign_key="sessions.id", index=True)
    problem_id: str = Field(max_length=40)
    # "for"     -> the belief showed up: a wrong answer was diagnosed to it.
    # "against" -> a problem that tests it was answered correctly.
    direction: str = Field(max_length=10)
    # initial | probe | reassess, matching Attempt.phase.
    phase: str = Field(default="initial", max_length=20)
    # What this single row is worth. A targeted retest is a full point; an
    # incidental correct answer on a problem testing N beliefs is 1/N, because
    # the learner got it right for one reason, not N.
    weight: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=_now)

