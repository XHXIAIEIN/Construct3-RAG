"""evals/grade.py over a run it has not seen: a design an agent wrote, graded the way an iteration is."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, SHEET


def graded(tmp_path: Path, project: Path, case: str) -> dict[str, dict]:
    """grading.json of one run of case, the project as it is, by the text of each assertion."""
    run = tmp_path / "iteration" / case / "with_skill"
    shutil.copytree(project, run / "project")
    (run / "fixture.json").write_text("{}", encoding="utf-8")
    p = subprocess.run([sys.executable, str(SKILL / "evals" / "grade.py"), str(tmp_path / "iteration")],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    results = json.loads((run / "grading.json").read_text(encoding="utf-8"))["assertion_results"]
    return {r["text"].split(":")[0]: r for r in results}


@pytest.mark.parametrize("kind, counts", [("regular", True), ("once", False)])
def test_a_countdown_on_a_one_second_timer_loses_one_per_second(tmp_path, project, kind, counts):
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

    result = graded(tmp_path, project, "add-countdown")["The countdown loses one per second"]
    assert result["passed"] is counts, result
    assert 'on-timer("tick") -> set-eventvar-value(Countdown | Countdown - 1)' in result["evidence"]
