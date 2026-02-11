"""Tests for meal planner (mocked Cookpad API)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cookpad.fridge.planner import DailyMealPlan, Meal, MealPlanner
from cookpad.fridge.vision import DetectedIngredient
from cookpad.types import Recipe, SearchResponse


def _make_recipe(id: int, title: str) -> Recipe:
    """Helper to create a minimal Recipe for testing."""
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
        ingredients=[],
        user=None,
        advice="",
        bookmarks_count=0,
        view_count=0,
        comments_count=0,
        steps=[],
        href="",
        country="JP",
        language="ja",
        premium=False,
    )


def _make_search_response(recipes: list[Recipe]) -> SearchResponse:
    return SearchResponse(
        recipes=recipes,
        total_count=len(recipes),
        next_page=None,
        raw={},
    )


def _make_ingredients() -> list[DetectedIngredient]:
    return [
        DetectedIngredient(name="トマト", confidence=0.95, category="野菜"),
        DetectedIngredient(name="鶏肉", confidence=0.9, category="肉"),
        DetectedIngredient(name="たまねぎ", confidence=0.85, category="野菜"),
        DetectedIngredient(name="卵", confidence=0.8, category="卵"),
        DetectedIngredient(name="にんじん", confidence=0.75, category="野菜"),
    ]


class TestMealPlanner:
    @pytest.mark.asyncio
    async def test_plan_daily_basic(self):
        """MealPlanner returns a DailyMealPlan with meals."""
        mock_client = AsyncMock()

        # Return different recipes for each search call
        call_count = 0
        async def mock_search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_search_response([
                _make_recipe(call_count * 10 + 1, f"レシピ{call_count}A"),
                _make_recipe(call_count * 10 + 2, f"レシピ{call_count}B"),
                _make_recipe(call_count * 10 + 3, f"レシピ{call_count}C"),
            ])

        mock_client.search_recipes = mock_search
        mock_client._client = MagicMock()

        planner = MealPlanner(cookpad=mock_client)
        plan = await planner.plan_daily(_make_ingredients())

        assert isinstance(plan, DailyMealPlan)
        assert len(plan.detected_ingredients) == 5
        assert len(plan.meals) > 0
        for meal in plan.meals:
            assert meal.main_dish is not None
            assert meal.meal_type in ("breakfast", "lunch", "dinner")

    @pytest.mark.asyncio
    async def test_plan_daily_no_duplicates(self):
        """Meals should not share the same recipe."""
        mock_client = AsyncMock()

        counter = 0
        async def mock_search(*args, **kwargs):
            nonlocal counter
            counter += 1
            return _make_search_response([
                _make_recipe(counter * 100 + i, f"レシピ{counter}_{i}")
                for i in range(5)
            ])

        mock_client.search_recipes = mock_search
        mock_client._client = MagicMock()

        planner = MealPlanner(cookpad=mock_client)
        plan = await planner.plan_daily(_make_ingredients())

        all_ids = []
        for meal in plan.meals:
            all_ids.append(meal.main_dish.id)
            for side in meal.side_dishes:
                all_ids.append(side.id)
        # No duplicate IDs
        assert len(all_ids) == len(set(all_ids))

    @pytest.mark.asyncio
    async def test_plan_daily_filters_low_confidence(self):
        """Ingredients below 0.5 confidence are excluded."""
        mock_client = AsyncMock()
        mock_client.search_recipes = AsyncMock(
            return_value=_make_search_response([_make_recipe(1, "テスト")])
        )
        mock_client._client = MagicMock()

        low_conf = [
            DetectedIngredient(name="何か", confidence=0.3, category="その他"),
        ]
        planner = MealPlanner(cookpad=mock_client)
        with pytest.raises(ValueError, match="信頼度"):
            await planner.plan_daily(low_conf)

    @pytest.mark.asyncio
    async def test_plan_daily_custom_meals_count(self):
        """Can request fewer meals."""
        mock_client = AsyncMock()

        counter = 0
        async def mock_search(*args, **kwargs):
            nonlocal counter
            counter += 1
            return _make_search_response([
                _make_recipe(counter * 10 + 1, f"レシピ{counter}"),
            ])

        mock_client.search_recipes = mock_search
        mock_client._client = MagicMock()

        planner = MealPlanner(cookpad=mock_client)
        plan = await planner.plan_daily(_make_ingredients(), meals_count=1)

        assert len(plan.meals) == 1
        assert plan.meals[0].meal_type == "breakfast"


class TestDailyMealPlan:
    def test_display(self):
        """display() returns a formatted string."""
        plan = DailyMealPlan(
            date="2025-01-15",
            detected_ingredients=["トマト", "鶏肉"],
            meals=[
                Meal(
                    meal_type="breakfast",
                    meal_type_ja="朝食",
                    main_dish=_make_recipe(1, "トマトスープ"),
                    side_dishes=[_make_recipe(2, "サラダ")],
                ),
            ],
        )
        text = plan.display()
        assert "2025-01-15" in text
        assert "トマト" in text
        assert "朝食" in text
        assert "トマトスープ" in text
        assert "サラダ" in text
