"""Install this skill in a Construct 3 game project, or refresh a copy of it.

    python <Construct3-RAG>/skills/construct3-agent-plugin/scripts/install.py [--project FOLDER] [--into DIR]

Copies the skill's folder from the Construct3-RAG clone into the project's
skills directory, and adds the Construct 3 block to the project's AGENTS.md
when no instruction file there names the clone yet, with the clone's path
filled in, and the line `@AGENTS.md` to CLAUDE.md. Run again, it refreshes
every copy the project holds. The clone is the source: run from an installed
copy, it hands over to the clone's own install.py.

Two parts of a project come from the skill's assets and sit between two
markers there: the Construct 3 block of the instruction file, and the helpers
of the generator, tools/build_project.py. When a part is an older version and
unedited there, it is replaced with the skill's; the lines outside the markers
stay as they are. --block-only and --helpers-only refresh one part alone, for
a project that has no copy of the skill.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import c3project as c3
from c3project import SKILL, SKILL_DIR

BLOCK = c3.BLOCK_TEMPLATE
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


def add_block(project: Path, rag: Path, skill_path: str, replace_edited: bool, dry_run: bool) -> list[str]:
    """The block goes into AGENTS.md once, and a block this script wrote is refreshed where it
    stands. An instruction file that names the clone without such a block is the user's: it is
    left as it is, and what it lacks is said."""
    found = c3.instruction_block(project)
    if found.state != "missing":
        notes = refresh_block(project, rag, found, skill_path, replace_edited, dry_run)[1]
        notes += clone_note(project / found.file, rag)
        if found.file == "AGENTS.md":
            notes += lead_claude_md(project, dry_run)
        return notes
    notes = []
    row = f"`{skill_path}/SKILL.md`"
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = (project / name).read_text(encoding="utf-8") if (project / name).exists() else ""
        if not RAG_KEY.search(text):
            continue
        notes += clone_note(project / name, rag)
        if SKILL not in text:
            notes.append(f"{name}: left as it is; its table has no row for this skill. The row to add: "
                         f"| Looking an ACE up, reading a sheet as events, putting events into a sheet, checking "
                         f"project files, generating the whole project | {row} |")
        notes = notes or [f"{name}: already names the clone and this skill, left as it is. It holds no block that "
                          f"this script wrote, so none is refreshed there; to have one, put the skill's block, "
                          f"{BLOCK.as_posix()}, markers included, in place of the file's Construct 3 lines"]
        if name == "AGENTS.md":
            notes += lead_claude_md(project, dry_run)
        return notes

    block = "\n".join(c3.block_lines(rag, skill_path)) + "\n"
    agents = project / "AGENTS.md"
    before = agents.read_text(encoding="utf-8") if agents.exists() else ""
    if not dry_run:
        agents.write_text((before.rstrip("\n") + "\n\n" if before.strip() else "") + block, encoding="utf-8", newline="\n")
    did = "added" if before.strip() else "created with"
    notes.append(f"AGENTS.md: {'would be ' if dry_run else ''}{did} the Construct 3 block, "
                 f"Construct3-RAG: {rag.as_posix()}")
    notes += lead_claude_md(project, dry_run)
    # The block records the clone for this project alone, and nothing here writes outside the
    # project: the next project starts with no record of the clone anywhere on the machine.
    notes.append(f"memory: keep 'Construct3-RAG: {rag.as_posix()}' where your client stores notes between "
                 f"sessions; the next project starts without this block")
    return notes


def lead_claude_md(project: Path, dry_run: bool) -> list[str]:
    """Claude Code before 2.1.277 reads CLAUDE.md only, and any version reads it
    instead of AGENTS.md when both exist: one line there leads to the block in
    AGENTS.md, whether this run wrote the block or found it."""
    claude = project / "CLAUDE.md"
    had = claude.read_text(encoding="utf-8") if claude.exists() else ""
    if "@AGENTS.md" in had or RAG_KEY.search(had):
        return []
    if not dry_run:
        claude.write_text((had.rstrip("\n") + "\n\n" if had.strip() else "") + "@AGENTS.md\n",
                          encoding="utf-8", newline="\n")
    return [f"CLAUDE.md: {'would be ' if dry_run else ''}{'added' if had.strip() else 'created with'} "
            f"the line @AGENTS.md, which Claude Code follows to the block"]


def clone_note(path: Path, rag: Path) -> list[str]:
    """The line to write when the instruction file's Construct3-RAG line does not reach the clone."""
    found = c3.rag_line(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else None
    if found and c3.is_clone(Path(found)):
        return []
    return [f"{path.name}: its Construct3-RAG line does not lead to the clone; "
            f"the line to write is '- Construct3-RAG: {rag.as_posix()}'"]


def refresh_block(project: Path, rag: Path, found: c3.BlockState, skill_path: str | None, replace_edited: bool,
                  dry_run: bool) -> tuple[bool, list[str]]:
    """The project's Construct 3 block replaced with the skill's when it is an older version left
    unedited there; whether it is the skill's afterwards, and what to print. Edits between the
    markers are the project's, so an edited block is kept unless the run asks with replace_edited.
    Its changes are listed against the block as written when the clone's history holds that
    version, else against the skill's."""
    name = found.file
    if found.state == "missing":
        return False, ["AGENTS.md: holds no Construct 3 block that this script wrote, so there is none to refresh"]
    if found.state == "broken":
        return False, [f"{name}: {found.detail}; its Construct 3 block was left as it is"]
    if found.state == "current":
        return True, [f"{name}: its Construct 3 block is the skill's of {found.want.version}, already current"]
    have, want = c3.versions(found.have, found.want)
    if found.state == "newer":
        return False, [f"{name}: its Construct 3 block is of {have}, newer than this skill's of {want}, and was left "
                       f"as it is; update the clone, git -C \"{rag}\" pull --ff-only, and run this again"]
    if found.state == "edited" and not replace_edited:
        written = c3.copied_from(rag, c3.BLOCK_IN_CLONE, found.have.stamp, lambda lines: c3.block_in(lines, past=False))
        against = f"the block as written, of {have}" if written else f"the skill's of {want}"
        changes = c3.block_changes(project, found, written or c3.text_lines(BLOCK)[0])
        notes = [f"{name}: its Construct 3 block was edited between its markers, so it was left as it is. Where it "
                 f"differs from {against}:", *(f"  {change}" for change in changes)]
        if found.have.stamp == found.want.stamp:
            return False, notes + ["The skill's block has not changed since it was written; a line the project adds "
                                   "belongs below the end marker, where a refresh leaves it"]
        return False, notes + [f"Move the project's own lines below the end marker, then run "
                               f"{again('--replace-edited-block')}, which writes the skill's of {want} and keeps "
                               f"the lines that name a clone's folder"]
    c3.replace_block(project, found, rag, skill_path, dry_run)
    before = "" if found.have.marked else ", written before the block had markers,"
    return True, [f"{name}: {'would replace' if dry_run else 'replaced'} its Construct 3 block of {have}{before} with "
                  f"the skill's of {want}; the lines that name a clone's folder and every line outside the block "
                  f"are as they were"]


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
    """This run's command with flag in place of any earlier use of it."""
    def quoted(s: str) -> str:
        return f'"{s}"' if " " in s else s
    kept = [a for a in sys.argv[1:] if a.split("=")[0] != flag.split("=")[0]]
    return " ".join(["python", quoted(Path(__file__).resolve().as_posix()), *map(quoted, kept), flag])


def generator(project: Path, rag: Path, replace_edited: str | None, dry_run: bool) -> tuple[bool, list[str]]:
    """The helpers of the project's tools/build_project.py replaced with the skill's when they
    are an older version left unedited there; whether they are the skill's afterwards, and what
    to print. Edits between the markers are the game's, so they are kept unless the run asks
    with replace_edited, and even then while one would be lost: a helper the game changed, with
    no def of its name below the end marker, that is not among the names given. The game changed
    a helper that differs from the template its part was copied from, found in the clone's
    history; without that history, every helper that differs from the skill's counts."""
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
    if h.state == "edited":
        copied = c3.copied_template(rag, h.have.stamp)
        lost = c3.unkept_helpers(project, copied=copied)
        if isinstance(lost, str):
            return False, [f"{name}: {lost}; its helpers were left as they are"]
        taken = {n.strip() for n in (replace_edited or "").split(",")}
        lost = [entry for entry in lost if entry[0] not in taken]
    if h.state == "edited" and replace_edited is None:
        changed = f" ({', '.join(n for n, _, _ in lost)})" if copied and lost else ""
        return False, [f"{name}: its helpers, between the markers, were edited there, so they were left as they "
                       f"are. Copy each helper changed there{changed} below the end marker, where a def of the same "
                       f"name replaces the one between the markers, then run {again('--replace-edited-helpers')}"]
    if h.state == "edited" and lost and copied:
        return False, [f"{name}: replacing its helpers would lose these, which were edited there and have no def "
                       f"of the same name below the end marker; nothing was written:",
                       *(f"  {n}: here {here!r}, as copied {was!r}" for n, here, was in lost),
                       f"Copy each one below the end marker, where it replaces the skill's, then run "
                       f"{again('--replace-edited-helpers')}"]
    if h.state == "edited":
        if lost:
            return False, [f"{name}: replacing its helpers would lose these, which differ from the skill's and "
                           f"have no def of the same name below the end marker; nothing was written:",
                           *(f"  {n}: here {here!r}, the skill's {skills!r}" for n, here, skills in lost),
                           f"Copy below the end marker each one the game changed, where it replaces the skill's. "
                           f"One that differs only because the skill's changed since needs no copy: name it, "
                           f"then run {again('--replace-edited-helpers=NAME,NAME')}"]
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
                    "to CLAUDE.md. Replaces the Construct 3 block of the project's instruction file and the helpers "
                    "of its tools/build_project.py, each between its markers, with the skill's when they are an "
                    "older version left unedited there. Safe to run again.",
        epilog="examples:\n"
               "  python install.py                          into the project found from the current directory\n"
               "  python install.py --project ../MyGame --into .claude/skills\n"
               "  python install.py --into ~/.agents/skills  one copy for every project of this user\n"
               "  python install.py --helpers-only           the generator's helpers alone, as with the plugin\n"
               "  python install.py --block-only             the instruction file's Construct 3 block alone\n\n"
               "skills directories: .agents/skills is read by most agents; Claude Code reads .claude/skills,\n"
               "TRAE .trae/skills (.agents/skills once enabled in its settings), Deep Code .deepcode/skills.\n\n"
               "exit codes: 0 installed or already current, 1 no project or no clone found; with --helpers-only\n"
               "or --block-only, 0 when the part it refreshes is the skill's and 1 when it is not: missing, no\n"
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
    ap.add_argument("--replace-edited-helpers", nargs="?", const="", metavar="NAME,NAME",
                    help=f"replace the helpers of {c3.GENERATOR} even when they were edited there, once each "
                         f"helper edited there has a def of its name below the end marker, where it replaces "
                         f"the skill's, or is named here as one to take the skill's of. Without the clone's "
                         f"history, every helper that differs from the skill's counts as edited")
    ap.add_argument("--block-only", action="store_true",
                    help="refresh only the Construct 3 block of the project's AGENTS.md or CLAUDE.md, between its "
                         "markers; no copy of the skill is written. For a project that uses the skill without a "
                         "copy, as the Claude Code plugin does")
    ap.add_argument("--replace-edited-block", action="store_true",
                    help="replace the Construct 3 block even when its text was edited between its markers. The "
                         "lines that name a clone's folder stay; move the project's own lines below the end "
                         "marker first")
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

    if args.helpers_only or args.block_only:
        if project is None:
            sys.exit(f"no project.c3proj in {Path.cwd()} or above it; run this from the game project, or pass "
                     f"--project <folder>")
        current, lines = True, []
        if args.block_only:
            # the folder of the project's copy of the skill; without a copy, the one the block names
            held = args.into or any(project.glob(f".*/skills/{SKILL}/SKILL.md"))
            ok, notes = refresh_block(project, rag, c3.instruction_block(project),
                                      shown(targets(project, args.into)[0], project) if held else None,
                                      args.replace_edited_block, args.dry_run)
            current, lines = current and ok, lines + notes
        if args.helpers_only:
            ok, notes = generator(project, rag, args.replace_edited_helpers, args.dry_run)
            current = current and ok
            lines += notes or [f"{c3.GENERATOR}: not in {project}, so there are no helpers to refresh"]
        print("\n".join(lines))
        if args.dry_run:
            print("dry run: nothing was written")
        return 0 if current else 1

    places = targets(project, args.into)
    for target in places:
        print(f"{shown(target, project)}: {mirror(SKILL_DIR, target, args.dry_run)}")
    if project:
        notes = unnamed_clone(project, rag) if args.no_block else \
            add_block(project, rag, shown(places[0], project), args.replace_edited_block, args.dry_run)
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
