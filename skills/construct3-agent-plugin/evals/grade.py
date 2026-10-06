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
ORIGINAL_GLOBALS = {"score", "COIN_COUNT", "ROUND_COINS", "beat"}   # the stand-in's, before and after BEATS
SIZE_ACTIONS = {"set-size", "set-scale", "set-width", "set-height"}
TWEEN_ENDS = {"on-tweens-finished", "on-any-tweens-finished"}
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
COMPARE = {0: lambda a, b: a == b, 1: lambda a, b: a != b, 2: lambda a, b: a < b,      # the cmp parameter
           3: lambda a, b: a <= b, 4: lambda a, b: a > b, 5: lambda a, b: a >= b}


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
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 6
    rows = list(walk(events))
    timers = [ev["name"] for ev, _ in rows if ev.get("eventType") == "variable" and ev["name"] not in ORIGINAL_GLOBALS]
    # The Timer behavior is the other way, the one event-sheet-thinking.md names for a countdown: started for 30
    # seconds, restarting on On timer, the time left read from its expressions.
    holders = {ev["name"] for ev, _ in rows if ev.get("eventType") == "variable" and str(ev.get("initialValue")) == "30"}
    acts = [(a, conditions_over(ev, above)) for ev, above in rows for a in ev.get("actions", [])]
    started = [a for a, conds in acts if a.get("id") == "start-timer"
               and str(a.get("parameters", {}).get("duration", "")).strip() in {"30", "30.0", *holders}]
    tags = {str(a["parameters"].get("tag", "")) for a in started}
    names = re.compile("|".join([*map(re.escape, timers), r"\b(?:Duration|CurrentTime|TotalTime|NormalizedProgress)\s*\("])
                       if timers or started else r"$^", re.I)

    # A Timer started for 1 second, Regular, fires On timer once a second: the variable it takes 1 from counts down.
    ticks = {str(a["parameters"].get("tag", "")) for a, _ in acts if a.get("id") == "start-timer"
             and str(a.get("parameters", {}).get("duration", "")).strip() in {"1", "1.0"}
             and str(a["parameters"].get("type", "")).lower() == "regular"}

    def by_one(a: dict) -> bool:
        p = a.get("parameters", {})
        value = str(p.get("value", "")).strip()
        return (a.get("id") == "subtract-from-eventvar" and value in ("1", "1.0")
                or a.get("id") == "add-to-eventvar" and value in ("-1", "-1.0")
                or a.get("id") == "set-eventvar-value"
                and re.fullmatch(rf"{re.escape(str(p.get('variable', '')))}\s*-\s*1(?:\.0)?", value) is not None)

    ticking = [(ev, above, a) for ev, above in rows for a in ev.get("actions", [])
               if a.get("id") in ("subtract-from-eventvar", "add-to-eventvar", "set-eventvar-value") and names.search(values([a]))]
    per_second, seen = False, "no action writes a countdown variable"
    for ev, above, a in ticking:
        conds = conditions_over(ev, above)
        every = [c for c in conds if c.get("id") == "every-x-seconds"]
        on_tick = any(c.get("id") == "on-timer" and str(c.get("parameters", {}).get("tag", "")) in ticks for c in conds)
        worded = "; ".join(c.get("id", "?") + "(" + values([c]) + ")" for c in conds) or "no condition"
        seen = f"{worded} -> {a['id']}({values([a])})"
        if (any(values([c]).strip() in ("1", "1.0") for c in every) or re.search(r"\bdt\b", values([a]), re.I)
                or on_tick and by_one(a)):
            per_second = True
            break
    if not per_second and started:
        per_second, seen = True, f"Timer started for {started[0]['parameters']['duration']} seconds, tag {sorted(tags)}"
    results.append((per_second, seen))

    # A comparison of a countdown variable with a number has a direction: it holds once the countdown has
    # run out and not while 30 seconds are left. Countdown > 0 reads the variable and restarts at once.
    def runs_out(conds: list) -> bool | None:
        """False when a comparison of a countdown variable with a number holds at 30 or never at 0;
        None when no condition is such a comparison."""
        verdicts = []
        for c in conds:
            p = c.get("parameters", {})
            if c.get("id") == "compare-eventvar":
                left, right = str(p.get("variable", "")), str(p.get("value", ""))
            elif c.get("id") == "compare-two-values":
                left, right = str(p.get("first-value", "")), str(p.get("second-value", ""))
            else:
                continue
            left, right, op = left.strip(), right.strip(), COMPARE.get(p.get("comparison"))
            if op is None:
                continue
            if left in timers and NUMBER.fullmatch(right):
                at = {x: op(x, float(right)) for x in (30, 0, -0.5)}    # -0.5: a countdown that loses dt passes 0
            elif right in timers and NUMBER.fullmatch(left):
                at = {x: op(float(left), x) for x in (30, 0, -0.5)}
            else:
                continue
            if c.get("isInverted"):
                at = {x: not v for x, v in at.items()}
            verdicts.append(not at[30] and (at[0] or at[-0.5]))
        return all(verdicts) if verdicts else None

    restarts = [(ev, above) for ev, above in rows if any(a.get("id") == "restart-layout" for a in ev.get("actions", []))]
    hit = next((ev for ev, above in restarts if names.search(values(conditions_over(ev, above)))
                and runs_out(conditions_over(ev, above)) is not False
                or any(c.get("id") == "on-timer" and str(c.get("parameters", {}).get("tag", "")) in tags
                       for c in conditions_over(ev, above))), None)
    backwards = [ev for ev, above in restarts if runs_out(conditions_over(ev, above)) is False]
    results.append((hit is not None, f"restart-layout under {values(hit['conditions'])}" if hit else
                    f"restart-layout under {values(backwards[0]['conditions'])}, which holds while 30 seconds are "
                    f"left or never at 0" if backwards else
                    f"{len(restarts)} event(s) restart the layout, none reads {timers or 'a countdown variable'}"
                    + (f" or is On timer {sorted(tags)}" if tags else "")))

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

    # Restart layout keeps global variables (Construct3-Manual system-reference/system-actions.md): a countdown
    # set only by its declaration is still 0 once the layout has restarted, and never runs 30 seconds again.
    # A Timer started under On start of layout starts over with it: Start timer on a running tag restarts it.
    def starts_over(a: dict) -> bool:
        p = a.get("parameters", {})
        value = str(p.get("value", "")).strip()
        return a.get("id") == "reset-global-variables" or (
            a.get("id") == "set-eventvar-value" and p.get("variable") in timers
            and (value in ("30", "30.0") or (value in holders and value != p.get("variable"))))

    on_start = [a for a, conds in acts if any(c.get("id") == "on-start-of-layout" for c in conds)
                and (starts_over(a) or a in started)]
    at_restart = [a for a in (hit or {}).get("actions", []) if starts_over(a)]
    results.append((bool(on_start or at_restart),
                    "set back under On start of layout" if on_start else "set back in the restart on the countdown"
                    if at_restart else f"{timers} set back nowhere: after the first restart it is still 0"
                    if timers else "no countdown variable and no Timer started for 30 seconds on start"))
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


def system_text(locale: str, kind: str, ace: str) -> str:
    """The display text of a System condition or action in one locale, without its markup."""
    aces = json.loads((REPO / "data" / "c3-schemas" / locale / "plugins" / "system.json").read_text(encoding="utf-8"))[kind]
    return re.sub(r"\[/?[bi]\]", "", next(a["display-text"] for a in aces if a["id"] == ace))


# A run that answers in Chinese uses the zh-CN editor's wording: "事件 9", "仅触发一次", "等待 1 秒".
ZH_TRIGGER_ONCE = system_text("zh-CN", "conditions", "trigger-once-while-true")
ZH_SECONDS = system_text("zh-CN", "actions", "wait").split("{0}")[1].split()[0]
EVENT_NUMBER = re.compile(r"(?:\bevent(?:\s+number)?|事件(?:编号)?)[\s:：*#`]*(\d+)", re.I)


def grade_name_the_restart_event(run: Path) -> list[tuple[bool, str]]:
    answer = answer_of(run)
    numbers = [int(n) for n in EVENT_NUMBER.findall(answer)]
    # 9 restarts and 8 is the group it sits in. The first number is the answer; a later one may name another
    # event as context ("Setup (event 2) runs again"), and 8 may stand on a line that calls it the group.
    as_event = {int(n) for line in answer.splitlines() if not re.search(r"\bgroup\b|组", line, re.I)
                for n in EVENT_NUMBER.findall(line)}
    results = [(numbers[:1] == [9] and 8 not in as_event, f"event numbers the answer gives, in order: {numbers or 'none'}"
                + ("; 8 as the event, not as its group" if 8 in as_event else ""))]
    # "仅" is "only"; answers drop it.
    trigger_once = rf"trigger\s+once|{re.escape(ZH_TRIGGER_ONCE).replace('仅', '仅?')}"
    parts = {"Coin.Count = 0": re.search(r"coin\.count`?\s*=+\s*`?0", answer, re.I),
             "Trigger once": re.search(trigger_once, answer, re.I),
             "1 second wait": re.search(rf"\b(1|one)[\s-]*(s\b|sec)|(1|一)\s*{ZH_SECONDS}", answer, re.I)}
    results.append((all(parts.values()), "stated: " + ", ".join(k for k, v in parts.items() if v)
                    + ("; missing: " + ", ".join(k for k, v in parts.items() if not v) if not all(parts.values()) else "")))
    results.append(unchanged(run))
    return results


def unchanged(run: Path, allowed: tuple[str, ...] = ()) -> tuple[bool, str]:
    """Whether no project file differs from the fixture, with the list of those that do. A path that starts
    with one of `allowed` is skipped, and so are .tmp, where the skill's scripts write their results, and .git,
    which SKILL.md tells a run to create."""
    want = {k: v for k, v in json.loads((run / "fixture.json").read_text(encoding="utf-8")).items() if not k.endswith(".sids")}
    project = run / "project"
    have = {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted(project.rglob("*"))
            if p.is_file() and p.name != "AGENTS.md" and not {".agents", "__pycache__", ".tmp", ".git"} & set(p.parts)}
    changed = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k) and not k.startswith(allowed))
    return not changed, f"files that differ from the fixture: {changed or 'none'}"


def answer_of(run: Path) -> str:
    """The run's answer, without the list of commands it ran."""
    path = run / "outputs" / "answer.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return re.split(r"^#+\s*commands?\s+run", text, flags=re.I | re.M)[0]


def event_numbers(answer: str) -> list[int]:
    """Every number that follows "event" or "events" in the answer: "event 103", "events 104 and 105",
    "Events 103-105"."""
    return sorted({int(n) for span in re.findall(r"\bevents?\b[^.\n]{0,40}", answer, re.I)
                   for n in re.findall(r"(?<![\w.])\d{1,3}(?![\w.]|\s*(?:seconds?|s\b|px|%))", span)})


def grade_find_in_a_long_sheet(run: Path) -> list[tuple[bool, str]]:
    answer = answer_of(run)
    numbers = event_numbers(answer)
    said = f"event numbers the answer gives: {numbers or 'none'}"
    return [(103 in numbers and bool(re.search(r"finish\s*line", answer, re.I)), said),
            (108 in numbers and "showgameover" in answer.lower() and bool(re.search(r"restart", answer, re.I)), said),
            (all(re.search(word, answer, re.I) for word in ("player", "success", "fail")),
             "stated: " + ", ".join(w for w in ("player", "success", "fail") if re.search(w, answer, re.I))),
            # 87 to 91 abduct the player's tractor, the other way to game over; naming them is no error.
            (bool(numbers) and all(102 <= n <= 108 or 87 <= n <= 91 for n in numbers), said),
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
        return results + [(False, "layouts/Game.json is not readable JSON")] * (
            len(CASES["lay-out-the-hud"]["assertions"]) - len(results))
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


WIDTH_ACTIONS = {"set-width", "set-size", "set-scale"}
TWEEN_SIZE = {"width", "size", "scale", "offsetwidth", "offsetscalex"}      # the Tween combo's keys, lower-cased


def hud_instances(project: Path) -> list:
    try:
        layout = json.loads((project / "layouts" / "Game.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [inst for layer in layout.get("layers", []) if layer.get("name", "").lower() in HUD_LAYERS
            for inst in layer.get("instances", []) if "world" in inst]


def box_of(inst: dict) -> tuple[float, float, float, float]:
    w = inst["world"]
    left = w["x"] - w.get("originX", 0) * w["width"]
    top = w["y"] - w.get("originY", 0) * w["height"]
    return left, top, left + w["width"], top + w["height"]


def contains(outer: tuple, inner: tuple, slack: float = 1) -> bool:
    return (outer[0] - slack <= inner[0] and outer[1] - slack <= inner[1]
            and outer[2] + slack >= inner[2] and outer[3] + slack >= inner[3])


def plugin_id(project: Path, kind: str) -> str | None:
    try:
        return json.loads((project / "objectTypes" / f"{kind}.json").read_text(encoding="utf-8")).get("plugin-id")
    except (OSError, ValueError):
        return None


def frames_of(project: Path, kind: str) -> int:
    try:
        anims = json.loads((project / "objectTypes" / f"{kind}.json").read_text(encoding="utf-8")).get("animations")
    except (OSError, ValueError):
        return 0
    return sum(len(a.get("frames", [])) for a in anims.get("items", [])) if isinstance(anims, dict) else 0


def sheet_rows(project: Path) -> list:
    """Every event of every sheet with the events above it; [] when none is readable."""
    rows = []
    for path in sorted((project / "eventSheets").glob("*.json")):
        if path.name.endswith(".uistate.json"):
            continue
        try:
            rows += list(walk(json.loads(path.read_text(encoding="utf-8"))["events"]))
        except (OSError, ValueError, KeyError):
            pass
    return rows


def variables_starting_at(rows: list, initial: str) -> set[str]:
    names = {ev["name"] for ev, _ in rows if ev.get("eventType") == "variable" and str(ev.get("initialValue")) == initial}
    return names


def ivars_starting_at(project: Path, initial) -> set[str]:
    """Instance variables whose initial value on the type, or whose value on a layout
    instance, is `initial`."""
    names = set()
    for path in (project / "objectTypes").glob("*.json"):
        try:
            for v in json.loads(path.read_text(encoding="utf-8")).get("instanceVariables", []):
                if str(v.get("initialValue")) == str(initial):
                    names.add(v["name"])
        except (OSError, ValueError):
            pass
    for path in (project / "layouts").glob("*.json"):
        try:
            layout = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for layer in layout.get("layers", []):
            for inst in layer.get("instances", []):
                for k, v in inst.get("instanceVariables", {}).items():
                    if str(v) == str(initial):
                        names.add(k)
    return names


SET_VALUE = {"add-to-eventvar", "add-to-instvar", "subtract-from-eventvar", "subtract-from-instvar",
             "set-eventvar-value", "set-instvar-value"}


def value_actions(rows: list, names: set[str], ids: set[str] = SET_VALUE) -> list:
    pat = re.compile("|".join(map(re.escape, names)) or r"$^")
    return [a for ev, _ in rows for a in ev.get("actions", []) if a.get("id") in ids and pat.search(values([a]))]


def constants_at(rows: list, initial: str) -> set[str]:
    return {ev["name"] for ev, _ in rows if ev.get("eventType") == "variable" and str(ev.get("initialValue")) == initial}


def steps_by(rows: list, names: set[str], amount: str) -> list:
    """Actions that move one of the names by `amount`: a literal, a variable holding it, or the
    same with the sign in the action (`Add -1`, `Subtract 1`, `Set x - 1`)."""
    magnitude = amount.lstrip("-")
    holders = constants_at(rows, amount) | constants_at(rows, magnitude)
    number = re.compile(r"(?<![\w.])-?" + re.escape(magnitude) + r"(?![\w.])")
    holder = re.compile("|".join(map(re.escape, holders)) or r"$^")
    # A function handed the amount: `AddHealth(10)` whose body adds its parameter.
    passed = any(number.search(values([a])) for ev, _ in rows for a in ev.get("actions", [])
                 if "callFunction" in a or a.get("id") in ("call-function", "call-custom-action"))
    out = []
    for a in value_actions(rows, names):
        text = values([a])
        if number.search(text) or holder.search(text) or (passed and re.search(r"[+-]\s*[A-Za-z_]\w*", text)):
            out.append(a)
    return out


def aliases_of(rows: list, names: set[str]) -> set[str]:
    """The names plus every variable set from one of them: `lives` set to `MAX_LIVES`."""
    out = set(names)
    pat = re.compile("|".join(map(re.escape, names)) or r"$^")
    for ev, _ in rows:
        for a in ev.get("actions", []):
            p = a.get("parameters", {})
            if a.get("id") in ("set-eventvar-value", "set-instvar-value") and pat.search(str(p.get("value", ""))):
                out.add(p.get("variable") or p.get("instance-variable") or "")
    return {n for n in out if n}


def width_drivers(rows: list, names: set[str]) -> dict[str, list]:
    """Objects whose width an action sets from one of the names, by object, with the actions."""
    pat = re.compile("|".join(map(re.escape, names)) or r"$^")
    out: dict[str, list] = {}
    for ev, _ in rows:
        for a in ev.get("actions", []):
            params = a.get("parameters", {})
            is_width = a.get("id") in WIDTH_ACTIONS or (a.get("id") == "tween-one-property"
                                                       and str(params.get("property", "")).lower() in TWEEN_SIZE)
            if is_width and pat.search(values([a])):
                out.setdefault(a.get("objectClass"), []).append(a)
    return out


def generator_is_source(run: Path) -> tuple[bool, str]:
    project = run / "project"
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "game"
        shutil.copytree(project, copy, ignore=shutil.ignore_patterns("__pycache__"))
        try:
            p = subprocess.run([sys.executable, "tools/build_project.py"], cwd=copy, capture_output=True, text=True,
                               encoding="utf-8", timeout=180, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"rerun of tools/build_project.py: {type(e).__name__}: {e}"
        same = ((copy / "layouts" / "Game.json").read_bytes().replace(b"\r\n", b"\n")
                == (project / "layouts" / "Game.json").read_bytes().replace(b"\r\n", b"\n"))
        said = f"rerun exit {p.returncode}; layouts/Game.json {'identical' if same else 'differs'}"
        if p.returncode:
            said += ": " + ((p.stdout + p.stderr).strip().splitlines() or ["?"])[-1]
        return p.returncode == 0 and same, said


def checker_line(project: Path) -> tuple[bool, str]:
    code, out = checker(project)
    lines = out.splitlines() or [""]
    return code == 0, f"exit {code}: {lines[0] if code else lines[-1]}"


def grade_show_hp_as_a_bar(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    results = [checker_line(project)]
    rows = sheet_rows(project)
    hp = aliases_of(rows, variables_starting_at(rows, "40") | ivars_starting_at(project, 40))
    adds10 = steps_by(rows, hp, "10")
    results.append((bool(hp) and bool(adds10), f"variables at 40: {sorted(hp) or 'none'}; actions adding 10: {len(adds10)}"))
    pat = re.compile("|".join(map(re.escape, hp)) or r"$^")
    capped = [a for ev, _ in rows for a in ev.get("actions", []) if pat.search(values([a]))
              and re.search(r"\b(min|clamp)\s*\(", values([a]))]
    compared = [c for ev, _ in rows for c in ev.get("conditions", []) if pat.search(values([c])) and re.search(r"(?<![\d.])100(?![\d.])", values([c]))]
    results.append((bool(hp) and bool(capped or compared), f"min/clamp on it: {len(capped)}; comparisons with 100: {len(compared)}"))
    drivers = width_drivers(rows, hp)
    with_max = {k: v for k, v in drivers.items() if any(re.search(r"(?<![\d.])100(?![\d.])|max|/", values([a])) for a in v)}
    results.append((bool(with_max), f"width set from hp: {sorted(drivers) or 'none'}; with a maximum: {sorted(with_max) or 'none'}"))
    hud = hud_instances(project)
    fill = next((i for i in hud if i["type"] in with_max), None) or next((i for i in hud if i["type"] in drivers), None)
    ox = fill["world"].get("originX", 0) if fill else None
    results.append((fill is not None and ox in (0, 1), f"fill {fill['type'] if fill else 'none on the UI layer'} originX {ox}"))
    frame = next((i for i in hud if fill and i is not fill and i["type"] != fill["type"] and contains(box_of(i), box_of(fill))), None)
    results.append((frame is not None, f"frame around the fill: {frame['type'] if frame else 'none'}"))
    slides = [a for a in sum(drivers.values(), []) if a.get("id") == "tween-one-property"
              or (a.get("id") in WIDTH_ACTIONS and re.search(r"lerp\s*\(.*\bdt\b", values([a])))]
    results.append((bool(slides), f"sliding actions on the fill: {[a.get('id') for a in slides] or 'none'}"))
    score = next((i for i in hud if i["type"] == "ScoreText"), None)
    under = frame is not None and score is not None and box_of(frame)[1] >= box_of(score)[3] - 0.5
    inside = frame is not None and box_of(frame)[0] >= 0 and box_of(frame)[1] >= 0 and box_of(frame)[2] <= VIEW_W and box_of(frame)[3] <= VIEW_H
    results.append((under and inside, f"frame box {box_of(frame) if frame else None}, score bottom {box_of(score)[3] if score else None}"))
    results.append(generator_is_source(run))
    return results


def gradient_images(project: Path) -> set[str]:
    """Object types whose first image runs from one colour to another left to right."""
    try:
        from PIL import Image
    except ImportError:
        return set()
    out = set()
    for png in (project / "images").glob("*.png"):
        try:
            with Image.open(png) as im:
                im = im.convert("RGB")
                w, h = im.size
                if w < 16:
                    continue
                left = [im.getpixel((x, h // 2)) for x in range(0, max(1, w // 10))]
                right = [im.getpixel((x, h // 2)) for x in range(w - max(1, w // 10), w)]
                l = [sum(c[i] for c in left) / len(left) for i in range(3)]
                r = [sum(c[i] for c in right) / len(right) for i in range(3)]
                if sum(abs(a - b) for a, b in zip(l, r)) > 120:
                    out.add(png.stem.split("-")[0].lower())
        except OSError:
            pass
    return out


def painted_border(project: Path, kind: str) -> list[str]:
    """Images of the type whose outermost rows are dark while the middle row is not: a frame
    painted into the picture instead of a second object."""
    try:
        from PIL import Image
    except ImportError:
        return []
    out = []
    for png in (project / "images").glob(f"{kind.lower()}*.png"):
        try:
            with Image.open(png) as im:
                im = im.convert("RGB")
                w, h = im.size
                if w < 8 or h < 8:
                    continue
                def row(y: int) -> float:
                    return sum(sum(im.getpixel((x, y))) for x in range(w)) / w
                if max(row(0), row(h - 1)) + 60 < row(h // 2):
                    out.append(png.name)
        except OSError:
            pass
    return out


def grade_reveal_the_gradient(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    results = [checker_line(project)]
    rows = sheet_rows(project)
    hp = aliases_of(rows, variables_starting_at(rows, "40") | ivars_starting_at(project, 40))
    adds = steps_by(rows, hp, "10")
    results.append((bool(hp) and bool(adds), f"variables at 40: {sorted(hp) or 'none'}; actions adding 10: {len(adds)}"))
    hud = hud_instances(project)
    grads = gradient_images(project)
    shown = [i for i in hud if i["type"].lower() in grads]
    results.append((bool(shown), f"gradient images: {sorted(grads) or 'none'}; shown on the UI layer by: {sorted({i['type'] for i in shown}) or 'none'}"))
    drivers = width_drivers(rows, hp)
    all_width = {a.get("objectClass") for ev, _ in rows for a in ev.get("actions", []) if a.get("id") in WIDTH_ACTIONS
                 or (a.get("id") == "tween-one-property" and str(a.get("parameters", {}).get("property", "")).lower() in TWEEN_SIZE)}
    verdicts = []
    ok = False
    hp_pat = re.compile("|".join(map(re.escape, hp)) or r"$^")
    for i in shown:
        kind, plug = i["type"], plugin_id(project, i["type"])
        framed = [a for ev, _ in rows for a in ev.get("actions", []) if a.get("objectClass") == kind
                  and a.get("id") in ("set-animation-frame", "set-animation") and hp_pat.search(values([a]))]
        if kind in all_width:
            if plug == "TiledBg":
                ok = True; verdicts.append(f"{kind}: Tiled Background set by width, a cut of the painting")
            else:
                verdicts.append(f"{kind}: {plug} set by width, stretched")
        elif frames_of(project, kind) >= 2 and framed:
            ok = True; verdicts.append(f"{kind}: a strip of {frames_of(project, kind)} frames, the frame set from hp")
        else:
            cover = [j for j in hud if j["type"] in all_width and j is not i and j["world"].get("originX") == 1
                     and box_of(i)[0] - 1 <= box_of(j)[0] and box_of(j)[2] <= box_of(i)[2] + 1]
            atop = [j for j in hud if j["type"] in all_width and j["world"].get("blendMode") in ("source-atop", "source-in", "destination-in")]
            if cover:
                ok = True; verdicts.append(f"{kind} static, covered from the right by {cover[0]['type']}")
            elif atop:
                ok = True; verdicts.append(f"{kind} static, {atop[0]['type']} drawn {atop[0]['world']['blendMode']} over it")
            else:
                verdicts.append(f"{kind} static and nothing reveals it")
    results.append((ok and not any("stretched" in v for v in verdicts), "; ".join(verdicts) or "no gradient object"))
    framed_from_hp = {a.get("objectClass") for ev, _ in rows for a in ev.get("actions", [])
                      if a.get("id") in ("set-animation-frame", "set-animation") and hp_pat.search(values([a]))}
    readers = set(drivers) | framed_from_hp
    results.append((bool(readers), f"objects whose width or frame is set from hp: {sorted(readers) or 'none'}"))
    frame = None
    painted = []
    for i in shown:
        frame = next((j for j in hud if j is not i and j["type"] != i["type"] and contains(box_of(j), box_of(i))), None)
        if frame:
            break
        painted += painted_border(project, i["type"])
    results.append((frame is not None or bool(painted),
                    f"frame around the gradient: {frame['type'] if frame else 'no object'}; border painted into the image: {painted or 'none'}"))
    results.append(generator_is_source(run))
    return results


def grade_lives_as_hearts(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    results = [checker_line(project)]
    rows = sheet_rows(project)
    lives = aliases_of(rows, variables_starting_at(rows, "5") | ivars_starting_at(project, 5))
    subs = [a for a in steps_by(rows, lives, "1") if a.get("id").startswith("subtract") or "-" in values([a])]
    results.append((bool(lives) and bool(subs), f"variables at 5: {sorted(lives) or 'none'}; actions taking 1: {len(subs)}"))
    pat = re.compile("|".join(map(re.escape, lives)) or r"$^")
    by_width = width_drivers(rows, lives)
    # A count of icons on a Sprite whose frame is the count, or on instances picked against it: the
    # count itself, a loop index compared with it, or an index variable compared with what a
    # function was handed.
    by_frame = [a for ev, _ in rows for a in ev.get("actions", []) if a.get("id") in ("set-animation-frame", "set-animation") and pat.search(values([a]))]
    SHOWS = ("destroy", "set-visible", "set-animation-frame", "set-animation", "set-opacity")
    by_pick = [(ev, c) for ev, _ in rows for c in ev.get("conditions", [])
               if c.get("id") in ("pick-by-evaluate", "compare-instance-variable", "evaluate-expression", "compare-eventvar", "compare-two-values")
               and (pat.search(values([c])) or re.search(r"index|idx|slot|loopindex", values([c]) + str(c.get("parameters", {}).get("instance-variable", "")), re.I))
               and any(a.get("id") in SHOWS for a in ev.get("actions", []))]
    how = [k for k, v in (("width", by_width), ("frame", by_frame), ("pick", by_pick)) if v]
    results.append((bool(how), f"driven by the count through: {how or 'nothing'}"))
    hud = hud_instances(project)
    hearts = [i for i in hud if re.search(r"heart|life|lives", i["type"], re.I)]
    kinds = sorted({i["type"] for i in hearts})
    empty = []
    for kind in kinds:
        others = [i for i in hud if i["type"] != kind and any(contains(box_of(i), box_of(h), 2) or contains(box_of(h), box_of(i), 2) for h in hearts if h["type"] == kind)]
        if others:
            empty.append(f"{kind}: under it {sorted({o['type'] for o in others})}")
        if frames_of(project, kind) >= 2:
            empty.append(f"{kind}: {frames_of(project, kind)} frames")
    picked_shows = [ev for ev, c in by_pick if any(a.get("id") in ("set-animation-frame", "set-animation", "set-opacity", "set-visible") for a in ev.get("actions", []))]
    picked_destroys = [ev for ev, c in by_pick if any(a.get("id") == "destroy" for a in ev.get("actions", []))]
    if picked_shows:
        empty.append("picked hearts are shown empty, not destroyed")
    results.append((bool(empty) and not (picked_destroys and not picked_shows), "; ".join(empty) or f"no empty state found for {kinds or 'no heart type'}"))
    literal_compares = set()
    for ev, _ in rows:
        for c in ev.get("conditions", []):
            if pat.search(values([c])):
                # The operator is a number too ("comparison": 4 is "greater or equal"); only the operands count.
                operands = " | ".join(str(v) for k, v in c.get("parameters", {}).items() if k != "comparison")
                literal_compares |= set(re.findall(r"(?<![\w.])\d+(?![\w.])", operands))
    literal_compares -= {"0", "1"}
    results.append((bool(lives) and len(literal_compares) <= 2, f"literal numbers the count is compared with: {sorted(literal_compares) or 'none'}"))
    texts = [i for i in hud if i["type"] in ("ScoreText", "TimerText") or plugin_id(project, i["type"]) == "Text"]
    if hearts:
        boxes_ = [box_of(i) for i in hearts]
        l, t, r, b = min(x[0] for x in boxes_), min(x[1] for x in boxes_), max(x[2] for x in boxes_), max(x[3] for x in boxes_)
        centred = abs((l + r) / 2 - VIEW_W / 2) <= 0.5
        inside = l >= 0 and t >= 0 and r <= VIEW_W and b <= VIEW_H
        clear = not any(min(r, box_of(x)[2]) - max(l, box_of(x)[0]) > 0.5 and min(b, box_of(x)[3]) - max(t, box_of(x)[1]) > 0.5 for x in texts)
        results.append((centred and inside and clear, f"hearts box ({l:g},{t:g})-({r:g},{b:g}) centred {centred}, inside {inside}, clear of text {clear}"))
    else:
        results.append((False, "no heart instance on the UI layer"))
    results.append(generator_is_source(run))
    return results


NAVY = (0x02, 0x30, 0x47)


def contrast(a: tuple, b: tuple) -> float:
    """The contrast ratio of two RGB colours, 1 to 21 (WCAG 2.2, relative luminance)."""
    def luminance(c: tuple) -> float:
        lin = [v / 255 / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rgb255(colour: list) -> tuple:
    return tuple(round(c * 255) for c in colour[:3])


def one_colour(project: Path, kind: str) -> tuple | None:
    """The colour of a type whose first image shows one colour, else None."""
    try:
        from PIL import Image
    except ImportError:
        return None
    for png in sorted((project / "images").glob(f"{kind.lower()}*.png")):
        try:
            with Image.open(png) as im:
                shown = {c[:3] for n, c in (im.convert("RGBA").getcolors(1 << 20) or []) if c[3] == 255}
        except OSError:
            continue
        return next(iter(shown)) if len(shown) == 1 else None
    return None


def colours_of(project: Path, kind: str) -> set[tuple]:
    """The opaque colours of a type's first image; empty when it has none or PIL is missing."""
    try:
        from PIL import Image
    except ImportError:
        return set()
    for png in sorted((project / "images").glob(f"{kind.lower()}*.png")):
        try:
            with Image.open(png) as im:
                return {c[:3] for n, c in (im.convert("RGBA").getcolors(1 << 20) or []) if c[3] == 255}
        except OSError:
            continue
    return set()


def background_colours(layout: dict, project: Path) -> tuple[set[tuple], str]:
    """What the viewport shows behind the game: the image of an instance on the Background layer that
    covers the viewport (the template's backdrop), else the layer's colour when it is opaque."""
    back = next((layer for layer in layout.get("layers", []) if layer.get("name", "").lower() == "background"), None)
    if back is None:
        return set(), "no Background layer"
    cover = next((i for i in reversed(back.get("instances", []))
                  if contains(box_of(i), (0, 0, VIEW_W, VIEW_H)) and colours_of(project, i["type"])), None)
    if cover:
        return colours_of(project, cover["type"]), f"{cover['type']} covering the viewport"
    if back.get("isTransparent", True):
        return set(), "a transparent Background layer and nothing covering the viewport"
    return {rgb255(back["backgroundColor"])}, "the Background layer's colour"


def grade_readable_on_a_dark_background(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    results = [checker_line(project)]
    try:
        layout = json.loads((project / "layouts" / "Game.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return results + [(False, "layouts/Game.json is not readable JSON")] * 5
    # The template's backdrop covers the layer: its colour alone is never seen. Its labels are dark ink on
    # light grey, so the navy is what puts readability at stake.
    shown, source = background_colours(layout, project)
    dark = bool(shown) and all(abs(a - b) <= 40 for colour in shown for a, b in zip(colour, NAVY))
    results.append((dark, f"{source}: {sorted(shown) or 'no colour'}"))
    hud = hud_instances(project)
    texts = [i for i in hud if plugin_id(project, i["type"]) == "Text"]
    # The first round deals fewer coins than six; the label starts from the count, not a number.
    left = [i for i in texts if re.search(r"left", str(i["properties"].get("text", "")), re.I)]
    rows = sheet_rows(project)
    changed = {a.get("parameters", {}).get("variable") or a.get("parameters", {}).get("instance-variable")
               for ev, _ in rows for a in ev.get("actions", []) if a.get("id") in SET_VALUE}
    setters = [a for ev, _ in rows for a in ev.get("actions", []) if a.get("id") == "set-text"
               and a.get("objectClass") in {i["type"] for i in left}]
    counted = [a for a in setters if re.search(r"\.Count\b", values([a]))
               or set(re.findall(r"[A-Za-z_]\w*", values([a]))) & {c for c in changed if c}]
    results.append((bool(left) and bool(counted), f"labels saying Left: {[i['type'] for i in left] or 'none'}; "
                                                  f"set-text from the coins left: {len(counted)} of {len(setters)}"))
    score = next((i for i in texts if i["type"] == "ScoreText"), None)
    if left:
        l, t, r, b = box_of(left[0])
        off = score is None or not (min(r, box_of(score)[2]) - max(l, box_of(score)[0]) > 0.5
                                    and min(b, box_of(score)[3]) - max(t, box_of(score)[1]) > 0.5)
        placed = l >= 0 and t >= 0 and r <= VIEW_W and b <= VIEW_H and r >= VIEW_W * 3 / 4 and t <= VIEW_H / 4 and off
        results.append((placed, f"{left[0]['type']} box ({l:g},{t:g})-({r:g},{b:g}), clear of ScoreText {off}"))
    else:
        results.append((False, "no Left label on the UI layer"))
    verdicts, ok = [], bool(texts) and bool(shown)
    for i in texts:
        fg = rgb255(i["properties"].get("color", [1, 1, 1, 1]))
        panel = next((one_colour(project, j["type"]) for j in hud if j is not i and plugin_id(project, j["type"]) != "Text"
                      and contains(box_of(j), box_of(i)) and one_colour(project, j["type"])), None)
        behind = {panel} if panel else shown
        ratio = min((contrast(fg, b) for b in behind), default=0)
        ok = ok and ratio >= 4.5
        verdicts.append(f"{i['type']} {fg} on {'panel ' if panel else ''}{sorted(behind)}: {ratio:.1f}:1")
    results.append((ok, "; ".join(verdicts) or "no Text on the UI layer"))
    results.append(generator_is_source(run))
    return results


def triggered(project: Path):
    """A test of whether a condition is a trigger, from the clone's schemas."""
    sys.path.insert(0, str(SKILL / "scripts"))
    import c3project as c3
    p = c3.Project(project, REPO, "en-US", c3.Findings())
    return lambda c: bool((p.ace_entry("conditions", c) or {}).get("isTrigger"))


def original_sids(run: Path, rows: list, sheet: str) -> tuple[bool, str]:
    original = json.loads((run / "fixture.json").read_text(encoding="utf-8")).get(f"eventSheets/{sheet}.sids", [])
    have = {ev.get("sid") for ev, _ in rows}
    lost = [s for s in original if s not in have]
    return bool(original) and not lost, f"{len(original) - len(lost)} of {len(original)} original event sids present"


WASD = {87: "up", 65: "left", 83: "down", 68: "right"}
ARROWS = {38: "up", 37: "left", 40: "down", 39: "right"}


def grade_walk_with_wasd(run: Path) -> list[tuple[bool, str]]:
    """Each letter holds its control: Simulate control under Key is down with no trigger in the branch,
    since a simulated control holds for the tick it runs in."""
    project = run / "project"
    code, out = checker(project)
    original = set(json.loads((run / "fixture.json").read_text(encoding="utf-8")).get("eventSheets/event sheet 1.json.sids", []))
    # The example warns on a Spawn another object of its own; a warning on an event the run added names a new sid.
    warnings = [line for line in out.splitlines() if line.startswith("warning:")
                and not ((m := re.search(r"\(sid (\d+)\)", line)) and int(m.group(1)) in original)]
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else out.splitlines()[-1]}"),
               (not warnings, warnings[0] if warnings else "no warning line on an added event")]
    try:
        events = json.loads((project / "eventSheets" / "event sheet 1.json").read_text(encoding="utf-8"))["events"]
    except (OSError, ValueError, KeyError):
        return results + [(False, "eventSheets/event sheet 1.json is not readable JSON")] * 3
    rows = list(walk(events))
    is_trigger = triggered(project)
    held: dict[int, set[str]] = {}      # key code -> the controls simulated while it is down
    pressed = []
    for ev, above in rows:
        conds = conditions_over(ev, above)
        moves = [a for a in ev.get("actions", []) if a.get("id") == "simulate-control" and a.get("objectClass") == "Player"]
        if not moves:
            continue
        # Key is down takes the key as a code, Key code is down as an expression.
        keys = [c.get("parameters", {}).get("key") for c in conds if c.get("id") == "key-is-down"] +             [int(k) for c in conds if c.get("id") == "key-code-is-down"
             if (k := str(c.get("parameters", {}).get("keycode", "")).strip()).isdigit()]
        triggers = [c for c in conds if is_trigger(c)]
        for a in moves:
            control = a.get("parameters", {}).get("control")
            if triggers:
                pressed.append(f"{control} under {triggers[0].get('id')}")
                continue
            for k in keys:
                if isinstance(k, int):
                    held.setdefault(k, set()).add(control)
    missing = [f"{chr(k)} {d}" for k, d in WASD.items() if d not in held.get(k, set())]
    results.append((not missing and not pressed, "held: " + ", ".join(f"{chr(k)} {d}" for k, d in WASD.items()
                    if d in held.get(k, set())) + (f"; missing: {missing}" if missing else "")
                    + (f"; under a trigger: {pressed}" if pressed else "")))
    layout = json.loads((project / "layouts" / "layout 1.json").read_text(encoding="utf-8"))
    on = [i.get("behaviors", {}).get("8Direction", {}).get("properties", {}).get("default-controls")
          for layer in layout["layers"] for i in layer.get("instances", []) if i.get("type") == "Player"]
    arrows = all(d in held.get(k, set()) for k, d in ARROWS.items())
    results.append((bool(on) and all(on) or arrows, f"Default controls {on}, arrows held under Key is down: {arrows}"))
    results.append(original_sids(run, rows, "event sheet 1.json"))
    return results


def seconds_of(a: dict) -> float:
    try:
        return float(str(a.get("parameters", {}).get("seconds", "")).strip())
    except ValueError:
        return 0.0


def grade_countdown_between_rounds(run: Path) -> list[tuple[bool, str]]:
    """The countdown starts once when the round ends, shows 3, 2 and 1, and the restart waits for it."""
    project = run / "project"
    code, out = checker(project)
    warnings = [line for line in out.splitlines() if line.startswith("warning:")]
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else out.splitlines()[-1]}"),
               (not warnings, warnings[0] if warnings else "no warning line")]
    events = sheet_of(project)
    if events is None:
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 4
    rows = list(walk(events))
    is_trigger = triggered(project)
    paced = {"trigger-once-while-true", "every-x-seconds", "is-timer-running"}
    starts = [(a, conditions_over(ev, above)) for ev, above in rows for a in ev.get("actions", []) if a.get("id") == "start-timer"]
    every_tick = [a for a, conds in starts if not any(is_trigger(c) or c.get("id") in paced for c in conds)]
    results.append((not every_tick, f"{len(starts)} Start timer, {len(every_tick)} in an event that runs every tick"
                    + (": " + "; ".join(values([a]) for a in every_tick) if every_tick else "")))

    texts = [a for ev, _ in rows for a in ev.get("actions", []) if a.get("id") == "set-text"
             and a.get("objectClass") == "ScoreText" and re.search(r"next\s*round", values([a]), re.I)]
    reads = [a for a in texts if re.search(r"&\s*[A-Za-z(]", values([a]))]
    counted = {n for a in texts for n in re.findall(r"\b([123])\b", values([a]))}
    results.append((bool(reads) or counted >= {"1", "2", "3"},
                    f"{len(texts)} Set text with Next round; " + ("reads " + values(reads[:1]) if reads else f"literals {sorted(counted)}")))

    after = []
    for ev, above in rows:
        actions = ev.get("actions", [])
        for i, a in enumerate(actions):
            if a.get("id") != "restart-layout":
                continue
            conds = conditions_over(ev, above)
            waited = sum(seconds_of(w) for w in actions[:i] if w.get("id") == "wait") + \
                sum(seconds_of(w) for e in above for w in e.get("actions", []) if w.get("id") == "wait")
            on_timer = any(c.get("id") == "on-timer" for c in conds)
            reaches_0 = any(re.search(r"(?:^|\|\s*)0(?:\.0)?\s*(?:\||$)", values([c])) for c in conds
                            if c.get("id") in ("compare-eventvar", "compare-two-values", "compare-instance-variable")
                            and ".count" not in values([c]).lower())
            after.append((on_timer or waited >= 3 or reaches_0,
                          f"Restart layout {'under On timer' if on_timer else f'after {waited:g} s of Wait'}"
                          + (", under a test of 0" if reaches_0 else "")))
    results.append((any(ok for ok, _ in after), "; ".join(said for _, said in after) or "no Restart layout"))
    results.append(original_sids(run, rows, "Game.json"))
    return results


SEEDED = re.compile(r"^6(?:333|444|555)\d{11}$")     # the sids make_fixtures.py gives the entries it seeds


def grade_fix_wasd_twitch(run: Path) -> list[tuple[bool, str]]:
    """The seeded On key pressed events walk for one tick a press; the fix holds each key with Key is down.
    The checks are walk-with-wasd's, with the seeded events counted as the run's own."""
    results = grade_walk_with_wasd(run)
    original = json.loads((run / "fixture.json").read_text(encoding="utf-8")).get("eventSheets/event sheet 1.json.sids", [])
    example = {s for s in original if not SEEDED.match(str(s))}
    code, out = checker(run / "project")
    warnings = [line for line in out.splitlines() if line.startswith("warning:")
                and not ((m := re.search(r"\(sid (\d+)\)", line)) and int(m.group(1)) in example)]
    results[1] = (not warnings, warnings[0] if warnings else "no warning line on an added or seeded event")
    events = json.loads((run / "project" / "eventSheets" / "event sheet 1.json").read_text(encoding="utf-8"))["events"]
    have = {ev.get("sid") for ev, _ in walk(events)}
    lost = [s for s in example if s not in have]
    results[4] = (bool(example) and not lost, f"{len(example) - len(lost)} of {len(example)} example event sids present")
    return results


def grade_fix_next_round(run: Path) -> list[tuple[bool, str]]:
    """The seeded round end starts its Timer in every tick; the fix starts it once, and Restart layout
    and Set beat still run once per round."""
    project = run / "project"
    code, out = checker(project)
    warnings = [line for line in out.splitlines() if line.startswith("warning:")]
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else out.splitlines()[-1]}"),
               (not warnings, warnings[0] if warnings else "no warning line")]
    events = sheet_of(project)
    if events is None:
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 3
    rows = list(walk(events))
    is_trigger = triggered(project)
    paced = {"trigger-once-while-true", "every-x-seconds", "is-timer-running"}
    acts = [(a, conditions_over(ev, above)) for ev, above in rows for a in ev.get("actions", [])]
    every_tick = [a for a, conds in acts if a.get("id") == "start-timer"
                  and not any(is_trigger(c) or c.get("id") in paced for c in conds)]
    results.append((not every_tick, f"{sum(a.get('id') == 'start-timer' for a, _ in acts)} Start timer, "
                    f"{len(every_tick)} in an event that runs every tick"))
    once = [(a, conds) for a, conds in acts if a.get("id") == "restart-layout"
            or (a.get("id") == "set-eventvar-value" and a.get("parameters", {}).get("variable") == "beat")]
    loose = [a["id"] for a, conds in once if not any(is_trigger(c) or c.get("id") == "trigger-once-while-true" for c in conds)]
    results.append((bool(once) and not loose, f"{len(once)} Restart layout or Set beat, every tick: {loose or 'none'}"))
    original = json.loads((run / "fixture.json").read_text(encoding="utf-8")).get("eventSheets/Game.json.sids", [])
    game = [s for s in original if not SEEDED.match(str(s))]
    have = {ev.get("sid") for ev, _ in rows}
    lost = [s for s in game if s not in have]
    results.append((bool(game) and not lost, f"{len(game) - len(lost)} of {len(game)} game event sids present"))
    return results


TURN_CHANGES = {"set-eventvar-value", "toggle-boolean-eventvar", "add-to-eventvar", "subtract-from-eventvar"}


def grade_fix_turn_flip(run: Path) -> list[tuple[bool, str]]:
    """The seeded Else passes the turn in every tick; the fix passes it once per tapped coin: in the tap's
    branch or another trigger's, in the custom action or function the tap calls, or in an event that resets
    a variable it tests."""
    project = run / "project"
    code, out = checker(project)
    warnings = [line for line in out.splitlines() if line.startswith("warning:")]
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else out.splitlines()[-1]}"),
               (not warnings, warnings[0] if warnings else "no warning line")]
    events = sheet_of(project)
    if events is None:
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 2
    rows = list(walk(events))
    is_trigger = triggered(project)
    once, every_tick = [], []
    for ev, above in rows:
        for a in ev.get("actions", []):
            params = a.get("parameters") if isinstance(a.get("parameters"), dict) else {}
            if params.get("variable") != "side" or a.get("id") not in TURN_CHANGES \
                    or (a.get("id") == "set-eventvar-value" and str(params.get("value")).strip() == "1"):
                continue
            conds = conditions_over(ev, above)
            in_block = any(e.get("eventType") in ("function-block", "custom-ace-block") for e in (*above, ev))
            tested = {c.get("parameters", {}).get("variable") for c in conds if c.get("id") == "compare-eventvar"}
            reset = {b.get("parameters", {}).get("variable") for e in (*above, ev) for b in e.get("actions", [])
                     if b.get("id") == "set-eventvar-value"} - {"side"}
            (once if in_block or any(is_trigger(c) for c in conds) or tested & reset else every_tick).append(values([a]))
    results.append((bool(once) and not every_tick, f"side changes once per tap: {once or 'nowhere'}"
                    + (f"; in every tick: {every_tick}" if every_tick else "")))
    original = json.loads((run / "fixture.json").read_text(encoding="utf-8")).get("eventSheets/Game.json.sids", [])
    game = [s for s in original if not SEEDED.match(str(s))]
    have = {ev.get("sid") for ev, _ in rows}
    lost = [s for s in game if s not in have]
    results.append((bool(game) and not lost, f"{len(game) - len(lost)} of {len(game)} game event sids present"))
    return results


TURN_NAME = re.compile(r"turn|player|side|current|whose|active", re.I)
# A time or a score is not the turn, though its name may say player or current: turnTimeLeft, player1Score.
NOT_TURN = re.compile(r"time|timer|sec|clock|left|limit|count|remain|score|point", re.I)


def grade_two_player_turns(run: Path) -> list[tuple[bool, str]]:
    """The turn variable is the run's own: its name says whose turn it is, or ScoreText's text reads it, and it
    is not named for a time or a score. Each change of it runs once: under a trigger, in a function or custom
    action, or in an event that resets a variable it tests, a function the event calls included. A flip reads
    the variable (3 - turn, Toggle) or runs under a condition that tests it; a set to a fixed value is a reset,
    which also runs once under Trigger once or Every X seconds. One flip sits under the tap or in a function or
    custom action. A change under On start of layout is not read."""
    project = run / "project"
    code, out = checker(project)
    warnings = [line for line in out.splitlines() if line.startswith("warning:")]
    results = [(code == 0, f"exit {code}: {out.splitlines()[0] if code else out.splitlines()[-1]}"),
               (not warnings, warnings[0] if warnings else "no warning line")]
    events = sheet_of(project)
    if events is None:
        return results + [(False, "eventSheets/Game.json is not readable JSON")] * 3
    rows = list(walk(events))
    texts = [a for ev, _ in rows for a in ev.get("actions", [])
             if a.get("objectClass") == "ScoreText" and a.get("id") == "set-text"]

    def reads(name: str, text: str) -> bool:
        return bool(re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", text, re.I))

    new = {ev["name"] for ev, _ in rows if ev.get("eventType") == "variable"} - ORIGINAL_GLOBALS
    turns = {n for n in new if (TURN_NAME.search(n) or reads(n, values(texts))) and not NOT_TURN.search(n)}
    sets_in = {ev.get("functionName"): {a.get("parameters", {}).get("variable") for e, _ in walk([ev])
                                        for a in e.get("actions", []) if a.get("id") == "set-eventvar-value"}
               for ev, _ in rows if ev.get("eventType") == "function-block"}
    is_trigger = triggered(project)
    once, every_tick, on_tap = [], [], []
    for ev, above in rows:
        conds = conditions_over(ev, above)
        if any(c.get("id") == "on-start-of-layout" for c in conds):
            continue
        for a in ev.get("actions", []):
            params = a.get("parameters") if isinstance(a.get("parameters"), dict) else {}
            name = params.get("variable")
            if name not in turns or a.get("id") not in TURN_CHANGES:
                continue
            in_block = any(e.get("eventType") in ("function-block", "custom-ace-block") for e in (*above, ev))
            # the variables its conditions test, and those its branch or the functions it calls set
            tested = {c.get("parameters", {}).get("variable") for c in conds if c.get("id") == "compare-eventvar"}
            tested |= {w for c in conds if c.get("id") in ("compare-two-values", "evaluate-expression")
                       for w in re.findall(r"[A-Za-z_]\w*", values([c]))}
            branch = [b for e in (*above, ev) for b in e.get("actions", [])]
            reset = {b.get("parameters", {}).get("variable") for b in branch if b.get("id") == "set-eventvar-value"}
            reset = (reset | {v for b in branch for v in sets_in.get(b.get("callFunction"), ())}) - {name}
            flip = a.get("id") != "set-eventvar-value" or reads(name, str(params.get("value", ""))) or name in tested
            # Trigger once runs a reset once, but a flip once a round
            paced = any(is_trigger(c) for c in conds) or (not flip and any(
                c.get("id") in ("trigger-once-while-true", "every-x-seconds") for c in conds))
            (once if in_block or paced or tested & reset else every_tick).append(f"{name}: {values([a])}")
            if flip and (in_block or any(is_trigger(c) and c.get("objectClass") in ("Touch", "Mouse") for c in conds)):
                on_tap.append(f"{name}: {values([a])}")
    results.append((bool(on_tap) and not every_tick, f"turn variables {sorted(turns) or 'none'}; changed once: "
                    f"{once or 'nowhere'}; on a tap: {on_tap or 'nowhere'}"
                    + (f"; in every tick: {every_tick}" if every_tick else "")))
    said = [values([a]) for a in texts if any(reads(n, values([a])) for n in turns) or re.search(r"player", values([a]), re.I)]
    results.append((bool(said), f"ScoreText texts that say whose turn: {said or 'none'}"))
    results.append(original_sids(run, rows, "Game.json"))
    return results


def drag_examples() -> dict[str, str]:
    """The official examples that use the Drag & Drop behavior, id to name."""
    out = {}
    for path in sorted((REPO / "data" / "c3-examples" / "en-US").glob("*.json")):
        e = json.loads(path.read_text(encoding="utf-8"))
        if "DragnDrop" in e.get("used-addons", {}).get("behaviors", []):
            out[e["id"]] = e.get("name", "")
    return out


def drop_events(example: str) -> set[int]:
    """The event numbers at which an example's sheets hold On drop, as print_sheet.py numbers them, over its
    folders: <id>, or <id>-js and <id>-ts."""
    sys.path.insert(0, str(SKILL / "scripts"))
    import c3project as c3
    folder = c3.siblings_folder(REPO) / "Construct-Example-Projects" / "example-projects"
    numbers = set()
    for end in ("", "-js", "-ts"):
        if (folder / f"{example}{end}" / "project.c3proj").is_file():
            out = subprocess.run([sys.executable, str(SKILL / "scripts" / "print_sheet.py"), "--project",
                                  str(folder / f"{example}{end}"), "--rag", str(REPO), "--limit", "0"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8")).stdout
            numbers |= {int(n) for n in re.findall(r"^\s*(\d+)\s+.*\bOn \w+ drop\b", out, re.M)}
    return numbers


# The words an answer uses for each trap in the pitfall entries on dragging
DRAG_TRAPS = {"moves only when the pointer moves": r"only\s+(?:when|while|if)\s+the\s+(?:pointer|mouse|finger|cursor)\s+"
              r"(?:moves|is\s+moving)|set\s+position\b.{0,80}\boverwrit",
              "a slot reads empty": r"collisions?\s+(?:are\s+|is\s+)?(?:disabled|off)|reads?\s+(?:as\s+)?empty|lands?\s+on\s+top",
              "the Mouse object ignores a finger": r"\bmouse\b.{0,80}\b(?:ignores?|only)\b.{0,40}\b(?:finger|touch|pen)",
              "Pick children in On drop": r"pick\s+children"}


def grade_find_a_drag_example(run: Path) -> list[tuple[bool, str]]:
    answer = answer_of(run)
    named = {i: n for i, n in drag_examples().items()
             if re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", answer, re.I) or (n and re.search(re.escape(n), answer, re.I))}
    numbers = event_numbers(answer)
    drops = {i: sorted(drop_events(i)) for i in named}
    hit = {i: sorted(set(d) & set(numbers)) for i, d in drops.items() if set(d) & set(numbers)}
    traps = [k for k, pattern in DRAG_TRAPS.items() if re.search(pattern, answer, re.I | re.S)]
    return [(bool(named), f"Drag & Drop examples the answer names: {sorted(named) or 'none'}"),
            (bool(hit), f"event numbers the answer gives: {numbers or 'none'}; On drop in the named examples: "
                        f"{drops or 'none'}"),
            (bool(traps), f"traps named: {traps or 'none'}"),
            unchanged(run)]


def grade_script_shift_and_edges(run: Path) -> list[tuple[bool, str]]:
    path = run / "project" / "scripts" / "main.ts"
    code = path.read_text(encoding="utf-8") if path.exists() else ""
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)      # a comment can name what the code does not do
    code = re.sub(r"getLayout\([^)]*\)", "layout", code)            # a layout got by name is read as runtime.layout
    keys = [k or n for k, n in re.findall(r"isKeyDown\(\s*(?:[\"'`](\w+)[\"'`]|(\d+))\s*\)", code)]
    arrows = {"ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"} - set(keys)
    shift = [k for k in keys if k.lower().startswith("shift") or k == "16"]
    double = re.search(r"\*\s*2(?![\d.])|(?<![\w.])2\s*\*|\?\s*2(?![\d.])|=\s*2\s*;|\b400\b", code)
    layout = [w for w in ("width", "height") if re.search(rf"layout\.{w}\b", code)]
    own = re.search(r"(?<!layout)\.(?:width|height)\b|getBoundingBox", code)
    return [(bool(code) and not arrows, f"arrow keys tested: {sorted(set(keys) & {'ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown'})}"
                                        + (f"; missing: {sorted(arrows)}" if arrows else "")),
            (bool(shift and double), f"Shift keys tested: {shift or 'none'}; doubled: {double.group(0) if double else 'no'}"),
            (len(layout) == 2 and bool(own), f"layout sides read: {layout or 'none'}; the player's size: "
                                             f"{own.group(0) if own else 'not read'}"),
            # open_in_editor.py --typescript writes scripts/ts-defs/ and scripts/tsconfig.json
            unchanged(run, ("scripts/main.ts", "scripts/ts-defs/", "scripts/tsconfig.json"))]


def grade_platform_state_in_chinese(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    read = [p.relative_to(project).as_posix() for p in sorted((project / ".tmp").rglob("*.json"))
            if "behaviors.platform.properties.max-speed" in p.read_text(encoding="utf-8", errors="replace")]
    answer = answer_of(run)
    floor = re.search(r"地面上|站在地|落地|着地|落在地|on\s+the\s+(?:floor|ground)", answer, re.I)
    numbers = [n for n in ("330", "650", "1500") if re.search(rf"(?<!\d){n}(?!\d)", answer)]
    texts = json.loads((REPO / "data" / "c3-lang" / "zh-CN.json").read_text(encoding="utf-8"))["text"]
    names = [texts["behaviors"]["platform"]["properties"][k]["name"] for k in ("max-speed", "jump-strength", "gravity")]
    return [(bool(read), f"state files that hold Platform's values: {read or 'none'}"),
            (bool(floor), f"on the floor: {floor.group(0) if floor else 'not said'}"),
            (len(numbers) == 3, f"values given: {numbers}"),
            (all(n in answer for n in names), "names given: " + ", ".join(n for n in names if n in answer)
             + ("; missing: " + ", ".join(n for n in names if n not in answer) if not all(n in answer for n in names) else "")),
            unchanged(run)]


def grade_design_a_catch_game(run: Path) -> list[tuple[bool, str]]:
    project = run / "project"
    design = project / "tools" / "design.json"
    if design.exists():
        p = subprocess.run([sys.executable, str(SKILL / "scripts" / "check_design.py"), str(design), "--project",
                            str(project), "--rag", str(REPO), "--limit", "0"],
                           capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        lines = (p.stdout + p.stderr).strip().splitlines()
        checked = (p.returncode == 0, f"exit {p.returncode}: {lines[-1] if lines else 'no output'}")
        try:
            example = (json.loads(design.read_text(encoding="utf-8")).get("reference") or {}).get("example")
        except (ValueError, AttributeError):
            example = None
    else:
        checked, example = (False, "no tools/design.json"), None
    ids = {path.stem for path in (REPO / "data" / "c3-examples" / "en-US").glob("*.json")}
    return [checked,
            (isinstance(example, str) and example in ids, f"reference.example: {example!r}"),
            unchanged(run, ("tools/",))]


GRADERS = {"add-countdown": grade_add_countdown, "fix-load-errors": grade_fix_load_errors,
           "name-the-restart-event": grade_name_the_restart_event, "find-in-a-long-sheet": grade_find_in_a_long_sheet,
           "lay-out-the-hud": grade_lay_out_the_hud, "show-hp-as-a-bar": grade_show_hp_as_a_bar,
           "reveal-the-gradient": grade_reveal_the_gradient, "lives-as-hearts": grade_lives_as_hearts,
           "readable-on-a-dark-background": grade_readable_on_a_dark_background,
           "walk-with-wasd": grade_walk_with_wasd, "countdown-between-rounds": grade_countdown_between_rounds,
           "fix-wasd-twitch": grade_fix_wasd_twitch, "fix-next-round": grade_fix_next_round,
           "fix-turn-flip": grade_fix_turn_flip, "two-player-turns": grade_two_player_turns,
           "two-player-turn-limit": grade_two_player_turns, "find-a-drag-example": grade_find_a_drag_example,
           "script-shift-and-edges": grade_script_shift_and_edges,
           "platform-state-in-chinese": grade_platform_state_in_chinese,
           "design-a-catch-game": grade_design_a_catch_game}


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


def optional_json(path: Path) -> dict:
    """A file a run has only once it has reported (timing.json) or been traced (trace.json); {} without it."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
            score = f"{passed}/{len(graded)}"
            summary = {"passed": passed, "failed": len(graded) - passed, "total": len(graded),
                       "pass_rate": round(passed / len(graded), 3)}
            (run / "grading.json").write_text(json.dumps({"assertion_results": graded, "summary": summary},
                                                         indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            timing = optional_json(run / "timing.json")
            trace = optional_json(run / "trace.json")
            arm = re.sub(r"_\d+$", "", run.name)           # with_skill_2 is a second run of with_skill
            cells.setdefault(name, {}).setdefault(arm, []).append({
                "run": run.name, "passed": score, "pass_rate": summary["pass_rate"],
                "tokens": timing.get("total_tokens"), "seconds": round(timing["duration_ms"] / 1000, 1) if timing else None,
                **{k: trace[k] for k in ("tool_calls", "lost_calls") if k in trace}})
            print(f"{name}/{run.name}: {score}" + ("" if timing else "  (no timing.json)"))
            for g in graded:
                if not g["passed"]:
                    print(f"    FAIL {g['text']}\n         {g['evidence']}")
    if not cells and not void:
        sys.exit(f"{iteration} holds no <case>/<arm>/project of a case in evals.json")

    by_case = {name: {arm: {"runs": runs, **{key: spread([r[key] for r in runs if r.get(key) is not None]) for key in METRICS}}
                      for arm, runs in arms.items()} for name, arms in cells.items()}
    # Per arm, the mean of its cases' means: a deviation across different cases would measure the cases.
    arms = sorted({arm for case in by_case.values() for arm in case})
    run_summary = {arm: {key: round(statistics.mean(means), 3) for key in METRICS
                         if (means := [case[arm][key]["mean"] for case in by_case.values() if arm in case and case[arm].get(key)])}
                   for arm in arms}
    run_summary["delta"] = deltas(by_case)
    (iteration / "benchmark.json").write_text(json.dumps(
        {"run_summary": run_summary, "by_case": by_case, "void_runs": void}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {iteration / 'benchmark.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
