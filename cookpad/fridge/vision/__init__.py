"""Vision backend base class, data types, and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import FridgeConfig


@dataclass
class DetectedIngredient:
    name: str  # 食材名（日本語）
    confidence: float  # 0.0〜1.0
    category: str  # 野菜, 肉, 魚, 乳製品, 調味料, etc.


class VisionBackend(ABC):
    """Abstract base for food ingredient detection from images."""

    @abstractmethod
    async def detect_ingredients(
        self, image_paths: list[str]
    ) -> list[DetectedIngredient]:
        """Detect ingredients from one or more fridge images.

        Duplicates across images should be merged.
        """
        ...


def create_backend(config: FridgeConfig) -> VisionBackend:
    """Create a vision backend based on configuration."""
    backend_name = config.vision.backend

    match backend_name:
        case "claude":
            from .claude import ClaudeVisionBackend

            return ClaudeVisionBackend(
                api_key=config.vision.claude.api_key,
                model=config.vision.claude.model,
            )
        case "gemini":
            from .gemini import GeminiVisionBackend

            return GeminiVisionBackend(
                api_key=config.vision.gemini.api_key,
                model=config.vision.gemini.model,
            )
        case "ai_hat":
            from .ai_hat import AIHatVisionBackend

            return AIHatVisionBackend(
                model_path=config.vision.ai_hat.model_path,
            )
        case _:
            raise ValueError(
                f"不明なVisionバックエンド: {backend_name!r}  "
                f"(claude / gemini / ai_hat から選択してください)"
            )
