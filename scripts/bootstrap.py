"""Set a machine up from this clone alone: the sibling repositories, a game
project, and the skill inside it.

    python scripts/bootstrap.py                     # clone what is missing beside this repository
    python scripts/bootstrap.py --project MyGame    # ... and install the skill in MyGame beside them;
                                                    # a folder that does not exist yet gets the empty project

Clones Construct3-Manual, Construct-Example-Projects, Construct-Addon-SDK and
the empty project into the folder that holds this repository, each one only
when it is not there yet, then runs the skill's install.py on the project.
Safe to run again: a clone already present is left as it is, and install.py
refreshes rather than overwrites.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = ROOT / "skills" / "construct3-agent-plugin" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))
import c3project as c3  # noqa: E402
from new_project import new_project  # noqa: E402

INSTALL = SKILL_SCRIPTS / "install.py"

# Folder name beside this repository, its origin, and whether a shallow clone
# is enough. The examples are hundreds of megabytes of history; one commit
# holds every project the block and the skill read.
SIBLINGS = {
    "Construct3-Manual": ("https://github.com/XHXIAIEIN/Construct3-Manual", False),
    "Construct-Addon-SDK": ("https://github.com/Scirra/Construct-Addon-SDK", False),
    "Construct-Example-Projects": ("https://github.com/Scirra/Construct-Example-Projects", True),
}
# The project the editor saves for Project > New, so that a project can start
# without the editor. Copied, never used in place.
TEMPLATE = ROOT / "data" / "c3-new-project"


def git() -> str | None:
    return shutil.which("git")


def clone(name: str, url: str, shallow: bool, folder: Path, dry_run: bool) -> str:
    """One sibling: present, cloned, or the command to run by hand."""
    target = folder / name
    if target.exists() and any(target.iterdir()):
        return f"{name}: already at {target}"
    cmd = ["git", "clone", *(["--depth", "1"] if shallow else []), url, str(target)]
    if dry_run:
        return f"{name}: would run {' '.join(cmd)}"
    if not git():
        return (f"{name}: git is not installed, so it was not cloned. Install Git (https://git-scm.com), "
                f"or download {url} and unpack it as {target}")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return f"{name}: git clone failed; run by hand: {' '.join(cmd)}\n{p.stderr.strip()}"
    return f"{name}: cloned to {target}"


def game_folder(given: str, folder: Path) -> Path:
    """Where `--project` points. A bare name is a name, and a name goes beside
    the clones, whatever directory the command was run from; the README's
    `--project MyGame` means the same folder from a game project, from the
    desktop or from here. A path spelt out — a separator, a drive letter, `~`,
    `.` — is read from the current directory, as a path is anywhere else."""
    spelt_out = given.startswith(("~", ".")) or any(c in given for c in "/\\:")
    return Path(given).expanduser().resolve() if spelt_out else (folder / given).resolve()


def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Clone the repositories this one reads beside it, create a game project when the folder "
                    "does not exist yet, and install the construct3-agent-plugin skill in it. Safe to run again.",
        epilog="examples:\n"
               "  python scripts/bootstrap.py                          the siblings only\n"
               "  python scripts/bootstrap.py --project MyGame         siblings, then the skill in MyGame,\n"
               "                                                       created beside them when it does not exist\n"
               "  python scripts/bootstrap.py --project ../MyGame --into .claude/skills\n\n"
               "exit codes: 0 done, 1 a clone or the project failed; the line says what to run by hand")
    ap.add_argument("--project", metavar="NAME|FOLDER",
                    help="the game project, created from the empty project when missing. A name goes beside the "
                         "clones; a path is read from the current directory")
    ap.add_argument("--into", metavar="DIR", help="skills directory inside the project, passed to install.py")
    ap.add_argument("--beside", metavar="FOLDER",
                    help="where the clones go (default: the folder that holds this repository, where the block "
                         "expects them)")
    ap.add_argument("--template", metavar="FOLDER",
                    help=f"the empty project to copy (default: {TEMPLATE.relative_to(ROOT).as_posix()})")
    ap.add_argument("--no-examples", action="store_true", help="skip Construct-Example-Projects (the largest clone)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be done, do nothing")
    args = ap.parse_args()
    c3.utf8_output()

    folder = Path(args.beside).expanduser().resolve() if args.beside else ROOT.parent
    failed = False
    wanted = dict(SIBLINGS)
    if args.no_examples:
        wanted.pop("Construct-Example-Projects")
        if not (folder / "Construct-Example-Projects").is_dir():
            print("Construct-Example-Projects: not cloned (--no-examples), so print_sheet.py reads no official "
                  "example and search_guides.py gives each one's editor URL; run this again without "
                  "--no-examples to clone it")
    project = game_folder(args.project, folder) if args.project else None
    template = Path(args.template).expanduser().resolve() if args.template else TEMPLATE
    for name, (url, shallow) in wanted.items():
        line = clone(name, url, shallow, folder, args.dry_run)
        failed |= "not cloned" in line or "failed" in line
        print(line)

    if project is None:
        print("dry run: nothing was done" if args.dry_run else
              f"ok: next, python {Path(__file__).as_posix()} --project <game folder>")
        return 1 if failed else 0

    if not (project / "project.c3proj").exists():
        line = new_project(template, project, args.dry_run)
        print(line)
        if "not created" in line or "not empty" in line:
            return 1
    if args.dry_run:
        print("dry run: nothing was done")
        return 1 if failed else 0
    passed = ["--project", str(project)] + (["--into", args.into] if args.into else [])
    p = subprocess.run([sys.executable, str(INSTALL), *passed], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    lines = (p.stdout + p.stderr).rstrip("\n").splitlines()
    if not p.returncode and folder != ROOT.parent:
        # Before install.py's last line, "ok: read ...", which stays the last line of the run.
        lines.insert(-1, name_clones(project, folder, list(wanted)))
    print("\n".join(lines))
    return 1 if failed or p.returncode else 0


def name_clones(project: Path, folder: Path, names: list[str]) -> str:
    """The block expects the clones beside this repository. Cloned elsewhere,
    each gets its line under the Construct3-RAG line, once."""
    agents = project / "AGENTS.md"
    text = agents.read_text(encoding="utf-8") if agents.exists() else ""
    missing = [n for n in names if f"{n}:" not in text]
    key = "- Construct3-RAG:"
    if not missing or key not in text:
        return "AGENTS.md: the clones are already named"
    lines = "".join(f"- {n}: {(folder / n).as_posix()}\n" for n in missing)
    head, _, tail = text.partition(key)
    line, _, rest = tail.partition("\n")
    agents.write_text(head + key + line + "\n" + lines + rest, encoding="utf-8", newline="\n")
    return f"AGENTS.md: named {', '.join(missing)} under {folder.as_posix()}, which is not beside Construct3-RAG"


if __name__ == "__main__":
    sys.exit(main())
