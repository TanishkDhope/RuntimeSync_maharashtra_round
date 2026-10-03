"""Tests for the Ollama GGUF diagnoser."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.diagnosis import build_diagnoser
from app.diagnosis.ollama import OllamaDiagnoser


def test_ollama_diagnoser_ranks_misconceptions(library):
    diagnoser = OllamaDiagnoser(
        library=library,
        model_name="relearn-diagnosis",
        base_url="http://localhost:11434",
    )
    assert diagnoser.name == "ollama"

    problem = library.problem("PO_VAR_02")
    ranked = diagnoser.rank(problem, "5 10 5", "x never changed value")

    assert len(ranked) == len(library.ranked_misconceptions())
    scores = [c.score for c in ranked]
    assert scores == sorted(scores, reverse=True), "Scores must be sorted high to low"
    # Top score should be positive cosine similarity
    assert ranked[0].score > 0.0


def test_build_diagnoser_returns_ollama_diagnoser(settings, library):
    settings.diagnoser = "ollama"
    diagnoser = build_diagnoser(settings, library)
    assert diagnoser.name == "ollama"


def test_build_diagnoser_with_gguf_model_path(settings, library, tmp_path):
    # Create a dummy .gguf file
    gguf_file = tmp_path / "custom-model.gguf"
    gguf_file.write_bytes(b"GGUF_DUMMY_HEADER")

    settings.diagnoser = "model"
    settings.model_path = str(gguf_file)

    diagnoser = build_diagnoser(settings, library)
    assert diagnoser.name == "model"
    assert isinstance(diagnoser, OllamaDiagnoser)


def test_ollama_unreachable_raises_clear_error(settings, library):
    settings.diagnoser = "ollama"
    settings.ollama_base_url = "http://127.0.0.1:59999"  # invalid port

    with pytest.raises(RuntimeError, match="Ollama server is not reachable"):
        build_diagnoser(settings, library)
