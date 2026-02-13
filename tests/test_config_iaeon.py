"""Tests for iAEON/database/nutrition configuration loading."""

import pytest

from cookpad.fridge.config import (
    DatabaseConfig,
    FridgeConfig,
    IAEONConfig,
    NutritionConfig,
    load_config,
)


def test_default_iaeon_config():
    """Default IAEONConfig is disabled."""
    config = load_config()
    assert config.iaeon.enabled is False
    assert config.iaeon.phone == ""
    assert config.iaeon.otp_method == "manual"
    assert config.iaeon.receipt_days == 7


def test_default_database_config():
    """Default DatabaseConfig points to standard path."""
    config = load_config()
    assert "inventory.db" in config.database.path


def test_default_nutrition_config():
    """Default NutritionConfig matches Japanese guidelines."""
    config = load_config()
    assert config.nutrition.enabled is True
    assert config.nutrition.energy_target == 2000.0
    assert config.nutrition.protein_pct == 15.0
    assert config.nutrition.fat_pct == 25.0
    assert config.nutrition.carb_pct == 60.0
    assert config.nutrition.salt_max == 7.5
    assert config.nutrition.fiber_min == 21.0
    assert config.nutrition.prioritize_expiring is True


def test_load_iaeon_from_toml(tmp_path):
    """IAEONConfig loads from TOML file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[iaeon]
enabled = true
phone = "090-1234-5678"
password = "secret"
otp_method = "bypass"
receipt_days = 14
"""
    )
    config = load_config(config_file)
    assert config.iaeon.enabled is True
    assert config.iaeon.phone == "090-1234-5678"
    assert config.iaeon.password == "secret"
    assert config.iaeon.otp_method == "bypass"
    assert config.iaeon.receipt_days == 14


def test_load_database_from_toml(tmp_path):
    """DatabaseConfig loads from TOML file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[database]
path = "/custom/path/data.db"
"""
    )
    config = load_config(config_file)
    assert config.database.path == "/custom/path/data.db"


def test_load_nutrition_from_toml(tmp_path):
    """NutritionConfig loads from TOML file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[nutrition]
enabled = true
energy_target = 1800
protein_pct = 20
fat_pct = 20
carb_pct = 60
salt_max = 6.0
fiber_min = 25
prioritize_expiring = false
"""
    )
    config = load_config(config_file)
    assert config.nutrition.energy_target == 1800.0
    assert config.nutrition.protein_pct == 20.0
    assert config.nutrition.salt_max == 6.0
    assert config.nutrition.prioritize_expiring is False


def test_iaeon_env_override(tmp_path, monkeypatch):
    """IAEON_PHONE and IAEON_PASSWORD env vars override empty config."""
    monkeypatch.setenv("IAEON_PHONE", "080-9999-0000")
    monkeypatch.setenv("IAEON_PASSWORD", "envpassword")

    config = load_config()
    assert config.iaeon.phone == "080-9999-0000"
    assert config.iaeon.password == "envpassword"


def test_iaeon_config_file_takes_precedence(tmp_path, monkeypatch):
    """Config file values take precedence over env vars."""
    monkeypatch.setenv("IAEON_PHONE", "080-env-phone")

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[iaeon]
phone = "090-file-phone"
"""
    )
    config = load_config(config_file)
    # Config file value should be used
    assert config.iaeon.phone == "090-file-phone"


def test_fridge_config_has_all_new_fields():
    """FridgeConfig has iaeon, database, and nutrition fields."""
    config = FridgeConfig()
    assert isinstance(config.iaeon, IAEONConfig)
    assert isinstance(config.database, DatabaseConfig)
    assert isinstance(config.nutrition, NutritionConfig)
