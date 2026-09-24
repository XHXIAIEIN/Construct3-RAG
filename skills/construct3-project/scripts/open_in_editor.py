"""Open a project in the Construct 3 editor and print whether it opens, or the
editor's message when it does not.

    python scripts/open_in_editor.py [PATH ...] [--project FOLDER] [--release rNNN] [--browser EXE]
                                     [--steps] [--shots DIR] [--out RESULTS.json] [--jobs 2] [--headed]

Run it when check_project.py ends with ok:. The checker reads the files; the
editor also reads the events, and refuses a project for what the checker does
not see, a type mismatch in an expression among them. The project goes to
https://editor.construct.net/ the way a user drops a .c3p onto it: the window
title turns to the project's name, or a dialog says why it did not open, with
the exception the editor logged. The file is handed to the page in the
browser, not uploaded to a server.

It starts the Microsoft Edge, Google Chrome or Chromium the machine has,
headless, with a profile of its own in .tmp/editor-<browser>, and drives it
over the DevTools protocol with Python's standard library: no package to
install and nothing asked of the agent. The first run fills the profile's
cache, about 80 MB, in 20 to 40 seconds; each later one takes about 4. With
no such browser, or with --steps, it writes the project as
.tmp/open-in-editor.c3p in the project folder and prints the same check as
steps for a browser tool of the agent: one that opens a page, runs
JavaScript in it and puts a file on a file input.

Without a PATH it opens the project the current directory is in. A PATH is a
folder project (the folder that holds project.c3proj), a .c3p, or any folder
above them: every project.c3proj below it is opened.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import c3project as c3

EPILOG = """examples:
  python scripts/open_in_editor.py
  python scripts/open_in_editor.py --project "D:/Games/Snake" --release r502
  python scripts/open_in_editor.py --steps
  python scripts/open_in_editor.py <eval iteration folder> --jobs 3 --out opened.json

output, one entry per project:
  opened   <project>  (<window title>)
  failed   <project>
    editor: <the dialog's text, which names the sheet, event and parameter at fault>
    exception: <the first line of the exception the editor logged>

exit codes: 0 every project opened; 1 at least one did not; 2 no project
found, or the editor did not load; 3 no browser here, or --steps: the steps
for a browser tool were printed instead, the project is not opened yet
"""

EDITOR = "https://editor.construct.net/"
# Inside the project, where check_project.py does not look and the editor does not write.
SCRATCH = ".tmp"
TIMEOUT = 200   # seconds a DevTools call may take: SETUP and RESULT wait inside the page

# The page side, the same for the script and for an agent's browser tool. With a
# tool, every call is a round trip through the model and every character of a
# function is written by it, so SETUP, which comes before the import, is short, and
# the waiting happens in the page.
#
# SETUP keeps what the editor logs as an error, puts a file input first in the page
# and closes the dialogs the editor shows on start, by their close or OK button in
# any language, until a file is put on the input: a modal dialog hides the rest of
# the page from a snapshot, and the update offers come a few seconds after the
# menu. It returns once the menu is there and no dialog is open, about 3 seconds
# after the page loads. The editor's own Open button uses a file picker no tool
# can fill, hence the input. Its file is dropped on the editor when no dialog has
# been open for a second, since a drop while the welcome dialog closes is ignored;
# the editor handles a synthetic drop like a file dragged from the desktop.
# __c3Title keeps the title at the drop, null for a file with no bytes: the upload
# action of a tool accepts a path that does not exist and hands the page nothing.
SETUP_JS = r"""async () => {
  const w = t => new Promise(r => setTimeout(r, t)), e = window.__c3Errors = [], log = console.error.bind(console);
  const open = () => [...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog');
  const ok = () => document.getElementById('mainMenuButton') && !open().length;
  console.error = (...a) => { e.push(a.map(String).join(' ')); log(...a); };
  const keep = setInterval(() => { document.querySelector('a.noThanksLink')?.click();
    open().forEach(d => d.querySelector('ui-close-button, .okButton')?.click()); }, 200);
  const i = document.createElement('input');
  i.type = 'file'; i.ariaLabel = 'Project to open'; document.body.prepend(i);
  i.onchange = async () => {
    if (!i.files[0].size) return window.__c3Title = null;
    for (let calm = 0; calm < 5; await w(200)) calm = ok() ? calm + 1 : 0;
    clearInterval(keep); window.__c3Title = document.title;
    const dt = new DataTransfer(); dt.items.add(i.files[0]); i.remove();
    for (const type of ['dragenter', 'dragover', 'drop'])
      document.body.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt}));
  };
  for (let n = 0; n < 300 && !ok(); n++) await w(200);
  return ok() ? 'ready' : 'not ready: the editor did not load';
}"""

# RESULT waits for the drop, then for the editor's answer: the title turns to the
# project's name, or a dialog says why it did not open. A dialog can follow the
# title by a moment, hence the last wait.
RESULT_JS = r"""async () => {
  const w = t => new Promise(r => setTimeout(r, t)), start = () => window.__c3Title;
  const open = () => [...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog');
  for (let n = 0; start() === undefined; n++) { if (n > 300) return 'no file on the input: put the .c3p on it'; await w(200); }
  if (start() === null) return 'the file on the input is empty: its path does not exist';
  for (let n = 0; n < 360; n++, await w(250))
    if (!document.querySelector('#progressDialog[open]') && (open().length || document.title != start())) break;
  await w(1500);
  const dialogs = open().map(d => d.innerText.trim().replace(/\s+/g, ' ').slice(0, 1500));
  return {opened: !dialogs.length && document.title != start(), title: document.title, dialogs,
          errors: window.__c3Errors.filter(x => x.includes('Exception')).map(x => x.slice(0, 600))};
}"""

NEXT = ("next: the editor's message names the place, `Game, event 12, condition 1` is event 12 of sheet Game "
        "as scripts/print_sheet.py numbers it. Fix it, run scripts/check_project.py, then this script again. "
        "When the checker passed what the editor refused, tell the user the message: the checker lacks that rule.")


class EditorNotLoaded(Exception):
    pass


def find_projects(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_file() or (path / "project.c3proj").is_file():
            found.append(path)
        elif path.is_dir():
            found += sorted(p.parent for p in path.rglob("project.c3proj") if ".git" not in p.parts)
    return list(dict.fromkeys(p.resolve() for p in found))


def pack(project: Path) -> bytes:
    """A folder project as the .c3p the editor would save: the same files, zipped."""
    if project.is_file():
        return project.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(project.rglob("*")):
            rel = f.relative_to(project)
            if f.is_file() and rel.parts[0] not in (".git", SCRATCH):
                z.write(f, rel.as_posix())
    return buf.getvalue()


def write_c3p(project: Path) -> Path:
    """The project as a file a browser tool can put on the page, in a folder Git leaves alone."""
    if project.is_file():
        return project
    scratch = project / SCRATCH
    scratch.mkdir(exist_ok=True)
    if not (scratch / ".gitignore").exists():
        (scratch / ".gitignore").write_text("*\n", encoding="utf-8")
    c3p = scratch / "open-in-editor.c3p"
    c3p.write_bytes(pack(project))
    return c3p


def steps(project: Path, editor: str, why: str) -> str:
    c3p = write_c3p(project)
    tail = f" Git ignores {c3p.parent}; delete it when you are done." if c3p != project else ""
    return f"""{why}. Open it with a browser tool of this session that runs JavaScript in a page and puts
a file on a file input, in three rounds of calls; the page does the waiting, so make each call once:
1. Open {editor} in a new page, in an isolated context if the tool has one.
2. In one message: run SETUP in that page (a tool that takes an expression gets it called:
   `(...)()`), then take a snapshot of it. SETUP returns "ready" about 3 seconds after the page
   loads, and the snapshot lists the input "Project to open" first; if it does not, take it again.
3. In one message: put this file on that input with the tool's upload action (a tool that waits
   for a file chooser gets one by clicking the input), then run RESULT:
   {c3p}
   RESULT returns {{opened, title, dialogs, errors}} a few seconds after the upload. opened true
   is the hand-over. Otherwise the dialog names the place and errors holds the exception the
   editor logged. {NEXT.removeprefix("next: ")}
Without such a tool, ask the user to open the project in Construct 3 and paste the text of the
dialog it shows.{tail}

SETUP:
{SETUP_JS}

RESULT:
{RESULT_JS}"""


class DevToolsError(Exception):
    pass


def browser_path() -> str | None:
    """The Edge, Chrome or Chromium of this machine, where their installers put them."""
    places: list[Path] = []
    if sys.platform == "win32":
        for base in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            if os.environ.get(base):
                places += [Path(os.environ[base], "Microsoft/Edge/Application/msedge.exe"),
                           Path(os.environ[base], "Google/Chrome/Application/chrome.exe")]
    elif sys.platform == "darwin":
        places += [Path("/Applications", app, "Contents/MacOS", name) for app, name in (
            ("Google Chrome.app", "Google Chrome"), ("Microsoft Edge.app", "Microsoft Edge"),
            ("Chromium.app", "Chromium"))]
    for place in places:
        if place.is_file():
            return str(place)
    names = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "chrome")
    return next(filter(None, map(shutil.which, names)), None)


class WebSocket:
    """The client end of RFC 6455, as much as the DevTools protocol needs: text
    frames out, masked, and whole messages in."""

    def __init__(self, url: str) -> None:
        u = urllib.parse.urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=TIMEOUT)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
                           ).encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            self.buf += self._recv()
        status, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in status.split(b"\r\n")[0]:
            raise DevToolsError(status.split(b"\r\n")[0].decode(errors="replace"))

    def _recv(self) -> bytes:
        chunk = self.sock.recv(65536)
        if not chunk:
            raise DevToolsError("the browser closed the connection")
        return chunk

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            self.buf += self._recv()
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def send(self, text: str) -> None:
        data, mask = text.encode(), os.urandom(4)
        n = len(data)
        size = bytes([0x80 | n]) if n < 126 else bytes([0xFE]) + n.to_bytes(2, "big") if n < 65536 \
            else bytes([0xFF]) + n.to_bytes(8, "big")
        self.sock.sendall(b"\x81" + size + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def receive(self) -> str:
        parts = []
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n > 125:
                n = int.from_bytes(self._read(2 if n == 126 else 8), "big")
            data = self._read(n)
            if b0 & 0x0F == 0x8:
                raise DevToolsError("the browser closed the connection")
            if b0 & 0x0F in (0x0, 0x1, 0x2):
                parts.append(data)
                if b0 & 0x80:
                    return b"".join(parts).decode()

    def close(self) -> None:
        self.sock.close()


class DevTools:
    """One DevTools connection, to the browser or to a page. Calls wait for their
    own answer; the events a page sends meanwhile are skipped."""

    def __init__(self, url: str) -> None:
        self.ws, self.last, self.lock = WebSocket(url), 0, threading.Lock()

    def call(self, method: str, **params) -> dict:
        with self.lock:
            self.last += 1
            self.ws.send(json.dumps({"id": self.last, "method": method, "params": params}))
            while True:
                message = json.loads(self.ws.receive())
                if message.get("id") == self.last:
                    if "error" in message:
                        raise DevToolsError(f"{method}: {message['error'].get('message')}")
                    return message["result"]

    def evaluate(self, expression: str, by_value: bool = True):
        r = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=by_value)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise DevToolsError(d.get("exception", {}).get("description") or d.get("text", "exception"))
        return r["result"].get("value") if by_value else r["result"]


class Browser:
    """The machine's browser with a profile of its own and a DevTools port the
    system picks, written by the browser to DevToolsActivePort in the profile.

    The profile is kept between runs. The editor is some megabytes of scripts,
    and a page in the profile reads them from its disk cache: a run then takes
    about 4 seconds against 20 to 40 from a cold profile, and a context of its
    own per page, which has no disk cache, is cold every time."""

    def __init__(self, exe: str, profile: Path, headed: bool) -> None:
        self.profile = profile
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "DevToolsActivePort").unlink(missing_ok=True)   # a port file left from an earlier run
        args = [exe, f"--user-data-dir={profile}", "--remote-debugging-port=0", "--no-first-run",
                "--no-default-browser-check", "--window-size=1400,900", "about:blank"]
        self.proc = subprocess.Popen(args if headed else [*args, "--headless=new"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = profile / "DevToolsActivePort"
        for _ in range(150):
            if port_file.is_file() and port_file.read_text().strip():
                break
            if self.proc.poll() is not None:
                raise DevToolsError(f"{exe} exited with code {self.proc.returncode}")
            time.sleep(0.2)
        else:
            self.close()
            raise DevToolsError(f"{exe} opened no DevTools port in 30 seconds")
        self.port = int(port_file.read_text().split()[0])
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=10) as r:
            self.devtools = DevTools(json.load(r)["webSocketDebuggerUrl"])

    def page(self, url: str) -> tuple[str, DevTools]:
        target = self.devtools.call("Target.createTarget", url=url)["targetId"]
        return target, DevTools(f"ws://127.0.0.1:{self.port}/devtools/page/{target}")

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def load(page: DevTools, editor: str) -> None:
    """Until the editor's page has loaded. A new page starts as about:blank, whose
    readyState is complete too, and its context goes away as the editor loads."""
    where = ["", "", 0]
    for _ in range(300):
        try:
            where = page.evaluate("[location.href, document.readyState, "
                                  "performance.getEntriesByType('navigation')[0]?.responseStatus || 0]")
        except DevToolsError:
            pass
        if where[0].startswith("chrome-error:"):
            raise EditorNotLoaded(f"{editor} could not be reached")
        if where[0].startswith(editor) and where[1] == "complete":
            break
        time.sleep(0.2)
    else:
        raise EditorNotLoaded(f"{editor} did not finish loading in 60 seconds")
    if where[2] >= 400:
        raise EditorNotLoaded(f"{editor} answered HTTP {where[2]}")


def open_one(browser: Browser, editor: str, project: Path, staged: Path, shot: Path | None) -> dict:
    staged.write_bytes(pack(project))
    target, page = browser.page(editor)
    try:
        load(page, editor)
        ready = page.evaluate(f"({SETUP_JS})()")
        if ready != "ready":
            raise EditorNotLoaded(ready)
        started = time.monotonic()
        field = page.evaluate("document.querySelector('input[aria-label=\"Project to open\"]')", by_value=False)
        page.call("DOM.setFileInputFiles", files=[str(staged)], objectId=field["objectId"])
        result = page.evaluate(f"({RESULT_JS})()")
        if shot:
            shot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot")["data"]))
    finally:
        page.ws.close()
        browser.devtools.call("Target.closeTarget", targetId=target)
        staged.unlink(missing_ok=True)

    if isinstance(result, str):
        result = {"opened": False, "title": "", "dialogs": [], "errors": [result]}
    status = "opened" if result["opened"] else "failed" if result["dialogs"] or result["errors"] else "timeout"
    return {"project": str(project), "status": status, "title": result["title"], "dialogs": result["dialogs"],
            "exception": next(iter(result["errors"]), ""), "seconds": round(time.monotonic() - started, 1)}


def report(result: dict) -> list[str]:
    if result["status"] == "opened":
        return [f"opened   {result['project']}  ({result['title']})"]
    lines = [f"{result['status']:<8} {result['project']}"]
    lines += [f"  editor: {d}" for d in result["dialogs"]]
    if result["status"] == "timeout":
        lines.append(f"  editor: no answer in 90 seconds, the title is {result['title']!r}; "
                     f"--shots DIR saves what the editor shows")
    if result["exception"]:
        lines.append(f"  exception: {result['exception'].splitlines()[0]}")
    return lines


def run(projects: list[Path], editor: str, exe: str, args) -> list[dict]:
    first = projects[0] if projects[0].is_dir() else projects[0].parent
    # One profile per browser: Chrome does not load a profile Edge has written.
    browser = Browser(exe, first / SCRATCH / f"editor-{Path(exe).stem.lower()}", args.headed)
    results: list[dict] = []
    printed = 0     # characters; results are printed as they come, until --limit
    lock = threading.Lock()

    def one(i: int, project: Path) -> None:
        nonlocal printed
        shot = args.shots / f"{i:03d}-{project.name}.png" if args.shots else None
        result = open_one(browser, editor, project, browser.profile / f"project-{i}.c3p", shot)
        with lock:
            results.append(result)
            text = "\n".join(report(result))
            if not args.limit or printed + len(text) <= args.limit:
                print(text, flush=True)
                printed += len(text) + 1
            else:
                result["unprinted"] = True

    try:
        with ThreadPoolExecutor(max(1, args.jobs)) as pool:
            for future in [pool.submit(one, i, pr) for i, pr in enumerate(projects)]:
                future.result()
    finally:
        browser.close()
    return sorted(results, key=lambda r: r["project"])


def main() -> int:
    c3.utf8_output()
    ap = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, metavar="PATH",
                    help="a folder project, a .c3p, or a folder above them (default: the project of --project, "
                         "else the one the current directory is in)")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--steps", action="store_true",
                    help="print the steps for a browser tool of the agent's instead of opening the project here")
    ap.add_argument("--browser", metavar="EXE",
                    help="the Chromium-based browser to start (default: Edge, Chrome or Chromium where installed)")
    ap.add_argument("--release", metavar="rNNN",
                    help="open in this release of the editor, as its URL spells it: r502, r495-2 "
                         "(default: the current stable release, the one the user gets)")
    ap.add_argument("--out", type=Path, help="write every result, dialogs and exceptions included, as JSON")
    ap.add_argument("--shots", type=Path, help="save a screenshot of the editor per project into this folder")
    ap.add_argument("--jobs", type=int, default=2, help="projects open at once (default 2)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--limit", type=int, default=c3.LIMIT, metavar="CHARS",
                    help=f"stop printing results after about this many characters, since a harness cuts longer "
                         f"tool output; --out keeps them all, 0 prints everything (default: {c3.LIMIT})")
    args = ap.parse_args()

    if args.paths:
        projects = find_projects(args.paths)
    else:
        project = c3.find_project(args.project)
        projects = find_projects([project]) if project else []
    if not projects:
        where = ", ".join(map(str, args.paths)) if args.paths else args.project or str(Path.cwd())
        print(f"no project.c3proj or .c3p found under {where}; run this in the project folder or pass "
              f"--project <folder>", file=sys.stderr)
        return 2
    editor = f"{EDITOR}{args.release.strip('/')}/" if args.release else EDITOR

    # A browser tool opens one project at a time, as the agent's own step.
    exe = args.browser or browser_path()
    why = "not opened here (--steps)" if args.steps else None if exe else "no Edge, Chrome or Chromium found here"
    if why and len(projects) > 1:
        print(f"{why}, and {len(projects)} projects were found; name one with --project", file=sys.stderr)
        return 2
    if why:
        print(steps(projects[0], editor, why))
        return 3

    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    try:
        results = run(projects, editor, exe, args)
    except EditorNotLoaded as e:
        print(f"the editor did not load: {e}. Check the network connection and --release, and run again; "
              f"without a connection, ask the user to open the project in Construct 3 and paste the text of the "
              f"dialog it shows.", file=sys.stderr)
        return 2
    except (DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser, or --steps to open the "
              f"project with a browser tool of this session.", file=sys.stderr)
        return 2
    unprinted = sum(1 for r in results if r.pop("unprinted", False))
    if args.out:
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = [r for r in results if r["status"] != "opened"]
    if unprinted:
        print(f"{unprinted} results not printed: --out FILE keeps every one, --limit 0 prints them")
    print(f"{len(results) - len(failed)} of {len(results)} opened" + (f"; full results in {args.out}" if args.out else ""))
    if failed:
        print(NEXT)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
