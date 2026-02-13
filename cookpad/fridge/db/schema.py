"""Database schema definitions and migration helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS food_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'その他',
    quantity REAL NOT NULL DEFAULT 1.0,
    unit TEXT NOT NULL DEFAULT '個',
    purchase_date TEXT,
    expiration_date TEXT,
    receipt_id TEXT,
    price INTEGER,
    consumed REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'active',
    mext_food_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_inventory_status ON food_inventory(status);
CREATE INDEX IF NOT EXISTS idx_inventory_expiration ON food_inventory(expiration_date);
CREATE INDEX IF NOT EXISTS idx_inventory_name ON food_inventory(name);

CREATE TABLE IF NOT EXISTS nutrition_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_name TEXT NOT NULL UNIQUE,
    energy_kcal REAL,
    protein REAL,
    fat REAL,
    carbohydrate REAL,
    fiber REAL,
    sodium REAL,
    calcium REAL,
    iron REAL,
    vitamin_a REAL,
    vitamin_c REAL,
    vitamin_d REAL,
    salt_equivalent REAL,
    source TEXT NOT NULL DEFAULT 'mext',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS meal_plan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'camera',
    plan_json TEXT NOT NULL,
    total_calories REAL,
    total_protein REAL,
    total_fat REAL,
    total_carbs REAL,
    pdf_path TEXT,
    drive_file_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_meal_history_date ON meal_plan_history(plan_date);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


def ensure_schema(db_path: str | Path) -> sqlite3.Connection:
    """Open (or create) the database and ensure the schema is up to date.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open sqlite3.Connection with the schema applied.
    """
    db_path = Path(db_path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Check current schema version
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        current_version = row["version"] if row else 0
    except sqlite3.OperationalError:
        current_version = 0

    if current_version < _SCHEMA_VERSION:
        conn.executescript(_DDL)
        # Update version
        conn.execute("DELETE FROM schema_version")
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (_SCHEMA_VERSION,),
        )
        conn.commit()

    return conn
