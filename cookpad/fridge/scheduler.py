"""Scheduled job execution for automated meal planning."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class MealPlanScheduler:
    """Manages scheduled jobs for receipt fetching and meal plan generation.

    Uses APScheduler for cron-based scheduling.
    """

    def __init__(self, config) -> None:
        """Initialize scheduler with a FridgeConfig.

        Args:
            config: FridgeConfig instance.

        Raises:
            ImportError: If apscheduler is not installed.
        """
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            raise ImportError(
                "apscheduler が必要です: pip install 'cookpad[scheduler]'"
            )

        self._config = config
        self._scheduler = AsyncIOScheduler()
        self._CronTrigger = CronTrigger
        self._running = False

    def setup_jobs(self) -> None:
        """Register scheduled jobs based on config."""
        # Job 1: Fetch receipts from iAEON
        if self._config.iaeon.enabled:
            trigger = self._parse_cron(self._config.iaeon.fetch_schedule)
            self._scheduler.add_job(
                self._job_fetch_receipts,
                trigger=trigger,
                id="fetch_receipts",
                name="iAEONレシート取得",
                replace_existing=True,
            )
            logger.info(
                "レシート取得ジョブ登録: %s",
                self._config.iaeon.fetch_schedule,
            )

        # Job 2: Generate nutrition-balanced meal plan
        if self._config.iaeon.enabled:
            trigger = self._parse_cron(self._config.iaeon.plan_schedule)
            self._scheduler.add_job(
                self._job_generate_plan,
                trigger=trigger,
                id="generate_plan",
                name="栄養バランス献立生成",
                replace_existing=True,
            )
            logger.info(
                "献立生成ジョブ登録: %s",
                self._config.iaeon.plan_schedule,
            )

        # Job 3: Expire old items (daily at midnight)
        trigger = self._parse_cron("0 0 * * *")
        self._scheduler.add_job(
            self._job_expire_items,
            trigger=trigger,
            id="expire_items",
            name="期限切れチェック",
            replace_existing=True,
        )
        logger.info("期限切れチェックジョブ登録: 0 0 * * *")

    def start(self) -> None:
        """Start the scheduler."""
        self.setup_jobs()
        self._scheduler.start()
        self._running = True
        logger.info("スケジューラー開始")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("スケジューラー停止")

    @property
    def running(self) -> bool:
        return self._running

    def get_jobs(self) -> list[dict]:
        """Return info about scheduled jobs."""
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })
        return jobs

    def _parse_cron(self, expr: str):
        """Parse a cron expression into a CronTrigger."""
        parts = expr.split()
        if len(parts) == 5:
            return self._CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        raise ValueError(f"無効なcron式: {expr}")

    async def _job_fetch_receipts(self) -> None:
        """Fetch recent receipts and add food items to inventory."""
        logger.info("レシート取得ジョブ実行中...")

        try:
            from .db import InventoryDB
            from .iaeon import IAEONAuthenticator, ReceiptFetcher

            # Authenticate
            auth = IAEONAuthenticator(
                phone=self._config.iaeon.phone,
                password=self._config.iaeon.password,
                otp_method=self._config.iaeon.otp_method,
            )
            session = await auth.login()

            # Fetch receipts
            fetcher = ReceiptFetcher(session)
            entries = await fetcher.fetch_recent_receipts(
                days=self._config.iaeon.receipt_days
            )
            food_items = fetcher.extract_food_items(entries)

            # Store in DB
            db = InventoryDB(self._config.database.path)
            try:
                ids = db.add_food_items(food_items)
                logger.info("食品 %d 件をDBに登録しました", len(ids))
            finally:
                db.close()

        except Exception:
            logger.exception("レシート取得ジョブでエラーが発生しました")

    async def _job_generate_plan(self) -> None:
        """Generate a nutritionally balanced meal plan from inventory."""
        logger.info("献立生成ジョブ実行中...")

        try:
            from ..client import Cookpad
            from .db import InventoryDB, MealHistoryDB
            from .nutrition.calculator import NutritionTargets
            from .planner import NutritionAwareMealPlanner

            # Get active inventory
            db = InventoryDB(self._config.database.path)
            try:
                ingredients = db.get_inventory_as_ingredients()
            finally:
                db.close()

            if not ingredients:
                logger.warning("在庫が空のため献立生成をスキップします")
                return

            # Build nutrition targets from config
            nc = self._config.nutrition
            targets = NutritionTargets(
                energy_kcal=nc.energy_target,
                protein_pct=nc.protein_pct,
                fat_pct=nc.fat_pct,
                carb_pct=nc.carb_pct,
                salt_max=nc.salt_max,
                fiber_min=nc.fiber_min,
            )

            # Generate plan
            client_kwargs = {
                "country": self._config.cookpad.country,
                "language": self._config.cookpad.language,
            }
            if self._config.cookpad.token:
                client_kwargs["token"] = self._config.cookpad.token

            async with Cookpad(**client_kwargs) as client:
                planner = NutritionAwareMealPlanner(
                    cookpad=client,
                    storage_locations=self._config.planner.storage_locations,
                    nutrition_targets=targets,
                )
                plan = await planner.plan_daily_balanced(
                    ingredients=ingredients,
                    meals_count=self._config.planner.meals_per_day,
                )

            # Save to history
            history_db = MealHistoryDB(self._config.database.path)
            try:
                plan_data = {
                    "date": plan.date,
                    "detected_ingredients": plan.detected_ingredients,
                    "meals": [
                        {
                            "meal_type": m.meal_type,
                            "main_dish": {"id": m.main_dish.id, "title": m.main_dish.title},
                            "side_dishes": [
                                {"id": s.id, "title": s.title}
                                for s in m.side_dishes
                            ],
                        }
                        for m in plan.meals
                    ],
                }
                dn = plan.daily_nutrition
                history_db.save_plan(
                    plan_date=plan.date,
                    plan_json=plan_data,
                    source="iaeon",
                    total_calories=dn.total_energy if dn else None,
                    total_protein=dn.total_protein if dn else None,
                    total_fat=dn.total_fat if dn else None,
                    total_carbs=dn.total_carbs if dn else None,
                )
                logger.info("献立を履歴に保存しました: %s", plan.date)
            finally:
                history_db.close()

            # Generate PDF if gdrive is enabled
            if self._config.gdrive.enabled:
                from .gdrive import GoogleDriveUploader
                from .pdf import generate_pdf

                pdf_path = Path(tempfile.mktemp(suffix=".pdf", prefix="kondate_"))
                try:
                    generate_pdf(plan, pdf_path, daily_nutrition=dn)

                    uploader = GoogleDriveUploader(
                        credentials_path=self._config.gdrive.credentials_path,
                        token_path=self._config.gdrive.token_path,
                        folder_id=self._config.gdrive.folder_id,
                    )
                    filename = f"{plan.date} の献立.pdf"
                    file_id = uploader.upload(pdf_path, filename=filename)
                    logger.info("Google Drive にアップロード完了: %s", file_id)
                except Exception:
                    logger.exception("PDF生成/アップロードでエラーが発生しました")
                finally:
                    if pdf_path.exists():
                        pdf_path.unlink()

        except Exception:
            logger.exception("献立生成ジョブでエラーが発生しました")

    async def _job_expire_items(self) -> None:
        """Mark expired items in the inventory."""
        logger.info("期限切れチェック実行中...")

        try:
            from .db import InventoryDB

            db = InventoryDB(self._config.database.path)
            try:
                count = db.mark_expired()
                if count > 0:
                    logger.info("期限切れ食品 %d 件をマークしました", count)
            finally:
                db.close()
        except Exception:
            logger.exception("期限切れチェックでエラーが発生しました")
