"""Screenshot an event sheet as the Construct 3 editor shows it, cropped to the sheet, for a forum post,
a bug report or a page of documentation.

    python scripts/screenshot_sheet.py [SHEET] [--group TITLE ...] [--scale 2] [--out FOLDER]
                                       [--dark] [--project FOLDER] [--release rNNN] [--browser EXE]
                                       [--profile FOLDER]

It opens the project in the editor as open_in_editor.py does, opens SHEET from the Project Bar, and
captures it in English with the editor's own icons and colours. Four things make the picture read
well outside the editor:

- The conditions column is as wide as the longest condition, and the actions column as wide as the
  longest action, each up to a cap, so that every line the caps allow stays on one line and the
  picture has no empty band on its right. The conditions column is the width the divider between the
  columns sets in the editor; the project's files are not changed.
- Text is drawn with grayscale antialiasing and without hinting, close to macOS. The coloured fringes
  of Windows' subpixel text turn into halos once a forum or a viewer scales the picture.
- The window grows to the height of the picture, so a sheet that fits is one picture, and anything
  the editor shows over the sheet, a notice or a banner, is hidden first. One picture holds at most
  the smaller of 16384 device pixels and the GPU's largest texture, less the editor's bars: about
  8000 px of the sheet at --scale 2. A taller sheet or group is not taken. The line that says so
  gives the height that fits and names the groups to take one at a time with --group.
- The sheet is light, as the default theme draws it on a system in light mode, whatever the mode of
  this machine: the default theme follows the system's colour scheme. --dark draws it dark.

Each picture is written to .build/sheets/ of the project, a folder Git ignores: <SHEET>@<scale>x.png
for the whole sheet, or <SHEET> - <group>@<scale>x.png for each --group instead. At --scale 2 a
picture stays sharp when it is shown at half its size, which is how most forums and viewers show it.
"""
import base64
import math
import sys
import time
from pathlib import Path

import c3project as c3
import open_in_editor as oe
import pack_project as pp

EPILOG = """examples:
  python scripts/screenshot_sheet.py                              the project's only or first sheet
  python scripts/screenshot_sheet.py Game --group Targeting       the group Targeting alone
  python scripts/screenshot_sheet.py Game --scale 1 --out shots   at the size the editor shows it, into shots/

output:
  opened   <project>  (<window title>, <the editor it opened in>)
  columns of the sheet Game: conditions 474 px, actions 654 px
  wrote .build/sheets/Game@2x.png, 2360 x 1202

exit codes: 0 every picture written; 1 the editor refused the project, a sheet or group was not found
in it, or a picture was not taken (the line says why); 2 the flags, the project or the browser could
not be used; 3 no Edge, Chrome or Chromium here"""

WIDTH = 2600            # CSS px of the window: room for both columns at their caps beside the editor's panes
HEIGHT = 1000           # the least height of the window, which grows to a taller picture
COND_CAP = 600          # the widest the conditions column grows to; a longer condition wraps
ACT_CAP = 900           # the same for the actions column
# Device px: the browser captures no window taller than this, nor taller than the GPU's largest
# texture. Past it the picture repeats the top of the window or stays blank, and the capture still
# answers, so the window never grows past it.
MOST = 16384
NO_GPU = 8192           # the same where the page has no WebGL to read; unmeasured, half the usual texture
PAD = 10                # CSS px of the sheet's own background around a picture
AIR = 24                # CSS px after the longest condition and the longest action, so no line meets its edge
OPEN_WAIT = 15          # seconds for a sheet to show, its double-click repeated; it takes about 1
# Seconds a call into the editor waits per sid of the sheet, on top of open_in_editor's CALL:
# the editor lays out every row at once. Fitting the columns waits three times as long, because it
# lays the sheet out about 25 times; it takes about 2 s at 2300 sids.
SID_WAIT = 0.01
PIXEL_WAIT = 1          # seconds a capture waits per million device px of its picture; it takes under 1 s

# Grayscale antialiasing, no LCD subpixel colour; the CSS below turns hinting off and thickens stems a
# little, as macOS draws text. The editor follows the browser's language, and the pictures are English.
BROWSER_ARGS = ("--disable-lcd-text", "--lang=en-US")
# The default theme draws light or dark by the system's colour scheme, read once as the editor loads;
# Blink's preferredColorScheme is 0 for dark and 1 for light.
SCHEME_ARG = "--blink-settings=preferredColorScheme={}"
SMOOTH_CSS = ("* { text-rendering: geometricPrecision !important; -webkit-font-smoothing: antialiased !important;"
              " -webkit-text-stroke: 0.25px currentColor; }")

ZOOM_JS = r"""(() => { const d = document.querySelector('dialog#okDialog[open]');
  if (!d || !/zoom level/.test(d.textContent)) return null;
  const r = d.querySelector('button.okButton').getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()"""
ITEM_JS = r"""(name => { const e = [...document.querySelectorAll(
    'ui-treeitem.eventSheet:not(.parentItem) > .tree-item-wrap .tree-item-name')].find(e => e.textContent.trim() === name);
  if (!e) return null;
  e.scrollIntoView({block: 'center'});
  const r = e.getBoundingClientRect();
  return r.width ? {x: r.x + r.width / 2, y: r.y + r.height / 2} : {hidden: true}; })"""
# The event sheet tab on show is a ui-pane.eventSheetViewPane; its ui-body.eventSheetView scrolls, and the
# rows are the grid of the div.eventSheetRootView inside it.
PANE_JS = "[...document.querySelectorAll('ui-pane.eventSheetViewPane')].find(e => e.getBoundingClientRect().width > 0)"
BODY_JS = f"{PANE_JS}?.querySelector('ui-body.eventSheetView')"
ROOT_JS = f"{BODY_JS}?.querySelector('div.eventSheetRootView')"
SHOWN_JS = f"(() => {{ const r = {ROOT_JS}; return r ? r.children.length : 0; }})()"
STYLE_JS = (f"document.head.appendChild(Object.assign(document.createElement('style'), "
            f"{{textContent: {SMOOTH_CSS!r}}})).isConnected")
# The narrowest width at which no condition, then no action, wraps, found by bisection up to the caps;
# only the cells between top and bottom count when they are given, those of one group.
# The condition blocks size themselves from --conditions-column-size, the editor's divider; the actions
# take the grid's last track, fixed here instead of the rest of the window.
FIT_JS = r"""(async (condCap, actCap, top, bottom, air) => {
  const root = %s;
  const inside = c => { const r = c.getBoundingClientRect(); return r.width > 0 && (top === null || (r.top >= top && r.bottom <= bottom)); };
  const cells = {'.conditionDescCell': [...root.querySelectorAll('.conditionDescCell')].filter(inside),
                 '.actionDescCell': [...root.querySelectorAll('.actionDescCell')].filter(inside),
                 '.eventCommentWrap': [...root.querySelectorAll('.eventCommentWrap')].filter(inside)};
  const lines = c => { const r = document.createRange(); r.selectNodeContents(c);
    const rects = [...r.getClientRects()].filter(q => q.width > 0 && q.height > 0);
    if (!rects.length) return 0;
    const top = Math.min(...rects.map(q => q.top)), em = parseFloat(getComputedStyle(c).fontSize);
    return 1 + new Set(rects.filter(q => q.top > top + 0.8 * em).map(q => Math.round((q.top - top) / em))).size; };
  // A comment may hold line breaks of its own; only a line the column breaks counts.
  const wraps = sel => cells[sel].some(c => lines(c) > c.innerText.split(String.fromCharCode(10)).length);
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const margin = parseFloat(getComputedStyle(root).gridTemplateColumns);
  let cond = condCap, act = actCap;
  const apply = async () => { root.style.setProperty('--conditions-column-size', cond + 'px');
    root.style.gridTemplateColumns = margin + 'px var(--conditions-column-size) ' + act + 'px'; await frame(); };
  const narrowest = async (sel, set, lo, hi) => {
    set(hi); await apply();
    if (wraps(sel)) return [hi, true];
    while (hi - lo > 4) { const mid = Math.round((lo + hi) / 2); set(mid); await apply();
      if (wraps(sel)) lo = mid; else hi = mid; }
    set(hi); await apply(); return [hi, false]; };
  const [c, condWraps] = await narrowest('.conditionDescCell', v => cond = v, 120, condCap);
  let [a, actWraps] = await narrowest('.actionDescCell', v => act = v, 160, actCap);
  // A comment spans both columns: the actions column widens until no comment wraps either.
  const [ac, commentWraps] = await narrowest('.eventCommentWrap', v => act = v, a, actCap);
  a = Math.max(a, ac);
  cond = c + air; act = a + air; await apply();
  return {margin, cond, act, condWraps, actWraps, commentWraps};
})""" % ROOT_JS
# The box of the sheet, or of the group with this title from its header to its "Add event to" row, and
# the box of the sheet's view, in CSS px of the page. The box is null when the sheet has no such group.
BOX_JS = r"""(title => {
  const body = %s, root = body.querySelector('div.eventSheetRootView'), r = root.getBoundingClientRect();
  const cols = getComputedStyle(root).gridTemplateColumns.split(' ').map(parseFloat);
  const right = r.left + cols.reduce((a, b) => a + b, 0) + parseFloat(getComputedStyle(root).paddingLeft);
  const v = body.getBoundingClientRect();
  const out = {view: {left: v.left, top: v.top, right: v.left + body.clientWidth, bottom: v.top + body.clientHeight},
               inner: innerHeight, outer: outerHeight, box: null};
  if (title === null) {
    const rows = [...root.children].filter(e => e.getBoundingClientRect().height > 0);
    const last = rows.filter(e => !/^Add event$/.test(e.textContent.trim())).pop() || root;
    out.box = {left: r.left, top: r.top, right, bottom: last.getBoundingClientRect().bottom};
    return out;
  }
  const leaves = [...root.querySelectorAll('*')].filter(e => e.children.length === 0);
  const head = leaves.find(e => e.textContent.trim() === title && e.closest('[class*=group i]'));
  const end = leaves.find(e => e.textContent.trim() === "Add event to '" + title + "'");
  if (head && end)
    out.box = {left: r.left, top: head.closest('[class*=group i]').getBoundingClientRect().top, right,
               bottom: end.getBoundingClientRect().bottom};
  return out; })""" % BODY_JS
SCROLL_JS = f"(by => {{ const body = {BODY_JS}; body.scrollTop += by; }})"
# The tallest window the GPU draws: its largest texture and render buffer.
GPU_JS = r"""(() => { const c = document.createElement('canvas'), g = c.getContext('webgl2') || c.getContext('webgl');
  return g ? Math.min(g.getParameter(g.MAX_TEXTURE_SIZE), g.getParameter(g.MAX_RENDERBUFFER_SIZE)) : null; })()"""
# Hide whatever the editor draws over the picture (a notice, a banner, a tooltip): each fixed, absolute
# or sticky element that overlaps the picture's box, except the sheet's pane and the elements that hold
# it. The editor draws its notices as fixed elements inside the element that holds the pane.
UNCOVER_JS = r"""(b => { const pane = %s; let hidden = 0;
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT,
    {acceptNode: e => e === pane ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
  for (let e = walk.nextNode(); e; e = walk.nextNode()) {
    if (e.contains(pane) || !/^(fixed|absolute|sticky)$/.test(getComputedStyle(e).position)) continue;
    const r = e.getBoundingClientRect();
    if (r.right > b.left && r.left < b.right && r.bottom > b.top && r.top < b.bottom) {
      e.style.visibility = 'hidden'; hidden++; } }
  return hidden; })""" % PANE_JS


def click(page: oe.DevTools, x: float, y: float, count: int = 1) -> None:
    page.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    for n in range(1, count + 1):
        for kind in ("mousePressed", "mouseReleased"):
            page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=n)


def close_zoom_notice(page: oe.DevTools, patience: float = 2, wait: float = oe.CALL) -> None:
    """The editor says the zoom level changed when the device scale does, and its dialog blocks the
    Project Bar; OK closes it. The scale is the screenshot's, not a zoom of the user's."""
    deadline = time.monotonic() + patience
    while time.monotonic() < deadline:
        at = page.evaluate(ZOOM_JS, wait=wait)
        if at:
            click(page, at["x"], at["y"])
            return
        time.sleep(0.2)


def resize(browser: oe.Browser, target: str, width: int, height: int) -> None:
    """The window itself, not an emulated viewport: a second emulated size reads to the editor as a zoom."""
    window = browser.devtools.call("Browser.getWindowForTarget", targetId=target)["windowId"]
    browser.devtools.call("Browser.setWindowBounds", windowId=window, bounds={"width": width, "height": height})


def clip(box: dict, view: dict) -> dict:
    """The box with PAD of the sheet's background around it, never past the sheet's view into the editor."""
    left, top = max(box["left"] - PAD, view["left"]), max(box["top"] - PAD, view["top"])
    return {"x": left, "y": top, "width": min(box["right"] + PAD, view["right"]) - left,
            "height": min(box["bottom"] + PAD, view["bottom"]) - top, "scale": 1}


def sids(obj) -> int:
    """The sids in a sheet's JSON: its events, conditions, actions and variables."""
    if isinstance(obj, dict):
        return ("sid" in obj) + sum(sids(v) for v in obj.values())
    return sum(sids(v) for v in obj) if isinstance(obj, list) else 0


def group_titles(events: list, inside: str | None = None, into: dict | None = None) -> dict:
    """The groups of a sheet by title: the key None lists the groups directly in the sheet, and each
    title the groups directly inside that group."""
    into = {None: []} if into is None else into
    for ev in events:
        title = ev.get("title", "") if ev.get("eventType") == "group" else None
        if title is not None:
            into[inside].append(title)
            into.setdefault(title, [])
        group_titles(ev.get("children", []), inside if title is None else title, into)
    return into


def room(most: int, scale: int, editor: float) -> float:
    """The CSS px of the sheet that one picture holds at scale: the tallest window, less the editor's bars
    and the PAD above and below the picture."""
    return most // scale - editor - 2 * PAD


def too_tall(what: str, height: float, scale: int, most: int, editor: float, groups: list[str]) -> str:
    """Why a picture is not taken, and what to take instead."""
    shown = " ".join(f"--group {c3.quoted(g)}" for g in groups[:8]) + (f" and {len(groups) - 8} more"
                                                                      if len(groups) > 8 else "")
    return (f"{what} is {height:.0f} px tall, and a picture at --scale {scale} holds {room(most, scale, editor):.0f} "
            f"px: the browser captures a window up to {most} device px tall. Take "
            + ("it at --scale 1, or " if scale > 1 and height <= room(most, 1, editor) else "")
            + (f"its groups one at a time: {shown}" if groups else
               "a part of it: put its events into smaller groups in the editor, then take each with --group"))


def fit_columns(page: oe.DevTools, lines: list[str], what: str, wait: float, top: float | None = None,
                bottom: float | None = None) -> dict:
    """Fit both columns to the cells between top and bottom, or to the whole sheet, and say how wide."""
    fit = page.evaluate(f"({FIT_JS})({COND_CAP}, {ACT_CAP}, {'null' if top is None else top}, "
                        f"{'null' if bottom is None else bottom}, {AIR})", wait=3 * wait)
    lines.append(f"columns of {what}: conditions {fit['cond']} px, actions {fit['act']} px"
                 + "".join(f"; some {kind} still wrap at the cap of {cap} px"
                           for kind, cap, wraps in (("conditions", COND_CAP, fit["condWraps"]),
                                                    ("actions", ACT_CAP, fit["actWraps"]),
                                                    ("comments", ACT_CAP, fit["commentWraps"])) if wraps))
    return fit


def open_sheet(page: oe.DevTools, sheet: str, out: Path, wait: float) -> str | None:
    """Double-click the sheet in the Project Bar until it shows; why it did not, or None."""
    # A double-click that lands while the editor is still settling opens nothing; it is tried again.
    deadline = time.monotonic() + OPEN_WAIT
    while not page.evaluate(SHOWN_JS, wait=wait):
        if time.monotonic() > deadline:
            seen = out / "failed.png"
            seen.write_bytes(base64.b64decode(page.call("Page.captureScreenshot", format="png")["data"]))
            return f"the event sheet {sheet} did not show {OPEN_WAIT} s after its double-click; the editor then: {seen}"
        close_zoom_notice(page, 0.6, wait)
        at = page.evaluate(f"({ITEM_JS})({sheet!r})", wait=wait)
        if not at or at.get("hidden"):
            return f"the Project Bar shows no event sheet {sheet!r}" + (" (it is in a collapsed folder)" if at else "")
        click(page, at["x"], at["y"], count=2)
        for _ in range(12):
            time.sleep(0.3)
            if page.evaluate(SHOWN_JS, wait=wait):
                break
    return None


def take(browser: oe.Browser, target: str, page: oe.DevTools, sheet: str, title: str | None, name: str,
         scale: int, most: int, inside: list[str], wait: float, run: dict) -> None:
    """One picture: the whole sheet, or the group with this title. Fit the columns to it, scroll the view
    to put it at the top, and grow the window to its height, up to `most` device px."""
    what = f"group {title}" if title else f"the sheet {sheet}"
    measure = f"({BOX_JS})({'null' if title is None else repr(title)})"
    run["doing"] = f"measuring {what}"
    found = page.evaluate(measure, wait=wait)
    if not found["box"]:
        run["missing"].append(title)
        run["lines"].append(f"no group {title!r} in {sheet}; the titles are as the sheet spells them")
        return
    run["doing"] = f"fitting the columns of {what}"
    top, bottom = (found["box"]["top"], found["box"]["bottom"]) if title else (None, None)
    fit_columns(page, run["lines"], what, wait, top, bottom)
    found = page.evaluate(measure, wait=wait)
    box, view = found["box"], found["view"]
    editor = found["inner"] - (view["bottom"] - view["top"])     # the editor's bars above and below the view
    height = box["bottom"] - box["top"]
    if height > room(most, scale, editor):
        run["errors"].append(too_tall(what, height, scale, most, editor, inside))
        return
    run["doing"] = f"growing the window to {what}"
    page.evaluate(f"({SCROLL_JS})({box['top'] - PAD - view['top']})", wait=wait)
    resize(browser, target, WIDTH, max(HEIGHT, math.ceil(found["outer"] - found["inner"] + editor + height + 2 * PAD)))
    time.sleep(1)
    close_zoom_notice(page, 0.6, wait)
    found = page.evaluate(measure, wait=wait)
    box, view = found["box"], found["view"]
    if box["right"] > view["right"]:
        run["errors"].append(f"the columns of {what} end at {box['right']:.0f} px, past the sheet's view at "
                             f"{view['right']:.0f}: the picture would show the editor's panes; raise WIDTH")
        return
    page.evaluate(f"({UNCOVER_JS})({box!r})", wait=wait)
    area = clip(box, view)
    pixels = area["width"] * area["height"] * scale * scale
    run["doing"] = f"capturing {name} ({pixels / 1e6:.0f} million pixels)"
    shot = page.call("Page.captureScreenshot", wait=oe.CALL + PIXEL_WAIT * pixels / 1e6, format="png", clip=area)
    path = run["out"] / name
    path.write_bytes(base64.b64decode(shot["data"]))
    run["lines"].append(f"wrote {path}, {round(area['width'] * scale)} x {round(area['height'] * scale)}")


def capture(browser: oe.Browser, target: str, page: oe.DevTools, sheet: str, groups: list[str], scale: int,
            out: Path, titles: dict, wait: float) -> dict:
    """What open_one() runs once the project opened: the pictures, and the lines to print. titles are
    the sheet's groups as group_titles() gives them; wait is the seconds a call into the editor may take."""
    run = {"lines": [], "errors": [], "missing": [], "out": out, "doing": f"opening the sheet {sheet}"}
    try:
        page.call("Emulation.setDeviceMetricsOverride", width=0, height=0, deviceScaleFactor=scale, mobile=False)
        resize(browser, target, WIDTH, HEIGHT)
        close_zoom_notice(page, wait=wait)
        refused = open_sheet(page, sheet, out, wait)
        if refused:
            run["errors"].append(refused)
            return run
        page.evaluate(STYLE_JS, wait=wait)
        most = min(page.evaluate(GPU_JS, wait=wait) or NO_GPU, MOST)
        for title in groups or [None]:
            name = f"{sheet} - {title}@{scale}x.png" if title else f"{sheet}@{scale}x.png"
            take(browser, target, page, sheet, title, name, scale, most, titles.get(title, []), wait, run)
    except oe.NoAnswer as e:
        smaller = ("" if run["doing"].startswith("opening") else "; if it stops at the same step, take smaller "
                   "pictures: a lower --scale, or one group at a time with --group")
        run["errors"].append(f"the editor did not answer while {run['doing']}: {e}. Run again{smaller}")
    except oe.DevToolsError as e:
        run["errors"].append(f"the editor refused a call while {run['doing']}: {e}")
    return run


def main() -> int:
    c3.utf8_output()
    ap = c3.argparse.ArgumentParser(description=__doc__, epilog=EPILOG,
                                    formatter_class=c3.argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", nargs="?", metavar="SHEET",
                    help="the event sheet, as the Project Bar names it (default: the project's only or first sheet)")
    ap.add_argument("--group", action="append", default=[], metavar="TITLE",
                    help="a picture of this group alone, by its title, instead of the whole sheet; repeat for more")
    ap.add_argument("--scale", type=int, default=2, choices=(1, 2, 3),
                    help="device pixels per CSS pixel: 2 stays sharp at half size, 1 is the size the editor "
                         "shows (default 2)")
    ap.add_argument("--dark", action="store_true",
                    help="draw the sheet in the default theme's dark mode instead of its light mode")
    ap.add_argument("--out", type=Path, metavar="FOLDER",
                    help="where the pictures go (default: .build/sheets in the project)")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--release", metavar="rNNN", help="open in this release of the editor, as open_in_editor.py does")
    ap.add_argument("--browser", metavar="EXE",
                    help="the Chromium-based browser to start (default: Edge, Chrome or Chromium where installed)")
    ap.add_argument("--profile", type=Path, metavar="FOLDER",
                    help="keep the browser profile in FOLDER/editor-<browser> instead of the project's .tmp/")
    args = ap.parse_args()

    project = c3.find_project(args.project)
    if not project or not (project / "project.c3proj").is_file():
        print(f"no project.c3proj in {args.project or Path.cwd()} or above it; run this in the project folder or "
              f"pass --project <folder>", file=sys.stderr)
        return 2
    files = c3.listed_files(project, c3.load(project / "project.c3proj"), "eventSheets")
    sheets = list(files)
    if not sheets:
        print(f"{project} has no event sheet to take a picture of", file=sys.stderr)
        return 2
    sheet = args.sheet or sheets[0]
    if sheet not in sheets:
        print(f"no event sheet {sheet!r} in {project.name}{c3.closest(sheet, sheets)}; its sheets are "
              f"{', '.join(sheets)}")
        return 1
    events = c3.load(files[sheet]).get("events", []) if files[sheet] else []
    titles = group_titles(events)
    named = [t for t in titles if t is not None]
    for title in args.group:
        if events and title not in titles:
            print(f"no group {title!r} in {sheet}{c3.closest(title, named)}; its groups are "
                  f"{', '.join(named) or 'none'}")
            return 1
    wait = oe.CALL + SID_WAIT * sids(events)
    exe = args.browser or oe.browser_path()
    if not exe:
        print("no Edge, Chrome or Chromium found here, so no picture; pass one with --browser, or open the sheet "
              "in the editor and take the screenshot there", file=sys.stderr)
        return 3
    if not args.out:
        pp.ignored_folder(project / pp.BUILD)
    out = (args.out or (project / pp.BUILD / "sheets")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    editor = f"{oe.EDITOR}{args.release.strip('/')}/" if args.release else oe.EDITOR
    profile = (args.profile.resolve() if args.profile else oe.scratch(project)) / f"editor-{Path(exe).stem.lower()}"
    try:
        browser = oe.Browser(exe, profile, headed=False,
                              extra=(*BROWSER_ARGS, SCHEME_ARG.format(0 if args.dark else 1)))
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    try:
        result = oe.open_one(browser, editor, project, profile / "project-sheet.c3p", None, bool(args.release),
                             lambda b, t, p: capture(b, t, p, sheet, args.group, args.scale, out,
                                                             titles, wait))
    except oe.EditorNotLoaded as e:
        print(f"the editor did not load: {e}. Check the network connection and --release, and run again.",
              file=sys.stderr)
        return 2
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    finally:
        browser.close()
    print("\n".join(oe.report({k: v for k, v in result.items() if k != "preview"})))
    shot = result.get("preview") or {}
    for line in shot.get("lines", []):
        print(f"  {line}")
    for error in shot.get("errors", []):
        print(f"  failed: {error}")
    if result["status"] != "opened":
        print(oe.NEXT)
        return 1
    return 1 if shot.get("errors") or shot.get("missing") else 0


if __name__ == "__main__":
    sys.exit(main())
