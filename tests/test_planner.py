"""Tests for meal planner (mocked Cookpad API)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cookpad.fridge.planner import (
    AnnotatedIngredient,
    DailyMealPlan,
    Meal,
    MealPlanner,
    _guess_category,
    _match_ingredient,
    annotate_ingredients,
)
from cookpad.fridge.vision import DetectedIngredient
from cookpad.types import Ingredient, Recipe, SearchResponse, Step


def _make_recipe(
    id: int,
    title: str,
    ingredients: list[Ingredient] | None = None,
    steps: list[Step] | None = None,
) -> Recipe:
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


def _make_recipe_with_details(id: int, title: str) -> Recipe:
    """Helper to create a Recipe with ingredients and steps."""
    return _make_recipe(
        id=id,
        title=title,
        ingredients=[
            Ingredient(name="トマト", quantity="2個", id=1),
            Ingredient(name="鶏もも肉", quantity="200g", id=2),
            Ingredient(name="塩", quantity="少々", id=3),
            Ingredient(name="オリーブオイル", quantity="大さじ1", id=4),
        ],
        steps=[
            Step(description="トマトを切る", id=1),
            Step(description="鶏肉を焼く", id=2),
            Step(description="塩で味を調える", id=3),
        ],
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


class TestGuessCategory:
    def test_meat_category(self):
        assert _guess_category("鶏もも肉") == "肉"
        assert _guess_category("豚バラ肉") == "肉"
        assert _guess_category("ベーコン") == "肉"

    def test_vegetable_category(self):
        assert _guess_category("トマト") == "野菜"
        assert _guess_category("にんじん") == "野菜"
        assert _guess_category("ブロッコリー") == "野菜"

    def test_seasoning_category(self):
        assert _guess_category("醤油") == "調味料"
        assert _guess_category("塩") == "調味料"
        assert _guess_category("オリーブオイル") == "調味料"

    def test_egg_category(self):
        assert _guess_category("卵") == "卵"
        assert _guess_category("たまご") == "卵"

    def test_dairy_category(self):
        assert _guess_category("チーズ") == "乳製品"
        assert _guess_category("バター") == "乳製品"

    def test_unknown_category(self):
        assert _guess_category("謎の食材") == "その他"


class TestMatchIngredient:
    def test_exact_match(self):
        assert _match_ingredient("トマト", ["トマト", "鶏肉"]) is True

    def test_partial_match_detected_in_name(self):
        assert _match_ingredient("鶏もも肉", ["鶏肉", "トマト"]) is True

    def test_partial_match_name_in_detected(self):
        assert _match_ingredient("トマト", ["ミニトマト", "鶏肉"]) is True

    def test_no_match(self):
        assert _match_ingredient("バター", ["トマト", "鶏肉"]) is False

    def test_empty_detected(self):
        assert _match_ingredient("トマト", []) is False


class TestAnnotateIngredients:
    def test_basic_annotation(self):
        recipe = _make_recipe_with_details(1, "テスト")
        detected = ["トマト", "鶏肉"]
        result = annotate_ingredients(recipe, detected)

        assert len(result) == 4  # 4 ingredients
        # トマト - detected
        tomato = result[0]
        assert tomato.name == "トマト"
        assert tomato.available_in_fridge is True
        assert tomato.storage_location == "野菜室"

        # 鶏もも肉 - detected (partial match with 鶏肉)
        chicken = result[1]
        assert chicken.name == "鶏もも肉"
        assert chicken.available_in_fridge is True
        assert chicken.storage_location == "チルド室"

        # 塩 - not detected
        salt = result[2]
        assert salt.name == "塩"
        assert salt.available_in_fridge is False
        assert salt.storage_location == "ドアポケット"

    def test_custom_storage_locations(self):
        recipe = _make_recipe(
            1, "テスト",
            ingredients=[Ingredient(name="トマト", quantity="1個")],
        )
        custom = {"野菜": "冷蔵室上段"}
        result = annotate_ingredients(recipe, [], storage_locations=custom)
        assert result[0].storage_location == "冷蔵室上段"

    def test_headline_ingredients_skipped(self):
        recipe = _make_recipe(
            1, "テスト",
            ingredients=[
                Ingredient(name="ソース", quantity="", headline=True),
                Ingredient(name="トマト", quantity="1個"),
            ],
        )
        result = annotate_ingredients(recipe, [])
        assert len(result) == 1
        assert result[0].name == "トマト"


class TestDailyMealPlan:
    def test_shopping_list(self):
        """shopping_list() returns only unavailable ingredients, deduplicated."""
        plan = DailyMealPlan(
            date="2025-01-15",
            detected_ingredients=["トマト"],
            meals=[
                Meal(
                    meal_type="breakfast",
                    meal_type_ja="朝食",
                    main_dish=_make_recipe(1, "テスト"),
                    main_dish_ingredients=[
                        AnnotatedIngredient("トマト", "1個", "野菜室", True),
                        AnnotatedIngredient("塩", "少々", "ドアポケット", False),
                        AnnotatedIngredient("バター", "10g", "チルド室", False),
                    ],
                    side_dish_ingredients=[
                        [
                            AnnotatedIngredient("塩", "少々", "ドアポケット", False),
                            AnnotatedIngredient("砂糖", "大さじ1", "ドアポケット", False),
                        ],
                    ],
                ),
            ],
        )
        shopping = plan.shopping_list()
        names = [s.name for s in shopping]
        assert "トマト" not in names  # available
        assert "塩" in names
        assert "バター" in names
        assert "砂糖" in names
        assert names.count("塩") == 1  # deduplicated

    def test_display_with_ingredients(self):
        """display() includes ingredient tables and steps."""
        recipe = _make_recipe_with_details(1, "トマトチキン")
        plan = DailyMealPlan(
            date="2025-01-15",
            detected_ingredients=["トマト", "鶏肉"],
            meals=[
                Meal(
                    meal_type="breakfast",
                    meal_type_ja="朝食",
                    main_dish=recipe,
                    main_dish_ingredients=[
                        AnnotatedIngredient("トマト", "2個", "野菜室", True),
                        AnnotatedIngredient("鶏もも肉", "200g", "チルド室", True),
                        AnnotatedIngredient("塩", "少々", "ドアポケット", False),
                    ],
                ),
            ],
        )
        text = plan.display()
        assert "2025-01-15" in text
        assert "トマト" in text
        assert "朝食" in text
        assert "トマトチキン" in text
        assert "冷蔵庫にあり" in text
        assert "要購入" in text
        assert "手順:" in text
        assert "トマトを切る" in text

    def test_display_with_shopping_list(self):
        """display() shows shopping list when there are unavailable items."""
        plan = DailyMealPlan(
            date="2025-01-15",
            detected_ingredients=["トマト"],
            meals=[
                Meal(
                    meal_type="breakfast",
                    meal_type_ja="朝食",
                    main_dish=_make_recipe(1, "テスト"),
                    main_dish_ingredients=[
                        AnnotatedIngredient("バター", "10g", "チルド室", False),
                    ],
                ),
            ],
        )
        text = plan.display()
        assert "買い物リスト" in text
        assert "バター" in text

    def test_display_basic(self):
        """display() works with no ingredients/steps (backward compat)."""
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
                _make_recipe_with_details(call_count * 10 + 1, f"レシピ{call_count}A"),
                _make_recipe_with_details(call_count * 10 + 2, f"レシピ{call_count}B"),
                _make_recipe_with_details(call_count * 10 + 3, f"レシピ{call_count}C"),
            ])

        mock_client.search_recipes = mock_search
        mock_client.get_recipe = AsyncMock(
            side_effect=lambda id: _make_recipe_with_details(id, f"詳細レシピ{id}")
        )
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
                _make_recipe_with_details(counter * 100 + i, f"レシピ{counter}_{i}")
                for i in range(5)
            ])

        mock_client.search_recipes = mock_search
        mock_client.get_recipe = AsyncMock(
            side_effect=lambda id: _make_recipe_with_details(id, f"詳細レシピ{id}")
        )
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
                _make_recipe_with_details(counter * 10 + 1, f"レシピ{counter}"),
            ])

        mock_client.search_recipes = mock_search
        mock_client.get_recipe = AsyncMock(
            side_effect=lambda id: _make_recipe_with_details(id, f"詳細レシピ{id}")
        )
        mock_client._client = MagicMock()

        planner = MealPlanner(cookpad=mock_client)
        plan = await planner.plan_daily(_make_ingredients(), meals_count=1)

        assert len(plan.meals) == 1
        assert plan.meals[0].meal_type == "breakfast"

    @pytest.mark.asyncio
    async def test_plan_daily_has_annotated_ingredients(self):
        """Meals should have annotated ingredients after planning."""
        mock_client = AsyncMock()

        async def mock_search(*args, **kwargs):
            return _make_search_response([
                _make_recipe_with_details(1, "トマトチキン"),
            ])

        mock_client.search_recipes = mock_search
        mock_client.get_recipe = AsyncMock(
            side_effect=lambda id: _make_recipe_with_details(id, "トマトチキン")
        )
        mock_client._client = MagicMock()

        planner = MealPlanner(cookpad=mock_client)
        plan = await planner.plan_daily(_make_ingredients(), meals_count=1)

        meal = plan.meals[0]
        assert len(meal.main_dish_ingredients) > 0
        # トマト should be available (detected in fridge)
        tomato_ing = [i for i in meal.main_dish_ingredients if "トマト" in i.name]
        assert len(tomato_ing) > 0
        assert tomato_ing[0].available_in_fridge is True

    @pytest.mark.asyncio
    async def test_plan_daily_with_storage_locations(self):
        """Custom storage_locations are used for annotation."""
        mock_client = AsyncMock()

        async def mock_search(*args, **kwargs):
            return _make_search_response([
                _make_recipe_with_details(1, "テスト"),
            ])

        mock_client.search_recipes = mock_search
        mock_client.get_recipe = AsyncMock(
            side_effect=lambda id: _make_recipe_with_details(id, "テスト")
        )
        mock_client._client = MagicMock()

        custom_locations = {"野菜": "冷蔵室上段", "肉": "冷凍室"}
        planner = MealPlanner(
            cookpad=mock_client, storage_locations=custom_locations
        )
        plan = await planner.plan_daily(_make_ingredients(), meals_count=1)

        meal = plan.meals[0]
        tomato = [i for i in meal.main_dish_ingredients if "トマト" in i.name]
        assert tomato[0].storage_location == "冷蔵室上段"
