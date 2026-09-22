"""Install this skill in a Construct 3 game project, or refresh a copy of it.

    python <Construct3-RAG>/skills/construct3-project/scripts/install.py [--project FOLDER] [--into DIR]

Copies the skill's folder from the Construct3-RAG clone into the project's
skills directory, and adds the Construct 3 block to the project's AGENTS.md
when no instruction file there names the clone yet, with the clone's path
filled in, and the line `@AGENTS.md` to CLAUDE.md. Run again, it refreshes
every copy the project holds and leaves the instruction files alone. The
clone is the source: run from an installed copy, it hands over to the clone's
own install.py.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import c3project as c3
from c3project import SKILL, SKILL_DIR

BLOCK = SKILL_DIR / "assets" / "game-project-block.md"
DEFAULT_INTO = ".agents/skills"
RAG_KEY = re.compile(r"^[ \t>*-]*Construct3-RAG\s*[:=]", re.M)


def targets(project: Path | None, into: str | None) -> list[Path]:
    """Where the skill goes: --into, else every copy the project already holds, else the default."""
    if into:
        folder = Path(into).expanduser()
        if not folder.is_absolute():
            if project is None:
                sys.exit(f"--into {into} is relative to a project, and no project.c3proj was found from "
                         f"{Path.cwd()} upward; pass --project <folder>, or an absolute --into")
            folder = project / folder
        return [folder / SKILL]
    if project is None:
        sys.exit(f"no project.c3proj in {Path.cwd()} or above it; run this from the game project, pass "
                 f"--project <folder>, or pass an absolute --into such as ~/.agents/skills")
    held = sorted(p.parent for p in project.glob(f".*/skills/{SKILL}/SKILL.md"))
    return held or [project / DEFAULT_INTO / SKILL]


def mirror(source: Path, target: Path, dry_run: bool) -> str:
    """Make target hold exactly the files of source; a file the skill no longer has goes."""
    wanted, have = c3.skill_files(source), c3.skill_files(target) if target.exists() else {}
    written = [rel for rel, path in wanted.items() if rel not in have or not c3.same_text(path, have[rel])]
    removed = [rel for rel in have if rel not in wanted]
    if not dry_run:
        for rel in written:
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wanted[rel], target / rel)
        for rel in removed:
            (target / rel).unlink()
    if not written and not removed:
        return f"{len(wanted)} files, already current"
    wrote, gone = ("would write", "would remove") if dry_run else ("wrote", "removed")
    parts = ([f"{wrote} {', '.join(written)}"] if written else []) + ([f"{gone} {', '.join(removed)}"] if removed else [])
    return "; ".join(parts)


def shown(path: Path, project: Path | None) -> str:
    """A path as the block and the report name it: relative to the project where it is inside it."""
    if project and path.is_relative_to(project):
        return path.relative_to(project).as_posix()
    return path.as_posix()


def add_block(project: Path, rag: Path, skill_path: str, dry_run: bool) -> list[str]:
    """The block goes into AGENTS.md once. An instruction file that already names
    the clone is the user's: it is left as it is, and what it lacks is said."""
    notes = []
    row = f"`{skill_path}/SKILL.md`"
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = (project / name).read_text(encoding="utf-8") if (project / name).exists() else ""
        if not RAG_KEY.search(text):
            continue
        found = c3.rag_line(text)
        if not found or not c3.is_clone(Path(found)):
            notes.append(f"{name}: its Construct3-RAG line does not lead to the clone; "
                         f"the line to write is '- Construct3-RAG: {rag.as_posix()}'")
        if SKILL not in text:
            notes.append(f"{name}: left as it is; its table has no row for this skill. The row to add: "
                         f"| Looking an ACE up, reading a sheet as events, putting events into a sheet, checking "
                         f"project files, generating the whole project | {row} |")
        return notes or [f"{name}: already names the clone and this skill, left as it is"]

    block = BLOCK.read_text(encoding="utf-8")
    block = block.replace("<path-to>/Construct3-RAG", rag.as_posix()).replace(f"{DEFAULT_INTO}/{SKILL}", skill_path)
    agents = project / "AGENTS.md"
    before = agents.read_text(encoding="utf-8") if agents.exists() else ""
    if not dry_run:
        agents.write_text((before.rstrip("\n") + "\n\n" if before.strip() else "") + block, encoding="utf-8", newline="\n")
    did = "added" if before.strip() else "created with"
    notes.append(f"AGENTS.md: {'would be ' if dry_run else ''}{did} the Construct 3 block, "
                 f"Construct3-RAG: {rag.as_posix()}")
    # Claude Code before 2.1.277 reads CLAUDE.md only, and any version reads it
    # instead of AGENTS.md when both exist: one line there leads to the block.
    claude = project / "CLAUDE.md"
    had = claude.read_text(encoding="utf-8") if claude.exists() else ""
    if "@AGENTS.md" not in had:
        if not dry_run:
            claude.write_text((had.rstrip("\n") + "\n\n" if had.strip() else "") + "@AGENTS.md\n",
                              encoding="utf-8", newline="\n")
        notes.append(f"CLAUDE.md: {'would be ' if dry_run else ''}{'added' if had.strip() else 'created with'} "
                     f"the line @AGENTS.md, which Claude Code follows to the block")
    # The block records the clone for this project alone, and nothing here writes outside the
    # project: the next project starts with no record of the clone anywhere on the machine.
    notes.append(f"memory: keep 'Construct3-RAG: {rag.as_posix()}' where your client stores notes between "
                 f"sessions. The next project starts without this block, and an agent that cannot find "
                 f"this clone clones it and the repositories beside it again")
    return notes


def unnamed_clone(project: Path, rag: Path) -> list[str]:
    """--no-block on a project whose instruction files do not lead to the clone:
    the copied scripts would stop at 'Construct3-RAG not found', so say how they find it."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = (project / name).read_text(encoding="utf-8") if (project / name).exists() else ""
        found = c3.rag_line(text)
        if found and c3.is_clone(Path(found)):
            return []
    return [f"no instruction file of the project names the clone, and --no-block adds none: the scripts find it "
            f"through CONSTRUCT3_RAG={rag.as_posix()} or --rag {rag.as_posix()}"]


def earlier_tools(project: Path, skill_path: str) -> list[str]:
    """The two files a project got by hand before the skill. Nothing refreshes
    them, and the generator among them ends by running the checker beside it."""
    notes = []
    if (project / "tools" / "check-project.py").exists():
        notes.append(f"tools/check-project.py: an earlier copy of the checker that nothing refreshes; run "
                     f"{skill_path}/scripts/check_project.py instead, and remove the copy when the user agrees")
    if (project / "tools" / "build-project.py").exists():
        notes.append("tools/build-project.py: it ends by running the checker beside it; replace its last lines "
                     "with those of assets/build_project.py, which run the skill's checker")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Install the construct3-project skill in a Construct 3 game project, or refresh the copies it "
                    "holds, from the Construct3-RAG clone this script sits in. Adds the Construct 3 block to the "
                    "project's AGENTS.md when no instruction file there names the clone yet, and the line @AGENTS.md "
                    "to CLAUDE.md. Safe to run again.",
        epilog="examples:\n"
               "  python install.py                          into the project found from the current directory\n"
               "  python install.py --project ../MyGame --into .claude/skills\n"
               "  python install.py --into ~/.agents/skills  one copy for every project of this user\n\n"
               "skills directories: .agents/skills is read by most agents; Claude Code reads .claude/skills,\n"
               "TRAE .trae/skills (.agents/skills once enabled in its settings), Deep Code .deepcode/skills.\n\n"
               "exit codes: 0 installed or already current, 1 no project or no clone found")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--into", metavar="DIR",
                    help=f"skills directory to install into, relative to the project or absolute (default: every "
                         f"copy the project already holds, else {DEFAULT_INTO})")
    ap.add_argument("--rag", metavar="FOLDER", help="the Construct3-RAG clone, when run from an installed copy")
    ap.add_argument("--no-block", action="store_true", help="do not touch the project's AGENTS.md")
    ap.add_argument("--dry-run", action="store_true", help="say what would be written, write nothing")
    args = ap.parse_args()
    c3.utf8_output()

    project = c3.find_project(args.project)
    if project and not (project / "project.c3proj").exists():
        sys.exit(f"no project.c3proj in {project}: --project is the folder the editor saved the project into")

    rag = c3.above(SKILL_DIR, "data/c3-schemas/_index.json")
    if rag is None or (rag / "skills" / SKILL).resolve() != SKILL_DIR:
        # An installed copy: the clone holds the current files, so its install.py does the work.
        rag = c3.find_rag(project, args.rag)
        theirs = rag / "skills" / SKILL / "scripts" / "install.py"
        if not theirs.exists():
            sys.exit(f"{rag} has no skills/{SKILL}: update the clone (git pull) and run again")
        passed = sys.argv[1:]
        if not args.into:
            passed += ["--into", str(SKILL_DIR.parent)]
        return subprocess.run([sys.executable, str(theirs), *passed]).returncode

    places = targets(project, args.into)
    for target in places:
        print(f"{shown(target, project)}: {mirror(SKILL_DIR, target, args.dry_run)}")
    if project:
        notes = unnamed_clone(project, rag) if args.no_block else \
            add_block(project, rag, shown(places[0], project), args.dry_run)
        for note in notes + earlier_tools(project, shown(places[0], project)):
            print(note)
    if args.dry_run:
        print("dry run: nothing was written")
    else:
        print(f"ok: read {shown(places[0], project)}/SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
