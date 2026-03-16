"""Tests for SchemaParser CDN mode — parse ACE from allAces + precompiled lang."""
import pytest
from unittest.mock import MagicMock

from src.ingest.schema_parser import SchemaParser, ACEEntry


@pytest.fixture
def mock_fetcher():
    f = MagicMock()
    f.fetch_all_aces.return_value = {
        "plugins": {
            "Sprite": {
                "animations": {
                    "conditions": [{
                        "id": "is-animation-playing",
                        "scriptName": "IsAnimPlaying",
                        "params": [{"id": "animation", "type": "animation"}],
                    }],
                    "actions": [{
                        "id": "set-animation",
                        "scriptName": "SetAnimation",
                        "params": [
                            {"id": "animation", "type": "animation"},
                            {"id": "from", "type": "combo", "items": ["beginning", "current-frame"]},
                        ],
                    }],
                    "expressions": [{
                        "id": "animation-frame",
                        "expressionName": "AnimationFrame",
                        "returnType": "number",
                    }],
                }
            },
        },
        "behaviors": {
            "Platform": {
                "": {
                    "conditions": [{
                        "id": "is-on-floor",
                        "scriptName": "IsOnFloor",
                        "isTrigger": False,
                    }],
                    "actions": [],
                    "expressions": [{
                        "id": "speed",
                        "expressionName": "Speed",
                        "returnType": "number",
                    }],
                }
            },
        },
    }

    def _lang(locale):
        is_en = "en" in locale
        return {"text": {
            "plugins": {
                "sprite": {
                    "name": "Sprite" if is_en else "精灵",
                    "conditions": {
                        "is-animation-playing": {
                            "list-name": "Is playing" if is_en else "正在播放",
                            "description": "Test which animation is playing." if is_en else "检测当前播放的动画。",
                            "params": {
                                "animation": {"name": "Animation" if is_en else "动画"}
                            },
                        }
                    },
                    "actions": {
                        "set-animation": {
                            "list-name": "Set animation" if is_en else "设置动画",
                            "description": "Set the current animation." if is_en else "设置当前动画。",
                            "params": {
                                "animation": {"name": "Animation" if is_en else "动画"},
                                "from": {"name": "From" if is_en else "从"},
                            },
                        }
                    },
                    "expressions": {
                        "animation-frame": {
                            "translated-name": "AnimationFrame" if is_en else "动画帧",
                            "description": "Get current frame." if is_en else "获取当前帧。",
                        }
                    },
                },
            },
            "behaviors": {
                "platform": {
                    "name": "Platform" if is_en else "平台",
                    "conditions": {
                        "is-on-floor": {
                            "list-name": "Is on floor" if is_en else "在地面上",
                            "description": "Test if on floor." if is_en else "检测是否在地面。",
                        }
                    },
                    "actions": {},
                    "expressions": {
                        "speed": {
                            "translated-name": "Speed" if is_en else "速度",
                            "description": "Current speed." if is_en else "当前速度。",
                        }
                    },
                },
            },
        }}

    f.fetch_lang.side_effect = _lang
    return f


def test_parse_from_cdn(mock_fetcher):
    parser = SchemaParser(fetcher=mock_fetcher)
    entries = parser.parse_ace_entries()
    # 1 condition + 1 action + 1 expression from Sprite + 1 condition + 1 expression from Platform
    assert len(entries) == 5

    cond = next(e for e in entries if e.ace_id == "is-animation-playing")
    assert cond.name_en == "Is playing"
    assert cond.name_zh == "正在播放"
    assert cond.plugin_name == "Sprite"
    assert cond.plugin_name_zh == "精灵"
    assert cond.plugin_type == "plugin"
    assert cond.ace_type == "condition"
    assert cond.script_name == "IsAnimPlaying"
    assert cond.description_en == "Test which animation is playing."
    assert len(cond.params) == 1
    assert cond.params[0]["name_zh"] == "动画"


def test_action_with_params(mock_fetcher):
    parser = SchemaParser(fetcher=mock_fetcher)
    entries = parser.parse_ace_entries()
    action = next(e for e in entries if e.ace_id == "set-animation")
    assert action.ace_type == "action"
    assert action.name_zh == "设置动画"
    assert len(action.params) == 2
    assert action.params[1]["items"] == ["beginning", "current-frame"]


def test_expression_uses_translated_name(mock_fetcher):
    parser = SchemaParser(fetcher=mock_fetcher)
    entries = parser.parse_ace_entries()
    expr = next(e for e in entries if e.ace_id == "animation-frame")
    assert expr.ace_type == "expression"
    assert expr.name_en == "AnimationFrame"
    assert expr.name_zh == "动画帧"
    assert expr.return_type == "number"


def test_behavior_parsed(mock_fetcher):
    parser = SchemaParser(fetcher=mock_fetcher)
    entries = parser.parse_ace_entries()
    beh = next(e for e in entries if e.plugin_name == "Platform")
    assert beh.plugin_type == "behavior"
    assert beh.plugin_name_zh == "平台"


def test_export_vectordb_format(mock_fetcher):
    parser = SchemaParser(fetcher=mock_fetcher)
    entries = parser.parse_ace_entries()
    docs = parser.export_ace_for_vectordb(entries)
    assert len(docs) == 5
    assert all("text" in d and "metadata" in d for d in docs)
    sprite_doc = next(d for d in docs if d["metadata"]["ace_id"] == "is-animation-playing")
    assert "精灵" in sprite_doc["text"]
    assert "Sprite" in sprite_doc["text"]


def test_effects_from_cdn(mock_fetcher):
    """Effects are parsed from CDN allEffects.json + lang."""
    mock_fetcher.fetch_effects.return_value = [{
        "json": {"id": "blur", "category": "blending", "parameters": []}
    }]
    parser = SchemaParser(fetcher=mock_fetcher)
    effects = parser.parse_effects()
    assert len(effects) >= 1
    assert effects[0].id == "blur"
