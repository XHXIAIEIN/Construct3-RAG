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
counts up, and when the last coin is gone the next round starts, one round a
beat of BEATS. Replace PALETTE with the game's colours by role, SHAPE_STYLE
with its outline and shadow, BEATS with its pacing, build_images(),
build_object_types(), build_layouts(), the module_*() functions of the
event sheet and the name and orientation in build_project(); keep the
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

# --- look -----------------------------------------------------------------------------
# Decided once, here, as named values: each colour by the role it plays, the text sizes, the
# font. Every image the generator draws, every label and every layer takes its colour from
# PALETTE by role, and write_png() stops the run on a pixel of any other colour, so a new
# object reuses the game's colours or names the role a new one plays. The official pixel-art
# examples keep to few colours with hard edges, 9 covering 95% of a project's opaque pixels
# and 35 its whole art at the median, and their text to one or two colours in two sizes
# (Construct3-RAG/docs/decisions/game-look-from-design-skills.md).
# The stand-in is a blockout: value carries the hierarchy, greys from the canvas to ink, and two
# accents for what must be noticed wherever the eye is. An accent loses to its background on
# value and shows by the ink outline round it, so shape() draws an accent with its outline, and
# check_palette() stops the run on greys that lose the ratios below
# (Construct3-RAG/docs/decisions/greybox-blockout.md). A game adds a third accent only for a role
# the two do not cover, a goal for instance.
PALETTE = {
    "canvas": (244, 244, 244),         # the backdrop's light cells; an opaque layer's fill
    "canvas_alt": (228, 228, 228),     # the backdrop's dark cells, at most 1.2:1 from canvas
    "solid": (128, 128, 128),          # structure, at least 3:1 on the backdrop; a bar's frame
    "dim": (90, 90, 90),               # a secondary label
    "ink": (28, 28, 28),               # the player, outlines, shadows, labels, a bar's fill
    "reward": (245, 197, 24),          # what the player collects: the coin
    "danger": (226, 59, 46),           # what hurts or is lost
    "flash": (255, 255, 255),          # the fill of an object for the instant it is hit
}
# The outline and the cast shadow of every image shape() draws, one switch for the game. They
# are drawn into the image: Construct's own effects have neither (none of the 89 of
# data/c3-schemas/_index.json does), and a third-party effect stays out of the template. The
# outline lies inside the shape's edge, so the shape keeps its size on the grid; the shadow is
# a hard copy of the shape, offset, and widens the image on its side. Being in the image, a
# shadow turns with a rotating sprite and darkens where two shadows overlap: draw such a sprite
# with shape(..., shadow=False). Values: Construct3-RAG/docs/decisions/greybox-blockout.md.
SHAPE_STYLE = {
    "outline": True,
    "outline_width": max(1, UNIT // 4),                      # px, inside the edge
    "outline_role": "ink",
    "shadow": True,
    "shadow_distance": round(0.027 * min(VIEW_W, VIEW_H)),   # px: 2.7% of the shorter side
    "shadow_angle": 45,                                      # degrees clockwise from rightwards: 90 is down
    "shadow_opacity": 0.5,
    "shadow_role": "ink",
}
# A hit shows as a colour for an instant: the shape's second frame, drawn by hit_frame() in the
# role below with the same outline and shadow, shown by hit_flash() for `seconds` of real time.
# Not the Flash behavior, which blinks the object's opacity: a colour set for 0.05 to 0.1 s is
# what the studios of Construct3-RAG/docs/decisions/published-game-visual-language.md use, white
# or danger. An object's colour in Construct multiplies its image, so it cannot turn a yellow
# shape white; a frame can.
HIT_FLASH = {"role": "flash", "seconds": 0.08}
# Squash and stretch: the size set at once to a share of the image's size, held, then tweened
# back to it. [author]'s recipes: a hit (merge), a landing and a jump; squash(obj, kind) shows
# one, hit() a hit's with its colour. Squash what is drawn, never the object that collides: a
# Platform or Solid object that grows sinks into the floor. The art is a second object pinned
# to an invisible collision mask, with its origin at its feet, shape(..., oy=1).
SQUASH = {
    "hit": {"width": 0.8, "height": 1.2, "hold": 0, "seconds": 0.25, "ease": "easeoutback"},
    "land": {"width": 1.2, "height": 0.8, "hold": 0, "seconds": 0.5, "ease": "easeoutelastic"},
    "jump": {"width": 0.7, "height": 1.3, "hold": 0.2, "seconds": 0.75, "ease": "easeoutelastic"},
}
# the behaviors whose object collides, by behaviorId; squash() stops the run on one of them
COLLIDING = ("Platform", "EightDir", "Physics", "Car", "solid", "jumpthru")
FONT = "Arial"                             # one font for every label
TEXT_SIZE = {"body": UNIT, "title": 2 * UNIT}   # a label is body, a banner title: two sizes
# 360 px high or less is pixel art: the project samples Nearest and scales by whole numbers,
# as every official example at that size samples and 116 of 159 scale (build_project()).
PIXEL_ART = UNIT == 8

# --- pacing ---------------------------------------------------------------------------
# The order in which the game asks things of the player, one beat at a time: a camera zone of a
# level, or in a one-screen game like this one a round, a wave or a window of time. A beat has a
# type, an intensity from 0 to 3, the mechanics it asks for alone or together, and for a rest
# what it holds; anything else in it is the game's own, here the coins a round deals. pace()
# stops the run on a curve that breaks the rules of Construct3-RAG/docs/decisions/
# greybox-blockout.md, *Pacing*, and prints the curve, one line a beat.
BEAT_TYPES = ("intro", "teach", "practice", "twist", "rest", "climax", "exit")


def beat(kind: str, intensity: int, mechanics: tuple = (), holds: str = "", **game) -> dict:
    """One beat of BEATS: beat("rest", 0, holds="pickup", coins=2)."""
    return {"type": kind, "intensity": intensity, "mechanics": list(mechanics), "holds": holds, **game}


BEATS = [
    beat("intro", 0, ["tap"], coins=1),
    beat("teach", 1, ["tap"], coins=3),
    beat("practice", 2, ["tap"], coins=6),
    beat("rest", 0, ["tap"], holds="pickup", coins=2),
    beat("climax", 3, ["tap"], coins=10),
    beat("exit", 0, ["tap"], coins=1),
]


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
    viewport: a HUD is read at a glance, so nothing on it hides behind anything else. A box
    wholly inside another is a layer on purpose, a bar's fill in its frame or an icon on its
    panel, and passes, unless the outer one is a label, which anything on top of it hides.
    Called on the UI layer in build_layouts(); a layer whose art is meant to stack is not
    passed."""
    boxes = []
    for inst in instances:
        w = inst.get("world")
        if w:
            left = w["x"] - w.get("originX", 0) * w["width"]
            top = w["y"] - w.get("originY", 0) * w["height"]
            boxes.append((inst["type"], left, top, left + w["width"], top + w["height"], "text" in inst.get("properties", {})))
    for kind, l, t, r, b, _ in boxes:
        if l < 0 or t < 0 or r > VIEW_W or b > VIEW_H:
            sys.exit(f"{where}: {kind} ({l:g},{t:g})-({r:g},{b:g}) reaches past the {VIEW_W}x{VIEW_H} viewport; "
                     f"place it with anchor() or row(), which keep it MARGIN inside the edge")

    def layered(inner: tuple, outer: tuple) -> bool:
        """inner wholly inside outer, and outer not a label: a label under another label is hidden."""
        return (not outer[5] and outer[1] <= inner[1] and outer[2] <= inner[2]
                and inner[3] <= outer[3] and inner[4] <= outer[4])

    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if layered(a, b) or layered(b, a):
                continue
            if min(a[3], b[3]) - max(a[1], b[1]) > 0 and min(a[4], b[4]) - max(a[2], b[2]) > 0:
                dy = math.ceil((a[4] + UNIT - b[2]) / UNIT)
                sys.exit(f"{where}: {a[0]} ({a[1]:g},{a[2]:g})-({a[3]:g},{a[4]:g}) overlaps {b[0]} "
                         f"({b[1]:g},{b[2]:g})-({b[3]:g},{b[4]:g}). Move {b[0]} down {dy} units: dy={dy} on its "
                         f"anchor(), row() or hud_text() call, on top of any dy it has, puts its top one unit under "
                         f"{a[0]}. Or size a label to its text with hud_text(), space repeated items with row(), "
                         f"or hold one of them to another edge.")


def pace(beats: list) -> list[str]:
    """Stops the generator on a curve of BEATS that breaks a rule of pacing, else returns it as one
    line a beat, which build_all() prints. The rules: the first beat is at 0; a beat of 2 or more
    is followed by a rest, which holds a pickup or a checkpoint, or the climax by the exit; a
    mechanic is taught alone in a teach before a beat combines it; one climax, in the last third;
    the last third more intense on average than the first."""
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
    """How far across, in px, the Platform behavior of `platform` (PLATFORM unless given) carries
    the player at full speed landing `rise` px higher than it took off, lower when negative; 0
    when it cannot rise that high. Its max speed times its air time, from the manual's units:
    jump strength v px/s, gravity g px/s², jump sustain s ms, so the jump rises v·s + v²/2g and
    stays in the air s + v/g + √(2(height - rise)/g). The approximation leaves out acceleration,
    the max fall speed and the frame steps: confirm the reach in a preview before trusting the
    bands of jump()."""
    p = (platform or PLATFORM)["Platform"]["properties"]
    v, g, s = p["jump-strength"], p["gravity"], p["jump-sustain"] / 1000
    height = v * s + v * v / (2 * g)
    if rise > height:
        return 0
    return p["max-speed"] * (s + v / g + math.sqrt(2 * (height - rise) / g))


def jump(gap: float, rise: float = 0, platform: dict | None = None) -> str:
    """How hard a gap of `gap` units is, landing `rise` units higher: "easy" up to half the
    player's reach, "medium", "hard" from eight tenths; the run stops past nine tenths, where
    the approximation of jump_reach() leaves no margin. Check every gap and step up of a level
    with it where build_layouts() places them."""
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
    """Stops the run when PALETTE's greys lose the ratios the look stands on (WCAG 2.2 contrast):
    the backdrop's two at most 1.2:1, so the checker reads as texture and not as things;
    structure at least 3:1 on the darker of them, so it shows without an outline (1.4.11)."""
    ratio = contrast(rgb("canvas"), rgb("canvas_alt"))
    if ratio > 1.2:
        sys.exit(f"PALETTE: canvas {PALETTE['canvas']} and canvas_alt {PALETTE['canvas_alt']} are {ratio:.2f}:1; the "
                 f"backdrop's two greys stay at most 1.2:1, so the checker reads as texture, not as things. Bring "
                 f"canvas_alt nearer canvas")
    ratio = contrast(rgb("solid"), rgb("canvas_alt"))
    if ratio < 3:
        sys.exit(f"PALETTE: solid {PALETTE['solid']} on canvas_alt {PALETTE['canvas_alt']} reads {ratio:.2f}:1; "
                 f"structure needs 3:1 on the backdrop to show without an outline (WCAG 2.2, 1.4.11). Darken solid")


def alphas() -> set[int]:
    """The alpha values a drawn image may hold: clear, opaque, and the shadow of SHAPE_STYLE."""
    return {0, 255, round(255 * SHAPE_STYLE["shadow_opacity"])}


def write_png(rel: str, w: int, h: int, pixel, painted: bool = False) -> None:
    """images/<rel> from an RGBA function of (x, y). Every pixel that shows is a colour of
    PALETTE, its alpha one of alphas(); painted=True is for a picture meant to hold its own
    colours and soft edges, a gradient or a photograph, and skips both checks. A clear pixel
    is written as (0, 0, 0, 0) whatever the function returns: a colour hidden under alpha 0
    bleeds into the edge when the image is scaled with linear sampling."""
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
    """The 16x16 images of bar_types(), one role of PALETTE each; with `caps` a 2 px border in
    "ink", the margin a 9-patch keeps at any length. A painted fill replaces the fill's
    image with the painting, drawn with painted=True."""
    for name, role in ((frame_name, frame_role), (fill_name, fill_role)):
        def pixel(x, y, role=role):
            edge = caps and (x < 2 or y < 2 or x >= 14 or y >= 14)
            return (*rgb("ink" if edge else role), 255)

        write_png(f"{name.lower()}.png", 16, 16, pixel)


SHAPES = ("rect", "circle", "triangle")
FRAMES: dict[str, dict] = {}               # the frame of each image shape() drew, by file name
PADS: dict[str, tuple[int, int]] = {}      # where the shape starts inside that image, past its shadow
DRAWN_AS: dict[str, tuple] = {}            # the arguments each image was drawn with, for hit_frame()


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


def shape(rel: str, kind: str, w: int, h: int, role: str, ox: float = 0.5, oy: float = 0.5,
          outline: bool | None = None, shadow: bool | None = None) -> dict:
    """images/<rel>: a flat `kind` of SHAPES, w x h px in whole units, in the colour of `role`, with the outline
    and shadow of SHAPE_STYLE unless outline or shadow says otherwise for this image. Returns
    the frame for sprite_type(), kept in FRAMES[rel] as well: its origin is (ox, oy) of the
    shape, its collision polygon the shape's, and its size the image's, the shadow included,
    which is the size an instance of it is written at (drawn(rel))."""
    if kind not in SHAPES:
        sys.exit(f"{rel}: {kind!r} is no shape; shape() draws {', '.join(SHAPES)}")
    if w % UNIT or h % UNIT:
        sys.exit(f"{rel}: {w}x{h} is not whole units of {UNIT} px; a shape covers whole cells of the grid, "
                 f"so give it units(n) or TOUCH, {math.ceil(w / UNIT) * UNIT}x{math.ceil(h / UNIT) * UNIT} here")
    style = SHAPE_STYLE
    edge = style["outline_width"] if (style["outline"] if outline is None else outline) else 0
    if not edge and accent(role):
        sys.exit(f"{rel}: {role} is an accent, which loses to the backdrop on value and shows by the outline round "
                 f"it; draw it with its outline, or in a grey role")
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
    corners = {"rect": [(0, 0), (1, 0), (1, 1), (0, 1)], "triangle": [(0.5, 0), (1, 1), (0, 1)],
               "circle": [(0.5 + math.cos(a) / 2, 0.5 + math.sin(a) / 2)
                          for a in (i * math.pi / 8 for i in range(16))]}[kind]
    poly = [round(v, 4) for cx, cy in corners for v in ((left + cx * w) / iw, (top + cy * h) / ih)]
    FRAMES[rel] = frame(iw, ih, (left + ox * w) / iw, (top + oy * h) / ih, poly)
    PADS[rel] = (left, top)
    DRAWN_AS[rel] = (kind, w, h, ox, oy, outline, shadow)
    return FRAMES[rel]


def hit_frame(rel: str) -> dict:
    """The hit frame of the shape drawn as images/<rel>, "coin-default-000.png": the same shape,
    outline and shadow, filled in HIT_FLASH's role, drawn as the next frame's file and tagged
    "hit". Put it after the shape's frame in the animation; hit_flash() shows it."""
    if rel not in DRAWN_AS or not rel.endswith("-000.png"):
        sys.exit(f"hit_frame({rel!r}): draw the frame first with shape({rel!r}, ...), named <type>-<animation>-000.png")
    kind, w, h, ox, oy, outline, shadow = DRAWN_AS[rel]
    hit = rel[:-len("000.png")] + "001.png"
    f = shape(hit, kind, w, h, HIT_FLASH["role"], ox, oy, outline, shadow)
    f["tag"] = "hit"
    return f


def drawn(rel: str) -> dict:
    """The frame shape() drew as images/<rel>: sprite_type() takes it, and an instance of it is
    drawn(rel)["width"] x drawn(rel)["height"]."""
    if rel not in FRAMES:
        sys.exit(f"images/{rel} was not drawn: draw it with shape({rel!r}, ...) in build_images(), "
                 f"which runs before build_object_types()")
    return FRAMES[rel]


# Objects are flat; an area or an edge carries a pattern, a Tiled Background, which repeats its
# image at any size without stretching it. Four patterns, each two roles of PALETTE and one job.
# A red triangle is one hazard, a red-striped area a hazardous region; a yellow circle is a
# pickup, a yellow-striped strip a door or a plate.
PATTERNS = {
    "checker": ("canvas", "canvas_alt"),   # empty space, and the ruler: the backdrop only
    "low": ("solid", "dim"),               # a surface special and harmless: a one-way platform, a safe zone
    "caution": ("reward", "ink"),          # what moves, triggers or blocks on a condition: a door, a plate
    "hazard": ("danger", "ink"),           # an area that hurts: lava, a kill zone
}
PATTERN_OF: dict[str, str] = {}            # the pattern of each type pattern() drew, by type name
TILES: dict[str, int] = {}                 # its tile in px, which tiledbg_inst() aligns to the layout


def pattern(name: str, kind: str) -> None:
    """images/<name lower>.png: a one-unit tile of the pattern `kind` of PATTERNS for the Tiled
    Background type `name`, pattern_type(name). The checker is cells of UNIT / 2, two to a unit,
    so the backdrop counts units; the stripes run at 45 degrees, a pair to the unit, and join
    across tiles."""
    if kind not in PATTERNS:
        sys.exit(f"pattern({name!r}, {kind!r}): the patterns are {', '.join(PATTERNS)}")
    a, b = PATTERNS[kind]
    half = UNIT // 2
    if kind == "checker":
        def pixel(x, y):
            return (*rgb(a if (x // half + y // half) % 2 == 0 else b), 255)
    else:
        def pixel(x, y):
            return (*rgb(a if (x + y) % UNIT < half else b), 255)
    write_png(f"{name.lower()}.png", UNIT, UNIT, pixel)
    PATTERN_OF[name], TILES[name] = kind, UNIT


def build_images() -> None:
    pattern("Backdrop", "checker")
    shape("coin-default-000.png", "circle", COIN_SIZE, COIN_SIZE, "reward")
    hit_frame("coin-default-000.png")


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


def hit_flash(obj: str) -> list:
    """The actions that show obj's hit frame for HIT_FLASH["seconds"], then its rest frame 0.
    The wait is in real time, so slow motion does not stretch the flash. Put them last in a
    block: the actions after a wait run once it is over."""
    return [act("set-animation-frame", obj, {"frame-number": q("hit")}),
            wait(str(HIT_FLASH["seconds"]), use_timescale=False),
            act("set-animation-frame", obj, {"frame-number": "0"})]


SQUASHED: set[str] = set()                 # the objects squash() acts on, checked in build_all()


def squash(obj: str, kind: str, tween: str = "Tween") -> list:
    """The actions of a squash of SQUASH, "hit", "land" or "jump": stop the squash obj is in,
    set its size to the kind's share of its image's size, hold it, and tween it back under the
    tag "squash". The rest size is the image's, the size shape_inst() writes. obj is the art,
    not the object that collides, and needs the Tween behavior, named `tween` on it; a hold
    waits, so the actions go last in their block.

        event("Squash the art on landing", [cond("on-landed", "Player", beh="Platform")],
              squash("PlayerArt", "land"))"""
    if kind not in SQUASH:
        sys.exit(f"squash({obj!r}, {kind!r}): the kinds are {', '.join(SQUASH)}; add one to SQUASH")
    k = SQUASH[kind]
    SQUASHED.add(obj)
    return [act("stop-tweens", obj, {"tags": q("squash")}, beh=tween),
            act("set-size", obj, {"width": f"Self.ImageWidth * {k['width']:g}",
                                  "height": f"Self.ImageHeight * {k['height']:g}"}),
            *([wait(f"{k['hold']:g}", use_timescale=False)] if k["hold"] else []),
            tween2(obj, "squash", "size", "Self.ImageWidth", "Self.ImageHeight", f"{k['seconds']:g}",
                   k["ease"], beh=tween)]


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
    """A hit: the squash of SQUASH["hit"], then the colour flash, whose wait makes it last in its block."""
    return [*squash(obj, "hit", tween), *hit_flash(obj)]


def grid_random(lo: int, hi: int) -> str:
    """An expression for a random whole-UNIT position from lo to hi px, both on the grid: an
    object created at runtime starts on the grid like one placed in a layout."""
    return f"{UNIT} * floor(random({lo // UNIT}, {hi // UNIT + 1}))"


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
        # Restart layout keeps every global variable: a value the round starts from is set here,
        # before any text shows it.
        event("Empty the score and deal this round's coins",
              [on_start()], [set_var("score", "0"), set_text("ScoreText", q("Score: 0"))], children=[
                  block([for_loop("i", "0", f"int(tokenat(ROUND_COINS, beat, {q(',')})) - 1")], [
                      create("Coin", "Game", f"{grid_random(0, VIEW_W - COIN_SIZE)} + {COIN_SIZE // 2}",
                             f"{grid_random(snap(1.5 * COIN_SIZE), VIEW_H - COIN_SIZE)} + {COIN_SIZE // 2}"),
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
    """What the groups call: a custom action for what acts on the caller's picked
    instances, a function for a value or for logic that picks its own."""
    return [
        *procedure("Score the coin, show the hit, then shrink it away", custom_action("Coin", "Collect", steps(
            ("Score it, then show the hit", [call("AddScore", "Coin.value"), *hit("Coin")]),
            ("Shrink it away once the punch is over", [
                wait(f"{SQUASH['hit']['seconds'] - HIT_FLASH['seconds']:g}", use_timescale=False),
                tween2("Coin", "collect", "size", "0", "0", "0.25", "easeinback", destroy=True)]),
        ))),
        *procedure("Add points and show the score", func("AddScore", [
            add_var("score", "points"),
            set_text("ScoreText", q("Score: ") + " & score"),
        ], params=[param("points", "number", 0)])),
    ]


def module_restart() -> dict:
    return module("Restart", events=[
        event("Start the next round when the last coin is gone",
              [cmp2("Coin.Count", EQ, "0"), trigger_once()],
              [set_var("beat", f"(beat + 1) % tokencount(ROUND_COINS, {q(',')})"), wait("1"), restart_layout()]),
    ])


def build_event_sheet() -> dict:
    """What the sheet covers, the constants under Settings, the state the groups share,
    then the groups; a variable one group owns is declared in that module instead."""
    events = [
        comment("Coins. Tap a coin to collect it; when the last one is gone the next round starts.\n"
                "The touched coin is the trigger's pick: Collect runs on it and nothing else"),
        comment("Settings"),
        var("ROUND_COINS", "string", ",".join(str(b["coins"]) for b in BEATS),
            "Coins dealt in each round, one round a beat of the generator's BEATS", const=True),
        comment("Gameplay variables"),
        var("score", "number", 0, "Points collected this round"),
        var("beat", "number", 0, "The round being played, from 0; a global keeps it across the restart"),
        module_setup(),
        module_input(),
        *scoring(),
        module_restart(),
    ]
    return {"name": "Game", "events": events, "sid": sid()}


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
    """Tiled Background ("TiledBg") or 9-patch ("NinePatch"): one image, images/<name lower>.png,
    no animations. The keys are the editor's (berry-harvester ProgressBar, car-selection-screen
    StatusBar)."""
    image = {"width": w, "height": h, "originX": ox, "originY": oy, "originalSource": "", "exportFormat": "lossless",
             "exportQuality": 0.8, "imageSpriteId": image_id(), "useCollisionPoly": True}
    if plugin_id == "TiledBg":
        image["tag"] = ""
    return {"name": name, "plugin-id": plugin_id, "sid": sid(), "isGlobal": False, "instanceVariables": list(ivars),
            "behaviorTypes": list(behaviors), "effectTypes": [], "image": image}


def bar_types(frame_name: str, fill_name: str, caps: bool = False, tween: bool = True) -> dict:
    """The two object types of a bar for hud_bar(): Tiled Backgrounds of a 16x16 image each,
    which Set width repeats and never stretches, so a painted fill is revealed; 9-patches when
    `caps`, whose corners keep their size at any length. The fill carries Tween for
    tween_width(). Images: bar_images() in build_images()."""
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
    """Object types whose instances are created, destroyed and picked together, a
    tank base with its turret. A container has no file of its own: it is a row of
    project.c3proj's "containers", and its members are object types, not families."""
    return {"members": list(members)}


def build_object_types() -> tuple[dict, dict, list]:
    types = {
        "Coin": sprite_type("Coin", [animation("Default", [drawn("coin-default-000.png"), drawn("coin-default-001.png")])],
                            ivars=[ivar_def("value", "number", "Points it is worth."),
                                   ivar_def("kind", "string", "Which coin: \"gold\" or \"silver\".")],
                            behaviors=[beh_def("Tween")]),
        "Backdrop": pattern_type("Backdrop"),
        "ScoreText": text_type("ScoreText"),
        "Touch": single_global_type("Touch", "Touch", {"use-mouse-input": True}),
    }
    families = {}
    containers = []
    return types, families, containers


# --- layouts -------------------------------------------------------------------------------
def layer(name: str, bg: str | None = None, transparent: bool = True, parallax: float = 1) -> dict:
    """parallax 0 for a HUD layer that stays put while the layout scrolls. bg is the role of
    PALETTE an opaque layer fills with, "canvas" unless named; a transparent layer keeps
    the editor's white, which it never draws."""
    fill = rgb(bg or "canvas") if bg or not transparent else (255, 255, 255)
    return {"name": name, "overriden": 0, "subLayers": [], "instances": [], "sid": sid(), "effectTypes": [],
            "isInitiallyVisible": True, "isInitiallyInteractive": True, "isHTMLElementsLayer": False,
            "color": [1, 1, 1, 1], "backgroundColor": rgba(fill), "isTransparent": transparent,
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


def shape_inst(otype: str, rel: str, col: int, row: int, ivars=None, behaviors=None,
               collisions: bool = True) -> dict:
    """An instance of the shape shape() drew as images/<rel>, its top-left corner on the grid
    cell (col, row): the shape covers whole cells, the shadow hangs off it, and the instance
    is written at the image's size with the frame's origin, as the editor shows it."""
    f, (left, top) = drawn(rel), PADS[rel]
    x = col * UNIT - left + f["originX"] * f["width"]
    y = row * UNIT - top + f["originY"] * f["height"]
    return instance(otype, {"initially-visible": True, "initial-animation": "Default", "initial-frame": 0,
                            "enable-collisions": collisions, "live-preview": False},
                    world(x, y, f["width"], f["height"], f["originX"], f["originY"]), ivars, behaviors)


def on_grid(instances: list, where: str) -> None:
    """Stops the generator when an instance of a world layer does not start on the grid: its
    box's left and top, or its shape's past a shadow on the left or top, are whole UNITs.
    The HUD is held to the viewport's edges by anchor() instead and is not passed; a rotated
    instance is skipped, its box being no longer the one written."""
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
    """The contrast ratio of two RGB colours, from 1 to 21 (WCAG 2.2, relative luminance)."""
    def luminance(rgb_: tuple) -> float:
        lin = [c / 255 / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb_]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def readable(otype: str, color: str, on: str, size: float) -> None:
    """Stops the run when a label in `color` does not read on `on`, both roles of PALETTE: text
    needs 4.5:1 against what is behind it, 3:1 from TEXT_SIZE["title"] up (WCAG 2.2, 1.4.3)."""
    need = 3 if size >= TEXT_SIZE["title"] else 4.5
    ratio = contrast(rgb(color), rgb(on))
    if ratio < need:
        fits = [role for role in PALETTE if role != on and contrast(PALETTE[role], PALETTE[on]) >= need]
        sys.exit(f"{otype}: {color} {PALETTE[color]} on {on} {PALETTE[on]} reads {ratio:.1f}:1; text of size "
                 f"{size:g} needs {need:g}:1. Roles that read on {on}: {', '.join(fits) or 'none'}; or put the "
                 f"label on a panel whose role it reads on and pass it as on=")


def text_inst(otype: str, text: str, x: float, y: float, w: float, h: float, size: float | None = None,
              halign: str = "left", bold: bool = False, color: str = "ink", on: str = "canvas_alt",
              ivars=None, behaviors=None) -> dict:
    """A Text in FONT at a size of TEXT_SIZE, its colour the role `color` of PALETTE; `on` is
    the role of what lies behind it, which it must read on (readable()): the backdrop's darker
    cell unless a panel is behind it."""
    size = size or TEXT_SIZE["body"]
    readable(otype, color, on, size)
    return instance(otype, {"text": text, "enable-bbcode": False, "font": FONT, "size": size, "line-height": 0,
                            "bold": bold, "italic": False, "color": rgba(rgb(color)), "horizontal-alignment": halign,
                            "vertical-alignment": "center", "wrapping": "word", "text-direction": "ltr",
                            "icon-set": -1, "initially-visible": True, "origin": "top-left", "read-aloud": False},
                    world(x, y, w, h, 0, 0), ivars, behaviors)


def hud_text(otype: str, text: str, where: str, size: float | None = None, longest: str | None = None,
             bold: bool = True, color: str = "ink", on: str = "canvas_alt", dx: float = 0, dy: float = 0,
             ivars=None, behaviors=None) -> dict:
    """A HUD label held against an edge or corner by anchor(). Its box is as wide as its
    longest text (about 0.6 em a character, rounded up to a unit) and the text is aligned to
    the side the box hangs on, so a right-hand label grows leftwards and two labels on one
    edge never meet. `longest` is the widest text the label shows at runtime, "Score: 999"
    for a label that starts as "Score: 0". The size is TEXT_SIZE["body"] unless a banner
    asks for TEXT_SIZE["title"]; color and on are roles of PALETTE, as for text_inst()."""
    size = size or TEXT_SIZE["body"]
    w = math.ceil(len(longest or text) * size * 0.6 / UNIT) * UNIT
    h = math.ceil(size * 1.5 / UNIT) * UNIT
    halign = {"left": "left", "middle": "center", "right": "right"}[sides(where)[1]]
    x, y = anchor(where, w, h, 0, 0, dx, dy)
    return text_inst(otype, text, x, y, w, h, size=size, halign=halign, bold=bold, color=color, on=on,
                     ivars=ivars, behaviors=behaviors)


def origin_name(ox: float, oy: float) -> str:
    """The "origin" property of a Tiled Background or 9-patch for an (ox, oy) origin."""
    v = {0: "top", 0.5: "", 1: "bottom"}[oy]
    h = {0: "left", 0.5: "", 1: "right"}[ox]
    return "-".join(p for p in (v, h) if p) or "center"


def tiledbg_inst(otype: str, x: float, y: float, w: float, h: float, ox: float = 0, oy: float = 0.5,
                 ivars=None, behaviors=None) -> dict:
    """A Tiled Background instance; the properties are the editor's (berry-harvester ProgressBar).
    A pattern of pattern() is offset by minus its box's corner, modulo its tile: tiling starts at
    the instance's own corner, the runtime shifts the image by the offset, and so every piece of
    one pattern lines up with the layout and two of them meet without a seam."""
    tile = TILES.get(otype)
    off_x, off_y = (round(-(x - ox * w)) % tile, round(-(y - oy * h)) % tile) if tile else (0, 0)
    return instance(otype, {"initially-visible": True, "origin": origin_name(ox, oy), "wrap-horizontal": "repeat",
                            "wrap-vertical": "repeat", "image-offset-x": off_x, "image-offset-y": off_y, "image-scale-x": 1,
                            "image-scale-y": 1, "image-angle": 0, "enable-tile-randomization": False, "x-random": 1,
                            "y-random": 1, "angle-random": 1, "blend-margin-x": 0.1, "blend-margin-y": 0.1},
                    world(x, y, w, h, ox, oy), ivars, behaviors)


def area(otype: str, col: int, row: int, cols: int, rows: int, ivars=None, behaviors=None) -> dict:
    """An area or an edge in the pattern type `otype` of pattern_type(), covering cols x rows grid
    cells from cell (col, row): a one-way platform in low stripes, a door in caution stripes, lava
    in hazard stripes. The high-contrast stripes cover strips and small zones, their shorter side
    a quarter of the viewport's at most; the checker is the backdrop's alone, backdrop()."""
    kind = PATTERN_OF.get(otype)
    if not kind:
        sys.exit(f"area({otype!r}): not a pattern; draw it with pattern({otype!r}, kind) in build_images() and give "
                 f"it pattern_type({otype!r}) in build_object_types()")
    if kind == "checker":
        sys.exit(f"area({otype!r}): the checker is empty space, the backdrop alone; place it with backdrop({otype!r})")
    most = min(VIEW_W, VIEW_H) // 4 // UNIT
    if kind in ("caution", "hazard") and min(cols, rows) > most:
        sys.exit(f"area({otype!r}): {cols}x{rows} cells of {kind} stripes; these cover strips and small zones, never "
                 f"a backdrop, so keep the shorter side to {most} cells, a quarter of the viewport's")
    return tiledbg_inst(otype, units(col), units(row), units(cols), units(rows), 0, 0, ivars, behaviors)


def backdrop(otype: str, width: int = VIEW_W, height: int = VIEW_H) -> dict:
    """The checker of pattern `otype` behind everything: one Tiled Background from the layout's
    origin over `width` x `height`, the layout's size, on a layer at parallax 1, so its cells are
    the ruler that sizes and distances are counted in. It replaces a grid: never both."""
    if PATTERN_OF.get(otype) != "checker":
        sys.exit(f"backdrop({otype!r}): the backdrop is the checker; draw it with pattern({otype!r}, \"checker\")")
    return tiledbg_inst(otype, 0, 0, width, height, 0, 0)


def ninepatch_inst(otype: str, x: float, y: float, w: float, h: float, ox: float = 0, oy: float = 0.5, margin: int = 2,
                   edges: str = "stretch", fill: str = "stretch", ivars=None, behaviors=None) -> dict:
    """A 9-patch instance; `margin` is the border its corners keep, in image pixels (car-selection-screen StatusBar)."""
    return instance(otype, {"left-margin": margin, "right-margin": margin, "top-margin": margin, "bottom-margin": margin,
                            "edges": edges, "fill": fill, "initially-visible": True, "origin": origin_name(ox, oy),
                            "seams": "overlap"},
                    world(x, y, w, h, ox, oy), ivars, behaviors)


def hud_bar(frame_name: str, fill_name: str, where: str, length: float, height: float = 0, inset: float = 2,
            caps: bool = False, dx: float = 0, dy: float = 0) -> tuple[dict, dict]:
    """A bar held to an edge or corner by anchor(): a frame `length` px wide and, `inset` px
    inside it, a fill with its origin on the left edge, so that a width set from a value grows
    it rightwards and never past the frame. Types from bar_types(), images from bar_images(),
    both with the same `caps`. The sheet sets the fill from the value, in the one place the
    value changes:
        set_width(fill, bar_width("hp", "HP_MAX", HP_BAR_LENGTH))
    or slides it there with tween_width(); HP_BAR_LENGTH = length - 2 * inset is a constant of
    the sheet. A count of icons is a bar too: the fill `count * icon` wide over a frame that
    shows the empty icon. Returns (frame instance, fill instance)."""
    height = height or units(1)
    cx, cy = anchor(where, length, height, 0.5, 0.5, dx, dy)
    make = ninepatch_inst if caps else tiledbg_inst
    frame_inst = make(frame_name, cx, cy, length, height, 0.5, 0.5)
    fill_inst = make(fill_name, cx - length / 2 + inset, cy, length - 2 * inset, height - 2 * inset, 0, 0.5,
                     behaviors=dict(TWEEN))
    return frame_inst, fill_inst


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
        layer("Background", transparent=False),
        layer("Game"),
        layer("UI", parallax=0),
    ], sheet="Game")
    # The checker behind everything is the ruler: two cells a unit. An area or an edge in a
    # pattern is area(type, col, row, cols, rows) on the Game layer.
    game["layers"][0]["instances"].append(backdrop("Backdrop"))
    # The HUD hangs on the edges, MARGIN inside them: a label by hud_text(), repeated items by
    # row(), anything else by anchor(); the middle of the screen is the game's. no_overlap()
    # stops the run when two HUD boxes meet or one leaves the viewport. A label is
    # TEXT_SIZE["body"] in rgb("ink"), a banner TEXT_SIZE["title"], and hud_text() stops the
    # run on a colour that does not read on what is behind it.
    ui = game["layers"][2]["instances"]
    ui.append(hud_text("ScoreText", "Score: 0", "top-left", longest="Score: 999"))
    # A value shown as a bar: ui.extend(hud_bar("HpFrame", "HpFill", "top-left", units(12), dy=3)), its
    # types from bar_types() and images from bar_images(), and the sheet sets the fill with
    # set_width("HpFill", bar_width("hp", "HP_MAX", HP_BAR_LENGTH)) or tween_width().
    no_overlap(ui)
    # Everything outside the HUD starts on the grid: a shape by shape_inst() on a cell, one
    # created at runtime at grid_random(); on_grid() stops the run on an instance that does not.
    on_grid(game["layers"][1]["instances"], "layer Game")
    # Runtime-created objects are copied from a template instance; keep those in a layout that never runs.
    objects = layout("Objects", [layer("Objects")], sheet=None)
    objects["layers"][0]["instances"].append(
        shape_inst("Coin", "coin-default-000.png", MARGIN // UNIT, MARGIN // UNIT,
                   ivars={"value": 1, "kind": "gold"}, behaviors=dict(TWEEN)))
    on_grid(objects["layers"][0]["instances"], "layout Objects")
    return {"Game": game, "Objects": objects}


# --- project.c3proj -------------------------------------------------------------------------
ADDON_NAMES = {"TiledBg": "Tiled Background", "NinePatch": "9-patch", "Spritefont2": "Sprite font", "EightDir": "8 Direction",
               "Sin": "Sine", "DragnDrop": "Drag & Drop", "ScrollTo": "Scroll To", "MoveTo": "Move To", "LOS": "Line of sight",
               "destroy": "Destroy outside layout", "bound": "Bound to layout", "solid": "Solid", "wrap": "Wrap",
               "jumpthru": "Jump-thru", "AdvancedRandom": "Advanced Random", "LocalStorage": "Local Storage"}


def used_addons(types: dict, families: dict) -> list:
    """project.c3proj's usedAddons, from the plugins and behaviors the types and families use:
    the editor refuses a type whose plugin is not listed, and a type added later is then
    listed by this rerun. The name is the editor's display name for the ids it knows, the
    id otherwise."""
    plugins, behaviors = [], []
    for t in list(types.values()) + list(families.values()):
        if t["plugin-id"] not in plugins:
            plugins.append(t["plugin-id"])
        for b in t.get("behaviorTypes", []):
            if b["behaviorId"] not in behaviors:
                behaviors.append(b["behaviorId"])
    return ([{"type": "plugin", "id": i, "name": ADDON_NAMES.get(i, i), "author": "Scirra", "bundled": False} for i in plugins]
            + [{"type": "behavior", "id": i, "name": ADDON_NAMES.get(i, i), "author": "Scirra", "bundled": False} for i in behaviors])
# What the editor reads out of project.c3proj before it opens a single file of
# the project, and asserts as it reads: a project that lacks one of these opens
# as "TypeError: expected string", which names neither the key nor the file.
# The editor writes them into every project it saves, so they are filled in only
# when the folder was not saved by the editor; savedWithRelease decides where an
# object type is read from and is left as the editor wrote it.
PROJECT_DEFAULTS = {"projectFormatVersion": 1, "savedWithRelease": 49502, "runtime": "c3",
                    "useWorker": "auto", "bundleAddons": False, "functionsName": "Functions",
                    "autosaveData": None}
PROPERTY_DEFAULTS = {"description": "", "version": "1.0.0.0", "autoIncrementVersion": False,
                     "author": "", "authorEmail": "", "authorWebsite": "", "appId": "",
                     "pixelRounding": False, "zAxisScale": "regular", "fov": 0.7853981633974483,
                     "useLoaderLayout": False, "fullscreenMode": "letterbox-scale",
                     "fullscreenQuality": "high", "viewportFit": "auto",
                     "backgroundColor": [0, 0, 0, 0], "splashColor": [1, 1, 1, 0],
                     "useThemeColor": False, "themeColor": [1, 1, 1, 0], "webgpu": "auto",
                     "multitexturing": "auto", "gpuPreference": "high-performance",
                     "framerateMode": "vsync", "fixedFramerate": 30, "sampling": "trilinear",
                     "downscaling": "medium", "renderingMode": "auto",
                     "anisotropicFiltering": "auto", "zNear": 10, "zFar": 100000,
                     "maxSpriteSheetSize": 2048, "loaderStyle": "splash", "preloadSounds": True,
                     "uidAllocationMode": "increment", "cordovaiOSScheme": "app",
                     "cordovaAndroidScheme": "https", "exportFileStructure": "folders",
                     "scriptsType": "module"}


def build_project(existing: dict, types: dict, families: dict, containers: list, layouts: dict,
                  sheets: list) -> dict:
    """Only the keys this script owns change; uniqueId, icons, scripts and the
    properties the project already has stay."""
    p = dict(existing)
    for key, value in PROJECT_DEFAULTS.items():
        p.setdefault(key, value)
    p["properties"] = dict(p.get("properties") or {})
    for key, value in PROPERTY_DEFAULTS.items():
        p["properties"].setdefault(key, value)
    p["name"] = "Coins"
    p["usedAddons"] = used_addons(types, families)
    p["objectTypes"] = {"items": list(types), "subfolders": []}
    p["families"] = {"items": list(families), "subfolders": []}
    p["containers"] = list(containers)
    p["layouts"] = {"items": list(layouts), "subfolders": []}
    p["eventSheets"] = {"items": sheets, "subfolders": []}
    p["viewportWidth"] = VIEW_W
    p["viewportHeight"] = VIEW_H
    if PIXEL_ART:
        # The viewport decides the art: pixel art sampled Nearest stays crisp, and scaled by
        # whole numbers every pixel stays square.
        p["properties"]["sampling"] = "nearest"
        p["properties"]["fullscreenMode"] = "letterbox-integer-scale"
    p["firstLayout"] = "Game"
    p["properties"]["orientations"] = "portrait"
    return p


def build_all() -> None:
    c3proj = ROOT / "project.c3proj"
    if not c3proj.exists():
        sys.exit(
            f"{c3proj} not found: create the project in the editor and save it as a folder first")
    check_palette()
    for line in pace(BEATS):
        print(line)
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
    squash_the_art(types, families)
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
