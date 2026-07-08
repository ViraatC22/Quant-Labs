"""Fail if the ORM models and the migrated database schema have drifted.

Run against a database that has had ``alembic upgrade head`` applied (see the
``api-postgres`` CI job). This is a name-level check: every table and column the
ORM declares must exist in the live schema. It deliberately ignores column type
nuance (custom ``Vector``/``GUID`` types reflect inconsistently), so it will not
false-positive on those, while still catching the common failure mode: a column
added to a model without a matching migration.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.db.base import Base
from app.models import domain  # noqa: F401  (registers tables on the metadata)


def find_drift() -> list[str]:
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    live_tables = set(inspector.get_table_names())

    problems: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in live_tables:
            problems.append(f"missing table: {table_name}")
            continue
        live_columns = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in live_columns:
                problems.append(f"missing column: {table_name}.{column.name}")
    engine.dispose()
    return problems


def main() -> int:
    problems = find_drift()
    if problems:
        print("Schema drift detected between ORM models and the migrated database:")
        for problem in problems:
            print(f"  - {problem}")
        print("\nAdd an Alembic migration to reconcile the schema.")
        return 1
    print("No schema drift: models and migrated database agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
