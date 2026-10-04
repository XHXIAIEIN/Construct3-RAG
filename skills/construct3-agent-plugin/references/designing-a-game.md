# Designing a new game before building it

A new game starts as a design in JSON, before any project file: the core
loop, the closest official example, the screen, the state table, the inputs,
the rules as data, win and lose, and acceptance tests. `scripts/check_design.py`
checks that the design is complete and plays the tests on the rules
themselves, a prototype that runs in milliseconds without the editor. Only a
design whose tests pass is built. After the build, `scripts/play_design.py`
plays the same tests in the editor on the built game, so a bug in the rules
shows before the build and a bug in the events after it.

## Steps

1. Find the closest official example by its tags and addons in
   `Construct3-RAG/data/c3-examples/<locale>/*.json`, and read its events:
   `python scripts/print_sheet.py --project <Construct-Example-Projects>/example-projects/<id>`.
   Take how it is built (which object holds what, which trigger does what),
   not its events: the design names it under `reference`.
2. Write the design, below, to `tools/design.json` in the project.
3. `python scripts/check_design.py tools/design.json` until its last line
   starts with `ok:`. Each finding names its path in the design.
4. Build the game from it: one event per rule, the rule's id in the comment
   above the event, each state row where its `stored_in` says.
5. `python scripts/check_project.py`, then
   `python scripts/play_design.py tools/design.json`. A failed expect names
   the test, the step, the values the game held and the rules whose events
   to compare with the design.

## The design

```json
{"game": "Whack",
 "core_loop": "A mole shows in one of nine holes; tap it before it moves on. Three escapes end the game",
 "reference": {"example": "<id of the example read>", "takes": "what the design takes from how it is built"},
 "screen": {"score": "top-left", "holes": "a 3 x 3 grid in the middle", "message": "below the holes"},
 "state": [
  {"name": "score", "start": 0, "stored_in": "global"},
  {"name": "escapes", "start": 0, "stored_in": "global"},
  {"name": "over", "start": 0, "stored_in": "global", "means": "0 playing, 1 over"},
  {"name": "hole", "start": 4, "stored_in": "Mole.hole", "means": "the hole the mole is in, 0 to 8"},
  {"name": "message", "start": "", "stored_in": "Message.text"}],
 "inputs": [
  {"name": "hit", "player": "tap a hole", "args": ["h"], "game": {"tap": "Hole", "args": {"h": "index"}}},
  {"name": "again", "player": "tap anywhere once it is over", "game": {"tap": [0.5, 0.9]}}],
 "rules": [
  {"id": "new-game", "on": "start", "do": ["score = 0", "escapes = 0", "over = 0"]},
  {"id": "hit", "on": "hit", "if": ["over = 0", "h = hole"], "do": ["score += 1", "hole = floor(random(9))"],
   "feedback": "the mole jumps to another hole and the score goes up"},
  {"id": "escape", "on": "every 1", "if": ["over = 0"], "do": ["escapes += 1", "hole = floor(random(9))"],
   "children": [{"id": "lose", "if": ["escapes >= 3"], "do": ["over = 1", "message = \"Over: \" & score & \" points. Tap\""]}]},
  {"id": "restart", "on": "again", "if": ["over = 1"], "do": ["restart"], "feedback": "a new game starts"}],
 "win": "score >= 20",
 "lose": "over = 1",
 "tests": [
  {"name": "a hit scores", "steps": [{"set": "hole = 4"}, {"do": "hit", "h": 4}, {"expect": "score = 1"}]},
  {"name": "a miss does not", "steps": [{"set": "hole = 4"}, {"do": "hit", "h": 2}, {"expect": "score = 0"}]},
  {"name": "twenty hits win", "steps": [{"set": "score = 19"}, {"set": "hole = 1"}, {"do": "hit", "h": 1}, {"expect": "score >= 20"}]},
  {"name": "three escapes lose, a tap restarts", "steps": [{"wait": 3.2}, {"expect": "over = 1"},
   {"expect": "find(message, \"Over\") >= 0"}, {"do": "again"}, {"wait": 0.3}, {"expect": "over = 0"}, {"expect": "escapes = 0"}]}]}
```

- `state`: one row per piece of state, the table of `generating-a-project.md`,
  "Plan the state". `stored_in` is `"global"` (a global variable of the same
  name), `"Array"` (an Array object of the same name, with `"size": [w, h]`
  in place of `start`), or `"Object.variable"`, `"Object.text"`,
  `"Object.x"`, `"Object.y"`, `"Object.frame"` of an object with one
  instance. `"keep": true` for a value meant to outlast a restart (a best
  score), `"const": true` for a tuning value no rule changes. The check
  prints who writes and who reads each row and refuses a row nothing writes
  or nothing reads, and one place that stores two rows.
- `inputs`: what the player does, with the arguments the rules read. `game`
  says how it is done in the game: `{"tap": "Hole", "args": {"h": "index"}}`
  taps the Hole whose instance variable `index` holds `h`;
  `{"tap": [0.5, 0.9]}` taps that point of the screen, as shares of its width
  and height; `{"tap": "screen", "args": {"x": "x"}}` taps where the argument
  `x` says, in px of the layout, for a game that follows the finger;
  `{"key": "ArrowLeft"}` presses a key. A design reads only its own state and
  the arguments: a basket's position is a state row stored in `Basket.x`, not
  `Basket.X` in a rule.
- `rules`: each one event. `on` is its trigger: `start`, `tick`, `every N`
  (seconds) or an input's name. `if` holds its other conditions, `do` its
  actions in order, `children` its sub-events, and `"else": true` makes a
  child the Else of the child before it. A rule fired by an input names its
  `feedback`, what the player sees: the input -> rule -> feedback table.
- `win` and `lose`: expressions over the state, or `"lose": "none"` for a
  game without losing. Some test must reach each.
- `tests`: from a first launch each. `{"do": "hit", "h": 4}` does an input,
  then lets the game run 0.15 s; `{"wait": 1}` lets it run;
  `{"expect": "score = 1"}` must hold; `{"set": "hole = 4"}` is a fixture
  that puts the game in a state, for what is random or slow. Every rule must
  run in some test, every input be done, and some test restart after the
  win or the lose.

## Rules as data

Expressions are written as in the event sheet: numbers, `"text"` (a quote
inside written twice), the state's names and the input's arguments, `+ - *
/ % ^`, `= <> < <= > >=`, `&` (joins when either side is text, a logical and
otherwise), `|`, `c ? a : b`, `Grid.At(x, y)`, `Grid.Width`, `Grid.Height`,
`dt` in a tick rule, and `abs floor ceil round sqrt int min max clamp len
find str random choose`, plus `InARow(Grid, n, value)`, whether n cells in a
row across, down or on a diagonal hold value, and `count(Grid, value)`.

Effects: `name = expr`, `name += expr`, `name -= expr`,
`Grid.At(x, y) = expr`, `wait N` (the rest of the actions and the sub-events
run N seconds later), and `restart`.

The prototype runs them as the runtime runs events: 60 ticks a second,
sub-events after the actions, a restart at the end of the tick that resets
what the layout holds (Arrays, instance variables, texts, positions), keeps
the globals and runs the `start` rules again. So a global that a new game
needs back at its start value is set in a `start` rule; the check refuses a
restart that leaves one as it was.

## Shapes that recur

- A line on a board (gomoku, tic-tac-toe, connect four): the placing rule
  writes the cell, `Board.At(c, r) = turn`; its first child is
  `{"id": "win", "if": ["InARow(Board, 5, turn)"], "do": [...]}` and its next
  child, `"else": true`, passes the turn, `turn = 3 - turn`. InARow tests
  every line of the board; neighbours counted by hand miss most of them.
- Something that falls: a `tick` rule `fy += 400 * dt`, with a child for
  reaching the floor that scores or costs a life and puts it back at the
  top. A test puts it near the floor with `{"set": "fy = 1000"}` instead of
  waiting for it.
- A countdown: an `every 1` rule `left -= 1` with a child `left <= 0` that
  ends the game; a test sets `left = 1` and waits 1.1 s.
- Moving in steps (snake, a grid walk): the positions as numbers or an
  Array, an `every 0.2` rule that moves, and inputs that only change the
  direction.
- The end and the restart: the rule that ends sets the state, then
  `wait 0.5`, then a second value the restart rule tests, so the tap that
  ended the game does not also restart it.

## From the design to the events

| Design | Event |
|--------|-------|
| `"on": "start"` | System *On start of layout* |
| `"on": "tick"` | no trigger: the block runs every tick |
| `"on": "every 1"` | System *Every 1 seconds* |
| an input `{"tap": "Hole", ...}` | Touch *On touched Hole*; an argument is the tapped instance's variable, `Hole.index` |
| an input `{"tap": [x, y]}` | Touch *On any touch start*, with *Compare two values* on `Touch.X` or `Touch.Y` when two inputs split the screen |
| an input `{"tap": "screen", "args": {"x": "x"}}` | Touch *On any touch start*; the argument is `Touch.X` |
| an input `{"key": ...}` | Keyboard *On key pressed* |
| a condition | *Compare variable*, *Compare two values* or the instance's own condition |
| `name = expr` | *Set value*, *Set text*, *Set instance variable*, *Set X* by where `name` is stored |
| `Grid.At(x, y) = v` | Array *Set value at (x, y)* |
| `InARow(Grid, n, v)` | two *For* loops over the Array and one *Compare two values* that tests the four directions |
| `wait N` | System *Wait N seconds* |
| `restart` | System *Restart layout* |
| `children`, `"else": true` | sub-events, System *Else* |

A state the design keeps in a global is declared with the start value as its
initial value; one kept in an object starts there in the layout, a text with
its `start` as the text. `play_design.py` reads each one in the project's
files before it opens the editor and refuses a start that differs from the
design's.
