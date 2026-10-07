"""Tests for C3Fetcher — CDN access layer with weekly cache expiry."""
import json
import os
import re
import shutil
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingest.c3_fetcher import C3Fetcher, _cache_expired, _http_get, latest_stable_version
from src.ingest.common_aces import COMMON_PROPERTIES
from src.lookup.schema_index import SchemaIndex
from src.lookup.schema_layout import schema_is_complete

LOCALES = ("en-US", "zh-CN")


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


@pytest.mark.parametrize("version, directory", [("r495.2", "r495-2"), ("r503", "r503")])
def test_fetch_reads_the_release_directory_and_caches_under_the_release_name(tmp_path, version, directory):
    """A patch release is served under a dash (r495-2/); the cache keeps the dot."""
    fetcher = C3Fetcher(version=version, cache_dir=tmp_path)
    requested = []

    def cdn(url: str) -> bytes:
        requested.append(url)
        return b"{}" if url.endswith(".json") else b"// main.js"

    with patch.object(fetcher, "_http_get", side_effect=cdn):
        fetcher.fetch("plugins/allAces.json")
        fetcher.fetch_raw("main.js")

    assert requested == [
        f"https://editor.construct.net/{directory}/plugins/allAces.json",
        f"https://editor.construct.net/{directory}/main.js",
    ]
    assert fetcher.cache_dir == tmp_path / version
    assert (tmp_path / version / "plugins_allAces.json").exists()


@pytest.mark.parametrize("method", ["fetch", "fetch_raw"])
def test_a_missing_release_file_stops_instead_of_reading_the_root(tmp_path, method):
    """The root serves the current stable release; a 404 must not pull it in."""
    fetcher = C3Fetcher(version="r495.2", cache_dir=tmp_path)
    requested = []

    def cdn(url: str) -> bytes:
        requested.append(url)
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    with patch.object(fetcher, "_http_get", side_effect=cdn):
        with pytest.raises(FileNotFoundError, match="r495-2/plugins/allEditorPlugins.js returned 404"):
            getattr(fetcher, method)("plugins/allEditorPlugins.js")

    assert requested == ["https://editor.construct.net/r495-2/plugins/allEditorPlugins.js"]
    assert not (fetcher.cache_dir / "plugins_allEditorPlugins.js").exists()


@pytest.mark.parametrize("version", ["r495-2", "495.2", "latest", ""])
def test_release_is_named_as_versions_json_names_it(tmp_path, version):
    """The directory's spelling would label data/ and the cache with a release
    versions.json never names."""
    with pytest.raises(ValueError, match="r495.2"):
        C3Fetcher(version=version, cache_dir=tmp_path)


def test_latest_stable_version():
    """Detect latest stable version from versions.json."""
    mock_versions = [
        {"branchName": "Beta", "releaseName": "r477"},
        {"branchName": "Stable", "releaseName": "r476"},
        {"branchName": "LTS", "releaseName": "r449.3"},
    ]
    with patch("src.ingest.c3_fetcher._http_get", return_value=json.dumps(mock_versions).encode()) as cdn:
        assert latest_stable_version() == "r476"
    # The one file at the CDN root, not under a release.
    cdn.assert_called_once_with("https://editor.construct.net/versions.json")


def test_latest_stable_version_without_stable_fails():
    with patch("src.ingest.c3_fetcher._http_get", return_value=b"[]"):
        with pytest.raises(LookupError):
            latest_stable_version()


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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _editor_flags(aces: dict, deprecated: tuple[str, ...] = ()) -> dict:
    """What the editor bundles say of these addons: only ``deprecated`` are."""
    return {kind: {addon: addon in deprecated for addon in aces.get(kind, {})}
            for kind in ("plugins", "behaviors")}


def _export_with(fetcher: C3Fetcher, texts: dict[str, dict], aces: dict | None = None,
                 effects: list[dict] | None = None, flags: dict | None = None) -> Path:
    """Run export_schemas on these CDN files: ``texts`` holds the language pack
    of each locale, and ``flags`` default to the editor deprecating no addon."""
    if aces is None:
        aces = {"plugins": {}, "behaviors": {}}
    if flags is None:
        flags = _editor_flags(aces)
    with patch.object(fetcher, "fetch_all_aces", return_value=aces), \
         patch.object(fetcher, "fetch_addon_deprecation", return_value=flags), \
         patch.object(fetcher, "fetch_lang", side_effect=lambda locale="en-US": texts[locale]), \
         patch.object(fetcher, "fetch_effects", return_value=effects or []), \
         patch.object(fetcher, "fetch_examples", return_value=[]):
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


def _common_texts(en_actions: dict, zh_actions: dict) -> dict:
    return {
        "en-US": {"text": {"plugins": {"_common": {"actions": en_actions}}, **_instance_properties()}},
        "zh-CN": {"text": {"plugins": {"_common": {"actions": zh_actions}}, **_instance_properties()}},
    }


def test_export_schemas_keeps_root_index_language_neutral(fetcher):
    """Localized names go to {locale}/_index.json; the root index stays structural."""
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
    schemas_dir = _export_with(fetcher, texts, aces=aces, effects=effects)

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

    en = _read_json(schemas_dir / "en-US" / "_index.json")
    zh = _read_json(schemas_dir / "zh-CN" / "_index.json")
    assert (en["version"], en["language"]) == (fetcher.version, "en-US")
    assert en["plugins"]["sprite"] == {"name": "Sprite", "file": "plugins/sprite.json"}
    assert zh["plugins"]["sprite"] == {"name": "精灵", "file": "plugins/sprite.json"}
    assert zh["behaviors"]["platform"]["name"] == "平台"
    assert zh["plugins"]["_common"] == {"name": "公共", "file": "plugins/_common.json"}
    assert zh["effects"]["blur"] == {"name": "模糊", "file": "effects/blur.json"}

    assert schema_is_complete(schemas_dir)
    assert SchemaIndex(schemas_dir).find_effect_in_query("模糊") == (("blur",), 0, 2)


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

    en = _read_json(schemas_dir / "en-US" / "plugins" / "_common.json")
    zh = _read_json(schemas_dir / "zh-CN" / "plugins" / "_common.json")
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
    zh_index = _read_json(schemas_dir / "zh-CN" / "_index.json")
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
    schemas_dir = _export_with(fetcher, dict.fromkeys(LOCALES, text), aces=aces)

    flags = ("isTrigger", "isFakeTrigger", "isLooping", "isInvertible", "isCompatibleWithTriggers")
    system = _read_json(schemas_dir / "en-US" / "plugins" / "system.json")
    timer = _read_json(schemas_dir / "en-US" / "behaviors" / "timer.json")
    by_id = {c["id"]: {k: c[k] for k in flags if k in c} for c in system["conditions"] + timer["conditions"]}
    assert by_id == {
        "on-start-of-layout": {"isTrigger": True},
        "for-each": {"isLooping": True},
        "else": {"isInvertible": False, "isCompatibleWithTriggers": False},
        "every-tick": {},
        "on-timer": {"isTrigger": True, "isFakeTrigger": True},
    }


def test_export_keeps_the_default_the_editor_fills_in(fetcher):
    """Wait's "use time scale" is ticked when the action is added; a template that
    wrote false made every Wait ignore the time scale."""
    aces = {"plugins": {"system": {"time": {"conditions": [], "expressions": [], "actions": [
        {"id": "wait", "scriptName": "Wait", "params": [
            {"id": "seconds", "type": "number", "initialValue": "1.0"},
            {"id": "use-timescale", "type": "boolean", "initialValue": "true"},
            {"id": "note", "type": "string"},
        ]},
    ]}}}, "behaviors": {}}
    text = {"text": {"plugins": {"system": {"name": "System", "actions": {"wait": {"list-name": "Wait"}}}}}}
    schemas_dir = _export_with(fetcher, dict.fromkeys(LOCALES, text), aces=aces)

    for locale in LOCALES:
        params = _read_json(schemas_dir / locale / "plugins" / "system.json")["actions"][0]["params"]
        assert {k: v.get("initialValue") for k, v in params.items()} == \
            {"seconds": "1.0", "use-timescale": "true", "note": None}


def test_export_marks_an_expression_that_takes_more_arguments_than_it_lists(fetcher):
    """Mouse.X takes an optional layer and max any number of values; the parameters
    alone would make Mouse.X("HUD") read as a wrong call."""
    aces = {"plugins": {"Mouse": {"cursor": {"conditions": [], "actions": [], "expressions": [
        {"id": "x", "expressionName": "X", "returnType": "number", "isVariadicParameters": True},
        {"id": "absolute-x", "expressionName": "AbsoluteX", "returnType": "number"},
    ]}}}, "behaviors": {}}
    text = {"text": {"plugins": {"mouse": {"name": "Mouse", "expressions": {
        "x": {"translated-name": "X"}, "absolute-x": {"translated-name": "AbsoluteX"}}}}}}
    schemas_dir = _export_with(fetcher, dict.fromkeys(LOCALES, text), aces=aces)
    mouse = _read_json(schemas_dir / "en-US" / "plugins" / "mouse.json")
    assert {e["id"]: e.get("isVariadicParameters") for e in mouse["expressions"]} == {
        "x": True, "absolute-x": None}


def test_export_leaves_out_what_the_editor_deprecates_though_translated(fetcher):
    """NW.js and the old Warp are still in both language packs; the editor's
    flags, not the packs, keep them out of every file and index."""
    aces = {
        "plugins": {pid: {"general": {"conditions": [], "actions": [{"id": "act", "scriptName": "Act"}],
                                      "expressions": []}}
                    for pid in ("Sprite", "NodeWebkit")},
        "behaviors": {"Platform": {"general": {"conditions": [], "actions": [{"id": "act", "scriptName": "Act"}],
                                               "expressions": []}}},
    }
    effects = [
        {"json": {"id": "blur", "category": "blur", "parameters": []}},
        {"json": {"id": "warp", "category": "distortion", "is-deprecated": True, "parameters": []}},
    ]

    def pack(suffix: str) -> dict:
        addon = lambda name: {"name": name + suffix, "actions": {"act": {"list-name": "Act" + suffix}}}
        return {"text": {
            "plugins": {"sprite": addon("Sprite"), "nodewebkit": addon("NW.js")},
            "behaviors": {"platform": addon("Platform")},
            "effects": {"blur": {"name": "Blur" + suffix}, "warp": {"name": "Warp" + suffix}},
        }}

    texts = {"en-US": pack(""), "zh-CN": pack(" 中")}
    schemas_dir = _export_with(fetcher, texts, aces=aces, effects=effects,
                               flags=_editor_flags(aces, ("NodeWebkit",)))

    root = _read_json(schemas_dir / "_index.json")
    assert set(root["plugins"]) == {"sprite"}
    assert set(root["behaviors"]) == {"platform"}
    assert set(root["effects"]) == {"blur"}
    for locale in LOCALES:
        index = _read_json(schemas_dir / locale / "_index.json")
        assert (set(index["plugins"]), set(index["effects"])) == ({"sprite"}, {"blur"})
        assert not (schemas_dir / locale / "plugins" / "nodewebkit.json").exists()
        assert not (schemas_dir / locale / "effects" / "warp.json").exists()
    assert schema_is_complete(schemas_dir)


def test_export_lists_what_the_editor_deprecates_per_locale(fetcher):
    """{locale}/_deprecated.json holds the deprecated addons and every deprecated ACE,
    kept in the schema or not; a kept one is flagged in its file as well."""
    aces = {
        "plugins": {
            "Mouse": {"general": {"conditions": [], "expressions": [], "actions": [
                {"id": "set-cursor-style", "scriptName": "SetCursor", "isDeprecated": True},
                {"id": "set-cursor-style2", "scriptName": "SetCursor2"},
                {"id": "old-hint", "scriptName": "OldHint", "isDeprecated": True},
            ]}},
            "NodeWebkit": {"general": {"conditions": [], "actions": [], "expressions": []}},
        },
        "behaviors": {},
    }
    effects = [{"json": {"id": "warp", "category": "distortion", "is-deprecated": True, "parameters": []}},
               {"json": {"id": "blur", "category": "blur", "parameters": []}}]
    actions = {"set-cursor-style": "Set cursor style", "set-cursor-style2": "Set cursor style", "old-hint": "Old hint"}

    def pack(zh: bool) -> dict:
        own = {k: v for k, v in actions.items() if not (zh and k == "set-cursor-style")}   # dropped from zh-CN
        return {"text": {
            "plugins": {"mouse": {"name": "鼠标" if zh else "Mouse",
                                  "actions": {k: {"list-name": ("中 " if zh else "") + v} for k, v in own.items()}},
                        "nodewebkit": {"name": "NW.js", "description": "Desktop"}},
            "effects": {"blur": {"name": "Blur"}, "warp": {"name": "扭曲" if zh else "Warp"}},
        }}

    texts = {"en-US": pack(False), "zh-CN": pack(True)}
    schemas_dir = _export_with(fetcher, texts, aces=aces, effects=effects,
                               flags=_editor_flags(aces, ("NodeWebkit",)))

    en = _read_json(schemas_dir / "en-US" / "_deprecated.json")
    zh = _read_json(schemas_dir / "zh-CN" / "_deprecated.json")
    assert (en["version"], en["language"], zh["language"]) == (fetcher.version, "en-US", "zh-CN")
    assert en["addons"] == {
        "plugins": {"nodewebkit": {"originalId": "NodeWebkit", "name": "NW.js", "description": "Desktop"}},
        "behaviors": {},
        "effects": {"warp": {"name": "Warp", "description": ""}},
    }
    assert zh["addons"]["effects"]["warp"]["name"] == "扭曲"
    assert en["aces"]["plugins"]["mouse"]["actions"] == {
        "set-cursor-style": {"list-name": "Set cursor style", "description": "", "current": "set-cursor-style2"},
        "old-hint": {"list-name": "Old hint", "description": ""},
    }
    # zh-CN has no text for the one it dropped: the English stands in.
    assert zh["aces"]["plugins"]["mouse"]["actions"]["set-cursor-style"]["list-name"] == "Set cursor style"
    assert zh["aces"]["plugins"]["mouse"]["actions"]["old-hint"]["list-name"] == "中 Old hint"

    mouse = _read_json(schemas_dir / "en-US" / "plugins" / "mouse.json")
    assert {a["id"]: a.get("isDeprecated", False) for a in mouse["actions"]} == {
        "set-cursor-style2": False, "old-hint": True,
    }


def test_export_stops_when_the_editor_bundle_does_not_construct_an_addon(fetcher):
    """An addon of allAces.json the bundle does not build may be deprecated
    or not; the export stops instead of guessing."""
    aces = {"plugins": {"Sprite": {}}, "behaviors": {}}
    with pytest.raises(ValueError, match="constructs no plugin Sprite"):
        _export_with(fetcher, dict.fromkeys(LOCALES, {"text": {}}), aces=aces, flags=_editor_flags({}))
    assert not (fetcher.cache_dir / "schemas" / ".exported").exists()


def test_export_stops_when_language_pack_names_an_unknown_common_ace(fetcher):
    """A shared ACE the committed extract lacks must not be exported with guessed types."""
    texts = _common_texts(
        {"destroy": {"list-name": "Destroy"}, "levitate": {"list-name": "Levitate"}},
        {"destroy": {"list-name": "销毁"}, "levitate": {"list-name": "悬浮"}},
    )
    with pytest.raises(ValueError, match="actions/levitate"):
        _export_with(fetcher, texts)
    assert not (fetcher.cache_dir / "schemas" / ".exported").exists()


_SPRITE_ACES = {
    "plugins": {"Sprite": {"general": {"conditions": [{"id": "is-visible", "scriptName": "isVisible"}]}}},
    "behaviors": {"Platform": {"general": {"actions": [{"id": "jump", "scriptName": "simulateJump"}]}}},
}
_SPRITE_EFFECTS = [{"id": "blur", "category": "blur", "parameters": []}]
_SPRITE_TEXTS = {
    locale: {"text": {
        "plugins": {"sprite": {"name": name, "conditions": {"is-visible": {"list-name": name}}}},
        "behaviors": {"platform": {"name": name, "actions": {"jump": {"list-name": name}}}},
        "effects": {"blur": {"name": name}},
    }}
    for locale, name in (("en-US", "Sprite"), ("zh-CN", "精灵"))
}


def _full_cache(fetcher: C3Fetcher) -> dict[str, Path]:
    """A cache holding every export of one release, with the CDN files that
    say what each must hold: example "demo", and a/one.d.ts in offline.json."""
    schemas_dir = _export_with(fetcher, _SPRITE_TEXTS, aces=_SPRITE_ACES, effects=_SPRITE_EFFECTS)
    for locale in LOCALES:
        (fetcher.cache_dir / "examples" / locale / "demo.json").write_text("{}", encoding="utf-8")
    (fetcher.cache_dir / "media_example-project-data.json").write_text(
        json.dumps({"projects": [{"id": "demo"}]}), encoding="utf-8")
    (fetcher.cache_dir / "offline.json").write_text(
        json.dumps({"fileList": ["a/one.d.ts", "main.js"]}), encoding="utf-8")
    lang_dir = fetcher.cache_dir / "lang"
    lang_dir.mkdir()
    for locale in LOCALES:
        (lang_dir / f"{locale}.json").write_text("{}", encoding="utf-8")
    ts_dir = fetcher.cache_dir / "ts-defs"
    (ts_dir / "a").mkdir(parents=True)
    (ts_dir / "a" / "one.d.ts").write_text("interface One {}", encoding="utf-8")
    (ts_dir / "autocomplete-data.json").write_text("{}", encoding="utf-8")
    (ts_dir / ".exported").write_text(fetcher.version, encoding="utf-8")
    return {"schemas": schemas_dir, "lang": lang_dir, "ts": ts_dir}


_TARGETS = ("c3-schemas", "c3-examples", "c3-lang", "c3-ts-defs")


def _committed_data(tmp_path: Path) -> Path:
    """A data/ whose four targets each hold one file of the release before."""
    data_dir = tmp_path / "data"
    for name in _TARGETS:
        (data_dir / name).mkdir(parents=True)
        (data_dir / name / "before.txt").write_text(name, encoding="utf-8")
    return data_dir


def _export_to_data(fetcher: C3Fetcher, cache: dict[str, Path], data_dir: Path) -> dict[str, Path]:
    with patch.object(fetcher, "export_schemas", return_value=cache["schemas"]),          patch.object(fetcher, "export_lang", return_value=cache["lang"]),          patch.object(fetcher, "export_ts_defs", return_value=cache["ts"]),          patch.object(fetcher, "_http_get", side_effect=AssertionError("no CDN call")):
        return fetcher.export_to_data(data_dir)


def _left_as_it_was(data_dir: Path) -> bool:
    return sorted(p.relative_to(data_dir).as_posix() for p in data_dir.rglob("*") if p.is_file()) ==         sorted(f"{name}/before.txt" for name in _TARGETS) and         sorted(p.name for p in data_dir.parent.iterdir()) == ["data", "r476"]


def test_export_to_data_replaces_committed_directories_without_cache_markers(fetcher, tmp_path):
    """data/ mirrors the four exports; stale files and dot-markers do not survive."""
    cache = _full_cache(fetcher)
    data_dir = _committed_data(tmp_path)

    targets = _export_to_data(fetcher, cache, data_dir)

    assert targets["c3-schemas"] == data_dir / "c3-schemas"
    assert (data_dir / "c3-schemas" / "en-US" / "plugins" / "sprite.json").exists()
    assert (data_dir / "c3-schemas" / "_index.json").exists()
    assert not any((data_dir / name / "before.txt").exists() for name in _TARGETS)
    assert not (data_dir / "c3-schemas" / ".exported").exists()
    assert (data_dir / "c3-examples" / "zh-CN" / "demo.json").exists()
    assert (data_dir / "c3-lang" / "en-US.json").exists()
    assert (data_dir / "c3-ts-defs" / "a" / "one.d.ts").exists()
    assert (data_dir / "c3-ts-defs" / "autocomplete-data.json").exists()
    assert not (data_dir / "c3-ts-defs" / ".exported").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "r476"]


@pytest.mark.parametrize("break_cache, named", [
    (lambda cache: shutil.rmtree(cache["schemas"].parent / "examples"), "examples"),
    (lambda cache: (cache["schemas"].parent / "examples" / "zh-CN" / "demo.json").unlink(), "zh-CN/demo.json"),
    (lambda cache: (cache["ts"] / "a" / "one.d.ts").unlink(), "a/one.d.ts"),
    (lambda cache: (cache["ts"] / "autocomplete-data.json").unlink(), "autocomplete-data.json"),
    (lambda cache: (cache["lang"] / "zh-CN.json").unlink(), "zh-CN.json"),
    (lambda cache: (cache["schemas"] / "zh-CN" / "plugins" / "sprite.json").unlink(), "c3-schemas"),
])
def test_export_to_data_leaves_data_as_it_was_when_an_export_is_short(fetcher, tmp_path, break_cache, named):
    """A missing file must not reach data/ as a deletion, nor leave two releases there."""
    cache = _full_cache(fetcher)
    break_cache(cache)
    data_dir = _committed_data(tmp_path)

    with pytest.raises(RuntimeError, match=re.escape(named)):
        _export_to_data(fetcher, cache, data_dir)
    assert _left_as_it_was(data_dir)


def test_export_to_data_puts_every_target_back_when_a_swap_fails(fetcher, tmp_path):
    cache = _full_cache(fetcher)
    data_dir = _committed_data(tmp_path)
    real_rename = Path.rename
    failed: list[Path] = []

    def rename(self, target):
        if Path(target) == data_dir / "c3-lang" and not failed:
            failed.append(self)
            raise PermissionError("held open by another process")
        return real_rename(self, target)

    with patch.object(Path, "rename", rename), pytest.raises(RuntimeError, match="held open"):
        _export_to_data(fetcher, cache, data_dir)
    assert _left_as_it_was(data_dir)


def test_a_failed_swap_removes_a_target_that_was_not_there(fetcher, tmp_path):
    cache = _full_cache(fetcher)
    data_dir = _committed_data(tmp_path)
    shutil.rmtree(data_dir / "c3-examples")
    real_rename = Path.rename

    def rename(self, target):
        if Path(target) == data_dir / "c3-ts-defs" and self.parent.name != "earlier":
            raise PermissionError("held open by another process")
        return real_rename(self, target)

    with patch.object(Path, "rename", rename), pytest.raises(RuntimeError, match="held open"):
        _export_to_data(fetcher, cache, data_dir)
    assert sorted(p.name for p in data_dir.iterdir()) == ["c3-lang", "c3-schemas", "c3-ts-defs"]
    assert all((data_dir / name / "before.txt").exists() for name in ("c3-lang", "c3-schemas", "c3-ts-defs"))


def test_export_schemas_stops_without_a_marker_when_the_examples_fail(fetcher):
    with patch.object(fetcher, "fetch_examples", side_effect=ValueError("[CDN] media/example-project-data.json: not JSON")),          pytest.raises(ValueError, match="example-project-data"):
        with patch.object(fetcher, "fetch_all_aces", return_value=_SPRITE_ACES),              patch.object(fetcher, "fetch_addon_deprecation", return_value=_editor_flags(_SPRITE_ACES)),              patch.object(fetcher, "fetch_lang", side_effect=lambda locale="en-US": _SPRITE_TEXTS[locale]),              patch.object(fetcher, "fetch_effects", return_value=_SPRITE_EFFECTS):
            fetcher.export_schemas()
    assert not (fetcher.cache_dir / "schemas" / ".exported").exists()


def test_export_ts_defs_stops_when_offline_json_lists_no_definitions(fetcher):
    listing = json.dumps({"fileList": ["main.js"]}).encode()
    with patch.object(fetcher, "_http_get", return_value=listing),          pytest.raises(RuntimeError, match="offline.json lists no .d.ts"):
        fetcher.export_ts_defs()
    assert not (fetcher.cache_dir / "ts-defs" / ".exported").exists()


def _ts_cdn(fetcher: C3Fetcher, failing: frozenset[str] = frozenset()):
    """A CDN with two .d.ts files; a path in ``failing`` raises as a dropped connection does."""
    files = {
        "offline.json": json.dumps({"fileList": ["a/one.d.ts", "b/two.d.ts", "main.js"]}).encode(),
        "a/one.d.ts": b"interface One {}",
        "b/two.d.ts": b"interface Two {}",
        "media/autocomplete-data.json": b"{}",
    }

    def get(url: str) -> bytes:
        path = url.removeprefix(fetcher.url(""))
        if path in failing:
            raise urllib.error.URLError("connection reset")
        return files[path]

    return get


def test_export_ts_defs_stops_without_a_marker_when_a_file_fails(fetcher):
    """A file that fails must not drop out of data/: the export stops, and the next run fetches it."""
    with patch.object(fetcher, "_http_get", side_effect=_ts_cdn(fetcher, frozenset({"b/two.d.ts"}))):
        with pytest.raises(RuntimeError, match="b/two.d.ts"):
            fetcher.export_ts_defs()
    ts_dir = fetcher.cache_dir / "ts-defs"
    assert not (ts_dir / ".exported").exists()
    assert (ts_dir / "a" / "one.d.ts").exists()

    with patch.object(fetcher, "_http_get", side_effect=_ts_cdn(fetcher)) as cdn:
        assert fetcher.export_ts_defs() == ts_dir
    assert (ts_dir / "b" / "two.d.ts").read_bytes() == b"interface Two {}"
    assert (ts_dir / ".exported").exists()
    assert not any(c.args[0].endswith("a/one.d.ts") for c in cdn.call_args_list)


def test_export_ts_defs_stops_when_the_autocomplete_listing_fails(fetcher):
    cdn = _ts_cdn(fetcher, frozenset({"media/autocomplete-data.json"}))
    with patch.object(fetcher, "_http_get", side_effect=cdn):
        with pytest.raises(RuntimeError, match="autocomplete"):
            fetcher.export_ts_defs()
    assert not (fetcher.cache_dir / "ts-defs" / ".exported").exists()


def test_an_interrupted_write_leaves_no_file_that_looks_complete(fetcher):
    """The export skips a .d.ts that exists, so a half-written one would stay for good."""
    real_write = Path.write_bytes

    def dies_writing_in(folder: Path):
        def write(self, data):
            if self.parent != folder:
                return real_write(self, data)
            real_write(self, data[: len(data) // 2])
            raise KeyboardInterrupt
        return write

    cache_one = fetcher.cache_dir / "a_one.d.ts"
    ts_one = fetcher.cache_dir / "ts-defs" / "a" / "one.d.ts"
    with patch.object(fetcher, "_http_get", side_effect=_ts_cdn(fetcher)):
        with patch.object(Path, "write_bytes", dies_writing_in(cache_one.parent)), pytest.raises(KeyboardInterrupt):
            fetcher.fetch_raw("a/one.d.ts")
        assert not cache_one.exists()

        with patch.object(Path, "write_bytes", dies_writing_in(ts_one.parent)), pytest.raises(KeyboardInterrupt):
            fetcher.export_ts_defs()
        assert not ts_one.exists()


@pytest.mark.parametrize("path, body", [
    ("plugins/pluginList.json", b"<html>Service Unavailable</html>"),
    ("plugins/allAces.json", b"[]"),
    ("loader/lang/precompiled-en-US.json", b'{"languageTag": "en-US"}'),
    ("offline.json", b'{"version": 49502}'),
    ("a/one.d.ts", b"\xef\xbb\xbf  <!DOCTYPE html><html>Bad Gateway</html>"),
    ("main.js", b"<html>Service Unavailable</html>"),
])
def test_a_body_of_the_wrong_shape_is_refused_and_not_cached(fetcher, path, body):
    """An error page served with 200 must not stay in the cache until next week."""
    good = b"interface One {}" if path.endswith(".d.ts") else b"// main" if path.endswith(".js") else \
        json.dumps({"text": {}, "fileList": [], "pluginList": {}}).encode()
    with patch.object(fetcher, "_http_get", side_effect=[body, good]) as cdn:
        with pytest.raises(ValueError, match=re.escape(path)):
            fetcher.fetch_raw(path)
        assert not (fetcher.cache_dir / path.replace("/", "_")).exists()
        assert fetcher.fetch_raw(path) == good
    assert cdn.call_count == 2


def _status(code: int):
    return urllib.error.HTTPError("https://cdn", code, "status", None, None)


@pytest.mark.parametrize("transient", [_status(503), urllib.error.URLError("connection reset"), TimeoutError("timed out")])
def test_a_transient_failure_is_retried(transient, caplog):
    body = b'{"fileList": []}'
    with patch("src.ingest.c3_fetcher._RETRY_DELAY", 0), \
         patch("urllib.request.urlopen", side_effect=[transient, _response(body)]) as urlopen:
        assert _http_get("https://cdn/offline.json") == body
    assert urlopen.call_count == 2
    assert "retrying" in caplog.text


def test_retries_stop_after_two():
    with patch("src.ingest.c3_fetcher._RETRY_DELAY", 0), \
         patch("urllib.request.urlopen", side_effect=[_status(502)] * 3 + [_response(b"{}")]) as urlopen:
        with pytest.raises(urllib.error.HTTPError):
            _http_get("https://cdn/offline.json")
    assert urlopen.call_count == 3


@pytest.mark.parametrize("code", [403, 404])
def test_a_client_error_is_not_retried(code):
    with patch("src.ingest.c3_fetcher._RETRY_DELAY", 0), \
         patch("urllib.request.urlopen", side_effect=[_status(code), _response(b"{}")]) as urlopen:
        with pytest.raises(urllib.error.HTTPError):
            _http_get("https://cdn/offline.json")
    assert urlopen.call_count == 1


def _response(body: bytes) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value.read.return_value = body
    return response


def test_export_to_data_creates_a_data_folder_that_is_not_there(fetcher, tmp_path):
    cache = _full_cache(fetcher)
    data_dir = tmp_path / "fresh" / "data"
    _export_to_data(fetcher, cache, data_dir)
    assert sorted(p.name for p in data_dir.iterdir()) == sorted(_TARGETS)
    assert sorted(p.name for p in data_dir.parent.iterdir()) == ["data"]
