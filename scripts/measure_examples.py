"""Measure the official example projects for the numbers a generated game would otherwise borrow:
the player's height on the screen by genre, the share of the screen the HUD covers, how popups
open and close, and the Sine behavior's idle motion.

    python scripts/measure_examples.py actors --examples <Construct-Example-Projects>/example-projects
    python scripts/measure_examples.py hud --examples ... [--out ROWS.json]
    python scripts/measure_examples.py popups --examples ...
    python scripts/measure_examples.py sine --examples ...

Each subcommand prints a summary and, with --out, writes every measured row as JSON. Examples
tagged "3D" are left out. Genres are the examples' tags in data/c3-examples/en-US. The decision
records under docs/decisions/ cite the summaries; the rows stay in .local/docs/evidence/.
Exit codes: 0 measured, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RAG = Path(__file__).resolve().parents[1]
GENRES = ("Platformer", "Shooter", "Arcade", "Puzzle", "Action", "Adventure", "Racing", "Strategy", "RPG")
# A behavior the player moves by; an enemy can have one too, so a name that says player wins.
CONTROL = {"Platform", "EightDir", "Car", "TileMovement"}
PLAYER = re.compile(r"player|hero", re.I)
# The suffix of an invisible box that the player's art is pinned to.
COLLIDER = re.compile(r"(collision|collider|box|mask|hitbox|base|body)$", re.I)
# Pinned to the player and not its body.
NOT_BODY = re.compile(r"light|shadow|laser|bullet|gun|weapon|input|name|text|particle|trail|aim|cursor|health|bar", re.I)


def examples_meta(rag: Path) -> dict[str, dict]:
    """The metadata of every example that is not 3D, by id."""
    meta = {}
    for f in sorted((rag / "data" / "c3-examples" / "en-US").glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        if "3D" not in m.get("tags", []):
            meta[m["id"]] = m
    return meta


def project_folders(examples: Path):
    """(id, folder) of every example project, 3D ones and those without metadata included: a
    popup or a Sine motion is the same on a 2D layer of a 3D game."""
    for folder in sorted(examples.iterdir()):
        if (folder / "project.c3proj").is_file():
            yield folder.name, folder


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def layers_in(layers: list):
    for lay in layers:
        yield lay
        yield from layers_in(lay.get("subLayers", []))


def instances(folder: Path):
    """(layout, layer, instance) of every instance of every layout of the project."""
    for f in sorted((folder / "layouts").glob("*.json")):
        layout = load(f)
        for layer in layers_in(layout["layers"]):
            for inst in layer["instances"]:
                yield layout, layer, inst


def visible(layer: dict, inst: dict) -> bool:
    return layer.get("isInitiallyVisible", True) and inst.get("properties", {}).get("initially-visible", True) is not False


def quantiles(values: list[float]) -> str:
    v = sorted(values)
    if not v:
        return "n=0"
    q = lambda k: v[min(len(v) - 1, int(k * len(v)))]
    return (f"n={len(v):3} min {v[0]:.3f} p25 {q(0.25):.3f} median {statistics.median(v):.3f} "
            f"p75 {q(0.75):.3f} max {v[-1]:.3f}")


# --- actors -------------------------------------------------------------------------------
def opaque_share(folder: Path, otype: dict) -> float:
    """The share of the first frame's height its opaque pixels span; 1 when the image is missing."""
    try:
        from PIL import Image
    except ImportError:
        return 1.0
    anims = otype.get("animations", {}).get("items", [])
    if not anims:
        return 1.0
    name = f"{otype['name']}-{anims[0]['name']}-000".lower()
    for f in (folder / "images").glob("*.png"):
        if f.stem.lower() == name:
            img = Image.open(f).convert("RGBA")
            box = img.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
            return (box[3] - box[1]) / img.height if box else 1.0
    return 1.0


def player_type(folder: Path) -> dict | None:
    """The object type most likely to be the player: a name that says so, then a camera target,
    then a movement behavior."""
    best, best_score = None, 0
    for f in sorted((folder / "objectTypes").glob("*.json")):
        o = load(f)
        behs = {b["behaviorId"] for b in o.get("behaviorTypes", [])}
        if o.get("plugin-id") != "Sprite" or NOT_BODY.search(o["name"]):
            continue
        score = 4 * bool(PLAYER.search(o["name"])) + 2 * ("scrollto" in behs) + (bool(behs & CONTROL))
        if score > best_score and (PLAYER.search(o["name"]) or behs & CONTROL):
            best, best_score = o, score
    return best


def measure_actors(examples: Path, rag: Path) -> list[dict]:
    rows = []
    for gid, meta in examples_meta(rag).items():
        folder = examples / gid
        if not (folder / "project.c3proj").is_file():
            continue
        proj = load(folder / "project.c3proj")
        vw, vh = proj["viewportWidth"], proj["viewportHeight"]
        player = player_type(folder)
        if not player:
            continue
        found = [(lay, layer, i) for lay, layer, i in instances(folder) if i["type"] == player["name"] and i.get("world")]
        if not found:
            continue
        _, layer, inst = found[0]
        art_name = player["name"]
        if not visible(layer, inst):
            # The art pinned to an invisible box: a visible child in the scene graph, or a visible
            # instance named after the box without its suffix (PlayerCollision -> PlayerArt).
            kids = {c["uid"] for c in (inst.get("sceneGraphData") or {}).get("children", [])}
            stem = COLLIDER.sub("", player["name"]) or player["name"]
            art = [(i["uid"] not in kids, ly, i) for _, ly, i in instances(folder)
                   if visible(ly, i) and i.get("world") and i["type"] != player["name"] and not NOT_BODY.search(i["type"])
                   and (i["uid"] in kids or i["type"].lower().startswith(stem.lower()))]
            if not art:
                continue
            _, layer, inst = min(art, key=lambda a: a[0])
            art_name = inst["type"]
        otype_file = folder / "objectTypes" / f"{art_name}.json"
        share = opaque_share(folder, load(otype_file)) if otype_file.is_file() else 1.0
        h = abs(inst["world"]["height"]) * share
        moves = sorted({b["behaviorId"] for b in player.get("behaviorTypes", [])} & CONTROL)
        rows.append({"example": gid, "genres": [g for g in GENRES if g in meta.get("tags", [])], "moves": moves,
                     "template": bool({"Game template", "Demo game"} & set(meta.get("tags", []))),
                     "player": player["name"], "art": art_name, "viewport": [vw, vh],
                     "height": round(h, 1), "of_viewport_height": round(h / vh, 3)})
    return rows


def report_actors(rows: list[dict]) -> None:
    print("player art height (opaque pixels) as a share of the viewport height")
    print(f"  {'all':10} {quantiles([r['of_viewport_height'] for r in rows])}")
    for g in GENRES:
        vals = [r["of_viewport_height"] for r in rows if g in r["genres"]]
        if len(vals) >= 3:
            print(f"  {g:10} {quantiles(vals)}")
    print("by the behavior the player moves by")
    for b in sorted(CONTROL):
        vals = [r["of_viewport_height"] for r in rows if b in r["moves"]]
        if len(vals) >= 3:
            distinct = len({(r["height"], tuple(r["viewport"])) for r in rows if b in r["moves"]})
            print(f"  {b:12} {quantiles(vals)}  ({distinct} distinct sizes)")
    games = [r["of_viewport_height"] for r in rows if r["template"]]
    print(f"  {'templates':10} {quantiles(games)}  (tagged Game template or Demo game)")


# --- hud ------------------------------------------------------------------------------------
# A layout that is a menu or a screen between rounds, not play.
NOT_PLAY = re.compile(r"menu|title|start|splash|load|intro|over|win|lose|credit|setting|option|shop|select|pause|"
                      r"repositor|bank|objects|template|tutorial|help|end", re.I)


def box_on_screen(w: dict, vw: float, vh: float) -> tuple[float, float, float, float] | None:
    """The instance's box clipped to the viewport, for a layer that does not scroll."""
    left = w["x"] - w.get("originX", 0) * w["width"]
    top = w["y"] - w.get("originY", 0) * w["height"]
    left, top = min(left, left + w["width"]), min(top, top + w["height"])
    box = (max(left, 0), max(top, 0), min(left + abs(w["width"]), vw), min(top + abs(w["height"]), vh))
    return box if box[2] > box[0] and box[3] > box[1] else None


def union_share(boxes: list, vw: float, vh: float, cell: float) -> float:
    """The share of the viewport that the boxes cover together, on a grid of `cell` px."""
    cols, rows = max(1, int(vw / cell)), max(1, int(vh / cell))
    grid = bytearray(cols * rows)
    for x0, y0, x1, y1 in boxes:
        for r in range(int(y0 / cell), min(rows, int(-(-y1 // cell)))):
            grid[r * cols + int(x0 / cell): r * cols + min(cols, int(-(-x1 // cell)))] = b"\1" * (
                min(cols, int(-(-x1 // cell))) - int(x0 / cell))
    return sum(grid) / len(grid)


# A HUD element shown only for a moment: an instruction, a message between rounds, a popup.
TRANSIENT = re.compile(r"tutorial|instruct|help|tip|hint|gameover|game_over|won|win|lose|ending|celebrat|popup|menu|"
                       r"pause|dialog|closeup|loading|achiev|buy|cancel|confirm|shop|fader|fade|transition|message", re.I)
BBCODE = re.compile(r"\[/?[^\]]*\]")


def measure_hud(examples: Path, rag: Path) -> list[dict]:
    """Per play layout of a game example: what the HUD covers, from the visible instances of its
    layers at parallax 0. Left out: full-screen overlays (80% of the screen both ways), elements
    named for a moment (TRANSIENT), and a Text of more than 30 characters, an instruction. `covers`
    is the share of the screen the elements cover together, a Text with its whole box; `bands` is
    the depth of the strips along the top and bottom edges that hold them, as a share of the
    screen's height, the room the playfield loses."""
    rows = []
    for gid, meta in examples_meta(rag).items():
        if not {"Game template", "Demo game"} & set(meta.get("tags", [])):
            continue
        folder = examples / gid
        if not (folder / "project.c3proj").is_file():
            continue
        proj = load(folder / "project.c3proj")
        vw, vh = proj["viewportWidth"], proj["viewportHeight"]
        for f in sorted((folder / "layouts").glob("*.json")):
            layout = load(f)
            if NOT_PLAY.search(layout["name"]):
                continue
            boxes, types = [], set()
            for layer in layers_in(layout["layers"]):
                if layer.get("parallaxX", 1) != 0 or layer.get("parallaxY", 1) != 0 or not layer.get("isInitiallyVisible", True):
                    continue
                for inst in layer["instances"]:
                    w, props = inst.get("world"), inst.get("properties", {})
                    if not w or not visible(layer, inst) or TRANSIENT.search(inst["type"]):
                        continue
                    if len(BBCODE.sub("", str(props.get("text", "")))) > 30:
                        continue
                    box = box_on_screen(w, vw, vh)
                    if not box or (box[2] - box[0] >= 0.8 * vw and box[3] - box[1] >= 0.8 * vh):
                        continue
                    boxes.append(box)
                    types.add(inst["type"])
            if not boxes:
                continue
            top = max((b[3] for b in boxes if b[1] < vh / 3), default=0)
            bottom = vh - min((b[1] for b in boxes if b[3] > 2 * vh / 3), default=vh)
            rows.append({"example": gid, "layout": layout["name"], "viewport": [vw, vh], "types": sorted(types),
                         "covers": round(union_share(boxes, vw, vh, max(1.0, min(vw, vh) / 360)), 3),
                         "bands": round(min(1.0, (top + bottom) / vh), 3)})
    return rows


def report_hud(rows: list[dict]) -> None:
    print("the HUD of the play layouts of the game examples: visible instances of layers at parallax 0")
    print(f"  {'covers':8} {quantiles([r['covers'] for r in rows])}  (share of the screen, a Text with its whole box)")
    print(f"  {'bands':8} {quantiles([r['bands'] for r in rows])}  (top and bottom strips, share of the height)")
    examples = len({r["example"] for r in rows})
    print(f"  {len(rows)} layouts of {examples} examples; a game whose HUD shares a scrolling layer is not counted")


# --- popups -------------------------------------------------------------------------------------
# An object or layer that shows for a moment over play: a pause or game-over screen, a menu, a shop.
POPUP = re.compile(r"pause|menu|shop|popup|gameover|game_?over|skill|inventory|info|result|win|lose|dialog|panel|"
                   r"window|confirm|upgrade|complete|reward", re.I)
TWEENS = ("tween-one-property", "tween-two-properties")


def actions_in(events: list):
    for ev in events:
        yield from ev.get("actions") or []
        yield from actions_in(ev.get("children") or [])


def number(text) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def measure_popups(examples: Path, rag: Path) -> list[dict]:
    """Every Tween action on a popup's object, an object of a layer at parallax 0 whose own name or
    layer's name says popup (POPUP), and every System *Set layer visible* of such a layer."""
    rows = []
    for gid, folder in project_folders(examples):
        on, popup_layers = defaultdict(set), set()
        for _, layer, inst in instances(folder):
            if layer.get("parallaxX", 1) == 0:
                on[inst["type"]].add(layer["name"])
                if POPUP.search(layer["name"]):
                    popup_layers.add(layer["name"])
        for f in sorted((folder / "eventSheets").glob("*.json")):
            for act in actions_in(load(f).get("events", [])):
                p, obj = act.get("parameters", {}), act.get("objectClass")
                if act.get("id") in TWEENS and obj in on and (POPUP.search(obj) or any(map(POPUP.search, on[obj]))):
                    end = number(p.get("end-value"))
                    rows.append({"example": gid, "object": obj, "action": "tween", "property": p.get("property"),
                                 "end": end, "time": number(p.get("time")), "ease": p.get("ease"),
                                 "ping_pong": p.get("ping-pong") == "yes"})
                elif act.get("id") == "set-layer-visible" and str(p.get("layer", "")).strip('"') in popup_layers:
                    rows.append({"example": gid, "object": str(p.get("layer")).strip('"'), "action": "set-layer-visible"})
    return rows


def report_popups(rows: list[dict]) -> None:
    tweens = [r for r in rows if r["action"] == "tween" and not r["ping_pong"]]
    print(f"popups of the examples: {len(tweens)} tweens on popup objects in {len({r['example'] for r in tweens})} "
          f"examples, {sum(r['action'] == 'set-layer-visible' for r in rows)} Set layer visible of a popup layer")
    props = defaultdict(int)
    for r in tweens:
        props[r["property"]] += 1
    print("  property: " + ", ".join(f"{k} {v}" for k, v in sorted(props.items(), key=lambda kv: -kv[1])))
    eases = defaultdict(int)
    for r in tweens:
        eases[r["ease"]] += 1
    print("  ease: " + ", ".join(f"{k} {v}" for k, v in sorted(eases.items(), key=lambda kv: -kv[1])))
    fades = [r for r in tweens if r["property"] == "offsetOpacity" and r["time"] is not None]
    print(f"  {'open (opacity to 100)':24} time {quantiles([r['time'] for r in fades if r['end'] == 100])}")
    print(f"  {'close (opacity to 0)':24} time {quantiles([r['time'] for r in fades if r['end'] == 0])}")


# --- sine -----------------------------------------------------------------------------------------
# An object the player collects, which the examples set bobbing or pulsing where it waits.
PICKUP = re.compile(r"coin|collect|pickup|power|item|key|gem|bonus|skull|banana|feather|crystal", re.I)


def measure_sine(examples: Path, rag: Path) -> list[dict]:
    """The Sine behavior's properties on the first instance of each object type that has it, with the
    instance's size: the motion the examples give an object at rest."""
    rows = []
    for gid, folder in project_folders(examples):
        seen = set()
        for _, layer, inst in instances(folder):
            for name, beh in (inst.get("behaviors") or {}).items():
                props, w = beh.get("properties", {}), inst.get("world") or {}
                if "period" not in props or "magnitude" not in props or (inst["type"], name) in seen:
                    continue
                seen.add((inst["type"], name))
                rows.append({"example": gid, "object": inst["type"], "movement": props.get("movement"),
                             "wave": props.get("wave"), "period": props["period"], "magnitude": props["magnitude"],
                             "enabled": props.get("enabled", True), "size": [abs(w.get("width", 0)), abs(w.get("height", 0))]})
    return rows


def report_sine(rows: list[dict]) -> None:
    rows = [r for r in rows if r["enabled"] and r["wave"] == "sine"]
    print(f"Sine on {len(rows)} object types of {len({r['example'] for r in rows})} examples (enabled, sine wave), by movement")
    by = defaultdict(list)
    for r in rows:
        by[r["movement"]].append(r)
    for movement, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(rs) < 5:
            continue
        print(f"  {movement:16} period s   {quantiles([r['period'] for r in rs])}")
        if movement in ("horizontal", "vertical", "forwards-backwards"):
            mags = [r["magnitude"] / r["size"][1] for r in rs if r["size"][1]]
            print(f"  {'':16} magnitude {quantiles(mags)}  (px over the object's height)")
        elif movement in ("size", "width", "height"):
            mags = [r["magnitude"] / max(r["size"]) for r in rs if max(r["size"])]
            print(f"  {'':16} magnitude {quantiles(mags)}  (px over the object's longer side)")
        else:
            print(f"  {'':16} magnitude {quantiles([r['magnitude'] for r in rs])}")
    bob = [r for r in rows if r["movement"] in ("vertical", "size") and PICKUP.search(r["object"]) and r["size"][1]]
    print(f"  pickups bobbing or pulsing, {len(bob)} types named as one ({PICKUP.pattern}):")
    print(f"  {'':16} period s   {quantiles([r['period'] for r in bob])}")
    print(f"  {'':16} magnitude {quantiles([r['magnitude'] / r['size'][1] for r in bob])}  (px over the object's height)")


# --- command line -----------------------------------------------------------------------------
MEASURES = {"actors": (measure_actors, report_actors), "hud": (measure_hud, report_hud),
            "popups": (measure_popups, report_popups), "sine": (measure_sine, report_sine)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="example: python scripts/measure_examples.py actors --examples "
                                        "../Construct-Example-Projects/example-projects "
                                        "--out .local/docs/evidence/w11-measurements/actors.json")
    ap.add_argument("measure", choices=sorted(MEASURES))
    ap.add_argument("--examples", type=Path, required=True, help="the example-projects folder of the clone")
    ap.add_argument("--out", type=Path, help="write every measured row here as JSON")
    ap.add_argument("--rag", type=Path, default=RAG, help="the Construct3-RAG folder, for the examples' tags")
    args = ap.parse_args()
    if not args.examples.is_dir():
        print(f"--examples {args.examples}: not a folder; pass <Construct-Example-Projects>/example-projects", file=sys.stderr)
        return 2
    measure, report = MEASURES[args.measure]
    rows = measure(args.examples, args.rag)
    if not rows:
        print("nothing measured: check that --examples is the example-projects folder")
        return 0
    report(rows)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"rows in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
