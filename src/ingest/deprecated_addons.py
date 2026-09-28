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

Effects need none of this: ``allEffects.json`` has ``is-deprecated``.
"""
from __future__ import annotations

import re

from src.ingest.common_aces import _group_end, _js_value, _top_level

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
    at = main_js.find(anchor)
    if at == -1:
        raise ValueError(f"no {anchor!r} in main.js")
    start = at + len(anchor) - 1
    body = main_js[start:_group_end(main_js, start)]
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
        ids = list(re.finditer(rf'(?<![\w$.]){re.escape(m.group(2))}="([^"]+)"', bundle_js[:m.start()]))
        if not ids:
            raise ValueError(f"cannot resolve the {kind[:-1]} id at offset {m.start()} of the editor bundle")
        addon_id = ids[-1].group(1)
        if addon_id in result:
            raise ValueError(f"{kind[:-1]} {addon_id!r} is constructed twice in the editor bundle")
        head = bundle_js.rfind("constructor(){", 0, m.start())
        if head == -1:
            raise ValueError(f"{kind[:-1]} {addon_id!r} builds its info outside a constructor")
        body_start = head + len("constructor()")
        body = bundle_js[body_start:_group_end(bundle_js, body_start)]
        top = _top_level(body)
        receivers = r"this\.p" + (f"|{re.escape(m.group(1))}" if m.group(1) else "")
        deprecated = False
        for call in re.finditer(rf"(?<![\w$.])(?:{receivers})\.{setter}\(", body):
            if not top[call.start()]:
                continue
            value = _js_value(body[call.end():_group_end(body, call.end() - 1) - 1])
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
