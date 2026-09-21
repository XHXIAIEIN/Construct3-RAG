"""Grade the runs of one eval iteration and aggregate them.

    python evals/grade.py ITERATION_DIR

ITERATION_DIR holds <case>/<arm>/ with project/, outputs/answer.md,
fixture.json and, once the run has reported, timing.json. Every assertion of
evals/evals.json is checked by code against the files the run left, with the
clone's own checker, and written to <case>/<arm>/grading.json with the
evidence. benchmark.json sums the arms up and gives with_skill less each
other arm; a run with a trace.json (evals/trace.py --out) adds its tool calls
and the ones it lost.

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
import statistics
import subprocess
import sys
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
    numbers = sorted(set(map(int, re.findall(r"\bevent(?:\s+number)?[\s:*#`]*(\d+)", answer, re.I))))
    results = [(numbers == [9], f"event numbers the answer gives: {numbers or 'none'}")]
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


GRADERS = {"add-countdown": grade_add_countdown, "fix-load-errors": grade_fix_load_errors,
           "name-the-restart-event": grade_name_the_restart_event, "find-in-a-long-sheet": grade_find_in_a_long_sheet}


def mean(numbers: list[float]) -> dict | None:
    """A mean over the cases of an arm. No deviation: each case is run once per
    arm, and a spread across different cases measures the cases, not the arm."""
    return {"mean": round(statistics.mean(numbers), 3), "cases": len(numbers)} if numbers else None


def deltas(by_case: dict[str, dict[str, dict]]) -> dict:
    """with_skill less each other arm, over the cases both ran: what the skill
    buys in pass rate and costs in seconds, tokens and tool calls."""
    out = {}
    for other in sorted({arm for runs in by_case.values() for arm in runs} - {"with_skill"}):
        both = [runs for runs in by_case.values() if "with_skill" in runs and other in runs]
        out[f"with_skill - {other}"] = {"cases": len(both), **{
            key: round(statistics.mean(runs["with_skill"][key] - runs[other][key] for runs in pairs), 3)
            for key in ("pass_rate", "seconds", "tokens", "tool_calls", "lost_calls")
            if (pairs := [r for r in both if r["with_skill"].get(key) is not None and r[other].get(key) is not None])}}
    return out


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(sys.argv) == 2 else 1
    iteration = Path(sys.argv[1]).resolve()
    arms: dict[str, dict[str, list]] = {}
    by_case: dict[str, dict[str, dict]] = {}
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
            arm = arms.setdefault(run.name, {"pass_rate": [], "time_seconds": [], "tokens": [], "runs": []})
            arm["pass_rate"].append(summary["pass_rate"])
            arm["runs"].append(f"{name}: {passed}/{len(graded)}")
            by_case.setdefault(name, {})[run.name] = {
                "passed": f"{passed}/{len(graded)}", "pass_rate": summary["pass_rate"], "tokens": timing.get("total_tokens"),
                "seconds": round(timing["duration_ms"] / 1000, 1) if timing else None,
                **{k: trace[k] for k in ("tool_calls", "lost_calls") if k in trace}}
            if timing:
                arm["time_seconds"].append(timing["duration_ms"] / 1000)
                arm["tokens"].append(timing["total_tokens"])
            print(f"{name}/{run.name}: {passed}/{len(graded)}" + ("" if timing else "  (no timing.json)"))
            for g in graded:
                if not g["passed"]:
                    print(f"    FAIL {g['text']}\n         {g['evidence']}")
    if not arms and not void:
        sys.exit(f"{iteration} holds no <case>/<arm>/project of a case in evals.json")

    summary = {arm: {"pass_rate": mean(v["pass_rate"]), "time_seconds": mean(v["time_seconds"]),
                     "tokens": mean(v["tokens"]), "runs": v["runs"]} for arm, v in arms.items()}
    summary["delta"] = deltas(by_case)
    (iteration / "benchmark.json").write_text(json.dumps(
        {"runs_per_case_and_arm": 1, "run_summary": summary, "by_case": by_case, "void_runs": void}, indent=2) + "\n",
        encoding="utf-8")
    print(f"wrote {iteration / 'benchmark.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
