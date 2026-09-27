# Greybox Blockout: The Stand-in Look and the Level's Pacing

Date: 2026-09-26
Schema: Construct 3 r495.2
Status: draft for the user's review; the outline and the shadow are
implemented, the rest is not

## Problem

A generated game has no art until the user brings some, and until then it
has to look like what it is: a blockout that can be played, read and judged,
and still looks like a designed thing rather than a debug screen. Iterations
21 to 23 (`game-look-from-design-skills.md`) settled that the template must
not draw art: `pixel_art()` held the colours, the sizes and the contrast, and
the drawing still varied from a clean heart to an octagon between runs of one
prompt. What the template draws instead was left as "a stand-in of one colour
or a plain shape", which each run filled in its own way.

Where things go in a level had the same gap. The grid, `anchor()` and
`no_overlap()` place a HUD; nothing places a level's content, so a model
lays platforms, hazards and pickups one at a time, with no measure of what
the player can jump and no order in which the level asks things of the
player.

Task: a generated game gets a blockout look that holds together and a level
laid out on grids and paced like a directed sequence, both from values of
the generator template and checks where the generator writes, so that a
small model gets them by default.

## Evidence

### The user's references

Six images the user supplied on 2026-09-26: three engine blockouts (white
or light grey geometry under a world-aligned grid, actors as flat saturated
capsules and cubes, one class of wall in an orange grid), a grey figure with
grey cubes before a grid wall, a level-design book page on judging distance
to floating blocks, and a top-down tactical map (white walls, red-and-black
hatched zones, yellow-and-black thresholds, yellow markers). Read together:

- Value carries the hierarchy. The grey figure scene has no colour at all;
  figure, props, wall and floor are four separate values.
- Colour is kept for what must be noticed wherever the eye is.
- Pattern marks areas and edges, not objects: the hatched zones and the
  striped thresholds of the map; objects are flat.
- A grid behind or under everything is a ruler: sizes and distances are
  read by counting cells.
- A floating thing needs a reference to judge where it is: a shadow, or a
  connection to something grounded.

### What the user decided in review

On 2026-09-26, over five mock-ups:

- Placeholders are three shapes: rectangle, triangle, circle.
- Deep black and white with greys between, and a few highly recognisable
  colours as accents.
- Patterns from Tiled Background tiling, such as a 2×2 grey-and-white
  checker and diagonal stripes, may add colour, as decoration that stays
  within the system.
- The backdrop is the grey-and-white checkerboard that image editors show
  for transparency.
- Soft translucent cast shadows looked wrong, and the overall contrast
  needed designing.
- On 2026-09-27, over an A/B mock-up and a grid of angles and opacities: a
  hard shadow at half opacity with an outline of a quarter unit, both
  drawn into the images, with one switch for the game.
- The whole should look interesting and designed, not only functional.
- Level zoning follows a grid and camera zones, placed from a director's
  view that controls the rhythm of tension and rest.

### Contrast of the proposed values

Relative luminance and contrast ratio as WCAG 2.2 defines them, the same
formula as `contrast()` in the template; lightness as CIE L*.

| Role | Colour | L* |
|------|--------|---:|
| `canvas` | #F4F4F4 | 96 |
| `canvas_alt` | #E4E4E4 | 91 |
| `solid` | #808080 | 54 |
| `dim` | #5A5A5A | 38 |
| `ink` | #1C1C1C | 10 |
| `reward` | #F5C518 | 82 |
| `danger` | #E23B2E | 51 |

| Pair | Ratio | Reading |
|------|------:|---------|
| `canvas` / `canvas_alt` | 1.16 | Texture, not an object |
| `solid` / `canvas_alt` | 3.11 | Above 3:1, WCAG 2.2 1.4.11, without an outline |
| `ink` / `solid` | 4.32 | The player on a platform |
| `ink` / `canvas_alt` | 13.40 | The player, an outline or a label on the backdrop |
| `dim` / `canvas_alt` | 5.42 | A secondary label |
| `reward` / `canvas_alt` | 1.28 | Invisible without its outline |
| `danger` / `solid` | 1.09 | Invisible without its outline |
| `ink` / `reward` | 10.45 | What makes a pickup show |
| `ink` / `danger` | 3.98 | What makes a hazard show |
| `solid` / `dim` | 1.75 | The low-contrast stripe pair |

The accents lose to their backgrounds on value, so they are read by the ink
outline around them and understood by their hue. A frame rendered without
saturation keeps the hierarchy.

### Level design

- Koichi Hayashida, director of *Super Mario 3D Land*, in a 2012 interview
  with Gamasutra ("The Structure of Fun: Learning from *Super Mario 3D
  Land*'s Director", gamedeveloper.com): a level introduces one idea,
  develops it, turns it, and concludes, the four-panel *kishōtenketsu*.
- Smith, Treanor, Whitehead and Mateas, "Rhythm-Based Level Generation for
  2D Platformers", FDG 2009: levels built as rhythm groups, each a run of
  challenges, joined by small platforms that serve as rest areas.
- The Platform behavior (Construct 3 manual, `behavior-reference/platform.md`
  at `2b1f879`): *Max speed* in pixels per second, *Jump strength* the
  initial vertical speed, *Gravity* in pixels per second per second, *Jump
  sustain* the milliseconds the jump speed holds while the control is held.
  Jump height is then about `v·s + v²/2g` and air time for a jump that lands
  at its take-off height about `s + v/g + √(2h/g)`; horizontal reach is the
  max speed over that time. The approximation ignores acceleration up to max
  speed, the max fall speed and frame-by-frame integration.
- The template's viewports are not whole grid units on their short side:
  720 is 22.5 units of 32, 1080 is 33.75, 180 is 22.5 units of 8.

### Construct facts the design leans on

- A Tiled Background repeats its image at any size without stretching it;
  a Sprite scales its image with the object. A pattern stays at its pixel
  size only on a Tiled Background.
- A Tiled Background instance has the `image-offset-x` and `image-offset-y`
  properties, written as 0 by `tiledbg_inst()` today. Tiling starts at the
  object's own corner, so two neighbouring pieces of a pattern join without
  a seam only when their offsets align the pattern to the layout.
- None of the 89 effects in `data/c3-schemas/_index.json` draws an outline
  or a drop shadow. Published Construct games use a third-party effect for
  them, or an offset copy of each shape tinted dark.
- Sine, Tween and Flash are behaviors in `data/c3-schemas/_index.json`;
  Shadow Light is a plugin with a Shadow caster behavior, shown in the
  official `shadows-*` examples.

## Options

1. **Leave the stand-in to the model.** Iterations 21 to 23: each run draws
   its own, and a template default is what a small model repeats.
2. **A look section in the prompts.** Prose that the repository has
   measured not to reach a small model (`event-sheet-design-guidance.md`,
   "What small models read").
3. **A fixed vocabulary, values and checks in the template.** Chosen, below.
4. **Soft drop shadows and a light top edge on every object.** Tried in
   mock-up and turned down: a translucent, blurred shadow over the checker
   reads as a smear. A hard one reads as a sticker lifted off the page.
5. **Depth layers in parallax, each farther one lighter.** Offered as a
   reading of "onion skin"; the user meant the transparency checker.
6. **Shadow Light in every game.** Real shadows are right where light is a
   mechanic of a top-down game; as a default they are a cost with no role.
   Left for a game that asks for it.
7. **The shadow as a copy of each object on a layer below.** Overlapping
   shadows would not darken at layer opacity 50%, and the direction would
   hold under rotation. Each object then needs a twin kept in step with
   it, one more thing a small model writes wrong; drawing the shadow into
   the image needs nothing at run time.

## Decision (proposed)

### The vocabulary

Three dimensions, each with one job.

| Dimension | Says | Values |
|-----------|------|--------|
| Shape | What a thing is | Rectangle: the player and structure. Circle: what is collected. Triangle: what hurts. |
| Colour | What role it plays | The roles of `PALETTE` above |
| Pattern | What an area or an edge does | Four patterns, below |

Objects are Sprites of one flat colour with an ink outline. Areas and edges
are Tiled Backgrounds with a pattern. A triangle and a circle get collision
polygons of their shape; `frame()` writes a rectangle today, and a spike's
empty corners would hurt.

Every object carries an ink outline and a hard cast shadow, drawn into its
image by `shape()` from one table, `SHAPE_STYLE`, which turns either off or
changes it for the game; `shape(..., outline=False, shadow=False)` does so
for one image.

| Value | Default | Source |
|-------|---------|--------|
| Outline width | `max(1, UNIT / 4)` px, inside the edge: 8 px at 1920×1080, 2 px at 320×180 | [author] bakes 4 px into a 74 px sprite; [author] about 0.75% of the short side |
| Shadow offset | 2.7% of the viewport's shorter side | Median of [author]'s 12 games with a shadow |
| Shadow angle | 45°, down and to the right | [author]'s majority, [author]'s slime |
| Shadow opacity | 0.5 | [game]; the range seen is 0.25 to 1 |
| Shadow colour | `ink` | |

The outline lies inside the edge, so a shape keeps its size on the grid.
The shadow widens the image on its side; the frame's origin and collision
polygon stay on the shape, and an instance is written at the image's size.
Drawn into the image, a shadow turns with a rotating sprite and darkens
where two shadows overlap; a sprite that rotates is drawn without one. In a
top-down game, anything airborne gets a flat ellipse of `ink` at about 25%
alpha on the ground under it instead, the distance between the two being
its height.

### The values

`PALETTE` becomes the table under "Contrast of the proposed values": two
canvas greys, one solid grey, `dim` for secondary labels, `ink`, and two
accents. The player is `ink`, the darkest and highest-contrast thing on
screen. A game adds a third accent only for a role the two do not cover, a
goal for instance. A bar's fill takes `ink`, its frame `solid`.

Checks, where the colours are written, each stopping the run with the roles
that would pass:

- `canvas` against `canvas_alt` at most 1.2:1.
- `solid` against `canvas_alt` at least 3:1.
- `ink` against every fill at least 3:1.
- An object in an accent role is drawn with its outline.
- A label at least 4.5:1, a title 3:1, as the branch checks today.

### The backdrop

The transparency checker, cells of `UNIT / 2` so two make a unit, in
`canvas` and `canvas_alt`, one Tiled Background on a layer at parallax 1
aligned to the layout origin. It replaces the grid as the ruler: never both.
In a top-down game it is the floor.

### The patterns

| Pattern | Colours | Marks |
|---------|---------|-------|
| Checker | `canvas`, `canvas_alt` | Empty space: the backdrop only |
| Low stripes | `solid`, `dim` | A surface that is special and harmless: a one-way platform, a safe zone |
| Caution stripes | `reward`, `ink` | What moves, triggers or blocks on a condition: a door, a plate, a crusher's edge |
| Hazard stripes | `danger`, `ink` | An area that hurts: lava, a kill zone |

A red triangle is one hazard; a red-striped area is a hazardous region. The
yellow of a pickup and of caution stripes do not clash: one is a circle,
the other an area. The high-contrast stripes cover strips and small zones,
never a backdrop. Stripes run at 45°, their period divides the tile, the
tile is a whole number of units, and `tiledbg_inst()` writes
`image-offset = -position mod tile` so any two pieces meet without a seam.

### Motion and type

- Pickups bob with Sine; a pickup collected scales up and fades with Tween;
  the player squashes on landing and recovers with Tween; a hit flashes with
  Flash. Durations and easing are constants of the template, one set for
  the game, measured from the studio examples before they are fixed.
- Type stays Arial bold in the two sizes of `TEXT_SIZE`. A number is shown
  at the title size in `ink`, its label at the body size in `dim`.

### The level on three grids

- **Unit**: `UNIT`, as today.
- **Module**: the player's reach in units, from the Platform properties by
  the approximation above. Every gap and every step up is checked against
  it at generation; a gap of at most half the reach is easy, eight or nine
  tenths is hard. The approximation is confirmed in a preview before its
  bands are trusted.
- **Camera zone**: one viewport. Each zone is a shot about one idea: when
  the camera arrives, the entry, the challenge and the exit are in frame,
  and a corner of the next zone shows. A challenge does not straddle a zone
  edge: a stop with a room-locked camera, a warning with a following one.
  Zones start on the unit grid; the fractional unit left on the short side
  is margin.

### Pacing

A `BEATS` list at the top of the generator gives each zone a type (`intro`,
`teach`, `practice`, `twist`, `rest`, `climax`, `exit`) and an intensity
from 0 to 3. Checks:

- The first zone is 0, its entry safe, the goal or its direction visible.
- A beat of 2 or more is followed by a `rest`, which holds a pickup or a
  checkpoint.
- A mechanic appears alone in a `teach` before any beat combines it.
- The `climax` is in the last third and followed by a release.
- The mean intensity of the last third exceeds that of the first.

The generator prints the curve as one line of text per zone, the form a
small model reads. In a one-screen game, the template's default, beats are
windows of time, spawn waves or rounds, under the same rules, and the
screen keeps one focus at a time with the HUD on the edges.

### What changes in the template

In place: `shape()` for the three shapes with `SHAPE_STYLE`'s outline and
shadow, `drawn()` for their frames, `frame()` with a collision polygon, and
the coin stand-in drawn by them. To come: `PALETTE`, `bar_images()`,
`layer()`'s fill, `tiledbg_inst()` for offsets; helpers for the four
patterns and the checker backdrop; `BEATS` with its
checks and printed curve; a reach function from the Platform properties.
`event-sheet-style.md`, *Project*, and `generating-a-project.md` get the
vocabulary in a few lines each. Tests pin each check and its message.

## Verification planned

- The checks as tests, each held to a fixture it must fail on.
- A Haiku 4.5 iteration on the cases of iterations 21 to 23 and a paced
  platformer case, against the template of iteration 23.
- The template's stand-in game rendered before and after, from its files,
  for the user to judge. Whether it looks designed is the user's call; no
  script scores it.

## Re-evaluate when

- The user's reading of the rendered stand-in disagrees with the mock-ups.
- A run adds colours outside `PALETTE` or passes `painted=True` to flat
  shapes to get around the checks.
- The reach from the approximation and the reach measured in a preview
  differ by more than one unit.
- A game needs more than three accents: the vocabulary is then too small
  for it, or the game is past the blockout.
- Real art arrives, from the user, a kit of the examples or an image model:
  the blockout gives way, and its grids and pacing stay.

## Update 2026-09-27: the manifest, pure alpha and the grid

The user asked for the look as metadata an agent can hand a model and
confirm against, and for two strict rules: a clean alpha channel, and
objects locked to one grid instead of drifting.

`skills/construct3-project/assets/look-manifest.json` lists every rule of
this record with a status: `enforced` when a check stops the generator,
`adopted` when the user decided it and the template holds it, `open` when
the template holds a value the user has not chosen, `proposed`, and
`rejected`. A rule the template holds names the symbol and the value, and
`tests/test_project_tools.py` fails when the two drift apart. Its
`deliver` steps are what a model writing the generator is given; its
`confirm` steps are what the agent runs on the result.

The strict rules, enforced where the generator writes and confirmed on the
project's files by `scripts/check_look.py`:

- `alpha.pure`: `write_png()` writes a clear pixel as (0, 0, 0, 0) and stops
  on an alpha other than 0, 255 and the shadow's. A colour under alpha 0
  bleeds into the edge when linear sampling scales the image.
- `grid.shape-size`: `shape()` stops on a size that is not whole units.
- `grid.world-placement`: `shape_inst()` places a shape by the cell of its
  top-left corner, whatever side the shadow hangs on; `on_grid()` stops on
  a world instance whose box does not start on the grid. The HUD keeps
  `anchor()`: 720 and 1080 are not whole units of 32, so an edge-held box
  sits MARGIN from the edge, not on the grid.
- `grid.runtime-spawn`: `grid_random()` gives a random whole-unit position;
  the stand-in's coins use it, where they used a raw `random()` before.

A tween, a shake or a squash moves an object off the grid while it plays;
the rule holds its rest position. `motion.hit` is open: this record says
Flash, the study of published games says a colour set for 0.05 to 0.1 s.

## Update 2026-09-27: the hit and the shadow's angle

The user decided both open rules. A hit sets the object's colour to white
or `danger` for 0.05 to 0.1 s with a size punch, as the three studios of
`published-game-visual-language.md` do, in place of the Flash behavior of
*Motion and type* above. The shadow stays at 45°, down and to the right.
The manifest marks both `adopted`; neither has a check, and the hit has no
helper in the template yet.

## Update 2026-09-27: the hit in the template

An object's colour in Construct multiplies its image, so Set color cannot
turn a yellow shape white, and the Set color effect would recolour the baked
shadow with it. The hit is therefore a frame: `hit_frame()` draws the
shape's second frame with the same outline and shadow, filled in the new
`flash` role of `PALETTE` and tagged `hit`; `hit_flash(obj)` gives the three
actions that show it for `HIT_FLASH["seconds"]`, 0.08 s of real time so that
slow motion does not stretch it, and return to frame 0. The coin's `Collect`
uses it. `beh_def("Flash")` stops the generator, and `check_look.py` reports
a type or family that holds the Flash behavior. The size punch stays with
`motion.squash`, which is proposed.

## Update 2026-09-27: the size punch

The user asked for the hit's size punch in the template as well.
`size_punch(obj)` sets the object to 0.8 of its image's width and 1.2 of its
height, then tweens it back to the image's size over 0.25 s with
`easeoutback`, under the tag `punch`: the hit squash of [author]'s merge
(`published-game-visual-language.md`), the one hit squash the study found,
held in `SIZE_PUNCH`. `hit(obj)` gives the punch and the flash together. The
rest size is the image's, which `shape_inst()` writes. The coin's `Collect`
scores, shows the hit, and shrinks the coin away once the punch is over; the
tap that starts it now requires that no tween is playing on the coin, so a
coin already being collected is not collected twice. `motion.squash`, for
landing and jumping, stays proposed.

## Update 2026-09-27: landing and jump squash

The user asked for the landing and jump squash. `SQUASH` holds three kinds,
each [author]'s recipe from `published-game-visual-language.md`: a hit, 0.8 ×
1.2 back in 0.25 s `easeoutback`; a landing, 1.2 × 0.8 back in 0.5 s
`easeoutelastic`; a jump, 0.7 × 1.3 held 0.2 s, back in 0.75 s
`easeoutelastic`. `squash(obj, kind)` stops the squash the object is in,
sets the size, holds it and tweens back under the tag `squash`; the earlier
punch is its `hit` kind. A Platform or Solid object that grows moves its
collision box into the floor, and [author] separates the two in 13 of 18
games, so a squash acts on the art pinned to an invisible mask. The
generator stops on a squash of an object whose behavior collides, and
`check_look.py` reports one. `motion.squash` is adopted and
`motion.squash-art` enforced.
