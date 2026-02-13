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

    # iaeon-login
    sub.add_parser("iaeon-login", help="iAEON認証セットアップ")

    # iaeon-fetch
    iaeon_fetch_parser = sub.add_parser("iaeon-fetch", help="iAEONレシート手動取得")
    iaeon_fetch_parser.add_argument(
        "--days", type=int, default=7, help="取得する日数 (デフォルト: 7)"
    )

    # inventory
    inv_parser = sub.add_parser("inventory", help="食品在庫一覧表示")
    inv_parser.add_argument(
        "--expiring", action="store_true", help="期限切れ間近の食品のみ表示"
    )
    inv_parser.add_argument("--json", action="store_true", help="JSON形式で出力")

    # nutrition-plan
    np_parser = sub.add_parser("nutrition-plan", help="栄養バランス献立生成")
    np_parser.add_argument(
        "--pdf", type=str, default=None, metavar="FILE",
        help="PDF ファイルに出力",
    )
    np_parser.add_argument(
        "--drive", action="store_true", help="Google Drive にアップロード"
    )
    np_parser.add_argument("--json", action="store_true", help="JSON形式で出力")

    # schedule
    sched_parser = sub.add_parser("schedule", help="スケジューラー管理")
    sched_parser.add_argument(
        "action", choices=["start", "stop", "status"],
        help="スケジューラーアクション",
    )

    # nutrition-lookup
    nl_parser = sub.add_parser("nutrition-lookup", help="食品栄養情報検索")
    nl_parser.add_argument("food_name", type=str, help="検索する食品名")

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
        case "iaeon-login":
            asyncio.run(_cmd_iaeon_login(config))
        case "iaeon-fetch":
            asyncio.run(_cmd_iaeon_fetch(config, args))
        case "inventory":
            _cmd_inventory(config, args)
        case "nutrition-plan":
            asyncio.run(_cmd_nutrition_plan(config, args))
        case "schedule":
            _cmd_schedule(config, args)
        case "nutrition-lookup":
            _cmd_nutrition_lookup(args)


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


async def _cmd_iaeon_login(config) -> None:
    from .iaeon import IAEONAuthenticator

    phone = config.iaeon.phone
    password = config.iaeon.password

    if not phone:
        phone = input("iAEON 電話番号: ").strip()
    if not password:
        import getpass
        password = getpass.getpass("iAEON パスワード: ")

    print("iAEON にログイン中...")
    try:
        auth = IAEONAuthenticator(
            phone=phone,
            password=password,
            otp_method=config.iaeon.otp_method,
        )
        session = await auth.login()
        print(f"ログイン成功 (User ID: {session.user_id})")
        print("設定ファイルに phone と password を保存するか、")
        print("環境変数 IAEON_PHONE / IAEON_PASSWORD を設定してください。")
    except (ImportError, RuntimeError) as e:
        print(f"ログインエラー: {e}", file=sys.stderr)
        sys.exit(1)


async def _cmd_iaeon_fetch(config, args) -> None:
    from .db import InventoryDB
    from .iaeon import IAEONAuthenticator, ReceiptFetcher

    if not config.iaeon.phone or not config.iaeon.password:
        print("iAEON の認証情報が設定されていません。", file=sys.stderr)
        print("設定ファイルまたは環境変数で IAEON_PHONE / IAEON_PASSWORD を設定してください。")
        sys.exit(1)

    print("iAEON にログイン中...")
    try:
        auth = IAEONAuthenticator(
            phone=config.iaeon.phone,
            password=config.iaeon.password,
            otp_method=config.iaeon.otp_method,
        )
        session = await auth.login()
    except (ImportError, RuntimeError) as e:
        print(f"ログインエラー: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"レシートを取得中 (過去 {args.days} 日間)...")
    fetcher = ReceiptFetcher(session)
    try:
        entries = await fetcher.fetch_recent_receipts(days=args.days)
    except (ImportError, RuntimeError) as e:
        print(f"レシート取得エラー: {e}", file=sys.stderr)
        sys.exit(1)

    food_items = fetcher.extract_food_items(entries)

    if not food_items:
        print("食品データが見つかりませんでした。")
        return

    db = InventoryDB(config.database.path)
    try:
        ids = db.add_food_items(food_items)
        print(f"食品 {len(ids)} 件をDBに登録しました:")
        for item in food_items:
            print(f"  {item.name} ({item.category}) - ¥{item.price}")
    finally:
        db.close()


def _cmd_inventory(config, args) -> None:
    from .db import InventoryDB

    db = InventoryDB(config.database.path)
    try:
        if args.expiring:
            items = db.get_expiring_soon(days=3)
            label = "期限切れ間近の食品"
        else:
            items = db.get_active_inventory()
            label = "食品在庫"

        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2, default=str))
            return

        if not items:
            print(f"{label}はありません。")
            return

        print(f"{label}: {len(items)} 件")
        print(f"  {'名前':<12} {'カテゴリ':<8} {'数量':<6} {'期限':<12} {'価格'}")
        print(f"  {'─' * 50}")
        for item in items:
            expiry = item.get("expiration_date", "-") or "-"
            price = f"¥{item['price']}" if item.get("price") else "-"
            print(
                f"  {item['name']:<12} {item['category']:<8} "
                f"{item['quantity']:<6} {expiry:<12} {price}"
            )
    finally:
        db.close()


async def _cmd_nutrition_plan(config, args) -> None:
    from ..client import Cookpad
    from .db import InventoryDB, MealHistoryDB
    from .nutrition.calculator import NutritionTargets
    from .planner import NutritionAwareMealPlanner

    # Get ingredients from inventory
    db = InventoryDB(config.database.path)
    try:
        ingredients = db.get_inventory_as_ingredients()
    finally:
        db.close()

    if not ingredients:
        print("在庫が空です。iaeon-fetch コマンドでレシートを取得するか、")
        print("カメラで食材を検出してください。")
        return

    # Build nutrition targets
    nc = config.nutrition
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
        "country": config.cookpad.country,
        "language": config.cookpad.language,
    }
    if config.cookpad.token:
        client_kwargs["token"] = config.cookpad.token

    async with Cookpad(**client_kwargs) as client:
        planner = NutritionAwareMealPlanner(
            cookpad=client,
            storage_locations=config.planner.storage_locations,
            nutrition_targets=targets,
        )
        print("栄養バランス献立を作成中...")
        plan = await planner.plan_daily_balanced(
            ingredients=ingredients,
            meals_count=config.planner.meals_per_day,
        )

    if args.json:
        data = {
            "date": plan.date,
            "source": plan.source,
            "detected_ingredients": plan.detected_ingredients,
            "meals": [
                {
                    "meal_type": m.meal_type,
                    "meal_type_ja": m.meal_type_ja,
                    "main_dish": {
                        "id": m.main_dish.id,
                        "title": m.main_dish.title,
                    },
                    "side_dishes": [
                        {"id": s.id, "title": s.title}
                        for s in m.side_dishes
                    ],
                }
                for m in plan.meals
            ],
            "nutrition": plan.daily_nutrition.summary_dict()
            if plan.daily_nutrition else None,
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print()
        print(plan.display())

    # Save to history
    history_db = MealHistoryDB(config.database.path)
    try:
        dn = plan.daily_nutrition
        history_db.save_plan(
            plan_date=plan.date,
            plan_json={"date": plan.date, "source": plan.source},
            source=plan.source,
            total_calories=dn.total_energy if dn else None,
            total_protein=dn.total_protein if dn else None,
            total_fat=dn.total_fat if dn else None,
            total_carbs=dn.total_carbs if dn else None,
        )
    finally:
        history_db.close()

    # PDF output
    if args.pdf or args.drive:
        pdf_path = Path(args.pdf) if args.pdf else Path(
            tempfile.mktemp(suffix=".pdf", prefix="kondate_")
        )

        from .pdf import generate_pdf

        print("PDF を生成中...")
        try:
            generate_pdf(plan, pdf_path, daily_nutrition=plan.daily_nutrition)
            if args.pdf:
                print(f"   PDF 保存: {pdf_path}")
        except (ImportError, FileNotFoundError) as e:
            print(f"PDF 生成エラー: {e}", file=sys.stderr)
            return

        if args.drive:
            from .gdrive import GoogleDriveUploader

            print("Google Drive にアップロード中...")
            try:
                uploader = GoogleDriveUploader(
                    credentials_path=config.gdrive.credentials_path,
                    token_path=config.gdrive.token_path,
                    folder_id=config.gdrive.folder_id,
                )
                filename = f"{plan.date} の献立.pdf"
                file_id = uploader.upload(pdf_path, filename=filename)
                print(f"   アップロード完了 (File ID: {file_id})")
            except (ImportError, FileNotFoundError) as e:
                print(f"Google Drive エラー: {e}", file=sys.stderr)

        if not args.pdf and pdf_path.exists():
            pdf_path.unlink()


def _cmd_schedule(config, args) -> None:
    match args.action:
        case "start":
            from .scheduler import MealPlanScheduler

            try:
                scheduler = MealPlanScheduler(config)
            except ImportError as e:
                print(f"スケジューラーエラー: {e}", file=sys.stderr)
                sys.exit(1)

            scheduler.start()
            print("スケジューラーを開始しました。")
            jobs = scheduler.get_jobs()
            for job in jobs:
                next_run = job["next_run"] or "未定"
                print(f"  {job['name']}: 次回実行 {next_run}")

            print("\nCtrl+C で停止します...")
            try:
                asyncio.get_event_loop().run_forever()
            except KeyboardInterrupt:
                scheduler.stop()
                print("\nスケジューラーを停止しました。")

        case "stop":
            print("スケジューラーは現在のプロセスでのみ動作します。")
            print("Ctrl+C で停止してください。")

        case "status":
            from .scheduler import MealPlanScheduler

            try:
                scheduler = MealPlanScheduler(config)
                scheduler.setup_jobs()
                jobs = scheduler.get_jobs()
                if not jobs:
                    print("登録されたジョブはありません。")
                else:
                    print(f"登録済みジョブ: {len(jobs)} 件")
                    for job in jobs:
                        next_run = job["next_run"] or "未定"
                        print(f"  {job['name']} ({job['id']}): 次回実行 {next_run}")
            except ImportError as e:
                print(f"スケジューラーエラー: {e}", file=sys.stderr)
                sys.exit(1)


def _cmd_nutrition_lookup(args) -> None:
    from .nutrition import MEXTDatabase

    db = MEXTDatabase.instance()
    results = db.search(args.food_name)

    if not results:
        # Try fuzzy lookup
        info = db.lookup_by_name(args.food_name)
        if info:
            results = [info]

    if not results:
        print(f"「{args.food_name}」に一致する食品が見つかりませんでした。")
        return

    for info in results:
        print(f"食品名: {info.name} ({info.group})")
        print(f"  エネルギー: {info.energy_kcal} kcal")
        print(f"  たんぱく質: {info.protein} g")
        print(f"  脂質:       {info.fat} g")
        print(f"  炭水化物:   {info.carbohydrate} g")
        print(f"  食物繊維:   {info.fiber} g")
        print(f"  食塩相当量: {info.salt_equivalent} g")
        print(f"  カルシウム: {info.calcium} mg")
        print(f"  鉄:         {info.iron} mg")
        print(f"  ビタミンA:  {info.vitamin_a} μgRAE")
        print(f"  ビタミンC:  {info.vitamin_c} mg")
        print(f"  ビタミンD:  {info.vitamin_d} μg")
        print(f"  (100g あたり)")
        print()
