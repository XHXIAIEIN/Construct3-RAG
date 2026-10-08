# Art from the Image Tool

Date: 2026-10-06
Schema: Construct 3 r495.2

## Problem

The generator template draws stand-ins, and the skill said nothing about
where the art comes from beyond "the user or real assets". The template's
own comment said that real projects draw with Pillow. So an agent asked for
a game that looks finished drew the art itself, in code, even when its
client had an image model it could call.

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

The cut-out was measured on eight real image-model pictures, one figure
each on magenta or green: two full-body illustrations, two in pixel art,
four small stills. Counted are the shown pixels within 3 px of a clear one
that lean to the key by more than 40 (the lowest keyed channel less the
highest other one):

| Picture | Alpha ramp on the distance from the key | Alpha from the lean to the key |
|---------|-----------------------------------------|--------------------------------|
| Illustration, green key | 255 | 0 |
| Illustration, magenta key | 116 | 1 |
| Pixel art, green and magenta | 4, 0 | 0, 0 |
| Four stills | 12 to 73 | 0 |

A ramp on the RGB distance from the key leaves half a blend of the key with a colour
far from it opaque and tinted, pink along green hair. Three ways of finding
a blend's alpha were compared on a figure whose matte is known:

| Method | Mean alpha error (levels) | Pixels off colour by over 40 |
|--------|---------------------------|------------------------------|
| Lean to the key | 0.33 | 2 |
| Tint score, the mean of the keyed channels less the others | 0.78 | 92 |
| Projection onto the subject's colour | 0.83 | 4 |

The lean is linear in the blend and leaves red under magenta and gold under
green opaque; the tint score calls red magenta and yellow green. The
projection also took more of the real pictures' edges.

Between strands of hair the key shows in shade, 66 to 89 from the edge's
colour, and does not join the background. The gap distance of 70 clears it
on the green illustration; 50 left it, and 90 cut into the subject of the
magenta illustration and into the edge of a green heart under green, 92
away. A hot-pink heart under magenta is 94 away. The edge's depth follows
the picture's size: at 1.4 and 2 times the size of the real pictures, 3 px
left key on the edge that 4 and 5 px cleared.

On white, a cut also erases the subject's whites. LANCZOS makes pixels in
colours the source never had: a light rim and a key tint.

What `--list` warns of was measured on the subjects of a card game that a
small model generated with `art()`, all in Chinese. Many end in "无文字" (no
text), which the prompt asks for too, so a word after a negation does not
count. Most name the outline that `ART_STYLE` names, so a style word that
`ART_STYLE` also names does not count. Three groups of enemies and the
buttons are one subject in several colours or elements. Text similarity of
the subjects does not find these groups: two different creatures scored
0.87, one creature in two elements 0.94. The same subject without its
colour and element words does. Printed all at once, that game's prompts
passed the output limit, and its key picture showed four cards that
differ only in colour.

A published sprite tool that draws several poses in one picture reports
four a picture as stable, and repeated or dropped subjects at nine and
twelve.

Whether the key picture can reach the image tool was tried on the clients
at hand. Codex CLI's built-in image tool takes a list of local picture
paths as references. Given two drawn characters, it drew both in one
picture, with features that the prompt did not describe. Given one, it
drew the same character in a new pose. Its pictures came back opaque, on
a magenta that varied by up to 20 levels per channel. A Claude Code
session has no image tool of its own, and the Figma connector's image
tool takes a prompt only. A chat client's agent mode edits from a list of
reference picture URLs. The pictures and calls are in
`.local/docs/evidence/w11-measurements/image-refs/`.

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
  pictures share one style.
- `scripts/prepare_art.py --list` prints the next step only, so that no
  picture is made before what it depends on. While `ART_STYLE` is empty, it
  asks for that. With more than one sprite to make and no
  `art/raw/_key.png`, it asks for the key picture: a line-up of four
  subjects, the first of each object before a second of one, shown to the
  user when they are there to choose one. Then it prints a prompt per
  picture still to make, the aspect ratio to ask for, and where to save it,
  `art/raw/`. A sprite is asked for on a flat key colour, magenta, or green
  for a subject in pink or purple, with no ground shadow and no text. Its
  prompt gives the key picture as the reference image, which sets the
  style and the palette and is not a picture to copy. A scene's prompt
  does not, because the key picture's background is the key colour.
- `--list` warns of three kinds of subject and prints the prompts all the
  same:
  - a sprite's subject that names a background or a shadow;
  - a subject that names text, or a drawing style that `ART_STYLE` does
    not;
  - three or more subjects of one kind and box that are the same without
    their colour, shade and element words.

  A word after "no", "without", "无" or "不含" does not count.
- `scripts/prepare_art.py` keeps a picture's own transparency. Otherwise it
  refuses a picture whose edge is not one flat colour, is neither key, or
  is crossed by the subject, saying what to make instead. It removes the
  key where it joins the edge, with a shadow cast on it (the key darker),
  and the key in shade wherever it shows through a gap. Each edge pixel,
  up to 3 px in from the background, or a pixel per 240 px of the
  picture's long side when that is more, is a blend of the background and
  the subject behind it. Its alpha is how far its lean lies below the
  background's, as a share of the gap between the background's lean and
  the subject's. Its colour is the pixel less its share of the
  background, divided by that alpha. Key light inside the
  subject gets the colour around it back. It refuses a cut that leaves
  more than 0.5% of the edge leaning to the key, naming the other key.
  Then it trims the subject, fits it into its box (on the box's bottom
  when the origin is at the feet) with alpha and colour scaled apart
  through a filter without negative lobes, clears the colour under alpha
  0, and writes the hit frame, the silhouette in the flash colour. It
  marks each file so that `check_look.py` lets its soft edges through.
  Its line counts the gap pixels and the recoloured ones.
- A refused picture is recorded in `art/refused.json` by a fingerprint of
  its bytes, so that a second run on it does not count it again. `--list`
  gives its prompt again with a sentence for the image tool on what the
  refused picture got wrong, and with the other key when the edge leaned
  to the first. After three
  refusals a picture keeps its stand-in, and both runs say so, count it
  and go on. A new subject in `art()` starts the count again.
- Without an image tool, the stand-ins stay. `SKILL.md`, the reference on
  generating a project and the look manifest say that art is not drawn in
  code.

## Open

- No run of a small model with an image tool has used the route. The
  real pictures behind the thresholds were not made in a session of this
  skill: the full-body ones are reduced to about half their size and to a
  palette, the stills to an eighth. They stay out of
  the repository: `tests/test_skill_prepare_art.py` runs on such a folder
  when `CONSTRUCT3_RAG_ART_PICTURES` names it, and on a known-truth figure
  always.
- A pixel that blends three colours, a strand over a shirt on the key, is
  unmixed as two and can take a wrong tint at part alpha. It shows where a
  palette rounds the blend.
- Pixel art: a picture is resampled and its alpha cut at half, not redrawn
  on the pixel grid.
- Tiled Backgrounds, 9-patches and the HUD's bars keep their drawn
  images; `art()` covers sprites and backdrops.
- Contrast of the art against the backdrop is the user's call on a
  screenshot, as `review_look.py` asks it; no check measures it.
- No game's whole set of pictures was made with the key picture as the
  reference, so whether it holds one style across them is untested. A
  client whose image tool takes no reference, such as a prompt-only one,
  gets the style from `ART_STYLE` alone. The English warning words were
  tried on subjects written for the tests, not on a model's run. The cap
  of three refusals and the four subjects of the key picture are choices;
  neither was measured on an image tool here.
- The buttons of the card game are one thing in several colours, as
  meant, and get the colour warning; it says that it applies to different
  things.

## Re-evaluate when

- A run with an image tool still draws the art in code: the route needs a
  line in a tool's output, not only `SKILL.md`.
- A real picture of the image tool is refused for its edge, or leaves a
  fringe, a hole, a shadow or a tint: put it in the folder of the
  real-picture test and change the thresholds in `prepare_art.py`, whose
  comments give what each was measured against.
- A subject in the key made darker, a dark magenta cloth under magenta,
  is taken for a gap. Then the gap rule needs the region's size or its
  link to the background.
- An image tool returns pictures with transparency as a rule: the key
  colour drops out of the prompt.
- The pictures of one game drift apart in style despite the key picture:
  generate several subjects on one picture and cut them apart.
- A warning fires on a subject that comes out right, or a subject comes
  out wrong without one: change the word lists in `prepare_art.py`, and
  add the subject to the ones above.
- A picture keeps its stand-in after three refusals that a fourth picture
  would have fixed, or the image tool itself refuses a prompt: the cap or
  the refusal's sentence needs that run's evidence.
