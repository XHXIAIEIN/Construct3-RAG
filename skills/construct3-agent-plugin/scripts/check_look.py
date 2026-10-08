"""Confirm the strict rules of assets/look-manifest.json on a project's files.

    python scripts/check_look.py [--project FOLDER] [--painted FILE ...] [--unit PX]

Run it after the generator's own check ends with ok:, on a project built from
assets/build_project.py, whoever edited the generator. It reads the images,
layouts and event sheets the editor would load and checks:

  alpha.pure            a clear pixel holds no colour, and the project's images
                        hold one alpha value between clear and opaque, the
                        shadow's; a painting meant to keep soft edges is
                        named with --painted, and the art prepare_art.py
                        wrote is known by the mark it leaves in the file
  grid.world-placement  an instance of a world layer starts on the grid: its
                        box's left or right edge and top or bottom edge are
                        whole UNITs, the other side being the shadow's
  grid.runtime-spawn    an object created at runtime is not placed at a raw
                        random(): the template's grid_random() rounds it
  motion.hit            no object type or family has the Flash behavior: a
                        hit shows as a colour, the template's hit_frame() and
                        hit_flash()
  motion.squash-art     a squash, a size set to a share of the image's size,
                        acts on the drawn art, not on an object whose
                        behavior collides
  screen.fill           a warning, not a finding: the project fills the
                        screen, Scale outer or Integer scale outer, not a
                        Letterbox mode, which shows bars

UNIT is 8 for a viewport 360 px high or less, else 32, as in the template.
A layer at parallax 0 is the HUD, held to the viewport's edges, and is not
checked; neither is a rotated instance. Whether the look works is the user's
call on a screenshot.

Exit 0: the last line starts with ok:. Exit 1: findings, or no project.
"""
import fnmatch
import json
import re
import struct
import sys
from pathlib import Path

import c3project as c3


def painted_mark(path: Path) -> bool:
    """Whether the PNG carries the text chunk scripts/prepare_art.py writes into a painting."""
    data = path.read_bytes()
    pos = 8
    while pos + 8 <= len(data):
        n, tag = struct.unpack(">I", data[pos:pos + 4])[0], data[pos + 4:pos + 8]
        if tag == b"tEXt" and data[pos + 8:pos + 8 + n].startswith(b"c3-art\0"):
            return True
        if tag == b"IDAT":
            return False
        pos += 12 + n
    return False


def check_alpha(root: Path, painted: list[str], out: list[str]) -> int:
    """alpha.pure over images/; returns how many images were read."""
    partial: dict[str, dict[int, tuple[int, int]]] = {}      # image: {alpha: first (x, y)}
    read = 0
    for png in sorted((root / "images").rglob("*.png")):
        rel = png.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(png.name, p) or fnmatch.fnmatch(rel, p) for p in painted):
            continue
        img = c3.png_rgba(png.read_bytes())
        if img is None:
            out.append(f"alpha.pure: {rel} is not an 8-bit non-interlaced PNG; write it as the template's "
                       f"write_png() does, or name it with --painted")
            continue
        read += 1
        w, _, pixels = img
        hidden = [i for i, p in enumerate(pixels) if p[3] == 0 and p[:3] != (0, 0, 0)]
        if hidden:
            out.append(f"alpha.pure: {rel} has {len(hidden)} clear pixels that hold a colour, the first at "
                       f"({hidden[0] % w},{hidden[0] // w}); write a clear pixel as (0, 0, 0, 0)")
        if painted_mark(png):       # art from prepare_art.py keeps the soft edges of its picture
            continue
        for i, p in enumerate(pixels):
            if 0 < p[3] < 255:
                partial.setdefault(rel, {}).setdefault(p[3], (i % w, i // w))
    # The shadow is the alpha the most images hold; any other is a soft edge.
    held = [a for alphas in partial.values() for a in alphas]
    shadow = max(set(held), key=held.count) if held else None
    for rel, alphas in partial.items():
        others = sorted(a for a in alphas if a != shadow)
        if others:
            x, y = alphas[others[0]]
            more = f" and {len(others) - 1} more values" if len(others) > 1 else ""
            out.append(f"alpha.pure: {rel} has alpha {others[0]} at ({x},{y}){more}; the project's shadow is "
                       f"{shadow}, and a drawn image is clear, opaque or the shadow. A painting meant to keep soft "
                       f"edges: --painted {Path(rel).name}")
    return read


def on_grid(v: float, unit: int) -> bool:
    return abs(v / unit - round(v / unit)) < 1e-6


def check_grid(root: Path, unit: int, out: list[str]) -> int:
    """grid.world-placement over layouts/; returns how many instances were checked."""
    checked = 0
    for path in sorted((root / "layouts").rglob("*.json")):
        if path.name.endswith(".uistate.json"):
            continue
        layout = c3.load(path)
        for layer, _ in c3.layers_of(layout.get("layers", [])):
            if layer.get("parallaxX", 1) == 0 and layer.get("parallaxY", 1) == 0:
                continue
            for inst in layer.get("instances", []):
                w = inst.get("world")
                if not w or w.get("angle"):
                    continue
                checked += 1
                left = w["x"] - w.get("originX", 0) * w["width"]
                top = w["y"] - w.get("originY", 0) * w["height"]
                if not ((on_grid(left, unit) or on_grid(left + w["width"], unit))
                        and (on_grid(top, unit) or on_grid(top + w["height"], unit))):
                    out.append(f"grid.world-placement: layout {layout.get('name', path.stem)} layer "
                               f"{layer.get('name')}: {inst.get('type')} at ({left:g},{top:g}) "
                               f"{w['width']:g}x{w['height']:g} is off the {unit} px grid; place a shape with "
                               f"shape_inst(type, image, col, row) and anything else with units() or snap()")
    return checked


def actions_of(node):
    if isinstance(node, dict):
        for a in node.get("actions", []) or []:
            if isinstance(a, dict):
                yield a
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from actions_of(v)
    elif isinstance(node, list):
        for v in node:
            yield from actions_of(v)


def check_spawn(root: Path, out: list[str]) -> int:
    """grid.runtime-spawn over eventSheets/; returns how many create actions were read."""
    read = 0
    for path in sorted((root / "eventSheets").rglob("*.json")):
        if path.name.endswith(".uistate.json"):
            continue
        sheet = c3.load(path)
        for a in actions_of(sheet.get("events", [])):
            if a.get("id") != "create-object":
                continue
            read += 1
            params = a.get("parameters", {})
            for axis in ("x", "y"):
                expr = str(params.get(axis, ""))
                if "random(" in expr and not re.search(r"\b(floor|round|ceil)\(", expr):
                    out.append(f"grid.runtime-spawn: sheet {sheet.get('name', path.stem)}: create "
                               f"{params.get('object-to-create')} at {axis} = {expr}, a raw random(); write "
                               f"grid_random(lo, hi) plus the origin's offset, as the template's module_setup() does")
    return read


COLLIDING = ("Platform", "EightDir", "Physics", "Car", "solid", "jumpthru")


def colliding_items(root: Path) -> dict[str, list[str]]:
    """Object types and families by name, with the behaviors that make them collide."""
    found = {}
    for kind in ("objectTypes", "families"):
        for path in sorted((root / kind).rglob("*.json")):
            if not path.name.endswith(".uistate.json"):
                item = c3.load(path)
                ids = [b.get("behaviorId") for b in item.get("behaviorTypes", []) if b.get("behaviorId") in COLLIDING]
                if ids:
                    found[item.get("name", path.stem)] = ids
    return found


def check_squash(root: Path, out: list[str]) -> None:
    """motion.squash-art over eventSheets/."""
    colliding = colliding_items(root)
    for path in sorted((root / "eventSheets").rglob("*.json")):
        if path.name.endswith(".uistate.json"):
            continue
        sheet = c3.load(path)
        for a in actions_of(sheet.get("events", [])):
            obj = a.get("objectClass")
            if a.get("id") == "set-size" and obj in colliding and "ImageWidth" in str(a.get("parameters", {})):
                out.append(f"motion.squash-art: sheet {sheet.get('name', path.stem)}: {obj} is squashed but has "
                           f"{', '.join(colliding[obj])}, so its collision box grows into the floor; squash its art, "
                           f"a second object drawn with shape(..., oy=1) and pinned to {obj}")


def check_hit(root: Path, out: list[str]) -> None:
    """motion.hit over objectTypes/ and families/."""
    for kind in ("objectTypes", "families"):
        for path in sorted((root / kind).rglob("*.json")):
            if path.name.endswith(".uistate.json"):
                continue
            item = c3.load(path)
            for b in item.get("behaviorTypes", []):
                if b.get("behaviorId") == "Flash":
                    out.append(f"motion.hit: {item.get('name', path.stem)} has the Flash behavior "
                               f"{b.get('name')}; a hit shows as a colour for an instant: draw a hit frame with "
                               f"hit_frame() and show it with hit_flash(), then remove the behavior")


def check_screen(project: dict, warned: list[str]) -> None:
    """screen.fill over project.c3proj, a warning: a Letterbox mode shows bars around the game on a
    screen whose shape differs from the viewport's, where the template fills the screen."""
    mode = (project.get("properties") or {}).get("fullscreenMode", "")
    if mode.startswith("letterbox"):
        want = "integer-scale-outer" if "integer" in mode else "scale-outer"
        warned.append(f"warning: screen.fill: project.c3proj has fullscreenMode {mode}, which shows bars where the "
                      f"screen's shape differs from the viewport's; the template's build_project() writes {want} "
                      f"(FULLSCREEN). Run the generator again, or remove the line that sets another mode. The "
                      f"generator also holds the HUD to the screen's edges (anchored()) and extends the backdrop "
                      f"past the viewport (backdrop()).")


def main() -> int:
    c3.utf8_output()
    ap = c3.argument_parser(__doc__.split("\n\n")[0], "examples:\n"
                            "  python scripts/check_look.py\n"
                            "  python scripts/check_look.py --project D:/games/Coins --painted title-*.png\n\n"
                            "exit codes: 0 when the last line starts with ok:, 1 on findings or no project")
    ap.add_argument("--painted", nargs="*", default=[], metavar="FILE",
                    help="image names or globs under images/ meant to keep their own soft edges")
    ap.add_argument("--unit", type=int, metavar="PX", help="the grid in px (default: from the viewport)")
    args = ap.parse_args()
    root = c3.find_project(args.project)
    if root is None or not (root / "project.c3proj").exists():
        print(f"no project.c3proj in {root or Path.cwd()}: run this from the project folder or pass "
              f"--project <folder>", file=sys.stderr)
        return 1
    project = c3.load(root / "project.c3proj")
    unit = args.unit or (8 if project.get("viewportHeight", 1080) <= 360 else 32)
    out: list[str] = []
    images = check_alpha(root, args.painted, out)
    instances = check_grid(root, unit, out)
    creates = check_spawn(root, out)
    check_hit(root, out)
    check_squash(root, out)
    warned: list[str] = []
    check_screen(project, warned)
    for line in warned:
        print(line)
    shown = c3.fitting(out, args.limit)
    for line in out[:shown]:
        print(line)
    if shown < len(out):
        print(f"... {len(out) - shown} more; --limit 0 prints them all")
    summary = f"{images} images, {instances} world instances on a {unit} px grid, {creates} runtime creations"
    print(f"{len(out)} findings: {summary}" if out else f"ok: {summary}")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
