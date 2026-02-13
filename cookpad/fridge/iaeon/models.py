"""Data models for iAEON receipt and food item data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReceiptEntry:
    """A single item line from an iAEON receipt."""

    product_name: str
    price: int
    quantity: int = 1
    category: str = ""
    receipt_id: str = ""
    purchase_date: str = ""
    store_name: str = ""
    barcode: str = ""


@dataclass
class FoodItem:
    """A normalized food item extracted from a receipt entry."""

    name: str              # Normalized food name
    category: str          # Food category (肉, 魚, 野菜, etc.)
    quantity: float = 1.0
    unit: str = "個"
    price: int = 0
    purchase_date: str = ""
    estimated_expiry: str = ""
    receipt_id: str = ""
