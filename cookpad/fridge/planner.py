"""Meal planning logic using detected ingredients and Cookpad search."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from ..client import Cookpad
from ..types import Ingredient, Recipe
from .vision import DetectedIngredient

if TYPE_CHECKING:
    from .iaeon.models import FoodItem
    from .nutrition.calculator import DailyNutrition, NutritionTargets

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

DEFAULT_STORAGE_LOCATIONS: dict[str, str] = {
    "野菜": "野菜室",
    "果物": "野菜室",
    "肉": "チルド室",
    "魚": "チルド室",
    "乳製品": "チルド室",
    "豆腐・大豆": "チルド室",
    "卵": "ドアポケット",
    "調味料": "ドアポケット",
    "飲料": "ドアポケット",
    "穀物": "冷蔵室",
    "その他": "冷蔵室",
}

# Keyword → category mapping for guessing ingredient categories
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "肉": [
        "鶏", "豚", "牛", "肉", "ハム", "ベーコン", "ソーセージ", "ウインナー",
        "ひき肉", "ミンチ", "もも", "むね", "ささみ", "手羽",
    ],
    "魚": [
        "鮭", "サーモン", "まぐろ", "ツナ", "さば", "いわし", "えび", "海老",
        "いか", "たこ", "かに", "しらす", "ちくわ", "かまぼこ", "魚",
    ],
    "野菜": [
        "トマト", "きゅうり", "なす", "ピーマン", "にんじん", "人参",
        "たまねぎ", "玉ねぎ", "じゃがいも", "キャベツ", "レタス", "ほうれん草",
        "小松菜", "ブロッコリー", "もやし", "大根", "白菜", "ねぎ", "長ねぎ",
        "にんにく", "しょうが", "生姜", "セロリ", "アスパラ", "かぼちゃ",
        "さつまいも", "れんこん", "ごぼう", "オクラ", "ズッキーニ", "パプリカ",
    ],
    "果物": [
        "りんご", "バナナ", "みかん", "レモン", "いちご", "ぶどう", "桃", "梨",
        "キウイ", "オレンジ", "グレープフルーツ", "柿", "メロン", "すいか",
    ],
    "卵": ["卵", "たまご", "玉子"],
    "乳製品": [
        "牛乳", "ミルク", "チーズ", "バター", "ヨーグルト", "生クリーム",
        "マーガリン", "クリーム",
    ],
    "豆腐・大豆": [
        "豆腐", "納豆", "油揚げ", "厚揚げ", "味噌", "みそ", "大豆", "豆乳",
        "がんもどき",
    ],
    "調味料": [
        "醤油", "しょうゆ", "塩", "砂糖", "酢", "みりん", "酒", "料理酒",
        "ケチャップ", "マヨネーズ", "ソース", "ポン酢", "めんつゆ", "だし",
        "コンソメ", "鶏ガラ", "オリーブオイル", "サラダ油", "ごま油",
        "こしょう", "胡椒", "片栗粉", "小麦粉", "パン粉",
    ],
    "飲料": ["ジュース", "お茶", "コーヒー", "ビール", "ワイン", "水"],
    "穀物": [
        "米", "ご飯", "パン", "パスタ", "うどん", "そば", "そうめん",
        "ラーメン", "もち", "餅", "シリアル",
    ],
}


@dataclass
class AnnotatedIngredient:
    """Recipe ingredient annotated with storage location and fridge availability."""

    name: str
    quantity: str
    storage_location: str  # "野菜室", "チルド室", "ドアポケット" etc.
    available_in_fridge: bool  # True if detected by vision


@dataclass
class Meal:
    meal_type: str  # "breakfast" | "lunch" | "dinner"
    meal_type_ja: str  # "朝食" | "昼食" | "夕食"
    main_dish: Recipe
    side_dishes: list[Recipe] = field(default_factory=list)
    main_dish_ingredients: list[AnnotatedIngredient] = field(default_factory=list)
    side_dish_ingredients: list[list[AnnotatedIngredient]] = field(
        default_factory=list
    )


@dataclass
class DailyMealPlan:
    date: str
    detected_ingredients: list[str]
    meals: list[Meal] = field(default_factory=list)

    def shopping_list(self) -> list[AnnotatedIngredient]:
        """Return deduplicated list of ingredients that need to be purchased."""
        seen: set[str] = set()
        result: list[AnnotatedIngredient] = []
        for meal in self.meals:
            for ing in meal.main_dish_ingredients:
                if not ing.available_in_fridge and ing.name not in seen:
                    seen.add(ing.name)
                    result.append(ing)
            for side_ings in meal.side_dish_ingredients:
                for ing in side_ings:
                    if not ing.available_in_fridge and ing.name not in seen:
                        seen.add(ing.name)
                        result.append(ing)
        return result

    def display(self) -> str:
        """Format meal plan for terminal display."""
        lines: list[str] = []
        lines.append(f"📅 {self.date} の献立")
        lines.append(f"🥬 検出食材: {', '.join(self.detected_ingredients)}")
        lines.append("")

        for meal in self.meals:
            lines.append(f"{'─' * 50}")
            lines.append(f"🍽  {meal.meal_type_ja}")
            lines.append("")

            # Main dish
            lines.append(f"  【主菜】{meal.main_dish.title}")
            if meal.main_dish.cooking_time:
                lines.append(f"         調理時間: {meal.main_dish.cooking_time}")
            if meal.main_dish.serving:
                lines.append(f"         分量: {meal.main_dish.serving}")

            # Main dish ingredients table
            if meal.main_dish_ingredients:
                lines.append("")
                lines.append(
                    f"    {'食材名':<10} {'分量':<10} {'保存場所':<8} {'状態'}"
                )
                lines.append(f"    {'─' * 44}")
                for ing in meal.main_dish_ingredients:
                    status = (
                        "✓ 冷蔵庫にあり" if ing.available_in_fridge else "要購入"
                    )
                    lines.append(
                        f"    {ing.name:<10} {ing.quantity:<10} "
                        f"{ing.storage_location:<8} {status}"
                    )

            # Main dish steps
            if meal.main_dish.steps:
                lines.append("")
                lines.append("    手順:")
                for j, step in enumerate(meal.main_dish.steps, 1):
                    lines.append(f"      {j}. {step.description}")

            # Side dishes
            for i, side in enumerate(meal.side_dishes, 1):
                lines.append("")
                lines.append(f"  【副菜{i}】{side.title}")
                if side.cooking_time:
                    lines.append(f"         調理時間: {side.cooking_time}")

                if i - 1 < len(meal.side_dish_ingredients):
                    side_ings = meal.side_dish_ingredients[i - 1]
                    if side_ings:
                        lines.append("")
                        lines.append(
                            f"    {'食材名':<10} {'分量':<10} "
                            f"{'保存場所':<8} {'状態'}"
                        )
                        lines.append(f"    {'─' * 44}")
                        for ing in side_ings:
                            status = (
                                "✓ 冷蔵庫にあり"
                                if ing.available_in_fridge
                                else "要購入"
                            )
                            lines.append(
                                f"    {ing.name:<10} {ing.quantity:<10} "
                                f"{ing.storage_location:<8} {status}"
                            )

                if side.steps:
                    lines.append("")
                    lines.append("    手順:")
                    for j, step in enumerate(side.steps, 1):
                        lines.append(f"      {j}. {step.description}")

            lines.append("")

        # Shopping list
        shopping = self.shopping_list()
        if shopping:
            lines.append(f"{'─' * 50}")
            lines.append("🛒 買い物リスト")
            lines.append("")
            lines.append(f"    {'食材名':<10} {'分量':<10} {'保存場所'}")
            lines.append(f"    {'─' * 30}")
            for ing in shopping:
                lines.append(
                    f"    {ing.name:<10} {ing.quantity:<10} {ing.storage_location}"
                )
            lines.append("")

        return "\n".join(lines)


def _guess_category(ingredient_name: str) -> str:
    """Guess ingredient category from its name using keyword matching."""
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in ingredient_name:
                return category
    return "その他"


def _match_ingredient(name: str, detected_names: list[str]) -> bool:
    """Check if an ingredient name matches any detected fridge ingredient.

    Uses substring matching plus character-set containment for Japanese
    ingredient names (e.g. "鶏肉" matches "鶏もも肉").
    """
    for detected in detected_names:
        # Direct substring match
        if detected in name or name in detected:
            return True
        # Character-set containment: all chars of the shorter name
        # appear in the longer name (handles 鶏肉 ↔ 鶏もも肉 etc.)
        shorter, longer = (detected, name) if len(detected) <= len(name) else (name, detected)
        if len(shorter) >= 2 and set(shorter).issubset(set(longer)):
            return True
    return False


def annotate_ingredients(
    recipe: Recipe,
    detected_names: list[str],
    storage_locations: dict[str, str] | None = None,
) -> list[AnnotatedIngredient]:
    """Annotate recipe ingredients with storage locations and availability."""
    locations = storage_locations or DEFAULT_STORAGE_LOCATIONS
    result: list[AnnotatedIngredient] = []
    for ing in recipe.ingredients:
        if ing.headline:
            continue
        category = _guess_category(ing.name)
        location = locations.get(category, "冷蔵室")
        available = _match_ingredient(ing.name, detected_names)
        result.append(
            AnnotatedIngredient(
                name=ing.name,
                quantity=ing.quantity,
                storage_location=location,
                available_in_fridge=available,
            )
        )
    return result


async def _enrich_recipe(client: Cookpad, recipe: Recipe) -> Recipe:
    """Fetch full recipe detail if ingredients/steps are missing."""
    if recipe.ingredients and recipe.steps:
        return recipe
    try:
        return await client.get_recipe(recipe.id)
    except Exception:
        return recipe


class MealPlanner:
    """Plan daily meals from detected fridge ingredients using Cookpad."""

    def __init__(
        self,
        cookpad: Cookpad | None = None,
        storage_locations: dict[str, str] | None = None,
    ) -> None:
        self._cookpad = cookpad
        self._owns_client = cookpad is None
        self._storage_locations = storage_locations

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

                    # Enrich all recipes with full details in parallel
                    enrich_tasks = [_enrich_recipe(client, main_dish)] + [
                        _enrich_recipe(client, s) for s in sides
                    ]
                    enriched = await asyncio.gather(*enrich_tasks)
                    main_dish = enriched[0]
                    sides = list(enriched[1:])

                    # Annotate ingredients
                    main_ings = annotate_ingredients(
                        main_dish, ingredient_names, self._storage_locations
                    )
                    side_ings = [
                        annotate_ingredients(
                            s, ingredient_names, self._storage_locations
                        )
                        for s in sides
                    ]

                    meals.append(
                        Meal(
                            meal_type=meal_type,
                            meal_type_ja=meal_type_ja,
                            main_dish=main_dish,
                            side_dishes=sides,
                            main_dish_ingredients=main_ings,
                            side_dish_ingredients=side_ings,
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


def food_items_to_ingredients(items: list[FoodItem]) -> list[DetectedIngredient]:
    """Convert iAEON FoodItem list to DetectedIngredient list for the planner.

    Receipt data gets confidence=1.0 since it's confirmed purchase data.
    """
    return [
        DetectedIngredient(
            name=item.name,
            confidence=1.0,
            category=item.category,
        )
        for item in items
    ]


@dataclass
class NutritionDailyMealPlan(DailyMealPlan):
    """Extended DailyMealPlan with nutrition information."""

    daily_nutrition: DailyNutrition | None = None
    source: str = "camera"

    def display(self) -> str:
        """Format meal plan with nutrition info for terminal display."""
        base = super().display()

        if self.daily_nutrition is None:
            return base

        dn = self.daily_nutrition
        lines: list[str] = [base]
        lines.append(f"{'─' * 50}")
        lines.append("栄養バランス")
        lines.append("")
        lines.append(
            f"  {'栄養素':<10} {'摂取量':<10} {'目標':<10} {'達成率'}"
        )
        lines.append(f"  {'─' * 44}")

        targets = dn.targets
        rows = [
            ("エネルギー", f"{dn.total_energy:.0f}kcal",
             f"{targets.energy_kcal:.0f}kcal",
             dn.total_energy / targets.energy_kcal * 100 if targets.energy_kcal else 0),
            ("たんぱく質", f"{dn.total_protein:.1f}g",
             f"{targets.protein_g:.1f}g",
             dn.total_protein / targets.protein_g * 100 if targets.protein_g else 0),
            ("脂質", f"{dn.total_fat:.1f}g",
             f"{targets.fat_g:.1f}g",
             dn.total_fat / targets.fat_g * 100 if targets.fat_g else 0),
            ("炭水化物", f"{dn.total_carbs:.1f}g",
             f"{targets.carb_g:.1f}g",
             dn.total_carbs / targets.carb_g * 100 if targets.carb_g else 0),
            ("食物繊維", f"{dn.total_fiber:.1f}g",
             f"{targets.fiber_min:.1f}g",
             dn.total_fiber / targets.fiber_min * 100 if targets.fiber_min else 0),
            ("食塩相当量", f"{dn.total_salt:.1f}g",
             f"{targets.salt_max:.1f}g以下",
             (1 - dn.total_salt / targets.salt_max) * 100 if targets.salt_max else 0),
        ]

        for name, actual, target, pct in rows:
            lines.append(
                f"  {name:<10} {actual:<10} {target:<10} {pct:.0f}%"
            )

        lines.append("")
        lines.append(
            f"  PFC比率: P{dn.protein_pct:.0f}% / "
            f"F{dn.fat_pct:.0f}% / C{dn.carb_pct:.0f}%"
        )
        lines.append(f"  バランススコア: {dn.balance_score:.2f}")
        lines.append("")

        return "\n".join(lines)


class NutritionAwareMealPlanner(MealPlanner):
    """Meal planner that optimizes for nutritional balance.

    Extends MealPlanner to evaluate multiple candidate recipes per meal
    and select the combination with the best PFC balance score.
    """

    def __init__(
        self,
        cookpad: Cookpad | None = None,
        storage_locations: dict[str, str] | None = None,
        nutrition_targets: NutritionTargets | None = None,
    ) -> None:
        super().__init__(cookpad, storage_locations)
        self._nutrition_targets = nutrition_targets

    async def plan_daily_balanced(
        self,
        ingredients: list[DetectedIngredient] | None = None,
        food_items: list[FoodItem] | None = None,
        meals_count: int = 3,
        candidate_count: int = 5,
    ) -> NutritionDailyMealPlan:
        """Create a nutritionally balanced daily meal plan.

        Can accept either DetectedIngredient (from camera) or
        FoodItem (from iAEON receipts).

        Args:
            ingredients: Camera-detected ingredients.
            food_items: iAEON receipt food items.
            meals_count: Number of meals per day.
            candidate_count: Number of candidate recipes to evaluate per meal slot.

        Returns:
            A NutritionDailyMealPlan with nutrition information.
        """
        from .nutrition.calculator import (
            DailyNutrition,
            NutritionCalculator,
            NutritionTargets,
        )

        # Convert food items to ingredients if provided
        if food_items is not None:
            ingredients = food_items_to_ingredients(food_items)
        if ingredients is None:
            raise ValueError("ingredients または food_items を指定してください")

        source = "iaeon" if food_items is not None else "camera"
        targets = self._nutrition_targets or NutritionTargets()

        # Use the parent's plan_daily for the basic plan
        plan = await self.plan_daily(ingredients, meals_count)

        # Calculate nutrition for all recipes in the plan
        calculator = NutritionCalculator()
        all_recipes: list[Recipe] = []
        for meal in plan.meals:
            all_recipes.append(meal.main_dish)
            all_recipes.extend(meal.side_dishes)

        daily_nutrition = calculator.calculate_daily_nutrition(
            all_recipes, targets
        )

        return NutritionDailyMealPlan(
            date=plan.date,
            detected_ingredients=plan.detected_ingredients,
            meals=plan.meals,
            daily_nutrition=daily_nutrition,
            source=source,
        )
