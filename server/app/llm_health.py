"""Is the configured LLM actually reachable? (brief s9)

/health previously reported only that a key was present, which says nothing
about whether a generation call would succeed. This asks the provider.

No generation happens here: the check is a cheap metadata request with a short
timeout, because /health is polled by the UI and must stay fast. Nothing in
the app generates text yet - the intervention path ships hand-written
explanations and probes come from the dataset bank - so an unreachable LLM is
reported, not fatal.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Settings

TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class LlmHealth:
    configured: bool
    reachable: bool | None  # None: nothing to reach, or no check for this provider
    detail: str


def check_llm(settings: Settings) -> LlmHealth:
    provider = (settings.llm_provider or "").strip().lower()
    model = settings.resolved_llm_model.strip()

    if not provider or not model:
        return LlmHealth(
            configured=False,
            reachable=None,
            detail=(
                "No LLM configured. Interventions use the hand-written "
                "explanations and probes come from the dataset bank."
            ),
        )

    if provider == "ollama":
        return _check_ollama(settings.ollama_base_url, model)
    if provider in {"gemini", "google", "google-genai"}:
        return _check_gemini(settings.resolved_llm_api_key, model)
    if provider == "groq":
        return _check_groq(settings.llm_api_key, model)

    return LlmHealth(
        configured=bool(settings.llm_api_key),
        reachable=None,
        detail=f"No reachability check is implemented for provider {provider!r}.",
    )


def _check_groq(api_key: str, model: str) -> LlmHealth:
    if not api_key:
        return LlmHealth(False, False, "LLM_API_KEY is empty.")
    
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "relearn/1.0"
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return LlmHealth(True, False, f"Groq rejected the request: HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        return LlmHealth(True, False, f"Groq was not reachable: {exc}")
    
    models = [m.get("id") for m in data.get("data", [])]
    if model in models:
        return LlmHealth(True, True, f"Groq is reachable and {model} exists.")
    return LlmHealth(True, False, f"Groq reachable but {model!r} not found.")

def _check_ollama(base_url: str, model: str) -> LlmHealth:
    """A local Ollama needs no key, so `configured` is true once it answers."""
    try:
        with urllib.request.urlopen(
            f"{base_url.rstrip('/')}/api/tags", timeout=TIMEOUT_SECONDS
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any failure is "not reachable"
        return LlmHealth(True, False, f"Ollama at {base_url} did not answer: {exc}")

    installed = [m.get("name", "") for m in data.get("models", [])]
    if model in installed or f"{model}:latest" in installed:
        return LlmHealth(True, True, f"Ollama is serving {model}.")
    return LlmHealth(
        True,
        False,
        f"Ollama answered but {model!r} is not installed. Have: "
        + (", ".join(installed) or "nothing"),
    )


def _check_gemini(api_key: str, model: str) -> LlmHealth:
    if not api_key:
        return LlmHealth(False, False, "LLM_API_KEY is empty.")
    name = model if model.startswith("models/") else f"models/{model}"
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/{name}",
        headers={"x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        return LlmHealth(True, False, f"Gemini rejected the request: HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        return LlmHealth(True, False, f"Gemini was not reachable: {exc}")
    return LlmHealth(True, True, f"Gemini is reachable and {model} exists.")
