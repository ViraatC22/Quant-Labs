from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Columns added after the initial SQLite create_all, kept in sync for the
# unmanaged dev/test SQLite path (PostgreSQL uses Alembic migrations instead).
# Each entry: table -> {column: "<sqlite column definition>"}.
_SQLITE_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "trades": {"contract_multiplier": "NUMERIC NOT NULL DEFAULT 1"},
    # label_embedding lands on an already-created dev DB; JSON-backed on SQLite.
    "kg_nodes": {"label_embedding": "JSON"},
}

_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables for databases not managed by Alembic (SQLite dev/test).

    Production runs on PostgreSQL and applies Alembic migrations, so this is a
    no-op there — the tables already exist.
    """
    if not _is_sqlite:
        return

    # Import models so every table is registered on the metadata before create.
    from app.db.base import Base
    from app.models import domain  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """Add columns introduced after a dev/test SQLite DB was first created.

    create_all never alters existing tables, so a local SQLite database from a
    previous schema would be missing newly added columns. This applies those
    additions idempotently; PostgreSQL is untouched (it runs Alembic).
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table, columns in _SQLITE_ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in present:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    )
