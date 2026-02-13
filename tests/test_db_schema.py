"""Tests for database schema creation and migration."""

import sqlite3

import pytest

from cookpad.fridge.db.schema import _SCHEMA_VERSION, ensure_schema


def test_ensure_schema_creates_tables(tmp_path):
    """Schema creates all three tables."""
    db_path = tmp_path / "test.db"
    conn = ensure_schema(db_path)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {row["name"] for row in tables}

    assert "food_inventory" in table_names
    assert "nutrition_cache" in table_names
    assert "meal_plan_history" in table_names
    assert "schema_version" in table_names

    conn.close()


def test_ensure_schema_creates_parent_dirs(tmp_path):
    """Schema creates parent directories if they don't exist."""
    db_path = tmp_path / "sub" / "dir" / "test.db"
    conn = ensure_schema(db_path)
    assert db_path.exists()
    conn.close()


def test_ensure_schema_sets_version(tmp_path):
    """Schema version is set after creation."""
    db_path = tmp_path / "test.db"
    conn = ensure_schema(db_path)

    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row["version"] == _SCHEMA_VERSION

    conn.close()


def test_ensure_schema_idempotent(tmp_path):
    """Calling ensure_schema twice doesn't error."""
    db_path = tmp_path / "test.db"
    conn1 = ensure_schema(db_path)
    conn1.close()

    conn2 = ensure_schema(db_path)
    row = conn2.execute("SELECT version FROM schema_version").fetchone()
    assert row["version"] == _SCHEMA_VERSION
    conn2.close()


def test_ensure_schema_wal_mode(tmp_path):
    """Schema sets WAL journal mode."""
    db_path = tmp_path / "test.db"
    conn = ensure_schema(db_path)

    mode = conn.execute("PRAGMA journal_mode").fetchone()
    assert mode[0] == "wal"

    conn.close()


def test_food_inventory_columns(tmp_path):
    """food_inventory table has expected columns."""
    db_path = tmp_path / "test.db"
    conn = ensure_schema(db_path)

    info = conn.execute("PRAGMA table_info(food_inventory)").fetchall()
    col_names = {row["name"] for row in info}

    expected = {
        "id", "name", "category", "quantity", "unit",
        "purchase_date", "expiration_date", "receipt_id", "price",
        "consumed", "status", "mext_food_id", "created_at", "updated_at",
    }
    assert expected.issubset(col_names)

    conn.close()
