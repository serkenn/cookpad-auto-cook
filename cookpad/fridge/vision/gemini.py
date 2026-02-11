"""Gemini API vision backend for ingredient detection."""

from __future__ import annotations

import json
from pathlib import Path

from . import DetectedIngredient, VisionBackend

_PROMPT = """\
この画像は冷蔵庫の中を撮影したものです。
写っている食材をすべて日本語で列挙してください。

以下のJSON形式で返してください（他のテキストは不要です）:
[
  {"name": "食材名", "confidence": 0.0〜1.0, "category": "カテゴリ"}
]

カテゴリは以下から選んでください:
野菜, 果物, 肉, 魚, 卵, 乳製品, 豆腐・大豆, 調味料, 飲料, 穀物, その他

confidence は食材がはっきり見える場合は 0.8〜1.0、
やや不確かな場合は 0.5〜0.8、ほとんど見えない場合は 0.5 未満としてください。
"""


class GeminiVisionBackend(VisionBackend):
    """Detect fridge ingredients using Google Gemini's vision capability."""

    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model = model

    async def detect_ingredients(
        self, image_paths: list[str]
    ) -> list[DetectedIngredient]:
        if not self._api_key:
            raise ValueError(
                "Gemini APIキーが設定されていません。"
                "設定ファイルまたは GEMINI_API_KEY 環境変数を確認してください。"
            )

        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai SDK is required: pip install google-generativeai"
            ) from None

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model)

        parts: list = []
        for path in image_paths:
            data = Path(path).read_bytes()
            parts.append({"mime_type": "image/jpeg", "data": data})
        parts.append(_PROMPT)

        response = await model.generate_content_async(parts)
        return _parse_response(response.text)


def _parse_response(text: str) -> list[DetectedIngredient]:
    """Parse the JSON array from Gemini's response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    items = json.loads(cleaned)
    seen: dict[str, DetectedIngredient] = {}
    for item in items:
        name = item["name"]
        if name in seen:
            if item["confidence"] > seen[name].confidence:
                seen[name] = DetectedIngredient(
                    name=name,
                    confidence=item["confidence"],
                    category=item.get("category", "その他"),
                )
        else:
            seen[name] = DetectedIngredient(
                name=name,
                confidence=item["confidence"],
                category=item.get("category", "その他"),
            )
    return list(seen.values())
