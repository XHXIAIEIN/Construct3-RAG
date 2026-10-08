"""edit_sheet.py: changing a sheet from a plan."""
import codecs
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import (EXAMPLES, NO_EXAMPLES, REPO, SKILL, SHEET, run, tool, check, edit, events,
                                 every_event, collect_tween, plan)

sys.path.insert(0, str(SKILL / "scripts"))
from c3project import NUMBERED  # noqa: E402

# What a copy of an example leaves out: the scripts read no image, sound or font.
MEDIA = ("*.png", "*.jpg", "*.webp", "*.webm", "*.ogg", "*.m4a", "*.mp3", "*.wav", "*.woff", "*.woff2", "*.ttf")


def source_tool(root: Path, name: str, *args: str) -> tuple[int, str]:
    """A script of the skill's source run on a project without the skill installed, such as a copy of an example."""
    return run(root, SKILL / "scripts" / f"{name}.py", "--rag", str(REPO), *args)


def printed(root: Path) -> str:
    return tool(root, "print_sheet", "Game")[1]


def sheet_on_disk(root: Path) -> dict:
    return json.loads((root / SHEET).read_text(encoding="utf-8"))


def all_events(root: Path) -> list[dict]:
    return list(every_event(sheet_on_disk(root)["events"]))


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
    assert out.splitlines()[-1].startswith("ok:") and "open_in_editor" not in out     # the closing check names it
    sheet = printed(project)
    assert ("     global number beat = 0\n         // The round being played, from 0; a global keeps it across the "
            "restart\n     global number deal = 0\n         // The grid cell this round's first coin lands on; "
            "the others step from it\n     global number timeLeft = 30\n   1 group Setup") in sheet
    assert '-> System: Set deal to floor(random(15))\n           -> ScoreText: Set text to "Time: " & timeLeft' in sheet
    assert "   4       (runs with its parent)\n               -> Coin: Set scale to 1.5" in sheet
    assert "     // Countdown.\n  11 group Timer\n       // Count down.\n  12   System: Every 1 seconds" in sheet
    assert check(project)[0] == 0


def test_plan_writes_what_the_editor_writes(project):
    """Keys the editor always writes are filled in, in its order, every new entry has a sid, and the file is tabs and LF."""
    assert plan(project, {"into": 0, "events": [{"eventType": "variable", "name": "lives"}, TIMER]})[0] != 0   # timeLeft is not declared
    code, out = plan(project, {"into": 0, "events": [{"eventType": "variable", "name": "timeLeft", "type": "number"}, TIMER]})
    assert code == 0, out
    rows = all_events(project)
    variable = next(ev for ev in rows if ev.get("name") == "timeLeft")
    assert list(variable) == ["eventType", "name", "type", "initialValue", "comment", "isStatic", "isConstant", "sid"]
    assert (variable["initialValue"], variable["isConstant"]) == ("0", False)
    group = next(ev for ev in rows if ev.get("title") == "Timer")
    assert list(group) == ["eventType", "disabled", "title", "description", "isActiveOnStart", "children", "sid"]
    condition = next(e for e in group["children"] if e["eventType"] == "block")["conditions"][0]
    assert list(condition) == ["id", "objectClass", "sid", "parameters"] and len(str(condition["sid"])) == 15
    raw = (project / SHEET).read_bytes()
    assert b"\r" not in raw and not raw.endswith(b"\n") and b'\n\t\t{\n\t\t\t"eventType"' in raw


def test_files_with_a_byte_order_mark_are_read_and_a_sheet_is_written_without_it(project):
    """The editor opens a file that starts with one and writes none."""
    for name in ("project.c3proj", SHEET):
        (project / name).write_bytes(codecs.BOM_UTF8 + (project / name).read_bytes())
    assert check(project)[0] == 0
    assert "   1 group Setup" in printed(project)
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]})
    assert code == 0 and "Traceback" not in out, out
    assert "started with a byte order mark" in out
    assert not (project / SHEET).read_bytes().startswith(codecs.BOM_UTF8)


def test_a_sheet_keeps_the_name_it_has_on_disk(project):
    """project.c3proj lists Game; on a case-insensitive file system game.json is its file and stays game.json."""
    (project / SHEET).rename(project / "eventSheets" / "game.json")
    if not (project / SHEET).exists():
        pytest.skip("this file system tells Game.json from game.json")
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]})
    assert code == 0, out
    assert "game.json" in os.listdir(project / "eventSheets")


def test_a_loop_written_as_an_action_says_where_it_goes(project):
    """Told only that For is a condition, a small model rewrote its loops away instead of moving them (2026-10-04)."""
    code, out = plan(project, {"event": 2, "add-actions": [{"id": "for", "objectClass": "System", "parameters": {
        "name": '"i"', "start-index": "0", "end-index": "3"}}]})
    assert code == 1
    assert 'for is one of its conditions, not its actions: move it into the "conditions" of this event' in out
    assert "a loop is a condition, and the actions of its event run once per pass" in out


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


SIDE_AND_PHASE = {"before": 1, "events": [{"eventType": "variable", "name": "side", "initialValue": "1"},
                                          {"eventType": "variable", "name": "phase", "initialValue": "0"}]}
FLIP_SIDE = {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "side", "value": "3 - side"}}
PHASE_IS_1 = {"id": "compare-eventvar", "objectClass": "System", "parameters": {"variable": "phase", "comparison": 0,
                                                                               "value": "1"}}
TOUCHED_COIN = {"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "Coin", "type": "start"}}


def test_plan_refuses_a_new_event_that_flips_a_variable_on_every_tick(project):
    """A new event that flips a variable on every tick is refused, and the first line says where the flip goes.
    The same flip under a tap goes through; under Trigger once and tests of values it is a warning."""
    before = (project / SHEET).read_bytes()
    shown = {"eventType": "block", "conditions": [PHASE_IS_1],
             "actions": [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": '"Moving"'}}]}
    swap = {"eventType": "block", "conditions": [{"id": "else", "objectClass": "System"}], "actions": [FLIP_SIDE]}
    code, out = plan(project, SIDE_AND_PHASE, {"into": 0, "events": [
        {"eventType": "comment", "text": "A move is playing."}, shown,
        {"eventType": "comment", "text": "Otherwise the other side plays."}, swap]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert re.match(r"operation 2: sheet Game event \d+ \(sid \d+\) action 1: Set side to 3 - side flips side on "
                    r"every tick, so an input can read either value", out), out
    assert ('Move the flip into the event whose trigger causes the change, or into a sub-event of it. Trigger once '
            'does not fix it') in out.splitlines()[0], out
    tap = '{"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "<Object>", "type": "start"}}'
    assert tap in out.splitlines()[0], out
    assert out.splitlines()[-1] == "the plan adds 1 problem(s) to the project; nothing was written"
    tapped = {"eventType": "block", "conditions": [TOUCHED_COIN], "actions": [FLIP_SIDE]}
    code, out = plan(project, SIDE_AND_PHASE, {"into": 0, "events": [
        {"eventType": "comment", "text": "A tapped coin passes the play to the other side."}, tapped]},
        flags=("--dry-run",))
    assert code == 0 and "warning:" not in out, out
    swap["conditions"].append({"id": "trigger-once-while-true", "objectClass": "System"})
    code, out = plan(project, SIDE_AND_PHASE, {"into": 0, "events": [
        {"eventType": "comment", "text": "A move is playing."}, shown,
        {"eventType": "comment", "text": "Otherwise the other side plays."}, swap]}, flags=("--dry-run",))
    assert code == 0 and [w for w in out.splitlines() if w.startswith("warning:") and "under Trigger once flips" in w], out


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
                     {"event": 6, "action": 10, "set": {"behaviorType": "Tween"}},
                     {"event": 8, "action": 2, "set": {"id": "set-text"}},
                     {"move": 7, "after": 6})
    assert code == 0 and out.splitlines()[-1].startswith("ok:"), out
    raw = sheet_on_disk(project)
    sheet = events(raw)
    assert "isInverted" not in sheet["setup"]["conditions"][0], "the editor writes isInverted only when it is true"
    assert list(collect_tween(raw))[:4] == ["id", "objectClass", "sid", "behaviorType"]
    assert "Coin: On Tween \"collect\" finished\n         -> Functions: Call AddScore(Coin.value)" in printed(project)


def test_plan_sets_the_values_of_an_event_and_removes_an_action(project):
    code, out = plan(project, {"event": 8, "set": {"title": "Over", "isActiveOnStart": False}},
                     {"event": 9, "action": 2, "remove": True})
    assert code == 0, out
    sheet = printed(project)
    assert "   8 group Over (inactive on start)" in sheet and "Wait 1 seconds" not in sheet
    code, out = plan(project, {"event": 9, "set": {"actions": []}})
    assert code == 1 and "\"set\" changes values, not 'actions'" in out


def test_plan_shows_a_condition_or_action_it_disables_as_disabled(project):
    code, out = plan(project, {"event": 5, "condition": 2, "set": {"disabled": True}},
                     {"event": 7, "action": 1, "set": {"disabled": True}})
    assert code == 0, out
    assert "       Coin: NOT Is any Tween playing [condition disabled]\n" in out
    assert "         -> System: Add points to score [action disabled]\n" in out
    assert events(sheet_on_disk(project))["input"]["conditions"][1]["disabled"] is True


def test_plan_names_an_older_form_of_a_text_it_left_alone(project):
    """Eval runs changed the score text at the start and left the one in AddScore, event 7, as it was."""
    code, out = plan(project, {"event": 2, "action": 2, "set": {"parameters": {"text": '"Score: 0"'}}},
                     {"event": 7, "action": 2, "set": {"parameters": {"text": '"Score: " & score'}}})
    assert code == 0, out                               # the labelled score those runs started from
    both = '"Score: " & score & "  Time: " & round(time)'
    code, out = plan(project, {"event": 2, "action": 2, "set": {"parameters": {"text": both}}}, flags=("--dry-run",))
    assert code == 0, out
    note = [line for line in out.splitlines() if line.startswith("note: event")]
    assert note == ['note: event 7 action 2 (ScoreText set-text) still has text "Score: " & score, which this plan '
                    f'writes elsewhere as {both}; if both show the same thing, change it too: '
                    + json.dumps({"event": 7, "line": "function AddScore(points: number)", "action": 2,
                                  "set": {"parameters": {"text": both}}})], out
    code, out = plan(project, {"event": 2, "action": 2, "set": {"parameters": {"text": both}}},
                     {"event": 7, "action": 2, "set": {"parameters": {"text": both}}}, flags=("--dry-run",))
    assert code == 0 and "note: event" not in out, out
    code, out = plan(project, {"event": 2, "action": 2, "set": {"parameters": {"text": '"Tap the coins"'}}},
                     flags=("--dry-run",))
    assert code == 0 and "note: event" not in out, out     # another text, not an older form of it
    code, out = plan(project, {"event": 2, "action": 2, "set": {"parameters": {"text": '"Score: 0  Time: 30"'}}},
                     {"event": 5, "add-actions": [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": both}}]},
                     flags=("--dry-run",))
    assert code == 0 and [line for line in out.splitlines() if line.startswith("note: event")] == note, out


def test_set_takes_no_key_of_the_plans_own_making(project):
    """Two eval runs wrote {"event": 2, "set": {"inverted": false}}: the key stayed in the sheet and changed nothing."""
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"event": 2, "set": {"inverted": False}})
    assert code == 1 and "'inverted' is not a value of a block, which has: bookmark, disabled, isOrBlock" in out
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
    restart["actions"] = [a for a in restart["actions"] if a["id"] != "wait"]   # no wait before the restart
    sids = {c["sid"] for c in restart["conditions"]}
    code, out = plan(project, {"replace": 9, "events": [restart]}, {"move": 7, "before": 6}, {"remove": 4})
    assert code == 0, out
    sheet = printed(project)
    assert sheet.index("function AddScore") < sheet.index("custom action Coin.Collect") and "group Input" not in sheet
    assert '% tokencount(ROUND_COINS, ",")\n           -> System: Restart layout' in sheet
    assert sids <= {c.get("sid") for ev in all_events(project) for c in ev.get("conditions", [])}, "a replaced event keeps the sids it is given"


def put_back(root: Path, sheet: str, path: Path, n: int, script=tool) -> tuple[bytes, str]:
    """Event n of a sheet printed with --show and replaced by what was printed: the file after, and what the plan said."""
    code, shown = script(root, "print_sheet", sheet, "--show", str(n), "--limit", "0")
    assert code == 0, shown
    (root / "plan.json").write_text(json.dumps([{"replace": n, "events": [json.loads(shown)]}]), encoding="utf-8")
    code, out = script(root, "edit_sheet", sheet, "plan.json")
    assert code == 0, out
    return path.read_bytes(), out


def test_an_event_put_back_as_print_sheet_shows_it_leaves_the_sheet_byte_for_byte(project):
    """--show N, then a plan that replaces N with what it printed, changes nothing: for every event, sub-events too."""
    for path in sorted((project / "eventSheets").glob("*.json")):
        before = path.read_bytes()
        sheet = json.loads(before)
        count = sum(ev["eventType"] in NUMBERED for ev in every_event(sheet["events"]))
        assert count > 1
        for n in range(1, count + 1):
            after, out = put_back(project, sheet["name"], path, n)
            assert after == before, f"{sheet['name']} event {n}: {out}"
            assert out.splitlines()[0].endswith(", 0 new sids"), out


# One event of an official example for each way a round trip changed a sheet, found by
# evals/sweep_round_trip.py, which puts back every event of every example.
@pytest.mark.skipif(not EXAMPLES.is_dir(), reason=NO_EXAMPLES)
@pytest.mark.parametrize("example, file, n", [
    pytest.param("date-time", "event sheet 1.json", 3, id="a function saved before functionCopyPicked"),
    pytest.param("high-tech-vision", "Events.json", 45, id="functionCopyPicked after functionName"),
    pytest.param("eventide", "EventsEnemy.json", 40, id="a bookmark, which the editor writes first"),
    pytest.param("pair-of-knights", "Events.json", 38, id="a sid twice in one event"),
])
def test_an_event_of_an_official_example_put_back_leaves_its_sheet_byte_for_byte(tmp_path, example, file, n):
    root = tmp_path / example
    shutil.copytree(EXAMPLES / example, root, ignore=shutil.ignore_patterns(*MEDIA))
    path = root / "eventSheets" / file
    before = path.read_bytes().replace(b"\r\n", b"\n")      # LF as the examples' repository stores it
    path.write_bytes(before)
    after, out = put_back(root, json.loads(before)["name"], path, n, script=source_tool)
    assert after == before, out


def test_removing_an_event_names_the_sub_events_that_go_with_it(project):
    # A model removed a trigger with no actions as empty; the summary's event count alone did not stop it.
    code, out = plan(project, {"remove": 4})
    assert code == 0, out
    assert re.search(r"-- event 4 removed with its sub-events? 5(-\d+)?, \d+ actions? in all", out), out


def test_an_event_replaced_by_one_without_a_sid_keeps_its_own(project):
    was = events(sheet_on_disk(project))["restart_block"]["sid"]
    code, out = plan(project, {"replace": 9, "events": [{"eventType": "block", "conditions": [], "actions": [
        {"id": "restart-layout", "objectClass": "System"}]}]})
    assert code == 0, out
    assert events(sheet_on_disk(project))["restart_block"]["sid"] == was


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
    assert plan(project, {"before": 9, "events": [{"eventType": "comment", "text": "All coins gone"}]})[0] == 0
    code, out = plan(project, {"before": 9, "events": [{"eventType": "block", "conditions": [], "actions": []}]})
    assert code == 0, out
    assert ("   9   (every tick)\n       // All coins gone\n       // Start the next round when the last coin is gone\n"
            "  10   System: Coin.Count = 0") in printed(project)


def test_a_sid_the_project_uses_is_replaced(project):
    taken = events(sheet_on_disk(project))["restart"]["sid"]
    code, out = plan(project, {"into": 0, "events": [{"eventType": "block", "conditions": [], "actions": [], "sid": taken}]})
    assert code == 0 and "1 new sids" in out.splitlines()[0]
    sids = [ev["sid"] for ev in all_events(project) if "sid" in ev]
    assert len(sids) == len(set(sids))


def test_dry_run_checks_and_shows_and_writes_nothing(project):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]}, flags=("--dry-run",))
    assert code == 0 and (project / SHEET).read_bytes() == before
    assert "global number timeLeft = 0" in out and out.splitlines()[-1] == "dry run: nothing was written"
    assert "open_in_editor" not in out     # nothing to open yet


@pytest.mark.parametrize("operation, said", [
    ({"after": 40, "events": [TIMER]}, "40 is not an event of the sheet, which has 9"),
    ({"after": 8}, 'needs "events"'),
    ({"after": 8, "before": 2, "events": [TIMER]}, "an operation is one of"),
    ({"after": 8, "event": [TIMER]}, "an operation is one of"),
    ({"after": 8, "events": [{"eventType": "group"}]}, "a group needs 'title'"),
    ({"after": 8, "events": [{"conditions": [], "actions": []}]}, "An event with conditions and actions is a 'block'"),
    ({"after": 8, "events": [{**TIMER, "subEvents": [TIMER]}]}, "'subEvents' is not a key of a group"),
    ({"after": 8, "events": [{**TIMER, "sub-events": [TIMER]}]}, "sub-events are its 'children'"),
    ({"event": 2, "add-actions": [{"objectClass": "Coin"}]}, "has no 'id'"),
    ({"event": 2, "add-actions": [{**SET_TIME, "params": SET_TIME["parameters"]}]},
     "'params' is not a key of a condition or action"),
    ({"event": 2, "add-actions": [{"id": "set-text", "objectClass": "ScoreText", "params": {"text": '""'}}]},
     "closest: parameters; the editor would drop it with its value"),
    ({"event": 2, "add-conditions": [{"id": "is-playing", "objectClass": "Coin", "behavior-type": "Tween",
                                      "parameters": {"tag": '"t"'}}]}, "closest: behaviorType"),
    ({"event": 2, "add-actions": [{"type": "comment", "txt": "Score."}]}, "'txt' is not a key of a comment row"),
    ({"event": 1, "add-actions": [SET_TIME]}, "event 1 is a group, which has no actions"),
    ({"event": 2, "add-actions": [SET_TIME], "position": 7}, "position is 1 to 5"),
    ({"into": 5, "events": [{"eventType": "variable", "name": "n", "type": "int"}]}, "'number', 'string' or 'boolean'"),
    ({"move": 1, "into": 3}, "event 3 is event 1 or inside it"),
])
def test_a_plan_that_cannot_be_read_says_what_an_operation_is(project, operation, said):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, operation)
    assert code == 1 and said in out and "nothing was written" in out and "Traceback" not in out
    assert (project / SHEET).read_bytes() == before


def test_a_sheet_saved_after_it_was_printed_waits_for_a_new_print(project):
    """A save in the editor between print_sheet.py and the plan can move the events the plan numbers."""
    timer = {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]}
    tool(project, "print_sheet", "Game")
    edit(project, SHEET, lambda s: s["events"].insert(0, {"eventType": "comment", "text": "Saved in the editor."}))
    code, out = plan(project, timer, flags=("--dry-run",))
    assert code == 1 and "changed on disk after print_sheet.py printed it" in out, out
    tool(project, "print_sheet", "Game")
    code, out = plan(project, timer, flags=("--dry-run",))
    assert code == 0, out


def test_the_plan_skill_md_shows_is_one_the_script_takes(project):
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    shown = text.split("## Change a sheet with a plan")[1].split("```json\n")[1].split("```")[0]
    (project / "plan.json").write_text(shown, encoding="utf-8")
    code, out = tool(project, "edit_sheet", "Game", "plan.json")
    assert code == 0 and out.splitlines()[-1].startswith("ok:") and "by number alone" not in out, out


def test_new_sid_left_in_a_plan_is_named(project):
    (project / "plan.json").write_text('[{"event": 2, "add-actions": [{"id": "x", "objectClass": "Coin", "sid": <new sid>}]}]',
                                       encoding="utf-8")
    code, out = tool(project, "edit_sheet", "Game", "plan.json")
    assert code == 1 and 'leave "sid" out' in out


def test_plan_takes_the_children_key_off_an_event_it_empties(project):
    """The editor saves an event without sub-events with no "children": a [] left behind
    comes back changed in the diff of the sheet's next save."""
    code, out = plan(project, {"after": 8, "events": [{"eventType": "group", "title": "Timer", "children": [
        {"eventType": "comment", "text": "Show the clock."},
        {"eventType": "block", "conditions": [], "actions": [{**SET_TIME, "parameters": {"text": '"Go"'}}]}]}]})
    assert code == 0, out
    n = int(re.search(r"^\s*(\d+) group Timer", printed(project), re.M).group(1))
    code, out = plan(project, {"remove": n + 1})
    assert code == 0, out
    timer = next(ev for ev in all_events(project) if ev.get("title") == "Timer")
    assert "children" not in timer


def local_n_in_two_groups(project: Path) -> None:
    """A local n in group Setup and another in group Restart: one name, two variables."""
    def change(sheet):
        groups = {ev.get("title"): ev for ev in sheet["events"]}
        for group, sid in ((groups["Setup"], 811111111111111), (groups["Restart"], 822222222222222)):
            group["children"].insert(0, {"eventType": "variable", "name": "n", "type": "number", "initialValue": "0",
                                         "comment": "", "isStatic": False, "isConstant": False, "sid": sid})
    edit(project, SHEET, change)
    assert "   1 group Setup\n       local number n = 0" in printed(project)


def test_plan_sets_a_variable_by_its_name(project):
    """A variable has no number: the plan names it, and a value kept in a constant changes there."""
    code, out = plan(project, {"variable": "ROUND_COINS", "set": {"initialValue": "2,4"}},
                     {"variable": "score", "set": {"initialValue": 5, "comment": "Points this round"}})
    assert code == 0, out
    assert "-- variable ROUND_COINS changed: global constant string ROUND_COINS = 2,4" in out
    score = next(ev for ev in all_events(project) if ev.get("name") == "score")
    assert (score["initialValue"], score["comment"]) == ("5", "Points this round")
    assert list(score) == ["eventType", "name", "type", "initialValue", "comment", "isStatic", "isConstant", "sid"]
    assert check(project)[0] == 0


@pytest.mark.parametrize("values, said", [
    ({"isConstant": True}, "score is a constant and an action cannot change it"),
    ({"initialValue": "fast"}, "initialValue 'fast' is not a number"),
    ({"type": "boolean"}, "should be \"true\" or \"false\""),
    ({"name": "points"}, "the plan removes or renames score, and the events above still use it"),
])
def test_a_variable_set_keeps_the_checkers_guarantees(project, values, said):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"variable": "score", "set": values})
    assert code == 1 and said in out and out.splitlines()[-1].endswith("nothing was written"), out
    assert (project / SHEET).read_bytes() == before


def test_plan_removes_a_variable_and_a_comment(project):
    code, out = plan(project, {"before": 1, "events": [{"eventType": "variable", "name": "unused"}]},
                     {"variable": "unused", "remove": True}, {"comment": "Settings", "remove": True})
    assert code == 0, out
    assert "-- variable unused removed" in out and "-- comment // Settings removed" in out
    sheet = printed(project)
    assert "unused" not in sheet and "// Settings" not in sheet and "global constant string ROUND_COINS" in sheet
    code, out = plan(project, {"variable": "beat", "remove": True})
    assert code == 1 and "variable 'beat' is not in scope" in out and "the events above still use it" in out


def test_plan_changes_a_comment_by_words_of_its_text(project):
    code, out = plan(project, {"comment": "Start the next round", "set": {"text": "Next round once the coins are gone"}})
    assert code == 0, out
    assert "  8 group Restart\n       // Next round once the coins are gone\n   9" in printed(project)
    code, out = plan(project, {"comment": "coin", "set": {"text": "x"}})
    assert code == 1 and "comments hold 'coin'" in out and '"in": 1' in out


def test_an_unknown_variable_is_refused_with_the_variables_of_the_sheet(project):
    code, out = plan(project, {"variable": "Score", "set": {"initialValue": "1"}})
    assert code == 1 and "the sheet has no variable named 'Score'; closest: score" in out, out
    assert "Its variables: global constant string ROUND_COINS = 1,3,6,2,10,1, global number score = 0" in out
    code, out = plan(project, {"event": 2, "set": {"initialValue": "1"}})
    assert code == 1 and '{"variable": "NAME", "set": {"initialValue": "0.5"}}' in out, out
    code, out = plan(project, {"variable": 3, "set": {"initialValue": "1"}})
    assert code == 1 and "not a number" in out


def test_a_local_name_in_two_events_is_named_with_in(project):
    local_n_in_two_groups(project)
    code, out = plan(project, {"variable": "n", "set": {"initialValue": "3"}})
    assert code == 1, out
    assert ("2 variables are named 'n': in event 1 (group Setup); in event 8 (group Restart). "
            'Name the event that holds the one to change with "in"') in out
    assert '{"variable": "n", "in": 1, "set": {"initialValue": "3"}}' in out
    code, out = plan(project, {"variable": "n", "in": 8, "set": {"initialValue": "3"}})
    assert code == 0 and "local number n = 3 in event 8 (group Restart)" in out, out
    assert "local number n = 0" in printed(project)
    code, out = plan(project, {"variable": "n", "in": 0, "remove": True})
    assert code == 1 and "no variable named 'n' at the top level" in out and "local number n = 0 in event 1" in out


def test_a_variable_change_in_a_dry_run_writes_nothing(project):
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {"variable": "ROUND_COINS", "set": {"initialValue": "2,4"}}, flags=("--dry-run",))
    assert code == 0 and "global constant string ROUND_COINS = 2,4" in out
    assert out.splitlines()[-1] == "dry run: nothing was written" and (project / SHEET).read_bytes() == before


def test_print_says_how_a_plan_names_a_variable(project):
    lines = printed(project).splitlines()
    assert lines[-1].startswith('-- a variable or comment has no number, so a plan of edit_sheet.py names it. '
                                'A variable: {"variable": "ROUND_COINS", "set": {"initialValue": "1,3,6,2,10,1"}}; '
                                'a value a constant holds is changed there')
    (project / "plan.json").write_text(json.dumps([json.loads(re.search(r"(\{\"variable\".*?\}\})", lines[-1]).group(1))]))
    assert tool(project, "edit_sheet", "Game", "plan.json", "--dry-run")[0] == 0
    assert "has no number" not in tool(project, "print_sheet", "Game", "--events", "4-5")[1]


def test_new_makes_the_sheet_a_project_without_one_runs(project):
    """A project of scripts has no sheet for a plan to change: --new lists one and sets it on the layouts that have none."""
    layouts = list((project / "layouts").glob("*.json"))
    (project / SHEET).unlink()
    edit(project, "project.c3proj", lambda p: p["eventSheets"].update(items=[]))
    for path in layouts:
        edit(project, path.relative_to(project).as_posix(), lambda lay: lay.update(eventSheet=None))
    start = {"into": 0, "events": [{"eventType": "comment", "text": "Score from zero."}, {
        "eventType": "block", "conditions": [{"id": "on-start-of-layout", "objectClass": "System"}],
        "actions": [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": '"Score: 0"'}}]}]}
    code, out = plan(project, start)
    assert code == 1 and "--new creates it" in out
    code, out = plan(project, start, flags=("--new",))
    assert code == 0, out
    assert out.splitlines()[0].startswith("Game: a new event sheet in eventSheets/, listed in project.c3proj, run by layout")
    sheet = sheet_on_disk(project)
    assert list(sheet) == ["name", "events", "sid"] and len(str(sheet["sid"])) == 15
    assert json.loads((project / "project.c3proj").read_text(encoding="utf-8"))["eventSheets"]["items"] == ["Game"]
    assert all(json.loads(p.read_text(encoding="utf-8"))["eventSheet"] == "Game" for p in layouts)
    assert "System: On start of layout" in printed(project) and check(project)[0] == 0


@pytest.mark.parametrize("blocked", ["eventSheets/Game.json.tmp", "project.c3proj.tmp", "layout"])
def test_new_puts_back_what_it_wrote_when_a_later_file_fails(project, blocked):
    """--new writes the sheet, project.c3proj and the layouts that run it; a write that fails, here on a folder
    where its draft goes, leaves every file as it was, and the same plan runs once the way is clear (the audit
    of 2026-10-07 left a sheet that project.c3proj did not list, which the plan then refused)."""
    layouts = list((project / "layouts").glob("*.json"))
    (project / SHEET).unlink()
    edit(project, "project.c3proj", lambda p: p["eventSheets"].update(items=[]))
    for path in layouts:
        edit(project, path.relative_to(project).as_posix(), lambda lay: lay.update(eventSheet=None))
    files = {p: p.read_bytes() for p in (project / "project.c3proj", *layouts)}
    folder = project / (f"layouts/{layouts[-1].name}.tmp" if blocked == "layout" else blocked)
    folder.mkdir()
    start = {"into": 0, "events": [{"eventType": "comment", "text": "Score from zero."}]}
    code, out = plan(project, start, flags=("--new",))
    assert code == 1 and "could not be written" in out and "nothing was written" in out, out
    assert all(p.read_bytes() == raw for p, raw in files.items()) and not (project / SHEET).exists()
    folder.rmdir()
    code, out = plan(project, start, flags=("--new",))
    assert code == 0 and (project / SHEET).is_file(), out


def test_a_new_sheet_beside_others_says_no_layout_runs_it(project):
    layouts = {p: p.read_bytes() for p in (project / "layouts").glob("*.json")}
    (project / "plan.json").write_text(json.dumps([{"into": 0, "events": [{"eventType": "variable", "name": "menuShown"}]}]),
                                       encoding="utf-8")
    code, out = tool(project, "edit_sheet", "Menu", "plan.json", "--new")
    assert code == 0 and "run by no layout" in out, out
    assert (project / "eventSheets" / "Menu.json").is_file()
    assert all(p.read_bytes() == raw for p, raw in layouts.items())


def test_a_generated_project_is_told_the_change_belongs_in_the_generator(project):
    """The generator's next run writes the sheet over an edit: the note says so after a write and in a dry run."""
    timer = {"before": 1, "events": [{"eventType": "variable", "name": "timeLeft"}]}
    code, out = plan(project, timer, flags=("--dry-run",))
    assert code == 0 and ("note: tools/build_project.py generates this project, and its next run writes "
                          "eventSheets/Game.json over what this plan would write") in out, out
    code, out = plan(project, timer)
    assert code == 0 and "writes eventSheets/Game.json over this change: make the change in the generator" in out, out
    assert out.splitlines()[-1].startswith("ok:")
    shutil.rmtree(project / "tools")
    code, out = plan(project, {"remove": 1}, flags=("--dry-run",))
    assert code == 0 and "build_project" not in out, out


STALE = {"event": 6, "line": "function AddScore(points: number)", "add-actions": [
    {"id": "wait", "objectClass": "System", "parameters": {"seconds": "0"}}]}


def test_a_plan_from_an_older_print_is_refused_with_where_its_line_is_now(project):
    """A second plan that uses the numbers of an earlier print names another event once an earlier plan has
    moved it. The line refuses it."""
    code, out = plan(project, {"before": 7, "line": "AddScore", "events": [
        {"eventType": "comment", "text": "Points."},
        {"eventType": "function-block", "functionName": "Bonus", "actions": []}]})
    assert code == 0 and "named an event by number alone" not in out, out
    before = (project / SHEET).read_bytes()
    code, out = plan(project, {**STALE, "event": 7})      # AddScore prints as event 7 before the first plan, 8 after
    assert code == 1 and out.splitlines()[0] == (
        'operation 1 (event 7): "function AddScore(points: number)" is event 8 now. Event 7 prints "function Bonus()". '
        "The plan's numbers may come from an older print of the sheet, or 7 may be miscounted. Take each number and "
        "its line from print_sheet.py as it prints the sheet now"), out
    assert (project / SHEET).read_bytes() == before
    code, out = plan(project, {**STALE, "event": 8}, flags=("--dry-run",))
    assert code == 0, out


@pytest.mark.parametrize("line", ["   7 function AddScore(points: number)", "AddScore(points",
                                  "function AddScore(points: number)  [event disabled]"])
def test_a_line_is_found_as_print_sheet_prints_it_or_in_part(project, line):
    """The line with its number or a mark print_sheet.py adds, or a part of it."""
    code, out = plan(project, {**STALE, "event": 7, "line": line}, flags=("--dry-run",))
    assert code == 0, out


def test_a_line_copied_from_a_print_in_another_locale_names_the_event(project):
    """A print with --locale zh-CN words the line in Chinese; the plan runs without --locale."""
    printed = tool(project, "print_sheet", "Game", "--events", "5", "--locale", "zh-CN")[1]
    line = next(row for row in printed.splitlines() if row.startswith("   5 "))[5:].strip()
    assert line != "Touch: On touched Coin (start)", printed
    code, out = plan(project, {"event": 5, "line": line, "action": 1, "set": {"disabled": True}}, flags=("--dry-run",))
    assert code == 0, out


def test_a_plan_without_lines_is_carried_out_and_noted(project):
    """A plan without lines, such as one made from a finding's place, which names no line, is carried out with a
    note."""
    code, out = plan(project, {"event": 7, "add-actions": STALE["add-actions"]}, {"remove": 5},
                     {"into": 0, "events": [{"eventType": "comment", "text": "End."}]}, flags=("--dry-run",))
    assert code == 0 and ('note: operations 1 and 2 named events by number alone. Add "line" to each: the line '
                          'print_sheet.py prints for its event, as in {"event": 7, "line": "function AddScore(points: '
                          'number)", ...}. A number from an older print is then refused instead of changing another '
                          'event') in out, out
    code, out = plan(project, {"into": 0, "line": "x", "events": [{"eventType": "comment", "text": "End."}]})
    assert code == 1 and 'operation 1 (into 0): 0 is the sheet itself, which prints no line; leave "line" out' in out
    code, out = plan(project, {"variable": "score", "line": "x", "set": {"initialValue": "1"}})
    assert code == 1 and "a variable is changed with" in out, out
