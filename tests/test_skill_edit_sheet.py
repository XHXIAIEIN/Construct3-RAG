"""edit_sheet.py: changing a sheet from a plan."""
import json
import re
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL, SHEET, tool, check, edit, events, collect_tween, plan


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
    assert out.splitlines()[-1].startswith("ok:") and "open_in_editor" not in out     # the closing check names it
    sheet = printed(project)
    assert "     global number beat = 0\n     global number timeLeft = 30\n   1 group Setup" in sheet
    assert '-> ScoreText: Set text to "Score: 0"\n           -> ScoreText: Set text to "Time: " & timeLeft' in sheet
    assert "   4       (runs with its parent)\n               -> Coin: Set scale to 1.5" in sheet
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
                     {"event": 6, "action": 10, "set": {"behaviorType": "Tween"}},
                     {"event": 8, "action": 2, "set": {"id": "set-text"}},
                     {"move": 7, "after": 6})
    assert code == 0 and out.splitlines()[-1].startswith("ok:"), out
    raw = json.loads((project / SHEET).read_text(encoding="utf-8"))
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
    assert "       Coin: NOT Is any Tween playing [disabled]\n" in out
    assert "         -> System: Add points to score [disabled]\n" in out
    assert events(json.loads((project / SHEET).read_text(encoding="utf-8")))["input"]["conditions"][1]["disabled"] is True


def test_plan_names_an_older_form_of_a_text_it_left_alone(project):
    """Eval runs changed the score text at the start and left the one in AddScore, event 7, as it was."""
    both = '"Score: " & score & "  Time: " & round(time)'
    code, out = plan(project, {"event": 2, "action": 2, "set": {"parameters": {"text": both}}}, flags=("--dry-run",))
    assert code == 0, out
    note = [line for line in out.splitlines() if line.startswith("note: event")]
    assert note == ['note: event 7 action 2 (ScoreText set-text) still has text "Score: " & score, which this plan '
                    f'writes elsewhere as {both}; if both show the same thing, change it too: '
                    + json.dumps({"event": 7, "action": 2, "set": {"parameters": {"text": both}}})], out
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
    restart["actions"] = [a for a in restart["actions"] if a["id"] != "wait"]   # no wait before the restart
    sids = {c["sid"] for c in restart["conditions"]}
    code, out = plan(project, {"replace": 9, "events": [restart]}, {"move": 7, "before": 6}, {"remove": 4})
    assert code == 0, out
    sheet = printed(project)
    assert sheet.index("function AddScore") < sheet.index("custom action Coin.Collect") and "group Input" not in sheet
    assert '% tokencount(ROUND_COINS, ",")\n           -> System: Restart layout' in sheet
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
    assert plan(project, {"before": 9, "events": [{"eventType": "comment", "text": "All coins gone"}]})[0] == 0
    code, out = plan(project, {"before": 9, "events": [{"eventType": "block", "conditions": [], "actions": []}]})
    assert code == 0, out
    assert ("   9   (every tick)\n       // All coins gone\n       // Start the next round when the last coin is gone\n"
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
    ({"event": 2, "add-actions": [SET_TIME], "position": 5}, "position is 1 to 3"),
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
