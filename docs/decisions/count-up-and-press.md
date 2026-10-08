# Count-up and Press: A Score That Counts and a Button That Presses

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

A score that counts to its new value and a button that presses under the
finger each have a trap in Construct. A count driven by *Tween (value)*
reads 0 once the tween ends (`prompts/pitfalls/tween.md`), so a count that
keeps reading the tween ends on 0. A press needs two events, the touch's
start and its end. A label linked to its button by position only keeps its
full size while the button squashes.

Task: a helper for each in the generator template, with numbers measured
on the official examples.

## Evidence

### What the official examples do

From the event sheets of the official examples, studio cohort
(`docs/decisions/event-sheet-design-guidance.md`, "The authoring style"):

- **Counting.** A HUD score is set at once. A result screen may count a
  number up, reading the shown number back from the text and stepping it:
  a point every 0.075 s, or steps spaced so that the whole count takes 2 s.
- **Pressing.** A button swaps to a drawn *Pressed* frame at once on the
  touch's start and back on its end. The action runs on the end, under
  *Is touching* the button, so a finger that slides off cancels. A button
  that changes size instead pops to 0.85 to 1.25 of its size in 0.075 to
  0.1 s each way, with a sine ease and no overshoot.

### What the preview showed

- A label linked to its button by position only keeps its size while the
  button squashes. A label whose link also follows width and height scales
  its letters with its box: its text width fell by the button's share.
- A count rounded down shows a gain of 1 only when the count ends, 0.5 s
  late. Rounded towards the target, the gain shows in the frame the score
  changes, and a loss counts down from the first frame.
- A gain that comes mid-count starts the next count from the number on the
  screen. Without *Stop* before the new tween, a second value tween under the
  same tag runs beside the first and the expressions read the first. The
  text held its number while the new count ran, then jumped to catch up.
- *On finished* sets the exact value, and no frame showed 0.
- *Is touching* still holds for the touch whose end triggers the event: a
  release on the button ran its action, a slide off did not.
- An overshooting ease on a 6% press rose 0.6% over the rest size, 1 px on
  a 160 px button. That is too small to see, so the press takes a sine ease.

Scripts, the probe and its recordings: `.local/docs/evidence/ui-recipes/`.

## Options

1. Leave both to the game: each run writes its own, and the count that ends
   on 0 comes back.
2. A row in `prompts/references/feel.md` alone: prose reaches the model that
   reads it, and the helper is what the template's games call.
3. Helpers in the template, the numbers from the examples, a row in
   `feel.md` for a game written without the template.

## Decision

Option 3.

- `count_up(obj, value)` stops the count that runs. It then starts a value
  tween under `count` from `int(obj.Text)`, the number on the screen, to
  `value`, over `COUNT_UP`: 0.5 s with `easeoutquad`. The examples' pace of
  0.075 s a point gives 0.075 to 0.375 s for a gain of 1 to 5 and 0.75 s
  for 10, and a fixed time suits a gain of any size.
- `counting(obj, value)` writes two events. While the count plays, the text
  is the value rounded towards `value`: `ceil` when counting up, `floor`
  when counting down. When the count ends, the text is `value`.
- The stand-in's score is set at once, as the examples' HUD scores are. A
  counted text belongs to its count: a count and any other *Set text* on it
  overwrite each other. The stand-in is the game the skill's evals ask to
  change, and their tasks write the score's text.
- `press(obj, actions)` writes two events. The touch that lands on the
  button sets its boolean `pressed` and squashes it at once. The end of a
  touch springs a pressed button back and runs `actions` under
  *Is touching*. `build_all()` gives the type `pressed` and its instances
  false.
- The press is a kind of `squash()`, `SQUASH["press"]`, which defaults to
  `SQUASH_PRESS`: 0.9 at once, back in 0.1 s with `easeoutsine`. It is at
  once because the examples swap a frame at once, and 0.1 s with a sine ease
  because their size presses use both. It is 0.9 because a held press keeps
  its size while the finger stays, so it deforms less than the examples'
  one-tap pops. `squash(obj, kind, half=...)` gives the actions through the
  hold or the tween back, for a squash that two events share.
- `button()` links its label with width and height, so a press squashes
  both. `link(..., size=True)` does it for any child.

## Re-evaluate when

- A game counts large numbers, thousands a gain, where a fixed 0.5 s blurs
  the digits; then the count's time follows the size of the gain.
- A preview shows a press the finger hides on a phone, or a pressed frame
  drawn by the art replaces the squash.
- A Construct release changes how a Text child follows its parent's size.
