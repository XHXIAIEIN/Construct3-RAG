# A New Game Is a Checked Design, Played as a Prototype Before It Is Built

Date: 2026-10-04

## Problem

A small model that makes a game from one sentence ("make gomoku") writes
events that open, preview without errors and still play wrong: no win
detected, the winner's name swapped, a restart on the winning tap. The
checker reads files and the preview reports runtime errors; neither knows
the game's rules, so neither sees these. A recipe per genre in the prompt
fixed one genre at a time and steered the model only partly.

Task: for any genre, the model states what the game does in a form fixed
code can check and run, the rules are tried before any event is written,
and the built game is held to the same tests.

## Evidence

A chat bot on a small hosted model, thinking off, made games from one
sentence through the skill's generator path; a judge that did not read the
design played each game it sent. With a gomoku recipe in the prompt and no
design step, 6 of 12 runs were playable, 3 shipped a logic bug and 3 sent
nothing.

| With this design step | Runs | Playable | Logic bug sent | Nothing sent |
|-----------------------|------|----------|----------------|--------------|
| Gomoku | 9 | 4 | 1 | 4 |
| A catch game | 11 | 1 | 1 | 9 |

- The prototype refused a design for a failed test in 15 of the 20 runs, and
  the editor run refused a built game in 15; those games were fixed or not
  sent. Each logic bug sent was one the tests did not read: a pick that
  changed every piece where the test read the Array, and a game over at
  launch that fixtures stepped past.
- 9 of the 13 runs that sent nothing ran out of steps while resending a
  refused design or spec. A design that names its fault in values ("over = 0
  is false (over = 1)") was fixed in one or two calls; one whose fix needs a
  new idea (InARow in place of counting neighbours) was resent until the
  steps ran out.
- The recipe's games all waited before a restart and used a 15 x 15 board,
  which the first judge assumed. The second judge fits any board and any
  state names; the table counts by it.

## Options

1. A kit per genre: board games, falling objects, snakes, each with its
   events written by fixed code. Correct where a kit exists, nothing
   elsewhere, and every new genre is new code.
2. A stronger model for the events. Not every agent has one, and the
   failures above are rules the model never stated, not syntax.
3. Acceptance tests the model writes, played in the editor only. Each
   failure costs a build and an editor run, about 20 seconds, and names an
   event the model then has to read and debug.
4. The design as data, with the rules in a small expression language that
   fixed code runs as a prototype, and the same tests played in the editor
   after the build.

## Decision

Option 4: `scripts/check_design.py`, `scripts/play_design.py`,
`scripts/game_model.py`, and `references/designing-a-game.md`.

- The design holds the core loop, the official example it was read
  against, the screen's regions, the state table, the inputs with how each
  is done in the game, the rules (trigger, conditions, effects, sub-rules,
  Else), win and lose, and the tests. Each rule becomes one event.
- The check refuses a gap by its path: a state no rule writes or nothing
  reads, a fact stored twice, an input without feedback, no restart, a
  design of more than 10 state rows or 14 rules.
- The prototype runs the rules at 60 ticks a second in the runtime's
  order: actions, then sub-events, Else after a sibling that did not run,
  Wait deferring the rest of the event, a restart that resets what the
  layout holds and keeps the globals. Every rule must run in some test,
  every input be done, win and lose be reached, every text the player
  reads be expected, and a restart must leave the state of a new game. A
  failed expect names the values, and the rule that would have changed
  them with the condition that held it back: that sentence is what a small
  model fixed its design from.
- The expressions are parsed into trees and evaluated by the script; the
  editor's tests are JavaScript generated from the same trees, with names
  checked against the state and values encoded by the script, so nothing a
  design holds runs as code. A test under Node holds the generated
  JavaScript to the prototype's values.
- `play_design.py` reads the start values from the project files rather
  than the running game, where a falling object has moved before it is
  read. Where an instance lands is the layout grid's to say, so
  `--adopt-starts` writes the project's start values into the design and
  goes on only if the prototype still passes.

With a small model the design step trades logic bugs for games not sent; it
did not raise the share of playable games. What it adds is that a game that
is sent passed tests the model stated, and that a failure names its cause.

## Re-evaluate when

- More than half the runs still send nothing: the steps a run may take, a
  stronger model for the design, or a refusal that names the fix where it
  now names only the fault.
- A sent game breaks in a way its tests did not read, such as every
  instance changed by one pick: a state the tests can read for it.

- The prototype and the editor disagree on a construct: the simulator
  follows the runtime there, or the construct is refused.
- A genre needs what the expression language cannot state, such as
  physics or a behavior's motion: the design abstracts it, and a test that
  depends on it is left to the editor run.
- A model writes correct events without the design step at the same rate.
