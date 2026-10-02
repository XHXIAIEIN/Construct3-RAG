"""Preview a project in the Construct 3 editor and play it from a plan: tap, hold
and drag the game's own instances, press keys, wait for what the events do, run
scripts against the runtime, and read the state, take screenshots and record between steps.

    python scripts/preview_project.py PLAN.json [--project FOLDER] [--release rNNN] [--browser EXE]
                                      [--shots DIR] [--out RESULT.json] [--headed] [--profile FOLDER]

Use it to check what a player does: a merge, a drop, a jump, a purchase. The
plan is JSON, the steps run in order, and a step that fails stops the run:

  {"viewport": [430, 932], "touch": true,
   "steps": [
     {"until": "runtime.objects.Enemy.getAllInstances().length >= 3", "timeout": 10},
     {"js": "runtime.callFunction('finishTutorial')"},
     {"tap": "StartButton"},
     {"drag": "Piece 0", "to": "BattleSlot 1", "seconds": 0.4},
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

Steps, each an object with one of these keys, and "note" for a label:
  tap TARGET                    press and release
  hold TARGET, seconds          press, wait, release (default 0.5 s)
  drag TARGET, to TARGET, seconds   press, move in steps, release (default 0.4 s)
  key NAME, seconds             press a key: ArrowLeft, Space, Enter, Escape, KeyA or a, Digit1 or 1
                                (default 0.1 s)
  wait SECONDS                  let the game run
  until EXPRESSION, timeout     wait until the JavaScript expression is true (default 10 s)
  js CODE                       run JavaScript against the runtime and print what it returns
  state [TYPE ...]              the globals, every type's count, the named types' instances
  shot NAME                     a screenshot, NN-NAME.png in --shots
  record NAME, watch            record the window from here to the next record step or the end
                                of the plan, as NN-NAME.mp4 with ffmpeg, NN-NAME.gif with Pillow,
                                and always the frames, NN-NAME/0001.jpg ...; false stops it.
                                watch is {"label": EXPRESSION, ...}, read at every frame. The
                                recording leaves NN-NAME.html to review it: the frames, the steps
                                that ran and the watched values, frame by frame, and a part
                                selected there copied as a task for an agent; and
                                NN-NAME/timeline.json with the same

TARGET is where to press, the middle of an instance's bounding box:
  "Button"                      the first instance of an object type, as the project spells it
  "Piece 2"                     its instance of index 2, in creation order
  "uid 12"                      an instance by UID
  {"x": 40, "y": 600, "layer": "UI"}   a position on a layer (default: the layout's first layer)
  {"js": "CODE"}                JavaScript that returns an instance, a UID, or {x, y, layer}

CODE and EXPRESSION see `runtime`, the scripting API (IRuntime), `vars`, an object
kept from step to step, and `wait(seconds)`. A single expression is returned as it
is; longer code says `return`. A list of strings is joined into lines.

The game starts on the layout the editor opens on, as with F5. The browser runs
headless and silent; --headed shows it. A step that fails leaves a screenshot,
NN-failed.png. Screenshots and recordings go to --shots, by default
.tmp/preview/ in the project, and the whole result, every value and state, to
--out, by default .tmp/preview-project.json; .tmp/ is ignored by Git. The last
line names both: read a cut-off result there instead of playing the plan again.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import c3project as c3
import open_in_editor as oe

EPILOG = """examples:
  python scripts/preview_project.py .tmp/merge-plan.json
  python scripts/preview_project.py plan.json --project "D:/Games/Merge" --headed

output:
  opened   <project>  (<window title>, <the editor it opened in>)
    warning: <a notice the editor showed over the opened project, as open_in_editor.py prints it>
    preview: layout 'Game', runtime in the worker, viewport 430x932, touch
    1 until runtime.objects.Enemy.getAllInstances().length >= 3: true after 1.4 s
    2 drag Piece 0 to BattleSlot 1: (120, 712) to (215, 388) in 0.4 s
      runtime: <an error the game logged during the step, with its event>
    3 state Piece: <as open_in_editor.py --state prints it>
    4 shot after-merge: .tmp/preview/04-after-merge.png
    recorded merge: 95 frames in 3.4 s, .tmp/preview/02-merge.mp4; frames in .tmp/preview/02-merge
    ran: 4 of 4 steps in 9.6 s, 1 runtime error

exit codes: 0 every step ran and the game logged no error; 1 a step failed, the game logged an error, or
the project did not open; 2 the plan, the project or the editor could not be used; 3 no browser here
"""

STEPS = ("tap", "hold", "drag", "key", "wait", "until", "js", "state", "shot", "record")
FIELDS = {"tap": set(), "hold": {"seconds"}, "drag": {"to", "seconds"}, "key": {"seconds"}, "wait": set(),
          "until": {"timeout"}, "js": {"timeout"}, "state": set(), "shot": set(), "record": {"watch"}}
PRESS = {"hold": 0.5, "drag": 0.4, "key": 0.1}
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


def code(text: str | list[str]) -> str:
    """The body of an async function: a single expression is returned as it is."""
    body = "\n".join(text) if isinstance(text, list) else text
    one = body.strip().rstrip(";")
    if "\n" not in one and ";" not in one and not one.startswith(("return ", "return;", "const ", "let ", "if ")):
        return f"return ({one});"
    return body


def scope(text: str | list[str]) -> str:
    """A step's code as an async function of no arguments, with what the code sees."""
    return ("(async () => { const runtime = c3probe.runtime, vars = c3play.vars, wait = c3play.wait;\n"
            f"{code(text)}\n}})")


def check_plan(plan) -> tuple[dict, list[str]]:
    """The plan as {viewport, touch, steps}, and what is wrong with it."""
    problems: list[str] = []
    if isinstance(plan, list):
        plan = {"steps": plan}
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        return {}, ['the plan is {"steps": [...]} or a list of steps, with at least one step']
    for extra in set(plan) - {"steps", "viewport", "touch", "keep_saves"}:
        problems.append(f"the plan has {extra!r}; it takes steps, viewport, touch and keep_saves")
    view = plan.get("viewport")
    if view is not None and not (isinstance(view, list) and len(view) == 2 and all(isinstance(n, int) and n > 0
                                                                                   for n in view)):
        problems.append("viewport is [width, height] in CSS pixels, such as [430, 932]")
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
        for field in ("seconds", "timeout"):
            if field in step and not (isinstance(step[field], (int, float)) and step[field] >= 0):
                problems.append(f"step {n} ({kind}): {field} is a number of seconds")
    return plan, problems


def target_ok(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return set(value) == {"js"} and isinstance(value["js"], (str, list)) or \
            {"x", "y"} <= set(value) <= {"x", "y", "layer"} and all(isinstance(value[k], (int, float)) for k in "xy")
    return False


def target_text(value) -> str:
    if isinstance(value, str):
        return value
    if "js" in value:
        return "{js}"
    return f"({value['x']}, {value['y']}) on {value.get('layer', 'the first layer')}"


class Game:
    """A running preview: the window's page for input and screenshots, the session
    that runs the game for code."""

    def __init__(self, win: oe.DevTools, live: str | None, touch: bool, size: tuple[int, int], url: str,
                 viewport: list[int] | None, project: Path) -> None:
        self.win, self.live, self.touch, self.size, self.url, self.viewport = win, live, touch, size, url, viewport
        self.project = project
        self.recording: tuple[str, Recorder, Path] | None = None

    def record(self, name: str, video: Path, watch: dict[str, str]) -> None:
        self.recording = (name, Recorder(self.url, video.with_suffix(""), self.viewport, watch, self.project), video)

    def stop_recording(self) -> str:
        """What the recording that ran made, or "" when none ran."""
        if not self.recording:
            return ""
        (name, recorder, video), self.recording = self.recording, None
        return f"recorded {name}: {recorder.finish(name, video)}"

    def run(self, js: str, wait: float = 60):
        return self.win.evaluate(js, wait=wait, session=self.live)

    def aim(self, target) -> tuple[float, float]:
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
    emulated. An emulated size holds for the connection that set it, so this one
    sets the plan's viewport again."""

    def __init__(self, url: str, folder: Path, viewport: list[int] | None, watch: dict[str, str],
                 project: Path) -> None:
        super().__init__(daemon=True)
        self.folder, self.project, self.frames, self.steps, self.done = folder, project, [], [], threading.Event()
        self.first = threading.Event()
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        self.page = oe.DevTools(url)
        if viewport:
            emulate(self.page, viewport)
        self.session, self.watch = None, None
        if watch:
            self.session = self.game_session()
            body = ", ".join(f"[{json.dumps(name)}, await read(async () => ({expression}))]"
                             for name, expression in watch.items())
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

    def finish(self, name: str, video: Path) -> str:
        """Stop, and leave the frames, the timeline, a video and the review page: what
        to print about them."""
        self.done.set()
        self.join(10)
        self.page.ws.close()
        frames = self.frames
        if not frames:
            return f"no frames: the window answered no screenshot; {self.folder} is empty"
        start = frames[0]["t"]
        seconds = [max(b["t"] - a["t"], 0.001) for a, b in zip(frames, frames[1:])] + [0.05]
        made = make_video([self.folder / f["file"] for f in frames], seconds, video)
        timeline = {"name": name, "folder": self.folder.name, "path": self.folder.resolve().as_posix(),
                    "project": self.project.resolve().as_posix(), "video": made,
                    "frames": [{**f, "t": round(f["t"] - start, 3)} for f in frames],
                    "steps": [{**s, "start": round(s["start"] - start, 3), "end": round(s["end"] - start, 3)}
                              for s in self.steps]}
        (self.folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")
        page = video.with_suffix(".html")
        data = json.dumps(timeline, ensure_ascii=False).replace("</", "<\\/")     # no </script> inside the script
        page.write_text(REVIEW.replace("/*TIMELINE*/null", data), encoding="utf-8")
        lines = [f"{len(frames)} frames in {sum(seconds):.1f} s, {made or 'no ffmpeg or Pillow here to join them'}",
                 f"review {page}; frames and timeline.json in {self.folder}"]
        return "\n    ".join(lines + watch_lines(timeline["frames"]))


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


def emulate(page: oe.DevTools, viewport: list[int]) -> None:
    page.call("Emulation.setDeviceMetricsOverride", width=viewport[0], height=viewport[1], deviceScaleFactor=1,
              mobile=False)


class StepFailed(Exception):
    pass


def step_line(n: int, step: dict) -> str:
    kind = next(k for k in STEPS if k in step)
    value = step[kind]
    what = {"tap": lambda: target_text(value), "hold": lambda: target_text(value),
            "drag": lambda: f"{target_text(value)} to {target_text(step['to'])}", "key": lambda: value,
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
        (x1, y1), (x2, y2) = game.aim(value), game.aim(step["to"])
        seconds = step.get("seconds", PRESS["drag"])
        moves = max(8, round(seconds / 0.03))
        game.press(x1, y1)
        for k in range(1, moves + 1):
            time.sleep(seconds / moves)
            game.move(x1 + (x2 - x1) * k / moves, y1 + (y2 - y1) * k / moves)
        time.sleep(0.05)
        game.release(x2, y2)
        return f"({x1:.0f}, {y1:.0f}) to ({x2:.0f}, {y2:.0f}) in {seconds:g} s", None
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
        return "; ".join(filter(None, [said, "recording" if value else ""])), None
    return screenshot(game, shots / f"{n:02d}-{value}.png"), None


def screenshot(game: Game, path: Path) -> str:
    path.write_bytes(base64.b64decode(game.win.call("Page.captureScreenshot")["data"]))
    return str(path)


def play(plan: dict, shots: Path, project: Path):
    """The `then` of open_in_editor.open_one: preview the project and run the plan."""
    def run(browser: oe.Browser, target: str, page: oe.DevTools) -> dict:
        if not plan.get("keep_saves"):     # a game reads its save on start, so the profile's would carry over
            page.call("Storage.clearDataForOrigin", origin=PREVIEW, storageTypes="local_storage,indexeddb")
        started = oe.start_preview(browser, target, page)
        if isinstance(started, list):
            return {"started": False, "layout": None, "runtime": None, "errors": started, "steps": []}
        window, win = started
        touch = bool(plan.get("touch"))
        steps: list[dict] = []
        try:
            if plan.get("viewport"):
                emulate(win, plan["viewport"])
            size = tuple(win.evaluate("[innerWidth, innerHeight]"))     # a headed window loses its frame's share
            if touch:
                win.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
            win.call("Emulation.setFocusEmulationEnabled", enabled=True)    # keys reach a page in the background
            sessions, live, stalled = oe.attach(win, patience=30)
            if not live:
                return {"started": False, "layout": None, "runtime": None, "steps": [], "errors": [
                    "the runtime loaded but did not tick for 3 seconds" if stalled
                    else "the preview window opened but no runtime was found in it in 30 seconds"]}
            session = live[0]
            win.evaluate(PLAY_JS, session=session)
            for s in sessions:
                try:
                    win.call("Runtime.enable", session=s)
                except oe.DevToolsError:    # a worker that ended since
                    pass
            win.evaluate("0")
            before = oe.runtime_errors(win)
            game = Game(win, session, touch, size, f"ws://127.0.0.1:{browser.port}/devtools/page/{window['targetId']}",
                        plan.get("viewport"), project)
            began = time.monotonic()
            for n, step in enumerate(plan["steps"], 1):
                done = {"step": n, "line": step_line(n, step), "ok": True}
                started_at = time.monotonic()
                try:
                    done["said"], extra = do_step(game, step, n, shots)
                    done.update(extra or {})
                except (StepFailed, oe.DevToolsError) as e:     # the code threw, or the page stopped answering
                    done.update(ok=False, said=str(e).splitlines()[0])
                    try:
                        done["said"] += f"; the window then: {screenshot(game, shots / f'{n:02d}-failed.png')}"
                    except oe.DevToolsError:
                        pass
                win.evaluate("0", session=session)      # the errors the step caused have arrived
                done["errors"] = oe.runtime_errors(win)
                steps.append(done)
                if game.recording:      # its timeline places the step
                    game.recording[1].steps.append({k: done[k] for k in ("step", "line", "ok", "said", "errors")}
                                                   | {"start": started_at, "end": time.monotonic()})
                if not done["ok"]:
                    break
            seconds = time.monotonic() - began
            recorded = game.stop_recording()
            snap = win.evaluate("c3probe.snapshot([], 0)", wait=6, session=session)
        finally:
            win.ws.close()
            browser.devtools.call("Target.closeTarget", targetId=window["targetId"])
        return {"started": True, "layout": snap["layout"], "runtime": "worker" if session else "page",
                "seconds": round(seconds, 1), "viewport": list(size), "touch": touch,
                "errors": before, "steps": steps, "planned": len(plan["steps"]), "recorded": recorded}
    return run


def report(result: dict) -> list[str]:
    if result["status"] != "opened":
        return oe.report(result)
    lines = [f"opened   {result['project']}  ({result['title']}, {result['editor']})"]
    lines += [f"  warning: {w}" for w in result.get("warnings", [])]
    ran = result.get("preview")
    if not ran or not ran["started"]:
        return lines + [f"  preview did not run: {e}" for e in (ran or {}).get("errors", ["no preview"])]
    touch = ", touch" if ran["touch"] else ""
    lines.append(f"  preview: layout {ran['layout']!r} at the end, runtime in the {ran['runtime']}, "
                 f"viewport {ran['viewport'][0]}x{ran['viewport'][1]}{touch}")
    lines += [f"  runtime: {e.splitlines()[0]}" for e in ran["errors"]]
    for done in ran["steps"]:
        said = f": {done['said']}" if done["said"] else ""
        lines.append(f"  {done['line']}{said}" if done["ok"] else f"  {done['line']}: FAILED, {done['said']}")
        if "state" in done:
            lines += ["  " + line for line in oe.state_lines(done["state"])]
        lines += [f"    runtime: {e.splitlines()[0]}" for e in done["errors"]]
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


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path, metavar="PLAN.json", help="the steps to play, as described above")
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
    ap.add_argument("--limit", type=int, default=c3.LIMIT, metavar="CHARS",
                    help=f"stop printing after about this many characters; --out keeps everything, 0 prints "
                         f"everything (default: {c3.LIMIT})")
    args = ap.parse_args()

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
    lines = report(result)
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
    return 0 if result["status"] == "opened" and ran.get("started") and not failed and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
