"""evals/grade.py on runs of its cases: what grading.json says about each.

The answers in fixtures/restart_event_answers/ are runs' answer.md files of the name-the-restart-event case,
with their run folder replaced by <run>. The project of each of those runs is empty and so is its fixture.json,
so the third assertion passes throughout. An add-countdown run is the stand-in game with the events it wrote.
"""
import importlib.util
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, SHEET, run

ANSWERS = Path(__file__).parent / "fixtures" / "restart_event_answers"
CHINESE_ALL_THREE = "**事件 9**（Restart 组）：Coin.Count = 0，仅触发一次。触发后等待 1 秒，再重载场景。\n"


def grade(tmp_path: Path, answer: str) -> list[bool]:
    case = tmp_path / "it" / "name-the-restart-event" / "with_skill"
    (case / "project").mkdir(parents=True)
    (case / "outputs").mkdir()
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    (case / "outputs" / "answer.md").write_text(answer, encoding="utf-8")
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    graded = json.loads((case / "grading.json").read_text(encoding="utf-8"))["assertion_results"]
    return [g["passed"] for g in graded]


@pytest.mark.parametrize(("name", "passed"), [
    ("english_all_three.md", [True, True, True]),
    # "Setup (event 2) runs again" names another event after the answer, 9
    ("english_names_setup_as_context.md", [True, True, True]),
    # "事件 8" is the Restart group's row; "仅触发一次" and "等待 1 秒" are the zh-CN wording
    ("chinese_gives_the_group_number.md", [False, True, True]),
    ("english_without_the_wait.md", [True, False, True]),
])
def test_restart_event_answers(tmp_path: Path, name: str, passed: list[bool]) -> None:
    assert grade(tmp_path, (ANSWERS / name).read_text(encoding="utf-8")) == passed


def test_chinese_answer_with_all_three(tmp_path: Path) -> None:
    assert grade(tmp_path, CHINESE_ALL_THREE) == [True, True, True]


def test_group_number_first_fails(tmp_path: Path) -> None:
    assert grade(tmp_path, "Event 8 restarts it: Coin.Count = 0, Trigger once, then a 1 second wait. "
                           "Event 9 is inside it.\n")[0] is False


@pytest.mark.parametrize(("kind", "counts"), [("regular", True), ("once", False)])
def test_a_countdown_on_a_one_second_timer_loses_one_per_second(tmp_path: Path, project: Path, kind: str,
                                                                counts: bool) -> None:
    """The add-countdown run of 2026-10-06 (with_q35_lean_2) started ScoreText's Timer "tick" for 1 second, Regular,
    under On start of layout, and took 1 from Countdown under On timer "tick". A Once timer fires a single time."""
    path = project / SHEET
    sheet = json.loads(path.read_text(encoding="utf-8"))
    sheet["events"].insert(0, {"eventType": "variable", "name": "Countdown", "type": "number", "initialValue": "30",
                               "comment": "", "isStatic": False, "isConstant": False, "sid": 767136845493875})
    setup = next(g for g in sheet["events"] if g.get("title") == "Setup")
    start = next(ev for ev in setup["children"] if any(c["id"] == "on-start-of-layout" for c in ev.get("conditions", [])))
    start["actions"].insert(0, {"id": "start-timer", "objectClass": "ScoreText", "sid": 101, "behaviorType": "Timer",
                                "parameters": {"duration": "1", "type": kind, "tag": '"tick"'}})
    setup["children"].append({"eventType": "block", "sid": 102, "conditions": [
        {"id": "on-timer", "objectClass": "ScoreText", "sid": 103, "behaviorType": "Timer", "parameters": {"tag": '"tick"'}}],
        "actions": [{"id": "set-eventvar-value", "objectClass": "System", "sid": 104,
                     "parameters": {"variable": "Countdown", "value": "Countdown - 1"}}]})
    path.write_text(json.dumps(sheet, indent="\t"), encoding="utf-8")
    case = tmp_path / "it" / "add-countdown" / "with_skill"
    shutil.copytree(project, case / "project")
    (case / "fixture.json").write_text("{}", encoding="utf-8")

    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    graded = json.loads((case / "grading.json").read_text(encoding="utf-8"))["assertion_results"]
    result = next(g for g in graded if g["text"].startswith("The countdown loses one per second"))
    assert result["passed"] is counts, result
    assert 'on-timer("tick") -> set-eventvar-value(Countdown | Countdown - 1)' in result["evidence"]


@pytest.mark.parametrize(("comparison", "value", "inverted", "restarts"), [
    (3, "0", False, True),      # Countdown <= 0
    (2, "0", False, True),      # Countdown < 0, which a countdown losing dt passes
    (4, "0", False, False),     # Countdown > 0: holds from the start (the audit of 2026-10-07)
    (4, "0", True, True),       # not Countdown > 0
    (5, "30", False, False),    # Countdown >= 30
])
def test_the_restart_reads_the_countdown_running_out(tmp_path: Path, project: Path, comparison: int, value: str,
                                                     inverted: bool, restarts: bool) -> None:
    """A countdown from 30 that loses dt every tick, set back on start of layout and shown in ScoreText, restarts
    the layout under a comparison of the countdown: it passes only when the comparison holds at 0 and not at 30."""
    path = project / SHEET
    sheet = json.loads(path.read_text(encoding="utf-8"))
    sheet["events"].insert(0, {"eventType": "variable", "name": "Countdown", "type": "number", "initialValue": "30",
                               "comment": "", "isStatic": False, "isConstant": False, "sid": 767136845493875})
    setup = next(g for g in sheet["events"] if g.get("title") == "Setup")
    start = next(ev for ev in setup["children"] if any(c["id"] == "on-start-of-layout" for c in ev.get("conditions", [])))
    start["actions"].insert(0, {"id": "set-eventvar-value", "objectClass": "System", "sid": 101,
                                "parameters": {"variable": "Countdown", "value": "30"}})
    restart = {"id": "compare-eventvar", "objectClass": "System", "sid": 105,
               "parameters": {"variable": "Countdown", "comparison": comparison, "value": value}}
    if inverted:
        restart["isInverted"] = True
    setup["children"] += [
        {"eventType": "block", "sid": 102, "conditions": [{"id": "every-tick", "objectClass": "System", "sid": 103}],
         "actions": [{"id": "subtract-from-eventvar", "objectClass": "System", "sid": 104,
                      "parameters": {"variable": "Countdown", "value": "dt"}}]},
        {"eventType": "block", "sid": 106, "conditions": [restart],
         "actions": [{"id": "restart-layout", "objectClass": "System", "sid": 107}]}]
    path.write_text(json.dumps(sheet, indent="\t"), encoding="utf-8")
    case = tmp_path / "it" / "add-countdown" / "with_skill"
    shutil.copytree(project, case / "project")
    (case / "fixture.json").write_text("{}", encoding="utf-8")

    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    graded = json.loads((case / "grading.json").read_text(encoding="utf-8"))["assertion_results"]
    result = next(g for g in graded if g["text"].startswith("An event restarts the layout"))
    assert result["passed"] is restarts, result


def test_a_run_that_wrote_outside_its_folder_is_not_scored(tmp_path: Path) -> None:
    """Its grade would count work that is not in its project, or that another run reads."""
    case = tmp_path / "it" / "name-the-restart-event" / "with_skill"
    (case / "project").mkdir(parents=True)
    (case / "outputs").mkdir()
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    (case / "outputs" / "answer.md").write_text(CHINESE_ALL_THREE, encoding="utf-8")
    elsewhere = str(tmp_path / "scratchpad" / "plan.json")
    (case / "trace.json").write_text(json.dumps({"tool_calls": 3, "lost_calls": 0, "outside": [
        {"tool": "Write", "path": elsewhere}], "outside_reads": []}), encoding="utf-8")
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    assert f"name-the-restart-event/with_skill: void, not scored: it wrote outside its folder: {elsewhere}" in out
    assert json.loads((case / "grading.json").read_text(encoding="utf-8")) == {
        "void": f"it wrote outside its folder: {elsewhere}"}
    benchmark = json.loads((tmp_path / "it" / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["void_runs"] == [{"run": "name-the-restart-event/with_skill",
                                       "reason": f"it wrote outside its folder: {elsewhere}"}]


sys.path.insert(0, str(SKILL / "evals"))
sys.path.insert(0, str(SKILL / "scripts"))
import grade as grader  # noqa: E402
import play_cases  # noqa: E402
import preview_project  # noqa: E402

# evals/trace.py by its path: the standard library has a module named trace.
tracer = importlib.util.module_from_spec(spec := importlib.util.spec_from_file_location("eval_trace", SKILL / "evals" / "trace.py"))
spec.loader.exec_module(tracer)

CASES = {c["name"]: c for c in json.loads((SKILL / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}


@pytest.mark.parametrize("name", sorted(play_cases.PLANS))
def test_every_plan_is_one_preview_project_plays(name: str) -> None:
    """A plan preview_project.py refuses would fail every run of its case; a check's text names its assertion."""
    assert name in CASES
    plan, problems = preview_project.check_plan(play_cases.plan_for(name))
    assert not problems, problems
    texts = play_cases.check_texts(name)
    assert len(texts) == len(set(texts)) >= 2 and texts[-1] == play_cases.NO_ERROR


def test_held_out_cases_have_a_plan() -> None:
    """A held-out case is judged by what its game does; its file assertions only say that it still opens."""
    held = [n for n, c in CASES.items() if c.get("held_out")]
    assert held and all(n in play_cases.PLANS for n in held)


def played(case: Path, oks: list[bool]) -> None:
    """A play/result.json in which the plan's checks returned oks in order, as preview_project.py writes it."""
    plan = play_cases.plan_for(case.parent.name)
    steps, verdicts = [], iter(oks)
    for n, step in enumerate(plan["steps"], 1):
        done = {"step": n, "line": f"{n} {next(iter(step))} ...", "ok": True, "said": "", "errors": []}
        if step.get("note", "").startswith(play_cases.CHECK):
            done["value"] = {"ok": next(verdicts), "said": f"check {n}"}
        steps.append(done)
    (case / "play").mkdir()
    (case / "play" / "result.json").write_text(json.dumps({"status": "opened", "preview": {
        "started": True, "errors": [], "steps": steps}}), encoding="utf-8")


def test_runtime_checks_are_graded_from_the_played_result(tmp_path: Path, project: Path) -> None:
    case = tmp_path / "it" / "fix-next-round" / "with_skill"
    shutil.copytree(project, case / "project")
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    played(case, [True, False])
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    grading = json.loads((case / "grading.json").read_text(encoding="utf-8"))
    runtime = [(g["passed"], g["evidence"]) for g in grading["assertion_results"] if g["level"] == "runtime"]
    checks = [n for n, s in enumerate(play_cases.plan_for("fix-next-round")["steps"], 1)
              if s.get("note", "").startswith(play_cases.CHECK)]
    assert runtime == [(True, f"check {checks[0]}"), (False, f"check {checks[1]}"), (True, "no runtime error")]
    assert grading["summary"]["runtime"] == {"passed": 2, "total": 3}
    assert "FAIL [runtime] The next round deals 3 coins" in out


def test_an_unplayed_plan_is_not_scored(tmp_path: Path, project: Path) -> None:
    """Grading without --play compares with iterations graded before the plans: the runtime checks are listed
    and left out of the scores."""
    case = tmp_path / "it" / "fix-next-round" / "with_skill"
    shutil.copytree(project, case / "project")
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    grading = json.loads((case / "grading.json").read_text(encoding="utf-8"))
    assert grading["summary"]["runtime"] == "not played"
    assert grading["summary"]["total"] == len(CASES["fix-next-round"]["assertions"])
    assert {g["passed"] for g in grading["assertion_results"] if g["level"] == "runtime"} == {None}


def test_a_held_out_case_is_aggregated_apart_and_its_failures_are_not_printed(tmp_path: Path, project: Path) -> None:
    case = tmp_path / "it" / "coins-in-a-ring" / "with_skill"
    shutil.copytree(project, case / "project")
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    played(case, [False, False, True])
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    assert "coins-in-a-ring/with_skill: held out, " in out and "FAIL" not in out
    benchmark = json.loads((tmp_path / "it" / "benchmark.json").read_text(encoding="utf-8"))
    assert "coins-in-a-ring" not in benchmark["by_case"] and "coins-in-a-ring" in benchmark["held_out"]["by_case"]
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"), "--show-held-out")
    assert "FAIL [runtime] Round 2's three coins sit evenly" in out


def test_make_fixtures_lays_out_a_held_out_case_only_when_asked(tmp_path: Path) -> None:
    code, out = run(tmp_path, SKILL / "evals" / "make_fixtures.py", str(tmp_path / "runs"), "--cases", "coins-in-a-ring")
    assert code == 1 and "held out of tuning" in out and "--held-out" in out


@pytest.mark.parametrize(("k", "n", "interval"), [(0, 0, [0.0, 1.0]), (2, 2, [0.342, 1.0]), (1, 2, [0.095, 0.905]),
                                                  (8, 10, [0.49, 0.943])])
def test_the_interval_of_fully_passed_runs(k: int, n: int, interval: list[float]) -> None:
    assert grader.wilson(k, n) == interval


@pytest.mark.parametrize(("levels", "reached"), [
    ({"checker": [True], "files": [True], "runtime": [True]}, "runtime"),
    ({"checker": [True], "files": [True], "runtime": [None]}, "files"),
    ({"checker": [True], "files": [False], "runtime": [True]}, "checker"),
    ({"checker": [False], "files": [True]}, "none"),
])
def test_the_level_a_run_reached(levels: dict, reached: str) -> None:
    graded = [{"level": level, "passed": p} for level, ps in levels.items() for p in ps]
    assert grader.reached(graded) == reached


def test_trace_reads_turns_tokens_and_time(tmp_path: Path) -> None:
    """A response with two content blocks is written twice with one message id: one turn."""
    def entry(t: str, mid: str | None, out: int) -> str:
        message = {"id": mid, "model": "m", "usage": {"input_tokens": 2, "cache_creation_input_tokens": 10,
                                                       "cache_read_input_tokens": 100, "output_tokens": out}}
        return json.dumps({"type": "assistant" if mid else "user", "timestamp": t, "message": message if mid else {}})
    path = tmp_path / "agent.jsonl"
    path.write_text("\n".join([entry("2026-10-08T10:00:00Z", None, 0), entry("2026-10-08T10:00:05Z", "a", 50),
                               entry("2026-10-08T10:00:05Z", "a", 50), entry("2026-10-08T10:01:30Z", "b", 70)]),
                    encoding="utf-8")
    assert tracer.usage_of(path) == {"turns": 2, "output_tokens": 120, "input_tokens": 224, "seconds": 90.0, "model": "m"}


def screenshots(tmp_path: Path, fill: Callable[[int, float], tuple], lit: tuple[float, float]) -> dict:
    """A result with before and after screenshots of a 400 px bar lit to lit[0] and then lit[1] of its length,
    its pixel at x coloured fill(x, lit), and the bar's box as the UI layer's only object."""
    from PIL import Image
    shots = []
    for name, part in zip(("before", "after"), lit):
        im = Image.new("RGB", (500, 100), (2, 48, 71))
        for x in range(50, 50 + int(400 * part)):
            for y in range(40, 60):
                im.putpixel((x, y), fill(x - 50, part))
        im.save(tmp_path / f"{name}.png")
        shots.append(tmp_path / f"{name}.png")
    box = [{"type": "Bar", "text": False, "box": {"l": 50, "t": 40, "r": 450, "b": 60}}]
    steps = [{"step": 1, "line": "1 js ... (boxes before)", "ok": True, "value": box},
             {"step": 2, "line": "2 shot before", "ok": True, "said": str(shots[0])},
             {"step": 3, "line": "3 shot after", "ok": True, "said": str(shots[1])},
             {"step": 4, "line": "4 js ... (boxes after)", "ok": True, "value": box}]
    return {"status": "opened", "preview": {"started": True, "errors": [], "steps": steps}}


def green_to_red(x: int, part: float) -> tuple:
    u = x / 400
    return round(255 * u), round(255 * (1 - u)), 0


def stretched(x: int, part: float) -> tuple:
    u = x / (400 * part)
    return round(255 * u), round(255 * (1 - u)), 0


@pytest.mark.parametrize(("fill", "kept"), [(green_to_red, True), (stretched, False)])
def test_a_gradient_bar_is_revealed_not_stretched(tmp_path: Path, fill: Callable, kept: bool) -> None:
    pytest.importorskip("PIL")
    lit, colours = play_cases.gradient_checks(screenshots(tmp_path, fill, (0.5, 0.6)))
    assert lit[0], lit
    assert colours[0] is kept, colours
