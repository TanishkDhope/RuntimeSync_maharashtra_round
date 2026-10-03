"""Request and response shapes.

Responses to the quiz endpoints are a union tagged by `step`. The frontend
renders whatever step it is handed and holds no flow logic of its own
(brief s9), so adding the intervention and reassessment steps later means
adding members here, not reshaping anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# --- learners ---------------------------------------------------------------

class LearnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class LearnerOut(BaseModel):
    id: int
    name: str
    created_at: datetime


# --- meta -------------------------------------------------------------------

class TopicOut(BaseModel):
    topic: str
    problem_count: int


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    diagnoser: Literal["stub", "model", "ollama"] | str
    diagnoser_is_real_model: bool
    model_path: str
    database: str
    database_connected: bool
    problem_count: int
    misconception_count: int
    library_size: int
    llm_configured: bool = False


# --- problems ---------------------------------------------------------------

class TestCaseOut(BaseModel):
    """Only the call is sent before grading; `expected` is withheld."""

    call: str


class ProblemOut(BaseModel):
    problem_id: str
    item_type: Literal["predict_output", "write_code"]
    topic: str
    problem_text: str
    test_cases: list[TestCaseOut] | None = None


# --- diagnosis --------------------------------------------------------------

class DiagnosisCandidate(BaseModel):
    misconception_id: str
    description: str
    topic: str | None
    confusable_group: str | None
    score: float


class TestResultOut(BaseModel):
    call: str
    expected: str
    got: str | None
    passed: bool
    error: str | None


# --- steps ------------------------------------------------------------------

class Progress(BaseModel):
    index: int  # 1-based position of the current problem
    total: int


class AskStep(BaseModel):
    step: Literal["ask"] = "ask"
    session_id: int
    progress: Progress
    problem: ProblemOut


class FeedbackStep(BaseModel):
    step: Literal["feedback"] = "feedback"
    session_id: int
    progress: Progress
    problem: ProblemOut
    student_response: str
    student_explanation: str
    is_correct: bool
    correct_output: str | None = None
    test_results: list[TestResultOut] | None = None
    diagnoser: Literal["stub", "model", "ollama"] | str
    diagnoser_is_real_model: bool
    diagnosis: list[DiagnosisCandidate] = []
    # True when the top score is below UNKNOWN_THRESHOLD: nothing in the
    # library matches well. No belief is drafted (that path is not built).
    unknown: bool = False
    # True when the top two scores are equal and the stub cannot separate
    # them. Surfaced honestly; the probe path that would resolve it is not
    # built yet.
    tied: bool = False
    has_next: bool


class SummaryMisconception(BaseModel):
    misconception_id: str
    description: str
    times: int


class SummaryAttempt(BaseModel):
    problem_id: str
    topic: str
    item_type: str
    is_correct: bool
    # None when the answer was right, or when the diagnoser did not put one
    # belief ahead of the rest.
    top_misconception: str | None = None


class SummaryStep(BaseModel):
    step: Literal["summary"] = "summary"
    session_id: int
    topic: str
    total: int
    correct_count: int
    attempts: list[SummaryAttempt]
    misconception_counts: list[SummaryMisconception]
    # Wrong answers the diagnoser did not narrow to a single belief. Reported
    # rather than quietly dropped, so the tally below is not read as covering
    # every mistake.
    undiagnosed_count: int = 0


Step = AskStep | FeedbackStep | SummaryStep


# --- requests ---------------------------------------------------------------

class SessionCreate(BaseModel):
    learner_id: int
    topic: str = "mixed"


class AnswerIn(BaseModel):
    student_response: str
    student_explanation: str = Field(min_length=1)

    @field_validator("student_explanation")
    @classmethod
    def _require_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("a one-line reason is required")
        return stripped
