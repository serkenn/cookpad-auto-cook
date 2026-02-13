"""PDF generation for meal plans using ReportLab."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .planner import DailyMealPlan

if TYPE_CHECKING:
    from .nutrition.calculator import DailyNutrition

# Font search paths by platform
_FONT_SEARCH_PATHS = [
    # Noto Sans CJK (Debian/Ubuntu)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    # Noto Sans CJK (Fedora/RHEL)
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    # Noto Sans JP (standalone)
    "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf",
    "/usr/share/fonts/noto/NotoSansJP-Regular.ttf",
    # IPAex Gothic (Debian/Ubuntu)
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _find_japanese_font() -> str:
    """Find a Japanese-capable font on the system."""
    for path in _FONT_SEARCH_PATHS:
        if Path(path).exists():
            return path
    raise FileNotFoundError(
        "日本語フォントが見つかりません。以下のいずれかをインストールしてください:\n"
        "  Ubuntu/Debian: sudo apt install fonts-noto-cjk\n"
        "  Fedora/RHEL:   sudo dnf install google-noto-sans-cjk-ttc-fonts\n"
        "  macOS:         ヒラギノフォントが標準搭載されています"
    )


def _register_japanese_font() -> str:
    """Register a Japanese font with ReportLab and return the font name."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = _find_japanese_font()
    font_name = "JapaneseFont"
    pdfmetrics.registerFont(TTFont(font_name, font_path))
    return font_name


def generate_pdf(
    plan: DailyMealPlan,
    output_path: str | Path,
    daily_nutrition: DailyNutrition | None = None,
) -> Path:
    """Generate a PDF file from a DailyMealPlan.

    Args:
        plan: The meal plan to render.
        output_path: Where to save the PDF file.
        daily_nutrition: Optional nutrition data to include in the PDF.

    Returns:
        Path to the generated PDF file.

    Raises:
        ImportError: If reportlab is not installed.
        FileNotFoundError: If no Japanese font is found.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        raise ImportError(
            "reportlab が必要です: pip install 'cookpad[pdf]'"
        )

    font_name = _register_japanese_font()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title_JP",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=24,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle_JP",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.grey,
    )
    heading_style = ParagraphStyle(
        "Heading_JP",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        leading=20,
        spaceAfter=4 * mm,
    )
    dish_style = ParagraphStyle(
        "Dish_JP",
        parent=styles["Heading3"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        spaceBefore=3 * mm,
    )
    body_style = ParagraphStyle(
        "Body_JP",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13,
    )
    step_style = ParagraphStyle(
        "Step_JP",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13,
        leftIndent=10 * mm,
    )

    elements: list = []

    # Title
    elements.append(Paragraph(f"{plan.date} の献立", title_style))
    elements.append(Paragraph("冷蔵庫スマート献立", subtitle_style))
    elements.append(Spacer(1, 3 * mm))
    elements.append(
        Paragraph(
            f"検出された食材: {', '.join(plan.detected_ingredients)}",
            body_style,
        )
    )
    elements.append(Spacer(1, 6 * mm))

    table_header_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A90D9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])

    for meal in plan.meals:
        elements.append(Paragraph(meal.meal_type_ja, heading_style))

        # Main dish
        main = meal.main_dish
        time_str = f" ({main.cooking_time})" if main.cooking_time else ""
        serving_str = f" / {main.serving}" if main.serving else ""
        elements.append(
            Paragraph(
                f"【主菜】{main.title}{time_str}{serving_str}",
                dish_style,
            )
        )

        # Main dish ingredients table
        if meal.main_dish_ingredients:
            table_data = [["食材名", "分量", "保存場所", "状態"]]
            for ing in meal.main_dish_ingredients:
                status = "✓ 冷蔵庫にあり" if ing.available_in_fridge else "要購入"
                table_data.append([
                    ing.name, ing.quantity, ing.storage_location, status,
                ])
            col_widths = [45 * mm, 35 * mm, 30 * mm, 40 * mm]
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(table_header_style)
            elements.append(Spacer(1, 2 * mm))
            elements.append(t)

        # Main dish steps
        if main.steps:
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph("手順:", body_style))
            for j, step in enumerate(main.steps, 1):
                elements.append(
                    Paragraph(f"{j}. {step.description}", step_style)
                )

        # Side dishes
        for i, side in enumerate(meal.side_dishes, 1):
            time_str = f" ({side.cooking_time})" if side.cooking_time else ""
            elements.append(
                Paragraph(f"【副菜{i}】{side.title}{time_str}", dish_style)
            )

            if i - 1 < len(meal.side_dish_ingredients):
                side_ings = meal.side_dish_ingredients[i - 1]
                if side_ings:
                    table_data = [["食材名", "分量", "保存場所", "状態"]]
                    for ing in side_ings:
                        status = (
                            "✓ 冷蔵庫にあり"
                            if ing.available_in_fridge
                            else "要購入"
                        )
                        table_data.append([
                            ing.name, ing.quantity, ing.storage_location, status,
                        ])
                    col_widths = [45 * mm, 35 * mm, 30 * mm, 40 * mm]
                    t = Table(table_data, colWidths=col_widths)
                    t.setStyle(table_header_style)
                    elements.append(Spacer(1, 2 * mm))
                    elements.append(t)

            if side.steps:
                elements.append(Spacer(1, 2 * mm))
                elements.append(Paragraph("手順:", body_style))
                for j, step in enumerate(side.steps, 1):
                    elements.append(
                        Paragraph(f"{j}. {step.description}", step_style)
                    )

        elements.append(Spacer(1, 6 * mm))

    # Shopping list
    shopping = plan.shopping_list()
    if shopping:
        elements.append(Paragraph("買い物リスト", heading_style))
        table_data = [["食材名", "分量", "保存場所"]]
        for ing in shopping:
            table_data.append([ing.name, ing.quantity, ing.storage_location])

        shopping_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E67E22")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF3E0")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])
        col_widths = [50 * mm, 40 * mm, 40 * mm]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(shopping_style)
        elements.append(t)

    # Nutrition summary section
    if daily_nutrition is not None:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("栄養バランス", heading_style))

        dn = daily_nutrition
        targets = dn.targets

        # PFC ratio table
        nutrition_data = [
            ["栄養素", "摂取量", "目標", "達成率"],
            [
                "エネルギー",
                f"{dn.total_energy:.0f} kcal",
                f"{targets.energy_kcal:.0f} kcal",
                f"{dn.total_energy / targets.energy_kcal * 100:.0f}%"
                if targets.energy_kcal else "-",
            ],
            [
                "たんぱく質",
                f"{dn.total_protein:.1f} g",
                f"{targets.protein_g:.1f} g",
                f"{dn.total_protein / targets.protein_g * 100:.0f}%"
                if targets.protein_g else "-",
            ],
            [
                "脂質",
                f"{dn.total_fat:.1f} g",
                f"{targets.fat_g:.1f} g",
                f"{dn.total_fat / targets.fat_g * 100:.0f}%"
                if targets.fat_g else "-",
            ],
            [
                "炭水化物",
                f"{dn.total_carbs:.1f} g",
                f"{targets.carb_g:.1f} g",
                f"{dn.total_carbs / targets.carb_g * 100:.0f}%"
                if targets.carb_g else "-",
            ],
            [
                "食物繊維",
                f"{dn.total_fiber:.1f} g",
                f"{targets.fiber_min:.1f} g",
                f"{dn.total_fiber / targets.fiber_min * 100:.0f}%"
                if targets.fiber_min else "-",
            ],
            [
                "食塩相当量",
                f"{dn.total_salt:.1f} g",
                f"{targets.salt_max:.1f} g 以下",
                "OK" if dn.total_salt <= targets.salt_max else "超過",
            ],
        ]

        nutrition_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27AE60")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#E8F5E9")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])

        col_widths = [40 * mm, 35 * mm, 35 * mm, 30 * mm]
        t = Table(nutrition_data, colWidths=col_widths)
        t.setStyle(nutrition_style)
        elements.append(t)

        # Balance score
        elements.append(Spacer(1, 3 * mm))
        pfc_text = (
            f"PFC比率: P{dn.protein_pct:.0f}% / "
            f"F{dn.fat_pct:.0f}% / C{dn.carb_pct:.0f}%"
            f"  |  バランススコア: {dn.balance_score:.2f}"
        )
        elements.append(Paragraph(pfc_text, body_style))

    doc.build(elements)
    return output_path
