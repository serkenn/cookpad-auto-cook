#!/usr/bin/env python3
"""デバッグ実行スクリプト: iAEONログイン → レシート取得 → 食材抽出 → Cookpadレシピ検索"""

import asyncio
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

# レシートの非商品行を追加フィルタ（parse_receiptで残ったゴミ）
_EXTRA_NON_FOOD = re.compile(
    r"小\s*計|合\s*計|支払|残高|お釣|お預|現\s*金|"
    r"カード会社|伝票番号|ﾏｽﾀｰ|VISA|ｲｵﾝ|"
    r"値引|割引|円引|10円引|20円引|"
    r"\d{4,}",  # 伝票番号のような大きな数値のみの商品名
)


def is_cooking_ingredient(name: str) -> bool:
    """料理に使える食材かどうかを判定"""
    # 明らかなお菓子・飲料は除外しない（お菓子でも料理に使える場合がある）
    # ただし非商品行は除外
    if _EXTRA_NON_FOOD.search(name):
        return False
    if len(name) <= 1:
        return False
    return True


async def main():
    # ── Step 0: 環境変数読み込み ──
    phone = os.getenv("PHONE_NUMBER", "").strip('"')
    password = os.getenv("PASSWORD", "").strip('"')
    device_id = os.getenv("DEVICE_ID", "").strip('"')
    receipt_account_id = os.getenv("RECEIPT_ACCOUNT_ID", "").strip('"')
    android_host = os.getenv("ANDROID_HOST", "192.168.1.1").strip('"')
    android_port = int(os.getenv("ANDROID_PORT", "8765").strip('"'))

    print("=" * 60)
    print("  冷蔵庫スマート献立 デバッグ実行")
    print("=" * 60)
    print(f"[DEBUG] Phone: {phone[:3]}****{phone[-4:]}")
    print(f"[DEBUG] Device ID: {device_id}")
    print(f"[DEBUG] OTPリレー: {android_host}:{android_port}")
    print()

    # ── Step 1: iAEONログイン ──
    print("── Step 1: iAEON ログイン ──")
    from iaeon import IAEONAuth

    auth = IAEONAuth(device_id=device_id)

    def otp_provider() -> str:
        try:
            from plusmsg_otp import PlusMessageOTP
            otp_client = PlusMessageOTP(host=android_host, port=android_port)
            print("[DEBUG] +Message OTPリレーに接続中...")
            otp_client.clear()
            print("[DEBUG] OTP待機中 (最大120秒)...")
            code = otp_client.wait_for_otp(timeout=120)
            print(f"[DEBUG] OTP自動取得成功: {code}")
            return code
        except Exception as e:
            print(f"[WARN] OTP自動取得失敗: {e}")
            return input("SMSで届いた6桁の認証コードを入力: ").strip()

    try:
        access_token = auth.full_login(phone, password, otp_provider)
        print(f"[OK] ログイン成功!")
        print(f"[DEBUG] access_token: {access_token[:30]}...")
    except Exception as e:
        print(f"[ERROR] ログイン失敗: {e}")
        sys.exit(1)

    print()

    # ── Step 2: レシート取得 ──
    print("── Step 2: レシート取得 ──")
    from iaeon import IAEONReceiptClient
    from iaeon.inventory import parse_receipt
    from datetime import date, timedelta

    if not receipt_account_id:
        print("[DEBUG] receipt_account_id を取得中...")
        temp = IAEONReceiptClient(access_token=access_token, receipt_account_id="")
        info = temp.get_user_receipt_info()
        receipt_account_id = info.get("receipt_account_id", "")
        print(f"[DEBUG] receipt_account_id: {receipt_account_id}")

    client = IAEONReceiptClient(
        access_token=access_token,
        receipt_account_id=receipt_account_id,
    )

    print("[DEBUG] レシートサービス認証中...")
    jwt = client.auth_receipt()
    print(f"[OK] receipt JWT取得成功")

    days = 90
    to_date = date.today().strftime("%Y%m%d")
    from_date = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
    print(f"[DEBUG] レシート一覧取得: {from_date} ~ {to_date} ({days}日間)")

    summaries = client.list_receipts(from_date, to_date)
    print(f"[OK] レシート {len(summaries)} 件取得")

    for i, s in enumerate(summaries):
        print(f"  [{i+1}] {s.store_name} | {s.datetime[:10]} | ¥{s.total or '?'}")

    print()

    # ── Step 3: レシート詳細 → 食材抽出 ──
    print("── Step 3: 食材抽出 ──")
    from cookpad.fridge.iaeon.models import ReceiptEntry
    from cookpad.fridge.iaeon.receipts import ReceiptFetcher
    from cookpad.fridge.iaeon.auth import IAEONSession

    all_entries: list[ReceiptEntry] = []

    for summary in summaries:
        detail = client.get_receipt_detail(summary.receipt_id)
        parsed = parse_receipt(detail, summary)

        raw_dt = parsed.purchased_at or ""
        if "T" in raw_dt:
            purchase_date = raw_dt[:10]
        elif len(raw_dt) >= 8 and raw_dt[:8].isdigit():
            purchase_date = f"{raw_dt[:4]}-{raw_dt[4:6]}-{raw_dt[6:8]}"
        else:
            purchase_date = raw_dt[:10]

        for product in parsed.products:
            all_entries.append(
                ReceiptEntry(
                    product_name=product.name,
                    price=product.price,
                    quantity=product.quantity,
                    receipt_id=parsed.receipt_id,
                    purchase_date=purchase_date,
                    store_name=parsed.store_name,
                    barcode=product.barcode or "",
                )
            )

    print(f"[DEBUG] 全商品 (raw): {len(all_entries)} 件")

    # ReceiptFetcherで食品フィルタリング
    dummy_session = IAEONSession(access_token=access_token, device_id=device_id)
    fetcher = ReceiptFetcher(dummy_session)
    food_items = fetcher.extract_food_items(all_entries)

    # 追加フィルタ: 非商品行を除去
    food_items = [f for f in food_items if is_cooking_ingredient(f.name)]

    print(f"[OK] 食品アイテム: {len(food_items)} 件\n")
    for item in food_items:
        print(f"  - {item.name:<20s} ({item.category}) ¥{item.price}")

    if not food_items:
        print("[WARN] 食品が見つかりませんでした。")
        sys.exit(0)

    print()

    # ── Step 4: 料理向き食材を選別してCookpad検索 ──
    print("── Step 4: Cookpad レシピ検索 ──")
    from cookpad import Cookpad

    # 料理に使いやすいカテゴリを優先
    cooking_categories = {"肉", "魚", "野菜", "卵", "豆腐・大豆"}
    cooking_items = [f for f in food_items if f.category in cooking_categories]

    if not cooking_items:
        # 料理食材がない場合、全食品から検索
        cooking_items = food_items

    # 期限の近いものを優先
    sorted_items = sorted(cooking_items, key=lambda x: x.estimated_expiry or "9999")
    priority_names = list(dict.fromkeys(item.name for item in sorted_items))[:5]
    print(f"[DEBUG] 優先食材: {', '.join(priority_names)}")

    async with Cookpad() as cookpad:
        all_recipes = []

        # まず組み合わせ検索
        if len(priority_names) >= 2:
            combo_query = " ".join(priority_names[:3])
            print(f"[DEBUG] 組み合わせ検索: '{combo_query}'")
            result = await cookpad.search_recipes(combo_query)
            all_recipes.extend(result.recipes)
            print(f"  → {len(result.recipes)} 件")

        # 個別食材でも検索
        for name in priority_names[:5]:
            print(f"[DEBUG] 個別検索: '{name}'")
            result = await cookpad.search_recipes(name)
            # 重複除去しつつ追加
            existing_ids = {r.id for r in all_recipes}
            for r in result.recipes[:5]:
                if r.id not in existing_ids:
                    all_recipes.append(r)
                    existing_ids.add(r.id)
            print(f"  → {len(result.recipes)} 件 (累計: {len(all_recipes)})")

        print(f"\n[OK] 合計 {len(all_recipes)} レシピ\n")

        # ── 結果表示 ──
        print("=" * 60)
        print("  🍳 おすすめレシピ (レシートの食材から)")
        print("=" * 60)

        for i, recipe in enumerate(all_recipes[:10], 1):
            print(f"\n{'─' * 50}")
            print(f"  {i}. {recipe.title}")
            print(f"     by {recipe.user.name if recipe.user else '不明'}")

            if recipe.story:
                story = recipe.story[:80]
                print(f"     {story}{'...' if len(recipe.story) > 80 else ''}")

            # レシピ詳細を取得して材料を表示
            try:
                detail = await cookpad.get_recipe(recipe.id)
                if detail.ingredients:
                    ing_text = ", ".join(
                        f"{ing.name}({ing.quantity})" for ing in detail.ingredients[:8]
                    )
                    print(f"     材料: {ing_text}")
                if detail.steps:
                    print(f"     手順: {len(detail.steps)}ステップ")
            except Exception:
                pass

    print(f"\n{'=' * 60}")
    print("  完了!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
