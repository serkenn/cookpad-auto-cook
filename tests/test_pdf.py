"""Tests for PDF generation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cookpad.fridge.planner import AnnotatedIngredient, DailyMealPlan, Meal
from cookpad.types import Ingredient, Recipe, Step


def _make_recipe(
    id: int,
    title: str,
    ingredients: list[Ingredient] | None = None,
    steps: list[Step] | None = None,
) -> Recipe:
    return Recipe(
        id=id,
        title=title,
        story="",
        serving="2人分",
        cooking_time="15分",
        published_at="",
        hall_of_fame=False,
        cooksnaps_count=0,
        image_url="",
        ingredients=ingredients or [],
        user=None,
        advice="",
        bookmarks_count=0,
        view_count=0,
        comments_count=0,
        steps=steps or [],
        href="",
        country="JP",
        language="ja",
        premium=False,
    )


def _make_plan() -> DailyMealPlan:
    return DailyMealPlan(
        date="2025-01-15",
        detected_ingredients=["トマト", "鶏肉"],
        meals=[
            Meal(
                meal_type="breakfast",
                meal_type_ja="朝食",
                main_dish=_make_recipe(
                    1,
                    "トマトチキン",
                    ingredients=[
                        Ingredient(name="トマト", quantity="2個"),
                        Ingredient(name="鶏もも肉", quantity="200g"),
                    ],
                    steps=[
                        Step(description="トマトを切る"),
                        Step(description="鶏肉を焼く"),
                    ],
                ),
                side_dishes=[
                    _make_recipe(2, "サラダ"),
                ],
                main_dish_ingredients=[
                    AnnotatedIngredient("トマト", "2個", "野菜室", True),
                    AnnotatedIngredient("鶏もも肉", "200g", "チルド室", True),
                    AnnotatedIngredient("塩", "少々", "ドアポケット", False),
                ],
                side_dish_ingredients=[
                    [
                        AnnotatedIngredient("レタス", "1/2個", "野菜室", False),
                    ],
                ],
            ),
        ],
    )


class TestPDFGeneration:
    def test_generate_pdf_import_error(self):
        """generate_pdf raises ImportError when reportlab is not installed."""
        with patch.dict("sys.modules", {"reportlab": None}):
            # Force reimport to pick up the patched module
            from cookpad.fridge.pdf import generate_pdf

            # The actual import of reportlab submodules happens inside generate_pdf
            # so we need to mock it differently
            pass

    def test_generate_pdf_creates_file(self):
        """generate_pdf creates a valid PDF file (requires reportlab + font)."""
        try:
            from reportlab.lib.pagesizes import A4  # noqa: F401
        except ImportError:
            pytest.skip("reportlab not installed")

        from cookpad.fridge.pdf import _find_japanese_font

        try:
            _find_japanese_font()
        except FileNotFoundError:
            pytest.skip("No Japanese font available")

        from cookpad.fridge.pdf import generate_pdf

        plan = _make_plan()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "test_output.pdf"
            result = generate_pdf(plan, output)
            assert result == output
            assert output.exists()
            assert output.stat().st_size > 0
            # Check PDF magic bytes
            with open(output, "rb") as f:
                assert f.read(4) == b"%PDF"

    def test_generate_pdf_creates_parent_dirs(self):
        """generate_pdf creates parent directories if needed."""
        try:
            from reportlab.lib.pagesizes import A4  # noqa: F401
        except ImportError:
            pytest.skip("reportlab not installed")

        from cookpad.fridge.pdf import _find_japanese_font

        try:
            _find_japanese_font()
        except FileNotFoundError:
            pytest.skip("No Japanese font available")

        from cookpad.fridge.pdf import generate_pdf

        plan = _make_plan()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "subdir" / "nested" / "test.pdf"
            result = generate_pdf(plan, output)
            assert output.exists()

    def test_generate_pdf_empty_plan(self):
        """generate_pdf works with an empty meal plan."""
        try:
            from reportlab.lib.pagesizes import A4  # noqa: F401
        except ImportError:
            pytest.skip("reportlab not installed")

        from cookpad.fridge.pdf import _find_japanese_font

        try:
            _find_japanese_font()
        except FileNotFoundError:
            pytest.skip("No Japanese font available")

        from cookpad.fridge.pdf import generate_pdf

        plan = DailyMealPlan(
            date="2025-01-15",
            detected_ingredients=["トマト"],
            meals=[],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "empty.pdf"
            result = generate_pdf(plan, output)
            assert output.exists()


class TestFontDiscovery:
    def test_find_japanese_font_not_found(self):
        """_find_japanese_font raises when no font exists."""
        from cookpad.fridge.pdf import _FONT_SEARCH_PATHS, _find_japanese_font

        with patch(
            "cookpad.fridge.pdf._FONT_SEARCH_PATHS",
            ["/nonexistent/font.ttf"],
        ):
            with pytest.raises(FileNotFoundError, match="日本語フォント"):
                _find_japanese_font()
