"""preview_project.py: the plan, checked before the editor opens, and the report."""
import json
import os
import re
import sys

import pytest

from tests.skill_helpers import SKILL, INSTALLED, run

sys.path.insert(0, str(SKILL / "scripts"))
try:
    import preview_project as pp  # noqa: E402
finally:
    sys.path.pop(0)


def test_preview_project_keeps_the_result_in_the_project_by_default(tmp_path):
    """A plan whose printed lines a pipe cut is read again from the file, not played again."""
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
        {"record": "r", "watch": {"coins": 3}}, {"record": False, "watch": {"coins": "1"}},
        {"drag": "Ball", "to": "Ball", "through": "Goal", "rest": -1},
        {"drag": "Ball", "to": "Ball", "through": [{"x": 1, "y": 2}], "rest": 0}],
        "keep_saves": True, "pixel_ratio": 0}), encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "plan.json")
    assert code == 2, out
    for expected in ("the plan has 'speed'", "step 1 has none of", "closest: tap", 'step 2 (drag) needs "to"',
                     "step 3 (key): 'F13'", "step 4 (wait) takes seconds", "step 5 (shot) takes a file name",
                     "step 6 (tap) has 'seconds'", "step 7 (until) has 'timout'; closest: timeout",
                     "step 8 (record) takes a file name of letters, digits, - and _, or false to stop",
                     'step 10 (record): watch is {"label": "EXPRESSION", ...}',
                     'step 11 (record): watch is {"label": "EXPRESSION", ...} on a step that starts',
                     "step 12 (drag): through is a list of targets", "step 12 (drag): rest is a number of seconds",
                     "pixel_ratio is device pixels per CSS pixel"):
        assert expected in out, (expected, out)
    assert "step 9" not in out and "step 13" not in out, out     # false stops a recording
    assert "has 'keep_saves'" not in out and "has 'pixel_ratio'" not in out, out
    assert not (project / ".tmp" / "preview").exists()

    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "--help")
    assert code == 0 and "TARGET is where to press" in out and "exit codes:" in out, out


def test_preview_project_reads_a_step_of_code_and_a_key_as_the_page_needs_them():
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
    page = Page([pp.oe.DevToolsError("Cannot find context"), [778, 511, 1], [778, 511, 1], [430, 932, 1]])
    assert pp.emulate(page, [430, 932]) == (430, 932)
    assert page.calls == [("Emulation.setDeviceMetricsOverride",
                           {"width": 430, "height": 932, "deviceScaleFactor": 1, "mobile": False})]
    page = Page([[430, 932, 1], [430, 932, 2]])     # a pixel ratio alone keeps the window's size
    assert pp.emulate(page, None, 2) == (430, 932) and not page.sizes[1:]
    assert page.calls[0][1] == {"width": 0, "height": 0, "deviceScaleFactor": 2, "mobile": False}
    monkeypatch.setattr(pp, "RESIZE", 0.05)
    assert pp.emulate(Page([[778, 511, 1]]), [430, 932]) == (778, 511)
    assert pp.emulate(Page([pp.oe.DevToolsError("Cannot find context")]), [430, 932]) is None


def test_preview_project_drags_through_its_waypoints_and_can_release_moving(monkeypatch, tmp_path):
    """A path back to where the drag started, every target aimed before the press; each
    leg's time by its length; with rest 0 the release follows the last move at once."""
    moves = pp.path([(0, 0), (90, 0), (0, 0)], 0.48)
    assert len(moves) == 16 and moves[7][1:] == (90, 0) and moves[-1][1:] == (0, 0)
    assert sum(m[0] for m in moves) == pytest.approx(0.48)
    assert pp.path([(0, 0), (30, 40)], 0.4) == [(0.4 / 13, 30 * k / 13, 40 * k / 13) for k in range(1, 14)]
    legs = pp.path([(0, 0), (300, 0), (300, 100)], 0.8)
    assert sum(m[0] for m in legs if m[2] == 0) == pytest.approx(0.6)

    game = pp.Game(None, None, True, (430, 932), "", None, tmp_path)
    places = {"Ball": (100, 500), "Goal": (300, 200)}
    sent, slept = [], []
    monkeypatch.setattr(game, "aim", lambda t: places[t] if isinstance(t, str) else (t["x"], t["y"]))
    monkeypatch.setattr(game, "finger", lambda kind, x=0, y=0: sent.append((kind, round(x), round(y))))
    monkeypatch.setattr(pp.time, "sleep", slept.append)
    step = {"drag": "Ball", "through": ["Goal", {"x": 100, "y": 200}], "to": "Ball", "seconds": 0.9, "rest": 0}
    said, _ = pp.do_step(game, step, 1, tmp_path)
    assert said == "(100, 500) through (300, 200) through (100, 200) to (100, 500) in 0.9 s, released moving"
    assert pp.step_line(1, step) == "1 drag Ball through Goal through (100, 200) on the first layer to Ball"
    assert sent[0] == ("touchStart", 100, 500) and sent[-2] == ("touchMove", 100, 500) and sent[-1][0] == "touchEnd"
    assert ("touchMove", 300, 200) in sent and ("touchMove", 100, 200) in sent and slept[-1] == 0


def test_preview_project_reports_each_step_with_the_errors_it_caused():
    """One line per step; a runtime error under the step it followed; a failed step
    ends the list and says why."""
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


class ReloadingGame:
    """A game whose page reloads: each step's outcomes in turn, and what reloaded() answers after each try."""

    def __init__(self, outcomes, reloads):
        self.outcomes, self.reloads, self.win, self.recording, self.tries = outcomes, reloads, None, None, []

    def reloaded(self):
        back = self.reloads.pop(0)
        if isinstance(back, Exception):
            raise back
        return back


def play_reloading(monkeypatch, tmp_path, steps, outcomes, reloads):
    game = ReloadingGame(outcomes, reloads)

    def do_step(game, step, n, shots):
        game.tries.append(n)
        got = game.outcomes.pop(0)
        if isinstance(got, Exception):
            raise got
        return got, None

    monkeypatch.setattr(pp, "do_step", do_step)
    monkeypatch.setattr(pp.oe, "runtime_errors", lambda win: [])
    monkeypatch.setattr(pp, "screenshot", lambda game, path: str(path.name))
    return game, pp.play_steps(game, steps, tmp_path)


def test_preview_project_goes_on_after_the_game_reloads_its_page(monkeypatch, tmp_path):
    """A tap on a button that reloads the page: the probe is left again, the step after
    it that found no probe runs again in the new page, and every step's result is kept."""
    steps = [{"tap": "ResetButton"}, {"until": "runtime.globalVars.Level === 1"}, {"tap": "StartButton"}]
    game, played = play_reloading(monkeypatch, tmp_path, steps,
                                  ["at (40, 600)", pp.oe.DevToolsError("ReferenceError: c3play is not defined"),
                                   "true after 0.2 s", "at (215, 466)"],
                                  [1.24, 0.81, None, None])
    assert game.tries == [1, 2, 2, 3]
    assert [(d["ok"], d["said"], d.get("reloaded")) for d in played] == [
        (True, "at (40, 600); then the page reloaded, and the game started again 1.2 s later", [1.2]),
        (True, "the page reloaded during the step, so it ran again 0.8 s later: true after 0.2 s", [0.8]),
        (True, "at (215, 466)", None)]


def test_preview_project_leaves_the_probe_again_in_the_reloaded_page(monkeypatch, tmp_path):
    """The worker that ran the game went with the page; the new one gets the probe and c3play."""

    class Window:
        def __init__(self):
            self.calls = []

        def evaluate(self, js, wait=None, session=None):
            if js == "typeof c3play === 'object'":
                raise pp.oe.DevToolsError("Runtime.evaluate: Session with given id not found.")
            self.calls.append(("evaluate", js[:12], session))

        def call(self, method, session=None, **params):
            self.calls.append((method, session))

    win = Window()
    game = pp.Game(win, "worker-1", False, (430, 932), "", None, tmp_path)
    monkeypatch.setattr(pp.oe, "attach", lambda win, patience: ([None, "worker-2"], ["worker-2"], False))
    assert game.reloaded() >= 0 and game.live == "worker-2"
    assert win.calls == [("evaluate", pp.PLAY_JS[:12], "worker-2"), ("Runtime.enable", None),
                         ("Runtime.enable", "worker-2")]
    monkeypatch.setattr(pp.oe, "attach", lambda win, patience: ([None], [], False))
    with pytest.raises(pp.StepFailed, match="the page reloaded, and no runtime ran in it in 30 seconds"):
        game.reloaded()


def test_preview_project_stops_with_the_steps_kept_when_a_reload_breaks_off_a_js_step(monkeypatch, tmp_path):
    """Code that had started may have done part of its work, so it does not run twice; a
    page that runs no game after the reload stops the plan, naming the reload."""
    steps = [{"wait": 1}, {"js": "runtime.callFunction('wipe')"}, {"wait": 1}]
    game, played = play_reloading(monkeypatch, tmp_path, steps,
                                  ["ok", pp.oe.DevToolsError("Execution context was destroyed.")], [None, 0.5])
    assert game.tries == [1, 2] and [d["ok"] for d in played] == [True, False]
    assert played[1]["said"] == ("Execution context was destroyed.; the page reloaded while the code ran, so the step "
                                 "did not run again; the window then: 02-failed.png")

    steps = [{"tap": "ResetButton"}, {"wait": 1}]
    _, played = play_reloading(monkeypatch, tmp_path, steps, ["at (40, 600)"],
                               [pp.StepFailed("the page reloaded, and no runtime ran in it in 30 seconds")])
    assert [(d["ok"], d["said"]) for d in played] == [
        (False, "at (40, 600); the page reloaded, and no runtime ran in it in 30 seconds; the window then: "
                "01-failed.png")]


def test_preview_project_joins_a_recording_into_a_gif_without_ffmpeg(tmp_path, monkeypatch):
    """Each frame stays up for as long as the window showed it."""
    image = pytest.importorskip("PIL.Image", reason="Pillow is not installed; pip install pillow")
    frames = [tmp_path / "0001.jpg", tmp_path / "0002.jpg"]
    for frame, colour in zip(frames, ("red", "blue")):
        image.new("RGB", (8, 8), colour).save(frame)
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    made = pp.make_video(frames, [0.25, 0.05], tmp_path / "02-merge")
    assert made == str(tmp_path / "02-merge.gif")
    with image.open(made) as gif:
        assert gif.n_frames == 2 and gif.info["duration"] == 250


def test_preview_project_picks_the_frames_of_a_contact_sheet():
    """The ends, each step's start and end, the frames around the largest change, each with why,
    and the cells left over where the picture moves: here the slide of frames 1 to 30."""
    frames = [{"t": i / 30, "watch": {"x": 50 + min(i, 30) * 4 + (200 if i >= 40 else 0), "label": "a"}}
              for i in range(60)]
    change = pp.frame_change([], frames)        # no frame files: the watched numbers tell
    assert max(range(60), key=change.__getitem__) == 40
    steps = [{"step": 3, "start": 0.2, "end": 1.0}]
    assert pp.sheet_frames(frames, steps, change) == [
        (0, "start"), (6, "step 3 starts"), (9, ""), (24, ""), (30, "step 3 ends"), (39, ""), (40, "largest change"),
        (41, ""), (59, "end")]
    many = [{"step": n, "start": n / 10, "end": n / 10 + 0.05} for n in range(1, 19)]
    picked = pp.sheet_frames(frames, many, [0.0] * 60)
    assert len(picked) == pp.SHEET_CELLS and picked[0] == (0, "start") and picked[-1] == (59, "end")
    assert [i for i, _ in pp.sheet_frames(frames[:3], [], [0.0] * 3)] == [0, 1, 2]


@pytest.mark.parametrize("pillow", [True, False])
def test_preview_project_joins_the_sheet_frames_into_one_image(tmp_path, monkeypatch, pillow):
    """With Pillow each frame is numbered with its time; ffmpeg alone tiles them, a short last row included."""
    image = pytest.importorskip("PIL.Image", reason="Pillow is not installed; pip install pillow")
    if not pillow and not (pp.shutil.which("ffmpeg") and pp.shutil.which("ffprobe")):
        pytest.skip("ffmpeg is not installed")
    paths = []
    for k in range(7):
        paths.append(tmp_path / f"{k + 1:04d}.jpg")
        image.new("RGB", (430, 932), (k * 30, 0, 0)).save(paths[-1])
    if not pillow:
        real = __import__
        monkeypatch.setattr("builtins.__import__", lambda name, *a, **k: (_ for _ in ()).throw(ImportError(name))
                            if name.startswith("PIL") else real(name, *a, **k))
    made = pp.make_sheet(paths, [k / 10 for k in range(7)], tmp_path / "02-merge-sheet.png")
    monkeypatch.undo()
    assert made == str(tmp_path / "02-merge-sheet.png")
    with image.open(made) as sheet:
        assert max(sheet.size) <= pp.SHEET_SIDE and sheet.size[0] > sheet.size[1] / 2


def test_preview_project_prints_how_the_watched_values_changed():
    """The agent reviews a recording from these lines: each change once, with its time."""
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
