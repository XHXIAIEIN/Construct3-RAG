# Paper and Ink: The Generator Template's Default Look

Date: 2026-10-14
Schema: Construct 3 r495.2

## Problem

The generator template's stand-in look was the plain sheet of
`greybox-blockout.md`: flat fills on an off-white canvas, labels in the
platform's `system-ui` face at two sizes, a cobalt and a red accent. The
owner judged its layout and its type as lacking taste, and named the
references that show the taste meant.

Task: a game the template generates looks designed before its art arrives,
in a look the owner picked on screenshots, held by values of the template
and checks where the generator writes, so that a small model gets it by
default.

## Evidence

### The owner's references

Four design-led websites the owner named, two light editorial ones and two
dark technical ones, measured in a browser on 2026-10-14:

- Every one ships its own font; none uses a platform face.
- One family each, with at most a monospace beside it, in two or three
  weights.
- A display line 7 to 21% of the viewport high.
- A near-monochrome interface on a tinted neutral; the colour comes from
  the content.

### The owner's picks

The owner compared mock-ups of one game screen in the template's look and
in two directions drawn from the references: paper with line-drawn ranges
and one accent, and a dark screen with a dot grid and a gradient accent.
The owner accepted the paper screen, then refined it in a playable
prototype at 1280×720 and decided:

- The look comes from the prototype; its attack timing does not.
- Areas and ranges are lines; objects are flat fills.
- One accent, for what is hit or must be noticed.
- The control hints dim to 35% after the player's first input.
- The prototype's character is a reference for the shape, contrast and
  proportions of the subjects on the screen, not a part of the template.

The prototype's values, at 1280×720:

| What | Value |
|------|-------|
| Paper, ink, accent | `#ECEAE4`, `#141311`, `#E0452B` |
| Structure drawn as lines | `#CFCAC0`, 1 px |
| An area or a range | a 1 px edge at 55% ink over a 6% ink fill |
| Type | Inter: title 20 px weight 500; a tracked Latin tag 10 px, 0.3 em apart; a stat's name 11 px over its number 40 px weight 300; a control's key 11 px weight 500 in a 1 px ink box, its verb 12 px beside it |
| HUD | the header top left, the count the player plays for top right, the controls bottom left, 48 px from the edges |
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
| the accent | #E0452B | 3.45 | 3.06 |

The prototype's dim, `#8A867D`, reads 3.0:1 on the paper and fails the
4.5:1 of a small label. `#65615A` passes on `canvas_alt`, the surface a
label is checked against.

### Fonts in Construct

A probe project in the editor's preview (r495.2, Edge and Chrome on
Windows) showed:

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

## Options

1. **Keep the plain sheet.** The owner rejected its type and layout.
2. **Paper and ink in the platform face.** No file to ship, but every
   reference ships its own font, and the platform face changes the look on
   every system.
3. **Paper and ink with a subset of Inter shipped by the skill.** Chosen.
4. **The dark direction.** The owner picked paper.
5. **A Chinese font subset as well.** A subset depends on the game's text
   and must be rebuilt when the text changes, and a full Chinese face is
   megabytes. Chinese keeps the platform face.
6. **The prototype's character as a template object.** The owner ruled it
   out: the character is a reference for the subjects' shape, contrast and
   proportions.

## Decision

Option 3, as the default of `skills/construct3-agent-plugin/assets/build_project.py`.

### The font

The skill ships Inter in three weights under `assets/fonts/`, with its SIL
Open Font License 1.1 text:

| File | Weight | Used for |
|------|--------|----------|
| `Inter-Regular.woff` | 400 | labels, tags, verbs |
| `Inter-Medium.woff` | 500 | titles, keys, button labels |
| `InterDisplay-Light.woff` | 300 | the count the player plays for |

Source: Inter 4.1, `https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip`,
sha256 `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e`,
the static TTFs of `extras/ttf/`. Each subset holds Basic Latin, Latin-1,
the dashes, quotes, bullets and spaces of General Punctuation, the euro,
the trademark, four arrows and the minus, and keeps the copyright and
license entries of the name table:

```bash
python -m fontTools.subset extras/ttf/Inter-Regular.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+0152-0153,U+2002-200A,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2030,U+2039-203A,U+20AC,U+2122,U+2190-2193,U+2212" --name-IDs="*" --flavor=woff --output-file=Inter-Regular.woff
```

The template copies the files `FONT` names into the project's `fonts/` and
lists them in `project.c3proj`. It stops when a file is in neither place,
because a missing font draws the game's Latin text in a serif face.

### The look

To be written with the template change: `PALETTE`, `FONT`, `TEXT_SIZE`, the
line-drawn areas and ranges, the header, stat and control helpers, and the
subjects' sizes.

## Open

- Whether the collectible takes the accent, an ink ring, or the cobalt of
  the plain sheet, and so whether a second accent stays: the owner's
  choice on screenshots.
- The Chinese fallback was seen on Windows only; on macOS, iOS and Android
  the platform's per-script default decides the face.

## Re-evaluate when

- The owner's reading of a generated game disagrees with the prototype.
- A game's Latin text shows in a serif face: a font file did not reach the
  project.
- A platform draws the fallback Chinese in a serif face.
- Claude's directory holds a plugin version for the font files.
