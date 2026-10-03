"""The trained diagnoser backed by an Ollama model (e.g. relearn-diagnosis.gguf).

Uses Ollama's REST API (/api/embed) for generating embeddings of problem queries
and misconception descriptions, ranking candidate misconceptions by cosine similarity.
"""

from __future__ import annotations

import json
import logging

from pathlib import Path
import subprocess
from typing import Sequence
import urllib.error
import urllib.request

import numpy as np

from ..data import Library, Problem
from .base import Candidate
from .model import build_query_text

log = logging.getLogger("relearn")


class OllamaDiagnoser:
    name = "ollama"

    def __init__(
        self,
        library: Library,
        model_name: str = "relearn-diagnosis",
        base_url: str = "http://localhost:11434",
        gguf_path: Path | None = None,
        query_prompt: str = "",
        doc_prompt: str = "",
        name_override: str | None = None,
    ) -> None:
        if name_override:
            self.name = name_override
        self._library = library
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._query_prompt = query_prompt
        self._doc_prompt = doc_prompt

        self._ensure_ollama_and_model(gguf_path)

        self._ids = [m.misconception_id for m in library.ranked_misconceptions()]
        descriptions = [
            f"{self._doc_prompt}{library.misconception(i).description}"
            if self._doc_prompt
            else library.misconception(i).description
            for i in self._ids
        ]

        # Pre-compute and normalize description embeddings
        raw_doc_embeddings = self._embed(descriptions)
        norms = np.linalg.norm(raw_doc_embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1e-12
        self._doc_embeddings = raw_doc_embeddings / norms

    def _ensure_ollama_and_model(self, gguf_path: Path | None) -> None:
        """Verify Ollama is reachable and model exists, creating it from GGUF if needed."""
        tags_url = f"{self._base_url}/api/tags"
        try:
            req = urllib.request.Request(tags_url)
            with urllib.request.urlopen(req, timeout=3.0) as res:
                data = json.loads(res.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
        except Exception as exc:
            raise RuntimeError(
                f"DIAGNOSER={self.name} but Ollama server is not reachable at {self._base_url}.\n"
                "Please make sure Ollama is running (`ollama serve`)."
            ) from exc

        has_model = any(
            m == self._model_name or m.startswith(f"{self._model_name}:")
            for m in models
        )

        if not has_model:
            target_gguf = self._find_gguf_file(gguf_path)
            if target_gguf and target_gguf.exists():
                log.info("Registering GGUF file '%s' into Ollama as '%s'...", target_gguf, self._model_name)
                self._create_model_from_gguf(target_gguf)
            else:
                raise RuntimeError(
                    f"DIAGNOSER={self.name} requested Ollama model '{self._model_name}', "
                    f"but model is not loaded in Ollama and no GGUF file was found at {gguf_path}.\n"
                    "Place your .gguf file in the model/ or models/ folder, or run `ollama create`."
                )

    def _find_gguf_file(self, path_hint: Path | None) -> Path | None:
        if path_hint:
            if path_hint.is_file() and path_hint.name.endswith(".gguf"):
                return path_hint
            if path_hint.is_dir():
                ggufs = list(path_hint.glob("*.gguf"))
                if ggufs:
                    return ggufs[0]

        # Common fallback locations relative to server directory
        server_dir = Path(__file__).resolve().parent.parent.parent
        candidates = [
            server_dir / "model" / "relearn-diagnosis.gguf",
            server_dir / "models" / "relearn-diagnosis.gguf",
            server_dir / "model" / "relearn-diagnosis" / "final.gguf",
            server_dir / "models" / "relearn-diagnosis" / "final.gguf",
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return None

    def _create_model_from_gguf(self, gguf_path: Path) -> None:
        posix_path = gguf_path.resolve().as_posix()
        modelfile_content = f'FROM "{posix_path}"\n'
        try:
            subprocess.run(
                ["ollama", "create", self._model_name, "-f", "-"],
                input=modelfile_content,
                text=True,
                capture_output=True,
                check=True,
            )
            log.info("Successfully created Ollama model '%s'", self._model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create Ollama model '{self._model_name}' from '{gguf_path}': {exc}"
            ) from exc

    def _embed(self, texts: Sequence[str]) -> np.ndarray:
        url = f"{self._base_url}/api/embed"
        payload = {
            "model": self._model_name,
            "input": list(texts),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as res:
                data = json.loads(res.read().decode("utf-8"))
                embeddings = data.get("embeddings", [])
                return np.array(embeddings, dtype=np.float32)
        except Exception as exc:
            raise RuntimeError(
                f"Ollama embedding request failed for model '{self._model_name}': {exc}"
            ) from exc

    def rank(
        self,
        problem: Problem,
        student_response: str,
        student_explanation: str,
    ) -> list[Candidate]:
        raw_query = build_query_text(problem, student_response, student_explanation)
        query = f"{self._query_prompt}{raw_query}" if self._query_prompt else raw_query

        raw_query_emb = self._embed([query])[0]
        norm = float(np.linalg.norm(raw_query_emb))
        if norm == 0:
            norm = 1e-12
        query_emb = raw_query_emb / norm

        similarities = self._doc_embeddings @ query_emb
        ranked = sorted(
            (Candidate(misconception_id=i, score=float(s)) for i, s in zip(self._ids, similarities)),
            key=lambda c: -c.score,
        )
        return ranked
