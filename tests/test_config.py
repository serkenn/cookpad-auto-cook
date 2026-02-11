"""Tests for fridge config loading."""

import os
import tempfile
from pathlib import Path

from cookpad.fridge.config import (
    CameraConfig,
    CookpadConfig,
    FridgeConfig,
    load_config,
)


def test_load_config_defaults():
    """Loading with no path returns all defaults."""
    config = load_config()
    assert isinstance(config, FridgeConfig)
    assert config.camera.indices == [0]
    assert config.camera.save_dir == "/tmp/fridge"
    assert config.vision.backend == "claude"
    assert config.vision.min_confidence == 0.5
    assert config.planner.meals_per_day == 3
    assert config.cookpad.country == "JP"
    assert config.cookpad.language == "ja"


def test_load_config_nonexistent_file():
    """Loading a nonexistent file returns defaults."""
    config = load_config("/nonexistent/path.toml")
    assert config.camera.indices == [0]


def test_load_config_from_toml():
    """Loading a valid TOML file populates config."""
    toml_content = b"""\
[camera]
indices = [0, 1, 2]
save_dir = "/var/fridge"

[vision]
backend = "gemini"
min_confidence = 0.7

[vision.gemini]
api_key = "test-key-123"
model = "gemini-pro"

[planner]
meals_per_day = 2
recipes_per_meal = 2

[cookpad]
country = "US"
language = "en"
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    assert config.camera.indices == [0, 1, 2]
    assert config.camera.save_dir == "/var/fridge"
    assert config.vision.backend == "gemini"
    assert config.vision.min_confidence == 0.7
    assert config.vision.gemini.api_key == "test-key-123"
    assert config.vision.gemini.model == "gemini-pro"
    assert config.planner.meals_per_day == 2
    assert config.cookpad.country == "US"


def test_load_config_env_override(monkeypatch):
    """Environment variables override empty API keys."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-anthropic-key")
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")

    config = load_config()
    assert config.vision.claude.api_key == "env-anthropic-key"
    assert config.vision.gemini.api_key == "env-gemini-key"


def test_load_config_file_key_takes_precedence(monkeypatch):
    """Config file API key takes precedence over env var."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

    toml_content = b"""\
[vision.claude]
api_key = "file-key"
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)
    assert config.vision.claude.api_key == "file-key"


def test_load_config_partial_toml():
    """Partial TOML uses defaults for missing sections."""
    toml_content = b"""\
[camera]
indices = [3]
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)
    assert config.camera.indices == [3]
    # Other sections use defaults
    assert config.vision.backend == "claude"
    assert config.planner.meals_per_day == 3
