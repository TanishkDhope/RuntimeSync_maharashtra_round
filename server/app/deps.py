"""Shared application state and FastAPI dependencies.

The dataset, the diagnoser and the database engine are built once at startup
and held on app.state. Request handlers reach them through these dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from .config import Settings, get_settings
from .data import Library
from .diagnosis.base import Diagnoser


@dataclass
class AppState:
    settings: Settings
    library: Library
    diagnoser: Diagnoser
    engine: object
    database_backend: str
    database_connected: bool


def get_state(request: Request) -> AppState:
    return request.app.state.relearn


def get_library(request: Request) -> Library:
    return get_state(request).library


def get_diagnoser(request: Request) -> Diagnoser:
    return get_state(request).diagnoser


def get_db(request: Request):
    engine = get_state(request).engine
    with Session(engine) as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
StateDep = Annotated[AppState, Depends(get_state)]
LibraryDep = Annotated[Library, Depends(get_library)]
DiagnoserDep = Annotated[Diagnoser, Depends(get_diagnoser)]
DbDep = Annotated[Session, Depends(get_db)]
