"""evals/grade.py on answers of the name-the-restart-event case: what grading.json says about each.

The answers in fixtures/restart_event_answers/ are runs' answer.md files, with their run folder replaced by
<run>. The project of each run is empty and so is its fixture.json, so the third assertion passes throughout.
"""
import json
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, run

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
