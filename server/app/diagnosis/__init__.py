"""Diagnoser selection.

One config value, DIAGNOSER, decides which implementation serves:

  stub   -> stub.py    no ML, scores from the dataset's predicted_outputs
  model  -> model.py   a fine-tuned sentence-transformers folder
  ollama -> ollama.py  the same fine-tuned model as a GGUF, served by Ollama

There is deliberately no fallback. The brief (s5) requires a clear failure
when a real model is asked for and is not there, because a silent fall back to
the stub would put stub scores on screen under a "Trained model" label.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..data import Library
from .base import Candidate, Diagnoser
from .stub import StubDiagnoser

log = logging.getLogger("relearn")

__all__ = ["Candidate", "Diagnoser", "build_diagnoser"]


def build_diagnoser(settings: Settings, library: Library) -> Diagnoser:
    if settings.diagnoser == "ollama":
        from .ollama import OllamaDiagnoser

        return OllamaDiagnoser(
            library=library,
            model_name=settings.ollama_model,
            base_url=settings.ollama_base_url,
            gguf_path=settings.model_dir,
            query_prompt=settings.query_prompt,
            doc_prompt=settings.doc_prompt,
        )

    if settings.diagnoser == "model":
        model_path = settings.model_dir
        if not model_path.exists():
            raise RuntimeError(
                f"DIAGNOSER=model but nothing exists at MODEL_PATH ({model_path}).\n"
                "Point MODEL_PATH at the folder train_diagnosis_model.py saved "
                "(models/relearn-diagnosis/final) or at a .gguf file, or set "
                "DIAGNOSER=stub.\n"
                "Refusing to fall back to the stub: stub scores must never be "
                "shown under a trained-model label."
            )

        # A .gguf cannot be loaded by sentence-transformers, so it is served
        # through Ollama instead. This is the same trained model either way,
        # so it keeps reporting itself as "model".
        is_gguf = (model_path.is_file() and model_path.suffix == ".gguf") or (
            model_path.is_dir() and any(model_path.glob("*.gguf"))
        )
        if is_gguf:
            from .ollama import OllamaDiagnoser

            log.info("MODEL_PATH '%s' is a GGUF; serving it through Ollama.", model_path)
            return OllamaDiagnoser(
                library=library,
                model_name=settings.ollama_model,
                base_url=settings.ollama_base_url,
                gguf_path=model_path,
                query_prompt=settings.query_prompt,
                doc_prompt=settings.doc_prompt,
                name_override="model",
            )

        from .model import ModelDiagnoser

        return ModelDiagnoser(
            library=library,
            model_dir=model_path,
            query_prompt=settings.query_prompt,
            doc_prompt=settings.doc_prompt,
        )

    return StubDiagnoser(library=library)
