"""Generate a Construct 3 folder project from Python: images, object types,
families, layouts, event sheets and the parts of project.c3proj that list them.

    python tools/build_project.py

This file is the template of the construct3-project skill: copy it to tools/
in a project the editor created and saved as a folder, so that project.c3proj
already has its uniqueId, icons and scripts, and rewrite it for the game. The
generated files replace the previous ones; files the editor owns (uistate,
icons, scripts) are left alone. It ends by running the skill's
check_project.py on what it wrote and exits with the checker's code: the
project is ready for the editor when the last line starts with `ok:`.

The game below is a stand-in: coins appear, a tap collects one, the score
counts up, and when the last coin is gone the layout restarts. Replace
build_images(), build_object_types(), build_layouts(), the module_*()
functions of the event sheet and the addon list in build_project(); keep the
helpers, or grow them from the skill's `scripts/lookup_ace.py <object>
<words>`, which prints an ACE with the JSON to write, when the game needs one
they do not cover. The encodings are the ones the editor writes; see
Construct3-RAG/prompts/references/hand-editing-project-files.md.

The sheet is written a group at a time: one module_*() per group, laid out as
the official examples lay a group out (module, event, procedure, steps, cases
below). Write one, run this file, read the sheet it printed, then the next.
"""
import json
import math
import random
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Seeded so a rerun produces the same sids and the diff shows only what changed.
random.seed(20170328)

VIEW_W, VIEW_H = 720, 1280

# --- placement grid -------------------------------------------------------------------
# Every position and size is a whole number of UNITs, so that a layout reads as cells, not as
# numbers chosen one by one. The official examples align to 8 px at 320x180 (three quarters of
# their x, five sixths of their widths) and to 32 px at 1920x1080 (half of their x, three
# fifths of their widths); a HUD element sits 0, one or two units from the viewport edge
# (Construct3-RAG/docs/decisions/event-sheet-design-guidance.md, placement survey 2026-09-22).
UNIT = 8 if VIEW_H <= 360 else 32          # the grid; a pixel-art viewport gets the small one
MARGIN = UNIT                              # the HUD's distance from the viewport edge
# The smallest object a finger taps: 48 dp on Android, 44 pt on iOS (Apple HIG, Accessibility;
# Android accessibility help; WCAG 2.5.5). The viewport's shorter side is shown across a
# phone's ~360 dp, so 48 dp is 48 * shorter side / 360 viewport px, rounded up to a unit:
# 24 at 320x180, 96 at 720x1280, 160 at 1920x1080.
TOUCH = math.ceil(48 * min(VIEW_W, VIEW_H) / 360 / UNIT) * UNIT

COIN_SIZE = TOUCH                          # a coin is tapped, so it is never smaller than a finger
COIN_COUNT = 6


def units(n: float) -> int:
    """n grid units in pixels: units(3) is 96 at UNIT 32."""
    return int(round(n * UNIT))


def snap(v: float) -> int:
    """v moved to the nearest grid line."""
    return int(round(v / UNIT)) * UNIT


def anchor(where: str, w: float, h: float, ox: float = 0, oy: float = 0, dx: float = 0, dy: float = 0) -> tuple[int, int]:
    """The (x, y) of a w x h box held against the viewport edge named by `where`, MARGIN
    inside it: "top-left", "top", "top-right", "left", "center", "right", "bottom-left",
    "bottom", "bottom-right". The point returned is the box's origin (ox, oy), 0 for its
    top-left corner, 0.5 for its centre, so pass the instance's origin. dx and dy shift it
    by whole units along the axes: a second element beside the first is dx, a second row
    under a 2-unit label is dy=3, one unit of air between them, and no_overlap() prints
    the dy that clears a box that is in the way. A box held to
    the left or top lands on the grid; one held to the right, the bottom or the middle
    sits exactly MARGIN from that edge, or exactly centred, which is what the eye checks
    there. The centre of the screen is where the game is; the HUD lives on the edges."""
    vert, horiz = sides(where)
    x = {"left": MARGIN, "middle": (VIEW_W - w) / 2, "right": VIEW_W - MARGIN - w}[horiz]
    y = {"top": MARGIN, "middle": (VIEW_H - h) / 2, "bottom": VIEW_H - MARGIN - h}[vert]
    return int(round(x + units(dx) + ox * w)), int(round(y + units(dy) + oy * h))


def sides(where: str) -> tuple[str, str]:
    """An anchor name as (top|middle|bottom, left|middle|right)."""
    if where == "center":
        return "middle", "middle"
    if where in ("left", "right"):
        return "middle", where
    if where in ("top", "bottom"):
        return where, "middle"
    vert, _, horiz = where.partition("-")
    if vert not in ("top", "bottom") or horiz not in ("left", "right"):
        sys.exit(f"anchor {where!r}: one of top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right")
    return vert, horiz


def row(where: str, n: int, w: float, h: float, gap: float = 1, ox: float = 0.5, oy: float = 0.5,
        dx: float = 0, dy: float = 0) -> list[tuple[int, int]]:
    """n boxes of w x h side by side, `gap` units apart, the row as a whole held by anchor():
    three hearts top centre are row("top", 3, TOUCH, TOUCH). Returns each box's origin
    point, (ox, oy) as for anchor(), so the items never touch, whatever their size."""
    step = w + units(gap)
    x0, y0 = anchor(where, n * step - units(gap), h, 0, 0, dx, dy)
    return [(int(round(x0 + i * step + ox * w)), int(round(y0 + oy * h))) for i in range(n)]


def no_overlap(instances: list, where: str = "layer UI") -> None:
    """Stops the generator when two of these instances' boxes overlap or one reaches past the
    viewport: a HUD is read at a glance, so nothing on it hides behind anything else. Called
    on the UI layer in build_layouts(); a layer whose art is meant to stack is not passed."""
    boxes = []
    for inst in instances:
        w = inst.get("world")
        if w:
            left = w["x"] - w.get("originX", 0) * w["width"]
            top = w["y"] - w.get("originY", 0) * w["height"]
            boxes.append((inst["type"], left, top, left + w["width"], top + w["height"]))
    for kind, l, t, r, b in boxes:
        if l < 0 or t < 0 or r > VIEW_W or b > VIEW_H:
            sys.exit(f"{where}: {kind} ({l:g},{t:g})-({r:g},{b:g}) reaches past the {VIEW_W}x{VIEW_H} viewport; "
                     f"place it with anchor() or row(), which keep it MARGIN inside the edge")
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if min(a[3], b[3]) - max(a[1], b[1]) > 0 and min(a[4], b[4]) - max(a[2], b[2]) > 0:
                dy = math.ceil((a[4] + UNIT - b[2]) / UNIT)
                sys.exit(f"{where}: {a[0]} ({a[1]:g},{a[2]:g})-({a[3]:g},{a[4]:g}) overlaps {b[0]} "
                         f"({b[1]:g},{b[2]:g})-({b[3]:g},{b[4]:g}). Move {b[0]} down {dy} units: dy={dy} on its "
                         f"anchor(), row() or hud_text() call, on top of any dy it has, puts its top one unit under "
                         f"{a[0]}. Or size a label to its text with hud_text(), space repeated items with row(), "
                         f"or hold one of them to another edge.")


# --- ids ----------------------------------------------------------------------
_used_sids: set[int] = set()
_used_images: set[int] = set()
_next_uid = 0


def sid() -> int:
    """15-digit id, unique across the whole project; the editor uses the same range."""
    while True:
        v = random.randint(10**14, 10**15 - 1)
        if v not in _used_sids:
            _used_sids.add(v)
            return v


def image_id() -> int:
    while True:
        v = random.randint(10**6, 10**7 - 1)
        if v not in _used_images:
            _used_images.add(v)
            return v


def uid() -> int:
    """Instance id, unique across all layouts and single-global objects."""
    global _next_uid
    _next_uid += 1
    return _next_uid


def write_json(rel: str, obj) -> None:
    """Tab indent, LF, raw UTF-8, no trailing newline: byte for byte what the editor saves."""
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, indent="\t", ensure_ascii=False))


def q(s: str) -> str:
    """A string literal inside an expression parameter: q("tag") -> "\"tag\"". Quotes inside double up."""
    return '"' + s.replace('"', '""') + '"'


# the comparison parameter is an index into =, ≠, <, ≤, >, ≥
EQ, NE, LT, LE, GT, GE = 0, 1, 2, 3, 4, 5


# --- images ----------------------------------------------------------------------
# Stand-in art without Pillow: a PNG from an RGBA function. Real projects draw with
# Pillow or ship files; the file names below are the ones the editor expects.
def write_png(rel: str, w: int, h: int, pixel) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(pixel(x, y))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path = ROOT / "images" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def build_images() -> None:
    r = COIN_SIZE / 2

    def coin(x, y):
        d = math.hypot(x + 0.5 - r, y + 0.5 - r)
        if d > r:
            return (0, 0, 0, 0)
        return (240, 190, 60, 255) if d < r - 8 else (170, 120, 30, 255)

    write_png("coin-default-000.png", COIN_SIZE, COIN_SIZE, coin)


# --- event sheet: conditions, actions, blocks ------------------------------------------
# Ids and parameter keys come from data/c3-schemas/{locale}/plugins/{id}.json and
# behaviors/{id}.json; ACEs shared by every world object are in plugins/_common.json.
def cond(id: str, obj: str, params: dict | None = None, beh: str | None = None, inverted: bool = False) -> dict:
    c = {"id": id, "objectClass": obj, "sid": sid()}
    if beh:
        c["behaviorType"] = beh
    if params is not None:
        c["parameters"] = params
    if inverted:
        c["isInverted"] = True
    return c


def act(id: str, obj: str, params: dict | None = None, beh: str | None = None) -> dict:
    a = {"id": id, "objectClass": obj, "sid": sid()}
    if beh:
        a["behaviorType"] = beh
    if params is not None:
        a["parameters"] = params
    return a


def call(name: str, *params: str) -> dict:
    a = {"callFunction": name, "sid": sid()}
    if params:
        a["parameters"] = list(params)
    return a


def call_custom(obj: str, name: str, *params: str, family: str | None = None) -> dict:
    """Run a custom action on the picked instances of obj. family names the family
    whose block it is when obj is a member type with an override of its own."""
    a = {"customAction": name, "objectClass": obj, "sid": sid()}
    if family:
        a["customActionObjectClass"] = family
    if params:
        a["parameters"] = list(params)
    return a


def block(conds: list, acts: list, children: list | None = None, or_block: bool = False) -> dict:
    b = {"eventType": "block", "conditions": conds, "actions": acts, "sid": sid()}
    if or_block:
        b["isOrBlock"] = True
    if children:
        b["children"] = children
    return b


def var(name: str, vtype: str, init, comment: str = "", const: bool = False, static: bool = False) -> dict:
    """At the top level of a sheet this is a global; inside a group or a block, a local of that scope."""
    return {"eventType": "variable", "name": name, "type": vtype, "initialValue": str(init), "comment": comment,
            "isStatic": static, "isConstant": const, "sid": sid()}


def group(title: str, children: list, description: str = "", active: bool = True) -> dict:
    return {"eventType": "group", "disabled": False, "title": title, "description": description,
            "isActiveOnStart": active, "children": children, "sid": sid()}


def comment(text: str) -> dict:
    return {"eventType": "comment", "text": text}


def flat(rows: list) -> list:
    """Rows and lists of rows, what event() and procedure() return, as one list."""
    out: list = []
    for r in rows:
        out.extend(r if isinstance(r, list) else [r])
    return out


def event(text: str, conds: list, acts: list, children: list | None = None, or_block: bool = False) -> list:
    """A top-level event as the official examples write one: a one-sentence comment
    above the block, saying what it does or which case it is."""
    return [comment(text), block(conds, acts, children, or_block)]


def procedure(text: str, proc: dict) -> list:
    """A function or custom action with the comment above it; its description is the same sentence."""
    if not proc.get("functionDescription"):
        proc["functionDescription"] = text
    return [comment(text), proc]


def module(title: str, events: list, variables: list | None = None, procedures: list | None = None,
           active: bool = True) -> dict:
    """A group laid out as the official examples lay one out: the variables only this
    group reads (a constant with the group's prefix, a static local for state that
    outlives the tick), then its functions and custom actions, then its events.
    Entries may be rows or the row pairs event() and procedure() return."""
    return group(title, list(variables or []) + flat(procedures or []) + flat(events), active=active)


def steps(*batches: tuple) -> list:
    """The actions of a long block in labelled batches: each (label, actions) becomes
    a comment action and its three to five actions, the way the official examples
    step a block. Eight actions in a row without one is a style warning of the checker."""
    out: list = []
    for label, acts in batches:
        out.append({"type": "comment", "text": label})
        out.extend(acts)
    return out


def cases(gate: list, branches: list, acts: list | None = None) -> dict:
    """A decision as the official examples write one: one event with the shared
    conditions, then the cases as flat sub-events, each (text, conds, acts) under its
    comment. conds None is the Else of the case before it; a list that starts with
    else_() an else-if. Not a tree three sub-events deep with one call at every leaf."""
    kids: list = []
    for text, conds, case_acts in branches:
        kids.append(comment(text))
        kids.append(block([else_()] if conds is None else conds, case_acts))
    return block(gate, acts or [], kids)


def param(name: str, ptype: str, init="0", comment: str = "") -> dict:
    return {"name": name, "type": ptype, "initialValue": str(init), "comment": comment, "sid": sid()}


def func(name: str, actions: list, children: list | None = None, params: list | None = None,
         returns: str = "none", copy_picked: bool = False, is_async: bool = False, description: str = "") -> dict:
    """Locals declared as children are not in scope for the block's own actions;
    compute them in a child block instead."""
    f = {"functionName": name, "functionDescription": description, "functionCategory": "",
         "functionReturnType": returns, "functionCopyPicked": copy_picked, "functionIsAsync": is_async,
         "functionParameters": params or [], "eventType": "function-block", "conditions": [],
         "actions": actions, "sid": sid()}
    if children:
        f["children"] = children
    return f


def custom_action(obj: str, name: str, actions: list, children: list | None = None, params: list | None = None,
                  copy_picked: bool = True, description: str = "") -> dict:
    """A custom action on an object type or family: runs on exactly the instances the
    caller picked. Inside a family's block, write the family's name, not a member's."""
    f = {"aceType": "action", "aceName": name, "objectClass": obj, "functionDescription": description,
         "functionCategory": "", "functionReturnType": "none", "functionCopyPicked": copy_picked,
         "functionIsAsync": False, "functionParameters": params or [], "eventType": "custom-ace-block",
         "conditions": [], "actions": actions, "sid": sid()}
    if children:
        f["children"] = children
    return f


# System
def on_start() -> dict:
    return cond("on-start-of-layout", "System")


def every_tick() -> dict:
    return cond("every-tick", "System")


def else_() -> dict:
    return cond("else", "System")


def trigger_once() -> dict:
    return cond("trigger-once-while-true", "System")


def cmp2(a: str, op: int, b: str) -> dict:
    return cond("compare-two-values", "System", {"first-value": a, "comparison": op, "second-value": b})


def var_cmp(name: str, op: int, value: str) -> dict:
    return cond("compare-eventvar", "System", {"variable": name, "comparison": op, "value": value})


def for_loop(name: str, start: str, end: str) -> dict:
    """loopindex("name") inside. The end index is inclusive."""
    return cond("for", "System", {"name": q(name), "start-index": start, "end-index": end})


def for_each(obj: str) -> dict:
    return cond("for-each", "System", {"object": obj})


def pick_last_created(obj: str) -> dict:
    return cond("pick-last-created", "System", {"object": obj})


def set_var(name: str, value: str) -> dict:
    return act("set-eventvar-value", "System", {"variable": name, "value": value})


def add_var(name: str, value: str) -> dict:
    return act("add-to-eventvar", "System", {"variable": name, "value": value})


def set_bool_var(name: str, value: bool) -> dict:
    return act("set-boolean-eventvar", "System", {"variable": name, "value": "true" if value else "false"})


def create(obj: str, layer: str, x: str, y: str) -> dict:
    """Picks only the new instance. Give every runtime-created type a template instance in a layout that never runs."""
    return act("create-object", "System", {"object-to-create": obj, "layer": q(layer), "x": x, "y": y,
                                           "create-hierarchy": False, "template-name": q("")})


def wait(seconds: str, use_timescale: bool = True) -> dict:
    return act("wait", "System", {"seconds": seconds, "use-timescale": use_timescale})


def wait_for_previous() -> dict:
    return act("wait-for-previous-actions", "System")


def restart_layout() -> dict:
    return act("restart-layout", "System")


def go_to_layout(name: str) -> dict:
    return act("go-to-layout", "System", {"layout": name})


def set_group_active(title: str, state: str = "activated") -> dict:
    return act("set-group-active", "System", {"group-name": q(title), "state": state})


# Shared by every world object (plugins/_common.json)
def ivar_cmp(obj: str, ivar: str, op: int, value: str) -> dict:
    return cond("compare-instance-variable", obj, {"instance-variable": ivar, "comparison": op, "value": value})


def is_bool(obj: str, ivar: str, inverted: bool = False) -> dict:
    return cond("is-boolean-instance-variable-set", obj, {"instance-variable": ivar}, inverted=inverted)


def is_overlapping(obj: str, other: str, inverted: bool = False) -> dict:
    return cond("is-overlapping-another-object", obj, {"object": other}, inverted=inverted)


def pick_children(obj: str, child: str) -> dict:
    return cond("pick-children", obj, {"child": child, "which": "own"})


def set_ivar(obj: str, ivar: str, value: str) -> dict:
    return act("set-instvar-value", obj, {"instance-variable": ivar, "value": value})


def set_bool(obj: str, ivar: str, value: bool) -> dict:
    return act("set-boolean-instvar", obj, {"instance-variable": ivar, "value": "true" if value else "false"})


def set_position(obj: str, x: str, y: str) -> dict:
    return act("set-position", obj, {"x": x, "y": y})


def set_visible(obj: str, visible: bool) -> dict:
    return act("set-visible", obj, {"visibility": "visible" if visible else "invisible"})


def destroy(obj: str) -> dict:
    return act("destroy", obj)


def add_child(parent: str, child: str, follow: bool = False) -> dict:
    """follow=True moves and turns the child with its parent; False keeps only the relation."""
    return act("add-child", parent, {
        "child": child, "transform-x": follow, "transform-y": follow, "transform-z-elevation": False,
        "transform-w": False, "transform-h": False, "transform-d": False, "transform-a": follow,
        "transform-o": False, "transform-visibility": False, "destroy-with-parent": True})


# Sprite, Text
def set_animation(obj: str, name: str) -> dict:
    return act("set-animation", obj, {"animation": q(name), "from": "beginning"})


def set_text(obj: str, text: str) -> dict:
    return act("set-text", obj, {"text": text})


# Tween behavior (behaviors/tween.json); beh is the name given to the behavior on the object
def tween1(obj: str, tag: str, prop: str, end: str, time: str, ease: str = "easeinoutsine",
           destroy: bool = False, beh: str = "Tween") -> dict:
    """prop: offsetX, offsetY, size, offsetWidth, offsetHeight, offsetAngle, offsetOpacity, offsetScaleX, ..."""
    return act("tween-one-property", obj, {
        "tags": q(tag), "property": prop, "end-value": end, "time": time, "ease": ease,
        "destroy-on-complete": "yes" if destroy else "no", "loop": "no", "ping-pong": "no", "repeat-count": "1"}, beh=beh)


def tween2(obj: str, tag: str, prop: str, end_x: str, end_y: str, time: str, ease: str = "easeinoutsine",
           destroy: bool = False, beh: str = "Tween") -> dict:
    """prop: position, size or scale."""
    return act("tween-two-properties", obj, {
        "tags": q(tag), "property": prop, "end-x": end_x, "end-y": end_y, "time": time, "ease": ease,
        "destroy-on-complete": "yes" if destroy else "no", "loop": "no", "ping-pong": "no", "repeat-count": "1"}, beh=beh)


def tween_value(obj: str, tag: str, start: str, end: str, time: str, ease: str = "easeinoutsine", beh: str = "Tween") -> dict:
    """Read it back with Obj.Tween.Value("tag") while is_playing; for what Tween has no property for."""
    return act("tween-value", obj, {
        "tags": q(tag), "start-value": start, "end-value": end, "time": time, "ease": ease,
        "destroy-on-complete": "no", "loop": "no", "ping-pong": "no", "repeat-count": "1"}, beh=beh)


def is_playing(obj: str, tag: str, inverted: bool = False, beh: str = "Tween") -> dict:
    return cond("is-playing", obj, {"tags": q(tag)}, beh=beh, inverted=inverted)


def on_tween_finished(obj: str, tag: str, beh: str = "Tween") -> dict:
    return cond("on-tweens-finished", obj, {"tags": q(tag)}, beh=beh)


def on_any_tween_finished(obj: str, beh: str = "Tween") -> dict:
    return cond("on-any-tweens-finished", obj, beh=beh)


def stop_tweens(obj: str, tag: str, beh: str = "Tween") -> dict:
    return act("stop-tweens", obj, {"tags": q(tag)}, beh=beh)


# Timer behavior (behaviors/timer.json)
def start_timer(obj: str, tag: str, duration: str, regular: bool = False, beh: str = "Timer") -> dict:
    """Starting a tag that is running restarts it."""
    return act("start-timer", obj, {"duration": duration, "type": "regular" if regular else "once", "tag": q(tag)}, beh=beh)


def stop_timer(obj: str, tag: str, beh: str = "Timer") -> dict:
    return act("stop-timer", obj, {"tag": q(tag)}, beh=beh)


def on_timer(obj: str, tag: str, beh: str = "Timer") -> dict:
    """Can fire with several instances picked; add for_each before per-instance work."""
    return cond("on-timer", obj, {"tag": q(tag)}, beh=beh)


def timer_running(obj: str, tag: str, inverted: bool = False, beh: str = "Timer") -> dict:
    return cond("is-timer-running", obj, {"tag": q(tag)}, beh=beh, inverted=inverted)


# Touch plugin
def on_touched(obj: str) -> dict:
    """Fires when the finger lands; a tap is only known on release (type "end")."""
    return cond("on-touched-object", "Touch", {"object": obj, "type": "start"})


# --- the event sheet -------------------------------------------------------------------
# One function per group, in play order. A game grows a group at a time: write a
# module, run the generator, read the sheet it printed, then write the next.
def module_setup() -> dict:
    return module("Setup", events=[
        event("Deal the coins and show the empty score.",
              [on_start()], [set_text("ScoreText", q("Score: 0"))], children=[
                  block([for_loop("i", "0", "COIN_COUNT - 1")], [
                      create("Coin", "Game", f"random({COIN_SIZE}, LayoutWidth - {COIN_SIZE})",
                             f"random({COIN_SIZE * 2}, LayoutHeight - {COIN_SIZE})"),
                      set_ivar("Coin", "value", "choose(1, 5)"),
                  ]),
              ]),
    ])


def module_input() -> dict:
    return module("Input", events=[
        event("A touched coin collects itself.", [on_touched("Coin")], [call_custom("Coin", "Collect")]),
    ])


def scoring() -> list:
    """What the groups call: a custom action for what acts on the caller's picked
    instances, a function for a value or for logic that picks its own."""
    return [
        *procedure("Shrink the coin away and score it.", custom_action("Coin", "Collect", [
            tween2("Coin", "collect", "size", "0", "0", "0.25", "easeinback", destroy=True),
            call("AddScore", "Coin.value"),
        ])),
        *procedure("Add points and show the score.", func("AddScore", [
            add_var("score", "points"),
            set_text("ScoreText", q("Score: ") + " & score"),
        ], params=[param("points", "number", 0)])),
    ]


def module_restart() -> dict:
    return module("Restart", events=[
        event("Restart when the last coin is gone.",
              [cmp2("Coin.Count", EQ, "0"), trigger_once()], [wait("1"), restart_layout()]),
    ])


def build_event_sheet() -> dict:
    """What the sheet covers, the constants under Settings, the state the groups share,
    then the groups; a variable one group owns is declared in that module instead."""
    events = [
        comment("Coins. Tap a coin to collect it; when the last one is gone the layout restarts.\n"
                "The touched coin is the trigger's pick: Collect runs on it and nothing else."),
        comment("Settings."),
        var("COIN_COUNT", "number", COIN_COUNT, "Coins dealt at the start.", const=True),
        comment("Gameplay variables."),
        var("score", "number", 0, "Points collected this round."),
        module_setup(),
        module_input(),
        *scoring(),
        module_restart(),
    ]
    return {"name": "Game", "events": events, "sid": sid()}


# --- object types --------------------------------------------------------------------
def frame(w: int, h: int, ox: float = 0.5, oy: float = 0.5) -> dict:
    return {"width": w, "height": h, "originX": ox, "originY": oy, "originalSource": "",
            "exportFormat": "lossless", "exportQuality": 0.8, "fileType": "image/png", "imageSpriteId": image_id(),
            "collisionPoly": {"points": [0, 0, 1, 0, 1, 1, 0, 1]}, "useCollisionPoly": True, "duration": 1, "tag": ""}


def animation(name: str, frames: list, speed: float = 0) -> dict:
    """speed 0 holds the frame for events to choose; above 0 the animation loops at that many frames a second."""
    return {"frames": frames, "sid": sid(), "name": name, "isLooping": speed > 0, "isPingPong": False,
            "repeatCount": 1, "repeatTo": 0, "speed": speed}


def ivar_def(name: str, vtype: str, desc: str = "") -> dict:
    return {"name": name, "type": vtype, "desc": desc, "show": True, "sid": sid()}


def beh_def(behavior_id: str, name: str | None = None) -> dict:
    """name is what events refer to; two Sine behaviors on one object need two names."""
    return {"behaviorId": behavior_id, "name": name or behavior_id, "sid": sid()}


def sprite_type(name: str, animations: list, ivars: list = (), behaviors: list = ()) -> dict:
    return {"name": name, "plugin-id": "Sprite", "sid": sid(), "isGlobal": False, "editorNewInstanceIsReplica": True,
            "instanceVariables": list(ivars), "behaviorTypes": list(behaviors), "effectTypes": [],
            "animations": {"items": animations, "subfolders": []}}


def text_type(name: str, ivars: list = (), behaviors: list = ()) -> dict:
    return {"name": name, "plugin-id": "Text", "sid": sid(), "isGlobal": False, "editorNewInstanceIsReplica": True,
            "instanceVariables": list(ivars), "behaviorTypes": list(behaviors), "effectTypes": []}


def single_global_type(name: str, plugin_id: str, properties: dict) -> dict:
    """Touch, Keyboard, Mouse, Audio, AdvancedRandom, LocalStorage: one instance, not placed in a layout."""
    return {"name": name, "plugin-id": plugin_id, "sid": sid(),
            "singleglobal-inst": {"type": name, "properties": properties, "uid": uid(), "sid": sid(), "tags": ""}}


def nonworld_type(name: str, plugin_id: str, ivars: list = ()) -> dict:
    """Array, Dictionary, JSON: instances go in a layout's nonworld-instances."""
    return {"name": name, "plugin-id": plugin_id, "sid": sid(), "isGlobal": False, "instanceVariables": list(ivars)}


def family(name: str, plugin_id: str, members: list, ivars: list = (), behaviors: list = ()) -> dict:
    """Instance variables and behaviors declared here are the members'; a member's
    layout instances carry them as their own. Written to families/<name>.json."""
    return {"name": name, "plugin-id": plugin_id, "sid": sid(), "instanceVariables": list(ivars),
            "behaviorTypes": list(behaviors), "effectTypes": [], "members": list(members)}


def container(members: list) -> dict:
    """Object types whose instances are created, destroyed and picked together, a
    tank base with its turret. A container has no file of its own: it is a row of
    project.c3proj's "containers", and its members are object types, not families."""
    return {"members": list(members)}


def build_object_types() -> tuple[dict, dict, list]:
    types = {
        "Coin": sprite_type("Coin", [animation("Default", [frame(COIN_SIZE, COIN_SIZE)])],
                            ivars=[ivar_def("value", "number", "Points it is worth."),
                                   ivar_def("kind", "string", "Which coin: \"gold\" or \"silver\".")],
                            behaviors=[beh_def("Tween")]),
        "ScoreText": text_type("ScoreText"),
        "Touch": single_global_type("Touch", "Touch", {"use-mouse-input": True}),
    }
    families = {}
    containers = []
    return types, families, containers


# --- layouts -------------------------------------------------------------------------------
def layer(name: str, bg=(255, 255, 255), transparent: bool = True, parallax: float = 1) -> dict:
    """parallax 0 for a HUD layer that stays put while the layout scrolls."""
    return {"name": name, "overriden": 0, "subLayers": [], "instances": [], "sid": sid(), "effectTypes": [],
            "isInitiallyVisible": True, "isInitiallyInteractive": True, "isHTMLElementsLayer": False,
            "color": [1, 1, 1, 1], "backgroundColor": [c / 255 for c in bg] + [1], "isTransparent": transparent,
            "sampling": "auto", "parallaxX": parallax, "parallaxY": parallax, "scaleRate": 1, "forceOwnTexture": False,
            "renderingMode": "3d", "drawOrder": "z-order", "useRenderCells": False, "blendMode": "normal",
            "zElevation": 0, "global": False}


def layout(name: str, layers: list, sheet: str | None, nonworld: list = (), width: int = VIEW_W, height: int = VIEW_H) -> dict:
    return {"name": name, "layers": layers, "sid": sid(), "nonworld-instances": list(nonworld), "effectTypes": [],
            "width": width, "height": height, "unboundedScrolling": False, "sampling": "auto", "ambientLight": 0.03,
            "vpX": 0.5, "vpY": 0.5, "projection": "perspective", "eventSheet": sheet}


def world(x: float, y: float, w: float, h: float, ox: float = 0.5, oy: float = 0.5, angle: float = 0,
          color=(1, 1, 1, 1)) -> dict:
    """angle in degrees; the file stores radians. color is RGBA in 0..1, alpha being the opacity."""
    return {"x": x, "y": y, "width": w, "height": h, "depth": 0, "originX": ox, "originY": oy,
            "color": list(color), "z": 0, "angle": math.radians(angle) if angle else 0}


def instance(otype: str, properties: dict, world_: dict | None, ivars: dict | None = None,
             behaviors: dict | None = None) -> dict:
    """ivars must list every instance variable of the type and its families; behaviors
    every behavior, as {name: {"properties": {...}}}."""
    inst = {"type": otype, "properties": properties, "uid": uid(), "sid": sid(), "tags": "",
            "instanceVariables": ivars or {}, "behaviors": behaviors or {}, "showing": True, "locked": False}
    if world_ is not None:
        inst["world"] = world_
    return inst


def sprite_inst(otype: str, x: float, y: float, w: float, h: float, anim: str = "Default", ivars=None,
                behaviors=None, collisions: bool = True) -> dict:
    return instance(otype, {"initially-visible": True, "initial-animation": anim, "initial-frame": 0,
                            "enable-collisions": collisions, "live-preview": False},
                    world(x, y, w, h), ivars, behaviors)


def text_inst(otype: str, text: str, x: float, y: float, w: float, h: float, size: float = 24,
              halign: str = "left", bold: bool = False, ivars=None, behaviors=None) -> dict:
    return instance(otype, {"text": text, "enable-bbcode": False, "font": "Arial", "size": size, "line-height": 0,
                            "bold": bold, "italic": False, "color": [1, 1, 1, 1], "horizontal-alignment": halign,
                            "vertical-alignment": "center", "wrapping": "word", "text-direction": "ltr",
                            "icon-set": -1, "initially-visible": True, "origin": "top-left", "read-aloud": False},
                    world(x, y, w, h, 0, 0), ivars, behaviors)


def hud_text(otype: str, text: str, where: str, size: float = 32, longest: str | None = None, bold: bool = True,
             dx: float = 0, dy: float = 0, ivars=None, behaviors=None) -> dict:
    """A HUD label held against an edge or corner by anchor(). Its box is as wide as its
    longest text (about 0.6 em a character, rounded up to a unit) and the text is aligned to
    the side the box hangs on, so a right-hand label grows leftwards and two labels on one
    edge never meet. `longest` is the widest text the label shows at runtime, "Score: 999"
    for a label that starts as "Score: 0"."""
    w = math.ceil(len(longest or text) * size * 0.6 / UNIT) * UNIT
    h = math.ceil(size * 1.5 / UNIT) * UNIT
    halign = {"left": "left", "middle": "center", "right": "right"}[sides(where)[1]]
    x, y = anchor(where, w, h, 0, 0, dx, dy)
    return text_inst(otype, text, x, y, w, h, size=size, halign=halign, bold=bold, ivars=ivars, behaviors=behaviors)


# The properties block a layout instance writes for a behavior, keyed by the name
# the behavior has on the object (beh_def's name; the key changes with it). The
# keys are the schema's `properties` (behaviors/<id>.json), the values the ones
# official examples hold; change a value, not a key. A behavior missing here:
# copy the block from an instance of an official example that has it, under the
# behavior's name on that object, not its id ("Sine", not "Sin").
TWEEN = {"Tween": {"properties": {"enabled": True}}}
TIMER = {"Timer": {"properties": {}}}
SOLID = {"Solid": {"properties": {"enabled": True, "use-instance-tags": True, "tags": ""}}}
SINE = {"Sine": {"properties": {"movement": "horizontal", "wave": "sine", "period": 4, "period-random": 0,
                                "period-offset": 0, "period-offset-random": 0, "magnitude": 50,
                                "magnitude-random": 0, "enabled": True, "live-preview": False}}}
FADE = {"Fade": {"properties": {"fade-in-time": 0, "wait-time": 0, "fade-out-time": 1, "destroy": True,
                                "enabled": True, "live-preview": False}}}
FLASH = {"Flash": {"properties": {}}}
BULLET = {"Bullet": {"properties": {"speed": 400, "acceleration": 0, "gravity": 0, "bounce-off-solids": False,
                                    "set-angle": True, "step": False, "enabled": True}}}
EIGHT_DIR = {"8Direction": {"properties": {"max-speed": 200, "acceleration": 600, "deceleration": 500,
                                           "directions": "dir-8", "set-angle": "smooth", "allow-sliding": True,
                                           "default-controls": True, "enabled": True}}}
PLATFORM = {"Platform": {"properties": {"max-speed": 330, "acceleration": 1500, "deceleration": 1500,
                                        "jump-strength": 650, "gravity": 1500, "max-fall-speed": 1000,
                                        "double-jump": False, "jump-sustain": 0, "default-controls": True,
                                        "enabled": True}}}
MOVE_TO = {"MoveTo": {"properties": {"max-speed": 200, "acceleration": 600, "deceleration": 600, "rotate-speed": 0,
                                     "set-angle": False, "stop-on-solids": False, "enabled": True}}}
ROTATE = {"Rotate": {"properties": {"speed": 90, "acceleration": 0, "rotation-type": "2d", "enabled": True,
                                    "live-preview": False}}}
PIN = {"Pin": {"properties": {"destroy": False}}}
DRAG_DROP = {"DragDrop": {"properties": {"axes": "both", "enabled": True}}}
SCROLL_TO = {"ScrollTo": {"properties": {"enabled": True}}}
DESTROY_OUTSIDE = {"DestroyOutsideLayout": {"properties": {"region": "layout"}}}
BOUND_TO_LAYOUT = {"BoundToLayout": {"properties": {"bound-by": "edge", "region": "layout"}}}
LINE_OF_SIGHT = {"LineOfSight": {"properties": {"obstacles": "solids", "range": 512, "cone-of-view": 90,
                                                "use-collision-cells": True}}}


def build_layouts() -> dict[str, dict]:
    game = layout("Game", [
        layer("Background", bg=(30, 34, 48), transparent=False),
        layer("Game"),
        layer("UI", parallax=0),
    ], sheet="Game")
    # The HUD hangs on the edges, MARGIN inside them: a label by hud_text(), repeated items by
    # row(), anything else by anchor(); the middle of the screen is the game's. no_overlap()
    # stops the run when two HUD boxes meet or one leaves the viewport.
    ui = game["layers"][2]["instances"]
    ui.append(hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999"))
    no_overlap(ui)
    # Runtime-created objects are copied from a template instance; keep those in a layout that never runs.
    objects = layout("Objects", [layer("Objects")], sheet=None)
    objects["layers"][0]["instances"].append(
        sprite_inst("Coin", *anchor("top-left", COIN_SIZE, COIN_SIZE, 0.5, 0.5), COIN_SIZE, COIN_SIZE,
                    ivars={"value": 1, "kind": "gold"}, behaviors=dict(TWEEN)))
    return {"Game": game, "Objects": objects}


# --- project.c3proj -------------------------------------------------------------------------
def build_project(existing: dict, types: dict, families: dict, containers: list, layouts: dict,
                  sheets: list) -> dict:
    """Only the keys this script owns change; uniqueId, icons, scripts and properties stay."""
    p = dict(existing)
    p["name"] = "Coins"
    p["usedAddons"] = [
        {"type": "plugin", "id": "Sprite", "name": "Sprite",
            "author": "Scirra", "bundled": False},
        {"type": "plugin", "id": "Text", "name": "Text",
            "author": "Scirra", "bundled": False},
        {"type": "plugin", "id": "Touch", "name": "Touch",
            "author": "Scirra", "bundled": False},
        {"type": "behavior", "id": "Tween", "name": "Tween",
            "author": "Scirra", "bundled": False},
    ]
    p["objectTypes"] = {"items": list(types), "subfolders": []}
    p["families"] = {"items": list(families), "subfolders": []}
    p["containers"] = list(containers)
    p["layouts"] = {"items": list(layouts), "subfolders": []}
    p["eventSheets"] = {"items": sheets, "subfolders": []}
    p["viewportWidth"] = VIEW_W
    p["viewportHeight"] = VIEW_H
    p["firstLayout"] = "Game"
    p["properties"]["orientations"] = "portrait"
    return p


def build_all() -> None:
    c3proj = ROOT / "project.c3proj"
    if not c3proj.exists():
        sys.exit(
            f"{c3proj} not found: create the project in the editor and save it as a folder first")
    build_images()
    types, families, containers = build_object_types()
    for name, t in types.items():
        write_json(f"objectTypes/{name}.json", t)
    for name, f in families.items():
        write_json(f"families/{name}.json", f)
    layouts = build_layouts()
    for name, lay in layouts.items():
        write_json(f"layouts/{name}.json", lay)
    sheet = build_event_sheet()
    write_json(f"eventSheets/{sheet['name']}.json", sheet)
    with c3proj.open(encoding="utf-8") as f:
        existing = json.load(f)
    write_json("project.c3proj", build_project(
        existing, types, families, containers, layouts, [sheet["name"]]))


if __name__ == "__main__":
    build_all()
    # Generating without checking is how a project reaches the editor with a mistake
    # the checker names in one line; the two always run together. The skill is
    # installed in the project, or once for the user, under a client's skills folder.
    checker = "skills/construct3-project/scripts/check_project.py"
    found = sorted(ROOT.glob(f".*/{checker}")) or sorted(Path.home().glob(f".*/{checker}"))
    if not found:
        sys.exit("generated, not checked: the construct3-project skill is not installed in this project; "
                 "run python <Construct3-RAG>/skills/construct3-project/scripts/install.py here, then "
                 "its scripts/check_project.py")
    print("generated; checking")
    sys.stdout.flush()
    # --style: the agent wrote every event, so the readability warnings of the official
    # examples' style apply to all of them.
    sys.exit(subprocess.run([sys.executable, str(found[0]), "--project", str(ROOT), "--style"]).returncode)
