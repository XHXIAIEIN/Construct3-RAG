"""Export a folder project to Web (HTML5) in the Construct 3 editor and unpack it into a folder.

    python scripts/export_project.py [--to FOLDER] [--version X | --bump] [--attach PORT|URL|FILE]
                                     [--slow] [--project FOLDER] [--dry-run]

The Free edition does not export a project over its limits, so the editor needs an
account with a subscription. The editor keeps its login in the open page only: it is
gone when the browser closes or the page reloads. The script therefore drives a
headed browser on a profile of its own, .tmp/export-<browser> of the main clone,
and waits there for the user to log in when the editor shows Guest or Free edition;
a GitHub or Google login stays in that profile, so logging in again is a click or
two. It restores the window and keeps the page active while it drives it, so the
export runs with other windows over it. After the export it closes the project and
minimizes the window, which keeps the page and its login for the next run. A run that
stops on an error closes the copy it handed to the editor, without saving, and the
dialogs over it; an editor that crashed shows a report whose one way out is Restart,
which the script presses, and the reloaded editor may ask for the login again.
--attach uses a browser of the user's own instead, already logged in.

The project goes to the editor of the release that saved it, savedWithRelease of
project.c3proj, since an older one refuses it, with the files the editor reads, as
pack_project.py packs them. The editor exports a zip with
Offline support, Deduplicate images and Optimize images on and the other
options as it remembers them; the zip replaces
the contents of --to, by default .build/web of the project, a folder Git ignores. The export carries the version given by --version or
--bump, else the project's, with Auto-increment version off in the copy handed to
the editor, and that version is written into project.c3proj when it differs. The
copy also sets Use worker to Auto, which lets the engine decide, whatever the
project sets for preview.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import c3project as c3
import open_in_editor as oe
import pack_project as pp

EPILOG = """examples:
  python scripts/export_project.py --to export/web --bump
  python scripts/export_project.py --to export/web --version 1.2.0.0
  python scripts/export_project.py --to export/web --bump --attach 9222
  python scripts/export_project.py --to export/web --bump --dry-run

--attach uses a Chrome or Edge the user has open: turn remote debugging on at
chrome://inspect/#remote-debugging (edge://inspect/#remote-debugging) and pass the
address it shows, a port, an http:// or ws:// address, or the DevToolsActivePort
file of the browser's user data folder. Given a port that does not answer
/json/version, as a browser debugged from that page does not, the script looks for
the DevToolsActivePort with that port in the user data folders of Chrome, Chromium
and Edge. It works in an editor tab that shows the start page and is new enough,
never in one with a project open, which may hold the user's unsaved work; without
one it opens a tab and closes it after the export, or when the run stops. A tab of the
user's is left on the start page either way.

output:
  logged in as <name>, exporting <version>
  exported <version> into <folder>, runtime in the worker|page; project.c3proj version <version>

exit codes: 0 exported; 1 the export did not finish: no subscription within 5 minutes,
the project did not open, or a dialog stopped it; the copy is closed, the window is left
open, and a run again goes on in it; 2 no project, a flag that cannot be used, or the
editor did not load; 3 no Edge, Chrome or Chromium here
"""

LOGIN_WAIT = 300        # seconds the user has to log in
EXPORT_WAIT = 300       # seconds the editor has to export
UI_WAIT = 30            # seconds a menu item or a dialog has to appear
CHUNK = 3 << 20         # bytes of the zip read from the page per call
SLOW = 3                # how much longer the pauses between clicks are with --slow or after a missed step
pace = 1.0


class Stop(Exception):
    """The export did not finish; the message says what the user sees and does next."""


class Missed(Stop):
    """A menu item or a dialog did not come, as when the editor is slower than the pauses."""


def pause(seconds: float) -> None:
    time.sleep(seconds * pace)


# --- the browser ----------------------------------------------------------------------
def scratch(project: Path) -> Path:
    """.tmp of the main clone, so that every worktree of a project uses the same window."""
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=project,
                            capture_output=True, text=True).stdout.strip()
    return oe.scratch(Path(common).parent if common else project)


def own_browser(project: Path, exe: str) -> oe.Browser:
    """A headed browser on a profile of this script's own. One still running on it is the window
    a run before left, logged in: it is taken over, not restarted."""
    return oe.Browser(exe, scratch(project) / f"export-{Path(exe).stem.lower()}", headed=True)


def editor_url(project: Path) -> str:
    """The editor of the release that saved the project; the editor's root may be an older one."""
    major, minor = divmod(oe.saved_release(project), 100)
    return f"{oe.EDITOR}r{major}{f'-{minor}' if minor else ''}/" if major else oe.EDITOR


def own_page(b: oe.Browser, url: str) -> tuple[str, oe.DevTools]:
    """The editor page a run before left in the browser, with its login, else a new one.
    The login lives in the page, so it is never reloaded."""
    for t in b.devtools.call("Target.getTargets")["targetInfos"]:
        if t["type"] == "page" and t["url"].startswith(url):
            page = oe.DevTools(f"ws://127.0.0.1:{b.port}/devtools/page/{t['targetId']}")
            oe.keep_active(page)
            return t["targetId"], page
    target, page = b.page(url)
    oe.load(page, url)
    return target, page


def show_window(b: oe.Browser, target: str, state: str) -> None:
    """normal or minimized. A minimized window draws nothing, so clicks miss what the editor
    shows next: it is restored before an export, and minimized after it, out of the way."""
    window = b.devtools.call("Browser.getWindowForTarget", targetId=target)["windowId"]
    b.devtools.call("Browser.setWindowBounds", windowId=window, bounds={"windowState": state})


# --attach with a port alone: where Chrome, Chromium and Edge keep DevToolsActivePort
USER_DATA = [Path.home() / "AppData/Local" / d / "User Data" for d in (
    "Google/Chrome", "Google/Chrome Beta", "Google/Chrome Dev", "Google/Chrome SxS", "Chromium",
    "Microsoft/Edge", "Microsoft/Edge Beta", "Microsoft/Edge Dev", "Microsoft/Edge SxS")] + \
    [Path.home() / "Library/Application Support" / d for d in (
        "Google/Chrome", "Google/Chrome Beta", "Google/Chrome Canary", "Chromium", "Microsoft Edge")] + \
    [Path.home() / ".config" / d for d in ("google-chrome", "google-chrome-beta", "chromium", "microsoft-edge")]


ALLOW_WAIT = 60     # seconds the user has to allow remote debugging when the browser asks


def connect(url: str) -> oe.DevTools:
    """A browser debugged from chrome://inspect holds the connection until the user allows it."""
    print("if the browser asks whether to allow remote debugging, allow it", flush=True)
    try:
        return oe.DevTools(url, ALLOW_WAIT)
    except OSError as e:
        raise ValueError(f"no answer from {url} in {ALLOW_WAIT} seconds ({e}); allow remote debugging in the "
                         f"browser and run again") from e


def attach(spec: str) -> oe.DevTools:
    """The browser-wide connection to a browser the user has open."""
    if Path(spec).is_file():        # DevToolsActivePort: the port, then the browser's ws path
        port, path = Path(spec).read_text().split()[:2]
        return connect(f"ws://127.0.0.1:{port}{path}")
    if spec.startswith("ws://"):
        return connect(spec)
    found = re.fullmatch(r"(?:https?://[^:/]+:)?(\d+)/?", spec)
    if not found:
        raise ValueError(f"--attach {spec} is neither a port, an http:// or ws:// address, nor a "
                         f"DevToolsActivePort file that exists")
    port = found.group(1)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as r:
            return connect(json.load(r)["webSocketDebuggerUrl"])
    except OSError:     # remote debugging turned on at chrome://inspect does not answer it
        pass
    for active in (d / "DevToolsActivePort" for d in USER_DATA):
        if active.is_file() and active.read_text().split()[:1] == [port]:
            return attach(str(active))
    raise ValueError(f"nothing answers at 127.0.0.1:{port}, and no DevToolsActivePort of the usual browsers "
                     f"names that port; pass --attach the DevToolsActivePort file of the browser's user data folder")


class SessionPage:
    """A tab of the user's browser, driven through a session on the browser-wide connection:
    a browser debugged from chrome://inspect refuses a connection to the tab itself (403).
    It has the call and evaluate of oe.DevTools."""

    def __init__(self, devtools: oe.DevTools, target: str) -> None:
        self.devtools, self.target = devtools, target
        self.session = devtools.call("Target.attachToTarget", targetId=target, flatten=True)["sessionId"]

    def call(self, method: str, wait: float = oe.CALL, **params) -> dict:
        return self.devtools.call(method, wait, self.session, **params)

    def evaluate(self, expression: str, by_value: bool = True, wait: float = oe.CALL):
        return self.devtools.evaluate(expression, by_value, wait, self.session)


# The start page's title begins with one of these; with a project open it is "<name> - Construct 3"
START_TITLES = ("Game Making Software", "Construct 3")


def attached_page(devtools: oe.DevTools, project: Path) -> tuple[SessionPage, bool]:
    """An editor tab of the user's browser on the start page and of a release that opens the project,
    else a new tab; and whether the script opened it."""
    saved = oe.saved_release(project)
    for t in devtools.call("Target.getTargets")["targetInfos"]:
        if t["type"] != "page" or not t["url"].startswith(oe.EDITOR) or not t["title"].startswith(START_TITLES):
            continue
        page = SessionPage(devtools, t["targetId"])
        oe.keep_active(page)
        major, minor = (page.evaluate(oe.RELEASE_JS) + [0, 0])[:2]
        if major * 100 + minor >= saved:
            return page, False
        devtools.call("Target.detachFromTarget", sessionId=page.session)
    url = editor_url(project)
    page = SessionPage(devtools, devtools.call("Target.createTarget", url=url, newWindow=True)["targetId"])
    oe.keep_active(page)
    oe.load(page, url)
    return page, True


# --- the editor -----------------------------------------------------------------------
# The account at the top right: the user's name, or Guest. Without a subscription a
# "Free edition" badge stands before it, which a subscription hides (display: none; its
# text stays). An editor that has just loaded shows the last name with the badge hidden
# until the server answers, so only a state that holds for some seconds counts.
ACCOUNT_JS = r"""(() => {
  const name = document.getElementById('userAccountWrap')?.innerText.trim().split('\n').pop() || '';
  const badge = document.getElementById('userLicenseType');
  return {name, paid: !!badge && getComputedStyle(badge).display === 'none' && !['', '...', 'Guest'].includes(name)};
})()"""


def account(page) -> dict:
    try:
        return page.evaluate(ACCOUNT_JS) or {"name": "", "paid": False}
    except oe.DevToolsError:    # the page reloads as the user logs in
        return {"name": "", "paid": False}


def settled_account(page, seconds: float) -> dict:
    last, since = account(page), time.time()
    while time.time() - since < seconds:
        time.sleep(1)
        now = account(page)
        if now != last:
            last, since = now, time.time()
    return last


def wait_for_login(page) -> str:
    who = settled_account(page, 5)
    if not who["paid"]:
        print("log in to a Construct account with a subscription in the editor window: Menu > Account > "
              "Log in; the export goes on once the editor shows the name without Free edition", flush=True)
        deadline = time.time() + LOGIN_WAIT
        while not who["paid"]:
            if time.time() > deadline:
                raise Stop(f"no account with a subscription in {LOGIN_WAIT // 60} minutes (the editor shows "
                           f"{who['name'] or 'nothing'}); log in in the window, which stays open, and run again")
            time.sleep(2)
            who = settled_account(page, 5) if account(page)["paid"] else account(page)
    return who["name"]


def click(page, x: float, y: float) -> None:
    page.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    pause(0.1)
    for kind in ("mousePressed", "mouseReleased"):
        page.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)


# The centre of the visible element whose first line of text is `text`: a menu item, or
# anything in the topmost dialog
FIND_JS = r"""((scope, text) => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const dialog = [...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog').pop();
  const pool = scope === 'menu' ? document.querySelectorAll('ui-menuitem') : dialog ? dialog.querySelectorAll('*') : [];
  const e = [...pool].filter(vis).filter(e => (e.innerText || '').trim().split('\n')[0] === text).pop();
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return [r.x + r.width / 2, r.y + r.height / 2];
})"""

DIALOG_JS = r"""(() => {
  const d = [...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog').pop();
  return d ? {id: d.id, text: d.innerText.trim().replace(/\s+/g, ' ').slice(0, 600)} : null;
})()"""

# Closes what a run that stopped left open
DISMISS_JS = r"""[...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog')
  .forEach(d => d.querySelector('ui-close-button, .cancelButton, .okButton')?.click())"""


def press(page, scope: str, text: str, settle: float = 0.3) -> None:
    deadline = time.time() + UI_WAIT
    while time.time() < deadline:
        at = page.evaluate(f"{FIND_JS}({json.dumps(scope)}, {json.dumps(text)})")
        if at:
            click(page, *at)
            pause(settle)
            return
        time.sleep(0.2)
    raise Missed(f"no '{text}' in the editor; it shows {json.dumps(page.evaluate(DIALOG_JS))}")


def open_menu(page) -> None:
    at = page.evaluate("(() => { const r = document.getElementById('mainMenuButton').getBoundingClientRect(); "
                       "return [r.x + r.width / 2, r.y + r.height / 2]; })()")
    click(page, *at)
    pause(0.3)


def project_title(project: Path) -> str:
    """The start of the window title while the project is open."""
    return json.loads((project / "project.c3proj").read_text(encoding="utf-8-sig"))["name"] + " - "


def project_open(page) -> bool:
    return not page.evaluate("document.title").startswith(START_TITLES)


CRASH_JS = "!!document.querySelector('#crashReportDialog[open]')"
RESTART_WAIT = 60       # seconds the editor has to load again after Restart


def restart(page) -> None:
    """Press Restart on the editor's crash report, the report's one way out: a crashed editor shows
    it again as soon as the menu opens. The editor reloads after the page's own question about
    leaving, which is answered Leave, since the project is the script's copy."""
    print("the editor showed its crash report over the copy; pressing its Restart, which reloads the "
          "editor: log in there again if it asks", flush=True)
    page.call("Page.enable")        # without it the question is not seen
    page.evaluate(DISMISS_JS)       # a dialog over the report, such as a preview that failed
    before = page.evaluate("performance.timeOrigin")
    page.evaluate("setTimeout(() => document.querySelector('#crashReportDialog .reloadButton').click(), 0), 1")
    deadline = time.time() + RESTART_WAIT
    while time.time() < deadline:
        try:
            page.call("Page.handleJavaScriptDialog", wait=2, accept=True)
        except oe.DevToolsError:    # not asked yet, or answered
            pass
        try:
            origin, ready = page.evaluate("[performance.timeOrigin, document.readyState == 'complete' && "
                                          "!!document.getElementById('mainMenuButton')]", wait=2)
            if origin != before and ready:
                return
        except oe.DevToolsError:    # the page is unloading
            pass
        time.sleep(0.3)
    raise Stop(f"the editor did not load again in {RESTART_WAIT} seconds after Restart; reload its tab by hand")


def close_project(page) -> None:
    """Close the project open in the editor without saving. The page is one the script drives, on
    the start page when the run began, so the project is a copy the script handed over: this run's,
    or one a run that stopped left open. A crashed editor is restarted instead."""
    if not project_open(page):
        return
    if not page.evaluate(CRASH_JS):
        page.evaluate(DISMISS_JS)
        try:
            open_menu(page)
            press(page, "menu", "Project", 0.2)
            press(page, "menu", "Close project", 0.3)
        except Missed:
            if not page.evaluate(CRASH_JS):
                raise
    deadline = time.time() + UI_WAIT
    while time.time() < deadline:   # the editor asks to save a project it holds as changed
        if not project_open(page):
            return
        if page.evaluate(CRASH_JS):
            restart(page)
            return
        if page.evaluate(FIND_JS + "('dialog', \"Don't save\")"):
            press(page, "dialog", "Don't save", 0.3)
        time.sleep(0.2)
    raise Stop(f"the project did not close; the editor shows {json.dumps(page.evaluate(DIALOG_JS))}; close it "
               f"in the editor window, Menu > Project > Close project, and run again")


# What open_in_editor's SETUP leaves in a page until a file is dropped: the file input and the
# interval that closes the editor's dialogs
UNSET_JS = r"""(() => { clearInterval(window.__c3Keep);
  document.querySelectorAll('input[aria-label="Project to open"]').forEach(i => i.remove()); })()"""


def discard(page, devtools: oe.DevTools | None, opened: bool) -> None:
    """Undo what a run that stopped did in the editor, so that it leaves no copy open: a tab the
    script opened in the user's browser is closed; in the user's own tab or the script's window,
    the copy is closed without saving and the dialogs and the file input are taken away. The page
    keeps its login, unless the editor had crashed and had to restart."""
    try:
        if opened:
            devtools.call("Target.closeTarget", targetId=page.target)
            return
        close_project(page)
        page.evaluate(DISMISS_JS)
        page.evaluate(UNSET_JS)
    except (Stop, oe.DevToolsError) as e:
        print(f"the copy may still be open in the editor ({e}); close it there without saving: Menu > "
              f"Project > Close project, Don't save", flush=True)


def open_project(page, project: Path, staged: Path) -> None:
    # A project a run that stopped left opening: until it has opened, the title is the start page's
    for _ in range(oe.RESULT_WAIT):
        if not page.evaluate("!!document.querySelector('#progressDialog[open]')"):
            break
        time.sleep(1)
    close_project(page)
    if page.evaluate(f"({oe.SETUP_JS})()", wait=oe.SETUP_WAIT) != "ready":
        raise Stop("the editor did not get ready to open a project; run again")
    field = page.evaluate("document.querySelector('input[aria-label=\"Project to open\"]')", by_value=False)
    page.call("DOM.setFileInputFiles", files=[str(staged)], objectId=field["objectId"])
    result = page.evaluate(f"({oe.RESULT_JS})()", wait=oe.RESULT_WAIT)
    if not isinstance(result, dict) or result["dialogs"]:
        raise Stop(f"the project did not open: {result}")
    for _ in range(60):     # a large project takes longer than RESULT_JS waits
        if page.evaluate("document.title").startswith(project_title(project)):
            return
        time.sleep(1)
    raise Stop(f"the project did not open in {oe.RESULT_WAIT + 60} seconds: {result}")


# The export options: a zip, with Offline support, which lets players get an update,
# and the images deduplicated and optimized, which makes the download smaller
OPTIONS_JS = r"""(() => {
  const to = document.getElementById('exportTo');
  if (to.value !== 'zip') { to.value = 'zip'; to.dispatchEvent(new Event('change', {bubbles: true})); }
  for (const id of ['exportOfflineSupport', 'exportDeduplicateImages', 'exportOptimizeImages']) {
    const box = document.getElementById(id);
    if (!box.checked) box.click();
  }
})()"""

# The report's download link is a blob URL: read it into the page, then fetch it in parts
ZIP_JS = r"""(async () => {
  const a = document.querySelector('#webExportReportDialog a[download]');
  window.__exportZip = new Uint8Array(await (await fetch(a.href)).arrayBuffer());
  return window.__exportZip.length;
})()"""


def export(page) -> bytes:
    """Project > Export > Web (HTML5); the zip it makes."""
    open_menu(page)
    press(page, "menu", "Project", 0.2)
    press(page, "menu", "Export", 0.5)
    press(page, "dialog", "Web (HTML5)", 0.2)
    press(page, "dialog", "Next", 0.3)
    deadline = time.time() + UI_WAIT
    while (dialog := page.evaluate(DIALOG_JS)) is None or dialog["id"] != "exportStandardOptionsDialog":
        if time.time() > deadline:      # until then the Next found is the one just pressed
            raise Missed(f"the export options did not open; the editor shows {json.dumps(dialog)}")
        time.sleep(0.2)
    page.evaluate(OPTIONS_JS)
    press(page, "dialog", "Next", 0.3)
    for _ in range(EXPORT_WAIT * 2):
        dialog = page.evaluate(DIALOG_JS)
        if dialog and dialog["id"] == "webExportReportDialog":
            break
        time.sleep(0.5)
    else:
        raise Stop(f"the export did not finish in {EXPORT_WAIT // 60} minutes; the editor shows {json.dumps(dialog)}")
    size = page.evaluate(ZIP_JS, wait=120)
    data = b"".join(base64.b64decode(page.evaluate(
        f"(() => {{ const s = window.__exportZip.subarray({i}, {i + CHUNK}); let b = ''; "
        f"for (let k = 0; k < s.length; k += 0x8000) b += String.fromCharCode(...s.subarray(k, k + 0x8000)); "
        f"return btoa(b); }})()", wait=60)) for i in range(0, size, CHUNK))
    page.evaluate("delete window.__exportZip")
    press(page, "dialog", "OK", 0.5)
    return data


def slow_down(page) -> None:
    """Pauses SLOW times longer, and the editor back to no menu and no dialog."""
    global pace
    pace = SLOW
    for kind in ("keyDown", "keyUp"):
        page.call("Input.dispatchKeyEvent", type=kind, key="Escape", code="Escape", windowsVirtualKeyCode=27)
    page.evaluate(DISMISS_JS)
    pause(1)


# --- versions and files ---------------------------------------------------------------
# The Version of project.c3proj as the editor writes it: 3 or 4 numbers of 0 to 99
VERSION_RE = re.compile(r'^(\t\t"version": ")([^"]*)(",)$', re.M)
VERSION_FORMAT = re.compile(r"\d{1,2}(\.\d{1,2}){2,3}")


def project_version(project: Path) -> str:
    found = VERSION_RE.search((project / "project.c3proj").read_text(encoding="utf-8"))
    return found.group(2) if found else ""


def exported_versions(folder: Path) -> list[str]:
    """The strings of data.json's project array in a Web export that look like a version."""
    if not (folder / "data.json").is_file():
        return []
    return [v for v in json.loads((folder / "data.json").read_text(encoding="utf-8"))["project"]
            if isinstance(v, str) and VERSION_FORMAT.fullmatch(v)]


def bumped(project: Path, folder: Path) -> str:
    """The last number of the export in folder plus one, a number past 99 carrying into the one
    before; the project's version when that is greater, as after a hand edit that starts a new line."""
    def parts(v: str) -> list[int]:
        return [int(x) for x in v.split(".")] if VERSION_FORMAT.fullmatch(v or "") else []
    last = parts((exported_versions(folder) or [""])[0])
    if last:
        last[-1] += 1
        for i in range(len(last) - 1, 0, -1):
            if last[i] > 99:
                last[i], last[i - 1] = 0, last[i - 1] + 1
    return ".".join(map(str, max(last, parts(project_version(project)))))


def with_version(text: str, version: str) -> str:
    return VERSION_RE.sub(lambda m: m.group(1) + version + m.group(3), text)


# Use worker in project.c3proj: auto, worker (Yes) or dom (No). Auto runs in a worker unless the
# project has a script or an addon without worker support.
WORKER_RE = re.compile(r'("useWorker": ")([a-z]+)(")')


# start-export.js at the end of scripts/main.js: const e=true;...RuntimeInterface({useWorker:e,...
EXPORTED_WORKER_RE = re.compile(r'const (\w+)=(true|false);window\["c3_runtimeInterface"\]=new '
                                r'self\.RuntimeInterface\(\{useWorker:\1[,}]')


def exported_worker(folder: Path) -> bool | None:
    """Whether the export in folder starts its runtime in a worker; None when main.js does not say."""
    main = folder / "scripts" / "main.js"
    found = EXPORTED_WORKER_RE.search(main.read_text(encoding="utf-8")) if main.is_file() else None
    return found.group(2) == "true" if found else None


def build(project: Path) -> Path:
    """.build/ of the project, where the products go, with a .gitignore of * so that Git commits none."""
    path = project / pp.BUILD
    path.mkdir(exist_ok=True)
    if not (path / ".gitignore").exists():
        (path / ".gitignore").write_text("*\n", encoding="utf-8")
    return path


def pack(project: Path, version: str, skip: Path | None) -> bytes:
    """The files the editor reads as a .c3p carrying version, with Auto-increment version off so
    that the export carries it unchanged, and Use worker Auto. The rest stays
    out: an earlier export, the worktrees of an agent under .claude, which made a game's .c3p 1.8 GB;
    and skip, the export folder."""
    files, _ = pp.editor_files(pp.from_folder(project), ())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, f in files.items():
            if skip and f.is_relative_to(skip):
                continue
            if name == "project.c3proj":
                text = with_version(f.read_text(encoding="utf-8"), version)
                text = text.replace('"autoIncrementVersion": true', '"autoIncrementVersion": false')
                text = WORKER_RE.sub(r"\g<1>auto\g<3>", text)
                z.writestr(name, text)
            else:
                z.write(f, name)
    return buf.getvalue()


def unpack(data: bytes, folder: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if "data.json" not in z.namelist():
            raise Stop("the zip the editor made holds no data.json, so it is not a Web export")
        shutil.rmtree(folder, ignore_errors=True)
        z.extractall(folder)


# --- the run --------------------------------------------------------------------------
def run(project: Path, folder: Path, version: str, spec: str | None, exe: str | None) -> bool | None:
    """Exports; whether the export runs in a worker, as its main.js says."""
    staged = scratch(project) / "export-project.c3p"
    staged.write_bytes(pack(project, version, folder if folder.is_relative_to(project) else None))
    devtools, opened = None, False
    if spec:
        devtools = attach(spec)
        page, opened = attached_page(devtools, project)
    else:
        b = own_browser(project, exe)
        target, page = own_page(b, editor_url(project))
        show_window(b, target, "normal")
        close_project(page)     # one a run that was killed left, before the login is read: a restart loses it
    print(f"logged in as {wait_for_login(page)}, exporting {version}", flush=True)
    try:
        open_project(page, project, staged)
        try:
            data = export(page)
        except Missed as e:
            if pace >= SLOW:
                raise
            print(f"{e}; trying again with longer pauses", flush=True)
            slow_down(page)
            data = export(page)
    except (Stop, oe.DevToolsError):
        discard(page, devtools, opened)
        staged.unlink(missing_ok=True)
        raise
    # Close the project, so that this editor and one the user has open elsewhere do not both
    # change it. The script's own window is minimized and keeps its login for the next run; in the
    # user's browser a tab the script opened is closed and the user's own is left on the start page
    close_project(page)
    if not spec:
        show_window(b, target, "minimized")
    elif opened:
        devtools.call("Target.closeTarget", targetId=page.target)
    staged.unlink(missing_ok=True)
    unpack(data, folder)
    if version not in exported_versions(folder):
        raise Stop(f"the export in {folder} carries {exported_versions(folder)}, not {version}; "
                   f"project.c3proj is left as it was")
    path = project / "project.c3proj"
    text = path.read_text(encoding="utf-8")
    if project_version(project) != version:
        path.write_bytes(with_version(text, version).encode("utf-8"))
    return exported_worker(folder)


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--to", metavar="FOLDER", type=Path,
                    help="the folder the export replaces, relative to the project (default: .build/web)")
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--version", help="the version to export, 3 or 4 numbers of 0 to 99: 1.2.0.0")
    which.add_argument("--bump", action="store_true",
                       help="the version of the export already in --to with its last number plus one, or the "
                            "project's version when that is greater")
    ap.add_argument("--attach", metavar="PORT|URL|FILE",
                    help="export in a Chrome or Edge the user has open and is logged in to, not in a window "
                         "of the script's own (see below)")
    ap.add_argument("--slow", action="store_true",
                    help=f"pauses {SLOW} times longer between clicks from the start, for a slow machine or "
                         f"network; without it a step the editor missed is tried once more this way")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the version, the editor and the folder, and open nothing")
    args = ap.parse_args()

    project = c3.find_project(args.project)
    if not project or not (project / "project.c3proj").is_file():
        print(f"no project.c3proj found from {args.project or Path.cwd()}; run this in the project folder or "
              f"pass --project <folder>", file=sys.stderr)
        return 2
    folder = (project / (args.to or Path(pp.BUILD) / "web")).resolve()
    version = args.version or (bumped(project, folder) if args.bump else project_version(project))
    if not VERSION_FORMAT.fullmatch(version or ""):
        print(f"the version to export is '{version}', not 3 or 4 numbers of 0 to 99; pass --version 1.0.0.0 or "
              f"set Version in the project properties", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"would export {version} in {editor_url(project)} into {folder}; project.c3proj version "
              f"{project_version(project)}{f' -> {version}' if version != project_version(project) else ''}")
        return 0
    if not args.to:
        build(project)
    if args.slow:
        global pace
        pace = SLOW
    exe = None if args.attach else (oe.browser_path())
    if not args.attach and not exe:
        print("no Edge, Chrome or Chromium found here; export in the editor by hand, or pass --attach",
              file=sys.stderr)
        return 3
    try:
        in_worker = run(project, folder, version, args.attach, exe)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    except oe.EditorNotLoaded as e:
        print(f"the editor did not load: {e}; check the network connection and run again", file=sys.stderr)
        return 2
    except (Stop, oe.DevToolsError) as e:
        print(f"not exported: {e}")
        return 1
    where = {True: "the worker", False: "the page", None: "a place scripts/main.js does not name"}[in_worker]
    print(f"exported {version} into {folder}, runtime in {where}; project.c3proj version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
