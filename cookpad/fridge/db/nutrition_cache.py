"""Nutrition information cache backed by SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import ensure_schema


class NutritionCacheDB:
    """Caches MEXT nutrition lookup results to avoid repeated searches."""

    def __init__(self, db_path: str | Path = "~/.config/cookpad/inventory.db") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = ensure_schema(self._db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def get(self, food_name: str) -> dict | None:
        """Look up cached nutrition data for a food name.

        Returns:
            dict with nutrition fields, or None if not cached.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM nutrition_cache WHERE food_name = ?",
            (food_name,),
        ).fetchone()
        return dict(row) if row else None

    def put(
        self,
        food_name: str,
        *,
        energy_kcal: float = 0.0,
        protein: float = 0.0,
        fat: float = 0.0,
        carbohydrate: float = 0.0,
        fiber: float = 0.0,
        sodium: float = 0.0,
        calcium: float = 0.0,
        iron: float = 0.0,
        vitamin_a: float = 0.0,
        vitamin_c: float = 0.0,
        vitamin_d: float = 0.0,
        salt_equivalent: float = 0.0,
        source: str = "mext",
    ) -> None:
        """Insert or update a nutrition cache entry."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO nutrition_cache
               (food_name, energy_kcal, protein, fat, carbohydrate,
                fiber, sodium, calcium, iron,
                vitamin_a, vitamin_c, vitamin_d, salt_equivalent, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(food_name) DO UPDATE SET
                 energy_kcal=excluded.energy_kcal,
                 protein=excluded.protein,
                 fat=excluded.fat,
                 carbohydrate=excluded.carbohydrate,
                 fiber=excluded.fiber,
                 sodium=excluded.sodium,
                 calcium=excluded.calcium,
                 iron=excluded.iron,
                 vitamin_a=excluded.vitamin_a,
                 vitamin_c=excluded.vitamin_c,
                 vitamin_d=excluded.vitamin_d,
                 salt_equivalent=excluded.salt_equivalent,
                 source=excluded.source""",
            (
                food_name,
                energy_kcal,
                protein,
                fat,
                carbohydrate,
                fiber,
                sodium,
                calcium,
                iron,
                vitamin_a,
                vitamin_c,
                vitamin_d,
                salt_equivalent,
                source,
            ),
        )
        conn.commit()

    def get_all(self) -> list[dict]:
        """Return all cached nutrition entries."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM nutrition_cache").fetchall()
        return [dict(r) for r in rows]
