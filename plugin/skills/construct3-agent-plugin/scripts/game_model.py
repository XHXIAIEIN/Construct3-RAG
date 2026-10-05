"""A game's design as data, and the prototype that runs it: the expression
language of its rules, the checks of its tables, and a simulator that plays
its acceptance tests without the editor.

Not a command. check_design.py checks and plays a design with it, and
play_design.py turns the same tests into a plan for preview_project.py.

The rules are data a model wrote, never code: this file parses each
expression into a tree of literals, names, operators and the functions
listed in FUNCTIONS, and evaluates the tree itself. Nothing a design holds is
passed to eval, exec or a shell, and the JavaScript play_design.py writes is
generated from the same trees.

The semantics follow the event sheet's: a rule is an event, its trigger the
first condition, its "if" the other conditions, its "do" the actions in
order, its "children" the sub-events that run after the actions, "else" an
Else after the sibling before it; `wait N` defers the rest of the actions and
the sub-events; `restart` restarts the layout at the end of the tick, which
resets what the layout holds (Arrays placed on it, instance variables, a
text's text, positions) and keeps the globals, then runs the start rules
again. Comparisons give 1 or 0, `&` joins text when either side is text and
is a logical and otherwise, and At() outside an Array gives 0.

Every tap is a tap on the screen. Touch *On any touch start* fires for every
tap, a tap on an object included. It fires before *On touched object*,
whatever the order of the two events in the sheet. So a tap fires the rules
of every screen input whose region holds it, then the rules of the object it
taps. The prototype knows where a point tap lands. A tap on an object or at
an argument's position counts as outside every region, and a rule that reads
a position the prototype does not know stops the test.
"""
from __future__ import annotations

import json
import math
import random as _random
import re
from dataclasses import dataclass, field

TICK = 1 / 60
AFTER_INPUT = 0.15          # seconds the game runs after each input, in the prototype and in the editor
SETTLE = 1.0                # seconds a test runs after its last step before its last expects are read again
OPS_MAX = 50_000            # actions one test may run before it counts as a loop
TESTS_MAX = 6
STATE_MAX = 10              # a small game: what a small model can keep consistent, and the prototype explain
RULES_MAX = 14
STEPS_MAX = 60              # steps of one test
WAIT_MAX = 20.0             # seconds one test may wait in all
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}$")
KEY = re.compile(r"(Arrow(Left|Right|Up|Down)|Space|Enter|Escape|Key[A-Z]|Digit[0-9]|[a-z0-9])$")
PROPS = ("x", "y", "text", "frame", "visible", "angle", "width", "height", "opacity")
SEEN = ("text", "x", "y", "frame", "visible", "angle", "width", "height", "opacity", "shown")   # props the player sees
# "Stone.shown" counts the Stone instances the player sees; "Stone.shown(frame=1)" those showing frame 1
SHOWN = re.compile(r"([A-Za-z][A-Za-z0-9_]*)\.shown(?:\(frame\s*=\s*(\d+)\))?")

DESIGN_KEYS = {"game", "core_loop", "reference", "screen", "state", "inputs", "rules", "win", "lose", "tests"}
STATE_KEYS = {"name", "start", "size", "stored_in", "means", "keep", "const"}
INPUT_KEYS = {"name", "player", "args", "game"}
RULE_KEYS = {"id", "on", "if", "do", "children", "else", "feedback"}
TEST_KEYS = {"name", "steps"}


class ModelError(Exception):
    """An expression or an effect that cannot be read or run; the message says what to write."""


class Unplaced:
    """The position of a tap the prototype does not know: on an object, or at a point given in shares."""

    def __repr__(self) -> str:
        return "unplaced"


UNPLACED = Unplaced()


# --- expressions ------------------------------------------------------------------------
TOKEN = re.compile(r"""\s*(?:
    (?P<num>\d+\.\d*|\.\d+|\d+)
  | (?P<str>"(?:[^"]|"")*")
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>\+=|-=|<>|<=|>=|!=|==|&&|\|\||[-+*/%^=<>&|?:(),.])
  )""", re.VERBOSE)
WRONG_OPS = {"!=": "<>", "==": "=", "&&": "&", "||": "|"}


def tokens(text: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    text = str(text)
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            bad = text[pos:].strip()[:1]
            hint = ' Text is in double quotes, "like this"; a quote inside it is written twice.' if bad in "'“”" else ""
            raise ModelError(f"cannot read {bad!r} at character {pos + 1} of {text!r}.{hint}")
        kind = m.lastgroup
        value = m.group(kind)
        if kind == "op" and value in WRONG_OPS:
            raise ModelError(f"{value!r} in {text!r}: the event sheet writes {WRONG_OPS[value]!r}")
        out.append((kind, value))
        pos = m.end()
    return out


@dataclass
class Node:
    kind: str                       # num str name call at prop un bin cond
    value: object = None
    args: list = field(default_factory=list)


# Each function: (fewest arguments, most arguments or None for any, what it does in words)
FUNCTIONS = {
    "abs": (1, 1), "floor": (1, 1), "ceil": (1, 1), "round": (1, 1), "sqrt": (1, 1), "int": (1, 1),
    "min": (2, None), "max": (2, None), "clamp": (3, 3), "len": (1, 1), "find": (2, 2), "str": (1, 1),
    "random": (1, 2), "choose": (1, None), "InARow": (3, 3), "count": (2, 2),
}
ARRAY_FUNCS = ("InARow", "count")    # their first argument is an Array's name


class Parser:
    def __init__(self, text: str) -> None:
        self.text = str(text)
        self.toks = tokens(self.text)
        self.i = 0

    def peek(self, value: str | None = None) -> bool:
        if self.i >= len(self.toks):
            return False
        return value is None or self.toks[self.i][1] == value

    def take(self, value: str | None = None) -> tuple[str, str]:
        if self.i >= len(self.toks):
            raise ModelError(f"{self.text!r} ends where {value!r} was expected" if value else f"{self.text!r} ends too early")
        tok = self.toks[self.i]
        if value is not None and tok[1] != value:
            raise ModelError(f"{self.text!r}: {value!r} expected before {tok[1]!r}")
        self.i += 1
        return tok

    def whole(self) -> Node:
        node = self.ternary()
        if self.i < len(self.toks):
            rest = self.toks[self.i][1]
            hint = " An effect is one assignment, 'name = expression'; a condition is one comparison." if rest in ("=", "+=", "-=") else ""
            raise ModelError(f"{self.text!r}: unexpected {rest!r}.{hint}")
        return node

    def ternary(self) -> Node:
        cond = self.binary(0)
        if self.peek("?"):
            self.take("?")
            yes = self.ternary()
            self.take(":")
            no = self.ternary()
            return Node("cond", None, [cond, yes, no])
        return cond

    LEVELS = (("|",), ("&",), ("=", "<>", "<", "<=", ">", ">="), ("+", "-"), ("*", "/", "%"), ("^",))

    def binary(self, level: int) -> Node:
        if level == len(self.LEVELS):
            return self.unary()
        left = self.binary(level + 1)
        while self.peek() and self.toks[self.i][0] == "op" and self.toks[self.i][1] in self.LEVELS[level]:
            op = self.take()[1]
            right = self.binary(level + 1)
            left = Node("bin", op, [left, right])
        return left

    def unary(self) -> Node:
        if self.peek("-"):
            self.take()
            return Node("un", "-", [self.unary()])
        if self.peek("+"):
            self.take()
            return self.unary()
        return self.atom()

    def atom(self) -> Node:
        kind, value = self.take()
        if kind == "num":
            return Node("num", float(value))
        if kind == "str":
            return Node("str", value[1:-1].replace('""', '"'))
        if value == "(":
            node = self.ternary()
            self.take(")")
            return node
        if kind != "name":
            raise ModelError(f"{self.text!r}: a value was expected where {value!r} stands")
        if self.peek("."):
            self.take(".")
            member = self.take()[1]
            if member == "At":
                self.take("(")
                args = self.arguments()
                if not 1 <= len(args) <= 2:
                    raise ModelError(f"{self.text!r}: {value}.At(x, y) takes one or two indexes")
                return Node("at", value, args)
            if member in ("Width", "Height"):
                return Node("prop", (value, member))
            raise ModelError(object_member(self.text, value, member))
        if self.peek("("):
            self.take("(")
            args = self.arguments()
            if value not in FUNCTIONS:
                raise ModelError(f"{self.text!r}: no function {value!r}; the functions are {', '.join(FUNCTIONS)}")
            lo, hi = FUNCTIONS[value]
            if len(args) < lo or hi is not None and len(args) > hi:
                raise ModelError(f"{self.text!r}: {value}() takes {lo}" + (f" to {hi}" if hi != lo else "") + " arguments")
            if value in ARRAY_FUNCS and args[0].kind != "name":
                raise ModelError(f"{self.text!r}: the first argument of {value}() is an Array's name")
            return Node("call", value, args)
        if value in FUNCTIONS:
            raise ModelError(f"{self.text!r}: {value} is a function; write {value}(...)")
        return Node("name", value)

    def arguments(self) -> list[Node]:
        args = []
        if self.peek(")"):
            self.take(")")
            return args
        while True:
            args.append(self.ternary())
            if self.peek(","):
                self.take(",")
                continue
            self.take(")")
            return args


def object_member(text: str, obj: str, member: str) -> str:
    """What to write in place of an object's property in a design, which reads only its own state."""
    if obj in ("Touch", "Mouse", "Keyboard"):
        return (f"{text!r}: {obj}.{member} reads the input device. What the player does is an input of the design, "
                f"and the touch position its argument: \"args\": [\"x\"] with \"game\": {{\"tap\": \"screen\", "
                f"\"args\": {{\"x\": \"x\"}}}}, then the rule fired by it reads x")
    row = obj[0].lower() + obj[1:] + member[:1].upper() + member[1:].lower()
    return (f"{text!r}: {obj}.{member} reads an object of the game, and a design reads only its own state and the "
            f"input's arguments. Give it a state row, {{\"name\": \"{row}\", \"start\": ..., \"stored_in\": "
            f"\"{obj}.{member.lower()}\"}}, and write {row} here. An Array of the state is read as {obj}.At(x, y)")


def parse(text: str) -> Node:
    if not isinstance(text, str) or not text.strip():
        raise ModelError(f"{text!r}: an expression is a non-empty string")
    return Parser(text).whole()


def names_in(node: Node) -> set[str]:
    """The state names and arguments an expression reads; an Array counts by its name."""
    found: set[str] = set()
    if node.kind == "name":
        found.add(node.value)
    elif node.kind in ("at",):
        found.add(node.value)
    elif node.kind == "prop":
        found.add(node.value[0])
    for a in node.args:
        found |= names_in(a)
    return found


def is_text(v) -> bool:
    return isinstance(v, str)


def num(v) -> float:
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return 0.0
    return float(v)


def show(v) -> str:
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v)


def in_a_row(grid: list[list[float]], n: int, value) -> bool:
    w = len(grid)
    h = len(grid[0]) if w else 0
    for x in range(w):
        for y in range(h):
            for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if all(0 <= x + dx * k < w and 0 <= y + dy * k < h and grid[x + dx * k][y + dy * k] == value
                       for k in range(n)):
                    return True
    return False


# --- the design --------------------------------------------------------------------------
@dataclass
class Rule:
    id: str
    path: str
    on: str | None
    when: list[Node]
    when_text: list[str]
    do: list[tuple]                 # ("set", target, op, Node) | ("wait", Node) | ("restart",)
    do_text: list[str]
    children: list["Rule"]
    otherwise: bool
    feedback: str
    every: float | None = None


@dataclass
class State:
    name: str
    start: object
    kind: str                       # value or array
    size: tuple[int, int] | None
    stored_in: str
    keep: bool
    const: bool
    path: str
    shown: tuple[str, int | None] | None = None   # (object, frame or None) for a count of instances seen

    @property
    def seen(self) -> bool:
        """Whether the player sees this row: a property of an instance on screen, or a count of instances."""
        return bool(self.shown) or "." in self.stored_in and self.stored_in.rsplit(".", 1)[1] in SEEN


class Design:
    """A design read from its JSON: problems go to self.problems as (path, what to write)."""

    def __init__(self, data) -> None:
        self.problems: list[tuple[str, str]] = []
        self.data = data if isinstance(data, dict) else {}
        self.state: dict[str, State] = {}
        self.inputs: dict[str, dict] = {}
        self.rules: list[Rule] = []
        self.by_id: dict[str, Rule] = {}
        self.win: Node | None = None
        self.lose: Node | None = None
        self.tests: list[dict] = []
        if not isinstance(data, dict):
            self.bad("design", "is not a JSON object; write the design as references/designing-a-game.md shows")
            return
        self.read()

    def bad(self, path: str, what: str) -> None:
        if (path, what) not in self.problems:
            self.problems.append((path, what))

    @property
    def ends(self) -> bool:
        """Whether the game is won or lost. With "win": "none" and "lose": "none" it never ends, as a demo of
        one mechanic, and has no new game to restart into."""
        return self.win is not None or self.lose is not None

    def text(self, key: str, what: str) -> str:
        v = self.data.get(key)
        if not isinstance(v, str) or len(v.strip()) < 3:
            self.bad(key, f"missing; {what}")
            return ""
        return v.strip()

    def keys(self, item, allowed: set, path: str) -> bool:
        if not isinstance(item, dict):
            self.bad(path, f"is {type(item).__name__}; it is an object with the keys {', '.join(sorted(allowed))}")
            return False
        for k in sorted(set(item) - allowed):
            self.bad(f"{path}.{k}", f"unknown key; this entry has {', '.join(sorted(allowed))}")
        return True

    def expr(self, text, path: str) -> Node | None:
        try:
            return parse(text)
        except ModelError as e:
            self.bad(path, str(e))
            return None

    def read(self) -> None:
        d = self.data
        self.keys(d, DESIGN_KEYS, "design")
        self.text("game", "the game's name as the player sees it")
        self.text("core_loop", "one sentence: what the player does again and again, and what it leads to")
        ref = d.get("reference")
        if not isinstance(ref, dict) or not isinstance(ref.get("example"), str) or not isinstance(ref.get("takes"), str) \
                or not ref.get("takes", "").strip():
            self.bad("reference", 'missing; {"example": "<id of the closest official example, read with print_sheet.py '
                                  '--project <its folder>>", "takes": "what this design takes from how it is built"}')
        screen = d.get("screen")
        if not isinstance(screen, dict) or not screen or not all(isinstance(v, str) and v.strip() for v in screen.values()):
            self.bad("screen", 'missing; each region of the screen and where it sits: {"title": "above the board", '
                               '"board": "centre", "status": "below the board"}')
        self.read_state()
        self.read_inputs()
        rules = d.get("rules")
        if not isinstance(rules, list) or not rules:
            self.bad("rules", "missing; a list of rules, each one event: trigger, conditions, effects")
        else:
            self.rules = [rule for i, item in enumerate(rules) if (rule := self.read_rule(item, f"rules[{i}]", top=True))]
            if len(self.all_rules()) > RULES_MAX:
                self.bad("rules", f"{len(self.all_rules())} rules, sub-rules counted; at most {RULES_MAX}. Keep the "
                                  f"game small: one rule per thing the player does or the game does by itself")
            for name in self.inputs:
                fired = [r for r in self.rules if r.on == name]
                if fired and not any(r.feedback.strip() for r in fired):
                    self.bad(f"{fired[0].path}.feedback", f"missing: the input {name} fires this rule, and none of its "
                             f"rules says what the player sees. Add \"feedback\": \"<what the player sees when it works>\" "
                             f"to this rule, e.g. \"a stone appears on the crossing\"")
        win = d.get("win")
        if win is None:
            self.bad("win", 'missing; the expression over the state that is true once the game is won: "over = 1", '
                            'or "none" when nothing is won (a demo of one mechanic, a toy, a game that is only lost)')
        elif win != "none":
            self.win = self.expr(win, "win")
        lose = d.get("lose")
        if lose is None:
            self.bad("lose", 'missing; the expression that is true once the game is lost, or "none" when the game '
                             'has no losing (two players, one of whom wins)')
        elif lose != "none":
            self.lose = self.expr(lose, "lose")
        tests = d.get("tests")
        if not isinstance(tests, list) or not tests:
            self.bad("tests", "missing; acceptance tests that play the rules: input, wait, expect")
        elif len(tests) > TESTS_MAX:
            self.bad("tests", f"{len(tests)} tests; at most {TESTS_MAX}")
        else:
            for i, t in enumerate(tests):
                self.read_test(t, f"tests[{i}]")
        self.check_names()

    def read_state(self) -> None:
        rows = self.data.get("state")
        if not isinstance(rows, list) or not rows:
            self.bad("state", 'missing; one row per piece of state: {"name": "score", "start": 0, "stored_in": "global"}')
            return
        stores: dict[str, str] = {}
        if len(rows) > STATE_MAX:
            self.bad("state", f"{len(rows)} rows; at most {STATE_MAX}. Keep the game small: a value that follows "
                              f"from others is an expression, not a row")
        for i, row in enumerate(rows):
            path = f"state[{i}]"
            if not self.keys(row, STATE_KEYS, path):
                continue
            name = row.get("name")
            if not isinstance(name, str) or not NAME.match(name) or name in FUNCTIONS or name in ("dt", "restart", "wait"):
                self.bad(f"{path}.name", f"{name!r}: a name is an English letter, then letters, digits or _, and not "
                                         f"a function's name")
                continue
            if name in self.state:
                self.bad(f"{path}.name", f"{name!r} is the name of {self.state[name].path} too")
                continue
            where = row.get("stored_in")
            if not isinstance(where, str) or not where.strip():
                self.bad(f"{path}.stored_in", 'where the game keeps it: "global" (a global variable of this name), '
                                              '"Array" (an Array object of this name), "Object.variable", "Object.text", '
                                              '"Object.x", "Object.y", "Object.frame" of an object with one instance, '
                                              'or "Object.shown", how many instances of Object the player sees')
                continue
            where = where.strip()
            kind = "array" if where == "Array" else "value"
            shown = None
            if where not in ("global", "Array"):
                m = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)", where)
                s = SHOWN.fullmatch(where)
                if s:
                    shown = (s.group(1), int(s.group(2)) if s.group(2) else None)
                elif not m:
                    self.bad(f"{path}.stored_in", f"{where!r}: \"global\", \"Array\", \"Object.variable\" such as "
                                                  f"\"Player.lives\" or \"Status.text\", or \"Object.shown\" or "
                                                  f"\"Object.shown(frame=1)\", how many Object instances the player "
                                                  f"sees, of any frame or of that frame")
                    continue
            if where in stores and where not in ("global", "Array"):
                self.bad(f"{path}.stored_in", f"{where!r} also stores {stores[where]}: one fact is kept in one place")
            stores[where] = name
            size = None
            if kind == "array":
                s = row.get("size")
                if not (isinstance(s, list) and len(s) == 2 and all(isinstance(v, int) and 1 <= v <= 1000 for v in s)):
                    self.bad(f"{path}.size", "an Array's [width, height], whole numbers from 1: [15, 15]")
                    continue
                size, start = (s[0], s[1]), 0
            else:
                start = row.get("start")
                if isinstance(start, bool):
                    start = int(start)
                if not isinstance(start, (int, float, str)):
                    self.bad(f"{path}.start", "the value at the first launch: a number or a text")
                    continue
                if isinstance(start, (int, float)):
                    start = float(start)
                if shown and not (isinstance(start, float) and start >= 0 and start == int(start)):
                    self.bad(f"{path}.start", f"{where} is a count of instances: a whole number from 0, the instances "
                                              f"the first screen shows")
                    continue
            self.state[name] = State(name, start, kind, size, where, bool(row.get("keep")), bool(row.get("const")), path,
                                     shown)

    def read_inputs(self) -> None:
        rows = self.data.get("inputs")
        if not isinstance(rows, list) or not rows:
            self.bad("inputs", 'missing; what the player does: {"name": "place", "player": "tap an empty crossing", '
                               '"args": ["c", "r"], "game": {"tap": "Cell", "args": {"c": "col", "r": "row"}}}')
            return
        for i, row in enumerate(rows):
            path = f"inputs[{i}]"
            if not self.keys(row, INPUT_KEYS, path):
                continue
            name = row.get("name")
            if not isinstance(name, str) or not NAME.match(name) or name in ("start", "tick") or name.startswith("every"):
                self.bad(f"{path}.name", f"{name!r}: a plain name, not start, tick or every")
                continue
            if name in self.inputs or name in self.state:
                self.bad(f"{path}.name", f"{name!r} names something else too")
                continue
            if not isinstance(row.get("player"), str) or not row["player"].strip():
                self.bad(f"{path}.player", "what the player does, in words: \"tap an empty crossing\"")
            args = row.get("args") or []
            if not isinstance(args, list) or not all(isinstance(a, str) and NAME.match(a) for a in args) or len(args) > 3:
                self.bad(f"{path}.args", 'up to three names the input carries, read by its rules: ["c", "r"]')
                args = []
            for a in args:
                if a in self.state:
                    self.bad(f"{path}.args", f"{a!r} is a state name too; give the argument another name")
            game = row.get("game")
            self.read_binding(game, args, f"{path}.game")
            self.inputs[name] = {"args": args, "game": game if isinstance(game, dict) else {}, "path": path,
                                 "player": str(row.get("player") or ""), "kind": input_kind(game)}

    def read_binding(self, game, args: list[str], path: str) -> None:
        """How the player does it in the game: tap an object, tap a point of the screen, or press a key."""
        what = ('how the player does it in the game: {"tap": "Cell", "args": {"c": "col", "r": "row"}} taps the Cell '
                'whose instance variables col and row hold the arguments; {"tap": [0.5, 0.5]} taps that point of the '
                'screen, as shares of its width and height, and fires on every tap unless "region": [x0, y0, x1, y1] '
                'names the part of the screen it fires in; {"tap": "screen", "args": {"x": "x"}} taps the screen '
                'where the argument x says, in px of the layout; {"key": "ArrowLeft"} presses a key')
        if not isinstance(game, dict) or len({"tap", "key"} & set(game)) != 1:
            self.bad(path, what)
            return
        extra = set(game) - {"tap", "key", "args", "seconds", "region"}
        if extra:
            self.bad(path, f"unknown key(s) {', '.join(sorted(extra))}; " + what)
        if "key" in game:
            if not isinstance(game["key"], str) or not KEY.match(game["key"]):
                self.bad(f"{path}.key", "a key: ArrowLeft, ArrowRight, ArrowUp, ArrowDown, Space, Enter, Escape, KeyA, Digit1")
            if args:
                self.bad(path, "a key carries no arguments; make one input per key")
            if "region" in game:
                self.bad(f"{path}.region", "a key has no region; leave it out")
            seconds = game.get("seconds", 0.1)
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0.05 <= seconds <= 3:
                self.bad(f"{path}.seconds", "how long the key is held, 0.05 to 3 seconds")
            return
        tap = game["tap"]
        if isinstance(tap, list):
            if len(tap) != 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in tap):
                self.bad(f"{path}.tap", "a point as shares of the screen, [0.5, 0.5] for its middle")
            if args:
                self.bad(path, "a tap on a point carries no arguments; tap an object for them")
            region = game.get("region")
            if region is not None:
                if not (isinstance(region, list) and len(region) == 4 and all(
                        isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in region)
                        and region[0] < region[2] and region[1] < region[3]):
                    self.bad(f"{path}.region", "the part of the screen the tap fires in, [x0, y0, x1, y1] as shares "
                                               "of its width and height: [0, 0.8, 1, 1] for the bottom fifth")
                elif len(tap) == 2 and not in_region(tap, region):
                    self.bad(f"{path}.tap", f"{tap} lies outside its own region {region}; tap a point inside it")
            return
        if "region" in game:
            self.bad(f"{path}.region", "only a tap on a point has a region: a tap on an object fires where the object "
                                       "is, and the rule of a tap at an argument's position tests the argument, "
                                       "\"x < 360\"")
        if tap == "screen":
            bound = game.get("args") or {}
            if not isinstance(bound, dict) or set(bound) != set(args) or not set(bound.values()) <= {"x", "y"}:
                self.bad(f"{path}.args", f"each argument {args} and the coordinate of the tap it holds, \"x\" or "
                                         f"\"y\" in px of the layout: " + json.dumps({a: "x" for a in args}))
            return
        if not isinstance(tap, str) or not NAME.match(tap):
            self.bad(f"{path}.tap", "the object's name as the project spells it, or a point [x, y] as shares of the screen")
            return
        bound = game.get("args") or {}
        if not isinstance(bound, dict) or set(bound) != set(args) or not all(isinstance(v, str) and NAME.match(v)
                                                                               for v in bound.values()):
            self.bad(f"{path}.args", f"each argument {args} and the instance variable of {tap} that holds it: "
                                     + json.dumps({a: "col" for a in args}) if args else
                     f"leave it out: the input carries no arguments")

    def read_rule(self, r, path: str, top: bool) -> Rule | None:
        if not self.keys(r, RULE_KEYS, path):
            return None
        rid = r.get("id")
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", rid):
            self.bad(f"{path}.id", f"{rid!r}: a short name for the rule, the comment above its event: \"place\"")
            rid = f"?{path}"
        elif rid in self.by_id:
            self.bad(f"{path}.id", f"{rid!r} is the id of {self.by_id[rid].path} too")
        node = path
        if not rid.startswith("?"):
            path = f"{path} '{rid}'"    # a finding names the rule as well as its place
        on, every = r.get("on"), None
        if top:
            if not isinstance(on, str):
                self.bad(f"{path}.on", 'what fires it: "start" (the layout starts, again after a restart), "tick" (every '
                                       'tick), "every 1.5" (every 1.5 seconds), or an input\'s name')
            elif on.startswith("every"):
                m = re.fullmatch(r"every\s+(\d+(?:\.\d+)?)", on)
                if not m or not 0.05 <= float(m.group(1)) <= 60:
                    self.bad(f"{path}.on", '"every N", N seconds from 0.05 to 60: "every 1.5"')
                else:
                    every = float(m.group(1))
            elif on not in ("start", "tick") and on not in self.inputs:
                self.bad(f"{path}.on", f"{on!r} is no input; the inputs are {', '.join(self.inputs) or 'none'}, or "
                                       f"start, tick, every N")
        elif on is not None:
            self.bad(f"{path}.on", "a sub-rule has no trigger: it runs right after its parent's effects, as a "
                                   "sub-event does; leave \"on\" out")
        conds = r.get("if") or []
        if not isinstance(conds, list):
            self.bad(f"{path}.if", 'a list of conditions, each one comparison: ["over = 0", "Grid.At(c, r) = 0"]')
            conds = []
        when = [n for k, c in enumerate(conds) if (n := self.expr(c, f"{path}.if[{k}]"))]
        effects = r.get("do") or []
        if not isinstance(effects, list):
            self.bad(f"{path}.do", 'a list of effects: ["score += 1", "status = \\"Score \\" & score", "wait 0.5", "restart"]')
            effects = []
        do = []
        for k, e in enumerate(effects):
            try:
                do.append(effect(e))
            except ModelError as exc:
                self.bad(f"{path}.do[{k}]", str(exc))
        otherwise = r.get("else") is True
        if "else" in r and not isinstance(r.get("else"), bool):
            self.bad(f"{path}.else", "true, for the case when the rule before it did not run")
        if otherwise and top:
            self.bad(f"{path}.else", "an else is a sub-rule after a sibling sub-rule; put both under the parent's children")
        if not do and not r.get("children"):
            self.bad(f"{path}.do", "empty, so the rule changes nothing; write its effects")
        feedback = r.get("feedback")
        rule = Rule(rid, path, on if top else None, when, [str(c) for c in conds], do, [str(e) for e in effects], [],
                    otherwise, feedback if isinstance(feedback, str) else "", every)
        self.by_id[rid] = rule
        kids = r.get("children") or []
        if not isinstance(kids, list):
            self.bad(f"{path}.children", "a list of sub-rules")
            kids = []
        cases = [c for c in kids if isinstance(c, dict) and (c.get("if") or c.get("else") is True)]
        for k, c in enumerate(kids):
            if isinstance(c, dict) and not c.get("if") and c.get("else") is not True and cases:
                self.bad(f"{node}.children[{k}].if", "empty, so this sub-rule runs every time beside siblings that test "
                         "a case; write the condition of its case, such as \"InARow(Board, 5, turn)\", or make it the "
                         "other case with \"else\": true after the sibling it excludes")
            if k == 0 and isinstance(c, dict) and c.get("else") is True:
                self.bad(f"{path}.children[0].else", "an else follows a sibling sub-rule; there is none before it")
            child = self.read_rule(c, f"{node}.children[{k}]", top=False)
            if child:
                rule.children.append(child)
        return rule

    def read_test(self, t, path: str) -> None:
        if not self.keys(t, TEST_KEYS, path):
            return
        if not isinstance(t.get("name"), str) or not t["name"].strip():
            self.bad(f"{path}.name", "what the test shows, in words: \"five across wins\"")
        steps = t.get("steps")
        if not isinstance(steps, list) or not steps:
            self.bad(f"{path}.steps", 'a list of steps: {"do": "place", "c": 7, "r": 7}, {"wait": 1}, {"expect": "over = 1"}')
            return
        if len(steps) > STEPS_MAX:
            self.bad(f"{path}.steps", f"{len(steps)} steps; at most {STEPS_MAX}")
        waited = 0.0
        read: list[dict] = []
        for k, s in enumerate(steps):
            at = f"{path}.steps[{k}]"
            if not isinstance(s, dict):
                self.bad(at, 'a step is an object: {"do": ...}, {"wait": ...}, {"expect": ...} or {"set": ...}')
                continue
            kinds = [k2 for k2 in ("do", "wait", "expect", "set") if k2 in s]
            if len(kinds) != 1:
                self.bad(at, 'one of "do" (an input, with its arguments beside it), "wait" (seconds), "expect" (an '
                             'expression that must be true) or "set" (a fixture: "name = expression")')
                continue
            kind = kinds[0]
            step = {"kind": kind, "path": at}
            if kind == "do":
                name = s["do"]
                if name not in self.inputs:
                    self.bad(f"{at}.do", f"{name!r} is no input; the inputs are {', '.join(self.inputs) or 'none'}")
                    continue
                want = self.inputs[name]["args"]
                given = {k2: v for k2, v in s.items() if k2 != "do"}
                if set(given) != set(want):
                    self.bad(at, f"the input {name} carries {want or 'no arguments'}; give exactly those beside \"do\"")
                    continue
                if not all(isinstance(v, (int, float, str)) and not isinstance(v, bool) for v in given.values()):
                    self.bad(at, "an argument is a number or a text")
                    continue
                step.update(input=name, args={k2: float(v) if isinstance(v, (int, float)) else v for k2, v in given.items()})
                waited += AFTER_INPUT
            elif kind == "wait":
                w = s["wait"]
                if isinstance(w, bool) or not isinstance(w, (int, float)) or not 0 < w <= 10 or len(s) > 1:
                    self.bad(at, "seconds to let the game run, more than 0 and at most 10")
                    continue
                step["seconds"] = float(w)
                waited += w
            elif kind == "expect":
                node = self.expr(s["expect"], f"{at}.expect")
                if not node:
                    continue
                if len(s) > 1:
                    self.bad(at, "an expect step holds the expression alone")
                step.update(node=node, text=s["expect"])
            else:
                try:
                    eff = effect(s["set"])
                except ModelError as exc:
                    self.bad(f"{at}.set", str(exc))
                    continue
                if eff[0] != "set":
                    self.bad(f"{at}.set", "a fixture sets a value: \"fx = 100\"")
                    continue
                step.update(effect=eff, text=s["set"])
            read.append(step)
        if waited > WAIT_MAX:
            self.bad(f"{path}.steps", f"the steps run the game {waited:g} s; at most {WAIT_MAX:g}")
        self.tests.append({"name": t.get("name", path), "path": path, "steps": read})

    def check_names(self) -> None:
        """Every name an expression reads is state, an argument in reach, or dt in a tick rule."""
        arrays = {n for n, s in self.state.items() if s.kind == "array"}

        def scope_ok(node: Node, allowed: set[str], path: str) -> None:
            for n in sorted(names_in(node)):
                if n not in allowed:
                    near = ", ".join(sorted(allowed)) or "none"
                    self.bad(path, f"{n!r} is not known here; the names here are {near}")
            walk_arrays(node, path)

        def walk_arrays(node: Node, path: str) -> None:
            if node.kind == "at" and node.value not in arrays:
                self.bad(path, f"{node.value}.At(): {node.value} is no Array of the state")
            if node.kind == "call" and node.value in ARRAY_FUNCS and node.args[0].value not in arrays:
                self.bad(path, f"{node.value}(): {node.args[0].value} is no Array of the state")
            if node.kind == "name" and node.value in arrays:
                self.bad(path, f"{node.value} is an Array; read a cell with {node.value}.At(x, y)")
            for i, a in enumerate(node.args):
                if not (node.kind == "call" and node.value in ARRAY_FUNCS and i == 0):
                    walk_arrays(a, path)

        values = set(self.state)

        def rule(r: Rule, allowed: set[str], tick: bool) -> None:
            for k, c in enumerate(r.when):
                scope_ok(c, allowed, f"{r.path}.if[{k}]")
            for k, e in enumerate(r.do):
                if e[0] == "set":
                    target = e[1]
                    st = self.state.get(target[0])
                    if not st:
                        self.bad(f"{r.path}.do[{k}]", f"{target[0]!r} is no state; an effect changes a state row")
                    elif st.kind == "array" and target[1] is None:
                        self.bad(f"{r.path}.do[{k}]", f"{target[0]} is an Array; set a cell: {target[0]}.At(x, y) = ...")
                    elif st.kind != "array" and target[1] is not None:
                        self.bad(f"{r.path}.do[{k}]", f"{target[0]} is no Array")
                    for idx in target[1] or []:
                        scope_ok(idx, allowed, f"{r.path}.do[{k}]")
                    scope_ok(e[3], allowed, f"{r.path}.do[{k}]")
                elif e[0] == "wait":
                    scope_ok(e[1], allowed, f"{r.path}.do[{k}]")
                elif e[0] == "restart" and r.on == "start":
                    self.bad(f"{r.path}.do[{k}]", "a start rule that restarts restarts forever")
            for c in r.children:
                rule(c, allowed, tick)

        for r in self.rules:
            args = set(self.inputs[r.on]["args"]) if r.on in self.inputs else set()
            rule(r, values | args | ({"dt"} if r.on == "tick" else set()), r.on == "tick")
        for key, node in (("win", self.win), ("lose", self.lose)):
            if node:
                scope_ok(node, values, key)
        for t in self.tests:
            for s in t["steps"]:
                if s["kind"] == "expect":
                    scope_ok(s["node"], values, f"{s['path']}.expect")
                if s["kind"] == "set":
                    target = s["effect"][1]
                    if target[0] not in self.state:
                        self.bad(f"{s['path']}.set", f"{target[0]!r} is no state")
                    elif self.state[target[0]].shown:
                        self.bad(f"{s['path']}.set", f"{target[0]} counts the {self.state[target[0]].shown[0]} instances "
                                                     f"the player sees, and a fixture cannot make or show instances. "
                                                     f"Reach it with the inputs, \"do\" steps, and set only what the "
                                                     f"rules read")
                    scope_ok(s["effect"][3], values, f"{s['path']}.set")

    def all_rules(self) -> list[Rule]:
        out: list[Rule] = []

        def walk(r: Rule) -> None:
            out.append(r)
            for c in r.children:
                walk(c)
        for r in self.rules:
            walk(r)
        return out


def effect(text) -> tuple:
    """An effect as ("set", (name, [index nodes] or None), op, Node), ("wait", Node) or ("restart",)."""
    if not isinstance(text, str) or not text.strip():
        raise ModelError(f"{text!r}: an effect is a non-empty string such as \"score += 1\"")
    s = text.strip()
    if s == "restart":
        return ("restart",)
    m = re.fullmatch(r"wait\s+(.+)", s)
    if m:
        return ("wait", parse(m.group(1)))
    p = Parser(s)
    kind, name = p.take()
    if kind != "name":
        raise ModelError(f"{s!r}: an effect starts with the state it changes: \"score += 1\", \"Grid.At(c, r) = turn\", "
                         f"\"wait 0.5\" or \"restart\"")
    index = None
    if p.peek("."):
        p.take(".")
        if p.take()[1] != "At":
            p.i -= 1
            raise ModelError(object_member(s, name, p.take()[1]))
        p.take("(")
        index = p.arguments()
        if not 1 <= len(index) <= 2:
            raise ModelError(f"{s!r}: {name}.At(x, y) takes one or two indexes")
    if not p.peek() or p.toks[p.i][1] not in ("=", "+=", "-="):
        raise ModelError(f"{s!r}: an effect is \"name = expression\", \"name += expression\" or \"name -= expression\"")
    op = p.take()[1]
    value = p.whole()
    return ("set", (name, index), op, value)


def input_kind(game) -> str:
    """key, object (Touch On touched object), point or screen (both Touch On any touch start)."""
    if not isinstance(game, dict):
        return ""
    if "key" in game:
        return "key"
    tap = game.get("tap")
    if isinstance(tap, list):
        return "point"
    return "screen" if tap == "screen" else "object"


def in_region(point, region) -> bool:
    return region[0] <= point[0] <= region[2] and region[1] <= point[1] <= region[3]


def how_tapped(inp: dict) -> str:
    tap = inp["game"].get("tap")
    if inp["kind"] == "object":
        return f"a tap on {tap}"
    if inp["kind"] == "point":
        return f"a tap at {tap} of the screen"
    return "a tap on the screen"


# --- the simulator -----------------------------------------------------------------------
class Sim:
    """The design's state machine at 60 ticks a second."""

    def __init__(self, design: Design, seed: int = 1) -> None:
        self.d = design
        self.rng = _random.Random(seed)
        self.t = 0.0
        self.ops = 0
        self.values: dict[str, object] = {}
        self.arrays: dict[str, list[list[float]]] = {}
        self.pending: list[tuple[float, int, Rule, int, dict, str]] = []
        self.restart_due: tuple[str, str] | None = None     # the rule that asked for it, and what started that rule
        self.rule = ""                  # the rule running now
        self.cause = ""                 # the step that started it, "" for a timer
        self.tap: tuple[str, str] | None = None     # while a screen input runs for another tap: (that tap, this input)
        self.echoed: list[tuple[str, str]] = []     # the last input's rules run for it as a tap on the screen
        self.settling = False
        self.late: dict[str, tuple[str, str]] = {}  # in the settle: what a restart changed, by state name
        self.restarts = 0
        self.ran: dict[str, int] = {}
        self.won = self.lost = False
        self.order = 0
        self.after_restart: list[tuple[str, object, object]] = []
        self.reset(first=True)
        self.baseline = dict(self.values)
        self.run_start()
        self.baseline = dict(self.values)
        self.watch()

    def reset(self, first: bool) -> None:
        for n, s in self.d.state.items():
            if s.kind == "array":
                self.arrays[n] = [[0.0] * s.size[1] for _ in range(s.size[0])]
            elif first or s.stored_in != "global":
                self.values[n] = s.start

    def run_start(self) -> None:
        for r in self.d.rules:
            if r.on == "start":
                self.run(r, {})

    # expressions
    def ev(self, node: Node, scope: dict):
        k = node.kind
        if k == "num" or k == "str":
            return node.value
        if k == "name":
            if node.value in scope:
                if scope[node.value] is UNPLACED:
                    raise ModelError(self.unplaced(node.value))
                return scope[node.value]
            if node.value == "dt":
                return TICK
            return self.values[node.value]
        if k == "at":
            grid = self.arrays[node.value]
            idx = [int(math.floor(num(self.ev(a, scope)))) for a in node.args] + [0]
            x, y = idx[0], idx[1]
            if 0 <= x < len(grid) and 0 <= y < len(grid[0]):
                return grid[x][y]
            return 0.0
        if k == "prop":
            grid = self.arrays[node.value[0]]
            return float(len(grid) if node.value[1] == "Width" else len(grid[0]))
        if k == "un":
            return -num(self.ev(node.args[0], scope))
        if k == "cond":
            return self.ev(node.args[1], scope) if truth(self.ev(node.args[0], scope)) else self.ev(node.args[2], scope)
        if k == "bin":
            op = node.value
            a = self.ev(node.args[0], scope)
            if op == "&" and not is_text(a):
                b = self.ev(node.args[1], scope)
                if is_text(b):
                    return show_plain(a) + b
                return 1.0 if truth(a) and truth(b) else 0.0
            if op == "|":
                return 1.0 if truth(a) or truth(self.ev(node.args[1], scope)) else 0.0
            b = self.ev(node.args[1], scope)
            return binop(op, a, b)
        if k == "call":
            return self.call(node, scope)
        raise ModelError(f"cannot evaluate {k}")

    def call(self, node: Node, scope: dict):
        f = node.value
        if f in ARRAY_FUNCS:
            grid = self.arrays[node.args[0].value]
            rest = [self.ev(a, scope) for a in node.args[1:]]
            if f == "InARow":
                return 1.0 if in_a_row(grid, int(num(rest[0])), rest[1]) else 0.0
            return float(sum(v == rest[0] for col in grid for v in col))
        a = [self.ev(x, scope) for x in node.args]
        if f == "abs":
            return abs(num(a[0]))
        if f == "floor":
            return float(math.floor(num(a[0])))
        if f == "ceil":
            return float(math.ceil(num(a[0])))
        if f == "round":
            return float(math.floor(num(a[0]) + 0.5))
        if f == "sqrt":
            return math.sqrt(max(0.0, num(a[0])))
        if f == "int":
            return float(int(num(a[0])))
        if f == "min":
            return min(num(v) for v in a)
        if f == "max":
            return max(num(v) for v in a)
        if f == "clamp":
            return min(max(num(a[0]), num(a[1])), num(a[2]))
        if f == "len":
            return float(len(show_plain(a[0])))
        if f == "find":
            return float(show_plain(a[0]).lower().find(show_plain(a[1]).lower()))
        if f == "str":
            return show_plain(a[0])
        if f == "random":
            lo, hi = (0.0, num(a[0])) if len(a) == 1 else (num(a[0]), num(a[1]))
            return lo + self.rng.random() * (hi - lo)
        if f == "choose":
            return self.rng.choice(a)
        raise ModelError(f"no function {f}")

    def unplaced(self, name: str) -> str:
        rule = self.rule
        if not self.tap:
            return f"rule {rule} reads {name}, the position of a tap the prototype does not know"
        tap, screen = self.tap
        where = (f": in the game it is where the {self.d.inputs[tap]['game']['tap']} lies"
                 if self.d.inputs[tap]["kind"] == "object" else "")
        return (f"{tap} is {how_tapped(self.d.inputs[tap])}, and every tap is also a tap on the screen: Touch On any "
                f"touch start fires {screen} for it, before On touched object. Rule {rule} then reads {name}, the "
                f"position of that tap, which the prototype does not know{where}. Give {rule} a condition, placed "
                f"before the one that reads {name}, that is false on that tap, such as a state of the game's "
                f"phase")

    # rules
    def run(self, r: Rule, scope: dict, from_effect: int = 0) -> bool:
        self.rule = r.id
        if from_effect == 0:
            if not all(truth(self.ev(c, scope)) for c in r.when):
                return False
            self.ran[r.id] = self.ran.get(r.id, 0) + 1
        for k in range(from_effect, len(r.do)):
            e = r.do[k]
            self.ops += 1
            if self.ops > OPS_MAX:
                raise ModelError(f"more than {OPS_MAX} effects ran in one test: rules fire each other without end")
            if e[0] == "wait":
                self.order += 1
                self.pending.append((self.t + max(0.0, num(self.ev(e[1], scope))), self.order, r, k + 1, dict(scope),
                                     self.cause))
                return True
            if e[0] == "restart":
                self.restart_due = (r.id, self.cause)
                continue
            (name, index), op, value = e[1], e[2], e[3]
            v = self.ev(value, scope)
            if index is None:
                old = self.values[name]
                self.values[name] = v if op == "=" else (num(old) + num(v) if op == "+=" else num(old) - num(v))
            else:
                grid = self.arrays[name]
                idx = [int(math.floor(num(self.ev(a, scope)))) for a in index] + [0]
                if 0 <= idx[0] < len(grid) and 0 <= idx[1] < len(grid[0]):
                    old = grid[idx[0]][idx[1]]
                    grid[idx[0]][idx[1]] = num(v) if op == "=" and not is_text(v) else (
                        v if op == "=" else num(old) + num(v) if op == "+=" else num(old) - num(v))
        self.children(r, scope)
        return True

    def children(self, r: Rule, scope: dict) -> None:
        """Sub-rules in order; an else runs when no rule of its chain before it ran."""
        done = False
        for c in r.children:
            if c.otherwise and done:
                continue
            done = self.run(c, scope) or (c.otherwise and done)

    def screen_inputs(self, name: str, args: dict) -> dict[str, dict]:
        """The screen inputs a tap fires, each with its arguments: itself when it is one, and every other whose
        region holds the tap. A coordinate the tap does not give is UNPLACED."""
        inp = self.d.inputs[name]
        kind = inp["kind"]
        if kind == "key":
            return {}
        given = {coord: args[arg] for arg, coord in (inp["game"].get("args") or {}).items()} if kind == "screen" else {}
        out = {}
        for other, o in self.d.inputs.items():
            if o["kind"] not in ("point", "screen"):
                continue
            region = o["game"].get("region")
            if other != name and region and not (kind == "point" and in_region(inp["game"]["tap"], region)):
                continue
            out[other] = dict(args) if other == name else {
                arg: given.get(coord, UNPLACED) for arg, coord in (o["game"].get("args") or {}).items()}
        return out

    def fire(self, name: str, args: dict, step: str = "") -> None:
        """Play one input as the runtime gets it. First run the rules of every screen input the tap fires, in
        the sheet's order (Touch On any touch start). Then run the input's own rules (On touched object, On key
        pressed)."""
        screen = self.screen_inputs(name, args)
        self.echoed = []
        for r in self.d.rules:
            if r.on in screen:
                self.tap = (name, r.on) if r.on != name else None
                self.cause = step + (f" ({name}, whose tap also fired {r.on})" if r.on != name else f" ({name})")
                before = dict(self.ran)
                self.run(r, dict(screen[r.on]))
                if r.on != name:
                    self.echoed += [(r.on, rid) for rid, c in self.ran.items() if c != before.get(rid, 0)]
        self.tap = None
        for r in self.d.rules:
            if r.on == name and name not in screen:
                self.cause = f"{step} ({name})"
                self.run(r, dict(args))
        self.cause = ""
        self.advance(AFTER_INPUT)

    def settle(self, seconds: float = SETTLE) -> None:
        """Let the game run after a test's last step, noting what a restart changes meanwhile. A change by
        anything else, such as a timer or a Wait, is the game running on and is not noted."""
        self.settling, self.late = True, {}
        try:
            self.advance(seconds)
        finally:
            self.settling = False

    def tick(self) -> None:
        before = self.t
        self.t += TICK
        for r in self.d.rules:
            if r.on == "tick":
                self.run(r, {})
            elif r.every and math.floor(self.t / r.every + 1e-9) > math.floor(before / r.every + 1e-9):
                self.run(r, {})
        due = sorted((p for p in self.pending if p[0] <= self.t + 1e-9), key=lambda p: (p[0], p[1]))
        self.pending = [p for p in self.pending if p[0] > self.t + 1e-9]
        for _, _, r, k, scope, cause in due:
            self.cause = cause          # a restart after a Wait names the step that started its rule
            try:
                self.run(r, scope, from_effect=k)
            finally:
                self.cause = ""
        if self.restart_due:
            rid, cause = self.restart_due
            self.restart_due = None
            self.restarts += 1
            self.pending = []
            before = (dict(self.values), json.dumps(self.arrays))
            self.reset(first=False)
            self.run_start()
            if self.settling:
                said = f"the restart of rule {rid}" + (f", started by {cause.strip()}" if cause.strip() else "")
                old_arrays = json.loads(before[1])
                for n in self.d.state:
                    old = old_arrays.get(n) if n in self.arrays else before[0].get(n)
                    if old != (self.arrays.get(n) if n in self.arrays else self.values.get(n)):
                        self.late.setdefault(n, (rid, said))
            for n, s in self.d.state.items():
                if s.kind != "array" and not s.keep and self.values[n] != self.baseline[n]:
                    self.after_restart.append((n, self.values[n], self.baseline[n]))
        self.watch()

    def advance(self, seconds: float) -> None:
        for _ in range(max(1, round(seconds / TICK))):
            self.tick()

    def watch(self) -> None:
        if self.d.win and truth(self.ev(self.d.win, {})):
            self.won = True
        if self.d.lose and truth(self.ev(self.d.lose, {})):
            self.lost = True

    def set(self, eff: tuple) -> None:
        """A test's fixture: one effect run outside the rules."""
        self.run(Rule("fixture", "", None, [], [], [eff], [], [], False, ""), {})
        self.ran.pop("fixture", None)


def truth(v) -> bool:
    if isinstance(v, str):
        raise ModelError(f"the text {v!r} stands where a condition is tested; a condition compares: x = \"text\"")
    return v != 0


def show_plain(v) -> str:
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else f"{v:g}"
    return str(v)


def binop(op: str, a, b):
    if op in ("=", "<>"):
        same = (a == b) if is_text(a) == is_text(b) else show_plain(a) == show_plain(b)
        return 1.0 if same == (op == "=") else 0.0
    if op in ("<", "<=", ">", ">="):
        if is_text(a) and is_text(b):
            x, y = a, b
        else:
            x, y = num(a), num(b)
        return 1.0 if {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op] else 0.0
    if op == "+":
        if is_text(a) or is_text(b):
            return show_plain(a) + show_plain(b)
        return num(a) + num(b)
    x, y = num(a), num(b)
    if op == "-":
        return x - y
    if op == "*":
        return x * y
    if op == "/":
        return x / y if y else (math.inf if x > 0 else -math.inf if x < 0 else 0.0)
    if op == "%":
        return math.fmod(x, y) if y else 0.0
    if op == "^":
        return x ** y
    if op == "&":
        return show_plain(a) + show_plain(b)
    raise ModelError(f"no operator {op}")
