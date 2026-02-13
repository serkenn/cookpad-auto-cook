"""Smart fridge meal planning module for Cookpad."""

from .camera import CameraCapture, FridgeCamera
from .config import (
    DatabaseConfig,
    FridgeConfig,
    GDriveConfig,
    IAEONConfig,
    NutritionConfig,
    PrinterConfig,
    load_config,
)
from .planner import (
    AnnotatedIngredient,
    DailyMealPlan,
    Meal,
    MealPlanner,
    NutritionAwareMealPlanner,
    NutritionDailyMealPlan,
    food_items_to_ingredients,
)
from .vision import DetectedIngredient, VisionBackend, create_backend

__all__ = [
    "FridgeCamera",
    "CameraCapture",
    "VisionBackend",
    "DetectedIngredient",
    "create_backend",
    "MealPlanner",
    "NutritionAwareMealPlanner",
    "DailyMealPlan",
    "NutritionDailyMealPlan",
    "Meal",
    "AnnotatedIngredient",
    "food_items_to_ingredients",
    "FridgeConfig",
    "IAEONConfig",
    "DatabaseConfig",
    "NutritionConfig",
    "PrinterConfig",
    "GDriveConfig",
    "load_config",
]
