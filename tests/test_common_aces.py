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
    common_aces_of,
    extract_common_aces,
    extract_common_requirements,
    extract_plugin_flags,
    load_common_aces,
    load_common_availability,
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


# ── which shared ACEs a plugin gets ──────────────────────────────────────

# The shape of r495.2: the info class holds the flags (a setter writes the field
# a getter reads), window.SDK.IPluginInfo names the setters, the _common block
# guards each group on a getter, and a built-in plugin calls the setters in its
# constructor.
INFO = (
    'class extends Q.l{#c=!1;constructor(t){super(),this.ty="object",this.sg=!1,this.ap=!1,this.col=!1,this.ang=!1}'
    'k(t){this.n=t}Jt(t){Q.bp(t),this.ty=t}MF(){return this.ty}it(t){this.sg=!!t}UF(){return this.sg}'
    'oi(){this.ap=!0}mcs(){return this.ap}ti(t){this.col=!!t}Eoe(){return this.col}li(){this.ang=!0}'
    'fcs(){return this.ang}ir(){this.#c=!0}Mcs(){return this.#c}'
    'Kcs(){if("object"===this.ty&&this.ap)throw new Error("plugin type \'object\' cannot use common ACEs")}}'
    '{const Ak=new WeakMap;window.SDK.IPluginInfo=class{constructor(t){Ak.set(this,t)}'
    'SetPluginType(t){Ak.get(this).Jt(t)}SetIsSingleGlobal(t){Ak.get(this).it(t)}'
    'AddCommonAppearanceACEs(){Ak.get(this).oi()}SetSupportsColor(t){Ak.get(this).ti(t)}'
    'AddCommonAngleACEs(){Ak.get(this).li()}}}'
)
GUARDED = (
    'uR.Xcs=function(t,i){uR.u.o("plugins._common");'
    'i.fcs()&&(t.$("angle"),t.tds({id:"angle",c2id:-1,expressionName:"Angle",returnType:"number"})),'
    'i.mcs()&&(t.$("appearance"),t.Qcs({id:"is-visible",c2id:-9,scriptName:"IsVisible"}),'
    'i.Eoe()&&(t.Jcs({id:"set-default-color",scriptName:"SetDefaultColor",params:[{id:"color",type:"number"}]})),'
    't.Jcs({id:"set-visible",scriptName:"SetVisible"})),'
    'i.UF()||(t.$("misc"),t.Jcs({id:"destroy",c2id:-9,scriptName:"Destroy"}),'
    '"object"!==i.MF()&&t.tds({id:"asjson",c2id:-19,expressionName:"AsJSON",returnType:"string"})),'
    'i.Mcs()&&(t.$("collisions"),t.Qcs({id:"is-overlapping-another-object",c2id:1,scriptName:"IsOverlapping",'
    'params:[{id:"object",type:"object"}]})),'
    'i.mcs()||(t.$("appearance"),t.Qcs({id:"is-visible",scriptName:"IsVisible"}))};'
)
GUARDED_LANG = {
    "aceCategories": {"angle": "Angle", "appearance": "Appearance", "misc": "Misc", "collisions": "Collisions"},
    "conditions": {"is-visible": {}, "is-overlapping-another-object": {}},
    "actions": {"set-default-color": {}, "set-visible": {}, "destroy": {}},
    "expressions": {"angle": {}, "asjson": {}},
}
PLUGINS = (
    '{const a=self.t,b="Sprite",c=a.h.Sprite=class extends a.l{constructor(){super(),a.u.o("plugins."+b.toLowerCase());'
    'const t=this.p=a.m(self.v,b);t.k("Sprite"),t.Jt("world"),t.li(),t.oi(),t.ti(!0),t.ir(),'
    't.gi([new a.P("combo","x",{wi:function(t){t.ti(!1)}})])}}}'
    '{const a=self.t,d="Text",c=a.h.Text=class extends a.l{constructor(){super(),a.u.o("plugins.text");'
    'const t=this.p=a.m(self.v,d);t.Jt("world"),t.li(),t.oi()}}}'
    '{const a=self.t,e="Keyboard",c=a.h.Keyboard=class extends a.l{constructor(){super(),a.u.o("plugins.keyboard"),'
    'this.p=a.m(self.v,e),this.p.it(!0)}}}'
    '{const a=self.t,f="Arr",c=a.h.Arr=class extends a.l{constructor(){super(),a.u.o("plugins.arr");'
    'const t=this.p=a.m(self.v,f);t.k("Array")}}}'
)


def test_requirements_follow_the_guards_of_the_block():
    requires = extract_common_requirements(INFO + GUARDED, GUARDED_LANG)
    assert requires["expressions"]["angle"] == [["AddCommonAngleACEs"]]
    assert requires["actions"]["set-default-color"] == [["AddCommonAppearanceACEs", "SetSupportsColor"]]
    # A guard without a public setter is named after the first ACE it registers.
    assert requires["conditions"]["is-overlapping-another-object"] == [["editor:is-overlapping-another-object"]]
    assert requires["actions"]["destroy"] == [["!SetIsSingleGlobal"]]
    assert requires["expressions"]["asjson"] == [["!SetIsSingleGlobal", "SetPluginType!=object"]]
    # Registered twice: either list gives it.
    assert requires["conditions"]["is-visible"] == [["AddCommonAppearanceACEs"], ["!AddCommonAppearanceACEs"]]


def test_plugin_flags_are_what_the_constructor_sets_at_its_own_level():
    flags = extract_plugin_flags(INFO + GUARDED, PLUGINS, GUARDED_LANG)
    assert list(flags) == ["Arr", "Keyboard", "Sprite", "Text"]
    # t.ti(!1) inside a property's callback is not the plugin's.
    assert flags["Sprite"]["SetSupportsColor"] is True
    assert flags["Sprite"]["editor:is-overlapping-another-object"] is True
    assert flags["Text"]["SetSupportsColor"] is False and flags["Text"]["AddCommonAppearanceACEs"] is True
    assert flags["Keyboard"]["SetIsSingleGlobal"] is True
    assert flags["Arr"]["SetPluginType"] == "object"


def test_a_plugin_gets_the_shared_aces_whose_requirements_hold():
    requires = extract_common_requirements(INFO + GUARDED, GUARDED_LANG)
    flags = extract_plugin_flags(INFO + GUARDED, PLUGINS, GUARDED_LANG)
    text = common_aces_of(flags["Text"], requires)
    assert "set-default-color" not in text["actions"] and "set-visible" in text["actions"]
    assert "set-default-color" in common_aces_of(flags["Sprite"], requires)["actions"]
    assert common_aces_of(flags["Keyboard"], requires) == {
        "conditions": ["is-visible"], "actions": [], "expressions": []}
    arr = common_aces_of(flags["Arr"], requires)
    assert "destroy" in arr["actions"] and "asjson" not in arr["expressions"]


def test_committed_extract_gives_text_no_set_color():
    """Observed: the r495.2 editor refused a project with Set color on a Text
    ("missing action id 'set-default-color'"); Text's colour is Set font color."""
    available = load_common_availability()
    assert "set-default-color" not in available["Text"]["actions"]
    assert "color-value" not in available["Text"]["expressions"]
    assert "set-default-color" in available["Sprite"]["actions"]
    assert available["Keyboard"] == {"conditions": [], "actions": [], "expressions": []}
    assert "set-x" not in available["Arr"]["actions"] and "destroy" in available["Arr"]["actions"]


def test_committed_extract_requirements_cover_every_shared_ace():
    data = json.loads(COMMON_ACES_PATH.read_text(encoding="utf-8"))
    structural = _structural_index(data["categories"])
    assert {(t, ace_id) for t in ACE_TYPES for ace_id in data["requires"][t]} == set(structural)
    assert data["_source"]["plugins"].startswith("plugins/allEditorPlugins.js")


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

def test_exported_plugins_list_the_shared_aces_they_get():
    """commonAces is structural: the same in every locale, what the committed
    extract gives the plugin, and every id in it is one of plugins/_common.json."""
    available = load_common_availability()
    schemas = ROOT / "data" / "c3-schemas"
    common = json.loads((schemas / "en-US" / "plugins" / "_common.json").read_text(encoding="utf-8"))
    ids = {t: {a["id"] for a in common[t]} for t in ACE_TYPES}
    index = json.loads((schemas / "_index.json").read_text(encoding="utf-8"))["plugins"]
    for plugin_id, entry in index.items():
        if plugin_id == "_common":
            continue
        en, zh = (json.loads((schemas / locale / entry["file"]).read_text(encoding="utf-8")) for locale in LOCALES)
        assert en["commonAces"] == zh["commonAces"], plugin_id
        assert en["commonAces"] == available[entry["originalId"]], plugin_id
        for t in ACE_TYPES:
            assert set(en["commonAces"][t]) <= ids[t], (plugin_id, t)
