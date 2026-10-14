"""Generate a Construct 3 folder project: images, object types, families,
layouts, event sheets and the parts of project.c3proj that list them.

    python tools/build_project.py

Copy this template to tools/ of a project that the editor saved as a folder,
then rewrite it for the game. A run replaces the files it generates and keeps
the editor's own: uistate, icons, scripts. It ends with the skill's
check_project.py and exits with its code; a last line that starts with `ok:`
means the editor can open the project.

The file has three parts:
1. The game's settings: name, viewport, grid, look.
2. The skill's helpers, between the begin and end markers, the same in every
   game. The skill's install.py replaces them when the skill is refreshed.
3. The game: BEATS, build_files(), build_images(), build_object_types(),
   build_layouts() and the module_*() functions of the event sheet.

The game here is a stand-in: tap the coins, the score counts up, and the next
round starts when the last coin is gone. Rewrite the settings and the game
part, draw every sprite with art(), and keep the helpers. A helper the game
needs goes below the end marker; the skill's `scripts/lookup_ace.py <object>
<words>` prints an ACE with the JSON to write.

Write the sheet one group at a time: write a module_*(), run this file, read
the sheet it prints, then write the next.
"""
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Fixed seed: a rerun writes the same sids, so a diff shows only real changes
random.seed(20170328)

VIEW_W, VIEW_H = 1920, 1080
PROJECT_NAME = "Coins"                     # project name in the editor
FIRST_LAYOUT = "Game"                      # layout the game starts on
ORIENTATION = "landscape"                  # "portrait", "landscape" or "any"

# --- placement grid -------------------------------------------------------------------
# Every position and size is whole UNITs, so a layout reads as cells
UNIT = 8 if VIEW_H <= 360 else 32          # grid cell in px; 8 for a pixel-art viewport
MARGIN = UNIT                              # HUD distance from the viewport edge
# Smallest tap target in px: 48 dp, the viewport's shorter side being a phone's 360 dp, rounded
# up to a unit: 24 at 320x180, 96 at 720x1280, 160 at 1920x1080
TOUCH = math.ceil(48 * min(VIEW_W, VIEW_H) / 360 / UNIT) * UNIT

COIN_SIZE = TOUCH                          # a coin is tapped, so it is never smaller than a finger

# --- look -----------------------------------------------------------------------------
# Colours by role. Every image, label and layer takes its colour from here, and write_png()
# stops the run on any other colour, so a new object reuses a role or adds one.
# solid and the accents read at least 3:1 on canvas_alt, so a shape shows without an outline;
# check_palette() stops solid below that, and shape() an accent drawn without its outline.
# Two accents, reward and danger; add a third only for a role they do not cover, such as a goal.
PALETTE = {
    "canvas": (250, 250, 247),         # opaque layer fill; light checker cells
    "canvas_alt": (238, 238, 234),     # dark checker cells, at most 1.2:1 from canvas
    "solid": (132, 132, 128),          # structure, a bar's frame; at least 3:1 on canvas_alt
    "dim": (100, 100, 96),             # secondary label
    "ink": (17, 17, 17),               # player, outlines, labels, a bar's fill
    "reward": (37, 99, 235),           # what the player collects
    "danger": (220, 38, 60),           # what hurts or is lost
    "flash": (255, 255, 255),          # fill of an object at the instant it is hit
}
# Outline and cast shadow of every image shape() draws. The outline lies inside the shape's
# edge, so the shape keeps its grid size; the shadow is an offset copy that widens the image.
# Both are drawn into the image, because no built-in effect draws an outline or a shadow.
# A shadow in the image turns with a rotating sprite: draw such a sprite with shape(..., shadow=False).
SHAPE_STYLE = {
    "outline": False,
    "outline_width": max(1, UNIT // 4),                      # px, inside the edge
    "outline_role": "ink",
    "shadow": False,
    "shadow_distance": round(0.027 * min(VIEW_W, VIEW_H)),   # px: 2.7% of the shorter side
    "shadow_angle": 45,                                      # degrees clockwise from rightwards: 90 is down
    "shadow_opacity": 0.5,
    "shadow_role": "ink",
}
# Hit flash: the shape's second frame in this role, shown by hit_flash() for `seconds` of real
# time. hit_frame() draws it with the outline, so a white flash shows on the sheet.
# A frame, not the object's colour: the colour multiplies the image and cannot turn it white.
HIT_FLASH = {"role": "flash", "seconds": 0.08}
# Squash and stretch by kind: the size set to a share of the image's size, held, then tweened
# back. squash(obj, kind) plays one; hit() plays the hit's with its flash.
# Squash the art, never the object that collides: a Platform or Solid object that grows sinks
# into the floor. The art is a second object, origin at its feet with shape(..., oy=1), pinned
# to an invisible collision mask.
SQUASH = {
    "hit": {"width": 0.8, "height": 1.2, "hold": 0, "seconds": 0.25, "ease": "easeoutback"},
    "land": {"width": 1.2, "height": 0.8, "hold": 0, "seconds": 0.5, "ease": "easeoutelastic"},
    "jump": {"width": 0.7, "height": 1.3, "hold": 0.2, "seconds": 0.75, "ease": "easeoutelastic"},
}
FONT = "system-ui"                         # every label; the platform's own UI face
TEXT_SIZE = {"body": UNIT, "title": 2 * UNIT}   # body for labels, title for banners
# 360 px high or less is pixel art: Nearest sampling, whole-number scaling
PIXEL_ART = UNIT == 8
# Art direction in one sentence, agreed with the user: rendering, linework, colour temperature,
# light direction, proportions and framing, never a subject. For example "flat vector with soft
# cel shading, thick dark outlines, warm colours, light from the top left, chunky proportions,
# side view", or "ink wash on rice paper, dry brush edges, cool muted greens, light from above,
# slender proportions, three-quarter view from above". Every image prompt of the skill's scripts/prepare_art.py starts with it;
# prepare_art.py --list warns of a dimension it leaves out.
ART_STYLE = ""


# ==== construct3-agent-plugin helpers: begin ======================================================
# The skill's helpers, the same in every game. They read the settings above, so a game changes
# their values and keeps their names. The skill's install.py replaces this part, up to the end
# marker, when the skill is refreshed, unless it was edited here.
# To change a helper for this game, define it again below the end marker: the definition there
# wins, and a refresh keeps it.
import difflib
import json
import math
import random
import struct
import subprocess
import sys
import unicodedata
import zlib
from pathlib import Path


# --- grid and pacing --------------------------------------------------------------------
# Beat types of BEATS; pace() checks the curve they make
BEAT_TYPES = ("intro", "teach", "practice", "twist", "rest", "climax", "exit")


def beat(kind: str, intensity: int, mechanics: tuple = (), holds: str = "", **game) -> dict:
    """One beat of BEATS: beat("rest", 0, holds="pickup", coins=2)."""
    return {"type": kind, "intensity": intensity, "mechanics": list(mechanics), "holds": holds, **game}


def units(n: float) -> int:
    """n grid units in pixels: units(3) is 96 at UNIT 32."""
    return int(round(n * UNIT))


def snap(v: float) -> int:
    """v moved to the nearest grid line."""
    return int(round(v / UNIT)) * UNIT


def anchor(where: str, w: float, h: float, ox: float = 0, oy: float = 0, dx: float = 0, dy: float = 0) -> tuple[int, int]:
    """(x, y) of a w x h box held MARGIN inside the viewport edge `where`: "top-left", "top",
    "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right".
    The point is the box's origin (ox, oy): 0 its top-left corner, 0.5 its centre. dx and dy
    shift it in whole units, for a second element beside or under the first. Give the instance
    behaviors=anchored(where), which holds it to the screen's edge."""
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
    """Origins of n w x h boxes side by side, `gap` units apart, the row held by anchor():
    row("top", 3, TOUCH, TOUCH) for three hearts top centre. Give each instance
    behaviors=anchored(where)."""
    step = w + units(gap)
    x0, y0 = anchor(where, n * step - units(gap), h, 0, 0, dx, dy)
    return [(int(round(x0 + i * step + ox * w)), int(round(y0 + oy * h))) for i in range(n)]


# --- the screen ---------------------------------------------------------------------------
# Scale outer fills any screen; pixel art takes Integer scale outer, which keeps pixels square.
# anchored() holds a HUD element to an edge, screen_box() pads a backdrop or a cover by
# SCREEN_PAD, and layout() scrolls a one-screen layout unbounded.
FULLSCREEN = "integer-scale-outer" if PIXEL_ART else "scale-outer"
# px a backdrop reaches past each viewport edge: covers any screen up to 4:1 and a shaking camera
SCREEN_PAD = math.ceil(2 * max(VIEW_W, VIEW_H) / UNIT) * UNIT


def anchored(where: str) -> dict:
    """The Anchor behavior block that holds a parallax-0 instance to the screen edge `where`, as
    anchor() names it; {} for "center". hud_text(), hud_bar(), labelled_bar() and band_text()
    add it themselves, and build_all() gives the object type the behavior."""
    vert, horiz = sides(where)
    if vert == horiz == "middle":
        return {}
    return {"Anchor": {"properties": {"left-edge": {"left": "window-left", "right": "window-right"}.get(horiz, "none"),
                                      "top-edge": {"top": "window-top", "bottom": "window-bottom"}.get(vert, "none"),
                                      "right-edge": "none", "bottom-edge": "none", "enabled": True}}}


def screen_box(width: int | None = None, height: int | None = None, ox: float = 0, oy: float = 0) -> tuple[int, int, int, int]:
    """(x, y, w, h) of a box over the layout, `width` x `height` (the viewport's by default),
    reaching SCREEN_PAD past it on every side, with (x, y) at its origin (ox, oy). For a
    backdrop, or a popup's dim: sprite_inst("Dim", *screen_box(ox=0.5, oy=0.5)).
    A dim that closes its popup tests the tap against the panel (On any touch start and NOT Is
    touching the panel), so the dim's size decides nothing about input."""
    w = (VIEW_W if width is None else width) + 2 * SCREEN_PAD
    h = (VIEW_H if height is None else height) + 2 * SCREEN_PAD
    return int(-SCREEN_PAD + ox * w), int(-SCREEN_PAD + oy * h), w, h


def no_overlap(instances: list, where: str = "layer UI") -> None:
    """Stops the run when two of these instances overlap or one reaches past the viewport.
    A box wholly inside another passes (a bar's fill in its frame, an icon on its panel) unless
    the outer one is a label; so do the parts of one link() hierarchy. Pass the UI layer, not a
    layer whose art stacks on purpose."""
    boxes, parts, said = [], [], []
    for inst in instances:
        b = box_of(inst)
        if b:
            boxes.append((inst["type"], *b, "text" in inst.get("properties", {})))
            parts.append(inst)
    for kind, l, t, r, b, _ in boxes:
        if l < 0 or t < 0 or r > VIEW_W or b > VIEW_H:
            said.append(f"{where}: {kind} ({l:g},{t:g})-({r:g},{b:g}) reaches past the {VIEW_W}x{VIEW_H} viewport; "
                        f"place it with anchor() or row(), which keep it MARGIN inside the edge")

    def layered(inner: tuple, outer: tuple) -> bool:
        """inner wholly inside outer, outer not a label, which hides what lies on it."""
        return (not outer[5] and outer[1] <= inner[1] and outer[2] <= inner[2]
                and inner[3] <= outer[3] and inner[4] <= outer[4])

    parent_of = {inst["uid"]: (inst.get("sceneGraphData") or {}).get("parent-uid") for inst in parts}

    def root(inst: dict) -> int:
        """The uid at the top of the instance's hierarchy among these instances."""
        u, seen = inst["uid"], set()
        while parent_of.get(u) in parent_of and u not in seen:
            seen.add(u)
            u = parent_of[u]
        return u

    def linked(m: int, n: int) -> bool:
        """Two parts of one link() hierarchy, which their helper laid out together."""
        return root(parts[m]) == root(parts[n]) and (parent_of[parts[m]["uid"]] is not None
                                                   or parent_of[parts[n]["uid"]] is not None)

    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes[i + 1:], i + 1):
            if layered(a, b) or layered(b, a) or linked(i, j):
                continue
            if min(a[3], b[3]) - max(a[1], b[1]) > 0 and min(a[4], b[4]) - max(a[2], b[2]) > 0:
                dy = math.ceil((a[4] + UNIT - b[2]) / UNIT)
                said.append(f"{where}: {a[0]} ({a[1]:g},{a[2]:g})-({a[3]:g},{a[4]:g}) overlaps {b[0]} "
                            f"({b[1]:g},{b[2]:g})-({b[3]:g},{b[4]:g}). Move {b[0]} down {dy} units: dy={dy} on its "
                            f"anchor(), row() or hud_text() call, on top of any dy it has, puts its top one unit under "
                            f"{a[0]}. Or size a label to its text with hud_text(), space repeated items with row(), "
                            f"or hold one of them to another edge.")
    if said:
        sys.exit("\n".join(said))


def pace(beats: list) -> list[str]:
    """Stops the run on a BEATS curve that breaks a pacing rule; else returns it, one line a beat.
    Rules:
    - the first beat is at 0
    - a beat of 2 or more is followed by a rest that holds a pickup or a checkpoint, the climax
      by the exit
    - a mechanic gets a teach of its own before a beat combines it
    - one climax, in the last third
    - the last third averages above the first"""
    if not beats:
        sys.exit("BEATS is empty: give the game at least an intro, beat(\"intro\", 0)")
    names = [f"beat {i + 1} {b['type']}" for i, b in enumerate(beats)]
    for name, b in zip(names, beats):
        if b["type"] not in BEAT_TYPES or b["intensity"] not in (0, 1, 2, 3):
            sys.exit(f"BEATS: {name} at {b['intensity']!r}; a beat is one of {', '.join(BEAT_TYPES)} at an "
                     f"intensity of 0, 1, 2 or 3")
    if beats[0]["intensity"]:
        sys.exit(f"BEATS: {names[0]} is at {beats[0]['intensity']}; the first beat is at 0, its entry safe and the "
                 f"goal or its direction in view")
    taught: set = set()
    for i, (name, b) in enumerate(zip(names, beats)):
        if b["type"] == "rest" and b["holds"] not in ("pickup", "checkpoint"):
            sys.exit(f"BEATS: {name} holds {b['holds'] or 'nothing'}; a rest holds a pickup or a checkpoint, "
                     f"holds=\"pickup\" or holds=\"checkpoint\"")
        if b["type"] == "teach" and len(b["mechanics"]) == 1:
            taught.update(b["mechanics"])
        untaught = [m for m in b["mechanics"] if m not in taught] if len(b["mechanics"]) > 1 else []
        if untaught:
            sys.exit(f"BEATS: {name} combines {', '.join(b['mechanics'])}, but {', '.join(untaught)} has had no "
                     f"teach of its own; put beat(\"teach\", 1, [{untaught[0]!r}]) before it")
        if b["intensity"] >= 2:
            after = beats[i + 1]["type"] if i + 1 < len(beats) else None
            if after != "rest" and not (b["type"] == "climax" and after == "exit"):
                sys.exit(f"BEATS: {name} at {b['intensity']} is followed by {after or 'nothing'}; a beat of 2 or "
                         f"more is followed by a rest that holds a pickup or a checkpoint, the climax by a rest or "
                         f"the exit, so the player breathes before the next ask")
    k = max(1, round(len(beats) / 3))
    climaxes = [i for i, b in enumerate(beats) if b["type"] == "climax"]
    if len(climaxes) != 1 or climaxes[0] < len(beats) - k:
        where = ", ".join(names[i] for i in climaxes) or "none"
        sys.exit(f"BEATS: the climax is {where}; a game has one climax, in its last third, beats "
                 f"{len(beats) - k + 1} to {len(beats)} here")
    first = sum(b["intensity"] for b in beats[:k]) / k
    last = sum(b["intensity"] for b in beats[-k:]) / k
    if last <= first:
        sys.exit(f"BEATS: the last third averages {last:g} and the first {first:g}; the game rises towards its end, "
                 f"so raise a late beat or lower an early one")
    return [f"{name:<18} {b['intensity']} |{'#' * b['intensity']:<3}| {', '.join(b['mechanics'])}"
            + (f"; holds a {b['holds']}" if b["holds"] else "") for name, b in zip(names, beats)]


def jump_reach(rise: float = 0, platform: dict | None = None) -> float:
    """Reach in px of a full-speed jump with `platform` (PLATFORM by default) that lands `rise` px
    higher, lower when negative; 0 when it cannot rise that high.
    Leaves out acceleration, max fall speed and frame steps: confirm a reach in a preview."""
    p = (platform or PLATFORM)["Platform"]["properties"]
    v, g, s = p["jump-strength"], p["gravity"], p["jump-sustain"] / 1000
    height = v * s + v * v / (2 * g)
    if rise > height:
        return 0
    return p["max-speed"] * (s + v / g + math.sqrt(2 * (height - rise) / g))


def jump(gap: float, rise: float = 0, platform: dict | None = None) -> str:
    """Difficulty of a gap of `gap` units that lands `rise` units higher: "easy" up to half the
    player's reach, "hard" from 0.8 of it, "medium" between. Stops the run past 0.9, where
    jump_reach() leaves no margin. Check every gap where build_layouts() places it."""
    reach = jump_reach(units(rise), platform) / UNIT
    if not reach or gap > 0.9 * reach:
        sys.exit(f"a gap of {gap:g} units rising {rise:g} is past the player's reach of {reach:.1f} units at that "
                 f"rise; keep a gap to {math.floor(0.9 * reach)} units at most, or raise the Platform's max speed "
                 f"or jump strength in PLATFORM")
    return "easy" if gap <= reach / 2 else "hard" if gap >= 0.8 * reach else "medium"


# --- ids ----------------------------------------------------------------------
_used_sids: set[int] = set()
_used_images: set[int] = set()
_next_uid = 0


def sid() -> int:
    """15-digit id, unique across the project, in the editor's range."""
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
    """Tab indent, LF, raw UTF-8, no trailing newline, whole floats as ints: byte for byte
    what the editor saves."""
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(shortest(obj), indent="\t", ensure_ascii=False))


def shortest(obj):
    """Numbers in the shortest form the editor writes them in: 284.0 as 284, -0.0 as 0."""
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    if isinstance(obj, dict):
        return {k: shortest(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shortest(v) for v in obj]
    return obj


# --- project files ----------------------------------------------------------------------
# A table of records (cards, enemies, levels, loot) is a data file, not events: a Dictionary or
# Array file under files/, loaded once at start. build_files() writes them.
_general_files: list[dict] = []
_ajax_used = False


def general_file(name: str, text: str) -> str:
    """Writes files/<name> and lists it in Files; returns the name for request_project_file()."""
    path = ROOT / "files" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    kind = "application/json" if name.endswith(".json") else "text/plain"
    global _general_files
    _general_files = [e for e in _general_files if e["name"] != name]
    _general_files.append({"name": name, "type": kind, "sid": sid(), "file-info": {"purpose": "none"}})
    return name


def dictionary_file(name: str, data: dict) -> str:
    """files/<name>.json in a Dictionary's format: a few named numbers or strings, such as
    settings {"startGold": 60, "handSize": 5}. Load it with load_data_file(). For a table of
    records, use record_table()."""
    for key, value in data.items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float, str)):
            sys.exit(f"dictionary_file({name!r}): {key!r}: {value!r} is not a number or a string; a Dictionary "
                     f"holds those only. A record with fields is a row of record_table()")
    return general_file(f"{name}.json", json.dumps({"c2dictionary": True, "data": shortest(data)}, indent=4,
                                                   ensure_ascii=False))


def array_file(name: str, table: list) -> str:
    """files/<name>.json in an Array's format: table[x][y] is Arr.At(x, y), a list of columns of
    equal length, numbers or strings. Load it with load_data_file(). For records, use
    record_table()."""
    height = len(table[0]) if table else 0
    for x, column in enumerate(table):
        if len(column) != height:
            sys.exit(f"array_file({name!r}): column {x} has {len(column)} cells, column 0 has {height}; pad it")
        for y, value in enumerate(column):
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                sys.exit(f"array_file({name!r}): at ({x}, {y}) {value!r} is not a number or a string")
    return general_file(f"{name}.json", json.dumps(
        {"c2array": True, "size": [len(table), height, 1], "data": [[[v] for v in column] for column in shortest(table)]},
        indent=4, ensure_ascii=False))


def record_table(name: str, records: dict, fields: list | None = None) -> str:
    """files/<name>.json as an Array of records: a row (Y) per record and a column (X) per
    field, so the editor's Array editor shows a table. Row 0 holds "id" and the field names,
    column 0 the ids:
        record_table("Cards", {"strike": {"name": "Strike", "cost": 1, "dmg": 6},
                               "guard": {"name": "Guard", "cost": 1, "block": 5}})
    A missing field is 0, or "" for a text field. fields= fixes the columns and their order; a
    field outside it stops the run. Without fields=, a field that one record has and that is
    spelt like another prints a warning, because a misspelt key reads 0 in the game.
    Load it with load_data_file(), then table_to_dictionary(), and read Cards.Get("strike.dmg")."""
    where = f"record_table({name!r})"
    for rid, r in records.items():
        for f in r if fields else ():
            if f not in fields:
                near = difflib.get_close_matches(f, fields, n=1)
                sys.exit(f"{where}: record {rid!r} has the field {f!r}, which fields= does not list. The table "
                         f"would leave its value out. Write it as one of {', '.join(map(repr, fields))}"
                         + (f" (the nearest is {near[0]!r})" if near else "") + ", or add it to fields=")
    texts = {f for r in records.values() for f, v in r.items() if isinstance(v, str)}
    if not fields:
        fields = list(dict.fromkeys(f for r in records.values() for f in r))
        held = {f: [rid for rid, r in records.items() if f in r] for f in fields}
        for f in (f for f in fields if len(held[f]) == 1):
            rid = held[f][0]
            near = difflib.get_close_matches(f, [g for g in fields if g not in records[rid]], n=1, cutoff=0.8)
            if near:
                g = near[0]
                print(f"warning: {where}: only record {rid!r} has the field {f!r}, and {len(held[g])} "
                      f"record{'s have' if len(held[g]) > 1 else ' has'} {g!r}; if they are one field, write {g!r} "
                      f"in {rid!r}. Otherwise {g!r} reads {'""' if g in texts else 0} for {rid!r}")
    rows = [["id", *fields]] + [[rid, *(r.get(f, "" if f in texts else 0) for f in fields)]
                                for rid, r in records.items()]
    return array_file(name, [list(column) for column in zip(*rows)])


def table_to_dictionary(table: str, dictionary: str) -> list:
    """The sub-event, with its comment, that copies a record_table() Array into a Dictionary, one
    key "<id>.<field>" per cell. Put it among the sub-events of the On start that runs
    load_data_file(): children=[*table_to_dictionary(...), ...].
    The wait of load_data_file() delays the sub-events too."""
    cell = f'{table}.At(loopindex("field"), loopindex("row"))'
    key = f'{table}.At(0, loopindex("row")) & "." & {table}.At(loopindex("field"), 0)'
    return event(f"Copy each record of {table} into {dictionary}, one key per field",
                 [for_loop("row", "1", f"{table}.Height - 1"), for_loop("field", "1", f"{table}.Width - 1")],
                 [act("add-key", dictionary, {"key": key, "value": cell})])


def q(s: str) -> str:
    """q("tag") is the string literal "tag", quotes included, for an expression parameter; a quote
    inside is doubled."""
    return '"' + s.replace('"', '""') + '"'


# Comparison operators: =, ≠, <, ≤, >, ≥
EQ, NE, LT, LE, GT, GE = 0, 1, 2, 3, 4, 5


# --- images ----------------------------------------------------------------------
# Stand-in images, each a PNG drawn from an RGBA function. The game's art comes from the
# session's image tool through art() and the skill's scripts/prepare_art.py, or from the user.
# Do not draw the game's art in code: it looks worse than the stand-ins and mixes styles.
def rgb(role: str) -> tuple[int, int, int]:
    """The colour of a role of PALETTE: rgb("danger")."""
    if role not in PALETTE:
        sys.exit(f"{role!r} is no role of PALETTE, which has {', '.join(PALETTE)}; "
                 f"add the colour to PALETTE under the role it plays")
    return PALETTE[role]


def rgba(colour: tuple, alpha: float = 1) -> list:
    """An RGB colour as a layout writes one: channels from 0 to 1, whole ones as integers."""
    return [c // 255 if c in (0, 255) else c / 255 for c in colour] + [alpha]


def accent(role: str) -> bool:
    """Whether a role of PALETTE is a hue, not a grey: an accent, which shows by its outline."""
    c = rgb(role)
    return max(c) - min(c) > 32


def check_palette() -> None:
    """Stops the run when PALETTE's greys lose their contrast: canvas and canvas_alt at most 1.2:1,
    so the checker reads as texture; solid at least 3:1 on canvas_alt, so structure shows without
    an outline."""
    ratio = contrast(rgb("canvas"), rgb("canvas_alt"))
    if ratio > 1.2:
        sys.exit(f"PALETTE: canvas {PALETTE['canvas']} and canvas_alt {PALETTE['canvas_alt']} are {ratio:.2f}:1; the "
                 f"backdrop's two greys stay at most 1.2:1, so the checker reads as texture, not as things. Bring "
                 f"canvas_alt nearer canvas")
    ratio = contrast(rgb("solid"), rgb("canvas_alt"))
    if ratio < 3:
        sys.exit(f"PALETTE: solid {PALETTE['solid']} on canvas_alt {PALETTE['canvas_alt']} reads {ratio:.2f}:1; "
                 f"structure needs 3:1 on the backdrop to show without an outline. Darken solid")


def alphas() -> set[int]:
    """The alpha values a drawn image may hold: clear, opaque, and the shadow of SHAPE_STYLE."""
    return {0, 255, round(255 * SHAPE_STYLE["shadow_opacity"])}


def write_png(rel: str, w: int, h: int, pixel, painted: bool = False) -> None:
    """images/<rel> from an RGBA function of (x, y). Every visible pixel is a PALETTE colour with
    an alpha of alphas(); painted=True skips both checks, for a picture with its own colours and
    soft edges.
    A clear pixel is written as (0, 0, 0, 0): a colour under alpha 0 bleeds into the edge under
    linear sampling."""
    raw = bytearray()
    colours = set(PALETTE.values())
    allowed = alphas()
    stray: dict = {}
    for y in range(h):
        raw.append(0)
        for x in range(w):
            px = tuple(pixel(x, y))
            if not px[3]:
                px = (0, 0, 0, 0)
            elif not painted and px[3] not in allowed:
                sys.exit(f"images/{rel}: alpha {px[3]} at ({x},{y}); a drawn image is clear, opaque or the shadow's "
                         f"{round(255 * SHAPE_STYLE['shadow_opacity'])}, so its edges stay hard. A picture meant "
                         f"to hold soft edges is write_png(..., painted=True)")
            elif not painted and px[:3] not in colours:
                stray.setdefault(px[:3], (x, y))
            raw.extend(px)
    if stray:
        first, (x, y) = next(iter(stray.items()))
        near = min(PALETTE, key=lambda k: sum((a - b) ** 2 for a, b in zip(PALETTE[k], first)))
        others = f", nor are {len(stray) - 1} more of its colours" if len(stray) > 1 else ""
        sys.exit(f"images/{rel}: {first} at ({x},{y}) is no colour of PALETTE{others}; the nearest is "
                 f"{near} {PALETTE[near]}. Draw with rgb({near!r}), or add the colour to PALETTE under the "
                 f"role it plays; a picture meant to hold its own colours, a gradient or a photograph, is "
                 f"write_png(..., painted=True)")

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path = ROOT / "images" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def bar_images(frame_name: str, fill_name: str, frame_role: str = "solid", fill_role: str = "ink",
               caps: bool = False) -> None:
    """The 16x16 images of bar_types(), one PALETTE role each; `caps` adds a 2 px ink border, which
    a 9-patch keeps at any length. For a painted fill, write its image with painted=True instead."""
    for name, role in ((frame_name, frame_role), (fill_name, fill_role)):
        def pixel(x, y, role=role):
            edge = caps and (x < 2 or y < 2 or x >= 14 or y >= 14)
            return (*rgb("ink" if edge else role), 255)

        write_png(f"{name.lower()}.png", 16, 16, pixel)


SHAPES = ("rect", "circle", "triangle")
FRAMES: dict[str, dict] = {}               # frame of each drawn image, by file name
PADS: dict[str, tuple[int, int]] = {}      # where the shape starts inside its image, past the shadow
DRAWN_AS: dict[str, tuple] = {}            # arguments each image was drawn with, for hit_frame()
FILLS: dict[str, str] = {}                 # fill role of each image, for a label on it


def shadow_offset() -> tuple[int, int]:
    """The (dx, dy) in px of SHAPE_STYLE's shadow from its shape."""
    angle = math.radians(SHAPE_STYLE["shadow_angle"])
    d = SHAPE_STYLE["shadow_distance"]
    return round(d * math.cos(angle)), round(d * math.sin(angle))


def inside(kind: str, w: float, h: float, x: float, y: float, inset: float = 0) -> bool:
    """Whether (x, y) lies in a w x h shape at least `inset` px from its edge: a rectangle,
    the ellipse it holds, or the triangle standing on its bottom edge."""
    if kind == "rect":
        return min(x, w - x, y, h - y) >= inset
    if kind == "circle":
        rx, ry = w / 2 - inset, h / 2 - inset
        return rx > 0 and ry > 0 and ((x - w / 2) / rx) ** 2 + ((y - h / 2) / ry) ** 2 <= 1
    corners = ((w / 2, 0), (w, h), (0, h))
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        if ((bx - ax) * (y - ay) - (by - ay) * (x - ax)) / math.hypot(bx - ax, by - ay) < inset:
            return False
    return True


def corners(kind: str) -> list[tuple[float, float]]:
    """The collision polygon of a kind of SHAPES across its box, from 0 to 1."""
    return {"rect": [(0, 0), (1, 0), (1, 1), (0, 1)], "triangle": [(0.5, 0), (1, 1), (0, 1)],
            "circle": [(0.5 + math.cos(a) / 2, 0.5 + math.sin(a) / 2)
                       for a in (i * math.pi / 8 for i in range(16))]}[kind]


def shape(rel: str, kind: str, w: int, h: int, role: str, ox: float = 0.5, oy: float = 0.5,
          outline: bool | None = None, shadow: bool | None = None) -> dict:
    """images/<rel>: a flat `kind` of SHAPES, w x h px in whole units, in the colour of `role`,
    with SHAPE_STYLE's outline and shadow unless `outline` or `shadow` says otherwise. Returns
    its frame, also kept in FRAMES[rel]: origin (ox, oy) of the shape, the shape's collision
    polygon, and the image's size with the shadow, which is the instance's size."""
    if kind not in SHAPES:
        sys.exit(f"{rel}: {kind!r} is no shape; shape() draws {', '.join(SHAPES)}")
    if w % UNIT or h % UNIT:
        sys.exit(f"{rel}: {w}x{h} is not whole units of {UNIT} px; a shape covers whole cells of the grid, "
                 f"so give it units(n) or TOUCH, {math.ceil(w / UNIT) * UNIT}x{math.ceil(h / UNIT) * UNIT} here")
    style = SHAPE_STYLE
    edge = style["outline_width"] if (style["outline"] if outline is None else outline) else 0
    ratio = contrast(rgb(role), rgb("canvas_alt"))
    if not edge and accent(role) and ratio < 3:
        sys.exit(f"{rel}: {role} {PALETTE[role]} reads {ratio:.2f}:1 on canvas_alt, and an accent without an outline "
                 f"needs 3:1 to show; darken {role}, or draw it with its outline")
    ratio = contrast(rgb(role), rgb(style["outline_role"]))
    if edge and role != style["outline_role"] and ratio < 3:
        fits = [r for r in PALETTE if contrast(PALETTE[r], rgb(style["outline_role"])) >= 3]
        sys.exit(f"{rel}: its {role} fill reads {ratio:.1f}:1 against its {style['outline_role']} outline, which needs "
                 f"3:1 to show; fill it in one of {', '.join(fits)}")
    dx, dy = shadow_offset() if (style["shadow"] if shadow is None else shadow) else (0, 0)
    left, top = max(0, -dx), max(0, -dy)
    iw, ih = w + abs(dx), h + abs(dy)
    alpha = round(255 * style["shadow_opacity"])

    def pixel(x, y):
        px, py = x + 0.5 - left, y + 0.5 - top
        if inside(kind, w, h, px, py):
            return (*rgb(role if inside(kind, w, h, px, py, edge) else style["outline_role"]), 255)
        if (dx or dy) and inside(kind, w, h, px - dx, py - dy):
            return (*rgb(style["shadow_role"]), alpha)
        return (0, 0, 0, 0)

    write_png(rel, iw, ih, pixel)
    poly = [round(v, 4) for cx, cy in corners(kind) for v in ((left + cx * w) / iw, (top + cy * h) / ih)]
    FRAMES[rel] = frame(iw, ih, (left + ox * w) / iw, (top + oy * h) / ih, poly)
    PADS[rel] = (left, top)
    DRAWN_AS[rel] = (kind, w, h, ox, oy, outline, shadow)
    FILLS[rel] = role
    return FRAMES[rel]


def hit_frame(rel: str) -> dict:
    """The hit frame of images/<rel>, "coin-default-000.png", drawn by shape() or art(): the
    shape filled in HIT_FLASH's role, or the picture's silhouette in it, written as the next
    frame and tagged "hit". Put it after the first frame of the animation; hit_flash() shows it."""
    if rel not in DRAWN_AS or not rel.endswith("-000.png"):
        sys.exit(f"hit_frame({rel!r}): draw the frame first with shape({rel!r}, ...) or art({rel!r}, ...), named "
                 f"<type>-<animation>-000.png")
    hit = rel[:-len("000.png")] + "001.png"
    if DRAWN_AS[rel][0] == "art":
        # Silhouette in the flash colour, written by prepare_art.py
        source = ROOT / "art" / (rel[:-len(".png")] + ".hit.png")
        if not source.exists():
            sys.exit(f"art/{source.name} is missing: run the skill's scripts/prepare_art.py, which writes each "
                     f"picture's hit frame beside it")
        (ROOT / "images" / hit).write_bytes(source.read_bytes())
        FRAMES[hit] = {**FRAMES[rel], "imageSpriteId": image_id(), "tag": "hit"}
        return FRAMES[hit]
    kind, w, h, ox, oy, outline, shadow = DRAWN_AS[rel]
    f = shape(hit, kind, w, h, HIT_FLASH["role"], ox, oy, True, shadow)
    f["tag"] = "hit"
    return f


def drawn(rel: str) -> dict:
    """The frame shape() or art() drew as images/<rel>: sprite_type() takes it, and an instance
    of it is drawn(rel)["width"] x drawn(rel)["height"]."""
    if rel not in FRAMES:
        sys.exit(f"images/{rel} was not drawn: draw it with art({rel!r}, ...) or shape({rel!r}, ...) in "
                 f"build_images(), which runs before build_object_types()")
    return FRAMES[rel]


# --- art -------------------------------------------------------------------------------
# art() asks for a picture of `subject` and shows the stand-in shape() until the picture is in
# art/. The skill's scripts/prepare_art.py --list prints a prompt per picture; without --list it
# cuts each picture out and fits it to its box. The picture keeps the stand-in's box, origin and
# collision polygon, so layouts and events stay as they are.
ART: dict[str, dict] = {}                  # what art() asked for, by file name: art/wanted.json


def art(rel: str, kind: str, w: int, h: int, role: str, subject: str, ox: float = 0.5, oy: float = 0.5,
        outline: bool | None = None, shadow: bool | None = None) -> dict:
    """images/<rel>: the picture art/<rel> when it is there, else the stand-in
    shape(rel, kind, w, h, role, ...). `subject` says what the picture shows, for its prompt:
    "a gold coin seen from the front". Kind "scene" is an opaque picture that fills its box, such
    as a backdrop, with a flat rectangle of `role` as its stand-in. Returns the frame."""
    scene = kind == "scene"
    if kind not in SHAPES and not scene:
        sys.exit(f"art({rel!r}): {kind!r} is no kind; art() takes {', '.join(SHAPES)} or scene")
    if not subject.strip():
        sys.exit(f"art({rel!r}): say what the picture shows, the words its prompt is made of: art({rel!r}, "
                 f"{kind!r}, {w}, {h}, {role!r}, \"a gold coin seen from the front\")")
    ART[rel] = {"file": rel, "kind": kind, "width": w, "height": h, "origin": [ox, oy], "subject": subject}
    picture = ROOT / "art" / rel
    if not picture.exists():
        if scene:
            return shape(rel, "rect", w, h, role, ox, oy, outline=False, shadow=False)
        return shape(rel, kind, w, h, role, ox, oy, outline, shadow)
    if w % UNIT or h % UNIT:
        sys.exit(f"art({rel!r}): {w}x{h} is not whole units of {UNIT} px; give it units(n) or TOUCH, "
                 f"{math.ceil(w / UNIT) * UNIT}x{math.ceil(h / UNIT) * UNIT} here, then run prepare_art.py again")
    data = picture.read_bytes()
    size = struct.unpack(">II", data[16:24]) if data[:8] == b"\x89PNG\r\n\x1a\n" else None
    if size != (w, h):
        sys.exit(f"art/{rel} is {'not a PNG' if size is None else '%dx%d' % size}, and art() asks {w}x{h}: put the "
                 f"picture in art/raw/ and run the skill's scripts/prepare_art.py, which fits it to its box, or "
                 f"delete art/{rel} to show the stand-in")
    target = ROOT / "images" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    poly = [round(v, 4) for point in corners("rect" if scene else kind) for v in point]
    FRAMES[rel] = frame(w, h, ox, oy, poly)
    PADS[rel] = (0, 0)
    DRAWN_AS[rel] = ("art", w, h)
    FILLS[rel] = role
    return FRAMES[rel]


def write_wanted() -> None:
    """Writes art/wanted.json for the skill's scripts/prepare_art.py and prints how many sprites
    still show their stand-in."""
    if not ART:
        return
    write_json("art/wanted.json", {"style": ART_STYLE, "flash": list(rgb(HIT_FLASH["role"])),
                                   "pixel_art": PIXEL_ART, "images": list(ART.values())})
    waiting = [rel for rel in ART if not (ROOT / "art" / rel).exists()]
    if waiting:
        print(f"art: {len(waiting)} of {len(ART)} images show their stand-in ({', '.join(waiting[:3])}"
              f"{' ...' if len(waiting) > 3 else ''}); with an image tool in this session, run the skill's "
              f"scripts/prepare_art.py --list for their prompts")
    else:
        print(f"art: all {len(ART)} images from art/")


# Patterns of areas and edges, Tiled Backgrounds that repeat at any size: two PALETTE roles and
# one job each. A red triangle is one hazard, a red-striped area a hazardous region.
PATTERNS = {
    "plain": ("canvas", "canvas"),         # the sheet; backdrop only
    "checker": ("canvas", "canvas_alt"),   # transparency, a mask, a background to come; backdrop only
    "low": ("solid", "dim"),               # a harmless special surface: a one-way platform, a safe zone
    "caution": ("reward", "ink"),          # what moves, triggers or blocks on a condition: a door, a plate
    "hazard": ("danger", "ink"),           # an area that hurts: lava, a kill zone
}
BACKDROPS = ("plain", "checker")           # patterns of backdrop() only
PATTERN_OF: dict[str, str] = {}            # pattern of each type pattern() drew, by type name
TILES: dict[str, int] = {}                 # tile size in px, which tiledbg_inst() aligns to the layout


def pattern(name: str, kind: str) -> None:
    """images/<name lower>.png: a one-unit tile of the pattern `kind` for the Tiled Background type
    `name`. The checker has two cells to a unit, so the backdrop counts units; the stripes run at
    45 degrees and join across tiles."""
    if kind not in PATTERNS:
        sys.exit(f"pattern({name!r}, {kind!r}): the patterns are {', '.join(PATTERNS)}")
    a, b = PATTERNS[kind]
    half = UNIT // 2
    if kind in BACKDROPS:
        def pixel(x, y):
            return (*rgb(a if (x // half + y // half) % 2 == 0 else b), 255)
    else:
        def pixel(x, y):
            return (*rgb(a if (x + y) % UNIT < half else b), 255)
    write_png(f"{name.lower()}.png", UNIT, UNIT, pixel)
    PATTERN_OF[name], TILES[name] = kind, UNIT


# --- event sheet: conditions, actions, blocks ------------------------------------------
# Ids and parameter keys are the schema's; the skill's scripts/lookup_ace.py prints them
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
    """A call of a custom action on the picked instances of obj. `family` names the family that
    declares the action when obj is a member that does not."""
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
    """A top-level block under a one-sentence comment: what it does, or which case it is."""
    return [comment(text), block(conds, acts, children, or_block)]


def procedure(text: str, proc: dict) -> list:
    """A function or custom action with the comment above it; its description is the same sentence."""
    if not proc.get("functionDescription"):
        proc["functionDescription"] = text
    return [comment(text), proc]


def module(title: str, events: list, variables: list | None = None, procedures: list | None = None,
           active: bool = True) -> dict:
    """A group: the variables only it reads (a constant with the group's prefix, a static local
    for state that outlives the tick), then its functions and custom actions, then its events.
    Entries may be rows or the row pairs of event() and procedure()."""
    return group(title, list(variables or []) + flat(procedures or []) + flat(events), active=active)


def steps(*batches: tuple) -> list:
    """A long block's actions in labelled batches of three to five: each (label, actions) becomes
    a comment action and its actions. Eight actions in a row without a label is a style warning."""
    out: list = []
    for label, acts in batches:
        out.append({"type": "comment", "text": label})
        out.extend(acts)
    return out


def cases(gate: list, branches: list, acts: list | None = None) -> dict:
    """A decision: one event with the shared conditions, then each case (text, conds, acts) as a
    flat sub-event under its comment. conds None is the Else of the case before it; a list that
    starts with else_() is an else-if. Use it in place of a tree with one call at each leaf."""
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
    """Picks only the new instance. Give every runtime-created type a template instance in a layout
    that never runs, because without one its behavior properties read 0."""
    return act("create-object", "System", {"object-to-create": obj, "layer": q(layer), "x": x, "y": y,
                                           "create-hierarchy": False, "template-name": q("")})


def hit_flash(obj: str) -> list:
    """Actions that show obj's hit frame for HIT_FLASH["seconds"] of real time, then frame 0.
    Put them last in a block: actions after a wait run once it ends."""
    return [act("set-animation-frame", obj, {"frame-number": q("hit")}),
            wait(str(HIT_FLASH["seconds"]), use_timescale=False),
            act("set-animation-frame", obj, {"frame-number": "0"})]


SQUASHED: set[str] = set()                 # objects squash() acts on, checked in build_all()
# Behaviors whose object collides, by behaviorId; squash() stops the run on one
COLLIDING = ("Platform", "EightDir", "Physics", "Car", "solid", "jumpthru")
# Squash of a button under a finger, press(); a game tunes it as SQUASH["press"]
SQUASH_PRESS = {"width": 0.9, "height": 0.9, "hold": 0, "seconds": 0.1, "ease": "easeoutsine"}


def squash(obj: str, kind: str, tween: str = "Tween", half: str = "both") -> list:
    """Actions of a squash of SQUASH ("hit", "land", "jump" or "press") on obj: stop its running
    squash, set its size to the kind's share of its image size, hold, and tween back under the tag
    "squash". obj is the art, not the object that collides, and has the Tween behavior `tween`.
    The tween ends at the image's size, the size shape_inst() places obj at.
    The hold waits, so put the actions last in their block.
    half="down" gives the actions up to the hold, "back" the tween back; press() uses both halves.

        event("Squash the art on landing", [cond("on-landed", "Player", beh="Platform")],
              squash("PlayerArt", "land"))"""
    kinds = {**SQUASH, "press": SQUASH.get("press", SQUASH_PRESS)}
    if kind not in kinds:
        sys.exit(f"squash({obj!r}, {kind!r}): the kinds are {', '.join(kinds)}; add one to SQUASH")
    if half not in ("both", "down", "back"):
        sys.exit(f"squash({obj!r}, {kind!r}, half={half!r}): half is both, down or back")
    k = kinds[kind]
    SQUASHED.add(obj)
    down = [act("stop-tweens", obj, {"tags": q("squash")}, beh=tween),
            act("set-size", obj, {"width": f"Self.ImageWidth * {k['width']:g}",
                                  "height": f"Self.ImageHeight * {k['height']:g}"}),
            *([wait(f"{k['hold']:g}", use_timescale=False)] if k["hold"] else [])]
    back = [tween2(obj, "squash", "size", "Self.ImageWidth", "Self.ImageHeight", f"{k['seconds']:g}", k["ease"],
                   beh=tween)]
    return {"both": down + back, "down": down, "back": back}[half]


def squash_the_art(types: dict, families: dict) -> None:
    """Stops the run when squash() acts on an object that collides: its box grows into the floor."""
    for obj in sorted(SQUASHED):
        item = types.get(obj) or families.get(obj) or {}
        hits = [b["behaviorId"] for b in item.get("behaviorTypes", []) if b["behaviorId"] in COLLIDING]
        if hits:
            sys.exit(f"squash({obj!r}): {obj} has {', '.join(hits)} and collides, so a squash moves its collision "
                     f"box; squash its art instead, a second object drawn with shape(..., oy=1) and pinned to "
                     f"{obj} with add_child(), and keep {obj} invisible")


def hit(obj: str, tween: str = "Tween") -> list:
    """Actions of a hit: SQUASH["hit"], then the flash. The flash waits, so put them last in a block."""
    return [*squash(obj, "hit", tween), *hit_flash(obj)]


PRESSED: set[str] = set()                  # types press() acts on; build_all() gives them "pressed"


def press(obj: str, actions: list, tween: str = "Tween") -> list:
    """The two events of a press on obj, a button()'s shape with Tween. The touch that lands on
    it marks it pressed and squashes it; the touch's end springs it back and runs `actions` only
    if the touch ends on it, so a finger that slides off cancels.
        module("Menu", events=[*press("Restart", [restart_layout()])])"""
    PRESSED.add(obj)
    return [*event(f"Press {obj} down under the finger", [on_touched(obj)],
                   [set_bool(obj, "pressed", True), *squash(obj, "press", tween, "down")]),
            *event(f"Let {obj} spring back when the touch ends, and act when it ends on it",
                   [cond("on-any-touch-end", "Touch"), is_bool(obj, "pressed")],
                   [set_bool(obj, "pressed", False), *squash(obj, "press", tween, "back")],
                   children=[block([cond("is-touching-object", "Touch", {"object": obj})], actions)])]


def press_types(types: dict, layouts: dict) -> None:
    """Gives each type press() acts on the boolean instance variable "pressed", false on every
    instance, because an instance lists every instance variable of its type."""
    for name in sorted(PRESSED & set(types)):
        ivars = types[name].setdefault("instanceVariables", [])
        if not any(v["name"] == "pressed" for v in ivars):
            ivars.append(ivar_def("pressed", "boolean", "Held down by a finger: press() sets it on the touch's "
                                                        "start and clears it on its end."))
    for lay in layouts.values():
        for layer_ in layers_in(lay["layers"]):
            for inst in layer_["instances"]:
                if inst["type"] in PRESSED:
                    inst["instanceVariables"].setdefault("pressed", False)


# Duration and ease of count_up()
COUNT_UP = {"seconds": 0.5, "ease": "easeoutquad"}


def count_up(obj: str, value: str, tag: str = "count", tween: str = "Tween") -> list:
    """Actions that count the Text obj, which shows a number alone, to the expression `value`. A
    value tween under `tag` starts from the number shown, so a gain mid-count goes on from the
    screen. obj has the Tween behavior `tween`; the events of counting() show the count.
    The running count stops first, because a second tween under one tag runs beside it.
        func("AddScore", [add_var("score", "points"), *count_up("ScoreText", "score")], ...)"""
    return [stop_tweens(obj, tag, beh=tween),
            tween_value(obj, tag, f"int({obj}.Text)", value, f"{COUNT_UP['seconds']:g}", COUNT_UP["ease"], beh=tween)]


def counting(obj: str, value: str, tag: str = "count", tween: str = "Tween") -> list:
    """The two events that show count_up()'s count on obj: during it, the tween's value rounded
    towards `value`, so a gain of 1 shows at once; at its end, `value`, because the tween's value
    reads 0 once the tween has ended."""
    v = f"Self.{tween}.Value({q(tag)})"
    return [*event(f"Show {obj}'s count while it runs", [is_playing(obj, tag, beh=tween)],
                   [set_text(obj, f"{v} < {value} ? ceil({v}) : floor({v})")]),
            *event(f"End {obj}'s count on the exact value", [on_tween_finished(obj, tag, beh=tween)],
                   [set_text(obj, value)])]


def grid_random(lo: int, hi: int) -> str:
    """Expression for a random grid position from lo to hi px, for an object created at runtime."""
    return f"{UNIT} * floor(random({lo // UNIT}, {hi // UNIT + 1}))"


def wait(seconds: str, use_timescale: bool = True) -> dict:
    return act("wait", "System", {"seconds": seconds, "use-timescale": use_timescale})


def wait_for_previous() -> dict:
    return act("wait-for-previous-actions", "System")


def request_project_file(file: str, tag: str) -> dict:
    """AJAX: Request a file of files/ by its bare name; adds the AJAX object to the project."""
    global _ajax_used
    _ajax_used = True
    return act("request-project-file", "AJAX", {"tag": q(tag), "file": file})


def load_json(obj: str, json_: str = "AJAX.LastData") -> dict:
    """Dictionary or Array: Load from JSON, by default what the last AJAX request returned."""
    return act("load", obj, {"json": json_})


def load_data_file(obj: str, file: str) -> list:
    """Three actions that load a dictionary_file() or array_file() into obj: request, wait, load.
    Put them first in On start of layout, with the actions that read obj after them: the wait
    ends the tick, and another event in that tick sees obj empty."""
    return [request_project_file(file, Path(file).stem), wait_for_previous(), load_json(obj)]


def restart_layout() -> dict:
    return act("restart-layout", "System")


def go_to_layout(name: str) -> dict:
    return act("go-to-layout", "System", {"layout": name})


def set_group_active(title: str, state: str = "activated") -> dict:
    return act("set-group-active", "System", {"group-name": q(title), "state": state})


# Shared by every world object
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


# Tween behavior; beh is the behavior's name on the object
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


def set_width(obj: str, width: str) -> dict:
    return act("set-width", obj, {"width": width})


def bar_width(value: str, maximum: str, length: float) -> str:
    """The width of a bar's fill: value over maximum of length, clamped, so the fill never
    grows past its frame: bar_width("hp", "HP_MAX", 380)."""
    return f"clamp({value} / {maximum}, 0, 1) * {length:g}"


def tween_width(obj: str, tag: str, width: str, time: str = "0.25", ease: str = "easeinoutsine", beh: str = "Tween") -> dict:
    """Slides a fill to a new width instead of jumping: tween_width("HpFill", "hp", bar_width("hp", "HP_MAX", 380))."""
    return tween1(obj, tag, "offsetWidth", width, time, ease, beh=beh)


def tween_value(obj: str, tag: str, start: str, end: str, time: str, ease: str = "easeinoutsine", beh: str = "Tween") -> dict:
    """A tween of a number, for what Tween has no property for. Read it as Obj.Tween.Value("tag")
    while it plays; it reads 0 after it ends."""
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


# Timer behavior
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


# --- object types --------------------------------------------------------------------
def frame(w: int, h: int, ox: float = 0.5, oy: float = 0.5, poly: list | None = None) -> dict:
    """poly: the collision polygon as x, y pairs from 0 to 1 across the image; the whole image
    unless given. An image of shape() has its frame from drawn()."""
    return {"width": w, "height": h, "originX": ox, "originY": oy, "originalSource": "",
            "exportFormat": "lossless", "exportQuality": 0.8, "fileType": "image/png", "imageSpriteId": image_id(),
            "collisionPoly": {"points": poly or [0, 0, 1, 0, 1, 1, 0, 1]}, "useCollisionPoly": True, "duration": 1,
            "tag": ""}


def animation(name: str, frames: list, speed: float = 0) -> dict:
    """speed 0 holds the frame for events to choose; above 0 the animation loops at that many frames a second."""
    return {"frames": frames, "sid": sid(), "name": name, "isLooping": speed > 0, "isPingPong": False,
            "repeatCount": 1, "repeatTo": 0, "speed": speed}


def ivar_def(name: str, vtype: str, desc: str = "") -> dict:
    return {"name": name, "type": vtype, "desc": desc, "show": True, "sid": sid()}


def beh_def(behavior_id: str, name: str | None = None) -> dict:
    """name is what events refer to; two Sine behaviors on one object need two names."""
    if behavior_id == "Flash":
        sys.exit(f"{name or behavior_id}: a hit shows as a colour, not the Flash behavior's blinking; draw the "
                 f"object's hit frame with hit_frame() and show it with hit_flash(obj) in the sheet")
    return {"behaviorId": behavior_id, "name": name or behavior_id, "sid": sid()}


def sprite_type(name: str, animations: list, ivars: list = (), behaviors: list = ()) -> dict:
    return {"name": name, "plugin-id": "Sprite", "sid": sid(), "isGlobal": False, "editorNewInstanceIsReplica": True,
            "instanceVariables": list(ivars), "behaviorTypes": list(behaviors), "effectTypes": [],
            "animations": {"items": animations, "subfolders": []}}


def text_type(name: str, ivars: list = (), behaviors: list = ()) -> dict:
    return {"name": name, "plugin-id": "Text", "sid": sid(), "isGlobal": False, "editorNewInstanceIsReplica": True,
            "instanceVariables": list(ivars), "behaviorTypes": list(behaviors), "effectTypes": []}


def image_type(name: str, plugin_id: str, w: int, h: int, ox: float = 0.5, oy: float = 0.5,
               ivars: list = (), behaviors: list = ()) -> dict:
    """A Tiled Background ("TiledBg") or 9-patch ("NinePatch") type: one image,
    images/<name lower>.png."""
    image = {"width": w, "height": h, "originX": ox, "originY": oy, "originalSource": "", "exportFormat": "lossless",
             "exportQuality": 0.8, "imageSpriteId": image_id(), "useCollisionPoly": True}
    if plugin_id == "TiledBg":
        image["tag"] = ""
    return {"name": name, "plugin-id": plugin_id, "sid": sid(), "isGlobal": False, "instanceVariables": list(ivars),
            "behaviorTypes": list(behaviors), "effectTypes": [], "image": image}


def bar_types(frame_name: str, fill_name: str, caps: bool = False, tween: bool = True) -> dict:
    """The frame and fill types of a hud_bar(): Tiled Backgrounds, whose Set width reveals the fill
    without stretching it, or with `caps` 9-patches, whose corners keep their size. Each has a 16x16
    image from bar_images(); the fill carries Tween for tween_width()."""
    plugin = "NinePatch" if caps else "TiledBg"
    return {frame_name: image_type(frame_name, plugin, 16, 16),
            fill_name: image_type(fill_name, plugin, 16, 16, 0, 0.5, behaviors=[beh_def("Tween")] if tween else [])}


def pattern_type(name: str) -> dict:
    """The Tiled Background type of the pattern pattern() drew for `name` in build_images();
    area() and backdrop() place it."""
    if name not in PATTERN_OF:
        sys.exit(f"pattern_type({name!r}): draw its tile first with pattern({name!r}, kind) in build_images()")
    return image_type(name, "TiledBg", TILES[name], TILES[name], 0, 0)


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
    """Object types whose instances are created, destroyed and picked together, a tank base with
    its turret: a row of project.c3proj's "containers", sorted as the editor sorts it. Members are
    object types, not families."""
    return {"members": sorted(members, key=str.lower)}


# --- layouts -------------------------------------------------------------------------------
def layer(name: str, bg: str | None = None, transparent: bool = True, parallax: float = 1) -> dict:
    """parallax 0 for a HUD layer that stays put while the layout scrolls. bg is the PALETTE role
    an opaque layer fills with, "canvas" by default. A transparent layer keeps the editor's white,
    which it never draws."""
    fill = rgb(bg or "canvas") if bg or not transparent else (255, 255, 255)
    return {"name": name, "overriden": 0, "subLayers": [], "instances": [], "sid": sid(), "effectTypes": [],
            "isInitiallyVisible": True, "isInitiallyInteractive": True, "isHTMLElementsLayer": False,
            "color": [1, 1, 1, 1], "backgroundColor": rgba(fill), "isTransparent": transparent,
            "sampling": "auto", "parallaxX": parallax, "parallaxY": parallax, "scaleRate": 1, "forceOwnTexture": False,
            "renderingMode": "3d", "drawOrder": "z-order", "useRenderCells": False, "blendMode": "normal",
            "zElevation": 0, "global": False}


def layout(name: str, layers: list, sheet: str | None, nonworld: list = (), width: int | None = None,
           height: int | None = None) -> dict:
    """A layout, the viewport's size unless width and height say otherwise.
    A one-screen layout scrolls unbounded: under Scale outer, bounded scrolling holds the layout's
    top-left corner to the screen's and slides the game off centre."""
    width, height = VIEW_W if width is None else width, VIEW_H if height is None else height
    return {"name": name, "layers": layers, "sid": sid(), "nonworld-instances": list(nonworld), "effectTypes": [],
            "width": width, "height": height,
            "unboundedScrolling": (width, height) == (VIEW_W, VIEW_H), "sampling": "auto", "ambientLight": 0.03,
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
            "instanceVariables": ivars or {}, "behaviors": behaviors or {}}
    if world_ is not None:
        inst["materialSurfaceType"] = "smooth"
    inst |= {"showing": True, "locked": False}
    if world_ is not None:
        inst["world"] = world_
    return inst


def nonworld_inst(otype: str, properties: dict | None = None) -> dict:
    """An Array, Dictionary or JSON instance, in layout(..., nonworld=[...]): properties {} for a
    Dictionary, {"width": 10, "height": 1, "depth": 1} for an Array."""
    return {"type": otype, "properties": properties or {}, "uid": uid(), "sid": sid(), "tags": "",
            "instanceVariables": {}}


def sprite_inst(otype: str, x: float, y: float, w: float, h: float, anim: str = "Default", ivars=None,
                behaviors=None, collisions: bool = True) -> dict:
    return instance(otype, {"initially-visible": True, "initial-animation": anim, "initial-frame": 0,
                            "enable-collisions": collisions, "live-preview": False},
                    world(x, y, w, h), ivars, behaviors)


def shape_inst(otype: str, rel: str, col: int, row: int, ivars=None, behaviors=None,
               collisions: bool = True) -> dict:
    """An instance of the shape images/<rel> with its top-left corner on grid cell (col, row), at
    the image's size and the frame's origin; the shadow hangs off the cells."""
    f, (left, top) = drawn(rel), PADS[rel]
    x = col * UNIT - left + f["originX"] * f["width"]
    y = row * UNIT - top + f["originY"] * f["height"]
    return instance(otype, {"initially-visible": True, "initial-animation": "Default", "initial-frame": 0,
                            "enable-collisions": collisions, "live-preview": False},
                    world(x, y, f["width"], f["height"], f["originX"], f["originY"]), ivars, behaviors)


def on_grid(instances: list, where: str) -> None:
    """Stops the run when an instance of a world layer starts off the grid: its box's left and
    top, or its shape's past a shadow, are whole UNITs. Skips a rotated instance. Do not pass the
    HUD, which anchor() holds to the edges."""
    dx, dy = shadow_offset()
    pads_x, pads_y = {0, max(0, -dx)}, {0, max(0, -dy)}

    def fits(v: float, pads: set) -> bool:
        return any(abs((v + p) / UNIT - round((v + p) / UNIT)) < 1e-6 for p in pads)

    for inst in instances:
        w = inst.get("world")
        if not w or w.get("angle"):
            continue
        left = w["x"] - w.get("originX", 0) * w["width"]
        top = w["y"] - w.get("originY", 0) * w["height"]
        if not (fits(left, pads_x) and fits(top, pads_y)):
            sys.exit(f"{where}: {inst['type']} starts at ({left:g},{top:g}), off the {UNIT} px grid. Place a shape "
                     f"with shape_inst(type, image, col, row), which puts its corner on cell (col, row), and "
                     f"anything else with units() or snap()")


def contrast(a: tuple, b: tuple) -> float:
    """WCAG contrast ratio of two RGB colours, from 1 to 21."""
    def luminance(rgb_: tuple) -> float:
        lin = [c / 255 / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb_]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def text_contrast(size: float) -> float:
    """Contrast a text of `size` points needs against what is behind it: 4.5:1, or 3:1 from 18 pt.
    Bold does not lower the threshold, so a regular label of the same size reads too."""
    return 3 if size >= 18 else 4.5


def readable(otype: str, color: str, on: str, size: float) -> None:
    """Stops the run when a label in the role `color` does not read on the role `on` at its size."""
    need = text_contrast(size)
    ratio = contrast(rgb(color), rgb(on))
    if ratio < need:
        fits = [role for role in PALETTE if role != on and contrast(PALETTE[role], PALETTE[on]) >= need]
        sys.exit(f"{otype}: {color} {PALETTE[color]} on {on} {PALETTE[on]} reads {ratio:.1f}:1; text of size "
                 f"{size:g} needs {need:g}:1. Roles that read on {on}: {', '.join(fits) or 'none'}; or put the "
                 f"label on a panel whose role it reads on and pass it as on=")


def text_inst(otype: str, text: str, x: float, y: float, w: float, h: float, size: float | None = None,
              halign: str = "left", bold: bool = False, color: str = "ink", on: str = "canvas_alt",
              ivars=None, behaviors=None) -> dict:
    """A Text in FONT at a TEXT_SIZE size, in the PALETTE role `color`. `on` is the role behind it,
    which it must read on: canvas_alt, the darker backdrop cell, unless a panel is behind it."""
    size = size or TEXT_SIZE["body"]
    readable(otype, color, on, size)
    return instance(otype, {"text": text, "enable-bbcode": False, "font": FONT, "size": size, "line-height": 0,
                            "bold": bold, "italic": False, "color": rgba(rgb(color)), "horizontal-alignment": halign,
                            "vertical-alignment": "center", "wrapping": "word", "text-direction": "ltr",
                            "icon-set": -1, "initially-visible": True, "origin": "top-left", "read-aloud": False},
                    world(x, y, w, h, 0, 0), ivars, behaviors)


# A Text's size is in points, drawn at 96 px per 72 pt: 1 em is size * PX_PER_PT px
PX_PER_PT = 4 / 3
LINE_EMS = 1.2                             # line height in em


def text_ems(text: str) -> float:
    """Width of `text` in em: 1 for a wide or full-width character (Chinese, Japanese, Korean, the
    full-width comma and colon), 0.6 for any other. In px: text_ems(s) * size * PX_PER_PT."""
    return round(sum(1.0 if unicodedata.east_asian_width(c) in ("W", "F") else 0.6 for c in text), 6)


def hud_text(otype: str, text: str, where: str, size: float | None = None, longest: str | None = None,
             bold: bool = True, color: str = "ink", on: str = "canvas_alt", dx: float = 0, dy: float = 0,
             ivars=None, behaviors=None) -> dict:
    """A HUD label held to the edge `where` by anchor(), as wide as `longest` and a line high, in
    whole units. `longest` is the widest text it shows at runtime: "Score: 999" for a label that
    starts as "Score: 0". The text aligns to the side it hangs on, so a right-hand label grows
    leftwards. Size TEXT_SIZE["body"], or ["title"] for a banner; color and on as for text_inst()."""
    size = size or TEXT_SIZE["body"]
    w, h = label_box(longest or text, size)
    halign = {"left": "left", "middle": "center", "right": "right"}[sides(where)[1]]
    x, y = anchor(where, w, h, 0, 0, dx, dy)
    return text_inst(otype, text, x, y, w, h, size=size, halign=halign, bold=bold, color=color, on=on,
                     ivars=ivars, behaviors={**anchored(where), **(behaviors or {})})


def label_box(text: str, size: float | None = None) -> tuple[int, int]:
    """(w, h) in px of a one-line label of `text` at `size` (TEXT_SIZE["body"] by default), each
    rounded up to a whole unit."""
    size = size or TEXT_SIZE["body"]
    return (math.ceil(text_ems(text) * size * PX_PER_PT / UNIT) * UNIT,
            math.ceil(size * PX_PER_PT * LINE_EMS / UNIT) * UNIT)


def line_height(size: float | None = None) -> int:
    """Height in px of one line of text at `size` (TEXT_SIZE["body"] by default), rounded up."""
    return math.ceil((size or TEXT_SIZE["body"]) * PX_PER_PT * LINE_EMS)


def origin_name(ox: float, oy: float) -> str:
    """The "origin" property of a Tiled Background or 9-patch for an (ox, oy) origin."""
    v = {0: "top", 0.5: "", 1: "bottom"}[oy]
    h = {0: "left", 0.5: "", 1: "right"}[ox]
    return "-".join(p for p in (v, h) if p) or "center"


def tiledbg_inst(otype: str, x: float, y: float, w: float, h: float, ox: float = 0, oy: float = 0.5,
                 ivars=None, behaviors=None) -> dict:
    """A Tiled Background instance. A pattern() type is offset back to the layout's origin, so its
    pieces line up with the layout and two of them meet without a seam."""
    tile = TILES.get(otype)
    off_x, off_y = (round(-(x - ox * w)) % tile, round(-(y - oy * h)) % tile) if tile else (0, 0)
    return instance(otype, {"initially-visible": True, "origin": origin_name(ox, oy), "wrap-horizontal": "repeat",
                            "wrap-vertical": "repeat", "image-offset-x": off_x, "image-offset-y": off_y, "image-scale-x": 1,
                            "image-scale-y": 1, "image-angle": 0, "enable-tile-randomization": False, "x-random": 1,
                            "y-random": 1, "angle-random": 1, "blend-margin-x": 0.1, "blend-margin-y": 0.1},
                    world(x, y, w, h, ox, oy), ivars, behaviors)


def area(otype: str, col: int, row: int, cols: int, rows: int, ivars=None, behaviors=None) -> dict:
    """An area or an edge of the pattern type `otype`, cols x rows cells from cell (col, row): a
    one-way platform in low stripes, a door in caution, lava in hazard. Caution and hazard cover
    strips and small zones, their shorter side a quarter of the viewport's at most. The plain sheet
    and the checker are for backdrop() only."""
    kind = PATTERN_OF.get(otype)
    if not kind:
        sys.exit(f"area({otype!r}): not a pattern; draw it with pattern({otype!r}, kind) in build_images() and give "
                 f"it pattern_type({otype!r}) in build_object_types()")
    if kind in BACKDROPS:
        sys.exit(f"area({otype!r}): the {kind} pattern is empty space, the backdrop alone; place it with "
                 f"backdrop({otype!r})")
    most = min(VIEW_W, VIEW_H) // 4 // UNIT
    if kind in ("caution", "hazard") and min(cols, rows) > most:
        sys.exit(f"area({otype!r}): {cols}x{rows} cells of {kind} stripes; these cover strips and small zones, never "
                 f"a backdrop, so keep the shorter side to {most} cells, a quarter of the viewport's")
    return tiledbg_inst(otype, units(col), units(row), units(cols), units(rows), 0, 0, ivars, behaviors)


def backdrop(otype: str, width: int | None = None, height: int | None = None) -> dict:
    """The backdrop in the pattern `otype` behind everything: one Tiled Background over the layout
    (`width` x `height`, the viewport's by default) reaching SCREEN_PAD past it, so no screen shows
    its edge. The plain sheet, or the checker when the game has something transparent, a mask or a
    background to come."""
    if PATTERN_OF.get(otype) not in BACKDROPS:
        sys.exit(f"backdrop({otype!r}): the backdrop is the plain sheet or the checker; draw it with "
                 f"pattern({otype!r}, \"plain\") or pattern({otype!r}, \"checker\")")
    return tiledbg_inst(otype, *screen_box(width, height), 0, 0)


def ninepatch_inst(otype: str, x: float, y: float, w: float, h: float, ox: float = 0, oy: float = 0.5, margin: int = 2,
                   edges: str = "stretch", fill: str = "stretch", ivars=None, behaviors=None) -> dict:
    """A 9-patch instance; `margin` is the border its corners keep, in image pixels."""
    return instance(otype, {"left-margin": margin, "right-margin": margin, "top-margin": margin, "bottom-margin": margin,
                            "edges": edges, "fill": fill, "initially-visible": True, "origin": origin_name(ox, oy),
                            "seams": "overlap"},
                    world(x, y, w, h, ox, oy), ivars, behaviors)


def hud_bar(frame_name: str, fill_name: str, where: str, length: float, height: float = 0, inset: float = 2,
            caps: bool = False, dx: float = 0, dy: float = 0) -> tuple[dict, dict]:
    """A bar held to the edge `where` by anchor(): a frame `length` px long, and a fill `inset` px
    inside it. The fill's origin is on its left edge, so a width set from a value grows it
    rightwards. Types come from bar_types() and images from bar_images(), with the same `caps`.
    Set the fill in the one place the value changes:
        set_width(fill, bar_width("hp", "HP_MAX", HP_BAR_LENGTH))
    or slide it with tween_width(); HP_BAR_LENGTH = length - 2 * inset, a constant of the sheet. A
    count of icons is a bar too: the fill `count * icon` wide over a frame of empty icons.
    Returns (frame, fill)."""
    height = height or units(1)
    cx, cy = anchor(where, length, height, 0.5, 0.5, dx, dy)
    return bar_at(frame_name, fill_name, cx, cy, length, height, inset, caps, anchored(where))


def bar_at(frame_name: str, fill_name: str, cx: float, cy: float, length: float, height: float, inset: float = 2,
           caps: bool = False, behaviors: dict | None = None) -> tuple[dict, dict]:
    """hud_bar()'s frame and fill, the frame's centre at (cx, cy); `behaviors` go on both."""
    make = ninepatch_inst if caps else tiledbg_inst
    frame_inst = make(frame_name, cx, cy, length, height, 0.5, 0.5, behaviors=dict(behaviors or {}))
    fill_inst = make(fill_name, cx - length / 2 + inset, cy, length - 2 * inset, height - 2 * inset, 0, 0.5,
                     behaviors={**TWEEN, **(behaviors or {})})
    return frame_inst, fill_inst


# --- components and screens ---------------------------------------------------------------
# A button is a shape with its label as its child (link()), so hiding, moving or destroying the
# button takes the label along. A bar has its name in front.
# A screen is bands (bands()): title, status, stage, hint. band_text() puts a label in a band;
# fit() sizes the stage's main object.
SCENE_FLAGS = {"x": True, "y": True, "z": False, "w": False, "h": False, "a": False, "o": True, "v": True, "d": True,
               "sm": "normal"}
STAGE_SHARE = 0.6                          # share of the stage, across or down, its main object covers


def link(parent: dict, *children: dict, size: bool = False) -> None:
    """Makes `children` follow the layout instance `parent`: position, opacity, visibility and
    destruction. So "Set invisible" on a button hides its label. size=True adds width and height,
    and a Text's letters scale with its box, so squashing the parent squashes the label. Each
    child starts visible as the parent does. Put a child on the parent's layer, after it."""
    preview = {"transformX": 0, "transformY": 0, "transformZElevation": 0, "transformW": 0, "transformH": 0,
               "transformA": 0, "transformSX": 0, "transformSY": 0, "transformO": 0, "previewSceneGraph": False}
    own = {"x": True, "y": True, "z": True, "w": True, "h": True, "a": True, "o": False, "v": False, "d": True,
           "sm": "normal"}

    def put(inst: dict, graph: dict) -> None:
        items = [(k, v) for k, v in inst.items() if k != "sceneGraphData"]
        inst.clear()
        for k, v in items:
            if k == "showing":
                inst["sceneGraphData"] = graph
            inst[k] = v

    graph = parent.get("sceneGraphData") or {"parent-uid": None, "uid": parent["uid"], "children": [],
                                              "flags": dict(own), "preview": dict(preview)}
    if "children" not in graph:
        # A child with children of its own, a slider's knob: "children" goes after "uid", as the editor writes it
        graph = {k: v for key, value in graph.items()
                 for k, v in ((key, value), *((("children", []),) if key == "uid" else ()))}
    flags = {**SCENE_FLAGS, "w": size, "h": size}
    for child in children:
        graph["children"].append({"uid": child["uid"], "flags": dict(flags)})
        put(child, {"parent-uid": parent["uid"], "uid": child["uid"], "flags": dict(flags),
                    "preview": dict(preview)})
        child["properties"]["initially-visible"] = parent["properties"].get("initially-visible", True)
    put(parent, graph)


def text_on(on: str, size: float | None = None) -> str:
    """The role a label reads best in on the role `on`: "ink" or "flash", whichever stands out
    more, or another role when neither reads."""
    best = max((r for r in ("ink", "flash") if r in PALETTE and r != on), key=lambda r: contrast(PALETTE[r], rgb(on)))
    if contrast(PALETTE[best], rgb(on)) >= text_contrast(size or TEXT_SIZE["body"]):
        return best
    return max((r for r in PALETTE if r != on), key=lambda r: contrast(PALETTE[r], PALETTE[on]))


def button_size(text: str, size: float | None = None) -> tuple[int, int]:
    """(w, h) in px of a button labelled `text`, its longest text: the label plus a unit on each
    side and half a unit above and below, at least TOUCH each way. Draw the button at it:
    shape(rel, "rect", *button_size("Restart"), "solid")."""
    w, h = label_box(text, size)
    return max(TOUCH, w + 2 * UNIT), max(TOUCH, h + UNIT)


def label_size(text: str, w: float, h: float) -> float:
    """Size of a label of `text` on a w x h px box: TEXT_SIZE["title"] when the box holds it, else
    TEXT_SIZE["body"]."""
    tw, th = button_size(text, TEXT_SIZE["title"])
    return TEXT_SIZE["title"] if tw <= w and th <= h else TEXT_SIZE["body"]


def button(otype: str, rel: str, label: str, text: str, col: int, row: int, size: float | None = None,
           longest: str | None = None, color: str | None = None, ivars=None, behaviors=None, label_ivars=None,
           label_behaviors=None) -> tuple[dict, dict]:
    """A button: the shape images/<rel> on cell (col, row), and the Text type `label` showing
    `text` centred on it. The label's size is `size` or label_size()'s, and its role reads on the
    fill unless `color` names one. The label is the shape's child, size included, so press()
    squashes both. `longest` is the widest text it shows; a shape smaller than its button_size()
    stops the run. Returns (shape, label): put both on one layer in that order, so the label draws
    on top."""
    if rel not in DRAWN_AS:
        sys.exit(f"button({otype!r}): draw images/{rel} first, shape({rel!r}, \"rect\", *button_size({text!r}), "
                 f"role), in build_images()")
    w, h = DRAWN_AS[rel][1:3]
    size = size or label_size(longest or text, w, h)
    need = button_size(longest or text, size)
    if w < need[0] or h < need[1]:
        sys.exit(f"button({otype!r}): the label {longest or text!r} needs a shape of {need[0]}x{need[1]} px and "
                 f"images/{rel} is {w}x{h}; draw it at button_size({longest or text!r}), or shorten the text")
    shape_ = shape_inst(otype, rel, col, row, ivars=ivars, behaviors=behaviors)
    on = FILLS.get(rel, "canvas_alt")
    text_ = text_inst(label, text, units(col), units(row), w, h, size, "center", bold=True,
                      color=color or text_on(on, size), on=on, ivars=label_ivars, behaviors=label_behaviors)
    link(shape_, text_, size=True)
    return shape_, text_


def labelled_bar(label: str, text: str, frame_name: str, fill_name: str, where: str, length: float,
                 height: float = 0, inset: float = 2, caps: bool = False, dx: float = 0, dy: float = 0,
                 color: str = "ink", on: str = "canvas_alt") -> tuple[dict, dict, dict]:
    """A bar with its name in front, held to the edge `where` as one box: the Text `label` showing
    `text`, a unit of space, then hud_bar()'s frame and fill. Returns (label, frame, fill); set the
    fill as for hud_bar()."""
    height = height or units(1)
    lw, lh = label_box(text)
    box_h = max(lh, height)
    x, y = anchor(where, lw + UNIT + length, box_h, 0, 0, dx, dy)
    name = text_inst(label, text, x, y, lw, box_h, halign="left", bold=True, color=color, on=on,
                     behaviors=anchored(where))
    return (name, *bar_at(frame_name, fill_name, x + lw + UNIT + length / 2, y + box_h / 2, length, height, inset, caps,
                          anchored(where)))


SCREENS = ("stage",)


def bands(screen: str = "stage", title: bool = True) -> dict[str, tuple[int, int, int, int]]:
    """The named bands of a screen, each (x, y, w, h) in px, MARGIN inside the viewport, tops on
    the grid:
        title   at the top, a line of TEXT_SIZE["title"] for the game's name
        status  under it, a body line for what the player watches, the score or the time
        stage   a unit under the status, where the game is
        hint    at the bottom, a unit under the stage, a body line for what to do
    A screen with no title, title=False, starts with the status band, and the stage takes the room."""
    if screen not in SCREENS:
        sys.exit(f"bands({screen!r}): the screens are {', '.join(SCREENS)}")
    width = VIEW_W - 2 * MARGIN
    title_h = label_box("", TEXT_SIZE["title"])[1] if title else 0
    line_h = label_box("", TEXT_SIZE["body"])[1]
    status_y = MARGIN + title_h
    stage_y = status_y + line_h + UNIT
    hint_y = (VIEW_H - MARGIN - line_h) // UNIT * UNIT
    return {"title": (MARGIN, MARGIN, width, title_h), "status": (MARGIN, status_y, width, line_h),
            "stage": (MARGIN, stage_y, width, hint_y - UNIT - stage_y), "hint": (MARGIN, hint_y, width, line_h)}


def band_text(otype: str, text: str, band: str, align: str = "center", longest: str | None = None,
              screen: str = "stage", title: bool = True, color: str = "ink", on: str = "canvas_alt", ivars=None,
              behaviors=None) -> dict:
    """A label in the band `band` of bands(), at its `align` side, sized as hud_text() sizes it.
    Title and stage bands take TEXT_SIZE["title"], or the body size when the text is too wide;
    status and hint take the body size. The stage band centres it vertically. A text the band
    cannot hold stops the run. anchored() holds title and status labels to the top, hint labels
    to the bottom, and a left or right label to its side."""
    box = bands(screen, title).get(band)
    if box is None:
        sys.exit(f"band_text({otype!r}): {band!r} is no band; the bands are {', '.join(bands(screen, title))}")
    if align not in ("left", "center", "right"):
        sys.exit(f"band_text({otype!r}): align {align!r}; left, center or right")
    x0, y0, bw, bh = box
    size = TEXT_SIZE["title"] if band in ("title", "stage") else TEXT_SIZE["body"]
    if label_box(longest or text, size)[0] > bw:
        size = TEXT_SIZE["body"]
    w, h = label_box(longest or text, size)
    if w > bw:
        chars = int(bw / (size * PX_PER_PT))
        sys.exit(f"band_text({otype!r}): {longest or text!r} is {w} px wide and the {band} band {bw}; it holds about "
                 f"{chars} Chinese characters or {int(chars / 0.6)} letters, so shorten it")
    x = {"left": x0, "center": x0 + (bw - w) // 2, "right": x0 + bw - w}[align]
    y = y0 + (bh - h) // 2 if band == "stage" else y0
    edge = {"title": "top", "status": "top", "hint": "bottom"}.get(band)
    where = "-".join(side for side in (edge, None if align == "center" else align) if side) or "center"
    return text_inst(otype, text, x, y, w, h, size, align, bold=True, color=color, on=on, ivars=ivars,
                     behaviors={**anchored(where), **(behaviors or {})})


def fit(w: float, h: float, screen: str = "stage", share: float = STAGE_SHARE, title: bool = True) -> tuple[int, int]:
    """(cols, rows) of the largest box in the proportions w:h that covers `share` of the stage
    across or down: the size of the stage's main object, fit(1, 1) for a square."""
    _, _, sw, sh = bands(screen, title)["stage"]
    k = min(share * sw / UNIT / w, share * sh / UNIT / h)
    return max(1, int(w * k)), max(1, int(h * k))


def stage_cell(cols: int, rows: int, screen: str = "stage", title: bool = True) -> tuple[int, int]:
    """Cell (col, row) that centres a box of cols x rows units in the stage."""
    x, y, w, h = bands(screen, title)["stage"]
    return (x + (w - cols * UNIT) // 2) // UNIT, (y + (h - rows * UNIT) // 2) // UNIT


# --- input controls -----------------------------------------------------------------------------
# Slider, toggle and text input: a row TOUCH high from a grid cell, its label, then the control.
# The text input is Construct's Text input, an HTML element over the canvas, because the caret,
# selection, paste and Chinese input methods are the browser's.
# Controls of one kind share their object types; the events tell them apart by the instance
# variable "name" and set a global per name.
SLIDER = {"track": "SliderTrack", "fill": "SliderFill", "knob": "SliderKnob", "label": "SliderLabel",
          "value": "SliderValue"}
TOGGLE = {"switch": "Toggle", "label": "ToggleLabel"}
TEXT_INPUT = {"box": "TextInput", "label": "TextInputLabel"}
# Visible size of each control in its TOUCH-high row: the slider's bar and knob, the toggle's switch
CONTROL_SIZE = {"bar": max(2, UNIT // 2), "knob": units(2), "switch": (units(4), units(2))}
SLIDER_REACH = math.ceil(TOUCH / 2 / UNIT) * UNIT   # px the knob's hit box reaches past each track end


def control_label(otype: str, text: str, col: int, row: int, cols: int | None, on: str) -> tuple[dict | None, int]:
    """The label of a control's row at cell (col, row): `cols` units wide or as wide as `text`,
    TOUCH high. Returns (label, or None without text; x in px where the control starts)."""
    x = units(col)
    if not text:
        return None, x
    w = units(cols) if cols else label_box(text)[0]
    if label_box(text)[0] > w:
        sys.exit(f"{otype}: {text!r} needs {label_box(text)[0] // UNIT} units and label_cols is {cols}; widen it")
    return text_inst(otype, text, x, units(row), w, TOUCH, color=text_on(on), on=on), x + w + UNIT


def control_frame(rel: str, w: int, h: int, pixel, tag: str = "") -> dict:
    """images/<rel> from `pixel`, and its frame: centred origin, and the whole box as collision
    polygon, so a finger anywhere in the box hits the control."""
    write_png(rel, w, h, pixel)
    FRAMES[rel] = {**frame(w, h), "tag": tag}
    PADS[rel] = (0, 0)
    return FRAMES[rel]


def need_contrast(what: str, a: str, b: str) -> None:
    """Stops the run when the roles `a` and `b` of a control's parts read under 3:1 on each other."""
    if contrast(rgb(a), rgb(b)) < 3:
        fits = [r for r in PALETTE if contrast(PALETTE[r], rgb(b)) >= 3]
        sys.exit(f"{what}: {a} on {b} reads {contrast(rgb(a), rgb(b)):.1f}:1, and a control's part needs 3:1 to "
                 f"show; use one of {', '.join(fits)}")


def slider_types(track_role: str = "solid", fill_role: str = "ink", knob_role: str = "ink") -> dict:
    """Object types and images of slider(): types.update(slider_types()) in build_object_types().
    The track is TOUCH high with the bar across its middle, so a finger anywhere along it hits it.
    The knob is a Sprite with Drag & Drop along X and its value in instance variables.
    Names: SLIDER."""
    need_contrast("slider fill", fill_role, track_role)
    need_contrast("slider knob", knob_role, "canvas_alt")
    bar, knob = CONTROL_SIZE["bar"], CONTROL_SIZE["knob"]
    track = image_type(SLIDER["track"], "TiledBg", UNIT, TOUCH, 0, 0.5)
    write_png(f"{SLIDER['track'].lower()}.png", UNIT, TOUCH, lambda x, y: (*rgb(track_role), 255)
              if abs(y + 0.5 - TOUCH / 2) < bar / 2 else (0, 0, 0, 0))
    fill = image_type(SLIDER["fill"], "TiledBg", UNIT, bar, 0, 0.5)
    write_png(f"{SLIDER['fill'].lower()}.png", UNIT, bar, lambda x, y: (*rgb(fill_role), 255))
    edge = SHAPE_STYLE["outline_width"] if SHAPE_STYLE["outline"] else 0
    rel = f"{SLIDER['knob'].lower()}-default-000.png"

    def disc(x, y):
        px, py = x + 0.5 - (TOUCH - knob) / 2, y + 0.5 - (TOUCH - knob) / 2
        if not inside("circle", knob, knob, px, py):
            return (0, 0, 0, 0)
        return (*rgb(knob_role if inside("circle", knob, knob, px, py, edge) else SHAPE_STYLE["outline_role"]), 255)

    knob_type = sprite_type(SLIDER["knob"], [animation("Default", [control_frame(rel, TOUCH, TOUCH, disc)])],
                            ivars=[ivar_def("name", "string", "Which slider: the events set the global of this name."),
                                   ivar_def("value", "number", "The value the knob stands at, from lo to hi."),
                                   ivar_def("lo", "number", "The value at the track's left end."),
                                   ivar_def("hi", "number", "The value at the track's right end."),
                                   ivar_def("step", "number", "The value moves in steps of this size.")],
                            behaviors=[beh_def("DragnDrop", "DragDrop")])
    return {SLIDER["track"]: track, SLIDER["fill"]: fill, SLIDER["knob"]: knob_type,
            SLIDER["label"]: text_type(SLIDER["label"]), SLIDER["value"]: text_type(SLIDER["value"])}


def slider(name: str, col: int, row: int, length: int, lo: float = 0, hi: float = 100, value: float | None = None,
           step: float = 1, text: str = "", label_cols: int | None = None, value_at: str = "end",
           on: str = "canvas_alt") -> list[dict]:
    """A slider named `name` in a TOUCH-high row from cell (col, row): the label `text`, room for
    the knob, the track `length` px long in whole units, room again, and the value. The knob
    starts at `value`, lo by default. It moves from lo at the left to hi at the right in steps of
    `step`.
    `value_at` shows the value at the "end", over the "knob", or None. `label_cols` widens the label
    so a column of sliders lines up its tracks. Types: slider_types(); events: slider_events().
    Returns the instances, track first; put them on one layer. Read the value from the global
    slider_events() sets, or from SliderKnob.value picked by name."""
    if length % UNIT or length <= 0:
        sys.exit(f"slider({name!r}): length {length} is not whole units of {UNIT} px; give it units(n)")
    if not hi > lo or step <= 0:
        sys.exit(f"slider({name!r}): lo {lo:g}, hi {hi:g}, step {step:g}; a slider runs from a lower lo to a higher "
                 f"hi in a step above 0")
    if value_at not in ("end", "knob", None):
        sys.exit(f"slider({name!r}): value_at {value_at!r}; \"end\", \"knob\" or None")
    value = lo if value is None else min(max(value, lo), hi)
    label, x = control_label(SLIDER["label"], text, col, row, label_cols, on)
    tx, cy = x + SLIDER_REACH, units(row) + TOUCH / 2
    kx = tx + length * (value - lo) / (hi - lo)
    track = tiledbg_inst(SLIDER["track"], tx, cy, length, TOUCH, 0, 0.5)
    fill = tiledbg_inst(SLIDER["fill"], tx, cy, kx - tx, CONTROL_SIZE["bar"], 0, 0.5)
    knob = sprite_inst(SLIDER["knob"], kx, cy, TOUCH, TOUCH,
                       ivars={"name": name, "value": value, "lo": lo, "hi": hi, "step": step},
                       behaviors={"DragDrop": {"properties": {"axes": "horizontal-only", "enabled": True}}})
    parts = [track, fill, knob, *([label] if label else [])]
    widest = max((f"{v:g}" for v in (lo, hi, lo + step)), key=text_ems)
    vw, vh = label_box(widest)[0], line_height()
    shown = None
    if value_at == "end":
        shown = text_inst(SLIDER["value"], f"{value:g}", tx + length + SLIDER_REACH, units(row), vw, TOUCH,
                          halign="right", color=text_on(on), on=on)
        parts.append(shown)
    link(track, *parts[1:])
    if value_at == "knob":
        shown = text_inst(SLIDER["value"], f"{value:g}", kx - vw / 2, cy - CONTROL_SIZE["knob"] / 2 - GAP_IN - vh, vw,
                          vh, halign="center", color=text_on(on), on=on)
        link(knob, shown)
        parts.append(shown)
    return parts


def slider_events(sets: dict | None = None) -> list:
    """Event rows that work every slider(): the custom action Slide, which puts a knob on its track
    at a step and shows its value, and the events that call it. A dragged knob slides; a finger on
    the track elsewhere draws the knob to it. `sets` maps a slider to the number global it sets,
    {"volume": "volume"} for slider("volume", ...); declare it as a number.
        module("Settings", events=[*slider_events({"volume": "volume"}), ...])"""
    knob, track, fill, shown = SLIDER["knob"], SLIDER["track"], SLIDER["fill"], SLIDER["value"]
    left, right = f"{track}.BBoxLeft", f"{track}.BBoxRight"
    value = f"clamp(Self.lo + round(unlerp({left}, {right}, Self.X) * (Self.hi - Self.lo) / Self.step) * Self.step, " \
            f"Self.lo, Self.hi)"
    show = [comment("Fill the track up to the knob"),
            block([pick_children(track, fill)], [set_width(fill, f"{knob}.X - {fill}.X")]),
            comment("Show the value rounded to three places"),
            block([cond("pick-children", track, {"child": shown, "which": "all"})],
                  [set_text(shown, f"str(round({knob}.value * 1000) / 1000)")])]
    for n, v in (sets or {}).items():
        show += [comment(f"The {n} slider sets {v}"), block([ivar_cmp(knob, "name", EQ, q(n))], [set_var(v, f"{knob}.value")])]
    return [
        *procedure("Put each picked knob on its track at a step, then show its value and set its global",
                   custom_action(knob, "Slide", [], children=[
                       block([for_each(knob), cond("pick-parent", knob, {"parent": track, "which": "own"})], [
                           set_ivar(knob, "value", value),
                           act("set-x", knob, {"x": f"lerp({left}, {right}, unlerp(Self.lo, Self.hi, Self.value))"}),
                       ], children=show)])),
        *event("Show each slider at its knob's value", [on_start()], [call_custom(knob, "Slide")]),
        *event("Slide a dragged knob along its track", [cond("is-dragging", knob, beh="DragDrop")],
               [call_custom(knob, "Slide")]),
        *event("Draw a knob to the finger that holds its track elsewhere",
               [cond("is-touching-object", "Touch", {"object": track})], [], children=[
                   block([pick_children(track, knob), cond("is-dragging", knob, beh="DragDrop", inverted=True)],
                         [act("set-x", knob, {"x": f"Touch.X({track}.LayerName)"}), call_custom(knob, "Slide")])]),
    ]


def toggle_types(off_role: str = "solid", on_role: str = "ink", knob_role: str = "canvas") -> dict:
    """Object types and images of toggle(): types.update(toggle_types()). The toggle is a Sprite with
    frames "off" and "on", a switch of CONTROL_SIZE["switch"] in a TOUCH-high box, with Tween for
    press(). Names: TOGGLE."""
    for state in (off_role, on_role):
        need_contrast("toggle switch", state, "canvas_alt")
        need_contrast("toggle knob", knob_role, state)
    sw, sh = CONTROL_SIZE["switch"]
    w, h = max(TOUCH, sw), TOUCH
    left, top, r = (w - sw) / 2, (h - sh) / 2, sh / 2
    inset = max(1, UNIT // 4)
    frames = []
    for n, (tag, role) in enumerate((("off", off_role), ("on", on_role))):
        kx = left + (r if tag == "off" else sw - r)

        def pixel(x, y, role=role, kx=kx):
            px, py = x + 0.5, y + 0.5
            if math.hypot(px - kx, py - h / 2) <= r - inset:
                return (*rgb(knob_role), 255)
            cx = min(max(px, left + r), left + sw - r)
            return (*rgb(role), 255) if math.hypot(px - cx, py - h / 2) <= r else (0, 0, 0, 0)

        frames.append(control_frame(f"{TOGGLE['switch'].lower()}-default-{n:03d}.png", w, h, pixel, tag))
    return {TOGGLE["switch"]: sprite_type(TOGGLE["switch"], [animation("Default", frames)],
                                          ivars=[ivar_def("name", "string", "Which toggle: the events set the global "
                                                                            "of this name."),
                                                 ivar_def("on", "boolean", "Whether the toggle is on.")],
                                          behaviors=[beh_def("Tween")]),
            TOGGLE["label"]: text_type(TOGGLE["label"])}


def toggle(name: str, col: int, row: int, on: bool = False, text: str = "", label_cols: int | None = None,
           behind: str = "canvas_alt") -> list[dict]:
    """A toggle named `name` in a TOUCH-high row from cell (col, row): the label `text`, a unit, then
    the switch, on or off as `on` says; `behind` is the PALETTE role behind the label. Types:
    toggle_types(); events: toggle_events(). Returns [switch] plus the label when `text` is given;
    put them on one layer."""
    label, x = control_label(TOGGLE["label"], text, col, row, label_cols, behind)
    w = max(TOUCH, CONTROL_SIZE["switch"][0])
    switch = sprite_inst(TOGGLE["switch"], x + w / 2, units(row) + TOUCH / 2, w, TOUCH,
                         ivars={"name": name, "on": on}, behaviors=dict(TWEEN))
    switch["properties"]["initial-frame"] = 1 if on else 0
    if label:
        link(switch, label)
    return [switch, *([label] if label else [])]


def toggle_events(sets: dict | None = None) -> list:
    """Event rows that work every toggle(): the custom action Show, which shows a toggle's frame and
    sets its global, a Show at start, and a press() that flips the toggle. `sets` maps a toggle to
    the boolean global it sets, {"sound": "sound"} for toggle("sound", ...); declare it as a boolean.
        module("Settings", events=[*toggle_events({"sound": "sound"}), ...])"""
    t = TOGGLE["switch"]
    names: list = []
    for n, v in (sets or {}).items():
        names += [comment(f"The {n} toggle sets {v}"),
                  cases([ivar_cmp(t, "name", EQ, q(n))], [("On", [is_bool(t, "on")], [set_bool_var(v, True)]),
                                                          ("Off", None, [set_bool_var(v, False)])])]
    return [
        *procedure("Show each picked toggle's state and set its global",
                   custom_action(t, "Show", [], children=[block([for_each(t)], [], children=[
                       comment("On: the knob at the right"),
                       block([is_bool(t, "on")], [act("set-animation-frame", t, {"frame-number": q("on")})]),
                       comment("Off: the knob at the left"),
                       block([else_()], [act("set-animation-frame", t, {"frame-number": q("off")})]),
                       *names])])),
        *event("Show each toggle as it starts", [on_start()], [call_custom(t, "Show")]),
        *press(t, [act("toggle-boolean-instvar", t, {"instance-variable": "on"}), call_custom(t, "Show")]),
    ]


def text_input_types() -> dict:
    """Object types of text_input(): the Text input, with the instance variable "name", and its
    label. Names: TEXT_INPUT."""
    box = {"name": TEXT_INPUT["box"], "plugin-id": "TextBox", "sid": sid(), "isGlobal": False,
           "editorNewInstanceIsReplica": True,
           "instanceVariables": [ivar_def("name", "string", "Which text input: the events set the global of this "
                                                            "name.")],
           "behaviorTypes": []}
    return {TEXT_INPUT["box"]: box, TEXT_INPUT["label"]: text_type(TEXT_INPUT["label"])}


def text_input(name: str, col: int, row: int, cols: int, text: str = "", placeholder: str = "", kind: str = "text",
               label: str = "", label_cols: int | None = None, on: str = "canvas_alt") -> list[dict]:
    """A text input named `name` in a TOUCH-high row from cell (col, row): the label `label`, a
    unit, then the field, `cols` units wide. The field holds `text`, or the faint `placeholder`
    when empty. `kind` is text, password, email, number, telephone-number, url or search, which
    picks the phone's keyboard. text_input_events() gives it the look's font and colours. Returns [field] plus the
    label when given; put them on one layer.
    The field is an HTML element and draws over every canvas layer: keep popups away from it, or
    hide it while they show."""
    kinds = ("text", "password", "email", "number", "telephone-number", "url", "search")
    if kind not in kinds:
        sys.exit(f"text_input({name!r}): kind {kind!r}; one of {', '.join(kinds)}")
    caption, x = control_label(TEXT_INPUT["label"], label, col, row, label_cols, on)
    field = instance(TEXT_INPUT["box"], {"text": text, "placeholder": placeholder, "tooltip": "",
                                         "initially-visible": True, "enabled": True, "read-only": False,
                                         "spell-check": False, "type": kind, "auto-font-size": False, "id": "",
                                         "class": ""},
                     world(x, units(row), units(cols), TOUCH, 0, 0), {"name": name})
    if caption:
        link(field, caption)
    return [field, *([caption] if caption else [])]


def css_px(px: float) -> str:
    """CSS length of `px` at the viewport's size, scaled as Scale outer scales the canvas, so an HTML
    element keeps its size against the drawing. Under Integer scale outer it can come out larger."""
    return f"min({100 * px / VIEW_W:.4g}vw, {100 * px / VIEW_H:.4g}vh)"


def text_input_events(sets: dict | None = None) -> list:
    """Event rows that work every text_input(): at start, the look's font, size and colours as CSS,
    since the field is an HTML element; on each change, the string global `sets` names for the
    field, {"player": "player"} for text_input("player", ...); declare it as a string."""
    box = TEXT_INPUT["box"]
    style = {"font-family": FONT, "font-size": css_px(TEXT_SIZE["body"] * PX_PER_PT), "color": "rgb({}, {}, {})"
             .format(*rgb("ink")), "background-color": "rgb({}, {}, {})".format(*rgb("canvas")),
             "border": f"{css_px(max(1, UNIT // 8))} solid " + "rgb({}, {}, {})".format(*rgb("solid")),
             "border-radius": "0", "padding": f"0 {css_px(UNIT / 2)}"}
    def names() -> list:
        out: list = []
        for n, v in (sets or {}).items():
            out += [comment(f"The {n} field sets {v}"), block([ivar_cmp(box, "name", EQ, q(n))], [set_var(v, f"{box}.Text")])]
        return out

    look = event("Give each text input the look's font, size and colours", [on_start()],
                 [act("set-css-style", box, {"property-name": q(k), "value": q(v)}) for k, v in style.items()])
    if not sets:
        return look
    return [*look,
            *event("Start each text input's global at its text", [on_start(), for_each(box)], [], children=names()),
            *event("Keep a text input's global its text", [cond("on-text-changed", box)], [], children=names())]


# --- groups and the play area -----------------------------------------------------------------
# What belongs together sits closer than what does not. hud_stat() places a value under its name
# as one group; spaced() stops the run on two groups too close. The playfield sits in what the HUD
# leaves (play_area(), centred()); balanced() and filled() warn on one off the middle or too small.
GAP_IN = max(1, UNIT // 4)                 # px between the parts of a group
GAP_OUT = UNIT                             # px at least between the HUD and the playfield
GROUP_RATIO = 1.5                          # least ratio of the gap between groups to the gap inside one
OPTICAL_LIFT = 0.05                        # share of the area's height the playfield sits above centre
PLAYFIELD_MIN = 0.15                       # least share of the screen the playfield covers


def hud_stat(name_type: str, value_type: str, name: str, where: str, value: str = "0", longest: str | None = None,
             dx: float = 0, dy: float = 0, name_color: str = "dim", color: str = "ink", on: str = "canvas_alt",
             ivars=None, behaviors=None) -> list[dict]:
    """A value under its name, held to the edge `where` as one group. The name is in the body size
    and `name_color`. GAP_IN lower, the value is in the title size and `color`, as wide as `longest`.
    Both align to the side the group hangs on. `ivars` and `behaviors` go on the value. Returns
    [name, value], one group for spaced():
        HUD = [hud_stat("ScoreLabel", "ScoreText", "SCORE", "top-left", longest="999"), ...]"""
    body, title = TEXT_SIZE["body"], TEXT_SIZE["title"]
    nw, vw = label_box(name, body)[0], label_box(longest or value, title)[0]
    nh, vh = line_height(body), line_height(title)
    gw = max(nw, vw)
    x, y = anchor(where, gw, nh + GAP_IN + vh, 0, 0, dx, dy)
    horiz = sides(where)[1]
    halign = {"left": "left", "middle": "center", "right": "right"}[horiz]
    share = {"left": 0, "middle": 0.5, "right": 1}[horiz]
    name_ = text_inst(name_type, name, round(x + share * (gw - nw)), y, nw, nh, body, halign, False, name_color, on,
                      behaviors=anchored(where))
    value_ = text_inst(value_type, value, round(x + share * (gw - vw)), y + nh + GAP_IN, vw, vh, title, halign, False,
                       color, on, ivars=ivars, behaviors={**anchored(where), **(behaviors or {})})
    return [name_, value_]


def box_of(inst: dict) -> tuple[float, float, float, float] | None:
    """(left, top, right, bottom) of a layout instance's box; None for an instance with no world."""
    w = inst.get("world")
    if not w:
        return None
    left, top = w["x"] - w.get("originX", 0) * w["width"], w["y"] - w.get("originY", 0) * w["height"]
    return left, top, left + w["width"], top + w["height"]


def gap(a: tuple, b: tuple) -> float:
    """Space between two box_of() boxes: across when they share rows, down when they share
    columns, else the smaller of the two; 0 when they meet."""
    across, down = max(0, b[0] - a[2], a[0] - b[2]), max(0, b[1] - a[3], a[1] - b[3])
    return min(across, down) if across and down else max(across, down)


def spaced(groups: list, where: str = "layout Game") -> None:
    """Stops the run when two groups sit closer than GROUP_RATIO times the gap inside either: a name
    far from its value and near the board reads as the board's. A group is a list of instances,
    such as hud_stat()'s pair, [a label] or [the board]. Pass every HUD group and the playfield."""
    found = [[(i["type"], box_of(i)) for i in g if box_of(i)] for g in groups]
    found = [g for g in found if g]

    def inner(parts: list) -> float:
        return max((min(gap(a, b) for m, (_, b) in enumerate(parts) if m != n) for n, (_, a) in enumerate(parts)),
                   default=0) if len(parts) > 1 else 0

    def hull(parts: list) -> tuple:
        boxes = [b for _, b in parts]
        return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)

    def named(parts: list) -> str:
        return " + ".join(name for name, _ in parts)

    said = []
    for n, a in enumerate(found):
        for b in found[n + 1:]:
            between = gap(hull(a), hull(b))
            inside, tight = max((inner(a), a), (inner(b), b), key=lambda p: p[0])
            if between < GROUP_RATIO * inside:
                said.append(f"{where}: {named(a)} and {named(b)} are {between:g} px apart, and {named(tight)} holds "
                            f"its parts {inside:g} px apart: groups need {GROUP_RATIO:g} times that between them, "
                            f"{GROUP_RATIO * inside:g} px. Put a value under its name with hud_stat(), GAP_IN apart, "
                            f"and the playfield at centred(w, h, play_area(hud)), GAP_OUT from the HUD.")
    if said:
        sys.exit("\n".join(said))


def play_area(hud: list) -> tuple[int, int, int, int]:
    """(x, y, w, h) in px the HUD leaves for the playfield: MARGIN inside the viewport and GAP_OUT
    clear of every box in `hud`. A box in the top third ends the area's top, one in the bottom third
    its bottom, one between them its left or right side."""
    left, top, right, bottom = MARGIN, MARGIN, VIEW_W - MARGIN, VIEW_H - MARGIN
    for inst in hud:
        b = box_of(inst)
        if not b:
            continue
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if cy < VIEW_H / 3:
            top = max(top, math.ceil(b[3] + GAP_OUT))
        elif cy > 2 * VIEW_H / 3:
            bottom = min(bottom, math.floor(b[1] - GAP_OUT))
        elif cx < VIEW_W / 2:
            left = max(left, math.ceil(b[2] + GAP_OUT))
        else:
            right = min(right, math.floor(b[0] - GAP_OUT))
    if right <= left or bottom <= top:
        sys.exit(f"play_area(): the HUD leaves no room, ({left},{top})-({right},{bottom}); move a HUD element to "
                 f"another edge or make it smaller")
    return left, top, right - left, bottom - top


def centred(w: float, h: float, area: tuple, lift: float = OPTICAL_LIFT) -> tuple[int, int]:
    """Top-left (x, y) on the grid of a w x h px box centred in play_area()'s `area`, raised by
    `lift` of the area's height and kept inside it. A box larger than the area stops the run."""
    ax, ay, aw, ah = area
    if w > aw or h > ah:
        sys.exit(f"centred(): a {w:g}x{h:g} px box does not fit the {aw}x{ah} px play area at ({ax},{ay}); make it "
                 f"smaller, with fewer or smaller cells, or move a HUD element to another edge")

    def place(start: int, room: int, size: float, raised: float) -> int:
        lo, hi = math.ceil(start / UNIT) * UNIT, math.floor((start + room - size) / UNIT) * UNIT
        v = snap(start + (room - size) / 2 - raised)
        return v if lo > hi else min(max(v, lo), hi)

    return place(ax, aw, w, 0), place(ay, ah, h, lift * ah)


def balanced(content: list, area: tuple, lift: float = OPTICAL_LIFT, where: str = "layout Game") -> None:
    """Warns when the box around `content`, the playfield's instances, has its centre more than a
    unit from the middle of `area`, raised by `lift`.
    A warning, not a stop: a game may hold its playfield off the middle on purpose."""
    boxes = [b for b in map(box_of, content) if b]
    if not boxes:
        return
    cx = (min(b[0] for b in boxes) + max(b[2] for b in boxes)) / 2
    cy = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2
    ax, ay, aw, ah = area
    tx, ty = ax + aw / 2, ay + ah / 2 - lift * ah
    if max(abs(cx - tx), abs(cy - ty)) > UNIT:
        names = " + ".join(dict.fromkeys(i["type"] for i in content if box_of(i)))
        print(f"warning: {where}: {names} is centred at ({cx:g},{cy:g}) and the middle of the play area the HUD "
              f"leaves is ({tx:g},{ty:g}), {abs(cx - tx):g} px across and {abs(cy - ty):g} px down; place it at "
              f"centred(w, h, play_area(hud)), or keep it there if the offset is meant")


def filled(content: list, where: str = "layout Game") -> None:
    """Warns when the box around `content`, the playfield's instances in the layout, covers less
    than PLAYFIELD_MIN of the viewport.
    A warning, not a stop: a playfield created at runtime shows less in the layout than in play."""
    boxes = [b for b in map(box_of, content) if b]
    if not boxes:
        return
    w = min(max(b[2] for b in boxes), VIEW_W) - max(min(b[0] for b in boxes), 0)
    h = min(max(b[3] for b in boxes), VIEW_H) - max(min(b[1] for b in boxes), 0)
    covers = max(0, w) * max(0, h) / (VIEW_W * VIEW_H)
    if covers < PLAYFIELD_MIN:
        names = " + ".join(dict.fromkeys(i["type"] for i in content if box_of(i)))
        print(f"warning: {where}: {names} covers {covers:.0%} of the {VIEW_W}x{VIEW_H} screen, under "
              f"PLAYFIELD_MIN {PLAYFIELD_MIN:.0%}. Make it larger, bigger cells or more of them, or fit(w, h) "
              f"for its size on the stage")


# --- the order of each layer and the HUD's behavior --------------------------------------------
# build_all() runs both over the layouts before it writes them
def layers_in(layers: list):
    """Every layer of `layers` and of their sublayers, a parent before its sublayers."""
    for lay in layers:
        yield lay
        yield from layers_in(lay.get("subLayers", []))


def z_order(instances: list) -> list:
    """A layer's instances back to front: the backdrop, then pattern() areas, then the rest by the
    bottom of their box, so a nearer object covers a farther one. Ties keep their order. A link()
    child follows its parent, and a box wholly inside another follows it unless the outer box is a
    label. For another order, such as a 3D layer by depth, define z_order() below the end marker."""
    boxes = [box_of(inst) for inst in instances]
    keys = []
    for n, inst in enumerate(instances):
        kind = PATTERN_OF.get(inst["type"])
        rank = 0 if kind in BACKDROPS else 1 if kind else 2
        keys.append((rank, boxes[n][3] if rank == 2 and boxes[n] else 0, n))
    # What each instance follows: its parent, else the smallest box that holds it, not a label
    holders = sorted((m for m, inst in enumerate(instances) if keys[m][0] == 2 and boxes[m]
                      and "text" not in inst.get("properties", {})),
                     key=lambda m: ((boxes[m][2] - boxes[m][0]) * (boxes[m][3] - boxes[m][1]), m))
    at = {inst.get("uid"): n for n, inst in enumerate(instances)}
    follows = {}
    for n, inst in enumerate(instances):
        parent = (inst.get("sceneGraphData") or {}).get("parent-uid")
        if parent in at and at[parent] != n:
            follows[n] = at[parent]
        elif keys[n][0] == 2 and boxes[n]:
            b = boxes[n]
            for m in holders:
                h = boxes[m]
                if m != n and h[0] <= b[0] and h[1] <= b[1] and b[2] <= h[2] and b[3] <= h[3] and (h != b or m < n):
                    follows[n] = m
                    break
    for n in list(follows):                  # cut a loop that a cyclic parent chain makes
        seen, m = {n}, follows.get(n)
        while m is not None and m not in seen:
            seen.add(m)
            m = follows.get(m)
        if m == n:
            del follows[n]
    after: dict[int, list[int]] = {}
    for n, m in follows.items():
        after.setdefault(m, []).append(n)
    ordered: list[dict] = []

    def put(n: int) -> None:
        ordered.append(instances[n])
        for c in sorted(after.get(n, []), key=keys.__getitem__):
            put(c)

    for n in sorted((n for n in range(len(instances)) if n not in follows), key=keys.__getitem__):
        put(n)
    return ordered


def anchor_types(types: dict, layouts: dict) -> None:
    """Gives the Anchor behavior to every type with an instance that anchored() holds, and a
    disabled block to that type's other instances, because the editor reads a block on every
    instance for each behavior of its type."""
    instances = [inst for lay in layouts.values() for layer_ in layers_in(lay["layers"]) for inst in layer_["instances"]]
    held = sorted({inst["type"] for inst in instances if "Anchor" in inst.get("behaviors", {})} & set(types))
    for name in held:
        behaviors = types[name].setdefault("behaviorTypes", [])
        if not any(b["name"] == "Anchor" for b in behaviors):
            behaviors.append(beh_def("Anchor"))
    for inst in instances:
        if inst["type"] in held and "Anchor" not in inst.get("behaviors", {}):
            inst["behaviors"] = {**inst.get("behaviors", {}), "Anchor": {"properties": {
                "left-edge": "none", "top-edge": "none", "right-edge": "none", "bottom-edge": "none", "enabled": False}}}


# Behavior property blocks of a layout instance, keyed by the behavior's name on the object.
# Change a value, not a key. For a behavior missing here, copy the block from an official
# example's instance, keyed by the behavior's name ("Sine"), not its id ("Sin").
TWEEN = {"Tween": {"properties": {"enabled": True}}}
TIMER = {"Timer": {"properties": {}}}
SOLID = {"Solid": {"properties": {"enabled": True, "use-instance-tags": True, "tags": ""}}}
SINE = {"Sine": {"properties": {"movement": "horizontal", "wave": "sine", "period": 4, "period-random": 0,
                                "period-offset": 0, "period-offset-random": 0, "magnitude": 50,
                                "magnitude-random": 0, "enabled": True, "live-preview": False}}}
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
DRAG_DROP = {"DragDrop": {"properties": {"axes": "both", "enabled": True}}}
SCROLL_TO = {"ScrollTo": {"properties": {"enabled": True}}}
DESTROY_OUTSIDE = {"DestroyOutsideLayout": {"properties": {"region": "layout"}}}
BOUND_TO_LAYOUT = {"BoundToLayout": {"properties": {"bound-by": "edge", "region": "layout"}}}
LINE_OF_SIGHT = {"LineOfSight": {"properties": {"obstacles": "solids", "range": 512, "cone-of-view": 90,
                                                "use-collision-cells": True}}}


# --- project.c3proj -------------------------------------------------------------------------
ADDON_NAMES = {"TiledBg": "Tiled Background", "NinePatch": "9-patch", "Spritefont2": "Sprite font", "EightDir": "8 Direction",
               "Sin": "Sine", "DragnDrop": "Drag & Drop", "ScrollTo": "Scroll To", "MoveTo": "Move To", "LOS": "Line of sight",
               "destroy": "Destroy outside layout", "bound": "Bound to layout", "solid": "Solid", "wrap": "Wrap",
               "jumpthru": "Jump-thru", "Arr": "Array", "AdvancedRandom": "Advanced Random", "LocalStorage": "Local Storage"}


def used_addons(types: dict, families: dict) -> list:
    """project.c3proj's usedAddons, from the plugins and behaviors of the types and families. The
    editor refuses a type whose plugin is not listed. Plugins come before behaviors, each sorted by
    id in code-point order as the editor saves them, so a save leaves the list as it is."""
    plugins, behaviors = [], []
    for t in list(types.values()) + list(families.values()):
        if t["plugin-id"] not in plugins:
            plugins.append(t["plugin-id"])
        for b in t.get("behaviorTypes", []):
            if b["behaviorId"] not in behaviors:
                behaviors.append(b["behaviorId"])
    return ([{"type": "plugin", "id": i, "name": ADDON_NAMES.get(i, i), "author": "Scirra", "bundled": False} for i in sorted(plugins)]
            + [{"type": "behavior", "id": i, "name": ADDON_NAMES.get(i, i), "author": "Scirra", "bundled": False} for i in sorted(behaviors)])
# Keys the editor asserts in project.c3proj before it opens any file; a missing one fails as
# "TypeError: expected string", naming neither key nor file. Filled in only when the editor did not
# save the folder. savedWithRelease stays as the editor wrote it: it decides where an object type
# is read from.
PROJECT_DEFAULTS = {"projectFormatVersion": 1, "savedWithRelease": 49502, "runtime": "c3",
                    "useWorker": "auto", "bundleAddons": False, "functionsName": "Functions",
                    "autosaveData": None}
PROPERTY_DEFAULTS = {"description": "", "version": "1.0.0.0", "autoIncrementVersion": False,
                     "author": "", "authorEmail": "", "authorWebsite": "", "appId": "",
                     "pixelRounding": False, "zAxisScale": "regular", "fov": 0.7853981633974483,
                     "useLoaderLayout": False, "fullscreenMode": FULLSCREEN,
                     "fullscreenQuality": "high", "viewportFit": "auto",
                     "backgroundColor": [0, 0, 0, 0], "splashColor": [1, 1, 1, 0],
                     "useThemeColor": False, "themeColor": [1, 1, 1, 0], "webgpu": "auto",
                     "multitexturing": "auto", "gpuPreference": "high-performance",
                     "framerateMode": "vsync", "fixedFramerate": 30, "sampling": "trilinear",
                     "downscaling": "medium", "renderingMode": "auto",
                     "anisotropicFiltering": "auto", "zNear": 10, "zFar": 100000,
                     "maxSpriteSheetSize": 2048, "loaderStyle": "splash", "preloadSounds": True,
                     "uidAllocationMode": "random", "cordovaiOSScheme": "app",
                     "cordovaAndroidScheme": "https", "exportFileStructure": "folders",
                     "scriptsType": "module"}


def with_files(block: dict, kind: str) -> dict:
    """A timelines or flowcharts list without the names that have no file.
    A new project lists Timeline 1 and Flowchart 1; copied without their folders, it stops the
    editor with "missing file path 'timelines\\Timeline 1.json'"."""
    on_disk = {f.stem for f in (ROOT / kind).rglob("*.json")} if (ROOT / kind).is_dir() else set()
    return {**block, "items": [n for n in block.get("items", []) if n in on_disk],
            "subfolders": [with_files(sub, kind) for sub in block.get("subfolders", []) if isinstance(sub, dict)]}


def build_project(existing: dict, types: dict, families: dict, containers: list, layouts: dict,
                  sheets: list) -> dict:
    """project.c3proj with only this script's keys changed; uniqueId, icons, scripts and the
    existing properties stay."""
    p = dict(existing)
    for key, value in PROJECT_DEFAULTS.items():
        p.setdefault(key, value)
    p["properties"] = dict(p.get("properties") or {})
    for key, value in PROPERTY_DEFAULTS.items():
        p["properties"].setdefault(key, value)
    p["name"] = PROJECT_NAME
    p["usedAddons"] = used_addons(types, families)
    p["objectTypes"] = {"items": list(types), "subfolders": []}
    p["families"] = {"items": list(families), "subfolders": []}
    p["containers"] = list(containers)
    p["layouts"] = {"items": list(layouts), "subfolders": []}
    p["eventSheets"] = {"items": sheets, "subfolders": []}
    for kind in ("timelines", "flowcharts"):     # this script writes neither; keep what has a file
        if isinstance(p.get(kind), dict):
            p[kind] = with_files(p[kind], kind)
    if _general_files:
        # the files of build_files(), in place of a listed file of the same name; the others stay
        folders = p["rootFileFolders"] = dict(p.get("rootFileFolders") or {})
        for kind in ("script", "sound", "music", "video", "font", "icon", "general"):
            folders.setdefault(kind, {"items": [], "subfolders": []})
        ours = {e["name"] for e in _general_files}
        general = folders["general"] = dict(folders["general"])
        general["items"] = [e for e in general.get("items", []) if e.get("name") not in ours] + _general_files
    p["viewportWidth"] = VIEW_W
    p["viewportHeight"] = VIEW_H
    # Fill the screen at any aspect ratio, in place of the editor's Letterbox scale
    p["properties"]["fullscreenMode"] = FULLSCREEN
    if PIXEL_ART:
        # Pixel art stays crisp
        p["properties"]["sampling"] = "nearest"
    p["firstLayout"] = FIRST_LAYOUT
    p["properties"]["orientations"] = ORIENTATION
    return p


def build_all() -> None:
    c3proj = ROOT / "project.c3proj"
    if not c3proj.exists():
        if (ROOT / "SKILL.md").exists():
            sys.exit(f"{Path(__file__).name} is the skill's template: copy it to tools/build_project.py in the "
                     f"game project and run the copy there")
        sys.exit(
            f"{c3proj} not found: create the project in the editor and save it as a folder first")
    check_palette()
    for line in pace(BEATS):
        print(line)
    build_images()
    write_wanted()
    build_files()
    types, families, containers = build_object_types()
    layouts = build_layouts()
    anchor_types(types, layouts)
    for lay in layouts.values():
        for layer_ in layers_in(lay["layers"]):
            layer_["instances"] = z_order(layer_["instances"])
    # Sheet first: press() records its types, and press_types() gives them their variable
    sheet = build_event_sheet()
    press_types(types, layouts)
    for name, t in types.items():
        write_json(f"objectTypes/{name}.json", t)
    for name, f in families.items():
        write_json(f"families/{name}.json", f)
    for name, lay in layouts.items():
        write_json(f"layouts/{name}.json", lay)
    if _ajax_used and "AJAX" not in types:
        types["AJAX"] = single_global_type("AJAX", "AJAX", {})
        write_json("objectTypes/AJAX.json", types["AJAX"])
    squash_the_art(types, families)
    write_json(f"eventSheets/{sheet['name']}.json", sheet)
    with c3proj.open(encoding="utf-8-sig") as f:
        existing = json.load(f)
    write_json("project.c3proj", build_project(
        existing, types, families, containers, layouts, [sheet["name"]]))


def build_and_check() -> None:
    """build_all(), then the skill's check_project.py --style on what it wrote; exits with the
    checker's code."""
    build_all()
    # The skill's checker, in the project or in the user's skills folder
    checker = "skills/construct3-agent-plugin/scripts/check_project.py"
    found = sorted(ROOT.glob(f".*/{checker}")) or sorted(Path.home().glob(f".*/{checker}"))
    if not found:
        sys.exit("generated, not checked: the construct3-agent-plugin skill is not installed in this project; "
                 "run python <Construct3-RAG>/skills/construct3-agent-plugin/scripts/install.py here, then "
                 "its scripts/check_project.py")
    print("generated; checking")
    sys.stdout.flush()
    # --style: every event here is written by the agent, so the style warnings apply to all
    sys.exit(subprocess.run([sys.executable, str(found[0]), "--project", str(ROOT), "--style"]).returncode)


# ==== construct3-agent-plugin helpers: end; version 2026-10-14, stamp b92083d48136 ================


# --- the game ---------------------------------------------------------------------------
# Pacing, then what build_all() calls: images, data files, object types, layouts, the event sheet


# --- pacing ---------------------------------------------------------------------------
# What the game asks of the player, a beat at a time: a camera zone of a level, or here a round.
# A beat has a type, an intensity from 0 to 3, the mechanics it asks for, and for a rest what it
# holds; other keys are the game's own, here the coins a round deals. pace() checks the curve.
BEATS = [
    beat("intro", 0, ["tap"], coins=1),
    beat("teach", 1, ["tap"], coins=3),
    beat("practice", 2, ["tap"], coins=6),
    beat("rest", 0, ["tap"], holds="pickup", coins=2),
    beat("climax", 3, ["tap"], coins=10),
    beat("exit", 0, ["tap"], coins=1),
]
# Board: COLS x ROWS coin-sized slots, a unit apart
# A round deals cells (deal + i * STRIDE) mod CELLS; STRIDE shares no factor with CELLS, so no two
# coins land on one cell
COLS, ROWS = 5, 3
CELLS = COLS * ROWS
STRIDE = next(s for s in (7, 11, 13, 17, 19, 23) if math.gcd(s, CELLS) == 1)
PITCH = COIN_SIZE + UNIT
BOARD_W, BOARD_H = COLS * PITCH - UNIT, ROWS * PITCH - UNIT
# HUD groups, built first so the board can be centred in the room they leave
HUD = [hud_stat("ScoreLabel", "ScoreText", "SCORE", "top-left", longest="999"),
       [hud_text("RoundText", "ROUND 1 / 6", "top-right", longest="ROUND 10 / 10", bold=False, color="dim")]]
PLAY_AREA = play_area(flat(HUD))
BOARD_LEFT, BOARD_TOP = centred(BOARD_W, BOARD_H, PLAY_AREA)
if max(b["coins"] for b in BEATS) > CELLS:
    sys.exit(f"BEATS deal up to {max(b['coins'] for b in BEATS)} coins and the board has {CELLS} slots; "
             f"widen COLS or ROWS")


def build_files() -> None:
    """The game's data files, written before the object types. For example
    record_table("CardTable", {"strike": {...}}), with nonworld_type("CardTable", "Arr") and
    nonworld_type("Cards", "Dictionary"), their nonworld_inst() in the layout that loads them,
    load_data_file("CardTable", "CardTable.json") first in that layout's On start, and
    *table_to_dictionary("CardTable", "Cards") among its sub-events.
    The stand-in has none."""


def build_images() -> None:
    pattern("Backdrop", "plain")
    # Board slot: a coin-sized disc in canvas_alt and a unit of space, repeated by the Tiled Background
    write_png("board.png", PITCH, PITCH, lambda x, y: (*rgb("canvas_alt"), 255)
              if inside("circle", COIN_SIZE, COIN_SIZE, x + 0.5, y + 0.5) else (0, 0, 0, 0))
    art("coin-default-000.png", "circle", COIN_SIZE, COIN_SIZE, "reward", "a gold coin seen from the front")
    hit_frame("coin-default-000.png")


def build_object_types() -> tuple[dict, dict, list]:
    types = {
        "Coin": sprite_type("Coin", [animation("Default", [drawn("coin-default-000.png"), drawn("coin-default-001.png")])],
                            ivars=[ivar_def("value", "number", "Points it is worth."),
                                   ivar_def("kind", "string", "Which coin: \"gold\" or \"silver\".")],
                            behaviors=[beh_def("Tween")]),
        "Backdrop": pattern_type("Backdrop"),
        "Board": image_type("Board", "TiledBg", PITCH, PITCH, 0, 0),
        "ScoreLabel": text_type("ScoreLabel"),
        "ScoreText": text_type("ScoreText"),
        "RoundText": text_type("RoundText"),
        "Touch": single_global_type("Touch", "Touch", {"use-mouse-input": True}),
    }
    families = {}
    containers = []
    return types, families, containers


def build_layouts() -> dict[str, dict]:
    game = layout("Game", [
        layer("Background", transparent=False),
        layer("Game"),
        layer("UI", parallax=0),
    ], sheet="Game")
    # Backdrop and board. A patterned area or edge is area(type, col, row, cols, rows) on the Game
    # layer. Add instances in any order: build_all() sorts each layer
    game["layers"][0]["instances"].append(backdrop("Backdrop"))
    board = tiledbg_inst("Board", BOARD_LEFT, BOARD_TOP, BOARD_W, BOARD_H, 0, 0)
    game["layers"][0]["instances"].append(board)
    # HUD on the edges: a label by hud_text(), a value under its name by hud_stat(), repeated items
    # by row(), anything else by anchor(). The middle of the screen is the game's
    ui = game["layers"][2]["instances"]
    ui.extend(flat(HUD))
    # A value as a bar: ui.extend(hud_bar("HpFrame", "HpFill", "top-left", units(12), dy=3))
    # Layout checks: HUD overlap, spacing between groups, the board centred and large enough
    no_overlap(ui)
    spaced([*HUD, [board]])
    balanced([board], PLAY_AREA)
    filled([board])
    # Off the HUD, everything starts on the grid: shape_inst() on a cell, grid_random() at runtime
    on_grid(game["layers"][1]["instances"], "layer Game")
    # Template instances of runtime-created objects, in a layout that never runs
    objects = layout("Objects", [layer("Objects")], sheet=None)
    objects["layers"][0]["instances"].append(
        shape_inst("Coin", "coin-default-000.png", MARGIN // UNIT, MARGIN // UNIT,
                   ivars={"value": 1, "kind": "gold"}, behaviors=dict(TWEEN)))
    on_grid(objects["layers"][0]["instances"], "layout Objects")
    return {"Game": game, "Objects": objects}


# --- the event sheet -------------------------------------------------------------------
# One function per group, in play order
def module_setup() -> dict:
    return module("Setup", events=[
        # Restart layout keeps globals, so the round's values are reset here, before any text shows them
        event("Empty the score and deal this round's coins",
              [on_start()], [set_var("score", "0"), set_text("ScoreText", q("0")),
                             set_text("RoundText", f'{q("ROUND ")} & (beat + 1) & {q(" / ")} & '
                                                   f'tokencount(ROUND_COINS, {q(",")})'),
                             set_var("deal", f"floor(random({CELLS}))")], children=[
                  block([for_loop("i", "0", f"int(tokenat(ROUND_COINS, beat, {q(',')})) - 1")], [
                      create("Coin", "Game",
                             f'{BOARD_LEFT + COIN_SIZE // 2} + {PITCH} * ((deal + (loopindex("i") * {STRIDE})) % {COLS})',
                             f'{BOARD_TOP + COIN_SIZE // 2} + {PITCH} * floor(((deal + (loopindex("i") * {STRIDE})) '
                             f'% {CELLS}) / {COLS})'),
                      set_ivar("Coin", "value", "choose(1, 5)"),
                  ]),
              ]),
    ])


def module_input() -> dict:
    return module("Input", events=[
        event("A touched coin collects itself, once", [on_touched("Coin"), cond("is-any-playing", "Coin", beh="Tween",
                                                                           inverted=True)],
              [call_custom("Coin", "Collect")]),
    ])


def scoring() -> list:
    """What the groups call: a custom action to act on the caller's picked instances, a function
    for a value or for logic that picks its own."""
    return [
        *procedure("Score the coin, show the hit, then shrink it away", custom_action("Coin", "Collect", steps(
            ("Score it, then show the hit", [call("AddScore", "Coin.value"), *hit("Coin")]),
            ("Shrink it away once the punch is over", [
                wait(f"{SQUASH['hit']['seconds'] - HIT_FLASH['seconds']:g}", use_timescale=False),
                tween2("Coin", "collect", "size", "0", "0", "0.25", "easeinback", destroy=True)]),
        ))),
        *procedure("Add points and show the score", func("AddScore", [
            add_var("score", "points"),
            set_text("ScoreText", "score"),
        ], params=[param("points", "number", 0)])),
    ]


def module_restart() -> dict:
    return module("Restart", events=[
        event("Start the next round when the last coin is gone",
              [cmp2("Coin.Count", EQ, "0"), trigger_once()],
              [set_var("beat", f"(beat + 1) % tokencount(ROUND_COINS, {q(',')})"), wait("1"), restart_layout()]),
    ])


def build_event_sheet() -> dict:
    """The sheet: what it covers, the constants under Settings, the shared state, then the groups.
    A variable that one group owns is declared in its module."""
    events = [
        comment("Coins. Tap a coin to collect it; when the last one is gone the next round starts.\n"
                "The touched coin is the trigger's pick: Collect runs on it and nothing else"),
        comment("Settings"),
        var("ROUND_COINS", "string", ",".join(str(b["coins"]) for b in BEATS),
            "Coins dealt in each round, one round a beat of the generator's BEATS", const=True),
        comment("Gameplay variables"),
        var("score", "number", 0, "Points collected this round"),
        var("beat", "number", 0, "The round being played, from 0; a global keeps it across the restart"),
        var("deal", "number", 0, "The grid cell this round's first coin lands on; the others step from it"),
        module_setup(),
        module_input(),
        *scoring(),
        module_restart(),
    ]
    return {"name": "Game", "events": events, "sid": sid()}


if __name__ == "__main__":
    build_and_check()
