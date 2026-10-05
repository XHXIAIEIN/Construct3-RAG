"""Start a Construct 3 folder project from the empty project the editor saves for Project > New.

    python scripts/new_project.py FOLDER [--rag FOLDER] [--dry-run]

Copies `Construct3-RAG/data/c3-new-project/` to FOLDER, gives the project the
folder's name and its own uniqueId, and runs `git init` in it when Git is
installed. FOLDER is read from the current directory and must not exist yet,
or be empty, or hold only a Git repository. The editor opens the result like
a project it saved itself; then check it with check_project.py.

exit codes: 0 created, 1 not created (the line says why), 2 bad arguments
"""
import argparse
import json
import random
import shutil
import string
import subprocess
import sys
from pathlib import Path

import c3project as c3

TEMPLATE = "data/c3-new-project"


def unique_id() -> str:
    """The shape the editor writes: eleven lowercase letters and digits."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=11))


def new_project(template: Path, target: Path, dry_run: bool) -> str:
    """The empty project copied to target with its own name and uniqueId. A
    folder that already holds files and is not a project is left alone; a
    folder that holds only a Git repository counts as empty."""
    if not (template / "project.c3proj").exists():
        return (f"{target.name}: not created; {template} holds no project.c3proj. In the editor, choose "
                f"Project > New, then save the project as a folder at {target}")
    if target.exists() and any(p.name != ".git" for p in target.iterdir()):
        return f"{target.name}: {target} is not empty and holds no project.c3proj; pass an empty or new folder"
    if dry_run:
        return f"{target.name}: would copy {template} to {target}"
    shutil.copytree(template, target, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    proj = target / "project.c3proj"
    data = json.loads(proj.read_text(encoding="utf-8"))
    data["name"], data["uniqueId"] = target.name, unique_id()
    proj.write_text(json.dumps(data, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    line = f"{target.name}: created from {template.name} at {target}"
    if shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=target, check=False)
        line += ", git initialised"
    return line


def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Start a Construct 3 folder project from the empty project the editor saves for Project > New.",
        epilog="examples:\n"
               "  python scripts/new_project.py MyGame                a folder MyGame in the current directory\n"
               "  python scripts/new_project.py ../games/MyGame --dry-run\n\n"
               "exit codes: 0 created, 1 not created (the line says why), 2 bad arguments")
    ap.add_argument("folder", help="the project folder to create, read from the current directory")
    ap.add_argument("--rag", metavar="FOLDER", help="the Construct3-RAG folder, when it is not found on its own")
    ap.add_argument("--dry-run", action="store_true", help="say what would be done, do nothing")
    args = ap.parse_args()
    c3.utf8_output()
    target = Path(args.folder).expanduser().resolve()
    if (target / "project.c3proj").exists():
        print(f"{target.name}: {target} already holds project.c3proj; "
              f"next, python {(c3.SKILL_DIR / 'scripts' / 'check_project.py').as_posix()} --project \"{target}\"")
        return 0
    line = new_project(c3.find_rag(None, args.rag) / TEMPLATE, target, args.dry_run)
    print(line)
    if "not created" in line or "not empty" in line:
        return 1
    if not args.dry_run:
        print(f"ok: next, python {(c3.SKILL_DIR / 'scripts' / 'check_project.py').as_posix()} --project \"{target}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
