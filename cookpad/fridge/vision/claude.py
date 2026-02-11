"""Claude API vision backend for ingredient detection."""

from __future__ import annotations

import base64
import json
import mimetypes
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


class ClaudeVisionBackend(VisionBackend):
    """Detect fridge ingredients using Claude's vision capability."""

    def __init__(self, api_key: str = "", model: str = "claude-sonnet-4-5-20250929") -> None:
        self._api_key = api_key
        self._model = model

    async def detect_ingredients(
        self, image_paths: list[str]
    ) -> list[DetectedIngredient]:
        if not self._api_key:
            raise ValueError(
                "Anthropic APIキーが設定されていません。"
                "設定ファイルまたは ANTHROPIC_API_KEY 環境変数を確認してください。"
            )

        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic SDK is required: pip install anthropic"
            ) from None

        content: list[dict] = []
        for path in image_paths:
            data = Path(path).read_bytes()
            media_type = mimetypes.guess_type(path)[0] or "image/jpeg"
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.standard_b64encode(data).decode(),
                    },
                }
            )
        content.append({"type": "text", "text": _PROMPT})

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        text = response.content[0].text
        return _parse_response(text)


def _parse_response(text: str) -> list[DetectedIngredient]:
    """Parse the JSON array from Claude's response."""
    # Strip markdown fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    items = json.loads(cleaned)
    seen: dict[str, DetectedIngredient] = {}
    for item in items:
        name = item["name"]
        if name in seen:
            # Keep higher confidence
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
