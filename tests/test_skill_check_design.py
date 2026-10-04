"""check_design.py and play_design.py: a game's design as data, its prototype, and the same tests as
preview plans. The editor is not opened: play_design's bindings, plans and generated JavaScript are
checked offline, the JavaScript against the prototype under Node when the machine has it."""
import copy
import json
import re
import shutil
import subprocess
import sys

import pytest

from tests.skill_helpers import REPO, SKILL, run

REFERENCE = SKILL / "references" / "designing-a-game.md"


def module(name):
    sys.path.insert(0, str(SKILL / "scripts"))
    try:
        return __import__(name)
    finally:
        sys.path.pop(0)


def example() -> dict:
    """The design the reference shows, with a real example id."""
    block = re.search(r"```json\n(.*?)```", REFERENCE.read_text(encoding="utf-8"), re.S).group(1)
    design = json.loads(block)
    design["reference"]["example"] = sorted(p.stem for p in (REPO / "data" / "c3-examples" / "en-US").glob("*.json"))[0]
    return design


def check(tmp_path, design) -> tuple[int, str]:
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
    return run(tmp_path, SKILL / "scripts" / "check_design.py", str(path), "--rag", str(REPO))


def test_check_design_passes_the_reference_example_and_prints_its_tables(tmp_path):
    code, out = check(tmp_path, example())
    assert code == 0, out
    assert "hit (tap a hole): hit -> the mole jumps to another hole" in out
    assert "  escapes  global  new-game, escape  escape, lose" in out
    assert "ok    three escapes lose, a tap restarts: 7 steps, lose reached, restarted" in out
    assert out.splitlines()[-1].startswith("ok: design complete; 4 tests pass in the prototype, win and lose reached")


def test_check_design_names_every_missing_table(tmp_path):
    code, out = check(tmp_path, {"game": "X"})
    assert code == 1
    for key in ("core_loop", "reference", "screen", "state", "inputs", "rules", "win", "lose", "tests"):
        assert re.search(rf"^{key}: missing", out, re.M), (key, out)
    assert "the tests did not run" in out


def test_check_design_names_the_test_step_and_the_values_of_a_failed_expect(tmp_path):
    design = example()
    design["rules"][1]["do"][0] = "score += 2"
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("tests[0].steps[2]: expect score = 1: false in the prototype; score = 2. Rules that ran in this test "
            "so far: new-game x1, hit x1") in out


def test_check_design_refuses_a_restart_that_keeps_a_global_of_the_last_game(tmp_path):
    """A restart keeps globals, as the runtime does: a new game needs them set in a start rule."""
    design = example()
    design["rules"][0]["do"].remove("escapes = 0")
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("after the restart escapes is 3, and a new game starts with 0: a restart keeps global variables, so "
            "set escapes in a \"start\" rule") in out


def test_check_design_refuses_a_rule_no_test_reaches_and_a_missing_feedback(tmp_path):
    design = example()
    design["rules"].append({"id": "bonus", "on": "hit", "if": ["score >= 100"], "do": ["score += 10"]})
    design["rules"][1].pop("feedback")
    code, out = check(tmp_path, design)
    assert code == 1
    assert "rules[4] 'bonus': rule bonus never ran in any test" in out
    assert "rules[1] 'hit'.feedback: missing: the input hit fires this rule" in out


def test_check_design_reads_the_sheet_syntax_and_says_what_to_write(tmp_path):
    design = example()
    design["rules"][1]["if"][1] = "h == hole"
    design["state"][0]["stored_in"] = "Score count"
    code, out = check(tmp_path, design)
    assert code == 1
    assert "rules[1] 'hit'.if[1]: '==' in 'h == hole': the event sheet writes '='" in out
    assert "state[0].stored_in: 'Score count'" in out


def test_the_prototype_runs_events_as_the_runtime_does():
    """Else after a sibling that ran is skipped, a Wait defers the sub-events too, & joins text and is a
    logical and on numbers, At() outside an Array is 0, comparisons give 1 or 0."""
    gm = module("game_model")
    design = gm.Design({
        "game": "probe", "core_loop": "one tap", "reference": {"example": "x", "takes": "nothing"},
        "screen": {"all": "screen"},
        "state": [{"name": "a", "start": 0, "stored_in": "global"}, {"name": "b", "start": 0, "stored_in": "global"},
                  {"name": "t", "start": "", "stored_in": "Label.text"},
                  {"name": "G", "size": [3, 3], "stored_in": "Array"}],
        "inputs": [{"name": "go", "player": "tap", "game": {"tap": [0.5, 0.5]}}],
        "rules": [{"id": "go", "on": "go", "do": ["a = 1"], "feedback": "it goes", "children": [
            {"id": "first", "if": ["a = 1"], "do": ["b = 1"]},
            {"id": "other", "else": True, "do": ["b = 2"]},
            {"id": "later", "if": ["b > 0"], "do": ["wait 0.5", "t = \"n\" & a & (2 > 1)"], "children": [
                {"id": "deep", "do": ["G.At(5, 5) = 9", "a = G.At(5, 5) + (1 & 0) + (1 & 1)"]}]}]}],
        "win": "a = 1", "lose": "none",
        "tests": [{"name": "t", "steps": [{"do": "go"}]}]})
    assert not design.problems, design.problems
    sim = gm.Sim(design)
    sim.fire("go", {})
    assert sim.values["b"] == 1 and sim.ran.get("other") is None
    assert sim.values["t"] == "" and sim.ran.get("deep") is None      # 0.15 s in: the wait holds them
    sim.advance(0.5)
    assert sim.values["t"] == "n11" and sim.values["a"] == 1


def write_project(root, globals_, types, placed, viewport=(720, 1280)):
    """The files play_design reads: project.c3proj, the types, one sheet, the first layout."""
    (root / "objectTypes").mkdir(parents=True)
    (root / "eventSheets").mkdir()
    (root / "layouts").mkdir()
    (root / "project.c3proj").write_text(json.dumps({
        "name": "probe", "viewportWidth": viewport[0], "viewportHeight": viewport[1], "firstLayout": "Game",
        "objectTypes": {"items": list(types), "subfolders": []}, "eventSheets": {"items": ["Game"], "subfolders": []},
        "layouts": {"items": ["Game"], "subfolders": []}}), encoding="utf-8")
    for name, (plugin, ivars) in types.items():
        (root / "objectTypes" / f"{name}.json").write_text(json.dumps(
            {"name": name, "plugin-id": plugin, "instanceVariables": [{"name": v} for v in ivars]}), encoding="utf-8")
    (root / "eventSheets" / "Game.json").write_text(json.dumps({"name": "Game", "events": [
        {"eventType": "variable", "name": n, "type": t, "initialValue": v} for n, (t, v) in globals_.items()]}),
        encoding="utf-8")
    (root / "layouts" / "Game.json").write_text(json.dumps({"name": "Game", "layers": [
        {"name": "Game", "parallaxX": 1, "parallaxY": 1, "instances": [i for i in placed if i.get("layer") != "UI"]},
        {"name": "UI", "parallaxX": 0, "parallaxY": 0, "instances": [i for i in placed if i.get("layer") == "UI"]}]}),
        encoding="utf-8")


def whack_project(root):
    write_project(root, {"score": ("number", "0"), "escapes": ("number", "0"), "over": ("number", "0")},
                  {"Mole": ("Sprite", ["hole"]), "Hole": ("Sprite", ["index"]), "Message": ("Text", []),
                   "ScoreText": ("Text", []), "Touch": ("Touch", [])},
                  [{"type": "Mole", "world": {"x": 100, "y": 100}, "instanceVariables": {"hole": 4}},
                   {"type": "Hole", "world": {"x": 100, "y": 100}, "instanceVariables": {"index": 0}},
                   {"type": "Message", "layer": "UI", "world": {"x": 0, "y": 0}, "properties": {"text": ""}},
                   {"type": "ScoreText", "layer": "UI", "world": {"x": 0, "y": 0}, "properties": {"text": "Score: 0"}}])


def test_play_design_writes_one_plan_per_test_and_taps_by_instance_variables(tmp_path):
    design = tmp_path / "design.json"
    design.write_text(json.dumps(example()), encoding="utf-8")
    whack_project(tmp_path / "game")
    plans = tmp_path / "plans.json"
    code, out = run(tmp_path, SKILL / "scripts" / "play_design.py", str(design), "--project", str(tmp_path / "game"),
                    "--plan-only", str(plans))
    assert code == 0, out
    assert "wrote 5 plans" in out
    written = json.loads(plans.read_text(encoding="utf-8"))
    hit = written[1]["steps"]
    assert hit[0] == {"wait": 0.4}
    assert "H.put(\"Mole\", \"hole\", 4.0);" in hit[1]["js"]
    assert 'H.eq(H.v(i.instVars["index"]), 4.0) === 1' in hit[2]["tap"]["js"] and hit[3] == {"wait": 0.15}
    assert "H.eq(H.v(runtime.globalVars[\"score\"]), 1.0)" in hit[4]["js"]
    again = written[4]["steps"]
    assert {"tap": {"x": 360.0, "y": 1152.0, "layer": "UI"}} in again


def play(tmp_path, data, *args):
    design = tmp_path / "design.json"
    design.write_text(json.dumps(data), encoding="utf-8")
    if not (tmp_path / "game").exists():
        whack_project(tmp_path / "game")
    return design, run(tmp_path, SKILL / "scripts" / "play_design.py", str(design), "--project", str(tmp_path / "game"),
                       "--plan-only", str(tmp_path / "plans.json"), *args)


def test_play_design_refuses_a_name_the_project_lacks(tmp_path):
    data = example()
    data["inputs"][0]["game"]["args"] = {"h": "number"}
    _, (code, out) = play(tmp_path, data)
    assert code == 1
    assert "inputs[0].game.args.h: Hole has no instance variable number; it has index" in out
    assert not (tmp_path / "plans.json").exists()


def test_play_design_takes_the_project_start_only_when_the_prototype_still_passes(tmp_path):
    """Where the layout's grid placed an instance is the project's to say; the design adopts it, played again."""
    data = example()
    data["state"][4]["start"] = 7
    _, (code, out) = play(tmp_path, data)
    assert code == 1
    assert ("state[4]: hole starts as 4 in the project (Mole.hole) and 7 in the design; write 4 as its start in the "
            "design and change nothing in the project") in out
    design, (code, out) = play(tmp_path, data, "--adopt-starts")
    assert code == 0, out
    assert "adopted the project's start values into" in out and "hole = 4; the prototype still passes" in out
    assert json.loads(design.read_text(encoding="utf-8"))["state"][4]["start"] == 4
    data = example()
    data["rules"][0]["do"].remove("score = 0")      # nothing sets the score back: the first launch's value counts
    (tmp_path / "game" / "eventSheets" / "Game.json").write_text(json.dumps({"name": "Game", "events": [
        {"eventType": "variable", "name": n, "type": "number", "initialValue": v}
        for n, v in (("score", "5"), ("escapes", "0"), ("over", "0"))]}), encoding="utf-8")
    _, (code, out) = play(tmp_path, data, "--adopt-starts")
    assert code == 1
    assert "with the project's start values (score = 5) the prototype refuses the design:" in out
    assert "tests[0].steps[2]: expect score = 1: false in the prototype; score = 6." in out


def test_play_design_finds_a_play_area_off_the_middle():
    pd = module("play_design")
    layers = {"Game": {"parallax": [1, 1], "shown": True, "view": [0, 0, 720, 1280]}}
    board = {"type": "Board", "uid": 3, "layer": "Game", "box": [0, 300, 480, 780], "shown": True, "angle": 0, "root": 3}
    found = pd.centre_findings({"viewport": [720, 1280], "layers": layers, "instances": [board]})
    assert [f["rule"] for f in found] == ["centre"]
    assert "has its middle at x 240 and the screen's is at 360" in found[0]["line"]
    board["box"] = [120, 300, 600, 780]
    assert pd.centre_findings({"viewport": [720, 1280], "layers": layers, "instances": [board]}) == []


EXPRESSIONS = ["1 + 2 * 3", "\"a\" & 1 & \"b\"", "1 & 0", "2 | 0", "score = 3 ? \"yes\" : \"no\"", "-score + 10 % 4",
               "max(1, score, 2) - min(4, 5)", "clamp(score * 3, 0, 5)", "floor(7 / 2) + ceil(0.2) + round(2.5)",
               "find(label, \"OVER\")", "len(label) + abs(-2)", "label = \"Game over\"", "score <> 3",
               "G.At(1, 2) + G.At(9, 9) + G.Width", "InARow(G, 3, 1)", "count(G, 1)", "2 ^ 3 >= 8", "str(score) & \"!\"",
               "stones * 10 + blacks"]


def test_the_generated_javascript_evaluates_as_the_prototype(tmp_path):
    """Each expression compiled for the runtime gives what the prototype gives, run under Node on a stand-in
    runtime that holds the same values: a count of instances shown leaves out the hidden, the transparent and
    those on a hidden layer."""
    node = shutil.which("node")
    if not node:
        pytest.skip("no Node here")
    gm, pd = module("game_model"), module("play_design")
    design = gm.Design({"game": "probe", "core_loop": "none", "reference": {"example": "x", "takes": "x"},
                        "screen": {"a": "b"}, "state": [
                            {"name": "score", "start": 3, "stored_in": "global"},
                            {"name": "label", "start": "Game over", "stored_in": "Label.text"},
                            {"name": "G", "size": [3, 3], "stored_in": "Array"},
                            {"name": "stones", "start": 0, "stored_in": "Stone.shown"},
                            {"name": "blacks", "start": 0, "stored_in": "Stone.shown(frame=1)"}],
                        "inputs": [], "rules": [], "win": "score = 3", "lose": "none", "tests": []})
    sim = gm.Sim.__new__(gm.Sim)
    sim.d, sim.rng = design, None
    sim.values = {"score": 3.0, "label": "Game over", "stones": 2.0, "blacks": 1.0}
    sim.arrays = {"G": [[1.0, 0.0, 0.0], [0.0, 1.0, 5.0], [0.0, 0.0, 1.0]]}
    want = [sim.ev(gm.parse(e), {}) for e in EXPRESSIONS]
    body = ",\n".join(pd.compile_expr(gm.parse(e), design) for e in EXPRESSIONS)
    script = f"""
const grid = {json.dumps(sim.arrays["G"])};
const runtime = {{globalVars: {{score: 3}}, objects: {{
  Label: {{getFirstInstance: () => ({{text: "Game over", instVars: {{}}}})}},
  G: {{getFirstInstance: () => ({{width: 3, height: 3, getAt: (x, y) => grid[x][y]}})}},
  Stone: {{getAllInstances: () => [
    {{isVisible: true, opacity: 1, layer: {{isVisible: true}}, animationFrame: 1}},
    {{isVisible: true, opacity: 1, layer: {{isVisible: true}}, animationFrame: 2}},
    {{isVisible: false, opacity: 1, layer: {{isVisible: true}}, animationFrame: 1}},
    {{isVisible: true, opacity: 0, layer: {{isVisible: true}}, animationFrame: 1}},
    {{isVisible: true, opacity: 1, layer: {{isVisible: false}}, animationFrame: 1}}]}}}}}};
{pd.HELPERS}
console.log(JSON.stringify([{body}]));
"""
    (tmp_path / "probe.js").write_text(script, encoding="utf-8")
    got = json.loads(subprocess.run([node, str(tmp_path / "probe.js")], capture_output=True, text=True,
                                    encoding="utf-8", check=True).stdout)
    for expr, w, g in zip(EXPRESSIONS, want, got):
        assert (w == g) if isinstance(w, str) else abs(float(w) - float(g)) < 1e-9, (expr, w, g)


def test_a_failed_expect_names_the_rule_that_would_change_it_and_the_condition_that_holds_it_back(tmp_path):
    design = example()
    design["inputs"][1]["game"]["region"] = [0, 0.8, 1, 1]      # a tap on a hole is outside it: not a tap on again
    design["tests"][0]["steps"] = [{"set": "hole = 4"}, {"set": "over = 1"}, {"do": "hit", "h": 4}, {"expect": "score = 1"}]
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("hit would change it, fired by hit, and did not run: over = 0 is false (over = 1); h = hole needs the "
            "arguments of hit") in out


def test_check_design_keeps_a_design_small(tmp_path):
    design = example()
    design["state"] += [{"name": f"extra{i}", "start": 0, "stored_in": "global", "const": True} for i in range(8)]
    code, out = check(tmp_path, design)
    assert code == 1
    assert "state: 14 rows; at most 10" in out


def test_a_design_reads_its_state_not_the_game_and_taps_the_screen_where_an_argument_says(tmp_path):
    design = example()
    design["rules"][1]["if"].append("Mole.X > 0")
    code, out = check(tmp_path, design)
    assert ("Mole.X reads an object of the game, and a design reads only its own state and the input's arguments. "
            "Give it a state row, {\"name\": \"moleX\", \"start\": ..., \"stored_in\": \"Mole.x\"}") in out
    design = example()
    design["inputs"][1] = {"name": "again", "player": "tap anywhere", "args": ["x"],
                           "game": {"tap": "screen", "args": {"x": "x"}}}
    design["tests"][3]["steps"][3] = {"do": "again", "x": 100}
    code, out = check(tmp_path, design)
    assert code == 0, out
    (tmp_path / "design.json").write_text(json.dumps(design), encoding="utf-8")
    whack_project(tmp_path / "game")
    code, out = run(tmp_path, SKILL / "scripts" / "play_design.py", str(tmp_path / "design.json"), "--project",
                    str(tmp_path / "game"), "--plan-only", str(tmp_path / "plans.json"))
    assert code == 0, out
    assert {"tap": {"x": 100.0, "y": 1024.0}} in json.loads((tmp_path / "plans.json").read_text(encoding="utf-8"))[4]["steps"]


def test_a_sub_rule_with_no_condition_beside_cases_is_refused(tmp_path):
    design = example()
    design["rules"][2]["children"][0]["if"] = []
    design["rules"][2]["children"].append({"id": "fine", "if": ["escapes < 3"], "do": ["message = \"\""]})
    code, out = check(tmp_path, design)
    assert "rules[2].children[0].if: empty, so this sub-rule runs every time beside siblings that test a case" in out


def board_game(stones: bool = True) -> dict:
    """Two players place pieces on a 9 x 9 board; five in a row wins. With stones, a row counts the pieces shown."""
    state = [{"name": "turn", "start": 1, "stored_in": "global"}, {"name": "over", "start": 0, "stored_in": "global"},
             {"name": "status", "start": "Black to move", "stored_in": "Status.text"},
             {"name": "Board", "size": [9, 9], "stored_in": "Array"}]
    place = ["Board.At(c, r) = turn"]
    if stones:
        state.append({"name": "stones", "start": 0, "stored_in": "Stone.shown"})
        place.append("stones += 1")
    five = [{"do": "place", "c": x, "r": r} for x in range(5) for r in (0, 1)][:9]
    return {
        "game": "Five", "core_loop": "Two players place stones in turn; five in a row wins",
        "reference": {"example": sorted(p.stem for p in (REPO / "data" / "c3-examples" / "en-US").glob("*.json"))[0],
                      "takes": "a board of cells tapped by their col and row"},
        "screen": {"board": "centre", "status": "below the board"},
        "state": state,
        "inputs": [{"name": "place", "player": "tap an empty crossing", "args": ["c", "r"],
                    "game": {"tap": "Cell", "args": {"c": "col", "r": "row"}}},
                   {"name": "again", "player": "tap below the board", "game": {"tap": [0.5, 0.95]}}],
        "rules": [{"id": "new-game", "on": "start", "do": ["turn = 1", "over = 0"]},
                  {"id": "place", "on": "place", "if": ["over = 0", "Board.At(c, r) = 0"], "do": place,
                   "feedback": "a stone of the side to move appears on the crossing", "children": [
                       {"id": "win", "if": ["InARow(Board, 5, turn)"], "do": ["over = 1", "status = \"Five! Tap\""]},
                       {"id": "next", "else": True, "do": ["turn = 3 - turn",
                                                           "status = turn = 1 ? \"Black to move\" : \"White to move\""]}]},
                  {"id": "restart", "on": "again", "if": ["over = 1"], "do": ["restart"], "feedback": "an empty board"}],
        "win": "over = 1", "lose": "none",
        "tests": [{"name": "a stone shows and the turn passes", "steps": [
                      {"do": "place", "c": 4, "r": 4}, {"expect": "turn = 2"}, {"expect": "status = \"White to move\""}]
                   + ([{"expect": "stones = 1"}] if stones else [])},
                  {"name": "five across win, a tap restarts", "steps": five + [
                      {"expect": "over = 1"}, {"expect": "find(status, \"Five\") >= 0"}, {"do": "again"}, {"wait": 0.2},
                      {"expect": "over = 0"}]}]}


def test_an_array_cell_an_input_writes_needs_a_count_of_the_instances_shown(tmp_path):
    """The status line changing says nothing of the stone: a rule that writes a board cell changes a count of the
    pieces shown, and a test expects it after the tap."""
    code, out = check(tmp_path, board_game(stones=False))
    assert code == 1
    assert ("rules[1] 'place': rule place writes a cell of Board, and an Array is not on screen: the player sees the "
            "cell as an instance. Add a row that counts the instances shown") in out
    design = board_game()
    code, out = check(tmp_path, design)
    assert code == 0, out
    design["tests"][0]["steps"].pop()
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("inputs[0]: no test expects what the player sees after place: stones. After a step {\"do\": \"place\", "
            "\"c\": ..., \"r\": ...}, add {\"expect\": \"stones = ...\"}") in out
    design = board_game()
    design["tests"][0]["steps"].insert(0, {"set": "stones = 3"})
    code, out = check(tmp_path, design)
    assert "tests[0].steps[0].set: stones counts the Stone instances the player sees, and a fixture cannot" in out


def test_an_input_that_changes_nothing_the_player_sees_is_refused(tmp_path):
    design = example()
    design["rules"][1]["do"].remove("scoreLine = \"Score: \" & score")
    design["rules"][2]["children"][0]["do"][1] = "message = \"Over\""
    design["tests"][0]["steps"].pop()
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("inputs[0]: the input hit changes only score, hole, which the player does not see (a global, an Array, an "
            "instance variable)") in out


def test_a_game_over_at_launch_is_refused_though_a_fixture_steps_past_it(tmp_path):
    design = example()
    design["lose"] = "lives <= 0"
    design["state"].append({"name": "lives", "start": 0, "stored_in": "global"})
    design["rules"][2]["do"].append("lives -= 1")
    for t in design["tests"]:
        t["steps"].insert(0, {"set": "lives = 3"})
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("lose: lives <= 0 holds on the first screen, before the player does anything (lives = 0 after the start "
            "rules): the game is over at launch") in out


def stone_project(root, placed):
    write_project(root, {"turn": ("number", "1"), "over": ("number", "0")},
                  {"Stone": ("Sprite", []), "Cell": ("Sprite", ["col", "row"]), "Status": ("Text", []),
                   "Board": ("Arr", []), "Touch": ("Touch", [])},
                  [{"type": "Cell", "world": {"x": 0, "y": 0}, "instanceVariables": {"col": 0, "row": 0}},
                   {"type": "Status", "layer": "UI", "world": {"x": 0, "y": 0}, "properties": {"text": "Black to move"}},
                   {"type": "Board", "world": {"x": 0, "y": 0}}] + placed)


def test_play_design_counts_the_instances_shown_from_the_layout_and_in_the_runtime(tmp_path):
    design = board_game()
    design["state"].append({"name": "blacks", "start": 0, "stored_in": "Stone.shown(frame=1)"})
    design["rules"][1]["do"].append("blacks += turn = 1 ? 1 : 0")
    design["tests"][0]["steps"].append({"expect": "blacks = 1"})
    assert check(tmp_path, design)[0] == 0
    path = tmp_path / "design.json"
    path.write_text(json.dumps(design), encoding="utf-8")
    hidden = [{"type": "Stone", "world": {"x": 0, "y": 0}, "properties": {"initially-visible": False}}] * 3
    shown = [{"type": "Stone", "world": {"x": 0, "y": 0}, "properties": {"initial-frame": 1}}]
    stone_project(tmp_path / "game", hidden + shown)
    code, out = run(tmp_path, SKILL / "scripts" / "play_design.py", str(path), "--project", str(tmp_path / "game"),
                    "--plan-only", str(tmp_path / "plans.json"))
    assert code == 1
    assert "stones starts as 1 in the project (Stone.shown) and 0 in the design" in out
    assert "blacks starts as 1 in the project (Stone.shown(frame=1)) and 0 in the design" in out
    shutil.rmtree(tmp_path / "game")
    stone_project(tmp_path / "game", hidden)
    code, out = run(tmp_path, SKILL / "scripts" / "play_design.py", str(path), "--project", str(tmp_path / "game"),
                    "--plan-only", str(tmp_path / "plans.json"))
    assert code == 0, out
    plans = json.loads((tmp_path / "plans.json").read_text(encoding="utf-8"))
    assert any('H.shown("Stone", null)' in s.get("js", "") for s in plans[1]["steps"])
    assert any('H.shown("Stone", 1)' in s.get("js", "") for s in plans[1]["steps"])
    start = plans[0]["steps"][2]
    assert start["note"] == "start" and '"stones": ' in start["js"] and '"status": ' in start["js"]


def test_the_first_screen_is_held_to_the_prototype():
    """A value the first screen shows, and a win or lose there, read in the game against the prototype."""
    gm, pd = module("game_model"), module("play_design")
    design = gm.Design(example())
    still = pd.launch_values(design)
    assert still["ends"] == {"win": False, "lose": False}
    assert set(still["rows"]) == {"scoreLine", "message"}
    found = pd.launch_findings(design, {"rows": {"scoreLine": "Score: 0", "message": ""}, "ends": {"win": 0, "lose": 1}})
    assert len(found) == 1 and found[0].startswith(
        "lose: over = 1 is true on the first screen of the game and false in the prototype: the game is over at launch")
    found = pd.launch_findings(design, {"rows": {"scoreLine": "Score: 3", "message": ""}, "ends": {"win": 0, "lose": 0}})
    assert found == ["state[1]: scoreLine is \"Score: 3\" on the first screen of the game (ScoreText.text) and "
                     "\"Score: 0\" in the prototype. Compare the start rules' events and where the project starts it "
                     "with the design"]


def tapping(restart_if, win_do, tests=None) -> dict:
    """A board game in small: three taps on a cell win, a tap on the screen starts a new game."""
    return {"game": "Three", "core_loop": "tap cells until three are placed", "reference": example()["reference"],
            "screen": {"board": "centre"},
            "state": [{"name": "n", "start": 0, "stored_in": "global"}, {"name": "over", "start": 0, "stored_in": "global"},
                      {"name": "pieces", "start": 0, "stored_in": "Piece.shown"}],
            "inputs": [{"name": "place", "player": "tap a cell", "args": ["c"], "game": {"tap": "Cell", "args": {"c": "col"}}},
                       {"name": "again", "player": "tap once it is over", "game": {"tap": [0.5, 0.9]}}],
            "rules": [{"id": "new-game", "on": "start", "do": ["n = 0", "over = 0"]},
                      {"id": "place", "on": "place", "if": ["over = 0"], "do": ["n += 1", "pieces += 1"], "feedback": "a piece shows",
                       "children": [{"id": "win", "if": ["n >= 3"], "do": win_do}]},
                      {"id": "restart", "on": "again", "if": restart_if, "do": ["wait 0.3", "restart"],
                       "feedback": "a new game"}],
            "win": "over = 1", "lose": "none",
            "tests": tests or [
                {"name": "three win", "steps": [{"do": "place", "c": 0}, {"do": "place", "c": 1}, {"do": "place", "c": 2},
                                                {"expect": "over = 1"}, {"expect": "pieces = 3"}]},
                {"name": "a tap restarts", "steps": [{"set": "n = 3"}, {"set": "over = 1"}, {"do": "again"}, {"wait": 0.5},
                                                     {"expect": "over = 0"}, {"expect": "n = 0"}]}]}


def test_a_tap_on_an_object_fires_the_taps_on_the_screen_first_as_the_runtime_does(tmp_path):
    """Touch On any touch start fires for every tap and before On touched object, whatever the sheet's order:
    a restart that tests the state the winning tap sets does not fire on that tap."""
    code, out = check(tmp_path, tapping(["over = 1"], ["over = 1"]))
    assert code == 0, out
    code, out = check(tmp_path, tapping([], ["over = 1"]))      # a restart on every tap
    assert code == 1
    assert ("tests[0].steps[2] does place, a tap on Cell. Every tap is also a tap on the screen, so Touch On any "
            "touch start fires again for it, before On touched object, and rule restart ran.") in out
    design = tapping([], ["over = 1"])
    design["inputs"][1]["game"]["region"] = [0, 0.8, 1, 1]
    code, out = check(tmp_path, design)
    assert code == 0, out


def test_a_test_ends_with_a_settle_that_shows_what_a_wait_held_back(tmp_path):
    code, out = check(tmp_path, tapping(["over = 1"], ["over = 1", "wait 0.3", "restart"]))
    assert code == 1
    assert ("tests[0].steps[3]: expect over = 1 held at its step and is false 1 s after the test's last step; over = 0. "
            "over was changed by the restart of rule win, started by tests[0].steps[2] (place)") in out
    assert "give rule win a condition that is false then" in out


def test_a_tap_whose_position_the_prototype_does_not_know_is_refused_where_a_rule_reads_it(tmp_path):
    design = tapping(["over = 1"], ["over = 1"])
    design["state"].append({"name": "px", "start": 0, "stored_in": "Paddle.x"})
    design["inputs"].append({"name": "steer", "player": "tap where the paddle goes", "args": ["x"],
                             "game": {"tap": "screen", "args": {"x": "x"}}})
    design["rules"].append({"id": "follow", "on": "steer", "do": ["px = x"], "feedback": "the paddle moves"})
    design["tests"].append({"name": "steer", "steps": [{"do": "steer", "x": 100}, {"expect": "px = 100"}]})
    code, out = check(tmp_path, design)
    assert code == 1
    assert ("tests[0].steps[0]: the prototype stopped here: place is a tap on Cell, and every tap is also a tap on the "
            "screen: Touch On any touch start fires steer for it, before On touched object. Rule follow then reads x, "
            "the position of that tap, which the prototype does not know: in the game it is where the Cell lies.") in out
    design["rules"][-1]["if"] = ["over = 0"]      # the tap that starts a new game does not steer; a cell's tap does
    code, out = check(tmp_path, design)
    assert "tests[0].steps[0]: the prototype stopped here" in out and "tests[1].steps[2]" not in out, out


def test_a_region_belongs_to_a_tap_on_a_point_and_holds_it(tmp_path):
    design = example()
    design["inputs"][1]["game"]["region"] = [0, 0, 1, 0.5]
    design["inputs"][0]["game"]["region"] = [0, 0, 1, 1]
    code, out = check(tmp_path, design)
    assert code == 1
    assert "inputs[1].game.tap: [0.5, 0.9] lies outside its own region [0, 0, 1, 0.5]" in out
    assert "inputs[0].game.region: only a tap on a point has a region" in out


def test_play_design_reads_the_last_expects_again_after_the_settle(tmp_path):
    """The plan ends with the settle and the expects the prototype still held then; a timer's change is left out.
    A settled expect that fails in the game is named as a change after the last step."""
    design = tmp_path / "design.json"
    design.write_text(json.dumps(example()), encoding="utf-8")
    whack_project(tmp_path / "game")
    plans = tmp_path / "plans.json"
    code, out = run(tmp_path, SKILL / "scripts" / "play_design.py", str(design), "--project", str(tmp_path / "game"),
                    "--plan-only", str(plans))
    assert code == 0, out
    written = json.loads(plans.read_text(encoding="utf-8"))
    hit = written[1]["steps"]
    at = hit.index({"wait": 1.0, "note": "settle"})
    again = hit[at + 1:]
    assert len(again) == 2 and all(s["note"] == "settled" for s in again)
    assert [s["js"] for s in again] == [s["js"] for s in hit[at - 2:at]]
    settled = [s["js"] for s in written[4]["steps"] if s.get("note") == "settled"]
    assert len(settled) == 1 and "over" in settled[0]      # escapes goes on with the timer: not read again
    pd, gm, cd = module("play_design"), module("game_model"), module("check_design")
    data = gm.Design(example())
    _, origin = pd.test_plan(data.tests[0], data, pd.Model(tmp_path / "game"), cd.run_test(data, data.tests[0])["stable"])
    steps = [{"ok": True, "value": {"ok": not (o and o["kind"] == "settled" and o["text"] == "score = 1"),
                                    "seen": {"score": 0}}} for o in origin]
    runs = [{"started": True, "steps": [{"ok": True}, {"ok": True, "value": {}}]}, {"started": True, "steps": steps}]
    lines, code = pd.report(data, [origin], {"status": "opened", "project": "p", "title": "t", "editor": "e",
                                             "preview": {"plans": runs}})
    assert code == 1
    assert ("FAIL  a hit scores: tests[0].steps[2] expect score = 1: held at its step and is false 1 s after the "
            "test's last step in the game") in "\n".join(lines)
