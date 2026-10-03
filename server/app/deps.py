"""Shared application state and FastAPI dependencies.

The dataset, the diagnoser and the database engine are built once at startup
and held on app.state. Request handlers reach them through these dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from .config import Settings, get_settings
from .data import Library
from .diagnosis.base import Diagnoser


@dataclass
class AppState:
    settings: Settings
    library: Library
    diagnoser: Diagnoser
    # None when the database could not even be constructed at startup, for
    # example a postgresql:// URL with no driver installed. /health reports it.
    engine: object | None
    database_backend: str
    database_connected: bool


def get_state(request: Request) -> AppState:
    return request.app.state.relearn


def get_library(request: Request) -> Library:
    return get_state(request).library


def get_diagnoser(request: Request) -> Diagnoser:
    return get_state(request).diagnoser


def get_db(request: Request):
    state = get_state(request)
    if state.engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"The database ({state.database_backend}) is not available. "
                "See GET /health, and the server log from startup."
            ),
        )
    with Session(state.engine) as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
StateDep = Annotated[AppState, Depends(get_state)]
LibraryDep = Annotated[Library, Depends(get_library)]
DiagnoserDep = Annotated[Diagnoser, Depends(get_diagnoser)]
DbDep = Annotated[Session, Depends(get_db)]
