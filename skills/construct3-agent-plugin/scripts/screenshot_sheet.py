"""Screenshot an event sheet as the Construct 3 editor shows it, cropped to the sheet, for a forum post,
a bug report or a page of documentation.

    python scripts/screenshot_sheet.py [SHEET] [--group TITLE ...] [--scale 2] [--out FOLDER]
                                       [--project FOLDER] [--release rNNN] [--browser EXE] [--profile FOLDER]

It opens the project in the editor as open_in_editor.py does, opens SHEET from the Project Bar, and
captures it in English with the editor's own icons and colours. Three things make the picture read
well outside the editor:

- The conditions column is as wide as the longest condition, and the actions column as wide as the
  longest action, each up to a cap, so that every line the caps allow stays on one line and the
  picture has no empty band on its right. The conditions column is the width the divider between the
  columns sets in the editor; the project's files are not changed.
- Text is drawn with grayscale antialiasing and without hinting, close to macOS. The coloured fringes
  of Windows' subpixel text turn into halos once a forum or a viewer scales the picture.
- The window grows to the sheet's height, so a long sheet is one picture, and anything the editor
  shows over the sheet, a notice or a banner, is hidden first.

Each picture is written to .build/sheets/ of the project, a folder Git ignores: <SHEET>@<scale>x.png
for the whole sheet and <SHEET> - <group>@<scale>x.png for each --group. At --scale 2 a picture stays
sharp when it is shown at half its size, which is how most forums and viewers show it.
"""
import base64
import sys
import time
from pathlib import Path

import c3project as c3
import open_in_editor as oe
import pack_project as pp

EPILOG = """examples:
  python scripts/screenshot_sheet.py                              the project's only or first sheet
  python scripts/screenshot_sheet.py Game --group Targeting       the sheet, and the group Targeting alone
  python scripts/screenshot_sheet.py Game --scale 1 --out shots   at the size the editor shows it, into shots/

output:
  opened   <project>  (<window title>, <the editor it opened in>)
  columns of the sheet: conditions 474 px, actions 654 px
  wrote .build/sheets/Game@2x.png, 2360 x 1202
  columns of group Targeting: conditions 474 px, actions 324 px
  wrote .build/sheets/Game - Targeting@2x.png, 1696 x 490

exit codes: 0 every picture written; 1 the editor refused the project, or a sheet or group was not
found in it; 2 the flags, the project or the browser could not be used; 3 no Edge, Chrome or Chromium here"""

WIDTH = 2600            # CSS px of the window: room for both columns at their caps beside the editor's panes
HEIGHT = 1000           # the window before it grows to the sheet
COND_CAP = 600          # the widest the conditions column grows to; a longer condition wraps
ACT_CAP = 900           # the same for the actions column
TALLEST = 30000         # CSS px; Chromium draws no screenshot much taller than this at scale 2
PAD = 10                # CSS px of the sheet's own background around a picture
OPEN_WAIT = 15          # seconds for a sheet to show, its double-click repeated; it takes about 1

# Grayscale antialiasing, no LCD subpixel colour; the CSS below turns hinting off and thickens stems a
# little, as macOS draws text. The editor follows the browser's language, and the pictures are English.
BROWSER_ARGS = ("--disable-lcd-text", "--lang=en-US")
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
FIT_JS = r"""(async (condCap, actCap, top, bottom) => {
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
  cond = c + 8; act = a + 8; await apply();       // a little air after the longest line
  return {margin, cond, act, condWraps, actWraps, commentWraps};
})""" % ROOT_JS
# The sheet's box and, for each group title asked for, the box from its header to the row that adds an
# event to it, in CSS px of the page.
BOXES_JS = r"""(titles => {
  const body = %s, root = body.querySelector('div.eventSheetRootView'), r = root.getBoundingClientRect();
  const cols = getComputedStyle(root).gridTemplateColumns.split(' ').map(parseFloat);
  const right = r.left + cols.reduce((a, b) => a + b, 0) + parseFloat(getComputedStyle(root).paddingLeft);
  const leaves = [...root.querySelectorAll('*')].filter(e => e.children.length === 0);
  const rows = [...root.children].filter(e => e.getBoundingClientRect().height > 0);
  const last = rows.filter(e => !/^Add event$/.test(e.textContent.trim())).pop() || root;
  const out = {sheet: {left: r.left, top: r.top, right, bottom: last.getBoundingClientRect().bottom},
               view: (v => ({left: v.getBoundingClientRect().left, top: v.getBoundingClientRect().top,
                             right: v.getBoundingClientRect().left + v.clientWidth}))(body),
               height: body.scrollHeight, shown: body.clientHeight, groups: {}};
  for (const t of titles) {
    const head = leaves.find(e => e.textContent.trim() === t && e.closest('[class*=group i]'));
    const end = leaves.find(e => e.textContent.trim() === "Add event to '" + t + "'");
    out.groups[t] = head && end ? {left: r.left, top: head.closest('[class*=group i]').getBoundingClientRect().top,
                                   right, bottom: end.getBoundingClientRect().bottom} : null;
  }
  return out; })""" % BODY_JS
# Hide whatever the editor draws over the box (a notice, a banner, a tooltip): the element under each
# point of a grid that is not inside the sheet is hidden, up to its child of the body.
UNCOVER_JS = r"""(b => { const pane = %s; let hidden = 0;
  for (let x = b.left + 4; x < b.right; x += 40) for (let y = b.top + 4; y < b.bottom; y += 40) {
    let e = document.elementFromPoint(x, y);
    if (!e || pane.contains(e)) continue;
    while (e.parentElement && e.parentElement !== document.body) e = e.parentElement;
    if (!e.contains(pane)) { e.style.visibility = 'hidden'; hidden++; } }
  return hidden; })""" % PANE_JS


def click(page: oe.DevTools, x: float, y: float, count: int = 1) -> None:
    page.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    for n in range(1, count + 1):
        for kind in ("mousePressed", "mouseReleased"):
            page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=n)


def close_zoom_notice(page: oe.DevTools, patience: float = 2) -> None:
    """The editor says the zoom level changed when the device scale does, and its dialog blocks the
    Project Bar; OK closes it. The scale is the screenshot's, not a zoom of the user's."""
    deadline = time.monotonic() + patience
    while time.monotonic() < deadline:
        at = page.evaluate(ZOOM_JS)
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
            "height": box["bottom"] + PAD - top, "scale": 1}


def fit_columns(page: oe.DevTools, lines: list[str], what: str, top: float | None = None,
                bottom: float | None = None) -> dict:
    """Fit both columns to the cells between top and bottom, or to the whole sheet, and say how wide."""
    fit = page.evaluate(f"({FIT_JS})({COND_CAP}, {ACT_CAP}, {'null' if top is None else top}, "
                        f"{'null' if bottom is None else bottom})", wait=60)
    lines.append(f"columns of {what}: conditions {fit['cond']} px, actions {fit['act']} px"
                 + "".join(f"; some {kind} still wrap at the cap of {cap} px"
                           for kind, cap, wraps in (("conditions", COND_CAP, fit["condWraps"]),
                                                    ("actions", ACT_CAP, fit["actWraps"]),
                                                    ("comments", ACT_CAP, fit["commentWraps"])) if wraps))
    return fit


def capture(browser: oe.Browser, target: str, page: oe.DevTools, sheet: str, groups: list[str], scale: int,
            out: Path) -> dict:
    """What open_one() runs once the project opened: the pictures, and the lines to print."""
    lines: list[str] = []
    page.call("Emulation.setDeviceMetricsOverride", width=0, height=0, deviceScaleFactor=scale, mobile=False)
    resize(browser, target, WIDTH, HEIGHT)
    close_zoom_notice(page)
    # A double-click that lands while the editor is still settling opens nothing; it is tried again.
    deadline = time.monotonic() + OPEN_WAIT
    while not page.evaluate(SHOWN_JS):
        if time.monotonic() > deadline:
            seen = out / "failed.png"
            seen.write_bytes(base64.b64decode(page.call("Page.captureScreenshot", format="png")["data"]))
            return {"errors": [f"the event sheet {sheet} did not show {OPEN_WAIT} s after its double-click; the "
                               f"editor then: {seen}"]}
        close_zoom_notice(page, 0.6)
        at = page.evaluate(f"({ITEM_JS})({sheet!r})")
        if not at or at.get("hidden"):
            return {"errors": [f"the Project Bar shows no event sheet {sheet!r}"
                               + (" (it is in a collapsed folder)" if at else "")]}
        click(page, at["x"], at["y"], count=2)
        for _ in range(12):
            time.sleep(0.3)
            if page.evaluate(SHOWN_JS):
                break
    page.evaluate(STYLE_JS)
    fit_columns(page, lines, "the sheet")
    boxes = page.evaluate(f"({BOXES_JS})({groups!r})")
    if boxes["height"] > boxes["shown"]:
        grow = min(boxes["height"], TALLEST) - boxes["shown"] + 2 * PAD
        inner = page.evaluate("[outerHeight - innerHeight, innerHeight]")
        resize(browser, target, WIDTH, inner[0] + inner[1] + grow)
        time.sleep(1)
        close_zoom_notice(page, 0.6)
        boxes = page.evaluate(f"({BOXES_JS})({groups!r})")
    if boxes["sheet"]["bottom"] - boxes["sheet"]["top"] > TALLEST:
        lines.append(f"the sheet is taller than {TALLEST} px and its picture stops there; take its groups "
                     f"one at a time with --group")
    wanted = [(f"{sheet}@{scale}x.png", None)]
    for title in groups:
        if boxes["groups"][title]:
            wanted.append((f"{sheet} - {title}@{scale}x.png", title))
        else:
            lines.append(f"no group {title!r} in {sheet}; the titles are as the sheet spells them")
    for name, title in wanted:
        if title:       # the columns fitted to this group's own conditions and actions
            area = boxes["groups"][title]
            fit_columns(page, lines, f"group {title}", area["top"], area["bottom"])
            boxes = page.evaluate(f"({BOXES_JS})({groups!r})")
        box = boxes["groups"][title] if title else boxes["sheet"]
        if box["right"] > boxes["view"]["right"]:
            return {"errors": [f"the columns end at {box['right']:.0f} px, past the sheet's view at "
                               f"{boxes['view']['right']:.0f}: the picture would show the editor's panes; raise WIDTH"]}
        page.evaluate(f"({UNCOVER_JS})({box!r})")
        area = clip(box, boxes["view"])
        shot = page.call("Page.captureScreenshot", wait=60, format="png", clip=area)
        path = out / name
        path.write_bytes(base64.b64decode(shot["data"]))
        lines.append(f"wrote {path}, {round(area['width'] * scale)} x {round(area['height'] * scale)}")
    return {"errors": [], "lines": lines, "missing": [t for t in groups if not boxes["groups"][t]]}


def main() -> int:
    c3.utf8_output()
    ap = c3.argparse.ArgumentParser(description=__doc__, epilog=EPILOG,
                                    formatter_class=c3.argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", nargs="?", metavar="SHEET",
                    help="the event sheet, as the Project Bar names it (default: the project's only or first sheet)")
    ap.add_argument("--group", action="append", default=[], metavar="TITLE",
                    help="also a picture of this group alone, by its title; repeat for more")
    ap.add_argument("--scale", type=int, default=2, choices=(1, 2, 3),
                    help="device pixels per CSS pixel: 2 stays sharp at half size, 1 is the size the editor "
                         "shows (default 2)")
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
    sheets = [name for name, _ in c3.folder_items(c3.load(project / "project.c3proj").get("eventSheets", {}))]
    if not sheets:
        print(f"{project} has no event sheet to take a picture of", file=sys.stderr)
        return 2
    sheet = args.sheet or sheets[0]
    if sheet not in sheets:
        print(f"no event sheet {sheet!r} in {project.name}{c3.closest(sheet, sheets)}; its sheets are "
              f"{', '.join(sheets)}")
        return 1
    exe = args.browser or oe.browser_path()
    if not exe:
        print("no Edge, Chrome or Chromium found here, so no picture; pass one with --browser, or open the sheet "
              "in the editor and take the screenshot there", file=sys.stderr)
        return 3
    out = (args.out or (project / pp.BUILD / "sheets")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.out and not (project / pp.BUILD / ".gitignore").exists():
        (project / pp.BUILD / ".gitignore").write_text("*\n", encoding="utf-8")
    editor = f"{oe.EDITOR}{args.release.strip('/')}/" if args.release else oe.EDITOR
    profile = (args.profile.resolve() if args.profile else oe.scratch(project)) / f"editor-{Path(exe).stem.lower()}"
    try:
        browser = oe.Browser(exe, profile, headed=False, extra=BROWSER_ARGS)
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    try:
        result = oe.open_one(browser, editor, project, profile / "project-sheet.c3p", None, bool(args.release),
                             lambda b, t, p: capture(b, t, p, sheet, args.group, args.scale, out))
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
