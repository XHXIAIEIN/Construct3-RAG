# Designing a new game before building it

A new game starts as a design in JSON, before any project file: the user's
request, what this round leaves for later, the core loop, the closest
official example, the screen, the state table, the inputs, the rules as
data, win and lose, and acceptance tests. `scripts/check_design.py`
checks that the design is complete and plays the tests on the rules
themselves, a prototype that runs in milliseconds without the editor. Only a
design whose tests pass is built. After the build, `scripts/play_design.py`
plays the same tests in the editor on the built game, so a bug in the rules
shows before the build and a bug in the events after it.

## Steps

1. Find the closest official example by its tags and addons,
   `python scripts/search_guides.py WORD ... --pitfalls 0`, and read its
   events with the `print_sheet.py` command it prints when the example
   projects are on the machine.
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
 "request": "a whack-a-mole: a mole pops out of one of nine holes and I tap it before it hides, I score for each hit, three escapes and it's over, with sounds and moles that get faster",
 "later": ["sounds", "moles that get faster"],
 "core_loop": "A mole shows in one of nine holes; tap it before it moves on. Three escapes end the game",
 "reference": {"example": "<id of the example read>", "takes": "what the design takes from how it is built"},
 "screen": {"score": "top-left", "holes": "centre, a 3 x 3 grid", "message": "below the holes"},
 "state": [
  {"name": "score", "start": 0, "stored_in": "global"},
  {"name": "scoreLine", "start": "Score: 0", "stored_in": "ScoreText.text"},
  {"name": "escapes", "start": 0, "stored_in": "global"},
  {"name": "over", "start": 0, "stored_in": "global", "means": "0 playing, 1 over"},
  {"name": "hole", "start": 4, "stored_in": "Mole.hole", "means": "the hole the mole is in, 0 to 8"},
  {"name": "message", "start": "", "stored_in": "Message.text"}],
 "inputs": [
  {"name": "hit", "player": "tap a hole", "args": ["h"], "game": {"tap": "Hole", "args": {"h": "index"}}},
  {"name": "again", "player": "tap anywhere once it is over", "game": {"tap": [0.5, 0.9]}}],
 "rules": [
  {"id": "new-game", "on": "start", "do": ["score = 0", "escapes = 0", "over = 0"]},
  {"id": "hit", "on": "hit", "if": ["over = 0", "h = hole"], "do": ["score += 1", "scoreLine = \"Score: \" & score", "hole = floor(random(9))"],
   "feedback": "the mole jumps to another hole and the score goes up"},
  {"id": "escape", "on": "every 1", "if": ["over = 0"], "do": ["escapes += 1", "hole = floor(random(9))"],
   "children": [{"id": "lose", "if": ["escapes >= 3"], "do": ["over = 1", "message = \"Over: \" & score & \" points. Tap\""]}]},
  {"id": "restart", "on": "again", "if": ["over = 1"], "do": ["restart"], "feedback": "a new game starts"}],
 "win": "score >= 20",
 "lose": "over = 1",
 "tests": [
  {"name": "a hit scores", "steps": [{"set": "hole = 4"}, {"do": "hit", "h": 4}, {"expect": "score = 1"}, {"expect": "scoreLine = \"Score: 1\""}]},
  {"name": "a miss does not", "steps": [{"set": "hole = 4"}, {"do": "hit", "h": 2}, {"expect": "score = 0"}]},
  {"name": "twenty hits win", "steps": [{"set": "score = 19"}, {"set": "hole = 1"}, {"do": "hit", "h": 1}, {"expect": "score >= 20"}]},
  {"name": "three escapes lose, a tap restarts", "steps": [{"wait": 3.2}, {"expect": "over = 1"},
   {"expect": "find(message, \"Over\") >= 0"}, {"do": "again"}, {"wait": 0.3}, {"expect": "over = 0"}, {"expect": "escapes = 0"}]}]}
```

- `request`: the user's request in their own words, copied, not summed up.
  A review holds the game to it, and a summary drifts toward what was
  built. The ok line of the check repeats its start.
- `later`: what this round leaves for later, each in a few words: the
  parts of the request the design does not build, and what the request
  takes for granted, such as sound or a best score. The next session then
  neither builds them again nor forgets them. An empty list is refused. If
  the design builds the whole request, write `["nothing left out"]`. The
  ok line of the check lists the items.
- `screen`: each region the player sees and where it sits. The key is the
  object type that shows the region (`Board`), a state row kept in an
  object (`message` for `Message.text`), or words of type names. Words of
  type names match every type whose name holds them: `score` matches
  `ScoreLabel` and `ScoreText` together. The words before the first comma
  give the place: `top`, `bottom`, `left`, `right`, `centre` as thirds of
  the screen (`top-left`, `bottom centre`), and `above KEY`, `below KEY`,
  `left of KEY`, `right of KEY` for another entry or object; a comment may
  follow the comma. `play_design.py` checks such a place on the first
  screen: the middle of the object's instances lies in that third, or past
  that side of the other entry. `review_look.py` asks about a place written
  in other words.
- `state`: one row per piece of state, the table of `generating-a-project.md`,
  "Plan the state". `stored_in` is `"global"` (a global variable of the same
  name), `"Array"` (an Array object of the same name, with `"size": [w, h]`
  in place of `start`), or `"Object.variable"`, `"Object.text"`,
  `"Object.x"`, `"Object.y"`, `"Object.frame"` of an object with one
  instance, or `"Object.shown"`, how many instances of the object the
  player sees (visible, not transparent, on a shown layer), and
  `"Object.shown(frame=1)"`, how many of them show frame 1. A rule changes a
  count as a number, `stones += 1`; the game changes it by creating,
  destroying, showing or hiding instances. `"keep": true` for a value meant
  to outlast a restart (a best score), `"const": true` for a tuning value no
  rule changes. The check prints who writes and who reads each row and
  refuses a row nothing writes or nothing reads, and one place that stores
  two rows.
- `inputs`: what the player does, with the arguments the rules read. `game`
  says how it is done in the game: `{"tap": "Hole", "args": {"h": "index"}}`
  taps the Hole whose instance variable `index` holds `h`;
  `{"tap": [0.5, 0.9]}` taps that point of the screen, as shares of its width
  and height; `{"tap": "screen", "args": {"x": "x"}}` taps where the argument
  `x` says, in px of the layout, for a game that follows the finger;
  `{"key": "ArrowLeft"}` presses a key. A tap anywhere on the screen is a
  point, never an object: a Sprite as a tap area takes only the taps inside
  it, and the check refuses an object for an input whose `player` says the
  screen or anywhere. A design reads only its own state and
  the arguments: a basket's position is a state row stored in `Basket.x`, not
  `Basket.X` in a rule.
- Every tap is also a tap on the screen: a screen input fires on every tap,
  a tap on an object included, before the object's rules. So a tap on a
  Hole also runs the rules of `again`, first. To limit a tap on a point to a
  part of the screen, give it `"region": [x0, y0, x1, y1]`, as shares. The
  prototype counts a tap on an object as outside every region. When a rule
  of `{"tap": "screen", ...}` runs on a tap on an object and reads its
  argument, the prototype does not know that position, and the check stops
  there. Give that rule a condition that is false on that tap.
- `rules`: each one event. `on` is its trigger: `start`, `tick`, `every N`
  (seconds) or an input's name. `if` holds its other conditions, `do` its
  actions in order, `children` its sub-events, and `"else": true` makes a
  child the Else of the child before it. A rule fired by an input names its
  `feedback`, what the player sees: the input -> rule -> feedback table.
  The table is held to rows the player sees: each input changes, through
  its rules or rules that read what they change, a row stored in a text, a
  position, a frame, a visibility or a count of instances shown. A rule
  fired by an input that writes a cell of an Array changes, in the same
  rule or its sub-rules, a row that shows the Array, since a cell is not on
  screen: for a board, a count of the instances shown; for a list, such as
  stacked shields, a text, position, frame or visibility whose expression
  reads the Array, `line = "Shields " & (shields.At(0, 0) + shields.At(1, 0))`.
  A status line that does not read the Array says nothing of the cell.
- `win` and `lose`: expressions over the state, or `"none"` for a game
  never won or never lost. Some test must reach each, and neither may hold
  on the first screen, before the player does anything. A demo of one
  mechanic (a toggle, a countdown, a drag that snaps) writes `"none"` for
  both: it never ends, so it needs no restart rule and no test restarts it.
- A player who does nothing must not win. The prototype plays on from the
  first screen without input for up to 120 s, and refuses a win that comes
  before the lose, with the rule that set what the win reads. A game won by
  outlasting a timer, where the rules do not model the danger (a rock to
  dodge), writes `"won_by_waiting": "<what the player does while it runs>"`.
  The check refuses that field when the game is not won without input.
- `tests`: from a first launch each. `{"do": "hit", "h": 4}` does an input,
  then lets the game run 0.15 s; `{"wait": 1}` lets it run;
  `{"expect": "score = 1"}` must hold; `{"set": "hole = 4"}` is a fixture
  that puts the game in a state, for what is random or slow; it cannot set a
  count of instances. Every rule must run in some test, every input be
  done and be followed by an expect on a row the player sees, the row that
  shows the Array where it writes a cell, and some test restart after the
  win or the lose.
  After the last step the game runs 1 s more, and the expects at the end
  of the test are read again in the prototype; the editor reads again
  those that still hold. So a restart that a `wait` holds back fails the
  test that ends before the restart.

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
  writes the cell, `Board.At(c, r) = turn`, and counts the piece,
  `stones += 1` on a row stored in `Stone.shown`; its first child is
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
  `wait 0.5`, then a second value the restart rule tests, so a tap made
  while the end shows does not restart at once. A restart on a tap on the
  screen runs before the tap on an object that ends the game, so it sees
  the game still on and does not fire on that tap. A restart on the same
  input as the end, or on Touch *On tap*, which fires at the release, runs
  after the end. Without the second value it restarts on the tap that
  ended the game.

## From the design to the events

| Design | Event |
|--------|-------|
| `"on": "start"` | System *On start of layout* |
| `"on": "tick"` | no trigger: the block runs every tick |
| `"on": "every 1"` | System *Every 1 seconds* |
| an input `{"tap": "Hole", ...}` | Touch *On touched Hole*; an argument is the tapped instance's variable, `Hole.index` |
| an input `{"tap": [x, y]}` | Touch *On any touch start*, never *On tap*; it fires before every *On touched object* of the same tap, whatever the order of the events |
| `"region": [x0, y0, x1, y1]` | after *On any touch start*, *Compare two values* on `Touch.X` and `Touch.Y` against the region's edges: `OriginalViewportWidth * x0`, `OriginalViewportHeight * y0` and so on |
| an input `{"tap": "screen", "args": {"x": "x"}}` | Touch *On any touch start*; the argument is `Touch.X` |
| an input `{"key": ...}` | Keyboard *On key pressed* |
| a condition | *Compare variable*, *Compare two values* or the instance's own condition |
| `name = expr` | *Set value*, *Set text*, *Set instance variable*, *Set X* by where `name` is stored |
| `stones += 1` on `Stone.shown` | System *Create object* Stone, or *Set visible* on the Stone the event picked, such as the one on the tapped Cell; never an action on every Stone |
| `Grid.At(x, y) = v` | Array *Set value at (x, y)* |
| `InARow(Grid, n, v)` | two *For* loops over the Array and one *Compare two values* that tests the four directions |
| `wait N` | System *Wait N seconds* |
| `restart` | System *Restart layout* |
| `children`, `"else": true` | sub-events, System *Else* |

A state the design keeps in a global is declared with the start value as its
initial value; one kept in an object starts there in the layout, a text with
its `start` as the text, a count as that many visible instances on the first
layout. `play_design.py` reads each one in the project's files before it
opens the editor and refuses a start that differs from the design's. In the
editor it then reads the first screen without input: a text, a frame or a
count that differs from the prototype's, a win or a lose that holds there,
or an object outside the place its `screen` entry names is a finding.
