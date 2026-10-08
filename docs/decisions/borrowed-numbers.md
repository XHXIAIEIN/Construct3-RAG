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

## Re-evaluate when

- A generated game's player falls outside the examples' range and reads
  wrong in a preview, or a template for one genre is added: it takes that
  genre's median.
- A generated game's HUD covers its playfield while `filled()` passes it.
- A preview at another rate, or a Construct release, moves a jump window
  by more than a tick: rerun the probe, whose plan and log reader are in
  `.local/docs/evidence/w11-measurements/coyote/`.
