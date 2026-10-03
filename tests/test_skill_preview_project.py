"""preview_project.py: the plan, checked before the editor opens, and the report."""
import json
import os
import re
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


def test_preview_project_keeps_the_result_in_the_project_by_default(tmp_path):
    """A plan whose printed lines a pipe cut is read again from the file, not played again."""
    pp = module()
    tmp = tmp_path / ".tmp"
    assert pp.kept(None, None, tmp_path) == (tmp / "preview-project.json", tmp / "preview")
    assert pp.kept(tmp_path / "r.json", tmp_path / "s", tmp_path) == (tmp_path / "r.json", tmp_path / "s")
    assert pp.where(tmp / "preview-project.json", tmp / "preview") == \
        f"full result in {tmp / 'preview-project.json'}, screenshots in {tmp / 'preview'}"


def test_preview_project_refuses_a_wrong_plan_before_opening_anything(project):
    """A plan is read whole first: every mistake is named with its step, and the
    browser is not started."""
    plan = project / "plan.json"
    plan.write_text(json.dumps({"speed": 2, "steps": [
        {"tapp": "Button"}, {"drag": "Piece 0"}, {"key": "F13"}, {"wait": -1}, {"shot": "a b"},
        {"tap": "Button", "seconds": 1}, {"until": "true", "timout": 3}, {"record": "a b"}, {"record": False},
        {"record": "r", "watch": {"coins": 3}}, {"record": False, "watch": {"coins": "1"}}], "keep_saves": True}),
        encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "plan.json")
    assert code == 2, out
    for expected in ("the plan has 'speed'", "step 1 has none of", "closest: tap", 'step 2 (drag) needs "to"',
                     "step 3 (key): 'F13'", "step 4 (wait) takes seconds", "step 5 (shot) takes a file name",
                     "step 6 (tap) has 'seconds'", "step 7 (until) has 'timout'; closest: timeout",
                     "step 8 (record) takes a file name of letters, digits, - and _, or false to stop",
                     'step 10 (record): watch is {"label": "EXPRESSION", ...}',
                     'step 11 (record): watch is {"label": "EXPRESSION", ...} on a step that starts'):
        assert expected in out, (expected, out)
    assert "step 9" not in out and "has 'keep_saves'" not in out, out     # false stops a recording
    assert not (project / ".tmp" / "preview").exists()

    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "--help")
    assert code == 0 and "TARGET is where to press" in out and "exit codes:" in out, out


def test_preview_project_reads_a_step_of_code_and_a_key_as_the_page_needs_them():
    pp = module()
    assert pp.code("runtime.globalVars.Score") == "return (runtime.globalVars.Score);"
    assert pp.code(["const p = runtime.objects.Player.getFirstInstance();", "return p.x;"]) == \
        "const p = runtime.objects.Player.getFirstInstance();\nreturn p.x;"
    assert pp.code("return 1") == "return 1"
    some = "runtime.objects.Enemy.getAllInstances().some(e => { return e.hp < 5; })"
    assert pp.code(some) == f"return ({some});"
    assert pp.code("vars.n = 1; return vars.n") == "vars.n = 1; return vars.n"
    assert pp.code("text === ';'") == "return (text === ';');"
    assert pp.key_event("ArrowRight") == {"key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39}
    assert pp.key_event("KeyZ") == pp.key_event("z") == pp.key_event("Z") == \
        {"key": "z", "code": "KeyZ", "windowsVirtualKeyCode": 90, "text": "z"}
    assert pp.key_event("1")["code"] == "Digit1" and pp.key_event("Space")["text"] == " "
    assert pp.key_event("F13") is None


def test_preview_project_waits_until_the_window_has_taken_the_viewport(monkeypatch):
    """The browser answers the emulation before the page resizes: a size read at once
    was the window's own, 778x511, while the runtime aimed in 430x932."""
    pp = module()

    class Page:
        def __init__(self, sizes):
            self.sizes, self.calls = sizes, []

        def call(self, method, **params):
            self.calls.append((method, params))

        def evaluate(self, expression):
            got = self.sizes.pop(0) if len(self.sizes) > 1 else self.sizes[0]
            if isinstance(got, Exception):
                raise got
            return got

    monkeypatch.setattr(pp.time, "sleep", lambda s: None)
    page = Page([pp.oe.DevToolsError("Cannot find context"), [778, 511], [778, 511], [430, 932]])
    assert pp.emulate(page, [430, 932]) == (430, 932)
    assert page.calls == [("Emulation.setDeviceMetricsOverride",
                           {"width": 430, "height": 932, "deviceScaleFactor": 1, "mobile": False})]
    monkeypatch.setattr(pp, "RESIZE", 0.05)
    assert pp.emulate(Page([[778, 511]]), [430, 932]) == (778, 511)
    assert pp.emulate(Page([pp.oe.DevToolsError("Cannot find context")]), [430, 932]) is None


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


def test_preview_project_prints_how_the_watched_values_changed():
    """The agent reviews a recording from these lines: each change once, with its time."""
    pp = module()
    frames = [{"t": 0.0, "watch": {"coins": 40, "y": None}}, {"t": 0.5, "watch": {"coins": 40, "y": 662}},
              {"t": 0.9, "watch": {"coins": 30, "y": 662}}]
    frames += [{"t": 1 + i / 10, "watch": {"coins": 30, "y": 600 - i}} for i in range(9)]
    assert pp.watch_lines(frames) == [
        "watch coins: 40 at 0 ms, 30 at 900 ms",
        "watch y: null at 0 ms, 662 at 500 ms, 600 at 1000 ms, 599 at 1100 ms, 598 at 1200 ms, 597 at 1300 ms, "
        "596 at 1400 ms, 595 at 1500 ms, and 3 more in timeline.json"]
    assert pp.watch_lines([{"t": 0.0}]) == []


def test_preview_project_lists_every_recording_in_an_index_page(tmp_path):
    """index.html beside the recordings lists each one that has its review page, the newest first."""
    pp = module()
    for name, when, steps in (("02-merge", 100, [{"ok": True, "errors": []}]),
                              ("05-drop", 200, [{"ok": False, "errors": ["TypeError: x"]}])):
        (tmp_path / name).mkdir()
        timeline = tmp_path / name / "timeline.json"
        timeline.write_text(json.dumps({"frames": [{"t": 0}, {"t": 1.5}], "steps": steps, "project": "D:/G"}),
                            encoding="utf-8")
        (tmp_path / f"{name}.html").write_text("", encoding="utf-8")
        os.utime(timeline, (when, when))
    (tmp_path / "07-left").mkdir()      # its review page was deleted
    (tmp_path / "07-left" / "timeline.json").write_text('{"frames": []}', encoding="utf-8")
    (tmp_path / "stray").mkdir()
    (tmp_path / "stray" / "timeline.json").write_text("not json", encoding="utf-8")

    page = pp.write_index(tmp_path).read_text(encoding="utf-8")
    listed = json.loads(re.search(r"const recordings = (.*?);\s+//", page).group(1))
    assert [r["name"] for r in listed] == ["05-drop", "02-merge"]
    assert {k: listed[0][k] for k in ("page", "project", "frames", "seconds", "steps", "failed", "errors")} == {
        "page": "05-drop.html", "project": "D:/G", "frames": 2, "seconds": 1.5, "steps": 1, "failed": 1, "errors": 1}
    assert "let timeline = /*TIMELINE*/null" in page     # it opens as the list, not as one recording
