"""install.py and scripts/bootstrap.py: the skill reaches a game project, and its scripts find the
clone through the project alone."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import REPO, SKILL, INSTALLED, run, check, install, new_project


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
    assert code == 0 and "already current" in out and "left as it is" in out
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


def test_install_outside_a_project_says_what_to_pass(tmp_path):
    code, out = install(tmp_path)
    assert code != 0 and "--project" in out and "Traceback" not in out


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
    assert f"- Construct3-RAG: {REPO.as_posix()}" in (game / "AGENTS.md").read_text(encoding="utf-8")
    assert (game / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    # the clones are not beside the Construct3-RAG clone here, so the block gets a line for each
    block = (game / "AGENTS.md").read_text(encoding="utf-8")
    assert f"- Construct3-Manual: {(beside / 'Construct3-Manual').as_posix()}" in block
    assert block.index("- Construct3-RAG:") < block.index("- Construct3-Manual:") < block.index("Anything that changes")
    # a second run finds everything in place
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--project", str(game))
    assert code == 0 and "already current" in out and "created from" not in out
    assert (game / "AGENTS.md").read_text(encoding="utf-8") == block


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
    assert proj["properties"]["uidAllocationMode"] == "random"
    same = lambda d: {k: v for k, v in d.items() if k not in ("name", "uniqueId", "properties")}  # noqa: E731
    assert same(proj) == same(kept)
    assert {**proj["properties"], "uidAllocationMode": None} == {**kept["properties"], "uidAllocationMode": None}
    code, out = check(game)
    assert code == 0 and out.rstrip().splitlines()[-1].startswith("ok:"), out


def test_bootstrap_names_the_way_round_a_template_that_is_not_a_project(tmp_path):
    beside = siblings(tmp_path / "GitHub")
    (tmp_path / "empty").mkdir()
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--template", str(tmp_path / "empty"),
                          "--project", str(tmp_path / "MyGame"))
    assert code == 1 and "MyGame: not created" in out and "--template <folder>" in out
    assert not (tmp_path / "MyGame").exists()


def test_a_copy_that_differs_from_the_clone_says_how_to_refresh_it(project):
    script = project / INSTALLED / "scripts" / "print_sheet.py"
    script.write_text(script.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    code, out = check(project)
    assert code == 0 and "warning: this copy of the construct3-agent-plugin skill differs from the clone's" in out
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
