"""SQLite-only, Alembic-free schema evolution. `Base.metadata.create_all()`
(called at app startup, see app/main.py) creates any TABLE that doesn't exist
yet, but never adds a COLUMN to a table that already exists from a previous
run — so a model change like adding `Trace.evaluation_run_id` would silently
break every INSERT against an already-created `traces` table with a "no such
column" error. This module closes that gap the same additive way the rest of
this project avoids Alembic: only ever `ADD COLUMN` (never drop/rename/alter
an existing one), only ever nullable columns, so it's safe to run against a
table that already holds real rows.

This is intentionally not a general migration framework — just enough to let
new nullable columns show up on existing SQLite files without a destructive
recreate, which is the one thing this project's "no migrations yet" trade-off
(documented in app/main.py) doesn't otherwise allow.
"""

import logging

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import text

logger = logging.getLogger("app.database")


def sync_missing_columns(engine: Engine, base: type[DeclarativeBase]) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # a brand-new table — create_all() already made it, with every column

            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                if not column.nullable:
                    logger.warning(
                        "Skipping non-nullable new column %s.%s — cannot ADD COLUMN NOT NULL "
                        "without a default on a table that may already have rows.",
                        table.name,
                        column.name,
                    )
                    continue
                col_type = column.type.compile(engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                logger.info("Schema sync: adding missing column %s.%s", table.name, column.name)
                conn.execute(text(ddl))
