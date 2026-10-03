"""Probe selection, generation and evidence matching.

The bank is always tried first. Gemini is deliberately a narrow, optional
fallback: it proposes JSON only; this module validates and executes it before
anything reaches a learner.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from .checking import normalise_output
from .config import Settings
from .data import Library, Problem
from .runner import run_probe_program


@dataclass(frozen=True)
class ProbeDraft:
    problem_id: str | None
    topic: str
    program: str
    predictions: dict[str, str]
    source: str
    actual_output: str


def needs_probe(scores: list[float], gap: float) -> bool:
    return len(scores) >= 2 and scores[0] - scores[1] < gap


def find_bank_probe(library: Library, topic: str, candidate_ids: list[str], seen: set[str]) -> ProbeDraft | None:
    wanted = set(candidate_ids)
    # Prefer the same topic and validation/train items, then allow the rest.
    pool = sorted(library.problems.values(), key=lambda p: (p.topic != topic, p.split == "test", p.problem_id))
    for problem in pool:
        if problem.problem_id in seen or problem.item_type != "predict_output":
            continue
        if not wanted.issubset(problem.applicable_misconceptions):
            continue
        predictions = {mid: problem.predicted_outputs.get(mid, "") for mid in candidate_ids}
        if all(mid in problem.predicted_outputs for mid in candidate_ids) and _different(predictions):
            actual = run_probe_program(problem.problem_text, 5.0)
            if actual is not None:
                return ProbeDraft(problem.problem_id, problem.topic, problem.problem_text, predictions, "bank", actual)
    return None


def create_probe(library: Library, settings: Settings, problem: Problem, candidate_ids: list[str], seen: set[str]) -> ProbeDraft | None:
    bank = find_bank_probe(library, problem.topic, candidate_ids, seen)
    if bank:
        return bank
    for _ in range(2):
        generated = generate_gemini_probe(library, settings, problem, candidate_ids)
        if generated and validate_generated_probe(library, settings, generated, candidate_ids):
            return generated
    # A second bank search preserves the documented fallback even if data was
    # changed while an LLM request was in flight.
    return find_bank_probe(library, problem.topic, candidate_ids, seen)


def _different(predictions: dict[str, str]) -> bool:
    return len({normalise_output(value) for value in predictions.values()}) == len(predictions)


def generate_gemini_probe(library: Library, settings: Settings, problem: Problem, candidate_ids: list[str]) -> ProbeDraft | None:
    if settings.llm_provider.lower() not in {"gemini", "google", "google-genai"} or not settings.resolved_llm_api_key:
        return None
    beliefs = [library.misconception(mid) for mid in candidate_ids]
    prompt = """Return JSON only with keys program and candidate_predictions. candidate_predictions is an array of objects with misconception_id and predicted_output. Create a deterministic introductory Python predict-output program (six lines or fewer where possible), no input, imports, randomness, files, network, eval or exec. It must distinguish every listed misconception with a different predicted output.\n\n""" + f"Topic: {problem.topic}\nOriginal context: {problem.problem_text}\nCandidates:\n" + "\n".join(f"- {b.misconception_id}: {b.description}" for b in beliefs)
    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        model = settings.resolved_llm_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": settings.resolved_llm_api_key})
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        row = json.loads(text)
        predictions = {item["misconception_id"]: item["predicted_output"] for item in row["candidate_predictions"]}
        if set(predictions) != set(candidate_ids) or not isinstance(row["program"], str):
            return None
        actual = run_probe_program(row["program"], settings.run_timeout_seconds)
        if actual is None:
            return None
        return ProbeDraft(None, problem.topic, row["program"], predictions, "gemini", actual)
    except Exception:  # provider failures are an expected optional fallback
        return None


def validate_generated_probe(library: Library, settings: Settings, draft: ProbeDraft, candidate_ids: list[str]) -> bool:
    if not _different(draft.predictions) or run_probe_program(draft.program, settings.run_timeout_seconds) is None:
        return False
    return all(_independent_prediction(settings, draft.program, library.misconception(mid).description) == normalise_output(draft.predictions[mid]) for mid in candidate_ids)


def _independent_prediction(settings: Settings, program: str, description: str) -> str | None:
    """Independent call: sees one belief, never another prediction/candidate."""
    if not settings.resolved_llm_api_key:
        return None
    prompt = f"Return JSON only: {{\"predicted_output\": string}}. Predict the output a learner with this misconception would answer.\nProgram:\n{program}\nMisconception: {description}"
    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.resolved_llm_model}:generateContent"
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": settings.resolved_llm_api_key})
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode())
        return normalise_output(json.loads(data["candidates"][0]["content"]["parts"][0]["text"])["predicted_output"])
    except Exception:
        return None


def match_probe_answer(predictions: dict[str, str], response: str) -> tuple[str, str | None]:
    matches = [mid for mid, prediction in predictions.items() if normalise_output(prediction) == normalise_output(response)]
    if len(matches) == 1:
        return "confirmed", matches[0]
    if len(matches) > 1:
        return "ambiguous", None
    return "uncertain", None
