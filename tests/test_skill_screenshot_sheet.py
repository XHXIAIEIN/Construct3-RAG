"""screenshot_sheet.py: what it refuses before it starts a browser. Taking the picture needs the
editor online and is checked by running the script on a project, not here."""
from tests.skill_helpers import SKILL, INSTALLED, run, script_module


def test_screenshot_sheet_prints_its_help(project):
    code, out = run(project, f"{INSTALLED}/scripts/screenshot_sheet.py", "--help")
    assert code == 0 and "--group" in out and ".build/sheets" in out and "exit codes:" in out, out


def test_screenshot_sheet_names_the_sheets_when_one_is_misspelled(project):
    code, out = run(project, f"{INSTALLED}/scripts/screenshot_sheet.py", "Gmae")
    assert code == 1 and "no event sheet 'Gmae'" in out and "closest: Game" in out, out


def test_screenshot_sheet_needs_a_project(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out = run(empty, SKILL / "scripts" / "screenshot_sheet.py")
    assert code == 2 and "no project.c3proj" in out, out


def test_screenshot_sheet_keeps_the_picture_inside_the_sheet_view():
    clip = script_module("screenshot_sheet").clip
    view = {"left": 300, "top": 34, "right": 1500}
    assert clip({"left": 300, "top": 34, "right": 1200, "bottom": 600}, view) == \
        {"x": 300, "y": 34, "width": 910, "height": 576, "scale": 1}
    assert clip({"left": 320, "top": 200, "right": 1495, "bottom": 400}, view) == \
        {"x": 310, "y": 190, "width": 1190, "height": 220, "scale": 1}
