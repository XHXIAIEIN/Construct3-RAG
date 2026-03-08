"""Tests for examples_parser - no external services required."""
import json
import pytest
from pathlib import Path
from src.ingest.examples_parser import build_embed_text, load_examples_for_vectordb, _parse_tags


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

    def test_load_returns_list(self):
        docs = load_examples_for_vectordb()
        assert isinstance(docs, list)
        assert len(docs) > 0
        assert "id" in docs[0]
        assert "text" in docs[0]
        assert "metadata" in docs[0]
        assert "slug" in docs[0]["metadata"]

    def test_load_embed_text_not_empty(self):
        docs = load_examples_for_vectordb()
        for doc in docs:
            assert doc["text"].strip(), f"Empty embed text for {doc['id']}"
