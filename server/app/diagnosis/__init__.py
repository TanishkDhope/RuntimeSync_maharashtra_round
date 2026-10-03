"""Diagnoser selection."""

from __future__ import annotations

from ..config import Settings
from ..data import Library
from .base import Candidate, Diagnoser
from .stub import StubDiagnoser

__all__ = ["Candidate", "Diagnoser", "build_diagnoser"]


def build_diagnoser(settings: Settings, library: Library) -> Diagnoser:
    if settings.diagnoser == "model":
        from .model import ModelDiagnoser

        return ModelDiagnoser(
            library=library,
            model_dir=settings.model_dir,
            query_prompt=settings.query_prompt,
            doc_prompt=settings.doc_prompt,
        )
    return StubDiagnoser(library=library)
