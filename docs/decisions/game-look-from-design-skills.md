# The Game's Look: What Design Skills Do, and What the Generator Takes

Date: 2026-09-26
Schema: Construct 3 r495.2

## Problem

The generator template decided where things go (the grid, `anchor()`,
`hud_text()`, `row()`, `no_overlap()`, `hud_bar()`) and nothing about how a
game looks. It drew each image with RGB literals chosen one at a time, wrote
every label in white Arial at 32 px whatever the viewport, and left a
320×180 project at *Trilinear* sampling and a fractional letterbox scale,
which blurs pixel art.

Task: an agent that generates a game with no art direction gives it a look
that holds together, a few colours each with a role and labels that read at
any viewport, the way the grid gives it a layout that holds together. The
default path calls it: `SKILL.md`, "Generate a whole project", sends to
`references/generating-a-project.md` and `assets/build_project.py`.

## Evidence

### What design skills do

Fifteen skills in the Agent Skills format were read from their files, not
their READMEs: openai `game-studio` and `develop-web-game`,
awesome-gamedev-agent-skills, Claude-Code-Game-Studios, game-creator,
agentic-gamedev-skills, `godot-agent-vision`, anthropics `frontend-design`,
ui-ux-pro-max-skill, impeccable, interface-design, taste-skill,
`baseline-ui`, `design-review` and ux-ui-agent-skills.

- Most decide the look first, as a few named values the build reads, give
  every colour a role and keep the colours few, and look at the rendered
  result.
- Only one measures what it changes in an agent's output. It and the skill
  with the most machinery both put the rule where the agent writes, as a
  check that stops on a failure; in the measured one, those checks held
  while its critic still sent the work back.
- The web skills catalogue a generated page's generic look. The game skills
  name a game's failures: colours without a role, text unreadable over
  play, art at a scale that is not whole, the centre of the screen covered.
- Their finding matches this repository's: intent in prose loses to the
  patterns a model reaches for.

### What the official examples do

In the studio cohort of `Construct-Example-Projects` (the projects credited
to Viridino or Forsteri):

- A viewport 360 px high or less is pixel art: *Nearest* sampling at
  *Letterbox integer scale*, few colours, hard edges. Larger viewports
  sample *Trilinear*.
- Text is Arial or the project's own font, in about two sizes and two
  colours per project.

### A helper that draws art

`pixel_art()`, which drew icons from rows of characters, was tried and
removed. It settled what a check can settle (the colours, a box on the grid,
3:1 against the role behind it) but not the drawing, which changed from a
clean heart to an octagon between runs of one prompt; the user judged the
icons too crude for a default, and a default is what a small model repeats.
Without it, runs drew plain shapes in roles of `PALETTE` and scored as well.

## Options

1. **Install a third-party design skill beside this one.** The web skills
   hold a web page's failures, the game skills are prose for other engines,
   and a skill that installs others is not the user's to accept.
2. **A look section in the prompts.** Prose, which this repository has
   measured not to reach a small model.
3. **The look as values of the generator template, with checks where the
   generator writes.** What most of the fifteen share, in the form of the
   ones that check themselves.
4. **Checker warnings behind `--style` on colours, text sizes and
   sampling.** A sampling warning would fire on small projects that are not
   pixel art.
5. **A render-and-look loop** over the running game: the mechanism most
   skills share and the one with no counterpart here.
6. **A critic subagent or a model-scored rubric.** It finds what no check
   does and cannot be scored; an eval may use one, the flow does not need it.
7. **Copy an official example's art into the project.** The examples'
   images carry no names that say what an asset is or what part it plays,
   so an agent cannot choose one for a role.

## Decision

Option 3, with one bullet of option 2 in
`prompts/references/new-project.md`. In `assets/build_project.py`:

- `PALETTE`, the game's colours by role; `rgb(role)` stops the run on a role
  that is not there and lists those that are; `rgba()` writes a colour as a
  layout does. The roles and values are the blockout's
  (`greybox-blockout.md`).
- `write_png()` stops on a shown pixel whose colour is not in `PALETTE`,
  naming the nearest role and the two ways out: that role, or the colour
  added under the role it plays. `painted=True` lets a painting, a gradient
  or a photograph through.
- No helper draws art. The template draws stand-ins with `shape()` and
  leaves art to the user or to real assets.
- `FONT` and `TEXT_SIZE`: `body` one unit, `title` two. `text_inst()` and
  `hud_text()` take their size from it and stop below 4.5:1, or 3:1 from the
  title size up (WCAG 2.2, 1.4.3), naming the roles that would read.
- `PIXEL_ART` (a viewport 360 px high or less): *Nearest* sampling at
  *Letterbox integer scale*.
- `layer()` fills an opaque layer from a role, `canvas` unless named.

## Re-evaluate when

- A run passes `painted=True` for flat art: the way out is used as a way
  round; the message must say when it applies, or the flag goes.
- A label passes the contrast check and a user still cannot read it over
  play: check the colours under the label's box, not the layer's.
- The editor's preview is reachable from the session: try option 5,
  measured on the eval cases.
- A route to real art is built (CC0 packs or an image model): the icon
  checks, a box on the grid and 3:1 against the backdrop, go with it.
- A HUD sprite of one colour does not show on the layer behind it: check
  the UI layer's images in `no_overlap()`.
- The example clone updates: rerun the look survey.
