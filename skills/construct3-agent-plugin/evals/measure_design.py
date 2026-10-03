"""Run the rules of scripts/review_design.py over the official examples and game
projects, and count what each one finds, with variants of the thresholds.

    python evals/measure_design.py --examples <Construct-Example-Projects>/example-projects
                                   [--projects FOLDER ...] [--out HITS.json] [--rag FOLDER]

A rule stays a finding only when it finds (near) nothing in the examples, each
example hit read and explained; the counts and hits go to --out for that reading.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import c3project as c3              # noqa: E402
import review_design as rd          # noqa: E402


def design_of(root: Path, rag: Path) -> rd.Design:
    p = c3.Project(root, rag, "en-US", c3.Findings())
    return rd.Design.of(p)


def variants(d: rd.Design) -> dict:
    """What the thresholds are chosen from: the spread of conditions per event, and
    looser forms of the rules."""
    out: Counter = Counter()
    spread: Counter = Counter()
    for sheet in d.rows:
        for e in d.blocks(sheet):
            if e.ev.get("isOrBlock"):
                continue
            spread[len(d.filters(e))] += 1
            inverted = [c for c in d.filters(e) if c.get("isInverted") and c.get("objectClass") != "System"]
            out["inverted_3_any_object"] += len(inverted) >= 3
        for e in d.rows[sheet]:
            for a in e.actions:
                params = a.get("parameters") if isinstance(a.get("parameters"), dict) else {}
                out["ivar_set_to_uid"] += a.get("id") == "set-instvar-value" and bool(rd.UID_OF.match(str(params.get("value", ""))))
            for _, _, _, v in d.all_expressions(e):
                deep, repeated = rd.expression_shape(v)
                out["expr_deep_5"] += deep >= 5
                out["expr_repeat_15"] += len(repeated) >= 15
                out["expr_repeat_30"] += len(repeated) >= 30
                out["expr_deep_5_and_repeat_15"] += deep >= 5 and len(repeated) >= 15
                out["expressions"] += 1
    counts = rd.globals_count(d)
    laid = {lay.get("eventSheet") for lay in d.layouts.values()}
    out["sheets_10_globals_on_layout_sheet"] = sum(1 for s, n in counts.items() if n >= 10 and s in laid)
    uses = rd.global_uses(d)
    globals_ = d.globals()
    out["globals"] = len(globals_)
    off: Counter = Counter(globals_[g][0] for g, us in uses.items() if us and globals_[g][0] not in {u.e.sheet for u in us})
    out["sheets_declaring_10_globals_used_elsewhere"] = sum(1 for n in off.values() if n >= 10)
    out["globals_declared_off_their_sheets"] = sum(
        1 for g, us in uses.items() if us and globals_[g][0] not in {u.e.sheet for u in us})
    return {"variants": dict(out), "conditions": dict(spread)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--examples", type=Path, help="the example-projects folder of Construct-Example-Projects")
    ap.add_argument("--projects", type=Path, nargs="*", default=[], help="game project folders, counted one by one")
    ap.add_argument("--rag", type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument("--out", type=Path, help="write every hit and count as JSON")
    args = ap.parse_args()
    c3.utf8_output()
    sets = []
    if args.examples:
        sets.append(("examples", sorted(p.parent for p in args.examples.glob("*/project.c3proj"))))
    sets += [(p.name, [p]) for p in args.projects]
    result = {}
    for label, roots in sets:
        rules: Counter = Counter()
        projects_hit: dict[str, set] = {}
        var: Counter = Counter()
        spread: Counter = Counter()
        hits = []
        failed = []
        for root in roots:
            try:
                d = design_of(root, args.rag)
                found = rd.candidates(d)
                extra = variants(d)
            except (SystemExit, KeyError, TypeError, AttributeError, ValueError) as e:
                failed.append(f"{root.name}: {type(e).__name__} {e}")
                continue
            for f in found:
                ask = rd.CLASSES.get((f["rule"], f["variant"]), rd.DROPPED)
                kept = "finding" if ask is None else ask if ask == rd.DROPPED else f"question {ask}"
                tag = f["rule"] + (f"/{f['variant']}" if f["variant"] else "") + f" ({kept})"
                rules[tag] += 1
                projects_hit.setdefault(tag, set()).add(root.name)
                hits.append({"project": root.name, "kept": kept, **f})
            var.update(extra["variants"])
            spread.update({int(k): v for k, v in extra["conditions"].items()})
        total = sum(spread.values())
        at_least = {n: sum(v for k, v in spread.items() if k >= n) for n in (4, 5, 6, 8)}
        result[label] = {"projects": len(roots), "failed": failed, "rules": dict(rules),
                         "projects_hit": {k: len(v) for k, v in projects_hit.items()}, "variants": dict(var),
                         "events": total, "conditions_at_least": at_least, "hits": hits}
        print(f"== {label}: {len(roots)} projects, {total} events, {len(failed)} not read")
        for k in sorted(rules):
            print(f"  {k:<24} {rules[k]:>5} in {len(projects_hit[k])} projects")
        print("  conditions besides the trigger, events with at least: "
              + ", ".join(f"{n}: {c} ({100 * c / max(total, 1):.1f}%)" for n, c in at_least.items()))
        print("  variants: " + ", ".join(f"{k} {v}" for k, v in sorted(var.items())))
        for f in failed[:5]:
            print(f"  not read: {f}")
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
