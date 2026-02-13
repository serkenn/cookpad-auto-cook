"""Receipt fetching and food item extraction from iAEON."""

from __future__ import annotations

import re
from datetime import date, timedelta

from ..planner import _CATEGORY_KEYWORDS
from .auth import IAEONSession
from .models import FoodItem, ReceiptEntry

# Non-food keywords to filter out
_NON_FOOD_KEYWORDS: list[str] = [
    "レジ袋", "袋", "ポイント", "割引", "値引", "クーポン",
    "洗剤", "シャンプー", "リンス", "ボディソープ", "歯磨",
    "ティッシュ", "トイレットペーパー", "ラップ", "アルミホイル",
    "ゴミ袋", "電池", "雑貨", "日用品", "文具",
    "小計", "小　計", "合計", "支払", "残高", "お釣",
    "税込", "税抜", "外税", "内税", "非課税",
    "交通系", "WAON", "ワオン", "現金", "クレジット",
    "お買上", "点数", "お預り", "IC",
]

# AEON brand prefixes to strip
_BRAND_PREFIXES: list[str] = [
    "TV ", "トップバリュ ", "BP ", "ベストプライス ",
    "TV　", "トップバリュ　", "BP　", "ベストプライス　",
]

# Category-based expiry estimates (days from purchase)
_EXPIRY_DAYS: dict[str, int] = {
    "肉": 3,
    "魚": 3,
    "野菜": 7,
    "果物": 7,
    "卵": 14,
    "乳製品": 10,
    "豆腐・大豆": 5,
    "穀物": 30,
    "調味料": 180,
    "飲料": 30,
    "その他": 14,
}


class ReceiptFetcher:
    """Fetches receipts from iAEON and extracts food items."""

    def __init__(self, session: IAEONSession) -> None:
        self._session = session

    async def fetch_recent_receipts(self, days: int = 7) -> list[ReceiptEntry]:
        """Fetch receipt data from the last N days.

        Uses IAEONReceiptClient and parse_receipt from the iaeon library.

        Raises:
            ImportError: If the iaeon library is not installed.
        """
        try:
            from iaeon import IAEONReceiptClient  # type: ignore[import-untyped]
            from iaeon.inventory import parse_receipt  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "iaeon ライブラリが必要です: pip install 'cookpad[iaeon]'"
            )

        import asyncio

        access_token = self._session.access_token

        # 1. Get receipt_account_id
        temp_client = IAEONReceiptClient(
            access_token=access_token, receipt_account_id=""
        )
        info = await asyncio.to_thread(temp_client.get_user_receipt_info)
        receipt_account_id = info.get("receipt_account_id", "")

        # 2. Create authenticated receipt client
        client = IAEONReceiptClient(
            access_token=access_token,
            receipt_account_id=receipt_account_id,
        )
        await asyncio.to_thread(client.auth_receipt)

        # 3. List receipts for date range (YYYYMMDD format)
        to_date = date.today().strftime("%Y%m%d")
        from_date = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
        summaries = await asyncio.to_thread(
            client.list_receipts, from_date, to_date
        )

        # 4. Fetch detail for each receipt and parse into entries
        entries: list[ReceiptEntry] = []
        for summary in summaries:
            detail = await asyncio.to_thread(
                client.get_receipt_detail, summary.receipt_id
            )
            parsed = parse_receipt(detail, summary)

            # purchased_at may be ISO datetime or compact YYYYMMDD...
            raw_dt = parsed.purchased_at or ""
            if "T" in raw_dt:
                purchase_date = raw_dt[:10]  # "2026-02-12T..." → "2026-02-12"
            elif len(raw_dt) >= 8 and raw_dt[:8].isdigit():
                purchase_date = f"{raw_dt[:4]}-{raw_dt[4:6]}-{raw_dt[6:8]}"
            else:
                purchase_date = raw_dt[:10]

            for product in parsed.products:
                entries.append(
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

        return entries

    def extract_food_items(self, entries: list[ReceiptEntry]) -> list[FoodItem]:
        """Filter entries to food items only and normalize names."""
        food_items: list[FoodItem] = []

        for entry in entries:
            # Skip non-food items
            if self._is_non_food(entry.product_name):
                continue

            name = self._normalize_product_name(entry.product_name)
            if not name:
                continue

            category = self._guess_food_category(name)
            expiry = self._estimate_expiry(
                name, category, entry.purchase_date
            )

            food_items.append(
                FoodItem(
                    name=name,
                    category=category,
                    quantity=float(entry.quantity),
                    unit="個",
                    price=entry.price,
                    purchase_date=entry.purchase_date,
                    estimated_expiry=expiry,
                    receipt_id=entry.receipt_id,
                )
            )

        return food_items

    @staticmethod
    def _is_non_food(product_name: str) -> bool:
        """Check if a product name refers to a non-food item."""
        for keyword in _NON_FOOD_KEYWORDS:
            if keyword in product_name:
                return True
        return False

    @staticmethod
    def _normalize_product_name(raw: str) -> str:
        """Normalize an AEON product name.

        Strips brand prefixes, quantity labels, and origin markers.
        """
        name = raw.strip()

        # Remove brand prefixes
        for prefix in _BRAND_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]

        # Remove quantity/weight suffixes like "300g", "2L", "6本入"
        name = re.sub(r"\s*\d+(?:\.\d+)?(?:g|kg|ml|L|本入|個入|枚入|パック)\s*$", "", name)

        # Remove origin labels like "北海道産", "国産", "〇〇県産"
        name = re.sub(r"[^\s]*[都道府県産国内外]産\s*", "", name)

        # Remove leading/trailing whitespace and special chars
        name = name.strip("　 ・/")

        return name

    @staticmethod
    def _guess_food_category(name: str) -> str:
        """Guess food category using the shared category keywords."""
        for category, keywords in _CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name:
                    return category
        return "その他"

    @staticmethod
    def _estimate_expiry(name: str, category: str, purchase_date: str) -> str:
        """Estimate expiration date based on category.

        Uses conservative estimates; actual expiry may be longer.
        """
        if not purchase_date:
            return ""

        try:
            pdate = date.fromisoformat(purchase_date)
        except (ValueError, TypeError):
            return ""

        days = _EXPIRY_DAYS.get(category, 14)
        expiry = pdate + timedelta(days=days)
        return expiry.isoformat()
