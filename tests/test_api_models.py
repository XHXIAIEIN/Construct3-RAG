"""Tests for API response models — no external services required."""
import pytest
from pydantic import ValidationError

from src.application.models import SearchCommand, SearchOutcome
from src.domain.lookup import ACELocale, LookupIntent, LookupMatch, LookupResponse
from src.interfaces.http.models import (
    ACELocaleResult,
    LookupDebug,
    LookupItemResult,
    LookupMatchResult,
    LookupSection,
    SearchRequest,
)
from src.interfaces.http.presenters import present_search_outcome


def test_search_request_mode_default():
    req = SearchRequest(query="test")
    assert req.mode == "auto"


def test_search_request_mode_lookup():
    req = SearchRequest(query="test", mode="lookup")
    assert req.mode == "lookup"


def test_search_request_mode_list():
    req = SearchRequest(query="test", mode="list")
    assert req.mode == "list"


@pytest.mark.parametrize("mode", ["invalid", "semantic"])
def test_search_request_mode_invalid(mode):
    with pytest.raises(ValidationError):
        SearchRequest(query="test", mode=mode)


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


@pytest.mark.parametrize(
    "unknown_field",
    [
        {"plugin": "Sprite"},
        {"collections": ["plugins"]},
        {"top_k": 5},
    ],
)
def test_search_request_rejects_fields_it_does_not_have(unknown_field):
    with pytest.raises(ValidationError):
        SearchRequest(query="test", **unknown_field)


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
            timing_ms={"lookup": 0.1},
        )
    )

    names = response.lookup.matches["sprite"]["actions"][0].name
    assert names["en"].name == "Destroy"
    assert "ja" not in names
    assert "zh" not in names
