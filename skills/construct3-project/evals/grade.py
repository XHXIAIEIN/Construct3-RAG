"""Grade the runs of one eval iteration and aggregate them.

    python evals/grade.py ITERATION_DIR

ITERATION_DIR holds <case>/<arm>/ with project/, outputs/answer.md,
fixture.json and, once the run has reported, timing.json. Every assertion of
evals/evals.json is checked by code against the files the run left, with the
clone's own checker, and written to <case>/<arm>/grading.json with the
evidence. benchmark.json gives, per case and arm, the mean of every measure
and its deviation once a cell has more than one run (<arm>_2, <arm>_3 are
further runs of <arm>), and with_skill less each other arm. A run with a
trace.json (evals/trace.py --out) adds its tool calls and the ones it lost.

A run that did not keep to its arm is not scored: put the reason in
<case>/<arm>/void.txt, for example a baseline whose answer lists a script of
this skill among its commands. A run without timing.json has no time or
tokens in the benchmark; nothing is filled in for it.

exit codes: 0 graded, 1 ITERATION_DIR holds no run of a known case
"""
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent
CASES = {c["name"]: c for c in json.loads((Path(__file__).parent / "evals.json").read_text(encoding="utf-8"))["evals"]}
ORIGINAL_GLOBALS = {"score", "COIN_COUNT"}
SIZE_ACTIONS = {"set-size", "set-scale", "set-width", "set-height"}
TWEEN_ENDS = {"on-tweens-finished", "on-any-tweens-finished"}


def checker(project: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(SKILL / "scripts" / "check_project.py"),
                        "--project", str(project), "--rag", str(REPO)],
                       capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return p.returncode, (p.stdout + p.stderr).strip()


def walk(events: list, above: tuple = ()):
    """Every event with the events it sits under."""
    for ev in events:
        yield ev, above
        yield from walk(ev.get("children", []), (*above, ev))


def values(aces: list) -> str:
    """Every parameter value of some conditions or actions, as one searchable string."""
    out = []
    for a in aces:
        params = a.get("parameters", {})
        out += [str(v) for v in (params.values() if isinstance(params, dict) else params)]
    return " | ".join(out)


def conditions_over(ev: dict, above: tuple) -> list:
    return [c for e in (*above, ev) for c in e.get("conditions", [])]


def sheet_of(project: Path) -> list | None:
    try:
        return json.loads((project / "eventSheets" / "Game.json").read_text(encoding="utf-8"))["events"]
    except (OSError, ValueError, KeyError):
        return None


def grade_add_countdown(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    code, out = checker(project)
    last = out.splitlines()[-1] if out else ""
    warnings = [line for line in out.splitlines() if line.startswith("warning:")]
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else last}"),
               (not warnings, warnings[0] if warnings else "no warning line")]
    events = sheet_of(project)
    if events is None:
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 5
    rows = list(walk(events))
    timers = [ev["name"] for ev, _ in rows if ev.get("eventType") == "variable" and ev["name"] not in ORIGINAL_GLOBALS]
    names = re.compile("|".join(map(re.escape, timers)) or r"$^", re.I)

    ticking = [(ev, above, a) for ev, above in rows for a in ev.get("actions", [])
               if a.get("id") in ("subtract-from-eventvar", "add-to-eventvar", "set-eventvar") and names.search(values([a]))]
    per_second, seen = False, "no action writes a countdown variable"
    for ev, above, a in ticking:
        conds = conditions_over(ev, above)
        every = [c for c in conds if c.get("id") == "every-x-seconds"]
        worded = "; ".join(c.get("id", "?") + "(" + values([c]) + ")" for c in conds) or "no condition"
        seen = f"{worded} -> {a['id']}({values([a])})"
        if any(values([c]).strip() in ("1", "1.0") for c in every) or re.search(r"\bdt\b", values([a]), re.I):
            per_second = True
            break
    results.append((per_second, seen))

    restarts = [(ev, above) for ev, above in rows if any(a.get("id") == "restart-layout" for a in ev.get("actions", []))]
    hit = next((ev for ev, above in restarts if names.search(values(conditions_over(ev, above)))), None)
    results.append((hit is not None, f"restart-layout under {values(hit['conditions'])}" if hit else
                    f"{len(restarts)} event(s) restart the layout, none reads {timers or 'a countdown variable'}"))

    texts = [(a, conditions_over(ev, above)) for ev, above in rows for a in ev.get("actions", [])
             if a.get("id") == "set-text" and a.get("objectClass") == "ScoreText"]
    later = [a for a, conds in texts if not any(c.get("id") == "on-start-of-layout" for c in conds)]
    both = [a for a in later if names.search(values([a])) and re.search(r"\bscore\b", values([a]))]
    results.append((bool(later) and len(both) == len(later),
                    f"{len(both)} of {len(later)} set-text after the start hold score and time: "
                    + "; ".join(values([a]) for a in later)))

    sized = [(a, conditions_over(ev, above)) for ev, above in rows for a in ev.get("actions", [])
             if a.get("objectClass") == "Coin" and a.get("id") in SIZE_ACTIONS]
    by_value = next(((a, conds) for a, conds in sized if re.search(r"value", values([a]) + values(conds), re.I)), None)
    results.append((by_value is not None, f"{by_value[0]['id']}({values([by_value[0]])}) under "
                    f"{values(by_value[1]) or 'no condition'}" if by_value else
                    f"{len(sized)} size or scale action(s) on Coin, none reads value"))

    original = json.loads((run / "fixture.json").read_text(encoding="utf-8")).get("eventSheets/Game.json.sids", [])
    have = {ev.get("sid") for ev, _ in rows}
    lost = [s for s in original if s not in have]
    results.append((bool(original) and not lost, f"{len(original) - len(lost)} of {len(original)} original event sids present"))
    return results


def grade_fix_load_errors(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    code, out = checker(project)
    results = [(code == 0, f"exit {code}: {out.splitlines()[-1] if out else ''}")]
    events = sheet_of(project)
    if events is None:
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 7
    rows = list(walk(events))
    conds = [(c, ev, above) for ev, above in rows for c in ev.get("conditions", [])]
    acts = [(a, ev, above) for ev, above in rows for a in ev.get("actions", [])]

    start = [c for c, _, _ in conds if c.get("id") == "on-start-of-layout"]
    results.append((bool(start) and not any(c.get("isInverted") for c in start),
                    f"isInverted: {[c.get('isInverted', False) for c in start]}"))
    touched = [c for c, _, _ in conds if c.get("id") == "on-touched-object"]
    results.append((bool(touched) and all(c["parameters"].get("type") == "start" for c in touched),
                    f"type: {[c['parameters'].get('type') for c in touched]}"))
    tweens = [a for a, _, _ in acts if a.get("id") == "tween-two-properties"]
    results.append((bool(tweens) and all(a.get("behaviorType") == "Tween" for a in tweens),
                    f"behaviorType: {[a.get('behaviorType') for a in tweens]}"))

    collect = next((ev for ev, _ in rows if ev.get("eventType") == "custom-ace-block"), None)
    inside = [c.get("id") for ev, above in rows if collect in above or ev is collect
              for c in ev.get("conditions", []) if c.get("id") in TWEEN_ENDS]
    results.append((collect is not None and not inside,
                    f"triggers inside Collect: {inside or 'none'}" if collect else "the custom action Collect is gone"))

    ids = [a.get("id") for a, _, _ in acts if a.get("objectClass") == "ScoreText"]
    results.append(("set-txt" not in ids and "set-text" in ids, f"ScoreText action ids: {ids}"))

    calls = [(ev, above) for a, ev, above in acts if a.get("callFunction") == "AddScore"]
    on_collect = [("Collect" if ev is collect or collect in above else "tween end")
                  for ev, above in calls
                  if ev is collect or collect in above
                  or any(c.get("id") in TWEEN_ENDS and c.get("objectClass") == "Coin" for c in conditions_over(ev, above))]
    in_broken = [w for w, (ev, above) in zip(on_collect, calls) if w == "tween end" and collect in above]
    results.append((bool(on_collect) and not in_broken, f"AddScore called from: {on_collect or 'nowhere on collect'}"
                    + (" (still inside Collect, under the trigger)" if in_broken else "")))
    kept = [a for a in (collect or {}).get("actions", []) if a.get("id") == "tween-two-properties"
            and "collect" in str(a.get("parameters", {}).get("tags", ""))]
    results.append((bool(kept), f"tween actions in Collect tagged collect: {len(kept)}"))
    return results


def grade_name_the_restart_event(run: Path) -> list[tuple[bool, str]]:
    path = run / "outputs" / "answer.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    answer = re.split(r"^#+\s*commands?\s+run", text, flags=re.I | re.M)[0]
    given = re.compile(r"\bevent(?:\s+number)?[\s:*#`]*(\d+)", re.I)
    numbers = sorted(set(map(int, given.findall(answer))))
    # 9 restarts; 8 is the group it sits in, and an answer may say so on a line that calls it the group.
    beside = sorted({int(n) for line in answer.splitlines() if not re.search(r"\bgroup\b", line, re.I)
                     for n in given.findall(line)} - {9})
    results = [(9 in numbers and not beside, f"event numbers the answer gives: {numbers or 'none'}"
                + (f"; as the event, not as its group: {beside}" if beside else ""))]
    parts = {"Coin.Count = 0": re.search(r"coin\.count`?\s*=+\s*`?0", answer, re.I),
             "Trigger once": re.search(r"trigger\s+once", answer, re.I),
             "1 second wait": re.search(r"\b(1|one)[\s-]*(s\b|sec)", answer, re.I)}
    results.append((all(parts.values()), "stated: " + ", ".join(k for k, v in parts.items() if v)
                    + ("; missing: " + ", ".join(k for k, v in parts.items() if not v) if not all(parts.values()) else "")))
    results.append(unchanged(run))
    return results


def unchanged(run: Path) -> tuple[bool, str]:
    want = {k: v for k, v in json.loads((run / "fixture.json").read_text(encoding="utf-8")).items() if not k.endswith(".sids")}
    project = run / "project"
    have = {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted(project.rglob("*"))
            if p.is_file() and p.name != "AGENTS.md" and not {".agents", "__pycache__"} & set(p.parts)}
    changed = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
    return not changed, f"files that differ from the fixture: {changed or 'none'}"


def grade_find_in_a_long_sheet(run: Path) -> list[tuple[bool, str]]:
    path = run / "outputs" / "answer.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    answer = re.split(r"^#+\s*commands?\s+run", text, flags=re.I | re.M)[0]
    # Every number that follows the word: "event 103", "events 104 and 105", "Events 103-105".
    numbers = sorted({int(n) for span in re.findall(r"\bevents?\b[^.\n]{0,40}", answer, re.I)
                      for n in re.findall(r"(?<![\w.])\d{1,3}(?![\w.]|\s*(?:seconds?|s\b|px|%))", span)})
    said = f"event numbers the answer gives: {numbers or 'none'}"
    return [(103 in numbers and bool(re.search(r"finish\s*line", answer, re.I)), said),
            (108 in numbers and "showgameover" in answer.lower() and bool(re.search(r"restart", answer, re.I)), said),
            (all(re.search(word, answer, re.I) for word in ("player", "success", "fail")),
             "stated: " + ", ".join(w for w in ("player", "success", "fail") if re.search(w, answer, re.I))),
            (bool(numbers) and all(102 <= n <= 108 for n in numbers), said),
            unchanged(run)]


VIEW_W, VIEW_H, UNIT, MARGIN, TOUCH = 720, 1280, 32, 32, 96      # the stand-in's viewport and its grid
HUD_LAYERS = {"ui", "hud"}


def grade_lay_out_the_hud(run: Path) -> list[tuple[bool, str]]:
    """The HUD the run added through the generator: on the UI layer, whole numbers, sizes in
    units, every type's box held against an edge or centred, the tapped button a finger wide,
    and tools/build_project.py the source of layouts/Game.json."""
    project = run / "project"
    code, out = checker(project)
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else (out.splitlines() or [''])[-1]}")]
    try:
        layout = json.loads((project / "layouts" / "Game.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return results + [(False, "layouts/Game.json is not readable JSON")] * 6
    hud = [inst for layer in layout.get("layers", []) if layer.get("name", "").lower() in HUD_LAYERS
           for inst in layer.get("instances", []) if "world" in inst]
    added = [i for i in hud if i["type"] != "ScoreText"]
    kinds = sorted({i["type"] for i in added})
    listed = ", ".join(f"{i['type']}@({i['world']['x']},{i['world']['y']} {i['world']['width']}x{i['world']['height']})"
                       for i in hud) or "no instance on a layer named UI or HUD"
    results.append((len(added) >= 3 and len(kinds) >= 2, f"{len(added)} added instance(s) of {kinds}: {listed}"))

    def whole(v) -> bool:
        return isinstance(v, (int, float)) and float(v).is_integer()

    fractions = [i["type"] for i in hud if not all(whole(i["world"][k]) for k in ("x", "y", "width", "height"))]
    results.append((bool(hud) and not fractions, f"fractional coordinates or sizes on: {fractions or 'none'}"))
    off = [f"{i['type']} {i['world']['width']}x{i['world']['height']}" for i in hud
           if not all(whole(i["world"][k]) and int(i["world"][k]) % UNIT == 0 for k in ("width", "height"))]
    results.append((bool(hud) and not off, f"sizes not in {UNIT} px units: {off or 'none'}"))

    def box(insts: list) -> tuple[float, float, float, float]:
        lefts = [i["world"]["x"] - i["world"].get("originX", 0) * i["world"]["width"] for i in insts]
        tops = [i["world"]["y"] - i["world"].get("originY", 0) * i["world"]["height"] for i in insts]
        rights = [l + i["world"]["width"] for l, i in zip(lefts, insts)]
        bottoms = [t + i["world"]["height"] for t, i in zip(tops, insts)]
        return min(lefts), min(tops), max(rights), max(bottoms)

    def held(lo: float, hi: float, size: float) -> bool:
        return abs(lo - MARGIN) <= 0.5 or abs(hi - (size - MARGIN)) <= 0.5 or abs((lo + hi) / 2 - size / 2) <= 0.5

    kinds = {kind: box([i for i in hud if i["type"] == kind]) for kind in sorted({i["type"] for i in hud})}
    loose = []
    for kind, (l, t, r, b) in kinds.items():
        # A second row: its top one unit under a box of another type that is itself held to the top or bottom.
        stacked = any(abs(t - (ob + UNIT)) <= 0.5 and held(ot, ob, VIEW_H)
                      for other, (ol, ot, orr, ob) in kinds.items() if other != kind)
        if not (held(l, r, VIEW_W) and (held(t, b, VIEW_H) or stacked)):
            loose.append(f"{kind} box ({l:g},{t:g})-({r:g},{b:g})")
    results.append((bool(hud) and not loose, f"boxes neither {MARGIN} px inside an edge, nor centred, nor one unit "
                                             f"under a held box: {loose or 'none'}"))

    boxes = [(i["type"], *box([i])) for i in hud]
    outside = [f"{k} ({l:g},{t:g})-({r:g},{b:g})" for k, l, t, r, b in boxes if l < 0 or t < 0 or r > VIEW_W or b > VIEW_H]
    results.append((bool(hud) and not outside, f"boxes reaching past the viewport: {outside or 'none'}"))
    overlaps = [f"{a[0]} ({a[1]:g},{a[2]:g})-({a[3]:g},{a[4]:g}) and {b[0]} ({b[1]:g},{b[2]:g})-({b[3]:g},{b[4]:g})"
                for n, a in enumerate(boxes) for b in boxes[n + 1:]
                if min(a[3], b[3]) - max(a[1], b[1]) > 0.5 and min(a[4], b[4]) - max(a[2], b[2]) > 0.5]
    results.append((bool(hud) and not overlaps, f"overlapping boxes: {overlaps or 'none'}"))

    button = [i for i in added if re.search(r"pause|button|btn", i["type"], re.I)]
    small = [f"{i['type']} {i['world']['width']}x{i['world']['height']}" for i in button
             if min(i["world"]["width"], i["world"]["height"]) < TOUCH]
    results.append((bool(button) and not small,
                    f"button(s) {[i['type'] for i in button] or 'none found by name'}; under {TOUCH} px: {small or 'none'}"))

    def plugin_of(kind: str) -> str | None:
        try:
            return json.loads((project / "objectTypes" / f"{kind}.json").read_text(encoding="utf-8")).get("plugin-id")
        except (OSError, ValueError):
            return None

    lives = [i for i in added if plugin_of(i["type"]) == "Sprite" and i not in button]
    per_type: dict[str, int] = {}
    for i in lives:
        per_type[i["type"]] = per_type.get(i["type"], 0) + 1
    three = [k for k, n in per_type.items() if n >= 3]
    wide = sorted({i["type"] for i in lives if i["world"]["width"] >= 3 * i["world"]["height"] - 0.5})
    results.append((bool(three or wide), f"sprite instances besides the button, by type: {per_type or 'none'}; "
                                          f"three of one type: {three or 'none'}; three times as wide as high: {wide or 'none'}"))

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "game"
        shutil.copytree(project, copy, ignore=shutil.ignore_patterns("__pycache__"))
        try:
            p = subprocess.run([sys.executable, "tools/build_project.py"], cwd=copy, capture_output=True, text=True,
                               encoding="utf-8", timeout=180, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            same = ((copy / "layouts" / "Game.json").read_bytes().replace(b"\r\n", b"\n")
                    == (project / "layouts" / "Game.json").read_bytes().replace(b"\r\n", b"\n"))
            said = (f"rerun exit {p.returncode}; layouts/Game.json {'identical' if same else 'differs'}"
                    + ("" if p.returncode == 0 else ": " + (p.stdout + p.stderr).strip().splitlines()[-1]))
            results.append((p.returncode == 0 and same, said))
        except (OSError, subprocess.TimeoutExpired) as e:
            results.append((False, f"rerun of tools/build_project.py: {type(e).__name__}: {e}"))
    return results


GRADERS = {"add-countdown": grade_add_countdown, "fix-load-errors": grade_fix_load_errors,
           "name-the-restart-event": grade_name_the_restart_event, "find-in-a-long-sheet": grade_find_in_a_long_sheet,
           "lay-out-the-hud": grade_lay_out_the_hud}


METRICS = ("pass_rate", "seconds", "tokens", "tool_calls", "lost_calls")


def spread(numbers: list[float]) -> dict | None:
    """The mean over the runs of one case and arm, with their deviation once there is more than one."""
    if not numbers:
        return None
    out = {"mean": round(statistics.mean(numbers), 3), "runs": len(numbers)}
    if len(numbers) > 1:
        out["stddev"] = round(statistics.stdev(numbers), 3)
    return out


def deltas(by_case: dict[str, dict[str, dict]]) -> dict:
    """with_skill less each other arm, over the cases both ran: what the skill
    buys in pass rate and costs in seconds, tokens and tool calls."""
    out = {}
    for other in sorted({arm for arms in by_case.values() for arm in arms} - {"with_skill"}):
        both = [arms for arms in by_case.values() if "with_skill" in arms and other in arms]
        out[f"with_skill - {other}"] = {"cases": len(both), **{
            key: round(statistics.mean(arms["with_skill"][key]["mean"] - arms[other][key]["mean"] for arms in pairs), 3)
            for key in METRICS if (pairs := [a for a in both if a["with_skill"].get(key) and a[other].get(key)])}}
    return out


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(sys.argv) == 2 else 1
    iteration = Path(sys.argv[1]).resolve()
    cells: dict[str, dict[str, list[dict]]] = {}      # case -> arm -> its runs
    void = []
    for name, case in CASES.items():
        for run in sorted(p for p in (iteration / name).glob("*") if (p / "project").is_dir()):
            reason = (run / "void.txt").read_text(encoding="utf-8").strip() if (run / "void.txt").exists() else None
            if reason:
                (run / "grading.json").write_text(json.dumps({"void": reason}, indent=2) + "\n", encoding="utf-8")
                void.append({"run": f"{name}/{run.name}", "reason": reason})
                print(f"{name}/{run.name}: void, not scored")
                continue
            graded = [{"text": text, "passed": ok, "evidence": evidence}
                      for text, (ok, evidence) in zip(case["assertions"], GRADERS[name](run), strict=True)]
            passed = sum(g["passed"] for g in graded)
            summary = {"passed": passed, "failed": len(graded) - passed, "total": len(graded),
                       "pass_rate": round(passed / len(graded), 3)}
            (run / "grading.json").write_text(json.dumps({"assertion_results": graded, "summary": summary},
                                                         indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            timing = json.loads((run / "timing.json").read_text(encoding="utf-8")) if (run / "timing.json").exists() else {}
            trace = json.loads((run / "trace.json").read_text(encoding="utf-8")) if (run / "trace.json").exists() else {}
            arm = re.sub(r"_\d+$", "", run.name)           # with_skill_2 is a second run of with_skill
            cells.setdefault(name, {}).setdefault(arm, []).append({
                "run": run.name, "passed": f"{passed}/{len(graded)}", "pass_rate": summary["pass_rate"],
                "tokens": timing.get("total_tokens"), "seconds": round(timing["duration_ms"] / 1000, 1) if timing else None,
                **{k: trace[k] for k in ("tool_calls", "lost_calls") if k in trace}})
            print(f"{name}/{run.name}: {passed}/{len(graded)}" + ("" if timing else "  (no timing.json)"))
            for g in graded:
                if not g["passed"]:
                    print(f"    FAIL {g['text']}\n         {g['evidence']}")
    if not cells and not void:
        sys.exit(f"{iteration} holds no <case>/<arm>/project of a case in evals.json")

    by_case = {name: {arm: {"runs": runs, **{key: spread([r[key] for r in runs if r.get(key) is not None]) for key in METRICS}}
                      for arm, runs in arms.items()} for name, arms in cells.items()}
    # Per arm, the mean of its cases' means: a deviation across different cases would measure the cases.
    arms = sorted({arm for case in by_case.values() for arm in case})
    summary = {arm: {key: round(statistics.mean(means), 3) for key in METRICS
                     if (means := [case[arm][key]["mean"] for case in by_case.values() if arm in case and case[arm].get(key)])}
               for arm in arms}
    summary["delta"] = deltas(by_case)
    (iteration / "benchmark.json").write_text(json.dumps(
        {"run_summary": summary, "by_case": by_case, "void_runs": void}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {iteration / 'benchmark.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
