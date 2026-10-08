"""Preview a project, visit every layout, and print for each a screenshot to read,
what the runtime shows wrong on it, and the questions to answer about the picture.

    python scripts/review_look.py [PATH ...] [--project FOLDER] [--layouts NAME ...] [--settle SECONDS]
                                  [--viewport W H] [--release rNNN] [--browser EXE] [--shots DIR]
                                  [--out RESULT.json] [--headed] [--profile FOLDER]

Run it after open_in_editor.py --preview passes. It previews the project as F5
does, then goes to each layout in turn with the runtime's goToLayout, lets it run
SETTLE seconds, takes a screenshot, and reads every instance of the layout from
the runtime. It prints one line per mechanical finding, each naming the layout,
the object type, the instance's UID and what to change:

  text      a visible Text whose text needs more room than its box: it is cut
            or wraps beyond the box
  stacked   two or more visible instances of one object type on the same box,
            showing the same frame: instances created at runtime and never
            moved apart. Instances that show different frames or animations
            there, a fill under its rim, are layered on purpose and left out
  overlap   two visible instances on a layer of parallax 0 (the HUD), or two
            texts on any layer, one covering half of the other. A Text counts
            by the part its text covers. Left out: an instance inside a larger
            non-Text one (a label on its button, an icon on a panel), instances
            of one hierarchy, a text and its shadow, an overlay over half the
            screen
  edge      a visible HUD instance that the edge of the screen cuts; one wholly
            off screen waits there to move in and is left out
  frame     every visible instance of a Sprite type shows the same frame of an
            animation that has more, though a text instance variable differs
            between them and no text on each tells them apart

A screenshot is not drawn yet when 99.9% or more of it is one colour, black
or clear. It is taken again 1 s later, twice at most. A layout still of one
colour is named as drawing nothing in view, and no question is asked about it.

Then it prints the questions to answer from the screenshots, which the script
cannot judge: each is answered yes or no, and each yes names the object to
change. When the project has a design (--design, by default tools/design.json),
one question lists the design's screen entries that play_design.py cannot
measure: entries with other words before the first comma, and entries whose
key names no object of the project.

A layout reached by goToLayout starts without what the game's flow sets up
before it, so a layout that needs a run in progress may show less than in
play, or log errors that play does not: those are printed as `runtime:`
lines. Check such a scene by playing to it with preview_project.py and a
shot step.

Screenshots go to --shots, by default .tmp/look/ in the project, as
<layout>.png; the whole result to --out, by default .tmp/review-look.json.
Beside the screenshots it writes brief.md: the screenshots, the questions and
the form of the answer, for a reviewer that has not seen the project. The
agent that built the game reads its own pictures by what it meant to build.
So an agent that can start a sub-agent gives it the brief and takes the
answers from its reply, and one that cannot answers from the screenshots
itself. The last three lines are look:, with the result and the screenshots,
next:, and brief:, which says who answers the questions.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path

import c3project as c3
import game_model as gm
import open_in_editor as oe
import preview_project as play

EPILOG = """examples:
  python scripts/review_look.py
  python scripts/review_look.py --layouts Menu Map --settle 2
  python scripts/review_look.py --viewport 430 932

output:
  opened   <project>  (<window title>, <the editor it opened in>)
  layout 'Map' (2 of 3): screenshot .tmp/look/Map.png
    text: Text Title uid 12 "Choose your path": the text needs 212x40 px and its box is 160x40 ...
    stacked: Text CardName: 5 instances on one box at (300, 420) 120x30, uids 41, 42, 43 ...
    runtime: <an error the layout logged, with its event, and (N times) when it came more than once>
  layout 'Combat' (3 of 3): started, and its events went on to 'Map' before the screenshot; ...
  questions: answer every question yes or no for each screenshot above, through the brief as the last line ...
    1. Is any text cut off at an edge, broken onto a line of its own, or drawn over another object?
    ...
    7. Does the same decoration, not the HUD, appear on every screenshot?
  look: 2 findings on 3 layouts, 0 runtime errors; full result in .tmp/review-look.json, screenshots in .tmp/look
  next: <what to do>
  brief: if you can start a sub-agent, give it .tmp/look/brief.md as its whole task ...

exit codes: 0 every layout was visited with no finding and no runtime error; 1 a finding, a runtime error,
or the project did not open; 2 the project or the editor could not be used; 3 no browser here
"""

# Pixels of slack before a text, an overlap or a box on screen counts.
TOLERANCE = 4
# How many times its box's height a text may take: a line a little taller than its
# box still draws whole, a second line does not.
WRAPPED = 1.5
# Share of the smaller drawn box two instances may overlap by: a counter may touch
# its icon, but not cover half of it.
OVERLAP_SHARE = 0.5
# Share of the screen past which an instance is an overlay drawn over the HUD on purpose.
OVERLAY = 0.5
# Shots of one layout in all while it is one colour (c3project.BLANK), and the seconds between them.
BLANK_TRIES = 3
BLANK_WAIT = 1.0

QUESTIONS = (
    "Is any text cut off at an edge, broken onto a line of its own, or drawn over another object?",
    "Does any object cover part of another object that is not its own background, such as a name over a body "
    "or a character inside the cards?",
    "Is any object cut off by the edge of the screen?",
    "Do two outline weights, two kinds of shadow (hard and blurred), flat and gradient fills, or pixel and "
    "smooth edges appear on screen together?",
    "Is a background or a decoration larger or brighter than the objects the player taps or moves?",
    "Do two objects that stand for different things (two enemy types, two kinds of map node, two cards) look "
    "identical?",
)
ACROSS = "Does the same decoration, not the HUD, appear on every screenshot?"

# Evaluated where the game runs, after the probe: the layout, its layers and every
# world instance on it, with what the checks need. A Sprite's frame is read twice,
# 0.3 s apart, so an animation that plays is told from one that stands still.
LOOK_JS = r"""(async () => {
  const runtime = c3probe.runtime, layout = runtime.layout;
  const shown = layer => [layer, ...layer.parentLayers()].every(l => l.isVisible && l.opacity > 0);
  const layers = {};
  for (const layer of layout.allLayers()) {
    const v = layer.getViewport();
    layers[layer.name] = {parallax: [layer.parallaxX, layer.parallaxY], shown: shown(layer),
                          view: [v.left, v.top, v.right, v.bottom]};
  }
  // A Sprite whose animation is not set yet throws on animationName.
  const frameOf = i => { try { return typeof i.animationFrame === 'number' ? `${i.animationName}/${i.animationFrame}`
                                                                              : undefined; } catch (e) { return undefined; } };
  const seen = new Map(), frames = () => new Map([...seen.values()].map(i => [i.uid, frameOf(i)]));
  for (const name of Object.keys(runtime.objects))
    for (const i of runtime.objects[name].getAllInstances())
      try { if (typeof i.getBoundingBox === 'function' && i.layer && !seen.has(i.uid)) seen.set(i.uid, i); }
      catch (e) {}      // an instance between layouts, whose layer is gone
  const before = frames();
  await new Promise(r => setTimeout(r, 300));
  const after = frames(), instances = [];
  for (const i of seen.values()) try {
    const b = i.getBoundingBox();
    let root = i;
    while (root.getParent && root.getParent()) root = root.getParent();
    const r = {type: i.objectType.name, uid: i.uid, layer: i.layer.name, box: [b.left, b.top, b.right, b.bottom],
               shown: !!(i.isVisible && i.opacity > 0 && layers[i.layer.name]?.shown), angle: i.angle,
               root: root.uid};
    if (typeof i.textWidth === 'number') {
      r.text = String(i.text ?? '');
      r.textSize = [i.textWidth, i.textHeight];
      r.align = [i.horizontalAlign, i.verticalAlign];
    }
    if (frameOf(i) !== undefined) {
      r.animation = i.animationName;
      r.frame = i.animationFrame;
      r.frames = i.animation ? i.animation.frameCount : 1;
      r.playing = before.get(i.uid) !== after.get(i.uid);
    }
    if (i.instVars) r.instVars = Object.fromEntries(Object.keys(i.instVars).map(k => [k, i.instVars[k]]));
    instances.push(r);
  } catch (e) {}        // destroyed while it was read
  return {layout: layout.name, size: [layout.width, layout.height],
          viewport: [runtime.viewportWidth, runtime.viewportHeight], layers, instances};
})()"""


def area(box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def sized(inst: dict) -> bool:
    """Whether an instance is shown at a size to judge: not a speck, nor one a
    tween is growing from nothing."""
    box = inst["box"]
    return inst["shown"] and box[2] - box[0] > TOLERANCE and box[3] - box[1] > TOLERANCE


def meet(a, b) -> list[float]:
    """The box two boxes share, empty when they do not touch."""
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def inside(a, b, slack: float = 1) -> bool:
    """Whether box a lies within box b."""
    return a[0] >= b[0] - slack and a[1] >= b[1] - slack and a[2] <= b[2] + slack and a[3] <= b[3] + slack


def drawn(inst: dict) -> list[float]:
    """The part of an instance's box its picture covers: for a Text, where its text
    sits in the box by its alignment, never past the box."""
    box = inst["box"]
    if "textSize" not in inst:
        return box
    w, h = min(inst["textSize"][0], box[2] - box[0]), min(inst["textSize"][1], box[3] - box[1])
    h_align, v_align = inst.get("align") or ("left", "top")
    left = {"center": (box[0] + box[2] - w) / 2, "right": box[2] - w}.get(h_align, box[0])
    top = {"center": (box[1] + box[3] - h) / 2, "bottom": box[3] - h}.get(v_align, box[1])
    return [left, top, left + w, top + h]


def name(inst: dict) -> str:
    text = inst.get("text")
    words = f"{inst['type']} uid {inst['uid']}"
    if text and text.strip():
        one = " ".join(text.split())
        words += " " + json.dumps(one if len(one) <= 24 else one[:21] + "...", ensure_ascii=False)
    return words


def px(n: float) -> str:
    return str(round(n))


def text_findings(instances: list[dict]) -> list[dict]:
    found = []
    for i in instances:
        if not (sized(i) and "textSize" in i and (i.get("text") or "").strip() and not i.get("angle")):
            continue
        (tw, th), w, h = i["textSize"], i["box"][2] - i["box"][0], i["box"][3] - i["box"][1]
        if tw > w + TOLERANCE or th > h * WRAPPED:
            found.append({"rule": "text", "uids": [i["uid"]], "line":
                          f"{name(i)}: the text needs {px(tw)}x{px(th)} px and its box is {px(w)}x{px(h)}, so it "
                          f"is cut or wraps: make the box at least {px(max(tw, w))}x{px(max(th, h))} or the font "
                          f"smaller"})
    return found


def stacked_findings(instances: list[dict]) -> list[dict]:
    """Instances of one type on one box that show the same frame: two that show different
    frames or animations, a fill under its rim, are layered on purpose."""
    groups: dict[tuple, list[dict]] = {}
    for i in instances:
        if sized(i):
            box = tuple(round(v) for v in i["box"])
            groups.setdefault((i["type"], i["layer"], box, i.get("animation"), i.get("frame")), []).append(i)
    found = []
    for (kind, _, (left, top, right, bottom), *_), same in groups.items():
        if len(same) < 2:
            continue
        uids = [i["uid"] for i in same]
        texts = sorted({" ".join(i["text"].split()) for i in same if (i.get("text") or "").strip()})
        said = f", texts {', '.join(json.dumps(t[:20], ensure_ascii=False) for t in texts[:4])}" if len(texts) > 1 else ""
        found.append({"rule": "stacked", "uids": uids, "line":
                      f"{kind}: {len(same)} instances on one box at ({left}, {top}) {right - left}x{bottom - top}, "
                      f"uids {', '.join(map(str, uids[:6]))}{' ...' if len(uids) > 6 else ''}{said}: they were "
                      f"created and never moved apart; set each one's position from the instance it belongs to"})
    return found


def overlap_findings(instances: list[dict], layers: dict) -> list[dict]:
    def hud(i: dict) -> bool:
        return tuple(layers.get(i["layer"], {}).get("parallax", (1, 1))) == (0, 0)
    seen = [i for i in instances if sized(i) and not i.get("angle")
            and (hud(i) or (i.get("text") or "").strip())]
    found = []
    for n, a in enumerate(seen):
        for b in seen[n + 1:]:
            if a["layer"] != b["layer"] or a["root"] == b["root"] or not hud(a) and "textSize" not in b:
                continue
            if a["type"] == b["type"] and [round(v) for v in a["box"]] == [round(v) for v in b["box"]]:
                continue        # stacked, reported as such
            if "textSize" in a and "textSize" in b and (a["text"] == b["text"] or all(
                    abs(u - v) <= 2 * TOLERANCE for u, v in zip(a["box"], b["box"]))):
                continue        # a text and its shadow or outline
            da, db = drawn(a), drawn(b)
            screen = area(layers[a["layer"]]["view"])
            if area(da) > OVERLAY * screen or area(db) > OVERLAY * screen:
                continue        # a message or a backdrop over the whole screen
            if inside(da, b["box"]) and "textSize" not in b or inside(db, a["box"]) and "textSize" not in a:
                continue        # a label on its button, an icon on its panel
            shared = meet(da, db)
            w, h = shared[2] - shared[0], shared[3] - shared[1]
            if w <= TOLERANCE or h <= TOLERANCE or w * h < OVERLAP_SHARE * min(area(da), area(db)):
                continue
            found.append({"rule": "overlap", "uids": [a["uid"], b["uid"]], "line":
                          f"{name(a)} and {name(b)} overlap by {px(w)}x{px(h)} px on "
                          f"{'HUD ' if hud(a) else ''}layer {a['layer']!r}: "
                          f"move one of them clear of the other, or make the smaller a child of the one it "
                          f"belongs to"})
    return found


def edge_findings(instances: list[dict], layers: dict) -> list[dict]:
    """HUD instances the screen's edge cuts. One wholly off screen waits there to
    move in, and art on a world layer may run off the edge on purpose."""
    found = []
    for i in instances:
        layer = layers.get(i["layer"])
        if not (sized(i) and layer and tuple(layer["parallax"]) == (0, 0)):
            continue
        b, view = drawn(i), layer["view"]
        shared = meet(b, view)
        if shared[2] - shared[0] <= TOLERANCE or shared[3] - shared[1] <= TOLERANCE:
            continue            # off screen, or a sliver of it
        wide, tall = b[2] - b[0] >= view[2] - view[0], b[3] - b[1] >= view[3] - view[1]
        cut = [side for side, over, spans in (("left", view[0] - b[0], wide), ("top", view[1] - b[1], tall),
                                              ("right", b[2] - view[2], wide), ("bottom", b[3] - view[3], tall))
               if over > TOLERANCE and not spans]
        if cut:
            found.append({"rule": "edge", "uids": [i["uid"]], "line":
                          f"{name(i)}: the {' and '.join(cut)} edge of the screen cuts it, its box ({px(b[0])}, "
                          f"{px(b[1])}) to ({px(b[2])}, {px(b[3])}) and the screen ({px(view[0])}, {px(view[1])}) to "
                          f"({px(view[2])}, {px(view[3])}) on HUD layer {i['layer']!r}: move it inside the screen"})
    return found


def frame_findings(instances: list[dict]) -> list[dict]:
    kinds: dict[str, list[dict]] = {}
    for i in instances:
        if i["shown"] and "frame" in i:
            kinds.setdefault(i["type"], []).append(i)
    texts = [drawn(i) for i in instances if i["shown"] and (i.get("text") or "").strip()]
    found = []
    for kind, same in kinds.items():
        if len(same) < 2 or any(i["playing"] or i["frames"] < 2 for i in same):
            continue
        if all(any(inside(t, i["box"]) for t in texts) for i in same):
            continue        # each one carries a text that tells it apart
        if len({(i["animation"], i["frame"]) for i in same}) > 1:
            continue
        differ = {}
        for var in same[0].get("instVars") or {}:
            values = [i.get("instVars", {}).get(var) for i in same]
            distinct = {json.dumps(v) for v in values}
            if 1 < len(distinct) and all(isinstance(v, str) for v in values):
                differ[var] = sorted(distinct)
        if not differ:
            continue
        var, values = next(iter(differ.items()))
        shown_values = ", ".join(values[:4]) + (" ..." if len(values) > 4 else "")
        found.append({"rule": "frame", "uids": [i["uid"] for i in same], "line":
                      f"{kind}: all {len(same)} instances show animation {same[0]['animation']!r} frame "
                      f"{same[0]['frame']} of {same[0]['frames']}, though their {var} differs ({shown_values}): set "
                      f"each one's frame or animation from {var} where it is created"})
    return found


def findings(snap: dict) -> list[dict]:
    """Every mechanical finding on a layout read by LOOK_JS, each {rule, uids, line}."""
    instances, layers = snap["instances"], snap["layers"]
    return (text_findings(instances) + stacked_findings(instances) + overlap_findings(instances, layers)
            + edge_findings(instances, layers) + frame_findings(instances))


def file_name(layout: str) -> str:
    """A layout's name as a file name: letters and digits of any script, the rest as -."""
    return re.sub(r"[^\w-]+", "-", layout, flags=re.UNICODE).strip("-") or "layout"


# Goes to a layout, lets it run SETTLE seconds, and says which layouts started on
# the way and which one runs at the end: a layout whose start events go on to
# another shows as started and left.
GO_JS = """(async () => {{ const runtime = c3probe.runtime, want = {name}, entered = [];
  const on = () => entered.push(runtime.layout.name);
  runtime.addEventListener('afteranylayoutstart', on);
  try {{
    if (runtime.layout.name === want) entered.push(want); else runtime.goToLayout(want);
    const t0 = performance.now();
    while (!entered.includes(want)) {{ if (performance.now() - t0 > 10000) break;
      await new Promise(r => setTimeout(r, 20)); }}
    if (entered.includes(want)) await new Promise(r => setTimeout(r, {settle} * 1000));
  }} finally {{ runtime.removeEventListener('afteranylayoutstart', on); }}
  return {{entered, now: runtime.layout.name}}; }})()"""


def review(only: list[str] | None, settle: float, viewport: list[int] | None, shots: Path):
    """The `then` of open_in_editor.open_one: preview the project and visit its layouts."""
    def run(browser: oe.Browser, target: str, page: oe.DevTools) -> dict:
        page.call("Storage.clearDataForOrigin", origin=play.PREVIEW, storageTypes="local_storage,indexeddb")
        started = oe.start_preview(browser, target, page)
        if isinstance(started, list):
            return {"started": False, "errors": started, "layouts": []}
        window, win = started
        visited: list[dict] = []
        try:
            if viewport and play.emulate(win, viewport) != tuple(viewport):
                return {"started": False, "layouts": [], "errors": [
                    f"the preview window did not take the viewport {viewport[0]}x{viewport[1]} in {play.RESIZE} s"]}
            sessions, live, stalled = oe.attach(win, patience=30)
            if not live:
                return {"started": False, "layouts": [], "errors": [
                    "the runtime loaded but did not tick for 3 seconds" if stalled
                    else "the preview window opened but no runtime was found in it in 30 seconds"]}
            session = live[0]
            for s in sessions:
                try:
                    win.call("Runtime.enable", session=s)
                except oe.DevToolsError:    # a worker that ended since
                    pass
            win.evaluate("0")
            first_errors = oe.runtime_errors(win)
            names = win.evaluate("c3probe.runtime.getAllLayouts().map(l => l.name)", session=session)
            first = win.evaluate("c3probe.runtime.layout.name", session=session)
            order = [first] + [n for n in names if n != first]
            missing = [n for n in only or [] if n not in names]
            if missing:
                return {"started": False, "layouts": [], "errors": [
                    f"no layout {m!r}{c3.closest(m, names)}" for m in missing]}
            for layout in [n for n in order if not only or n in only]:
                done: dict = {"layout": layout, "errors": first_errors if layout == first else []}
                went = win.evaluate(GO_JS.format(name=json.dumps(layout), settle=settle), wait=settle + 20,
                                    session=session)
                if went["now"] != layout:
                    done["left"] = went["now"] if layout in went["entered"] else None
                    win.evaluate("0", session=session)
                    done["errors"] += oe.runtime_errors(win)
                    visited.append(done)
                    continue
                shot = shots / f"{file_name(layout)}.png"
                for tries in range(1, BLANK_TRIES + 1):
                    share = oe.blank(win)
                    if share is None or tries == BLANK_TRIES:
                        break
                    time.sleep(BLANK_WAIT)
                shot.write_bytes(base64.b64decode(win.call("Page.captureScreenshot")["data"]))
                if tries > 1:
                    done["blank"] = {"tries": tries, "share": share}
                try:
                    snap = win.evaluate(LOOK_JS, wait=20, session=session)
                    done.update(shot=str(shot), findings=findings(snap), snapshot=snap)
                except oe.DevToolsError as e:     # the layout's instances could not be read
                    done.update(shot=str(shot), findings=[])
                    done["errors"].append(f"its instances were not read: {str(e).splitlines()[0]}")
                win.evaluate("0", session=session)
                done["errors"] += oe.runtime_errors(win)
                visited.append(done)
        finally:
            win.ws.close()
            browser.devtools.call("Target.closeTarget", targetId=window["targetId"])
        return {"started": True, "runtime": "worker" if session else "page", "layouts": visited, "errors": []}
    return run


def unmeasured(project: Path, design: Path | None) -> list[str]:
    """The design's screen entries play_design.py does not measure, each as key "words": in words outside its
    vocabulary, or under a key that names no object type of the project."""
    path = design or project / "tools" / "design.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    types = [n for n, _ in c3.folder_items(c3.load(project / "project.c3proj").get("objectTypes", {}))]
    model = gm.Design(data)
    out = []
    for p in gm.screen_places(model):
        named = [gm.screen_objects(k, model, types) for k in [p.key] + [ref for _, ref in p.sides]]
        if not p.measured or not all(named):
            out.append(f"{p.key} {json.dumps(p.text, ensure_ascii=False)}")
    return out


def questions(several: bool, places: list[str] = ()) -> list[str]:
    """The questions the script cannot answer, about every screenshot."""
    out = list(QUESTIONS)
    if places:
        out.append(f"On a screenshot that shows it, does an object sit away from the place given for it: "
                   f"{'; '.join(places)}?")
    if several:
        out.append(ACROSS)
    return out


def ask(several: bool, places: list[str] = ()) -> list[str]:
    """The questions, put to the agent about every screenshot."""
    lines = ["questions: answer every question yes or no for each screenshot above, through the brief as the last "
             "line says, or with your image tool, one screenshot at a time. For each yes, name the layout, the object "
             "type to change and what to change:"]
    return lines + [f"  {n}. {q}" for n, q in enumerate(questions(several, places), 1)]


def shows_something(done: dict) -> bool:
    """Whether a layout's visit left a screenshot that shows something, one the questions are about."""
    return bool(done.get("shot")) and not (done.get("blank") or {}).get("share")


def brief(result: dict) -> str:
    """The questions as a task for a reviewer that has not seen the project: the screenshots, the questions and
    the form of the answer, and nothing of what the game was meant to show."""
    layouts = (result.get("preview") or {}).get("layouts", [])
    shots = [(d["layout"], d["shot"]) for d in layouts if shows_something(d)]
    asked = questions(len(layouts) > 1, result.get("places", []))
    lines = ["# Look review", "",
             "You have not seen this game's project, its events or how it was built, and you do not need to. Judge "
             "only what the screenshots show. If a picture does not show it, answer no.", "",
             "Open each screenshot with your image tool, one at a time:", ""]
    lines += [f"{n}. {layout}: {shot}" for n, (layout, shot) in enumerate(shots, 1)]
    lines += ["", "Answer every question for every screenshot, yes or no:", ""]
    lines += [f"{n}. {q}" for n, q in enumerate(asked, 1)]
    lines += ["", "Reply with one line per screenshot and question, and nothing else. Start each line with the "
                  "screenshot's name and the question's number. A yes says where on the screenshot the thing is and "
                  "what looks wrong; a no is the word alone. The form, not the content:", "", "```"]
    first = shots[0][0] if shots else "Layout"
    lines += [f"{first} 1: no", f"{first} 2: yes - <where on the screenshot>: <what looks wrong>", "...", "```", ""]
    return "\n".join(lines)


def report(result: dict) -> list[str]:
    if result["status"] != "opened":
        return oe.report(result)
    lines = [f"opened   {result['project']}  ({result['title']}, {result['editor']})"]
    lines += [f"  warning: {w}" for w in result.get("warnings", [])]
    ran = result.get("preview") or {"started": False, "errors": ["no preview"]}
    if not ran["started"]:
        return lines + [f"  preview did not run: {e}" for e in ran["errors"]]
    total = len(ran["layouts"])
    for n, done in enumerate(ran["layouts"], 1):
        shot, blank = done.get("shot"), done.get("blank") or {}
        if shot and blank.get("share"):
            lines.append(f"layout {done['layout']!r} ({n} of {total}): screenshot {shot}: {c3.BLANK:.1%} or more "
                         f"of it is one colour after {blank['tries']} shots {BLANK_WAIT:g} s apart, so the layout "
                         f"draws nothing in view at its start, or the preview did not draw it. No question is asked "
                         f"about it. If it should show something, raise --settle, or reach it in play with a shot "
                         f"step of a preview_project.py plan")
        elif shot:
            before = "the shot" if blank.get("tries") == 2 else f"the {blank.get('tries', 1) - 1} shots"
            again = f", taken when the layout was drawn; {before} before showed one colour, not drawn yet" if blank \
                else ""
            lines.append(f"layout {done['layout']!r} ({n} of {total}): screenshot {shot}{again}")
        elif done.get("left"):
            lines.append(f"layout {done['layout']!r} ({n} of {total}): started, and its events went on to "
                         f"{done['left']!r} before the screenshot; it needs what the game sets up before it: play to "
                         f"it with preview_project.py and a shot step, and read that screenshot the same way")
        else:
            lines.append(f"layout {done['layout']!r} ({n} of {total}): not reached in 10 seconds")
        lines += [f"  {f['rule']}: {f['line']}" for f in done.get("findings", [])]
        lines += oe.runtime_lines(done["errors"])
    if any(shows_something(d) for d in ran["layouts"]):
        lines += ask(total > 1, result.get("places", []))
    return lines


def counts(result: dict) -> tuple[int, int, int]:
    """Findings, runtime errors and layouts visited."""
    layouts = (result.get("preview") or {}).get("layouts", [])
    return (sum(len(d.get("findings", [])) for d in layouts), sum(len(d["errors"]) for d in layouts), len(layouts))


def look_line(results: list[dict], settle: float, out: Path, base: Path) -> str:
    """The count of findings, and when there is none, what the run did not see."""
    found, errors, layouts = map(sum, zip(*(counts(r) for r in results)))
    unseen = "" if found or errors else (f"; each layout ran {settle:g} s after a jump to it, without play, so a "
                                         f"scene the game reaches only in play is unseen")
    return (f"look: {found} finding{'' if found == 1 else 's'} on {layouts} layout{'' if layouts == 1 else 's'}, "
            f"{errors} runtime error{'' if errors == 1 else 's'}{unseen}; full result in {out}, screenshots in {base}")


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, metavar="PATH",
                    help="a folder project, or a folder above several (default: the project of --project, else "
                         "the one the current directory is in)")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--layouts", nargs="+", metavar="NAME", help="visit only these layouts (default: every layout, "
                                                                "the one the editor opens on first)")
    ap.add_argument("--settle", type=float, default=1.0, metavar="SECONDS",
                    help="how long each layout runs before its screenshot, for its start events and tweens "
                         "(default 1)")
    ap.add_argument("--viewport", type=int, nargs=2, metavar=("W", "H"),
                    help="CSS pixels of the preview window (default: the project's viewport size)")
    ap.add_argument("--release", metavar="rNNN", help="open in this release of the editor, as open_in_editor.py does")
    ap.add_argument("--browser", metavar="EXE",
                    help="the Chromium-based browser to start (default: Edge, Chrome or Chromium where installed)")
    ap.add_argument("--shots", type=Path, help="the folder for the screenshots (default: .tmp/look in the project)")
    ap.add_argument("--out", type=Path, help="write the result, every instance read included, as JSON "
                                             "(default: .tmp/review-look.json in the project)")
    ap.add_argument("--design", type=Path, metavar="DESIGN.json",
                    help="the game's design; a screen entry that play_design.py does not measure becomes a question "
                         "(default: tools/design.json in the project, when there is one)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--profile", type=Path, metavar="FOLDER",
                    help="keep the browser profile in FOLDER/editor-<browser> instead of the project's .tmp/")
    ap.add_argument("--limit", type=int, default=c3.LIMIT, metavar="CHARS",
                    help=f"stop printing after about this many characters; --out keeps everything, 0 prints "
                         f"everything (default: {c3.LIMIT})")
    args = ap.parse_args()

    if args.paths:
        projects = [p for p in oe.find_projects(args.paths) if p.is_dir()]
    else:
        project = c3.find_project(args.project)
        projects = [project] if project and (project / "project.c3proj").is_file() else []
    if not projects:
        print(f"no project.c3proj found under {', '.join(map(str, args.paths)) or args.project or Path.cwd()}; run "
              f"this in the project folder or pass --project <folder>", file=sys.stderr)
        return 2
    exe = args.browser or oe.browser_path()
    if not exe:
        print("no Edge, Chrome or Chromium found here, and this script needs one it can drive: install one, or open "
              "the project with open_in_editor.py --steps and take a screenshot of each layout with a browser tool "
              "of this session.")
        return 3
    editor = f"{oe.EDITOR}{args.release.strip('/')}/" if args.release else oe.EDITOR
    out, base = oe.kept(args.out, args.shots, projects[0], "review-look.json", "look")
    try:
        browser = oe.Browser(exe, (args.profile or oe.scratch(projects[0])) / f"editor-{Path(exe).stem.lower()}",
                             args.headed)
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    results, printed = [], 0
    try:
        for project in projects:
            shots = base if len(projects) == 1 else base / project.name
            shots.mkdir(parents=True, exist_ok=True)
            data = c3.load(project / "project.c3proj")
            view = args.viewport or [data.get("viewportWidth"), data.get("viewportHeight")]
            view = view if all(isinstance(n, int) and n > 0 for n in view) else None
            try:
                result = oe.open_one(browser, editor, project, browser.profile / "project-look.c3p", None,
                                     bool(args.release), review(args.layouts, args.settle, view, shots))
            except oe.EditorNotLoaded as e:
                print(f"the editor did not load: {e}. Check the network connection and --release, and run again.",
                      file=sys.stderr)
                return 2
            result["places"] = unmeasured(project, args.design)
            if any(shows_something(d) for d in (result.get("preview") or {}).get("layouts", [])):
                result["brief"] = str(shots / "brief.md")
                (shots / "brief.md").write_text(brief(result), encoding="utf-8")
            results.append(result)
            out.write_text(json.dumps(results if len(projects) > 1 else result, ensure_ascii=False, indent=1),
                           encoding="utf-8")       # kept as each project ends, should a later one stop the run
            lines = report(result)
            shown = c3.fitting(lines, max(1, args.limit - printed) if args.limit else 0)
            if shown:
                text = "\n".join(lines[:shown])
                print(text, flush=True)
                printed += len(text) + 1
            if shown < len(lines):
                print(f"{len(lines) - shown} lines not printed: {out} keeps everything, --limit 0 prints it")
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    finally:
        browser.close()
    found, errors, _ = map(sum, zip(*(counts(r) for r in results)))
    print(look_line(results, args.settle, out, base))
    if any(r["status"] != "opened" for r in results):
        print(oe.NEXT)
        return 1
    briefs = [r["brief"] for r in results if r.get("brief")]
    print("next: fix every finding line; a runtime error on a layout reached straight away may need the run that "
          "leads there, so play to it with preview_project.py before blaming the events. Then have the questions "
          "answered and fix each yes. Run this again until it prints no finding and every answer is no.")
    if briefs:
        print(f"brief: if you can start a sub-agent, give it {' and '.join(briefs)} as its whole task and take each "
              f"yes from its reply. Tell it nothing more about the game: it has not seen the project, so it judges the "
              f"pictures as a player does. Otherwise open each screenshot and answer the questions yourself.")
    return 1 if found or errors else 0


if __name__ == "__main__":
    sys.exit(main())
