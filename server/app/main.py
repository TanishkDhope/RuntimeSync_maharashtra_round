"""Re:Learn API.

Builds the dataset, the diagnoser and the database connection once at startup,
then serves the quiz loop. Which diagnoser is active comes from one config
value, DIAGNOSER, and is reported by GET /health.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import get_settings
from .data import load_library
from .db import build_engine, create_tables, describe_backend
from .deps import AppState
from .diagnosis import build_diagnoser
from .routers import learners, meta, sessions

log = logging.getLogger("relearn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    library = load_library(settings.data_path)
    log.info(
        "loaded %d problems and %d misconceptions (%d in the ranked library) from %s",
        len(library.problems),
        len(library.misconceptions),
        len(library.ranked_misconceptions()),
        settings.data_path,
    )

    # Raises with a clear message when DIAGNOSER=model but no model exists.
    diagnoser = build_diagnoser(settings, library)
    log.info("diagnoser: %s", diagnoser.name)

    backend = describe_backend(settings)
    engine = build_engine(settings)
    connected = False
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        create_tables(engine)
        connected = True
        log.info("database ready (%s)", backend)
    except Exception as exc:  # noqa: BLE001 - startup must report, not crash
        # A paused Supabase project or missing network should not stop the
        # server from starting: /health reports the failure instead.
        log.error("database unavailable (%s): %s", backend, exc)

    app.state.relearn = AppState(
        settings=settings,
        library=library,
        diagnoser=diagnoser,
        engine=engine,
        database_backend=backend,
        database_connected=connected,
    )
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Re:Learn API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(meta.router)
    app.include_router(learners.router)
    app.include_router(sessions.router)
    return app


app = create_app()
