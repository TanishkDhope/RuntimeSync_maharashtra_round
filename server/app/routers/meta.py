"""Health and dataset metadata."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import StateDep
from ..llm_health import check_llm
from ..schemas import HealthOut, TopicOut

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health(state: StateDep) -> HealthOut:
    """Reports which diagnoser is active so nobody demos the stub by accident.

    Also reports the prompts and thresholds in force: an empty QUERY_PROMPT
    against a model trained with one is the kind of mismatch that shows up as
    mediocre rankings rather than as an error, so it belongs where it can be
    seen.
    """
    settings = state.settings
    llm = check_llm(settings)
    return HealthOut(
        diagnoser=state.diagnoser.name,
        diagnoser_is_real_model=state.diagnoser.name in ("model", "ollama"),
        model_path=str(settings.model_dir),
        database=state.database_backend,
        database_connected=state.database_connected,
        problem_count=len(state.library.problems),
        misconception_count=len(state.library.misconceptions),
        library_size=len(state.library.ranked_misconceptions()),
        llm_configured=llm.configured,
        llm_reachable=llm.reachable,
        llm_detail=llm.detail,
        query_prompt=settings.query_prompt,
        doc_prompt=settings.doc_prompt,
        serve_write_code=settings.serve_write_code,
        unknown_threshold=settings.unknown_threshold,
        probe_gap=settings.probe_gap,
    )


@router.get("/topics", response_model=list[TopicOut])
def topics(state: StateDep) -> list[TopicOut]:
    counts = state.library.topic_counts()
    if state.settings.serve_write_code:
        return [TopicOut(topic=t, problem_count=n) for t, n in counts]

    # write_code problems are not served in this configuration, so they must
    # not be counted in what the start screen offers.
    served: dict[str, int] = {}
    for problem in state.library.problems.values():
        if problem.item_type == "write_code":
            continue
        served[problem.topic] = served.get(problem.topic, 0) + 1
    return [
        TopicOut(topic=topic, problem_count=served[topic])
        for topic, _ in counts
        if served.get(topic)
    ]
