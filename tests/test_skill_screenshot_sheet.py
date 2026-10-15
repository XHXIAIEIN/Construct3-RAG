"""screenshot_sheet.py without a browser: its help, what it refuses, and the parts that read a sheet and
size a picture. Taking the picture needs the editor online, so a run of the script on a project checks it."""
from tests.skill_helpers import SKILL, INSTALLED, run, script_module

SCRIPT = f"{INSTALLED}/scripts/screenshot_sheet.py"

ss = script_module("screenshot_sheet")


def test_screenshot_sheet_prints_its_help(project):
    code, out = run(project, SCRIPT, "--help")
    assert code == 0 and "--group" in out and ".build/sheets" in out and "exit codes:" in out, out


def test_screenshot_sheet_names_the_sheets_when_one_is_misspelled(project):
    code, out = run(project, SCRIPT, "Gmae")
    assert code == 1 and "no event sheet 'Gmae'" in out and "closest: Game" in out, out


def test_screenshot_sheet_names_the_groups_when_one_is_misspelled(project):
    code, out = run(project, SCRIPT, "Game", "--group", "Restrat")
    assert code == 1 and "no group 'Restrat' in Game; closest: Restart" in out and "Setup, Input, Restart" in out, out


def test_screenshot_sheet_needs_a_project(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out = run(empty, SKILL / "scripts" / "screenshot_sheet.py")
    assert code == 2 and "no project.c3proj" in out, out


def test_screenshot_sheet_keeps_the_picture_inside_the_sheet_view():
    view = {"left": 300, "top": 34, "right": 1500, "bottom": 900}
    assert ss.clip({"left": 300, "top": 34, "right": 1200, "bottom": 600}, view) == \
        {"x": 300, "y": 34, "width": 910, "height": 576, "scale": 1}
    assert ss.clip({"left": 320, "top": 200, "right": 1495, "bottom": 400}, view) == \
        {"x": 310, "y": 190, "width": 1190, "height": 220, "scale": 1}
    assert ss.clip({"left": 320, "top": 200, "right": 1200, "bottom": 895}, view)["height"] == 710


def test_screenshot_sheet_reads_the_groups_and_sids_of_a_sheet():
    events = [{"eventType": "variable", "sid": 1},
              {"eventType": "group", "title": "Combat", "sid": 2, "children": [
                  {"eventType": "block", "sid": 3, "conditions": [{"sid": 4}], "actions": [{"sid": 5}]},
                  {"eventType": "group", "title": "Combat hits", "sid": 6, "children": []}]},
              {"eventType": "group", "title": "Waves", "sid": 7, "children": []}]
    assert ss.group_titles(events) == {None: ["Combat", "Waves"], "Combat": ["Combat hits"],
                                       "Combat hits": [], "Waves": []}
    assert ss.sids(events) == 7


def test_screenshot_sheet_says_what_to_take_instead_of_a_picture_too_tall():
    # at scale 2 a window of 16384 device px holds 8192 CSS px, less the editor's 100 px and PAD above and below
    said = ss.too_tall("the sheet Game", 12000, 2, 16384, 100, ["Setup", "Enemy waves"])
    assert "12000 px tall" in said and "holds 8072 px" in said and "16384 device px" in said, said
    assert said.endswith('Take it at --scale 1, or its groups one at a time: --group Setup --group "Enemy waves"')
    said = ss.too_tall("group Bosses", 20000, 1, 16384, 100, [f"Part {n}" for n in range(10)])
    assert "--scale 1, or" not in said and said.endswith('--group "Part 7" and 2 more'), said
    assert ss.too_tall("group Bosses", 20000, 1, 16384, 100, []).endswith(
        "Take a part of it: put its events into smaller groups in the editor, then take each with --group")
