"""Compare the authors on the numbers in stats/stats.json.

    python -m scripts.reference_games report

Prints medians and shares per author; collaborations are reported on their own.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict

from .catalog import WORKSPACE as ROOT, load_catalog


def share(counter: Counter, n: int = 6) -> str:
    total = sum(counter.values()) or 1
    return ", ".join(f"{k} {v * 100 / total:.0f}%" for k, v in counter.most_common(n))


def main() -> None:
    games = json.loads((ROOT / "stats" / "stats.json").read_text(encoding="utf-8"))
    entries = load_catalog()
    authors = {entry["folder"]: entry["author"] for entry in entries}
    groups: dict[str, list[str]] = defaultdict(list)
    for g in games:
        groups[authors.get(g, "unknown")].append(g)
    for author, names in sorted(groups.items()):
        tw = [t for g in names for t in games[g]["tweens"]]
        times = [t["time"] for t in tw if t["time"] is not None]
        props = Counter(t["property"] for t in tw if t["property"])
        eases = Counter(t["ease"] for t in tw if t["ease"])
        by_prop: dict[str, list[float]] = defaultdict(list)
        for t in tw:
            if t["time"] is not None and t["property"]:
                by_prop[t["property"]].append(t["time"])
        waits = [w for g in names for w in games[g]["waits"]]
        shakes = Counter(tuple(p for p in s if not p.startswith("mode=")) for g in names for s in games[g]["shakes"])
        ts = Counter(s[-1].split("=", 1)[-1] for g in names for s in games[g]["timescale"] if s)
        viewports = Counter(f"{games[g]['viewport'][0]}x{games[g]['viewport'][1]} {games[g]['sampling']}" for g in names)
        print(f"== {author}: {len(names)} games, {len(tw)} tweens")
        print(f"   viewport/sampling: {dict(viewports)}")
        if times:
            q = statistics.quantiles(times, n=4) if len(times) > 3 else times
            print(f"   tween time median {statistics.median(times):.2f}s, quartiles {[round(x, 2) for x in q]}")
        print(f"   properties: {share(props)}")
        print(f"   eases: {share(eases, 8)}")
        for prop in ("Size", "Scale", "Angle", "Position", "Y", "Opacity", "Width", "Height", "Z"):
            if len(by_prop.get(prop, [])) >= 3:
                v = by_prop[prop]
                print(f"   {prop}: n={len(v)} median {statistics.median(v):.2f}s, common {Counter(v).most_common(3)}")
        if waits:
            print(f"   waits: n={len(waits)} median {statistics.median(waits):.2f}s, common {Counter(waits).most_common(6)}")
        if shakes:
            print(f"   shakes: {shakes.most_common(5)}")
        if ts:
            print(f"   time scale values: {ts.most_common(8)}")
        loops = sum(1 for t in tw if t["loop"] == "Yes")
        pingpong = sum(1 for t in tw if t["pingpong"] == "Yes")
        print(f"   looping tweens {loops}, ping-pong {pingpong}")


if __name__ == "__main__":
    main()
