"""Health and dataset metadata."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import StateDep
from ..schemas import HealthOut, TopicOut

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health(state: StateDep) -> HealthOut:
    """Reports which diagnoser is active so nobody demos the stub by accident."""
    return HealthOut(
        diagnoser=state.diagnoser.name,
        diagnoser_is_real_model=state.diagnoser.name in ("model", "ollama"),
        model_path=str(state.settings.model_dir),
        database=state.database_backend,
        database_connected=state.database_connected,
        problem_count=len(state.library.problems),
        misconception_count=len(state.library.misconceptions),
        library_size=len(state.library.ranked_misconceptions()),
        llm_configured=bool(state.settings.llm_api_key and state.settings.llm_model),
    )


@router.get("/topics", response_model=list[TopicOut])
def topics(state: StateDep) -> list[TopicOut]:
    return [
        TopicOut(topic=topic, problem_count=count)
        for topic, count in state.library.topic_counts()
    ]
