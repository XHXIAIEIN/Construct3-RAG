"""Play a design's acceptance tests in the Construct 3 editor, on the game
built from it, and check the look of its first screen.

    python scripts/play_design.py DESIGN.json [--project FOLDER] [--plan-only OUT.json]
                                  [--browser EXE] [--profile FOLDER] [--out RESULT.json] [--limit CHARS]

Run it after check_design.py passes on the design and the game is built from
it, check_project.py passing. It reads where the design says each piece of
state is kept ("stored_in": a global, an Array, an object's variable, text or
position, or a count of the instances shown) and how each input is done in the game ("game": tap an object by
its instance variables, tap a point of the screen, press a key), and refuses
a name the project does not have. Then it writes one preview_project.py plan
per test, from a first launch each, with the JavaScript generated from the
design's expressions by this script, and plays them in one editor session:

  - an input taps or presses, then lets the game run 0.15 s, as the prototype does
  - an expect reads the state from the runtime and must hold, as it held in
    the prototype; a failure names the test, the step, the values the game
    held, and the rules whose events to compare with the design
  - a set is the test's fixture, written into the runtime

Before it opens the editor it reads the project's files: every piece of state
starts as the design says (a global's initial value, an instance's place,
text or variable in the layout the game starts on, a count of shown instances).
Before the tests it previews the game once without input and checks the first
screen: what it shows (texts, frames, counts of instances) and whether the
win or the lose holds there, against the prototype, and the faults
review_look.py finds (a text cut by its box, two labels over each other, a HUD
instance cut by the screen's edge, instances stacked on one box), and a play
area off the screen's middle.

--plan-only writes the plans to OUT.json and plays nothing.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import c3project as c3
import game_model as gm
import open_in_editor as oe
import preview_project as play
import review_look as look

EPILOG = """examples:
  python scripts/play_design.py tools/design.json
  python scripts/play_design.py design.json --project "D:/Games/Gomoku" --plan-only .tmp/design-plans.json

output:
  opened   <project>  (<window title>, <the editor it opened in>)
  first screen: 1 finding
    look: Text Status uid 9 "White wins! Tap to play again": the text needs 380x40 px and its box is 288x40 ...
  tests:
    ok    a blocked four does not win: 12 steps
    FAIL  white wins on a diagonal: tests[2].steps[10] expect over >= 1: false in the game ...
  played: 2 of 3 tests pass, 2 findings on the first screen, 0 runtime errors

exit codes: 0 every test passes and the first screen has no finding; 1 a test failed, a finding, a runtime
error, or the project did not open; 2 the design, the project or the editor could not be used; 3 no browser
"""

TAP_PAUSE = gm.AFTER_INPUT
CENTRE_SLACK = 0.06        # share of the viewport's width the play area's middle may sit off the screen's
PLAY_AREA = 0.4            # a sprite at least this share of the viewport's width or height is the play area

# Shared by every generated step: how the design's expressions read and write the runtime.
HELPERS = r"""const H = {
  first: t => { const o = runtime.objects[t]; return o ? o.getFirstInstance() : null; },
  v: x => typeof x === 'boolean' ? (x ? 1 : 0) : (x === undefined || x === null ? 0 : x),
  s: x => typeof x === 'number' ? String(Math.round(x * 1e9) / 1e9) : String(H.v(x)),
  t: x => { if (typeof x === 'string') throw new Error(`the text "${x}" stands where a condition is tested`); return H.v(x) !== 0; },
  eq: (a, b) => (typeof a === typeof b ? a === b : H.s(a) === H.s(b)) ? 1 : 0,
  add: (a, b) => typeof a === 'string' || typeof b === 'string' ? H.s(a) + H.s(b) : a + b,
  and: (a, b) => typeof a === 'string' || typeof b === 'string' ? H.s(a) + H.s(b) : (H.t(a) && H.t(b) ? 1 : 0),
  cmp: (op, a, b) => { if (!(typeof a === 'string' && typeof b === 'string')) { a = Number(a); b = Number(b); }
    return (op === '<' ? a < b : op === '<=' ? a <= b : op === '>' ? a > b : a >= b) ? 1 : 0; },
  arr: t => { const a = H.first(t); if (!a) throw new Error(`no ${t} instance in the running layout`); return a; },
  at: (t, x, y) => { const a = H.arr(t); x = Math.floor(x); y = Math.floor(y || 0);
    return x >= 0 && y >= 0 && x < a.width && y < a.height ? H.v(a.getAt(x, y)) : 0; },
  setAt: (t, x, y, v) => { const a = H.arr(t); a.setAt(v, Math.floor(x), Math.floor(y || 0)); },
  inst: t => { const i = H.first(t); if (!i) throw new Error(`no ${t} instance in the running layout`); return i; },
  get: (t, p) => { const i = H.inst(t);
    if (p === 'frame') return i.animationFrame; if (p === 'angle') return i.angleDegrees;
    if (p === 'visible') return i.isVisible ? 1 : 0; if (i.instVars && p in i.instVars) return H.v(i.instVars[p]); return H.v(i[p]); },
  put: (t, p, v) => { const i = H.inst(t);
    if (p === 'frame') i.animationFrame = v; else if (p === 'angle') i.angleDegrees = v;
    else if (p === 'visible') i.isVisible = H.t(v); else if (i.instVars && p in i.instVars) i.instVars[p] = v; else i[p] = v; },
  inARow: (t, n, val) => { const a = H.arr(t);
    for (let x = 0; x < a.width; x++) for (let y = 0; y < a.height; y++)
      for (const [dx, dy] of [[1, 0], [0, 1], [1, 1], [1, -1]]) { let k = 0;
        for (; k < n; k++) { const cx = x + dx * k, cy = y + dy * k;
          if (cx < 0 || cy < 0 || cx >= a.width || cy >= a.height || H.eq(H.v(a.getAt(cx, cy)), val) !== 1) break; }
        if (k === n) return 1; }
    return 0; },
  count: (t, val) => { const a = H.arr(t); let c = 0;
    for (let x = 0; x < a.width; x++) for (let y = 0; y < a.height; y++) c += H.eq(H.v(a.getAt(x, y)), val); return c; },
  shown: (t, frame) => { const o = runtime.objects[t]; if (!o) throw new Error(`no object ${t} in the project`);
    return o.getAllInstances().filter(i => i.isVisible && i.opacity > 0 && (!i.layer || i.layer.isVisible)
      && (frame === null || i.animationFrame === frame)).length; },
};"""


class Binding(Exception):
    """The design names something the project does not have."""


def js_num(v: float) -> str:
    return repr(float(v)) if v == v and abs(v) != float("inf") else "0"


def compile_expr(node: gm.Node, design: gm.Design) -> str:
    """The expression as JavaScript over the helpers: names are read where the design stores them."""
    k = node.kind
    if k == "num":
        return js_num(node.value)
    if k == "str":
        return json.dumps(node.value, ensure_ascii=False)
    if k == "name":
        return read(node.value, design)
    if k == "at":
        x, y = (compile_expr(a, design) for a in (node.args + [gm.Node("num", 0.0)])[:2])
        return f"H.at({json.dumps(node.value)}, {x}, {y})"
    if k == "prop":
        return f"H.arr({json.dumps(node.value[0])}).{'width' if node.value[1] == 'Width' else 'height'}"
    if k == "un":
        return f"(-Number({compile_expr(node.args[0], design)}))"
    if k == "cond":
        c, a, b = (compile_expr(x, design) for x in node.args)
        return f"(H.t({c}) ? {a} : {b})"
    if k == "bin":
        a, b = (compile_expr(x, design) for x in node.args)
        op = node.value
        if op in ("=", "<>"):
            return f"H.eq({a}, {b})" if op == "=" else f"(1 - H.eq({a}, {b}))"
        if op in ("<", "<=", ">", ">="):
            return f"H.cmp({json.dumps(op)}, {a}, {b})"
        if op == "&":
            return f"H.and({a}, {b})"
        if op == "|":
            return f"((H.t({a}) || H.t({b})) ? 1 : 0)"
        if op == "+":
            return f"H.add({a}, {b})"
        if op == "^":
            return f"Math.pow(Number({a}), Number({b}))"
        return f"(Number({a}) {op} Number({b}))"
    if k == "call":
        f = node.value
        if f in gm.ARRAY_FUNCS:
            rest = ", ".join(compile_expr(a, design) for a in node.args[1:])
            return f"H.{'inARow' if f == 'InARow' else 'count'}({json.dumps(node.args[0].value)}, {rest})"
        args = [compile_expr(a, design) for a in node.args]
        nums = ", ".join(f"Number({a})" for a in args)
        a0, a1, last = args[0], args[1] if len(args) > 1 else "0", args[-1]
        if f == "clamp":
            return f"Math.min(Math.max(Number({a0}), Number({a1})), Number({last}))"
        if f == "len":
            return f"H.s({a0}).length"
        if f == "find":
            return f"H.s({a0}).toLowerCase().indexOf(H.s({last}).toLowerCase())"
        if f == "str":
            return f"H.s({a0})"
        if f == "random":
            return (f"(Math.random() * Number({a0}))" if len(args) == 1 else
                    f"(Number({a0}) + Math.random() * (Number({last}) - Number({a0})))")
        if f == "choose":
            return f"[{', '.join(args)}][Math.floor(Math.random() * {len(args)})]"
        return {"abs": f"Math.abs({nums})", "floor": f"Math.floor({nums})", "ceil": f"Math.ceil({nums})",
                "round": f"Math.floor({nums} + 0.5)", "sqrt": f"Math.sqrt(Math.max(0, {nums}))",
                "int": f"Math.trunc({nums})", "min": f"Math.min({nums})", "max": f"Math.max({nums})"}[f]
    raise Binding(f"cannot write {k} as JavaScript")


def split(where: str) -> tuple[str, str]:
    obj, _, prop = where.partition(".")
    return obj, prop


def read(name: str, design: gm.Design) -> str:
    st = design.state[name]
    if st.stored_in == "global":
        return f"H.v(runtime.globalVars[{json.dumps(name)}])"
    if st.shown:
        obj, frame = st.shown
        return f"H.shown({json.dumps(obj)}, {'null' if frame is None else int(frame)})"
    obj, prop = split(st.stored_in)
    return f"H.get({json.dumps(obj)}, {json.dumps(prop)})"


def write(eff: tuple, design: gm.Design) -> str:
    (name, index), op, value = eff[1], eff[2], eff[3]
    st = design.state[name]
    if st.shown:
        raise Binding(f"{name} counts instances; a fixture cannot write it")
    v = compile_expr(value, design)
    if index is not None:
        x, y = (compile_expr(a, design) for a in (index + [gm.Node("num", 0.0)])[:2])
        old = f"H.at({json.dumps(name)}, {x}, {y})"
        new = v if op == "=" else f"(Number({old}) {op[0]} Number({v}))"
        return f"H.setAt({json.dumps(name)}, {x}, {y}, {new});"
    new = v if op == "=" else f"(Number({read(name, design)}) {op[0]} Number({v}))"
    if st.stored_in == "global":
        return f"runtime.globalVars[{json.dumps(name)}] = {new};"
    obj, prop = split(st.stored_in)
    return f"H.put({json.dumps(obj)}, {json.dumps(prop)}, {new});"


# --- the project and the design's bindings ----------------------------------------------
class Model:
    """What play_design needs of the project: object types, their instance variables, globals, layers."""

    def __init__(self, project: Path) -> None:
        self.root = project
        self.c3proj = c3.load(project / "project.c3proj")
        self.types: dict[str, dict] = {}
        for name, sub in c3.folder_items(self.c3proj.get("objectTypes", {})):
            path = project / "objectTypes" / sub / f"{name}.json"
            if path.exists():
                self.types[name] = c3.load(path)
        self.globals: dict[str, dict] = {}
        for name, sub in c3.folder_items(self.c3proj.get("eventSheets", {})):
            path = project / "eventSheets" / sub / f"{name}.json"
            if path.exists():
                for ev in c3.load(path).get("events", []):
                    if ev.get("eventType") == "variable":
                        self.globals[ev["name"]] = ev
        self.hud: str | None = None
        self.placed: dict[str, list[dict]] = {}     # the instances of the layout the game starts on, by type
        self.seen: dict[str, list[dict]] = {}       # those of them the first screen shows, on a shown layer
        first = self.c3proj.get("firstLayout") or next((n for n, _ in c3.folder_items(self.c3proj.get("layouts", {}))), None)
        for name, sub in c3.folder_items(self.c3proj.get("layouts", {})):
            if name == first and (project / "layouts" / sub / f"{name}.json").exists():
                for layer in c3.load(project / "layouts" / sub / f"{name}.json").get("layers", []):
                    if layer.get("parallaxX") == 0 and layer.get("parallaxY") == 0 and not self.hud:
                        self.hud = layer["name"]
                    for inst in layer.get("instances", []):
                        self.placed.setdefault(inst.get("type"), []).append(inst)
                        if layer.get("isInitiallyVisible", True) is not False and                                 (inst.get("properties") or {}).get("initially-visible", True) is not False and                                 ((inst.get("world") or {}).get("color") or [1, 1, 1, 1])[3] > 0:
                            self.seen.setdefault(inst.get("type"), []).append(inst)
        self.size = (int(self.c3proj.get("viewportWidth", 854)), int(self.c3proj.get("viewportHeight", 480)))

    def plugin(self, name: str) -> str:
        return self.types.get(name, {}).get("plugin-id", "")

    def ivars(self, name: str) -> list[str]:
        return [v["name"] for v in self.types.get(name, {}).get("instanceVariables", [])]


def bindings(design: gm.Design, model: Model) -> list[str]:
    """What the design names that the project does not hold, each with what to change."""
    problems = []
    names = ", ".join(sorted(model.types)) or "none"
    for n, st in design.state.items():
        if st.stored_in == "global":
            if n not in model.globals:
                problems.append(f"{st.path}: {n} is stored in a global variable {n}, and no event sheet declares one; "
                                f"add {{\"eventType\": \"variable\", \"name\": \"{n}\", ...}} at the top of the sheet")
        elif st.shown:
            if st.shown[0] not in model.types:
                problems.append(f"{st.path}.stored_in: no object {st.shown[0]}; the objects are {names}")
        elif st.stored_in == "Array":
            if model.plugin(n) != "Arr":
                problems.append(f"{st.path}: {n} is stored in an Array {n}, and the project has no Array of that name; "
                                f"its objects are {names}")
        else:
            obj, prop = split(st.stored_in)
            if obj not in model.types:
                problems.append(f"{st.path}.stored_in: no object {obj}; the objects are {names}")
            elif prop not in gm.PROPS and prop not in model.ivars(obj):
                problems.append(f"{st.path}.stored_in: {obj} has no instance variable {prop}; it has "
                                f"{', '.join(model.ivars(obj)) or 'none'}, and every object has {', '.join(gm.PROPS)}")
    for name, i in design.inputs.items():
        tap = i["game"].get("tap")
        if isinstance(tap, str) and tap != "screen":
            if tap not in model.types:
                problems.append(f"{i['path']}.game.tap: no object {tap}; the objects are {names}")
                continue
            for arg, var in (i["game"].get("args") or {}).items():
                if var not in model.ivars(tap):
                    problems.append(f"{i['path']}.game.args.{arg}: {tap} has no instance variable {var}; it has "
                                    f"{', '.join(model.ivars(tap)) or 'none'}")
    return problems


def first_value(st: gm.State, model: Model):
    """What the project holds for a state row at the first launch, before any event runs; None when unknown."""
    if st.stored_in == "global":
        var = model.globals.get(st.name) or {}
        value = var.get("initialValue")
        if var.get("type") == "string" or value in (None, ""):
            return value
        try:
            return float(value)
        except ValueError:
            return value
    if st.shown:
        obj, frame = st.shown
        return float(sum(1 for i in model.seen.get(obj, [])
                         if frame is None or int((i.get("properties") or {}).get("initial-frame", 0)) == frame))
    obj, prop = split(st.stored_in)
    inst = model.placed[obj][0]
    if prop in ("x", "y"):
        return float(inst.get("world", {}).get(prop, 0))
    if prop == "text":
        return inst.get("properties", {}).get("text")
    if prop == "frame":
        return float(inst.get("properties", {}).get("initial-frame", 0))
    value = (inst.get("instanceVariables") or {}).get(prop)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


def starts(design: gm.Design, model: Model) -> tuple[list[str], dict[str, object]]:
    """Each state row the project starts with another value than the design, read from the files: the globals'
    initial values and the layout the game starts on. Read in the running game, a falling object has moved on.
    Returns the lines, and the project's value of each row that differs."""
    out, differ = [], {}
    for n, st in design.state.items():
        if st.kind == "array":
            continue
        if st.stored_in != "global" and not st.shown and not model.placed.get(split(st.stored_in)[0]):
            out.append(f"{st.path}: {n} is kept in {st.stored_in}, and the layout the game starts on has no "
                       f"{split(st.stored_in)[0]} instance; place one there")
            continue
        got = first_value(st, model)
        if got is not None and not same(got, st.start):
            differ[n] = got
            out.append(f"{st.path}: {n} starts as {gm.show(got)} in the project ({st.stored_in}) and "
                       f"{gm.show(st.start)} in the design; write {gm.show(got)} as its start in the design and "
                       f"change nothing in the project, then check_design.py again (--adopt-starts does both)")
    return out, differ


def adopt(data: dict, differ: dict[str, object]) -> tuple[dict, list[str]]:
    """The design with the project's start values, and what the prototype then refuses."""
    check = __import__("check_design")
    data = json.loads(json.dumps(data))
    for row in data["state"]:
        if row.get("name") in differ:
            row["start"] = differ[row["name"]]
    design = gm.Design(data)
    check.coverage(design)
    if not design.problems:
        check.play(design)
    return data, [f"{path}: {what}" for path, what in design.problems]


def find_js(obj: str, where: dict[str, str], args: dict) -> str:
    """JavaScript that returns the instance of obj whose variables hold the arguments, or says there is none."""
    tests = " && ".join(f"H.eq(H.v(i.instVars[{json.dumps(var)}]), {json.dumps(args[arg]) if isinstance(args[arg], str) else js_num(args[arg])}) === 1"
                        for arg, var in where.items()) or "true"
    said = ", ".join(f"{var} = {gm.show(args[arg])}" for arg, var in where.items())
    return (f"{HELPERS}\nconst all = runtime.objects[{json.dumps(obj)}] ? runtime.objects[{json.dumps(obj)}].getAllInstances() : [];\n"
            f"const i = all.find(i => {tests});\n"
            f"return i || {{error: {json.dumps(f'no {obj} with {said} to tap' if said else f'no {obj} to tap')} + ` (${{all.length}} {obj} in the layout)`}};")


# --- the plans ------------------------------------------------------------------------------
STILL = (0.2, 2.0)      # seconds after the launch between which a value the first screen shows holds still


def launch_values(design: gm.Design) -> dict:
    """What the prototype shows on the first screen and holds still through STILL: the seen rows other than a
    place or a size, which the layout grid decides, and whether the win and the lose hold."""
    sim = gm.Sim(design)
    sim.advance(STILL[0])
    early = dict(sim.values)
    won, lost = sim.won, sim.lost
    sim.advance(STILL[1] - STILL[0])
    rows = {n: v for n, v in early.items() if design.state[n].seen and same(sim.values[n], v)
            and design.state[n].stored_in.rsplit(".", 1)[-1] not in ("x", "y", "angle", "width", "height")}
    ends = {k: hit for k, node, hit, now in (("win", design.win, won, sim.won), ("lose", design.lose, lost, sim.lost))
            if node is not None and hit == now}
    return {"rows": rows, "ends": ends}


def launch_js(design: gm.Design, still: dict) -> str:
    """JavaScript that reads those rows and the win and the lose in the running game."""
    rows = ", ".join(f"{json.dumps(n)}: (() => {{ try {{ return {read(n, design)}; }} catch (e) {{ return e.message; }} }})()"
                     for n in still["rows"])
    ends = ", ".join(f"{k}: (() => {{ try {{ return H.t({compile_expr(design.win if k == 'win' else design.lose, design)})"
                     f" ? 1 : 0; }} catch (e) {{ return e.message; }} }})()" for k in still["ends"])
    return f"{HELPERS}\nreturn {{rows: {{{rows}}}, ends: {{{ends}}}}};"


def first_screen_plan(design: gm.Design, model: Model) -> dict:
    return {"viewport": list(model.size), "touch": True, "steps": [
        {"wait": 0.6},
        {"js": f"return await {look.LOOK_JS};", "note": "look"},
        {"js": launch_js(design, launch_values(design)), "note": "start"},
    ]}


def launch_findings(design: gm.Design, got: dict) -> list[str]:
    """Each value the first screen shows in the game and not in the prototype, and a win or lose at launch."""
    want = launch_values(design)
    out = []
    for k, hit in want["ends"].items():
        now = (got.get("ends") or {}).get(k)
        if isinstance(now, str):
            out.append(f"{k}: reading it on the first screen failed: {now}")
        elif now is not None and bool(now) != hit:
            names = sorted(n for n in gm.names_in(design.win if k == "win" else design.lose) if n in design.state)
            out.append(f"{k}: {design.data.get(k)} is {'true' if now else 'false'} on the first screen of the game and "
                       f"{'true' if hit else 'false'} in the prototype" + (": the game is over at launch" if now else "")
                       + f". Compare the start of {', '.join(names)} in the project and the events of the start rules "
                       f"{', '.join(r.id for r in design.rules if r.on == 'start') or '(none)'} with the design")
    for n, v in want["rows"].items():
        now = (got.get("rows") or {}).get(n)
        if now is None or not same(now, v):
            st = design.state[n]
            out.append(f"{st.path}: {n} is {gm.show(now) if not isinstance(now, (dict, list)) else now} on the first "
                       f"screen of the game ({st.stored_in}) and {gm.show(v)} in the prototype. Compare the start "
                       f"rules' events and where the project starts it with the design")
    return out


def test_plan(test: dict, design: gm.Design, model: Model) -> tuple[dict, list[dict]]:
    """The plan of one test, and for each plan step the test step it plays (None for a pause)."""
    steps, origin = [{"wait": 0.4}], [None]
    for s in test["steps"]:
        if s["kind"] == "do":
            game = design.inputs[s["input"]]["game"]
            if "key" in game:
                steps.append({"key": game["key"], "seconds": game.get("seconds", 0.1)})
            elif game["tap"] == "screen":
                where = {coord: s["args"][arg] for arg, coord in (game.get("args") or {}).items()}
                steps.append({"tap": {"x": round(float(where.get("x", model.size[0] / 2)), 1),
                                      "y": round(float(where.get("y", model.size[1] * 0.8)), 1)}})
            elif isinstance(game["tap"], list):
                fx, fy = game["tap"]
                point = {"x": round(fx * model.size[0], 1), "y": round(fy * model.size[1], 1)}
                if model.hud:
                    point["layer"] = model.hud
                steps.append({"tap": point})
            else:
                steps.append({"tap": {"js": find_js(game["tap"], game.get("args") or {}, s["args"])}})
            origin.append(s)
            steps.append({"wait": TAP_PAUSE})
            origin.append(None)
        elif s["kind"] == "wait":
            steps.append({"wait": s["seconds"]})
            origin.append(s)
        elif s["kind"] == "set":
            steps.append({"js": f"{HELPERS}\n{write(s['effect'], design)}\nreturn true;"})
            origin.append(s)
        else:
            names = sorted(n for n in gm.names_in(s["node"]) if n in design.state and design.state[n].kind != "array")
            seen = ", ".join(f"{json.dumps(n)}: (() => {{ try {{ return {read(n, design)}; }} catch (e) {{ return e.message; }} }})()"
                             for n in names)
            steps.append({"js": f"{HELPERS}\nlet ok;\ntry {{ ok = H.t({compile_expr(s['node'], design)}); }} "
                                f"catch (e) {{ ok = e.message; }}\nreturn {{ok, seen: {{{seen}}}}};"})
            origin.append(s)
    return {"viewport": list(model.size), "touch": True, "steps": steps}, origin


def writers(design: gm.Design, names: set[str]) -> list[str]:
    out = []
    for r in design.all_rules():
        if any(e[0] == "set" and e[1][0] in names for e in r.do) and r.id not in out:
            out.append(r.id)
    return out


# --- the first screen ---------------------------------------------------------------------
def centre_findings(snap: dict) -> list[dict]:
    """The play area, the largest sprite on a world layer that spans PLAY_AREA of the screen, off its middle."""
    vw, vh = snap["viewport"]
    best = None
    for i in snap["instances"]:
        layer = snap["layers"].get(i["layer"], {})
        if not i["shown"] or "textSize" in i or tuple(layer.get("parallax", (1, 1))) == (0, 0):
            continue
        b = i["box"]
        w, h = b[2] - b[0], b[3] - b[1]
        if (w >= PLAY_AREA * vw or h >= PLAY_AREA * vh) and w < 0.98 * vw and (best is None or w * h > best[0]):
            best = (w * h, i)
    if not best:
        return []
    i = best[1]
    view = snap["layers"][i["layer"]]["view"]
    middle = (i["box"][0] + i["box"][2]) / 2
    screen = (view[0] + view[2]) / 2
    if abs(middle - screen) > CENTRE_SLACK * vw:
        return [{"rule": "centre", "uids": [i["uid"]], "line":
                 f"{look.name(i)}, the play area, has its middle at x {round(middle)} and the screen's is at "
                 f"{round(screen)}: place it centred across the screen"}]
    return []


def same(game_value, design_value) -> bool:
    if isinstance(design_value, float) and isinstance(game_value, (int, float)) and not isinstance(game_value, bool):
        return abs(game_value - design_value) < 0.5
    return gm.show_plain(game_value) == gm.show_plain(design_value)


# --- running -----------------------------------------------------------------------------------
def run_all(project: Path, plans: list[dict], exe: str, profile: Path | None, shots: Path) -> dict:
    """One editor session; each plan previews the game afresh."""
    browser = oe.Browser(exe, (profile or oe.scratch(project)) / f"editor-{Path(exe).stem.lower()}", False)

    def then(browser_, target, page):
        ran = []
        for n, plan in enumerate(plans):
            ran.append(play.play(plan, shots / f"plan-{n}", project)(browser_, target, page))
        return {"started": True, "plans": ran}
    try:
        for n in range(len(plans)):
            (shots / f"plan-{n}").mkdir(parents=True, exist_ok=True)
        return oe.open_one(browser, oe.EDITOR, project, browser.profile / "project-design.c3p", None, False, then)
    finally:
        browser.close()


def report(design: gm.Design, plans_meta: list, result: dict) -> tuple[list[str], int]:
    lines: list[str] = []
    if result["status"] != "opened":
        return oe.report(result), 1
    lines.append(f"opened   {result['project']}  ({result['title']}, {result['editor']})")
    ran = result.get("preview") or {}
    runs = ran.get("plans") or []
    errors: list[str] = []
    problems = 0
    first = runs[0] if runs else {}
    screen: list[str] = []
    if not first.get("started"):
        return lines + [f"  preview did not run: {e}" for e in first.get("errors", ["no preview"])], 1
    errors += first.get("errors", [])
    by_note = dict(enumerate(first.get("steps", []), 1))
    snap = by_note.get(2, {}).get("value")
    if isinstance(snap, dict) and "instances" in snap:
        for f in look.findings(snap) + centre_findings(snap):
            screen.append(f"    look: {f['line']}")
    start = by_note.get(3, {}).get("value")
    if isinstance(start, dict):
        screen += [f"    start: {line}" for line in launch_findings(design, start)]
    for d in first.get("steps", []):
        errors += d.get("errors", [])
    lines.append(f"  first screen: {len(screen) or 'no'} finding{'s' if len(screen) != 1 else ''}")
    lines += screen
    problems += len(screen)
    lines.append("  tests:")
    passed = 0
    for test, origin, run in zip(design.tests, plans_meta, runs[1:]):
        if not run.get("started"):
            lines.append(f"    FAIL  {test['name']}: the preview did not run: {'; '.join(run.get('errors', []))[:300]}")
            problems += 1
            continue
        errors += run.get("errors", [])
        failed = None
        for d, s in zip(run.get("steps", []), origin):
            errors += d.get("errors", [])
            if failed:
                continue
            if not d["ok"]:
                where = s["path"] if s else test["path"]
                failed = f"{where}: {d['said'].split('; the window then')[0]}"
                continue
            if s and s["kind"] == "expect":
                got = d.get("value") or {}
                if got.get("ok") is not True:
                    seen = ", ".join(f"{n} = {gm.show(v) if not isinstance(v, (dict, list)) else v}"
                                     for n, v in (got.get("seen") or {}).items())
                    why = f"{got['ok']}" if isinstance(got.get("ok"), str) else "false in the game, true in the prototype"
                    rules = writers(design, gm.names_in(s["node"]))
                    failed = (f"{s['path']} expect {s['text']}: {why}" + (f"; {seen}" if seen else "") +
                              (f". Compare the events of rule{'s' if len(rules) > 1 else ''} {', '.join(rules)} with "
                               f"the design: print_sheet.py prints them" if rules else ""))
        if len(run.get("steps", [])) < len(origin) and not failed:
            failed = f"{test['path']}: the test stopped after {len(run.get('steps', []))} of {len(origin)} steps"
        if failed:
            problems += 1
            lines.append(f"    FAIL  {test['name']}: {failed}")
        else:
            passed += 1
            lines.append(f"    ok    {test['name']}: {len(test['steps'])} steps")
    unique = list(dict.fromkeys(e.splitlines()[0] for e in errors))
    lines += [f"  runtime: {e}" for e in unique[:8]]
    problems += len(unique)
    lines.append(f"  played: {passed} of {len(design.tests)} tests pass, {len(screen)} finding"
                 f"{'s' if len(screen) != 1 else ''} on the first screen, {len(unique)} runtime error"
                 f"{'s' if len(unique) != 1 else ''}")
    return lines, 1 if problems else 0


def main() -> int:
    c3.utf8_output()
    ap = c3.argument_parser(__doc__, EPILOG)
    ap.add_argument("design", type=Path, metavar="DESIGN.json")
    ap.add_argument("--plan-only", type=Path, metavar="OUT.json", help="write the plans and play nothing")
    ap.add_argument("--adopt-starts", action="store_true",
                    help="when the project starts a value elsewhere than the design (an instance placed on the grid), "
                         "write the project's value into the design, play the prototype again, and go on if it passes")
    ap.add_argument("--browser", metavar="EXE", help="the Chromium-based browser to start (default: Edge, Chrome or Chromium)")
    ap.add_argument("--profile", type=Path, metavar="FOLDER",
                    help="keep the browser profile in FOLDER/editor-<browser> instead of the project's .tmp/")
    ap.add_argument("--out", type=Path, help="the whole result as JSON (default: .tmp/play-design.json in the project)")
    args = ap.parse_args()
    try:
        data = json.loads(args.design.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        print(f"{args.design}: {e}. Write the design as JSON, as references/designing-a-game.md shows.", file=sys.stderr)
        return 2
    design = gm.Design(data)
    if design.problems:
        print(f"{args.design}: the design has {len(design.problems)} problem(s), the first {design.problems[0][0]}: "
              f"{design.problems[0][1]}. Run check_design.py on it until it ends with ok:, then this.", file=sys.stderr)
        return 2
    project = c3.find_project(args.project)
    if not project or not (project / "project.c3proj").exists():
        print(f"no project.c3proj found from {args.project or Path.cwd()} upward; pass --project <folder>", file=sys.stderr)
        return 2
    model = Model(project)
    missing = bindings(design, model)
    if missing:
        print("\n".join(missing + [f"design: {len(missing)} name(s) the project does not have; change the design "
                                   f"or the project so that they agree, then run this again"]))
        return 1
    differ_lines, differ = starts(design, model)
    if differ_lines and not (args.adopt_starts and len(differ) == len(differ_lines)):
        print("\n".join(differ_lines + [f"design: {len(differ_lines)} start value(s) differ from the project's"]))
        return 1
    if differ:
        data, refused = adopt(data, differ)
        said = ", ".join(f"{n} = {gm.show(v)}" for n, v in differ.items())
        if refused:
            print("\n".join([f"with the project's start values ({said}) the prototype refuses the design:"] + refused))
            return 1
        args.design.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        design = gm.Design(data)
        print(f"adopted the project's start values into {args.design}: {said}; the prototype still passes")
    plans = [first_screen_plan(design, model)]
    meta = []
    for t in design.tests:
        plan, origin = test_plan(t, design, model)
        plans.append(plan)
        meta.append(origin)
    for plan in plans:
        _, problems = play.check_plan(plan)
        if problems:
            print("the generated plan is refused, which is a fault of this script: " + "; ".join(problems), file=sys.stderr)
            return 2
    if args.plan_only:
        args.plan_only.parent.mkdir(parents=True, exist_ok=True)
        args.plan_only.write_text(json.dumps(plans, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {len(plans)} plans to {args.plan_only}: the first screen, then one per test")
        return 0
    exe = args.browser or oe.browser_path()
    if not exe:
        print("no Edge, Chrome or Chromium found here: write the plans with --plan-only and play each with the "
              "browser tool of this session, as references/reading-the-runtime.md says.")
        return 3
    out, shots = oe.kept(args.out, None, project, "play-design.json", "design")
    shots.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    try:
        result = run_all(project, plans, exe, args.profile, shots)
    except oe.EditorNotLoaded as e:
        print(f"the editor did not load: {e}. Check the network connection and run again.", file=sys.stderr)
        return 2
    except (oe.DevToolsError, OSError) as e:
        print(f"{exe} could not be driven: {e}. Pass another browser with --browser.", file=sys.stderr)
        return 2
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    lines, code = report(design, meta, result)
    shown = c3.fitting(lines, args.limit)
    print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"{len(lines) - shown} lines not printed: {out} keeps everything")
    print(f"ran in {time.monotonic() - began:.0f} s; full result in {out}")
    if code and result["status"] == "opened":
        print("next: fix each line where it says, in the events or in the design (then check_design.py again), "
              "and run this again")
    elif result["status"] != "opened":
        print(oe.NEXT)
    return code


if __name__ == "__main__":
    sys.exit(main())
