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


class OpenSessionOut(BaseModel):
    """A session this learner has not finished, so the UI can offer to resume it
    instead of silently opening a second one."""

    id: int
    topic: str
    state: str
    started_at: datetime


class LearnerOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    # None when every session this learner started has run to its verdict.
    open_session: OpenSessionOut | None = None


class EvidenceOut(BaseModel):
    """One row of the trail behind a belief's standing.

    What makes "resolved" answerable rather than assertable: the UI can show
    which answers moved the needle and by how much.
    """

    problem_id: str
    direction: Literal["for", "against"] | str
    phase: str
    weight: float
    session_id: int | None = None
    attempt_id: int | None = None
    created_at: datetime


class LearnerMisconceptionOut(BaseModel):
    misconception_id: str
    description: str
    topic: str | None = None
    status: Literal["active", "improving", "resolved"] | str
    times_seen: int
    is_recurring: bool
    returned: bool = False
    # How many times the belief came back after being called resolved.
    relapses: int = 0
    consecutive_correct: int
    # Evidence accumulated against the belief since it was last seen, and what
    # it takes to clear it. Both reported so "improving" can say how far along.
    evidence_against: float = 0.0
    evidence_needed: float = 0.0
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None = None


class TopicMasteryOut(BaseModel):
    topic: str
    total_attempts: int
    correct_attempts: int
    accuracy_percent: float
    active_misconceptions_count: int


class AttemptTimelineOut(BaseModel):
    id: int
    session_id: int
    problem_id: str
    phase: str = "initial"
    topic: str
    item_type: str
    problem_text: str
    student_response: str
    student_explanation: str
    is_correct: bool
    top_misconception: str | None = None
    diagnosed_misconception_id: str | None = None
    diagnosed_description: str | None = None
    created_at: datetime


class LearnerSummaryOut(BaseModel):
    total_sessions: int
    total_attempts: int
    correct_attempts: int
    accuracy_percent: float
    active_count: int
    improving_count: int
    resolved_count: int
    recurring_count: int


class LearnerHistoryOut(BaseModel):
    learner: LearnerOut
    summary: LearnerSummaryOut
    beliefs: list[LearnerMisconceptionOut]
    attempts: list[AttemptTimelineOut]
    misconceptions: list[LearnerMisconceptionOut]
    topic_mastery: list[TopicMasteryOut]
    timeline: list[AttemptTimelineOut]


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
    # A provider, model and key are all set in config.
    llm_configured: bool = False
    # Whether that provider actually answered just now (brief s9). None when
    # nothing is configured, so there is nothing to reach.
    llm_reachable: bool | None = None
    llm_detail: str | None = None
    # Prompts in use. Empty strings against a model trained with prompts mean
    # degraded rankings, so /health shows them rather than hiding them.
    query_prompt: str = ""
    doc_prompt: str = ""
    serve_write_code: bool = False
    unknown_threshold: float = 0.0
    probe_gap: float = 0.0


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
    # True when the top two scores are closer together than PROBE_GAP, so the
    # diagnoser has not really separated them. Surfaced honestly; the probe
    # path that would resolve it is not built yet.
    tied: bool = False
    # The numbers behind `tied`, so the UI can show why it fired rather than
    # just asserting it. None when there is only one candidate.
    top_two_gap: float | None = None
    probe_gap: float | None = None
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



# --- probe ------------------------------------------------------------------

class ProbeQuestion(BaseModel):
    """The generated or bank-sourced probe question."""
    problem: ProblemOut
    candidates: list[str]           # misconception_ids being differentiated
    predictions: dict[str, str]     # misconception_id -> expected output
    source: Literal["bank", "llm"] = "llm"
    executed: bool = False
    independent_check: bool = False


class ProbeStep(BaseModel):
    step: Literal["probe"] = "probe"
    session_id: int
    progress: Progress
    graded: dict                    # echoes the initial graded attempt info
    diagnosis: dict                 # echoes diagnosis info
    probe: ProbeQuestion


# --- intervention (explain) -------------------------------------------------

class ExplanationOut(BaseModel):
    text: str
    source: Literal["llm", "authored"] = "llm"


class MisconceptionRef(BaseModel):
    misconception_id: str
    description: str


class InterventionStep(BaseModel):
    step: Literal["intervention"] = "intervention"
    session_id: int
    progress: Progress
    graded: dict | None = None
    diagnosis: dict | None = None
    probe_outcome: dict | None = None
    misconception: MisconceptionRef
    explanation: ExplanationOut
    trace: dict | None = None       # future: execution trace steps


# --- reassess (retest) -------------------------------------------------------

class ReassessAskStep(BaseModel):
    step: Literal["ask"] = "ask"
    phase: Literal["reassess"] = "reassess"
    session_id: int
    progress: Progress
    problem: ProblemOut
    reassess: dict                  # {index, total}
    transfer: str | None = None


class ModelCheckOut(BaseModel):
    misconception_id: str
    rank: int
    score: float


class ReassessGraded(BaseModel):
    problem: ProblemOut
    student_response: str
    student_explanation: str
    is_correct: bool
    correct_output: str | None = None
    test_results: list[TestResultOut] | None = None


class ReassessStep(BaseModel):
    step: Literal["reassess"] = "reassess"
    session_id: int
    progress: Progress
    index: int
    total: int
    graded: ReassessGraded
    model_check: ModelCheckOut | None = None


# --- result (verdict) --------------------------------------------------------

class VerdictReason(BaseModel):
    text: str
    ok: bool


class MisconceptionRecord(BaseModel):
    misconception_id: str
    description: str
    from_: str | None = None        # previous status
    to: str                         # new status
    # Pydantic alias so it serialises as "from" in JSON, which is what the frontend reads
    model_config = {"populate_by_name": True}

    @classmethod
    def build(cls, m_id: str, description: str, from_status: str | None, to_status: str):
        return cls(misconception_id=m_id, description=description, from_=from_status, to=to_status)


class ResultStep(BaseModel):
    step: Literal["result"] = "result"
    session_id: int
    progress: Progress
    verdict: Literal["resolved", "improving", "active"]
    reasons: list[VerdictReason]
    record: dict                    # {misconception_id, description, from, to}
    has_next: bool


Step = AskStep | FeedbackStep | ProbeStep | InterventionStep | ReassessAskStep | ReassessStep | ResultStep | SummaryStep


# --- new requests -----------------------------------------------------------

class ProbeAnswerIn(BaseModel):
    student_response: str
    student_explanation: str = Field(min_length=1)

    @field_validator("student_explanation")
    @classmethod
    def _require_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("a one-line reason is required")
        return stripped


class RetestAnswerIn(BaseModel):
    student_response: str
    student_explanation: str = Field(min_length=1)

    @field_validator("student_explanation")
    @classmethod
    def _require_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("a one-line reason is required")
        return stripped



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
