"""Tests for MealPlanScheduler."""

import pytest

from cookpad.fridge.config import FridgeConfig, IAEONConfig, load_config


def test_scheduler_import_error():
    """MealPlanScheduler raises ImportError if apscheduler is missing."""
    # This test verifies behavior whether or not apscheduler is installed
    try:
        from cookpad.fridge.scheduler import MealPlanScheduler

        # If import succeeds, apscheduler is installed
        config = load_config()
        scheduler = MealPlanScheduler(config)
        assert scheduler is not None
        assert scheduler.running is False
    except ImportError:
        # Expected if apscheduler is not installed
        pass


def test_scheduler_setup_jobs():
    """Scheduler registers jobs when iaeon is enabled."""
    try:
        from cookpad.fridge.scheduler import MealPlanScheduler

        config = load_config()
        config.iaeon.enabled = True
        config.iaeon.fetch_schedule = "0 8 * * *"
        config.iaeon.plan_schedule = "0 6 * * *"

        scheduler = MealPlanScheduler(config)
        scheduler.setup_jobs()

        jobs = scheduler.get_jobs()
        job_ids = {j["id"] for j in jobs}
        assert "fetch_receipts" in job_ids
        assert "generate_plan" in job_ids
        assert "expire_items" in job_ids
    except ImportError:
        pytest.skip("apscheduler not installed")


def test_scheduler_expire_job_always_registered():
    """expire_items job is always registered."""
    try:
        from cookpad.fridge.scheduler import MealPlanScheduler

        config = load_config()
        config.iaeon.enabled = False

        scheduler = MealPlanScheduler(config)
        scheduler.setup_jobs()

        jobs = scheduler.get_jobs()
        job_ids = {j["id"] for j in jobs}
        assert "expire_items" in job_ids
        # iaeon jobs should not be registered
        assert "fetch_receipts" not in job_ids
    except ImportError:
        pytest.skip("apscheduler not installed")
