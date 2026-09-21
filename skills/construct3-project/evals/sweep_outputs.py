"""Record what the scripts print over many projects, and compare two records.

    python evals/sweep_outputs.py OUT.json --examples FOLDER [--projects FOLDER ...] [--limit 0] [--scripts DIR]
    python evals/sweep_outputs.py --compare OLD.json NEW.json

The first form runs check_project.py, print_sheet.py, print_sheet.py
--outline and a dry run of edit_sheet.py with a small plan on every folder
project under --examples (the example-projects folder of the
Construct-Example-Projects clone) and on each --projects folder, and a fixed
list of lookups, and writes exit code, a hash of stdout and of stderr and
their length per run. Nothing is written to a project. Record the old side
before a change and the new side after it; --limit 0 lifts the scripts'
output limit, so that what they print in full can be compared with a version
that had none. For an old side that was not recorded, --scripts names the
scripts folder of another checkout of the clone, such as a git worktree of
the previous commit; its own data/ is then the clone it reads, so that it
does not report itself as a copy that differs.

The second form lists the runs whose exit code, stdout or stderr differ, and
counts the runs that print more than 10 000 and 30 000 characters, where
agent harnesses start to cut tool output. A change that should not alter
output shows no difference; one that should shows exactly where.

exit codes: 0 recorded, or compared and identical; 1 compared and different;
2 no project found under --examples or --projects, or --scripts is not inside
a checkout of the clone
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMANDS = {"check": ["check_project.py"], "print": ["print_sheet.py"], "outline": ["print_sheet.py", "--outline"]}
# A plan every project takes: a comment, a variable and an event that uses it, at the end of its first sheet.
PLAN = [{"into": 0, "events": [
    {"eventType": "comment", "text": "sweep"}, {"eventType": "variable", "name": "SweepProbe"},
    {"eventType": "block", "conditions": [], "actions": [
        {"id": "add-to-eventvar", "objectClass": "System", "parameters": {"variable": "SweepProbe", "value": "1"}}]}]}]
LOOKUPS = [["System"], ["System", "wait"], ["System", "action"], ["System", "expression"], ["System", "every"],
           ["System", "timer"], ["System", "for", "each"], ["Sprite"], ["Sprite", "scale", "size"],
           ["Sprite", "animation"], ["Text", "set"], ["8 Direction", "speed"], ["Tween"], ["Tween", "two"],
           ["Platform", "jump"], ["Array"], ["Arr", "push"], ["Json", "get"], ["Keyboard"], ["Touch", "touched"],
           ["Audio", "play"], ["LocalStorage"], ["Timer"], ["Physics", "force"], ["NoSuchAddon"]]


def run(scripts: Path, args: list[str], extra: list[str]) -> dict:
    rag = scripts.parent.parent.parent
    p = subprocess.run([sys.executable, str(scripts / args[0]), *args[1:], "--rag", str(rag), *extra],
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out, err = (s.replace(b"\r\n", b"\n") for s in (p.stdout, p.stderr))
    return {"exit": p.returncode, "stdout": hashlib.sha256(out).hexdigest()[:16], "stdout_chars": len(out.decode("utf-8", "replace")),
            "stderr": hashlib.sha256(err).hexdigest()[:16], "stderr_chars": len(err.decode("utf-8", "replace"))}


def first_sheet(project: Path) -> str | None:
    def names(folder: dict) -> list[str]:
        return list(folder.get("items", [])) + [n for sub in folder.get("subfolders", []) for n in names(sub)]
    listed = names(json.loads((project / "project.c3proj").read_text(encoding="utf-8")).get("eventSheets", {}))
    return listed[0] if listed else None


def record(args: argparse.Namespace) -> int:
    scripts = Path(args.scripts).resolve() if args.scripts else HERE.parent / "scripts"
    if not (scripts.parent.parent.parent / "data" / "c3-schemas" / "_index.json").exists():
        print(f"{scripts} is not skills/<skill>/scripts of a checkout of the clone: no data/c3-schemas three "
              f"folders up", file=sys.stderr)
        return 2
    projects = [p.parent for folder in args.examples for p in sorted(Path(folder).glob("*/project.c3proj"))]
    projects += [Path(p) for p in args.projects]
    projects = [p for p in projects if (p / "project.c3proj").exists()]
    if not projects:
        print("no folder with a project.c3proj under --examples or --projects", file=sys.stderr)
        return 2
    jobs = [(f"{name} {p.name}", [*cmd, "--project", str(p)]) for p in projects for name, cmd in COMMANDS.items()]
    jobs += [("lookup " + " ".join(words), ["lookup_ace.py", *words]) for words in LOOKUPS]
    extra = [] if args.limit is None else ["--limit", str(args.limit)]
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=args.workers) as pool:
        plan = Path(tmp) / "plan.json"
        plan.write_text(json.dumps(PLAN), encoding="utf-8")
        jobs += [(f"edit {p.name}", ["edit_sheet.py", sheet, str(plan), "--dry-run", "--project", str(p)])
                 for p in projects if (sheet := first_sheet(p))]
        results = dict(zip((key for key, _ in jobs), pool.map(lambda job: run(scripts, job[1], extra), jobs)))
    Path(args.out).write_text(json.dumps({"scripts": str(scripts), "runs": results}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(results)} runs over {len(projects)} projects written to {args.out}")
    return 0


def sizes(runs: dict) -> str:
    by_command: dict[str, list[int]] = {}
    for key, r in runs.items():
        by_command.setdefault(key.split(" ")[0], []).append(r["stdout_chars"])
    return "; ".join(f"{name}: {sum(n > 10000 for n in chars)} over 10 000 and {sum(n > 30000 for n in chars)} over "
                     f"30 000 of {len(chars)}, longest {max(chars)}" for name, chars in by_command.items())


def compare(old_file: str, new_file: str) -> int:
    old, new = (json.loads(Path(f).read_text(encoding="utf-8"))["runs"] for f in (old_file, new_file))
    changed = [key for key in old if key in new and any(old[key][k] != new[key][k] for k in ("exit", "stdout", "stderr"))]
    for key in changed:
        o, n = old[key], new[key]
        print(f"{key}: exit {o['exit']} -> {n['exit']}, stdout {o['stdout_chars']} -> {n['stdout_chars']} chars, "
              f"stderr {o['stderr_chars']} -> {n['stderr_chars']}")
    only = sorted(set(old) ^ set(new))
    if only:
        print(f"in one record only: {', '.join(only[:8])}{' ...' if len(only) > 8 else ''}")
    print(f"{len(changed)} of {len(set(old) & set(new))} runs differ")
    print(f"old  {sizes(old)}")
    print(f"new  {sizes(new)}")
    return 1 if changed or only else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", metavar="OUT.json", help="where the record is written")
    ap.add_argument("--examples", action="append", default=[], metavar="FOLDER",
                    help="a folder of folder projects, such as Construct-Example-Projects/example-projects")
    ap.add_argument("--projects", nargs="*", default=[], metavar="FOLDER", help="single game projects")
    ap.add_argument("--scripts", metavar="DIR",
                    help="the scripts folder of another checkout of the clone (default: the one beside evals/)")
    ap.add_argument("--limit", type=int, metavar="CHARS", help="passed to every script; 0 lifts their output limit")
    ap.add_argument("--workers", type=int, default=8, help="runs in parallel (default: 8)")
    ap.add_argument("--compare", nargs=2, metavar=("OLD.json", "NEW.json"), help="compare two records")
    args = ap.parse_args()
    if args.compare:
        return compare(*args.compare)
    if not args.out:
        ap.error("OUT.json is required unless --compare is given")
    return record(args)


if __name__ == "__main__":
    sys.exit(main())
