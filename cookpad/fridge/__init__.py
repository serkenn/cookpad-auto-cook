"""Smart fridge meal planning module for Cookpad."""

from .camera import CameraCapture, FridgeCamera
from .config import (
    FridgeConfig,
    GDriveConfig,
    PrinterConfig,
    load_config,
)
from .planner import AnnotatedIngredient, DailyMealPlan, Meal, MealPlanner
from .vision import DetectedIngredient, VisionBackend, create_backend

__all__ = [
    "FridgeCamera",
    "CameraCapture",
    "VisionBackend",
    "DetectedIngredient",
    "create_backend",
    "MealPlanner",
    "DailyMealPlan",
    "Meal",
    "AnnotatedIngredient",
    "FridgeConfig",
    "PrinterConfig",
    "GDriveConfig",
    "load_config",
]
