# Paper and Ink: The Generator Template's Default Look

Date: 2026-10-14
Schema: Construct 3 r495.2

## Problem

The generator template's stand-in look was the plain sheet of
`greybox-blockout.md`: flat fills on an off-white canvas, labels in the
platform's `system-ui` face at two sizes, a cobalt and a red accent. The
user judged its layout and its type as lacking taste, and named the
references that show the taste meant.

Task: a game the template generates looks designed before its art arrives.
The look is the one the user picked on screenshots. Values of the template
and checks where the generator writes hold it, so that a small model gets
it by default.

## Evidence

### The user's references

Four design-led websites the user named, two light editorial ones and two
dark technical ones, measured in a browser on 2026-10-14:

- Every one ships its own font; none uses a platform face.
- One family each, with at most a monospace beside it, in two or three
  weights.
- A display line 7 to 21% of the viewport high.
- A near-monochrome interface on a tinted neutral; the colour comes from
  the content.

### The user's picks

The user compared mock-ups of one game screen in the template's look and
in two directions drawn from the references: paper with line-drawn ranges
and one accent, and a dark screen with a dot grid and a gradient accent.
The user accepted the paper screen, then refined it in a playable
prototype at 1280×720 and decided:

- The look comes from the prototype; its attack timing does not.
- Areas and ranges are lines; objects are flat fills.
- The prototype's red for what hurts or must be noticed. On screenshots of
  the stand-in, the user took the plain sheet's cobalt for what is
  collected over the red and over an ink ring with a dot.
- On the same screenshots the user preferred the plain sheet's coins to the
  prototype's proportions: each coin fills the box a finger taps, on a disc
  of the faint fill the same size, and the board has no frame.
- The control hints dim to 35% after the player's first input.
- The screen the player plays on shows no game name. The prototype's header
  labelled a demo page; a player needs the round, not the name.
- The prototype's character is a reference for the shape, contrast and
  proportions of the subjects on the screen, not a part of the template.

The prototype's values, at 1280×720:

| What | Value |
|------|-------|
| Paper, ink, accent | `#ECEAE4`, `#141311`, `#E0452B` |
| Structure drawn as lines | `#CFCAC0`, 1 px |
| An area or a range | a 1 px edge at 55% ink over a 6% ink fill |
| Type | Inter: title 20 px weight 500; a tracked Latin tag 10 px, 0.3 em apart; a stat's name 11 px over its number 40 px weight 300; a control's key 11 px weight 500 in a 1 px ink box, its verb 12 px beside it |
| HUD | a title and a tag top left, the count the player plays for top right, the controls bottom left, 48 px from the edges |
| The player and its targets | discs 44 px across, 6% of the height: the player solid ink, a target paper with a 2 px ink ring |

### Contrast of the values

WCAG 2.2 contrast ratios, the formula of `contrast()` in the template:

| Role | Colour | On `canvas` | On `canvas_alt` |
|------|--------|------------:|----------------:|
| `canvas` | #ECEAE4 | | 1.13 |
| `canvas_alt`, 6% ink over the paper | #DFDDD7 | 1.13 | |
| `line` | #CFCAC0 | 1.36 | 1.20 |
| `solid`, 55% ink over the paper | #757470 | 3.89 | 3.44 |
| `dim` | #65615A | 5.12 | 4.53 |
| `ink` | #141311 | 15.43 | 13.67 |
| `reward`, the plain sheet's cobalt | #2563EB | 4.30 | 3.81 |
| `danger`, the prototype's accent | #E0452B | 3.45 | 3.06 |

The prototype's dim, `#8A867D`, reads 3.0:1 on the paper and fails the
4.5:1 of small text. `#65615A` passes on `canvas_alt`, the surface a label
is checked against.

### Fonts in Construct

A probe project in the editor's preview (r495.2, Chrome on Windows)
showed:

- A font file in `fonts/`, listed under `rootFileFolders.font`, loads by its
  file name without the extension: `Inter-Regular.woff` is the font
  `Inter-Regular`. WOFF and TTF both load; the manual asks for WOFF or
  WOFF2, which work on every platform (`plugin-reference/text.md`).
- Chinese text in a Text whose font is Inter falls back to the platform's
  Chinese face, a sans serif on Windows.
- A Text whose font the project lacks draws its Latin letters in the
  browser's default serif face.
- Each weight is a file and a font of its own: the official examples list
  `RobotoRegular.ttf` and `RobotoBold.ttf` and name each in a Text.
- The Text object has no letter spacing. A space of a quarter em, U+2005,
  between letters tracks a tag in one Text.

### 9-patches in the preview

Stretched, a 9-patch whose fill is a few pixels blended that fill into its
edge across the whole area under linear sampling. With overlapping seams
its right and bottom edges came out a pixel thicker than the others. Parts
tiled at their size with exact seams drew every edge at its width.

### A game of the user's

A generated puzzle game of the user's, portrait at 720×1280, took the look
in its own generator: paper, glass drawn as a line of ink, its liquids the
only colour. Its HUD is an HTML Element, which drew the shipped fonts by
the same names as a Text does. At twice the prototype's px the HUD read at
a phone's size in the preview.

## Options

1. **Keep the plain sheet.** The user rejected its type and layout.
2. **Paper and ink in the platform face.** No file to ship, but every
   reference ships its own font, and the platform face changes the look on
   every system.
3. **Paper and ink with a subset of Inter shipped by the skill.** Chosen.
4. **The dark direction.** The user picked paper.
5. **A Chinese font subset as well.** A subset depends on the game's text
   and must be rebuilt when the text changes, and a full Chinese face is
   megabytes. Chinese keeps the platform face.
6. **The prototype's character as a template object.** The user ruled it
   out: the character is a reference for the subjects' shape, contrast and
   proportions.

## Decision

Option 3, as the default of `skills/construct3-agent-plugin/assets/build_project.py`.

### The font

The skill ships Inter in three weights under `assets/fonts/`, with its SIL
Open Font License 1.1 text:

| File | Weight | Used for |
|------|--------|----------|
| `Inter-Regular.woff` | 400 | body text, names, tags, verbs |
| `Inter-Medium.woff` | 500 | titles, keys, button labels, banners |
| `InterDisplay-Light.woff` | 300 | the count the player plays for |

Source: Inter 4.1, `https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip`,
sha256 `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e`,
the static TTFs of `extras/ttf/`. Each subset holds Basic Latin, Latin-1,
Œ and œ, the spaces, dashes, quotes, bullet, ellipsis, per mille and single
guillemets of General Punctuation, the euro, the trademark, four arrows and
the minus, and keeps the copyright and license entries of the name table:

```bash
python -m fontTools.subset extras/ttf/Inter-Regular.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+0152-0153,U+2002-200A,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2030,U+2039-203A,U+20AC,U+2122,U+2190-2193,U+2212" --name-IDs="*" --flavor=woff --output-file=Inter-Regular.woff
```

The template copies the files `FONT` names into the project's `fonts/` and
lists them in `project.c3proj`. It stops when a file is in neither place,
because a missing font draws the game's Latin text in a serif face.

### The colours

`PALETTE` holds the roles of the contrast table and `flash`, white, the
fill of a hit frame. `reward` is cobalt and `danger` red, and the shape
tells them apart as well: a circle is collected, a triangle hurts. The
caution stripes, what moves or triggers, are ink on the paper, and the
hazard stripes are red. `check_palette()`, `shape()` and `readable()` keep
the checks of `greybox-blockout.md`.

### The subjects

The prototype's player and targets set the shape, contrast and proportions
of what stands on the screen, not a character of the template:

- The player is the one solid ink mass, about 15:1 on the paper. What it
  collects is cobalt and what hurts it red, each over 3:1. Structure is the
  faintest: a fill of 6% ink for areas and slots, `line` at 1.4:1 for
  rings, and `solid` at 3.9:1 for an edge that marks where something
  applies.
- In an open field a subject is drawn `SUBJECT` across, 6% of the
  viewport's shorter side in whole units, 64 px at 1080, as the
  prototype's discs are 44 px at 720. One that is tapped keeps a box
  `TOUCH` wide around its drawing: `shape(..., inset=(TOUCH - SUBJECT) // 2)`,
  whose collision polygon covers the box.
- What is tapped on a board fills its `TOUCH` box, 160 px at 1080, on a
  slot of the same size, as the plain sheet drew its coins.
- In a viewport taller than 360 px every edge is antialiased: a pixel's
  alpha is the share the shape covers, sampled 4 × 4 where the edge crosses
  it, in a colour of `PALETTE`. Pixel art keeps its hard edges, and
  `check_look.py`'s `alpha.pure` holds them there.

### Lines

`LINE` is 1 px at 720 scaled to the viewport, 2 px at 1080. A region or a
range is a zone, `zone()`, a 9-patch of `zone_image()`: a `LINE` px edge in
`solid` round a `canvas_alt` fill, its parts tiled at their size with exact
seams. A ring around the play or a dashed reach is `ring()`, its coverage
from `ring_cover()`. A slot is a disc of `canvas_alt` the size of what
fills it, and a board of slots has no frame.

### Type and HUD

| Kind | Prototype px at 720 | `TEXT_SIZE` pt at 1080 | Weight |
|------|--------------------:|-----------------------:|--------|
| `tag`, tracked | 10 | 11 | regular, `dim` |
| `name`, of a stat or a key | 11 | 12 | regular; a key medium |
| `body`, body text and a verb | 12 | 14 | regular |
| `title`, a screen's title | 20 | 22 | medium |
| `number`, the count | 40 | 45 | light |
| `display`, a banner | | 64, two units | medium |

Points are the prototype's px scaled to the viewport's shorter side, times
0.75. In pixel art the small kinds are one unit and the large kinds two. A
label is never bold, because a weight is a file and the browser fakes a
bold that Inter lacks.

- `MARGIN` is a fifteenth of the shorter side in whole units, rounded down:
  64 px at 1080, as the prototype's 48 px at 720.
- `hud_tag()` sets what the player is on, a round, a level or a mode, top
  left as a small dim tag in tracked capitals: `tracked()` spaces them by
  U+2005, and `tracked_expr()` does it to a text the events set.
  `hud_header()` adds a title before a tag, on its baseline, for a menu or a
  result screen.
- `hud_stat()` sets the count top right: its name small and dim over a
  large light number.
- `hud_keys()` sets the controls bottom left: a key in a `LINE` px ink box
  with its verb beside it, every part a child of the first box.
  `hints(box_type)` is the group that tweens that box to 35% opacity in
  0.5 s on the first input. Its static local keeps the row dim after
  *Restart layout* (`prompts/pitfalls/restarting-a-layout.md`).
- `text_ems()` measures a printable ASCII character by its advance in Inter
  Medium, a wide one as 1 em and any other as 0.6 em, so a box fits its
  text in Inter.

The stand-in game shows the round as a tag, the score, one key, and
cobalt coins on a board of faint discs.

### Left out

The prototype's attack timing, hit-stop, screen shake and zoom punch stay
out, as the user decided; the hit keeps the template's flash and squash.

## Open

- The Chinese fallback was seen on Windows only; on macOS, iOS and Android
  the platform's per-script default decides the face.
- The text sizes suit a desktop window, the template's audience
  (`landscape-viewport.md`); on a phone held sideways a 12 pt name of a
  1920×1080 viewport is about 5 dp high.
- Claude's plugin directory holds a version for a reviewer when a script of
  the plugin uses a bundled image or font file (`plugin-folder.md`); whether
  the generator's copy of the font files counts as one is not known until a
  version is published.

## Re-evaluate when

- The user's reading of a generated game disagrees with the prototype.
- A game's Latin text shows in a serif face: a font file did not reach the
  project.
- A platform draws the fallback Chinese in a serif face.
- Claude's plugin directory holds a version for the font files.
- Most generated games are played on phones.
