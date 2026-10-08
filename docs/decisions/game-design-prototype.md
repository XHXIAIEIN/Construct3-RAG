# A New Game Is a Checked Design, Played as a Prototype Before It Is Built

Date: 2026-10-04

## Problem

A model that makes a game from a short request writes events that open,
preview without errors and still play wrong: a win that is never detected,
the wrong side named as the winner, a restart on the tap that ended the
game. The checker reads files and the preview reports runtime errors;
neither knows the game's rules, so neither sees these. Guidance per genre
fixes one genre at a time and does not reach the next one.

Task: for any genre, the model states what the game does in a form fixed
code can check and run, the rules are tried before any event is written,
and the built game is held to the same tests.

## Evidence

- A logic error is cheapest where the rules are data. In the prototype it
  shows in milliseconds as a value ("over = 0"); in the editor it costs a
  build and a preview run, and shows as an event the model has to read.
- A model fixes a refusal that names the fault in values and the place to
  change ("rule win would change it and did not run: over = 0 is false
  (over = 1)"). A refusal that names only the fault, where the fix needs an
  idea the model lacks, is resent unchanged until its steps run out.
- Tests that read only globals and Arrays pass a game whose state is right
  and whose screen is wrong: a pick that changes every instance of a type,
  a placing rule that writes the board and shows no piece, a game over at
  launch that a fixture steps past. The player sees instances: their text,
  place, frame, visibility, and how many of them there are.
- One tap is several triggers in a fixed order, not the sheet's: Touch *On
  any touch start*, then *On touched object*, then *On tap* at the release.
  A prototype that runs only the input a test names misses a tap that runs
  the rules of two inputs, and one that follows the sheet's order runs the
  two in the wrong order.
- A test that ends right after the step that starts a delayed effect, such
  as a restart after a Wait, passes although the player later sees the
  effect. A phase that a Wait sets after the end is a shape the guide
  recommends, so only a restart after the last step is a fault by itself.
- A value read in the running game has moved on by the time it is read; a
  start value read from the project files has not. Where an instance lands
  is the layout grid's to say, not the design's.
- A design that holds only the rules loses the request. A review then holds
  the game to the design, which is the model's reading of the request, and
  a part the model dropped leaves no trace: the next session either builds
  it unasked or never learns that it was asked for.
- A game can pass every test and still be won by a player who does nothing:
  a timer that ends the round and counts as the win, or a timer that raises
  the score. Every test plays inputs, so none shows it; a run without input
  does.
- The design step trades logic errors for games that are not delivered: a
  game that is delivered passed tests its model stated, and a game that
  fails says why. It does not by itself raise the share of games that play.

## Options

1. A kit per genre, whose events fixed code writes. Correct where a kit
   exists, nothing elsewhere, and every new genre is new code.
2. A stronger model for the events. Not every agent has one, and the errors
   above are rules the model never stated, not syntax.
3. Acceptance tests the model writes, played in the editor only. Each
   failure costs a build and an editor run and names an event to debug.
4. The design as data, with the rules in a small expression language that
   fixed code runs as a prototype, and the same tests played in the editor
   after the build.

## Decision

Option 4: `scripts/check_design.py`, `scripts/play_design.py`,
`scripts/game_model.py`, and `references/designing-a-game.md`.

- The design holds the user's request in their words, what this round
  leaves for later, the core loop, the official example it was read
  against, the screen's regions, the state table, the inputs with how each
  is done in the game, the rules (trigger, conditions, effects, sub-rules,
  Else), win and lose, and the tests. Each rule becomes one event.
- The check refuses a gap by its path: no request, an empty list of what is
  left for later, a state no rule writes or nothing reads, a fact stored
  twice, an input without feedback, no restart, a sub-rule with no
  condition beside siblings that test a case, a design of more than 10
  state rows or 14 rules. A round that builds the whole request writes
  `["nothing left out"]` as its `later`. The line that passes a design
  repeats the request, cut to about 100 characters, and the items left for
  later, and asks the report to name them.
- The prototype runs the rules at 60 ticks a second in the runtime's order:
  actions, then sub-events, Else after a sibling that did not run, Wait
  deferring the rest of the event, a restart that resets what the layout
  holds and keeps the globals. Every rule must run in some test, every
  input be done, win and lose be reached, every text the player reads be
  expected, and a restart must leave the state of a new game. A failed
  expect names the values, the rules that ran and changed them, and the
  rules that would have, with the condition that held each back.
- The input -> rule -> feedback table is held to what the player sees. A
  state row may count the instances of a type the player sees, of any frame
  or of one; the rules change it as a number, a test cannot set it, and the
  editor counts the visible instances. Each input changes a row the player
  sees, directly or through the rules that read what it changes, and some
  test expects one such row after it. A rule fired by an input that writes
  an Array cell changes a count in its own chain, since the cell is not on
  screen. Neither the win nor the lose may hold before the first input.
- The prototype plays on from the first screen without input for up to
  120 s, and a win that comes before the lose is refused with the rule that
  last set what the win reads. A game won by outlasting a timer, where the
  rules do not model the danger, says so in `won_by_waiting`: what the
  player does while it runs. The ok line repeats it, and the check refuses
  the field when the game is not won without input. The bound is a choice,
  not a measurement: six times the 20 s a test may wait, and the run takes
  milliseconds.
- Every tap is a tap on the screen: it runs the rules of every screen input
  whose region holds it, in the design's order, before the rules of the
  object it taps. An input on a point may name its region; a tap on an
  object or at an argument's position counts as outside every region. A
  rule that reads the position of a tap the prototype does not know stops
  the test, with the condition to add. A failed expect after a tap names
  the rule the tap ran as a tap on the screen.
- A test runs 1 s more after its last step, and the expects at its end are
  read again. In the prototype a restart in that second that breaks one is
  refused, with the step that started it; a change by anything else is the
  game running on. The expects that still hold are read again after the
  same second in the editor, where a trigger that fires later than the
  design's shows.
- The expressions are parsed into trees and evaluated by the script; the
  editor's tests are JavaScript generated from the same trees, with names
  checked against the state and values encoded by the script, so nothing a
  design holds runs as code. A test under Node holds the generated
  JavaScript to the prototype's values.
- `play_design.py` reads start values from the project files, a count as
  the visible instances of the first layout. `--adopt-starts` writes the
  project's start values into the design and goes on only if the prototype
  still passes. Before the tests it reads the first screen in the editor
  without input: each shown text, frame or count that holds still in the
  prototype through the first two seconds, and the win and the lose, must
  match the prototype.

## Re-evaluate when

- Most runs still deliver nothing: the steps a run may take, a stronger
  model for the design, or a refusal that names the fix where it now names
  only the fault.
- A delivered game breaks in a way its tests did not read, such as a piece
  shown in the wrong place or with the wrong frame while the count is right:
  a count over a region or a variable, not only over a frame.
- The prototype and the editor disagree on a construct: the simulator
  follows the runtime there, or the construct is refused.
- A tapped object lies inside a screen input's region, which only the
  editor run shows: the binding of a tap on an object would carry where the
  object lies.
- A game is won without input only after 120 s: the design states the
  length of its round, and the run without input lasts that long.
- A report after the build leaves out what was left for later although the
  ok line asks for it: the result of `play_design.py` repeats the list too.
- A genre needs what the expression language cannot state, such as physics
  or a behavior's motion: the design abstracts it, and a test that depends
  on it is left to the editor run.
