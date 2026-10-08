"""Measure the composition of the official game examples' one-screen layouts: how much of the
screen the box around their content covers, and how much larger their largest object is than
the next. The generator template's playfield checks take their thresholds from this.

    python evals/measure_layout.py --examples <Construct-Example-Projects>/example-projects
                                   [--out ROWS.json] [--rag FOLDER]

An example counts when its tags in data/c3-examples name a game ("Game template" or "Demo
game") and not "3D". A layout counts when it is one screen, at most 5% larger than the viewport
either way, is not a store of runtime templates (a name with "repository", "bank", "objects"
or "template"), and shows at least 4 instances. Content is every visible instance of a
scrolling layer, not a Text, not rotated, clipped to the viewport, less any that cover 80% of
it both ways, which are backdrops. Exit codes: 0 measured, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAG = Path(__file__).resolve().parents[3]
STORES = re.compile(r"repositor|bank|objects|template", re.I)


def games(rag: Path) -> list[str]:
    """The ids of the examples tagged as 2D games."""
    ids = []
    for f in sorted((rag / "data" / "c3-examples" / "en-US").glob("*.json")):
        meta = json.loads(f.read_text(encoding="utf-8"))
        tags = set(meta.get("tags", []))
        if tags & {"Game template", "Demo game"} and "3D" not in tags:
            ids.append(meta["id"])
    return ids


def layers_in(layers: list):
    for lay in layers:
        yield lay
        yield from layers_in(lay.get("subLayers", []))


def content(layout: dict, vw: float, vh: float) -> list[tuple[str, tuple, float]]:
    """(type, box clipped to the viewport, area) of each instance that counts as content."""
    found = []
    for layer in layers_in(layout["layers"]):
        if not layer.get("isInitiallyVisible", True) or 0 in (layer.get("parallaxX", 1), layer.get("parallaxY", 1)):
            continue
        for inst in layer["instances"]:
            props, w = inst.get("properties", {}), inst.get("world")
            if props.get("initially-visible") is False or "text" in props or not w or w.get("angle"):
                continue
            left = w["x"] - w.get("originX", 0) * w["width"]     # a mirrored instance has a negative size
            top = w["y"] - w.get("originY", 0) * w["height"]
            left, top = min(left, left + w["width"]), min(top, top + w["height"])
            box = (max(left, 0), max(top, 0), min(left + abs(w["width"]), vw), min(top + abs(w["height"]), vh))
            bw, bh = box[2] - box[0], box[3] - box[1]
            if bw <= 0 or bh <= 0 or (bw >= 0.8 * vw and bh >= 0.8 * vh):
                continue
            found.append((inst["type"], box, bw * bh))
    return found


def measure(examples: Path, rag: Path) -> list[dict]:
    rows = []
    for gid in games(rag):
        proj = examples / gid / "project.c3proj"
        if not proj.is_file():
            continue
        p = json.loads(proj.read_text(encoding="utf-8-sig"))
        vw, vh = p["viewportWidth"], p["viewportHeight"]
        for f in sorted((examples / gid / "layouts").glob("*.json")):
            lay = json.loads(f.read_text(encoding="utf-8"))
            if lay["width"] > 1.05 * vw or lay["height"] > 1.05 * vh or STORES.search(lay["name"]):
                continue
            found = content(lay, vw, vh)
            if len(found) < 4:
                continue
            hull = [min(b[1][0] for b in found), min(b[1][1] for b in found),
                    max(b[1][2] for b in found), max(b[1][3] for b in found)]
            ranked = sorted(found, key=lambda b: -b[2])
            rows.append({"example": gid, "layout": lay["name"], "viewport": [vw, vh], "instances": len(found),
                         "covers": round((hull[2] - hull[0]) * (hull[3] - hull[1]) / (vw * vh), 3),
                         "focal": round(ranked[0][2] / ranked[1][2], 2), "largest": ranked[0][0], "next": ranked[1][0]})
    return rows


def share(rows: list[dict], key: str, test) -> str:
    n = sum(1 for r in rows if test(r[key]))
    return f"{n} of {len(rows)} ({100 * n / len(rows):.0f}%)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="example: python evals/measure_layout.py --examples ../Construct-Example-Projects/"
                                        "example-projects --out .local/docs/evidence/layout.json")
    ap.add_argument("--examples", type=Path, required=True, help="the example-projects folder of the clone")
    ap.add_argument("--out", type=Path, help="write every measured layout here as JSON")
    ap.add_argument("--rag", type=Path, default=RAG, help="the Construct3-RAG folder, for the examples' tags")
    args = ap.parse_args()
    if not args.examples.is_dir():
        print(f"--examples {args.examples}: not a folder; pass <Construct-Example-Projects>/example-projects", file=sys.stderr)
        return 2
    rows = measure(args.examples, args.rag)
    if not rows:
        print("no layout measured: check that --examples is the example-projects folder")
        return 0
    for key in ("covers", "focal"):
        vals = sorted(r[key] for r in rows)
        cuts = " ".join(f"p{int(k * 100)} {vals[min(len(vals) - 1, int(k * len(vals)))]:g}"
                        for k in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9))
        print(f"{key}: {len(vals)} layouts, {cuts}")
    print(f"covers under 0.15: {share(rows, 'covers', lambda v: v < 0.15)}; 0.25 to 0.60: "
          f"{share(rows, 'covers', lambda v: 0.25 <= v <= 0.6)}; over 0.60: {share(rows, 'covers', lambda v: v > 0.6)}")
    print(f"focal 1.5 or more: {share(rows, 'focal', lambda v: v >= 1.5)}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"rows in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
