"""Meal planning logic using detected ingredients and Cookpad search."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..client import Cookpad
from ..types import Recipe
from .vision import DetectedIngredient

_MEAL_TYPES = [
    ("breakfast", "朝食"),
    ("lunch", "昼食"),
    ("dinner", "夕食"),
]

# Query hints per meal type to steer recipe selection
_MEAL_QUERIES: dict[str, list[str]] = {
    "breakfast": ["簡単 朝ごはん", "朝食", "トースト", "スープ"],
    "lunch": ["ランチ", "丼", "パスタ", "炒め物"],
    "dinner": ["晩ごはん", "メイン", "煮物", "定食"],
}


@dataclass
class Meal:
    meal_type: str  # "breakfast" | "lunch" | "dinner"
    meal_type_ja: str  # "朝食" | "昼食" | "夕食"
    main_dish: Recipe
    side_dishes: list[Recipe] = field(default_factory=list)


@dataclass
class DailyMealPlan:
    date: str
    detected_ingredients: list[str]
    meals: list[Meal] = field(default_factory=list)

    def display(self) -> str:
        """Format meal plan for terminal display."""
        lines: list[str] = []
        lines.append(f"📅 {self.date} の献立")
        lines.append(f"🥬 検出食材: {', '.join(self.detected_ingredients)}")
        lines.append("")

        for meal in self.meals:
            lines.append(f"{'─' * 40}")
            lines.append(f"🍽  {meal.meal_type_ja}")
            lines.append(f"  【主菜】{meal.main_dish.title}")
            if meal.main_dish.cooking_time:
                lines.append(f"         調理時間: {meal.main_dish.cooking_time}")
            for i, side in enumerate(meal.side_dishes, 1):
                lines.append(f"  【副菜{i}】{side.title}")
            lines.append("")

        return "\n".join(lines)


class MealPlanner:
    """Plan daily meals from detected fridge ingredients using Cookpad."""

    def __init__(self, cookpad: Cookpad | None = None) -> None:
        self._cookpad = cookpad
        self._owns_client = cookpad is None

    async def plan_daily(
        self,
        ingredients: list[DetectedIngredient],
        meals_count: int = 3,
    ) -> DailyMealPlan:
        """Create a daily meal plan from detected ingredients."""
        # Filter by confidence and sort
        reliable = sorted(
            [i for i in ingredients if i.confidence >= 0.5],
            key=lambda x: x.confidence,
            reverse=True,
        )
        ingredient_names = [i.name for i in reliable]

        if not ingredient_names:
            raise ValueError(
                "信頼度の高い食材が検出されませんでした。"
                "カメラの位置や照明を調整してみてください。"
            )

        client = self._cookpad
        if client is None:
            client = Cookpad()

        try:
            used_recipe_ids: set[int] = set()
            meals: list[Meal] = []
            meal_types = _MEAL_TYPES[:meals_count]

            for meal_type, meal_type_ja in meal_types:
                main_dish, sides = await self._search_meal(
                    client,
                    ingredient_names,
                    meal_type,
                    used_recipe_ids,
                )
                if main_dish is not None:
                    used_recipe_ids.add(main_dish.id)
                    for s in sides:
                        used_recipe_ids.add(s.id)

                    meals.append(
                        Meal(
                            meal_type=meal_type,
                            meal_type_ja=meal_type_ja,
                            main_dish=main_dish,
                            side_dishes=sides,
                        )
                    )
        finally:
            if self._owns_client and client is not None:
                if client._client is not None:
                    await client._client.aclose()

        return DailyMealPlan(
            date=date.today().isoformat(),
            detected_ingredients=ingredient_names,
            meals=meals,
        )

    async def _search_meal(
        self,
        client: Cookpad,
        ingredient_names: list[str],
        meal_type: str,
        exclude_ids: set[int],
    ) -> tuple[Recipe | None, list[Recipe]]:
        """Search for a main dish + side dishes for one meal."""
        queries = _MEAL_QUERIES.get(meal_type, ["レシピ"])
        top_ingredients = ingredient_names[:5]
        included = ",".join(top_ingredients[:3])

        main_dish: Recipe | None = None
        sides: list[Recipe] = []

        # Search for main dish using top ingredients + meal query
        query = f"{' '.join(top_ingredients[:2])} {queries[0]}"
        try:
            result = await client.search_recipes(
                query,
                order="popular",
                per_page=10,
                included_ingredients=included,
            )
            for recipe in result.recipes:
                if recipe.id not in exclude_ids:
                    main_dish = recipe
                    break
        except Exception:
            pass

        # If main search failed, try with just ingredient names
        if main_dish is None:
            try:
                result = await client.search_recipes(
                    " ".join(top_ingredients[:3]),
                    order="popular",
                    per_page=10,
                )
                for recipe in result.recipes:
                    if recipe.id not in exclude_ids:
                        main_dish = recipe
                        break
            except Exception:
                pass

        if main_dish is None:
            return None, []

        # Search for side dishes using remaining ingredients
        remaining = [n for n in ingredient_names if n not in top_ingredients[:2]]
        side_query_ingredients = remaining[:3] if remaining else top_ingredients[2:4]

        if side_query_ingredients:
            side_query = f"{' '.join(side_query_ingredients[:2])} 副菜"
            try:
                result = await client.search_recipes(
                    side_query,
                    order="popular",
                    per_page=10,
                )
                exclude_now = exclude_ids | {main_dish.id}
                for recipe in result.recipes:
                    if recipe.id not in exclude_now:
                        sides.append(recipe)
                        exclude_now.add(recipe.id)
                        if len(sides) >= 2:
                            break
            except Exception:
                pass

        return main_dish, sides
