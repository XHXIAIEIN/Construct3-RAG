"""The generator and the checker an agent copies into a game project.

Both are standalone scripts, so the tests run them the way an agent does: as
subprocesses inside a project folder. The stand-in game of build-project.py is
generated once; each test breaks a private copy in one way and reads what the
checker says about it. Every rule tested here is one the editor enforces when
it opens or previews a project (docs/decisions/checker-editor-load-rules.md).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "prompts" / "project-tools"
SHEET = "eventSheets/Game.json"


def run(root: Path, script: str, *args: str) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k != "CONSTRUCT3_RAG"}
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([sys.executable, f"tools/{script}", *args], cwd=root, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def check(root: Path, *args: str) -> tuple[int, str]:
    return run(root, "check-project.py", "--rag", str(REPO), *args)


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("coins")
    (root / "tools").mkdir()
    for name in ("build-project.py", "check-project.py"):
        shutil.copy(TOOLS / name, root / "tools" / name)
    # What the editor leaves after "Save as project folder", reduced to the keys the generator reads,
    # and the block's path line, which is how the checker the generator ends with finds the schemas.
    (root / "project.c3proj").write_text(json.dumps({"uniqueId": "test", "properties": {}}), encoding="utf-8")
    (root / "AGENTS.md").write_text(f"# Construct 3\n\n- Construct3-RAG: {REPO.as_posix()}\n", encoding="utf-8")
    code, out = run(root, "build-project.py")
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
    return {
        "setup": groups["Setup"]["children"][0],
        "loop": groups["Setup"]["children"][0]["children"][0],
        "input_group": groups["Input"],
        "input": groups["Input"]["children"][0],
        "restart": groups["Restart"],
        "collect": next(e for e in rows if e["eventType"] == "custom-ace-block"),
        "add_score": next(e for e in rows if e["eventType"] == "function-block"),
    }


def findings(root: Path, change, rel: str = SHEET) -> str:
    edit(root, rel, change)
    code, out = check(root)
    assert "Traceback" not in out, out
    return out


# --- the generated project ----------------------------------------------------------
def test_stand_in_project_passes_without_warnings(built):
    code, out = check(built)
    assert code == 0, out
    assert out.startswith("ok:") or "\nok:" in out
    assert [line for line in out.splitlines() if line.startswith("warning:") and "Pillow" not in line] == []


def test_generator_exits_with_the_checkers_findings(project):
    """One command builds and checks, so a finding cannot be skipped by forgetting the second."""
    source = project / "tools" / "build-project.py"
    source.write_text(source.read_text(encoding="utf-8").replace(
        'return cond("on-touched-object", "Touch", {"object": obj, "type": "start"})',
        'return cond("on-touched-object", "Touch", {"object": obj, "type": "\\"start\\""})'), encoding="utf-8")
    code, out = run(project, "build-project.py")
    assert code == 1
    assert "generated; checking" in out and 'write it bare, "start"' in out


def test_generator_without_the_checker_says_so(project):
    (project / "tools" / "check-project.py").unlink()
    code, out = run(project, "build-project.py")
    assert code != 0 and "generated, not checked" in out


def test_outline_numbers_events_as_the_editor_does(built):
    code, out = check(built, "--outline", "Game")
    rows = [line.split("[sid")[0].rstrip() for line in out.splitlines()]
    assert code == 0
    assert rows[:4] == ["== Game", "   (1) // Coins. Tap a coin to collect it; when the last one is gone the layout restarts.",
                        "   (1) number score = 0", "   (1) number COIN_COUNT = 6"]
    assert "   1 group Setup" in rows and "   2   System:on-start-of-layout" in rows


def test_print_words_the_sheet_as_the_editor_does(built):
    code, out = check(built, "--print", "Game")
    assert code == 0
    assert "   5   Touch: On touched Coin (start)\n           -> Coin: Collect()" in out
    assert "     global constant number COIN_COUNT = 6" in out
    assert "   7 function AddScore(points: number)\n         -> System: Add points to score" in out
    assert "   9   System: Coin.Count = 0\n       System: Trigger once" in out


def test_print_follows_the_locale(built):
    code, out = check(built, "--print", "Game", "--locale", "zh-CN")
    assert code == 0 and "System: 场景开始" in out


# --- looking an ACE up -------------------------------------------------------------------
def test_ace_lookup_reaches_a_behavior_through_the_object(built):
    code, out = check(built, "--ace", "Coin", "tween", "two")
    assert code == 0
    assert "action tween-two-properties - Tween (two properties) [behavior Tween, tween]  <isAsync>" in out
    assert '"objectClass": "Coin", "behaviorType": "Tween", "sid": <new sid>, "parameters": {"tags": "\\"\\"", "property": "position"' in out
    assert "property               combo      position | size | scale" in out


def test_ace_lookup_marks_shared_triggers_and_writes_expressions(built):
    code, out = check(built, "--ace", "Coin", "collision", "another")
    assert "condition on-collision-with-another-object - On collision with another object [_common]  <isTrigger>" in out
    code, out = check(built, "--ace", "Coin", "progress")
    assert "write: Coin.Tween.Progress(tags)  -> number" in out


def test_ace_lookup_words_may_name_the_behavior_and_the_kind(built):
    code, out = check(built, "--ace", "Coin", "tween", "condition", "playing")
    assert code == 0
    assert [line.split(" - ")[0] for line in out.splitlines() if " - " in line and not line.startswith(" ")] == [
        "condition is-playing", "condition is-any-playing"]


def test_ace_lookup_lists_briefly_when_many_match(built):
    code, out = check(built, "--ace", "System", "layer")
    assert code == 0 and "add a word to narrow them" in out and "write:" not in out


def test_ace_lookup_needs_no_project_and_takes_a_display_name(tmp_path):
    shutil.copytree(TOOLS, tmp_path / "tools")
    code, out = check(tmp_path, "--ace", "8 Direction", "max", "speed")
    assert code == 0, out
    assert "action set-max-speed" in out and "[behavior <behavior name on the object>, eightdir]" in out


def test_ace_lookup_offers_the_nearest_id(built):
    code, out = check(built, "--ace", "System", "wiat")
    assert code != 0 and "closest: wait" in out


# --- finding the schemas ---------------------------------------------------------------
@pytest.mark.parametrize("lines", [
    "- Construct3-RAG: {rag}",
    "- path-to = {parent}\\\n- Construct3-RAG: <path-to>/{name}",
    "- <path-to>: {parent}\n- Construct3-RAG: <path-to>/{name}",
])
def test_rag_is_read_from_the_project_instruction_file(project, lines):
    text = lines.format(rag=REPO.as_posix(), parent=REPO.parent.as_posix(), name=REPO.name)
    (project / "AGENTS.md").write_text(f"# Construct 3\n\n{text}\n\nText after the block.\n", encoding="utf-8")
    code, out = run(project, "check-project.py")
    assert code == 0, out


def test_unfilled_block_says_how_to_point_at_the_clone(project):
    (project / "AGENTS.md").write_text("- Construct3-RAG: <path-to>/Construct3-RAG\n", encoding="utf-8")
    code, out = run(project, "check-project.py")
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


def test_missing_key_stops_with_a_sentence(project):
    def change(s):
        del events(s)["add_score"]["functionParameters"]
    out = findings(project, change)
    assert "check-project.py stopped at line" in out and "missing key 'functionParameters'" in out


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
