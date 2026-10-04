"""review_design.py: each kept rule on a small project that has the shape and on one that
has the sound form beside it, and what the run prints. The rules are pure functions of
the parsed sheets; the projects are written here, the smallest the Project class reads."""
import json
import sys
from pathlib import Path

from tests.skill_helpers import REPO, SKILL, edit, run

SCRIPT = SKILL / "scripts" / "review_design.py"
SID = iter(range(100_000_000_000_001, 100_000_000_099_999))


def module():
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        import c3project as c3
        import review_design as rd
    finally:
        sys.path.pop(0)
    return c3, rd


# --- writing a project ---------------------------------------------------------------------
def c(ace_id, obj="System", inverted=False, **params):
    return {"id": ace_id, "objectClass": obj, "sid": next(SID), "parameters": params,
            **({"isInverted": True} if inverted else {})}


def a(ace_id, obj="System", **params):
    return {"id": ace_id, "objectClass": obj, "sid": next(SID), "parameters": params}


def ev(conditions, actions=(), children=()):
    return {"eventType": "block", "sid": next(SID), "conditions": list(conditions), "actions": list(actions),
            **({"children": list(children)} if children else {})}


def var(name, value="0", kind="number"):
    return {"eventType": "variable", "name": name, "type": kind, "initialValue": value, "comment": "",
            "isStatic": False, "isConstant": False, "sid": next(SID)}


def function(name, children, params=()):
    return {"eventType": "function-block", "functionName": name, "functionDescription": "", "functionCategory": "",
            "functionReturnType": "none", "functionCopyPicked": False, "functionIsAsync": False,
            "functionParameters": list(params), "conditions": [], "actions": [], "children": list(children),
            "sid": next(SID)}


def setv(name, value):
    return a("set-eventvar-value", variable=name, value=value)


def create(obj, x, y):
    return a("create-object", **{"object-to-create": obj, "layer": '"Game"', "x": x, "y": y,
                                 "create-hierarchy": False, "template-name": '""'})


def write(root: Path, sheets: dict, types: dict, layouts: dict | None = None) -> Path:
    """A folder project: sheets {name: events}, types {name: (plugin, [instance variable names])},
    layouts {name: sheet}."""
    layouts = layouts if layouts is not None else {name: name for name in sheets}
    for folder in ("eventSheets", "objectTypes", "layouts"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for name, events in sheets.items():
        (root / "eventSheets" / f"{name}.json").write_text(json.dumps({"name": name, "events": events}), "utf-8")
    for name, (plugin, ivars) in types.items():
        (root / "objectTypes" / f"{name}.json").write_text(json.dumps({
            "name": name, "plugin-id": plugin, "sid": next(SID), "isGlobal": False, "behaviorTypes": [],
            "instanceVariables": [{"name": v, "type": "number", "sid": next(SID)} for v in ivars]}), "utf-8")
    for name, sheet in layouts.items():
        (root / "layouts" / f"{name}.json").write_text(json.dumps({"name": name, "eventSheet": sheet, "layers": []}),
                                                       "utf-8")
    listing = {k: {"items": list(v), "subfolders": []} for k, v in
               (("eventSheets", sheets), ("objectTypes", types), ("layouts", layouts))}
    (root / "project.c3proj").write_text(json.dumps({"name": root.name, "families": {"items": [], "subfolders": []},
                                                     **listing}), "utf-8")
    return root


def found(root: Path) -> list[tuple]:
    """(rule, variant, ask, sheet, event) of every candidate a rule kept."""
    c3, rd = module()
    d = rd.Design.of(c3.Project(root, REPO, "en-US", c3.Findings()))
    return [(f["rule"], f["variant"], f["ask"], f["sheet"], f["event"]) for f in rd.review(d)]


def findings(root: Path, rule: str) -> list[tuple]:
    return [f for f in found(root) if f[0] == rule and f[2] is None]


# --- tic-tac-toe: one trigger split by globals, one fact twice, resets a restart makes ---------
CELL_TYPES = {"Cell": ("Sprite", ["Value", "Column", "Row"]), "Board": ("Arr", []), "Mouse": ("Mouse", [])}


def clicked():
    return c("on-object-clicked", "Mouse", **{"mouse-button": "left", "click-type": "clicked", "object-clicked": "Cell"})


def move(player, symbol, other):
    return ev([clicked(), c("compare-boolean-eventvar", inverted=True, variable="GameOver"),
               c("compare-instance-variable", "Cell", **{"instance-variable": "Value", "comparison": 0, "value": "0"}),
               c("compare-at-xy", "Board", x="Cell.Column", y="Cell.Row", comparison=0, value="0"),
               c("compare-eventvar", variable="CurrentPlayer", comparison=0, value=str(player))],
              [a("set-at-xy", "Board", x="Cell.Column", y="Cell.Row", value=str(player)),
               a("set-instvar-value", "Cell", **{"instance-variable": "Value", "value": str(player)}),
               a("set-animation", "Cell", animation=f'"{symbol}"', **{"from": "beginning"}),
               setv("CurrentPlayer", str(other))])


def tictactoe(root: Path) -> Path:
    events = [var("GameOver", "false", "boolean"), var("CurrentPlayer", "1"),
              ev([c("on-start-of-layout")], [setv("CurrentPlayer", "1")],
                 [ev([c("pick-all", object="Cell")],
                     [a("set-instvar-value", "Cell", **{"instance-variable": "Value", "value": "0"}),
                      a("set-animation", "Cell", animation='"Empty"', **{"from": "beginning"})])]),
              ev([clicked(), c("compare-boolean-eventvar", variable="GameOver")], [a("restart-layout")]),
              move(1, "X", 2), move(2, "O", 1)]
    return write(root, {"Game": events}, CELL_TYPES)


def test_tictactoe_one_trigger_split_by_globals_is_a_finding(tmp_path):
    hits = findings(tictactoe(tmp_path), "trigger")
    assert hits == [("trigger", "global", None, "Game", 3)], hits


def test_one_trigger_heading_steps_is_not_a_finding(tmp_path):
    """Sibling On start of layout events with a comment each, the examples' habit, run steps;
    nothing tells them apart."""
    steps = [ev([c("on-start-of-layout")], [setv("CurrentPlayer", str(n))]) for n in range(4)]
    root = write(tmp_path, {"Game": [var("CurrentPlayer"), *steps]}, CELL_TYPES)
    assert findings(root, "trigger") == []


def test_tictactoe_one_fact_in_the_array_and_the_cell(tmp_path):
    hits = findings(tictactoe(tmp_path), "twice")
    assert [h[4] for h in hits] == [4, 5], hits


def test_the_array_alone_is_not_twice(tmp_path):
    def drop_cell_writes(sheet):
        for e in sheet["events"][-2:]:
            e["actions"] = [x for x in e["actions"] if x["id"] != "set-instvar-value"]
    root = tictactoe(tmp_path)
    edit(root, "eventSheets/Game.json", drop_cell_writes)
    assert findings(root, "twice") == []


def test_tictactoe_resets_what_the_restart_restores(tmp_path):
    assert findings(tictactoe(tmp_path), "restart") == [("restart", "", None, "Game", 2)]


def test_resets_on_a_layout_never_entered_again(tmp_path):
    root = tictactoe(tmp_path)
    edit(root, "eventSheets/Game.json",
         lambda sheet: sheet["events"][3].update(actions=[a("go-to-layout", layout="Menu")]))
    assert findings(root, "restart") == []


def test_tictactoe_pair_is_a_question(tmp_path):
    asked = [f for f in found(tictactoe(tmp_path)) if f[0] == "pair"]
    assert asked == [("pair", "global", "value", "Game", 4)], asked


# --- a card game: scratch globals, globals on a layout's sheet, UID links, a table in actions ----
def card_game(root: Path, scratch="TMP", table=25) -> Path:
    shared = [var(f"G{n}") for n in range(12)]
    menu = [*shared, var(scratch), ev([c("on-start-of-layout")],
                                      [a("add-key", "CardTable", key=f'"c{n}"', value=f'"card {n}|{n}"')
                                       for n in range(table)])]
    reads = [setv(f"G{n}", f"G{n} + 1") for n in range(12)]
    deal = [create("CardLabel", "0", "0"),
            a("set-instvar-value", "Card", **{"instance-variable": "labelUid", "value": "CardLabel.UID"})]
    combat = [function("Draw", [ev([], [setv(scratch, "CardTable.Get(\"c1\")"), *deal])]),
              function("Show", [ev([c("compare-eventvar", variable=scratch, comparison=0, value='""')], reads)]),
              ev([c("pick-by-unique-id", "CardLabel", **{"unique-id": "Card.labelUid"})],
                 [a("set-text", "CardLabel", text='"x"')])]
    return write(root, {"Menu": menu, "Combat": combat},
                 {"Card": ("Sprite", ["labelUid"]), "CardLabel": ("Text", []), "CardTable": ("Dictionary", [])})


def test_card_game_scratch_global_and_globals_on_the_menu_sheet(tmp_path):
    hits = findings(card_game(tmp_path), "global")
    assert ("global", "scratch", None, "Menu", None) in hits and ("global", "sheet", None, "Menu", None) in hits, hits


def test_named_globals_on_a_globals_sheet_pass(tmp_path):
    """The examples' form: a sheet with the shared globals and no layout, a name for each value."""
    root = card_game(tmp_path, scratch="drawnKey")
    edit(root, "project.c3proj", lambda project: project["layouts"].update(items=["Combat"]))
    (root / "layouts" / "Menu.json").unlink()
    assert findings(root, "global") == []


def test_card_game_uid_of_an_instance_created_with_it(tmp_path):
    assert findings(card_game(tmp_path), "uid") == [("uid", "created", None, "Combat", 2)]


def test_a_uid_kept_without_the_create_is_a_question(tmp_path):
    def drop_create(sheet):
        actions = sheet["events"][0]["children"][0]["actions"]
        actions[:] = [x for x in actions if x["id"] != "create-object"]
    root = card_game(tmp_path)
    edit(root, "eventSheets/Combat.json", drop_create)
    assert [f for f in found(root) if f[0] == "uid"] == [("uid", "kept", "link", "Combat", 2)]


def test_card_game_table_written_as_actions(tmp_path):
    assert findings(card_game(tmp_path), "data") == [("data", "", None, "Menu", 1)]
    assert findings(card_game(tmp_path / "small", table=19), "data") == []


# --- a merge game: many conditions, a guard repeated, a repeated deep call ---------------------
def guard():
    return [c("is-enabled", "Piece"), c("is-dragging", "Piece", inverted=True),
            c("is-any-playing", "Piece", inverted=True)]


def merge_game(root: Path, conditions=12, repeat=True) -> Path:
    tests = [c("compare-two-values", **{"first-value": f"Piece.X + {n}", "comparison": 2, "second-value": "0"})
             for n in range(conditions)]
    long = 'clamp(Piece.level * (1 - Piece.X / 1000), 0, 1)'
    events = [ev(tests, [a("set-instvar-value", "Piece", **{"instance-variable": "level", "value": "1"})]),
              *[ev([*(guard() if repeat or n == 0 else guard()[:1]), c("compare-instance-variable", "Piece", **{
                  "instance-variable": "level", "comparison": 0, "value": str(n)})],
                   [a("set-instvar-value", "Piece", **{"instance-variable": "level", "value": str(n + 1)})])
                for n in range(3)],
              ev([c("every-tick")], [a("set-opacity", "Piece", opacity=f"max({long}, min(({long}) * 100, 50))"
                                       if repeat else "Piece.level")])]
    return write(root, {"Pieces": events}, {"Piece": ("Sprite", ["level"])})


def test_merge_game_twelve_conditions_is_a_finding_and_six_a_question(tmp_path):
    assert findings(merge_game(tmp_path), "conditions") == [("conditions", "many", None, "Pieces", 1)]
    asked = [f for f in found(merge_game(tmp_path / "six", conditions=6)) if f[0] == "conditions"]
    assert asked[0] == ("conditions", "some", "split", "Pieces", 1)
    assert {f[2] for f in asked} == {"split"}, asked     # the guard events hold 4 each


def test_merge_game_guard_repeated_in_three_events(tmp_path):
    assert findings(merge_game(tmp_path), "guard") == [("guard", "", None, "Pieces", 2)]
    assert findings(merge_game(tmp_path / "once", repeat=False), "guard") == []


def test_merge_game_expression_that_repeats_a_long_call(tmp_path):
    assert findings(merge_game(tmp_path), "expression") == [("expression", "", None, "Pieces", 5)]
    assert findings(merge_game(tmp_path / "plain", repeat=False), "expression") == []


def test_expression_shape_keeps_texts_apart():
    """Get("a") and Get("b") are two calls; a parenthesis inside a text is not counted."""
    _, rd = module()
    assert rd.expression_shape('CardTable.Get("a") & CardTable.Get("b")') == (1, "")
    assert rd.expression_shape('f(g("((("), g("((("))')[0] == 2


def test_numbering_follows_print_sheet(tmp_path):
    """Variables and comments take no number; groups, functions and sub-events do."""
    _, rd = module()
    rows = list(rd.walk("S", [var("x"), {"eventType": "group", "title": "G", "sid": 1, "children": [
        {"eventType": "comment", "text": "c"}, ev([], [], [ev([])])]}, function("f", [ev([])])]))
    assert [(r.kind, r.n) for r in rows] == [("variable", 1), ("group", 1), ("comment", 2), ("block", 2),
                                             ("block", 3), ("function-block", 4), ("block", 5)]


# --- the run ------------------------------------------------------------------------------
def test_review_prints_findings_then_questions_and_exits_0(tmp_path):
    root = tictactoe(tmp_path)
    code, out = run(root, SCRIPT, "--rag", str(REPO))
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == "== Game", out
    assert any(line.startswith("  trigger: sheet Game event 3: with events 4, 5") for line in lines), out
    assert any(line.startswith("  twice: sheet Game event 4: writes 1 into Board at (Cell.Column, Cell.Row)")
               for line in lines), out
    asked = next(i for i, line in enumerate(lines) if line.startswith("questions:"))
    assert lines[asked + 3].startswith("  3. Do these events do the same thing") and "Game 4 (with 5)" in lines[asked + 3]
    assert lines[-2].startswith("design: 4 findings on 1 of 1 sheets"), out
    assert lines[-1].startswith("next: ")


def test_review_cuts_findings_at_the_limit_and_keeps_the_questions(tmp_path):
    root = card_game(tmp_path)
    code, out = run(root, SCRIPT, "--rag", str(REPO), "--limit", "1800")
    assert code == 0 and "more lines of findings not printed" in out and "questions:" in out, out


def test_review_refuses_a_sheet_it_does_not_have(tmp_path):
    code, out = run(tictactoe(tmp_path), SCRIPT, "--rag", str(REPO), "--sheets", "Gmae")
    assert code == 2 and "no event sheet named 'Gmae'; closest: Game" in out, out


def test_review_without_a_project(tmp_path):
    code, out = run(tmp_path, SCRIPT, "--rag", str(REPO))
    assert code == 1 and "no project.c3proj" in out, out


# --- a label placed once beside a card that moves without it -----------------------------------
def hand(root: Path, link: bool = False, container: bool = True) -> Path:
    """A card drawn with its label set from its position, then laid out again by a function
    that moves the card alone; `link` adds the label as the card's child where it is made."""
    draw = [create("Card", "640", "600"), a("set-position", "CardLabel", x="Card.X - 60", y="Card.Y - 74")]
    if link:
        draw.append(a("add-child", "Card", child="CardLabel"))
    events = [function("Draw", [ev([], draw)]),
              function("Layout", [ev([c("for-each", object="Card")], [a("set-position", "Card", x="loopindex * 200",
                                                                          y="600")])])]
    root = write(root, {"Combat": events}, {"Card": ("Sprite", []), "CardLabel": ("Text", [])})
    if container:
        edit(root, "project.c3proj", lambda project: project.update(containers=[{"members": ["Card", "CardLabel"]}]))
    return root


def test_a_container_label_left_behind_by_a_moved_card(tmp_path):
    assert findings(hand(tmp_path), "follow") == [("follow", "", None, "Combat", 4)]


def test_a_label_added_as_a_child_follows(tmp_path):
    assert findings(hand(tmp_path, link=True), "follow") == []


def test_a_part_only_spawned_at_an_object_is_its_own(tmp_path):
    assert findings(hand(tmp_path, container=False), "follow") == []
