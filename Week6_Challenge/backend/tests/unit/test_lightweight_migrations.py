"""Proves the additive-column-sync mechanism actually works against a table
that already exists without the new column — the exact scenario that would
otherwise break every INSERT against an existing app.db/test.db file after a
model gains a new column, since Base.metadata.create_all() never alters an
existing table."""

from sqlalchemy import Column, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.database.lightweight_migrations import sync_missing_columns


class _Base(DeclarativeBase):
    pass


class _Widget(_Base):
    __tablename__ = "widgets_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    # Not present in the physical table created below — simulates a column
    # added to the model after the table already existed on disk.
    new_nullable_field: Mapped[str | None] = mapped_column(String(50), nullable=True)


def test_sync_missing_columns_adds_a_new_nullable_column_to_an_existing_table():
    engine = create_engine("sqlite:///:memory:")
    # Create the table WITHOUT the new column, simulating an old physical schema.
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets_test (id INTEGER PRIMARY KEY, name VARCHAR(50))"))

    inspector = inspect(engine)
    before = {col["name"] for col in inspector.get_columns("widgets_test")}
    assert "new_nullable_field" not in before

    sync_missing_columns(engine, _Base)

    inspector = inspect(engine)
    after = {col["name"] for col in inspector.get_columns("widgets_test")}
    assert "new_nullable_field" in after


def test_sync_missing_columns_does_not_touch_a_brand_new_table():
    """A table that doesn't exist yet is create_all()'s job, not this
    function's — sync_missing_columns should just skip it, not error."""
    engine = create_engine("sqlite:///:memory:")
    # No CREATE TABLE at all — the table doesn't exist yet.
    sync_missing_columns(engine, _Base)  # must not raise
    inspector = inspect(engine)
    assert "widgets_test" not in inspector.get_table_names()


def test_sync_missing_columns_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE widgets_test (id INTEGER PRIMARY KEY, name VARCHAR(50))"))

    sync_missing_columns(engine, _Base)
    sync_missing_columns(engine, _Base)  # running it twice must not error (duplicate ADD COLUMN)

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("widgets_test")]
    assert columns.count("new_nullable_field") == 1
