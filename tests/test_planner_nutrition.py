"""Tests for NutritionAwareMealPlanner and food_items_to_ingredients."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cookpad.fridge.iaeon.models import FoodItem
from cookpad.fridge.planner import (
    NutritionAwareMealPlanner,
    NutritionDailyMealPlan,
    food_items_to_ingredients,
)
from cookpad.fridge.vision import DetectedIngredient
from cookpad.types import Ingredient, Recipe


def test_food_items_to_ingredients():
    """Convert FoodItem list to DetectedIngredient list."""
    items = [
        FoodItem(name="トマト", category="野菜", quantity=3.0),
        FoodItem(name="鶏もも肉", category="肉", quantity=1.0),
    ]
    result = food_items_to_ingredients(items)

    assert len(result) == 2
    assert all(isinstance(r, DetectedIngredient) for r in result)
    assert all(r.confidence == 1.0 for r in result)
    assert result[0].name == "トマト"
    assert result[0].category == "野菜"


def test_food_items_to_ingredients_empty():
    """Empty list returns empty list."""
    assert food_items_to_ingredients([]) == []


def test_nutrition_daily_meal_plan_dataclass():
    """NutritionDailyMealPlan has nutrition and source fields."""
    plan = NutritionDailyMealPlan(
        date="2025-01-10",
        detected_ingredients=["トマト"],
        meals=[],
        daily_nutrition=None,
        source="iaeon",
    )
    assert plan.source == "iaeon"
    assert plan.daily_nutrition is None


@pytest.mark.asyncio
async def test_plan_daily_balanced_requires_input():
    """plan_daily_balanced raises ValueError with no input."""
    planner = NutritionAwareMealPlanner()
    with pytest.raises(ValueError, match="ingredients"):
        await planner.plan_daily_balanced()


@pytest.mark.asyncio
async def test_plan_daily_balanced_with_food_items():
    """plan_daily_balanced accepts food_items parameter."""
    mock_recipe = Recipe(
        id=1,
        title="トマト炒め",
        ingredients=[
            Ingredient(name="トマト", quantity="2個"),
        ],
        steps=[],
    )
    mock_search_result = MagicMock()
    mock_search_result.recipes = [mock_recipe]

    mock_client = AsyncMock()
    mock_client.search_recipes = AsyncMock(return_value=mock_search_result)
    mock_client.get_recipe = AsyncMock(return_value=mock_recipe)
    mock_client._client = None

    planner = NutritionAwareMealPlanner(cookpad=mock_client)

    food_items = [
        FoodItem(name="トマト", category="野菜", quantity=3.0),
    ]

    plan = await planner.plan_daily_balanced(
        food_items=food_items,
        meals_count=1,
    )

    assert isinstance(plan, NutritionDailyMealPlan)
    assert plan.source == "iaeon"
    assert plan.daily_nutrition is not None


def test_nutrition_daily_meal_plan_display_without_nutrition():
    """Display works without nutrition data."""
    plan = NutritionDailyMealPlan(
        date="2025-01-10",
        detected_ingredients=["トマト"],
        meals=[],
        daily_nutrition=None,
    )
    output = plan.display()
    assert "2025-01-10" in output


def test_nutrition_daily_meal_plan_display_with_nutrition():
    """Display includes nutrition section when available."""
    from cookpad.fridge.nutrition.calculator import (
        DailyNutrition,
        MealNutrition,
        NutritionTargets,
    )

    dn = DailyNutrition(
        meals=[
            MealNutrition(
                energy_kcal=600,
                protein=25,
                fat=20,
                carbohydrate=80,
                fiber=5,
                salt_equivalent=2.5,
            ),
        ],
        targets=NutritionTargets(),
    )

    plan = NutritionDailyMealPlan(
        date="2025-01-10",
        detected_ingredients=["トマト"],
        meals=[],
        daily_nutrition=dn,
    )
    output = plan.display()
    assert "栄養バランス" in output
    assert "バランススコア" in output
    assert "PFC比率" in output
