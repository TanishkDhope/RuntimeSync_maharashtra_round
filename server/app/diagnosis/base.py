"""The one interface the rest of the app knows about.

Two implementations, chosen by the DIAGNOSER config value:
  stub  -> app/diagnosis/stub.py   (no ML, for building and demoing today)
  model -> app/diagnosis/model.py  (the fine-tuned sentence-transformers model)

Nothing outside this package may branch on which one is active, beyond
reporting its name in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..data import Problem


@dataclass(frozen=True)
class Candidate:
    misconception_id: str
    score: float


class Diagnoser(Protocol):
    name: str

    def rank(
        self,
        problem: Problem,
        student_response: str,
        student_explanation: str,
    ) -> list[Candidate]:
        """Candidate misconceptions, sorted by score high to low."""
        ...
