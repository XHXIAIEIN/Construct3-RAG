"""Tests for API response models — no external services required."""
import pytest
from pydantic import ValidationError

from src.application.models import SearchCommand, SearchOutcome
from src.domain.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse
from src.api import (
    ACELocaleResult,
    DocResult,
    LookupDebug,
    LookupItemResult,
    LookupMatchResult,
    LookupSection,
    PluginInfo,
    SearchRequest,
    SemanticSection,
)
from src.interfaces.http.presenters import present_search_outcome


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
    assert "name" in d
    assert "en" in d["name"]
    assert "zh" in d["name"]
    assert d["name"]["zh"]["name"] == "碰撞"


def test_lookup_match_to_dict_en():
    m = LookupMatchResult(
        ace_id="test", ace_type="condition", plugin_id="sprite",
        en=ACELocaleResult(name="Test"),
    )
    d = m.to_dict(lang="")
    assert "name" in d
    assert d["name"]["en"]["name"] == "Test"
    assert "zh" not in d["name"]


def test_lookup_section_empty():
    section = LookupSection()
    assert section.matches is None
    assert section.context is None


@pytest.mark.parametrize("query", ["", " ", "\t\r\n"])
def test_search_request_rejects_blank_query(query):
    with pytest.raises(ValidationError):
        SearchRequest(query=query)


def test_search_request_rejects_unknown_language():
    with pytest.raises(ValidationError):
        SearchRequest(query="test", lang="xx")


@pytest.mark.parametrize("mode", ["lookup", "list"])
@pytest.mark.parametrize(
    "semantic_filter",
    [
        {"plugin": "Sprite"},
        {"collections": ["plugins"]},
        {"section_types": ["actions"]},
    ],
)
def test_lookup_modes_reject_semantic_filters(mode, semantic_filter):
    with pytest.raises(ValidationError):
        SearchRequest(query="test", mode=mode, **semantic_filter)


def test_semantic_section_parses_typed_results_and_context_tier():
    section = SemanticSection(
        docs=[{"score": 0.9, "content": "Sprite docs", "context_tier": "full"}]
    )

    assert isinstance(section.docs[0], DocResult)
    assert section.docs[0].context_tier == "full"


def test_lookup_section_has_no_private_application_state():
    assert LookupSection.__private_attributes__ == {}


def test_lookup_section_parses_typed_nested_items():
    section = LookupSection(
        matches={
            "sprite": {
                "actions": [
                    {
                        "ace_id": "set-animation",
                        "name": {"en": {"name": "Set animation"}},
                    }
                ]
            }
        }
    )

    item = section.matches["sprite"]["actions"][0]
    assert isinstance(item, LookupItemResult)
    assert item.name["en"].name == "Set animation"


def test_ja_hint_does_not_relabel_chinese_lookup_text():
    lookup = LookupResponse(
        intent=LookupIntent(intent_type="ace_search", plugin_id="sprite"),
        matches=[
            LookupMatch(
                ace_id="destroy",
                ace_type="action",
                plugin_id="sprite",
                collection="plugins",
                en=ACELocale(name="Destroy"),
                zh=ACELocale(name="销毁"),
            )
        ],
    )
    response = present_search_outcome(
        SearchOutcome(
            command=SearchCommand(query="Sprite destroy", lang="ja", mode="lookup"),
            lang="ja",
            elapsed_ms=0.1,
            lookup_result=lookup,
            semantic_results=(),
            timing_ms={"lookup": 0.1},
            semantic_candidates=0,
        )
    )

    names = response.lookup.matches["sprite"]["actions"][0].name
    assert names["en"].name == "Destroy"
    assert "ja" not in names
    assert "zh" not in names
