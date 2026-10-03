"""Database engine and session handling.

One DATABASE_URL drives everything. Supabase is just Postgres, so pointing
DATABASE_URL at a Supabase connection string is the whole switch:

    DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

A sqlite:/// URL still works for running offline.
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlsplit

from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from .config import Settings

_SUPABASE_TRANSACTION_POOLER_PORT = 6543


def normalise_database_url(url: str) -> str:
    """Accept the URL Supabase hands you and make SQLAlchemy use psycopg 3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def build_engine(settings: Settings):
    url = normalise_database_url(settings.database_url)

    if url.startswith("sqlite"):
        # SQLite objects are bound to the thread that made them; FastAPI's
        # threadpool hands requests to different threads.
        return create_engine(url, connect_args={"check_same_thread": False})

    kwargs: dict = {"pool_pre_ping": True}
    if urlsplit(url).port == _SUPABASE_TRANSACTION_POOLER_PORT:
        # Supabase's transaction pooler multiplexes server connections, so
        # client-side pooling and prepared statements both break on it.
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {"prepare_threshold": None}
    return create_engine(url, **kwargs)


def describe_backend(settings: Settings) -> str:
    url = normalise_database_url(settings.database_url)
    if url.startswith("sqlite"):
        return "sqlite"
    host = urlsplit(url).hostname or ""
    return "supabase" if "supabase" in host else "postgres"


def create_tables(engine) -> None:
    # Importing models registers them on SQLModel.metadata.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def session_factory(engine):
    def get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    return get_session
