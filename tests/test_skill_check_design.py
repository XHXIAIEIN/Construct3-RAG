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
            {"id": "later", "do": ["wait 0.5", "t = \"n\" & a & (2 > 1)"], "children": [
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
                   "Touch": ("Touch", [])},
                  [{"type": "Mole", "world": {"x": 100, "y": 100}, "instanceVariables": {"hole": 4}},
                   {"type": "Hole", "world": {"x": 100, "y": 100}, "instanceVariables": {"index": 0}},
                   {"type": "Message", "layer": "UI", "world": {"x": 0, "y": 0}, "properties": {"text": ""}}])


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
    data["state"][3]["start"] = 7
    _, (code, out) = play(tmp_path, data)
    assert code == 1
    assert ("state[3]: hole starts as 4 in the project (Mole.hole) and 7 in the design; write 4 as its start in the "
            "design and change nothing in the project") in out
    design, (code, out) = play(tmp_path, data, "--adopt-starts")
    assert code == 0, out
    assert "adopted the project's start values into" in out and "hole = 4; the prototype still passes" in out
    assert json.loads(design.read_text(encoding="utf-8"))["state"][3]["start"] == 4
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
               "G.At(1, 2) + G.At(9, 9) + G.Width", "InARow(G, 3, 1)", "count(G, 1)", "2 ^ 3 >= 8", "str(score) & \"!\""]


def test_the_generated_javascript_evaluates_as_the_prototype(tmp_path):
    """Each expression compiled for the runtime gives what the prototype gives, run under Node on a stand-in
    runtime that holds the same values."""
    node = shutil.which("node")
    if not node:
        pytest.skip("no Node here")
    gm, pd = module("game_model"), module("play_design")
    design = gm.Design({"game": "probe", "core_loop": "none", "reference": {"example": "x", "takes": "x"},
                        "screen": {"a": "b"}, "state": [
                            {"name": "score", "start": 3, "stored_in": "global"},
                            {"name": "label", "start": "Game over", "stored_in": "Label.text"},
                            {"name": "G", "size": [3, 3], "stored_in": "Array"}],
                        "inputs": [], "rules": [], "win": "score = 3", "lose": "none", "tests": []})
    sim = gm.Sim.__new__(gm.Sim)
    sim.d, sim.rng = design, None
    sim.values = {"score": 3.0, "label": "Game over"}
    sim.arrays = {"G": [[1.0, 0.0, 0.0], [0.0, 1.0, 5.0], [0.0, 0.0, 1.0]]}
    want = [sim.ev(gm.parse(e), {}) for e in EXPRESSIONS]
    body = ",\n".join(pd.compile_expr(gm.parse(e), design) for e in EXPRESSIONS)
    script = f"""
const grid = {json.dumps(sim.arrays["G"])};
const runtime = {{globalVars: {{score: 3}}, objects: {{
  Label: {{getFirstInstance: () => ({{text: "Game over", instVars: {{}}}})}},
  G: {{getFirstInstance: () => ({{width: 3, height: 3, getAt: (x, y) => grid[x][y]}})}}}}}};
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
    assert "state: 13 rows; at most 10" in out


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
