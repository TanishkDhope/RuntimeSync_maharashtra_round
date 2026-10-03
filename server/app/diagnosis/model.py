"""The trained diagnoser: a fine-tuned sentence-transformers embedding model.

sentence_transformers is imported lazily so running the stub needs no torch
install. The query text format below must match the training format exactly.
"""

from __future__ import annotations

from pathlib import Path

from ..data import Library, Problem
from .base import Candidate


def build_query_text(
    problem: Problem, student_response: str, student_explanation: str
) -> str:
    """The exact input format the model was trained on (brief s5). Do not reflow."""
    return (
        f"Topic: {problem.topic}\n"
        f"Problem:\n"
        f"{problem.problem_text}\n"
        f"Correct output: {problem.correct_output}\n"
        f"Student response:\n"
        f"{student_response}\n"
        f"Student reason: {student_explanation}"
    )


class ModelDiagnoser:
    name = "model"

    def __init__(
        self,
        library: Library,
        model_dir: Path,
        query_prompt: str = "",
        doc_prompt: str = "",
    ) -> None:
        if not model_dir.exists():
            raise RuntimeError(
                f"DIAGNOSER=model but no model found at {model_dir}.\n"
                "Train the model or point MODEL_PATH at it, or set DIAGNOSER=stub. "
                "Refusing to fall back to the stub silently."
            )
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise RuntimeError(
                "DIAGNOSER=model needs sentence-transformers: "
                "pip install -r requirements-model.txt"
            ) from exc

        self._library = library
        self._query_prompt = query_prompt
        self._doc_prompt = doc_prompt
        # EmbeddingGemma does not support float16.
        self._model = SentenceTransformer(str(model_dir), model_kwargs={"torch_dtype": "float32"})

        self._ids = [m.misconception_id for m in library.ranked_misconceptions()]
        descriptions = [library.misconception(i).description for i in self._ids]
        # Description embeddings never change, so compute them once.
        self._doc_embeddings = self._model.encode(
            descriptions,
            prompt=self._doc_prompt or None,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    def rank(
        self,
        problem: Problem,
        student_response: str,
        student_explanation: str,
    ) -> list[Candidate]:
        query = build_query_text(problem, student_response, student_explanation)
        embedding = self._model.encode(
            [query],
            prompt=self._query_prompt or None,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]
        similarities = self._doc_embeddings @ embedding  # both normalised: cosine
        ranked = sorted(
            (Candidate(misconception_id=i, score=float(s)) for i, s in zip(self._ids, similarities)),
            key=lambda c: -c.score,
        )
        return ranked
