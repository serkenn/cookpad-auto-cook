"""Tests for InventoryDB CRUD operations."""

import pytest

from cookpad.fridge.db.inventory import InventoryDB
from cookpad.fridge.iaeon.models import FoodItem


@pytest.fixture
def db(tmp_path):
    """Create a temporary InventoryDB."""
    inventory = InventoryDB(db_path=tmp_path / "test.db")
    yield inventory
    inventory.close()


@pytest.fixture
def sample_items():
    """Sample food items for testing."""
    return [
        FoodItem(
            name="トマト",
            category="野菜",
            quantity=3.0,
            unit="個",
            price=298,
            purchase_date="2025-01-10",
            estimated_expiry="2025-01-17",
            receipt_id="R001",
        ),
        FoodItem(
            name="鶏もも肉",
            category="肉",
            quantity=1.0,
            unit="パック",
            price=498,
            purchase_date="2025-01-10",
            estimated_expiry="2025-01-13",
            receipt_id="R001",
        ),
    ]


def test_add_food_items(db, sample_items):
    """Add food items and get their IDs."""
    ids = db.add_food_items(sample_items)
    assert len(ids) == 2
    assert all(isinstance(i, int) for i in ids)


def test_get_active_inventory(db, sample_items):
    """Get active inventory items."""
    db.add_food_items(sample_items)
    items = db.get_active_inventory()

    assert len(items) == 2
    assert items[0]["name"] in ("トマト", "鶏もも肉")
    assert items[0]["status"] == "active"


def test_get_active_inventory_empty(db):
    """Empty inventory returns empty list."""
    items = db.get_active_inventory()
    assert items == []


def test_consume_item_partial(db, sample_items):
    """Partially consuming an item keeps it active."""
    ids = db.add_food_items(sample_items)
    # Consume 1 of 3 tomatoes
    db.consume_item(ids[0], amount=1.0)

    items = db.get_active_inventory()
    tomato = next(i for i in items if i["name"] == "トマト")
    assert tomato["consumed"] == 1.0
    assert tomato["status"] == "active"


def test_consume_item_full(db, sample_items):
    """Fully consuming an item sets status to consumed."""
    ids = db.add_food_items(sample_items)
    # Consume all 3 tomatoes
    db.consume_item(ids[0], amount=3.0)

    items = db.get_active_inventory()
    # Tomato should no longer be active
    names = [i["name"] for i in items]
    assert "トマト" not in names


def test_mark_expired(db):
    """mark_expired updates past-expiry items."""
    items = [
        FoodItem(
            name="牛乳",
            category="乳製品",
            quantity=1.0,
            unit="本",
            price=198,
            purchase_date="2025-01-01",
            estimated_expiry="2025-01-05",
            receipt_id="R002",
        ),
    ]
    db.add_food_items(items)
    count = db.mark_expired()
    assert count == 1

    active = db.get_active_inventory()
    assert len(active) == 0


def test_delete_item(db, sample_items):
    """Delete removes an item."""
    ids = db.add_food_items(sample_items)
    db.delete_item(ids[0])

    items = db.get_active_inventory()
    assert len(items) == 1


def test_get_inventory_as_ingredients(db, sample_items):
    """Converts inventory to DetectedIngredient list."""
    db.add_food_items(sample_items)
    ingredients = db.get_inventory_as_ingredients()

    assert len(ingredients) == 2
    assert ingredients[0].confidence == 1.0
    names = {i.name for i in ingredients}
    assert "トマト" in names
    assert "鶏もも肉" in names
