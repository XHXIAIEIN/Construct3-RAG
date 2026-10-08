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
        {"drag": "Ball", "to": "Ball", "through": [{"x": 1, "y": 2}], "rest": 0},
        {"key": []}, {"key": ["ShiftLeft", "F13"]}, {"key": ["a", "KeyA"]}, {"key": ["ShiftLeft", "ArrowRight"]}],
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
                     "pixel_ratio is device pixels per CSS pixel", "step 14 (key): the list is empty",
                     "step 15 (key): 'F13' is no key", "or a list of them to hold together",
                     "step 16 (key) names a key twice"):
        assert expected in out, (expected, out)
    assert "step 9" not in out and "step 13" not in out and "step 17" not in out, out     # false stops a recording
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


def test_preview_project_holds_keys_together_with_their_modifiers(monkeypatch, tmp_path):
    """Keys pressed in order and released in reverse; while Shift is down every
    later event says so, and one key is pressed as before."""
    game = pp.Game(None, None, False, (430, 932), "", None, tmp_path)
    sent = []
    monkeypatch.setattr(game, "win", type("Win", (), {"call": lambda self, method, **e: sent.append(e)})())
    monkeypatch.setattr(pp.time, "sleep", lambda s: None)
    step = {"key": ["ShiftLeft", "ArrowRight"], "seconds": 1}
    assert pp.do_step(game, step, 3, tmp_path) == ("held 1 s", None)
    assert pp.step_line(3, step) == "3 key ShiftLeft+ArrowRight"
    assert [(e["type"], e["code"], e["modifiers"]) for e in sent] == [
        ("rawKeyDown", "ShiftLeft", 8), ("rawKeyDown", "ArrowRight", 8),
        ("keyUp", "ArrowRight", 8), ("keyUp", "ShiftLeft", 0)]
    sent.clear()
    pp.do_step(game, {"key": "a"}, 1, tmp_path)
    assert [(e["type"], e["key"], e["modifiers"], e.get("text")) for e in sent] == [
        ("keyDown", "a", 0, "a"), ("keyUp", "a", 0, None)]


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


def test_preview_project_says_what_a_passing_plan_left_untested():
    steps = [{"step": 1, "line": "1 tap Button (buy)", "ok": True, "said": "at (352, 882)", "errors": []}]
    lines = pp.report({"project": "Game", "status": "opened", "title": "Game - Construct 3",
                       "editor": "https://editor.construct.net/", "dialogs": [], "exception": "",
                       "preview": {"started": True, "layout": "Game", "runtime": "page", "viewport": [430, 932],
                                   "touch": False, "errors": [], "steps": steps, "planned": 1, "seconds": 1.2}})
    assert lines[-1] == "  ran: 1 of 1 steps in 1.2 s, no runtime errors; what the steps of the plan do not do is untested"


def test_preview_project_prints_an_error_raised_every_tick_once_with_its_count():
    """An error raised every tick comes hundreds of times; printed once a line it pushed a different
    error past the output's limit in a probe. Each distinct error is one line, in the order it
    first came, with how many times it came; the total stays in the ran line."""
    root = "Game, event 10, action 1: TypeError: Cannot read properties of null (reading 'limit')"
    tick = "Game, event 11, action 1: TypeError: Cannot read properties of undefined (reading 'push')"
    other = "Game, event 12, action 1: RangeError: a separate failure"
    errors = [root + "\n    at stack", *[tick] * 300, other, *[tick] * 200, other]
    steps = [{"step": 1, "line": "1 wait 5 s", "ok": True, "said": "ok", "errors": errors}]
    lines = pp.report({"project": "Game", "status": "opened", "title": "Game - Construct 3",
                       "editor": "https://editor.construct.net/", "dialogs": [], "exception": "",
                       "preview": {"started": True, "layout": "Game", "runtime": "page", "viewport": [430, 932],
                                   "touch": False, "errors": [], "steps": steps, "planned": 1, "seconds": 5.1}})
    assert lines[2:] == [
        "  1 wait 5 s: ok",
        f"    runtime: {root}",
        f"    runtime: {tick} (500 times)",
        f"    runtime: {other} (2 times)",
        "  ran: 1 of 1 steps in 5.1 s, 503 runtime errors",
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


def test_preview_project_replays_the_kept_plans_and_names_the_one_that_fails_now():
    """--all: one line per kept plan; a failed step, a runtime error or a refused plan fails it."""
    def done(steps, planned=None, errors=()):
        return {"started": True, "errors": list(errors), "steps": steps, "planned": planned or len(steps),
                "seconds": 2.04}
    ok = {"step": 1, "line": "1 wait 0.5 s", "ok": True, "said": "ok", "errors": []}
    bad = {"step": 2, "line": "2 until vars.merged", "ok": False, "said": "still false after 10 s", "errors": []}
    logged = {**ok, "errors": ["Event sheet 1, event 4, action 2: TypeError\n    at stack"]}
    result = {"project": "Game", "status": "opened", "title": "Game - Construct 3", "editor": "e", "preview": {
        "plans": {"merge": done([ok, bad], 3), "hint": done([ok]), "buy": done([logged])}}}
    lines, failed = pp.replay_report(result, {"old": ["step 1 has none of tap, hold"]})
    assert failed == 3
    assert lines[1:] == [
        "  FAIL  buy (tools/plans/buy.json): runtime: Event sheet 1, event 4, action 2: TypeError",
        "  ok    hint: 1 step in 2.0 s",
        "  FAIL  merge (tools/plans/merge.json): 2 until vars.merged: FAILED, still false after 10 s",
        "  FAIL  old (tools/plans/old.json): the plan is refused: step 1 has none of tap, hold",
        "  replayed: 1 of 4 kept plans pass, 1 runtime error",
    ], lines


def test_preview_project_keeps_a_plan_in_the_project_and_needs_one_to_replay(project, tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text('{"steps": [{"wait": 1}]}\n', encoding="utf-8")
    kept = pp.keep(plan, project, "merge-two")
    assert kept == project / "tools" / "plans" / "merge-two.json"
    assert kept.read_bytes() == plan.read_bytes()
    assert pp.kept_plans(project) == [kept]
    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "plan.json", "--keep", "a b")
    assert code == 2 and "--keep takes a NAME of letters, digits, - and _" in out, out
    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py")
    assert code == 2 and "give a PLAN.json to play, or --all" in out, out
    kept.unlink()
    code, out = run(project, f"{INSTALLED}/scripts/preview_project.py", "--all")
    assert code in (2, 3) and ("no kept plan in" in out or "no Edge, Chrome or Chromium" in out), out
