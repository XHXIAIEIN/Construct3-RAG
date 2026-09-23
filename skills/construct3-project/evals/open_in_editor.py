"""Open projects in the Construct 3 editor and report whether each one opens.

    python evals/open_in_editor.py PATH [PATH ...] [--out RESULTS.json] [--shots DIR] [--jobs 2] [--headed]

A PATH is a folder project (the folder that holds project.c3proj), a .c3p,
or any folder above them: every project.c3proj below it is opened, so an
eval iteration folder opens all of its runs. Each project is opened in a
fresh browser profile on https://editor.construct.net/, the way a user
drops a .c3p onto the editor, and its outcome is read from the editor: the
window title turns to the project's name, or a dialog says why it did not
open, with the exception the editor logged.

It needs Playwright and its Chromium (pip install playwright, then
playwright install chromium) and a network connection. Nothing is written
to a project. One line per project goes to stdout; --out keeps the dialogs
and console messages of every run.

exit codes: 0 every project opened; 1 at least one did not; 2 no project
found, Playwright missing, or the editor did not load
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

EDITOR = "https://editor.construct.net/"
# Served by a route on the editor's own origin: a page on a public origin may
# not fetch from localhost, so a local file server would be refused.
PROJECT_URL = EDITOR + "__open_in_editor__/project.c3p"

STATE_JS = """() => ({
  title: document.title,
  dialogs: [...document.querySelectorAll('dialog[open]')]
    .filter(d => d.id !== 'progressDialog')
    .map(d => d.innerText.trim().replace(/\\s+/g, ' ').slice(0, 400)),
  opening: !!document.querySelector('dialog#progressDialog[open]'),
})"""

# A synthetic drop is handled like a file dropped from the desktop.
DROP_JS = """async (url) => {
  const buf = await (await fetch(url)).arrayBuffer();
  const dt = new DataTransfer();
  dt.items.add(new File([buf], 'project.c3p'));
  const target = document.elementFromPoint(innerWidth / 2, innerHeight / 2) || document.body;
  for (const type of ['dragenter', 'dragover', 'drop'])
    target.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt}));
}"""


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
            if f.is_file() and ".git" not in f.relative_to(project).parts:
                z.write(f, f.relative_to(project).as_posix())
    return buf.getvalue()


async def open_one(browser, project: Path, timeout: float, shot: Path | None) -> dict:
    body = pack(project)
    console: list[str] = []
    # A new context is a new profile: the editor starts with its welcome dialog and no open project.
    # Its service worker would answer the project fetch before the route could.
    ctx = await browser.new_context(service_workers="block", viewport={"width": 1400, "height": 900})
    try:
        await ctx.route(PROJECT_URL, lambda r: r.fulfill(status=200, body=body, content_type="application/zip"))
        page = await ctx.new_page()
        page.on("console", lambda m: m.type == "error" and console.append(m.text[:600]))
        page.on("pageerror", lambda e: console.append(f"pageerror: {e}"[:600]))
        try:
            await page.goto(EDITOR, wait_until="load", timeout=120_000)
            await page.wait_for_selector("a.noThanksLink", timeout=120_000)
        except Exception as e:  # Playwright raises its own TimeoutError and network errors alike
            raise EditorNotLoaded(str(e).splitlines()[0]) from e
        await page.click("a.noThanksLink")
        await page.wait_for_timeout(500)
        for button in await page.query_selector_all("dialog[open] button"):
            if (await button.inner_text()).strip() == "OK":
                await button.click()
        start_title = (await page.evaluate(STATE_JS))["title"]

        started = time.monotonic()
        await page.evaluate(DROP_JS, PROJECT_URL)
        state = {"title": start_title, "dialogs": [], "opening": True}
        while time.monotonic() - started < timeout:
            await page.wait_for_timeout(1000)
            state = await page.evaluate(STATE_JS)
            if not state["opening"] and (state["dialogs"] or state["title"] != start_title):
                await page.wait_for_timeout(2000)  # an error dialog can follow the title by a moment
                state = await page.evaluate(STATE_JS)
                break
        if shot:
            await page.screenshot(path=str(shot))
    finally:
        await ctx.close()

    opened = state["title"] != start_title and not state["dialogs"]
    status = "opened" if opened else "timeout" if state["opening"] or not state["dialogs"] else "failed"
    exception = next((c for c in console if "Exception" in c or c.startswith("pageerror")), "")
    return {"project": str(project), "status": status, "title": state["title"], "dialogs": state["dialogs"],
            "exception": exception, "seconds": round(time.monotonic() - started, 1), "console": console}


def line(result: dict) -> str:
    if result["status"] == "opened":
        return f"opened   {result['project']}  ({result['title']})"
    why = " | ".join(result["dialogs"]) or "no dialog, the title did not change"
    first = result["exception"].splitlines()[0] if result["exception"] else ""
    return f"{result['status']:<8} {result['project']}: {why}" + (f" | {first}" if first else "")


async def run(projects: list[Path], args: argparse.Namespace) -> list[dict]:
    from playwright.async_api import async_playwright

    results: list[dict] = []
    gate = asyncio.Semaphore(args.jobs)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)

        async def one(i: int, project: Path) -> None:
            async with gate:
                shot = args.shots / f"{i:03d}-{project.name}.png" if args.shots else None
                result = await open_one(browser, project, args.timeout, shot)
                results.append(result)
                print(line(result), flush=True)

        try:
            await asyncio.gather(*(one(i, pr) for i, pr in enumerate(projects)))
        finally:
            await browser.close()
    return sorted(results, key=lambda r: r["project"])


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path, metavar="PATH")
    ap.add_argument("--out", type=Path, help="write every result, dialogs and console errors included, as JSON")
    ap.add_argument("--shots", type=Path, help="save a screenshot of the editor per project into this folder")
    ap.add_argument("--jobs", type=int, default=2, help="projects open at once (default 2)")
    ap.add_argument("--timeout", type=float, default=90, help="seconds to wait for one project to open (default 90)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    args = ap.parse_args()

    projects = find_projects(args.paths)
    if not projects:
        print("no project.c3proj or .c3p found under: " + ", ".join(map(str, args.paths)), file=sys.stderr)
        return 2
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("Playwright is missing: run pip install playwright, then playwright install chromium", file=sys.stderr)
        return 2
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    try:
        results = asyncio.run(run(projects, args))
    except EditorNotLoaded as e:
        print(f"the editor did not load from {EDITOR}: {e}. Check the network connection and run again.",
              file=sys.stderr)
        return 2
    if args.out:
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = [r for r in results if r["status"] != "opened"]
    print(f"{len(results) - len(failed)} of {len(results)} opened" + (f"; full results in {args.out}" if args.out else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
