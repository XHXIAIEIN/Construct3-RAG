"""Structural definitions of the ACEs every world object shares (``_common``).

``allAces.json`` covers plugins and behaviors only. The shared conditions,
actions and expressions (``compare-instance-variable``, ``pick-children``,
``set-visible``, ``X`` ...) are registered inside the editor bundle
``main.js``, which the CDN serves only at its root, not under a release
directory. Parsing a minified bundle on every export would tie the schema to
whatever release the root happens to serve, so the block is extracted once by
``scripts/extract_common_aces.py`` into ``common_aces.json`` next to this
module, in the same shape as one ``allAces.json`` plugin entry:

    {category: {"conditions": [...], "actions": [...], "expressions": [...]}}

The exporter reads that file offline. The language pack remains the list of
shared ACEs that exist in the current release; when it names one the file
does not know, the export stops instead of guessing parameter types.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

COMMON_ADDON_ID = "_common"
# Display name when a language pack has none (en-US says "(unused)", zh-CN nothing).
COMMON_ADDON_NAME = "Common"
COMMON_ACES_PATH = Path(__file__).with_name("common_aces.json")

# The editor bundle registers the shared ACEs in the function that follows
# this string. It is the language-pack path of the block, so it is expected
# to outlive the minified method names around it.
BUNDLE_ANCHOR = '"plugins._common"'

ACE_TYPES = ("conditions", "actions", "expressions")


def load_common_aces(path: Path = COMMON_ACES_PATH) -> dict[str, dict[str, list[dict]]]:
    """Return the category map of the committed shared-ACE definitions."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["categories"]


def load_common_availability(path: Path = COMMON_ACES_PATH) -> dict[str, dict[str, list[str]]]:
    """``{plugin id: {ace_type: [shared ACE ids]}}`` for the built-in plugins,
    from the requirements and plugin flags of the committed extract."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {plugin: common_aces_of(flags, data["requires"]) for plugin, flags in data["plugins"].items()}


def check_common_coverage(categories: dict[str, dict[str, list[dict]]], lang_common: dict) -> None:
    """Raise ``ValueError`` when the language pack has shared ACEs or params
    the structural file does not define.

    ``lang_common`` is ``text.plugins._common`` of one language pack. Only
    ACEs of that pack are checked, so the check is as strict as the release
    the export runs against.
    """
    structural: dict[tuple[str, str], dict] = {}
    for aces in categories.values():
        for ace_type in ACE_TYPES:
            for ace in aces.get(ace_type, []):
                structural[(ace_type, ace["id"])] = ace

    missing: list[str] = []
    for ace_type in ACE_TYPES:
        for ace_id, l_ace in lang_common.get(ace_type, {}).items():
            ace = structural.get((ace_type, ace_id))
            if ace is None:
                missing.append(f"{ace_type}/{ace_id}")
                continue
            known = {p["id"] for p in ace.get("params", [])}
            for param_id in l_ace.get("params", {}):
                if param_id not in known:
                    missing.append(f"{ace_type}/{ace_id}/params/{param_id}")
    if missing:
        raise ValueError(
            "language pack names shared ACEs that common_aces.json does not define: "
            + ", ".join(missing)
            + ". Run scripts/extract_common_aces.py against the current release."
        )


# ── Shared world-instance properties ─────────────────────────────────────

# The properties every world instance has. Their text is in the language
# pack, but under ``ui.bars.properties.instance``: the ``plugins._common``
# entry a plugin's properties would come from carries ACE text only, so the
# export used to leave ``_common`` with an empty properties dict.
#
# ``lang`` is the path to the text, ``written`` the key of the instance in a
# project file and the unit when the properties bar shows another one. Where
# the two disagree the file wins, and a reader that has only the bar's text
# writes degrees into a field of radians. The keys and their values were
# measured over the 33 225 world instances of the official examples
# (docs/decisions/common-instance-properties.md); the names match
# ``IWorldInstance`` of ``data/c3-ts-defs/``.
#
# Rows of the bar that are not stored on the instance are left out: Layer and
# Z index are its place in the layout, Instance variables, Behaviors and
# Effects have blocks of their own. The origin is in the world block but has
# no row, being set per animation frame; docs/guide/data-format.md has it.
COMMON_PROPERTIES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("x", ("position", "x"), "world.x"),
    ("y", ("position", "y"), "world.y"),
    ("z", ("position", "z"), "world.z, or world.zElevation in a project saved before r470"),
    ("width", ("size", "width"), "world.width"),
    ("height", ("size", "height"), "world.height"),
    ("depth", ("size", "depth"), "world.depth, 3D only"),
    ("angle", ("angle",), "world.angle, in radians; the properties bar shows degrees"),
    ("color", ("color",), "world.color, [r, g, b, a] from 0 to 1, white [1, 1, 1, 1] for none"),
    ("opacity", ("opacity",), "world.color[3], from 0 to 1; there is no opacity key"),
    ("blendMode", ("blend-mode",), 'world.blendMode, a name such as "additive"; absent is normal'),
    ("uid", ("uid",), "uid, beside world"),
    ("tags", ("tags",), "tags, beside world"),
)


def build_common_properties(lang_text: dict) -> dict[str, dict[str, str]]:
    """Return ``{id: {name, desc, written}}`` for the shared world-instance
    properties, in the language of ``lang_text`` (one pack's ``text``).

    Raises ``ValueError`` when the pack has no text at a path the table
    names, so that a row renamed or dropped upstream stops the export
    instead of exporting a property without its name.
    """
    instance = lang_text.get("ui", {}).get("bars", {}).get("properties", {}).get("instance", {})
    out: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for prop_id, path, written in COMMON_PROPERTIES:
        entry: dict = instance
        for part in path:
            entry = entry.get(part, {}) if isinstance(entry, dict) else {}
        if not isinstance(entry, dict) or not entry.get("name"):
            missing.append("ui.bars.properties.instance." + ".".join(path))
            continue
        out[prop_id] = {"name": entry["name"], "desc": entry.get("desc", ""), "written": written}
    if missing:
        raise ValueError(
            "language pack has no text for shared instance properties: "
            + ", ".join(missing)
            + ". Update COMMON_PROPERTIES in src/ingest/common_aces.py against the current release."
        )
    return out


# ── Editor bundle extraction ─────────────────────────────────────────────


def _literal_at(source: str, start: int) -> str:
    """Return the object literal that starts at ``source[start] == "{"``.

    Brace matching skips string contents; the registration block contains
    no regular expressions or template literals.
    """
    depth = 0
    quote: str | None = None
    i = start
    while i < len(source):
        ch = source[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    raise ValueError(f"unterminated object literal at offset {start}")


_KEY_RE = re.compile(r"[A-Za-z_$][\w$]*(?=\s*:)")
_NUMBER_RE = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _js_literal_to_json(literal: str) -> dict:
    """Convert a minified JS object literal to JSON: quote keys, expand the
    ``!0``/``!1`` booleans, normalise ``.5`` style numbers and rewrite
    single-quoted strings such as ``'"border"'``."""
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(literal):
        ch = literal[i]
        if quote:
            if ch == "\\":
                nxt = literal[i + 1]
                out.append(nxt if nxt == "'" else "\\" + nxt)
                i += 2
                continue
            if ch == quote:
                quote = None
                out.append('"')
            elif ch == '"':
                out.append('\\"')
            else:
                out.append(ch)
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append('"')
            i += 1
            continue
        if i == 0 or literal[i - 1] in "{,":
            key = _KEY_RE.match(literal, i)
            if key:
                out.append(f'"{key.group(0)}"')
                i = key.end()
                continue
        if literal.startswith("!0", i):
            out.append("true")
            i += 2
            continue
        if literal.startswith("!1", i):
            out.append("false")
            i += 2
            continue
        number = _NUMBER_RE.match(literal, i)
        if number and (i == 0 or literal[i - 1] in ":[,"):
            text = number.group(0)
            if text.startswith("."):
                text = "0" + text
            elif text.startswith("-."):
                text = "-0" + text[1:]
            out.append(text)
            i = number.end()
            continue
        out.append(ch)
        i += 1
    return json.loads("".join(out))


def _function_body(source: str, anchor_pos: int) -> tuple[int, str]:
    """Return the offset and text of the function body enclosing ``anchor_pos``."""
    head = source.rfind("function(", 0, anchor_pos)
    if head == -1:
        raise ValueError("no function head before the _common anchor")
    body_start = source.index("{", head)
    return body_start, _literal_at(source, body_start)


def extract_common_aces(main_js: str, lang_common: dict) -> dict[str, dict[str, list[dict]]]:
    """Parse the shared-ACE block of the editor bundle.

    ``lang_common`` supplies the ACE ids and category ids of the release, so
    nothing about the minified code is assumed except the anchor string and
    the ``{id:"...", ...}`` literals. A registration is kept when its id is
    listed in the language pack under the same ACE type; ids the pack does not
    know are reported by the caller. A DOM object registers ``is-visible`` and
    ``set-visible`` a second time under ``html-element``; the first, world
    object, definition wins and the duplicate must agree on parameter ids and
    types.
    """
    anchors = [m.start() for m in re.finditer(re.escape(BUNDLE_ANCHOR), main_js)]
    if len(anchors) != 1:
        raise ValueError(f"expected one {BUNDLE_ANCHOR} anchor in main.js, found {len(anchors)}")
    body_offset, body = _function_body(main_js, anchors[0])

    categories = set(lang_common.get("aceCategories", {}))
    lang_ids = {
        ace_type: set(lang_common.get(ace_type, {})) for ace_type in ACE_TYPES
    }

    # The receiver that registers ACEs also sets the category, e.g. t.$("angle").
    first = re.search(r'([\w$]+)\.[\w$]+\(\{id:"', body)
    if first is None:
        raise ValueError("no ACE registration found in the _common block")
    receiver = re.escape(first.group(1))
    category_re = re.compile(
        rf'(?<![\w$]){receiver}\.[\w$]+\("({"|".join(map(re.escape, sorted(categories)))})"\)'
    )
    category_at = [(m.start(), m.group(1)) for m in category_re.finditer(body)]

    result: dict[str, dict[str, list[dict]]] = {}
    seen: dict[tuple[str, str], dict] = {}
    for start, ace_type, ace in _registrations(body, lang_ids):
        ace_id = ace["id"]
        key = (ace_type, ace_id)
        if key in seen:
            _assert_same_params(seen[key], ace)
            continue
        category = next(
            (name for pos, name in reversed(category_at) if pos < start), None,
        )
        if category is None:
            raise ValueError(f"no category call precedes {ace_type}/{ace_id} in the _common block")
        seen[key] = ace
        result.setdefault(category, {t: [] for t in ACE_TYPES})[ace_type].append(ace)

    missing = [
        f"{ace_type}/{ace_id}"
        for ace_type in ACE_TYPES
        for ace_id in sorted(lang_ids[ace_type])
        if (ace_type, ace_id) not in seen
    ]
    if missing:
        raise ValueError(
            "language pack names shared ACEs the editor bundle block does not register: "
            + ", ".join(missing)
        )
    return result


def _registrations(body: str, lang_ids: dict[str, set[str]]):
    """Yield ``(offset, ace_type, ace)`` for each ACE registered in ``body``
    whose id the language pack lists under that type."""
    for match in re.finditer(r'\{id:"([a-z0-9-]+)",', body):
        literal = _literal_at(body, match.start())
        if "scriptName:" not in literal and "expressionName:" not in literal:
            continue  # a parameter literal such as {id:"x",type:"number"}
        ace = _js_literal_to_json(literal)
        ace_id = ace["id"]
        if "expressionName" in ace:
            ace_type = "expressions"
        elif ace_id in lang_ids["conditions"] and ace_id not in lang_ids["actions"]:
            ace_type = "conditions"
        elif ace_id in lang_ids["actions"] and ace_id not in lang_ids["conditions"]:
            ace_type = "actions"
        else:
            raise ValueError(f"cannot tell whether {ace_id!r} is a condition or an action")
        if ace_id in lang_ids[ace_type]:
            yield match.start(), ace_type, ace


def _assert_same_params(first: dict, other: dict) -> None:
    def shape(ace: dict) -> list[tuple]:
        return [
            (p.get("id"), p.get("type"), tuple(p.get("items", [])))
            for p in ace.get("params", [])
        ]

    if shape(first) != shape(other):
        raise ValueError(
            f"{first['id']!r} is registered twice with different parameters: "
            f"{shape(first)} vs {shape(other)}"
        )


# ── Which shared ACEs a plugin gets ──────────────────────────────────────
#
# The editor registers a shared ACE on a plugin only when the plugin's info
# asks for it: set-default-color needs AddCommonAppearanceACEs and
# SetSupportsColor, Text calls only the first, and the editor then refuses a
# project that uses it on a Text with "missing action id". The block of
# plugins._common wraps each group in a guard on the info, ``i.mcs()&&(...)``.
# A guard is named through the info class, whose setter writes the field the
# getter reads, and window.SDK.IPluginInfo, whose public method calls that
# setter. A guard with no public method (collisions, mesh, the DOM elements)
# is named after the first ACE it registers, ``editor:<id>``. The built-in
# plugins call the same setters in plugins/allEditorPlugins.js.

INFO_CLASS_ANCHOR = "plugin type 'object' cannot use common ACEs"
SDK_INFO_ANCHOR = "window.SDK.IPluginInfo=class{"
PLUGIN_INFO_RE = re.compile(r"(?:const ([\w$]+)=)?this\.p=[\w$]+\.m\((?:self|globalThis)\.v,([\w$]+)\)")


def _group_end(source: str, start: int) -> int:
    """Return the offset just past the bracket that closes ``source[start]``."""
    closing = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    quote: str | None = None
    i = start
    while i < len(source):
        ch = source[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in closing:
            stack.append(closing[ch])
        elif ch in ")]}":
            if not stack or stack.pop() != ch:
                raise ValueError(f"unbalanced {ch!r} at offset {i}")
            if not stack:
                return i + 1
        i += 1
    raise ValueError(f"unterminated group at offset {start}")


def _top_level(body: str) -> list[bool]:
    """For each offset of a constructor body ``{...}``, whether it lies in the
    body's own statements rather than in a call's arguments or a closure."""
    flags = [False] * len(body)
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(body):
        ch = body[i]
        flags[i] = depth == 1 and quote is None
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        i += 1
    return flags


def _js_value(token: str) -> bool | str:
    token = token.strip()
    if token == "!0":
        return True
    if token == "!1":
        return False
    if len(token) >= 2 and token[0] in "\"'" and token[-1] == token[0]:
        return token[1:-1]
    raise ValueError(f"not a literal: {token!r}")


def _info_class(main_js: str) -> tuple[dict[str, str], dict[str, str], dict[str, bool | str]]:
    """``(setter -> field, getter -> field, field -> initial value)`` of the
    editor's plugin info class, the one that refuses shared ACEs on an
    object-type plugin."""
    anchor = main_js.find(INFO_CLASS_ANCHOR)
    if anchor == -1:
        raise ValueError(f"no {INFO_CLASS_ANCHOR!r} in main.js: the plugin info class moved")
    text = main_js[main_js.rfind("class ", 0, anchor):anchor]
    initial: dict[str, bool | str] = {}
    for m in re.finditer(r'(?:this\.|[{;])(#?[\w$]+)=(!0|!1|"[^"]*")', text):
        initial.setdefault(m.group(1), _js_value(m.group(2)))
    setters = {m.group(1): m.group(2) for m in re.finditer(
        r'(?<=\})([\w$]+)\(\w?\)\{(?:[^{}]*?,)?this\.(#?[\w$]+)=[^{}]*\}', text)}
    getters = {m.group(1): m.group(2) for m in re.finditer(
        r'(?<=\})([\w$]+)\(\)\{return this\.(#?[\w$]+)\}', text)}
    return setters, getters, initial


def _sdk_names(main_js: str) -> dict[str, str]:
    """Internal setter -> public method of window.SDK.IPluginInfo."""
    anchor = main_js.find(SDK_INFO_ANCHOR)
    if anchor == -1:
        raise ValueError(f"no {SDK_INFO_ANCHOR!r} in main.js")
    start = anchor + len(SDK_INFO_ANCHOR) - 1
    text = main_js[start:_group_end(main_js, start)]
    return {m.group(2): m.group(1) for m in re.finditer(
        r'([A-Z]\w*)\([\w,]*\)\{[\w$]+\.get\(this\)\.([\w$]+)\(', text)}


def _common_guards(main_js: str, lang_common: dict) -> tuple[list[tuple[int, str, dict]], list[tuple[int, int, str, str]]]:
    """The registrations of the _common block and its guards, each guard as
    ``(start, end, requirement, field of the info class)``."""
    anchors = [m.start() for m in re.finditer(re.escape(BUNDLE_ANCHOR), main_js)]
    if len(anchors) != 1:
        raise ValueError(f"expected one {BUNDLE_ANCHOR} anchor in main.js, found {len(anchors)}")
    params = re.match(r"function\(([\w$]+),([\w$]+)\)", main_js[main_js.rfind("function(", 0, anchors[0]):])
    if params is None:
        raise ValueError("the _common block does not take (registrar, plugin info)")
    _, body = _function_body(main_js, anchors[0])
    lang_ids = {ace_type: set(lang_common.get(ace_type, {})) for ace_type in ACE_TYPES}
    registrations = list(_registrations(body, lang_ids))

    setters, getters, _ = _info_class(main_js)
    sdk = _sdk_names(main_js)
    public = {field: sdk[setter] for setter, field in setters.items() if setter in sdk}
    guards = []
    info = re.escape(params.group(2))
    for m in re.finditer(rf'(?:"([\w-]+)"(!==|===))?(?<![\w$.]){info}\.([\w$]+)\(\)(&&|\|\|)', body):
        start = m.end()
        # i.x()&&(t.$(...),t.Qcs(...)) guards the group, i.x()&&t.Jcs(...) one call.
        end = _group_end(body, start if body[start] == "(" else body.index("(", start))
        field = getters.get(m.group(3))
        if field is None:
            raise ValueError(f"guard {m.group(0)!r} reads no field of the plugin info class")
        name = public.get(field) or "editor:" + next(
            (ace["id"] for pos, _, ace in registrations if start <= pos < end), m.group(3))
        negate = m.group(4) == "||"
        if m.group(1) is not None:
            equal = (m.group(2) == "===") != negate
            requirement = f"{name}{'=' if equal else '!='}{m.group(1)}"
        else:
            requirement = ("!" if negate else "") + name
        guards.append((start, end, requirement, field))
    return registrations, guards


def extract_common_requirements(main_js: str, lang_common: dict) -> dict[str, dict[str, list[list[str]]]]:
    """``{ace_type: {ace_id: [[requirement, ...], ...]}}`` for the shared ACEs.

    A plugin gets an ACE when every requirement of one of its lists holds; an
    ACE has two lists when the block registers it twice (``is-visible`` for
    world objects and again for DOM elements). A requirement is a flag name,
    ``!name`` for a flag that must be false, or ``name=value`` and
    ``name!=value`` for a text flag, the plugin type.
    """
    registrations, guards = _common_guards(main_js, lang_common)
    result: dict[str, dict[str, list[list[str]]]] = {t: {} for t in ACE_TYPES}
    for pos, ace_type, ace in registrations:
        needs = [req for start, end, req, _ in guards if start <= pos < end]
        result[ace_type].setdefault(ace["id"], []).append(needs)
    return result


def extract_plugin_flags(main_js: str, plugins_js: str, lang_common: dict) -> dict[str, dict[str, bool | str]]:
    """``{plugin id: {flag: value}}`` for the built-in plugins, over the flags
    the requirements name.

    ``plugins_js`` is plugins/allEditorPlugins.js, where each plugin builds its
    info in its constructor: ``const t=this.p=X.m(self.v,ID);t.k(...),t.Qt(!0)``.
    A flag the constructor does not set keeps the info class's initial value.
    """
    _, guards = _common_guards(main_js, lang_common)
    setters, _, initial = _info_class(main_js)
    name_of = {field: req.lstrip("!").split("!=")[0].split("=")[0] for _, _, req, field in guards}

    plugins: dict[str, dict[str, bool | str]] = {}
    for m in PLUGIN_INFO_RE.finditer(plugins_js):
        ids = list(re.finditer(rf'(?<![\w$.]){re.escape(m.group(2))}="([^"]+)"', plugins_js[:m.start()]))
        if not ids:
            raise ValueError(f"cannot resolve the plugin id at offset {m.start()} of allEditorPlugins.js")
        plugin_id = ids[-1].group(1)
        if plugin_id in plugins:
            raise ValueError(f"plugin {plugin_id!r} is defined twice in allEditorPlugins.js")
        receiver = re.escape(m.group(1)) if m.group(1) else r"this\.p"
        body_start = plugins_js.rfind("constructor(){", 0, m.start()) + len("constructor()")
        body = plugins_js[body_start:_group_end(plugins_js, body_start)]
        top = _top_level(body)
        flags = {name: initial.get(field, False) for field, name in name_of.items()}
        for call in re.finditer(rf'(?<![\w$.]){receiver}\.([\w$]+)\(', body):
            field = setters.get(call.group(1))
            if field not in name_of or not top[call.start()]:
                continue
            args = body[call.end():_group_end(body, call.end() - 1) - 1]
            flags[name_of[field]] = _js_value(args) if args else True
        plugins[plugin_id] = dict(sorted(flags.items()))
    return dict(sorted(plugins.items(), key=lambda kv: kv[0].lower()))


def requirement_holds(requirement: str, flags: dict[str, bool | str]) -> bool:
    if "!=" in requirement:
        name, value = requirement.split("!=", 1)
        return flags.get(name) != value
    if "=" in requirement:
        name, value = requirement.split("=", 1)
        return flags.get(name) == value
    if requirement.startswith("!"):
        return not flags.get(requirement[1:], False)
    return bool(flags.get(requirement, False))


def common_aces_of(flags: dict[str, bool | str],
                   requires: dict[str, dict[str, list[list[str]]]]) -> dict[str, list[str]]:
    """The shared ACE ids, per type, that a plugin with ``flags`` gets."""
    return {
        ace_type: [ace_id for ace_id, options in requires.get(ace_type, {}).items()
                   if any(all(requirement_holds(r, flags) for r in option) for option in options)]
        for ace_type in ACE_TYPES
    }
