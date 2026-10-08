"""Check a game's design before any project file is written, and play its
acceptance tests on the design's own rules, without the editor.

    python scripts/check_design.py DESIGN.json [--rag FOLDER] [--limit CHARS]

The design is JSON, as references/designing-a-game.md describes: the user's
request in their words, what this round leaves for later, the core loop, the
closest official example and what it takes from it, the screen's regions,
the state table, the inputs, the rules as data (trigger, conditions,
effects, sub-rules), win and lose, and the acceptance tests. The script reads
it and refuses a gap by its path: a missing table, an empty list of what is
left for later, a name nothing defines,
a state no rule writes or nothing reads, a fact kept in two places, an input
without feedback, no rule that restarts a game that ends, an input that changes nothing the
player sees, and a cell of an Array an input writes with nothing on screen
that shows it: no count of instances, and no text or number whose expression
reads the Array.

Then it runs the rules as a prototype: each test from a first launch, 60
ticks a second, an input followed by 0.15 s of play, as the editor runs the
events. A tap is also a tap on the screen: it fires the screen inputs whose
region holds it, before the tapped object's rules, as the runtime does. After
the last step the game runs 1 s more and the test's last expects are read
again, so a restart that a Wait holds back shows. It refuses a failed expect
with the values the state held, a rule no test reaches, a win or a lose no
test reaches or that holds at launch, a win that comes within 120 s without
any input unless the design says waiting is the win, an input after which no
test expects what the player sees, a restart that leaves a value other than
a new game's, and rules that fire each other without end.
A design that passes holds a game whose rules close the loop; its ok line
repeats the request and what is left for later. Build it, one rule per
event, then play the same tests in the editor with play_design.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import c3project as c3
import game_model as gm

EPILOG = """examples:
  python scripts/check_design.py tools/design.json
  python scripts/check_design.py design.json --limit 0

output:
  design 'Gomoku': 2 inputs, 5 rules, 3 state rows, 3 tests
  input -> rule -> feedback:
    place (tap an empty crossing): place -> a stone appears and the status names the side to move
  state, stored in, written by, read by:
    turn  global  new-game, next  place, win, next
  tests:
    ok    five across wins: 11 steps, win reached
    FAIL  white wins on a diagonal: tests[1].steps[9] expect over = 1: false; over = 0, turn = 1
  tests[1].steps[9]: the expect failed ...
  design: 1 finding; fix each at its path and run this again

exit codes: 0 the design is complete and every test passes in the prototype; 1 findings;
2 the file cannot be read
"""


def where_read(design: gm.Design) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Which rules write and which read each state row; win and lose read too."""
    written: dict[str, list[str]] = {n: [] for n in design.state}
    read: dict[str, list[str]] = {n: [] for n in design.state}

    def add(table: dict, name: str, rid: str) -> None:
        if name in table and rid not in table[name]:
            table[name].append(rid)

    for r in design.all_rules():
        for c in r.when:
            for n in gm.names_in(c):
                add(read, n, r.id)
        for e in r.do:
            if e[0] == "set":
                add(written, e[1][0], r.id)
                for node in [e[3], *(e[1][1] or [])]:
                    for n in gm.names_in(node):
                        add(read, n, r.id)
                if e[2] != "=":
                    add(read, e[1][0], r.id)
            elif e[0] == "wait":
                for n in gm.names_in(e[1]):
                    add(read, n, r.id)
    for key, node in (("win", design.win), ("lose", design.lose)):
        for n in gm.names_in(node) if node else ():
            add(read, n, key)
    return written, read


def coverage(design: gm.Design) -> None:
    """Static gaps of the tables: state nobody writes or reads, no restart, an input the player does not see."""
    written, read = where_read(design)
    for n, s in design.state.items():
        if not written[n] and not s.const:
            design.bad(f"{s.path}", f"no rule changes {n}: write the rule that does, or mark the row \"const\": true "
                                    f"when it is a tuning value the game never changes")
        if not read[n] and not s.seen and not s.keep:
            design.bad(f"{s.path}", f"nothing reads {n}: no condition, effect, win or lose uses it and the player "
                                    f"does not see it; drop the row, or use it where the game decides something")
    if design.ends and not any(e[0] == "restart" for r in design.all_rules() for e in r.do):
        design.bad("rules", "no rule restarts the game: add one, fired by the input that starts a new game, whose "
                            "effects end with \"restart\". A demo of one mechanic that is never won or lost writes "
                            "\"win\": \"none\" and \"lose\": \"none\" instead, and needs no restart")
    seen_after(design)


def chain(rule: gm.Rule) -> list[gm.Rule]:
    """The rule and its sub-rules, all levels down."""
    out = [rule]
    for c in rule.children:
        out += chain(c)
    return out


def changes(rules: list[gm.Rule]) -> list[str]:
    """The state rows the effects of these rules set, in order."""
    out: list[str] = []
    for r in rules:
        for e in r.do:
            if e[0] == "set" and e[1][0] not in out:
                out.append(e[1][0])
    return out


def reads(design: gm.Design) -> dict[str, set[str]]:
    """Each rule's id and the rows it reads, its parents' conditions and effects counted: a sub-rule runs
    only after its parent read them."""
    out: dict[str, set[str]] = {}

    def walk(r: gm.Rule, above: set[str]) -> None:
        mine = set(above)
        for c in r.when:
            mine |= gm.names_in(c)
        for e in r.do:
            if e[0] == "set":
                for node in [e[3], *(e[1][1] or [])]:
                    mine |= gm.names_in(node)
            elif e[0] == "wait":
                mine |= gm.names_in(e[1])
        out[r.id] = mine
        for c in r.children:
            walk(c, mine)
    for r in design.rules:
        walk(r, set())
    return out


def playing(design: gm.Design, name: str) -> list[gm.Rule]:
    """The rules the input fires that do not restart: a restart shows the player a new game."""
    return [r for r in design.rules if r.on == name and not any(e[0] == "restart" for x in chain(r) for e in x.do)]


def shows(design: gm.Design, name: str) -> dict[str, list[str]]:
    """What the player sees after the input: the rows its rules change, or that change through rules reading
    them, each seen row with the names that lead to it."""
    fired = playing(design, name)
    changed = changes([x for r in fired for x in chain(r)])
    path = {n: [n] for n in changed}
    read_by = reads(design)
    grew = True
    while grew:
        grew = False
        for r in design.all_rules():
            source = next((n for n in path if n in read_by[r.id]), None)
            if source is None:
                continue
            for n in changes([r]):
                if n not in path:
                    path[n] = path[source] + [n]
                    grew = True
    return {n: p for n, p in path.items() if design.state[n].seen}


def showing(design: gm.Design, rules: list[gm.Rule], array: str) -> list[str]:
    """The seen rows these rules set that show the Array: a count of instances, or a text, x, y, frame or visible
    whose expression reads the Array (ARRAY.At(x, y), count(ARRAY, v) or its bare name)."""
    out: list[str] = []
    for r in rules:
        for e in r.do:
            if e[0] != "set" or e[1][1] is not None or e[1][0] in out:
                continue
            row = design.state[e[1][0]]
            if row.shown or row.seen and array in gm.names_in(e[3]):
                out.append(row.name)
    return out


def seen_after(design: gm.Design) -> None:
    """Refuse an input whose rules change only what the player does not see, and a cell of an Array written by an
    input with nothing on screen that shows it: no count of instances, and no seen row whose expression reads it."""
    for name, i in design.inputs.items():
        fired = playing(design, name)
        if not fired:
            continue
        for r in fired:
            for x in chain(r):
                arrays = list(dict.fromkeys(e[1][0] for e in x.do if e[0] == "set" and e[1][1] is not None))
                for a in arrays:
                    if showing(design, chain(x), a):
                        continue
                    design.bad(x.path, f"rule {x.id} writes a cell of {a}, and an Array is not on screen. Change in "
                               f"this rule or its sub-rules a row that shows it. A board: the player sees the cell as "
                               f"an instance, so add a row that counts the instances shown, such as {{\"name\": "
                               f"\"pieces\", \"start\": 0, \"stored_in\": \"Piece.shown\"}} (or "
                               f"\"Piece.shown(frame=1)\" for the pieces of frame 1), and change it beside the cell: "
                               f"\"pieces += 1\", or \"pieces = count({a}, 1)\". A list, such as stacked shields: the "
                               f"player reads it from a text or a number, so change a row stored in a text, x, y, "
                               f"frame or visible whose expression reads {a}, such as \"line = \\\"Shields \\\" & "
                               f"({a}.At(0, 0) + {a}.At(1, 0))\"; a text that does not read {a} shows nothing of the "
                               f"cell")
        if not shows(design, name):
            rows = changes([x for r in fired for x in chain(r)])
            design.bad(i["path"], f"the input {name} changes only {', '.join(rows) or 'nothing'}, which the player "
                       f"does not see (a global, an Array, an instance variable). Store what shows it where the "
                       f"player sees it, an object's text, x, y, frame or visible, or a count of instances, "
                       f"\"stored_in\": \"Piece.shown\", and change it in the rule {fired[0].id}")


def wanted(design: gm.Design, name: str) -> list[str]:
    """The seen rows a test expects after the input: where its rules write an Array cell, the rows that show the
    Array, since a status line that does not read it says nothing of the piece; else every seen row it changes."""
    rules = [x for r in playing(design, name) for x in chain(r)]
    rows = [n for x in rules for a in dict.fromkeys(e[1][0] for e in x.do if e[0] == "set" and e[1][1] is not None)
            for n in showing(design, chain(x), a)]
    return list(dict.fromkeys(rows)) or list(shows(design, name))


def expected_after(design: gm.Design) -> None:
    """Refuse an input after which no test expects what the player sees."""
    for name, i in design.inputs.items():
        rows = wanted(design, name)
        if not rows or not any(st["kind"] == "do" and st["input"] == name for t in design.tests for st in t["steps"]):
            continue        # no test does it: play() says so
        hit = False
        for t in design.tests:
            done = False
            for st in t["steps"]:
                done = done or st["kind"] == "do" and st["input"] == name
                if done and st["kind"] == "expect" and gm.names_in(st["node"]) & set(rows):
                    hit = True
        if not hit:
            row = design.state[rows[0]]
            design.bad(i["path"], f"no test expects what the player sees after {name}: {', '.join(rows)}. After a "
                       f"step {{\"do\": \"{name}\"" + "".join(f', "{a}": ...' for a in i["args"]) + f"}}, add "
                       f"{{\"expect\": \"{rows[0]} = ...\"}}, the value the game shows then; the editor reads it "
                       f"from {row.stored_in}")


def launch(design: gm.Design) -> None:
    """Refuse a win or a lose that holds on the first screen, before the player does anything; then play on without
    input and refuse a win that comes before the lose."""
    try:
        sim = gm.Sim(design)
        sim.advance(0.5)
    except gm.ModelError:
        return      # play() names it with the test
    for key, node, hit in (("win", design.win, sim.won), ("lose", design.lose, sim.lost)):
        if node is not None and hit:
            seen = ", ".join(f"{n} = {gm.show(sim.values[n])}" for n in sorted(gm.names_in(node)) if n in sim.values)
            design.bad(key, f"{design.data.get(key)} holds on the first screen, before the player does anything"
                            + (f" ({seen} after the start rules)" if seen else "") + ": the game is over at launch. "
                            f"Give the rows it reads the start of a new game, in the state's start and in a \"start\" "
                            f"rule, and play the tests from there rather than from a fixture. If the game is never "
                            f"{'won' if key == 'win' else 'lost'}, as a demo of one mechanic, write \"{key}\": \"none\"")
    if not (sim.won or sim.lost):
        idle(design, sim)


def idle(design: gm.Design, sim: gm.Sim) -> None:
    """Play on without input up to gm.IDLE seconds. A win that comes before the lose asks nothing of the player, so
    it is refused, unless "won_by_waiting" says that outlasting a timer is the win. That field is refused when the
    game is not won without input."""
    if design.win is None:
        return
    try:
        while sim.t < gm.IDLE and not (sim.won or sim.lost):
            sim.ops = 0         # OPS_MAX bounds one test, not this run; the rules bound what one tick runs
            sim.tick()
    except gm.ModelError:
        return      # play() names it with the test
    at = f"{sim.t:.1f} s"
    if sim.won and not sim.lost and not design.waiting:
        names = gm.names_in(design.win)
        hit = next(((n, rid) for n, rid in reversed(sim.set_by.items()) if n in names), None)
        by = "no rule set what it reads"
        if hit:
            top = top_rule(design, hit[1])
            by = (f"rule {hit[1]}" + (f" (a sub-rule of {top.id})" if top.id != hit[1] else "")
                  + f", fired by {top.on}, set {hit[0]}")
        design.bad("win", f"{design.data.get('win')} holds after {at} without any input"
                          + (", before the lose" if design.lose is not None else "") + f": {by}. A player who does "
                          f"nothing wins. Make the win need the player: give the rule that ends the round a condition "
                          f"that only the inputs make true, such as a score that the player's hits raise. Or let the "
                          f"end of the timer be the lose. If outlasting a timer is the win, as in a game where the "
                          f"player survives until it runs out, write \"won_by_waiting\": \"<what the player does while "
                          f"it runs>\"")
    elif not sim.won and design.waiting:
        how = f"the lose holds after {at}" if sim.lost else f"neither the win nor the lose holds in {gm.IDLE:g} s"
        design.bad("won_by_waiting", f"without any input the game is not won: {how}. The field is for a game won by "
                                     f"outlasting a timer; drop it")


def top_rule(design: gm.Design, rid: str) -> gm.Rule:
    """The top-level rule whose sub-rules hold the rule, or the rule itself."""
    parents = {c.id: r for r in design.all_rules() for c in r.children}
    rule = design.by_id[rid]
    while rule.id in parents:
        rule = parents[rule.id]
    return rule


def brief(text: str, most: int = 100) -> str:
    """The text on one line, cut after a word near `most` characters."""
    line = " ".join(text.split())
    if len(line) <= most:
        return line
    cut = line[:most]
    space = cut.rfind(" ")
    return (cut[:space] if space > most // 2 else cut).rstrip(",;:") + " ..."


def run_test(design: gm.Design, t: dict) -> dict:
    """Play one test from a first launch, then the settle. Returns a dict: "sim" (the Sim at the end), "failed"
    ((path, what) or None), "cover" (what the steps reached before the settle: ran, won, lost, restarts,
    after_restart), "stable" (the last expects that still hold after the settle; the editor reads them again after
    the same settle). Raises ModelError when the start rules fail."""
    sim = gm.Sim(design)
    failed = None
    last_do = None
    for step in t["steps"]:
        try:
            if step["kind"] == "do":
                sim.fire(step["input"], step["args"], step["path"])
                last_do = step
            elif step["kind"] == "wait":
                sim.advance(step["seconds"])
            elif step["kind"] == "set":
                sim.set(step["effect"])
            elif not gm.truth(sim.ev(step["node"], {})):
                seen = ", ".join(f"{n} = {state_text(sim, n)}" for n in sorted(gm.names_in(step["node"])))
                rules = ", ".join(f"{rid} x{c}" for rid, c in sim.ran.items()) or "none"
                failed = (step["path"], f"expect {step['text']}: false in the prototype; {seen}. Rules that "
                                        f"ran in this test so far: {rules}." + echo_note(design, sim, last_do, step["node"])
                                        + why_not(design, sim, step["node"])
                                        + " Change the rules, or the test when it expects the wrong thing")
                break
        except gm.ModelError as e:
            failed = (step["path"], f"the prototype stopped here: {e}")
            break
    tail = []
    for step in reversed(t["steps"]):
        if step["kind"] != "expect":
            break
        tail.insert(0, step)
    stable: list[dict] = []
    seen_by_steps = {"ran": dict(sim.ran), "won": sim.won, "lost": sim.lost, "restarts": sim.restarts,
                     "after_restart": list(sim.after_restart)}       # coverage counts the steps, not the settle
    if failed or not tail:
        return {"sim": sim, "cover": seen_by_steps, "failed": failed, "stable": stable}
    try:
        sim.settle()
    except gm.ModelError as e:
        return {"sim": sim, "cover": seen_by_steps, "failed": (t["path"], f"in the {gm.SETTLE:g} s after the last "
                                                                          f"step the prototype stopped: {e}"),
                "stable": stable}
    for step in tail:
        if gm.truth(sim.ev(step["node"], {})):
            stable.append(step)
            continue
        late = [(n, *sim.late[n]) for n in sorted(gm.names_in(step["node"])) if n in sim.late]
        if late and not failed:
            n, rid, said = late[0]
            seen = ", ".join(f"{m} = {state_text(sim, m)}" for m in sorted(gm.names_in(step["node"])))
            failed = (step["path"], f"expect {step['text']} held at its step and is false {gm.SETTLE:g} s after the "
                                    f"test's last step; {seen}. {n} was changed by {said}: the player sees that, and a "
                                    f"test that ends sooner does not. If the step should not start that restart, give "
                                    f"rule {rid} a condition that is false then, such as a state that the end sets after "
                                    f"a wait, or a \"region\" for a tap on the screen that the other tap lies outside. "
                                    f"If the change is meant, end the test after it with a wait, then expects of the "
                                    f"state it leaves")
    return {"sim": sim, "cover": seen_by_steps, "failed": failed, "stable": stable}


def echo_note(design: gm.Design, sim: gm.Sim, step: dict | None, node: gm.Node) -> str:
    """For a failed expect after a tap: the rules the tap ran as a tap on the screen that changed what it reads."""
    if not step:
        return ""
    names = gm.names_in(node)
    hit = [(screen, rid) for screen, rid in sim.echoed
           if any(e[0] == "set" and e[1][0] in names for e in design.by_id[rid].do)
           or any(e[0] == "restart" for e in design.by_id[rid].do)]
    if not hit:
        return ""
    screen, rid = hit[0]
    tap = step["input"]
    return (f" {step['path']} does {tap}, {gm.how_tapped(design.inputs[tap])}. Every tap is also a tap on the "
            f"screen, so Touch On any touch start fires {screen} for it, before On touched object, and rule {rid} ran. "
            f"If {rid} should not run on that tap, give it a condition that is false then: a state that the rule "
            f"that ends the game sets after a wait, or a \"region\" [x0, y0, x1, y1] for {screen} that the tapped "
            f"object lies outside.")


def play(design: gm.Design) -> list[str]:
    """Run every test; return its result lines and add a problem for each failure."""
    lines = []
    ran: dict[str, int] = {}
    done_inputs: set[str] = set()
    won = lost = restarted = False
    launch(design)
    for t in design.tests:
        done_inputs |= {s["input"] for s in t["steps"] if s["kind"] == "do"}
        try:
            result = run_test(design, t)
        except gm.ModelError as e:
            design.bad("rules", f"the start rules fail: {e}")
            return lines
        cover, failed = result["cover"], result["failed"]
        for rid, c in cover["ran"].items():
            ran[rid] = ran.get(rid, 0) + c
        won |= cover["won"]
        lost |= cover["lost"]
        restarted |= cover["restarts"] > 0
        for name, now, first in cover["after_restart"][:3]:
            design.bad(t["path"], f"after the restart {name} is {gm.show(now)}, and a new game starts with "
                                  f"{gm.show(first)}: a restart keeps global variables, so set {name} in a "
                                  f"\"start\" rule, or mark the row \"keep\": true when it is meant to last (a best score)")
        if failed:
            design.bad(*failed)
            lines.append(f"  FAIL  {t['name']}: {failed[0]}")
        else:
            said = [w for w, hit in (("win reached", cover["won"]), ("lose reached", cover["lost"]),
                                     ("restarted", cover["restarts"])) if hit]
            lines.append(f"  ok    {t['name']}: {len(t['steps'])} steps" + (f", {', '.join(said)}" if said else ""))
    if any(p[0].startswith("tests") for p in design.problems):
        return lines        # coverage counts only once the tests run
    for r in design.all_rules():
        if not ran.get(r.id):
            design.bad(r.path, f"rule {r.id} never ran in any test: add steps that make its trigger fire and its "
                               f"conditions hold" + (", then an expect on what it changed" if r.do else ""))
    expected = {n for t in design.tests for st in t["steps"] if st["kind"] == "expect" for n in gm.names_in(st["node"])}
    for n, st in design.state.items():
        if st.stored_in.endswith(".text") and n not in expected and any(
                e[0] == "set" and e[1][0] == n for r in design.all_rules() for e in r.do):
            design.bad(st.path, f"no test expects {n}, the text the player reads: after the step that changes it, add "
                                f"an expect on what it must say, such as {{\"expect\": \"find({n}, \\\"...\\\") >= 0\"}}")
    for name, i in design.inputs.items():
        if name not in done_inputs:
            design.bad(i["path"], f"no test does {name}: add a step {{\"do\": \"{name}\"" +
                                  "".join(f', "{a}": ...' for a in i["args"]) + "}")
    expected_after(design)
    if design.win and not won:
        design.bad("win", "no test reaches the win: add a test that plays to it and expects it")
    if design.lose and not lost:
        design.bad("lose", "no test reaches the lose: add a test that plays to it and expects it")
    if design.ends and not restarted and not any(p[0] == "rules" for p in design.problems):
        design.bad("tests", "no test restarts the game: after the win or lose, do the input that starts a new game, "
                            "wait, and expect the state of a new game")
    return lines


def why_not(design: gm.Design, sim: gm.Sim, node: gm.Node) -> str:
    """For a failed expect: the rules that change what it reads and did not run in the test, each with its
    conditions, and the parents' conditions, as they stand now."""
    names = gm.names_in(node)
    parents: dict[str, gm.Rule] = {}
    for r in design.all_rules():
        for c in r.children:
            parents[c.id] = r
    said = []
    for r in design.all_rules():
        if sim.ran.get(r.id) and any(e[0] == "set" and e[1][0] in names for e in r.do):
            said.append(f"{r.id} ran {sim.ran[r.id]} time(s) and changed it, "
                        + (f"its conditions {', '.join(r.when_text)}" if r.when_text else
                           "with no condition of its own, so it runs every time its trigger or parent does"))
    for r in design.all_rules():
        if sim.ran.get(r.id) or not any(e[0] == "set" and e[1][0] in names for e in r.do):
            continue
        chain, up = [], r
        while up:
            chain.insert(0, up)
            up = parents.get(up.id)
        trigger = chain[0].on
        parts = []
        for rule in chain:
            for text, cond in zip(rule.when_text, rule.when):
                try:
                    held = gm.truth(sim.ev(cond, {"dt": gm.TICK}))
                    seen = ", ".join(f"{n} = {state_text(sim, n)}" for n in sorted(gm.names_in(cond))
                                     if n in sim.values or n in sim.arrays)
                    parts.append(f"{text} is {'true' if held else 'false'}" + (f" ({seen})" if seen else ""))
                except (gm.ModelError, KeyError):
                    parts.append(f"{text} needs the arguments of {trigger}")
        if r.otherwise:
            parts.append("it is an Else, so it runs only when the rule before it did not")
        said.append(f"{r.id} would change it, fired by {trigger}, and did not run: "
                    + ("; ".join(parts) if parts else "no condition holds it back, so its trigger never fired"))
    return (" " + ". ".join(said[:4]) + ".") if said else ""


def state_text(sim: gm.Sim, name: str) -> str:
    if name in sim.arrays:
        grid = sim.arrays[name]
        filled = sum(v != 0 for col in grid for v in col)
        return f"an Array with {filled} cells not 0"
    return gm.show(sim.values.get(name))


def tables(design: gm.Design) -> list[str]:
    written, read = where_read(design)
    lines = ["input -> rule -> feedback:"]
    for r in design.rules:
        if r.on in design.inputs:
            lines.append(f"  {r.on} ({design.inputs[r.on]['player']}): {r.id} -> {r.feedback or '(no feedback)'}")
    lines.append("state, stored in, written by, read by:")
    for n, s in design.state.items():
        lines.append(f"  {n}  {s.stored_in}  {', '.join(written[n]) or '-'}  {', '.join(read[n]) or '-'}")
    return lines


def reference(design: gm.Design, rag: Path | None) -> None:
    ref = design.data.get("reference")
    if not rag or not isinstance(ref, dict) or not isinstance(ref.get("example"), str):
        return
    ids = {k.removesuffix(".json") for k in c3.data_texts(rag, "data/c3-examples/en-US", "*.json")}
    if ids and ref["example"] not in ids:
        design.bad("reference.example", f"{ref['example']!r} is no official example{c3.closest(ref['example'], ids)}; "
                                        f"find one with the same input or genre in data/c3-examples by its tags")


def main() -> int:
    c3.utf8_output()
    ap = c3.argument_parser(__doc__, EPILOG)
    ap.add_argument("design", type=Path, metavar="DESIGN.json")
    args = ap.parse_args()
    try:
        data = json.loads(args.design.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        print(f"{args.design}: {e}. Write the design as JSON, as references/designing-a-game.md shows.", file=sys.stderr)
        return 2
    rag = None
    try:
        rag = c3.find_rag(c3.find_project(args.project), args.rag)
    except SystemExit:
        pass        # without the clone the example's id is not checked
    design = gm.Design(data)
    reference(design, rag)
    out = [f"design {design.data.get('game', '?')!r}: {len(design.inputs)} inputs, {len(design.all_rules())} rules, "
           f"{len(design.state)} state rows, {len(design.tests)} tests"]
    # a gap that leaves the rules runnable (a feedback not written) does not hold the tests back
    readable = not any(p[0].startswith(("rules", "state", "inputs", "tests", "win", "lose")) and not p[0].endswith(".feedback")
                       for p in design.problems)
    if readable:
        coverage(design)
        out += tables(design)
        results = play(design)
        if results:
            out += ["tests:"] + results
    else:
        out.append("the tests did not run: the rules, state, inputs or tests have the problems below")
    out += [f"{path}: {what}" for path, what in design.problems]
    n = len(design.problems)
    if n:
        out.append(f"design: {n} finding{'s' if n != 1 else ''}; fix each at its path and run this again")
    else:
        ends = " and ".join(k for k, node in (("win", design.win), ("lose", design.lose)) if node is not None)
        said = f"{ends} reached, restart checked" if ends else "no win or lose: a demo that never ends"
        if design.win is not None:
            said += (f", won by waiting as the design says: {brief(design.waiting, 80)}" if design.waiting
                     else f", not won in {gm.IDLE:g} s without input")
        whole = [v.lower() for v in design.later] == [gm.NOTHING_LATER]
        later = "nothing is left for later" if whole else "left for later: " + "; ".join(design.later)
        out.append(f"ok: design complete; {len(design.tests)} tests pass in the prototype, {said}. Request: "
                   f"\"{brief(design.request)}\"; {later}."
                   + ("" if whole else " When you report, name what is left for later.")
                   + " Next, build the game, one event per rule with the rule's id in the comment above it, then play "
                   f"the same tests in the editor: python scripts/play_design.py {args.design}")
    shown = c3.fitting(out, args.limit)
    print("\n".join(out[:shown]))
    if shown < len(out):
        print(f"{len(out) - shown} lines not printed; --limit 0 prints everything")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
