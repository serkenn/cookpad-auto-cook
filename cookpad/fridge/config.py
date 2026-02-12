"""TOML configuration loader for the fridge module."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class CameraConfig:
    indices: list[int] = field(default_factory=lambda: [0])
    save_dir: str = "/tmp/fridge"


@dataclass
class ClaudeVisionConfig:
    api_key: str = ""
    model: str = "claude-sonnet-4-5-20250929"


@dataclass
class GeminiVisionConfig:
    api_key: str = ""
    model: str = "gemini-2.0-flash"


@dataclass
class AIHatVisionConfig:
    model_path: str = "/usr/share/hailo-models/yolov8s.hef"


@dataclass
class VisionConfig:
    backend: str = "claude"
    min_confidence: float = 0.5
    claude: ClaudeVisionConfig = field(default_factory=ClaudeVisionConfig)
    gemini: GeminiVisionConfig = field(default_factory=GeminiVisionConfig)
    ai_hat: AIHatVisionConfig = field(default_factory=AIHatVisionConfig)


@dataclass
class PlannerConfig:
    meals_per_day: int = 3
    recipes_per_meal: int = 3
    storage_locations: dict[str, str] = field(default_factory=lambda: {
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
    })


@dataclass
class PrinterConfig:
    enabled: bool = False
    printer_name: str = ""


@dataclass
class GDriveConfig:
    enabled: bool = False
    credentials_path: str = "~/.config/cookpad/gdrive_credentials.json"
    token_path: str = "~/.config/cookpad/gdrive_token.json"
    folder_id: str = ""


@dataclass
class CookpadConfig:
    token: str = ""
    country: str = "JP"
    language: str = "ja"


@dataclass
class FridgeConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    cookpad: CookpadConfig = field(default_factory=CookpadConfig)
    printer: PrinterConfig = field(default_factory=PrinterConfig)
    gdrive: GDriveConfig = field(default_factory=GDriveConfig)


def load_config(path: str | Path | None = None) -> FridgeConfig:
    """Load configuration from a TOML file.

    Falls back to defaults if no path is given or the file doesn't exist.
    API keys can be overridden via environment variables.
    """
    raw: dict = {}

    if path is not None:
        p = Path(path)
        if p.exists():
            if tomllib is None:
                raise ImportError(
                    "tomli is required on Python < 3.11: pip install tomli"
                )
            with open(p, "rb") as f:
                raw = tomllib.load(f)

    cam = raw.get("camera", {})
    vis = raw.get("vision", {})
    pln = raw.get("planner", {})
    cpd = raw.get("cookpad", {})
    prn = raw.get("printer", {})
    gdr = raw.get("gdrive", {})

    claude_cfg = vis.get("claude", {})
    gemini_cfg = vis.get("gemini", {})
    ai_hat_cfg = vis.get("ai_hat", {})

    # Resolve API keys: config file → environment variable
    claude_api_key = claude_cfg.get("api_key", "") or os.environ.get(
        "ANTHROPIC_API_KEY", ""
    )
    gemini_api_key = gemini_cfg.get("api_key", "") or os.environ.get(
        "GEMINI_API_KEY", ""
    )

    # Merge custom storage_locations with defaults
    default_locations = PlannerConfig().storage_locations
    custom_locations = pln.get("storage_locations", {})
    storage_locations = {**default_locations, **custom_locations}

    return FridgeConfig(
        camera=CameraConfig(
            indices=cam.get("indices", [0]),
            save_dir=cam.get("save_dir", "/tmp/fridge"),
        ),
        vision=VisionConfig(
            backend=vis.get("backend", "claude"),
            min_confidence=vis.get("min_confidence", 0.5),
            claude=ClaudeVisionConfig(
                api_key=claude_api_key,
                model=claude_cfg.get("model", "claude-sonnet-4-5-20250929"),
            ),
            gemini=GeminiVisionConfig(
                api_key=gemini_api_key,
                model=gemini_cfg.get("model", "gemini-2.0-flash"),
            ),
            ai_hat=AIHatVisionConfig(
                model_path=ai_hat_cfg.get(
                    "model_path", "/usr/share/hailo-models/yolov8s.hef"
                ),
            ),
        ),
        planner=PlannerConfig(
            meals_per_day=pln.get("meals_per_day", 3),
            recipes_per_meal=pln.get("recipes_per_meal", 3),
            storage_locations=storage_locations,
        ),
        cookpad=CookpadConfig(
            token=cpd.get("token", ""),
            country=cpd.get("country", "JP"),
            language=cpd.get("language", "ja"),
        ),
        printer=PrinterConfig(
            enabled=prn.get("enabled", False),
            printer_name=prn.get("printer_name", ""),
        ),
        gdrive=GDriveConfig(
            enabled=gdr.get("enabled", False),
            credentials_path=gdr.get(
                "credentials_path",
                "~/.config/cookpad/gdrive_credentials.json",
            ),
            token_path=gdr.get(
                "token_path",
                "~/.config/cookpad/gdrive_token.json",
            ),
            folder_id=gdr.get("folder_id", ""),
        ),
    )
