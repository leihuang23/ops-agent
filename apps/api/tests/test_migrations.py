from __future__ import annotations

import importlib.util
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

import app.models  # noqa: F401
from app.db.base import Base

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "20260706_0009_add_hot_path_indexes.py"
)


def _load_migration_module():
    """Load the Alembic migration file as a Python module.

    Migration filenames start with digits, so they cannot be imported as
    regular Python packages. Use importlib to load the file directly.
    """
    if not MIGRATION_PATH.exists():
        pytest.fail(
            f"Expected migration file not found: {MIGRATION_PATH.name}. "
            "Create apps/api/alembic/versions/20260706_0009_add_hot_path_indexes.py."
        )
    spec = importlib.util.spec_from_file_location(
        "migration_20260706_0009_add_hot_path_indexes", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_in_migration_context(engine: Engine, fn_name: str) -> None:
    """Bind an Alembic Operations context to the engine and invoke fn_name.

    ``Operations.context`` is a context manager that installs the module-level
    ``alembic.op`` proxy for the duration of the block, so the migration's
    ``op.create_index(...)`` / ``op.drop_index(...)`` calls resolve correctly.
    """
    migration = _load_migration_module()
    fn = getattr(migration, fn_name, None)
    if fn is None:
        pytest.fail(f"Migration module does not define {fn_name}()")
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


@pytest.fixture()
def fresh_engine(tmp_path) -> Generator[Engine, None, None]:
    """A SQLite engine with all tables created from the current ORM metadata.

    Composite indexes are NOT declared on the ORM models (they are added only
    by the migration), so the freshly-created schema will not have them yet.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'migration_test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_hot_path_indexes_migration_creates_composite_indexes(
    fresh_engine: Engine,
) -> None:
    _run_in_migration_context(fresh_engine, "upgrade")

    inspector = inspect(fresh_engine)
    invoice_indexes = inspector.get_indexes("invoices")
    subscription_indexes = inspector.get_indexes("subscriptions")

    invoice_names = {ix["name"] for ix in invoice_indexes}
    subscription_names = {ix["name"] for ix in subscription_indexes}

    assert "ix_invoices_status_invoice_date" in invoice_names
    assert "ix_subscriptions_status_canceled_at" in subscription_names

    invoice_target = next(
        ix for ix in invoice_indexes if ix["name"] == "ix_invoices_status_invoice_date"
    )
    assert invoice_target["column_names"] == ["status", "invoice_date"]
    assert not invoice_target["unique"]

    subscription_target = next(
        ix
        for ix in subscription_indexes
        if ix["name"] == "ix_subscriptions_status_canceled_at"
    )
    assert subscription_target["column_names"] == ["status", "canceled_at"]
    assert not subscription_target["unique"]


def test_hot_path_indexes_migration_downgrade_drops_composite_indexes(
    fresh_engine: Engine,
) -> None:
    _run_in_migration_context(fresh_engine, "upgrade")
    _run_in_migration_context(fresh_engine, "downgrade")

    inspector = inspect(fresh_engine)
    invoice_names = {ix["name"] for ix in inspector.get_indexes("invoices")}
    subscription_names = {ix["name"] for ix in inspector.get_indexes("subscriptions")}

    assert "ix_invoices_status_invoice_date" not in invoice_names
    assert "ix_subscriptions_status_canceled_at" not in subscription_names


def test_hot_path_indexes_migration_revision_links_to_previous_head() -> None:
    migration = _load_migration_module()
    assert migration.revision == "20260706_0009"
    assert migration.down_revision == "20260705_0008"
