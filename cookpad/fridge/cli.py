"""CLI entry point for the fridge module."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
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

    # printers
    sub.add_parser("printers", help="利用可能なプリンタ一覧を表示")

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
    plan_parser.add_argument(
        "--pdf", type=str, default=None, metavar="FILE",
        help="PDF ファイルに出力",
    )
    plan_parser.add_argument(
        "--print", action="store_true", dest="do_print",
        help="デフォルトプリンタで印刷",
    )
    plan_parser.add_argument(
        "--printer", type=str, default=None,
        help="指定プリンタで印刷",
    )
    plan_parser.add_argument(
        "--drive", action="store_true",
        help="Google Drive にアップロード",
    )
    plan_parser.add_argument(
        "--drive-folder", type=str, default=None,
        help="Google Drive のフォルダ ID",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    match args.command:
        case "cameras":
            _cmd_cameras()
        case "printers":
            _cmd_printers()
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


def _cmd_printers() -> None:
    from .printer import Printer

    try:
        printers = Printer.list_printers()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if not printers:
        print("利用可能なプリンタが見つかりませんでした。")
        return
    print(f"利用可能なプリンタ: {len(printers)} 台")
    for p in printers:
        default_mark = " (デフォルト)" if p.is_default else ""
        print(f"  {p.name}{default_mark}")


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
        planner = MealPlanner(
            cookpad=client,
            storage_locations=config.planner.storage_locations,
        )
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

    # PDF / Print / Drive pipeline
    needs_pdf = args.pdf or args.do_print or args.printer or args.drive
    if not needs_pdf:
        return

    # Determine PDF output path
    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        pdf_path = Path(tempfile.mktemp(suffix=".pdf", prefix="kondate_"))

    # Generate PDF
    from .pdf import generate_pdf

    print("📄 PDF を生成中...")
    try:
        generate_pdf(plan, pdf_path)
        print(f"   PDF 保存: {pdf_path}")
    except (ImportError, FileNotFoundError) as e:
        print(f"PDF 生成エラー: {e}", file=sys.stderr)
        return

    # Print
    if args.do_print or args.printer:
        from .printer import Printer

        printer_name = args.printer
        print("🖨  印刷中...")
        try:
            Printer.print_file(pdf_path, printer_name=printer_name)
            target = printer_name or "デフォルトプリンタ"
            print(f"   印刷ジョブ送信: {target}")
        except RuntimeError as e:
            print(f"印刷エラー: {e}", file=sys.stderr)

    # Google Drive upload
    if args.drive:
        from .gdrive import GoogleDriveUploader

        print("☁  Google Drive にアップロード中...")
        try:
            uploader = GoogleDriveUploader(
                credentials_path=config.gdrive.credentials_path,
                token_path=config.gdrive.token_path,
                folder_id=config.gdrive.folder_id,
            )
            folder_id = args.drive_folder or config.gdrive.folder_id or None
            filename = f"{plan.date} の献立.pdf"
            file_id = uploader.upload(
                pdf_path, filename=filename, folder_id=folder_id
            )
            print(f"   アップロード完了 (File ID: {file_id})")
        except (ImportError, FileNotFoundError) as e:
            print(f"Google Drive エラー: {e}", file=sys.stderr)

    # Clean up temp PDF if not explicitly requested
    if not args.pdf and pdf_path.exists():
        pdf_path.unlink()
