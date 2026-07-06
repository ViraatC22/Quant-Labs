from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

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
