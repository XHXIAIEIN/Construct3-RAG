# Numbers and Rules from Other Agent Frameworks, Measured Here First

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

Agent frameworks for other engines give a generated game numbers and
rules with no source. The numbers include a player's height by genre, a
cap on the HUD's share of the screen, popup timings, idle-motion periods,
a coyote time and a jump buffer. Two of their skills set the idle period
four times apart. The rules include preloading the images of objects that
events create, a refresh after files change on disk, a cap on a design's
size, a question about the notch and fixing the first runtime error first.

A number or rule that enters the generator template, a check or a tool's
output becomes what every generated game does. So each one is measured
here first, on the official examples or in the editor.

`python scripts/measure_examples.py <measure> --examples <example-projects>`
prints the current numbers for the examples. Its rows, with the example
names, are in `.local/docs/evidence/borrowed-numbers/`, beside the probes
of the editor's experiments.

## Evidence

### Player height

`measure_examples.py actors` takes the player of each 2D example. The
player is the Sprite named for a player or hero, else the one Scroll To
follows, else one with a movement behavior. When the player is an
invisible box, its art is the visible child pinned to it or the visible
object named after it. The height is the art's opaque pixels, scaled to
the instance, as a share of the viewport's height.

| The player moves by | Least | Quartiles | Most |
|---------------------|-------|-----------|------|
| Platform | 5% | 8%, 8%, 12% | 24% |
| 8 Direction | 4% | 8%, 11%, 18% | 21% |
| Tile movement | 1% | 9%, 11%, 13% | 19% |

Most Platform players are one studio's pixel art at 320×180, so their
median repeats one scale. By the examples' tags, arcade players span 1% to
50% of the height. Half the shooters show one top-down character, shared
between examples, which sets their median of 18%.

The template's `TOUCH`, the 48 dp a finger needs, is 15% of the shorter
side at 1920×1080. It sizes what is tapped. A player moved by keys is
smaller than that in most examples.

### HUD share

`measure_examples.py hud` reads the play layouts of the game examples:
the visible instances of their layers at parallax 0. It leaves out
full-screen overlays, objects named for a moment, such as a tutorial, a
game-over message or a popup, and Texts longer than 30 characters, which
are instructions.

| Share | Quartiles | Most |
|-------|-----------|------|
| Of the screen, covered by the HUD's objects together, a Text by its whole box | 3%, 4%, 22% | 99% |
| Of the height, taken by the strips along the top and bottom edges that hold them | 9%, 13%, 58% | 100% |

The upper quarter are games whose interface is a frame around the play
area, an inventory bar or a dashboard. A game whose HUD shares a
scrolling layer is not counted. The template's stand-in game covers 2% of
its screen, in strips of 18% of its height.

### Popups and idle motion

`measure_examples.py popups` reads every Tween action on a popup's
objects. A popup's object is on a layer at parallax 0, and its name or its
layer's name says pause, menu, shop, result, game over or the like.
Nearly all of these tweens fade the opacity with `easeinoutsine`. A few
slide a menu in by X or Y, and none scales a popup. Opening and closing
both take 0.25 to 1 s in the middle half, 0.5 s at the median. The HUD's
motion measured in `prompts/references/new-project.md` agrees: fades, sine
eases, 0.5 to 1 s.

`measure_examples.py sine` reads the Sine behavior on the first instance
of each object type, enabled and with the sine wave:

| Movement | Period, quartiles | Magnitude, quartiles |
|----------|-------------------|----------------------|
| Vertical | 1, 3, 4 s | 3%, 6%, 15% of the object's height |
| Angle | 2, 2, 4 s | 5°, 10°, 30° |
| Size | 0.5, 2, 4 s | 3%, 8%, 13% of the longer side |
| Opacity | 0.5, 1, 1 s | 5, 15, 25 |

Vertical Sine also moves enemies, platforms and water. A pickup, an
object named as a coin, gem, key, power-up or the like, bobs or pulses
while it waits to be collected. Its period is 1 to 2 s, 1.5 s at the
median. Its magnitude is 5% to 15% of its height, 12.5% at the median.
The two borrowed idle periods are 1.4 s and 0.33 s. The examples' pickups
agree with the slower one, and none bobs at 0.33 s.

### Coyote time and a jump buffer

The borrowed windows are about 0.1 s each. A probe put them into a copy
of the platformer template example: the Timer behavior on the player, and
`CoyoteTime` and `BufferTime` as globals of 0.1, as in the recipe of
`prompts/references/feel.md`. `preview_project.py` played the probe in the
stable editor's preview at the display's 144 Hz. It played it again at
60 Hz with the browser's GPU off, which makes a headless page draw every
16.7 ms. A script in the page logged every tick: when the jump key went
down, the fall or the landing, and the vertical speed.

| Trial | 144 Hz | 60 Hz |
|-------|--------|-------|
| Jump pressed after walking off a ledge | jumped up to 97 ms, not from 118 ms | jumped up to 100 ms, not from 133 ms |
| Jump pressed before landing | jumped on landing up to 90 ms, not from 111 ms | up to 83 ms, not from 100 ms |
| Jump pressed again 7 to 67 ms after the top of a jump | no jump | no jump |

So both windows hold at either rate to within one tick, because a Timer
counts seconds, not ticks. With *Simulate control* Jump in place of
*Set vector Y* for the coyote jump, no press jumped. The manual gives
*Double jump* as the one jump in the air (`behavior-reference/platform.md`),
and the probe showed no other.

### Images of objects created by events

The borrowed rule preloads the images of every object that events create.
The manual says that a layout loads the images of the objects placed in
it. An object created only by events loads its images when it is created,
while the game keeps running (`tips-and-guides/memory-usage.md`). The
template keeps its coin in a layout that never runs and creates it on the
game's layout, which is that case.

A probe added Sprites of noise to the template's stand-in game. A script
created them 1.5 s into a fresh preview and read at every tick whether
the first frame had a texture:

| Picture | Not loaded before | Placed in the layout, or *Load object images* at the start |
|---------|-------------------|-------------------------------------------------------------|
| 160×160, the template's coin | texture by the next tick | texture at once |
| 1920×1080, a scene picture | no texture for 62 to 100 ms, 6 to 10 ticks | texture at once |

No tick took longer than usual, at 60 Hz or at 144 Hz, so the game does
not pause; a large picture shows late. The preview serves the pictures
from the editor's memory. An exported game downloads them, so it shows
them later still.

### An editor open while files change

The borrowed rule asks for an explicit refresh after files change on
disk. A probe opened the template's stand-in game in the stable editor.
It saved the game as a project folder into the page's origin-private file
system, through a stubbed folder picker. A script then changed files in
that folder as another tool would: a comment added to the event sheet, an
instance moved 7 px in the layout, a new text file. The editor showed no
dialog and kept the files as it had loaded them. Then it saved:

| Before the save | Written by the save | The outside changes |
|-----------------|---------------------|---------------------|
| No edit in the editor | one file of the editor's own interface state | all kept |
| Every instance of the layout nudged 1 px in the editor | that layout and interface state | the sheet's and the new file kept; the layout's lost, the instance at the editor's position plus 1 px |

So a save writes each file edited in the editor, from the copy the editor
loaded, over any change made to that file on disk. A folder on disk is
reached through the same kind of folder handle; that case was not run.

### Design size and build success

The borrowed cap keeps a first version to about seven items. Of the
skill's eval cases, one writes a design, `design-a-catch-game`. Its six
runs wrote five to seven rules each, and all six passed `check_design.py`.
The case ends at the design, so no run built a game from it. The sample
has neither failures nor a spread of sizes, so it relates nothing.

### Safe area and notch

The borrowed rule asks about edge controls under a notch. The project
property *Viewport fit* decides where they go. *Auto*, the property's
default, adds borders so that the whole viewport is visible on a screen
with a notch. *Cover* draws under the notch and the rounded corners
(manual: `project-primitives/projects.md`). PlatformInfo's
`SafeAreaInsetTop` and the other three insets give the hidden edges in
CSS pixels.

The template's stand-in game was made portrait, 1080×1920. It was
previewed at 430×932 with a safe-area inset of 59 CSS px at the top, which
the browser emulates as a phone with a notch reports it. The preview
ignores *Viewport fit*: with *Auto* and with *Cover*, the canvas filled
the window and the page's meta viewport named neither. The anchored HUD
lay 13 to 78 px from the top, under the 59 px band. So a game set to
*Cover* puts its top HUD under a notch, and a preview cannot show the
borders that *Auto* adds on the phone.

### The first runtime error

The borrowed rule is to fix the first runtime error first. A probe gave
the template's stand-in game three script actions. The first, in *On
start of layout*, fails once, before it sets up a list. The second, in
*Every tick*, uses the list and so fails every tick. The third fails
separately every 2 seconds. A 5-second preview logged over 600 errors:
the first action's once, the second's at every tick, the third's twice.
`open_in_editor.py` printed a `runtime:` line per error until its output
limit. The third action's errors came 289th and 578th, so neither was
printed. With the first action fixed, only the third action's errors were
left.

So the first error can cause a flood that hides the other errors. The
scripts print the errors in the order they came, so the first error is
the first line.

## Options

1. **Take each borrowed number or rule as it is.** Every generated game
   would carry numbers that were never checked against Construct.
2. **Leave them all out.** A generated game would lack the ones that hold.
3. **Measure each one, and add a rule only where the measurement supports
   it.** Chosen.

## Decision

- Player height: no default and no warning. Within one way of moving, the
  size varies about fivefold, and one studio's scale fills most of the
  sample, so a single default would copy that studio. The borrowed height
  for a platformer, 8%, agrees with the examples' median; the others have
  no counterpart here.
- HUD share: no cap. A borrowed cap of 20 to 25% of the screen falls
  inside the examples' upper quarter, games built around their interface,
  and would flag them. A cap guards against a HUD that crowds the
  playfield. That shows in the playfield's share, and `filled()` warns on
  it under `PLAYFIELD_MIN` (`greybox-blockout.md`).
- Popups: no `popup()` helper with a scale pop. A popup fades, as the HUD's
  motion in `new-project.md` says for menus.
- Idle motion: a row in `prompts/references/feel.md` for a pickup: Sine
  *Vertical* with a period of 1 to 2 s and 5% to 15% of its height, or
  Sine *Size* for a pulse. The template's `SINE` block keeps its values,
  because it is the shape of the properties, not a motion the stand-in
  game shows.
- Coyote time and a jump buffer: a row in `feel.md` with the measured
  recipe, naming `CoyoteTime` and `BufferTime` as the variables to tune.
  The jump in the air goes into the Input pitfalls, because it changes
  which action an agent writes.
- Images of objects created by events: a pitfall under Creating objects,
  *Load object images* in *On start of layout* for a large picture. No
  checker warning: the template's small sprites show by the next tick, its
  scene pictures are placed in their layouts, and only a large picture
  created by events shows late.
- An editor open while files change: a bullet in the skill's "Before the
  first command" says to ask the user to save and close the project before
  its files change, and to open it again after, because the loss is silent.
  `edit_sheet.py`'s note after a write says to close the project without
  saving and open it again, since a save then would write over the change.
- Design size: no warning in `check_design.py`. A threshold needs runs that
  build games from designs of different sizes, some of which fail.
- Safe area: no question in `review_look.py`, whose screenshots come from
  the preview and cannot show a notch. `check_look.py` warns,
  `screen.safe-area`, when `viewportFit` is `cover` and no event expression
  or script reads the insets; the look manifest holds the rule. It is a
  warning, because the editor accepts the setting and a game may move its
  HUD by other means.
- The first runtime error: `open_in_editor.py`, `preview_project.py` and
  `review_look.py` print each distinct error once, in the order it first
  came, with how many times it came. The summary line keeps the total. The
  `next:` line after a preview with errors says to fix the first error
  first, because the errors after it can follow from it.

## Re-evaluate when

- A generated game's player falls outside the examples' range and reads
  wrong in a preview, or a template for one genre is added: it takes that
  genre's median.
- A generated game's HUD covers its playfield while `filled()` passes it.
- A preview at another rate, or a Construct release, moves a jump window
  by more than a tick: rerun the probe, whose plan and log reader are in
  `.local/docs/evidence/borrowed-numbers/coyote/`.
- An exported game shows a flicker or a blank sprite on creation, or a
  generated game creates large pictures by events: measure the export,
  then decide on a warning.
- The editor reloads a folder project from disk, or warns of a file
  changed there: the skill's bullet and the note change with it.
- An eval case builds a game from its design in a preview: count the
  design's rules against the build's outcome over its runs.
- The preview applies *Viewport fit*, or a phone shows the template's HUD
  under its notch with *Auto*: then a screenshot question can ask it.
- Runs fix a later error before the first, or errors that differ only in
  a value print as separate lines in a flood: group by the error without
  its values.
