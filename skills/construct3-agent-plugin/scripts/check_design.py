"""Check a game's design before any project file is written, and play its
acceptance tests on the design's own rules, without the editor.

    python scripts/check_design.py DESIGN.json [--rag FOLDER] [--limit CHARS]

The design is JSON, as references/designing-a-game.md describes: the core
loop, the closest official example and what it takes from it, the screen's
regions, the state table, the inputs, the rules as data (trigger, conditions,
effects, sub-rules), win and lose, and the acceptance tests. The script reads
it and refuses a gap by its path: a missing table, a name nothing defines,
a state no rule writes or nothing reads, a fact kept in two places, an input
without feedback, no rule that restarts.

Then it runs the rules as a prototype: each test from a first launch, 60
ticks a second, an input followed by 0.15 s of play, as the editor runs the
events. It refuses a failed expect with the values the state held, a rule
no test reaches, a win or a lose no test reaches, a restart that leaves a
value other than a new game's, and rules that fire each other without end.
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


SHOWN = (".text", ".x", ".y", ".frame", ".visible", ".angle", ".width", ".height", ".opacity")


def coverage(design: gm.Design) -> None:
    """Static gaps of the tables: state nobody writes or reads, no restart."""
    written, read = where_read(design)
    for n, s in design.state.items():
        if not written[n] and not s.const:
            design.bad(f"{s.path}", f"no rule changes {n}: write the rule that does, or mark the row \"const\": true "
                                    f"when it is a tuning value the game never changes")
        if not read[n] and not s.stored_in.endswith(SHOWN) and not s.keep:
            design.bad(f"{s.path}", f"nothing reads {n}: no condition, effect, win or lose uses it and the player "
                                    f"does not see it; drop the row, or use it where the game decides something")
    if not any(e[0] == "restart" for r in design.all_rules() for e in r.do):
        design.bad("rules", "no rule restarts the game: add one, fired by the input that starts a new game, whose "
                            "effects end with \"restart\"")


def play(design: gm.Design) -> list[str]:
    """Run every test; return its result lines and add a problem for each failure."""
    lines = []
    ran: dict[str, int] = {}
    done_inputs: set[str] = set()
    won = lost = restarted = False
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
    return (" " + ". ".join(said[:3]) + ".") if said else ""


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
