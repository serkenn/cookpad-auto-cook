"""MEXT food composition database loader (singleton)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NutrientInfo:
    """Nutrient information per 100g of edible portion."""

    food_id: str
    name: str
    group: str
    energy_kcal: float
    protein: float
    fat: float
    carbohydrate: float
    fiber: float
    sodium: float
    calcium: float
    iron: float
    vitamin_a: float
    vitamin_b1: float
    vitamin_b2: float
    vitamin_c: float
    vitamin_d: float
    salt_equivalent: float


class MEXTDatabase:
    """Singleton accessor for the MEXT food composition data.

    Usage:
        db = MEXTDatabase.instance()
        info = db.lookup_by_name("トマト")
    """

    _instance: MEXTDatabase | None = None
    _foods: list[NutrientInfo]
    _name_index: dict[str, NutrientInfo]

    def __init__(self) -> None:
        self._foods = []
        self._name_index = {}
        self._load()

    @classmethod
    def instance(cls) -> MEXTDatabase:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def _load(self) -> None:
        data_path = Path(__file__).parent / "data" / "mext_2020_v8.json"
        with open(data_path, encoding="utf-8") as f:
            raw = json.load(f)

        for entry in raw["foods"]:
            info = NutrientInfo(
                food_id=entry["id"],
                name=entry["name"],
                group=entry.get("group", ""),
                energy_kcal=entry.get("energy_kcal", 0),
                protein=entry.get("protein", 0),
                fat=entry.get("fat", 0),
                carbohydrate=entry.get("carbohydrate", 0),
                fiber=entry.get("fiber", 0),
                sodium=entry.get("sodium", 0),
                calcium=entry.get("calcium", 0),
                iron=entry.get("iron", 0),
                vitamin_a=entry.get("vitamin_a", 0),
                vitamin_b1=entry.get("vitamin_b1", 0),
                vitamin_b2=entry.get("vitamin_b2", 0),
                vitamin_c=entry.get("vitamin_c", 0),
                vitamin_d=entry.get("vitamin_d", 0),
                salt_equivalent=entry.get("salt_equivalent", 0),
            )
            self._foods.append(info)
            self._name_index[info.name] = info

    def lookup_by_name(self, name: str) -> NutrientInfo | None:
        """Look up nutrient info by food name.

        Tries exact match first, then substring match, then character-set
        containment (same strategy as planner._match_ingredient).
        """
        # Exact match
        if name in self._name_index:
            return self._name_index[name]

        # Substring match
        for food in self._foods:
            if name in food.name or food.name in name:
                return food

        # Character-set containment
        for food in self._foods:
            shorter, longer = (
                (name, food.name) if len(name) <= len(food.name) else (food.name, name)
            )
            if len(shorter) >= 2 and set(shorter).issubset(set(longer)):
                return food

        return None

    def lookup_by_id(self, food_id: str) -> NutrientInfo | None:
        """Look up by MEXT food ID."""
        for food in self._foods:
            if food.food_id == food_id:
                return food
        return None

    def search(self, query: str, limit: int = 10) -> list[NutrientInfo]:
        """Search foods by name substring."""
        results: list[NutrientInfo] = []
        for food in self._foods:
            if query in food.name:
                results.append(food)
                if len(results) >= limit:
                    break
        return results

    @property
    def all_foods(self) -> list[NutrientInfo]:
        return list(self._foods)
