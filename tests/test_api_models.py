"""Tests for API response models — no external services required."""
import pytest
from src.api import SearchRequest, LookupSection, LookupMatchResult, ACELocaleResult, PluginInfo, LookupDebug


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


def test_lookup_match_to_dict_zh():
    m = LookupMatchResult(
        ace_id="on-collision", ace_type="condition",
        plugin_id="sprite",
        en=ACELocaleResult(name="On collision"),
        localized=ACELocaleResult(name="碰撞"),
    )
    d = m.to_dict(lang="zh")
    assert "i18n" in d
    assert "en" in d["i18n"]
    assert "zh" in d["i18n"]
    assert d["i18n"]["zh"]["name"] == "碰撞"


def test_lookup_match_to_dict_en():
    m = LookupMatchResult(
        ace_id="test", ace_type="condition", plugin_id="sprite",
        en=ACELocaleResult(name="Test"),
    )
    d = m.to_dict(lang="")
    assert "i18n" in d
    assert d["i18n"]["en"]["name"] == "Test"
    assert "zh" not in d["i18n"]


def test_lookup_section_empty():
    section = LookupSection()
    assert section.matches is None
    assert section.context is None
