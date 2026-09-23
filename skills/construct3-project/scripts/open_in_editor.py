"""Open a project in the Construct 3 editor and print whether it opens, or the
editor's message when it does not.

    python scripts/open_in_editor.py [PATH ...] [--project FOLDER] [--steps] [--release rNNN]
                                     [--shots DIR] [--out RESULTS.json] [--jobs 2] [--headed]

Run it when check_project.py ends with ok:. The checker reads the files; the
editor also reads the events, and refuses a project for what the checker does
not see, a type mismatch in an expression among them. The project goes to
https://editor.construct.net/ the way a user drops a .c3p onto it: the window
title turns to the project's name, or a dialog says why it did not open, with
the exception the editor logged. The file is handed to the page in the
browser, not uploaded to a server.

Where Python has Playwright (pip install playwright), the script does it all
in a browser of its own: Playwright's Chromium, else Microsoft Edge, else
Google Chrome. Where it has not, or with --steps, it writes the project as
.tmp/open-in-editor.c3p in the project folder and prints the same steps for
whatever browser tool the agent has: one that opens a page, runs JavaScript
in it and puts a file on a file input. A project takes about 10 seconds.

Without a PATH it opens the project the current directory is in. A PATH is a
folder project (the folder that holds project.c3proj), a .c3p, or any folder
above them: every project.c3proj below it is opened.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import c3project as c3

EPILOG = """examples:
  python scripts/open_in_editor.py
  python scripts/open_in_editor.py --steps
  python scripts/open_in_editor.py --project "D:/Games/Snake" --release r502
  python scripts/open_in_editor.py <eval iteration folder> --jobs 3 --out opened.json

output, one entry per project:
  opened   <project>  (<window title>)
  failed   <project>
    editor: <the dialog's text, which names the sheet, event and parameter at fault>
    exception: <the first line of the exception the editor logged>

exit codes: 0 every project opened; 1 at least one did not; 2 no project
found, or the editor did not load; 3 the steps for a browser tool were printed
instead, the project is not opened yet
"""

EDITOR = "https://editor.construct.net/"
# Playwright's own build first, then a browser a Windows or Mac machine already has.
CHANNELS = (None, "msedge", "chrome")
# Inside the project, where check_project.py does not look and the editor does not write.
SCRATCH = ".tmp"

# The page side, the same for the script and for an agent's browser tool. Each
# function waits inside the page, so a tool calls it once instead of polling.
#
# SETUP waits until the editor has loaded and no dialog has been open for 2 seconds,
# closing the ones it shows on start: a file dropped while the welcome dialog closes
# is ignored, and the update offers come a moment after the menu. Then it keeps what
# the editor logs as an error and puts a file input at the top of the page. A file
# put on that input is dropped on the editor, which handles a synthetic drop like a
# file dragged from the desktop, and the editor's answer is awaited in the page.
SETUP_JS = r"""async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const open = () => [...document.querySelectorAll('dialog[open]')].filter(d => d.id !== 'progressDialog');
  const text = d => d.innerText.trim().replace(/\s+/g, ' ').slice(0, 1500);
  for (let calm = 0, i = 0; calm < 4; i++) {
    if (i > 120) return 'not ready: ' + (open().map(text).join(' | ') || 'the editor did not load');
    await wait(500);
    document.querySelector('a.noThanksLink')?.click();
    open().forEach(d => d.querySelector('ui-close-button, .okButton')?.click());
    calm = document.getElementById('mainMenuButton') && !open().length ? calm + 1 : 0;
  }
  const errors = [], log = console.error.bind(console);
  console.error = (...a) => { errors.push(a.map(String).join(' ').slice(0, 600)); log(...a); };
  const start = document.title, input = document.createElement('input');
  input.type = 'file';
  input.setAttribute('aria-label', 'Project to open');
  input.style.cssText = 'position:fixed;left:8px;top:8px;z-index:2147483647;background:#fff';
  document.body.prepend(input);
  input.onchange = () => window.__c3Open = (async () => {
    const dt = new DataTransfer();
    dt.items.add(input.files[0]);
    input.remove();
    const target = document.elementFromPoint(innerWidth / 2, innerHeight / 2) || document.body;
    for (const type of ['dragenter', 'dragover', 'drop'])
      target.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt}));
    for (let i = 0; i < 180; i++) {
      await wait(500);
      if (!document.querySelector('dialog#progressDialog[open]') && (open().length || document.title !== start)) {
        await wait(1500);
        const dialogs = open().map(text);
        return {opened: !dialogs.length && document.title !== start, title: document.title, dialogs,
                errors: errors.filter(e => e.includes('Exception'))};
      }
    }
    return {opened: false, timeout: true, title: document.title, dialogs: open().map(text), errors};
  })();
  return 'ready';
}"""

RESULT_JS = "async () => await window.__c3Open ?? 'no file on the input yet: put the .c3p on it first'"

NEXT = ("next: the editor's message names the place, `Game, event 12, condition 1` is event 12 of sheet Game "
        "as scripts/print_sheet.py numbers it. Fix it, run scripts/check_project.py, then this script again. "
        "When the checker passed what the editor refused, tell the user the message: the checker lacks that rule.")


class EditorNotLoaded(Exception):
    pass


class NoBrowser(Exception):
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
a file on a file input, in five calls; each function waits in the page, so call it once:
1. Open {editor} in a new page, in an isolated context if the tool has one.
2. Run SETUP in it (a tool that takes an expression gets it called: `(...)()`). It returns "ready".
3. Put this file on the input labelled "Project to open", the first element of the page, with the
   tool's upload action; a tool that waits for a file chooser gets one by clicking the input:
   {c3p}
4. Run RESULT. It returns {{opened, title, dialogs, errors}}. opened true is the hand-over.
   Otherwise the dialog names the place and errors holds the exception the editor logged.
   {NEXT.removeprefix("next: ")}
Without such a tool, ask the user to open the project in Construct 3 and paste the text of the
dialog it shows.{tail}

SETUP:
{SETUP_JS}

RESULT:
{RESULT_JS}"""


async def open_one(browser, editor: str, project: Path, shot: Path | None) -> dict:
    body = pack(project)
    # A new context is a new profile: the editor starts with its welcome dialog and no open project.
    ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
    try:
        page = await ctx.new_page()
        try:
            response = await page.goto(editor, wait_until="load", timeout=120_000)
        except Exception as e:  # Playwright raises its own TimeoutError and network errors alike
            raise EditorNotLoaded(str(e).splitlines()[0]) from e
        if response and response.status >= 400:
            raise EditorNotLoaded(f"{editor} answered HTTP {response.status}")
        ready = await page.evaluate(SETUP_JS)
        if ready != "ready":
            raise EditorNotLoaded(ready)
        started = time.monotonic()
        await page.get_by_label("Project to open").set_input_files(
            files=[{"name": "project.c3p", "mimeType": "application/zip", "buffer": body}])
        result = await page.evaluate(RESULT_JS)
        if shot:
            await page.screenshot(path=str(shot))
    finally:
        await ctx.close()

    status = "opened" if result["opened"] else "timeout" if result.get("timeout") else "failed"
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


async def launch(p, headless: bool):
    missing = []
    for channel in CHANNELS:
        try:
            return await p.chromium.launch(headless=headless, channel=channel)
        except Exception as e:  # Playwright raises a plain Error for a missing executable
            missing.append(f"{channel or 'chromium'}: {str(e).splitlines()[0]}")
    raise NoBrowser("; ".join(missing))


async def run(projects: list[Path], editor: str, args) -> list[dict]:
    from playwright.async_api import async_playwright

    results: list[dict] = []
    printed = 0     # characters; results are printed as they come, until --limit
    gate = asyncio.Semaphore(args.jobs)
    async with async_playwright() as p:
        browser = await launch(p, headless=not args.headed)

        async def one(i: int, project: Path) -> None:
            nonlocal printed
            async with gate:
                shot = args.shots / f"{i:03d}-{project.name}.png" if args.shots else None
                result = await open_one(browser, editor, project, shot)
                results.append(result)
                text = "\n".join(report(result))
                if not args.limit or printed + len(text) <= args.limit:
                    print(text, flush=True)
                    printed += len(text) + 1
                else:
                    result["unprinted"] = True

        try:
            await asyncio.gather(*(one(i, pr) for i, pr in enumerate(projects)))
        finally:
            await browser.close()
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
    why = "not opened here (--steps)" if args.steps else None
    if not why:
        try:
            import playwright  # noqa: F401
        except ImportError:
            why = "Python has no Playwright here"
    if why and len(projects) > 1:
        print(f"{why}, and {len(projects)} projects were found; name one with --project", file=sys.stderr)
        return 2
    if why:
        print(steps(projects[0], editor, why))
        return 3

    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    try:
        results = asyncio.run(run(projects, editor, args))
    except NoBrowser as e:
        if len(projects) == 1:
            print(steps(projects[0], editor, f"Playwright found no browser to start ({e})"))
            return 3
        print(f"Playwright found no browser to start ({e}); python -m playwright install chromium installs one",
              file=sys.stderr)
        return 2
    except EditorNotLoaded as e:
        print(f"the editor did not load from {editor}: {e}. Check the network connection and --release, and "
              f"run again; without a connection, ask the user to open the project in Construct 3 and paste the "
              f"text of the dialog it shows.", file=sys.stderr)
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
