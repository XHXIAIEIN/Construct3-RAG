"""Tests for API response models — no external services required."""
import pytest
from src.api import SearchRequest, LookupSection, LookupMatchResult, ACELocaleResult, PluginInfo


def test_search_request_mode_default():
    req = SearchRequest(query="test")
    assert req.mode == "auto"


def test_search_request_mode_lookup():
    req = SearchRequest(query="test", mode="lookup")
    assert req.mode == "lookup"


def test_search_request_mode_semantic():
    req = SearchRequest(query="test", mode="semantic")
    assert req.mode == "semantic"


def test_search_request_mode_invalid():
    with pytest.raises(Exception):
        SearchRequest(query="test", mode="invalid")


def test_lookup_section_model():
    section = LookupSection(
        hit=True, tier=1, confidence=0.85,
        intent="ace_search",
        plugin=PluginInfo(id="sprite", name="Sprite", name_localized="精灵"),
        keywords=["碰撞"],
        matches=[LookupMatchResult(
            ace_id="on-collision", ace_type="condition",
            plugin_id="sprite",
            en=ACELocaleResult(name="On collision"),
            localized=ACELocaleResult(name="碰撞"),
            localized_lang="zh",
        )],
        context="C: On collision: ...",
    )
    assert section.hit is True
    assert len(section.matches) == 1
    assert section.matches[0].ace_id == "on-collision"
    assert section.matches[0].en.name == "On collision"
    assert section.matches[0].localized.name == "碰撞"
    assert section.matches[0].localized_lang == "zh"


def test_lookup_en_only():
    """English query: no localized field."""
    m = LookupMatchResult(
        ace_id="test", ace_type="condition", plugin_id="sprite",
        en=ACELocaleResult(name="Test"),
    )
    assert m.en.name == "Test"
    assert m.localized is None
    assert m.localized_lang is None


def test_lookup_section_no_hit():
    section = LookupSection(hit=False)
    assert section.matches == []
    assert section.context == ""
