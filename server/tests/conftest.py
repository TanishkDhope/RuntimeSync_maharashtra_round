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
    """
    return Settings(
        diagnoser="stub",
        data_dir=str(DATA_DIR),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        session_length=3,
        run_timeout_seconds=3.0,
        serve_write_code=True,
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
