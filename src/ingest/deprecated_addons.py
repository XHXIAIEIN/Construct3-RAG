"""Which built-in plugins and behaviors the editor marks deprecated.

An addon calls ``SetIsDeprecated(true)`` on its info in its editor
constructor; the editor then hides it from the Add object and Add behavior
dialogs and keeps loading projects that use it (Addon SDK reference,
``IPluginInfo`` and ``IBehaviorInfo``). ``allAces.json`` and the language
packs carry no such flag, so the export reads it from the editor bundles:

- ``main.js``: ``window.SDK.IPluginInfo`` and ``window.SDK.IBehaviorInfo``,
  whose public ``SetIsDeprecated`` calls a minified setter on the internal
  info, ``SetIsDeprecated(t){Ak.get(this).Fs(t)}``. The name changes between
  builds, so it is looked up each time.
- ``plugins/allEditorPlugins.js`` and ``behaviors/allEditorBehaviors.js``:
  each addon's constructor, ``this.p=X.m(self.v,ID)`` followed by calls on
  ``this.p`` such as ``this.p.Fs(!0)``.

Effects need none of this: ``allEffects.json`` has ``is-deprecated``, and
ACEs have ``isDeprecated`` in ``allAces.json`` and in ``common_aces.json``.
``deprecated_list`` gathers all of it into ``{locale}/_deprecated.json``, so a
reader can tell a deprecated id from one that never existed.
"""
from __future__ import annotations

import re

from src.ingest.common_aces import _call_args, _constructor_body, _id_before, _js_value, _sdk_class
from src.lookup.schema_layout import SCHEMA_ACE_TYPES

ADDON_KINDS = ("plugins", "behaviors")

# The public info classes of the Addon SDK, one per kind.
SDK_INFO_ANCHORS = {
    "plugins": "window.SDK.IPluginInfo=class{",
    "behaviors": "window.SDK.IBehaviorInfo=class{",
}

# ``const t=this.p=X.m(self.v,ID)`` in a plugin constructor, ``self.sV`` in a
# behavior's: the optional alias, then the variable that holds the addon id.
ADDON_INFO_RE = re.compile(r"(?:const ([\w$]+)=)?this\.p=[\w$]+\.m\((?:self|globalThis)\.[\w$]+,([\w$]+)\)")


def deprecated_setter(main_js: str, kind: str) -> str:
    """The minified setter that ``SetIsDeprecated`` of the ``kind`` info class calls."""
    anchor = SDK_INFO_ANCHORS[kind]
    body = _sdk_class(main_js, anchor)
    m = re.search(r"SetIsDeprecated\([\w$]*\)\{[\w$]+\.get\(this\)\.([\w$]+)\(", body)
    if m is None:
        raise ValueError(f"{anchor!r} has no SetIsDeprecated that calls the internal info")
    return m.group(1)


def extract_deprecation(main_js: str, bundle_js: str, kind: str) -> dict[str, bool]:
    """``{addon id: deprecated}`` for every addon the editor bundle constructs.

    ``bundle_js`` is ``plugins/allEditorPlugins.js`` or
    ``behaviors/allEditorBehaviors.js``. Only a call in the constructor's own
    statements counts, not one inside a callback it passes; its argument must
    be a literal boolean.
    """
    setter = re.escape(deprecated_setter(main_js, kind))
    result: dict[str, bool] = {}
    for m in ADDON_INFO_RE.finditer(bundle_js):
        addon_id = _id_before(bundle_js, m.group(2), m.start())
        if addon_id is None:
            raise ValueError(f"cannot resolve the {kind[:-1]} id at offset {m.start()} of the editor bundle")
        if addon_id in result:
            raise ValueError(f"{kind[:-1]} {addon_id!r} is constructed twice in the editor bundle")
        body, top = _constructor_body(bundle_js, m.start(), f"{kind[:-1]} {addon_id!r}")
        receivers = r"this\.p" + (f"|{re.escape(m.group(1))}" if m.group(1) else "")
        deprecated = False
        for call in re.finditer(rf"(?<![\w$.])(?:{receivers})\.{setter}\(", body):
            if not top[call.start()]:
                continue
            value = _js_value(_call_args(body, call.end()))
            if not isinstance(value, bool):
                raise ValueError(f"{kind[:-1]} {addon_id!r} calls SetIsDeprecated with {value!r}")
            deprecated = value
        result[addon_id] = deprecated
    if not result:
        raise ValueError(f"no {kind[:-1]} constructor found in the editor bundle")
    return result


def deprecated_ids(flags: dict[str, bool], addon_ids: set[str], kind: str) -> set[str]:
    """The ids of ``addon_ids`` that ``flags`` marks deprecated.

    Raises ``ValueError`` for an addon the bundle does not construct: whether
    it is deprecated is then unknown, and the export stops rather than guess.
    """
    unknown = sorted(addon_ids - set(flags))
    if unknown:
        raise ValueError(
            f"the editor bundle constructs no {kind[:-1]} " + ", ".join(unknown)
            + "; cannot tell whether it is deprecated"
        )
    return {addon_id for addon_id in addon_ids if flags[addon_id]}


def deprecated_list(
    aces: dict[str, dict],
    retired: dict[str, set[str]],
    retired_effects: list[dict],
    texts: dict[str, dict],
    version: str,
) -> dict[str, dict]:
    """``{locale: contents of {locale}/_deprecated.json}``.

    ``aces`` is ``{"plugins": ..., "behaviors": ...}`` in the ``allAces.json``
    shape, ``_common`` included; ``retired`` the addon ids the editor marks
    deprecated; ``retired_effects`` the ``allEffects.json`` entries with
    ``is-deprecated``; ``texts`` the ``text`` of each language pack.

    The list holds every deprecated addon and every deprecated ACE of the
    other addons, whether the schema kept it or not. Text a locale's pack
    lacks is taken from en-US. ``current`` names the addon's ACE of the same
    kind and English name that is not deprecated and is in the schema, when
    there is exactly one: ``pin-to-object`` has ``pin-to-object-properties``.
    """
    en, zh = texts["en-US"], texts["zh-CN"]
    out = {
        lang: {
            "version": version,
            "language": lang,
            "addons": {**{kind: {} for kind in ADDON_KINDS}, "effects": {}},
            "aces": {kind: {} for kind in ADDON_KINDS},
        }
        for lang in texts
    }

    def text(lang: str, *path: str) -> dict:
        def walk(root: dict) -> dict:
            for key in path:
                root = root.get(key, {}) if isinstance(root, dict) else {}
            return root if isinstance(root, dict) else {}
        return walk(texts[lang]) or walk(en)

    for kind in ADDON_KINDS:
        for addon_id in sorted(retired.get(kind, ()), key=str.lower):
            for lang in texts:
                t = text(lang, kind, addon_id.lower())
                out[lang]["addons"][kind][addon_id.lower()] = {
                    "originalId": addon_id,
                    "name": t.get("name", addon_id),
                    "description": t.get("description", ""),
                }
        for addon_id, categories in sorted(aces.get(kind, {}).items(), key=lambda kv: kv[0].lower()):
            if addon_id in retired.get(kind, ()):
                continue
            pid = addon_id.lower()
            for ace_type in SCHEMA_ACE_TYPES:
                name_key = "translated-name" if ace_type == "expressions" else "list-name"
                items = [a for c in categories.values() for a in c.get(ace_type, [])]
                en_aces = en.get(kind, {}).get(pid, {}).get(ace_type, {})
                in_schema = zh.get(kind, {}).get(pid, {}).get(ace_type, {})
                # The English name of each ACE, lower-cased; "" when the pack has none.
                english = {a["id"]: str(en_aces.get(a["id"], {}).get(name_key, "")).lower() for a in items}

                live: dict[str, list[str]] = {}    # English name -> ids of the current ACEs
                for a in items:
                    if not a.get("isDeprecated") and in_schema.get(a["id"]) and english[a["id"]]:
                        live.setdefault(english[a["id"]], []).append(a["id"])
                for a in items:
                    if not a.get("isDeprecated"):
                        continue
                    same = live.get(english[a["id"]], [])
                    for lang in texts:
                        t = text(lang, kind, pid, ace_type, a["id"])
                        entry = {name_key: t.get(name_key, a["id"]), "description": t.get("description", "")}
                        if len(same) == 1:
                            entry["current"] = same[0]
                        out[lang]["aces"][kind].setdefault(pid, {}).setdefault(ace_type, {})[a["id"]] = entry

    for effect in sorted(retired_effects, key=lambda e: e.get("id", "")):
        for lang in texts:
            t = text(lang, "effects", effect["id"])
            out[lang]["addons"]["effects"][effect["id"]] = {
                "name": t.get("name", effect["id"]),
                "description": t.get("description", ""),
            }
    return out
