"""Database engine and session handling.

One DATABASE_URL drives everything. Supabase is just Postgres, so pointing
DATABASE_URL at a Supabase connection string is the whole switch:

    DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

A sqlite:/// URL still works for running offline.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from urllib.parse import urlsplit

from sqlalchemy import inspect, text
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from .config import Settings

log = logging.getLogger("relearn")

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
    add_missing_columns(engine)


def add_missing_columns(engine) -> list[str]:
    """Add columns that models.py has gained since the tables were created.

    create_all() creates missing tables but never alters an existing one, so a
    new column means every insert fails against a database made before it.
    This is the smallest thing that keeps a hackathon database usable: it adds
    columns, and does nothing else. It never drops, renames or retypes
    anything, and never touches a row.

    SQLite only. A Postgres or Supabase database that has drifted needs real
    migrations (Alembic) or to be dropped and recreated; this returns an empty
    list there rather than guessing. Returns what it added, for the log.
    """
    if engine.dialect.name != "sqlite":
        return []

    from . import models  # noqa: F401

    added: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" '
                ddl += column.type.compile(engine.dialect)
                default = _sqlite_default(column)
                if default is not None:
                    ddl += f" DEFAULT {default}"
                connection.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")

    if added:
        log.warning("added missing columns to the existing database: %s", ", ".join(added))
    return added


def _sqlite_default(column) -> str | None:
    """A literal for ADD COLUMN, so existing rows get a sensible value.

    SQLite requires a non-null default when adding a NOT NULL column to a
    table that already has rows.
    """
    arg = getattr(column.default, "arg", None) if column.default is not None else None
    if callable(arg) or arg is None:
        # A default_factory (datetime.now) cannot become a SQL literal, so the
        # column is left nullable and filled in by the application.
        return None if column.nullable else "''"
    if isinstance(arg, bool):
        return "1" if arg else "0"
    if isinstance(arg, (int, float)):
        return str(arg)
    return "'" + str(arg).replace("'", "''") + "'"


def session_factory(engine):
    """A FastAPI-style session dependency bound to one engine.

    Unused by the app, which builds sessions in deps.get_db from app.state.
    Kept because it is the natural seam for a script that needs a session
    without a request (the evaluation script will want one).
    """

    def get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    return get_session
