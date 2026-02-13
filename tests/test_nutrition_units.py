"""Tests for Japanese cooking unit conversion."""

import pytest

from cookpad.fridge.nutrition.units import parse_quantity, to_grams


class TestParseQuantity:
    def test_tablespoon(self):
        amount, unit = parse_quantity("大さじ2")
        assert amount == 2.0
        assert unit == "大さじ"

    def test_teaspoon(self):
        amount, unit = parse_quantity("小さじ1")
        assert amount == 1.0
        assert unit == "小さじ"

    def test_cup(self):
        amount, unit = parse_quantity("カップ1")
        assert amount == 1.0
        assert unit == "カップ"

    def test_counter_piece(self):
        amount, unit = parse_quantity("3個")
        assert amount == 3.0
        assert unit == "個"

    def test_fraction(self):
        amount, unit = parse_quantity("1/2本")
        assert amount == 0.5
        assert unit == "本"

    def test_grams(self):
        amount, unit = parse_quantity("200g")
        assert amount == 200.0
        assert unit == "g"

    def test_special_word(self):
        amount, unit = parse_quantity("少々")
        assert amount == 1.0
        assert unit == "少々"

    def test_empty(self):
        amount, unit = parse_quantity("")
        assert amount == 1.0
        assert unit == ""

    def test_plain_number(self):
        amount, unit = parse_quantity("2")
        assert amount == 2.0


class TestToGrams:
    def test_tablespoon(self):
        assert to_grams(2.0, "大さじ") == 30.0

    def test_teaspoon(self):
        assert to_grams(1.0, "小さじ") == 5.0

    def test_grams_direct(self):
        assert to_grams(200.0, "g") == 200.0

    def test_kg(self):
        assert to_grams(1.5, "kg") == 1500.0

    def test_counter_with_food(self):
        result = to_grams(2.0, "個", "卵")
        assert result == 120.0  # 2 * 60g

    def test_counter_with_tomato(self):
        result = to_grams(1.0, "個", "トマト")
        assert result == 150.0

    def test_counter_unknown_food(self):
        result = to_grams(1.0, "個", "未知の食品")
        assert result == 100.0  # fallback

    def test_special_unit(self):
        result = to_grams(1.0, "少々")
        assert result == 2.0

    def test_cm_unit(self):
        result = to_grams(2.0, "cm")
        assert result == 10.0

    def test_cup(self):
        assert to_grams(1.0, "カップ") == 200.0
