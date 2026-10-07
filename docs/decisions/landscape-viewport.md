# The Generator Template's Viewport: 1920×1080 Landscape

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

The generator template, `skills/construct3-agent-plugin/assets/build_project.py`,
started every game at 720×1280 in portrait. The value came with the first
generator, written for a phone puzzle game, and no record argued for it.
Most of the user's players see a game on a desktop browser, where a
portrait stage fills a third of a landscape window. `prompts/references/new-project.md`
already gives 1920×1080 for art that is not pixel art.

## Options

1. **Keep 720×1280.** Right for a phone game; the wrong default for the
   players the user has.
2. **1920×1080 landscape.** The size `new-project.md` names, and the one
   whose 32 px grid the placement survey of the official examples measured
   (`event-sheet-design-guidance.md`). Chosen.
3. **1280×720.** Fewer pixels for the stand-in images, but a second size
   beside the one the guidance names, with a grid unit of its own to derive.

## Decision

`VIEW_W, VIEW_H = 1920, 1080` and `ORIENTATION = "landscape"`. The values
derived from the viewport follow without code changes: `UNIT` 32, `MARGIN`
32, `TOUCH` 160 (48 dp × 1080 / 360, a whole number of units), `PIXEL_ART`
off. A phone game sets 720×1280 and `"portrait"`, and gets `TOUCH` 96.

The tests pin the derived numbers at 1920×1080, and the HUD eval case and
`evals/grade.py` grade at that viewport. A fixture from an older skill,
an `old_` arm, still has 720×1280 and is graded against the new numbers.

## Re-evaluate when

- Most of the games the user builds with the skill are for phones.
- The stand-in's images at this size slow the generator enough to matter.
