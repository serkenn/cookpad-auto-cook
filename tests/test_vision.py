"""Tests for vision backends (mocked API calls)."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cookpad.fridge.config import FridgeConfig, load_config
from cookpad.fridge.vision import DetectedIngredient, VisionBackend, create_backend
from cookpad.fridge.vision.claude import ClaudeVisionBackend, _parse_response
from cookpad.fridge.vision.gemini import GeminiVisionBackend
from cookpad.fridge.vision.gemini import _parse_response as gemini_parse_response


class TestDetectedIngredient:
    def test_dataclass(self):
        ing = DetectedIngredient(name="トマト", confidence=0.9, category="野菜")
        assert ing.name == "トマト"
        assert ing.confidence == 0.9
        assert ing.category == "野菜"


class TestCreateBackend:
    def test_create_claude_backend(self):
        config = load_config()
        backend = create_backend(config)
        assert isinstance(backend, ClaudeVisionBackend)

    def test_create_gemini_backend(self):
        config = load_config()
        config.vision.backend = "gemini"
        backend = create_backend(config)
        assert isinstance(backend, GeminiVisionBackend)

    def test_create_unknown_backend(self):
        config = load_config()
        config.vision.backend = "unknown"
        with pytest.raises(ValueError, match="不明なVisionバックエンド"):
            create_backend(config)


class TestClaudeParseResponse:
    def test_parse_json_array(self):
        text = json.dumps([
            {"name": "トマト", "confidence": 0.95, "category": "野菜"},
            {"name": "鶏肉", "confidence": 0.8, "category": "肉"},
        ])
        result = _parse_response(text)
        assert len(result) == 2
        assert result[0].name == "トマト"
        assert result[1].name == "鶏肉"

    def test_parse_with_markdown_fences(self):
        text = """```json
[
  {"name": "卵", "confidence": 0.9, "category": "卵"},
  {"name": "牛乳", "confidence": 0.7, "category": "乳製品"}
]
```"""
        result = _parse_response(text)
        assert len(result) == 2
        assert result[0].name == "卵"

    def test_parse_deduplicates_by_name(self):
        text = json.dumps([
            {"name": "トマト", "confidence": 0.6, "category": "野菜"},
            {"name": "トマト", "confidence": 0.9, "category": "野菜"},
        ])
        result = _parse_response(text)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_parse_default_category(self):
        text = json.dumps([
            {"name": "何か", "confidence": 0.5},
        ])
        result = _parse_response(text)
        assert result[0].category == "その他"


class TestGeminiParseResponse:
    def test_parse_json_array(self):
        text = json.dumps([
            {"name": "にんじん", "confidence": 0.85, "category": "野菜"},
        ])
        result = gemini_parse_response(text)
        assert len(result) == 1
        assert result[0].name == "にんじん"


class TestClaudeVisionBackend:
    @pytest.mark.asyncio
    async def test_detect_requires_api_key(self):
        backend = ClaudeVisionBackend(api_key="")
        with pytest.raises(ValueError, match="APIキー"):
            await backend.detect_ingredients(["/tmp/test.jpg"])

    @pytest.mark.asyncio
    async def test_detect_ingredients_mocked(self, tmp_path):
        """Test Claude backend with mocked API call."""
        # Create a fake image file
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps([
                    {"name": "トマト", "confidence": 0.95, "category": "野菜"},
                    {"name": "きゅうり", "confidence": 0.8, "category": "野菜"},
                ])
            )
        ]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            backend = ClaudeVisionBackend(api_key="test-key")
            result = await backend.detect_ingredients([str(img)])

        assert len(result) == 2
        assert result[0].name == "トマト"


class TestGeminiVisionBackend:
    @pytest.mark.asyncio
    async def test_detect_requires_api_key(self):
        backend = GeminiVisionBackend(api_key="")
        with pytest.raises(ValueError, match="APIキー"):
            await backend.detect_ingredients(["/tmp/test.jpg"])
