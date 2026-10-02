# Verifying a change by playing it

How to plan a check of what a change does in the running game: which cases
to play, how to reach each one, and how to read whether the events did what
they were written for. `scripts/preview_project.py --help` says how a plan is
written, [editor-and-preview.md](editor-and-preview.md) what the preview and
the input sent into it do, and
[reading-the-runtime.md](reading-the-runtime.md) how to read a value the
`state` step does not print. Read this before writing the plan for a change
the player triggers or sees: a drag, a merge, a jump, a hint, a sound.

A lesson about planning such a check goes here, one bullet each with its
source, in the section it belongs to; a fact about the editor or the preview
goes to `editor-and-preview.md`.

## Steps

1. **Name the cases before the plan.** Each change has a case it is
   written for, a neighbouring case where it must not fire, the case the
   game falls back to there, and a follow-through: the player does what the
   game asked and the state that asked for it clears. Play every one; a
   plan that plays only the first passes a condition that fires
   everywhere. [observed in a game project, r504 preview, 2026-10-02: an
   idle hint to deploy a piece was played with the slot's column holding an
   enemy, without one, where it had to fall back to a merge hint, and
   followed through by dragging as the hand showed]
2. **Reach each scene the way the game does.** Play to it when that is
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
3. **Meet the conditions that start the flow.** Read the trigger chain of
   the event under test back to its first trigger: a countdown that a touch
   starts, an audio clock that stands still until the first input, a
   tutorial or a save flag. Each run starts from a first launch, so a game
   with a first-launch tutorial needs it finished or skipped before the
   scene. [observed in a game project, r504 preview, 2026-10-02: the idle
   timer of a hint starts in *On any touch start*, and a plan that set the
   scene up through `runtime` alone waited 15 seconds for a hint that never
   came, until a tap on an empty spot came first]
4. **Read the result where the player sees it.** A variable that says the
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
5. **Keep what the run logs apart from what the change did.** A run that
   logs no error and never reached the event says nothing; a run that logs
   an error after a direct write may say nothing about the events either.
   Report which cases were played, the result read in each, and any value
   the plan forced. What is judged by eye, a motion's feel or timing, goes
   to the user as the recording's review page, `NN-NAME.html`: they play it
   frame by frame, select a part that looks wrong and copy it back as a
   task. [design: docs/decisions/preview-player.md, the bullets on
   `record` and the review page]

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
  key or a function the plan calls.
  [manual: plugin-reference/advanced-random.md "Seed", "Replace system
  random", "Update seed"]
- Sound: the preview runs muted, and a sound is checked by recording it in
  the page, as [editor-and-preview.md](editor-and-preview.md) describes. The
  audio clock does not run until the first release, click or key, so a plan
  that checks music sends one first. [Construct3-RAG
  `prompts/pitfalls/audio.md`, the bullet on the audio clock]
- Layouts: the preview starts on the layout open in the editor, not the
  project's first layout. [editor-and-preview.md, the first bullet]
