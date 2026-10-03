"""Style, with --style: the habits of small models as warnings from check_project.py, and the
same findings refusing what a plan of edit_sheet.py adds."""
import copy
import json
import re

from tests.skill_helpers import SHEET, check, edit, cond, block, events, findings, warnings, plan
from tests.test_skill_check_project import add_addon, add_keyboard, pathfinding_coin


STYLE_ACTIONS = [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": f'"{i}"'}} for i in range(8)]


def test_stand_in_project_passes_the_style_check(built):
    """The template is the shape the style asks for, so a generated project starts clean."""
    code, out = check(built, "--style")
    assert code == 0, out
    assert warnings(out) == [], out


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
    assert code == 0 and "event 2 (sid" in out and "10 actions in a row without a comment action" in out, out
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


def with_own_sids(ev: dict, start: int) -> dict:
    """The test helpers give every row sid 1 or 2; the checker wants them distinct."""
    fresh = iter(range(start, start + 500))

    def give(e):
        e["sid"] = next(fresh)
        for c in e.get("conditions", []):
            c["sid"] = next(fresh)
        for k in e.get("children", []):
            give(k)
        return e
    return give(ev)


def case(n: int) -> dict:
    return block([cond("compare-two-values", params={"first-value": str(n), "comparison": 0, "second-value": "1"})],
                 [{"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": f'"{n}"'}}])


def test_style_names_cases_with_no_comment_above_any(project):
    edit(project, SHEET, lambda s: events(s)["input"].update(
        children=[with_own_sids(case(n), 910_000_000_000_000 + 10 * n) for n in (1, 2)]))
    code, out = check(project, "--style")
    assert code == 0 and re.search(r"event 5 \(sid \d+\): none of its 2 case sub-events has a comment above it", out), out
    edit(project, SHEET, lambda s: events(s)["input"]["children"].insert(0, {"eventType": "comment", "text": "First."}))
    assert "case sub-events" not in check(project, "--style")[1]


def test_style_names_a_ladder_of_one_shape(project):
    def rungs(n):
        return [with_own_sids(case(i), 920_000_000_000_000 + 10 * i) for i in range(1, n + 1)]
    edit(project, SHEET, lambda s: events(s)["input"].update(children=rungs(5)))
    code, out = check(project, "--style")
    assert code == 0 and re.search(r"event 6 \(sid \d+\): with events 7, 8, 9, 10, the same conditions and actions "
                                   r"5 times over", out), out
    edit(project, SHEET, lambda s: events(s)["input"].update(children=rungs(4)))
    assert "times over" not in check(project, "--style")[1]


def test_style_names_every_tick_beside_another_condition(project):
    tick = cond("every-tick")
    test = cond("compare-two-values", params={"first-value": "1", "comparison": 0, "second-value": "1"})
    edit(project, SHEET, lambda s: events(s)["input"].update(children=[with_own_sids(
        block([tick, test], STYLE_ACTIONS[:1]), 930_000_000_000_000)]))
    code, out = check(project, "--style")
    assert code == 0 and re.search(r"event 6 \(sid \d+\): Every tick beside 1 other condition\(s\) changes nothing", out), out
    edit(project, SHEET, lambda s: events(s)["input"].update(children=[with_own_sids(
        block([tick], STYLE_ACTIONS[:1]), 930_000_000_000_000)]))
    assert "Every tick beside" not in check(project, "--style")[1]


def test_plan_refuses_a_new_every_tick_beside_another_condition(project):
    before = (project / SHEET).read_bytes()
    test = {"id": "compare-two-values", "objectClass": "System",
            "parameters": {"first-value": "1", "comparison": 0, "second-value": "1"}}
    ev = {"eventType": "block", "conditions": [{"id": "every-tick", "objectClass": "System"}, test],
          "actions": STYLE_ACTIONS[:1]}
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Show the score."}, ev]})
    assert code == 1 and (project / SHEET).read_bytes() == before and "Every tick beside 1 other" in out, out
    ev["conditions"] = [test]
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Show the score."}, ev]})
    assert code == 0 and warnings(out) == [], out


FIND_PATH = {"id": "find-path", "objectClass": "Coin", "behaviorType": "Pathfinding", "parameters": {"x": "100", "y": "100"}}
EVERY_HALF_SECOND = {"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "0.5"}}


def test_plan_refuses_a_new_find_path_every_tick(project):
    """Both arms of a Haiku run of 2026-10-03 chased with Every tick or NOT Is moving along path -> Find path,
    and the run that saw the warning kept it: in an event the plan creates it is refused, the first line
    naming the fix with the JSON of the condition; with Every 0.5 seconds it goes through."""
    pathfinding_coin(project)
    before = (project / SHEET).read_bytes()
    moving = {"id": "is-moving-along-path", "objectClass": "Coin", "behaviorType": "Pathfinding", "isInverted": True}
    for condition in ({"id": "every-tick", "objectClass": "System"}, moving):
        ev = {"eventType": "block", "conditions": [condition], "actions": [FIND_PATH]}
        code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Chase the player."}, ev]})
        assert code == 1 and (project / SHEET).read_bytes() == before, out
        assert re.match(r"operation 1: sheet Game event \d+ \(sid \d+\) action 1: Find path runs every tick; move it "
                        r"into the trigger that sets the target, such as Touch On tap", out), out
        assert json.dumps(EVERY_HALF_SECOND) in out.splitlines()[0]
        assert out.splitlines()[-1] == "the plan adds 1 problem(s) to the project; nothing was written"
    ev = {"eventType": "block", "conditions": [moving, EVERY_HALF_SECOND], "actions": [FIND_PATH]}
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Chase the player."}, ev]})
    assert code == 0 and warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out


def test_plan_warns_on_a_find_path_every_tick_in_an_event_it_did_not_create(project):
    """A Find path the plan adds to the user's own event, which runs every tick, is a warning under
    the output, as the comment findings are on such an event."""
    pathfinding_coin(project)
    edit(project, SHEET, lambda s: s["events"].append(with_own_sids(
        block([cond("every-tick")], STYLE_ACTIONS[:1]), 940_000_000_000_000)))
    code, out = plan(project, {"event": 10, "add-actions": [FIND_PATH]}, flags=("--dry-run",))
    assert code == 0 and "Traceback" not in out, out
    assert [w for w in warnings(out) if "Find path runs every tick" in w], out


def give_behavior(project, obj: str, behavior_id: str, name: str) -> None:
    """obj gets the behavior, on its type and on its instance: Coin's template in Objects, ScoreText's in Game."""
    edit(project, f"objectTypes/{obj}.json", lambda t: t.setdefault("behaviorTypes", []).append(
        {"behaviorId": behavior_id, "name": name, "sid": 950_000_000_000_000 + len(name)}))
    layout = "layouts/Objects.json" if obj == "Coin" else "layouts/Game.json"
    edit(project, layout, lambda d: next(i for layer in d["layers"] for i in layer["instances"] if i["type"] == obj)
         .setdefault("behaviors", {}).update({name: {"properties": {}}}))
    add_addon(project, "behavior", behavior_id, name)


def comment(text: str) -> dict:
    return {"eventType": "comment", "text": text}


NONE_LEFT = {"id": "compare-two-values", "objectClass": "System",
             "parameters": {"first-value": "Coin.Count", "comparison": 0, "second-value": "0"}}
ONCE = {"id": "trigger-once-while-true", "objectClass": "System"}
START_WAVE = {"id": "start-timer", "objectClass": "ScoreText", "behaviorType": "Timer",
              "parameters": {"duration": "3", "type": "once", "tag": '"wave"'}}


def test_plan_refuses_a_new_timer_started_every_tick(project):
    """The wave-system runs of the prompt evals of 2026-10-04 started the countdown between waves with no
    trigger, Enemy.Count = 0 -> Start timer, which starts it over each tick, so On timer never fires: refused
    in an event the plan creates, the first line naming Trigger once with its JSON. Trigger once, a cooldown's
    NOT Is timer running, or a Set of the variable the event tests goes through."""
    give_behavior(project, "ScoreText", "Timer", "Timer")
    before = (project / SHEET).read_bytes()
    ev = {"eventType": "block", "conditions": [NONE_LEFT], "actions": [START_WAVE]}
    code, out = plan(project, {"into": 0, "events": [comment("Count down to the next round."), ev]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert re.match(r'operation 1: sheet Game event \d+ \(sid \d+\) action 1: Start timer "wave" runs every tick\. '
                    r'No trigger', out), out
    assert "On timer \"wave\" never fires" in out and json.dumps(ONCE) in out.splitlines()[0], out
    running = {"id": "is-timer-running", "objectClass": "ScoreText", "behaviorType": "Timer",
               "parameters": {"tag": '"wave"'}, "isInverted": True}
    beat_is_0 = {"id": "compare-eventvar", "objectClass": "System",
                 "parameters": {"variable": "beat", "comparison": 0, "value": "0"}}
    set_beat = {"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "beat", "value": "1"}}
    for conditions, actions in (([NONE_LEFT, ONCE], [START_WAVE]), ([NONE_LEFT, running], [START_WAVE]),
                                ([beat_is_0], [START_WAVE, set_beat])):
        ev = {"eventType": "block", "conditions": conditions, "actions": actions}
        code, out = plan(project, {"into": 0, "events": [comment("Count down to the next round."), ev]},
                         flags=("--dry-run",))
        assert code == 0 and warnings(out) == [], (conditions, out)


def test_timer_started_under_a_trigger_or_by_an_overlap_is_left_alone(project):
    """A Start timer below a trigger runs once; one under a test of what moves, a position here, is the
    official examples' timer that fires once the test stops holding."""
    give_behavior(project, "ScoreText", "Timer", "Timer")
    moved = {"id": "compare-two-values", "objectClass": "System",
             "parameters": {"first-value": "ScoreText.X", "comparison": 4, "second-value": "100"}}
    for top in (block([cond("on-start-of-layout")], [], [block([NONE_LEFT], [START_WAVE])]),
                block([moved], [START_WAVE])):
        out = findings(project, lambda s: s["events"].append(with_own_sids(copy.deepcopy(top), 960_000_000_000_000)))
        assert "runs every tick" not in out and out.splitlines()[-1].startswith("ok:"), out


def test_simulate_control_under_a_trigger(project):
    """Every new-game plan of the prompt evals walked under On key pressed: Simulate control holds the
    control for that tick alone. Refused in a new event with the condition that holds, its key kept;
    under Key is down, and a Platform jump under On key pressed, go through."""
    give_behavior(project, "Coin", "EightDir", "8Direction")
    give_behavior(project, "Coin", "Platform", "Platform")
    add_keyboard(project, 87)
    before = (project / SHEET).read_bytes()
    up = {"id": "simulate-control", "objectClass": "Coin", "behaviorType": "8Direction", "parameters": {"control": "up"}}
    pressed = {"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 87}}
    ev = {"eventType": "block", "conditions": [pressed], "actions": [up]}
    code, out = plan(project, {"into": 0, "events": [comment("W walks up."), ev]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert re.match(r"operation 1: sheet Game event \d+ \(sid \d+\) action 1: Simulate control up runs only in the "
                    r"tick that Keyboard:on-key-pressed fires, so Coin moves for one tick and stops", out), out
    assert '{"id": "key-is-down", "objectClass": "Keyboard", "parameters": {"key": 87}}' in out.splitlines()[0], out
    touched = {"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "Coin", "type": "start"}}
    ev["conditions"] = [touched]
    code, out = plan(project, {"into": 0, "events": [comment("A touch walks up."), ev]})
    assert code == 1 and '{"id": "is-touching-object", "objectClass": "Touch", "parameters": {"object": "Coin"}}' in out
    ev["conditions"] = [{"id": "on-key-code-pressed", "objectClass": "Keyboard", "parameters": {"keycode": "87"}}]
    code, out = plan(project, {"into": 0, "events": [comment("W walks up."), ev]})
    assert code == 1 and '{"id": "key-code-is-down", "objectClass": "Keyboard", "parameters": {"keycode": "87"}}' in out
    jump = {"id": "simulate-control", "objectClass": "Coin", "behaviorType": "Platform", "parameters": {"control": "jump"}}
    for conditions, action in (([{**pressed, "id": "key-is-down"}], up), ([pressed], jump)):
        ev = {"eventType": "block", "conditions": conditions, "actions": [action]}
        code, out = plan(project, {"into": 0, "events": [comment("W moves."), ev]}, flags=("--dry-run",))
        assert code == 0 and warnings(out) == [], (conditions, out)


def test_none_left_in_the_event_that_destroys_the_last(project):
    """The key-and-door runs tested Key.Count = 0 in a sub-event of the trigger that destroys the key,
    which the destroyed key still fails: refused, naming the top-level event to write. Its own top-level
    event, a comparison with 1 as the official examples write it, or a Wait before the sub-events goes through."""
    before = (project / SHEET).read_bytes()
    touched = {"id": "on-touched-object", "objectClass": "Touch", "parameters": {"object": "Coin", "type": "start"}}
    destroy = {"id": "destroy", "objectClass": "Coin"}
    done = {"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": '"Done"'}}
    last = {"eventType": "block", "conditions": [NONE_LEFT], "actions": [done]}
    ev = {"eventType": "block", "conditions": [touched], "actions": [destroy], "children": [last]}
    code, out = plan(project, {"into": 0, "events": [comment("A touched coin goes."), ev]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert re.match(r"operation 1: sheet Game event (\d+) \(sid \d+\) condition 1: Coin.Count = 0 is false here even "
                    r"when the last Coin is gone\. sheet Game event \d+ \(sid \d+\) action 1 destroys it", out), out
    assert json.dumps([NONE_LEFT, ONCE]) in out.splitlines()[0], out
    one_left = {**NONE_LEFT, "parameters": {**NONE_LEFT["parameters"], "second-value": "1"}}
    wait = {"id": "wait", "objectClass": "System", "parameters": {"seconds": "0", "use-timescale": False}}
    for events_ in ([{**ev, "children": [{**last, "conditions": [one_left]}]}],
                    [{**ev, "actions": [destroy, wait]}],
                    [{**ev, "children": []}, comment("Then none is left."),
                     {"eventType": "block", "conditions": [NONE_LEFT, ONCE], "actions": [done]}]):
        code, out = plan(project, {"into": 0, "events": [comment("A touched coin goes."), *events_]},
                         flags=("--dry-run",))
        assert code == 0 and warnings(out) == [], (events_, out)


def test_picked_count_of_none_below_a_pick(project):
    """Three key-and-door runs wrote Pick all Key, then Key.PickedCount = 0: a pick of no instance stops its
    event, Pick all included, so the test never holds. Refused, naming Count in an event without the pick;
    Coin.Count = 0 with Trigger once goes through."""
    before = (project / SHEET).read_bytes()
    pick_all = {"id": "pick-all", "objectClass": "System", "parameters": {"object": "Coin"}}
    none_picked = {"id": "compare-two-values", "objectClass": "System",
                   "parameters": {"first-value": "Coin.PickedCount", "comparison": 0, "second-value": "0"}}
    done = {"id": "set-text", "objectClass": "ScoreText", "parameters": {"text": '"Done"'}}
    ev = {"eventType": "block", "conditions": [pick_all], "actions": [],
          "children": [{"eventType": "block", "conditions": [none_picked], "actions": [done]}]}
    code, out = plan(project, {"into": 0, "events": [comment("Say when no coin is left."), ev]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert re.match(r"operation 1: sheet Game event \d+ \(sid \d+\) condition 1: Coin.PickedCount = 0 never holds here\. "
                    r"System:pick-all above it picks Coin", out), out
    assert json.dumps(NONE_LEFT) in out.splitlines()[0], out
    ev = {"eventType": "block", "conditions": [NONE_LEFT, ONCE], "actions": [done]}
    code, out = plan(project, {"into": 0, "events": [comment("Say when no coin is left."), ev]}, flags=("--dry-run",))
    assert code == 0 and warnings(out) == [], out


def test_style_names_a_countdown_kept_by_hand(project):
    """Every 1 seconds, subtract 1 from a global: what every add-countdown run wrote, also as Add -1
    and Set v to v - 1. The plan goes through with the warning under it, which names the Timer
    actions to write instead; taking another amount off every N seconds counts things, not time,
    and passes."""
    every = {"id": "every-x-seconds", "objectClass": "System", "parameters": {"interval-seconds": "1"}}
    tick = {"id": "subtract-from-eventvar", "objectClass": "System", "parameters": {"variable": "score", "value": "1"}}
    ev = {"eventType": "block", "conditions": [every], "actions": [tick]}
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Count down."}, ev]}, flags=("--dry-run",))
    assert code == 0 and "score counts seconds by hand, 1 off every 1 seconds; a global keeps its value across " \
                         "Restart layout" in out, out
    assert '"id": "start-timer"' in out and 'ceil(<Object>.Timer.Duration("countdown")' in out
    for spelled in ({"id": "add-to-eventvar", "value": "-1"}, {"id": "set-eventvar-value", "value": "score - 1"}):
        ev["actions"] = [{**tick, "id": spelled["id"], "parameters": {"variable": "score", "value": spelled["value"]}}]
        code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Count down."}, ev]},
                         flags=("--dry-run",))
        assert code == 0 and "score counts seconds by hand, 1 off every 1 seconds" in out, (spelled, out)
    ev["actions"] = [tick]
    tick["parameters"]["value"] = "2"
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Count down."}, ev]}, flags=("--dry-run",))
    assert code == 0 and "counts seconds by hand" not in out, out


def test_plan_refuses_new_cases_without_a_comment(project):
    """An event the plan creates with case sub-events needs a comment above at least one case, like
    the comment above itself; cases the plan puts under the user's own event only warn."""
    before = (project / SHEET).read_bytes()
    cases = [{"eventType": "block", "conditions": [], "actions": STYLE_ACTIONS[:1]} for _ in range(2)]
    parent = {"eventType": "block", "conditions": [], "actions": STYLE_ACTIONS[:1], "children": cases}
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Show the score."}, parent]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    assert "none of its 2 case sub-events has a comment above it" in out
    assert out.splitlines()[-1] == "the plan adds 1 problem(s) to the project; nothing was written"
    parent["children"] = [{"eventType": "comment", "text": "First."}, *cases]
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Show the score."}, parent]})
    assert code == 0 and warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out


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
    assert code == 0 and warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out


def test_plan_names_the_group_its_uncommented_events_are_in(project):
    """A comment above a new group is not one above the events in it. The refusal names the group
    and each event's entry in its children, and no operation: the file has no such event number yet."""
    before = (project / SHEET).read_bytes()
    rows = [{"eventType": "block", "conditions": [], "actions": STYLE_ACTIONS[:1]} for _ in range(2)]
    timer = {"eventType": "group", "title": "Timer", "children": rows}
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Count the time down."}, timer]})
    assert code == 1 and (project / SHEET).read_bytes() == before, out
    refused = [line for line in out.splitlines() if "no comment above it" in line]
    assert [re.search(r'entry \d in the "children" of group "Timer"', line)[0] for line in refused] == \
        ['entry 1 in the "children" of group "Timer"', 'entry 2 in the "children" of group "Timer"'], out
    assert all(line.startswith("operation 1: ") for line in refused) and '"before"' not in out, out
    timer["children"] = [{"eventType": "comment", "text": "Take a second off."}, rows[0],
                         {"eventType": "comment", "text": "Show what is left."}, rows[1]]
    code, out = plan(project, {"into": 0, "events": [{"eventType": "comment", "text": "Count the time down."}, timer]})
    assert code == 0 and warnings(out) == [] and out.splitlines()[-1].startswith("ok:"), out


def test_style_names_the_operation_that_comments_an_event_in_a_group(project):
    """On disk the finding carries the operation that puts the comment in the group's children.
    A plan that inserts above the user's uncommented event moves its entry and prints no warning."""
    edit(project, SHEET, lambda s: events(s)["input_group"]["children"].pop(0))
    code, out = plan(project, {"before": 5, "events": [{"eventType": "comment", "text": "Show the time."},
                                                      {"eventType": "block", "conditions": [], "actions": STYLE_ACTIONS[:1]}]})
    assert code == 0 and warnings(out) == [], out
    code, out = check(project, "--style")
    found = [w for w in warnings(out) if "no comment above it" in w]
    assert len(found) == 1 and found[0].startswith("warning: sheet Game event 6 (sid"), out
    assert 'This one is entry 3 in the "children" of group "Input"' in found[0], out
    op = json.loads(found[0][found[0].index('{"before"'):])
    assert op == {"before": 6, "events": [{"eventType": "comment", "text": "..."}]}, found
    op["events"][0]["text"] = "A touched coin collects itself, once."
    code, out = plan(project, op)
    assert code == 0 and warnings(out) == [], out
    assert "no comment above it" not in check(project, "--style")[1]


def test_style_names_chooseindex_on_a_condition(project):
    """chooseindex(condition, a, b) returns b when the condition is true; ?: reads in that order.
    A number first is an index among the choices, and three or more choices are a pick."""
    def text(value):
        edit(project, SHEET, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text=value))
        return [w for w in warnings(check(project, "--style")[1]) if "two-way choice on a condition" in w]
    found = text('chooseindex(score > 1, "few", "many")')
    assert len(found) == 1 and found[0].endswith('write score > 1 ? "many" : "few"'), found
    assert text('chooseindex(score, "few", "many")') == []
    assert text('chooseindex(score > 1, "few", "many", "all")') == []


def test_style_names_a_table_written_as_letters(project):
    """mid through two text literals maps a value by its place in a string; a cycle is a number with %."""
    def text(value):
        edit(project, SHEET, lambda s: events(s)["setup"]["actions"][1]["parameters"].update(text=value))
        return [w for w in warnings(check(project, "--style")[1]) if "a table written as text" in w]
    found = text('mid("BCA", find("ABC", ScoreText.Text), 1)')
    assert len(found) == 1 and "keep ScoreText.Text as a number 0 to 2" in found[0] and \
        "(ScoreText.Text + 1) % 3" in found[0], found
    assert text('mid(ScoreText.Text, find(ScoreText.Text, "A"), 1)') == []
    assert text('"mid(""BCA"", find(""ABC"", x), 1)"') == []


def test_style_names_sibling_events_dispatching_on_find(project):
    """Sibling events testing one text with find for different codes: "B" also matches "BU"."""
    def finds(*codes):
        return [with_own_sids(block([cond("compare-two-values", params={
            "first-value": f'find(ScoreText.Text, "{code}")', "comparison": 5, "second-value": "0"})],
            STYLE_ACTIONS[:1]), 940_000_000_000_000 + 10 * i) for i, code in enumerate(codes)]
    edit(project, SHEET, lambda s: events(s)["input"].update(children=finds("B", "BU")))
    found = [w for w in warnings(check(project, "--style")[1]) if "picks a branch by testing" in w]
    assert len(found) == 1 and re.search(r"event 6 \(sid \d+\): with events 7, picks a branch by testing "
                                         r"ScoreText\.Text for the codes \"B\", \"BU\"", found[0]), found
    assert '"b" also matches "bu"' in found[0] and "compared with =" in found[0], found
    edit(project, SHEET, lambda s: events(s)["input"].update(children=finds("B")))
    assert "picks a branch by testing" not in check(project, "--style")[1]
