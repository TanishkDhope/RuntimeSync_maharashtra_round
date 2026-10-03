"""The Ollama GGUF diagnoser.

Most of this file talks to a real Ollama server, so it is marked
`integration` and skipped by the default pytest run (see pytest.ini). These
are the checks to run before demoing the GGUF as "the trained model":

    pytest -m integration

The tests that need no server - the file fingerprint and the refusal to go
looking for some other .gguf - run in the normal suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.diagnosis import build_diagnoser
from app.diagnosis.ollama import OllamaDiagnoser, gguf_fingerprint

MODEL_NAME = "relearn-diagnosis"
BASE_URL = "http://localhost:11434"


# --- no server needed -------------------------------------------------------

def test_the_fingerprint_changes_when_the_file_changes(tmp_path):
    """A newly trained .gguf must not be served under the old tag (review 2.8)."""
    path = tmp_path / "m.gguf"
    path.write_bytes(b"weights v1")
    first = gguf_fingerprint(path)

    path.write_bytes(b"weights v2")
    second = gguf_fingerprint(path)

    assert first != second
    assert len(first) == 12
    assert gguf_fingerprint(path) == second, "the same file must give the same id"


def test_a_missing_model_path_fails_instead_of_falling_back(settings, library):
    """Brief s5: no silent fall back to the stub, and no hunting for another
    .gguf in a nearby folder."""
    settings.diagnoser = "model"
    settings.model_path = "../model/does-not-exist.gguf"

    with pytest.raises(RuntimeError, match="nothing exists at MODEL_PATH"):
        build_diagnoser(settings, library)


def test_a_model_path_that_is_not_a_gguf_is_rejected(settings, library, tmp_path):
    not_a_model = tmp_path / "notes.txt"
    not_a_model.write_text("not a model")
    settings.diagnoser = "ollama"
    settings.model_path = str(not_a_model)

    with pytest.raises(RuntimeError, match="not a .gguf file|not reachable"):
        build_diagnoser(settings, library)


def test_ollama_unreachable_raises_a_clear_error(settings, library):
    settings.diagnoser = "ollama"
    settings.ollama_base_url = "http://127.0.0.1:59999"  # nothing listens here

    with pytest.raises(RuntimeError, match="not reachable"):
        build_diagnoser(settings, library)


# --- needs a running Ollama with the model registered -----------------------

@pytest.mark.integration
def test_the_diagnoser_ranks_the_whole_library(library):
    diagnoser = OllamaDiagnoser(
        library=library, model_name=MODEL_NAME, base_url=BASE_URL
    )
    assert diagnoser.name == "ollama"

    problem = library.problem("PO_VAR_03")
    ranked = diagnoser.rank(problem, "7\n2", "the = checked whether they were equal")

    assert len(ranked) == len(library.ranked_misconceptions())
    scores = [c.score for c in ranked]
    assert scores == sorted(scores, reverse=True), "scores must be sorted high to low"
    assert -1.0 <= scores[0] <= 1.0, "cosine similarity is bounded"


@pytest.mark.integration
def test_held_out_beliefs_are_never_ranked(library):
    diagnoser = OllamaDiagnoser(
        library=library, model_name=MODEL_NAME, base_url=BASE_URL
    )
    held_out = {
        m.misconception_id
        for m in library.misconceptions.values()
        if m.split != "train"
    }
    ranked = diagnoser.rank(library.problem("PO_VAR_02"), "5 10 5", "x never changed")
    assert not held_out.intersection(c.misconception_id for c in ranked)


@pytest.mark.integration
def test_build_diagnoser_registers_the_real_gguf(settings, library):
    """Drives the MODEL_PATH -> Ollama registration path end to end."""
    gguf = Path(__file__).resolve().parent.parent.parent / "model" / "relearn-diagnosis.gguf"
    if not gguf.is_file():
        pytest.skip(f"no GGUF at {gguf}")

    settings.diagnoser = "model"
    settings.model_path = str(gguf)
    diagnoser = build_diagnoser(settings, library)

    assert isinstance(diagnoser, OllamaDiagnoser)
    # A GGUF is still the trained model, so it reports itself as "model".
    assert diagnoser.name == "model"
