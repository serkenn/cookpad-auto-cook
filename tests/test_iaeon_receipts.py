"""Tests for iAEON receipt processing."""

import pytest

from cookpad.fridge.iaeon.models import FoodItem, ReceiptEntry
from cookpad.fridge.iaeon.receipts import ReceiptFetcher


@pytest.fixture
def fetcher():
    """Create a ReceiptFetcher with a dummy session."""
    from cookpad.fridge.iaeon.auth import IAEONSession

    session = IAEONSession(access_token="dummy", user_id="test")
    return ReceiptFetcher(session)


@pytest.fixture
def sample_entries():
    return [
        ReceiptEntry(
            product_name="TV 北海道産トマト 3個入",
            price=298,
            quantity=1,
            category="",
            receipt_id="R001",
            purchase_date="2025-01-10",
        ),
        ReceiptEntry(
            product_name="BP 鶏もも肉 300g",
            price=498,
            quantity=1,
            category="",
            receipt_id="R001",
            purchase_date="2025-01-10",
        ),
        ReceiptEntry(
            product_name="トップバリュ 牛乳 1000ml",
            price=178,
            quantity=1,
            category="",
            receipt_id="R001",
            purchase_date="2025-01-10",
        ),
        ReceiptEntry(
            product_name="レジ袋",
            price=5,
            quantity=1,
            category="",
            receipt_id="R001",
            purchase_date="2025-01-10",
        ),
        ReceiptEntry(
            product_name="洗剤 詰め替え",
            price=298,
            quantity=1,
            category="",
            receipt_id="R001",
            purchase_date="2025-01-10",
        ),
    ]


class TestNormalizeProductName:
    def test_strip_tv_prefix(self):
        result = ReceiptFetcher._normalize_product_name("TV トマト")
        assert result == "トマト"

    def test_strip_bp_prefix(self):
        result = ReceiptFetcher._normalize_product_name("BP 鶏もも肉")
        assert result == "鶏もも肉"

    def test_strip_topvalu_prefix(self):
        result = ReceiptFetcher._normalize_product_name("トップバリュ 牛乳")
        assert result == "牛乳"

    def test_strip_weight_suffix(self):
        result = ReceiptFetcher._normalize_product_name("鶏もも肉 300g")
        assert result == "鶏もも肉"

    def test_strip_count_suffix(self):
        result = ReceiptFetcher._normalize_product_name("トマト 3個入")
        assert result == "トマト"

    def test_strip_origin_label(self):
        result = ReceiptFetcher._normalize_product_name("北海道産トマト")
        assert "トマト" in result

    def test_empty_string(self):
        result = ReceiptFetcher._normalize_product_name("")
        assert result == ""

    def test_no_changes_needed(self):
        result = ReceiptFetcher._normalize_product_name("卵")
        assert result == "卵"


class TestIsNonFood:
    def test_bag(self):
        assert ReceiptFetcher._is_non_food("レジ袋") is True

    def test_detergent(self):
        assert ReceiptFetcher._is_non_food("洗剤 詰め替え") is True

    def test_food(self):
        assert ReceiptFetcher._is_non_food("トマト") is False


class TestGuessFoodCategory:
    def test_meat(self):
        assert ReceiptFetcher._guess_food_category("鶏もも肉") == "肉"

    def test_fish(self):
        assert ReceiptFetcher._guess_food_category("鮭切り身") == "魚"

    def test_vegetable(self):
        assert ReceiptFetcher._guess_food_category("トマト") == "野菜"

    def test_dairy(self):
        assert ReceiptFetcher._guess_food_category("ヨーグルト") == "乳製品"

    def test_unknown(self):
        assert ReceiptFetcher._guess_food_category("宇宙食") == "その他"


class TestEstimateExpiry:
    def test_meat_3_days(self):
        result = ReceiptFetcher._estimate_expiry("鶏肉", "肉", "2025-01-10")
        assert result == "2025-01-13"

    def test_vegetable_7_days(self):
        result = ReceiptFetcher._estimate_expiry("トマト", "野菜", "2025-01-10")
        assert result == "2025-01-17"

    def test_seasoning_180_days(self):
        result = ReceiptFetcher._estimate_expiry("醤油", "調味料", "2025-01-10")
        assert result == "2025-07-09"

    def test_empty_date(self):
        result = ReceiptFetcher._estimate_expiry("トマト", "野菜", "")
        assert result == ""

    def test_invalid_date(self):
        result = ReceiptFetcher._estimate_expiry("トマト", "野菜", "invalid")
        assert result == ""


class TestExtractFoodItems:
    def test_filters_non_food(self, fetcher, sample_entries):
        items = fetcher.extract_food_items(sample_entries)
        names = [i.name for i in items]
        assert "レジ袋" not in names
        assert all("洗剤" not in n for n in names)

    def test_extracts_food(self, fetcher, sample_entries):
        items = fetcher.extract_food_items(sample_entries)
        assert len(items) == 3  # tomato, chicken, milk

    def test_normalizes_names(self, fetcher, sample_entries):
        items = fetcher.extract_food_items(sample_entries)
        # BP prefix should be stripped
        names = [i.name for i in items]
        assert all(not n.startswith("BP ") for n in names)
        assert all(not n.startswith("TV ") for n in names)

    def test_assigns_categories(self, fetcher, sample_entries):
        items = fetcher.extract_food_items(sample_entries)
        categories = {i.name: i.category for i in items}
        # At least some categories should be assigned
        assert any(c != "その他" for c in categories.values())

    def test_estimates_expiry(self, fetcher, sample_entries):
        items = fetcher.extract_food_items(sample_entries)
        for item in items:
            if item.purchase_date:
                assert item.estimated_expiry != ""
