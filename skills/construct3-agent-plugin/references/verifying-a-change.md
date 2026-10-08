# Verifying a change by playing it

How to plan a check of what a change does in the running game: which cases
to play, how to reach each one, and how to read whether the events did what
they were written for. `scripts/preview_project.py --help` says how a plan is
written, [editor-and-preview.md](editor-and-preview.md) what the preview and
the input sent into it do, and
[reading-the-runtime.md](reading-the-runtime.md) how to read a value the
`state` step does not print. Read this before writing the plan for a change
the player triggers or sees: a drag, a merge, a jump, a hint, a sound.

A lesson about planning such a check goes into the step or row it
sharpens: rewrite that rule so it covers the lesson, and keep one source
per step, the one that shows the rule most plainly. A lesson no step covers
becomes a step with its source. The file is read for every kind of game, so
a source from one game shows the rule and does not narrow it; a list of one
game's cases under a step would be copied into games it does not fit. A fact
about the editor or the preview goes to `editor-and-preview.md`.

## Steps

1. **Name the cases before the plan.** A change that adds or moves a
   condition has a case it is written for, a neighbouring case where it
   must not fire, the case the game falls back to there, and a
   follow-through: the player does what the game asked and the state that
   asked for it clears. Play every one; a plan that plays only the first
   passes a condition that fires everywhere. A change with no condition of
   its own, a colour, a size, a duration, a volume, has one case: reach the
   scene where it shows and read it as step 5 says. [observed in a game project, r504 preview, 2026-10-02: an
   idle hint to deploy a piece was played with the slot's column holding an
   enemy, without one, where it had to fall back to a merge hint, and
   followed through by dragging as the hand showed]
2. **For a bug, see the plan fail before the fix.** Write the report in
   four parts: given, the scene and the state the game is in; doing, the
   input or the time that passes; produces, what the game does now;
   instead of, what it should do. The plan reaches the given, does the
   doing and reads the produces where the player sees it. Play it on the
   project before any event changes, and see it fail at that read for the
   reason the report gives. A plan that passes there, or fails at an
   earlier step, has not reached the bug, and a fix played against it shows
   nothing: change the plan until it fails as reported. Then change the
   events and play the same plan until it passes. [design:
   docs/decisions/preview-player.md, the bullet on a bug's plan]
3. **Reach each scene the way the game does.** Play to it when that is
   short; otherwise call the game's own functions with
   `runtime.callFunction`, which run the events that keep related values in
   step. Write a value directly only when no event reaches it, and then
   write every value the events tie to it as well: a value written alone
   lets the game's own expressions compute what play never produces, and
   the runtime errors that follow are the plan's. Rerun the same steps
   without the write before blaming the events. [observed in a game
   project, r504 preview, 2026-10-02: pieces made with the game's
   `createBase` behaved as bought ones; an enemy's hp set to 10^6 through a
   JSON instance's `setJsonDataCopy`, above the stage total the events add
   up as enemies spawn, drove a progress ratio near -20000 and a low-pass
   frequency computed from it to 0, logging a RangeError per call that the
   same steps without the write did not]
4. **Meet the conditions that start the flow.** Read the trigger chain of
   the event under test back to its first trigger: a countdown that a touch
   starts, an audio clock that stands still until the first input, a
   tutorial or a save flag. Each run starts from a first launch, so a game
   with a first-launch tutorial needs it finished or skipped before the
   scene. [observed in a game project, r504 preview, 2026-10-02: the idle
   timer of a hint starts in *On any touch start*, and a plan that set the
   scene up through `runtime` alone waited 15 seconds for a hint that never
   came, until a tap on an empty spot came first]
5. **Read the result where the player sees it.** A variable that says the
   flow ran is not the flow: read what is on screen, positions, opacity,
   the layer shown, and for anything that moves, read it over time. A
   tween caught in one screenshot shows a point on its way. Put a `record`
   step around the motion with the values to follow in `watch`: they are
   read with every frame, the run prints their changes, and
   `NN-NAME/timeline.json` puts frames, steps and values on one clock, so
   where a motion starts, rests and ends is read from them. A `js` step
   that samples one value in a loop does the same for a value read once.
   Wait with `until` on the result, not a fixed
   `wait`, so a slow run does not fail and a fast one does not hide a
   second firing. [observed in a game project, r504 preview, 2026-10-02:
   a guide hand that fades in, presses and drags was read as "from bench
   slot 3 to battle slot 0" from the first two samples less than 0.5 px
   apart and the last sample after 1.5 s]
6. **Turn a word of feel into a number.** Floaty, slow, sluggish or heavy
   names no value to change. Name the variable behind the word: a jump's
   gravity and strength, a tween's duration and ease, a speed, a delay.
   Read its current value in the project. Then measure what the player
   feels in a `record` step with that value in `watch`: the time from the
   press to the top of a jump, how long a tween takes to rest, how far a
   dragged piece lags. Write the target in the same measure, from the row
   for the effect in `Construct3-RAG/prompts/references/feel.md` where
   there is one, otherwise from the user. The change is done when the
   recording measures the target, not when the motion looks better.
   [design: docs/decisions/preview-player.md, the bullet on a word of feel]
7. **Keep what the run logs apart from what the change did.** A run that
   logs no error and never reached the event says nothing; a run that logs
   an error after a direct write may say nothing about the events either.
   Report which cases were played, the result read in each, and any value
   the plan forced. Judge a motion's feel and timing from the recording
   first: where it starts, overshoots and rests, and how long each part
   takes, against the row for the same effect in
   `Construct3-RAG/prompts/references/feel.md` where there is one. Then
   open the recording's contact sheet, `NN-NAME-sheet.png`, with the image
   tool and judge only what the frames show, not what the events were
   meant to do. Name the three worst defects, each with its time, what the
   frame shows and the event to change; fix only those and record that
   part again. The report says what the values and the sheet show and
   which part looks off, or that neither settles it. The recording's review
   page, `NN-NAME.html`, then goes to the user for what is left to the eye: they play it frame by
   frame, select a part that looks wrong and copy it back as a task.
   [design: docs/decisions/preview-player.md, the bullets on
   `record` and the review page]

## The look of each layout

`scripts/review_look.py` checks what every layout shows, once the preview
passes. It goes to each layout with the runtime's `goToLayout`, takes a
screenshot into `.tmp/look/`, and reads the layout's instances from the
runtime. Its finding lines are measured, each naming the layout, the object
type and the UID: a text its box cuts (`text`), instances of one type on one
box (`stacked`), overlaps on the HUD and texts over texts (`overlap`), a HUD
instance the screen's edge cuts (`edge`), and a type whose kinds show one
frame (`frame`). None of them fires on the official examples. Fix every one.

What a measurement cannot judge, the script asks: one list of yes/no
questions about visible facts: cut or overlapping text, objects that
cover others, the edge of the screen, mixed drawing styles, a backdrop that
outshines what the player acts on, kinds that look alike, and decoration
repeated on every layout, and, when the project has a design, the screen
entries that `play_design.py` cannot measure. The agent that wrote the
events reads its own screenshots by what it meant them to show, so the
script also writes the screenshots and the questions into `brief.md` beside
them, for a reviewer that has not seen the project. Where you can start a
sub-agent, give it the brief as its whole task, and for each yes in its
reply name the layout and the object type at the place it describes.
Otherwise open each screenshot with the image tool, answer each question
from the picture, and name the same for each yes. A question answered from
memory of the events, not from the picture, is not answered.

A layout reached by `goToLayout` starts without what the game's flow sets up
before it, and one whose start events leave at once is printed as left for
the layout they went to. Play to such a scene with a plan of
`scripts/preview_project.py` and a `shot` step, and answer the same
questions about that screenshot. [observed in a generated card game, r495-2
preview, 2026-10-04: the combat layout, reached directly, went to the ending
at once; played to by a plan, the same checks over its instances found the
names, descriptions and costs of five cards stacked on one card, in a
screenshot the agent had reported as rendering normally]

## The design of the sheets

`scripts/review_design.py` reads the event sheets once `check_project.py`
passes, before the editor opens them. It starts no browser. Each finding
line names the event as `print_sheet.py` numbers it and says what to write
instead; fix every one. A rule is a finding only where it finds next to
nothing in the 524 official examples, every example hit read; what the
examples also write becomes a question that names its events. Measured on
2026-10-04 with `evals/measure_design.py`, over the examples, a generated
card game, a merge game and a tic-tac-toe sheet:

| Rule | Finding at | Examples | Card | Merge | Tic-tac-toe |
|------|------------|----------|------|-------|-------------|
| `conditions` | 12 or more conditions besides the trigger; the examples' most is 11 | 0 | 0 | 1 | 0 |
| `guard` | the same 3 or more conditions of objects in 3 or more events of a sheet | 5 in 5 projects | 0 | 5 | 0 |
| `trigger` | 2 or more sibling events with one trigger, told apart by globals | 2 in 2 projects | 0 | 0 | 1 |
| `twice` | one action list writes a value into an Array cell indexed by an object's expressions and into that object's instance variable | 0 | 0 | 0 | 2 |
| `global` | a scratch global (`TMP`, `TMPN2`); a layout's sheet declaring 10 or more globals only other sheets use | 0 | 6 | 0 | 0 |
| `uid` | an instance variable set to the UID of an instance created in the same actions, then picked back by it: a container | 0 | 3 | 0 | 0 |
| `data` | 20 or more actions of one kind with literal values: a project file | 0 | 1 | 0 | 0 |
| `restart` | On start of layout setting instances after *Pick all*, on a layout that *Restart layout* or *Go to layout* enters again | 0 | 0 | 0 | 1 |
| `expression` | 5 or more parentheses deep, with a call of 30 or more characters written twice: a function | 0 | 6 | 1 | 0 |
| `follow` | a part in the object's container or created beside it, set from the object's position once, while another event moves the object alone: a hierarchy | 2 in 1 project | 3 | 0 | 0 |

The five `guard` hits in the examples repeat 3 or 4 conditions, inverted
*Is playing* or *Is touching* tests and a pick, across sibling events of one
group; a parent event would hold them once there too. The two `trigger`
hits press Space in sibling events told apart by booleans, the shape of the
tic-tac-toe sheet. The card game's `uid` hits were replaced by a container
while it was measured.

The `follow` rule was added later and measured the same way. Its two example hits
are in ceiling-trap: the rail path is placed at the trap once and stays while the
trap stomps down it, which is the design there. The card game's three hits move the
cards in the hand layout, the aim and the play while their name, cost and text labels
stay where the cards were drawn. Spawned parts that start at an object and then move
on their own, such as projectiles, are not made with the object, and the rule leaves them.

The questions name the events of what the examples write as well: 4 to 11
conditions (231 events in 76 example projects, 71 in the merge game),
sibling events of one trigger that test more than it (5 in 4), sibling
events that differ only in their numbers and texts (53 in 27; the style
ladder of `check_project.py --style` takes 5 or more), 3 or more inverted
conditions (34 in 21), a global one function or one group reads and writes
(262 in 92), and a UID kept in an instance variable (19 in 16). A question
is answered from `print_sheet.py` for the events it names, never from
memory of the plan. Two candidates were dropped: a global that several
functions write and others read (20 in 6 examples, 15 in the merge game,
all of them game state), and 10 or more globals on a layout's sheet (45
examples; the examples keep shared globals on a sheet with no layout,
samuroof `Globals`). An event of 6 or more conditions stays a question and
is not a `--style` warning of `check_project.py`: 44 events in 24 example
projects have one.

## By kind of game

What the plan drives, what it reads and what has to be held still differ
with the input and the timing the game is built on. A game mixing several
kinds takes the rows of each.

| Kind | Drive | Read | Hold still |
|------|-------|------|------------|
| Board, merge, puzzle, cards: input on instances | `tap` and `drag` with an instance or `{js}` as the target | instance variables, which cell an instance sits in, counts; a recording for the motion of a drop or a merge | random placement: read where an instance landed instead of assuming it |
| Platformer, top-down, action: input held over time | `key` with `seconds`, `hold` | positions and behavior state against a range, `until` a position is passed; a recording watching the position for a jump's arc | the frame rate, which sets `dt` |
| Physics | as above | positions and velocities against a range | the Physics time step |
| Rhythm, music, sound | input on the beat, timed from `Audio.CurrentTime` | the sound itself, recorded in the page | the audio clock's start |
| Spawners, random levels, loot | play or `callFunction` | what spawned and where | the random seed |
| Menus, several layouts | `tap` on buttons | the current layout and layer visibility | the layout the preview starts on |

- Frame rate: a preview ticks at the display's rate, so a move that
  integrates `dt` lands at a slightly different place each run. Compare
  positions against a range, and use `until` instead of a fixed wait.
  `runtime.timeScale` slows the game for a closer look; the audio clock is
  not scaled. [editor-and-preview.md, the bullet on the display's rate;
  manual: scripting/scripting-reference/iruntime.md `timeScale`]
- Physics time step: with the default *Framerate independent* stepping the
  simulation can differ between runs; *Set stepping mode* to *Fixed* makes
  it deterministic for the check. [manual:
  behavior-reference/physics.md "Set stepping mode"]
- Random seed: an Advanced Random object with *Replace system random* and a
  fixed *Seed* makes `random()` and the randomness of behaviors repeat from
  run to run; *Update seed* changes it from an event, such as a debug
  key or a function the plan calls. Fix the seed before recording a motion
  twice to compare the two contact sheets, so the frames differ only by
  the change.
  [manual: plugin-reference/advanced-random.md "Seed", "Replace system
  random", "Update seed"]
- Sound: the preview runs muted, and a sound is checked by recording it in
  the page, as [editor-and-preview.md](editor-and-preview.md) describes. The
  audio clock does not run until the first release, click or key, so a plan
  that checks music sends one first. [Construct3-RAG
  `prompts/pitfalls/audio.md`, the bullet on the audio clock]
- Layouts: the preview starts on the layout open in the editor, not the
  project's first layout. [editor-and-preview.md, the first bullet]
