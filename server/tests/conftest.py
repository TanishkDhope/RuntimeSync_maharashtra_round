from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.config import Settings  # noqa: E402
from app.data import load_library  # noqa: E402

DATA_DIR = SERVER_DIR.parent / "data"


#: Fields that make a paid outbound call when set. Blanked for the whole
#: suite, see _no_live_providers.
_NETWORK_FIELDS = ("LLM_API_KEY", "VERCEL_API_KEY", "GUARDRAIL_MODEL")


@pytest.fixture(autouse=True)
def _no_live_providers(monkeypatch, request):
    """Keep the suite off the network, whoever builds the Settings.

    Settings reads server/.env for every field a caller does not pass, so a
    developer with real keys in .env had the suite calling Groq and AI Gateway
    for real on every answer - and because data_dir is the shipped /data, the
    generation path appended its output to misconceptions.jsonl. The dataset
    had picked up 43 junk rows this way.

    Pinning the fields on the `settings` fixture is not enough: several tests
    construct their own Settings and bypass it. The environment beats the env
    file in pydantic-settings, so blanking these here covers every call site,
    including ones added later. A test that wants a provider on sets it
    explicitly on its own Settings object.

    Tests marked `integration` are exempt: calling the real provider is the
    whole point of those, and they are deselected by default (pytest.ini).
    """
    if request.node.get_closest_marker("integration"):
        return
    for name in _NETWORK_FIELDS:
        monkeypatch.setenv(name, "")


@pytest.fixture(scope="session")
def library():
    return load_library(DATA_DIR)


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Stub diagnoser, a throwaway SQLite file, short timeout.

    `serve_write_code` is on here although it is off in .env.example, so the
    runner and the write_code half of the flow stay covered. The test that the
    shipped default really excludes them lives in test_flow.py and builds its
    own Settings.

    `llm_api_key` is pinned empty. Settings still reads server/.env for every
    field not passed here, so a developer with a real key in .env had the
    whole suite calling Groq for real and - because data_dir is the shipped
    /data - appending every generated belief to misconceptions.jsonl.

    `guardrail_model` is pinned off for the same reason: left to .env it would
    put a live AI Gateway call in front of every answer in the suite.
    """
    return Settings(
        diagnoser="stub",
        data_dir=str(DATA_DIR),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        session_length=3,
        run_timeout_seconds=3.0,
        serve_write_code=True,
        llm_api_key="",
        llm_model="",
        llm_provider="",
        guardrail_model="",
    )


@pytest.fixture
def client(settings, monkeypatch):
    """A TestClient whose app uses the throwaway settings."""
    from fastapi.testclient import TestClient

    from app import config, main

    # app/deps.py captured this exact function object at import time, so it is
    # the key FastAPI looks up. Overriding a monkeypatched replacement instead
    # would silently leave the real .env settings in play.
    real_get_settings = config.get_settings

    # The lifespan reads settings directly rather than through a dependency.
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    app = main.create_app()
    app.dependency_overrides[real_get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
