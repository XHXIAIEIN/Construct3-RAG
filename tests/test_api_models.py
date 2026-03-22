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


def test_search_request_mode_list():
    req = SearchRequest(query="test", mode="list")
    assert req.mode == "list"


def test_search_request_mode_invalid():
    with pytest.raises(Exception):
        SearchRequest(query="test", mode="invalid")


def test_lookup_section_with_lang():
    m = LookupMatchResult(
        ace_id="on-collision", ace_type="condition",
        plugin_id="sprite",
        en=ACELocaleResult(name="On collision"),
        localized=ACELocaleResult(name="碰撞"),
    )
    section = LookupSection(
        hit=True, tier=1, confidence=0.85,
        intent="ace_search",
        lang="zh",
        plugin=PluginInfo(id="sprite", name="Sprite", name_localized="精灵"),
        keywords=["碰撞"],
        matches={"sprite": [m]},
    )
    assert section.hit is True
    assert section.lang == "zh"
    assert section.matches["sprite"][0].localized.name == "碰撞"


def test_lookup_section_en_only():
    section = LookupSection(
        hit=True, tier=1, intent="ace_list",
        matches={"sprite": [LookupMatchResult(
            ace_id="test", ace_type="condition", plugin_id="sprite",
            en=ACELocaleResult(name="Test"),
        )]},
    )
    assert section.lang is None
    assert section.matches["sprite"][0].localized is None


def test_lookup_section_no_hit():
    section = LookupSection(hit=False)
    assert section.matches is None
    assert section.context is None
