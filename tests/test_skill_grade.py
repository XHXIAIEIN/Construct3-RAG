"""evals/grade.py and the eval scripts beside it on runs of the skill's cases: what grading.json, benchmark.json
and trace.json say about a run.

The answers in fixtures/restart_event_answers/ are answer.md files of name-the-restart-event runs, with their run
folder replaced by <run>. Each of those runs has an empty project and an empty fixture.json, so the third assertion
passes throughout. An add-countdown run is the stand-in game with the events it wrote.
"""
import importlib.util
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, SHEET, run

sys.path.insert(0, str(SKILL / "evals"))
sys.path.insert(0, str(SKILL / "scripts"))
import grade as grader  # noqa: E402
import make_fixtures  # noqa: E402
import play_cases  # noqa: E402
import preview_project  # noqa: E402
import compare  # noqa: E402

# evals/trace.py by its path: the standard library has a module named trace.
tracer = importlib.util.module_from_spec(spec := importlib.util.spec_from_file_location("eval_trace", SKILL / "evals" / "trace.py"))
spec.loader.exec_module(tracer)

ANSWERS = Path(__file__).parent / "fixtures" / "restart_event_answers"
CHINESE_ALL_THREE = "**事件 9**（Restart 组）：Coin.Count = 0，仅触发一次。触发后等待 1 秒，再重载场景。\n"
CASES = {c["name"]: c for c in json.loads((SKILL / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def answer_case(case: Path, answer: str) -> None:
    """A name-the-restart-event run at case: answer as its answer.md, an empty project and an empty fixture.json."""
    (case / "project").mkdir(parents=True)
    (case / "outputs").mkdir()
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    (case / "outputs" / "answer.md").write_text(answer, encoding="utf-8")


def project_case(tmp_path: Path, project: Path, name: str) -> Path:
    """The with_skill run of case name in the iteration tmp_path/it: a copy of project and an empty fixture.json."""
    case = tmp_path / "it" / name / "with_skill"
    shutil.copytree(project, case / "project")
    (case / "fixture.json").write_text("{}", encoding="utf-8")
    return case


def grade_iteration(tmp_path: Path) -> str:
    """What grade.py prints on the iteration tmp_path/it, which it grades without an error."""
    code, out = run(tmp_path, SKILL / "evals" / "grade.py", str(tmp_path / "it"))
    assert code == 0, out
    return out


def grade(tmp_path: Path, answer: str) -> list[bool]:
    case = tmp_path / "it" / "name-the-restart-event" / "with_skill"
    answer_case(case, answer)
    grade_iteration(tmp_path)
    return [g["passed"] for g in read_json(case / "grading.json")["assertion_results"]]


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


def add_countdown(project: Path, first_on_start: dict, setup_events: list[dict]) -> None:
    """The stand-in's sheet with a global Countdown from 30, first_on_start as the first action of On start of
    layout, and setup_events at the end of the Setup group."""
    path = project / SHEET
    sheet = read_json(path)
    sheet["events"].insert(0, {"eventType": "variable", "name": "Countdown", "type": "number", "initialValue": "30",
                               "comment": "", "isStatic": False, "isConstant": False, "sid": 767136845493875})
    setup = next(g for g in sheet["events"] if g.get("title") == "Setup")
    start = next(ev for ev in setup["children"] if any(c["id"] == "on-start-of-layout" for c in ev.get("conditions", [])))
    start["actions"].insert(0, first_on_start)
    setup["children"] += setup_events
    path.write_text(json.dumps(sheet, indent="\t"), encoding="utf-8")


@pytest.mark.parametrize(("kind", "counts"), [("regular", True), ("once", False)])
def test_a_countdown_on_a_one_second_timer_loses_one_per_second(tmp_path: Path, project: Path, kind: str,
                                                                counts: bool) -> None:
    """The add-countdown run of 2026-10-06 (with_q35_lean_2) started ScoreText's Timer "tick" for 1 second, Regular,
    under On start of layout, and took 1 from Countdown under On timer "tick". A Once timer fires a single time."""
    add_countdown(project, {"id": "start-timer", "objectClass": "ScoreText", "sid": 101, "behaviorType": "Timer",
                            "parameters": {"duration": "1", "type": kind, "tag": '"tick"'}}, [
        {"eventType": "block", "sid": 102, "conditions": [
            {"id": "on-timer", "objectClass": "ScoreText", "sid": 103, "behaviorType": "Timer", "parameters": {"tag": '"tick"'}}],
         "actions": [{"id": "set-eventvar-value", "objectClass": "System", "sid": 104,
                      "parameters": {"variable": "Countdown", "value": "Countdown - 1"}}]}])
    case = project_case(tmp_path, project, "add-countdown")
    grade_iteration(tmp_path)
    graded = read_json(case / "grading.json")["assertion_results"]
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
    restart = {"id": "compare-eventvar", "objectClass": "System", "sid": 105,
               "parameters": {"variable": "Countdown", "comparison": comparison, "value": value}}
    if inverted:
        restart["isInverted"] = True
    add_countdown(project, {"id": "set-eventvar-value", "objectClass": "System", "sid": 101,
                            "parameters": {"variable": "Countdown", "value": "30"}}, [
        {"eventType": "block", "sid": 102, "conditions": [{"id": "every-tick", "objectClass": "System", "sid": 103}],
         "actions": [{"id": "subtract-from-eventvar", "objectClass": "System", "sid": 104,
                      "parameters": {"variable": "Countdown", "value": "dt"}}]},
        {"eventType": "block", "sid": 106, "conditions": [restart],
         "actions": [{"id": "restart-layout", "objectClass": "System", "sid": 107}]}])
    case = project_case(tmp_path, project, "add-countdown")
    grade_iteration(tmp_path)
    graded = read_json(case / "grading.json")["assertion_results"]
    result = next(g for g in graded if g["text"].startswith("An event restarts the layout"))
    assert result["passed"] is restarts, result


def test_a_function_call_on_start_is_graded_with_the_countdown(tmp_path: Path, project: Path) -> None:
    """A call of a function lists its arguments, not named parameters: iteration 65's add-countdown/with_skill
    called ShowScore under On start of layout, and the grader stopped on the list."""
    add_countdown(project, {"callFunction": "ShowScore", "sid": 101, "parameters": []}, [])
    case = project_case(tmp_path, project, "add-countdown")
    grade_iteration(tmp_path)
    graded = read_json(case / "grading.json")["assertion_results"]
    assert any(g["text"].startswith("An event restarts the layout") for g in graded), graded


def test_a_run_that_wrote_outside_its_folder_is_not_scored(tmp_path: Path) -> None:
    """Its grade would count work that is not in its project, or that another run reads."""
    case = tmp_path / "it" / "name-the-restart-event" / "with_skill"
    answer_case(case, CHINESE_ALL_THREE)
    elsewhere = str(tmp_path / "scratchpad" / "plan.json")
    (case / "trace.json").write_text(json.dumps({"tool_calls": 3, "lost_calls": 0, "outside": [
        {"tool": "Write", "path": elsewhere}], "outside_reads": []}), encoding="utf-8")
    out = grade_iteration(tmp_path)
    assert f"name-the-restart-event/with_skill: void, not scored: it wrote outside its folder: {elsewhere}" in out
    assert read_json(case / "grading.json") == {"void": f"it wrote outside its folder: {elsewhere}"}
    benchmark = read_json(tmp_path / "it" / "benchmark.json")
    assert benchmark["void_runs"] == [{"run": "name-the-restart-event/with_skill",
                                       "reason": f"it wrote outside its folder: {elsewhere}"}]


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


@pytest.mark.parametrize(("test", "passed"), [
    ('keyboard.isKeyDown("Shift")', False),
    ('keyboard.isKeyDown("ShiftLeft") || keyboard.isKeyDown("ShiftRight")', True),
    ("keyboard.isKeyDown(16)", True)])
def test_a_shift_key_counts_only_by_a_code_iskeydown_matches(tmp_path: Path, test: str, passed: bool) -> None:
    """isKeyDown matches a key's code: a run that tests "Shift" never doubles its speed in the game."""
    (tmp_path / "project" / "scripts").mkdir(parents=True)
    (tmp_path / "fixture.json").write_text("{}", encoding="utf-8")
    (tmp_path / "project" / "scripts" / "main.ts").write_text(f"const speed = {test} ? 400 : 200;", encoding="utf-8")
    assert grader.grade_script_shift_and_edges(tmp_path)[1][0] is passed


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
    case = project_case(tmp_path, project, "fix-next-round")
    played(case, [True, False])
    out = grade_iteration(tmp_path)
    grading = read_json(case / "grading.json")
    runtime = [(g["passed"], g["evidence"]) for g in grading["assertion_results"] if g["level"] == "runtime"]
    checks = [n for n, s in enumerate(play_cases.plan_for("fix-next-round")["steps"], 1)
              if s.get("note", "").startswith(play_cases.CHECK)]
    assert runtime == [(True, f"check {checks[0]}"), (False, f"check {checks[1]}"), (True, "no runtime error")]
    assert grading["summary"]["runtime"] == {"passed": 2, "total": 3}
    assert "FAIL [runtime] The next round deals 3 coins" in out


def test_an_unplayed_plan_is_not_scored(tmp_path: Path, project: Path) -> None:
    """Grading without --play compares with iterations graded before the plans: the runtime checks are listed
    and left out of the scores."""
    case = project_case(tmp_path, project, "fix-next-round")
    grade_iteration(tmp_path)
    grading = read_json(case / "grading.json")
    assert grading["summary"]["runtime"] == "not played"
    assert grading["summary"]["total"] == len(CASES["fix-next-round"]["assertions"])
    assert {g["passed"] for g in grading["assertion_results"] if g["level"] == "runtime"} == {None}


def test_a_held_out_case_is_aggregated_apart_and_its_failures_are_not_printed(tmp_path: Path, project: Path) -> None:
    case = project_case(tmp_path, project, "coins-in-a-ring")
    played(case, [False, False, True])
    out = grade_iteration(tmp_path)
    assert "coins-in-a-ring/with_skill: held out, " in out and "FAIL" not in out
    benchmark = read_json(tmp_path / "it" / "benchmark.json")
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


@pytest.mark.parametrize("command", [
    "sed -i '/^function Tick/,/^}/ s/^\\r$//' /d/run/main.ts",
    "sed -i -e '/^}/d' /d/run/main.ts",
    "sed -n '/^x/p' /d/run/main.ts > /d/run/out.txt"])
def test_trace_takes_a_sed_script_for_no_path(command: str) -> None:
    """A sed script can start with /, and Git Bash's /d is D:; only the file the command names is written."""
    writes, named = tracer.shell_paths(command)
    files = [Path(p).name for p in writes + named]
    assert files == (["out.txt", "main.ts"] if ">" in command else ["main.ts"]), (writes, named)


def screenshots(tmp_path: Path, fill: Callable[[int, float], tuple], lit: tuple[float, float]) -> dict:
    """A result with before and after screenshots of a 400 px bar lit to lit[0] and then lit[1] of its length,
    its pixel at x coloured fill(x, lit), and the bar's box as the UI layer's only object."""
    from PIL import Image
    shots = []
    for name, part in zip(("before", "after"), lit):
        im = Image.new("RGB", (500, 100), (2, 48, 71))
        for x in range(50, 50 + int(400 * part)):
            im.paste(fill(x - 50, part), (x, 40, x + 1, 60))
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


def transcript_of(path: Path, calls: list[tuple[str, dict, str, bool]]) -> Path:
    """A transcript of (tool, input, result, failed) calls, each with its result in the next entry."""
    lines = []
    for n, (tool, given, result, failed) in enumerate(calls):
        lines.append(json.dumps({"message": {"content": [{"type": "tool_use", "id": f"t{n}", "name": tool, "input": given}]}}))
        lines.append(json.dumps({"message": {"content": [
            {"type": "tool_result", "tool_use_id": f"t{n}", "is_error": failed, "content": result}]}}))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_trace_counts_the_route_of_a_run(tmp_path: Path) -> None:
    """Each route column of trace.json, from a transcript that holds one of everything it counts: a cat of
    SKILL.md, an instruction file whose clone line keeps <path-to>, reads of the clone, the check chain up to a
    passing plan, two --help reads of one script, a copied command that fails, a hand edit of a layout, a refused
    plan beside a dry run, a copied check and another that fail with findings, one that fails without, and a
    preview that never opened."""
    run_dir = tmp_path / "it" / "double-jump" / "with_skill"
    project, clone = run_dir / "project", tmp_path / "clone"
    (project / "layouts").mkdir(parents=True)
    block = ("path-to = " + clone.parent.as_posix() + "\n- Construct3-RAG: <path-to>/clone\n"
             "1. Run `python .agents/skills/construct3-agent-plugin/scripts/check_project.py` from the project folder.\n")
    (project / "AGENTS.md").write_text(block, encoding="utf-8")
    scripts = f"{project.as_posix()}/.agents/skills/construct3-agent-plugin/scripts"
    ok_line = ("ok: 7 object types, 0 families, 1 layouts, 1 sheets; next, review the design: python "
               ".agents/skills/construct3-agent-plugin/scripts/review_design.py, then open it: python "
               ".agents/skills/construct3-agent-plugin/scripts/open_in_editor.py --preview")
    calls = [
        ("Bash", {"command": f'cat "{project.as_posix()}/.agents/skills/construct3-agent-plugin/SKILL.md"'}, "x" * 6000, False),
        ("Read", {"file_path": f"{project.as_posix()}/AGENTS.md"}, block, False),
        ("Read", {"file_path": f"{clone.as_posix()}/data/c3-schemas/_index.json"}, "{}", False),
        ("Grep", {"pattern": "jump", "path": clone.as_posix()}, "No matches found", False),
        ("Bash", {"command": f'cd "{project.as_posix()}" && python {scripts}/check_project.py --project "{project.as_posix()}"'}, ok_line, False),
        ("Bash", {"command": f"python {scripts}/preview_project.py --help 2>&1 | head -c 6000"}, "usage: preview_project.py", False),
        ("Bash", {"command": f'S="{scripts}" && python "$S/preview_project.py" --help | tail -c +6000'}, "a plan is", False),
        ("Bash", {"command": "python scripts/review_design.py"}, "Exit code 2\npython: can't open file 'scripts/review_design.py'", True),
        ("Edit", {"file_path": f"{project.as_posix()}/layouts/x.json", "old_string": "a", "new_string": "b"}, "updated", False),
        ("Bash", {"command": f'python {scripts}/edit_sheet.py "Event sheet 1" .tmp/plan.json'},
         "Exit code 1\noperation 1: event 9 does not print the line given\nnothing was written", True),
        ("Bash", {"command": f'python {scripts}/edit_sheet.py "Event sheet 1" .tmp/plan.json --dry-run'},
         "Event sheet 1: 1 operation, 8 events before and 9 now (dry run)\ndry run: nothing was written", False),
        ("Bash", {"command": f'cd "{project.as_posix()}" && python .agents/skills/construct3-agent-plugin/scripts/check_project.py'},
         "Exit code 1\nEvent sheet 1 event 9: parameter omitted\n1 problem(s)", True),
        ("Bash", {"command": f"python {scripts}/check_project.py"},
         "Exit code 1\nwarning: Event sheet 1 event 3: no comment above it\nEvent sheet 1 event 9: parameter omitted\n1 problem(s)", True),
        ("Bash", {"command": f"python {scripts}/check_project.py --nonsense"},
         "Exit code 2\nusage: check_project.py [-h]\ncheck_project.py: error: unrecognized arguments: --nonsense", True),
        ("Bash", {"command": f"python {scripts}/open_in_editor.py --preview"},
         "no preview window in 20 seconds\n0 of 1 opened and ran without errors; full results in .tmp/open-in-editor.json", False),
        ("Bash", {"command": f"python {scripts}/preview_project.py .tmp/plan.json"},
         "opened   project\n  1 key ArrowRight 0.5 s  ok\nkeep: this plan passes; keep it with --keep NAME", False),
    ]
    transcript = transcript_of(tmp_path / "agent.jsonl", calls)
    code, out = run(tmp_path, SKILL / "evals" / "trace.py", str(transcript), "--out", str(run_dir))
    assert code == 0, out
    trace = read_json(run_dir / "trace.json")
    assert {k: trace[k] for k in grader.TRACE_COLUMNS} == {
        "tool_calls": 16, "lost_calls": 4, "turns": 0, "output_tokens": 0, "read_skill_md": True,
        "first_script": "check_project", "chain_depth": 4, "chain_end": "preview_project", "chain_reached": "preview_project",
        "chain_attempts": 7, "preview_failed": 1, "help_reads": 2, "repeat_help": 1, "plan_refusals": 1, "hand_edits": 1,
        "lookups_before_first_edit": 8, "data_reads": 1, "other_clone_reads": 1, "entry_chars": 6018 + len(block),
        "printed_command_failures": 1, "print_sheet_chars": 0, "whole_sheet_prints": 0}
    assert trace["chain"] == {"check_project": {"calls": 4, "passed": True}, "review_design": {"calls": 1, "passed": False},
                              "open_in_editor": {"calls": 1, "passed": False}, "preview_project": {"calls": 1, "passed": True},
                              "review_look": {"calls": 0, "passed": False}}
    assert trace["help_reads_by_script"] == {"preview_project": 2}
    assert trace["outside"] == [] and len(trace["outside_reads"]) == 2
    assert Path(trace["transcript"]) == transcript.resolve()
    assert (run_dir / "transcript.jsonl").read_bytes() == transcript.read_bytes()
    assert ("first script check_project, chain to preview_project (4 of 5, 7 calls), 2 help reads, 1 refused plans, "
            "1 hand edits, 8 calls before the first edit") in out
    code, out = run(tmp_path, SKILL / "evals" / "trace.py", str(transcript))
    assert code == 0, out
    assert "1 refused plans, hand edits and calls before the first edit need --out or --root with its project/" in out


@pytest.mark.parametrize(("command", "edit"), [
    ('cd "{p}" && python.exe - <<\'PY\'\nimport pathlib\np = pathlib.Path("scripts/main.ts")\n'
     'p.write_bytes(p.read_bytes().replace(b"200", b"400"))\nPY', True),
    ('python.exe - <<\'PY\'\np = "{p}/scripts/main.ts"\nopen(p, "wb").write(open(p, "rb").read())\nPY', True),
    ('cd "{p}" && cat > scripts/main.ts <<\'EOF\'\nconst a = 1;\nEOF', True),
    ('cd "{p}" && python -c "import json; print(json.load(open(\'objectTypes/Player.json\'))[\'name\'])"', False),
    ('cd "{p}" && cat > .tmp/plan.json <<\'EOF\'\n[]\nEOF', False),
])
def test_trace_sees_a_write_made_inside_a_script(tmp_path: Path, command: str, edit: bool) -> None:
    """A heredoc or an inline script that writes a project file is the run's edit, relative to the cd before it;
    a read, and a write under .tmp/, are not."""
    project = tmp_path / "project"
    project.mkdir()
    call = {"tool": "Bash", "what": "", "failed": False, "result": "", "input": {"command": command.format(p=project.as_posix())}}
    assert bool(tracer.project_edits(call, project)) is edit, tracer.inline_writes(call["input"]["command"])


@pytest.mark.parametrize(("command", "reads"), [
    ('cd "{c}" && cat prompts/event-sheet-thinking.md | head -c 9000', ["prompts/event-sheet-thinking.md"]),
    ('cd "{c}" && ls data/c3-schemas/ && ls data/c3-schemas/en-US/', ["data/c3-schemas", "data/c3-schemas/en-US"]),
    ('cd "{c}" && python skills/construct3-agent-plugin/scripts/print_sheet.py --project "{c}/x" Game', []),
    ('cd "{c}" && grep -rn "isKeyDown" --include=*.md . | head', ["."]),
    ('python check.py --rag "{c}" --project "{c}/game"', []),
])
def test_trace_reads_relative_to_the_cd_of_a_command(tmp_path: Path, command: str, reads: list[str]) -> None:
    """A path after a cd is read in that folder; a script run from the clone and a folder a script is pointed
    at are not reads of it."""
    clone = tmp_path / "clone"
    found = tracer.read_paths(command.format(c=clone.as_posix()))
    assert [Path(p) for p in found] == [(clone / r).resolve() for r in reads]


def restart_runs(tmp_path: Path, depths: dict[str, list[int]]) -> Path:
    """An iteration of name-the-restart-event runs that all pass, each traced with the chain depth given."""
    iteration = tmp_path / "it"
    answer = (ANSWERS / "english_all_three.md").read_text(encoding="utf-8")
    ends = {1: "check_project", 2: "review_design", 4: "preview_project", 5: "review_look"}
    for arm, cell in depths.items():
        for n, depth in enumerate(cell):
            case = iteration / "name-the-restart-event" / (arm if n == 0 else f"{arm}_{n + 1}")
            answer_case(case, answer)
            (case / "trace.json").write_text(json.dumps({
                "tool_calls": 20 + depth, "lost_calls": 1, "turns": 15, "output_tokens": 3000, "read_skill_md": True,
                "first_script": "check_project", "chain_depth": depth, "chain_end": ends[depth],
                "chain_reached": "review_look", "chain_attempts": depth + 1,
                "preview_failed": 0, "help_reads": 1, "repeat_help": 0, "plan_refusals": 0, "hand_edits": 0,
                "lookups_before_first_edit": 8, "data_reads": 1, "other_clone_reads": 0, "entry_chars": 30000,
                "printed_command_failures": 0, "print_sheet_chars": 9000, "whole_sheet_prints": 0, "outside": [],
                "outside_reads": []}), encoding="utf-8")
    return iteration


def test_grade_carries_the_route_columns_and_decides_on_one(tmp_path: Path) -> None:
    """benchmark.json holds every column per run, averaged or counted per cell and in the arm delta, and the
    verdict of decision.json; compare.py gives the same test from the file."""
    iteration = restart_runs(tmp_path, {"with_skill": [5, 5, 4], "old_skill": [1, 2, 1]})
    (iteration / "decision.json").write_text(json.dumps({
        "cases": ["name-the-restart-event"], "metric": "chain_depth", "direction": "up", "n_per_cell": 3,
        "guards": {"pass_rate": "not down"}, "concurrency": 3}), encoding="utf-8")
    out = grade_iteration(tmp_path)
    assert ("decision: chain_depth up: with_skill - old_skill = +10 over 1 case, one-sided p = 0.050 (exact, 20 "
            "reassignments); guard pass_rate not down holds (1.0 vs 1.0); verdict: holds at alpha 0.05, 3 runs at once") in out
    benchmark = read_json(iteration / "benchmark.json")
    with_skill = benchmark["by_case"]["name-the-restart-event"]["with_skill"]
    assert with_skill["chain_depth"] == {"mean": 4.667, "runs": 3, "stddev": 0.577}
    assert with_skill["chain_end"] == {"preview_project": 1, "review_look": 2} and with_skill["first_script"] == {"check_project": 3}
    assert with_skill["chain_reached"] == {"review_look": 3}
    assert set(grader.TRACE_COLUMNS) <= set(with_skill["runs"][0])
    assert with_skill["runs"][0]["tool_calls"] == 25 and with_skill["lost_calls"]["mean"] == 1
    assert benchmark["run_summary"]["delta"]["with_skill - old_skill"]["chain_depth"] == pytest.approx(10 / 3, abs=0.01)
    assert benchmark["run_summary"]["with_skill"]["chain_end"] == {"preview_project": 1, "review_look": 2}
    assert benchmark["decision"]["verdict"] == "holds" and benchmark["decision"]["p"] == 0.05
    code, out = run(tmp_path, SKILL / "evals" / "compare.py", str(iteration / "benchmark.json"), "chain_depth")
    assert code == 0 and out.strip() == ("chain_depth up: with_skill - old_skill = +10 over 1 case, one-sided p = 0.050 "
                                         "(exact, 20 reassignments)")
    code, out = run(tmp_path, SKILL / "evals" / "compare.py", str(iteration / "benchmark.json"), "chain_depth", "--direction", "down")
    assert "p = 1.000" in out


def test_grade_says_underpowered_and_aggregates_all_the_same(tmp_path: Path) -> None:
    iteration = restart_runs(tmp_path, {"with_skill": [5, 5, 4], "old_skill": [1, 2]})
    (iteration / "decision.json").write_text(json.dumps({
        "cases": ["name-the-restart-event"], "metric": "chain_depth", "direction": "up", "n_per_cell": 3}), encoding="utf-8")
    out = grade_iteration(tmp_path)
    assert "underpowered: name-the-restart-event/old_skill: 2 of 3; no verdict on chain_depth" in out
    benchmark = read_json(iteration / "benchmark.json")
    assert benchmark["decision"]["verdict"] == "underpowered"
    assert benchmark["by_case"]["name-the-restart-event"]["old_skill"]["chain_depth"]["mean"] == 1.5


@pytest.mark.parametrize(("text", "error"), [
    ('{"cases": ["name-the-restart-event"], "direction": "up", "n_per_cell": 3}', 'missing key "metric"'),
    ('{"cases": [', "not JSON ("),
])
def test_grade_writes_the_benchmark_when_decision_json_cannot_be_read(tmp_path: Path, text: str, error: str) -> None:
    """A misspelled key or a broken file costs the verdict, not the aggregation."""
    iteration = restart_runs(tmp_path, {"with_skill": [5, 5, 4], "old_skill": [1, 2, 1]})
    (iteration / "decision.json").write_text(text, encoding="utf-8")
    out = grade_iteration(tmp_path)
    assert f"decision.json: {error}" in out and "benchmark written without a verdict" in out
    benchmark = read_json(iteration / "benchmark.json")
    assert benchmark["decision"]["verdict"] == "not read" and benchmark["decision"]["error"].startswith(error)
    assert benchmark["by_case"]["name-the-restart-event"]["with_skill"]["chain_depth"]["mean"] == 4.667


def test_the_permutation_test_reassigns_within_each_case() -> None:
    one = {"a": [("with", 5), ("with", 5), ("with", 4), ("old", 1), ("old", 2), ("old", 1)]}
    assert compare.permutation_test(one, "with", "up") == {"observed": 10, "p": 0.05, "permutations": 20, "exact": True}
    assert compare.permutation_test(one, "with", "down")["p"] == 1.0
    two = one | {"b": [("with", 3), ("with", 3), ("old", 3), ("old", 3)]}
    assert compare.permutation_test(two, "with", "up") == {"observed": 10, "p": 0.05, "permutations": 120, "exact": True}
    assert compare.permutation_test(one | {"c": [("with", 9)]}, "with", "up")["permutations"] == 20
    with pytest.raises(ValueError):
        compare.permutation_test({"c": [("with", 9)]}, "with", "up")
    sampled = compare.permutation_test(one, "with", "up", exact_up_to=10)
    assert sampled["exact"] is False and sampled["permutations"] == 10 and 0 < sampled["p"] <= 1


def test_find_in_a_big_sheet_grades_the_event_and_the_bonus(tmp_path: Path) -> None:
    """Wave 17's bonus is event 284 of the fixture's sheet, GiveBonus(454); the wave and the bonus written near
    "event" are not taken for event numbers."""
    run_dir = tmp_path / "run"
    (run_dir / "project").mkdir(parents=True)
    (run_dir / "outputs").mkdir()
    (run_dir / "project" / "project.c3proj").write_text("{}", encoding="utf-8")
    (run_dir / "fixture.json").write_text(json.dumps(make_fixtures.digest(run_dir / "project")), encoding="utf-8")
    answer = run_dir / "outputs" / "answer.md"
    answer.write_text("Event 284, in the group Wave 17 score (event 280), pays the bonus of wave 17: it calls "
                      "GiveBonus(454), event 410, so the bonus is 454 points.\n\n## Commands run\n"
                      "python scripts/print_sheet.py Waves --events 1-17", encoding="utf-8")
    assert [ok for ok, _ in grader.grade_find_in_a_big_sheet(run_dir)] == [True, True, True, True]
    answer.write_text("Event 300 pays it: 380 points.", encoding="utf-8")
    assert [ok for ok, _ in grader.grade_find_in_a_big_sheet(run_dir)] == [False, False, False, True]
    assert make_fixtures.wave_bonus(make_fixtures.BIG_SHEET_FOCUS) == 454 and "coins-big-sheet" in make_fixtures.SEEDS


@pytest.mark.parametrize("command, whole", [
    ("python scripts/print_sheet.py Waves --limit 0", True),
    ('python scripts/print_sheet.py "Waves" --outline --limit=0', True),
    ("python scripts/print_sheet.py Waves --limit 0 --events 1-40", False),
    ("python scripts/print_sheet.py Waves --find GiveBonus --limit 0", False),
    ("python scripts/print_sheet.py Waves", False),
    ("python scripts/print_sheet.py Waves --limit 0 | grep -c Wave; python scripts/print_sheet.py Game", True),
])
def test_trace_counts_whole_sheet_prints_and_print_sheet_characters(tmp_path: Path, command: str, whole: bool) -> None:
    """The metric of a long sheet's list (docs/decisions/long-sheet-contents.md): what print_sheet.py printed, and
    how often a run asked for whole sheets past the limit."""
    transcript = transcript_of(tmp_path / "agent.jsonl", [("Bash", {"command": command}, "x" * 1234, False)])
    code, out = run(tmp_path, SKILL / "evals" / "trace.py", str(transcript), "--out", str(tmp_path))
    trace = read_json(tmp_path / "trace.json")
    assert code == 0 and trace["print_sheet_chars"] == 1234 and trace["whole_sheet_prints"] == int(whole)


def hud_results(case: Path, *words: str) -> tuple:
    """grade_lay_out_the_hud on case: the (passed, evidence) of the HUD case's first assertion holding each word."""
    results = dict(zip(CASES["lay-out-the-hud"]["assertions"], grader.grade_lay_out_the_hud(case)))
    return tuple(next(v for k, v in results.items() if word in k) for word in words)


def test_the_hud_case_grades_by_the_templates_own_rules(tmp_path: Path, project: Path) -> None:
    """A run of the HUD case is held to its own generator's MARGIN; a label inside its key's box is laid on
    purpose, not an overlap; a hollow box lies round a label and not behind it; and the stand-in's own HUD
    counts as nothing the run added."""
    pytest.importorskip("PIL")
    case = tmp_path / "it" / "lay-out-the-hud" / "with_skill"
    shutil.copytree(project, case / "project")
    assert grader.margin_of(case / "project") == 64 and grader.margin_of(tmp_path) == grader.MARGIN
    assert grader.one_colour(case / "project", "KeyBox") is None
    assert grader.one_colour(case / "project", "Coin") == (61, 90, 254)
    added, overlap, sizes, edges = hud_results(case, "besides", "overlap", "multiples", "held against")
    assert added[0] is False and "0 added instance(s)" in added[1]
    assert overlap == (True, "overlapping boxes: none")
    assert sizes[0] is False and "0 added non-text instance(s)" in sizes[1] and edges[0] is False


def test_the_hud_case_lines_a_small_drawing_up_by_what_it_draws(tmp_path: Path, project: Path) -> None:
    """A sprite the run adds to the HUD is sized in units and lines up by its box or by its drawing: a button
    drawn 64 px across in the middle of a 160 px box a finger hits has its drawing MARGIN inside the corner,
    and its box 16 px from the edge. The stand-in's texts are measured to their text and stay out of both."""
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw
    case = tmp_path / "it" / "lay-out-the-hud" / "with_skill"
    shutil.copytree(project, case / "project")
    image = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse([48, 48, 111, 111], fill=(20, 19, 17, 255))
    image.save(case / "project" / "images" / "pausebutton-default-000.png")
    (case / "project" / "objectTypes" / "PauseButton.json").write_text(
        json.dumps({"name": "PauseButton", "plugin-id": "Sprite"}), encoding="utf-8")
    path = case / "project" / "layouts" / "Game.json"
    layout = json.loads(path.read_text(encoding="utf-8"))
    ui = next(layer for layer in layout["layers"] if layer["name"] == "UI")["instances"]
    button = json.loads(json.dumps(next(i for i in ui if i["type"] == "KeyBox")))
    button["type"] = "PauseButton"
    ui.append(button)

    def graded(x: int, y: int) -> tuple:
        button["world"].update({"x": x, "y": y, "width": 160, "height": 160, "originX": 0, "originY": 0})
        path.write_text(json.dumps(layout), encoding="utf-8")
        return hud_results(case, "multiples", "held against")

    sizes, edges = graded(1920 - 64 - 112, 1080 - 64 - 112)
    assert sizes[0] is True and "1 added non-text instance(s)" in sizes[1]
    assert edges == (True, "added non-text types neither 64 px inside an edge, nor centred, nor one unit under a "
                           "held box, by box or drawing: none")
    sizes, edges = graded(1920 - 64 - 112 - 8, 1080 - 64 - 112)
    assert edges[0] is False and "PauseButton box (1736,904)-(1896,1064), drawn (1784,952)-(1848,1016)" in edges[1]


def test_a_step_handed_to_a_function_counts_by_the_constant_it_names() -> None:
    """`Call AddHealth(HP_PER_COIN)`, a constant at 10, whose body sets hp to `clamp(hp + amount, ...)`, adds 10
    to hp; handed a constant at 5 it does not."""
    def rows(per_coin: int) -> list:
        return [({"eventType": "variable", "name": "HP_PER_COIN", "initialValue": per_coin}, []),
                ({"eventType": "variable", "name": "hp", "initialValue": 40}, []),
                ({"eventType": "block", "actions": [{"callFunction": "AddHealth", "parameters": ["HP_PER_COIN"]}]}, []),
                ({"eventType": "function-block", "actions": [
                    {"id": "set-eventvar-value", "objectClass": "System",
                     "parameters": {"variable": "hp", "value": "clamp(hp + amount, 0, HP_MAX)"}}]}, [])]

    assert [a["parameters"]["value"] for a in grader.steps_by(rows(10), {"hp"}, "10")] == ["clamp(hp + amount, 0, HP_MAX)"]
    assert grader.steps_by(rows(5), {"hp"}, "10") == []


def test_the_lives_plan_counts_the_hearts_that_still_look_full() -> None:
    """Lives kept in a static local or drawn from a count of coins are no number the runtime shows, so the lives
    plan also watches, per sprite type of three or more on the UI layer, how many instances look like the
    leftmost one, leaving the stand-in's HUD out."""
    plan = play_cases.plan_for("lives-as-hearts")
    code = "\n".join(line for step in plan["steps"] if "js" in step for line in step["js"])
    assert "vars.h.fullHearts = () =>" in code and f"stand = {json.dumps(play_cases.STAND_IN_HUD)}" in code
    assert "vars.watch.numbers = () => Object.assign(vars.h.numbers(), vars.h.fullHearts())" in code


def test_lives_drawn_from_a_count_of_coins_start_at_5_and_drop_by_one() -> None:
    """`HEARTS - floor(taken / COINS_PER_LIFE)`, with HEARTS a constant at 5 and `Add 1 to taken` on a collect, are
    lives that start at 5 and drop by one, as a variable at 5 that loses 1 is; a count nothing adds 1 to is not."""
    def rows(step: str) -> list:
        return [({"eventType": "variable", "name": "HEARTS", "initialValue": 5}, []),
                ({"eventType": "variable", "name": "taken", "initialValue": 0}, []),
                ({"eventType": "block", "actions": [
                    {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "taken", "value": step}}]}, []),
                ({"eventType": "block", "conditions": [
                    {"id": "compare-instance-variable", "objectClass": "Heart",
                     "parameters": {"instance-variable": "slot", "comparison": 4,
                                    "value": "HEARTS - floor(taken / COINS_PER_LIFE)"}}]}, [])]

    assert grader.lives_from_count(rows("1"), {"HEARTS", "slot"}) == [("HEARTS", "taken")]
    assert grader.lives_from_count(rows("2"), {"HEARTS", "slot"}) == []
