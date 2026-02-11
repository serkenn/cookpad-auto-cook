"""CLI entry point for the fridge module."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .camera import FridgeCamera
from .config import load_config
from .planner import MealPlanner
from .vision import create_backend


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="cookpad-fridge",
        description="冷蔵庫スマート献立 — カメラで食材を検出し、献立を提案します",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="設定ファイルのパス (TOML)",
    )

    sub = parser.add_subparsers(dest="command")

    # cameras
    sub.add_parser("cameras", help="利用可能なカメラ一覧を表示")

    # scan
    scan_parser = sub.add_parser("scan", help="撮影して食材を検出")
    scan_parser.add_argument(
        "--image", type=str, nargs="+", help="既存の画像ファイルを使用"
    )
    scan_parser.add_argument("--json", action="store_true", help="JSON形式で出力")

    # plan
    plan_parser = sub.add_parser("plan", help="撮影→検出→献立提案")
    plan_parser.add_argument(
        "--image", type=str, nargs="+", help="既存の画像ファイルを使用"
    )
    plan_parser.add_argument("--json", action="store_true", help="JSON形式で出力")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    match args.command:
        case "cameras":
            _cmd_cameras()
        case "scan":
            asyncio.run(_cmd_scan(config, args))
        case "plan":
            asyncio.run(_cmd_plan(config, args))


def _cmd_cameras() -> None:
    cameras = FridgeCamera.list_cameras()
    if not cameras:
        print("利用可能なカメラが見つかりませんでした。")
        return
    print(f"利用可能なカメラ: {len(cameras)} 台")
    for idx in cameras:
        print(f"  カメラ {idx}")


async def _cmd_scan(config, args) -> None:
    # Get images
    if args.image:
        image_paths = args.image
    else:
        camera = FridgeCamera(
            camera_indices=config.camera.indices,
            save_dir=config.camera.save_dir,
        )
        print("📷 撮影中...")
        captures = camera.capture_all()
        image_paths = [c.image_path for c in captures]
        print(f"   {len(captures)} 枚撮影しました")

    # Detect ingredients
    backend = create_backend(config)
    print("🔍 食材を検出中...")
    ingredients = await backend.detect_ingredients(image_paths)

    # Filter by confidence
    reliable = [
        i for i in ingredients if i.confidence >= config.vision.min_confidence
    ]

    if args.json:
        data = [
            {"name": i.name, "confidence": i.confidence, "category": i.category}
            for i in reliable
        ]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if not reliable:
            print("食材が検出されませんでした。")
            return
        print(f"\n🥬 検出された食材 ({len(reliable)} 品):")
        for i in sorted(reliable, key=lambda x: x.confidence, reverse=True):
            bar = "█" * int(i.confidence * 10)
            print(f"  {i.name:<10} {i.confidence:.0%} {bar}  [{i.category}]")


async def _cmd_plan(config, args) -> None:
    # Get images
    if args.image:
        image_paths = args.image
    else:
        camera = FridgeCamera(
            camera_indices=config.camera.indices,
            save_dir=config.camera.save_dir,
        )
        print("📷 撮影中...")
        captures = camera.capture_all()
        image_paths = [c.image_path for c in captures]
        print(f"   {len(captures)} 枚撮影しました")

    # Detect ingredients
    backend = create_backend(config)
    print("🔍 食材を検出中...")
    ingredients = await backend.detect_ingredients(image_paths)

    reliable = [
        i for i in ingredients if i.confidence >= config.vision.min_confidence
    ]
    if not reliable:
        print("食材が検出されませんでした。")
        return

    # Build Cookpad client
    from ..client import Cookpad

    client_kwargs = {
        "country": config.cookpad.country,
        "language": config.cookpad.language,
    }
    if config.cookpad.token:
        client_kwargs["token"] = config.cookpad.token

    async with Cookpad(**client_kwargs) as client:
        planner = MealPlanner(cookpad=client)
        print("🍳 献立を作成中...")
        plan = await planner.plan_daily(
            reliable, meals_count=config.planner.meals_per_day
        )

    if args.json:
        data = {
            "date": plan.date,
            "detected_ingredients": plan.detected_ingredients,
            "meals": [
                {
                    "meal_type": m.meal_type,
                    "meal_type_ja": m.meal_type_ja,
                    "main_dish": {
                        "id": m.main_dish.id,
                        "title": m.main_dish.title,
                        "cooking_time": m.main_dish.cooking_time,
                    },
                    "side_dishes": [
                        {
                            "id": s.id,
                            "title": s.title,
                            "cooking_time": s.cooking_time,
                        }
                        for s in m.side_dishes
                    ],
                }
                for m in plan.meals
            ],
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print()
        print(plan.display())
