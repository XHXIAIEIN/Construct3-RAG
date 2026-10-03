# Art from the Image Tool

Date: 2026-10-04
Schema: Construct 3 r495.2

## Problem

The generator template draws stand-ins, and the skill said nothing about
where the art comes from beyond "the user or real assets". The template's
own comment said that real projects draw with Pillow. So an agent asked for
a game that looks finished draws the art itself, in code, even when its
client has an image model it could call.

Task: an agent with an image generation tool makes the game's art with it,
and the art drops into the generated project without changing a layout or
an event; an agent without one keeps the stand-ins.

## Evidence

A small model whose client ships an image model built a card game from the
skill and drew all of its art in Pillow, even when asked outright to use its
image ability, because a script that writes `images/` at the sizes the
generator registers was the only route the skill showed. The art had four
drawing styles on one screen, and fifteen enemies were one shape template in
different colours; two redraws in code did not fix it.

Before Construct can use a picture of the image tool, it needs what the
model had no tool for: the background removed when the picture comes back
opaque, the subject trimmed and fitted to the box the layouts place, the
editor's file names, a hit frame, and a clear pixel holding no colour.

## Options

1. **A line in `SKILL.md`: use the image tool.** The model went back to
   Pillow when told so directly: without a way to fit a picture into the
   project, prose does not move it.
2. **Leave the cut-out and fitting to the agent.** Each run writes its own
   chroma key, the step a small model gets wrong (fringes, holes, the
   ground shadow it was told not to draw).
3. **`art()` in the template and `prepare_art.py` in the skill.** Chosen.
4. **Keep drawing the art in code.** The result above; rejected.
5. **The skill calls an image model.** Every client has its own tool, and
   the default path calls no model; rejected.

## Decision

Option 3.

- `art(file, kind, w, h, role, subject)` in `assets/build_project.py`
  declares a sprite by what its picture shows, in a box of whole units. It
  draws the stand-in `shape()` until `art/<file>` exists, then copies that
  picture in with the stand-in's box, origin and collision polygon: the
  layouts and events stay as they were. Kind `"scene"` is an opaque
  backdrop. The generator writes `art/wanted.json` and prints how many
  sprites still show their stand-in, with the command that prints their
  prompts.
- `ART_STYLE`, one sentence of art direction, leads every prompt, so the
  pictures share one style. With more than one sprite to make,
  `prepare_art.py --list` first asks for a key picture, a line-up of the
  subjects, shown to the user when they are there to choose one; it is the
  reference image of every later picture where the tool takes one.
- `scripts/prepare_art.py --list` prints a prompt per picture still to
  make, the aspect ratio to ask for, and where to save it, `art/raw/`. A
  sprite is asked for on a flat key colour, magenta, or green for a subject
  in pink or purple, with no ground shadow and no text.
- `scripts/prepare_art.py` keeps a picture's own transparency, or removes
  the key colour where it joins the edge and wherever it is exact,
  together with a shadow cast on it (the key colour darker), and blends
  the edge against the colour beside it. It refuses a picture whose edge
  is not one flat colour or whose subject runs off it, saying what to make
  instead, trims the subject, fits it into its box (on the box's bottom
  when the origin is at the feet), clears the colour under alpha 0, and
  writes the hit frame, the silhouette in the flash colour. It marks each
  file so that `check_look.py` lets its soft edges through.
- Without an image tool, the stand-ins stay. `SKILL.md`, the reference on
  generating a project and the look manifest say that art is not drawn in
  code.

## Open

- No run of a small model with an image tool has used the route yet; the
  pictures it was tested on are synthetic, made to fail the way model
  output does (a near-flat key, JPEG noise, a ground shadow, a subject
  over the edge).
- Pixel art: a picture is resampled and its alpha cut at half, not redrawn
  on the pixel grid.
- Tiled Backgrounds, 9-patches and the HUD's bars keep their drawn
  images; `art()` covers sprites and backdrops.
- Contrast of the art against the backdrop is the user's call on a
  screenshot, as `review_look.py` asks it; no check measures it.

## Re-evaluate when

- A run with an image tool still draws the art in code: the route needs a
  line in a tool's output, not only `SKILL.md`.
- A real picture leaves a fringe, a hole or a shadow: change the key
  thresholds against that picture, and add it to the tests.
- An image tool returns pictures with transparency as a rule: the key
  colour drops out of the prompt.
- The pictures of one game drift apart in style despite the key picture:
  generate several subjects on one picture and cut them apart.
