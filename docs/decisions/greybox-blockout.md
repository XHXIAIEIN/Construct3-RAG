# Greybox Blockout: The Stand-in Look and the Level's Pacing

Date: 2026-09-26; the look revised 2026-10-08
Schema: Construct 3 r495.2

## Problem

A generated game has no art until the user or the agent's image tool
supplies it, and until then it has to look like what it is: a blockout that
can be played, read and judged, and still looks like a designed thing rather
than a debug screen. The template does not draw art
(`game-look-from-design-skills.md`). In place of art it drew "a stand-in of
one colour or a plain shape", and each run filled that in its own way.

A level had the same gap. The grid, `anchor()` and `no_overlap()` place a
HUD; nothing placed a level's content, so a model laid platforms, hazards
and pickups one at a time, with no measure of what the player can jump and
no order in which the level asks things of the player.

Task: a generated game gets a blockout look that holds together and a level
laid out on grids and paced like a directed sequence, both from values of
the generator template and checks where the generator writes, so that a
small model gets them by default.

## Evidence

### What the user decided

Over reference blockouts and mock-ups of the stand-in:

- Value carries the hierarchy; colour is kept for what must be noticed
  wherever the eye is. Deep black and white with greys between, and a few
  highly recognisable accents.
- Placeholders are three shapes: rectangle, triangle, circle.
- Pattern marks areas and edges, not objects, as Tiled Backgrounds.
- The look is neutral and costs a model no decisions: a template default it
  keeps, not a style it chooses per game.
- The stand-in is a plain sheet (2026-10-08). The user compared the
  template's preview, with the checker, a hard grey shadow and ink outlines,
  against six mock-ups of one coin screen. Three drew an app interface,
  with rounded cards, a score pill and a shadow on everything; the user
  read them as a template and as AI-made. Of three full-screen directions,
  a plain sheet, a two-ink print and an ink line, the user chose the plain
  sheet: flat fills on an off-white canvas, no outline, no shadow, the
  number large.
- The sheet's details (2026-10-08, a second round of mock-ups at
  1920×1080). The score is its name in small dim capitals over a large
  number of regular weight, the round in the top right corner. The coin is
  cobalt with no outline: colour alone keeps the sheet simple, and a gold
  reads 1.5:1 on near white without one. The coins sit on a small board
  centred on the screen, 5 × 3 slots with the empty ones in `canvas_alt`;
  scattered over the screen, or on a board as wide as the screen, they
  read as untidy. Every label is in `system-ui`, the generic family the
  editor's font picker lists as System UI: no font file ships with a game.
- Where something is transparent, a mask, or a background still to come,
  the backdrop is the grey-and-white checker editors show for transparency.
- Where a game turns them on, the shadow is hard at half opacity and the
  outline a quarter unit, both drawn into the images. Soft translucent
  shadows read as a smear.
- A hit is a colour set with a size punch, and landing and jumping squash;
  a shadow, when on, falls at 45°, down and to the right.
- Level zoning follows a grid and camera zones, placed from a director's
  view that controls the rhythm of tension and rest.
- The look is metadata an agent can hand a model and confirm against, with
  two strict rules: a clean alpha channel, and objects locked to one grid.

The outline, shadow, hit and squash values come from the evidence in
`published-game-visual-language.md`.

### Contrast of the values

The ratios are WCAG 2.2 contrast ratios of relative luminance, the formula
of `contrast()` in the template; L* is CIE lightness.

| Role | Colour | L* |
|------|--------|---:|
| `canvas` | #FAFAF7 | 98 |
| `canvas_alt` | #EEEEEA | 94 |
| `solid` | #848480 | 55 |
| `dim` | #646460 | 42 |
| `ink` | #111111 | 5 |
| `reward` | #2563EB | 46 |
| `danger` | #DC263C | 48 |

| Pair | Ratio | Reading |
|------|------:|---------|
| `canvas` / `canvas_alt` | 1.11 | The checker reads as texture, not an object |
| `solid` / `canvas_alt` | 3.23 | Above 3:1, WCAG 2.2 1.4.11, without an outline |
| `reward` / `canvas_alt` | 4.44 | A pickup shows without an outline |
| `danger` / `canvas_alt` | 4.12 | A hazard shows without an outline |
| `ink` / `solid` | 5.03 | The player on a platform |
| `ink` / `canvas_alt` | 16.23 | The player or a label on the backdrop |
| `dim` / `canvas_alt` | 5.11 | A secondary label |
| `reward` / `danger` | 1.08 | Told apart by hue and shape, not value |
| `ink` / `reward` | 3.65 | An outline, where a game turns it on |
| `ink` / `danger` | 3.94 | An outline, where a game turns it on |
| `solid` / `dim` | 1.58 | The low-contrast stripe pair |

Every fill reads at least 3:1 on the darker checker grey, so a shape shows
on the sheet and on the checker alone.

### Level design

- Koichi Hayashida on *Super Mario 3D Land* (Gamasutra, 2012, "The Structure
  of Fun"): a level introduces one idea, develops it, turns it, and
  concludes, the four-panel *kishōtenketsu*.
- Smith, Treanor, Whitehead and Mateas, "Rhythm-Based Level Generation for
  2D Platformers", FDG 2009: rhythm groups of challenges joined by rest
  platforms.
- The Platform behavior (manual, `behavior-reference/platform.md`): with
  *Jump strength* v, *Gravity* g and *Jump sustain* s, jump height is about
  `v·s + v²/2g` and air time for a landing at take-off height about
  `s + v/g + √(2h/g)`; reach is *Max speed* over that time. The
  approximation ignores acceleration, the max fall speed and frame-by-frame
  integration.

### Construct facts the design leans on

- A Tiled Background repeats its image at any size without stretching it,
  so a pattern keeps its pixel size only there. The runtime subtracts
  `image-offset / image size` from the texture coordinate (the Tiled
  Background plugin of a published export's `c3main.js`), so two pieces meet
  without a seam when their offsets align the pattern to the layout.
- None of the effects in `data/c3-schemas/_index.json` draws an outline or a
  drop shadow.
- An object's colour multiplies its image, so Set color cannot turn a yellow
  shape white, and the Set color effect would recolour a baked shadow.
- A Platform or Solid object that grows moves its collision box into the
  floor.

## Options

1. **Leave the stand-in to the model.** Each run draws its own, and a
   template default is what a small model repeats.
2. **A look section in the prompts.** Prose the repository has measured not
   to reach a small model (`event-sheet-design-guidance.md`).
3. **A fixed vocabulary, values and checks in the template.** Chosen.
4. **Soft drop shadows and a light top edge.** A translucent, blurred shadow
   over the checker reads as a smear.
5. **An app interface: a stage card, a score pill, a shadow under every
   element.** It looks finished in a mock-up, and the user read it as a
   template and as AI-made: a game's screen is the scene, not a dashboard.
6. **A two-ink print or an ink line.** Both have a character of their own,
   which a neutral default does not want, and the print's overprint and
   grain cost generation steps.
7. **The checker, outline and hard shadow by default.** The look of this
   record until 2026-10-08; on the preview the checker read as an image not
   yet loaded and the grey shadow as dirt. The checker stays for
   transparency, the outline and shadow as switches.
8. **Depth layers in parallax, each farther one lighter.** A misreading of
   the checker backdrop.
9. **Shadow Light in every game.** Right where light is a mechanic; as a
   default, a cost with no role.
10. **The shadow as an ink twin of each object on a layer below.** Each
    object then needs a twin kept in step with it, one more thing a small
    model writes wrong; drawn into the image, the shadow needs nothing at
    run time.
11. **The Flash behavior for a hit.** The evidence shows none using it for
    hits, and it blinks the whole image, shadow included.

## Decision

Option 3, in `skills/construct3-agent-plugin/assets/build_project.py`.

### The vocabulary

| Dimension | Says | Values |
|-----------|------|--------|
| Shape | What a thing is | Rectangle: the player and structure. Circle: what is collected. Triangle: what hurts. |
| Colour | What role it plays | The roles of `PALETTE` |
| Pattern | What an area or an edge does | The stripes of `PATTERNS` |

An object is `shape(file, kind, w, h, role)` in `build_images()`: one flat
colour, whole units wide and high, its collision polygon the shape's. The
outline and cast shadow of `SHAPE_STYLE` are off by default; a game that
turns them on gets them drawn into the image.

| `SHAPE_STYLE` | When on |
|---------------|---------|
| Outline | `max(1, UNIT / 4)` px of `ink`, inside the edge, so a shape keeps its size on the grid |
| Shadow | `ink` at 0.5 opacity, hard, 2.7% of the viewport's shorter side at 45° |

The shadow widens the image on its side; the origin and polygon stay on the
shape. A sprite that rotates is drawn with `shadow=False`.

The score is its name at `TEXT_SIZE["body"]` in `dim` over the number at
`TEXT_SIZE["title"]`, neither bold. Coins land on the board, `COLS` ×
`ROWS` slots a coin wide and a unit apart, one Tiled Background of a slot
tile, centred on the screen below the HUD. A round deals the cells
`(deal + i × STRIDE) mod CELLS`, with `STRIDE` and `CELLS` coprime, so no
two coins meet, and the run stops on a round with more coins than slots.

### Colour

`PALETTE` holds the table under "Contrast of the values" plus `flash`, the
fill of a hit. Keep the roles and change values only. The player is `ink`;
a bar is an `ink` fill in a `solid` frame. A game adds a third accent only
for a role the two do not cover. The run stops, naming the roles that would
pass, when:

- `canvas` and `canvas_alt` pass 1.2:1, or `solid` falls under 3:1 on
  `canvas_alt` (`check_palette()`);
- an accent, a role that is a hue rather than a grey, falls under 3:1 on
  `canvas_alt` and is drawn without its outline, or an outlined fill falls
  under 3:1 against `ink` (`shape()`);
- a label reads under 4.5:1, or under 3:1 from 18 pt up, large-scale text
  (`text_contrast()`, through `hud_text()` and every label).

### Backdrop and patterns

`backdrop()` lays a backdrop pattern on a layer at parallax 1 from the
layout's origin: the plain sheet by default, or, in a game with something
transparent, a mask or a background still to come, the checker, cells of
`UNIT / 2` in `canvas` and `canvas_alt`. The checker is then the ruler:
never a grid as well. In a top-down game the backdrop is the floor.

| Pattern | Colours | Marks |
|---------|---------|-------|
| Plain | `canvas` | Empty space: the backdrop only |
| Checker | `canvas`, `canvas_alt` | Empty space over transparency: the backdrop only |
| Low stripes | `solid`, `dim` | A surface that is special and harmless: a one-way platform, a safe zone |
| Caution stripes | `reward`, `ink` | What moves, triggers or blocks on a condition |
| Hazard stripes | `danger`, `ink` | An area that hurts |

`pattern(name, kind)` draws a one-unit tile, stripes at 45°;
`pattern_type()` declares its Tiled Background and `area()` places it on
grid cells, refusing the backdrop patterns and caution or hazard stripes wider than a
quarter of the viewport's shorter side. `tiledbg_inst()` writes
`image-offset = -corner mod tile`.

### Motion

- A hit is a frame: `hit_frame(file)` draws the shape's second frame in
  `flash` inside the ink outline, which keeps a white flash visible on the
  sheet, tagged `hit`; `hit_flash(obj)` shows it for
  `HIT_FLASH["seconds"]`, 0.08 s of real time so slow motion does not
  stretch it. `beh_def("Flash")` stops the run.
- `squash(obj, kind)` sets the size to the share `SQUASH` gives, holds it
  and tweens back under the tag `squash`: a hit 0.8 × 1.2 back in 0.25 s
  `easeoutback`, a landing 1.2 × 0.8 in 0.5 s `easeoutelastic`, a jump
  0.7 × 1.3 held 0.2 s, back in 0.75 s `easeoutelastic`. `hit(obj)` gives the
  hit's squash with the flash, as the coin's `Collect` does.
- A squash acts on the art: a player is an invisible mask with Platform and
  its art, drawn with `shape(..., oy=1)`, pinned to it. The run stops on a
  squash of an object whose behavior collides.

### The grid

- `shape_inst(type, file, col, row)` places a shape by the cell of its
  top-left corner, whatever side the shadow hangs on; `on_grid()` stops the
  run on a world instance off the grid. The HUD keeps `anchor()`: 720 and
  1080 are not whole units of 32.
- An object created at runtime goes to `grid_random(lo, hi)`, never a raw
  `random()`.
- `write_png()` writes a clear pixel as (0, 0, 0, 0) and stops on an alpha
  other than clear, opaque and the shadow's: a colour under alpha 0 bleeds
  into the edge when linear sampling scales the image.

A tween, a shake or a squash moves an object off the grid while it plays;
the rule holds its rest position.

### The level

- **Unit**: `UNIT`.
- **Module**: the player's reach. `jump_reach()` computes it from
  `PLATFORM` by the approximation above, 286 px or about 8.9 units with the
  template's values; `jump(gap, rise)` says easy, medium or hard and stops
  past nine tenths of it.
- **Camera zone**: one viewport, a shot about one idea: entry, challenge and
  exit in frame, a corner of the next zone showing. A challenge does not
  straddle a zone edge.

### Pacing

`BEATS` gives each zone, or each round, wave or window of time in a
one-screen game, a `beat(type, intensity, mechanics, holds=...)`. `pace()`
stops the run when the first beat is above 0; a beat of 2 or more is not
followed by a rest holding a pickup or a checkpoint, or the climax by the
exit; a mechanic is combined before a `teach` of its own; the climax is
missing or outside the last third; or the last third is not more intense on
average than the first. It prints the curve, one line a beat, above
`generated; checking`. The stand-in plays its beats as rounds:
`ROUND_COINS` holds each round's coins and a global `beat` counts them.

### The manifest

`skills/construct3-agent-plugin/assets/look-manifest.json` lists every rule of
this record with a status: `enforced` when a check stops the generator,
`adopted` when the user decided it and the template holds it, `proposed`,
`rejected`. Its `deliver` steps are what a model writing the generator is
given, its `confirm` steps what the agent runs on the result, among them
`scripts/check_look.py`, which confirms the strict rules on the project's
files. `tests/test_skill_build_project.py` fails when a rule and the
template value it names drift apart.

## Open

- The plain sheet has been previewed on the coin stand-in only, not on a
  game with structure, hazards or a player. The reach bands wait on a
  measured jump.
- No small-model iteration has run on this template. The eval case
  `readable-on-a-dark-background` asks for a navy backdrop, on which the
  labels' `ink` reads 1.4:1: `readable()` stops the generator, and the case
  grades what the model does with that stop.
- The score is at the title size with its label; the eval cases that grade
  the HUD have not run on it.
- Not in the template: camera-zone helpers; Sine
  bobbing for pickups; the juice functions, camera-zone fields and
  five-level worlds of `published-game-visual-language.md`, `proposed` in
  the manifest.

## Re-evaluate when

- The user's reading of the running stand-in disagrees with the mock-ups.
- A run adds colours outside `PALETTE`, or passes `painted=True` to flat
  shapes to get round the checks.
- The reach from the approximation and the reach measured in a preview
  differ by more than one unit.
- A game needs more than three accents: the vocabulary is too small for it,
  or the game is past the blockout.
- Real art arrives, from the user or an image model: the blockout gives
  way, and its grids and pacing stay.
