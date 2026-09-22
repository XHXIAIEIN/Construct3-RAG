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
        if ace_id not in lang_ids[ace_type]:
            continue

        key = (ace_type, ace_id)
        if key in seen:
            _assert_same_params(seen[key], ace)
            continue
        category = next(
            (name for pos, name in reversed(category_at) if pos < match.start()), None,
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
