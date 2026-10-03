"""The trained diagnoser, served as a GGUF through Ollama's /api/embed.

Ranks the misconception library against the student's response by cosine
similarity, exactly as model.py does with sentence-transformers. The query
text and the two prompts come from the same place as the sentence-transformers
path, so both backends embed the same strings.

Two things here exist to stop the demo lying about which model is running:

* The Ollama tag carries a fingerprint of the .gguf file. Drop a newly trained
  .gguf at MODEL_PATH and the tag changes, so Ollama is made to re-register it
  instead of quietly serving yesterday's weights.
* The .gguf must be the one MODEL_PATH names. No searching nearby folders for
  some other .gguf to load (brief s5).
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

import numpy as np

from ..data import Library, Misconception, Problem
from .base import Candidate
from .model import build_query_text

log = logging.getLogger("relearn")

# Training ran with max_seq_length = 384 (model/train_diagnosis_model.py), so
# sentence-transformers truncated every input at 384 tokens. Ollama is told the
# same limit: embedding the full untruncated text would feed the model inputs
# it never saw in that form.
TRAINING_MAX_TOKENS = 384

_FINGERPRINT_CHUNK = 1 << 20  # 1 MiB


def gguf_fingerprint(path: Path) -> str:
    """A short id that changes whenever the .gguf file changes.

    Size, mtime and the first and last megabyte, rather than a digest of the
    whole file: a 600 MB hash on every startup is not worth the few seconds,
    and this is only used to notice that the file is a different one.
    """
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode())
    digest.update(str(stat.st_mtime_ns).encode())
    with path.open("rb") as handle:
        digest.update(handle.read(_FINGERPRINT_CHUNK))
        if stat.st_size > _FINGERPRINT_CHUNK:
            handle.seek(max(0, stat.st_size - _FINGERPRINT_CHUNK))
            digest.update(handle.read(_FINGERPRINT_CHUNK))
    return digest.hexdigest()[:12]


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
        self._base_url = base_url.rstrip("/")
        self._query_prompt = query_prompt
        self._doc_prompt = doc_prompt

        self._model_tag = self._resolve_model_tag(model_name, gguf_path)

        self._ids = [m.misconception_id for m in library.ranked_misconceptions()]
        descriptions = [
            f"{self._doc_prompt}{library.misconception(i).description}"
            for i in self._ids
        ]
        self._doc_embeddings = _normalise_rows(self._embed(descriptions))

    # --- model registration -------------------------------------------------

    def _resolve_model_tag(self, model_name: str, gguf_path: Path | None) -> str:
        """The exact Ollama tag to embed with, registering the GGUF if needed."""
        available = self._installed_models()

        if gguf_path is None:
            # No file to register from: the caller is pointing at a model that
            # is already in Ollama (this is how the tests drive it).
            if not _has_model(available, model_name):
                raise RuntimeError(
                    f"DIAGNOSER={self.name} wants the Ollama model "
                    f"{model_name!r}, which is not installed, and no "
                    "MODEL_PATH was given to register it from.\n"
                    "Set MODEL_PATH to the .gguf file, or run `ollama create` "
                    "yourself."
                )
            return model_name

        if not gguf_path.is_file() or gguf_path.suffix != ".gguf":
            raise RuntimeError(
                f"DIAGNOSER={self.name} but MODEL_PATH is not a .gguf file: "
                f"{gguf_path}\n"
                "Point MODEL_PATH at the converted model, or set DIAGNOSER=stub. "
                "Refusing to search for some other .gguf: the demo must run the "
                "model you meant."
            )

        tag = f"{model_name}:{gguf_fingerprint(gguf_path)}"
        if _has_model(available, tag):
            log.info("Ollama already serves %s for %s", tag, gguf_path.name)
            return tag

        log.info("Registering %s in Ollama as %s", gguf_path, tag)
        self._create_model_from_gguf(tag, gguf_path)
        return tag

    def _installed_models(self) -> list[str]:
        try:
            request = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(request, timeout=3.0) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"DIAGNOSER={self.name} but the Ollama server is not reachable "
                f"at {self._base_url}.\n"
                "Start it with `ollama serve`, or set DIAGNOSER=stub."
            ) from exc
        return [m.get("name", "") for m in data.get("models", [])]

    def _create_model_from_gguf(self, tag: str, gguf_path: Path) -> None:
        modelfile = f'FROM "{gguf_path.resolve().as_posix()}"\n'
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".Modelfile") as f:
            f.write(modelfile)
            temp_path = Path(f.name)
        try:
            subprocess.run(
                ["ollama", "create", tag, "-f", str(temp_path)],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "The `ollama` command is not on PATH, so the GGUF at "
                f"{gguf_path} cannot be registered. Install the Ollama CLI or "
                "run `ollama create` on the machine that has it."
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(
                f"`ollama create {tag}` failed for {gguf_path}: {detail}"
            ) from exc
        finally:
            temp_path.unlink(missing_ok=True)
        log.info("Created Ollama model %s", tag)

    # --- embedding ----------------------------------------------------------

    def _embed(self, texts: Sequence[str]) -> np.ndarray:
        payload = {
            "model": self._model_tag,
            "input": list(texts),
            "truncate": True,
            "options": {"num_ctx": TRAINING_MAX_TOKENS},
        }
        request = urllib.request.Request(
            f"{self._base_url}/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60.0) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Ollama embedding request failed for {self._model_tag!r}: {exc}"
            ) from exc

        embeddings = np.array(data.get("embeddings") or [], dtype=np.float32)
        if embeddings.ndim != 2 or embeddings.shape[0] != len(texts):
            raise RuntimeError(
                f"Ollama returned {embeddings.shape} embeddings for "
                f"{len(texts)} inputs. Is {self._model_tag!r} an embedding "
                "model?"
            )
        return embeddings

    def rank(
        self,
        problem: Problem,
        student_response: str,
        student_explanation: str,
    ) -> list[Candidate]:
        query = self._query_prompt + build_query_text(
            problem, student_response, student_explanation
        )
        query_embedding = _normalise_rows(self._embed([query]))[0]
        similarities = self._doc_embeddings @ query_embedding
        return sorted(
            (
                Candidate(misconception_id=i, score=float(s))
                for i, s in zip(self._ids, similarities)
            ),
            key=lambda c: -c.score,
        )

    def add_misconception(self, misconception: 'Misconception') -> None:
        self._ids.append(misconception.misconception_id)
        new_desc = f"{self._doc_prompt}{misconception.description}"
        new_embedding = _normalise_rows(self._embed([new_desc]))
        self._doc_embeddings = np.vstack([self._doc_embeddings, new_embedding])


def _normalise_rows(matrix: np.ndarray) -> np.ndarray:
    """Unit-length rows, so a dot product is a cosine similarity."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12
    return matrix / norms


def _has_model(installed: Sequence[str], wanted: str) -> bool:
    return any(name == wanted or name == f"{wanted}:latest" for name in installed)
