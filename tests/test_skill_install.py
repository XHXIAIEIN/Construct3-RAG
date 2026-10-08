"""install.py and scripts/bootstrap.py: the skill reaches a game project, and its scripts find the
clone through the project alone."""
import datetime
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.skill_helpers import REPO, SKILL, INSTALLED, run, check, install, new_project, warnings

sys.path.insert(0, str(SKILL / "scripts"))
import c3project as c3  # noqa: E402

BLOCK_LINES = c3.text_lines(c3.BLOCK_TEMPLATE)[0]
BLOCK_VERSION = c3.block_in(BLOCK_LINES, past=False).version


# --- installing the skill in a game project ---------------------------------------------------
def test_install_copies_the_skill_and_writes_the_block_with_the_clones_path(tmp_path):
    root = new_project(tmp_path / "game")
    code, out = install(root)
    assert code == 0, out
    assert out.rstrip().splitlines()[-1] == f"ok: read {INSTALLED}/SKILL.md"
    assert (root / INSTALLED / "SKILL.md").is_file() and (root / INSTALLED / "scripts" / "check_project.py").is_file()
    block = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert f"- Construct3-RAG: {REPO.as_posix()}" in block and f"`{INSTALLED}/SKILL.md`" in block
    # the path line is what lets the installed scripts find the schemas on their own
    code, out = run(root, f"{INSTALLED}/scripts/lookup_ace.py", "System", "wait")
    assert code == 0 and "action wait - Wait [system]" in out


def test_a_copy_holds_no_evals_and_is_current_without_them(project):
    """evals/ tests the skill from the clone: a game project neither carries it nor is told to refresh over it."""
    assert (SKILL / "evals" / "evals.json").is_file()
    assert not (project / INSTALLED / "evals").exists()
    code, out = check(project)
    assert code == 0 and "differs from the clone's" not in out, out


def test_install_again_changes_nothing(project):
    before = (project / "AGENTS.md").read_text(encoding="utf-8")
    code, out = install(project)
    assert code == 0 and f"{INSTALLED}: " in out and "files, already current" in out
    assert f"AGENTS.md: its Construct 3 block is the skill's of {BLOCK_VERSION}, already current" in out
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == before


def test_install_leaves_an_instruction_file_that_names_the_clone(tmp_path):
    root = new_project(tmp_path / "game")
    mine = f"# My game\n\n- Construct3-RAG: {REPO.as_posix()}\n"
    (root / "CLAUDE.md").write_text(mine, encoding="utf-8")
    code, out = install(root)
    assert code == 0 and "CLAUDE.md: left as it is" in out and "The row to add" in out
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == mine and not (root / "AGENTS.md").exists()


def test_install_into_a_clients_own_skills_folder(tmp_path):
    root = new_project(tmp_path / "game")
    code, out = install(root, "--into", ".claude/skills")
    assert code == 0, out
    assert "`.claude/skills/construct3-agent-plugin/SKILL.md`" in (root / "AGENTS.md").read_text(encoding="utf-8")
    (root / "tools").mkdir()
    shutil.copy(SKILL / "assets" / "build_project.py", root / "tools" / "build_project.py")
    code, out = run(root, "tools/build_project.py")     # the generator finds the checker there too
    assert code == 0 and out.rstrip().splitlines()[-1].startswith("ok:"), out


def test_install_without_the_block_says_how_the_scripts_find_the_clone(tmp_path):
    root = new_project(tmp_path / "game")
    code, out = install(root, "--no-block")
    assert code == 0 and not (root / "AGENTS.md").exists()
    assert f"--rag {REPO.as_posix()}" in out and "CONSTRUCT3_RAG" in out
    assert "where your client stores notes between sessions" in out   # the one record left, as with the block
    (root / "CLAUDE.md").write_text(f"- Construct3-RAG: {REPO.as_posix()}\n", encoding="utf-8")
    code, out = install(root, "--no-block")
    assert code == 0 and "CONSTRUCT3_RAG" not in out


def test_install_dry_run_writes_nothing(tmp_path):
    root = new_project(tmp_path / "game")
    code, out = install(root, "--dry-run")
    assert code == 0 and "nothing was written" in out
    assert sorted(p.name for p in root.iterdir()) == ["project.c3proj"]


def test_install_names_the_copies_a_project_got_by_hand(tmp_path):
    """A project from before the skill: its tools/ holds a checker nothing refreshes."""
    root = new_project(tmp_path / "game")
    (root / "tools").mkdir()
    for name in ("check-project.py", "build-project.py"):
        (root / "tools" / name).write_text("", encoding="utf-8")
    code, out = install(root)
    assert code == 0
    assert f"tools/check-project.py: an earlier copy of the checker that nothing refreshes; run {INSTALLED}/scripts/" in out
    assert "tools/build-project.py: it ends by running the checker beside it" in out
    assert (root / "tools" / "check-project.py").exists()       # said, not removed: the file is the user's


def test_install_names_a_copy_under_the_skills_former_name(tmp_path):
    """A project installed before the rename keeps the old folder and the instruction lines that run it."""
    root = new_project(tmp_path / "game")
    old = root / ".agents" / "skills" / "construct3-project"
    old.mkdir(parents=True)
    (old / "SKILL.md").write_text("---\nname: construct3-project\n---\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(f"- Construct3-RAG: {REPO.as_posix()}\n\n"
                                    "Run .agents/skills/construct3-project/scripts/check_project.py\n", encoding="utf-8")
    code, out = install(root)
    assert code == 0, out
    assert (".agents/skills/construct3-project: a copy of this skill under its former name, which nothing refreshes "
            "and a client lists beside construct3-agent-plugin") in out
    assert f"AGENTS.md: names the skill's former folder construct3-project; write {INSTALLED} in place of" in out
    assert (old / "SKILL.md").exists() and (root / INSTALLED / "SKILL.md").exists()


def test_install_outside_a_project_says_what_to_pass(tmp_path):
    code, out = install(tmp_path)
    assert code != 0 and "--project" in out and "Traceback" not in out
    assert f"To start a new project, run python {(SKILL / 'scripts' / 'new_project.py').as_posix()} <folder>" in out


def test_install_into_a_folder_without_a_project_names_new_project(tmp_path):
    """An agent asked for a new game makes the folder and runs install.py on it first;
    install.py fills a project, and new_project.py is what creates one."""
    game = tmp_path / "New Game"
    game.mkdir()
    code, out = install(tmp_path, "--project", str(game))
    assert code == 1 and f"no project.c3proj in {game}" in out
    assert f'run python {(SKILL / "scripts" / "new_project.py").as_posix()} "{game}"' in out


def test_install_asks_the_agent_to_remember_where_the_clone_is(tmp_path):
    """The block records the clone for this project and nothing records it for the machine, since
    install.py writes inside the project only. A project that starts without a block leaves the
    agent's own memory as the one place the clone can be found again."""
    root = new_project(tmp_path / "game")
    code, out = install(root)
    assert code == 0 and f"memory: keep 'Construct3-RAG: {REPO.as_posix()}'" in out
    # the project now names the clone itself, and the line would be noise on every refresh
    code, out = install(root)
    assert code == 0 and "memory:" not in out


def test_install_leads_claude_code_to_the_block_through_claude_md(tmp_path):
    """Claude Code reads CLAUDE.md when it exists; a novice's project has none, or one without the line."""
    root = new_project(tmp_path / "game")
    code, out = install(root)
    assert code == 0 and "CLAUDE.md: created with the line @AGENTS.md" in out
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    root = new_project(tmp_path / "other")
    (root / "CLAUDE.md").write_text("# Mine\n", encoding="utf-8")
    code, out = install(root)
    assert code == 0 and "CLAUDE.md: added the line @AGENTS.md" in out
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "# Mine\n\n@AGENTS.md\n"
    code, out = install(root)
    assert "CLAUDE.md" not in out


def test_install_adds_the_claude_md_line_when_agents_md_already_has_the_block(tmp_path):
    """An AGENTS.md that already names the clone is left as it is, and a CLAUDE.md without @AGENTS.md still gets
    the line (the audit of 2026-10-07 found it reported as complete); --no-block writes neither."""
    root = new_project(tmp_path / "game")
    code, out = install(root)
    assert code == 0, out
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Mine\n", encoding="utf-8")
    code, out = install(root, "--no-block")
    assert code == 0 and (root / "CLAUDE.md").read_text(encoding="utf-8") == "# Mine\n"
    code, out = install(root)
    assert code == 0 and f"AGENTS.md: its Construct 3 block is the skill's of {BLOCK_VERSION}, already current" in out
    assert "CLAUDE.md: added the line @AGENTS.md" in out
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "# Mine\n\n@AGENTS.md\n"
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == agents


# --- bootstrapping a machine from the clone alone ---------------------------------------------
def bootstrap(root: Path, *args: str) -> tuple[int, str]:
    return run(root, REPO / "scripts" / "bootstrap.py", *args)


def template(folder: Path) -> Path:
    """An empty project reduced to the keys the checker reads."""
    folder.mkdir(parents=True)
    (folder / "project.c3proj").write_text(json.dumps({
        "name": "New project", "uniqueId": "he3qe448adg", "properties": {},
        "layouts": {"items": ["Layout 1"], "subfolders": []},
        "eventSheets": {"items": ["Event sheet 1"], "subfolders": []}}), encoding="utf-8")
    (folder / "layouts").mkdir()
    (folder / "layouts" / "Layout 1.json").write_text(json.dumps({"name": "Layout 1", "layers": [], "sid": 1}), encoding="utf-8")
    (folder / "eventSheets").mkdir()
    (folder / "eventSheets" / "Event sheet 1.json").write_text(json.dumps({"name": "Event sheet 1", "events": [], "sid": 2}), encoding="utf-8")
    return folder


def siblings(folder: Path) -> Path:
    for name in ("Construct3-Manual", "Construct-Addon-SDK", "Construct-Example-Projects"):
        (folder / name).mkdir(parents=True)
        (folder / name / "README.md").write_text("", encoding="utf-8")
    return folder


def test_bootstrap_creates_the_project_from_the_template_and_installs_the_skill(tmp_path):
    beside = siblings(tmp_path / "GitHub")
    game = tmp_path / "MyGame"
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--template", str(template(tmp_path / "tmpl")),
                          "--project", str(game))
    assert code == 0, out
    assert out.count("already at") == 3 and f"MyGame: created from tmpl at {game}" in out
    assert out.rstrip().splitlines()[-1] == f"ok: read {INSTALLED}/SKILL.md"
    proj = json.loads((game / "project.c3proj").read_text(encoding="utf-8"))
    assert proj["name"] == "MyGame" and re.fullmatch(r"[a-z0-9]{11}", proj["uniqueId"]) and proj["uniqueId"] != "he3qe448adg"
    assert (game / INSTALLED / "SKILL.md").is_file()
    assert (game / ".git").is_dir() and "git initialised" in out
    block = (game / "AGENTS.md").read_text(encoding="utf-8")
    assert f"- Construct3-RAG: {REPO.as_posix()}" in block
    assert (game / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    # the clones are not beside the Construct3-RAG clone here, so the block gets a line for each
    assert f"- Construct3-Manual: {(beside / 'Construct3-Manual').as_posix()}" in block
    assert block.index("- Construct3-RAG:") < block.index("- Construct3-Manual:") < block.index("Anything that changes")
    # a second run finds everything in place
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--project", str(game))
    assert code == 0 and "already current" in out and "created from" not in out
    assert (game / "AGENTS.md").read_text(encoding="utf-8") == block


def test_bootstrap_without_the_examples_says_what_they_are_missing_for(tmp_path):
    beside = tmp_path / "GitHub"
    for name in ("Construct3-Manual", "Construct-Addon-SDK"):
        (beside / name).mkdir(parents=True)
        (beside / name / "README.md").write_text("", encoding="utf-8")
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--no-examples")
    assert code == 0, out
    assert ("Construct-Example-Projects: not cloned (--no-examples), so print_sheet.py reads no official "
            "example and search_guides.py gives each one's editor URL; run this again without --no-examples "
            "to clone it") in out, out


def test_bootstrap_puts_a_named_project_beside_the_clones_whatever_the_directory(tmp_path):
    """The README's `--project MyGame` is a name, and a name goes where the clones are: a user or an
    agent that runs the command from somewhere else gets one set of folders, not a second one."""
    beside = siblings(tmp_path / "GitHub")
    tmpl = str(template(tmp_path / "tmpl"))
    elsewhere = tmp_path / "Desktop"
    elsewhere.mkdir()
    code, out = bootstrap(elsewhere, "--beside", str(beside), "--template", tmpl, "--project", "MyGame")
    assert code == 0, out
    assert (beside / "MyGame" / "project.c3proj").is_file() and not (elsewhere / "MyGame").exists()
    # a path spelt out is still read from the directory the command was run in
    code, out = bootstrap(elsewhere, "--beside", str(beside), "--template", tmpl, "--project", "./Other")
    assert code == 0, out
    assert (elsewhere / "Other" / "project.c3proj").is_file() and not (beside / "Other").exists()


def test_bootstrap_leaves_a_folder_that_is_not_a_project(tmp_path):
    beside = siblings(tmp_path / "GitHub")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.txt").write_text("", encoding="utf-8")
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--template", str(template(tmp_path / "tmpl")),
                          "--project", str(tmp_path / "docs"))
    assert code == 1 and "is not empty and holds no project.c3proj" in out
    assert sorted(p.name for p in (tmp_path / "docs").iterdir()) == ["notes.txt"]


def test_bootstrap_fills_a_folder_that_holds_only_a_git_repository(tmp_path):
    """An agent often makes the folder and runs git init before it finds bootstrap.py."""
    beside = siblings(tmp_path / "GitHub")
    game = tmp_path / "MyGame"
    (game / ".git").mkdir(parents=True)
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--template", str(template(tmp_path / "tmpl")),
                          "--project", str(game))
    assert code == 0, out
    assert (game / "project.c3proj").is_file() and (game / INSTALLED / "SKILL.md").is_file()


def test_bootstrap_dry_run_says_the_clones_it_would_make(tmp_path):
    code, out = bootstrap(tmp_path, "--beside", str(tmp_path / "GitHub"), "--project", str(tmp_path / "MyGame"),
                          "--dry-run")
    assert code == 0 and "nothing was done" in out, out
    assert out.count("would run git clone") == 3 and "--depth 1 https://github.com/Scirra/Construct-Example-Projects" in out
    assert not (tmp_path / "GitHub").exists() and not (tmp_path / "MyGame").exists()


def test_bootstrap_copies_the_committed_empty_project(tmp_path):
    """Without --template the project is the editor's empty project kept in data/, copied
    offline, with its own name and id, and the checker passes it."""
    beside = siblings(tmp_path / "GitHub")
    game = tmp_path / "MyGame"
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--project", str(game))
    assert code == 0, out
    assert "git clone" not in out and f"MyGame: created from c3-new-project at {game}" in out
    proj = json.loads((game / "project.c3proj").read_text(encoding="utf-8"))
    kept = json.loads((REPO / "data" / "c3-new-project" / "project.c3proj").read_text(encoding="utf-8"))
    assert proj["name"] == "MyGame" and proj["uniqueId"] != kept["uniqueId"]
    same = lambda d: {k: v for k, v in d.items() if k not in ("name", "uniqueId")}  # noqa: E731
    assert same(proj) == same(kept)
    code, out = check(game)
    assert code == 0 and out.rstrip().splitlines()[-1].startswith("ok:"), out


def test_bootstrap_names_the_way_round_a_template_that_is_not_a_project(tmp_path):
    beside = siblings(tmp_path / "GitHub")
    (tmp_path / "empty").mkdir()
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--template", str(tmp_path / "empty"),
                          "--project", str(tmp_path / "MyGame"))
    assert code == 1 and "MyGame: not created" in out and "Project > New" in out
    assert not (tmp_path / "MyGame").exists()


def test_a_copy_that_differs_from_the_clone_says_how_to_refresh_it(project):
    script = project / INSTALLED / "scripts" / "print_sheet.py"
    script.write_text(script.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    code, out = check(project)
    # a problem: a warning above the passing check's last line goes unread
    assert code == 1 and "warning: this copy" not in out
    assert "this copy of the construct3-agent-plugin skill differs from the clone's" in out
    assert "scripts/print_sheet.py" in out and "install.py" in out
    # the other scripts say it first, on stdout with their result: a Doubao run in PowerShell
    # read it as an error record on every call of a stale copy
    p = subprocess.run([sys.executable, f"{INSTALLED}/scripts/lookup_ace.py", "--rag", str(REPO), "System", "wait"],
                       cwd=project, env=dict(os.environ, PYTHONIOENCODING="utf-8"), capture_output=True, text=True,
                       encoding="utf-8")
    assert p.returncode == 0 and p.stderr == ""
    assert p.stdout.startswith("note: this copy of the construct3-agent-plugin skill differs from the clone's")
    assert "condition wait " not in p.stdout.splitlines()[0] and "action wait " in p.stdout
    # the installed copy hands over to the clone's install.py, which restores the file
    code, out = run(project, f"{INSTALLED}/scripts/install.py")
    assert code == 0 and "wrote scripts/print_sheet.py" in out, out
    code, out = check(project)
    assert "differs from the clone's" not in out


# --- refreshing the helpers of a game's generator ----------------------------------------------
TEMPLATE = (SKILL / "assets" / "build_project.py").read_text(encoding="utf-8").split("\n")
TEMPLATE_HELPERS = c3.helpers_in(TEMPLATE)
VERSION = TEMPLATE_HELPERS.version


def at(lines: list[str], prefix: str) -> int:
    return next(i for i, line in enumerate(lines) if line.startswith(prefix))


def as_the_game_has_it(lines: list[str]) -> list[str]:
    """The template's lines with a game's own changes outside the markers: its name, and a
    helper of its own below the end marker."""
    lines = list(lines)
    lines[at(lines, "PROJECT_NAME = ")] = 'PROJECT_NAME = "Gems"'
    main = at(lines, 'if __name__ == "__main__":')
    lines[main:main] = ["def gem_value() -> int:", '    """What a gem is worth."""', "    return 5", "", ""]
    return lines


def older_generator(root: Path, version: str = "2026-09-01", edited: bool = False, newline: str = "\n") -> bytes:
    """tools/build_project.py as a game holds it after a copy of an older template: tween_width() not
    written yet, units() without its docstring, the end marker stamped for that part and dated
    earlier. edited changes a line between the markers afterwards, as an agent's edit there does."""
    lines = list(TEMPLATE)
    del lines[at(lines, "def tween_width("):at(lines, "def tween_value(")]
    del lines[at(lines, '    """n grid units in pixels')]
    helpers = c3.helpers_in(lines)
    lines[helpers.end] = c3.helpers_end_line(version, helpers.actual)
    if edited:
        lines[at(lines, '    """v moved to the nearest grid line')] = '    """v moved to the grid line under it."""'
    data = newline.join(as_the_game_has_it(lines)).encode("utf-8")
    (root / "tools").mkdir(exist_ok=True)
    (root / "tools" / "build_project.py").write_bytes(data)
    return data


def test_install_refreshes_an_older_generators_helpers_and_keeps_the_game(project):
    """A game's generator keeps the helpers of the day it was copied. When the skill is refreshed,
    its part between the markers becomes the skill's, since nothing there was edited, and every
    line outside them stays as the game had it, line ends included."""
    older_generator(project, newline="\r\n")
    code, out = check(project)
    assert code == 0 and (f"warning: tools/build_project.py: its helpers, between the markers, are the skill's of "
                          f"2026-09-01, and the skill's are now of {VERSION}") in out, out
    assert "scripts/install.py --helpers-only, then run python tools/build_project.py" in out
    code, out = install(project)
    assert code == 0 and (f"tools/build_project.py: replaced its helpers of 2026-09-01 with the skill's of "
                          f"{VERSION}; the lines outside the markers are as they were") in out, out
    data = (project / "tools" / "build_project.py").read_bytes()
    assert data == "\r\n".join(as_the_game_has_it(TEMPLATE)).encode("utf-8")
    code, out = run(project, "tools/build_project.py")
    assert code == 0 and warnings(out) == [], out
    assert json.loads((project / "project.c3proj").read_text(encoding="utf-8"))["name"] == "Gems"
    code, out = install(project)
    assert code == 0 and f"tools/build_project.py: its helpers are the skill's of {VERSION}, already current" in out


def test_install_keeps_helpers_edited_in_the_game_and_says_how_to_take_the_new_ones(project):
    """An edit between the markers is the game's: the refresh leaves the part as it is and says to
    move the edit below the end marker, where a def replaces the skill's, before it replaces the part."""
    before = older_generator(project, edited=True)
    code, out = check(project)
    assert code == 0 and "are the skill's of 2026-09-01 with edits made there" in out and \
        "install.py --helpers-only --replace-edited-helpers" in out, out
    code, out = install(project)
    assert code == 0 and "tools/build_project.py: its helpers, between the markers, were edited there, so they " \
                         "were left as they are. Copy each helper changed there below the end marker" in out, out
    assert "--replace-edited-helpers" in out
    generator = project / "tools" / "build_project.py"
    assert generator.read_bytes() == before
    # the agent moves its snap() below the end marker, then takes the skill's helpers
    text = generator.read_text(encoding="utf-8").replace(
        'if __name__ == "__main__":', 'def snap(v: float) -> int:\n    """v moved to the grid line under it."""\n'
        '    return int(v // UNIT) * UNIT\n\n\nif __name__ == "__main__":')
    generator.write_text(text, encoding="utf-8", newline="\n")
    code, out = install(project, "--helpers-only", "--replace-edited-helpers=units")
    assert code == 0 and "replaced its helpers of 2026-09-01" in out, out
    lines = generator.read_text(encoding="utf-8").split("\n")
    helpers = c3.helpers_in(lines)
    assert lines[helpers.begin:helpers.end + 1] == TEMPLATE[TEMPLATE_HELPERS.begin:TEMPLATE_HELPERS.end + 1]
    game = runpy.run_path(str(generator), run_name="generator")
    assert game["snap"].__doc__ == "v moved to the grid line under it." and game["snap"](40) == 32


def test_replacing_edited_helpers_refuses_while_an_edit_would_be_lost(project):
    """The printed command run before the edit is copied below the end marker must not drop the edit:
    it names each helper that differs from the skill's and has no def below the end marker, with the
    first line that differs, and writes nothing."""
    before = older_generator(project, edited=True)
    generator = project / "tools" / "build_project.py"
    code, out = install(project, "--helpers-only", "--replace-edited-helpers")
    assert code == 1 and generator.read_bytes() == before, out
    assert "snap: here '    \"\"\"v moved to the grid line under it.\"\"\"', the skill's " in out, out
    assert "units: here " in out and "Copy below the end marker each one the game changed" in out, out
    assert out.rstrip().endswith("--helpers-only --replace-edited-helpers=NAME,NAME"), out

    # snap() copied below the end marker; units() differs because the skill's changed since
    text = generator.read_text(encoding="utf-8").replace(
        'if __name__ == "__main__":', 'def snap(v: float) -> int:\n    """v moved to the grid line under it."""\n'
        '    return int(v // UNIT) * UNIT\n\n\nif __name__ == "__main__":')
    generator.write_text(text, encoding="utf-8", newline="\n")
    code, out = install(project, "--helpers-only", "--replace-edited-helpers")
    assert code == 1 and "snap:" not in out and "units: here " in out, out
    code, out = install(project, "--helpers-only", "--replace-edited-helpers=units")
    assert code == 0 and "replaced its helpers of 2026-09-01" in out, out
    game = runpy.run_path(str(generator), run_name="generator")
    assert game["snap"].__doc__ == "v moved to the grid line under it."


def git(folder: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "core.autocrlf=false", *args],
                          check=True, capture_output=True, text=True, encoding="utf-8").stdout


def older_template() -> list[str]:
    """The template as older_generator() copies it, before the game changes anything."""
    lines = list(TEMPLATE)
    del lines[at(lines, "def tween_width("):at(lines, "def tween_value(")]
    del lines[at(lines, '    """n grid units in pixels')]
    helpers = c3.helpers_in(lines)
    lines[helpers.end] = c3.helpers_end_line("2026-09-01", helpers.actual)
    return lines


def clone_with_history(folder: Path) -> Path:
    """A clone of the skill alone with three commits of the generator template: one from before the
    markers, the one older_generator() copies, then the current one."""
    skill = folder / "skills" / SKILL.name
    shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("evals", "__pycache__"))
    index = folder / "data" / "c3-schemas" / "_index.json"
    index.parent.mkdir(parents=True)
    shutil.copy(REPO / "data" / "c3-schemas" / "_index.json", index)
    git(folder, "init", "-q")
    for k, lines in enumerate([["# before the markers"], older_template(), TEMPLATE]):
        (skill / "assets" / "build_project.py").write_bytes("\n".join(lines).encode("utf-8"))
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", f"template {k}")
    return folder


SNAP_BELOW = ('def snap(v: float) -> int:\n    """v moved to the grid line under it."""\n'
              '    return int(v // UNIT) * UNIT\n\n\nif __name__ == "__main__":')


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_with_the_clones_history_only_the_helpers_the_game_edited_block(tmp_path):
    """The clone's history holds the template the game's part was copied from, so a helper is the
    game's edit only when it differs from that template's: units(), which differs because the
    skill's changed since, needs neither a copy below the end marker nor a name in the flag."""
    script = clone_with_history(tmp_path / "rag") / "skills" / SKILL.name / "scripts" / "install.py"
    project = new_project(tmp_path / "game")
    before = older_generator(project, edited=True)
    generator = project / "tools" / "build_project.py"
    code, out = run(project, script, "--helpers-only")
    assert code == 1 and "snap" in out and "units" not in out, out
    code, out = run(project, script, "--helpers-only", "--replace-edited-helpers")
    assert code == 1 and generator.read_bytes() == before, out
    assert "snap: here '    \"\"\"v moved to the grid line under it.\"\"\"'" in out and "units" not in out, out
    assert out.rstrip().endswith("--helpers-only --replace-edited-helpers"), out

    generator.write_text(generator.read_text(encoding="utf-8").replace('if __name__ == "__main__":', SNAP_BELOW),
                         encoding="utf-8", newline="\n")
    code, out = run(project, script, "--helpers-only", "--replace-edited-helpers")
    assert code == 0 and "replaced its helpers of 2026-09-01" in out, out
    game = runpy.run_path(str(generator), run_name="generator")
    assert game["snap"].__doc__ == "v moved to the grid line under it."


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_copied_template_is_the_newest_commit_whose_part_has_the_stamp(tmp_path):
    stamp = c3.helpers_in(older_template()).stamp
    assert c3.copied_template(tmp_path, stamp) is None                  # no .git
    clone = clone_with_history(tmp_path / "rag")
    # the lines as git prints them, without the empty line after the file's last newline
    assert c3.copied_template(clone, stamp) == older_template()[:len(older_template()) - 1]
    assert c3.copied_template(clone, TEMPLATE_HELPERS.stamp) == TEMPLATE[:len(TEMPLATE) - 1]
    assert c3.copied_template(clone, "0" * 12) is None                  # no commit has it, down to the one without markers


def test_install_helpers_only_refreshes_the_generator_alone(tmp_path):
    """A project used through the Claude Code plugin holds no copy of the skill: --helpers-only
    refreshes the generator's helpers and writes nothing else."""
    root = new_project(tmp_path / "game")
    older_generator(root)
    code, out = install(root, "--helpers-only", "--dry-run")
    assert code == 0 and "would replace its helpers of 2026-09-01" in out and "dry run: nothing was written" in out
    assert c3.helpers_in((root / "tools" / "build_project.py").read_text(encoding="utf-8").split("\n")).version \
        == "2026-09-01"
    code, out = install(root, "--helpers-only")
    assert code == 0 and "replaced its helpers of 2026-09-01" in out, out
    assert sorted(p.name for p in root.iterdir()) == ["project.c3proj", "tools"]
    code, out = install(root, "--helpers-only")
    assert code == 0 and "already current" in out
    (root / "tools" / "build_project.py").unlink()
    code, out = install(root, "--helpers-only")
    assert code == 1 and "tools/build_project.py: not in" in out


def older_generator_changed(root: Path, change: Callable[[str], str]) -> None:
    """older_generator(), then its text changed by change."""
    older_generator(root)
    path = root / "tools" / "build_project.py"
    path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")


def unmarked(root: Path) -> None:
    """A generator copied before the template marked its helpers."""
    older_generator_changed(root, lambda text: "\n".join(line for line in text.split("\n")
                                                         if "construct3-agent-plugin helpers:" not in line))


def without_end_marker(root: Path) -> None:
    older_generator_changed(root, lambda text: "\n".join(line for line in text.split("\n")
                                                         if "helpers: end" not in line))


def not_compiling(root: Path) -> None:
    older_generator_changed(root, lambda text: text.replace("def gem_value() -> int:", "def gem_value( -> int:"))


@pytest.mark.parametrize("make, said, checked", [
    (unmarked, "tools/build_project.py: written before the template marked its helpers, so nothing refreshes them; "
               "left as it is", None),
    (lambda root: older_generator(root, version="2099-01-01"), "its helpers are of 2099-01-01, newer than this "
                                                              "skill's", None),
    (without_end_marker, "tools/build_project.py: it has 1 begin and 0 end markers of the helpers, not one of each; "
                         "copy the marker lines", "until then the skill cannot refresh its helpers"),
    (not_compiling, "with the skill's helpers it would not compile, line", "are the skill's of 2026-09-01, and"),
])
def test_install_leaves_a_generator_it_cannot_refresh(project, make, said, checked):
    make(project)
    generator = project / "tools" / "build_project.py"
    before = generator.read_bytes()
    code, out = install(project, "--helpers-only")
    assert code == 1 and said in out, out
    assert generator.read_bytes() == before
    code, out = install(project)
    assert code == 0 and said in out
    code, out = check(project)
    assert (checked in out) if checked else "tools/build_project.py" not in out, out


# --- refreshing the Construct 3 block of the instruction file ------------------------------------
# The lines that name a clone's folder in a project: the Construct3-RAG line install.py fills in, and one
# that bootstrap.py adds for a clone kept elsewhere. Neither counts as an edit of the block.
PLACES = [f"- Construct3-RAG: {REPO.as_posix()}", "- Construct3-Manual: D:/Elsewhere/Construct3-Manual"]
ABOVE = ["# Gems", "", "The project's own notes.", ""]
BELOW = ["", "## Ours", "", "A line the project keeps below the block.", ""]
# The block as the skill held it on 2026-10-02, before the block had markers. Its text dates from
# 2026-09-22, the version PAST_BLOCKS gives it, and a later version added a row.
PAST_BLOCK = (REPO / "tests" / "fixtures" / "game-project-block-2026-10-02.md").read_text(encoding="utf-8")


def rendered(places: list[str] = PLACES, skill: str = INSTALLED) -> list[str]:
    """The skill's block as a project holds it, markers included: its lines that name a clone's folder
    in place of the template's one, and the folder its copy of the skill is in."""
    lines = [line.replace(".agents/skills/construct3-agent-plugin", skill) for line in BLOCK_LINES[:-1]]
    at = lines.index("- Construct3-RAG: <path-to>/Construct3-RAG")
    return lines[:at] + places + lines[at + 1:]


def write_agents_md(root: Path, block: list[str], newline: str = "\n") -> bytes:
    data = newline.join(ABOVE + block + BELOW).encode("utf-8")
    (root / "AGENTS.md").write_bytes(data)
    return data


def older_block(root: Path, version: str = "2026-09-01", edited: bool = False, newline: str = "\n",
                skill: str = INSTALLED) -> bytes:
    """AGENTS.md with the block of an older version between text of the project's own: the last row
    of the table not written yet, the end marker stamped for that text and dated earlier. edited
    changes a line of the text afterwards, as an agent's edit there does."""
    lines = rendered(skill=skill)
    del lines[-2]
    lines[-1] = c3.block_end_line(version, c3.block_stamp(lines[1:-1]))
    if edited:
        lines[lines.index("eventSheets/*.json. Do not answer it from memory.")] = "eventSheets/*.json. Ask first."
    return write_agents_md(root, lines, newline)


def test_template_stamps_its_block():
    """The block's end marker carries its version and the stamp of its text, so that a project's
    block tells an older version, which install.py replaces, from one edited there, which it keeps.
    Changed text fails here until the end marker carries its stamp."""
    block = c3.block_in(BLOCK_LINES, past=False)
    assert isinstance(block, c3.Block), block
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    assert block.stamp == block.actual, (
        f"the text of assets/game-project-block.md changed, so its version and stamp did: replace line "
        f"{block.end + 1}, the end marker, with\n{c3.block_end_line(today, block.actual)}")
    assert BLOCK_LINES[block.end] == c3.block_end_line(block.version, block.stamp)
    # install.py appends the file whole, so everything in it is between the markers
    assert block.begin == 0 and BLOCK_LINES[block.end + 1:] == [""]


def test_install_writes_the_block_between_markers(tmp_path):
    root = new_project(tmp_path / "game")
    code, out = install(root)
    assert code == 0, out
    lines = (root / "AGENTS.md").read_text(encoding="utf-8").split("\n")
    assert lines[:-1] == rendered(PLACES[:1])
    assert c3.instruction_block(root).state == "current"


def test_install_refreshes_an_older_block_and_keeps_the_project(project):
    """A project's block keeps the text of the day it was written. When the skill is refreshed, the
    block becomes the skill's, since nothing in it was edited, and its lines that name a clone's folder
    and every line outside it stay as the project had them, line ends included."""
    older_block(project, newline="\r\n")
    code, out = check(project)
    assert code == 0 and (f"warning: AGENTS.md: its Construct 3 block is the skill's of 2026-09-01 and the skill's "
                          f"is now of {BLOCK_VERSION}; refresh it") in out, out
    assert "scripts/install.py --block-only" in out
    code, out = install(project)
    assert code == 0 and (f"AGENTS.md: replaced its Construct 3 block of 2026-09-01 with the skill's of "
                          f"{BLOCK_VERSION}; the lines that name a clone's folder and every line outside the block "
                          f"are as they were") in out, out
    assert (project / "AGENTS.md").read_bytes() == "\r\n".join(ABOVE + rendered() + BELOW).encode("utf-8")
    code, out = check(project)
    assert "Construct 3 block" not in out, out
    code, out = install(project)
    assert code == 0 and f"AGENTS.md: its Construct 3 block is the skill's of {BLOCK_VERSION}, already current" in out


def test_install_keeps_a_block_edited_in_the_project_and_says_where(project):
    """An edit between the markers is the project's: the refresh leaves the block as it is, names the
    lines that differ, and takes the skill's block only when asked, after the edit has moved below it."""
    before = older_block(project, edited=True)
    code, out = check(project)
    assert code == 0 and "its Construct 3 block is the skill's of 2026-09-01 with edits made between its " \
                         "markers" in out and "install.py --block-only lists the lines that differ" in out, out
    assert "--replace-edited-block" in out
    code, out = install(project)
    assert code == 0 and "AGENTS.md: its Construct 3 block was edited between its markers, so it was left as it " \
                         "is" in out, out
    at = len(ABOVE) + rendered().index("eventSheets/*.json. Do not answer it from memory.") + 1
    assert f"  line {at}: here 'eventSheets/*.json. Ask first.', there 'eventSheets/*.json. Do not answer it " \
           f"from memory.'" in out
    assert "--replace-edited-block" in out and (project / "AGENTS.md").read_bytes() == before
    code, out = install(project, "--block-only", "--replace-edited-block")
    assert code == 0 and "replaced its Construct 3 block of 2026-09-01" in out, out
    assert (project / "AGENTS.md").read_text(encoding="utf-8").split("\n") == ABOVE + rendered() + BELOW


def test_an_edit_with_nothing_newer_to_take_is_said_by_install_alone(project):
    lines = rendered()
    lines[lines.index("eventSheets/*.json. Do not answer it from memory.")] = "eventSheets/*.json. Ask first."
    before = write_agents_md(project, lines)
    code, out = install(project, "--block-only")
    assert code == 1 and "has not changed since it was written; a line the project adds belongs below the end " \
                         "marker" in out, out
    assert (project / "AGENTS.md").read_bytes() == before
    code, out = check(project)
    assert "Construct 3 block" not in out, out


def test_install_refreshes_a_block_written_before_the_markers(project):
    """A block install.py wrote before the block had markers is known by its text, which must be that
    of a version it wrote: then it is replaced, markers and all. Any other text is the project's."""
    past = [line.replace("<path-to>/Construct3-RAG", REPO.as_posix()) for line in PAST_BLOCK.split("\n")[:-1]]
    at = past.index(PLACES[0])
    past[at + 1:at + 1] = PLACES[1:]
    write_agents_md(project, past)
    code, out = check(project)
    assert ("warning: AGENTS.md: its Construct 3 block is the skill's of 2026-09-22, written before the block had "
            "markers, and the skill's is now of") in out, out
    code, out = install(project)
    assert code == 0 and "AGENTS.md: replaced its Construct 3 block of 2026-09-22, written before the block had " \
                         "markers, with the skill's of" in out, out
    assert (project / "AGENTS.md").read_text(encoding="utf-8").split("\n") == ABOVE + rendered() + BELOW
    # one word changed: not a version install.py wrote, so the file is the project's
    past[past.index("eventSheets/*.json. Do not answer it from memory.")] = "eventSheets/*.json. Ask first."
    before = write_agents_md(project, past)
    code, out = install(project)
    assert code == 0 and "AGENTS.md: already names the clone and this skill, left as it is. It holds no block " \
                         "that this script wrote" in out, out
    assert (project / "AGENTS.md").read_bytes() == before
    code, out = check(project)
    assert "Construct 3 block" not in out, out


def test_install_block_only_refreshes_the_block_alone(tmp_path):
    """A project used through the Claude Code plugin holds no copy of the skill: --block-only refreshes
    the block, which keeps naming the folder it named, and writes nothing else."""
    root = new_project(tmp_path / "game")
    older_block(root, skill=".claude/skills/construct3-agent-plugin")
    code, out = install(root, "--block-only", "--dry-run")
    assert code == 0 and "would replace its Construct 3 block of 2026-09-01" in out and "nothing was written" in out
    assert c3.instruction_block(root).have.version == "2026-09-01"
    code, out = install(root, "--block-only")
    assert code == 0 and "replaced its Construct 3 block of 2026-09-01" in out, out
    assert sorted(p.name for p in root.iterdir()) == ["AGENTS.md", "project.c3proj"]
    assert (root / "AGENTS.md").read_text(encoding="utf-8").split("\n") == \
        ABOVE + rendered(skill=".claude/skills/construct3-agent-plugin") + BELOW
    code, out = install(root, "--block-only")
    assert code == 0 and "already current" in out
    (root / "AGENTS.md").unlink()
    code, out = install(root, "--block-only")
    assert code == 1 and "AGENTS.md: holds no Construct 3 block that this script wrote" in out


@pytest.mark.parametrize("change, said", [
    (lambda lines: [line for line in lines if "block: end" not in line],
     "AGENTS.md: it has 1 begin and 0 end markers of the Construct 3 block, not one of each"),
    (lambda lines: [c3.block_end_line("2099-01-01", c3.block_stamp(lines[1:-1])) if "block: end" in line else line
                    for line in lines], "its Construct 3 block is of 2099-01-01, newer than this skill's"),
])
def test_install_leaves_a_block_it_cannot_refresh(project, change, said):
    before = write_agents_md(project, change(rendered()))
    code, out = install(project, "--block-only")
    assert code == 1 and said in out, out
    assert (project / "AGENTS.md").read_bytes() == before
    code, out = install(project)
    assert code == 0 and said in out and (project / "AGENTS.md").read_bytes() == before


# --- finding the schemas ---------------------------------------------------------------
@pytest.mark.parametrize("lines", [
    "- Construct3-RAG: {rag}",
    "- path-to = {parent}\\\n- Construct3-RAG: <path-to>/{name}",
    "- <path-to>: {parent}\n- Construct3-RAG: <path-to>/{name}",
])
def test_rag_is_read_from_the_project_instruction_file(project, lines):
    text = lines.format(rag=REPO.as_posix(), parent=REPO.parent.as_posix(), name=REPO.name)
    (project / "AGENTS.md").write_text(f"# Construct 3\n\n{text}\n\nText after the block.\n", encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/check_project.py")
    assert code == 0, out


def test_unfilled_block_says_how_to_point_at_the_clone(project):
    (project / "AGENTS.md").write_text("- Construct3-RAG: <path-to>/Construct3-RAG\n", encoding="utf-8")
    code, out = run(project, f"{INSTALLED}/scripts/check_project.py")
    assert code != 0
    assert "--rag" in out and "AGENTS.md" in out and "Traceback" not in out
