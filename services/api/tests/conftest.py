import os
import tempfile

import pytest

# Point the app at an isolated SQLite database before any app module (and its
# engine) is imported, so the test suite never touches the dev database.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")
os.environ["AI_ENRICHMENT_MODE"] = "local"
os.environ["RESEARCH_WRITER_MODE"] = "local"


@pytest.fixture(autouse=True)
def _isolate_database():
    """Reset all tables before each test.

    Every test shares one demo user in one SQLite file, so without this the data
    one test creates leaks into the next (e.g. polluting global, confidence-
    ranked recommendation ordering). Truncating per test makes them independent.
    """
    from app.db.base import Base
    from app.db.session import engine, init_db
    from app.models import domain  # noqa: F401  (registers tables)

    # Ensure the schema exists even for test files that never instantiate the
    # app (e.g. pure-function tests), so truncation below has tables to clear.
    init_db()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield
