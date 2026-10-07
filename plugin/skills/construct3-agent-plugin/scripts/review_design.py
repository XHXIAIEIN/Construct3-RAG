"""Read a project's event sheets and print where their design is hard to read or
fragile, with the form to write instead, then fixed questions to answer.

    python scripts/review_design.py [--project FOLDER] [--sheets NAME ...] [--limit CHARS]
                                    [--rag FOLDER] [--locale en-US]

Run it after check_project.py passes and before the editor. It reads the files,
starts no browser and changes nothing. A finding names its place as
print_sheet.py numbers it, `sheet Game event 15`, says what to change and
names the form to write instead. Each rule below finds nothing, or next to
nothing, in the 524 official examples:

  conditions  an event with 12 or more conditions besides its trigger, more than any
              event of the examples holds
  guard       the same 3 or more conditions of objects repeated in 3 or more events
  trigger     two or more sibling events that start with one trigger and test globals
              to tell the cases apart
  twice       one action list writing a value into an Array cell indexed by an
              object's expressions and into that object's instance variable
  global      a scratch global (TMP, TMP2, TMPN); a layout's sheet declaring 10 or
              more globals that only other sheets use
  uid         an instance variable set to the UID of an instance created in the
              same actions, and picked back by it
  data        20 or more actions of one kind with literal parameters: a table
  restart     On start of layout setting instances after Pick all, on a layout that
              Restart layout or Go to layout enters again
  expression  an expression 5 or more parentheses deep that writes a call of 30 or
              more characters twice
  follow      a part made with an object (one container, or one action list) and set
              from its position once, while another event moves the object alone

What the examples also write, and a reader judges, becomes a question: an event
with 4 to 11 conditions, sibling events of one trigger, sibling events that
differ only in their numbers and texts, 3 or more inverted conditions, a
global one function or one group uses, a UID kept in an instance variable.
The questions name those events; answer each one from print_sheet.py.
The measurement behind each threshold: references/verifying-a-change.md,
"The design of the sheets".
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterator

import c3project as c3
import print_sheet
from c3project import NUMBERED, STRING_LITERAL

EPILOG = """examples:
  python scripts/review_design.py
  python scripts/review_design.py --sheets Combat Map
  python scripts/review_design.py --project ../OtherGame --limit 0

output:
  == Combat
    uid: sheet Combat event 18: sets Card.TAGNAME to CardName.UID, and ...
    expression: sheet Combat event 30 action 2 (value): computes ...
  == Menu
    global: sheet Menu, global TMP: a scratch global ...
  questions: answer each one yes or no, reading the events it names with print_sheet.py ...
    1. Could each of these events be split ...? Weapons 107 (11 conditions), ...
    ...
  design: 3 findings on 2 sheets; the questions name 9 events
  next: <what to do>

exit codes: 0 the review printed, with findings or without; 1 the project or the clone was not found;
2 a sheet named with --sheets is not in the project"""

# Thresholds, from the measurement over the 524 official examples (verifying-a-change.md).
CONDITIONS_FINDING = 12     # the examples' most is 11, besides the trigger
CONDITIONS_QUESTION = 4     # 1.7% of the examples' events have 4 or more
GUARD_SIZE = 3              # conditions shared
GUARD_EVENTS = 3            # events sharing them
IDLE_INVERTED = 3           # inverted conditions in one event
PAIR_MAX = 4                # siblings of one shape; 5 or more is check_project --style's ladder
TRIGGER_SIBLINGS = 3
GLOBALS_ELSEWHERE = 10      # globals a layout's sheet declares and only other sheets use
DATA_ACTIONS = 20
REPEATED_CALL = 30          # characters of a call written twice in one expression
DEEP = 5                    # parentheses deep, together with a repeated call
SHOWN = 8                   # events a question names before "and N more"

EXPRESSION_TYPES = {"any", "number", "string", "layer", "animation", "animationframe", "groupname", "objecteffect",
                    "layereffect", "layouteffect"}
NAME_KEYS = {"variable", "instance-variable", "object", "layout", "comparison", "key"}
NUMBER_LITERAL = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:e[+-]?\d+)?(?![\w.])", re.I)
IDENT = re.compile(r"(?<![\w.])([A-Za-z_]\w*)(?!\s*\()")
CALL = re.compile(r"(?<![\w.])([A-Za-z_][\w.]*)\s*\(")
SPACES = re.compile(r"\s+")
MEMBER = re.compile(r"\s*(\w+)\s*\.\s*\w+\s*")          # Object.Field: the object that owns a value
PAREN = {"(": 1, ")": -1}                               # what a character adds to the parentheses depth
SCRATCH = re.compile(r"(?i)^(tmp|temp|scratch)[a-z]?\d*$")
UID_OF = re.compile(r"(?i)^\s*(\w+)\s*\.\s*uid\s*$")
WRITES = {"set-eventvar-value", "add-to-eventvar", "subtract-from-eventvar", "set-boolean-eventvar",
          "toggle-boolean-eventvar"}
READS = {"compare-eventvar", "compare-boolean-eventvar"}
ARRAY_SETS = {"set-at-x": ("x",), "set-at-xy": ("x", "y"), "set-at-xyz": ("x", "y", "z")}
SETS_ON_INSTANCES = re.compile(r"^(set-|add-to-|subtract-from-|toggle-)")

# The questions, in the order they print. A rule whose measurement found it in sound
# example code names its events under one of them instead of printing a finding.
QUESTIONS = {
    "split": "Could each of these events be split into a parent event with the conditions that say when, and "
             "sub-events that each add one or two, so that each event reads as one sentence?",
    "trigger": "Do these sibling events that start with one trigger make one decision, which one event with that "
               "trigger and a sub-event per case, the last one Else, would hold?",
    "value": "Do these events do the same thing for different values, where one event could read the value from "
             "an instance variable, a global or a function parameter?",
    "state": "Do these events test whether an instance is free through several conditions (dragging, a tween, a "
             "timer, an animation, a boolean), where one instance variable named for the state would answer it?",
    "owner": "Does each global have one owner? A global that one function or one group alone reads and writes "
             "is a local there, static when it keeps its value.",
    "link": "Does an instance keep the UID of another instance where a container or a hierarchy would link them?",
    "twice": "Is any fact stored in two places, such as an Array cell and an instance variable, or a variable "
             "beside a condition the engine answers (Is overlapping, Is dragging, Is playing)?",
}

# (rule, variant) -> None for a finding, the key of the question that names it, or DROPPED.
DROPPED = "dropped"
CLASSES = {
    ("conditions", "many"): None, ("conditions", "some"): "split",
    ("guard", ""): None,
    ("idle", "mechanisms"): "state", ("idle", "object"): "state", ("idle", "mechanisms+object"): "state",
    ("pair", ""): "value", ("pair", "global"): "value",
    ("trigger", "global"): None, ("trigger", "cases"): "trigger",
    ("twice", ""): None,
    ("global", "scratch"): None, ("global", "sheet"): None, ("global", "function"): "owner",
    ("global", "group"): "owner", ("global", "handoff"): DROPPED,
    ("uid", "created"): None, ("uid", "kept"): "link",
    ("data", ""): None, ("restart", ""): None, ("expression", ""): None, ("follow", ""): None,
}


# --- the sheets as events ---------------------------------------------------------------
@dataclass(eq=False)
class Ev:
    """One row of a sheet, with the editor's number and what it sits in."""
    sheet: str
    n: int
    ev: dict
    depth: int
    parent: "Ev | None"
    group: str | None           # the title of the innermost group
    function: str | None        # the function or custom action it is part of
    siblings: list
    scope: frozenset            # lower-case names of the locals and parameters visible here
    children: list = field(default_factory=list)

    @property
    def kind(self) -> str:
        return self.ev.get("eventType", "")

    @property
    def conditions(self) -> list[dict]:
        return [c for c in self.ev.get("conditions", []) if isinstance(c, dict) and not c.get("disabled")]

    @property
    def actions(self) -> list[dict]:
        return [a for a in self.ev.get("actions", []) if isinstance(a, dict) and not a.get("disabled")]

    @property
    def place(self) -> str:
        return f"sheet {self.sheet} event {self.n}"

    def ancestors(self) -> Iterator["Ev"]:
        e = self.parent
        while e:
            yield e
            e = e.parent

    def subtree(self) -> Iterator["Ev"]:
        """This row, then every row below it in document order."""
        yield self
        for k in self.children:
            yield from k.subtree()


def walk(sheet: str, events: list, counter: list[int] | None = None, parent: Ev | None = None,
         group: str | None = None, function: str | None = None, scope: frozenset = frozenset(),
         depth: int = 0) -> Iterator[Ev]:
    """Every row of a sheet in document order, numbered as print_sheet.py numbers it."""
    counter = counter if counter is not None else [0]
    if depth:       # the variables of a list below the sheet's own are locals
        scope = scope | {str(v.get("name", "")).lower() for v in events
                         if isinstance(v, dict) and v.get("eventType") == "variable"}
    for raw in events:
        if not isinstance(raw, dict):
            continue
        et = raw.get("eventType")
        if et in NUMBERED:
            counter[0] += 1
        n = counter[0] if et in NUMBERED else counter[0] + 1
        inner_group = raw.get("title") if et == "group" else group
        inner_function, inner_scope = function, scope
        if et == "function-block":
            inner_function = raw.get("functionName")
        elif et == "custom-ace-block":
            inner_function = f"{raw.get('objectClass')}.{raw.get('aceName')}"
        if et in ("function-block", "custom-ace-block"):
            inner_scope = scope | {str(fp.get("name", "")).lower() for fp in raw.get("functionParameters", [])}
        e = Ev(sheet, n, raw, depth, parent, group, function, events, scope)
        if parent:
            parent.children.append(e)
        yield e
        yield from walk(sheet, raw.get("children") or [], counter, e, inner_group, inner_function, inner_scope,
                        depth + 1)


def blank(expr: str) -> str:
    """An expression with the inside of its text literals blanked, at the same length, so
    a name or a parenthesis inside a text is not read and a place in it is a place in expr."""
    return STRING_LITERAL.sub(lambda m: '"' + " " * (len(m.group()) - 2) + '"', expr)


def normal(expr: str) -> str:
    """An expression with its texts and numbers replaced, and no spaces: two expressions
    equal here differ only by their constants."""
    return unspaced(NUMBER_LITERAL.sub("#", STRING_LITERAL.sub("$", expr)))


def unspaced(expr: str) -> str:
    return SPACES.sub("", expr)


def is_literal(expr: object) -> bool:
    if not isinstance(expr, str):
        return True
    s = expr.strip()
    return bool(STRING_LITERAL.fullmatch(s) or re.fullmatch(r"-?\d+(\.\d+)?", s))


def params_of(ace: dict) -> dict:
    """The parameters of a condition or action by name; {} when it has none, or a list,
    as a function call's are."""
    params = ace.get("parameters")
    return params if isinstance(params, dict) else {}


def key(ace: dict) -> tuple:
    """A condition or action with everything that makes it what it is."""
    return (ace.get("objectClass"), ace.get("behaviorType"), ace.get("id") or ace.get("callFunction"),
            bool(ace.get("isInverted")), json.dumps(ace.get("parameters"), sort_keys=True, ensure_ascii=False))


@dataclass
class Design:
    """The sheets of a project, what the rules read of the schemas, and the layouts.
    is_trigger and expressions come from the schemas; tests may pass their own."""
    sheets: dict[str, dict]
    is_trigger: Callable[[dict], bool]
    expressions: Callable[[str, dict], dict[str, str]]     # kind, ace -> {parameter: expression}
    layouts: dict[str, dict] = field(default_factory=dict)
    types: dict[str, dict] = field(default_factory=dict)
    words: Callable[[str, dict], str] | None = None         # kind, ace -> the editor's wording
    containers: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rows = {name: list(walk(name, sheet.get("events", []))) for name, sheet in self.sheets.items()}
        self._globals: dict[str, tuple[str, dict]] = {}
        for e in self.all_rows():
            if e.depth == 0 and e.kind == "variable" and not e.ev.get("isConstant"):
                self._globals.setdefault(str(e.ev.get("name", "")).lower(), (e.sheet, e.ev))

    @classmethod
    def of(cls, p: c3.Project, sheets: dict[str, dict] | None = None) -> "Design":
        def is_trigger(c: dict) -> bool:
            return bool(c.get("objectClass") in p.plugin_of and (p.ace_entry("conditions", c) or {}).get("isTrigger"))

        def expressions(kind: str, ace: dict) -> dict[str, str]:
            params = ace.get("parameters")
            if isinstance(params, list):
                return {str(i): v for i, v in enumerate(params) if isinstance(v, str)}
            if not isinstance(params, dict):
                return {}
            entry = p.ace_entry(kind, ace) if ace.get("objectClass") in p.plugin_of else None
            if entry is None:
                return {k: v for k, v in params.items() if isinstance(v, str) and k not in NAME_KEYS}
            types = {k: s.get("type") for k, s in (entry.get("params") or {}).items()}
            return {k: v for k, v in params.items() if isinstance(v, str) and types.get(k) in EXPRESSION_TYPES}

        def words(kind: str, ace: dict) -> str:
            return print_sheet.wording(p, kind, ace)
        return cls(sheets if sheets is not None else p.load_listed("eventSheets"), is_trigger, expressions,
                   p.load_listed("layouts"), p.types, words, p.data.get("containers") or [])

    # --- shared reads ---------------------------------------------------------------------
    def all_rows(self) -> Iterator[Ev]:
        """Every row of every sheet, the sheets in the project's order."""
        for rows in self.rows.values():
            yield from rows

    def blocks(self, sheet: str) -> list[Ev]:
        return [e for e in self.rows[sheet] if e.kind == "block"]

    def say(self, kind: str, ace: dict) -> str:
        if self.words:
            try:
                return self.words(kind, ace)
            except (KeyError, TypeError, IndexError, ValueError):
                pass
        return f"{ace.get('objectClass')}: {'NOT ' if ace.get('isInverted') else ''}{ace.get('id')}"

    def filters(self, e: Ev) -> list[dict]:
        """The conditions of an event besides its trigger."""
        return [c for c in e.conditions if not self.is_trigger(c)]

    def trigger(self, e: Ev) -> dict | None:
        return next((c for c in e.conditions if self.is_trigger(c)), None)

    def all_expressions(self, e: Ev) -> Iterator[tuple[str, str, int, str]]:
        """(kind, parameter, index, expression) of every condition and action of a row."""
        for kind, aces in (("conditions", e.conditions), ("actions", e.actions)):
            for i, ace in enumerate(aces, 1):
                for k, v in self.expressions(kind, ace).items():
                    yield kind, k, i, v

    def globals(self) -> dict[str, tuple[str, dict]]:
        """lower-case name -> (sheet, variable event) of every global that is not a constant."""
        return self._globals


def finding(rule: str, e: Ev | None, line: str, sheet: str | None = None, events: list[int] | None = None,
            variant: str = "", short: str = "") -> dict:
    """A candidate of a rule: where, what to change, and the few words a question names it by."""
    return {"rule": rule, "variant": variant, "sheet": e.sheet if e else sheet, "event": e.n if e else None,
            "events": events or ([e.n] if e else []), "line": line, "short": short}


# --- a: conditions per event -------------------------------------------------------------
def conditions_rule(d: Design) -> list[dict]:
    """An event with many conditions besides its trigger reads as several sentences in
    one; an OR block lists alternatives and is left out."""
    out = []
    for sheet in d.rows:
        for e in d.blocks(sheet):
            if e.ev.get("isOrBlock"):
                continue
            n = len(d.filters(e))
            if n >= CONDITIONS_QUESTION:
                out.append(finding("conditions", e, f"{e.place}: {n} conditions besides its trigger, more than "
                           f"any event of the official examples; split it: a parent event with the conditions that "
                           f"say when (the trigger and the guard), sub-events that each add one or two, and a "
                           f"function that returns the value when the conditions compute one",
                           variant="many" if n >= CONDITIONS_FINDING else "some", short=f"{n} conditions"))
    return out


# --- b: a guard repeated across events ---------------------------------------------------
def guard_rule(d: Design) -> list[dict]:
    """The same conditions of objects, three or more, in three or more events of a sheet:
    a guard written again in each event instead of once above them."""
    out: list[dict] = []
    for sheet in d.rows:
        sets: dict[Ev, set] = {}
        for e in d.blocks(sheet):
            if e.ev.get("isOrBlock"):
                continue
            own = {key(c) for c in d.filters(e) if c.get("objectClass") != "System"}
            if len(own) >= GUARD_SIZE:
                sets[e] = own
        by_combo: dict[frozenset, list[Ev]] = {}
        for e, own in sets.items():
            for combo in itertools.combinations(sorted(own, key=str)[:12], GUARD_SIZE):
                by_combo.setdefault(frozenset(combo), []).append(e)
        seen: set[tuple[frozenset, frozenset]] = set()
        for evs in by_combo.values():
            if len(evs) < GUARD_EVENTS:
                continue
            shared = frozenset.intersection(*(frozenset(sets[e]) for e in evs))
            group = frozenset(evs)
            if (shared, group) in seen or any(s >= shared and g == group for s, g in seen):
                continue
            seen.add((shared, group))
            evs = sorted(evs, key=lambda x: x.n)
            guard = [c for c in d.filters(evs[0]) if key(c) in shared]
            names = "; ".join(d.say("conditions", c) for c in guard)
            out.append(finding(
                "guard", evs[0], f"{evs[0].place}: with events {', '.join(str(x.n) for x in evs[1:])}, "
                f"the same {len(shared)} conditions ({names}) in {len(evs)} events; test them once: a parent "
                f"event or a group with these conditions and the events as its sub-events, or one condition "
                f"that says the same, such as a state instance variable on {guard[0].get('objectClass')}",
                events=[x.n for x in evs]))
    # one finding per guard: the largest set first, its smaller copies on the same events dropped
    out.sort(key=lambda f: -f["line"].count(";"))
    kept: list[dict] = []
    for f in out:
        if not any(set(f["events"]) <= set(k["events"]) and f["sheet"] == k["sheet"] for k in kept):
            kept.append(f)
    return kept


# --- c: an "is it free" test spread over inverted conditions -----------------------------
def idle_rule(d: Design) -> list[dict]:
    out = []
    for sheet in d.rows:
        for e in d.blocks(sheet):
            if e.ev.get("isOrBlock"):
                continue
            inverted = [c for c in d.filters(e) if c.get("isInverted") and c.get("objectClass") != "System"]
            mechanisms = {(c.get("behaviorType"), c.get("id")) for c in inverted}
            by_object: dict[str, list[dict]] = {}
            for c in inverted:
                by_object.setdefault(c["objectClass"], []).append(c)
            on_one_object = max(map(len, by_object.values()), default=0)
            variant = "+".join(v for v, hit in (("mechanisms", len(mechanisms) >= IDLE_INVERTED),
                                                ("object", on_one_object >= IDLE_INVERTED)) if hit)
            if variant:
                out.append(finding("idle", e, f"{e.place}: {len(inverted)} inverted conditions "
                           f"({'; '.join(d.say('conditions', c) for c in inverted)}), a test that the instance is "
                           f"free spread over {len(mechanisms)} mechanisms; keep one state instance variable on the "
                           f"object that owns it (state = \"idle\", \"moving\", \"attacking\"), set where each "
                           f"mechanism starts and ends, and test state = \"idle\"", variant=variant,
                           short=f"{len(inverted)} inverted conditions"))
    return out


# --- d: two to four siblings that differ only by constants ------------------------------
def shape_of(d: Design, ev: dict, exact: bool) -> tuple:
    def ace(kind: str, a: dict) -> tuple:
        values = d.expressions(kind, a)
        params = a.get("parameters")
        rest = {k: v for k, v in params.items() if k not in values} if isinstance(params, dict) else None
        return (a.get("objectClass"), a.get("behaviorType"), a.get("id") or a.get("callFunction"),
                a.get("isInverted", False), json.dumps(rest, sort_keys=True),
                tuple(sorted((k, v if exact else normal(v)) for k, v in values.items())))
    return (ev.get("isOrBlock", False),
            tuple(ace("conditions", c) for c in ev.get("conditions", []) if isinstance(c, dict)),
            tuple(ace("actions", a) for a in ev.get("actions", []) if isinstance(a, dict)),
            tuple(shape_of(d, k, exact) for k in ev.get("children", []) if k.get("eventType") == "block"))


def pair_variant(d: Design, same: list[Ev]) -> str:
    """"global" when the siblings differ in the value a global is compared with:
    CurrentPlayer = 1 and CurrentPlayer = 2."""
    globals_ = d.globals()
    tests = [[(str(c["parameters"].get("variable", "")).lower(), str(c["parameters"].get("value", "")))
              for c in e.conditions if c.get("id") == "compare-eventvar" and isinstance(c.get("parameters"), dict)]
             for e in same]
    for i, (name, _) in enumerate(tests[0]):
        if name in globals_ and len({t[i][1] for t in tests if i < len(t)}) > 1:
            return "global"
    return ""


def pair_rule(d: Design) -> list[dict]:
    """Sibling events whose conditions, actions and sub-events are the same but for the
    numbers and texts in their expressions, two to PAIR_MAX of them."""
    out = []
    for sheet in d.rows:
        lists: dict[int, list[Ev]] = {}
        for e in d.blocks(sheet):
            if e.actions or e.ev.get("children"):
                lists.setdefault(id(e.siblings), []).append(e)
        for evs in lists.values():
            by_shape: dict[tuple, list[Ev]] = {}
            for e in evs:
                by_shape.setdefault(shape_of(d, e.ev, False), []).append(e)
            for shape, same in by_shape.items():
                if not 2 <= len(same) <= PAIR_MAX or not shape[1] or len(shape[1]) + len(shape[2]) < 3:
                    continue
                if len({shape_of(d, e.ev, True) for e in same}) < len(same):
                    continue    # two copies of one event are another problem
                out.append(finding("pair", same[0], f"{same[0].place}: with event"
                           f"{'s' if len(same) > 2 else ''} {', '.join(str(e.n) for e in same[1:])}, the same "
                           f"conditions and actions, only the numbers or texts in them differ; write the event once "
                           f"over the value: read it from an instance variable or a global (CurrentPlayer, the "
                           f"symbol as an Array or a ?: expression), or call one function with the value as a "
                           f"parameter", events=[e.n for e in same], variant=pair_variant(d, same),
                           short="with " + ", ".join(str(e.n) for e in same[1:])))
    return out


# --- e: one trigger heading several sibling events ---------------------------------------
def trigger_rule(d: Design) -> list[dict]:
    out = []
    globals_ = d.globals()

    def global_test(e: Ev) -> bool:
        return any(c.get("id") in READS and str(params_of(c).get("variable", "")).lower() in globals_
                   for c in d.filters(e))
    for sheet in d.rows:
        lists: dict[int, list[Ev]] = {}
        for e in d.blocks(sheet):
            if e.parent is None or e.parent.kind == "group":
                lists.setdefault(id(e.siblings), []).append(e)
        for evs in lists.values():
            by_trigger: dict[tuple, list[Ev]] = {}
            for e in evs:
                t = d.trigger(e)
                if t is not None and not e.ev.get("isOrBlock"):
                    by_trigger.setdefault(key(t), []).append(e)
            for t_key, same in by_trigger.items():
                # Events that only run actions on one trigger are each a step with a comment, as the
                # examples write On start of layout; the ones that test more are cases of one decision.
                cases = [e for e in same if d.filters(e)]
                split = len(cases) >= 2 and sum(global_test(e) for e in cases) >= 2
                if (len(same) < TRIGGER_SIBLINGS or len(cases) < 2) and not split:
                    continue
                t = d.trigger(same[0])
                out.append(finding("trigger", same[0], f"{same[0].place}: with events "
                           f"{', '.join(str(e.n) for e in same[1:])}, {len(same)} sibling events start with "
                           f"{d.say('conditions', t)}"
                           + (", told apart by a global" if split else "") +
                           "; write the trigger once, its shared conditions beside it, and each case as a sub-event "
                           "with a comment, the last one Else", events=[e.n for e in same],
                           variant="global" if split else "cases",
                           short="with " + ", ".join(str(e.n) for e in same[1:])))
    return out


# --- f: one fact written into an Array and an instance variable --------------------------
def twice_rule(d: Design) -> list[dict]:
    out = []
    for e in d.all_rows():
        acts = e.actions
        for a in acts:
            axes = ARRAY_SETS.get(a.get("id"))
            params = params_of(a)
            if not axes or not all(isinstance(params.get(x), str) for x in axes):
                continue
            owners = {m.group(1) for m in map(MEMBER.fullmatch, (params[x] for x in axes)) if m}
            value = unspaced(str(params.get("value", "")))
            for b in acts:
                bp = params_of(b)
                if b.get("id") == "set-instvar-value" and b.get("objectClass") in owners and \
                        unspaced(str(bp.get("value", ""))) == value:
                    obj, var = b["objectClass"], bp.get("instance-variable")
                    out.append(finding("twice", e, f"{e.place}: writes {params['value']} into "
                               f"{a.get('objectClass')} at ({', '.join(params[x] for x in axes)}) and into "
                               f"{obj}.{var}, two copies of one fact that the events must keep equal; keep it in "
                               f"one place: {obj}.{var} when each {obj} stands for its cell (read and test it "
                               f"there), or the Array alone with {obj} drawing from it"))
    return out


# --- g: globals --------------------------------------------------------------------------
@dataclass
class Use:
    e: Ev
    write: bool


def global_uses(d: Design) -> dict[str, list[Use]]:
    """Where each global is read and written, a local or parameter of the same name
    in scope taking the name over."""
    globals_ = d.globals()
    uses: dict[str, list[Use]] = {g: [] for g in globals_}
    for e in d.all_rows():
        if e.kind == "variable":
            continue
        for kind, aces in (("conditions", e.conditions), ("actions", e.actions)):
            for ace in aces:
                ace_id = ace.get("id")
                named = str(params_of(ace).get("variable", "")).lower()
                if named in uses and named not in e.scope and (ace_id in WRITES or ace_id in READS):
                    uses[named].append(Use(e, ace_id in WRITES))
                for v in d.expressions(kind, ace).values():
                    for m in IDENT.finditer(blank(v)):
                        name = m.group(1).lower()
                        if name in uses and name not in e.scope:
                            uses[name].append(Use(e, False))
    return uses


def global_rule(d: Design) -> list[dict]:
    out = []
    globals_ = d.globals()
    uses = global_uses(d)
    for g, us in uses.items():
        sheet, var = globals_[g]
        name = var.get("name")
        place = f"sheet {sheet}, global {name}"
        written = [u for u in us if u.write]
        if not us or not written:
            continue
        functions = {u.e.function for u in us}
        groups = {u.e.group for u in us}
        writers = {u.e.function for u in written}
        if SCRATCH.match(str(name)):
            out.append(finding("global", None, f"{place}: a scratch global, written in "
                       f"{describe_owners(written)} and read in {describe_owners([u for u in us if not u.write])}; "
                       f"a value one event computes is a local of that event, and one handed to a function is its "
                       f"parameter or its return value", sheet=sheet, variant="scratch"))
        elif len(functions) == 1 and None not in functions:
            (owner,) = functions
            out.append(finding("global", None, f"{place}: read and written only in function "
                       f"{owner}; declare it there as a local variable, static when it keeps its value "
                       f"between calls", sheet=sheet, variant="function",
                       short=f"global {name} in function {owner}"))
        elif len(groups) == 1 and None not in groups and functions == {None}:
            (owner,) = groups
            out.append(finding("global", None, f"{place}: read and written only in group {owner}; declare it "
                       f"as the group's first child, a static local when it keeps its value from tick to tick",
                       sheet=sheet, variant="group", short=f"global {name} in group {owner}"))
        elif len(writers - {None}) >= 2 and any(u.e.function not in writers for u in us if not u.write):
            out.append(finding("global", None, f"{place}: written in functions "
                       f"{', '.join(sorted(f for f in writers if f))} and read elsewhere, a value handed "
                       f"between functions through a global; return it from the function that computes it, or "
                       f"pass it as a parameter", sheet=sheet, variant="handoff"))
    laid = {lay.get("eventSheet") for lay in d.layouts.values()}
    elsewhere: dict[str, list[str]] = {}
    for g, us in uses.items():
        sheet = globals_[g][0]
        if us and sheet in laid and sheet not in {u.e.sheet for u in us}:
            elsewhere.setdefault(sheet, []).append(str(globals_[g][1].get("name")))
    for sheet, names in elsewhere.items():
        if len(names) >= GLOBALS_ELSEWHERE:
            out.append(finding("global", None, f"sheet {sheet}: declares {len(names)} globals that only other sheets "
                       f"use ({', '.join(names[:6])}{' ...' if len(names) > 6 else ''}); the official examples keep "
                       f"shared globals on a sheet of their own, with no events and no layout (samuroof Globals, "
                       f"overloaded-underqualified GlobalsEvents): move them there, and move a value that describes "
                       f"one instance, such as the player's, to an instance variable of that object",
                       sheet=sheet, variant="sheet"))
    return out


def describe_owners(us: list[Use]) -> str:
    owners = sorted({u.e.function or f"sheet {u.e.sheet} event {u.e.n}" for u in us})
    return ", ".join(owners[:4]) + (" ..." if len(owners) > 4 else "") if owners else "nowhere"


def globals_count(d: Design) -> dict[str, int]:
    return {sheet: sum(1 for e in rows if e.depth == 0 and e.kind == "variable") for sheet, rows in d.rows.items()}


# --- h: a link kept as a UID -------------------------------------------------------------
def uid_rule(d: Design) -> list[dict]:
    out = []
    picks: dict[str, list[Ev]] = {}
    for e in d.all_rows():
        for c in e.conditions:
            if c.get("id") == "pick-by-unique-id":
                v = str(params_of(c).get("unique-id", ""))
                for m in re.finditer(r"(\w+)\s*\.\s*(\w+)", blank(v)):
                    picks.setdefault(m.group(2).lower(), []).append(e)
    seen: set[tuple[str | None, str]] = set()
    for e in d.all_rows():
        for a in e.actions:
            params = params_of(a)
            m = UID_OF.match(str(params.get("value", "")))
            var = str(params.get("instance-variable", ""))
            if a.get("id") != "set-instvar-value" or not m or var.lower() not in picks:
                continue
            if (a.get("objectClass"), var) in seen:
                continue
            seen.add((a.get("objectClass"), var))
            where = picks[var.lower()][0]
            made = any(b.get("id") in ("create-object", "spawn-another-object") and m.group(1).lower() in
                       {str(v).lower() for v in params_of(b).values()} for b in e.actions)
            out.append(finding("uid", e, f"{e.place}: sets {a.get('objectClass')}.{var} to {m.group(1)}.UID, "
                       f"and {where.place} picks {m.group(1)} back by it; link the two as the engine does: a "
                       f"container when they are created and destroyed together (picking one picks the other), "
                       f"or {m.group(1)} as a child of {a.get('objectClass')} in a hierarchy (Pick children)",
                       variant="created" if made else "kept", short=f"{a.get('objectClass')}.{var}"))
    return out


# --- i: a table written as actions -------------------------------------------------------
def data_rule(d: Design) -> list[dict]:
    out = []
    for e in d.all_rows():
        counts = Counter((a.get("objectClass"), a.get("id")) for a in e.actions
                         if (values := d.expressions("actions", a)) and all(is_literal(v) for v in values.values()))
        for (obj, ace_id), n in counts.items():
            if n >= DATA_ACTIONS:
                out.append(finding("data", e, f"{e.place}: {n} {obj} {ace_id} actions with literal values, a "
                           f"table written as events; keep it in a project file, an Array with one record per row "
                           f"and one field per column under Files, load it at start with AJAX Request project "
                           f"file and Load from AJAX.LastData, and copy it into {obj} with a For loop over its "
                           f"rows and fields. A generator writes the file with record_table() and the events "
                           f"with load_data_file() and table_to_dictionary(), in assets/build_project.py"))
    return out


# --- j: resets a restart already makes ---------------------------------------------------
def restart_rule(d: Design) -> list[dict]:
    """On start of layout picks all of a type and sets it, on a layout the events enter
    again by Restart layout or Go to layout: the layout's own instances come back as the
    layout holds them, so the resets repeat what the editor saved."""
    out = []
    sheet_of = {name: lay.get("eventSheet") for name, lay in d.layouts.items() if lay.get("eventSheet")}

    def reached(sheet: str, seen: set) -> set:
        seen.add(sheet)
        for e in d.rows.get(sheet, []):
            if e.kind == "include" and e.ev.get("includeSheet") not in seen:
                reached(e.ev["includeSheet"], seen)
        return seen
    for layout, sheet in sheet_of.items():
        if sheet not in d.rows:
            continue
        sheets = reached(sheet, set())
        again = any(a.get("id") == "restart-layout"
                    or (a.get("id") == "go-to-layout" and str(params_of(a).get("layout", "")) == layout)
                    for s in sheets for e in d.rows.get(s, []) for a in e.actions)
        if not again:
            continue
        for s in sheets:
            for e in d.blocks(s):
                if e.parent is not None and e.parent.kind != "group":
                    continue
                t = d.trigger(e)
                if not t or (t.get("objectClass"), t.get("id")) != ("System", "on-start-of-layout"):
                    continue
                for row in e.subtree():
                    for c in row.conditions:
                        obj = params_of(c).get("object") if c.get("id") == "pick-all" else None
                        if not obj or d.types.get(obj, {}).get("isGlobal"):
                            continue
                        sets = [a for r in row.subtree() for a in r.actions
                                if a.get("objectClass") == obj and SETS_ON_INSTANCES.match(str(a.get("id")))]
                        if sets:
                            out.append(finding("restart", row, f"{row.place}: On start of layout picks all {obj} "
                                       f"and sets them ({len(sets)} actions), on layout {layout}, which the events "
                                       f"enter again with Restart layout or Go to layout; the layout's own {obj} "
                                       f"instances start as the layout holds them, so set them there in the layout "
                                       f"and delete these actions"))
    return out


# --- k: an expression that should be a function ------------------------------------------
def calls(expr: str) -> list[str]:
    """Every call in an expression, as written from its name to its closing parenthesis,
    without spaces; texts in it are kept, so Get("a") and Get("b") are two calls."""
    plain, out = blank(expr), []
    for m in CALL.finditer(plain):
        depth = 0
        for j in range(m.end() - 1, len(plain)):
            depth += PAREN.get(plain[j], 0)
            if depth == 0:
                out.append(unspaced(expr[m.start():j + 1]))
                break
    return out


def nesting(expr: str) -> int:
    depth = deepest = 0
    for ch in expr:
        depth += PAREN.get(ch, 0)
        deepest = max(deepest, depth)
    return deepest


def expression_shape(expr: str) -> tuple[int, str]:
    """(parentheses deep, the longest call written twice) of an expression, texts emptied."""
    counted = Counter(calls(expr))
    repeated = max((c for c, n in counted.items() if n > 1), key=len, default="")
    return nesting(blank(expr)), repeated


def expression_rule(d: Design) -> list[dict]:
    out = []
    for e in d.all_rows():
        for kind, param, i, v in d.all_expressions(e):
            deep, repeated = expression_shape(v)
            if len(repeated) >= REPEATED_CALL and deep >= DEEP:
                shown = repeated if len(repeated) <= 60 else repeated[:57] + "..."
                out.append(finding("expression", e, f"{e.place} {kind[:-1]} {i} ({param}): computes {shown} "
                           f"more than once, {deep} parentheses deep; write a function that returns the value, "
                           f"with a local variable for the repeated part and a sub-event per decision, and call "
                           f"it here (a ?: for a two-way choice, an Array or Advanced Random for a table or a "
                           f"weighted pick)"))
    return out


# --- l: a part placed once beside an object that moves without it ----------------------
MOVES = {"set-position", "set-x", "set-y", "move-forward", "move-at-angle", "set-position-to-another-object",
         "set-position-3d"}
TWEEN_MOVES = {"position", "offsetx", "offsety"}


def moves(a: dict) -> bool:
    if a.get("id") in MOVES and not a.get("behaviorType"):
        return True
    prop = str(params_of(a).get("property", "")).lower()
    return str(a.get("id", "")).startswith("tween-") and prop in TWEEN_MOVES


def has_parent(d: Design) -> set[str]:
    """Types a layout's hierarchy or an Add child action makes a child of something: their
    position follows a parent, whichever one it is."""
    type_of, parent_of = {}, {}
    for lay in d.layouts.values():
        for layer in lay.get("layers", []):
            for inst in layer.get("instances", []):
                graph = inst.get("sceneGraphData") or {}
                type_of[inst.get("uid")] = inst.get("type")
                for child in graph.get("children") or []:
                    parent_of[child.get("uid")] = inst.get("uid")
    children = {type_of.get(child) for child in parent_of}
    for e in d.all_rows():
        for a in e.actions:
            if a.get("id") == "add-child":
                children.add(params_of(a).get("child"))
    return children


def together_made(d: Design) -> set[tuple[str, str]]:
    """Pairs of types made as one thing: members of one container, or created in one action list.
    A part spawned at an object and then left on its own, a bullet or a puff, is not one."""
    out = set()
    for c in d.containers:
        members = [str(m) for m in c.get("members", [])]
        out |= {(a, b) for a in members for b in members if a != b}
    for e in d.all_rows():
        made = [str(params_of(a).get("object-to-create", "")) for a in e.actions if a.get("id") == "create-object"]
        out |= {(a, b) for a in made for b in made if a != b}
    return out


def every_tick(d: Design, e: Ev) -> bool:
    """A row that runs on every tick: no trigger on it or above it, outside a function."""
    return e.function is None and not any(d.trigger(r) for r in [e, *e.ancestors()])


def follow_rule(d: Design) -> list[dict]:
    """A part set to an object's position in one event, then the object moved by another
    event that leaves the part behind: a label that stays where a card was drawn."""
    placed: dict[tuple[str, str], list[Ev]] = {}
    for e in d.all_rows():
        for a in e.actions:
            part = a.get("objectClass")
            if not part or not moves(a) or a.get("behaviorType"):
                continue
            text = " ".join(blank(v) for v in d.expressions("actions", a).values())
            owners = {m.group(1) for m in re.finditer(r"(?<![\w.])(\w+)\s*\.\s*(?:x|y|imagepointx|imagepointy)\b",
                                                      text, re.I)}
            if a.get("id") == "set-position-to-another-object":
                owners.add(str(params_of(a).get("object", "")))
            for owner in owners:
                if owner in d.types and owner != part:
                    placed.setdefault((owner, part), []).append(e)
    children, pinned = has_parent(d), {n for n, t in d.types.items()
                                for b in t.get("behaviorTypes", []) if b.get("behaviorId") == "Pin"}
    together = together_made(d)
    left: dict[tuple[int, str], tuple[Ev, list[str], Ev]] = {}     # (row, owner) -> row, parts, placing row
    for (owner, part), where in placed.items():
        if (owner, part) not in together or part in children or part in pinned \
                or any(every_tick(d, e) for e in where):
            continue
        for e in d.all_rows():
            if not any(a.get("objectClass") == owner and moves(a) for a in e.actions):
                continue
            if e in where or any(a.get("objectClass") == part for r in e.subtree() for a in r.actions):
                continue
            left.setdefault((id(e), owner), (e, [], where[0]))[1].append(part)
    out = []
    for (_, owner), (e, parts, first) in left.items():
        names = " and ".join(sorted(parts))
        out.append(finding("follow", e, f"{e.place}: moves {owner} and leaves {names} where {first.place} set "
                   f"{'them' if len(parts) > 1 else 'it'} from {owner}'s position; make {names} children of {owner}: "
                   f"in a layout put {'their instances' if len(parts) > 1 else 'its instance'} under the {owner} "
                   f"instance as a template hierarchy and create {owner} with create hierarchy on and that template, "
                   f"or call {owner}: Add child where both are created; then delete the actions that set their "
                   f"position", short=f"{owner} without {names}"))
    return sorted(out, key=lambda f: (f["sheet"], f["event"]))


RULES = (conditions_rule, guard_rule, idle_rule, pair_rule, trigger_rule, twice_rule, global_rule, uid_rule,
         data_rule, restart_rule, expression_rule, follow_rule)


def candidates(d: Design) -> list[dict]:
    """What every rule finds, before the measurement sorts it into findings and questions."""
    return [f for rule in RULES for f in rule(d)]


def review(d: Design) -> list[dict]:
    """The findings and the events the questions name: each candidate with `ask`, None for a
    finding or the key of its question, and the dropped candidates left out."""
    out = []
    for f in candidates(d):
        ask = CLASSES.get((f["rule"], f["variant"]), DROPPED)
        if ask != DROPPED:
            out.append({**f, "ask": ask})
    return out


# --- what it prints ----------------------------------------------------------------------
def questions(found: list[dict], shown: set[str]) -> list[str]:
    """The fixed questions, each naming the events of the sheets shown that it asks about,
    the ones with the most conditions or cases first."""
    first = next((f for f in found if f["ask"] and f["event"] and f["sheet"] in shown), None)
    example = f"{first['sheet']} --events {first['event']}" if first else "<sheet> --events <number>"
    lines = ["questions: answer each one yes or no, reading the events it names with print_sheet.py, for example "
             f"python scripts/print_sheet.py {example}. For each yes, change the sheet as the question says, with "
             f"edit_sheet.py, and run this review again:"]
    for n, (ask, text) in enumerate(QUESTIONS.items(), 1):
        named = [f for f in found if f["ask"] == ask and f["sheet"] in shown]
        named.sort(key=lambda f: (-leading_count(f["short"]), f["sheet"], f["event"] or 0))
        places = [f"{f['sheet']} {f['event']} ({f['short']})" if f["event"] else f"{f['sheet']} ({f['short']})"
                  for f in named[:SHOWN]]
        more = f" and {len(named) - SHOWN} more" if len(named) > SHOWN else ""
        lines.append(f"  {n}. {text}" + (f" Events: {', '.join(places)}{more}." if places else
                                         " No event named: answer it for the sheets you changed."))
    return lines


def leading_count(short: str) -> int:
    """The number a short description starts with ("11 conditions"), 0 when it starts with none."""
    m = re.match(r"\d+", short)
    return int(m.group()) if m else 0


def report(found: list[dict], sheets: list[str]) -> tuple[list[str], list[str]]:
    """The finding lines by sheet, and the questions."""
    lines = []
    for sheet in sheets:
        here = [f for f in found if f["ask"] is None and f["sheet"] == sheet]
        if here:
            lines.append(f"== {sheet}")
            lines += [f"  {f['rule']}: {f['line']}" for f in here]
    return lines, questions(found, set(sheets))


def main() -> int:
    ap = c3.argument_parser(
        "Review the design of a project's event sheets: where an event, a global or a link is hard to read or "
        "fragile, with the form to write instead, then fixed questions to answer from print_sheet.py. Reads "
        "the files only; run it after check_project.py passes and before the editor.", EPILOG)
    ap.add_argument("--sheets", nargs="+", metavar="NAME", help="print the findings and questions of these sheets "
                                                                "only (default: every sheet); globals are read over "
                                                                "the whole project either way")
    args = ap.parse_args()
    c3.utf8_output()
    findings = c3.Findings()
    c3.stop_with_a_sentence("review_design.py", findings)
    project = c3.Project.open(args, findings)
    c3.note_drift(project.rag)
    d = Design.of(project)
    for name in args.sheets or []:
        if name not in d.sheets:
            print(f"no event sheet named {name!r}{c3.closest(name, d.sheets)}; sheets: {', '.join(d.sheets)}",
                  file=sys.stderr)
            return 2
    sheets = args.sheets or list(d.sheets)
    found = review(d)
    lines, asked = report(found, sheets)
    room = args.limit - sum(len(q) + 1 for q in asked) - 600 if args.limit else 0
    shown = c3.fitting(lines, max(room, 1)) if args.limit else len(lines)
    if lines[:shown]:
        print("\n".join(lines[:shown]))
    if shown < len(lines):
        print(f"... {len(lines) - shown} more lines of findings not printed: fix these and run again, or pass "
              f"--limit 0, or name fewer sheets with --sheets")
    print("\n".join(asked))
    hits = [f for f in found if f["ask"] is None and f["sheet"] in sheets]
    named = sum(1 for f in found if f["ask"] and f["sheet"] in sheets)
    print(f"design: {len(hits)} finding{'' if len(hits) == 1 else 's'} on "
          f"{len({f['sheet'] for f in hits})} of {len(sheets)} sheets; the questions name {named} "
          f"event{'' if named == 1 else 's'}")
    print("next: fix every finding line in one plan of edit_sheet.py, each names the event and what to write; "
          "answer every question and change what you answered yes; then run check_project.py, and this review "
          "again until it prints no finding. A finding the user asked for on purpose stays, and the hand-over "
          "says why.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
