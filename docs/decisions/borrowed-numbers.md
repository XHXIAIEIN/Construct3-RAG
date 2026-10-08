# Numbers from Other Agent Frameworks, Measured Here First

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

Agent frameworks for other engines give a generated game fixed numbers
with no source: a player's height by genre, a cap on the HUD's share of
the screen, popup timings, idle-motion periods that two of them set four
times apart, a coyote time and a jump buffer. A number that enters the
generator template or a check becomes what every generated game does.
So each one is measured here first, on the official examples or in the
editor, and a rule is added only where the measurement supports one.

`python scripts/measure_examples.py <measure> --examples <example-projects>`
prints the current numbers for the examples. Its rows, with the example
names, are in `.local/docs/evidence/w11-measurements/`.

## Evidence

### Player height

`measure_examples.py actors` takes the player of each 2D example: the
Sprite named for a player or hero, else the one Scroll To follows, else
one with a movement behavior. When the player is an invisible box, its
art is the visible child pinned to it or the visible object named after
it. The height is the art's opaque pixels, scaled to the instance, as a
share of the viewport's height.

| The player moves by | Least | Quartiles | Most |
|---------------------|-------|-----------|------|
| Platform | 5% | 8%, 8%, 12% | 24% |
| 8 Direction | 4% | 8%, 11%, 18% | 21% |
| Tile movement | 1% | 9%, 11%, 13% | 19% |

Most Platform players are one studio's pixel art at 320×180, so the
median repeats one scale. By the examples' tags, arcade players span 1% to
50% of the height. Half the shooters show one top-down character shared
between examples, which sets their median of 18%.

The template's `TOUCH`, the 48 dp a finger needs, is 15% of the shorter
side at 1920×1080. It sizes what is tapped, and a player moved by keys is
smaller than that in most examples.

### HUD share

`measure_examples.py hud` reads the play layouts of the game examples:
the visible instances of their layers at parallax 0. It leaves out
full-screen overlays, objects named for a moment (a tutorial, a game-over
message, a popup) and Texts longer than 30 characters, which are
instructions. Two shares are measured:

| Share | Quartiles | Most |
|-------|-----------|------|
| Of the screen, covered by the HUD's objects together, a Text by its whole box | 3%, 4%, 22% | 99% |
| Of the height, taken by the strips along the top and bottom edges that hold them | 9%, 13%, 58% | 100% |

The upper quarter are games whose interface is a frame around the play
area, an inventory bar or a dashboard. A game whose HUD shares a scrolling
layer is not counted. The template's stand-in game covers 2% of its
screen, in strips of 18% of its height.

### Popups and idle motion

`measure_examples.py popups` reads every Tween action on a popup's
objects: objects of a layer at parallax 0 whose own name or layer's name
says pause, menu, shop, result, game over or the like. Nearly all fade the
opacity with `easeinoutsine`; a few slide a menu in by X or Y, and none
scales a popup. Opening and closing both take 0.25 to 1 s in the middle
half, 0.5 s at the median. The HUD's motion measured in
`prompts/references/new-project.md` agrees: fades, sine eases, 0.5 to 1 s.

`measure_examples.py sine` reads the Sine behavior on the first instance
of each object type, enabled and with the sine wave:

| Movement | Period, quartiles | Magnitude, quartiles |
|----------|-------------------|----------------------|
| Vertical | 1, 3, 4 s | 3%, 6%, 15% of the object's height |
| Angle | 2, 2, 4 s | 5°, 10°, 30° |
| Size | 0.5, 2, 4 s | 3%, 8%, 13% of the longer side |
| Opacity | 0.5, 1, 1 s | 5, 15, 25 |

Vertical Sine also moves enemies, platforms and water. An object that
waits to be collected, named as a coin, gem, key, power-up or the like,
bobs or pulses with a period of 1 to 2 s, 1.5 s at the median, and a
magnitude of 5% to 15% of its height, 12.5% at the median. The two
borrowed idle periods, 0.7 Hz and 3 Hz, that is 1.4 s and 0.33 s, differ
fourfold. The examples' pickups agree with the slower one, and none bobs
at 3 Hz.

### Coyote time and a jump buffer

The borrowed windows are about 0.1 s each. They were built into a copy of
the platformer template example, with the Timer behavior on the player and
`CoyoteTime` and `BufferTime` as globals of 0.1, the recipe of
`prompts/references/feel.md`. `preview_project.py` played them in the
stable editor's preview at the display's 144 Hz, and at 60 Hz with the
browser's GPU off, which makes a headless page draw every 16.7 ms. A
script in the page logged every tick: when the jump key went down, the
fall or the landing, and the vertical speed.

| Trial | 144 Hz | 60 Hz |
|-------|--------|-------|
| Jump pressed after walking off a ledge | jumped up to 97 ms, not from 118 ms | jumped up to 100 ms, not from 133 ms |
| Jump pressed before landing | jumped on landing up to 90 ms, not from 111 ms | up to 83 ms, not from 100 ms |
| Jump pressed again 7 to 67 ms after the top of a jump | no jump | no jump |

So both windows hold at either rate to within one tick, because a Timer
counts seconds, not ticks. With *Simulate control* Jump in place of
*Set vector Y* for the coyote jump, no press jumped: Platform jumps from
the floor only, unless *Double jump* is on (manual:
`behavior-reference/platform.md`).

### Images of objects created by events

The borrowed rule preloads the images of every object that events create.
The manual says that a layout loads the images of the objects placed in
it, and that an object created only by events loads its images when it is
created, while the game keeps running (`tips-and-guides/memory-usage.md`).
The template keeps its coin in a layout that never runs and creates it on
the game's layout, which is that case.

A probe added Sprites of noise to the template's stand-in game and created
them by a script, 1.5 s into a fresh preview. A script read every tick
whether the first frame had a texture:

| Picture | Not loaded before | Placed in the layout, or *Load object images* at the start |
|---------|-------------------|-------------------------------------------------------------|
| 160×160, the template's coin | texture by the next tick | texture at once |
| 1920×1080, a scene picture | no texture for 62 to 100 ms, 6 to 10 ticks | texture at once |

No tick took longer than usual, at 60 Hz or at 144 Hz, so the game does not
pause; a large picture shows late. The preview serves the pictures from
the editor's memory, so an exported game that downloads them shows them
later still.

### An editor open while files change

The borrowed rule asks for an explicit refresh after files change on
disk. A probe opened the template's stand-in game in the stable editor
and saved it as a project folder into the page's origin-private file
system, through a stubbed folder picker. A script then changed files in
that folder as another tool would: a comment added to the event sheet, an
instance moved 7 px in the layout, a new text file. The editor showed no
dialog and kept the files as it had loaded them. Then it saved:

| Before the save | Written by the save | The outside changes |
|-----------------|---------------------|---------------------|
| No edit in the editor | one file of the editor's own interface state | all kept |
| Every instance of the layout nudged 1 px in the editor | that layout and interface state | the sheet's and the new file kept; the layout's lost, the instance at the editor's position plus 1 px |

So a save writes each file edited in the editor, from the copy the editor
loaded, over any change made to it on disk. A folder on disk is reached
through the same kind of folder handle; that case was not run.

### Design size and build success

The borrowed cap keeps a first version to about seven items. Of the
skill's eval cases, one writes a design, `design-a-catch-game`. Its six
runs wrote five to seven rules each, all six passed `check_design.py`,
and the case ends at the design, so no run built a game from it. The
sample has neither failures nor a spread of sizes, so it relates nothing.

### Safe area and notch

The borrowed rule asks about edge controls under a notch. The project
property *Viewport fit* decides it: *Auto*, which a new project has, adds
borders so that the whole viewport is visible on a screen with a notch,
and *Cover* draws under the notch and the rounded corners (manual:
`project-primitives/projects.md`). PlatformInfo's `SafeAreaInsetTop` and
the other three insets give the hidden edges in CSS pixels.

The template's stand-in game was made portrait, 1080×1920, and previewed
at 430×932 with a safe-area inset of 59 CSS px at the top, which the
browser emulates as a phone with a notch reports it. The preview ignores
*Viewport fit*: with *Auto* and with *Cover* the canvas filled the window
and the page's meta viewport named neither. The anchored HUD lay 13 to
78 px from the top, under the 59 px band. So a game set to *Cover* puts
its top HUD under a notch, and a preview cannot show the borders that
*Auto* adds on the phone.

### The first runtime error

The borrowed rule is to fix the first runtime error first. A probe gave
the template's stand-in game three script actions: one in *On start of
layout* that fails once, before it sets up a list; one in *Every tick*
that uses the list and so fails every tick; and a separate failure every
2 seconds. A 5-second preview logged over 600 errors: the setup's once,
the one that follows from it at every tick, the separate one twice.
`open_in_editor.py` printed a `runtime:` line per error until its output
limit, so the separate failure, logged at the 289th and 578th place, was
not printed. With the setup fixed, only the separate failure was left.

So the first error can be the cause of a flood that hides the others.
The scripts' order already puts the first error first.

## Decision

- Player height: no default and no warning. Within one way of moving,
  the size varies about fivefold, and one studio's scale fills most of the
  sample, so a single default would copy that studio. The borrowed height
  for a platformer, 8%, agrees with the examples' median; the others have
  no counterpart here.
- HUD share: no cap. A borrowed cap of 20 to 25% of the screen falls
  inside the examples' upper quarter, games built around their interface,
  and would flag them. What a cap guards against, a HUD that crowds the
  playfield, shows in the playfield's share, and `filled()` warns on that
  under `PLAYFIELD_MIN` (`greybox-blockout.md`).
- Popups: no `popup()` helper with a scale pop. A popup fades, as the
  HUD's motion in `new-project.md` already says for menus.
- Idle motion: a row in `prompts/references/feel.md` for an object that
  waits to be collected, Sine *Vertical* with a period of 1 to 2 s and a
  tenth of its height, or Sine *Size* for a pulse. The template's `SINE`
  block keeps its values, because it is the shape of the properties, not
  a motion the stand-in game shows.
- Coyote time and a jump buffer: a row in `feel.md` with the measured
  recipe, naming `CoyoteTime` and `BufferTime` as the variables to tune.
  The in-air jump goes into the Input pitfalls, because it changes which
  action an agent writes.
- Images of objects created by events: a pitfall under Creating objects,
  *Load object images* in *On start of layout* for a large picture. No
  checker warning: the template's small sprites show by the next tick, its
  scene pictures are placed in their layouts, and only a large picture
  created by events shows late.
- An editor open while files change: a bullet in the skill's "Before the
  first command" says to ask the user to close the project without saving
  before the files change, and to open it again after, because the loss
  is silent. `edit_sheet.py`'s note after a write states the same
  behaviour.
- Design size: no warning in `check_design.py`. A threshold needs runs
  that build games from designs of different sizes, some of which fail.
- Safe area: no question in `review_look.py`, whose screenshots come from
  the preview and cannot show a notch. `check_look.py` warns,
  `screen.safe-area`, when `viewportFit` is `cover` and no event
  expression or script reads the insets; the look manifest holds the
  rule. It is a warning, because the editor accepts the setting and a game
  may move its HUD by other means.
- The first runtime error: `open_in_editor.py`, `preview_project.py` and
  `review_look.py` print each distinct error once, in the order it first
  came, with how many times it came, and the total stays in the summary
  line. The `next:` line after a preview with errors says to fix the first
  one first, since the errors after it can follow from it.

## Re-evaluate when

- A generated game's player falls outside the examples' range and reads
  wrong in a preview, or a template for one genre is added: it takes that
  genre's median.
- A generated game's HUD covers its playfield while `filled()` passes it.
- A preview at another rate, or a Construct release, moves a jump window
  by more than a tick: rerun the probe, whose plan and log reader are in
  `.local/docs/evidence/w11-measurements/coyote/`.
- An exported game shows a flicker or a blank sprite on creation, or a
  generated game creates large pictures by events: measure the export,
  then decide on a warning.
- The editor reloads a folder project from disk, or warns of a file
  changed there: the skill's bullet and the note change with it.
- An eval case builds a game from its design in a preview: count the
  design's rules against the build's outcome over its runs.
- The preview applies *Viewport fit*, or a phone shows the template's HUD
  under its notch with *Auto*: then a screenshot question can ask it.
- Runs fix a later error before the first, or two errors that differ only
  in a value print as separate lines in a flood: group by the error
  without its values.
