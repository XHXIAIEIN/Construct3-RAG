"""Tabulate the motion and look of decoded games: tweens, waits, shakes, time scale, zoom, flashes,
effects, viewports, background and tint colours, animations.

    python -m scripts.reference_games report

Writes ``stats/stats.md`` (per author and per game) and ``stats/stats.json``.
Authors come from the workspace's ``catalog.json``.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .catalog import DECODED, STATS, load_catalog

MOTION = {
    "tween": re.compile(r"Tween\.(Tween\w+)$"),
    "wait": re.compile(r"System\.(Wait|WaitForPreviousActions)$"),
    "shake": re.compile(r"\.Shake$"),
    "timescale": re.compile(r"System\.(SetTimescale|SetObjectTimescale|RestoreObjectTimescale)$"),
    "zoom": re.compile(r"System\.(SetLayoutScale|SetLayerScale)$"),
    "flash": re.compile(r"Flash\.Flash$"),
    "color": re.compile(r"\.(SetDefaultColor|SetColor|SetLayerBackground|SetEffectParam|SetLayerEffectParam)$"),
    "particles": re.compile(r"Particles\.\w+$"),
    "sine": re.compile(r"Sin\.\w+$"),
    "anim": re.compile(r"Sprite\.(SetAnim|SetAnimSpeed|SetAnimFrame|StartAnim|StopAnim)$"),
    "camera": re.compile(r"System\.(ScrollToObject|ScrollToXY)$|scrollto\.\w+$"),
    "audio": re.compile(r"Audio\.(Play|PlayByName|PlayAtPosition|SetPlaybackRate)$"),
}


def num(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None


def param(params: list[str], key: str) -> str | None:
    for p in params:
        if p.startswith(key + "="):
            return p.split("=", 1)[1]
    return None


def game_stats(folder: Path) -> dict:
    s = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (folder / "aces.jsonl").read_text(encoding="utf-8").splitlines() if l]
    acts = [r for r in rows if r["kind"] == "act"]
    motion: dict[str, list] = defaultdict(list)
    for r in acts:
        parts = r["ace"].split(".")
        ace = f"{parts[1]}.{parts[3]}" if len(parts) >= 4 else r["ace"]
        for key, rx in MOTION.items():
            if rx.search(ace):
                motion[key].append({"object": r["object"], "ace": ace, "params": r["params"]})
    tweens = []
    for m in motion["tween"]:
        p = m["params"]
        tweens.append({"object": m["object"], "tags": param(p, "tags"), "property": param(p, "property"),
                       "time": num(param(p, "time") or ""), "ease": param(p, "ease"),
                       "loop": param(p, "loop"), "pingpong": param(p, "ping-pong"), "ace": m["ace"]})
    waits = [num(param(m["params"], "seconds") or "") for m in motion["wait"]]
    anims = [a for o in s["objects"] for a in o["animations"] if a["frames"] > 1]
    effects = Counter(e.split(":")[0] for o in s["objects"] for e in o["effects"])
    bgs = Counter()
    for L in s["layouts"]:
        for ly in L["layers"]:
            effects.update(str(e) for e in ly["effects"])
            if ly["bg"] and not ly["transparent"]:
                bgs["#" + "".join(f"{int(c):02x}" for c in ly["bg"][:3])] += 1
    behaviors = Counter(b["type"] if isinstance(b["type"], str) else b["name"] for o in s["objects"] for b in o["behaviors"])
    plugins = Counter(o["plugin"] for o in s["objects"] if not o["family"])
    return {
        "name": s["name"], "viewport": s["viewport"], "sampling": s["sampling"], "readable": s["runtime_tables"],
        "counts": {k: len(v) for k, v in motion.items()}, "tweens": tweens, "waits": [w for w in waits if w is not None],
        "shakes": [m["params"] for m in motion["shake"]], "timescale": [m["params"] for m in motion["timescale"]],
        "zoom": [m["params"] for m in motion["zoom"]], "flash": [m["params"] for m in motion["flash"]],
        "anims": anims, "effects": effects.most_common(), "layer_bgs": bgs.most_common(12),
        "tints": s["instance_tints"][:16], "behaviors": behaviors.most_common(), "plugins": plugins.most_common(),
        "layouts": len(s["layouts"]), "objects": len(s["objects"]), "sheets": len(s["sheets"]),
        "fonts": [], "sounds": len(s["sounds"]),
    }


def hist(values: list[float], edges: list[float]) -> str:
    c = Counter()
    for v in values:
        for e in edges:
            if v <= e:
                c[e] += 1
                break
        else:
            c["more"] += 1
    return ", ".join(f"≤{e}s:{c[e]}" for e in edges if c[e]) + (f", more:{c['more']}" if c["more"] else "")


def main() -> None:
    entries = load_catalog()
    authors = {entry["folder"]: entry["author"] for entry in entries}
    games = {}
    for folder in sorted(DECODED.iterdir()):
        if (folder / "summary.json").exists():
            games[folder.name] = game_stats(folder)
    STATS.mkdir(exist_ok=True)
    (STATS / "stats.json").write_text(json.dumps(games, indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["# Motion and look across the reference games", "",
          "Durations in seconds from the decoded event sheets. Eases by the runtime's own index table.", ""]
    by_author: dict[str, list[str]] = defaultdict(list)
    for g in games:
        by_author[authors.get(g, "unknown")].append(g)
    edges = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 2]
    for author, names in sorted(by_author.items()):
        tw = [t for g in names for t in games[g]["tweens"]]
        md += [f"## {author} ({len(names)} games)", ""]
        times = [t["time"] for t in tw if t["time"] is not None]
        md.append(f"- Tweens: {len(tw)}; constant durations {len(times)}: {hist(times, edges)}")
        md.append("- Eases: " + ", ".join(f"{e}×{n}" for e, n in Counter(t["ease"] for t in tw).most_common(10)))
        md.append("- Properties: " + ", ".join(f"{e}×{n}" for e, n in Counter(t["property"] for t in tw).most_common(10)))
        waits = [w for g in names for w in games[g]["waits"]]
        md.append(f"- Waits: {len(waits)}: {hist(waits, edges)}")
        for key in ("shakes", "timescale", "zoom", "flash"):
            n = sum(len(games[g][key]) for g in names)
            if n:
                sample = Counter("(" + ", ".join(p) + ")" for g in names for p in games[g][key]).most_common(4)
                md.append(f"- {key}: {n}; most common " + "; ".join(f"{s} ×{c}" for s, c in sample))
        md.append("")
    md += ["## Per game", ""]
    for g, st in games.items():
        md.append(f"### {g} ({authors.get(g, 'unknown')})")
        md.append(f"{st['name']}, viewport {st['viewport']}, sampling {st['sampling']}, readable ACEs {st['readable']}, "
                  f"{st['objects']} objects, {st['layouts']} layouts, {st['sheets']} sheets")
        md.append("- Plugins: " + ", ".join(f"{p}×{n}" for p, n in st["plugins"][:12]))
        md.append("- Behaviors: " + ", ".join(f"{p}×{n}" for p, n in st["behaviors"][:12]))
        if st["effects"]:
            md.append("- Effects: " + ", ".join(f"{p}×{n}" for p, n in st["effects"][:10]))
        md.append("- Opaque layer backgrounds: " + ", ".join(f"{c}×{n}" for c, n in st["layer_bgs"]))
        md.append("- Instance tints: " + ", ".join(f"{c}×{n}" for c, n in st["tints"]))
        md.append("- Motion counts: " + ", ".join(f"{k} {v}" for k, v in st["counts"].items()))
        seen = set()
        lines = []
        for t in st["tweens"]:
            key = (t["object"], t["tags"], t["property"], t["time"], t["ease"], t["loop"], t["pingpong"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  - {t['object']} [{t['tags']}] {t['property']} {t['time']}s {t['ease']}"
                         f"{' loop' if t['loop'] == 'Yes' else ''}{' pingpong' if t['pingpong'] == 'Yes' else ''}")
        if lines:
            md.append(f"- Distinct tweens ({len(lines)}):")
            md += lines[:40]
        if st["shakes"]:
            md.append("- Shakes: " + "; ".join(", ".join(p) for p in st["shakes"][:6]))
        if st["timescale"]:
            md.append("- Time scale: " + "; ".join(", ".join(p) for p in st["timescale"][:6]))
        if st["anims"]:
            md.append("- Animations >1 frame: " + "; ".join(f"{a['name']} {a['frames']}f {a['speed']}fps" for a in st["anims"][:14]))
        md.append("")
    (STATS / "stats.md").write_text("\n".join(md), encoding="utf-8")
    print(f"{len(games)} games -> {STATS / 'stats.md'}")


if __name__ == "__main__":
    main()
