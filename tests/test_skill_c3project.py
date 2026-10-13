"""c3project.py: what the skill's scripts share. The one form of every command a script prints for the agent
to run next, from the current directory."""
from tests.skill_helpers import REPO, SKILL, new_project, script_module

c3 = script_module("c3project")
PRINT_SHEET = c3.quoted((SKILL / "scripts" / "print_sheet.py").as_posix())


def test_quoted_quotes_a_word_a_shell_would_split_or_read():
    assert c3.quoted("a b") == '"a b"'
    assert c3.quoted("D:/x/y.py") == "D:/x/y.py"
    assert c3.quoted("D:\\x\\y.py") == "D:\\x\\y.py"
    assert c3.quoted("Game") == "Game" and c3.quoted("eventSheets/Game.json") == "eventSheets/Game.json"
    assert c3.quoted("Game & HUD") == '"Game & HUD"'
    assert c3.quoted(7) == "7"


def test_script_command_names_the_script_and_the_project_from_the_current_directory(project, tmp_path, monkeypatch):
    """From inside the project, the script alone. From the repository root, the script relative to it and
    --project. From a folder in no project, the script absolute and --project, quoted when the root holds
    a space."""
    monkeypatch.chdir(project)
    assert c3.script_command(project, "print_sheet.py") == f"python {PRINT_SHEET}"
    assert c3.script_command(None, "print_sheet.py", " --outline") == f"python {PRINT_SHEET} --outline"
    monkeypatch.chdir(REPO)
    assert c3.script_command(project, "print_sheet.py") == (
        f"python skills/construct3-agent-plugin/scripts/print_sheet.py --project {project.resolve().as_posix()}")
    spaced = new_project(tmp_path / "New folder" / "game")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert c3.script_command(spaced, "print_sheet.py") == (
        f'python {PRINT_SHEET} --project "{spaced.resolve().as_posix()}"')
    assert c3.open_command(spaced).endswith(f' --project "{spaced.resolve().as_posix()}" --preview')
