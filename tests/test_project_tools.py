"""The construct3-project skill, used the way an agent uses it.

The skill is installed in a project folder by its own install.py and its
scripts run as subprocesses from there. The stand-in game of
assets/build_project.py is generated once; each test breaks a private copy in
one way and reads what the checker says about it. Every rule tested here is
one the editor enforces when it opens or previews a project
(docs/decisions/checker-editor-load-rules.md).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "construct3-project"
INSTALLED = ".agents/skills/construct3-project"
SHEET = "eventSheets/Game.json"


def run(root: Path, script: str | Path, *args: str) -> tuple[int, str]:
    """A script run from the project folder. No CONSTRUCT3_RAG and an empty home:
    the clone and the skill are found through the project alone."""
    env = {k: v for k, v in os.environ.items() if k != "CONSTRUCT3_RAG"}
    env.update(PYTHONIOENCODING="utf-8", HOME=str(root / ".home"), USERPROFILE=str(root / ".home"))
    p = subprocess.run([sys.executable, str(script), *args], cwd=root, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def tool(root: Path, name: str, *args: str) -> tuple[int, str]:
    return run(root, f"{INSTALLED}/scripts/{name}.py", "--rag", str(REPO), *args)


def check(root: Path, *args: str) -> tuple[int, str]:
    return tool(root, "check_project", *args)


def install(root: Path, *args: str) -> tuple[int, str]:
    return run(root, SKILL / "scripts" / "install.py", *args)


def new_project(root: Path) -> Path:
    """What the editor leaves after "Save as project folder", reduced to the keys the generator reads."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "project.c3proj").write_text(json.dumps({"uniqueId": "test", "properties": {}}), encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    root = new_project(tmp_path_factory.mktemp("coins"))
    code, out = install(root)
    assert code == 0, out
    (root / "tools").mkdir()
    shutil.copy(SKILL / "assets" / "build_project.py", root / "tools" / "build_project.py")
    code, out = run(root, "tools/build_project.py")
    assert code == 0, out
    assert out.splitlines()[0] == "generated; checking" and out.splitlines()[-1].startswith("ok:")
    return root


@pytest.fixture
def project(built, tmp_path) -> Path:
    root = tmp_path / "game"
    shutil.copytree(built, root)
    return root


def edit(root: Path, rel: str, change) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8")


def cond(ace_id: str, obj: str = "System", params: dict | None = None, **extra) -> dict:
    return {"id": ace_id, "objectClass": obj, "sid": 1, **({"parameters": params} if params else {}), **extra}


def block(conditions: list, actions: list | None = None, children: list | None = None) -> dict:
    return {"eventType": "block", "conditions": conditions, "actions": actions or [], "sid": 2,
            **({"children": children} if children else {})}


def events(sheet: dict) -> dict:
    """The stand-in sheet by role, so a test reads as what it breaks."""
    rows = sheet["events"]
    groups = {e["title"]: e for e in rows if e["eventType"] == "group"}

    def first_block(group):    # the comment above it is the group's first child
        return next(e for e in group["children"] if e["eventType"] == "block")
    return {
        "setup": first_block(groups["Setup"]),
        "loop": first_block(groups["Setup"])["children"][0],
        "input_group": groups["Input"],
        "input": first_block(groups["Input"]),
        "restart": groups["Restart"],
        "restart_block": first_block(groups["Restart"]),
        "collect": next(e for e in rows if e["eventType"] == "custom-ace-block"),
        "add_score": next(e for e in rows if e["eventType"] == "function-block"),
    }


def findings(root: Path, change, rel: str = SHEET) -> str:
    edit(root, rel, change)
    code, out = check(root)
    assert "Traceback" not in out, out
    return out


# --- the skill as the Agent Skills format defines it (https://agentskills.io/specification) -----
def frontmatter() -> dict[str, str]:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return dict(re.findall(r"^([a-z-]+): (.+)$", text.split("---\n")[1], re.M))


def test_skill_name_and_description_meet_the_specification():
    fields = frontmatter()
    assert fields["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]) and len(fields["name"]) <= 64
    assert 0 < len(fields["description"]) <= 1024
    assert len(fields["compatibility"]) <= 500
    # a plain scalar ends at ": " or " #"; a client with a strict YAML parser would drop the skill
    assert not re.search(r": | #", fields["description"] + fields["compatibility"])


def test_skill_body_stays_within_what_is_loaded_on_activation():
    assert len((SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()) < 500


def test_skill_md_reads_under_any_locale_codec():
    """skills-ref and plain clients read SKILL.md without naming an encoding; under cp936 a UTF-8 sign does not decode."""
    (SKILL / "SKILL.md").read_bytes().decode("ascii")


def test_every_file_the_skill_names_is_in_it():
    for doc in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
        # a path of the clone, Construct3-RAG/prompts/references/..., is not one of the skill's own
        for rel in set(re.findall(r"(?<![\w/])((?:scripts|references|assets)/[\w.-]+\.\w+)", doc.read_text(encoding="utf-8"))):
            assert (SKILL / rel).is_file(), f"{doc.name} names {rel}"


def test_every_file_of_the_clone_the_skill_names_exists():
    """A copy of the skill reaches these through the project's Construct3-RAG line; a rename here breaks them in silence."""
    for doc in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
        for rel in set(re.findall(r"Construct3-RAG/([\w./-]+\.\w+)", doc.read_text(encoding="utf-8"))):
            assert (REPO / rel).is_file(), f"{doc.name} names Construct3-RAG/{rel}"


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
    assert "`.claude/skills/construct3-project/SKILL.md`" in (root / "AGENTS.md").read_text(encoding="utf-8")
    (root / "tools").mkdir()
    shutil.copy(SKILL / "assets" / "build_project.py", root / "tools" / "build_project.py")
    code, out = run(root, "tools/build_project.py")     # the generator finds the checker there too
    assert code == 0 and out.rstrip().splitlines()[-1].startswith("ok:"), out


def test_install_without_the_block_says_how_the_scripts_find_the_clone(tmp_path):
    root = new_project(tmp_path / "game")
    code, out = install(root, "--no-block")
    assert code == 0 and not (root / "AGENTS.md").exists()
    assert f"CONSTRUCT3_RAG={REPO.as_posix()}" in out and "--rag" in out
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
    """The empty project as its repository holds it, reduced to the keys the checker reads."""
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
    assert out.count("would run git clone") == 4 and "--depth 1 https://github.com/Scirra/Construct-Example-Projects" in out
    assert not (tmp_path / "GitHub").exists() and not (tmp_path / "MyGame").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_bootstrap_clones_the_template_repository_beside_the_clone(tmp_path):
    source = template(tmp_path / "src" / "Construct3-New-Project")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], cwd=source, check=True)
    subprocess.run([*git, "add", "."], cwd=source, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "empty project"], cwd=source, check=True)
    beside = siblings(tmp_path / "GitHub")
    code, out = bootstrap(tmp_path, "--beside", str(beside), "--template", source.as_uri(),
                          "--project", str(tmp_path / "MyGame"))
    assert code == 0, out
    assert (beside / "Construct3-New-Project" / "project.c3proj").is_file()
    assert (tmp_path / "MyGame" / "project.c3proj").is_file() and not (tmp_path / "MyGame" / ".git").exists()


def test_a_copy_that_differs_from_the_clone_says_how_to_refresh_it(project):
    script = project / INSTALLED / "scripts" / "print_sheet.py"
    script.write_text(script.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    code, out = check(project)
    assert code == 0 and "warning: this copy of the construct3-project skill differs from the clone's" in out
    assert "scripts/print_sheet.py" in out and "install.py" in out
    # the installed copy hands over to the clone's install.py, which restores the file
    code, out = run(project, f"{INSTALLED}/scripts/install.py")
    assert code == 0 and "wrote scripts/print_sheet.py" in out, out
    code, out = check(project)
    assert "differs from the clone's" not in out


# --- the trigger evaluation of the description, against a stand-in for the client -------------
FAKE_CLIENT = '''
import json, sys
query = sys.argv[sys.argv.index("-p") + 1]
def say(event): print(json.dumps(event), flush=True)
def tool(name, **given): say({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": given}]}})
if "signed out" in query:
    say({"type": "result", "is_error": True, "result": "Failed to authenticate: OAuth session expired"})
elif "silent" in query:
    print("not json")
elif "event sheet" in query:
    tool("Glob", pattern="**/*.json")
    tool("Skill", skill="construct3-project")
elif "reads it" in query:
    tool("Read", file_path="C:\\\\game\\\\.claude\\\\skills\\\\construct3-project\\\\SKILL.md")
else:
    tool("Bash", command="ls")
    say({"type": "result", "is_error": False, "result": "done"})
'''


def trigger_eval(tmp_path: Path, queries: list[dict]) -> tuple[int, str, Path]:
    root = new_project(tmp_path / "game")
    code, out = install(root, "--into", ".claude/skills", "--no-block")
    assert code == 0, out
    (tmp_path / "client.py").write_text(FAKE_CLIENT, encoding="utf-8")
    (tmp_path / "queries.json").write_text(json.dumps(queries), encoding="utf-8")
    report = tmp_path / "report.json"
    code, out = run(tmp_path, SKILL / "evals" / "run_trigger_eval.py", "queries.json", "--project", str(root),
                    "--client", f"{Path(sys.executable).as_posix()} {(tmp_path / 'client.py').as_posix()}",
                    "--runs", "2", "--output", str(report))
    return code, out, report


def test_trigger_eval_counts_a_skill_call_and_a_read_of_skill_md(tmp_path):
    code, out, report = trigger_eval(tmp_path, [
        {"query": "fix my event sheet", "should_trigger": True},
        {"query": "the agent reads it", "should_trigger": True},
        {"query": "zip the folder", "should_trigger": False},
        {"query": "zip the folder, which should have triggered", "should_trigger": True}])
    assert code == 1, out
    results = json.loads(report.read_text(encoding="utf-8"))
    assert [r["trigger_rate"] for r in results["results"]] == [1.0, 1.0, 0.0, 0.0]
    assert [r["pass"] for r in results["results"]] == [True, True, True, False] and results["passed"] == 3


@pytest.mark.parametrize("query, said", [("signed out", "Failed to authenticate"), ("silent", "no assistant or result event")])
def test_trigger_eval_writes_nothing_when_the_client_cannot_answer(tmp_path, query, said):
    """A client that is signed out has not declined to trigger: no rate of 0 is recorded for it."""
    code, out, report = trigger_eval(tmp_path, [{"query": query, "should_trigger": True}])
    assert code == 2 and "no result written" in out and said in out
    assert not report.exists()


# --- the generated project ----------------------------------------------------------
def test_stand_in_project_passes_without_warnings(built):
    code, out = check(built)
    assert code == 0, out
    assert out.startswith("ok:") or "\nok:" in out
    assert [line for line in out.splitlines() if line.startswith("warning:") and "Pillow" not in line] == []


def test_checker_prints_the_findings_that_fit_and_counts_the_rest(project):
    def misspell_every_action(sheet):
        def walk(rows):
            for ev in rows:
                for action in ev.get("actions", []):
                    if "id" in action:
                        action["id"] += "-x"
                walk(ev.get("children", []))
        walk(sheet["events"])
    edit(project, SHEET, misspell_every_action)
    code, out = check(project, "--limit", "600")
    lines = out.splitlines()
    assert code == 1 and re.fullmatch(r"\d+ problem\(s\)", lines[-1])
    assert re.fullmatch(r"\.\.\. and \d+ more problems; fix these and run again \(--limit 0 prints all\)", lines[-2])
    code, everything = check(project, "--limit", "0")
    assert code == 1 and "more problems" not in everything and len(everything) > len(out)


def test_generator_exits_with_the_checkers_findings(project):
    """One command builds and checks, so a finding cannot be skipped by forgetting the second."""
    source = project / "tools" / "build_project.py"
    source.write_text(source.read_text(encoding="utf-8").replace(
        'return cond("on-touched-object", "Touch", {"object": obj, "type": "start"})',
        'return cond("on-touched-object", "Touch", {"object": obj, "type": "\\"start\\""})'), encoding="utf-8")
    code, out = run(project, "tools/build_project.py")
    assert code == 1
    assert "generated; checking" in out and 'write it bare, "start"' in out


def test_generator_without_the_skill_says_so(project):
    shutil.rmtree(project / INSTALLED)
    code, out = run(project, "tools/build_project.py")
    assert code != 0 and "generated, not checked" in out and "install.py" in out


def test_outline_numbers_events_as_the_editor_does(built):
    code, out = tool(built, "print_sheet", "--outline", "Game")
    rows = [line.split("[sid")[0].rstrip() for line in out.splitlines()]
    assert code == 0
    assert rows[:4] == ["== Game", "   (1) // Coins. Tap a coin to collect it; when the last one is gone the layout restarts.",
                        "   (1) // Settings.", "   (1) number COIN_COUNT = 6"]
    assert "   1 group Setup" in rows and "   2   System:on-start-of-layout" in rows


def test_print_words_the_sheet_as_the_editor_does(built):
    code, out = tool(built, "print_sheet", "Game")
    assert code == 0
    assert "   5   Touch: On touched Coin (start)\n           -> Coin: Collect()" in out
    assert "     global constant number COIN_COUNT = 6" in out
    assert "   7 function AddScore(points: number)\n         -> System: Add points to score" in out
    assert "   9   System: Coin.Count = 0\n       System: Trigger once" in out


def test_print_follows_the_locale(built):
    code, out = tool(built, "print_sheet", "Game", "--locale", "zh-CN")
    assert code == 0 and "System: 场景开始" in out


def test_expression_names_are_english_in_every_locale(built):
    """A project file holds `Coin.Count` whatever language the editor runs in; the locale's name is wording."""
    code, out = check(built, "--locale", "zh-CN")
    assert code == 0 and out.splitlines()[-1].startswith("ok:"), out
    code, out = tool(built, "lookup_ace", "Coin", "tween", "progress", "--locale", "zh-CN")
    assert code == 0 and "  write: Coin.Tween.Progress(tags)  -> number" in out, out


def test_print_stops_at_the_limit_and_names_the_part_that_continues(built):
    """A harness cuts long output without saying where; the script stops at an event and says how to go on."""
    code, whole = tool(built, "print_sheet", "Game")
    parts, events = [], "1-"
    while events:
        code, out = tool(built, "print_sheet", "Game", "--events", events, "--limit", "900")
        assert code == 0 and len(out) < 1500, out
        parts.append(out)
        last = out.splitlines()[-1]
        events = re.search(r"--events (\d+-)", last).group(1) if last.startswith("-- stopped at the limit") else None
    assert len(parts) > 1 and parts[0].startswith("== Game: events 1-")
    printed = {line for part in parts for line in part.splitlines() if "[context]" not in line}
    assert [line for line in whole.splitlines()[1:] if line not in printed] == []


def test_print_of_a_part_starts_with_the_events_it_sits_in(built):
    code, out = tool(built, "print_sheet", "Game", "--events", "9")
    assert code == 0
    assert out.splitlines()[:4] == ["== Game: events 9-9 of 9; a [context] row is an event these sit in, without its actions",
                                    "   8 group Restart  [context]", "       // Restart when the last coin is gone.",
                                    "   9   System: Coin.Count = 0"]
    assert "Touch: On touched" not in out


@pytest.mark.parametrize("events, said", [("40-", "has 9 events"), ("x", "40-80, 40- or 40"), ("5-2", "ends before it starts")])
def test_print_refuses_a_range_it_cannot_read(built, events, said):
    code, out = tool(built, "print_sheet", "Game", "--events", events)
    assert code == 1 and said in out


def test_print_without_a_name_lists_the_sheets_that_do_not_fit(project):
    shutil.copy(project / SHEET, project / "eventSheets" / "Menu.json")
    edit(project, "project.c3proj", lambda data: data["eventSheets"]["items"].append("Menu"))
    code, out = tool(project, "print_sheet", "--limit", "900")
    assert code == 0
    assert "2 event sheets" in out and re.search(r"Game +9 events +\d+ characters", out) and "-> " not in out
    code, out = tool(project, "print_sheet")
    assert code == 0 and "== Game\n" in out and "== Menu\n" in out


def test_scripts_write_utf8_and_survive_a_code_page_that_cannot(built):
    """A piped Python on Windows writes the ANSI code page: mojibake under cp936, a crash under cp1252."""
    script = built / INSTALLED / "scripts" / "print_sheet.py"
    for codec, want in ((None, "场景开始"), ("cp1252", "System: ")):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        env.update({"PYTHONIOENCODING": codec} if codec else {})
        p = subprocess.run([sys.executable, str(script), "Game", "--locale", "zh-CN", "--rag", str(REPO)],
                           cwd=built, env=env, capture_output=True)
        assert p.returncode == 0, p.stdout + p.stderr
        assert want in p.stdout.decode(codec or "utf-8")


# --- looking an ACE up -------------------------------------------------------------------
def test_ace_lookup_reaches_a_behavior_through_the_object(built):
    code, out = tool(built, "lookup_ace", "Coin", "tween", "two")
    assert code == 0
    assert "action tween-two-properties - Tween (two properties) [behavior Tween, tween]  <isAsync>" in out
    assert '"objectClass": "Coin", "behaviorType": "Tween", "sid": <new sid>, "parameters": {"tags": "\\"\\"", "property": "position"' in out
    assert "property               combo      position | size | scale" in out


def test_ace_lookup_marks_shared_triggers_and_writes_expressions(built):
    code, out = tool(built, "lookup_ace", "Coin", "collision", "another")
    assert "condition on-collision-with-another-object - On collision with another object [_common]  <isTrigger>" in out
    code, out = tool(built, "lookup_ace", "Coin", "progress")
    assert "write: Coin.Tween.Progress(tags)  -> number" in out


def test_ace_lookup_words_may_name_the_behavior_and_the_kind(built):
    code, out = tool(built, "lookup_ace", "Coin", "tween", "condition", "playing")
    assert code == 0
    assert [line.split(" - ")[0] for line in out.splitlines() if " - " in line and not line.startswith(" ")] == [
        "condition is-playing", "condition is-any-playing"]


def test_ace_lookup_lists_briefly_when_many_match(built):
    code, out = tool(built, "lookup_ace", "System", "layer")
    assert code == 0 and "add a word to narrow them" in out and "write:" not in out


def test_ace_lookup_needs_no_project_and_takes_a_display_name(tmp_path):
    shutil.copytree(SKILL, tmp_path / INSTALLED, ignore=shutil.ignore_patterns("__pycache__"))
    code, out = tool(tmp_path, "lookup_ace", "8 Direction", "max", "speed")
    assert code == 0, out
    assert "action set-max-speed" in out and "[behavior <behavior name on the object>, eightdir]" in out


def test_ace_lookup_offers_the_nearest_id(built):
    code, out = tool(built, "lookup_ace", "System", "wiat")
    assert code != 0 and "closest: wait" in out


def test_ace_lookup_does_not_take_a_near_name_for_the_addon(tmp_path):
    """`Platform` is the behavior; a near match used to read it as the plugin Platform Info."""
    shutil.copytree(SKILL, tmp_path / INSTALLED, ignore=shutil.ignore_patterns("__pycache__"))
    code, out = tool(tmp_path, "lookup_ace", "Platform", "jump", "strength")
    assert code == 0 and "action set-jump-strength" in out and "platforminfo" not in out
    code, out = tool(tmp_path, "lookup_ace", "Platfrom")
    assert code == 1 and "closest: platform" in out


def test_ace_lookup_takes_a_category_for_a_word(built):
    """The word an agent thinks of is the category more often than the id: time, not every-x-seconds."""
    code, out = tool(built, "lookup_ace", "System", "time")
    assert code == 0 and "condition  every-x-seconds " in out and "action     wait " in out
    code, out = tool(built, "lookup_ace", "System", "time", "condition")
    assert "condition compare-time - Compare time" in out and "by category, not by name: every-x-seconds" in out
    code, out = tool(built, "lookup_ace", "System", "timer")
    assert code == 1 and "categories, each a word too:" in out and " time," in out


def test_ace_lookup_by_name_is_not_widened_by_a_category(tmp_path):
    shutil.copytree(SKILL, tmp_path / INSTALLED, ignore=shutil.ignore_patterns("__pycache__"))
    code, out = tool(tmp_path, "lookup_ace", "Physics", "force")
    assert code == 0 and out.count("  write: ") == 3
    assert "by category, not by name: apply-impulse" in out


def test_ace_lookup_lists_the_entries_that_have_some_of_the_words(built):
    code, out = tool(built, "lookup_ace", "Coin", "tween", "position")
    assert code == 1 and "nothing under Coin has every word of 'tween position'" in out
    assert "action     set-position " in out and "[behavior Tween, tween]" in out


def test_ace_lookup_counts_per_category_what_does_not_fit(built):
    code, out = tool(built, "lookup_ace", "System")
    assert code == 0 and len(out) < 2000
    assert "Entries per category:" in out and "loops 5" in out and "add a word" in out
    code, out = tool(built, "lookup_ace", "System", "--limit", "0")
    assert code == 0 and "expression dt " in out


# --- changing a sheet from a plan ---------------------------------------------------------------
def plan(root: Path, *operations: dict, flags: tuple[str, ...] = ()) -> tuple[int, str]:
    (root / "plan.json").write_text(json.dumps(list(operations)), encoding="utf-8")
    return tool(root, "edit_sheet", "Game", "plan.json", *flags)


def printed(root: Path) -> str:
    return tool(root, "print_sheet", "Game")[1]


def all_events(root: Path) -> list[dict]:
    def walk(rows):
        for ev in rows:
            yield ev
            yield from walk(ev.get("children", []))
    return list(walk(json.loads((root / SHEET).read_text(encoding="utf-8"))["events"]))


SET_TIME = {"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": '"Time: " & timeLeft'}}
TIMER = {"eventType": "group", "title": "Timer", "children": [{"eventType": "comment", "text": "Count down."}, {
    "eventType": "block",
    "conditions": [{"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "1"}}],
    "actions": [{"id": "subtract-from-eventvar", "objectClass": "System", "parameters": {"variable": "timeLeft", "value": "1"}}]}]}


def test_plan_puts_events_in_by_the_numbers_the_sheet_has_now(project):
    """Four operations read off one print: the second still means event 2 after the first has put a row above it."""
    code, out = plan(project,
                     {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft", "initialValue": 30}]},
                     {"event": 2, "add-actions": [SET_TIME]},
                     {"into": 3, "events": [{"eventType": "block", "conditions": [], "actions": [
                         {"id": "set-scale", "objectClass": "Coin", "parameters": {"scale": "1.5"}}]}]},
                     {"after": 8, "events": [{"eventType": "comment", "text": "Countdown."}, TIMER]})
    assert code == 0, out
    assert out.splitlines()[0] == "Game: 4 operations, 9 events before and 12 now, 8 new sids"
    assert out.splitlines()[-1].startswith("ok:")
    sheet = printed(project)
    assert "     global number score = 0\n     global number timeLeft = 30\n   1 group Setup" in sheet
    assert '-> ScoreText: Set text to "Score: 0"\n           -> ScoreText: Set text to "Time: " & timeLeft' in sheet
    assert "   4       (every tick)\n               -> Coin: Set scale to 1.5" in sheet
    assert "     // Countdown.\n  11 group Timer\n       // Count down.\n  12   System: Every 1 seconds" in sheet
    assert check(project)[0] == 0


def test_plan_writes_what_the_editor_writes(project):
    """Keys the editor always writes are filled in, in its order, every new entry has a sid, and the file is tabs and LF."""
    assert plan(project, {"into": 0, "events": [{"eventType": "variable", "name": "lives"}, TIMER]})[0] != 0   # timeLeft is not declared
    code, out = plan(project, {"into": 0, "events": [{"eventType": "variable", "name": "timeLeft", "type": "number"}, TIMER]})
    assert code == 0, out
    events = all_events(project)
    variable = next(ev for ev in events if ev.get("name") == "timeLeft")
    assert list(variable) == ["eventType", "name", "type", "initialValue", "comment", "isStatic", "isConstant", "sid"]
    assert (variable["initialValue"], variable["isConstant"]) == ("0", False)
    group = next(ev for ev in events if ev.get("title") == "Timer")
    assert list(group) == ["eventType", "disabled", "title", "description", "isActiveOnStart", "children", "sid"]
    condition = next(e for e in group["children"] if e["eventType"] == "block")["conditions"][0]
    assert list(condition) == ["id", "objectClass", "sid", "parameters"] and len(str(condition["sid"])) == 15
    raw = (project / SHEET).read_bytes()
    assert b"\r" not in raw and not raw.endswith(b"\n") and b'\n\t\t{\n\t\t\t"eventType"' in raw


def test_plan_that_adds_a_problem_changes_nothing(project):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"after": 8, "events": [TIMER]},
                     {"event": 7, "add-actions": [{"id": "set-txt", "objectClass": "ScoreText", "parameters": {"text": '"x"'}}]})
    assert code == 1 and (project / SHEET).read_bytes() == before
    assert "operation 1: sheet Game event" in out and "timeLeft" in out
    assert "operation 2: sheet Game event 7" in out and "closest: set-text" in out
    assert out.splitlines()[-1] == "the plan adds 2 problem(s) to the project; nothing was written"


def test_a_problem_that_was_there_does_not_stop_a_plan(project):
    edit(project, SHEET, lambda sheet: events(sheet)["add_score"]["actions"][1].update(id="set-txt"))
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]})
    assert code == 0, out
    assert "1 problem(s) were in the project before this plan and still are" in out.splitlines()[-1]
    assert "global number timeLeft = 0" in printed(project)


def test_a_finding_names_the_place_a_plan_changes(project):
    """The five mistakes of the eval's broken sheet, repaired by the places the checker gives for them."""
    sys.path.insert(0, str(SKILL / "evals"))
    try:
        from make_fixtures import seed_load_errors
    finally:
        sys.path.pop(0)
    seed_load_errors(project)
    code, out = check(project)
    assert code == 1 and re.search(r"event 2 \(sid \d+\) condition 1: System:on-start-of-layout is inverted", out)
    assert re.search(r"event 5 \(sid \d+\) condition 1 Touch:on-touched-object", out)
    code, out = plan(project,
                     {"event": 2, "condition": 1, "set": {"isInverted": False}},
                     {"event": 5, "condition": 1, "set": {"parameters": {"type": "start"}}},
                     {"event": 6, "action": 1, "set": {"behaviorType": "Tween"}},
                     {"event": 8, "action": 2, "set": {"id": "set-text"}},
                     {"move": 7, "after": 6})
    assert code == 0 and out.splitlines()[-1].startswith("ok:"), out
    sheet = events(json.loads((project / SHEET).read_text(encoding="utf-8")))
    assert "isInverted" not in sheet["setup"]["conditions"][0], "the editor writes isInverted only when it is true"
    assert list(sheet["collect"]["actions"][0])[:4] == ["id", "objectClass", "sid", "behaviorType"]
    assert "Coin: On Tween \"collect\" finished\n         -> Functions: Call AddScore(Coin.value)" in printed(project)


def test_plan_sets_the_values_of_an_event_and_removes_an_action(project):
    code, out = plan(project, {"event": 8, "set": {"title": "Over", "isActiveOnStart": False}},
                     {"event": 9, "action": 1, "remove": True})
    assert code == 0, out
    sheet = printed(project)
    assert "   8 group Over (inactive on start)" in sheet and "Wait 1 seconds" not in sheet
    code, out = plan(project, {"event": 9, "set": {"actions": []}})
    assert code == 1 and "\"set\" changes values, not 'actions'" in out


def test_set_takes_no_key_of_the_plans_own_making(project):
    """Two eval runs wrote {"event": 2, "set": {"inverted": false}}: the key stayed in the sheet and changed nothing."""
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"event": 2, "set": {"inverted": False}})
    assert code == 1 and "'inverted' is not a value of a block, which has: disabled, isOrBlock" in out
    assert '{"event": N, "condition": 1, "set": {"isInverted": null}}' in out
    code, out = plan(project, {"event": 2, "condition": 1, "set": {"inverted": False}})
    assert code == 1 and "is not a value of a condition or action" in out and "closest: isInverted" in out
    code, out = plan(project, {"event": 1, "add-events": [TIMER]})
    assert code == 1 and 'sub-events go into an event with {"into": 1, "events": [...]}' in out
    assert (project / SHEET).read_bytes() == before


def test_plan_moves_replaces_and_removes(project):
    code, out = tool(project, "print_sheet", "Game", "--show", "9")
    restart = json.loads(out)
    assert code == 0 and [c["id"] for c in restart["conditions"]] == ["compare-two-values", "trigger-once-while-true"]
    restart["actions"] = restart["actions"][1:]                                 # no wait before the restart
    sids = {c["sid"] for c in restart["conditions"]}
    code, out = plan(project, {"replace": 9, "events": [restart]}, {"move": 7, "before": 6}, {"remove": 4})
    assert code == 0, out
    sheet = printed(project)
    assert sheet.index("function AddScore") < sheet.index("custom action Coin.Collect") and "group Input" not in sheet
    assert "System: Trigger once\n           -> System: Restart layout" in sheet
    assert sids <= {c.get("sid") for ev in all_events(project) for c in ev.get("conditions", [])}, "a replaced event keeps the sids it is given"


def test_an_event_replaced_by_one_without_a_sid_keeps_its_own(project):
    was = events(json.loads((project / SHEET).read_text(encoding="utf-8")))["restart_block"]["sid"]
    code, out = plan(project, {"replace": 9, "events": [{"eventType": "block", "conditions": [], "actions": [
        {"id": "restart-layout", "objectClass": "System"}]}]})
    assert code == 0, out
    assert events(json.loads((project / SHEET).read_text(encoding="utf-8")))["restart_block"]["sid"] == was


def test_an_event_replaced_by_one_keeps_its_number_for_the_operations_below(project):
    wait = {"eventType": "block", "conditions": [{"id": "every-tick", "objectClass": "System"}], "actions": []}
    code, out = plan(project, {"replace": 9, "events": [wait]},
                     {"event": 9, "add-actions": [{"id": "restart-layout", "objectClass": "System"}]},
                     {"after": 9, "events": [{"eventType": "comment", "text": "Below the restart."}]})
    assert code == 0, out
    assert "   9   System: Every tick\n           -> System: Restart layout\n       // Below the restart." in printed(project)


@pytest.mark.parametrize("operations, said", [
    (({"replace": 8, "events": [{"eventType": "group", "title": "Restart"}]}, {"event": 9, "set": {"disabled": True}}),
     "operation 2 (event 9): event 9 is gone, operation 1 replaced event 8, which held it"),
    (({"remove": 7}, {"after": 7, "events": [{"eventType": "comment", "text": "Score."}]}),
     "operation 2 (after 7): event 7 is gone, operation 1 removed it"),
])
def test_an_event_that_is_gone_names_the_operation_that_took_it(project, operations, said):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, *operations)
    assert code == 1 and said in out and '"move" takes it out first' in out, out
    assert (project / SHEET).read_bytes() == before


def test_before_an_event_is_above_the_comments_about_it(project):
    assert plan(project, {"before": 9, "events": [{"eventType": "comment", "text": "All coins gone."}]})[0] == 0
    code, out = plan(project, {"before": 9, "events": [{"eventType": "block", "conditions": [], "actions": []}]})
    assert code == 0, out
    assert ("   9   (every tick)\n       // All coins gone.\n       // Restart when the last coin is gone.\n"
            "  10   System: Coin.Count = 0") in printed(project)


def test_a_sid_the_project_uses_is_replaced(project):
    taken = events(json.loads((project / SHEET).read_text(encoding="utf-8")))["restart"]["sid"]
    code, out = plan(project, {"into": 0, "events": [{"eventType": "block", "conditions": [], "actions": [], "sid": taken}]})
    assert code == 0 and "1 new sids" in out.splitlines()[0]
    sids = [ev["sid"] for ev in all_events(project) if "sid" in ev]
    assert len(sids) == len(set(sids))


def test_dry_run_checks_and_shows_and_writes_nothing(project):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]}, flags=("--dry-run",))
    assert code == 0 and (project / SHEET).read_bytes() == before
    assert "global number timeLeft = 0" in out and out.splitlines()[-1] == "dry run: nothing was written"


@pytest.mark.parametrize("operation, said", [
    ({"after": 40, "events": [TIMER]}, "40 is not an event of the sheet, which has 9"),
    ({"after": 8}, 'needs "events"'),
    ({"after": 8, "before": 2, "events": [TIMER]}, "an operation is one of"),
    ({"after": 8, "event": [TIMER]}, "an operation is one of"),
    ({"after": 8, "events": [{"eventType": "group"}]}, "a group needs 'title'"),
    ({"after": 8, "events": [{"conditions": [], "actions": []}]}, "An event with conditions and actions is a 'block'"),
    ({"event": 2, "add-actions": [{"objectClass": "Coin"}]}, "has no 'id'"),
    ({"event": 1, "add-actions": [SET_TIME]}, "event 1 is a group, which has no actions"),
    ({"event": 2, "add-actions": [SET_TIME], "position": 5}, "position is 1 to 2"),
    ({"into": 5, "events": [{"eventType": "variable", "name": "n", "type": "int"}]}, "'number', 'string' or 'boolean'"),
    ({"move": 1, "into": 3}, "event 3 is event 1 or inside it"),
])
def test_a_plan_that_cannot_be_read_says_what_an_operation_is(project, operation, said):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, operation)
    assert code == 1 and said in out and "nothing was written" in out and "Traceback" not in out
    assert (project / SHEET).read_bytes() == before


def test_the_plan_skill_md_shows_is_one_the_script_takes(project):
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    shown = text.split("## Change a sheet with a plan")[1].split("```json\n")[1].split("```")[0]
    (project / "plan.json").write_text(shown, encoding="utf-8")
    code, out = tool(project, "edit_sheet", "Game", "plan.json")
    assert code == 0 and out.splitlines()[-1].startswith("ok:"), out


def test_new_sid_left_in_a_plan_is_named(project):
    (project / "plan.json").write_text('[{"event": 2, "add-actions": [{"id": "x", "objectClass": "Coin", "sid": <new sid>}]}]',
                                       encoding="utf-8")
    code, out = tool(project, "edit_sheet", "Game", "plan.json")
    assert code == 1 and 'leave "sid" out' in out


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


# --- triggers ------------------------------------------------------------------------------
def test_two_triggers_in_one_event(project):
    out = findings(project, lambda s: events(s)["input"]["conditions"].append(cond("on-start-of-layout")))
    assert "are two triggers in one event" in out and "event 5" in out


def test_trigger_below_a_trigger(project):
    out = findings(project, lambda s: events(s)["input"].update(children=[block([cond("on-start-of-layout")])]))
    assert "System:on-start-of-layout is a trigger inside an event that already has the trigger Touch:on-touched-object" in out
    assert "cannot add another trigger to event branch" in out


def test_on_timer_and_on_collision_count_as_triggers(project):
    """Fake triggers in the CDN's terms; the editor holds them to the same rule."""
    def change(s):
        events(s)["input"]["conditions"].append(
            cond("on-collision-with-another-object", "Coin", {"object": "Coin"}))
    assert "are two triggers in one event" in findings(project, change)


@pytest.mark.parametrize("role, holder", [("add_score", "the function AddScore"), ("collect", "the custom action Collect")])
def test_trigger_inside_a_function_or_custom_action(project, role, holder):
    out = findings(project, lambda s: events(s)[role].update(children=[block([cond("on-start-of-layout")])]))
    assert f"is a trigger inside {holder}, which counts as a trigger" in out


def test_or_block_may_list_several_triggers(project):
    def change(s):
        events(s)["input"]["conditions"].append(cond("on-start-of-layout"))
        events(s)["input"]["isOrBlock"] = True
    edit(project, SHEET, change)
    code, out = check(project)
    assert code == 0, out


@pytest.mark.parametrize("role, what", [("input", "a trigger"), ("loop", "a loop")])
def test_trigger_and_loop_cannot_be_inverted(project, role, what):
    out = findings(project, lambda s: events(s)[role]["conditions"][0].update(isInverted=True))
    assert f"is inverted, and {what} cannot be" in out and "condition not invertible" in out


@pytest.mark.parametrize("place", [
    lambda s: events(s)["input"]["conditions"].append(cond("trigger-once-while-true")),
    lambda s: events(s)["input"].update(children=[block([cond("trigger-once-while-true")])]),
])
def test_trigger_once_in_a_triggered_branch_is_a_warning(project, place):
    """Official examples do it, so it opens; the editor's own dialog no longer offers it."""
    out = findings(project, place)
    assert "System:trigger-once-while-true is in a branch run by the trigger Touch:on-touched-object" in out
    assert out.rstrip().splitlines()[-1].startswith("ok:")


def test_every_x_seconds_inside_a_function_is_not_flagged(project):
    """A function called every tick is an ordinary place for it (official example tank-movement)."""
    def change(s):
        events(s)["add_score"].update(children=[block([cond("every-x-seconds", params={"interval-seconds": "1"})])])
    assert "warning:" not in findings(project, change)


# --- Else ----------------------------------------------------------------------------------------
def test_else_after_a_plain_event_is_valid(project):
    edit(project, SHEET, lambda s: events(s)["restart"]["children"].append(block([cond("else")])))
    code, out = check(project)
    assert code == 0, out


@pytest.mark.parametrize("place, reason", [
    (lambda s: events(s)["restart"]["children"].insert(0, block([cond("else")])), "it is the first event of its list"),
    (lambda s: events(s)["input_group"]["children"].append(block([cond("else")])), "it follows a triggered event"),
    (lambda s: events(s)["setup"]["children"].append(block([cond("else")])), "it follows a loop"),
    (lambda s: events(s)["restart"]["children"].append(block([cond("every-tick"), cond("else")])),
     "it is not the first condition of its event"),
])
def test_else_where_the_editor_refuses_to_preview(project, place, reason):
    out = findings(project, place)
    assert "Else cannot stand here, " + reason in out


# --- parameters --------------------------------------------------------------------------------
def add_keyboard(root: Path, key) -> None:
    (root / "objectTypes" / "Keyboard.json").write_text(json.dumps({
        "name": "Keyboard", "plugin-id": "Keyboard", "sid": 3,
        "singleglobal-inst": {"type": "Keyboard", "properties": {}, "uid": 900, "sid": 4, "tags": ""}}), encoding="utf-8")

    def project_file(p):
        p["objectTypes"]["items"].append("Keyboard")
        p["usedAddons"].append({"type": "plugin", "id": "Keyboard", "name": "Keyboard", "author": "Scirra", "bundled": False})
    edit(root, "project.c3proj", project_file)
    edit(root, SHEET, lambda s: s["events"].append(block([cond("on-key-pressed", "Keyboard", {"key": key})])))


def test_key_is_a_key_code(project):
    add_keyboard(project, 32)
    assert check(project)[0] == 0


def test_key_written_as_a_name(project):
    add_keyboard(project, "Space")
    code, out = check(project)
    assert code == 1 and "should be a key code" in out and "expected finite number" in out


def test_action_cannot_write_a_constant(project):
    def change(s):
        events(s)["add_score"]["actions"].append(
            {"id": "set-eventvar-value", "objectClass": "System", "sid": 5,
             "parameters": {"variable": "COIN_COUNT", "value": "3"}})
    assert "COIN_COUNT is a constant and an action cannot change it" in findings(project, change)


def test_self_in_a_system_parameter_names_the_object_to_write(project):
    """Self is the object of the condition or action; in a System one it is nothing (editor: Invalid use of 'self')."""
    def change(s):
        events(s)["restart"]["children"].append(
            block([cond("for-each-ordered", "System", {"object": "Coin", "expression": "Self.value", "order": "ascending"})],
                  [{"id": "set-eventvar-value", "objectClass": "System", "sid": 5,
                    "parameters": {"variable": "score", "value": "score + Self.value"}}]))
    out = findings(project, change)
    assert "condition 1 System:for-each-ordered expression: Self names the object of the condition or action, "            "and here that is System; the editor stops with \"Invalid use of 'self'\"; write 'Coin.value'" in out
    assert "action 1 System:set-eventvar-value value: Self names the object" in out
    assert "name the object instead" in out


def test_self_in_an_objects_own_parameter_passes(project):
    out = findings(project, lambda s: events(s)["collect"]["actions"][0]["parameters"].update(**{"end-x": "Self.X"}))
    assert "Self" not in out, out


def test_ease_is_a_builtin_id(project):
    out = findings(project, lambda s: events(s)["collect"]["actions"][0]["parameters"].update(ease="ease-in-back"))
    assert "ease='ease-in-back' is not a built-in ease; closest: easeinback" in out


# --- messages that say what to write instead ----------------------------------------------
def test_behavior_action_without_behavior_type_names_the_behavior(project):
    out = findings(project, lambda s: events(s)["collect"]["actions"][0].pop("behaviorType"))
    assert 'it belongs to the behavior Tween: add "behaviorType": "Tween"' in out


def test_script_name_in_place_of_the_id(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][0].update(id="SetText"))
    assert "Text has no action SetText" in out and "the id is 'set-text'" in out


def test_misspelt_id_lists_the_nearest(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][0].update(id="set-txt"))
    assert "closest: set-text" in out


def test_unknown_parameter_lists_the_real_ones(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][0]["parameters"].update(value='"x"'))
    assert "unknown parameter value; the parameters are: text" in out


def test_behavior_expression_without_the_behavior_name(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][0]["parameters"].update(text="Coin.Progress"))
    assert "Coin.Progress is neither an expression nor an instance variable of Coin" in out
    assert "it is an expression of a behavior: Coin.Tween.Progress" in out


def test_quoted_combo_value_is_told_to_drop_the_quotes(project):
    """The commonest encoding slip in generated sheets: a combo written like a string expression."""
    out = findings(project, lambda s: events(s)["input"]["conditions"][0]["parameters"].update(type='"start"'))
    assert "type='\"start\"' is not one of" in out
    assert 'write it bare, "start": only an expression parameter carries inner quotes' in out


def test_bare_text_value_is_told_to_add_the_quotes(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][0]["parameters"].update(text="Hello"))
    assert "identifier 'Hello' is not a variable" in out and 'a text value carries inner quotes: "\\"Hello\\""' in out


def test_plugin_name_in_an_expression_names_the_object(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][0]["parameters"].update(text="Sprite.Count"))
    assert "unknown object Sprite in expression; Sprite is the plugin, the object of it here is Coin" in out


# --- addon ids and names ------------------------------------------------------------------------
def test_addon_id_is_case_sensitive(project):
    out = findings(project, lambda t: t.update({"plugin-id": "sprite"}), "objectTypes/Coin.json")
    assert "plugin id 'sprite' must be written 'Sprite'" in out


def test_display_name_in_place_of_the_addon_id(project):
    out = findings(project, lambda t: t.update({"plugin-id": "Array"}), "objectTypes/ScoreText.json")
    assert "plugin id 'Array' does not exist: the editor's id is 'Arr'" in out


def test_third_party_addon_stays_a_warning(project):
    edit(project, "project.c3proj", lambda p: p["usedAddons"].append(
        {"type": "plugin", "id": "Spriter", "name": "Spriter", "author": "BrashMonkey", "bundled": True}))
    out = findings(project, lambda t: t.update({"plugin-id": "Spriter"}), "objectTypes/ScoreText.json")
    assert "warning: no schema for plugin Spriter" in out
    assert out.rstrip().splitlines()[-1].startswith("ok:"), out     # its ACEs pass unchecked


def rename_type(root: Path, old: str, new: str) -> None:
    data = json.loads((root / "objectTypes" / f"{old}.json").read_text(encoding="utf-8"))
    data.update(name=new, sid=7)
    (root / "objectTypes" / f"{new}.json").write_text(json.dumps(data), encoding="utf-8")
    edit(root, "project.c3proj", lambda p: p["objectTypes"]["items"].append(new))


@pytest.mark.parametrize("name, message", [
    ("Floor", "object type Floor: the name is reserved (floor is a keyword or a system expression)"),
    ("Score-Text", "the editor does not keep the object type name 'Score-Text' as written, it becomes 'ScoreText'"),
    ("Hi Score", "it becomes 'HiScore'"),
])
def test_object_names_the_editor_changes_or_refuses(project, name, message):
    rename_type(project, "ScoreText", name)
    assert message in check(project)[1]


def test_file_name_and_inner_name_must_agree(project):
    out = findings(project, lambda t: t.update(name="coin"), "objectTypes/Coin.json")
    assert "object type Coin: the file says \"name\": 'coin'" in out


def test_instance_variable_named_like_an_expression(project):
    def change(t):
        t["instanceVariables"].append({"name": "Angle", "type": "number", "desc": "", "show": True, "sid": 6})
    assert "Coin: instance variable Angle collides with the expression Coin.angle" in findings(
        project, change, "objectTypes/Coin.json")


def test_instance_variable_and_behavior_share_a_name(project):
    def change(t):
        t["instanceVariables"].append({"name": "tween", "type": "number", "desc": "", "show": True, "sid": 6})
    assert "Coin: behavior Tween has the same name as instance variable tween" in findings(
        project, change, "objectTypes/Coin.json")


def test_instance_without_uid_is_reported_not_raised(project):
    out = findings(project, lambda lay: lay["layers"][0]["instances"][0].pop("uid"), "layouts/Objects.json")
    assert "instance of Coin has no integer uid" in out


def test_a_boolean_variable_holds_the_text_true_or_false(project):
    """The editor compares the text to "true", so a JSON boolean or "True" reads as false."""
    def change(sheet):
        sheet["events"].insert(0, {"eventType": "variable", "name": "paused", "type": "boolean", "initialValue": False,
                                   "comment": "", "isStatic": False, "isConstant": False, "sid": 900000000000001})
        sheet["events"].insert(1, {"eventType": "variable", "name": "muted", "type": "boolean", "initialValue": "True",
                                   "comment": "", "isStatic": False, "isConstant": False, "sid": 900000000000002})
    out = findings(project, change)
    assert 'variable paused: initialValue should be the text "true" or "false", not False' in out
    assert 'variable muted: initialValue \'True\' should be "true" or "false", lowercase' in out


def test_a_number_variable_holds_text_and_a_parameter_may_hold_a_number(project):
    def change(sheet):
        events(sheet)["add_score"]["functionParameters"][0]["initialValue"] = 5
        for ev in sheet["events"]:
            if ev.get("eventType") == "variable" and ev["name"] == "score":
                ev["initialValue"] = 0
    out = findings(project, change)
    assert 'variable score: initialValue should be text, "0", not 0' in out
    assert "parameter points" not in out


def test_a_boolean_parameter_written_as_a_json_boolean_is_named(project):
    def change(sheet):
        events(sheet)["add_score"]["functionParameters"].append(
            {"name": "loud", "type": "boolean", "initialValue": True, "comment": "", "sid": 900000000000003})
    out = findings(project, change)
    assert 'parameter loud: initialValue should be the text "true" or "false", not True' in out


def test_an_instance_writes_its_variable_as_a_json_value(project):
    out = findings(project, lambda lay: lay["layers"][0]["instances"][0]["instanceVariables"].update(value="1"),
                   "layouts/Objects.json")
    assert "Coin instance variable value = '1'; a number is written as a number such as 1 here" in out


def test_a_world_angle_beyond_a_full_turn_is_named_as_degrees(project):
    out = findings(project, lambda lay: lay["layers"][0]["instances"][0]["world"].update(angle=270),
                   "layouts/Objects.json")
    assert "Coin world angle 270 is more than a full turn; the file stores radians, 270 degrees is 4.7124" in out


def test_missing_key_stops_with_a_sentence(project):
    def change(s):
        del events(s)["add_score"]["functionParameters"]
    out = findings(project, change)
    assert "check_project.py stopped at check_project.py line" in out
    assert "missing key 'functionParameters'" in out


# --- the data the rules read ---------------------------------------------------------------------
@pytest.mark.parametrize("rel, ace_id", [
    ("plugins/_common.json", "on-collision-with-another-object"),
    ("behaviors/timer.json", "on-timer"),
    ("plugins/gamepad.json", "on-button-pressed"),
    ("plugins/keyboard.json", "on-key-pressed"),
])
def test_committed_schemas_mark_what_the_editor_treats_as_a_trigger(rel, ace_id):
    for locale in ("en-US", "zh-CN"):
        data = json.loads((REPO / "data" / "c3-schemas" / locale / rel).read_text(encoding="utf-8"))
        entry = next(c for c in data["conditions"] if c["id"] == ace_id)
        assert entry.get("isTrigger") is True, (locale, rel, ace_id)


# --- style, with --style: the three habits of small models, as warnings ----------------------------
STYLE_ACTIONS = [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": f'"{i}"'}} for i in range(8)]


def test_stand_in_project_passes_the_style_check(built):
    """The template is the shape the style asks for, so a generated project starts clean."""
    code, out = check(built, "--style")
    assert code == 0, out
    assert [line for line in out.splitlines() if line.startswith("warning:") and "Pillow" not in line] == []


def test_style_findings_come_only_when_asked(project):
    def drop_the_comment_above_input(sheet):
        rows = events(sheet)["input_group"]["children"]
        rows[:] = [r for r in rows if r["eventType"] != "comment"]
    edit(project, SHEET, drop_the_comment_above_input)
    code, out = check(project)
    assert code == 0 and "no comment above it" not in out
    code, out = check(project, "--style")
    assert code == 0 and re.search(r"warning: sheet Game event 5 \(sid \d+\): no comment above it", out), out


def test_style_names_a_long_run_of_actions(project):
    edit(project, SHEET, lambda s: events(s)["setup"]["actions"].extend(STYLE_ACTIONS))
    code, out = check(project, "--style")
    assert code == 0 and "event 2 (sid" in out and "9 actions in a row without a comment action" in out, out
    edit(project, SHEET, lambda s: events(s)["setup"]["actions"].insert(4, {"type": "comment", "text": "Reset the text."}))
    assert "actions in a row" not in check(project, "--style")[1]


def test_style_names_a_tree_of_one_call(project):
    def test(n):
        return cond("compare-two-values", params={"first-value": str(n), "comparison": 0, "second-value": "1"})

    def leaf(n):
        return block([test(n)], [{"callFunction": "AddScore", "parameters": [str(n)]}])
    tree = block([test(1)], [], [block([test(2)], [], [leaf(1), leaf(2)]), block([cond("else")], [], [leaf(3), leaf(4)])])
    fresh = iter(range(900_000_000_000_001, 900_000_000_000_099))

    def own_sids(ev):      # the test helpers give every row sid 1 or 2; the checker wants them distinct
        ev["sid"] = next(fresh)
        for c in ev["conditions"]:
            c["sid"] = next(fresh)
        for k in ev.get("children", []):
            own_sids(k)
    own_sids(tree)
    edit(project, SHEET, lambda s: events(s)["input"].update(children=[tree]))
    code, out = check(project, "--style")
    assert code == 0 and "event 5 (sid" in out and "sub-events 3 levels deep, every leaf calling AddScore" in out, out


def test_plan_refuses_new_events_without_their_comments(project):
    """The user's own uncommented event stays quiet; what the plan adds needs its comment above and,
    past eight actions, a comment action among them, or nothing is written."""
    edit(project, SHEET, lambda s: events(s)["input_group"]["children"].pop(0))
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"into": 0, "events": [{"eventType": "block", "conditions": [], "actions": STYLE_ACTIONS}]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert "operation 1: sheet Game event 10 (sid" in out
    assert "8 actions in a row without a comment action" in out and "no comment above it" in out
    assert "event 5 (sid" not in out and out.splitlines()[-1] == "the plan adds 2 problem(s) to the project; nothing was written"
    stepped = STYLE_ACTIONS[:4] + [{"type": "comment", "text": "Then the rest."}] + STYLE_ACTIONS[4:]
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Show the time."},
                                                    {"eventType": "block", "conditions": [], "actions": stepped}]})
    assert code == 0 and "warning:" not in out and out.splitlines()[-1].startswith("ok:"), out
