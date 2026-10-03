"""Open a project in the Construct 3 editor and print whether it opens, or the
editor's message when it does not.

    python scripts/open_in_editor.py [PATH ...] [--project FOLDER] [--release rNNN] [--browser EXE]
                                     [--preview [SECONDS]] [--state [TYPE ...]] [--steps] [--shots DIR]
                                     [--out RESULTS.json]
                                     [--jobs 2] [--headed] [--profile FOLDER]

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
install and nothing asked of the agent. The profile keeps the editor's
scripts cached, about 15 MB and at most 100: the first run takes 7 to 40
seconds, each later one 4 to 7. .tmp/ holds a .gitignore of *. With
no such browser, or with --steps, it writes the project as
.tmp/open-in-editor.c3p in the project folder and prints the same check as
steps for a browser tool of the agent: one that opens a page, runs
JavaScript in it and puts a file on a file input.

With --preview it then runs a preview, F5 in the editor, for some seconds and
prints the layout it started on and what the runtime reported: uncaught
exceptions and console errors, each with the event it came from. With --state it
then prints what the game holds at the end: the global variables, how many
instances each object type has, and every instance of the types named, its
position, instance variables and behavior values. On Windows the
preview needs the profile within about 190 characters; a deeper project, on a
volume without 8.3 short names, is refused with how to pass --profile, a
shorter folder for it.

Every result, the error stacks and the state included, goes to
.tmp/open-in-editor.json and a screenshot of the editor per project to
.tmp/shots/; the last line names both. Read a cut-off result there instead of
running the project again.

With --install-addon FILE.c3addon it first installs the addon into the editor of
the browser profile, as a user drops it on the editor and clicks Install, or
Update over an installed copy, in whatever language the editor shows; the profile keeps it for every later run. A
project that uses a custom plugin, behavior or effect opens only after that.
An addon the editor refuses stops the run with its message and exception.

Without a PATH it opens the project the current directory is in. A PATH is a
folder project (the folder that holds project.c3proj), a .c3p, or any folder
above them: every project.c3proj and .c3p below it is opened, .tmp/ and .build/ left out.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import c3project as c3
import pack_project as pp

EPILOG = """examples:
  python scripts/open_in_editor.py
  python scripts/open_in_editor.py --project "D:/Games/Snake" --release r502
  python scripts/open_in_editor.py --preview
  python scripts/open_in_editor.py --preview 10 --state Player Enemy
  python scripts/open_in_editor.py --steps
  python scripts/open_in_editor.py --install-addon MyEffect.c3addon --preview
  python scripts/open_in_editor.py <eval iteration folder> --jobs 3 --out opened.json

output, one entry per addon with --install-addon, then one per project:
  installed <addon>  (<name> <version>, <type>)
  refused  <addon>
    editor: <the dialog's text>
    exception: <what the editor logged, "invalid addon json" for an addon.json it does not take>
  opened   <project>  (<window title>, <the editor it opened in>)
    warning: <a notice the editor showed over the opened project, deprecated features: tell the user>
    preview: layout '<name>', runtime in the worker, 600 ticks in 4.2 s, 1 error      with --preview
    runtime: <the first line of each error; --out keeps the stack>
    globals: Score 0, Lives 3                                                         with --state
    objects: Player 1, Enemy 6, Coin 12
    Player: 1 instance                                                                with --state Player
      uid 4, at (56, 239.94) 8x12, on World; Health 3
        sprite: current-animation "Run", current-frame 2, is-playing true, speed 12, repeats 0
        Platform: vector-x 128, vector-y 0, max-speed 128, ...
  failed   <project>
    editor: <the dialog's text, which names the sheet, event and parameter at fault>
    exception: <the first line of the exception the editor logged>

exit codes: 0 every project opened, and with --preview ran without errors; 1 at least one did not, or an
--install-addon was refused; 2 no project
found, or the editor did not load; 3 no browser here, or --steps: the steps
for a browser tool were printed instead, the project is not opened yet
"""

EDITOR = "https://editor.construct.net/"
BETA = EDITOR + "beta"      # redirects to the latest beta release, /r503/ as of 2026-09-24
# Inside the project, where check_project.py does not look and the editor does not write.
SCRATCH = ".tmp"
# Seconds a DevTools call may take. SETUP waits in the page up to 45 for the editor,
# RESULT up to 30 for the drop and 45 for the answer; every other call answers at once.
CALL, SETUP_WAIT, RESULT_WAIT = 10, 55, 85

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
  for (let n = 0; n < 225 && !ok(); n++) await w(200);
  return ok() ? 'ready' : 'not ready: ' + (open().map(d => d.innerText.trim().replace(/\s+/g, ' ').slice(0, 300))
    .join(' | ') || (document.getElementById('mainMenuButton') ? 'no dialog' : 'no menu after 45 seconds'));
}"""

# RESULT waits for the drop, then for the editor's answer: the title turns to the
# project's name, or a dialog says why it did not open. A dialog can follow the
# title by a moment, hence the last wait. The Deprecated features dialog is a
# notice shown over the opened project: it is returned in warnings and closed, which
# takes up to half a second, so that a preview or an export can go on. It is told by
# its id, since the crash report, a refusal, also comes after the title has turned.
RESULT_JS = r"""async () => {
  const w = t => new Promise(r => setTimeout(r, t)), start = () => window.__c3Title;
  const open = () => [...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog');
  const notice = d => d.id == 'deprecatedFeaturesDialog', text = d => d.innerText.trim().replace(/\s+/g, ' ').slice(0, 1500);
  for (let n = 0; start() === undefined; n++) { if (n > 150) return 'no file on the input: put the .c3p on it'; await w(200); }
  if (start() === null) return 'the file on the input is empty: its path does not exist';
  for (let n = 0; n < 180; n++, await w(250))
    if (!document.querySelector('#progressDialog[open]') && (open().some(d => !notice(d)) || document.title != start())) break;
  await w(1500);
  const dialogs = open().filter(d => !notice(d)).map(text), warnings = open().filter(notice).map(text);
  open().filter(notice).forEach(d => d.querySelector('ui-close-button, .okButton')?.click());
  for (let n = 0; n < 20 && open().some(notice); n++) await w(100);
  return {opened: !dialogs.length && document.title != start(), title: document.title, dialogs, warnings,
          errors: window.__c3Errors.filter(x => x.includes('Exception')).map(x => x.slice(0, 600))};
}"""

# INSTALL answers the dialogs a dropped .c3addon brings, after SETUP put it on the
# input: the confirmation (#addonConfirmInstallDialog) by its OK button, Install,
# and the question over an installed copy (#confirmDialog) by its confirm button,
# Update; then the first other dialog is the editor's answer, "Addon install
# finished" or "Failed to install the addon", told apart by the error the editor
# logs when it refuses. Ids and classes, not the buttons' words, so that an editor
# in any language is answered.
INSTALL_JS = r"""async () => {
  const w = t => new Promise(r => setTimeout(r, t));
  const open = () => [...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog');
  const text = d => d.innerText.trim().replace(/\s+/g, ' ').slice(0, 1500);
  for (let n = 0; window.__c3Title === undefined; n++) { if (n > 150) return 'no file on the input'; await w(200); }
  if (window.__c3Title === null) return 'the file on the input is empty: its path does not exist';
  for (let n = 0; n < 240; n++, await w(250)) {
    const d = open()[0];
    if (!d) continue;
    const go = d.id == 'addonConfirmInstallDialog' ? d.querySelector('.okButton')
      : d.id == 'confirmDialog' ? d.querySelector('.confirmButton') : null;
    if (go) { go.click(); await w(500); continue; }
    const errors = window.__c3Errors.filter(x => /addon/i.test(x)).map(x => x.slice(0, 600)), answer = text(d);
    d.querySelector('ui-close-button, .okButton')?.click();
    return {installed: !errors.length, dialog: answer, errors};
  }
  return 'no answer from the editor in 60 seconds';
}"""

# Evaluated in the preview page and in each of its workers, it leaves `c3probe` where
# the game runs and answers true there, null elsewhere, false when the runtime did
# not tick; references/reading-the-runtime.md declares what it reads. The ticks and
# the wall time are the runtime's own: the window loads for part of the preview's
# seconds, so a 5-second preview runs the game about 4.
PROBE_JS = (c3.SKILL_DIR / "assets" / "runtime-probe.js").read_text(encoding="utf-8")
# Instances printed per type named by --state; --out keeps as many.
STATE_MAX = 20

OPEN_DIALOGS_JS = r"""[...document.querySelectorAll('dialog[open]')].filter(d => d.id != 'progressDialog')
  .map(d => d.innerText.trim().replace(/\s+/g, ' ').slice(0, 1500))"""

NEXT = ("next: a message that names a place, `Game, event 12, condition 1`, is event 12 of sheet Game as "
        "scripts/print_sheet.py numbers it: fix it, run scripts/check_project.py, then this script again, and "
        "when the checker had passed it, tell the user the message, since the checker lacks that rule. A missing "
        "addon by Scirra is an id the project invented: remove it from the files (Functions are built in and "
        "need no object type or usedAddons entry). A missing addon by another author is installed in the "
        "editor, not written into the files: tell the user which.")
NEXT_PREVIEW = ("next: a runtime error names its place, `Event sheet 1, event 3, action 1` for a script in an event, "
                "numbered as scripts/print_sheet.py numbers it: fix it and run this again with --preview. The preview "
                "starts on the layout the editor shows after opening, as F5 does: firstLayout, or the one the editor "
                "last left open in project.uistate.json.")


class AddonRefused(Exception):
    """An --install-addon the editor did not install; its message is printed."""


class EditorNotLoaded(Exception):
    pass


def find_projects(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_file() or (path / "project.c3proj").is_file():
            found.append(path)
        elif path.is_dir():
            found += sorted(p.parent for p in path.rglob("project.c3proj") if ".git" not in p.parts)
            found += sorted(p for p in path.rglob("*.c3p") if not {".git", SCRATCH, pp.BUILD} & set(p.parts))
    return list(dict.fromkeys(p.resolve() for p in found))


def saved_release(project: Path) -> int:
    """savedWithRelease of project.c3proj, 50200 for r502, 49502 for r495.2; 0 when unreadable."""
    try:
        if project.is_file():
            with zipfile.ZipFile(project) as z:
                text = z.read("project.c3proj")
        else:
            text = (project / "project.c3proj").read_bytes()
        return int(json.loads(text).get("savedWithRelease", 0))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return 0


# The release the page loaded its scripts from: editor.construct.net/r495-2/...
RELEASE_JS = r"""(performance.getEntriesByType('resource').map(e => e.name).join(' ')
  .match(/editor\.construct\.net\/r(\d+)(?:-(\d+))?\//) || []).slice(1).map(n => Number(n || 0))"""


def pack(project: Path) -> bytes:
    """A folder project as the .c3p the editor would save: the files it reads, as pack_project.py
    keeps them, zipped. The rest of the folder stays out, such as an export or the worktrees of
    an agent under .claude, which made a game's .c3p 1.8 GB."""
    if project.is_file():
        return project.read_bytes()
    files, _ = pp.editor_files(pp.from_folder(project), ())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, f in files.items():
            z.write(f, name)
    return buf.getvalue()


def scratch(folder: Path) -> Path:
    """.tmp/ of a project folder, with a .gitignore of * so that nothing in it is committed."""
    path = folder / SCRATCH
    path.mkdir(exist_ok=True)
    if not (path / ".gitignore").exists():
        (path / ".gitignore").write_text("*\n", encoding="utf-8")
    return path


def kept(out: Path | None, shots: Path | None, first: Path,
         result: str = "open-in-editor.json", folder: str = "shots") -> tuple[Path, Path]:
    """Where the results and the screenshots go, .tmp/ of the first project unless named: a run
    whose printed lines a pipe cut is read again from the file instead of run again."""
    if out and shots:
        return out, shots
    tmp = scratch(first)
    return out or tmp / result, shots or tmp / folder


def write_c3p(project: Path) -> Path:
    """The project as a file a browser tool can put on the page."""
    if project.is_file():
        return project
    c3p = scratch(project) / "open-in-editor.c3p"
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
   RESULT returns {{opened, title, dialogs, warnings, errors}} a few seconds after the upload.
   opened true is the hand-over; warnings holds what the editor noted over the opened project,
   deprecated features, to pass on to the user. Otherwise the dialog names the place and errors
   holds the exception the editor logged. {NEXT.removeprefix("next: ")}
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

    def __init__(self, url: str, timeout: float = CALL) -> None:
        u = urllib.parse.urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
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

    def __init__(self, url: str, timeout: float = CALL) -> None:
        """`timeout` is for the handshake: a browser debugged from chrome://inspect holds it until
        the user allows the connection."""
        self.ws, self.last, self.lock = WebSocket(url, timeout), 0, threading.Lock()
        self.events: list[dict] = []    # only a connection that enables a domain gets any

    def call(self, method: str, wait: float = CALL, session: str | None = None, **params) -> dict:
        """`session` addresses a target attached to this one, a page's worker."""
        with self.lock:
            self.last += 1
            self.ws.sock.settimeout(wait)
            request = {"id": self.last, "method": method, "params": params}
            if session:
                request["sessionId"] = session
            try:
                self.ws.send(json.dumps(request))
                while True:
                    message = json.loads(self.ws.receive())
                    if message.get("id") == self.last:
                        if "error" in message:
                            raise DevToolsError(f"{method}: {message['error'].get('message')}")
                        return message["result"]
                    if "method" in message:
                        self.events.append(message)
            except socket.timeout:
                raise DevToolsError(f"{method}: no answer in {wait:g} seconds") from None

    def evaluate(self, expression: str, by_value: bool = True, wait: float = CALL, session: str | None = None):
        r = self.call("Runtime.evaluate", wait, session, expression=expression, awaitPromise=True,
                      returnByValue=by_value)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise DevToolsError(d.get("exception", {}).get("description") or d.get("text", "exception"))
        return r["result"].get("value") if by_value else r["result"]


# What the browser would add to the profile besides the editor's cache: Edge
# downloads components (entity extraction, language models, 30 MB and more) and
# installs its built-in extensions afresh on every start, and the GPU writes
# shader caches. The disk cache is capped; the editor's scripts take about 20 MB
# a release. --mute-audio keeps a preview's sound off the user's speakers: the
# audio graph still runs, so a game timed by its audio clock plays as it would.
QUIET = ("--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-component-update",
         "--disable-background-networking", "--disable-sync", "--disable-gpu-shader-disk-cache",
         "--disk-cache-size=104857600", "--mute-audio")


# The browser opens no IndexedDB whose folder path reaches MAX_PATH, measured as a
# string: \\?\ does not lift this limit and counts against it. Without IndexedDB the
# preview page stops answering. The deepest folder is the preview's, this far below
# the profile.
INDEXEDDB = len(r"\Default\IndexedDB\https_preview.construct.net_0.indexeddb.leveldb")
MAX_PATH = 260


def user_data_dir(profile: Path) -> str:
    r"""The profile as --user-data-dir. A long Windows path goes by its 8.3 short name
    where the volume keeps one, else with \\?\, which lets the browser write files past
    MAX_PATH but stops it writing a cookie file: a login to the editor is then gone at
    the next start, so only a path that needs the prefix gets it."""
    data = str(profile.resolve())
    if sys.platform != "win32" or len(data) <= 150:     # the files of IndexedDB stay inside MAX_PATH
        return data
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    if 0 < ctypes.windll.kernel32.GetShortPathNameW(data, buffer, len(buffer)) < len(buffer):
        data = min(data, buffer.value, key=len)
    return data if len(data) <= 150 else "\\\\?\\" + data


def too_deep(data: str) -> bool:
    """Whether the preview's IndexedDB fits below a profile passed as `data`."""
    return sys.platform == "win32" and len(data) + INDEXEDDB >= MAX_PATH


class Browser:
    """The machine's browser with a profile of its own and a DevTools port the
    system picks, written by the browser to DevToolsActivePort in the profile.

    The profile is kept between runs. The editor is some megabytes of scripts,
    and a page in the profile reads them from its disk cache: a run then takes
    about 4 seconds against 20 to 40 from a cold profile, and a context of its
    own per page, which has no disk cache, is cold every time."""

    def __init__(self, exe: str, profile: Path, headed: bool, extra: tuple[str, ...] = ()) -> None:
        self.profile, self.proc = profile, None
        profile.mkdir(parents=True, exist_ok=True)
        self.data = user_data_dir(profile)
        for staged in profile.glob("project-*.c3p"):    # left by a run that was stopped
            staged.unlink(missing_ok=True)
        port_file = profile / "DevToolsActivePort"
        # A run that was stopped leaves its browser running on the profile, and a
        # second browser on it hands over to the first and exits: take that one over.
        url = self.devtools_url(port_file)
        if not url:
            port_file.unlink(missing_ok=True)
            args = [exe, f"--user-data-dir={self.data}", "--remote-debugging-port=0", *QUIET, *extra,
                    "--window-size=1400,900", "about:blank"]
            self.proc = subprocess.Popen(args if headed else [*args, "--headless=new"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(75):
                url = self.devtools_url(port_file)
                if url or self.proc.poll() is not None:
                    break
                time.sleep(0.2)
        if not url:
            self.close()
            raise DevToolsError(f"{exe} opened no DevTools port in 15 seconds")
        self.port = int(port_file.read_text().split()[0])
        self.devtools = DevTools(url)
        # The window the browser started with, closed by the first page that opens.
        self.blank = [t["targetId"] for t in self.devtools.call("Target.getTargets")["targetInfos"]
                      if t["type"] == "page" and t["url"] == "about:blank"]
        self.lock = threading.Lock()

    @staticmethod
    def devtools_url(port_file: Path) -> str | None:
        try:
            port = int(port_file.read_text().split()[0])
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.load(r)["webSocketDebuggerUrl"]
        except (OSError, ValueError, IndexError, KeyError):
            return None

    def page(self, url: str) -> tuple[str, DevTools]:
        """A page in a window of its own. In a shared window every tab but the front
        one is hidden, headless too: its timers fire once a second, its animation
        frames not at all, and an editor there could sit at "Opening (0%)" for longer
        than RESULT waits."""
        target = self.devtools.call("Target.createTarget", url=url, newWindow=True)["targetId"]
        # The window the browser started with is no longer needed once another is open. Pages
        # opened at once would each find it in the list of targets; only the first closes it.
        with self.lock:
            blank, self.blank = self.blank, []
        for t in blank:
            try:
                self.devtools.call("Target.closeTarget", targetId=t)
            except DevToolsError:   # a --headed window the user closed already
                pass
        page = DevTools(f"ws://127.0.0.1:{self.port}/devtools/page/{target}")
        keep_active(page)
        return target, page

    def close(self) -> None:
        try:
            self.devtools.call("Browser.close", wait=5)
        except (AttributeError, DevToolsError, OSError):   # no connection yet, or already closed
            pass
        if self.proc:
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        # A session file per run, never restored.
        shutil.rmtree(self.profile / "Default" / "Sessions", ignore_errors=True)


def keep_active(page) -> None:
    """Keep a page visible and focused while it is driven. A headed window covered by other
    windows makes its page hidden: the editor then lays out no menu, and an opening project
    stalls at its "Opening..." dialog until a call gives up. Bringing the page to the front does
    not undo it. Focus emulation keeps the page visible, and keys reach it in the background;
    the active lifecycle state thaws a page the browser froze. Both hold as long as the
    connection or session that set them stays open. A minimized window then reports visible
    but draws nothing: a click misses what the page shows after it, and a screenshot never
    comes, so it is restored as well."""
    page.call("Emulation.setFocusEmulationEnabled", enabled=True)
    page.call("Page.setWebLifecycleState", state="active")


def load(page: DevTools, editor: str) -> None:
    """Until the editor's page has loaded. A new page starts as about:blank, whose
    readyState is complete too, and its context goes away as the editor loads."""
    where = ["", "", 0]
    for _ in range(150):
        try:
            where = page.evaluate("[location.href, document.readyState, "
                                  "performance.getEntriesByType('navigation')[0]?.responseStatus || 0]")
        except DevToolsError:
            pass
        if where[0].startswith("chrome-error:"):
            raise EditorNotLoaded(f"{editor} could not be reached")
        if where[0].startswith(EDITOR) and where[1] == "complete":     # /beta redirects to its release
            break
        time.sleep(0.2)
    else:
        raise EditorNotLoaded(f"{editor} did not finish loading in 30 seconds")
    if where[2] >= 400:
        raise EditorNotLoaded(f"{editor} answered HTTP {where[2]}")


def message_text(event: dict) -> str | None:
    """An uncaught exception or a console.error of a Runtime event, else None."""
    p = event["params"]
    if event["method"] == "Runtime.exceptionThrown":
        d = p["exceptionDetails"]
        return d.get("exception", {}).get("description") or d.get("text", "exception")
    if event["method"] == "Runtime.consoleAPICalled" and p["type"] in ("error", "assert"):
        args = [str(a.get("value", a.get("description", ""))) for a in p["args"]]
        styles = args[0].count("%c") if args else 0     # the runtime styles its messages: "%cEvent sheet 1", css
        return " ".join([args[0].replace("%c", ""), *args[1 + styles:]]) if args else ""
    return None


def start_preview(browser: Browser, target: str, page: DevTools) -> tuple[dict, DevTools] | list[str]:
    """Press F5 in the editor, as the user would, and connect to the preview window
    it opens; or the reasons it opened none."""
    for kind in ("rawKeyDown", "keyUp"):
        page.call("Input.dispatchKeyEvent", type=kind, key="F5", code="F5", windowsVirtualKeyCode=116)
    window = None
    for _ in range(80):
        window = next((t for t in browser.devtools.call("Target.getTargets")["targetInfos"]
                       if t["type"] == "page" and t.get("openerId") == target), None)
        dialogs = page.evaluate(OPEN_DIALOGS_JS)
        if window or dialogs:
            break
        time.sleep(0.25)
    if not window:
        return dialogs or ["no preview window in 20 seconds"]
    win = DevTools(f"ws://127.0.0.1:{browser.port}/devtools/page/{window['targetId']}")
    keep_active(win)
    return window, win


def attach(win: DevTools, patience: float = 0) -> tuple[list[str | None], list[str | None], bool]:
    """Leave the probe where the game runs: the preview page, None, or one of its
    workers, a session id. Returns every session, the one that runs the game (an
    empty list when none does), and whether a runtime was found that did not tick.
    A preview that is still loading answers nothing yet; it is asked again for
    `patience` seconds."""
    win.call("Target.setAutoAttach", autoAttach=True, waitForDebuggerOnStart=False, flatten=True)
    end = time.monotonic() + patience
    while True:
        gone = {e["params"]["sessionId"] for e in win.events if e["method"] == "Target.detachedFromTarget"}
        sessions = [None] + [e["params"]["sessionId"] for e in win.events
                             if e["method"] == "Target.attachedToTarget"
                             and e["params"]["targetInfo"]["type"] == "worker" and e["params"]["sessionId"] not in gone]
        answers = []
        for session in sessions:
            try:
                answers.append(win.evaluate(PROBE_JS, wait=6, session=session))
            except DevToolsError:
                if not patience:
                    raise
                answers.append(None)    # the page replaced its context while loading
        live = [s for s, answer in zip(sessions, answers) if answer is True]
        if live or False in answers or time.monotonic() >= end:
            return sessions, live, False in answers
        time.sleep(0.25)


def runtime_errors(win: DevTools) -> list[str]:
    """The uncaught exceptions and console errors logged since the last call, once
    Runtime.enable has been sent to the session they came from."""
    errors = [text[:600] for text in map(message_text, win.events) if text]
    win.events[:] = [e for e in win.events if e["method"].startswith("Target.")]
    return errors


def preview(browser: Browser, editor: tuple[str, DevTools], seconds: float, state: list[str] | None = None) -> dict:
    """Preview the layout the editor shows, let it run for `seconds`, then read what
    the runtime reported, and with `state` what the game holds.

    Nothing listens while it runs: Runtime.enable hands over what a page or worker
    logged before it, so the preview page and its workers, the runtime in one of
    them, are attached once at the end."""
    target, page = editor
    started = start_preview(browser, target, page)
    if isinstance(started, list):
        return {"started": False, "layout": None, "runtime": None, "errors": started}
    window, win = started
    time.sleep(seconds)
    try:
        sessions, live, stalled = attach(win)
        snap, read = None, None
        if live:
            snap = win.evaluate("c3probe.snapshot([], 0)", wait=6, session=live[0])
            if state is not None:
                read = read_state(win, live[0], state)
        for session in sessions:
            win.call("Runtime.enable", session=session)
        win.evaluate("0")       # an answer after every replayed message
        errors = runtime_errors(win)
    finally:
        win.ws.close()
        browser.devtools.call("Target.closeTarget", targetId=window["targetId"])
    if not live:
        errors.insert(0, "the runtime loaded but did not tick for 3 seconds" if stalled
                      else "the preview window opened but no runtime was found in it")
    return {"started": bool(snap), "layout": snap and snap["layout"],
            "runtime": ("worker" if live[0] else "page") if live else None,
            "ticks": snap and snap.get("tickCount"), "wallTime": snap and snap.get("wallTime"), "errors": errors,
            **({"state": read} if read else {})}


def read_state(win: DevTools, session: str | None, names: list[str]) -> dict:
    """For --state: the global variables, the count of every type that has instances,
    and the instances of the types named, through the probe the preview holds."""
    def call(js: str):
        return win.evaluate(js, wait=6, session=session)
    try:
        snap = call("c3probe.snapshot(null, 0)")
        read = {"globalVars": snap["globalVars"] or {},
                "counts": {name: o["count"] for name, o in snap["objects"].items()}, "objects": {}}
        if names:
            read["objects"] = call(f"c3probe.snapshot({json.dumps(names)}, {STATE_MAX})")["objects"]
            if None in read["objects"].values():
                read["types"] = call("Object.keys(c3probe.runtime.objects)")
        return read
    except DevToolsError as e:
        return {"error": str(e)}


def key_name(key: str) -> str:
    """The last word of a key of the editor's language files: max-speed for
    behaviors.platform.properties.max-speed.name."""
    words = key.split(".")
    if len(words) > 2 and words[-1] in ("name", "title"):
        words.pop()
    return words[-1]


def value_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and math.isfinite(value):
        value = round(value, 2)
        return str(int(value)) if value == int(value) else str(value)
    if isinstance(value, str):
        return json.dumps(value[:80], ensure_ascii=False)
    if isinstance(value, list):
        return "/".join(key_name(v) if isinstance(v, str) else value_text(v) for v in value)
    return "null" if value is None else str(value)


def instance_lines(inst: dict) -> list[str]:
    """One line for an instance, then one per plugin or behavior section of the
    debugger's Inspect tab."""
    words = [f"uid {inst['uid']}"]
    if "x" in inst:
        words.append(f"at ({value_text(inst['x'])}, {value_text(inst['y'])}) "
                     f"{value_text(inst['width'])}x{value_text(inst['height'])}")
        if inst.get("angle"):
            words.append(f"angle {value_text(inst['angle'])}")
        words.append(f"on {inst['layer']}")
        if inst.get("isVisible") is False:
            words.append("hidden")
        if inst.get("opacity", 1) != 1:
            words.append(f"opacity {value_text(inst['opacity'])}")
    if inst.get("text") is not None:
        words.append(f"text {value_text(inst['text'])}")
    look = inst.get("inspector")
    if not look and inst.get("animationName") is not None:
        words.append(f"animation {inst['animationName']} frame {inst['animationFrame']}")
    line = ", ".join(words)
    if inst.get("instVars"):
        line += "; " + ", ".join(f"{k} {value_text(v)}" for k, v in inst["instVars"].items())
    lines = [f"    {line}"]
    if look:
        sections = [(s["title"].split(".")[1] if s["title"].startswith("plugins.") else key_name(s["title"]), s["values"])
                    for s in look["plugin"]] + list(look["behaviors"].items())
        lines += [f"      {label}: " + ", ".join(f"{key_name(k)} {value_text(v)}" for k, v in values.items())
                  for label, values in sections if values]
    return lines


def state_lines(read: dict) -> list[str]:
    if "error" in read:
        return [f"  state: not read: {read['error'].splitlines()[0]}"]
    lines = ["  globals: " + (", ".join(f"{k} {value_text(v)}" for k, v in read["globalVars"].items()) or "none"),
             "  objects: " + (", ".join(f"{k} {n}" for k, n in read["counts"].items()) or "none")]
    for name, o in read["objects"].items():
        if o is None:
            lines.append(f"  {name}: no object type of that name{c3.closest(name, read.get('types', []))}")
            continue
        lines.append(f"  {name}: {o['count']} instance{'' if o['count'] == 1 else 's'}")
        for inst in o["instances"]:
            lines += instance_lines(inst)
        if o["count"] > len(o["instances"]):
            lines.append(f"    and {o['count'] - len(o['instances'])} more, not read")
    return lines


def open_one(browser: Browser, editor: str, project: Path, staged: Path, shot: Path | None,
             pinned: bool, then: Callable[[Browser, str, DevTools], dict] | None = None) -> dict:
    """In the editor at `editor`; unless the release is pinned, a project saved by a
    newer release than that editor's, which it refuses as saved in a newer version,
    is opened in the latest beta instead. Once it opened, `then` previews it, given
    the browser and the editor's target and page, and its answer is the result's
    `preview`."""
    staged.write_bytes(pack(project))
    target, page = browser.page(editor)
    try:
        load(page, editor)
        saved, (major, minor) = saved_release(project), (page.evaluate(RELEASE_JS) + [0, 0])[:2]
        if not pinned and major and saved > major * 100 + minor:
            page.ws.close()
            browser.devtools.call("Target.closeTarget", targetId=target)
            editor = BETA
            target, page = browser.page(editor)
            load(page, editor)
        editor = page.evaluate("location.origin + location.pathname")
        ready = page.evaluate(f"({SETUP_JS})()", wait=SETUP_WAIT)
        if ready != "ready":
            raise EditorNotLoaded(ready)
        started = time.monotonic()
        field = page.evaluate("document.querySelector('input[aria-label=\"Project to open\"]')", by_value=False)
        page.call("DOM.setFileInputFiles", files=[str(staged)], objectId=field["objectId"])
        result = page.evaluate(f"({RESULT_JS})()", wait=RESULT_WAIT)
        if shot:
            shot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot")["data"]))
        if isinstance(result, str):
            result = {"opened": False, "title": "", "dialogs": [], "warnings": [], "errors": [result]}
        ran = None
        if result["opened"] and then and too_deep(browser.data):
            most = MAX_PATH - 1 - INDEXEDDB
            ran = {"started": False, "layout": None, "runtime": None, "errors": [
                f"the browser profile {browser.data} is {len(browser.data)} characters long, and the preview's "
                f"IndexedDB needs it at most {most}: copy the project to a shorter folder, or pass --profile "
                f"<a folder of at most {most - len('/editor-chromium')} characters>"]}
        elif result["opened"] and then:
            try:
                ran = then(browser, target, page)
            except DevToolsError as e:
                ran = {"started": False, "layout": None, "runtime": None, "errors": [f"the preview stopped answering: {e}"]}
    finally:
        page.ws.close()
        browser.devtools.call("Target.closeTarget", targetId=target)
        staged.unlink(missing_ok=True)

    status = "opened" if result["opened"] else "failed" if result["dialogs"] or result["errors"] else "timeout"
    return {"project": str(project), "status": status, "title": result["title"], "dialogs": result["dialogs"],
            "warnings": result["warnings"], "exception": next(iter(result["errors"]), ""), "editor": editor,
            "seconds": round(time.monotonic() - started, 1), **({"preview": ran} if ran else {})}


def addon_json(addon: Path) -> dict | str:
    """The addon.json of a .c3addon, or what is wrong with it, before the editor reads it."""
    try:
        with zipfile.ZipFile(addon) as z:
            raw = z.read("addon.json")
    except KeyError:
        return "no addon.json at the root of the zip: zip the files of the addon, not its folder"
    except (OSError, zipfile.BadZipFile) as e:
        return f"not a zip file: {e}"
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return f"addon.json is not valid JSON: {e}"
    return data if isinstance(data, dict) else "addon.json is not a JSON object"


def install_addon(browser: Browser, editor: str, addon: Path) -> dict:
    """Drop the addon on the editor of the profile and answer its dialogs."""
    found = addon_json(addon)
    if isinstance(found, str):
        return {"addon": str(addon), "status": "refused", "dialog": "", "exception": found}
    target, page = browser.page(editor)
    try:
        load(page, editor)
        ready = page.evaluate(f"({SETUP_JS})()", wait=SETUP_WAIT)
        if ready != "ready":
            raise EditorNotLoaded(ready)
        field = page.evaluate("document.querySelector('input[aria-label=\"Project to open\"]')", by_value=False)
        page.call("DOM.setFileInputFiles", files=[str(addon)], objectId=field["objectId"])
        result = page.evaluate(f"({INSTALL_JS})()", wait=RESULT_WAIT)
    finally:
        page.ws.close()
        browser.devtools.call("Target.closeTarget", targetId=target)
    if isinstance(result, str):
        result = {"installed": False, "dialog": "", "errors": [result]}
    return {"addon": str(addon), "status": "installed" if result["installed"] else "refused",
            "name": found.get("name", ""), "version": found.get("version", ""), "type": found.get("type", ""),
            "dialog": result["dialog"], "exception": next(iter(result["errors"]), "")}


def addon_report(result: dict) -> list[str]:
    if result["status"] == "installed":
        return [f"installed {result['addon']}  ({result['name']} {result['version']}, {result['type']})"]
    lines = [f"refused  {result['addon']}"]
    if result["dialog"]:
        lines.append(f"  editor: {result['dialog']}")
    if result["exception"]:
        lines.append(f"  exception: {result['exception'].splitlines()[0]}")
    return lines


def report(result: dict) -> list[str]:
    if result["status"] == "error":
        return [f"error    {result['project']}: {result['exception']}"]
    if result["status"] == "opened":
        lines = [f"opened   {result['project']}  ({result['title']}, {result['editor']})"]
        lines += [f"  warning: {w}" for w in result.get("warnings", [])]
        ran = result.get("preview")
        if ran and ran["started"]:
            n = len(ran["errors"])
            ticks = (f"{ran['ticks']} ticks in {ran['wallTime']:.1f} s, "
                     if ran.get("ticks") is not None and ran.get("wallTime") is not None else "")
            lines.append(f"  preview: layout {ran['layout']!r}, runtime in the {ran['runtime']}, {ticks}"
                         f"{n or 'no'} error{'' if n == 1 else 's'}")
            lines += [f"  runtime: {e.splitlines()[0]}" for e in ran["errors"]]
            if ran.get("state"):
                lines += state_lines(ran["state"])
        elif ran:
            lines += [f"  preview did not run: {e}" for e in ran["errors"]]
        return lines
    lines = [f"{result['status']:<8} {result['project']}"]
    lines += [f"  editor: {d}" for d in result["dialogs"]]
    lines += [f"  warning: {w}" for w in result.get("warnings", [])]
    if result["status"] == "timeout":
        lines.append(f"  editor: no answer in 45 seconds, the title is {result['title']!r}; "
                     f"its screenshot shows what the editor shows")
    if result["exception"]:
        lines.append(f"  exception: {result['exception'].splitlines()[0]}")
    return lines


def failed(result: dict) -> bool:
    return result["status"] != "opened" or bool(result.get("preview", {}).get("errors"))


def summary(results: list[dict], previewed: bool, out: Path, shots: Path) -> str:
    done = "opened and ran without errors" if previewed else "opened"
    return (f"{sum(not failed(r) for r in results)} of {len(results)} {done}; full results in {out}, "
            f"screenshots in {shots}")


def run(projects: list[Path], editor: str, exe: str, args) -> list[dict]:
    first = projects[0] if projects[0].is_dir() else projects[0].parent
    # One profile per browser: Chrome does not load a profile Edge has written.
    browser = Browser(exe, (args.profile or scratch(first)) / f"editor-{Path(exe).stem.lower()}", args.headed)
    results: list[dict] = []
    for addon in args.install_addon:
        try:
            done = install_addon(browser, editor, addon)
        except (EditorNotLoaded, DevToolsError, OSError) as e:
            done = {"addon": str(addon), "status": "refused", "dialog": "", "exception": str(e)}
        print("\n".join(addon_report(done)), flush=True)
        if done["status"] != "installed":
            browser.close()
            print("the addon was not installed, so no project was opened: fix addon.json or the file the "
                  "exception names, zip the addon again and run again")
            raise AddonRefused
    printed = 0     # characters; results are printed as they come, until --limit
    lock = threading.Lock()

    def one(i: int, project: Path) -> None:
        nonlocal printed
        shot = args.shots / f"{i:03d}-{project.name}.png"
        try:
            then = (lambda b, t, p: preview(b, (t, p), args.preview, args.state)) if args.preview is not None else None
            result = open_one(browser, editor, project, browser.profile / f"project-{i}.c3p", shot,
                              bool(args.release), then)
        except (EditorNotLoaded, DevToolsError, OSError) as e:
            result = {"project": str(project), "status": "error", "title": "", "dialogs": [], "warnings": [],
                      "exception": str(e), "editor": editor, "seconds": 0}
        with lock:
            results.append(result)
            lines = report(result)
            shown = c3.fitting(lines, max(1, args.limit - printed) if args.limit else 0)
            if shown:
                text = "\n".join(lines[:shown])
                print(text, flush=True)
                printed += len(text) + 1
            if shown < len(lines):
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
                         "(default: the current stable release, the one the user gets, or the latest beta for a "
                         "project a newer release saved)")
    ap.add_argument("--preview", type=float, nargs="?", const=5, metavar="SECONDS",
                    help="once it opened, preview the layout the editor shows for this long (default 5) and print "
                         "the layout, the uncaught exceptions and the console errors of the runtime")
    ap.add_argument("--state", nargs="*", metavar="TYPE",
                    help="at the end of the preview (5 seconds unless --preview says), print the global variables, "
                         f"the instance count of every object type, and the first {STATE_MAX} instances of each TYPE "
                         "named, as the project spells it; --out keeps them as JSON")
    ap.add_argument("--install-addon", type=Path, nargs="+", default=[], metavar="FILE",
                    help="install these .c3addon files into the editor of the browser profile before opening the "
                         "project, which keeps them for later runs; an addon the editor refuses stops the run")
    ap.add_argument("--profile", type=Path, metavar="FOLDER",
                    help="keep the browser profile in FOLDER/editor-<browser> instead of the project's .tmp/, for a "
                         "project too deep for the preview's IndexedDB, which it then names")
    ap.add_argument("--out", type=Path, help="write every result, dialogs and exceptions included, as JSON "
                                             "(default: .tmp/open-in-editor.json in the project)")
    ap.add_argument("--shots", type=Path, help="save a screenshot of the editor per project into this folder "
                                               "(default: .tmp/shots in the project)")
    ap.add_argument("--jobs", type=int, default=2, help="projects open at once (default 2)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--limit", type=int, default=c3.LIMIT, metavar="CHARS",
                    help=f"stop printing results after about this many characters, since a harness cuts longer "
                         f"tool output; --out keeps them all, 0 prints everything (default: {c3.LIMIT})")
    args = ap.parse_args()
    if args.state is not None and args.preview is None:
        args.preview = 5

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
    if why and args.install_addon:
        print(f"{why}: drop {', '.join(map(str, args.install_addon))} on the editor in the browser tool's page and "
              f"click Install, then follow these steps.")
    if why:
        print(steps(projects[0], editor, why))
        if args.preview is not None:
            print("\n--preview is not part of these steps: once it opened, press F5 in the editor page and read the "
                  "console of the preview window it opens.")
            if args.state is not None:
                print("To read the game's state there, evaluate assets/runtime-probe.js in the preview window, as "
                      "references/reading-the-runtime.md says.")
        return 3

    args.out, args.shots = kept(args.out, args.shots, projects[0] if projects[0].is_dir() else projects[0].parent)
    args.shots.mkdir(parents=True, exist_ok=True)
    missing = [a for a in args.install_addon if not a.is_file()]
    if missing:
        print(f"no file {', '.join(map(str, missing))}: pass the .c3addon's path", file=sys.stderr)
        return 2
    # The browser takes a file input's path from its own working directory.
    args.install_addon = [a.resolve() for a in args.install_addon]
    args.profile = args.profile and args.profile.resolve()
    try:
        results = run(projects, editor, exe, args)
    except AddonRefused:
        return 1
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
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    if all(r["status"] == "error" for r in results):
        print("the editor did not load for any project. Check the network connection and --release, and run "
              "again; without a connection, ask the user to open the project in Construct 3 and paste the text "
              "of the dialog it shows.", file=sys.stderr)
        return 2
    if unprinted:
        print(f"{unprinted} results not printed in full: {args.out} keeps every one, --limit 0 prints them")
    print(summary(results, args.preview is not None, args.out, args.shots))
    if any(r["status"] != "opened" for r in results):
        print(NEXT)
    if any(r.get("preview", {}).get("errors") for r in results):
        print(NEXT_PREVIEW)
    return 1 if any(failed(r) for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
