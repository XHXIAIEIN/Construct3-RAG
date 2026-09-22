"""Shared world-object ACE definitions: the committed extract, the bundle parser
and the exported ``_common.json``."""
import json
from pathlib import Path

import pytest

from src.ingest.common_aces import (
    ACE_TYPES,
    COMMON_ACES_PATH,
    COMMON_PROPERTIES,
    build_common_properties,
    check_common_coverage,
    extract_common_aces,
    load_common_aces,
)

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ("en-US", "zh-CN")


def _lang_common(locale: str) -> dict:
    pack = json.loads((ROOT / "data" / "c3-lang" / f"{locale}.json").read_text(encoding="utf-8"))
    return pack["text"]["plugins"]["_common"]


def _structural_index(categories: dict) -> dict[tuple[str, str], dict]:
    return {
        (ace_type, ace["id"]): ace
        for aces in categories.values()
        for ace_type in ACE_TYPES
        for ace in aces.get(ace_type, [])
    }


# ── committed extract vs committed language packs ────────────────────────


@pytest.mark.parametrize("locale", LOCALES)
def test_committed_extract_covers_the_language_pack(locale):
    categories = load_common_aces()
    lang = _lang_common(locale)
    check_common_coverage(categories, lang)

    structural = _structural_index(categories)
    in_lang = {(t, ace_id) for t in ACE_TYPES for ace_id in lang.get(t, {})}
    assert set(structural) == in_lang, "extract and language pack list different shared ACEs"
    assert set(categories) <= set(lang["aceCategories"])

    for (ace_type, ace_id), ace in structural.items():
        l_params = lang[ace_type][ace_id].get("params", {})
        # Same parameters; the order is the editor's (display-text {n} indexes
        # it), the language pack's dict order is not.
        assert {p["id"] for p in ace.get("params", [])} == set(l_params), (ace_type, ace_id)
        for param in ace.get("params", []):
            assert isinstance(param["type"], str) and param["type"], (ace_id, param["id"])
            if param["type"] == "combo":
                assert list(l_params[param["id"]]["items"]) == param["items"], (ace_id, param["id"])
            else:
                assert "items" not in l_params[param["id"]], (ace_id, param["id"])


def test_committed_extract_states_its_source():
    data = json.loads(COMMON_ACES_PATH.read_text(encoding="utf-8"))
    assert data["_source"]["file"] == "main.js"
    assert data["_source"]["script"] == "scripts/extract_common_aces.py"
    assert data["_source"]["release"].startswith("r")


def test_coverage_check_names_every_gap():
    categories = {"misc": {"conditions": [], "actions": [
        {"id": "destroy", "scriptName": "Destroy"},
        {"id": "set-x", "scriptName": "SetX", "params": [{"id": "x", "type": "number"}]},
    ], "expressions": []}}
    lang = {
        "conditions": {"is-visible": {}},
        "actions": {"destroy": {}, "set-x": {"params": {"x": {}, "y": {}}}},
        "expressions": {},
    }
    with pytest.raises(ValueError) as excinfo:
        check_common_coverage(categories, lang)
    assert "conditions/is-visible" in str(excinfo.value)
    assert "actions/set-x/params/y" in str(excinfo.value)
    assert "actions/destroy" not in str(excinfo.value)


# ── bundle parser ────────────────────────────────────────────────────────

BUNDLE = (
    'x.f=function(a){a.g("plugins.sprite")};'
    'uR.Xcs=function(t,i){uR.u.o("plugins._common");const e=self.app,n=e.lt("z-order");'
    't.$("angle"),t.Qcs({id:"is-within-angle",c2id:-11,scriptName:"AngleWithin",'
    'params:[{id:"within",type:"number",initialValue:.5},{id:"angle",type:"number"}]}),'
    't.tds({id:"angle",c2id:-1,expressionName:"Angle",returnType:"number"}),'
    'i.mcs()&&(t.$("appearance"),t.Qcs({id:"is-visible",c2id:-9,scriptName:"IsVisible"}),'
    't.Jcs({id:"set-visible",scriptName:"SetVisible",params:[{id:"visibility",type:"combo",'
    'items:["invisible","visible"],initialValue:"visible"}]})),'
    't.$("misc"),t.Qcs({id:"on-created",scriptName:"OnCreated",isTrigger:!0,isInvertible:!1}),'
    't.$("z-order"),t.Jcs({id:"move-to-layer",scriptName:"MoveToLayer",params:[{id:"layer",type:"layer"}]}),'
    'i.gcs()&&(t.$("html-element"),t.Qcs({id:"is-visible",scriptName:"IsVisible"}),'
    't.Jcs({id:"set-css-style",scriptName:"SetCSSStyle",params:[{id:"property-name",type:"string",'
    "initialValue:'\"border\"'}]}))};"
    'y.h=function(b){b.Qcs({id:"is-visible",scriptName:"Elsewhere"})};'
)

LANG = {
    "aceCategories": {"angle": "Angle", "appearance": "Appearance", "misc": "Misc",
                      "z-order": "Z Order", "html-element": "HTML element"},
    "conditions": {"is-within-angle": {}, "is-visible": {}, "on-created": {}},
    "actions": {"set-visible": {}, "move-to-layer": {}, "set-css-style": {}},
    "expressions": {"angle": {}},
}


def test_extract_reads_the_block_after_the_anchor_only():
    categories = extract_common_aces(BUNDLE, LANG)
    assert list(categories) == ["angle", "appearance", "misc", "z-order", "html-element"]
    assert categories["angle"]["conditions"] == [{
        "id": "is-within-angle", "c2id": -11, "scriptName": "AngleWithin",
        "params": [{"id": "within", "type": "number", "initialValue": 0.5},
                   {"id": "angle", "type": "number"}],
    }]
    assert categories["angle"]["expressions"] == [
        {"id": "angle", "c2id": -1, "expressionName": "Angle", "returnType": "number"},
    ]
    assert categories["misc"]["conditions"] == [
        {"id": "on-created", "scriptName": "OnCreated", "isTrigger": True, "isInvertible": False},
    ]
    # z-order is also a variable name in the prologue; only the category call counts.
    assert categories["z-order"]["actions"][0]["id"] == "move-to-layer"
    # The DOM re-registration of is-visible is a duplicate, the world one wins.
    assert [c["id"] for c in categories["appearance"]["conditions"]] == ["is-visible"]
    assert categories["appearance"]["conditions"][0]["c2id"] == -9
    assert categories["html-element"]["conditions"] == []
    assert categories["html-element"]["actions"][0]["params"][0]["initialValue"] == '"border"'


def test_extract_reports_shared_aces_missing_from_the_bundle():
    lang = {**LANG, "actions": {**LANG["actions"], "levitate": {}}}
    with pytest.raises(ValueError, match="actions/levitate"):
        extract_common_aces(BUNDLE, lang)


def test_extract_rejects_conflicting_duplicate_registrations():
    bundle = BUNDLE.replace(
        't.Qcs({id:"is-visible",scriptName:"IsVisible"}),',
        't.Qcs({id:"is-visible",scriptName:"IsVisible",params:[{id:"mode",type:"combo",items:["a"]}]}),',
    )
    with pytest.raises(ValueError, match="registered twice"):
        extract_common_aces(bundle, LANG)


def test_extract_requires_exactly_one_anchor():
    with pytest.raises(ValueError, match="anchor"):
        extract_common_aces(BUNDLE + BUNDLE, LANG)


# ── exported data ────────────────────────────────────────────────────────


def test_exported_common_schema_is_typed_and_structurally_identical_across_locales():
    files = {
        locale: json.loads(
            (ROOT / "data" / "c3-schemas" / locale / "plugins" / "_common.json").read_text(encoding="utf-8")
        )
        for locale in LOCALES
    }
    en = files["en-US"]
    structural = _structural_index(load_common_aces())
    for ace_type in ACE_TYPES:
        for entry in en[ace_type]:
            source = structural[(ace_type, entry["id"])]
            assert entry["scriptName"] == source.get("scriptName", source.get("expressionName"))
            assert entry["category"] in en["aceCategories"]
            for param_id, param in entry.get("params", {}).items():
                assert param["type"] == next(p["type"] for p in source["params"] if p["id"] == param_id)
                assert (param["type"] == "combo") == ("items" in param), (entry["id"], param_id)

    def shape(schema: dict) -> list:
        return [
            (t, a["id"], a["scriptName"], a["category"], a.get("isTrigger"), a.get("returnType"),
             tuple((k, v["type"], tuple(v.get("items", {})), v.get("initialValue"))
                   for k, v in a.get("params", {}).items()))
            for t in ACE_TYPES for a in schema[t]
        ]

    assert shape(files["en-US"]) == shape(files["zh-CN"])


# ── shared world-instance properties ─────────────────────────────────────


@pytest.mark.parametrize("locale", LOCALES)
def test_shared_properties_are_named_in_every_locale(locale):
    """Their text is under ui.bars.properties.instance; the plugins._common
    entry of the language pack has ACE text only, which is why the export
    left the properties empty."""
    pack = json.loads((ROOT / "data" / "c3-lang" / f"{locale}.json").read_text(encoding="utf-8"))
    assert "properties" not in pack["text"]["plugins"]["_common"]
    built = build_common_properties(pack["text"])
    assert [p for p, _, _ in COMMON_PROPERTIES] == list(built)
    for prop_id, entry in built.items():
        assert entry["name"] and entry["written"], prop_id


def test_build_stops_when_the_pack_has_no_text_for_a_property():
    with pytest.raises(ValueError, match="ui.bars.properties.instance.color"):
        build_common_properties({"ui": {"bars": {"properties": {"instance": {}}}}})


def test_exported_common_schema_carries_the_instance_properties():
    """An id is the key a project file holds, as it is for a plugin's own
    properties, and `written` says where, the properties bar and the file
    disagreeing on the angle and the opacity
    (docs/decisions/common-instance-properties.md)."""
    files = {
        locale: json.loads(
            (ROOT / "data" / "c3-schemas" / locale / "plugins" / "_common.json").read_text(encoding="utf-8")
        )["properties"]
        for locale in LOCALES
    }
    for locale, props in files.items():
        assert list(props) == [p for p, _, _ in COMMON_PROPERTIES], locale
        assert props["color"]["written"].startswith("world.color, [r, g, b, a]")
        assert "radians" in props["angle"]["written"]
        assert props["opacity"]["written"].startswith("world.color[3]")
    # written and the ids are structural: identical in every locale, the text is not.
    assert {k: v["written"] for k, v in files["en-US"].items()} == \
           {k: v["written"] for k, v in files["zh-CN"].items()}
    assert files["en-US"]["color"]["desc"] != files["zh-CN"]["color"]["desc"]
