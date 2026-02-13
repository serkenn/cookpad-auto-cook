"""Nutrition calculator for recipes and meal plans."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...types import Recipe
from .mext_data import MEXTDatabase, NutrientInfo
from .units import parse_quantity, to_grams


@dataclass
class NutritionTargets:
    """Daily nutrition targets based on Japanese dietary guidelines."""

    energy_kcal: float = 2000.0
    protein_pct: float = 15.0   # % of total energy
    fat_pct: float = 25.0       # % of total energy
    carb_pct: float = 60.0      # % of total energy
    salt_max: float = 7.5       # grams
    fiber_min: float = 21.0     # grams

    @property
    def protein_g(self) -> float:
        """Target protein in grams (4 kcal/g)."""
        return self.energy_kcal * self.protein_pct / 100 / 4

    @property
    def fat_g(self) -> float:
        """Target fat in grams (9 kcal/g)."""
        return self.energy_kcal * self.fat_pct / 100 / 9

    @property
    def carb_g(self) -> float:
        """Target carbs in grams (4 kcal/g)."""
        return self.energy_kcal * self.carb_pct / 100 / 4


@dataclass
class MealNutrition:
    """Aggregated nutrition for a single meal (recipe)."""

    recipe_title: str = ""
    energy_kcal: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbohydrate: float = 0.0
    fiber: float = 0.0
    salt_equivalent: float = 0.0
    calcium: float = 0.0
    iron: float = 0.0
    vitamin_a: float = 0.0
    vitamin_c: float = 0.0
    vitamin_d: float = 0.0
    matched_ingredients: int = 0
    total_ingredients: int = 0


@dataclass
class DailyNutrition:
    """Aggregated nutrition for a full day's meals."""

    meals: list[MealNutrition] = field(default_factory=list)
    targets: NutritionTargets = field(default_factory=NutritionTargets)

    @property
    def total_energy(self) -> float:
        return sum(m.energy_kcal for m in self.meals)

    @property
    def total_protein(self) -> float:
        return sum(m.protein for m in self.meals)

    @property
    def total_fat(self) -> float:
        return sum(m.fat for m in self.meals)

    @property
    def total_carbs(self) -> float:
        return sum(m.carbohydrate for m in self.meals)

    @property
    def total_fiber(self) -> float:
        return sum(m.fiber for m in self.meals)

    @property
    def total_salt(self) -> float:
        return sum(m.salt_equivalent for m in self.meals)

    @property
    def protein_pct(self) -> float:
        """Actual protein % of total energy."""
        if self.total_energy == 0:
            return 0.0
        return (self.total_protein * 4) / self.total_energy * 100

    @property
    def fat_pct(self) -> float:
        """Actual fat % of total energy."""
        if self.total_energy == 0:
            return 0.0
        return (self.total_fat * 9) / self.total_energy * 100

    @property
    def carb_pct(self) -> float:
        """Actual carb % of total energy."""
        if self.total_energy == 0:
            return 0.0
        return (self.total_carbs * 4) / self.total_energy * 100

    @property
    def balance_score(self) -> float:
        """PFC balance score (0.0 - 1.0).

        Measures how close the actual PFC ratio is to the target.
        1.0 = perfect match, 0.0 = completely off.
        """
        if self.total_energy == 0:
            return 0.0

        # Weighted distance for P, F, C percentages
        p_diff = abs(self.protein_pct - self.targets.protein_pct)
        f_diff = abs(self.fat_pct - self.targets.fat_pct)
        c_diff = abs(self.carb_pct - self.targets.carb_pct)

        # Each component can deviate by at most ~60%, so normalize by 60
        max_deviation = 60.0
        raw_score = 1.0 - (p_diff + f_diff + c_diff) / (3 * max_deviation)
        return max(0.0, min(1.0, raw_score))

    def summary_dict(self) -> dict:
        """Return a summary dict for JSON serialization."""
        return {
            "total_energy_kcal": round(self.total_energy, 1),
            "total_protein_g": round(self.total_protein, 1),
            "total_fat_g": round(self.total_fat, 1),
            "total_carbs_g": round(self.total_carbs, 1),
            "total_fiber_g": round(self.total_fiber, 1),
            "total_salt_g": round(self.total_salt, 1),
            "protein_pct": round(self.protein_pct, 1),
            "fat_pct": round(self.fat_pct, 1),
            "carb_pct": round(self.carb_pct, 1),
            "balance_score": round(self.balance_score, 2),
            "targets": {
                "energy_kcal": self.targets.energy_kcal,
                "protein_pct": self.targets.protein_pct,
                "fat_pct": self.targets.fat_pct,
                "carb_pct": self.targets.carb_pct,
            },
        }


class NutritionCalculator:
    """Calculates nutrition for recipes and meal plans."""

    def __init__(self, mext_db: MEXTDatabase | None = None) -> None:
        self._db = mext_db or MEXTDatabase.instance()

    def calculate_recipe_nutrition(self, recipe: Recipe) -> MealNutrition:
        """Calculate total nutrition for a single recipe.

        Estimates serving as 1 person worth by dividing by serving count
        if available.
        """
        result = MealNutrition(recipe_title=recipe.title)
        serving_count = self._parse_serving_count(recipe.serving)

        for ing in recipe.ingredients:
            if ing.headline:
                continue
            result.total_ingredients += 1

            # Parse quantity
            amount, unit = parse_quantity(ing.quantity)
            grams = to_grams(amount, unit, ing.name)
            if grams <= 0:
                continue

            # Look up nutrition per 100g
            info = self._db.lookup_by_name(ing.name)
            if info is None:
                continue

            result.matched_ingredients += 1
            ratio = grams / 100.0  # MEXT data is per 100g

            result.energy_kcal += info.energy_kcal * ratio
            result.protein += info.protein * ratio
            result.fat += info.fat * ratio
            result.carbohydrate += info.carbohydrate * ratio
            result.fiber += info.fiber * ratio
            result.salt_equivalent += info.salt_equivalent * ratio
            result.calcium += info.calcium * ratio
            result.iron += info.iron * ratio
            result.vitamin_a += info.vitamin_a * ratio
            result.vitamin_c += info.vitamin_c * ratio
            result.vitamin_d += info.vitamin_d * ratio

        # Divide by serving count for per-person nutrition
        if serving_count > 1:
            result.energy_kcal /= serving_count
            result.protein /= serving_count
            result.fat /= serving_count
            result.carbohydrate /= serving_count
            result.fiber /= serving_count
            result.salt_equivalent /= serving_count
            result.calcium /= serving_count
            result.iron /= serving_count
            result.vitamin_a /= serving_count
            result.vitamin_c /= serving_count
            result.vitamin_d /= serving_count

        return result

    def calculate_daily_nutrition(
        self,
        recipes: list[Recipe],
        targets: NutritionTargets | None = None,
    ) -> DailyNutrition:
        """Calculate aggregated daily nutrition from a list of recipes."""
        meal_nutritions = [self.calculate_recipe_nutrition(r) for r in recipes]
        return DailyNutrition(
            meals=meal_nutritions,
            targets=targets or NutritionTargets(),
        )

    @staticmethod
    def _parse_serving_count(serving: str) -> float:
        """Extract numeric serving count from a string like '2人分'."""
        if not serving:
            return 1.0
        import re

        m = re.search(r"(\d+(?:\.\d+)?)", serving)
        if m:
            val = float(m.group(1))
            return max(1.0, val)
        return 1.0
