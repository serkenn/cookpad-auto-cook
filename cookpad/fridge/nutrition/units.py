"""Japanese cooking unit to gram conversion utilities."""

from __future__ import annotations

import re

# Standard volume/count units → grams (water-equivalent or general)
_UNIT_TO_GRAMS: dict[str, float] = {
    "小さじ": 5.0,
    "大さじ": 15.0,
    "カップ": 200.0,
    "合": 180.0,
    "ml": 1.0,
    "cc": 1.0,
    "リットル": 1000.0,
    "L": 1000.0,
    "g": 1.0,
    "kg": 1000.0,
}

# Per-food weight for counter words (1個, 1本, 1枚, etc.)
_FOOD_WEIGHTS: dict[str, float] = {
    "卵": 60.0,
    "たまご": 60.0,
    "玉子": 60.0,
    "トマト": 150.0,
    "たまねぎ": 200.0,
    "玉ねぎ": 200.0,
    "じゃがいも": 150.0,
    "にんじん": 150.0,
    "人参": 150.0,
    "きゅうり": 100.0,
    "なす": 80.0,
    "ピーマン": 30.0,
    "パプリカ": 150.0,
    "にんにく": 6.0,  # 1片
    "しょうが": 15.0,  # 1かけ
    "生姜": 15.0,
    "大根": 1000.0,
    "キャベツ": 1000.0,
    "白菜": 2000.0,
    "レタス": 300.0,
    "ブロッコリー": 300.0,
    "かぼちゃ": 1500.0,
    "さつまいも": 250.0,
    "れんこん": 200.0,
    "ごぼう": 150.0,
    "長ねぎ": 100.0,
    "ねぎ": 100.0,
    "バナナ": 120.0,
    "りんご": 300.0,
    "みかん": 80.0,
    "レモン": 100.0,
    "鶏もも肉": 250.0,  # 1枚
    "鶏むね肉": 250.0,
    "鶏ささみ": 50.0,  # 1本
    "豚ロース": 200.0,  # 1枚
    "豚バラ": 200.0,
    "鮭": 80.0,  # 1切れ
    "サーモン": 80.0,
    "豆腐": 300.0,  # 1丁
    "油揚げ": 30.0,  # 1枚
    "厚揚げ": 150.0,
    "ちくわ": 30.0,  # 1本
    "ソーセージ": 20.0,  # 1本
    "ウインナー": 20.0,
    "食パン": 60.0,  # 1枚 (6枚切り)
    "パン": 60.0,
}

# Fraction patterns
_FRACTION_MAP: dict[str, float] = {
    "1/2": 0.5,
    "1/3": 1 / 3,
    "2/3": 2 / 3,
    "1/4": 0.25,
    "3/4": 0.75,
    "半": 0.5,
}

# Regex for quantity parsing: number + unit
_QTY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?(?:/\d+)?|半)?\s*"
    r"(小さじ|大さじ|カップ|合|個|本|枚|丁|切れ|かけ|片|束|袋|パック|缶|"
    r"ml|cc|リットル|L|g|kg|cm)?"
)


def parse_quantity(text: str) -> tuple[float, str]:
    """Parse a Japanese cooking quantity string.

    Args:
        text: e.g. "大さじ2", "1/2本", "3個", "少々"

    Returns:
        (amount, unit) tuple. Defaults to (1.0, "") if unparseable.
    """
    text = text.strip()
    if not text:
        return (1.0, "")

    # Handle special words
    if text in ("少々", "適量", "適宜", "お好みで"):
        return (1.0, text)

    # Try "unit + number" pattern (e.g. 大さじ2)
    for unit_name, grams in _UNIT_TO_GRAMS.items():
        if unit_name in text:
            # Extract the number after/before the unit
            rest = text.replace(unit_name, "").strip()
            amount = _parse_number(rest) if rest else 1.0
            return (amount, unit_name)

    # Try "number + counter" pattern (e.g. 2個, 1/2本)
    m = _QTY_PATTERN.match(text)
    if m:
        num_str, unit = m.group(1), m.group(2)
        amount = _parse_number(num_str) if num_str else 1.0
        return (amount, unit or "")

    return (1.0, "")


def _parse_number(s: str) -> float:
    """Parse a number string that may contain fractions."""
    s = s.strip()
    if not s:
        return 1.0

    if s in _FRACTION_MAP:
        return _FRACTION_MAP[s]

    if "/" in s:
        parts = s.split("/")
        try:
            return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            return 1.0

    try:
        return float(s)
    except ValueError:
        return 1.0


def to_grams(amount: float, unit: str, food_name: str = "") -> float:
    """Convert an amount with unit to grams.

    Args:
        amount: Numeric amount (e.g. 2.0)
        unit: Unit string (e.g. "大さじ", "個", "g")
        food_name: Optional food name for counter-word resolution

    Returns:
        Estimated weight in grams. Returns 0.0 if unable to convert.
    """
    # Direct gram/kg/ml units
    if unit in _UNIT_TO_GRAMS:
        return amount * _UNIT_TO_GRAMS[unit]

    # Counter words: need food_name to resolve
    if unit in ("個", "本", "枚", "丁", "切れ", "かけ", "片", "束", "袋", "パック", "缶"):
        # Look up food-specific weight
        for food_key, weight in _FOOD_WEIGHTS.items():
            if food_key in food_name or food_name in food_key:
                return amount * weight
        # Fallback: rough average for unknown foods
        return amount * 100.0

    # No unit — assume grams if amount is reasonable, else 1 piece
    if not unit:
        if amount >= 5:
            return amount  # Likely already in grams
        return amount * 100.0  # Likely counting pieces

    # Special units
    if unit in ("少々", "適量", "適宜", "お好みで"):
        return 2.0  # Minimal estimate

    if unit == "cm":
        # For things like "しょうが 1cm" — rough estimate
        return amount * 5.0

    return 0.0
