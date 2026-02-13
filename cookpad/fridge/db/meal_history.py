"""Meal plan history storage for tracking past meal plans."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .schema import ensure_schema


class MealHistoryDB:
    """Manages the meal_plan_history table."""

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

    def save_plan(
        self,
        plan_date: str,
        plan_json: dict | str,
        *,
        source: str = "camera",
        total_calories: float | None = None,
        total_protein: float | None = None,
        total_fat: float | None = None,
        total_carbs: float | None = None,
        pdf_path: str | None = None,
        drive_file_id: str | None = None,
    ) -> int:
        """Save a generated meal plan to history.

        Returns:
            The inserted row ID.
        """
        conn = self._get_conn()
        if isinstance(plan_json, dict):
            plan_json = json.dumps(plan_json, ensure_ascii=False)
        cur = conn.execute(
            """INSERT INTO meal_plan_history
               (plan_date, source, plan_json, total_calories, total_protein,
                total_fat, total_carbs, pdf_path, drive_file_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_date,
                source,
                plan_json,
                total_calories,
                total_protein,
                total_fat,
                total_carbs,
                pdf_path,
                drive_file_id,
            ),
        )
        conn.commit()
        return cur.lastrowid

    def get_recent(self, days: int = 7) -> list[dict]:
        """Return meal plans from the last N days."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM meal_plan_history
               WHERE plan_date >= date('now', 'localtime', '-' || ? || ' days')
               ORDER BY plan_date DESC""",
            (days,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("plan_json"):
                try:
                    d["plan_json"] = json.loads(d["plan_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def get_used_recipe_ids(self, days: int = 7) -> set[int]:
        """Extract recipe IDs from recent meal plans to avoid repetition."""
        recent = self.get_recent(days)
        ids: set[int] = set()
        for plan in recent:
            plan_data = plan.get("plan_json", {})
            if isinstance(plan_data, dict):
                for meal in plan_data.get("meals", []):
                    if "main_dish" in meal and "id" in meal["main_dish"]:
                        ids.add(meal["main_dish"]["id"])
                    for side in meal.get("side_dishes", []):
                        if "id" in side:
                            ids.add(side["id"])
        return ids

    def get_by_date(self, plan_date: str) -> list[dict]:
        """Return all meal plans for a specific date."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM meal_plan_history WHERE plan_date = ?",
            (plan_date,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("plan_json"):
                try:
                    d["plan_json"] = json.loads(d["plan_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result
