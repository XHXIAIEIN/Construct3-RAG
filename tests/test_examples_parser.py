"""Tests for examples_parser - no external services required."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.ingest.examples_parser import build_embed_text, load_examples_for_vectordb, _parse_tags


@pytest.fixture
def mock_fetcher():
    f = MagicMock()
    f.fetch_examples.return_value = [
        {
            "id": "platformer-basics",
            "tags": ["beginner", "game-template", "platformer"],
            "used-addons": {
                "plugins": ["Sprite", "Keyboard"],
                "behaviors": ["Platform", "Solid"],
                "effects": [],
            },
        },
        {
            "id": "particle-demo",
            "tags": ["intermediate", "effect-blur"],
            "used-addons": {
                "plugins": ["Particles"],
                "behaviors": [],
                "effects": ["blur"],
            },
        },
    ]
    return f


class TestParseTagsAndEmbed:
    def test_parse_plugin_tags(self):
        parsed = _parse_tags(["plugin-Sprite", "plugin-Tween", "beginner"])
        assert "Sprite" in parsed["plugins"]
        assert "Tween" in parsed["plugins"]
        assert parsed["level"] == "beginner"

    def test_parse_behavior_tags(self):
        parsed = _parse_tags(["behavior-Platform", "behavior-Tween"])
        assert "Platform" in parsed["behaviors"]
        assert "Tween" in parsed["behaviors"]

    def test_parse_effect_tags(self):
        parsed = _parse_tags(["effect-blur", "effect-noise"])
        assert "blur" in parsed["effects"]

    def test_build_embed_text_basic(self):
        parsed = _parse_tags(["plugin-Sprite", "behavior-Platform", "platformer", "intermediate"])
        text = build_embed_text("平台游戏", "Platform Game", parsed)
        assert "平台游戏" in text
        assert "Platform Game" in text
        assert "Sprite" in text
        assert "Platform" in text
        assert "platformer" in text
        assert "intermediate" in text

    def test_build_embed_text_same_title(self):
        parsed = _parse_tags(["plugin-Sprite"])
        text = build_embed_text("Cave Bridge", "Cave Bridge", parsed)
        assert text.count("Cave Bridge") == 1  # not duplicated

    def test_load_returns_list(self, mock_fetcher):
        docs = load_examples_for_vectordb(fetcher=mock_fetcher)
        assert isinstance(docs, list)
        assert len(docs) > 0
        assert "id" in docs[0]
        assert "text" in docs[0]
        assert "metadata" in docs[0]
        assert "slug" in docs[0]["metadata"]

    def test_load_embed_text_not_empty(self, mock_fetcher):
        docs = load_examples_for_vectordb(fetcher=mock_fetcher)
        for doc in docs:
            assert doc["text"].strip(), f"Empty embed text for {doc['id']}"
