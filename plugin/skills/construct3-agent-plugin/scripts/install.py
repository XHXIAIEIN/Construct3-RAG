"""Install this skill in a Construct 3 game project, or refresh a copy of it.

    python <Construct3-RAG>/skills/construct3-agent-plugin/scripts/install.py [--project FOLDER] [--into DIR]

Copies the skill's folder from the Construct3-RAG clone into the project's
skills directory, and adds the Construct 3 block to the project's AGENTS.md
when no instruction file there names the clone yet, with the clone's path
filled in, and the line `@AGENTS.md` to CLAUDE.md. Run again, it refreshes
every copy the project holds and leaves the instruction files alone. The
clone is the source: run from an installed copy, it hands over to the clone's
own install.py.

The project's generator, tools/build_project.py, keeps the template's helpers
between two markers. When they are an older version and unedited there, they
are replaced with the skill's; the lines outside the markers stay as they are.
--helpers-only does that alone, for a project that has no copy of the skill.
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
FORMER_NAMES = ("construct3-project",)     # the skill's folder before it was renamed
RAG_KEY = re.compile(r"^[ \t>*-]*Construct3-RAG\s*[:=]", re.M)


def new_project(folder: str) -> str:
    """install.py fills a project; new_project.py of this skill creates one first."""
    folder = f'"{folder}"' if " " in folder else folder
    return f". To start a new project, run python {(SKILL_DIR / 'scripts' / 'new_project.py').as_posix()} {folder}"


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
                 f"--project <folder>, or pass an absolute --into such as ~/.agents/skills"
                 f"{new_project('<folder>')}")
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
                 f"sessions; the next project starts without this block")
    return notes


def unnamed_clone(project: Path, rag: Path) -> list[str]:
    """--no-block on a project whose instruction files do not lead to the clone:
    the copied scripts would stop at 'Construct3-RAG not found', so say how they find it."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = (project / name).read_text(encoding="utf-8") if (project / name).exists() else ""
        found = c3.rag_line(text)
        if found and c3.is_clone(Path(found)):
            return []
    return [f"no instruction file of the project names the clone, and --no-block adds none: the scripts take "
            f"--rag {rag.as_posix()} or CONSTRUCT3_RAG set to it; keep that path where your client stores "
            f"notes between sessions"]


def again(flag: str) -> str:
    """This run's command with one more flag."""
    def quoted(s: str) -> str:
        return f'"{s}"' if " " in s else s
    return " ".join(["python", quoted(Path(__file__).resolve().as_posix()), *map(quoted, sys.argv[1:]), flag])


def generator(project: Path, rag: Path, replace_edited: bool, dry_run: bool) -> tuple[bool, list[str]]:
    """The helpers of the project's tools/build_project.py replaced with the skill's when they
    are an older version left unedited there; whether they are the skill's afterwards, and what
    to print. Edits between the markers are the game's, so they are kept unless the run asks."""
    h = c3.generator_helpers(project)
    name = c3.GENERATOR
    if h.state == "missing":
        return False, []
    if h.state == "unmarked":
        return False, [f"{name}: written before the template marked its helpers, so nothing refreshes them; "
                       f"left as it is"]
    if h.state == "broken":
        return False, [f"{name}: {h.detail}; its helpers were left as they are"]
    if h.state == "current":
        return True, [f"{name}: its helpers are the skill's of {h.want.version}, already current"]
    have, want = c3.versions(h.have, h.want)
    if h.state == "newer":
        return False, [f"{name}: its helpers are of {have}, newer than this skill's of {want}, "
                       f"and were left as they are; update the clone, git -C \"{rag}\" pull --ff-only, and run this "
                       f"again"]
    if h.state == "edited" and not replace_edited:
        return False, [f"{name}: its helpers, between the markers, were edited there, so they were left as they "
                       f"are. Copy each helper changed there below the end marker, where a def of the same name "
                       f"replaces the one between the markers, then run {again('--replace-edited-helpers')}"]
    problem = c3.replace_helpers(project, dry_run=dry_run)
    if problem:
        return False, [f"{name}: {problem}; nothing was written"]
    return True, [f"{name}: {'would replace' if dry_run else 'replaced'} its helpers of {have} with the "
                  f"skill's of {want}; the lines outside the markers are as they were. Run python "
                  f"{name}, which regenerates the project with them"]


def earlier_tools(project: Path, skill_path: str) -> list[str]:
    """The two files a project got by hand before the skill, and a copy of the skill under its
    former name. Nothing refreshes them. The generator of the two files ends by running the
    checker beside it. A client lists the former copy as a second skill."""
    notes = []
    if (project / "tools" / "check-project.py").exists():
        notes.append(f"tools/check-project.py: an earlier copy of the checker that nothing refreshes; run "
                     f"{skill_path}/scripts/check_project.py instead, and remove the copy when the user agrees")
    if (project / "tools" / "build-project.py").exists():
        notes.append("tools/build-project.py: it ends by running the checker beside it; replace its last lines "
                     "with those of assets/build_project.py, which run the skill's checker")
    for former in FORMER_NAMES:
        for copy in sorted(p.parent for p in project.glob(f".*/skills/{former}/SKILL.md")):
            notes.append(f"{shown(copy, project)}: a copy of this skill under its former name, which nothing "
                         f"refreshes and a client lists beside {SKILL}; remove the folder when the user agrees")
        for name in ("AGENTS.md", "CLAUDE.md"):
            path = project / name
            if path.exists() and f"/{former}/" in path.read_text(encoding="utf-8"):
                notes.append(f"{name}: names the skill's former folder {former}; write {skill_path} in place of "
                             f"each path to it")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Install the construct3-agent-plugin skill in a Construct 3 game project, or refresh the copies it "
                    "holds, from the Construct3-RAG clone this script sits in. Adds the Construct 3 block to the "
                    "project's AGENTS.md when no instruction file there names the clone yet, and the line @AGENTS.md "
                    "to CLAUDE.md. Replaces the helpers of the project's tools/build_project.py, between its "
                    "markers, with the skill's when they are an older version left unedited there. Safe to run "
                    "again.",
        epilog="examples:\n"
               "  python install.py                          into the project found from the current directory\n"
               "  python install.py --project ../MyGame --into .claude/skills\n"
               "  python install.py --into ~/.agents/skills  one copy for every project of this user\n"
               "  python install.py --helpers-only           the generator's helpers alone, as with the plugin\n\n"
               "skills directories: .agents/skills is read by most agents; Claude Code reads .claude/skills,\n"
               "TRAE .trae/skills (.agents/skills once enabled in its settings), Deep Code .deepcode/skills.\n\n"
               "exit codes: 0 installed or already current, 1 no project or no clone found; with --helpers-only,\n"
               "0 when the generator's helpers are the skill's and 1 when they are not: no generator, no\n"
               "markers, edited there or newer")
    ap.add_argument("--project", metavar="FOLDER",
                    help="the folder that holds project.c3proj (default: found from the current directory upward)")
    ap.add_argument("--into", metavar="DIR",
                    help=f"skills directory to install into, relative to the project or absolute (default: every "
                         f"copy the project already holds, else {DEFAULT_INTO})")
    ap.add_argument("--rag", metavar="FOLDER", help="the Construct3-RAG clone, when run from an installed copy")
    ap.add_argument("--no-block", action="store_true", help="do not touch the project's AGENTS.md")
    ap.add_argument("--helpers-only", action="store_true",
                    help=f"refresh only the helpers of the project's {c3.GENERATOR}, between its markers; no copy "
                         f"of the skill and no instruction file is written. For a project that uses the skill "
                         f"without a copy, as the Claude Code plugin does")
    ap.add_argument("--replace-edited-helpers", action="store_true",
                    help=f"replace the helpers of {c3.GENERATOR} even when they were edited there; copy each "
                         f"edited helper below the end marker first, where it replaces the skill's")
    ap.add_argument("--dry-run", action="store_true", help="say what would be written, write nothing")
    args = ap.parse_args()
    c3.utf8_output()

    project = c3.find_project(args.project)
    if project and not (project / "project.c3proj").exists():
        sys.exit(f"no project.c3proj in {project}: --project is the folder the editor saved the project into"
                 f"{new_project(str(project))}")

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

    if args.helpers_only:
        if project is None:
            sys.exit(f"no project.c3proj in {Path.cwd()} or above it; run this from the game project, or pass "
                     f"--project <folder>")
        current, lines = generator(project, rag, args.replace_edited_helpers, args.dry_run)
        print("\n".join(lines or [f"{c3.GENERATOR}: not in {project}, so there are no helpers to refresh"]))
        if args.dry_run:
            print("dry run: nothing was written")
        return 0 if current else 1

    places = targets(project, args.into)
    for target in places:
        print(f"{shown(target, project)}: {mirror(SKILL_DIR, target, args.dry_run)}")
    if project:
        notes = unnamed_clone(project, rag) if args.no_block else \
            add_block(project, rag, shown(places[0], project), args.dry_run)
        refreshed = generator(project, rag, args.replace_edited_helpers, args.dry_run)[1]
        for note in refreshed + notes + earlier_tools(project, shown(places[0], project)):
            print(note)
    if args.dry_run:
        print("dry run: nothing was written")
    else:
        print(f"ok: read {shown(places[0], project)}/SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
