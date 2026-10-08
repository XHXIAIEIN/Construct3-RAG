"""Preview a project in the Construct 3 editor and play it from a plan: tap, hold
and drag the game's own instances, press keys, wait for what the events do, run
scripts against the runtime, and read the state, take screenshots and record between steps.

    python scripts/preview_project.py PLAN.json [--keep NAME] [--project FOLDER] [--release rNNN]
                                      [--browser EXE] [--shots DIR] [--out RESULT.json] [--headed]
                                      [--profile FOLDER] [--locale en-US]
    python scripts/preview_project.py --all [--project FOLDER] ...

Use it to check what a player does: a merge, a drop, a jump, a purchase. The
plan is JSON, the steps run in order, and a step that fails stops the run:

  {"viewport": [430, 932], "touch": true,
   "steps": [
     {"until": "runtime.objects.Enemy.getAllInstances().length >= 3", "timeout": 10},
     {"js": "runtime.callFunction('finishTutorial')"},
     {"tap": "StartButton"},
     {"drag": "Piece 0", "to": "BattleSlot 1", "seconds": 0.4},
     {"drag": "Ball", "through": [{"x": 300, "y": 200}], "to": "Ball", "seconds": 0.8},
     {"drag": "Card", "to": {"x": 215, "y": 100}, "seconds": 0.15, "rest": 0},
     {"hold": {"x": 40, "y": 600, "layer": "UI"}, "seconds": 1},
     {"key": "ArrowRight", "seconds": 0.5},
     {"wait": 1.5, "note": "the merge animation"},
     {"state": ["Piece", "BattleSlot"]},
     {"shot": "after-merge"}]}

viewport  CSS pixels of the preview window, [width, height]; a phone's, 430 x 932,
          for a game designed for one (default: the window the editor opens)
touch     taps, holds and drags as touches instead of the mouse (default: false)
keep_saves  start from what earlier runs saved, Local Storage and IndexedDB, instead of
          from a first launch (default: false); the browser profile keeps them
pixel_ratio  device pixels per CSS pixel: the game draws, and screenshots and recordings
          come out, at that scale, 2 or 3 for a phone (default: 1)

Steps, each an object with one of these keys, and "note" for a label:
  tap TARGET                    press and release
  hold TARGET, seconds          press, wait, release (default 0.5 s)
  drag TARGET, to TARGET, seconds, through, rest
                                press, move in steps, release (default 0.4 s). through is a list
                                of TARGETs the pointer passes on the way, the time shared by
                                distance; every target is aimed before the press, so "to" can be
                                where the drag started. rest is the seconds the pointer stays
                                still on "to" before the release (default 0.05). For a flick,
                                give 0: the release follows the last move, since Touch reads a
                                speed of 0 from a pointer that has been still about 50 ms
  key NAME, seconds             press a key: ArrowLeft, Space, Enter, Escape, KeyA or a, Digit1 or 1
                                (default 0.1 s)
  wait SECONDS                  let the game run
  until EXPRESSION, timeout     wait until the JavaScript expression is true (default 10 s)
  js CODE                       run JavaScript against the runtime and print what it returns
  state [TYPE ...]              the globals, every type's count, the named types' instances with
                                their inspector values, named in --locale
  shot NAME                     a screenshot, NN-NAME.png in --shots
  record NAME, watch            record the window from here to the next record step or the end
                                of the plan, as NN-NAME.mp4 with ffmpeg, NN-NAME.gif with Pillow,
                                and always the frames, NN-NAME/0001.jpg ...; false stops it.
                                watch is {"label": EXPRESSION, ...}, read at every frame. The
                                recording leaves NN-NAME-sheet.png, up to 12 of its frames in one
                                image, each numbered with its time: the ends, the steps' starts
                                and ends, the largest change and where the picture moves most,
                                for the agent to judge the motion from (unnumbered with ffmpeg
                                and no Pillow); NN-NAME.html to review it: the frames, the steps
                                that ran and the watched values, frame by frame, and a part
                                selected there copied as a task for an agent; and
                                NN-NAME/timeline.json with the same. index.html in --shots
                                lists every recording there

TARGET is where to press, the middle of an instance's bounding box:
  "Button"                      the first instance of an object type, as the project spells it
  "Piece 2"                     its instance of index 2, in creation order
  "uid 12"                      an instance by UID
  {"x": 40, "y": 600, "layer": "UI"}   a position on a layer (default: the layout's first layer)
  {"js": "CODE"}                JavaScript that returns an instance, a UID, or {x, y, layer}

CODE and EXPRESSION see `runtime`, the scripting API (IRuntime), `vars`, an object
kept from step to step, and `wait(seconds)`. A single expression is returned as it
is; longer code says `return`. A list of strings is joined into lines.

The game starts on the layout the editor opens on, as with F5. A game that
reloads its page, with Browser Reload, starts again in the new page, and the plan
goes on there: the step's line says that the page reloaded. A step the reload
broke off runs again, except a js step whose code had started, which fails.

The browser runs headless and silent; --headed shows it. A step that fails
leaves a screenshot, NN-failed.png. Screenshots and recordings go to --shots, by default
.tmp/preview/ in the project, and the whole result, every value and state, to
--out, by default .tmp/preview-project.json; .tmp/ is ignored by Git. The last
line names both: read a cut-off result there instead of playing the plan again.

A plan that passes is kept with --keep NAME as tools/plans/NAME.json in the
project, committed with the change it checks; the editor ignores the folder.
--all replays every kept plan in one editor session, each from a first launch,
and names each one that fails, because a later change broke what it checks. Its result goes to .tmp/preview-plans.json and its screenshots
to .tmp/preview-plans/NAME/.

The result holds what the editor did, as open_in_editor.py writes it, and the
run under "preview"; the steps are in preview.steps, one object per step that ran:
  {"project", "status": "opened", "title", "editor", "warnings", ...,
   "preview": {"started": true, "layout" at the end, "runtime", "viewport",
     "pixel_ratio", "touch", "seconds", "planned" steps, "errors" before the first step,
     "recorded",
     "steps": [{"step": 1, "line", "ok", "said", "errors" the step caused,
                "value" of a js step, "state" of a state step,
                "reloaded": [seconds the game took to start again] after the page reloaded}]}}
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import c3project as c3
import open_in_editor as oe

EPILOG = """examples:
  python scripts/preview_project.py .tmp/merge-plan.json
  python scripts/preview_project.py plan.json --project "D:/Games/Merge" --headed
  python scripts/preview_project.py .tmp/merge-plan.json --keep merge-two-pieces
  python scripts/preview_project.py --all

output:
  opened   <project>  (<window title>, <the editor it opened in>)
    warning: <a notice the editor showed over the opened project, as open_in_editor.py prints it>
    preview: layout 'Game', runtime in the worker, viewport 430x932, touch
    1 until runtime.objects.Enemy.getAllInstances().length >= 3: true after 1.4 s
    2 drag Piece 0 to BattleSlot 1: (120, 712) to (215, 388) in 0.4 s
      runtime: <an error the game logged during the step, with its event, and (N times) when it came more than once>
    3 state Piece: <as open_in_editor.py --state prints it>
    4 shot after-merge: .tmp/preview/04-after-merge.png
    recorded merge: 95 frames in 3.4 s, .tmp/preview/02-merge.mp4
      sheet .tmp/preview/02-merge-sheet.png: 10 frames, numbered left to right, top down: 1 at 0 ms (start),
      2 at 35 ms (largest change), ..., 10 at 3380 ms (end)
        judge the motion from the sheet, not from what the events meant to do: open it with the image tool,
        name the three worst defects, each with its time, what the frame shows and the event to change, fix
        only those, and record that part again
      review .tmp/preview/02-merge.html: the user plays it there, selects the part that looks wrong and
      copies it to you as a task; .tmp/preview/index.html lists every recording
      frames and timeline.json in .tmp/preview/02-merge
      watch coins: 40 at 0 ms, 30 at 900 ms
    ran: 4 of 4 steps in 9.6 s, 1 runtime error

--all prints one line per kept plan instead of its steps:
    ok    merge-two-pieces: 6 steps in 4.1 s
    FAIL  hint-after-idle (tools/plans/hint-after-idle.json): step 3 until ...: FAILED, false after 10 s
  replayed: 1 of 2 kept plans pass, no runtime errors

exit codes: 0 every step ran and the game logged no error (--all: in every kept plan); 1 a step failed, the
game logged an error, or the project did not open; 2 the plan, the project, the editor or --locale could not be
used, or --all found no kept plan; 3 no browser here
"""

STEPS = ("tap", "hold", "drag", "key", "wait", "until", "js", "state", "shot", "record")
# Where a project keeps the plans that passed, one per change they checked.
KEPT = Path("tools") / "plans"
FIELDS = {"tap": set(), "hold": {"seconds"}, "drag": {"to", "seconds", "through", "rest"}, "key": {"seconds"}, "wait": set(),
          "until": {"timeout"}, "js": {"timeout"}, "state": set(), "shot": set(), "record": {"watch"}}
PRESS = {"hold": 0.5, "drag": 0.4, "key": 0.1}
# Seconds the preview window gets to take the plan's viewport.
RESIZE = 5
# Seconds a page the game reloaded gets to run its runtime again.
RELOAD = 30
# Where the editor serves a preview, and where a game's saves live.
PREVIEW = "https://preview.construct.net"
# The page that reviews a recording, its timeline put where it says TIMELINE.
REVIEW = (c3.SKILL_DIR / "assets" / "recording-review.html").read_text(encoding="utf-8")

# Left in the session that runs the game, after the probe: where a target is on the
# page, and what a step's code returns, as JSON. layerToCssPx gives the client
# position an input event of the page carries.
PLAY_JS = r"""(() => {
  if (globalThis.c3play) return true;
  const runtime = c3probe.runtime;
  const types = () => Object.keys(runtime.objects);
  const find = spec => {
    if (typeof spec === 'number') return runtime.getInstanceByUid(spec) || {error: `no instance has UID ${spec}`};
    const uid = /^uid\s+(\d+)$/i.exec(spec);
    if (uid) return runtime.getInstanceByUid(+uid[1]) || {error: `no instance has UID ${uid[1]}`};
    const [, name, index] = /^(.*?)(?:\s+(\d+))?$/.exec(spec.trim());
    const type = runtime.objects[name];
    if (!type) return {error: `no object type ${name}`, name, types: types()};
    const all = type.getAllInstances(), i = Number(index || 0);
    return all[i] || {error: `${name} has ${all.length} instance${all.length == 1 ? '' : 's'}, none of index ${i}`};
  };
  globalThis.c3play = {
    vars: {},
    wait: s => new Promise(r => setTimeout(r, s * 1000)),
    aim(spec) {
      let inst = spec;
      if (typeof spec === 'string' || typeof spec === 'number') inst = find(spec);
      if (inst && inst.error) return inst;
      if (inst && typeof inst.getBoundingBox === 'function') {
        const box = inst.getBoundingBox(), [x, y] = inst.layer.layerToCssPx(box.x + box.width / 2, box.y + box.height / 2);
        return {x, y, uid: inst.uid};
      }
      if (inst && typeof inst.x === 'number' && typeof inst.y === 'number') {
        const layer = inst.layer === undefined ? runtime.layout.getLayer(0) : runtime.layout.getLayer(inst.layer);
        if (!layer) return {error: `the layout ${runtime.layout.name} has no layer ${inst.layer}`};
        const [x, y] = layer.layerToCssPx(inst.x, inst.y);
        return {x, y};
      }
      return {error: `the target is ${JSON.stringify(inst) ?? String(inst)}: give an instance, a UID or {x, y, layer}`};
    },
    plain(v) {
      if (v && typeof v.getBoundingBox === 'function')
        return {uid: v.uid, type: v.objectType.name, x: v.x, y: v.y};
      if (Array.isArray(v)) return v.map(c3play.plain);
      try { return JSON.parse(JSON.stringify(v ?? null)); } catch (e) { return String(v); }
    },
  };
  return true;
})()"""

# A js step that failed so: its code never started, the page having reloaded before it.
NOT_STARTED = re.compile(r"ReferenceError: c3(probe|play) is not defined")

# The key, its code and the Windows key code a keyboard event carries.
NAMED_KEYS = {"ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40, "Space": 32, "Enter": 13,
              "Escape": 27, "Tab": 9, "Backspace": 8, "ShiftLeft": 16, "ControlLeft": 17, "AltLeft": 18}


def key_event(name: str) -> dict | None:
    """What Input.dispatchKeyEvent needs for a key named by its code or its character."""
    if name in NAMED_KEYS:
        key = {"Space": " ", "ShiftLeft": "Shift", "ControlLeft": "Control", "AltLeft": "Alt"}.get(name, name)
        return {"key": key, "code": name, "windowsVirtualKeyCode": NAMED_KEYS[name], **({"text": " "} if key == " " else {})}
    char = name[-1] if (name.startswith("Key") or name.startswith("Digit")) and len(name) in (4, 6) else name
    if len(char) == 1 and char.isalnum():
        code = f"Key{char.upper()}" if char.isalpha() else f"Digit{char}"
        return {"key": char.lower(), "code": code, "windowsVirtualKeyCode": ord(char.upper()), "text": char.lower()}
    return None


def statements(line: str) -> bool:
    """Whether a line holds a `;` outside brackets and strings, so more than one statement."""
    depth, quote, escaped = 0, "", False
    for ch in line:
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            return True
    return False


def code(text: str | list[str]) -> str:
    """The body of an async function: a single expression is returned as it is."""
    body = "\n".join(text) if isinstance(text, list) else text
    one = body.strip().rstrip(";")
    if "\n" not in one and not statements(one) and \
            not one.startswith(("return ", "return;", "const ", "let ", "var ", "if ", "for ", "while ", "throw ")):
        return f"return ({one});"
    return body


def scope(text: str | list[str]) -> str:
    """A step's code as an async function of no arguments, with what the code sees."""
    return ("(async () => { const runtime = c3probe.runtime, vars = c3play.vars, wait = c3play.wait;\n"
            f"{code(text)}\n}})")


def check_plan(plan: object) -> tuple[dict, list[str]]:
    """The plan as {viewport, touch, steps}, and what is wrong with it."""
    problems: list[str] = []
    if isinstance(plan, list):
        plan = {"steps": plan}
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        return {}, ['the plan is {"steps": [...]} or a list of steps, with at least one step']
    for extra in set(plan) - {"steps", "viewport", "touch", "keep_saves", "pixel_ratio"}:
        problems.append(f"the plan has {extra!r}; it takes steps, viewport, touch, keep_saves and pixel_ratio")
    view = plan.get("viewport")
    if view is not None and not (isinstance(view, list) and len(view) == 2 and all(isinstance(n, int) and n > 0
                                                                                   for n in view)):
        problems.append("viewport is [width, height] in CSS pixels, such as [430, 932]")
    ratio = plan.get("pixel_ratio", 1)
    if not (isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and 0 < ratio <= 4):
        problems.append("pixel_ratio is device pixels per CSS pixel, a number up to 4, such as 2")
    for n, step in enumerate(plan["steps"], 1):
        kinds = [k for k in STEPS if isinstance(step, dict) and k in step]
        if len(kinds) != 1:
            near = "".join(c3.closest(k, STEPS) for k in step) if isinstance(step, dict) and not kinds else ""
            problems.append(f"step {n} has {'none' if not kinds else ' and '.join(kinds)} of {', '.join(STEPS)}; "
                            f"give one{near}")
            continue
        kind = kinds[0]
        for extra in set(step) - {kind, "note"} - FIELDS[kind]:
            problems.append(f"step {n} ({kind}) has {extra!r}{c3.closest(extra, FIELDS[kind] | {'note'})}")
        value = step[kind]
        if kind in ("tap", "hold", "drag") and not target_ok(value):
            problems.append(f"step {n} ({kind}): the target is a type name, \"Type 2\", \"uid 12\", "
                            f"{{\"x\": .., \"y\": .., \"layer\": ..}} or {{\"js\": ..}}")
        if kind == "drag" and not target_ok(step.get("to")):
            problems.append(f"step {n} (drag) needs \"to\", a target like the one it drags")
        if kind == "drag" and "through" in step and not (isinstance(step["through"], list) and step["through"]
                                                         and all(map(target_ok, step["through"]))):
            problems.append(f"step {n} (drag): through is a list of targets like the one it drags")
        if kind == "key" and (not isinstance(value, str) or not key_event(value)):
            problems.append(f"step {n} (key): {value!r} is no key this script presses; use a letter (a or KeyA), "
                            f"a digit (1 or Digit1) or one of {', '.join(NAMED_KEYS)}")
        if kind == "wait" and not (isinstance(value, (int, float)) and value >= 0):
            problems.append(f"step {n} (wait) takes seconds, a number")
        if kind in ("until", "js") and not (isinstance(value, str) or isinstance(value, list) and value
                                            and all(isinstance(v, str) for v in value)):
            problems.append(f"step {n} ({kind}) takes JavaScript, a string or a list of lines")
        if kind == "state" and not (isinstance(value, list) and all(isinstance(v, str) for v in value)
                                    or isinstance(value, str)):
            problems.append(f"step {n} (state) takes the object types to list, [] for counts only")
        if kind in ("shot", "record") and not (isinstance(value, str) and value
                                               and all(c.isalnum() or c in "-_" for c in value)
                                               or kind == "record" and value is False):
            problems.append(f"step {n} ({kind}) takes a file name of letters, digits, - and _"
                            + (", or false to stop" if kind == "record" else ""))
        watch = step.get("watch") if kind == "record" else None
        if watch is not None and not (value and isinstance(watch, dict) and watch and all(
                isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in watch.items())):
            problems.append(f"step {n} (record): watch is {{\"label\": \"EXPRESSION\", ...}} on a step that starts "
                            f"a recording")
        for field in ("seconds", "timeout", "rest"):
            if field in step and not (isinstance(step[field], (int, float)) and step[field] >= 0):
                problems.append(f"step {n} ({kind}): {field} is a number of seconds")
    return plan, problems


def target_ok(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return set(value) == {"js"} and isinstance(value["js"], (str, list)) or \
            {"x", "y"} <= set(value) <= {"x", "y", "layer"} and all(isinstance(value[k], (int, float)) for k in "xy")
    return False


def target_text(value: str | dict) -> str:
    if isinstance(value, str):
        return value
    if "js" in value:
        return "{js}"
    return f"({value['x']}, {value['y']}) on {value.get('layer', 'the first layer')}"


class Game:
    """A running preview: the window's page for input and screenshots, the session
    that runs the game for code."""

    def __init__(self, win: oe.DevTools, live: str | None, touch: bool, size: tuple[int, int], url: str,
                 viewport: list[int] | None, project: Path, ratio: float = 1) -> None:
        self.win, self.live, self.touch, self.size, self.url, self.viewport = win, live, touch, size, url, viewport
        self.project, self.ratio = project, ratio
        self.recording: Recorder | None = None
        self.recorded: list[Recorder] = []      # finished, their connections closed after the window (Recorder)

    def record(self, name: str, video: Path, watch: dict[str, str]) -> None:
        self.recording = Recorder(self.url, name, video, self.viewport, watch, self.project, self.ratio)

    def stop_recording(self) -> str:
        """What the recording that ran made, or "" when none ran."""
        if not self.recording:
            return ""
        recorder, self.recording = self.recording, None
        self.recorded.append(recorder)
        return f"recorded {recorder.name}: {recorder.finish()}"

    def close(self) -> None:
        for recorder in self.recorded:
            recorder.page.ws.close()

    def run(self, js: str, wait: float = 60) -> Any:
        return self.win.evaluate(js, wait=wait, session=self.live)

    def reloaded(self) -> float | None:
        """None while the page the probe was left in still runs. After the game
        reloaded its page (Browser *Reload*), the probe and c3play are left again in
        the new page once its runtime ticks, and the seconds that took are returned.
        Raises StepFailed when no runtime ticks in the new page.
        The answer is also what the errors a step caused arrive before."""
        try:
            if self.run("typeof c3play === 'object'", wait=5):
                return None
        except oe.DevToolsError:    # the page's context or the worker went with the reload
            pass
        began = time.monotonic()
        sessions, live, stalled = oe.attach(self.win, patience=RELOAD)
        if not live:
            raise StepFailed("the page reloaded, and " + ("its runtime did not tick for 3 seconds" if stalled else
                                                          f"no runtime ran in it in {RELOAD} seconds"))
        self.live = live[0]
        self.win.evaluate(PLAY_JS, session=self.live)
        enable(self.win, sessions)
        if self.recording and self.recording.watch:
            self.recording.session = self.recording.game_session()
        return time.monotonic() - began

    def aim(self, target: str | dict) -> tuple[float, float]:
        if isinstance(target, dict) and "js" in target:
            got = self.run(f"(async () => c3play.aim(await {scope(target['js'])}()))()")
        else:
            got = self.run(f"c3play.aim({json.dumps(target)})")
        if not isinstance(got, dict) or "error" in got:
            error = got.get("error") if isinstance(got, dict) else f"the target gave {got!r}"
            if isinstance(got, dict) and got.get("types"):
                error += c3.closest(got["name"], got["types"])
            raise StepFailed(error)
        x, y = got["x"], got["y"]
        if not (0 <= x < self.size[0] and 0 <= y < self.size[1]):
            raise StepFailed(f"{target_text(target)} is at ({x:.0f}, {y:.0f}), outside the window, "
                             f"{self.size[0]}x{self.size[1]}: it is off screen, or the layer scrolled")
        return x, y

    def mouse(self, kind: str, x: float, y: float, down: bool) -> None:
        extra = {"button": "left", "clickCount": 1} if kind != "mouseMoved" else {"button": "left"} if down else {}
        self.win.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, buttons=1 if down else 0, **extra)

    def finger(self, kind: str, x: float = 0, y: float = 0) -> None:
        points = [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]
        self.win.call("Input.dispatchTouchEvent", type=kind, touchPoints=points)

    def press(self, x: float, y: float) -> None:
        if self.touch:
            self.finger("touchStart", x, y)
        else:
            self.mouse("mouseMoved", x, y, False)
            self.mouse("mousePressed", x, y, True)

    def move(self, x: float, y: float) -> None:
        if self.touch:
            self.finger("touchMove", x, y)
        else:
            self.mouse("mouseMoved", x, y, True)

    def release(self, x: float, y: float) -> None:
        if self.touch:
            self.finger("touchEnd")
        else:
            self.mouse("mouseReleased", x, y, False)


class Recorder(threading.Thread):
    """Screenshots of the window, one after another, on a connection of its own while
    the steps run, each with the values the record step watches, read right after it.
    The browser's screencast sends no frame, or a strip, once the window's size is
    emulated. This connection emulates the plan's viewport too, since one without an
    emulated size of its own takes a headed window's screenshots at the display's
    scale; and it stays open until the window closes, since closing a connection
    that emulated a size clears the size for the page, the steps' connection included."""

    def __init__(self, url: str, name: str, video: Path, viewport: list[int] | None, watch: dict[str, str],
                 project: Path, ratio: float = 1) -> None:
        super().__init__(name=name, daemon=True)
        self.video, self.folder, self.project = video, video.with_suffix(""), project
        self.frames, self.steps, self.done, self.first = [], [], threading.Event(), threading.Event()
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir(parents=True)
        self.page = oe.DevTools(url)
        if viewport or ratio != 1:
            emulate(self.page, viewport, ratio)
        self.session, self.watch = None, None
        if watch:
            self.session = self.game_session()
            body = ", ".join(f"[{json.dumps(label)}, await read(async () => ({expression}))]"
                             for label, expression in watch.items())
            self.watch = ("(async () => { const runtime = c3probe.runtime, vars = c3play.vars;\n"
                          "  const read = async f => { try { return c3play.plain(await f()); }"
                          " catch (e) { return `error: ${e.message}`; } };\n"
                          f"  return Object.fromEntries([{body}]); }})()")
        self.start()
        self.first.wait(5)      # the next step starts after the state before it is on record

    def game_session(self) -> str | None:
        """The page or the worker where the probe was left: the same globals as the
        steps see, through this connection."""
        self.page.call("Target.setAutoAttach", autoAttach=True, waitForDebuggerOnStart=False, flatten=True)
        workers = [e["params"]["sessionId"] for e in self.page.events if e["method"] == "Target.attachedToTarget"
                   and e["params"]["targetInfo"]["type"] == "worker"]
        for session in [None, *workers]:
            try:
                if self.page.evaluate("typeof c3probe === 'object'", wait=3, session=session):
                    return session
            except oe.DevToolsError:
                pass
        return None

    def run(self) -> None:
        try:
            while not self.done.is_set():
                taken = time.monotonic()
                shot = self.page.call("Page.captureScreenshot", format="jpeg", quality=70, optimizeForSpeed=True)
                frame = {"file": f"{len(self.frames) + 1:04d}.jpg", "t": taken}
                if self.watch:
                    try:
                        frame["watch"] = self.page.evaluate(self.watch, wait=5, session=self.session)
                    except oe.DevToolsError as e:
                        frame["watch"] = {"error": str(e).splitlines()[0]}
                (self.folder / frame["file"]).write_bytes(base64.b64decode(shot["data"]))
                self.frames.append(frame)
                self.first.set()
        except (oe.DevToolsError, OSError):     # the window closed
            return

    def finish(self) -> str:
        """Stop, and leave the frames, the timeline, a video and the review page: what
        to print about them."""
        self.done.set()
        self.join(10)
        frames = self.frames
        if not frames:
            return f"no frames: the window answered no screenshot; {self.folder} is empty"
        start = frames[0]["t"]
        seconds = [max(b["t"] - a["t"], 0.001) for a, b in zip(frames, frames[1:])] + [0.05]
        made = make_video([self.folder / f["file"] for f in frames], seconds, self.video)
        timeline = {"name": self.name, "folder": self.folder.name, "path": self.folder.resolve().as_posix(),
                    "project": self.project.resolve().as_posix(), "video": made,
                    "frames": [{**f, "t": round(f["t"] - start, 3)} for f in frames],
                    "steps": [{**s, "start": round(s["start"] - start, 3), "end": round(s["end"] - start, 3)}
                              for s in self.steps]}
        (self.folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")
        page = self.video.with_suffix(".html")
        page.write_text(REVIEW.replace("/*TIMELINE*/null", script_json(timeline)), encoding="utf-8")
        index = write_index(self.video.parent)
        lines = [f"{len(frames)} frames in {sum(seconds):.1f} s, {made or 'no ffmpeg or Pillow here to join them'}"]
        paths = [self.folder / f["file"] for f in frames]
        cells = sheet_frames(timeline["frames"], timeline["steps"], frame_change(paths, timeline["frames"]))
        sheet = make_sheet([paths[i] for i, _ in cells], [timeline["frames"][i]["t"] for i, _ in cells],
                           self.folder.with_name(self.folder.name + "-sheet.png"))
        if sheet:
            listed = ", ".join(f"{k} at {round(timeline['frames'][i]['t'] * 1000)} ms" + (f" ({why})" if why else "")
                               for k, (i, why) in enumerate(cells, 1))
            lines += [f"sheet {sheet}: {len(cells)} frames, numbered left to right, top down: {listed}",
                      "  judge the motion from the sheet, not from what the events meant to do: open it with the image "
                      "tool, name the three worst defects, each with its time, what the frame shows and the event to "
                      "change, fix only those, and record that part again"]
        lines += [f"review {page}: the user plays it there, selects the part that looks wrong and copies it to you "
                  f"as a task; {index} lists every recording",
                  f"frames and timeline.json in {self.folder}"]
        return "\n    ".join(lines + watch_lines(timeline["frames"]))


def script_json(value: object) -> str:
    """JSON to put in the page's script, with no </script> inside it."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def write_index(shots: Path) -> Path:
    """index.html in the shots folder: every recording there with its review page, the
    newest first, so the user opens one from a page instead of a folder chooser."""
    found = []
    for timeline in shots.glob("*/timeline.json"):
        page = timeline.parent.with_suffix(".html")
        try:
            data = json.loads(timeline.read_text(encoding="utf-8"))
            frames, steps, when = data["frames"], data.get("steps", []), timeline.stat().st_mtime
        except (OSError, ValueError, KeyError, TypeError):     # a folder that is not a recording
            continue
        if not page.exists():
            continue
        found.append((when, {"name": timeline.parent.name, "page": page.name, "project": data.get("project"),
                             "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(when)), "frames": len(frames),
                             "seconds": frames[-1]["t"] if frames else 0, "steps": len(steps),
                             "failed": sum(not s.get("ok", True) for s in steps),
                             "errors": sum(len(s.get("errors", [])) for s in steps)}))
    index = shots / "index.html"
    recordings = [r for _, r in sorted(found, key=lambda pair: pair[0], reverse=True)]
    index.write_text(REVIEW.replace("/*RECORDINGS*/null", script_json(recordings)), encoding="utf-8")
    return index


def watch_lines(frames: list[dict]) -> list[str]:
    """How each watched value changed over the recording, at most eight changes each."""
    lines = []
    for name in frames[0].get("watch") or {}:
        changes, last = [], object()
        for f in frames:
            value = json.dumps((f.get("watch") or {}).get(name), ensure_ascii=False)
            if value != last:
                changes.append(f"{value if len(value) <= 40 else value[:37] + '...'} at {round(f['t'] * 1000)} ms")
                last = value
        more = f", and {len(changes) - 8} more in timeline.json" if len(changes) > 8 else ""
        lines.append(f"watch {name}: " + ", ".join(changes[:8]) + more)
    return lines


def make_video(frames: list[Path], seconds: list[float], video: Path) -> str | None:
    """An .mp4 through ffmpeg where it is installed, else a .gif through Pillow; None
    with neither. Each frame stays up for as long as the window showed it."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        listing = video.with_suffix(".txt")
        lines = ["ffconcat version 1.0"]
        for frame, s in zip(frames, seconds):
            lines += [f"file '{frame.resolve().as_posix()}'", f"duration {s:.4f}"]
        lines.append(f"file '{frames[-1].resolve().as_posix()}'")     # concat drops the last duration otherwise
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        mp4 = video.with_suffix(".mp4")
        done = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                               "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p", "-r", "30", str(mp4)],
                              capture_output=True, text=True, timeout=120)
        listing.unlink(missing_ok=True)
        if done.returncode == 0:
            return str(mp4)
    try:
        from PIL import Image
    except ImportError:
        return None
    gif = video.with_suffix(".gif")
    images = [Image.open(f) for f in frames]
    images[0].save(gif, save_all=True, append_images=images[1:], loop=0,
                   duration=[max(20, round(s * 1000)) for s in seconds])
    return str(gif)


SHEET_CELLS, SHEET_SIDE, SHEET_GAP = 12, 1600, 4


def frame_change(paths: list[Path], frames: list[dict]) -> list[float]:
    """How much each frame differs from the one before it, 0 for the first: the mean
    difference of small grey copies with Pillow, else the watched numbers' changes,
    each over its own range; all 0 when neither tells."""
    try:
        from PIL import Image, ImageChops, ImageStat
        if not paths or len(paths) != len(frames):
            raise OSError("no frame for each time")
        small = []
        for p in paths:
            with Image.open(p) as image:
                image.draft("L", (64, 64))
                small.append(image.convert("L").resize((64, 64)))
        return [0.0] + [ImageStat.Stat(ImageChops.difference(a, b)).mean[0] for a, b in zip(small, small[1:])]
    except (ImportError, OSError):
        pass
    numbers: dict[str, list[float | None]] = {}
    for f in frames:
        for name, value in (f.get("watch") or {}).items():
            numbers.setdefault(name, [])
    for name, values in numbers.items():
        for f in frames:
            value = (f.get("watch") or {}).get(name)
            values.append(value if isinstance(value, (int, float)) and not isinstance(value, bool) else None)
    change = [0.0] * len(frames)
    for values in numbers.values():
        known = [v for v in values if v is not None]
        span = (max(known) - min(known)) if known else 0
        if not span:
            continue
        for i in range(1, len(values)):
            if values[i] is not None and values[i - 1] is not None:
                change[i] += abs(values[i] - values[i - 1]) / span
    return change


def sheet_frames(frames: list[dict], steps: list[dict], change: list[float]) -> list[tuple[int, str]]:
    """The frames of a recording's contact sheet, in order, each with why it is there:
    the first and the last, the frames around the largest change, then the start and end
    of each step, thinned evenly to fit; the cells left over go where the picture changes
    most, so a motion between two steps is on the sheet too."""
    if not frames:
        return []
    times = [f["t"] for f in frames]

    def nearest(t: float) -> int:
        return min(range(len(times)), key=lambda i: abs(times[i] - t))

    kept = {0: "start", len(frames) - 1: "end"}
    peak = max(range(len(change)), key=change.__getitem__) if change and max(change) > 0 else None
    if peak is not None:
        for i in (peak - 1, peak + 1):
            if 0 <= i < len(frames):
                kept.setdefault(i, "")
        kept[peak] = "largest change"
    rest: dict[int, str] = {}
    for s in steps:
        rest.setdefault(nearest(s["start"]), f"step {s['step']} starts")
        rest.setdefault(nearest(s["end"]), f"step {s['step']} ends")
    rest = {i: why for i, why in rest.items() if i not in kept}
    room = SHEET_CELLS - len(kept)
    chosen = sorted(rest)
    if len(chosen) > room:
        chosen = [chosen[round(k * (len(chosen) - 1) / max(room - 1, 1))] for k in range(room)] if room > 0 else []
    kept |= {i: rest[i] for i in chosen}
    spare = min(SHEET_CELLS, len(frames)) - len(kept)
    if spare > 0:       # spread over the change, so the frames fall where the picture moves
        total, run = sum(change), []
        for c in change:
            run.append((run[-1] if run else 0) + c)
        for k in range(spare):
            share = (k + 0.5) / spare
            kept.setdefault(next(j for j, r in enumerate(run) if r >= share * total) if total
                            else round(share * (len(frames) - 1)), "")
    return sorted(kept.items())


def make_sheet(paths: list[Path], times: list[float], out: Path) -> str | None:
    """The frames side by side in one image of at most SHEET_SIDE pixels a side, each
    numbered with its time: with Pillow, else unnumbered with ffmpeg; None with neither."""
    if not paths:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        Image = None
    if Image:
        with Image.open(paths[0]) as first:
            w, h = first.size
    else:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe or not shutil.which("ffmpeg"):
            return None
        probe = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                "-of", "csv=p=0", str(paths[0])], capture_output=True, text=True, timeout=60)
        try:
            w, h = (int(v) for v in probe.stdout.strip().split(","))
        except ValueError:
            return None
    n = len(paths)

    def scale(cols: int) -> float:
        rows = math.ceil(n / cols)
        return min(1.0, (SHEET_SIDE - SHEET_GAP * (cols + 1)) / (cols * w), (SHEET_SIDE - SHEET_GAP * (rows + 1)) / (rows * h))

    cols = max(range(1, n + 1), key=scale)
    rows, s = math.ceil(n / cols), scale(cols)
    cw, ch = max(2, int(w * s) // 2 * 2), max(2, int(h * s) // 2 * 2)
    if Image:
        sheet = Image.new("RGB", (cols * cw + (cols + 1) * SHEET_GAP, rows * ch + (rows + 1) * SHEET_GAP), (34, 34, 34))
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.load_default(size=max(12, min(cw, ch) // 16))
        except TypeError:       # Pillow before 10.1 has one size
            font = ImageFont.load_default()
        for k, (p, t) in enumerate(zip(paths, times)):
            x, y = SHEET_GAP + (k % cols) * (cw + SHEET_GAP), SHEET_GAP + (k // cols) * (ch + SHEET_GAP)
            with Image.open(p) as frame:
                sheet.paste(frame.convert("RGB").resize((cw, ch)), (x, y))
            label = f"{k + 1}  {round(t * 1000)} ms"
            box = draw.textbbox((x + 4, y + 4), label, font=font)
            draw.rectangle((box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3), fill=(0, 0, 0))
            draw.text((x + 4, y + 4), label, fill=(255, 255, 255), font=font)
        sheet.save(out)
        return str(out)
    listing = out.with_suffix(".txt")
    listing.write_text("ffconcat version 1.0\n" + "".join(f"file '{p.resolve().as_posix()}'\n" for p in paths),
                       encoding="utf-8")
    g = SHEET_GAP
    done = subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                           "-i", str(listing), "-vf", f"scale={cw}:{ch},tile={cols}x{rows}:padding={g}:margin={g}"
                           ":color=0x222222", "-frames:v", "1", str(out)], capture_output=True, text=True, timeout=120)
    listing.unlink(missing_ok=True)
    return str(out) if done.returncode == 0 and out.exists() else None


def emulate(page: oe.DevTools, viewport: list[int] | None, ratio: float = 1) -> tuple[int, int] | None:
    """Give the window the plan's viewport and pixel ratio, and the size the page then
    reports, None when it answered nothing; without a viewport the window keeps its
    own size. The browser answers before the page has resized, by as much as 0.4 s:
    a size read at once can be the window's own while the runtime already places its
    layers in the viewport."""
    width, height = viewport or (0, 0)     # 0 keeps the window's own
    page.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=ratio,
              mobile=False)
    size, scale, end = None, None, time.monotonic() + RESIZE
    while time.monotonic() < end:
        try:
            got = page.evaluate("[innerWidth, innerHeight, devicePixelRatio]")
            size, scale = tuple(got[:2]), got[2]
        except oe.DevToolsError:    # the preview page replaced its document while loading
            pass
        if scale == ratio and (not viewport or size == tuple(viewport)):
            break
        time.sleep(0.05)
    return size


def path(points: list[tuple[float, float]], seconds: float) -> list[tuple[float, float, float]]:
    """The moves of a drag through `points`, each (seconds before it, x, y): every
    0.03 s and at least 8 a leg, each leg given time in proportion to its length."""
    legs = list(zip(points, points[1:]))
    lengths = [math.dist(a, b) for a, b in legs]
    moves = []
    for ((x1, y1), (x2, y2)), length in zip(legs, lengths):
        share = seconds * (length / sum(lengths) if sum(lengths) else 1 / len(legs))
        count = max(8, round(share / 0.03))
        moves += [(share / count, x1 + (x2 - x1) * k / count, y1 + (y2 - y1) * k / count) for k in range(1, count + 1)]
    return moves


class StepFailed(Exception):
    pass


def step_line(n: int, step: dict) -> str:
    kind = next(k for k in STEPS if k in step)
    value = step[kind]
    what = {"tap": lambda: target_text(value), "hold": lambda: target_text(value),
            "drag": lambda: " through ".join(map(target_text, [value, *step.get("through", [])]))
            + f" to {target_text(step['to'])}", "key": lambda: value,
            "wait": lambda: f"{value:g} s", "until": lambda: one_line(value), "js": lambda: one_line(value),
            "state": lambda: " ".join([value] if isinstance(value, str) else value) or "counts",
            "shot": lambda: value, "record": lambda: value or "stop"}[kind]()
    note = f" ({step['note']})" if step.get("note") else ""
    return f"{n} {kind} {what}{note}"


def one_line(text: str | list[str]) -> str:
    text = " ".join(t.strip() for t in text) if isinstance(text, list) else " ".join(text.split())
    return text if len(text) <= 80 else text[:77] + "..."


def do_step(game: Game, step: dict, n: int, shots: Path) -> tuple[str, dict | None]:
    """Run one step; what to print after its line, and what it read: {"value"} or {"state"}."""
    kind = next(k for k in STEPS if k in step)
    value = step[kind]
    if kind == "wait":
        time.sleep(value)
        return "ok", None
    if kind == "tap":
        x, y = game.aim(value)
        game.press(x, y)
        time.sleep(0.05)
        game.release(x, y)
        return f"at ({x:.0f}, {y:.0f})", None
    if kind == "hold":
        x, y = game.aim(value)
        seconds = step.get("seconds", PRESS["hold"])
        game.press(x, y)
        time.sleep(seconds)
        game.release(x, y)
        return f"at ({x:.0f}, {y:.0f}) for {seconds:g} s", None
    if kind == "drag":
        points = [game.aim(t) for t in [value, *step.get("through", []), step["to"]]]
        seconds, rest = step.get("seconds", PRESS["drag"]), step.get("rest", 0.05)
        game.press(*points[0])
        for delay, x, y in path(points, seconds):
            time.sleep(delay)
            game.move(x, y)
        time.sleep(rest)
        game.release(*points[-1])
        where = " through ".join(f"({x:.0f}, {y:.0f})" for x, y in points[:-1])
        moving = ", released moving" if rest == 0 else ""
        return f"{where} to ({points[-1][0]:.0f}, {points[-1][1]:.0f}) in {seconds:g} s{moving}", None
    if kind == "key":
        event, seconds = key_event(value), step.get("seconds", PRESS["key"])
        down = "keyDown" if "text" in event else "rawKeyDown"
        game.win.call("Input.dispatchKeyEvent", type=down, **event)
        time.sleep(seconds)
        game.win.call("Input.dispatchKeyEvent", type="keyUp", **{k: v for k, v in event.items() if k != "text"})
        return f"held {seconds:g} s", None
    if kind == "until":
        timeout = step.get("timeout", 10)
        got = game.run(f"""(async () => {{ const test = {scope(value)}, t0 = performance.now();
          for (;;) {{ if (await test()) return (performance.now() - t0) / 1000;
            if (performance.now() - t0 > {timeout * 1000}) return null; await c3play.wait(0.05); }} }})()""",
                       wait=timeout + 10)
        if got is None:
            raise StepFailed(f"still false after {timeout:g} s")
        return f"true after {got:.1f} s", None
    if kind == "js":
        got = game.run(f"(async () => c3play.plain(await {scope(value)}()))()", wait=step.get("timeout", 60))
        text = json.dumps(got, ensure_ascii=False)
        return text if len(text) <= 1500 else text[:1500] + " ... (--out keeps it all)", {"value": got}
    if kind == "state":
        names = [value] if isinstance(value, str) else value
        read = oe.read_state(game.win, game.live, names)
        if "error" in read:
            raise StepFailed(read["error"].splitlines()[0])
        return "", {"state": read}
    if kind == "record":
        said = game.stop_recording()
        if value:
            game.record(value, shots / f"{n:02d}-{value}", step.get("watch") or {})
        return "; ".join(filter(None, ["recording" if value else "", said])), None
    return screenshot(game, shots / f"{n:02d}-{value}.png"), None


def screenshot(game: Game, path: Path) -> str:
    path.write_bytes(base64.b64decode(game.win.call("Page.captureScreenshot")["data"]))
    return str(path)


def play(plan: dict, shots: Path, project: Path) -> Callable[[oe.Browser, str, oe.DevTools], dict]:
    """The `then` of open_in_editor.open_one: preview the project and run the plan."""
    def run(browser: oe.Browser, target: str, page: oe.DevTools) -> dict:
        if not plan.get("keep_saves"):     # a game reads its save on start, so the profile's would carry over
            page.call("Storage.clearDataForOrigin", origin=PREVIEW, storageTypes="local_storage,indexeddb")
        started = oe.start_preview(browser, target, page)
        if isinstance(started, list):
            return {"started": False, "layout": None, "runtime": None, "errors": started, "steps": []}
        window, win = started
        touch, view, ratio = bool(plan.get("touch")), plan.get("viewport"), plan.get("pixel_ratio", 1)
        game = None
        try:
            if view or ratio != 1:
                size = emulate(win, view, ratio)
                if view and size != tuple(view):
                    return {"started": False, "layout": None, "runtime": None, "steps": [], "errors": [
                        f"the preview window did not take the viewport {view[0]}x{view[1]} in {RESIZE} seconds; "
                        f"it reports {'nothing' if size is None else f'{size[0]}x{size[1]}'}"]}
            if not view:
                size = tuple(win.evaluate("[innerWidth, innerHeight]"))     # a headed window loses its frame's share
            if touch:
                win.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
            sessions, live, stalled = oe.attach(win, patience=30)
            if not live:
                return {"started": False, "layout": None, "runtime": None, "steps": [], "errors": [
                    "the runtime loaded but did not tick for 3 seconds" if stalled
                    else "the preview window opened but no runtime was found in it in 30 seconds"]}
            win.evaluate(PLAY_JS, session=live[0])
            enable(win, sessions)
            win.evaluate("0")
            before = oe.runtime_errors(win)
            game = Game(win, live[0], touch, size, f"ws://127.0.0.1:{browser.port}/devtools/page/{window['targetId']}",
                        view, project, ratio)
            began = time.monotonic()
            steps = play_steps(game, plan["steps"], shots)
            seconds = time.monotonic() - began
            recorded = game.stop_recording()
            try:
                layout = win.evaluate("c3probe.snapshot([], 0)", wait=6, session=game.live)["layout"]
            except oe.DevToolsError:    # the last step left the page reloading
                layout = None
        finally:
            win.ws.close()
            browser.devtools.call("Target.closeTarget", targetId=window["targetId"])
            if game:
                game.close()
        return {"started": True, "layout": layout, "runtime": "worker" if game.live else "page",
                "seconds": round(seconds, 1), "viewport": list(size), "pixel_ratio": ratio, "touch": touch,
                "errors": before, "steps": steps, "planned": len(plan["steps"]), "recorded": recorded}
    return run


def enable(win: oe.DevTools, sessions: list[str | None]) -> None:
    """Have the page and each worker hand over the errors they log."""
    for s in sessions:
        try:
            win.call("Runtime.enable", session=s)
        except oe.DevToolsError:    # a worker that ended since
            pass


def play_steps(game: Game, steps: list[dict], shots: Path) -> list[dict]:
    """Run the steps in order until one fails: what each said, read and caused.

    A game that reloads its page loses the probe with it. After each step the
    probe is looked for, and left again in the new page; the step's `reloaded`
    lists the seconds the game took to start again. A step the reload broke
    off runs again in the new page, except a js step whose code had started:
    it may have done part of its work, so it fails."""
    played: list[dict] = []
    for n, step in enumerate(steps, 1):
        started_at = time.monotonic()
        ok, said, extra = attempt(game, step, n, shots)
        reloads: list[float] = []
        try:
            back = game.reloaded()
            if back is not None:
                reloads.append(back)
                if ok:
                    said += f"; then the page reloaded, and the game started again {back:.1f} s later"
                elif "js" not in step or NOT_STARTED.search(said):
                    ok, said, extra = attempt(game, step, n, shots)
                    said = f"the page reloaded during the step, so it ran again {back:.1f} s later: {said}"
                    back = game.reloaded()
                    if back is not None:
                        reloads.append(back)
                        said += f"; then the page reloaded again, and the game started {back:.1f} s later"
                else:
                    said += "; the page reloaded while the code ran, so the step did not run again"
        except StepFailed as e:     # the reloaded page ran no game
            ok, said = False, f"{said}; {e}"
        done = {"step": n, "line": step_line(n, step), "ok": ok, "said": said, **extra}
        if reloads:
            done["reloaded"] = [round(s, 1) for s in reloads]
        if not ok:
            try:
                done["said"] += f"; the window then: {screenshot(game, shots / f'{n:02d}-failed.png')}"
            except oe.DevToolsError:
                pass
        done["errors"] = oe.runtime_errors(game.win)    # they arrived before reloaded() was answered
        played.append(done)
        if game.recording:      # its timeline places the step
            game.recording.steps.append({k: done[k] for k in ("step", "line", "ok", "said", "errors")}
                                        | {"start": started_at, "end": time.monotonic()})
        if not ok:
            break
    return played


def attempt(game: Game, step: dict, n: int, shots: Path) -> tuple[bool, str, dict]:
    """Run one step: whether it ran, what to print after its line, and what it read."""
    try:
        said, extra = do_step(game, step, n, shots)
        return True, said, extra or {}
    except (StepFailed, oe.DevToolsError) as e:     # the code threw, or the page stopped answering
        return False, str(e).splitlines()[0], {}


def report(result: dict, label: Callable[[str], str] = oe.key_name) -> list[str]:
    if result["status"] != "opened":
        return oe.report(result, label)
    lines = [f"opened   {result['project']}  ({result['title']}, {result['editor']})"]
    lines += [f"  warning: {w}" for w in result.get("warnings", [])]
    ran = result.get("preview")
    if not ran or not ran["started"]:
        return lines + [f"  preview did not run: {e}" for e in (ran or {}).get("errors", ["no preview"])]
    touch = ", touch" if ran["touch"] else ""
    ratio = f" at pixel ratio {ran['pixel_ratio']:g}" if ran.get("pixel_ratio", 1) != 1 else ""
    lines.append(f"  preview: layout {ran['layout']!r} at the end, runtime in the {ran['runtime']}, "
                 f"viewport {ran['viewport'][0]}x{ran['viewport'][1]}{ratio}{touch}")
    lines += oe.runtime_lines(ran["errors"])
    for done in ran["steps"]:
        said = f": {done['said']}" if done["said"] else ""
        lines.append(f"  {done['line']}{said}" if done["ok"] else f"  {done['line']}: FAILED, {done['said']}")
        if "state" in done:
            lines += ["  " + line for line in oe.state_lines(done["state"], label)]
        lines += oe.runtime_lines(done["errors"], "    ")
    if ran.get("recorded"):
        lines.append(f"  {ran['recorded']}")
    errors = len(ran["errors"]) + sum(len(d["errors"]) for d in ran["steps"])
    ok = sum(d["ok"] for d in ran["steps"])
    lines.append(f"  ran: {ok} of {ran['planned']} steps in {ran['seconds']:.1f} s, "
                 f"{errors or 'no'} runtime error{'' if errors == 1 else 's'}")
    return lines


def kept(out: Path | None, shots: Path | None, project: Path) -> tuple[Path, Path]:
    return oe.kept(out, shots, project, "preview-project.json", "preview")


def where(out: Path, shots: Path) -> str:
    return f"full result in {out}, screenshots in {shots}"


def kept_plans(project: Path) -> list[Path]:
    folder = project / KEPT
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def keep(plan: Path, project: Path, name: str) -> Path:
    """The plan copied as it was written into the project's kept plans."""
    to = project / KEPT / f"{name}.json"
    to.parent.mkdir(parents=True, exist_ok=True)
    to.write_bytes(plan.read_bytes())
    return to


def play_all(plans: dict[str, dict], shots: Path, project: Path) -> Callable[[oe.Browser, str, oe.DevTools], dict]:
    """The `then` of open_in_editor.open_one: each plan previews the game afresh, in one editor session."""
    def run(browser: oe.Browser, target: str, page: oe.DevTools) -> dict:
        ran = {}
        for name, plan in plans.items():
            (shots / name).mkdir(parents=True, exist_ok=True)
            ran[name] = play(plan, shots / name, project)(browser, target, page)
        return {"started": True, "plans": ran}
    return run


def replay_report(result: dict, refused: dict[str, list[str]],
                  label: Callable[[str], str] = oe.key_name) -> tuple[list[str], int]:
    """One line per kept plan, ok or FAIL with the step that failed or the first runtime error, and how many
    failed."""
    if result["status"] != "opened":
        return oe.report(result, label), len(refused) + 1
    lines = [f"opened   {result['project']}  ({result['title']}, {result['editor']})"]
    lines += [f"  warning: {w}" for w in result.get("warnings", [])]
    ran = (result.get("preview") or {}).get("plans", {})
    failed, errors = 0, 0
    for name in sorted(set(ran) | set(refused)):
        where = (KEPT / f"{name}.json").as_posix()
        if name in refused:
            failed += 1
            lines.append(f"  FAIL  {name} ({where}): the plan is refused: {'; '.join(refused[name])}")
            continue
        done = ran[name]
        if not done["started"]:
            failed += 1
            lines.append(f"  FAIL  {name} ({where}): the preview did not run: {'; '.join(done['errors'])}")
            continue
        raw = done["errors"] + [e for d in done["steps"] for e in d["errors"]]
        logged = oe.runtime_lines(raw, "    ")
        errors += len(raw)
        bad = next((d for d in done["steps"] if not d["ok"]), None)
        if bad or logged or len(done["steps"]) < done["planned"]:
            failed += 1
            why = (f"{bad['line']}: FAILED, {bad['said']}" if bad else logged[0].strip() if logged
                   else f"stopped after {len(done['steps'])} of {done['planned']} steps")
            lines.append(f"  FAIL  {name} ({where}): {why}")
            lines += logged[1 if not bad else 0:][:3]
        else:
            lines.append(f"  ok    {name}: {done['planned']} step{'s' if done['planned'] != 1 else ''} in "
                         f"{done['seconds']:.1f} s")
    total = len(ran) + len(refused)
    lines.append(f"  replayed: {total - failed} of {total} kept plans pass, {errors or 'no'} runtime "
                 f"error{'' if errors == 1 else 's'}")
    return lines, failed


def replay(args: argparse.Namespace, project: Path, exe: str, editor: str) -> int:
    """--all: every kept plan, one editor session."""
    plans, refused = {}, {}
    for path in kept_plans(project):
        try:
            plan, problems = check_plan(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            plan, problems = {}, [str(e)]
        if problems:
            refused[path.stem] = problems
        else:
            plans[path.stem] = plan
    if not plans and not refused:
        print(f"no kept plan in {project / KEPT}: when a plan passes, run it again with --keep NAME to keep it there",
              file=sys.stderr)
        return 2
    out, shots = oe.kept(args.out, args.shots, project, "preview-plans.json", "preview-plans")
    shots.mkdir(parents=True, exist_ok=True)
    if plans:
        try:
            browser = oe.Browser(exe, (args.profile or oe.scratch(project)) / f"editor-{Path(exe).stem.lower()}",
                                 args.headed)
        except (oe.DevToolsError, OSError) as e:
            print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
            return 2
        try:
            result = oe.open_one(browser, editor, project, browser.profile / "project-play.c3p", None,
                                 bool(args.release), play_all(plans, shots, project))
        except oe.EditorNotLoaded as e:
            print(f"the editor did not load: {e}. Check the network connection and --release, and run again.",
                  file=sys.stderr)
            return 2
        except (oe.DevToolsError, OSError) as e:
            print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
            return 2
        finally:
            browser.close()
    else:
        result = {"status": "opened", "project": str(project), "title": "not opened: every kept plan is refused",
                  "editor": "-", "preview": {"plans": {}}}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    lines, failed = replay_report(result, refused)
    shown = c3.fitting(lines, args.limit)
    print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"{len(lines) - shown} lines not printed: {out} keeps everything, --limit 0 prints it")
    print(where(out, shots))
    if result["status"] != "opened":
        print(oe.NEXT)
    elif failed:
        print("next: a kept plan passed when the change it checks was made, so one that fails now names what a later "
              "change broke. Read its failing step and the events that step reads, fix the events, not the plan, and "
              "run --all again. Change a kept plan only when the game was meant to change what it checks.")
    return 1 if failed or result["status"] != "opened" else 0


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path, nargs="?", metavar="PLAN.json",
                    help="the steps to play, as described above (none with --all)")
    ap.add_argument("--keep", metavar="NAME",
                    help="when every step passes, keep the plan as tools/plans/NAME.json in the project, to commit "
                         "with the change it checks; NAME is letters, digits, - and _")
    ap.add_argument("--all", action="store_true",
                    help="replay every plan kept in tools/plans of the project, each from a first launch, and name "
                         "each one that fails")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--release", metavar="rNNN", help="open in this release of the editor, as open_in_editor.py does")
    ap.add_argument("--browser", metavar="EXE",
                    help="the Chromium-based browser to start (default: Edge, Chrome or Chromium where installed)")
    ap.add_argument("--shots", type=Path, help="the folder for the screenshots (default: .tmp/preview in the project)")
    ap.add_argument("--out", type=Path, help="write the result, every value and state included, as JSON "
                                             "(default: .tmp/preview-project.json in the project)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--profile", type=Path, metavar="FOLDER",
                    help="keep the browser profile in FOLDER/editor-<browser> instead of the project's .tmp/")
    ap.add_argument("--locale", default="en-US",
                    help="the language pack in data/c3-lang of Construct3-RAG or the plugin that names the inspector "
                         "values; a key the pack lacks keeps its last word (default: en-US)")
    ap.add_argument("--limit", type=int, default=c3.LIMIT, metavar="CHARS",
                    help=f"stop printing after about this many characters; --out keeps everything, 0 prints "
                         f"everything (default: {c3.LIMIT})")
    args = ap.parse_args()

    if bool(args.plan) == args.all:
        ap.error("give a PLAN.json to play, or --all to replay the kept plans")
    if args.keep is not None and (args.all or not re.fullmatch(r"[A-Za-z0-9_-]+", args.keep)):
        ap.error("--keep takes a NAME of letters, digits, - and _, with a PLAN.json")
    if args.all:
        project = c3.find_project(args.project)
        if not project:
            print(f"no project.c3proj found from {args.project or Path.cwd()} upward; run this in the project folder "
                  f"or pass --project <folder>", file=sys.stderr)
            return 2
        exe = args.browser or oe.browser_path()
        if not exe:
            print("no Edge, Chrome or Chromium found here, and replaying the kept plans needs one this script can "
                  "drive: install one, or play each plan in tools/plans with a browser tool of this session.")
            return 3
        return replay(args, project, exe, f"{oe.EDITOR}{args.release.strip('/')}/" if args.release else oe.EDITOR)
    try:
        plan, problems = check_plan(json.loads(args.plan.read_text(encoding="utf-8")))
    except (OSError, ValueError) as e:
        print(f"{args.plan}: {e}. Write the plan as JSON, as --help describes.", file=sys.stderr)
        return 2
    if problems:
        print("\n".join([f"{args.plan}: {p}" for p in problems] + ["See --help for the steps."]), file=sys.stderr)
        return 2
    project = c3.find_project(args.project)
    if not project:
        print(f"no project.c3proj found from {args.project or Path.cwd()} upward; run this in the project folder or "
              f"pass --project <folder>", file=sys.stderr)
        return 2
    label, note = oe.key_name, None
    if any("state" in step for step in plan["steps"]):     # the only step that prints inspector values
        try:
            label, note = oe.labeler(project, args.locale)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
    if note:
        print(note)
    exe = args.browser or oe.browser_path()
    if not exe:
        print("no Edge, Chrome or Chromium found here, and a plan needs one this script can drive: install one, or "
              "drive the preview with a browser tool of this session as references/reading-the-runtime.md says.")
        return 3
    editor = f"{oe.EDITOR}{args.release.strip('/')}/" if args.release else oe.EDITOR
    out, shots = kept(args.out, args.shots, project)
    shots.mkdir(parents=True, exist_ok=True)
    try:
        browser = oe.Browser(exe, (args.profile or oe.scratch(project)) / f"editor-{Path(exe).stem.lower()}", args.headed)
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    try:
        result = oe.open_one(browser, editor, project, browser.profile / "project-play.c3p", None, bool(args.release),
                             play(plan, shots, project))
    except oe.EditorNotLoaded as e:
        print(f"the editor did not load: {e}. Check the network connection and --release, and run again.",
              file=sys.stderr)
        return 2
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    finally:
        browser.close()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = report(result, label)
    shown = c3.fitting(lines, args.limit)
    print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"{len(lines) - shown} lines not printed: {out} keeps everything, --limit 0 prints it")
    print(where(out, shots))
    ran = result.get("preview") or {}
    failed = [d for d in ran.get("steps", []) if not d["ok"]]
    errors = ran.get("started") and (ran["errors"] or any(d["errors"] for d in ran["steps"]))
    if result["status"] != "opened":
        print(oe.NEXT)
    if failed:
        print(f"next: step {failed[0]['step']} failed and the steps after it did not run. A target that is not "
              f"there, or a condition that stays false, is what the events did or did not do: read the state "
              f"(add a state step before it) and the sheet, fix the events or the plan, and run this again.")
    if errors:
        print(oe.NEXT_PREVIEW.replace("run this again with --preview", "run this again"))
    passed = result["status"] == "opened" and ran.get("started") and not failed and not errors
    others = [p for p in kept_plans(project) if args.keep is None or p.stem != args.keep]
    if passed and args.keep:
        print(f"kept: {keep(args.plan, project, args.keep)}; commit it with the change it checks"
              + (f", and replay it with the {len(others)} other kept plan{'s' if len(others) != 1 else ''} after "
                 f"every change: python scripts/preview_project.py --all" if others else
                 "; after every change, replay the kept plans: python scripts/preview_project.py --all"))
    elif args.keep:
        print(f"not kept: only a plan that passes is kept. A plan that checks a bug fails until the fix works: fix "
              f"the events until it passes, then run it again with --keep {args.keep}")
    elif passed:
        print("keep: this plan passes; keep it as a check of this change with --keep NAME, and replay every kept plan "
              "after the next change with --all" + (f" ({len(others)} kept)" if others else ""))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
