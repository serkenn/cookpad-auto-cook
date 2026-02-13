"""Food inventory CRUD operations."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .schema import ensure_schema

if TYPE_CHECKING:
    from ..iaeon.models import FoodItem
    from ..vision import DetectedIngredient


class InventoryDB:
    """Manages the food_inventory table."""

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

    def add_food_items(self, items: list[FoodItem]) -> list[int]:
        """Insert food items from a receipt into the inventory.

        Returns:
            List of inserted row IDs.
        """
        conn = self._get_conn()
        ids: list[int] = []
        for item in items:
            cur = conn.execute(
                """INSERT INTO food_inventory
                   (name, category, quantity, unit, purchase_date,
                    expiration_date, receipt_id, price, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (
                    item.name,
                    item.category,
                    item.quantity,
                    item.unit,
                    item.purchase_date,
                    item.estimated_expiry,
                    item.receipt_id,
                    item.price,
                ),
            )
            ids.append(cur.lastrowid)
        conn.commit()
        return ids

    def get_active_inventory(self) -> list[dict]:
        """Return all items with status='active'."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM food_inventory WHERE status = 'active' ORDER BY expiration_date"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_expiring_soon(self, days: int = 3) -> list[dict]:
        """Return active items expiring within the given number of days."""
        conn = self._get_conn()
        target = date.today().isoformat()
        rows = conn.execute(
            """SELECT * FROM food_inventory
               WHERE status = 'active'
                 AND expiration_date IS NOT NULL
                 AND expiration_date <= date(?, '+' || ? || ' days')
               ORDER BY expiration_date""",
            (target, days),
        ).fetchall()
        return [dict(r) for r in rows]

    def consume_item(self, item_id: int, amount: float = 1.0) -> None:
        """Mark an item as (partially) consumed.

        If consumed >= quantity, status is set to 'consumed'.
        """
        conn = self._get_conn()
        conn.execute(
            """UPDATE food_inventory
               SET consumed = MIN(consumed + ?, quantity),
                   status = CASE
                       WHEN consumed + ? >= quantity THEN 'consumed'
                       ELSE status
                   END,
                   updated_at = datetime('now', 'localtime')
               WHERE id = ?""",
            (amount, amount, item_id),
        )
        conn.commit()

    def mark_expired(self) -> int:
        """Set status='expired' for active items past their expiration_date.

        Returns:
            Number of rows updated.
        """
        conn = self._get_conn()
        today = date.today().isoformat()
        cur = conn.execute(
            """UPDATE food_inventory
               SET status = 'expired',
                   updated_at = datetime('now', 'localtime')
               WHERE status = 'active'
                 AND expiration_date IS NOT NULL
                 AND expiration_date < ?""",
            (today,),
        )
        conn.commit()
        return cur.rowcount

    def get_inventory_as_ingredients(self) -> list[DetectedIngredient]:
        """Convert active inventory to DetectedIngredient list for the planner."""
        from ..vision import DetectedIngredient

        items = self.get_active_inventory()
        return [
            DetectedIngredient(
                name=item["name"],
                confidence=1.0,
                category=item["category"],
            )
            for item in items
        ]

    def delete_item(self, item_id: int) -> None:
        """Delete an inventory item by ID."""
        conn = self._get_conn()
        conn.execute("DELETE FROM food_inventory WHERE id = ?", (item_id,))
        conn.commit()
