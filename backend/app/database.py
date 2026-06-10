"""Database engine, session, and table initialisation."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

logger = logging.getLogger(__name__)


def _normalize_db_url(url: str) -> str:
    """Render/Heroku hand out ``postgres://`` URLs; SQLAlchemy needs
    ``postgresql+psycopg2://``. Normalise so the same code runs locally on
    SQLite and in production on Postgres."""
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_db_url(settings.database_url)
_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread=False; Postgres uses a pooled connection.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
_engine_kwargs: dict = {"echo": False, "connect_args": _connect_args}
if not _is_sqlite:
    _engine_kwargs.update(pool_pre_ping=True, pool_recycle=300)

engine = create_engine(DATABASE_URL, **_engine_kwargs)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Run SQLite column migrations for existing databases
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "")
        db_file = Path(db_path)
        if db_file.exists():
            try:
                from .migration import run_migrations
                added = run_migrations(db_file)
                if added:
                    logger.info("Migration: added %d new column(s)", added)
            except Exception as e:
                logger.warning("Migration warning: %s", e)


def get_session():
    with Session(engine) as session:
        yield session
