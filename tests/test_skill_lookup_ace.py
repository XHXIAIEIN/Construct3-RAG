"""lookup_ace.py: the conditions, actions and expressions to write, with their parameters."""
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests.skill_helpers import REPO, SKILL, INSTALLED, SHEET, tool, check, edit


@pytest.fixture
def skill_only(tmp_path) -> Path:
    """A folder that holds the skill and no project: an addon is looked up by its own name."""
    shutil.copytree(SKILL, tmp_path / INSTALLED, ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def test_ace_lookup_reaches_a_behavior_through_the_object(built):
    code, out = tool(built, "lookup_ace", "Coin", "tween", "two")
    assert code == 0
    assert "action tween-two-properties - Tween (two properties) [behavior Tween, tween]  <isAsync>" in out
    assert '"objectClass": "Coin", "behaviorType": "Tween", "sid": <new sid>, "parameters": {"tags": "\\"\\"", "property": "position"' in out
    assert "property               combo      The properties to tween.  (position | size | scale)" in out


def test_ace_lookup_names_combo_items_in_the_locale(built):
    """A combo item is written by its id and shown by its name. With the id alone a model named
    Pick top/bottom's top "上方" in a Chinese answer, where the editor shows "顶部"."""
    code, out = tool(built, "lookup_ace", "Coin", "pick-topbottom", "--locale", "zh-CN")
    assert code == 0 and "(top: 顶部 | bottom: 底部)" in out
    code, out = tool(built, "lookup_ace", "Coin", "pick-topbottom")
    assert code == 0 and "(top | bottom)" in out


def test_ace_lookup_marks_shared_triggers_and_writes_expressions(built):
    code, out = tool(built, "lookup_ace", "Coin", "collision", "another")
    assert "condition on-collision-with-another-object - On collision with another object [_common]  <isTrigger>" in out
    code, out = tool(built, "lookup_ace", "Coin", "progress")
    assert "write: Coin.Tween.Progress(tags)  -> number" in out


def test_ace_lookup_says_what_each_parameter_is(built):
    # find(text, find): the type says string twice, the schema's desc says which one is searched.
    code, out = tool(built, "lookup_ace", "System", "find")
    assert code == 0
    lines = out.splitlines()
    assert any(line.split()[:2] == ["text", "string"] and "Text to be searched." in line and "inner quotes" in line
               for line in lines), out
    assert any(line.split()[:2] == ["find", "string"] and "Text to search for." in line for line in lines), out
    code, out = tool(built, "lookup_ace", "System", "find", "--locale", "zh-CN")
    assert "原始字符串。" in out


def test_a_number_is_written_in_the_unit_its_description_names(built):
    """A grid column took a pixel position when the hint for every number showed one."""
    code, out = tool(built, "lookup_ace", "TileMovement", "grid", "position")
    line = next(line for line in out.splitlines() if line.split()[:2] == ["x", "number"])
    assert code == 0 and "The column to move the object to." in line and "in the unit its description names" in line
    assert "Self.X" not in line, line


def test_ace_lookup_names_the_entries_in_full_that_do_not_fit(built):
    code, out = tool(built, "lookup_ace", "System", "find", "--limit", "900")
    assert code == 0 and len(out) <= 900
    assert "expression find - find" in out and "1 more did not fit 900 characters (--limit): findcase" in out


def test_ace_lookup_words_may_name_the_behavior_and_the_kind(built):
    code, out = tool(built, "lookup_ace", "Coin", "tween", "condition", "playing")
    assert code == 0
    assert [line.split(" - ")[0] for line in out.splitlines() if " - " in line and not line.startswith(" ")] == [
        "condition is-playing", "condition is-any-playing"]


def test_ace_lookup_lists_briefly_when_many_match(built):
    code, out = tool(built, "lookup_ace", "System", "layer")
    assert code == 0 and "add a word to narrow them" in out and "write:" not in out


def test_ace_lookup_says_functions_is_built_in(built):
    code, out = tool(built, "lookup_ace", "Functions", "set", "return")
    assert code == 0
    assert out.splitlines()[0] == ('note: Functions is built in: project.c3proj names it in "functionsName", '
                                   'with no object type file and no usedAddons entry'), out


def test_a_functions_ace_found_under_system_is_written_on_the_functions_object(built):
    """Set return value and the function maps are in the System schema; the official examples
    write all of them with "objectClass": "Functions", none with "System"."""
    for target in ("System", "Functions"):
        code, out = tool(built, "lookup_ace", target, "set", "return")
        assert code == 0 and '"id": "set-function-return-value", "objectClass": "Functions"' in out, out
    code, out = tool(built, "lookup_ace", "System", "function", "map")
    assert '"id": "map-function", "objectClass": "Functions"' in out
    assert "write: Functions.CallMapped(name, string, ...)" in out
    code, out = tool(built, "lookup_ace", "Functions", "wait")
    assert '"objectClass": "Functions"' not in out     # Wait is System's, not the Functions object's


def test_ace_lookup_needs_no_project_and_takes_a_display_name(skill_only):
    code, out = tool(skill_only, "lookup_ace", "8 Direction", "max", "speed")
    assert code == 0, out
    assert "action set-max-speed" in out and "[behavior <behavior name on the object>, eightdir]" in out


def test_ace_lookup_offers_the_nearest_id(built):
    code, out = tool(built, "lookup_ace", "System", "wiat")
    assert code != 0 and "closest: wait" in out


def test_ace_lookup_does_not_take_a_near_name_for_the_addon(skill_only):
    """`Platform` is the behavior; a near match must not read it as the plugin Platform Info."""
    code, out = tool(skill_only, "lookup_ace", "Platform", "jump", "strength")
    assert code == 0 and "action set-jump-strength" in out and "platforminfo" not in out
    code, out = tool(skill_only, "lookup_ace", "Platfrom")
    assert code == 1 and "closest: platform" in out


def test_ace_lookup_takes_a_category_for_a_word(built):
    """The word an agent thinks of is the category more often than the id: time, not every-x-seconds."""
    code, out = tool(built, "lookup_ace", "System", "time")
    assert code == 0 and "condition  every-x-seconds " in out and "action     wait " in out
    code, out = tool(built, "lookup_ace", "System", "time", "condition")
    assert "condition compare-time - Compare time" in out and "by category, not by name: every-x-seconds" in out
    code, out = tool(built, "lookup_ace", "System", "timer")
    assert code == 1 and "categories, each a word too:" in out and " time," in out


def test_ace_lookup_by_name_is_not_widened_by_a_category(skill_only):
    code, out = tool(skill_only, "lookup_ace", "Physics", "force")
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


def test_ace_lookup_points_a_shared_ace_to_an_object(built, skill_only):
    """Pick nearest/furthest is every world object's, not System's, and so is Set color. The
    shared entry is the answer and comes first: printed after a line saying nothing was found,
    one Doubao run picked by lowest distance instead, another took a Sprite to have no color
    action and went to the manual, which does not list the shared ACEs either, to confirm it."""
    code, out = tool(built, "lookup_ace", "System", "nearest")
    assert code == 0 and out.startswith("every world object has these, in plugins/_common.json")
    assert "write: {\"id\": \"pick-nearestfurthest\", \"objectClass\": \"<Object>\"" in out
    assert "lookup_ace.py <Object> nearest writes its name in" in out
    code, out = tool(skill_only, "lookup_ace", "Sprite", "color")
    assert code == 0 and out.startswith("Sprite has these, in plugins/_common.json") and "set-default-color" in out
    assert "nothing under" not in out
    code, out = tool(built, "lookup_ace", "Coin", "nearest")
    assert code == 0 and "write: {\"id\": \"pick-nearestfurthest\", \"objectClass\": \"Coin\"" in out
    code, out = tool(built, "lookup_ace", "System", "wiat")
    assert code == 1 and "every world object has these" not in out


def test_ace_lookup_leaves_out_the_shared_aces_the_plugin_does_not_get(built, skill_only):
    """lookup_ace.py Text color printed Set color, which the editor refuses on a Text: of
    plugins/_common.json a plugin gets what its schema lists under commonAces."""
    code, out = tool(built, "lookup_ace", "ScoreText", "color")
    assert code == 0 and "set-font-color" in out and "set-default-color" not in out
    code, out = tool(built, "lookup_ace", "ScoreText", "opacity")
    assert code == 0 and "set-opacity" in out
    code, out = tool(skill_only, "lookup_ace", "Text", "default", "color")
    assert code == 1 and "set-default-color" not in out


def test_ace_lookup_finds_a_word_in_a_parameter(built):
    """Tween Color, which the event sheet guidance names, is Tween (one property) with the
    property offsetColor: the word is a combo value, and the names alone answer that Tween
    has no color. A parameter counts only when no name has every word."""
    code, out = tool(built, "lookup_ace", "Tween", "color")
    assert code == 0 and "no name under Tween has every word of 'color'" in out
    assert "tween-one-property" in out and "offsetColor" in out
    code, out = tool(built, "lookup_ace", "Tween", "pause")
    assert code == 0 and "pause-tweens" in out and "no name under Tween" not in out


def test_ace_lookup_prints_an_effect_with_its_parameters(built):
    """An effect has parameters and no ACEs. The zh-CN pack names both Brightness and
    Lighten 亮度, so that name prints both rather than the one a table kept last."""
    code, out = tool(built, "lookup_ace", "Bulge")
    assert code == 0 and out.startswith("effect bulge - Bulge [distortion]")
    assert "radius" in out and "scale" in out and "percent" in out
    code, out = tool(built, "lookup_ace", "Bulge", "radius")
    assert code == 0 and "radius" in out and "scale" not in out
    code, out = tool(built, "lookup_ace", "亮度", "--locale", "zh-CN")
    assert code == 0 and "effect brightness" in out and "effect lighten" in out and "no parameters" in out


def test_ace_lookup_names_what_the_editor_has_deprecated(skill_only):
    """A deprecated addon is said to be one, not listed as unknown; a deprecated ACE the
    schema kept comes after the current ones; one it left out is named, so that an id
    from an old project does not read as a typo."""
    code, out = tool(skill_only, "lookup_ace", "NW.js")
    assert code == 1 and out.startswith("NodeWebkit (NW.js) is a deprecated plugin: Construct 3 no longer offers it")
    code, out = tool(skill_only, "lookup_ace", "Warp")
    assert code == 1 and out.startswith("warp (Warp) is a deprecated effect")
    code, out = tool(skill_only, "lookup_ace", "Pin", "pin", "to", "object")
    assert code == 0 and out.index("action pin-to-object-properties") < out.index("action pin-to-object - ")
    assert "<deprecated>" in out and "the current action of the same name is pin-to-object-properties" in out
    code, out = tool(skill_only, "lookup_ace", "Mouse", "set-cursor-style")
    assert code == 0 and out.startswith("action set-cursor-style2 - Set cursor style")
    assert re.search(r"action +set-cursor-style +Set cursor style \[mouse\]  current of the same name: "
                     r"set-cursor-style2", out), out


def test_ace_lookup_prints_a_miss_on_stdout(built):
    """The miss and what comes near are the answer. On stderr, a harness that shows stdout
    alone printed nothing, and PowerShell wrapped each line in a NativeCommandError record,
    which is how two Doubao runs read it."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    def lookup(*words: str) -> subprocess.CompletedProcess:     # tool() joins stdout and stderr
        return subprocess.run([sys.executable, f"{INSTALLED}/scripts/lookup_ace.py", "--rag", str(REPO), *words],
                              cwd=built, env=env, capture_output=True, text=True, encoding="utf-8")
    p = lookup("Sprite", "aniamtion")
    assert p.returncode == 1
    assert p.stdout.startswith("nothing under Sprite has every word of 'aniamtion'\n") and "set-animation" in p.stdout
    assert p.stderr == ""
    p = lookup("Sprte")
    assert p.returncode == 1 and p.stdout == "" and "is not an object of this project" in p.stderr


def test_lookup_writes_a_sound_bare(built):
    code, out = tool(built, "lookup_ace", "Audio", "play-at-object")
    assert code == 0 and '"audio-file": "<sound>"' in out and "without its extension" in out, out


def test_lookup_writes_the_value_the_editor_fills_in(built):
    # A Wait written with "use-timescale": false ignores the time scale, unlike one added in the editor.
    code, out = tool(built, "lookup_ace", "System", "wait")
    assert code == 0 and '"parameters": {"seconds": "1.0", "use-timescale": true}' in out, out
    assert "the editor ticks it by default" in out, out


def test_lookup_writes_a_numeric_default_as_expression_text(built):
    """Set opacity's 100 and Add to's 1 are JSON numbers in the schema. A project file writes
    every expression as text, "opacity": "100" in the official examples, and the checker
    refuses "opacity": 100."""
    code, out = tool(built, "lookup_ace", "Coin", "set-opacity")
    assert code == 0 and '"parameters": {"opacity": "100"}' in out, out
    code, out = tool(built, "lookup_ace", "Coin", "add-to-instvar")
    assert code == 0 and '"parameters": {"instance-variable": "<variable>", "value": "1"}' in out, out


def test_every_shared_template_writes_its_expressions_as_text(project):
    """Each condition and action a Sprite gets from plugins/_common.json, copied from its
    write: line into a sheet: the checker finds no parameter that should be an expression
    string. The placeholders, <variable> and the like, are findings of their own."""
    schema = REPO / "data" / "c3-schemas" / "en-US" / "plugins" / "sprite.json"
    wanted = [(kind, ace) for kind in ("conditions", "actions")
              for ace in json.loads(schema.read_text(encoding="utf-8"))["commonAces"][kind]]
    with ThreadPoolExecutor(8) as pool:
        outs = list(pool.map(lambda w: tool(project, "lookup_ace", "Coin", w[1], w[0][:-1])[1], wanted))
    written = {"conditions": [], "actions": []}
    for n, ((kind, ace), out) in enumerate(zip(wanted, outs)):
        line = next((line for line in out.splitlines() if line.startswith(f'  write: {{"id": "{ace}"')), None)
        assert line, out
        written[kind].append(json.loads(line.removeprefix("  write: ").replace("<new sid>", str(900000 + n))))
    sid = iter(range(950000, 960000))

    def add(sheet):
        sheet["events"] += [{"eventType": "block", "conditions": [c], "actions": [], "sid": next(sid)}
                            for c in written["conditions"]]
        sheet["events"].append({"eventType": "block", "conditions": [], "actions": written["actions"], "sid": next(sid)})
    edit(project, SHEET, add)
    code, out = check(project, "--limit", "0")
    assert code == 1 and "<variable>" in out, out
    assert "should be an expression string" not in out, out


def test_a_behavior_looked_up_under_system_names_where_it_is(built):
    """`System timer` found nothing under System, and runs went on guessing words under it."""
    code, out = tool(built, "lookup_ace", "System", "timer")
    assert code == 1 and out.splitlines()[0].startswith(
        "Timer is a behavior, not part of System, and no object of the project has it: lookup_ace.py Timer lists")
    code, out = tool(built, "lookup_ace", "System", "tween", "two")
    assert out.splitlines()[0] == "Tween is a behavior, not part of System; Coin has it: lookup_ace.py Coin tween two"


def test_a_plugin_looked_up_under_another_object_names_the_object_that_is_one(built):
    code, out = tool(built, "lookup_ace", "Coin", "text", "set")
    assert out.splitlines()[0] == "Text is a plugin, not part of Coin: lookup_ace.py ScoreLabel set, a Text object of the project"


def test_a_behavior_inside_a_quoted_word_is_named_too(built):
    code, out = tool(built, "lookup_ace", "System", "start timer")
    assert out.splitlines()[0].startswith("Timer is a behavior, not part of System") and "lookup_ace.py Timer start" in out
