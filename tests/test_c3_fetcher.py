"""Tests for C3Fetcher — CDN access layer with weekly cache expiry."""
import json
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ingest.c3_fetcher import C3Fetcher, _cache_expired
from src.ingest.common_aces import COMMON_PROPERTIES


@pytest.fixture
def fetcher(tmp_path):
    return C3Fetcher(version="r476", cache_dir=tmp_path)


def test_fetch_caches_locally(fetcher):
    """Fetched data is cached to disk."""
    mock_data = {"pluginList": {"Sprite": {"path": "general/sprite"}}}
    with patch.object(fetcher, "_http_get", return_value=json.dumps(mock_data).encode()):
        result = fetcher.fetch("plugins/pluginList.json")
        assert result == mock_data
        # Second call should use cache, not HTTP
        fetcher._http_get = MagicMock(side_effect=Exception("should not be called"))
        result2 = fetcher.fetch("plugins/pluginList.json")
        assert result2 == mock_data


def test_fetch_force_bypasses_cache(fetcher):
    """force=True always hits HTTP even if cache exists."""
    data_v1 = {"v": 1}
    data_v2 = {"v": 2}
    with patch.object(fetcher, "_http_get", return_value=json.dumps(data_v1).encode()):
        fetcher.fetch("test.json")
    with patch.object(fetcher, "_http_get", return_value=json.dumps(data_v2).encode()):
        result = fetcher.fetch("test.json", force=True)
        assert result == data_v2


def test_handles_bom(fetcher):
    """UTF-8 BOM in response is stripped."""
    mock_data = {"ok": True}
    bom_bytes = b"\xef\xbb\xbf" + json.dumps(mock_data).encode()
    with patch.object(fetcher, "_http_get", return_value=bom_bytes):
        result = fetcher.fetch("bom_test.json")
        assert result == mock_data


def test_get_latest_version(fetcher):
    """Detect latest stable version from versions.json."""
    mock_versions = [
        {"branchName": "Beta", "releaseName": "r477"},
        {"branchName": "Stable", "releaseName": "r476"},
        {"branchName": "LTS", "releaseName": "r449.3"},
    ]
    with patch.object(fetcher, "_http_get", return_value=json.dumps(mock_versions).encode()):
        assert fetcher.get_latest_stable_version() == "r476"


def test_cache_expired_old_file(tmp_path):
    """Cache files older than 10 days are always expired (crosses a Wednesday)."""
    cache_file = tmp_path / "test_cache"
    cache_file.write_text("old")
    old_time = time.time() - 10 * 86400
    os.utime(cache_file, (old_time, old_time))
    assert _cache_expired(cache_file) is True


def test_cache_fresh_file(tmp_path):
    """Cache files written just now should not be expired."""
    cache_file = tmp_path / "test_cache"
    cache_file.write_text("fresh")
    assert _cache_expired(cache_file) is False


def test_cache_nonexistent_file(tmp_path):
    """Non-existent file counts as expired."""
    assert _cache_expired(tmp_path / "nope") is True


def test_fetch_all_aces(fetcher):
    """Convenience method returns joined plugin + behavior ACEs."""
    mock_plugin_aces = {"Sprite": {"": {"conditions": [{"id": "c1"}]}}}
    mock_behavior_aces = {"Platform": {"": {"actions": [{"id": "a1"}]}}}
    with patch.object(fetcher, "fetch", side_effect=[mock_plugin_aces, mock_behavior_aces]):
        result = fetcher.fetch_all_aces()
        assert "Sprite" in result["plugins"]
        assert "Platform" in result["behaviors"]


def test_fetch_examples(fetcher):
    """fetch_examples unwraps the 'projects' key."""
    mock = {"projects": [{"id": "demo"}]}
    with patch.object(fetcher, "fetch", return_value=mock):
        result = fetcher.fetch_examples()
        assert result == [{"id": "demo"}]


def test_fetch_effects(fetcher):
    """fetch_effects unwraps the 'all' key."""
    mock = {"all": [{"json": {"id": "blur"}}]}
    with patch.object(fetcher, "fetch", return_value=mock):
        result = fetcher.fetch_effects()
        assert result == [{"json": {"id": "blur"}}]


def test_export_lang_writes_readable_json_per_locale(fetcher):
    """Language packs are written per locale, pretty printed, without ASCII escaping."""
    payload = {
        "en-US": {"languageTag": "en-US", "text": {"plugins": {"sprite": {"name": "Sprite"}}}},
        "zh-CN": {"languageTag": "zh-CN", "text": {"plugins": {"sprite": {"name": "精灵"}}}},
    }
    with patch.object(fetcher, "fetch_lang", side_effect=lambda locale="en-US": payload[locale]):
        out_dir = fetcher.export_lang(("en-US", "zh-CN"))

    assert out_dir == fetcher.cache_dir / "lang"
    assert sorted(p.name for p in out_dir.glob("*.json")) == ["en-US.json", "zh-CN.json"]
    zh_text = (out_dir / "zh-CN.json").read_text(encoding="utf-8")
    assert json.loads(zh_text) == payload["zh-CN"]
    assert "精灵" in zh_text
    assert zh_text.count("\n") > 3


def test_export_schemas_keeps_root_index_language_neutral(fetcher):
    """Localized names go to {locale}/_index.json; the root index stays structural."""
    from src.lookup.indexes import SchemaIndex
    from src.lookup.schema_layout import schema_is_complete

    aces = {
        "plugins": {"Sprite": {"general": {
            "conditions": [{"id": "is-visible", "scriptName": "isVisible"}],
            "actions": [],
            "expressions": [],
        }}},
        "behaviors": {"Platform": {"general": {
            "conditions": [],
            "actions": [{"id": "set-speed", "scriptName": "setSpeed",
                         "params": [{"id": "speed", "type": "number"}]}],
            "expressions": [],
        }}},
    }
    texts = {
        "en-US": {"text": {
            "plugins": {"sprite": {"name": "Sprite",
                                   "conditions": {"is-visible": {"list-name": "Is visible"}}},
                        "_common": {"name": "Common",
                                    "actions": {"destroy": {"list-name": "Destroy"},
                                                "set-visible": {"list-name": "Set visible",
                                                                "params": {"visibility": {"name": "Visibility",
                                                                                          "items": {"invisible": "Invisible", "visible": "Visible", "toggle": "Toggle"}}}}}}},
            "behaviors": {"platform": {"name": "Platform",
                                       "actions": {"set-speed": {"list-name": "Set speed"}}}},
            "effects": {"blur": {"name": "Blur"}},
            **_instance_properties(),
        }},
        "zh-CN": {"text": {
            "plugins": {"sprite": {"name": "精灵",
                                   "conditions": {"is-visible": {"list-name": "可见"}}},
                        "_common": {"name": "公共",
                                    "actions": {"destroy": {"list-name": "销毁"},
                                                "set-visible": {"list-name": "设置可见性",
                                                                "params": {"visibility": {"name": "可见性",
                                                                                          "items": {"invisible": "不可见", "visible": "可见", "toggle": "切换"}}}}}}},
            "behaviors": {"platform": {"name": "平台",
                                       "actions": {"set-speed": {"list-name": "设置速度"}}}},
            "effects": {"blur": {"name": "模糊"}},
            **_instance_properties(),
        }},
    }
    effects = [{"id": "blur", "category": "blur", "parameters": []}]
    with patch.object(fetcher, "fetch_all_aces", return_value=aces), \
         patch.object(fetcher, "fetch_lang", side_effect=lambda locale="en-US": texts[locale]), \
         patch.object(fetcher, "fetch_effects", return_value=effects), \
         patch.object(fetcher, "fetch_examples", return_value=[]):
        schemas_dir = fetcher.export_schemas()

    root_text = (schemas_dir / "_index.json").read_text(encoding="utf-8")
    root = json.loads(root_text)
    assert root["version"] == fetcher.version
    assert root["languages"] == ["en-US", "zh-CN"]
    assert "supported_languages" not in root
    assert "name_en" not in root_text and "name_zh" not in root_text
    assert root["plugins"]["sprite"] == {
        "originalId": "Sprite", "file": "plugins/sprite.json",
        "conditions": 1, "actions": 0, "expressions": 0,
    }
    assert root["effects"]["blur"] == {"file": "effects/blur.json", "category": "blur"}
    assert root["plugins"]["_common"] == {
        "file": "plugins/_common.json", "conditions": 0, "actions": 2, "expressions": 0,
    }

    en = json.loads((schemas_dir / "en-US" / "_index.json").read_text(encoding="utf-8"))
    zh = json.loads((schemas_dir / "zh-CN" / "_index.json").read_text(encoding="utf-8"))
    assert (en["version"], en["language"]) == (fetcher.version, "en-US")
    assert en["plugins"]["sprite"] == {"name": "Sprite", "file": "plugins/sprite.json"}
    assert zh["plugins"]["sprite"] == {"name": "精灵", "file": "plugins/sprite.json"}
    assert zh["behaviors"]["platform"]["name"] == "平台"
    assert zh["plugins"]["_common"] == {"name": "公共", "file": "plugins/_common.json"}
    assert zh["effects"]["blur"] == {"name": "模糊", "file": "effects/blur.json"}

    assert schema_is_complete(schemas_dir)
    assert SchemaIndex(schemas_dir).find_effect_in_query("模糊") == ("blur", 0, 2)


def _export_with(fetcher, texts):
    aces = {"plugins": {}, "behaviors": {}}
    with patch.object(fetcher, "fetch_all_aces", return_value=aces),          patch.object(fetcher, "fetch_lang", side_effect=lambda locale="en-US": texts[locale]),          patch.object(fetcher, "fetch_effects", return_value=[]),          patch.object(fetcher, "fetch_examples", return_value=[]):
        return fetcher.export_schemas()


def _instance_properties() -> dict:
    """What a pack holds for the shared world-instance properties. A real one
    has it under ui.bars.properties.instance, not in its _common entry, which
    is why the export reads both; a pack missing a path stops the export
    (tests/test_common_aces.py)."""
    instance: dict = {}
    for prop_id, path, _ in COMMON_PROPERTIES:
        node = instance
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = {"name": prop_id.title(), "desc": f"The {prop_id} of this instance."}
    return {"ui": {"bars": {"properties": {"instance": instance}}}}


def _common_texts(en_actions, zh_actions):
    return {
        "en-US": {"text": {"plugins": {"_common": {"actions": en_actions}}, **_instance_properties()}},
        "zh-CN": {"text": {"plugins": {"_common": {"actions": zh_actions}}, **_instance_properties()}},
    }


def test_export_common_merges_bundle_structure_with_language_text(fetcher):
    """_common gets the same structural fields as a plugin: real type, items
    labelled per locale, initialValue, scriptName and editor category."""
    texts = _common_texts(
        {"set-visible": {"list-name": "Set visible", "display-text": "Set {0}",
                         "params": {"visibility": {"name": "Visibility", "desc": "Which.",
                                                   "items": {"invisible": "Invisible", "visible": "Visible", "toggle": "Toggle"}}}}},
        {"set-visible": {"list-name": "设置可见性", "display-text": "设置 {0}",
                         "params": {"visibility": {"name": "可见性", "desc": "哪种。",
                                                   "items": {"invisible": "不可见", "visible": "可见", "toggle": "切换"}}}}},
    )
    schemas_dir = _export_with(fetcher, texts)

    en = json.loads((schemas_dir / "en-US" / "plugins" / "_common.json").read_text(encoding="utf-8"))
    zh = json.loads((schemas_dir / "zh-CN" / "plugins" / "_common.json").read_text(encoding="utf-8"))
    assert (en["name"], zh["name"]) == ("Common", "Common")  # neither pack names it here
    assert en["actions"] == [{
        "id": "set-visible", "scriptName": "SetVisible", "category": "appearance",
        "list-name": "Set visible", "display-text": "Set {0}", "description": "",
        "params": {"visibility": {
            "type": "combo", "name": "Visibility", "desc": "Which.",
            "items": {"invisible": "Invisible", "visible": "Visible", "toggle": "Toggle"},
            "initialValue": "visible",
        }},
    }]
    assert zh["actions"][0]["params"]["visibility"]["items"] == {"invisible": "不可见", "visible": "可见", "toggle": "切换"}
    assert zh["actions"][0]["params"]["visibility"]["type"] == "combo"
    zh_index = json.loads((schemas_dir / "zh-CN" / "_index.json").read_text(encoding="utf-8"))
    assert zh_index["plugins"]["_common"] == {"name": "Common", "file": "plugins/_common.json"}


def test_export_marks_every_condition_the_editor_treats_as_a_trigger(fetcher):
    """A fake trigger (On timer, On collision) is a trigger to the editor: one
    per event branch, never inverted. isTrigger says so, the structural flags
    that decide where a condition may go are kept, and defaults stay absent."""
    aces = {
        "plugins": {"system": {"general": {
            "conditions": [
                {"id": "on-start-of-layout", "scriptName": "OnLayoutStart", "isTrigger": True},
                {"id": "for-each", "scriptName": "ForEach", "isLooping": True},
                {"id": "else", "scriptName": "Else", "isInvertible": False, "isCompatibleWithTriggers": False},
                {"id": "every-tick", "scriptName": "EveryTick"},
            ],
            "actions": [], "expressions": [],
        }}},
        "behaviors": {"Timer": {"general": {
            "conditions": [{"id": "on-timer", "scriptName": "OnTimer", "isFakeTrigger": True}],
            "actions": [], "expressions": [],
        }}},
    }
    ids = ("on-start-of-layout", "for-each", "else", "every-tick")
    text = {"text": {
        "plugins": {"system": {"name": "System", "conditions": {i: {"list-name": i} for i in ids}}},
        "behaviors": {"timer": {"name": "Timer", "conditions": {"on-timer": {"list-name": "On timer"}}}},
    }}
    with patch.object(fetcher, "fetch_all_aces", return_value=aces), \
         patch.object(fetcher, "fetch_lang", return_value=text), \
         patch.object(fetcher, "fetch_effects", return_value=[]), \
         patch.object(fetcher, "fetch_examples", return_value=[]):
        schemas_dir = fetcher.export_schemas()

    flags = ("isTrigger", "isFakeTrigger", "isLooping", "isInvertible", "isCompatibleWithTriggers")
    system = json.loads((schemas_dir / "en-US" / "plugins" / "system.json").read_text(encoding="utf-8"))
    timer = json.loads((schemas_dir / "en-US" / "behaviors" / "timer.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: {k: c[k] for k in flags if k in c} for c in system["conditions"] + timer["conditions"]}
    assert by_id == {
        "on-start-of-layout": {"isTrigger": True},
        "for-each": {"isLooping": True},
        "else": {"isInvertible": False, "isCompatibleWithTriggers": False},
        "every-tick": {},
        "on-timer": {"isTrigger": True, "isFakeTrigger": True},
    }


def test_export_stops_when_language_pack_names_an_unknown_common_ace(fetcher):
    """A shared ACE the committed extract lacks must not be exported with guessed types."""
    texts = _common_texts(
        {"destroy": {"list-name": "Destroy"}, "levitate": {"list-name": "Levitate"}},
        {"destroy": {"list-name": "销毁"}, "levitate": {"list-name": "悬浮"}},
    )
    with pytest.raises(ValueError, match="actions/levitate"):
        _export_with(fetcher, texts)
    assert not (fetcher.cache_dir / "schemas" / ".exported").exists()


def test_export_to_data_replaces_committed_directories_without_cache_markers(fetcher, tmp_path):
    """data/ mirrors the four exports; stale files and dot-markers do not survive."""
    schemas_dir = fetcher.cache_dir / "schemas"
    (schemas_dir / "en-US" / "plugins").mkdir(parents=True)
    (schemas_dir / "en-US" / "plugins" / "sprite.json").write_text("{}", encoding="utf-8")
    (schemas_dir / "_index.json").write_text("{}", encoding="utf-8")
    (schemas_dir / ".exported").write_text(fetcher.version, encoding="utf-8")
    examples_dir = fetcher.cache_dir / "examples" / "zh-CN"
    examples_dir.mkdir(parents=True)
    (examples_dir / "demo.json").write_text("{}", encoding="utf-8")
    lang_dir = fetcher.cache_dir / "lang"
    lang_dir.mkdir()
    (lang_dir / "en-US.json").write_text("{}", encoding="utf-8")
    ts_dir = fetcher.cache_dir / "ts-defs"
    (ts_dir / "plugins").mkdir(parents=True)
    (ts_dir / "plugins" / "sprite.d.ts").write_text("interface X {}", encoding="utf-8")
    (ts_dir / "autocomplete-data.json").write_text("{}", encoding="utf-8")
    (ts_dir / ".exported").write_text(fetcher.version, encoding="utf-8")

    data_dir = tmp_path / "data"
    stale = data_dir / "c3-schemas" / "en-US" / "plugins" / "retired.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")

    with patch.object(fetcher, "export_schemas", return_value=schemas_dir) as schemas, \
         patch.object(fetcher, "export_lang", return_value=lang_dir) as lang, \
         patch.object(fetcher, "export_ts_defs", return_value=ts_dir) as ts:
        targets = fetcher.export_to_data(data_dir)

    assert schemas.called and lang.called and ts.called
    assert targets["c3-schemas"] == data_dir / "c3-schemas"
    assert (data_dir / "c3-schemas" / "en-US" / "plugins" / "sprite.json").exists()
    assert (data_dir / "c3-schemas" / "_index.json").exists()
    assert not stale.exists()
    assert not (data_dir / "c3-schemas" / ".exported").exists()
    assert (data_dir / "c3-examples" / "zh-CN" / "demo.json").exists()
    assert (data_dir / "c3-lang" / "en-US.json").exists()
    assert (data_dir / "c3-ts-defs" / "plugins" / "sprite.d.ts").exists()
    assert (data_dir / "c3-ts-defs" / "autocomplete-data.json").exists()
    assert not (data_dir / "c3-ts-defs" / ".exported").exists()
