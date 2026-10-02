"""preview_project.py: the plan, checked before the editor opens, and the report."""
import json
import sys

import pytest

from tests.skill_helpers import SKILL, INSTALLED, run


def module():
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import preview_project as pp
    finally:
        sys.path.pop(0)
    return pp


def test_preview_project_refuses_a_wrong_plan_before_opening_anything(project):
    """A plan is read whole first: every mistake is named with its step, and the
    browser is not started."""
    plan = project / "plan.json"
    plan.write_text(json.dumps({"speed": 2, "steps": [
        {"tapp": "Button"}, {"drag": "Piece 0"}, {"key": "F13"}, {"wait": -1}, {"shot": "a b"},
        {"tap": "Button", "seconds": 1}, {"until": "true", "timout": 3}, {"record": "a b"}, {"record": False}]}),
        encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "plan.json")
    assert code == 2, out
    for expected in ("the plan has 'speed'", "step 1 has none of", "closest: tap", 'step 2 (drag) needs "to"',
                     "step 3 (key): 'F13'", "step 4 (wait) takes seconds", "step 5 (shot) takes a file name",
                     "step 6 (tap) has 'seconds'", "step 7 (until) has 'timout'; closest: timeout",
                     "step 8 (record) takes a file name of letters, digits, - and _, or false to stop"):
        assert expected in out, (expected, out)
    assert "step 9" not in out, out     # false stops a recording
    assert not (project / ".tmp" / "preview").exists()

    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "--help")
    assert code == 0 and "TARGET is where to press" in out and "exit codes:" in out, out


def test_preview_project_reads_a_step_of_code_and_a_key_as_the_page_needs_them():
    pp = module()
    assert pp.code("runtime.globalVars.Score") == "return (runtime.globalVars.Score);"
    assert pp.code(["const p = runtime.objects.Player.getFirstInstance();", "return p.x;"]) == \
        "const p = runtime.objects.Player.getFirstInstance();\nreturn p.x;"
    assert pp.code("return 1") == "return 1"
    assert pp.key_event("ArrowRight") == {"key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}
    assert pp.key_event("KeyZ") == pp.key_event("z") == pp.key_event("Z") == \
        {"key": "z", "code": "KeyZ", "windowsVirtualKeyCode": 90, "text": "z"}
    assert pp.key_event("1")["code"] == "Digit1" and pp.key_event("Space")["text"] == " "
    assert pp.key_event("F13") is None


def test_preview_project_reports_each_step_with_the_errors_it_caused():
    """One line per step; a runtime error under the step it followed; a failed step
    ends the list and says why."""
    pp = module()
    steps = [{"step": 1, "line": "1 tap Button (buy)", "ok": True, "said": "at (352, 882)",
              "errors": ["Event sheet 1, event 3, action 1: TypeError\n    at stack"]},
             {"step": 2, "line": "2 state Piece", "ok": True, "said": "", "errors": [],
              "state": {"globalVars": {"coins": 30}, "counts": {"Piece": 1}, "objects": {}}},
             {"step": 3, "line": "3 until vars.done", "ok": False, "said": "still false after 10 s", "errors": []}]
    lines = pp.report({"project": "Game", "status": "opened", "title": "Game - Construct 3",
                       "editor": "https://editor.construct.net/", "dialogs": [], "exception": "",
                       "preview": {"started": True, "layout": "Game", "runtime": "page", "viewport": [430, 932],
                                   "touch": True, "errors": [], "steps": steps, "planned": 4, "seconds": 3.94}})
    assert lines[1:] == [
        "  preview: layout 'Game' at the end, runtime in the page, viewport 430x932, touch",
        "  1 tap Button (buy): at (352, 882)",
        "    runtime: Event sheet 1, event 3, action 1: TypeError",
        "  2 state Piece",
        "    globals: coins 30",
        "    objects: Piece 1",
        "  3 until vars.done: FAILED, still false after 10 s",
        "  ran: 2 of 4 steps in 3.9 s, 1 runtime error",
    ], lines


def test_preview_project_joins_a_recording_into_a_gif_without_ffmpeg(tmp_path, monkeypatch):
    """Each frame stays up for as long as the window showed it."""
    image = pytest.importorskip("PIL.Image")
    pp = module()
    frames = []
    for i, colour in enumerate(("red", "blue")):
        frames.append(tmp_path / f"{i + 1:04d}.jpg")
        image.new("RGB", (8, 8), colour).save(frames[-1])
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    made = pp.make_video(frames, [0.25, 0.05], tmp_path / "02-merge")
    assert made == str(tmp_path / "02-merge.gif")
    with image.open(made) as gif:
        assert gif.n_frames == 2 and gif.info["duration"] == 250
