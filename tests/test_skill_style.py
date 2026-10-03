"""Style, with --style: the habits of small models as warnings from check_project.py, and the
same findings refusing what a plan of edit_sheet.py adds."""
import json
import re

from tests.skill_helpers import SHEET, check, edit, cond, block, events, warnings, plan


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
