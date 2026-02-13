"""Tests for nutrition calculator."""

import pytest

from cookpad.fridge.nutrition.calculator import (
    DailyNutrition,
    MealNutrition,
    NutritionCalculator,
    NutritionTargets,
)
from cookpad.fridge.nutrition.mext_data import MEXTDatabase
from cookpad.types import Ingredient, Recipe


@pytest.fixture(autouse=True)
def reset_mext():
    MEXTDatabase.reset()
    yield
    MEXTDatabase.reset()


@pytest.fixture
def calculator():
    return NutritionCalculator()


@pytest.fixture
def sample_recipe():
    return Recipe(
        id=1,
        title="トマトと卵の炒め物",
        ingredients=[
            Ingredient(name="トマト", quantity="2個"),
            Ingredient(name="卵", quantity="3個"),
            Ingredient(name="サラダ油", quantity="大さじ1"),
            Ingredient(name="塩", quantity="少々"),
        ],
        steps=[],
        serving="2人分",
    )


def test_calculate_recipe_nutrition(calculator, sample_recipe):
    """Basic recipe nutrition calculation."""
    result = calculator.calculate_recipe_nutrition(sample_recipe)

    assert isinstance(result, MealNutrition)
    assert result.recipe_title == "トマトと卵の炒め物"
    assert result.energy_kcal > 0
    assert result.protein > 0
    assert result.matched_ingredients > 0


def test_serving_division(calculator, sample_recipe):
    """Nutrition is divided by serving count."""
    # 2人分 recipe
    result = calculator.calculate_recipe_nutrition(sample_recipe)

    # Create 1人分 version
    recipe_1p = Recipe(
        id=2,
        title="Same recipe",
        ingredients=sample_recipe.ingredients,
        steps=[],
        serving="1人分",
    )
    result_1p = calculator.calculate_recipe_nutrition(recipe_1p)

    # 1人分 should be roughly double 2人分
    assert result_1p.energy_kcal > result.energy_kcal * 1.5


def test_nutrition_targets_defaults():
    """Default targets match Japanese dietary guidelines."""
    targets = NutritionTargets()
    assert targets.energy_kcal == 2000.0
    assert targets.protein_pct == 15.0
    assert targets.fat_pct == 25.0
    assert targets.carb_pct == 60.0


def test_nutrition_targets_gram_calculations():
    """Target gram calculations are correct."""
    targets = NutritionTargets(energy_kcal=2000)
    # P: 2000 * 15% / 4 = 75g
    assert targets.protein_g == 75.0
    # F: 2000 * 25% / 9 ≈ 55.6g
    assert round(targets.fat_g, 1) == 55.6
    # C: 2000 * 60% / 4 = 300g
    assert targets.carb_g == 300.0


def test_daily_nutrition_totals():
    """DailyNutrition correctly sums meal nutritions."""
    meals = [
        MealNutrition(energy_kcal=500, protein=20, fat=15, carbohydrate=70,
                       fiber=5, salt_equivalent=2.0),
        MealNutrition(energy_kcal=700, protein=30, fat=25, carbohydrate=90,
                       fiber=8, salt_equivalent=3.0),
    ]
    dn = DailyNutrition(meals=meals)

    assert dn.total_energy == 1200
    assert dn.total_protein == 50
    assert dn.total_fat == 40
    assert dn.total_carbs == 160
    assert dn.total_fiber == 13
    assert dn.total_salt == 5.0


def test_daily_nutrition_pfc_percentages():
    """PFC percentages are calculated correctly."""
    meals = [
        MealNutrition(energy_kcal=1000, protein=50, fat=33.3, carbohydrate=125),
    ]
    dn = DailyNutrition(meals=meals)

    # P: 50*4/1000 = 20%
    assert round(dn.protein_pct) == 20
    # F: 33.3*9/1000 ≈ 30%
    assert round(dn.fat_pct) == 30
    # C: 125*4/1000 = 50%
    assert round(dn.carb_pct) == 50


def test_balance_score_perfect():
    """Balance score for perfect PFC match is high."""
    targets = NutritionTargets(energy_kcal=2000)
    # Perfect match: P=15%, F=25%, C=60%
    meals = [
        MealNutrition(
            energy_kcal=2000,
            protein=75,        # 75*4=300 = 15% of 2000
            fat=55.56,         # 55.56*9=500 = 25% of 2000
            carbohydrate=300,  # 300*4=1200 = 60% of 2000
        ),
    ]
    dn = DailyNutrition(meals=meals, targets=targets)
    assert dn.balance_score > 0.9


def test_balance_score_empty():
    """Balance score for empty meals is 0."""
    dn = DailyNutrition(meals=[])
    assert dn.balance_score == 0.0


def test_summary_dict():
    """summary_dict returns serializable dict."""
    meals = [MealNutrition(energy_kcal=500, protein=20, fat=15, carbohydrate=60)]
    dn = DailyNutrition(meals=meals)
    d = dn.summary_dict()

    assert "total_energy_kcal" in d
    assert "balance_score" in d
    assert "targets" in d
    assert isinstance(d["balance_score"], float)


def test_calculate_daily_nutrition(calculator, sample_recipe):
    """calculate_daily_nutrition works with multiple recipes."""
    result = calculator.calculate_daily_nutrition([sample_recipe, sample_recipe])

    assert len(result.meals) == 2
    assert result.total_energy > 0


def test_parse_serving_count():
    """Serving count extraction from various formats."""
    assert NutritionCalculator._parse_serving_count("2人分") == 2.0
    assert NutritionCalculator._parse_serving_count("4人前") == 4.0
    assert NutritionCalculator._parse_serving_count("") == 1.0
    assert NutritionCalculator._parse_serving_count("たっぷり") == 1.0
