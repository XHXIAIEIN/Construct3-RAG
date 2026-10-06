"""evals/grade.py on runs of its cases: what grading.json says about each.

The answers in fixtures/restart_event_answers/ are runs' answer.md files of the name-the-restart-event case,
with their run folder replaced by <run>. The project of each of those runs is empty and so is its fixture.json,
so the third assertion passes throughout. An add-countdown run is the stand-in game with the events it wrote.
"""
import json
import shutil
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
