"""Put every event of the official examples back as print_sheet.py --show prints it, and list the sheets it changes.

    python evals/sweep_round_trip.py [--examples FOLDER] [--cli] [--workers 8] [--limit 40]

For each event N of each sheet, the JSON that `print_sheet.py SHEET --show N`
prints is applied as the plan [{"replace": N, "events": [<that JSON>]}] the
way edit_sheet.py applies it, and the sheet edit_sheet.py would write is
compared with the file. The invariant is that they are byte for byte the
same: a plan that puts an event back unchanged changes nothing. The sweep
calls the two scripts' functions in this process, without the checker, so
that the 17 000 events of the examples take seconds, not the hours that two
script runs per event take.

--cli runs the two scripts as an agent does, on the first event of every
sheet, in a copy of the project without its media: what the checker and the
writing add to the round trip. A sheet the clone checked out with CRLF line
ends is compared after its line ends are turned into LF, as the repository
of the examples stores it.

tests/test_skill_edit_sheet.py runs the same invariant through the scripts on
every event of the stand-in game and on a few events of the examples, one for
each defect this sweep found.

exit codes: 0 no event changes its sheet; 1 some do, listed; 2 no example
projects found
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import c3project as c3  # noqa: E402
import edit_sheet  # noqa: E402
import print_sheet  # noqa: E402

MEDIA = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.svg", "*.webm", "*.ogg", "*.m4a", "*.mp3", "*.mp4",
         "*.wav", "*.opus", "*.woff", "*.woff2", "*.ttf", "*.otf", "*.zip", "*.glb", "*.gltf", "*.bin")


def sheet_files(project: Path) -> list[Path]:
    folder = project / "eventSheets"
    return sorted(folder.rglob("*.json")) if folder.is_dir() else []


def first_change(before: str, after: str) -> str:
    """The first line that differs, as the line before and the line after."""
    for i, (a, b) in enumerate(zip(before.splitlines(), after.splitlines()), 1):
        if a != b:
            return f"line {i}: {a.strip()} -> {b.strip()}"
    return "the length differs"


def round_trip(sheet: dict, n: int) -> str:
    """The sheet as edit_sheet.py writes it after replacing event n with what print_sheet.py --show n prints."""
    shown = io.StringIO()
    with contextlib.redirect_stdout(shown):
        print_sheet.show(sheet, sheet.get("name", ""), n, 0)
    plan = edit_sheet.Plan(sheet, set(edit_sheet.sids_of(sheet)))
    plan.apply({"replace": n, "events": [json.loads(shown.getvalue())]}, 1)
    return json.dumps(plan.sheet, indent="\t", ensure_ascii=False)


def in_process(projects: list[Path]) -> tuple[int, int, list[str]]:
    sheets = events = 0
    changed = []
    for project in projects:
        for path in sheet_files(project):
            text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
            sheet = json.loads(text)
            sheets += 1
            where = f"{project.name}/{path.relative_to(project / 'eventSheets').as_posix()}"
            if json.dumps(sheet, indent="\t", ensure_ascii=False) != text:
                changed.append(f"{where}: not laid out as the editor writes it, so any plan rewrites it")
                continue
            for n in range(1, sum(1 for _ in c3.numbered_events(sheet["events"])) + 1):
                events += 1
                try:
                    after = round_trip(sheet, n)
                except edit_sheet.PlanError as e:
                    changed.append(f"{where} event {n}: refused: {e}")
                    continue
                if after != text:
                    changed.append(f"{where} event {n}: {first_change(text, after)}")
    return sheets, events, changed


def cli(project: Path, rag: Path) -> list[str]:
    """Event 1 of every sheet of the project, put back through the two scripts in a copy of the project."""
    changed = []
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / project.name
        shutil.copytree(project, copy, ignore=shutil.ignore_patterns(*MEDIA))
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CONSTRUCT3_RAG_OFFLINE="1")

        def run(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, *args, "--project", str(copy), "--rag", str(rag)], env=env,
                                  capture_output=True, text=True, encoding="utf-8", timeout=120)
        for path in sheet_files(copy):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
            before = path.read_bytes()
            sheet = json.loads(before.decode("utf-8-sig"))
            where = f"{project.name}/{path.name} event 1 (cli)"
            if not any(True for _ in c3.numbered_events(sheet["events"])):
                continue
            shown = run(str(SCRIPTS / "print_sheet.py"), sheet["name"], "--show", "1", "--limit", "0")
            if shown.returncode != 0:
                changed.append(f"{where}: print_sheet.py exit {shown.returncode}: {(shown.stdout + shown.stderr)[-200:]}")
                continue
            plan = Path(tmp) / "plan.json"
            plan.write_text(json.dumps([{"replace": 1, "events": [json.loads(shown.stdout)]}]), encoding="utf-8")
            edited = run(str(SCRIPTS / "edit_sheet.py"), sheet["name"], str(plan))
            if edited.returncode != 0:
                changed.append(f"{where}: edit_sheet.py exit {edited.returncode}: {(edited.stdout + edited.stderr)[-200:]}")
            elif path.read_bytes() != before:
                changed.append(f"{where}: {first_change(before.decode('utf-8-sig'), path.read_bytes().decode('utf-8'))}")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    rag = c3.clone_root(HERE.parent.parent.parent)
    default = c3.siblings_folder(rag) / "Construct-Example-Projects" / "example-projects"
    ap.add_argument("--examples", default=str(default), metavar="FOLDER",
                    help=f"a folder of folder projects (default: {default})")
    ap.add_argument("--cli", action="store_true", help="also run the two scripts on event 1 of every sheet")
    ap.add_argument("--workers", type=int, default=8, help="--cli projects in parallel (default: 8)")
    ap.add_argument("--limit", type=int, default=40, help="changed events listed (default: 40; 0 lists all)")
    args = ap.parse_args()
    c3.utf8_output()
    projects = [p.parent for p in sorted(Path(args.examples).glob("*/project.c3proj"))]
    if not projects:
        print(f"no folder with a project.c3proj under {args.examples}", file=sys.stderr)
        return 2
    start = time.monotonic()
    sheets, events, changed = in_process(projects)
    print(f"in process: {len(projects)} projects, {sheets} sheets, {events} events, "
          f"{len(changed)} change their sheet, {time.monotonic() - start:.1f} s")
    if args.cli:
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            found = [line for lines in pool.map(lambda p: cli(p, rag), projects) for line in lines]
        print(f"through the scripts: event 1 of every sheet, {len(found)} change their sheet or fail, "
              f"{time.monotonic() - start:.1f} s")
        changed += found
    for line in changed[:args.limit or None]:
        print(line)
    if args.limit and len(changed) > args.limit:
        print(f"... and {len(changed) - args.limit} more: --limit 0 lists all")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
