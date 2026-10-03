"""check_project.py: each rule the editor enforces when it opens or previews a project, broken
once in a private copy of the stand-in game (docs/decisions/checker-editor-load-rules.md)."""
import json
import re
from pathlib import Path

import pytest

from tests.skill_helpers import (
    REPO, SKILL, INSTALLED, SHEET, run, tool, check, edit, cond, block, events, collect_tween, warnings, findings,
    plan,
)


# --- what the editor reads as it opens a project --------------------------------------------------
def test_a_passing_check_ends_with_the_command_that_opens_the_project(built):
    code, out = check(built)
    assert code == 0 and out.splitlines()[-1].endswith(f"python {INSTALLED}/scripts/open_in_editor.py --preview"), out
    code, out = run(built.parent, SKILL / "scripts" / "check_project.py", "--rag", str(REPO), "--project", str(built))
    assert code == 0 and out.splitlines()[-1].endswith(
        f"open_in_editor.py --project {built.resolve().as_posix()} --preview"), out


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


@pytest.mark.parametrize("change, said", [
    (lambda p: p["properties"].pop("description"),
     'description is missing or not text'),
    (lambda p: p["properties"].pop("author") or p["properties"].pop("appId"),
     'author, appId are missing or not text'),
    (lambda p: p["properties"].pop("loaderStyle"), 'no "loaderStyle"'),
    (lambda p: p["properties"].update(orientations="vertical"),
     "orientations 'vertical' is not one of any, portrait, landscape"),
    (lambda p: p["properties"].update(sampling="linear"), None),       # the editor maps the older id
    (lambda p: p.update(viewportWidth="720"), "viewportWidth is '720'"),
    (lambda p: p.update(projectFormatVersion=2), "projectFormatVersion is 2"),
    (lambda p: p.pop("savedWithRelease"), r"looks for objectTypes\coin.json in lower case"),
    (lambda p: p.update(savedWithRelease=24402), "savedWithRelease 24402 is below r309"),
    (lambda p: p.pop("containers"), 'containers is None'),
    (lambda p: p.update(containers={}), '"TypeError: expected array"'),
    (lambda p: p.pop("eventSheets"), 'no "eventSheets"'),
    (lambda p: p.pop("layouts"), '"layouts": {"items": ["Game", "Objects"], "subfolders": []}'),
    (lambda p: p["objectTypes"].pop("subfolders"), "objectTypes: subfolders is None"),
    (lambda p: p["eventSheets"].update(items="Game"), "eventSheets: items is 'Game'"),
])
def test_checker_names_what_the_editor_reads_before_it_opens_a_file(project, change, said):
    out = findings(project, change, "project.c3proj")
    if said is None:
        assert warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out
    else:
        assert said in out, out


@pytest.mark.parametrize("rel, change, said", [
    ("layouts/Game.json", lambda d: d.pop("name"), 'layout Game: the file says "name": None'),
    ("layouts/Game.json", lambda d: d.pop("width"), "layout Game: width is None"),
    ("layouts/Game.json", lambda d: d.update(height=1), "height is 1; the editor refuses anything below 2"),
    ("layouts/Game.json", lambda d: d.pop("layers"), "layout Game: layers is None"),
    ("layouts/Game.json", lambda d: d["layers"][0].pop("name"), "a layer is named None"),
    ("layouts/Game.json", lambda d: d["layers"][0].pop("parallaxX"), "parallaxX is None"),
    ("layouts/Game.json", lambda d: d["layers"][0].pop("scaleRate"), "scaleRate is None"),
    ("layouts/Game.json", lambda d: d["layers"][0].update(blendMode="glow"), '"invalid blend mode"'),
    ("layouts/Game.json", lambda d: d["layers"][0].pop("instances"), 'writes "instances": []'),
    ("layouts/Objects.json", lambda d: d["layers"][0]["instances"][0].pop("world"),
     "Coin has no world block"),
    ("layouts/Objects.json", lambda d: d["layers"][0]["instances"][0]["world"].pop("originY"),
     "world.originY is None"),
    ("layouts/Objects.json", lambda d: d["layers"][0]["instances"][0]["world"].update(x="10"),
     "world.x is '10'"),
    ("eventSheets/Game.json", lambda d: d.pop("name"), 'sheet Game: the file says "name": None'),
    ("eventSheets/Game.json", lambda d: d.pop("events"), 'sheet Game: events is None'),
])
def test_checker_names_what_the_editor_reads_out_of_a_layout_or_a_sheet(project, rel, change, said):
    """Every one of these stops the open with a type and no place: the layout and
    layer loaders assert as they read (docs/decisions/checker-editor-load-rules.md)."""
    out = findings(project, change, rel)
    assert said in out, out


@pytest.mark.parametrize("change, said", [
    (lambda ev, d: ev.pop("conditions"), 'conditions is None'),
    (lambda ev, d: ev.pop("actions"), 'actions is None'),
    (lambda ev, d: ev.update(children={}), "children is {}"),
    (lambda ev, d: d["events"].append({"eventType": "script", "script": 5}), '"invalid script data"'),
    (lambda ev, d: d["events"].append("hello"), "an event is 'hello'"),
    (lambda ev, d: d["events"].append({"eventType": "group", "title": "Empty", "description": ""}), None),
])
def test_checker_names_the_lists_the_editor_walks_inside_a_sheet(project, change, said):
    """A block loops over its conditions and actions without looking first; a group
    without children is read and left empty, so it is not a finding."""
    out = findings(project, lambda sheet: change(events(sheet)["input"], sheet))
    if said is None:
        assert warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out
    else:
        assert said in out, out


def test_a_sprite_without_its_animations_folder_is_named(project):
    """The editor reads the folder as it opens the type: "TypeError: expected object"."""
    out = findings(project, lambda t: t.pop("animations"), "objectTypes/Coin.json")
    assert "object type Coin: a Sprite carries an animations folder" in out


@pytest.mark.parametrize("change, said", [
    (lambda t: t.pop("image"), 'Write "image": {"width": <w>'),
    (lambda t: t.update(animations=t.pop("image")), 'Write in place of its animations "image"'),
])
def test_a_single_image_type_without_its_image_is_named(project, change, said):
    """A Tiled Background, Sprite Font, Particles, Tilemap or 9-patch type without
    "image" stops the open with "TypeError: expected object"."""
    out = findings(project, change, "objectTypes/Backdrop.json")
    assert "object type Backdrop: a TiledBg carries one image" in out and said in out
    assert "the size of images/backdrop.png" in out


@pytest.mark.parametrize("block", [{}, {"enabled": True}])
def test_an_instance_behavior_without_properties_is_named(project, block):
    """`"Tween": {}` on an instance stops the open with "Cannot convert undefined or
    null to object"; every one of the examples' behavior blocks holds "properties"."""
    out = findings(project, lambda d: d["layers"][0]["instances"][0]["behaviors"].update(Tween=block),
                   "layouts/Objects.json")
    assert f'Coin instance behavior Tween is {json.dumps(block)}, with no "properties" block' in out
    assert 'Write "Tween": {"properties": {"enabled": true}}' in out


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
    assert warnings(findings(project, change)) == []


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


@pytest.mark.parametrize("value, refused", [
    ("Pop", False), ("POP", False), ('"Pop"', False), ("0", True), ("Pop.webm", True), ("Popp", True)])
def test_a_sound_is_named_as_a_sound_or_music_file(project, value, refused):
    """The editor opened a copy of the audio-scheduling example with its sound written SFX1 for sfx1.webm, and with
    it in inner quotes, and refused "0", "sfx1.webm" and a name it has not: "missing file '0'"."""
    (project / "objectTypes" / "Audio.json").write_text(json.dumps({
        "name": "Audio", "plugin-id": "Audio", "sid": 3,
        "singleglobal-inst": {"type": "Audio", "properties": {}, "uid": 900, "sid": 4, "tags": ""}}), encoding="utf-8")
    (project / "sounds").mkdir(exist_ok=True)
    (project / "sounds" / "pop.webm").write_bytes(b"")

    def project_file(p):
        p["objectTypes"]["items"].append("Audio")
        p["usedAddons"].append({"type": "plugin", "id": "Audio", "name": "Audio", "author": "Scirra", "bundled": False})
        p.setdefault("rootFileFolders", {})["sound"] = {"items": [
            {"name": "pop.webm", "type": "audio/webm; codecs=opus", "sid": 5, "file-info": {"purpose": "none"}}],
            "subfolders": []}
    edit(project, "project.c3proj", project_file)
    out = findings(project, lambda s: events(s)["add_score"]["actions"].append(
        {"id": "play", "objectClass": "Audio", "sid": 6, "parameters": {
            "audio-file": value, "loop": "not-looping", "volume": "0", "stereo-pan": "0", "tag-optional": '""'}}))
    assert ("is not a sound or music file of the project" in out) == refused, out
    if refused:
        assert "Write the file's name without its extension; " + ("the project has pop" if value == "0"
                                                                    else "closest: pop") in out, out


def test_action_cannot_write_a_constant(project):
    def change(s):
        events(s)["add_score"]["actions"].append(
            {"id": "set-eventvar-value", "objectClass": "System", "sid": 5,
             "parameters": {"variable": "ROUND_COINS", "value": '"3"'}})
    assert "ROUND_COINS is a constant and an action cannot change it" in findings(project, change)


def number_variable(name: str, constant: bool, sid: int) -> dict:
    return {"eventType": "variable", "name": name, "type": "number", "initialValue": "0", "comment": "",
            "isStatic": False, "isConstant": constant, "sid": sid}


@pytest.mark.parametrize("globals_, local, written, refused", [
    (["PHASE", "phase"], None, "phase", "global constant PHASE"),
    (["phase", "PHASE"], None, "phase", None),
    (["phase", "PHASE"], None, "PHASE", None),
    (["phase"], "PHASE", "phase", "local constant PHASE"),
    (["PHASE"], "phase", "PHASE", None),
])
def test_an_action_writes_the_variable_the_editor_finds_without_case(project, globals_, local, written, refused):
    """A constant PHASE declared above a variable phase made Add 1 to phase stop the editor with
    "event variable phase is constant": it finds a name without case, the nearest declaration
    first and, among the variables of one list of events, the first. Each case was opened in
    the editor (r495.2, 2026-10-02); the ones without this finding opened."""
    def change(sheet):
        sheet["events"][0:0] = [number_variable(n, n == "PHASE", 900000000000010 + i) for i, n in enumerate(globals_)]
        block = events(sheet)["setup"]
        if local:
            block.setdefault("children", []).insert(0, number_variable(local, local == "PHASE", 900000000000020))
            block = block["children"][1]
        block["actions"].append({"id": "add-to-eventvar", "objectClass": "System", "sid": 900000000000021,
                                 "parameters": {"variable": written, "value": "1"}})
    out = findings(project, change)
    if refused:
        assert f"{written} is read as the {refused}" in out
        assert f"'event variable {written} is constant'. Rename the variable {written}" in out
    else:
        assert "constant" not in out, out


@pytest.mark.parametrize("where, names, expected", [
    ("globals", ["lives", "lives"], "sheet Game variable lives: lives is declared again; the first lives is "
                                    "declared at the top level of sheet Game"),
    ("globals", ["PHASE", "phase"], "sheet Game variable phase: phase has the name of PHASE, declared at the top "
                                    "level of sheet Game, once case is ignored"),
    ("locals", ["step", "STEP"], "variable STEP: STEP has the name of step, declared above it in the same list "
                                 "of events, once case is ignored; the editor finds every use of either name as "
                                 "step, so STEP is never read or written. Rename it and its uses, for example "
                                 "STEPValue"),
    ("parameters", ["amount", "Amount"], "parameter Amount: Amount has the name of amount, an earlier parameter "
                                         "of the same function, once case is ignored"),
])
def test_two_variables_of_one_scope_with_one_name_are_refused(project, where, names, expected):
    """The editor's dialogs refuse a second variable named like one of its scope, case aside; a file
    that has two opens, and every use of the name reaches the first (opened in r495.2, 2026-10-02).
    A small model declared its globals at the top of both of its sheets."""
    def change(sheet):
        if where == "parameters":
            events(sheet)["add_score"]["functionParameters"] += [
                {"name": n, "type": "number", "initialValue": "0", "comment": "", "sid": 900000000000030 + i}
                for i, n in enumerate(names)]
            return
        declared = [number_variable(n, n == "PHASE", 900000000000030 + i) for i, n in enumerate(names)]
        if where == "globals":
            sheet["events"][0:0] = declared
        else:
            events(sheet)["setup"].setdefault("children", [])[0:0] = declared
    out = findings(project, change)
    assert expected in out, out
    assert out.count("never read or written") == 1, out


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
    out = findings(project, lambda s: collect_tween(s)["parameters"].update(**{"end-x": "Self.X"}))
    assert "Self" not in out, out


def test_event_text_keys_return_type_and_ace_type_are_the_editors(project):
    """Opened in the editor, each of these stops the project; the checker passed them before."""
    def change(s):
        rows = s["events"]
        next(e for e in rows if e["eventType"] == "variable").pop("comment")
        events(s)["restart"].pop("description")
        next(e for e in events(s)["restart"]["children"] if e["eventType"] == "comment").pop("text")
        events(s)["add_score"]["functionReturnType"] = "void"
        events(s)["collect"]["aceType"] = "condition"
    out = findings(project, change)
    assert "has comment None; write \"comment\": \"\" when it has none, the editor reads it as text and stops " \
           "with \"expected string\"" in out
    assert "the group has description None" in out
    assert "the comment has text None" in out and "reading 'endsWith'" in out
    assert "functionReturnType 'void' is not one of none, number, string, any" in out
    assert "aceType 'condition' should be \"action\"" in out


@pytest.mark.parametrize("kind, entry, said", [
    ("icon", {"name": "icon-512.png", "type": "image/png", "sid": 7, "icon-info": {"purpose": "app-icon"}},
     "icon file icon-512.png is listed in project.c3proj but icons/icon-512.png is missing"),
    ("video", {"name": "clip.webm", "type": "video/webm", "sid": 7, "file-info": {"purpose": "none"}},
     "video file clip.webm is listed in project.c3proj but videos/clip.webm is missing"),
])
def test_a_listed_root_file_exists_in_its_folder(project, kind, entry, said):
    """The editor opens every file rootFileFolders lists: "missing file path 'icons\\icon-16.png'", and
    "missing file path 'videos\\clip.webm'" in the stable editor, 2026-10-03."""
    def change(d):
        d.setdefault("rootFileFolders", {}).setdefault(kind, {"items": [], "subfolders": []})["items"].append(entry)
    out = findings(project, change, "project.c3proj")
    assert said in out, out


def test_a_frame_whose_size_differs_from_its_image_passes(project):
    """The editor takes an image's size from the file and ignores the width and height of its
    entry (Scirra's guide "Construct's project format"); a copy of an example with a frame's
    size changed opened and previewed in the stable editor, 2026-10-03."""
    def change(t):
        frame = t["animations"]["items"][0]["frames"][0]
        frame["width"], frame["height"] = frame["width"] * 3 + 7, frame["height"] * 2 + 5
    out = findings(project, change, "objectTypes/Coin.json")
    assert warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out


@pytest.mark.parametrize("file_type, missing", [("image/jpeg", False), ("image/png", True)])
def test_an_image_kept_in_a_lossy_format_is_found_by_its_file_type(project, file_type, missing):
    """An image imported as JPEG, AVIF or WebP and not edited keeps its format, which the
    entry's fileType names."""
    (project / "images" / "coin-default-000.png").rename(project / "images" / "coin-default-000.jpg")
    out = findings(project, lambda t: t["animations"]["items"][0]["frames"][0].update(fileType=file_type),
                   "objectTypes/Coin.json")
    assert ("missing image images/coin-default-000.png: the editor reads a frame from images/<object type>-"
            in out) == missing, out


def test_a_file_project_c3proj_does_not_list_is_named(project):
    """The editor reads only what project.c3proj lists: a copy of an example with an unlisted event
    sheet the editor would refuse opened and previewed in the stable editor, 2026-10-03. UI state
    files and the scripts folder, where the editor keeps unlisted TypeScript files, are not named."""
    (project / "eventSheets" / "Extra.json").write_text(json.dumps({"name": "Extra", "events": []}), encoding="utf-8")
    (project / "eventSheets" / "Game.uistate.json").write_text("{}", encoding="utf-8")
    (project / "layouts" / "uistate").mkdir(exist_ok=True)
    (project / "layouts" / "uistate" / "Game.instancesBar.json").write_text("{}", encoding="utf-8")
    (project / "files").mkdir(exist_ok=True)
    (project / "files" / "levels.json").write_text("[]", encoding="utf-8")
    (project / "scripts" / "ts-defs").mkdir(parents=True, exist_ok=True)
    (project / "scripts" / "ts-defs" / "index.d.ts").write_text("", encoding="utf-8")
    code, out = check(project)
    assert code == 0 and warnings(out) == [
        'warning: eventSheets/Extra.json is not listed in project.c3proj, so the editor ignores it: if the project '
        'uses it, add "Extra" to the "eventSheets" items',
        'warning: files/levels.json is not listed in project.c3proj, so the editor ignores it: if the project uses '
        'it, import it in the editor, or add an entry for "levels.json" to the rootFileFolders "general" items, '
        'written like the entries the editor saved there'], out


def test_sound_or_music_that_is_not_webm_opus_is_named(project):
    """Sound and music are WebM Opus (Scirra's guide "Construct's project format"); a copy of an
    example with its sound listed as a WAV file opened and previewed, so it is a warning."""
    (project / "sounds").mkdir(exist_ok=True)
    (project / "sounds" / "pop.wav").write_bytes(b"")
    out = findings(project, lambda d: d.setdefault("rootFileFolders", {}).update(sound={"items": [
        {"name": "pop.wav", "type": "audio/wav", "sid": 5, "file-info": {"purpose": "none"}}], "subfolders": []}),
        "project.c3proj")
    assert [w for w in warnings(out) if "pop.wav" in w] == [
        'warning: sound file pop.wav is not WebM Opus (.webm), the format a project\'s sound and music are in; the '
        'editor opens it, and whether it plays depends on the browser. Encode it, ffmpeg -i pop.wav -c:a libopus '
        'pop.webm, and list pop.webm with "type": "audio/webm; codecs=opus", or import the file in the editor, '
        'which converts it'], out


def test_a_script_listed_as_both_ts_and_js_is_named(project):
    """Construct runs the .js and ignores the .ts of one script
    [manual: scripting/using-scripting/typescript-construct.md]."""
    (project / "scripts").mkdir(exist_ok=True)
    for name in ("main.ts", "main.js"):
        (project / "scripts" / name).write_text("", encoding="utf-8")
    out = findings(project, lambda d: d.setdefault("rootFileFolders", {}).update(script={"items": [
        {"name": "main.ts", "type": "application/typescript", "sid": 5, "script-info": {"purpose": "main"}},
        {"name": "main.js", "type": "application/javascript", "sid": 6, "script-info": {"purpose": "none"}}],
        "subfolders": []}), "project.c3proj")
    assert "warning: scripts/main.ts and scripts/main.js are both listed; Construct runs the .js and ignores " \
           "the .ts" in out, out


def test_c_style_operators_are_refused_with_the_construct_ones(project):
    """The editor's parser refuses ==, !=, &&, ||, ** and ! ("Syntax error"); inside a text literal they are
    text. ^ is Construct's power: 2 ^ 3 ran as 8 in a preview."""
    def change(s):
        events(s)["add_score"]["actions"] += [
            {"id": "set-eventvar-value", "objectClass": "System", "sid": 5 + i,
             "parameters": {"variable": "score", "value": value}}
            for i, value in enumerate(['points == 5 ? 5 : 1', 'points != 5 & score || 1',
                                       '!points', 'points = 5 ? 1 : 0', 'len("a == b") <> 0 | 1',
                                       'points ** 2', 'points ^ 2 + len("2 ** 3")'])]
    out = findings(project, change)
    assert "value: == is not an operator of Construct expressions; the editor stops with \"Syntax error\"; " \
           "write 'points = 5 ? 5 : 1'" in out
    assert "value: !=, || are not operators of Construct expressions; the editor stops with \"Syntax error\"; " \
           "write 'points <> 5 & score | 1'" in out
    assert "value: ! is not an operator" in out and "a negation is a comparison with 0" in out
    assert "value: ** is not an operator of Construct expressions; the editor stops with \"Syntax error\"; " \
           "write 'points ^ 2'" in out
    assert out.count("of Construct expressions") == 4, out


def test_ease_is_a_builtin_id(project):
    out = findings(project, lambda s: collect_tween(s)["parameters"].update(ease="ease-in-back"))
    assert "ease='ease-in-back' is not a built-in ease; closest: easeinback" in out


# --- messages that say what to write instead ----------------------------------------------
def test_behavior_action_without_behavior_type_names_the_behavior(project):
    out = findings(project, lambda s: collect_tween(s).pop("behaviorType"))
    assert 'it belongs to the behavior Tween: add "behaviorType": "Tween"' in out


def test_script_name_in_place_of_the_id(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1].update(id="SetText"))
    assert "Text has no action SetText" in out and "the id is 'set-text'" in out


def test_misspelt_id_lists_the_nearest(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1].update(id="set-txt"))
    assert "closest: set-text" in out


def test_a_shared_ace_the_plugin_does_not_get_is_refused(project):
    """Set color is in plugins/_common.json, but the editor gives it only to a plugin that
    supports colour, and Text does not: it refused the LiquidVolume project with "missing
    action id 'set-default-color'". Text's colour is Set font color."""
    def change(sheet):
        setup = events(sheet)["setup"]
        setup["actions"][1].update(id="set-default-color", parameters={"color": "rgbEx(100, 0, 0)"})
        setup["actions"].append({"id": "set-opacity", "objectClass": "ScoreText", "sid": 900000000000003,
                                 "parameters": {"opacity": "50"}})
    out = findings(project, change)
    assert "Text has no action set-default-color: it is in plugins/_common.json, but the editor gives it only "            "to plugins that ask for it, not to Text" in out
    assert "closest: set-font-color" in out
    assert "set-opacity" not in out


def test_a_shared_expression_the_plugin_does_not_get_is_named(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="ScoreText.ColorValue"))
    assert "ScoreText.ColorValue is neither an expression nor an instance variable of ScoreText" in out
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="ScoreText.Opacity"))
    assert "ScoreText.Opacity" not in out


@pytest.mark.parametrize("name", ["mid", "Max"])
def test_a_variable_named_like_a_system_expression_is_refused(project, name):
    """A local mid passed as Functions.areaBelow(mid) is read as the text function mid(), and the
    editor refused the LiquidVolume project with "Invalid expressions ... parameter 0 does not
    take 'string'". The comparison ignores case, as the editor's reading of names does."""
    def change(sheet):
        setup = events(sheet)["setup"]
        setup.setdefault("children", []).insert(0, {
            "eventType": "variable", "name": name, "type": "number", "initialValue": "0", "comment": "",
            "isStatic": False, "isConstant": False, "sid": 900000000000004})
    out = findings(project, change)
    assert f"variable {name}: the name is that of the system expression {name.lower()}" in out
    assert f"rename it, for example {name}Value" in out


def test_a_function_parameter_named_like_a_system_expression_is_refused(project):
    """A parameter round used as "第 " & round & " 轮" stopped the editor with "'round' does not
    accept 0 parameters" (r504, 2026-10-02); roundNo opened."""
    def change(sheet):
        events(sheet)["add_score"]["functionParameters"].append(
            {"name": "round", "type": "number", "initialValue": "0", "comment": "", "sid": 900000000000008})
    out = findings(project, change)
    assert "parameter round: the name is that of the system expression round" in out
    assert "not as the parameter" in out


def test_a_call_with_an_empty_pair_of_parentheses_is_refused(project):
    """Functions.settling() stopped the editor with "Syntax error: ')' can't go here" (r504,
    2026-10-02); Functions.settling opened."""
    def change(sheet):
        sheet["events"].append({
            "functionName": "settling", "functionDescription": "", "functionCategory": "",
            "functionReturnType": "number", "functionCopyPicked": False, "functionIsAsync": False,
            "functionParameters": [], "eventType": "function-block", "conditions": [], "actions": [],
            "sid": 900000000000009})
        events(sheet)["setup"]["actions"][1]["parameters"].update(text="Functions.settling()")
    out = findings(project, change)
    assert "Functions.settling() has an empty pair of parentheses" in out
    assert "called without them: Functions.settling" in out
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(
        text="Functions.settling"))
    assert "empty pair" not in out


def test_a_local_that_hides_a_variable_of_another_type_by_case_is_refused(project):
    """A local string count hid the global constant COUNT, and COUNT - 1 below it stopped the editor
    with "Type mismatch: - does not work with 'string' and 'number'". A same-typed local, or one
    whose name differs by more than case, is accepted."""
    def change(sheet):
        children = events(sheet)["setup"].setdefault("children", [])
        children.insert(0, {"eventType": "variable", "name": "SCORE", "type": "string", "initialValue": "",
                            "comment": "", "isStatic": False, "isConstant": False, "sid": 900000000000005})
        events(sheet)["add_score"]["functionParameters"].append(
            {"name": "Score", "type": "number", "initialValue": "0", "comment": "", "sid": 900000000000006})
        children.insert(0, {"eventType": "variable", "name": "scoreText", "type": "string", "initialValue": "",
                            "comment": "", "isStatic": False, "isConstant": False, "sid": 900000000000007})
    out = findings(project, change)
    assert "variable SCORE: string SCORE has the name of the number variable score once case is ignored" in out
    assert "rename it, for example SCOREText" in out
    assert "parameter Score" not in out
    assert "scoreText" not in out


def test_unknown_parameter_lists_the_real_ones(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(value='"x"'))
    assert "unknown parameter value; the parameters are: text" in out


def test_behavior_expression_without_the_behavior_name(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="Coin.Progress"))
    assert "Coin.Progress is neither an expression nor an instance variable of Coin" in out
    assert "it is an expression of a behavior: Coin.Tween.Progress" in out


def test_quoted_combo_value_is_told_to_drop_the_quotes(project):
    """The commonest encoding slip in generated sheets: a combo written like a string expression."""
    out = findings(project, lambda s: events(s)["input"]["conditions"][0]["parameters"].update(type='"start"'))
    assert "type='\"start\"' is not one of" in out
    assert 'write it bare, "start": only an expression parameter carries inner quotes' in out


def test_bare_text_value_is_told_to_add_the_quotes(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="Hello"))
    assert "identifier 'Hello' is not a variable" in out and 'a text value carries inner quotes: "\\"Hello\\""' in out


def test_true_and_false_are_told_the_boolean_aces(project):
    """An agent writes a boolean as it would in JavaScript; quoting it would make a text."""
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="false"))
    assert "identifier 'false' is not a variable" in out and "an expression has no true or false" in out
    assert "compare-boolean-eventvar" in out and "inner quotes" not in out


def test_if_else_is_told_the_conditional_operator(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="if 1 else 2"))
    assert "identifier 'if' is not a variable" in out and "an expression chooses with condition ? a : b" in out


def test_names_outside_ascii_are_checked_like_the_others(project):
    """The editor takes names in any script; an undeclared one stops it with "unknown
    expression" as it opens the project. A mixed name is one name, not its ASCII part."""
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="速度 + 1"))
    assert "identifier '速度' is not a variable, parameter or system expression" in out
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="Coin.高度"))
    assert "Coin.高度 is neither an expression nor an instance variable of Coin" in out
    edit(project, SHEET, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text='"Score: 0"'))
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "目标y坐标", "initialValue": 30}]},
                     {"event": 2, "add-actions": [{"id": "set-text", "objectClass": "ScoreText",
                                                   "parameters": {"text": "目标y坐标 + 1"}}]})
    assert code == 0, out


def test_a_groups_local_is_not_seen_from_a_sibling_group(project):
    """A local declared in one group is out of scope in the next; the editor opens the
    project with "unknown expression" on every use there."""
    def change(sheet):
        ev = events(sheet)
        ev["input_group"]["children"].insert(0, {"eventType": "variable", "name": "拾取距离", "type": "number",
                                                 "initialValue": "40", "comment": "", "isStatic": False,
                                                 "isConstant": False, "sid": 4})
        ev["restart_block"]["actions"].append({"id": "set-text", "objectClass": "ScoreText", "sid": 5,
                                               "parameters": {"text": "拾取距离 + 1"}})
    out = findings(project, change)
    assert "identifier '拾取距离' is not a variable, parameter or system expression" in out


@pytest.mark.parametrize("text, said", [
    # r495.2: "Incorrect parameters: 'LocalStorage.ItemValue' does not accept 1 parameters"
    ("Coin.X(1)", "Coin.X takes 0 parameters and is given 1; the editor stops with \"Incorrect parameters: "
                  "'Coin.X' does not accept 1 parameters\". Write Coin.X"),
    ("clamp(Coin.X, 0)", "clamp takes 3 parameters and is given 2"),
    ("Coin.Tween.Progress", "Coin.Tween.Progress takes 1 parameter and is given 0; "),
    ("random()", "random takes at least 1 parameter and is given 0"),
    # Commas inside a literal or a nested call are not counted; a variadic expression takes more.
    ('tokenat("a,b", clamp(max(1, 2, 3), 0, 9), ",") & choose(1, 2, 3) & random(1, 5)', None),
    ("Coin.ImagePointX(0) + Coin.Tween.Progress(\"\") + loopindex", None),
])
def test_an_expression_is_given_the_arguments_its_schema_lists(project, text, said):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text=text))
    if said:
        assert said in out
    else:
        assert out.rstrip().splitlines()[-1].startswith("ok:"), out


def test_functions_call_mapped_is_an_expression_not_a_function(project):
    ok = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(
        text='Functions.CallMapped("map", "key")'))
    assert ok.rstrip().splitlines()[-1].startswith("ok:"), ok
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(
        text='Functions.CallMapped("map")'))
    assert "Functions.CallMapped takes at least 2 parameters and is given 1" in out


def test_plugin_name_in_an_expression_names_the_object(project):
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text="Sprite.Count"))
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


def test_an_invented_functions_object_type_is_refused(project):
    """A model wrote objectTypes/Functions.json with an addon by Scirra of that id; the editor
    reported "Missing addons ... Plugin Functions (Functions) by Scirra (legacy SDK v1)"."""
    edit(project, "project.c3proj", lambda p: p["usedAddons"].append(
        {"type": "plugin", "id": "Functions", "name": "Functions", "author": "Scirra", "bundled": False}))
    (project / "objectTypes" / "Functions.json").write_text(json.dumps(
        {"name": "Functions", "plugin-id": "Functions", "sid": 7, "isGlobal": True}), encoding="utf-8")
    edit(project, "project.c3proj", lambda p: p["objectTypes"]["items"].append("Functions"))
    code, out = check(project)
    assert code == 1, out
    assert "object type Functions has the name of the built-in Functions object" in out
    assert "plugin id 'Functions' is invented" in out and '"functionsName": "Functions"' in out
    assert "warning: no schema for plugin Functions" not in out


def test_an_invented_scirra_behavior_in_used_addons_is_refused(project):
    edit(project, "project.c3proj", lambda p: p["usedAddons"].append(
        {"type": "behavior", "id": "Gravity", "name": "Gravity", "author": "Scirra", "bundled": False}))
    code, out = check(project)
    assert code == 1 and "behavior id 'Gravity' is invented" in out, out


def test_a_deprecated_addon_is_named_so(project):
    """NW.js has no schema, like a third-party addon, but the editor still opens a project with it."""
    edit(project, "project.c3proj", lambda p: p["usedAddons"].append(
        {"type": "plugin", "id": "NodeWebkit", "name": "NW.js", "author": "Scirra", "bundled": False}))
    out = findings(project, lambda t: t.update({"plugin-id": "NodeWebkit"}), "objectTypes/ScoreText.json")
    assert "warning: plugin NodeWebkit (NW.js) is deprecated: Construct 3 no longer offers it" in out
    assert out.rstrip().splitlines()[-1].startswith("ok:"), out


def test_a_deprecated_ace_or_expression_warns_once_at_its_first_use(project):
    """The editor opens a project that uses them, so they are no error, but a new event
    should not. One warning each, at the first use: a model writing from memory repeats
    `rgb`, and a line for every use pushed the project's errors out of the report."""
    def change(s):
        events(s)["add_score"]["actions"] += [
            {"id": "set-minimum-framerate", "objectClass": "System", "sid": 910000000001,
             "parameters": {"minimum-fps": "30"}},
            {"id": "set-eventvar-value", "objectClass": "System", "sid": 910000000002,
             "parameters": {"variable": "score", "value": "rgb(1, 2, 3)"}},
            {"id": "set-eventvar-value", "objectClass": "System", "sid": 910000000003,
             "parameters": {"variable": "score", "value": "rgb(4, 5, 6) + unixtime"}}]
    out = findings(project, change)
    assert out.rstrip().splitlines()[-1].startswith("ok:"), out
    said = warnings(out)
    rgb = [w for w in said if "rgb is a deprecated expression of System" in w]
    assert len(rgb) == 1 and rgb[0].endswith("; used 1 more time after this"), said
    assert any("action set-minimum-framerate of System is deprecated" in w
               and "its parameters are not checked" in w for w in said), said
    assert any("unixtime is a deprecated expression of System" in w for w in said), said
    assert "System: set-minimum-framerate (minimum-fps: 30) [deprecated]" in tool(project, "print_sheet", "Game")[1]


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


def test_object_types_sharing_a_sid_stop_the_editor(project):
    """The editor refuses two object classes with one sid: "object class sid already in use"."""
    coin = json.loads((project / "objectTypes/Coin.json").read_text(encoding="utf-8"))
    out = findings(project, lambda t: t.update(sid=coin["sid"]), "objectTypes/ScoreText.json")
    line = next((x for x in out.splitlines() if "share the sid" in x), "")
    assert "Coin" in line and "ScoreText" in line and "object class sid already in use" in line, out


def test_another_repeated_sid_is_a_warning(project):
    """The editor opens a project whose events, instances, layers or animations repeat a sid."""
    def repeat(sheet):
        rows = [ev for ev in sheet["events"] if "sid" in ev]
        rows[1]["sid"] = rows[0]["sid"]
    out = findings(project, repeat)
    assert out.splitlines()[-1].startswith("ok:"), out
    assert [w for w in warnings(out) if "duplicate sids" in w], out


def test_instances_sharing_a_uid_are_named_with_what_the_editor_does(project):
    def repeat(lay):
        insts = [i for layer in lay["layers"] for i in layer["instances"]]
        insts[1]["uid"] = insts[0]["uid"]
    out = findings(project, repeat, "layouts/Game.json")
    assert "duplicate uids" in out and "gives all but one of them another uid" in out, out


@pytest.mark.parametrize("text, warned", [
    ('find("^", str(Coin.X))', True),
    ('findCase("""", str(Coin.X)) + 1', True),
    ('find(str(Coin.X), "^")', False),
    ('find("^", "a^")', False),
    ('find("ab", str(Coin.X))', False),
    ('"find(""^"", x)"', False),
])
def test_find_with_a_one_character_text_first_is_named(project, text, warned):
    """find(text, find) searches its first argument: a one-character literal there is the needle."""
    out = findings(project, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text=text))
    said = [w for w in warnings(out) if "searches the one-character text" in w and "takes the text to search first" in w]
    assert bool(said) == warned, out


def test_a_wait_for_a_signal_nothing_raises_is_named(project):
    wait = {"id": "wait-for-signal", "objectClass": "System", "sid": 1, "parameters": {"tag": '"go"'}}
    out = findings(project, lambda s: s["events"].append(block([cond("on-start-of-layout")], [wait])))
    assert [w for w in warnings(out) if 'raises "go", so this Wait for signal never ends' in w], out


FULLSCREEN = {"id": "request-fullscreen", "objectClass": "Browser", "sid": 5,
              "parameters": {"mode": "stretch-letterbox-scale", "navigation-ui": "auto"}}
TAPPED = cond("on-touched-object", "Touch", {"object": "Coin", "type": "start"})


@pytest.mark.parametrize("event, warned", [
    (block([cond("on-start-of-layout")], [FULLSCREEN]), True),
    (block([TAPPED], [], [block([cond("every-tick")], [FULLSCREEN])]), False),
    ({"functionName": "GoFullscreen", "functionDescription": "", "functionCategory": "", "functionReturnType": "none",
      "functionCopyPicked": False, "functionIsAsync": False, "eventType": "function-block", "sid": 6,
      "functionParameters": [], "conditions": [], "actions": [FULLSCREEN]}, False),
])
def test_an_action_the_browser_allows_only_after_input_is_named_outside_it(project, event, warned):
    """The manual asks for Request fullscreen in a user input trigger; a function may be called from one."""
    (project / "objectTypes" / "Browser.json").write_text(json.dumps({
        "name": "Browser", "plugin-id": "Browser", "sid": 3,
        "singleglobal-inst": {"type": "Browser", "properties": {}, "uid": 900, "sid": 4, "tags": ""}}), encoding="utf-8")

    def project_file(p):
        p["objectTypes"]["items"].append("Browser")
        p["usedAddons"].append({"type": "plugin", "id": "Browser", "name": "Browser", "author": "Scirra", "bundled": False})
    edit(project, "project.c3proj", project_file)
    out = findings(project, lambda s: s["events"].append(event))
    said = [w for w in warnings(out) if "the browser refuses it there" in w and "plugin-reference/browser.md" in w]
    assert bool(said) == warned and out.splitlines()[-1].startswith("ok:"), out


def add_addon(project, kind: str, addon_id: str, name: str) -> None:
    edit(project, "project.c3proj", lambda p: p["usedAddons"].append(
        {"type": kind, "id": addon_id, "name": name, "author": "Scirra", "bundled": False}))


def pathfinding_coin(project, obstacles: str = "solids") -> None:
    """Coin gets Pathfinding, taking its obstacles from Solids, and the Backdrop, which no event changes, Solid."""
    edit(project, "objectTypes/Coin.json", lambda t: t["behaviorTypes"].append(
        {"behaviorId": "Pathfinding", "name": "Pathfinding", "sid": 11}))
    edit(project, "layouts/Objects.json", lambda d: d["layers"][0]["instances"][0]["behaviors"].update(
        Pathfinding={"properties": {"obstacles": obstacles}}))
    edit(project, "objectTypes/Backdrop.json", lambda t: t["behaviorTypes"].append(
        {"behaviorId": "solid", "name": "Solid", "sid": 12}))
    edit(project, "layouts/Game.json", lambda d: d["layers"][0]["instances"][0].setdefault("behaviors", {}).update(
        Solid={"properties": {}}))
    add_addon(project, "behavior", "Pathfinding", "Pathfinding")
    add_addon(project, "behavior", "solid", "Solid")


FIND_PATH = {"id": "find-path", "objectClass": "Coin", "sid": 13, "behaviorType": "Pathfinding",
             "parameters": {"x": "100", "y": "100"}}
MOVE_ALONG = {"id": "move-along-path", "objectClass": "Coin", "sid": 14, "behaviorType": "Pathfinding"}
WAIT_FOR_PREVIOUS = {"id": "wait-for-previous-actions", "objectClass": "System", "sid": 15}
DESTROY_WALL = {"id": "destroy", "objectClass": "Backdrop", "sid": 16}
REGENERATE_MAP = {"id": "regenerate-obstacle-map", "objectClass": "Coin", "sid": 17, "behaviorType": "Pathfinding"}
NODE_X = {"id": "set-x", "objectClass": "Coin", "sid": 18, "parameters": {"x": "Coin.Pathfinding.NodeXAt(0)"}}
START = cond("on-start-of-layout")


@pytest.mark.parametrize("event, said", [
    (block([START], [FIND_PATH, MOVE_ALONG]), "reads the path a Find path above it in the same actions has only started"),
    (block([START], [FIND_PATH, NODE_X]), "reads the path a Find path above it in the same actions has only started"),
    (block([START], [FIND_PATH, WAIT_FOR_PREVIOUS, MOVE_ALONG]), None),
    (block([cond("every-tick")], [FIND_PATH]), "Find path runs every tick"),
    (block([cond("every-x-seconds", params={"interval-seconds": "1"})], [FIND_PATH]), None),
    (block([START], [], [block([cond("every-tick")], [FIND_PATH])]), None),
    (block([START], [DESTROY_WALL]), "this changes a Solid while Pathfinding takes its obstacles from Solids"),
    (block([START], [DESTROY_WALL, REGENERATE_MAP]), None),
])
def test_pathfinding_on_a_map_or_a_path_that_is_not_there_yet_is_named(project, event, said):
    """The manual: the obstacle map is built once at startup, a path is there only after On path found,
    and pathfinding every tick takes extremely high CPU (behavior-reference/pathfinding.md)."""
    pathfinding_coin(project)
    out = findings(project, lambda s: s["events"].append(event))
    said_lines = [w for w in warnings(out) if "behavior-reference/pathfinding.md" in w]
    assert out.splitlines()[-1].startswith("ok:"), out
    assert (said in said_lines[0] if said else not said_lines) and len(said_lines) <= 1, out


def test_a_solid_changed_beside_custom_obstacles_is_not_named(project):
    pathfinding_coin(project, obstacles="custom")
    out = findings(project, lambda s: s["events"].append(block([START], [DESTROY_WALL])))
    assert not [w for w in warnings(out) if "changes a Solid" in w], out


def function(name: str, sid: int, actions: list, children: list | None = None, params: list | None = None) -> dict:
    return {"functionName": name, "functionDescription": "", "functionCategory": "", "functionReturnType": "none",
            "functionCopyPicked": False, "functionIsAsync": False, "eventType": "function-block", "sid": sid,
            "functionParameters": params or [], "conditions": [], "actions": actions,
            **({"children": children} if children else {})}


def call(name: str, sid: int, *params: str) -> dict:
    return {"callFunction": name, "sid": sid, "parameters": list(params)}


CREATE_COIN = {"id": "create-object", "objectClass": "System", "sid": 31, "parameters": {
    "object-to-create": "Coin", "layer": '"Game"', "x": "0", "y": "0", "create-hierarchy": False,
    "template-name": '""'}}
COIN_X = {"id": "set-x", "objectClass": "Coin", "sid": 32, "parameters": {"x": "loopindex * 40"}}
UID_PARAM = [{"name": "uid", "type": "number", "initialValue": "0", "comment": "", "sid": 33}]
# DealCoins creates Coins through MakeCoin, in a loop, as a card game draws its hand.
DEAL = [function("MakeCoin", 34, [CREATE_COIN]),
        function("DealCoins", 35, [], [block([cond("repeat", params={"count": "3"})], [call("MakeCoin", 36)])])]
LAY_OUT = function("LayOutCoins", 37, [], [block([cond("for-each", params={"object": "Coin"})], [COIN_X])])
LAY_OUT_BY_UID = function("LayOutCoin", 38, [], [block([cond("pick-by-unique-id", "Coin", {"unique-id": "uid"}),
                                                        cond("for-each", params={"object": "Coin"})], [COIN_X])],
                          UID_PARAM)
WAIT_0 = {"id": "wait", "objectClass": "System", "sid": 39, "parameters": {"seconds": "0", "use-timescale": True}}


@pytest.mark.parametrize("rows, said", [
    # a turn deals coins, then lays them out: the For each runs before the new coins join
    ([*DEAL, LAY_OUT, function("NewTurn", 40, [call("DealCoins", 41), call("LayOutCoins", 42)])],
     "NewTurn action 2: LayOutCoins picks Coin (System:for-each in sheet Game event"),
    ([LAY_OUT, block([START], [CREATE_COIN, call("LayOutCoins", 42)])], "action 1 creates Coin earlier"),
    # through the functions it calls, with a cycle among them
    ([*DEAL, LAY_OUT, function("Turn", 43, [call("DealCoins", 41), call("Refresh", 44)]),
      function("Refresh", 45, [call("LayOutCoins", 42), call("Refresh", 46)])],
     "Refresh picks Coin through LayOutCoins"),
    ([*DEAL, LAY_OUT_BY_UID, function("NewTurn", 40, [call("DealCoins", 41), call("LayOutCoin", 42, "0")])], None),
    ([*DEAL, LAY_OUT, block([START], [call("DealCoins", 41)]), block([START], [call("LayOutCoins", 42)])], None),
    ([*DEAL, LAY_OUT, block([START], [call("DealCoins", 41), WAIT_0, call("LayOutCoins", 42)])], None),
    ([LAY_OUT, block([START], [call("LayOutCoins", 42), CREATE_COIN])], None),
])
def test_a_function_that_picks_what_an_earlier_call_created_is_named(project, rows, said):
    """A created instance joins the others when the top-level event or trigger that created it ends; until then
    only Pick by unique ID finds it outside its own event (prompts/pitfalls/creating-objects.md)."""
    out = findings(project, lambda s: s["events"].extend(rows))
    said_lines = [w for w in warnings(out) if "pitfalls/creating-objects.md" in w]
    assert out.splitlines()[-1].startswith("ok:"), out
    assert (said in said_lines[0] if said else not said_lines) and len(said_lines) <= 1, out


def sprite_font_label(project, text: str, bbcode: bool = True, properties: dict | None = None) -> None:
    """A Sprite Font Label on the Objects layout, drawing capitals, digits and the space, or with `properties`;
    its image is the backdrop's."""
    backdrop = json.loads((project / "objectTypes" / "Backdrop.json").read_text(encoding="utf-8"))
    (project / "images" / "label.png").write_bytes((project / "images" / "backdrop.png").read_bytes())
    (project / "objectTypes" / "Label.json").write_text(json.dumps({
        "name": "Label", "plugin-id": "Spritefont2", "sid": 21, "instanceVariables": [], "behaviorTypes": [],
        "effectTypes": [], "image": {**backdrop["image"], "imageSpriteId": 25}}), encoding="utf-8")
    edit(project, "project.c3proj", lambda p: p["objectTypes"]["items"].append("Label"))
    add_addon(project, "plugin", "Spritefont2", "Sprite font")

    def place(d):
        inst = json.loads(json.dumps(d["layers"][0]["instances"][0]))
        inst.update(type="Label", uid=22, sid=23, instanceVariables={}, behaviors={}, properties=properties or {
            "text": text, "character-set": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ", "enable-bbcode": bbcode,
            "character-width": 8, "character-height": 8})
        d["layers"][0]["instances"].append(inst)
    edit(project, "layouts/Objects.json", place)


def set_label(text: str) -> dict:
    return {"id": "set-text", "objectClass": "Label", "sid": 24, "parameters": {"text": text}}


@pytest.mark.parametrize("layout_text, bbcode, action, said", [
    ("SCORE 0", True, None, None),
    ("SCORE #0", True, None, "'#' is not in the Character set of the Sprite Font Label"),
    ("[color=#ff0000]SCORE[/color] 0", True, None, None),
    ("[color=#ff0000]SCORE[/color] 0", False, None, "'[', 'c', 'o', 'l', 'r', '=', '#', 'f', ']', '/' are not in"),
    ("SCORE", True, set_label('"BEST: " & Score'), "':' is not in the Character set"),
    ("SCORE", True, set_label('"BEST " & Score & int("1.5")'), None),
    ("SCORE", True, set_label('Score = 0 ? "NONE" : "SOME"'), None),
])
def test_text_a_sprite_font_cannot_draw_is_named(project, layout_text, bbcode, action, said):
    """The manual: a character outside the Character set is drawn as an empty space
    (plugin-reference/sprite-font.md). Only literals joined at the top level are text that shows."""
    sprite_font_label(project, layout_text, bbcode)
    out = findings(project, lambda s: action and s["events"].append(block([START], [action])))
    said_lines = [w for w in warnings(out) if "plugin-reference/sprite-font.md" in w]
    assert out.splitlines()[-1].startswith("ok:"), out
    assert (said in said_lines[0] if said else not said_lines) and len(said_lines) <= 1, out


@pytest.mark.parametrize("properties, said", [
    ({"text": "Score: 0"}, None),
    ({"text": "Score ★ 0"}, "'★' is not in the Character set of the Sprite Font Label"),
    ({"text": "Score {0}"}, "'{', '}' are not in the Character set"),
])
def test_a_sprite_font_without_its_character_set_reads_the_editors(project, properties, said):
    """The r495.2 editor fills a left-out Character set, cell size and Enable BBCode with its defaults (asked of
    the editor, 2026-10-03), so the text is checked against them and the missing properties are named."""
    sprite_font_label(project, "", properties=properties)
    out = findings(project, lambda s: None)
    said_lines = [w for w in warnings(out) if "plugin-reference/sprite-font.md" in w]
    assert out.splitlines()[-1].startswith("ok:"), out
    assert (said in said_lines[0] if said else not said_lines) and len(said_lines) <= 1, out
    named = [w for w in warnings(out) if "Label instance has no character-set, character-width, character-height" in w]
    assert len(named) == 1 and '"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789' in named[0], out


def test_a_sprite_font_with_its_character_set_is_not_named_for_it(project):
    sprite_font_label(project, "SCORE 0")
    assert not [w for w in warnings(findings(project, lambda s: None)) if "instance has no character-set" in w]


def test_a_sprite_font_without_enable_bbcode_draws_the_tags(project):
    """Enable BBCode left out reads as off in the r495.2 editor, so a tag is text the font draws."""
    sprite_font_label(project, "", properties={
        "text": "[b]SCORE[/b]", "character-set": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ",
        "character-width": 8, "character-height": 8})
    said = [w for w in warnings(findings(project, lambda s: None)) if "plugin-reference/sprite-font.md" in w]
    assert len(said) == 1 and "'[', 'b', ']', '/' are not in" in said[0], said


def set_effect(obj: str = "Coin", name: str = "AdjustHSL") -> dict:
    return {"id": "set-effect-parameter", "objectClass": obj, "sid": 31,
            "parameters": {"effect": f'"{name}"', "parameter-index": "2", "value": "100"}}


@pytest.mark.parametrize("coin_effects, action, said", [
    ([], set_effect(), "Coin has no effect named 'AdjustHSL' (it has none)"),
    (["AdjustHSL"], set_effect(), None),
    (["AdjustHSL"], set_effect(name="adjusthsl"), None),
    (["AdjustHSL"], set_effect(name="Tint"), "(it has AdjustHSL)"),
    ([], {"id": "set-layout-effect-parameter", "objectClass": "System", "sid": 32,
          "parameters": {"effect": '"AdjustHSL"', "parameter-index": "2", "value": "100"}},
     "no layout has an effect named 'AdjustHSL'"),
    ([], {"id": "set-layer-effect-enabled", "objectClass": "System", "sid": 33,
          "parameters": {"layer": '"Objects"', "mode": "enable", "effect": '"AdjustHSL"'}},
     "the layer Objects has no effect named 'AdjustHSL'"),
])
def test_an_effect_action_naming_an_effect_its_target_lacks_is_named(project, coin_effects, action, said):
    """A Set effect parameter naming an effect that is not there raises no error in a preview, and the
    next action runs (docs/decisions/checker-editor-load-rules.md)."""
    if coin_effects:
        edit(project, "objectTypes/Coin.json", lambda t: t["effectTypes"].extend(
            {"effectId": "hsladjust", "name": n} for n in coin_effects))
        add_addon(project, "effect", "hsladjust", "Adjust HSL")
    out = findings(project, lambda s: s["events"].append(block([START], [action])))
    said_lines = [w for w in warnings(out) if "so the action runs and changes nothing" in w]
    assert out.splitlines()[-1].startswith("ok:"), out
    assert (said in said_lines[0] if said else not said_lines) and len(said_lines) <= 1, out


def test_a_script_that_reads_a_parameter_bare_is_named(project):
    """A preview of such a script stopped with "ReferenceError: string is not defined" (2026-10-03)."""
    func = {"functionName": "Hex", "functionDescription": "", "functionCategory": "", "functionReturnType": "none",
            "functionCopyPicked": False, "functionIsAsync": False, "eventType": "function-block", "sid": 2,
            "functionParameters": [{"name": "text", "type": "string", "initialValue": "", "comment": "", "sid": 3}],
            "conditions": [], "actions": [{"type": "script", "language": "javascript",
                                           "script": ["console.log(parseInt(text, 16), localVars.text);"]}]}
    out = findings(project, lambda s: s["events"].append(func))
    assert [w for w in warnings(out) if "reads text as a bare name" in w and "localVars.text" in w], out


@pytest.mark.parametrize("returns, use, said", [
    ("number", {"callFunction": "Two", "sid": 4, "parameters": []}, "function 'Two' has wrong return type"),
    ("none", {"id": "set-text", "objectClass": "ScoreText", "sid": 4, "parameters": {"text": "Functions.Two"}},
     "has a return type of 'None' so cannot be used as an expression"),
])
def test_a_function_is_reached_as_its_return_type_says(project, returns, use, said):
    func = {"functionName": "Two", "functionDescription": "", "functionCategory": "", "functionReturnType": returns,
            "functionCopyPicked": False, "functionIsAsync": False, "functionParameters": [],
            "eventType": "function-block", "conditions": [], "actions": [], "sid": 2}
    out = findings(project, lambda s: s["events"].extend([func, block([cond("on-start-of-layout")], [use])]))
    assert said in out, out


@pytest.mark.parametrize("text, said", [
    ("", "Empty expression"), ('"Score: ', "String missing finishing"), ("1 \\ 2", "Unknown character"),
    ('"a\\b"', None),
])
def test_text_literals_as_the_editor_parses_them(project, text, said):
    act = {"id": "set-text", "objectClass": "ScoreText", "sid": 4, "parameters": {"text": text}}
    out = findings(project, lambda s: s["events"].append(block([cond("on-start-of-layout")], [act])))
    assert (said in out) if said else out.splitlines()[-1].startswith("ok:"), out


@pytest.mark.parametrize("family", ["coin", "Functions"])
def test_a_family_named_like_another_object_class_is_refused(project, family):
    (project / "families").mkdir(exist_ok=True)
    (project / "families" / f"{family}.json").write_text(json.dumps(
        {"name": family, "plugin-id": "Sprite", "sid": 5, "instanceVariables": [], "behaviorTypes": [],
         "effectTypes": [], "members": ["Coin"]}), encoding="utf-8")
    out = findings(project, lambda p: p.update(families={"items": [family], "subfolders": []}), "project.c3proj")
    assert f"object class name '{family}' already used" in out, out


def test_an_object_type_listed_twice_is_refused(project):
    out = findings(project, lambda p: p["objectTypes"]["items"].append("Coin"), "project.c3proj")
    assert "object type name 'Coin' already used" in out, out


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


def test_an_instance_variable_type_outside_the_three_is_named(project):
    """The editor's Text type is written "string". A type "text" used to stop the checker
    with `missing key 'text'`, a sentence about the wrong thing."""
    def change(t):
        t["instanceVariables"][1]["type"] = "text"
    out = findings(project, change, "objectTypes/Coin.json")
    assert "stopped at" not in out
    assert ("object type Coin: instance variable kind: type 'text' is not number, string or boolean; "
            "the editor's Text type is written \"string\"") in out


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
