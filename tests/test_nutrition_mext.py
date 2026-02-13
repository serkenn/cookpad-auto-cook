"""Tests for MEXT food composition database."""

import pytest

from cookpad.fridge.nutrition.mext_data import MEXTDatabase, NutrientInfo


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test."""
    MEXTDatabase.reset()
    yield
    MEXTDatabase.reset()


def test_singleton():
    """MEXTDatabase returns the same instance."""
    db1 = MEXTDatabase.instance()
    db2 = MEXTDatabase.instance()
    assert db1 is db2


def test_loads_foods():
    """Database loads food data from JSON."""
    db = MEXTDatabase.instance()
    assert len(db.all_foods) > 0


def test_lookup_by_name_exact():
    """Exact name lookup works."""
    db = MEXTDatabase.instance()
    info = db.lookup_by_name("トマト")
    assert info is not None
    assert info.name == "トマト"
    assert info.energy_kcal == 20


def test_lookup_by_name_substring():
    """Substring matching works."""
    db = MEXTDatabase.instance()
    info = db.lookup_by_name("鶏もも")
    assert info is not None
    assert "鶏もも" in info.name


def test_lookup_by_name_not_found():
    """Unknown food returns None."""
    db = MEXTDatabase.instance()
    info = db.lookup_by_name("宇宙食")
    assert info is None


def test_lookup_by_id():
    """ID-based lookup works."""
    db = MEXTDatabase.instance()
    info = db.lookup_by_id("06153")
    assert info is not None
    assert info.name == "トマト"


def test_search():
    """Search returns matching foods."""
    db = MEXTDatabase.instance()
    results = db.search("鶏")
    assert len(results) > 0
    assert all("鶏" in r.name for r in results)


def test_search_limit():
    """Search respects the limit parameter."""
    db = MEXTDatabase.instance()
    results = db.search("", limit=3)
    assert len(results) <= 3


def test_nutrient_info_fields():
    """NutrientInfo has all expected fields."""
    db = MEXTDatabase.instance()
    info = db.lookup_by_name("卵")
    assert info is not None
    assert info.energy_kcal > 0
    assert info.protein > 0
    assert isinstance(info.fat, (int, float))
    assert isinstance(info.carbohydrate, (int, float))
    assert isinstance(info.salt_equivalent, (int, float))
