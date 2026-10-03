"""Diagnoser selection."""

from __future__ import annotations

import logging
from pathlib import Path

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
        # Check if MODEL_PATH points to a GGUF file or contains a GGUF file
        is_gguf = (model_path.is_file() and model_path.name.endswith(".gguf")) or (
            model_path.is_dir() and bool(list(model_path.glob("*.gguf")))
        )
        if not model_path.exists():
            # Check default model/ or models/ folder for GGUF fallback
            server_dir = Path(__file__).resolve().parent.parent.parent
            for p in (
                server_dir / "model" / "relearn-diagnosis.gguf",
                server_dir / "models" / "relearn-diagnosis.gguf",
            ):
                if p.exists():
                    model_path = p
                    is_gguf = True
                    break

        if is_gguf:
            from .ollama import OllamaDiagnoser

            log.info("DIAGNOSER=model points to GGUF file '%s'. Using Ollama backend.", model_path)
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
            model_dir=settings.model_dir,
            query_prompt=settings.query_prompt,
            doc_prompt=settings.doc_prompt,
        )

    return StubDiagnoser(library=library)
