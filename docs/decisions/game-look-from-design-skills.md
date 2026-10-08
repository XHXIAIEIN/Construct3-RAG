# The Game's Look: What Design Skills Do, and What the Generator Takes

Date: 2026-10-04
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

### A generated card game

A small model built a card game from this skill, with the generator's look
values, and previewed four scenes with screenshots. The screenshots showed
labels cut by boxes too narrow for them, the names and descriptions of five
cards stacked on one card while the others showed none, a subtitle drawn over
the title, a name over the enemy it names, the hero inside the hand, every map
node with the same icon, one decoration repeated on every layout, and four
drawing styles at once. The model reported the menu as rendering normally.
Most of these are measurable from the runtime: run over the same project,
the instance checks below found the cut labels, the stacked card texts, a
price over a card's name and a wrapped score line; the rest showed only in
the picture. Run over the official examples, the same checks found nothing
once their exceptions were in place.

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
   skills share. `scripts/preview_project.py` makes it reachable: the
   runtime gives every instance's box, layer, text size and frame.
6. **A critic sub-agent that judges the look freely, or a model-scored
   rubric.** It finds what no check does and cannot be scored; an eval may
   use one, the flow does not need it.
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
- No helper draws art. The template draws stand-ins with `shape()`, and
  `art()` puts the art of the image tool or the user in their boxes
  (`art-from-the-image-tool.md`).
- `FONT` and `TEXT_SIZE`: `body` one unit, `title` two. `text_inst()` and
  `hud_text()` take their size from it and stop below 4.5:1, or 3:1 from 18 pt
  up (`text_contrast()`; WCAG 2.2, 1.4.3), naming the roles that would read.
- `PIXEL_ART` (a viewport 360 px high or less): *Nearest* sampling at
  *Integer scale outer*, which fills the screen (`fill-the-screen.md`).
- `layer()` fills an opaque layer from a role, `canvas` unless named.

Option 5, as a mechanical report and a fixed checklist, after the editor's
preview became reachable: `scripts/review_look.py` previews the project,
visits every layout through the runtime, takes a screenshot of each and
prints

- one line per measured fault, naming the layout, the object type, the UID
  and what to change: a text its box cuts, instances of one type on one box,
  overlaps on the HUD and texts over texts, a HUD instance the screen's edge
  cuts, kinds of a Sprite type shown with one frame. Each rule fired on an
  official example until an exception covered it, and the exception is in
  the rule: a text and its shadow, an overlay over half the screen, an
  instance waiting wholly off screen, art running off the edge of a world
  layer, hidden state such as a mine's, a kind told apart by its label.
- a fixed list of yes/no questions about what a player sees as a mistake,
  each yes naming the object to change: text cut, too small, too faint or
  hidden, an object over a text, a button or a card's face, the HUD cut by
  the screen's edge, a stand-in or an object drawn in a style of its own, a
  backdrop that catches the eye before what the player acts on, kinds that
  look alike, decoration repeated on every layout. Their wording comes from
  a judge's agreement with the user's own labels
  (`look-judge-calibration.md`).

The script also writes `brief.md` beside the screenshots: the screenshots,
the questions and the form of the answer, for a reviewer that has not seen
the project. Its last line tells an agent that can start a sub-agent to give
it the brief and take each yes from its reply; another agent answers the
questions itself. The model that built the card game above judged its own
screenshots by what it meant to build. On another generated card game, where
the measured checks found nothing, a sub-agent given only the brief answered
yes for text drawn over the map's nodes and a panel over the shop's cards,
both visible on the screenshots. Its reply of a few hundred tokens takes the
place of the screenshots, about 1 200 image tokens each, in the main agent's
context, at the cost of the sub-agent's own run.

The script judges no taste and calls no model; the default path stays
offline apart from the editor, as the opener is. A sub-agent given the brief
answers the same fixed questions the agent would. Option 6 stays out of the
flow: a free critic or a scored rubric is a second model to run and
calibrate, while a small model reading tool output answers concrete
questions.

## Re-evaluate when

- A run passes `painted=True` for flat art: the way out is used as a way
  round; the message must say when it applies, or the flag goes.
- A label passes the contrast check and a user still cannot read it over
  play: check the colours under the label's box, not the layer's.
- A finding line fires on an official example or a user's game where the
  picture shows nothing wrong: narrow the rule, or drop it.
- An agent answers the questions "no" over a screenshot that shows the
  fault: the question is not concrete enough for it, or option 6 is due,
  measured on the set of `look-judge-calibration.md`.
- A fault the picture shows recurs across generated games and the runtime
  can measure it: it becomes a finding line.
- Most faults sit in scenes `goToLayout` cannot reach: let the script play a
  plan to a scene before it reviews it.
- The art of the image tool reads poorly against the backdrop on the
  user's screenshots: a 3:1 check of a picture against the backdrop goes
  into `prepare_art.py`.
- A HUD sprite of one colour does not show on the layer behind it: check
  the UI layer's images in `no_overlap()`.
- The example clone updates: rerun the survey under "What the official
  examples do".
