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

## Decision

- Player height: no default and no warning. Within one way of moving,
  the size varies about fivefold, and one studio's scale fills most of the
  sample, so a single default would copy that studio. The borrowed height
  for a platformer, 8%, agrees with the examples' median; the others have
  no counterpart here.

## Re-evaluate when

- A generated game's player falls outside the examples' range and reads
  wrong in a preview, or a template for one genre is added: it takes that
  genre's median.
