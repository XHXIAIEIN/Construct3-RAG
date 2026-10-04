"""Check a game's design before any project file is written, and play its
acceptance tests on the design's own rules, without the editor.

    python scripts/check_design.py DESIGN.json [--rag FOLDER] [--limit CHARS]

The design is JSON, as references/designing-a-game.md describes: the core
loop, the closest official example and what it takes from it, the screen's
regions, the state table, the inputs, the rules as data (trigger, conditions,
effects, sub-rules), win and lose, and the acceptance tests. The script reads
it and refuses a gap by its path: a missing table, a name nothing defines,
a state no rule writes or nothing reads, a fact kept in two places, an input
without feedback, no rule that restarts, an input that changes nothing the
player sees, and a cell of an Array an input writes with no count of the
instances that show it.

Then it runs the rules as a prototype: each test from a first launch, 60
ticks a second, an input followed by 0.15 s of play, as the editor runs the
events. It refuses a failed expect with the values the state held, a rule
no test reaches, a win or a lose no test reaches or that holds at launch, an
input after which no test expects what the player sees, a restart that
leaves a value other than a new game's, and rules that fire each other
without end.
A design that passes holds a game whose rules close the loop; build it, one
rule per event, then play the same tests in the editor with play_design.py.
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
    if not any(e[0] == "restart" for r in design.all_rules() for e in r.do):
        design.bad("rules", "no rule restarts the game: add one, fired by the input that starts a new game, whose "
                            "effects end with \"restart\"")
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


def seen_after(design: gm.Design) -> None:
    """Refuse an input whose rules change only what the player does not see, and a cell of an Array written by an
    input with no instance shown for it."""
    for name, i in design.inputs.items():
        fired = playing(design, name)
        if not fired:
            continue
        for r in fired:
            for x in chain(r):
                arrays = [e[1][0] for e in x.do if e[0] == "set" and e[1][1] is not None]
                if arrays and not any(design.state[n].shown for n in changes(chain(x))):
                    design.bad(x.path, f"rule {x.id} writes a cell of {arrays[0]}, and an Array is not on screen: "
                               f"the player sees the cell as an instance. Add a row that counts the instances shown, "
                               f"such as {{\"name\": \"pieces\", \"start\": 0, \"stored_in\": \"Piece.shown\"}} (or "
                               f"\"Piece.shown(frame=1)\" for the pieces of frame 1), and change it in this rule beside "
                               f"the cell: \"pieces += 1\", or \"pieces = count({arrays[0]}, 1)\"")
        if not shows(design, name):
            rows = changes([x for r in fired for x in chain(r)])
            design.bad(i["path"], f"the input {name} changes only {', '.join(rows) or 'nothing'}, which the player "
                       f"does not see (a global, an Array, an instance variable). Store what shows it where the "
                       f"player sees it, an object's text, x, y, frame or visible, or a count of instances, "
                       f"\"stored_in\": \"Piece.shown\", and change it in the rule {fired[0].id}")


def wanted(design: gm.Design, name: str) -> list[str]:
    """The seen rows a test expects after the input: the counts of instances where its rules write an Array cell,
    since the status line changing says nothing of the piece, else every seen row it changes."""
    rules = [x for r in playing(design, name) for x in chain(r)]
    counts = [n for x in rules if any(e[0] == "set" and e[1][1] is not None for e in x.do)
              for n in changes(chain(x)) if design.state[n].shown]
    return list(dict.fromkeys(counts)) or list(shows(design, name))


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
    """Refuse a win or a lose that holds on the first screen, before the player does anything."""
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
                            f"rule, and play the tests from there rather than from a fixture")


def play(design: gm.Design) -> list[str]:
    """Run every test; return its result lines and add a problem for each failure."""
    lines = []
    ran: dict[str, int] = {}
    done_inputs: set[str] = set()
    won = lost = restarted = False
    launch(design)
    for t in design.tests:
        try:
            sim = gm.Sim(design)
        except gm.ModelError as e:
            design.bad("rules", f"the start rules fail: {e}")
            return lines
        failed = None
        for k, step in enumerate(t["steps"]):
            try:
                if step["kind"] == "do":
                    done_inputs.add(step["input"])
                    sim.fire(step["input"], step["args"])
                elif step["kind"] == "wait":
                    sim.advance(step["seconds"])
                elif step["kind"] == "set":
                    sim.set(step["effect"])
                else:
                    if not gm.truth(sim.ev(step["node"], {})):
                        seen = ", ".join(f"{n} = {state_text(sim, n)}" for n in sorted(gm.names_in(step["node"])))
                        rules = ", ".join(f"{rid} x{c}" for rid, c in sim.ran.items()) or "none"
                        failed = (step["path"], f"expect {step['text']}: false in the prototype; {seen}. Rules that "
                                                f"ran in this test so far: {rules}." + why_not(design, sim, step["node"])
                                                + " Change the rules, or the test when it expects the wrong thing")
                        break
            except gm.ModelError as e:
                failed = (step["path"], f"the prototype stopped here: {e}")
                break
        for rid, c in sim.ran.items():
            ran[rid] = ran.get(rid, 0) + c
        won |= sim.won
        lost |= sim.lost
        restarted |= sim.restarts > 0
        for name, now, first in sim.after_restart[:3]:
            design.bad(t["path"], f"after the restart {name} is {gm.show(now)}, and a new game starts with "
                                  f"{gm.show(first)}: a restart keeps global variables, so set {name} in a "
                                  f"\"start\" rule, or mark the row \"keep\": true when it is meant to last (a best score)")
        if failed:
            design.bad(*failed)
            lines.append(f"  FAIL  {t['name']}: {failed[0]}")
        else:
            said = [w for w, hit in (("win reached", sim.won), ("lose reached", sim.lost),
                                     ("restarted", sim.restarts)) if hit]
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
    if not restarted and not any(p[0] == "rules" for p in design.problems):
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
    ids = {p.stem for p in (rag / "data" / "c3-examples" / "en-US").glob("*.json")}
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
        out.append(f"ok: design complete; {len(design.tests)} tests pass in the prototype, win"
                   + (" and lose" if design.lose else "") + " reached, restart checked. Next, build the game, one "
                   "event per rule with the rule's id in the comment above it, then play the same tests in the "
                   "editor: python scripts/play_design.py " + str(args.design))
    shown = c3.fitting(out, args.limit)
    print("\n".join(out[:shown]))
    if shown < len(out):
        print(f"{len(out) - shown} lines not printed; --limit 0 prints everything")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
