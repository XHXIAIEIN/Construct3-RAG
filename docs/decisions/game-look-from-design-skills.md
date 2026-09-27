# The Game's Look: What Design Skills Do, and What the Generator Takes

Date: 2026-09-26
Schema: Construct 3 r495.2

## Problem

The user asked for the agent skills on GitHub about game aesthetics and UI
design to be surveyed, for how they get an agent to stable, high-quality
results to be worked out, and for what works to be brought into this
repository's flow.

The flow had the logic of a sheet (`event-sheet-thinking.md`), its style
(`event-sheet-style.md`) and, in the generator template, where things go:
the grid, `anchor()`, `hud_text()`, `row()`, `no_overlap()` and `hud_bar()`.
Nothing decided how a game looks. The template drew each image with RGB
literals chosen one at a time, wrote every label white Arial at 32 px
whatever the viewport, and left a 320×180 project at the editor's
*Trilinear* sampling and fractional letterbox scale, which blurs pixel art.

Task: an agent that generates a game with no art direction gives it a look
that holds together, few colours each with a role and labels that read, at
any viewport, the way it gets a layout that holds together from the grid.
The default path calls it: `SKILL.md`, "Generate a whole project", sends to
`references/generating-a-project.md` and `assets/build_project.py`.

## Evidence

### What the skills do

Fifteen skills in the Agent Skills format, read from shallow clones on
2026-09-26: openai/plugins `game-studio`, openai/skills `develop-web-game`,
gamedev-skills/awesome-gamedev-agent-skills, Donchitos/Claude-Code-Game-Studios,
OpusGameLabs/game-creator, abagames/agentic-gamedev-skills,
thedivergentai/GD-Agentic-Skills `godot-agent-vision`, anthropics/skills
`frontend-design`, nextlevelbuilder/ui-ux-pro-max-skill, pbakaus/impeccable,
Dammyjay93/interface-design, Leonxlnx/taste-skill, ibelick/ui-skills
`baseline-ui`, OneRedOak/claude-code-workflows `design-review`,
plugin87/ux-ui-agent-skills. A skill counts when its files do it, not when
its README says so.

| Mechanism | Skills | This repository before |
|-----------|-------:|------------------------|
| The look decided first, as a few named values the build reads | 9 | Grid and touch size as constants; no colour, type or sampling |
| Every colour has a role, and there are few (3 to 7) | 8 | RGB literals per image |
| Look at the rendered result | 9 | `open_in_editor.py --shots` saves the editor window; nothing renders the game |
| The defaults named, to be avoided | 7 | The style prompt's habits table, for sheets |
| Decisions kept for the next session | 6 | The generator, committed with the game, is the design |
| A check run where the agent writes, that stops on a failure | 5 | The checker, `edit_sheet.py`'s refusals, `no_overlap()` |
| A numeric contrast floor, 4.5:1 for text | 4 | None |
| Generated art anchored on one approved frame, normalized by script | 3 | No image generation |
| A judge apart from the builder; taste judged, never scored | 4 | Evals graded by script, on structure |
| Dials that vary the result | 2 | None, and none wanted: the task is stability |

- Fourteen of the fifteen publish no measurement of what they change in an
  agent's output. The one that measures, `ux-ui-agent-skills`, and the one
  with the most machinery, `impeccable`, both put a rule where the agent
  writes, as a script held to a fixture it must fail on; and the blind
  trials of the first found its gates held while its critic still sent the
  work back.
- The web skills catalogue the generic look of a generated page: fonts,
  gradients, cards. The game skills name a game's failures: colours without
  a role, text unreadable over play, art at a scale that is not whole, the
  centre of the screen covered.
- `interface-design` states this repository's own finding, that intent in
  prose loses to the patterns a model reaches for.

### What the official examples do

`Construct-Example-Projects` at `03d87043` (r495), 537 projects, 227 in the
studio cohort told apart by the Viridino or Forsteri credit in their sheets.

| Question | Studio | The other 310 |
|----------|--------|---------------|
| Sampling and fullscreen mode at a viewport 360 px high or less | 159 projects: *Nearest* in all; *Letterbox integer scale* 116 | 55: *Nearest* 45, *Trilinear* 10; integer scale 7 |
| The same above 360 px | 68: *Trilinear* 58 | 255, *Trilinear* 248 |
| Colours covering 95% of the opaque pixels of a pixel-art project, median | 9 | 19 |
| Semi-transparent pixels in a pixel-art project | Median share 0: hard edges | 0 |
| Font | Arial 281, the rest the project's own | Arial 627 |
| Text sizes, text colours per project | Median 2 and 2 | 1 and 2 |
| Sizes at 1920×1080 | 24, 32, 36, 48, 72; the smallest per project median 32 | |

### What the runs showed

Haiku 4.5, three runs per arm, on cases that ask for a HUD, hearts for
lives, and labels on a light background:

- The palette check held: no run's image held a colour outside `PALETTE`,
  none passed `painted=True`, and a label that read 1.8:1 was fixed from the
  check's message.
- A helper that drew icons from rows of characters, `pixel_art()`, gave
  better art than the runs drew alone and settled what a check can settle:
  the colours, a box on the grid, an icon that reads 3:1 on the role behind
  it. It did not settle the drawing, which went from a clean heart to an
  octagon between runs of one prompt. The user read the icons as too crude
  to be a default, and a default is what a small model repeats.
- Without it, the runs drew stand-ins of plain shapes in roles of
  `PALETTE`, and the cases scored as on the previous template.

## Options

1. **Install a third-party design skill beside this one.** What the web
   skills hold is the catalogue of a web page's failures, the game skills are
   prose for other engines, and a skill that installs others is not the
   user's to accept.
2. **Prose: a look section in the prompts.** Kept to one bullet of
   `event-sheet-style.md`, *Project*. Alone it is the option this repository
   has measured not to reach a small model.
3. **The look as values of the generator template, and checks where the
   generator writes.** Chosen: what most of the fifteen share, in the form
   of the two that check themselves.
4. **Checker warnings behind `--style` on colours, text sizes and sampling.**
   A generated project gets the template's checks, and a warning on sampling
   would fire on projects at that size that are not pixel art.
5. **A render-and-look loop** that captures the running game and the
   positions of its instances. The mechanism nine skills share and the one
   with no counterpart here.
6. **A critic subagent, or a rubric scored by the model.** The one skill
   that measured it says the critic finds what no gate does and cannot be
   scored; an eval can use one, the flow does not need it.
7. **A helper that draws art.** Tried as `pixel_art()`; see "What the runs
   showed".

## Decision

Option 3, with the one bullet of option 2. `assets/build_project.py`:

- `PALETTE`, the game's colours by role; `rgb(role)` stops the run on a role
  that is not there and lists those that are; `rgba()` writes a colour as a
  layout does. The roles and their values are the blockout's
  (`greybox-blockout.md`).
- `write_png()` stops the run on a shown pixel whose colour is not in
  `PALETTE`, naming the nearest role and the two ways out: that role, or the
  colour added under the role it plays. `painted=True` lets a painting, a
  gradient or a photograph through.
- No helper draws art. The template draws stand-ins with `shape()` and
  leaves the art to the user or to real assets.
- `FONT` and `TEXT_SIZE`, `body` one unit and `title` two: 32 and 64 at
  720×1280, 8 and 16 at 320×180. `text_inst()` and `hud_text()` take their
  size from it and stop the run below 4.5:1, or 3:1 from the title size up
  (WCAG 2.2, 1.4.3), naming the roles that would read.
- `PIXEL_ART`, a viewport 360 px high or less: the project samples
  *Nearest* at *Letterbox integer scale*.
- `layer()` fills an opaque layer from a role, `canvas` unless named.

`prompts/event-sheet-style.md`, *Project*, carries the counts above in one
bullet, `references/generating-a-project.md` one habit, and `evals/evals.json`
the case `readable-on-a-light-background`.

## Re-evaluate when

- A run adds colours with `painted=True` to art that is flat: the way out is
  taken as a way round, and the message needs to say when it applies, or the
  flag goes.
- A label passes the contrast check and a user still cannot read it over the
  play: the check then needs the colours under the label's box, not the
  layer's.
- The editor's preview is reachable from the session: option 5, measured
  on the eval cases.
- A route to real art is built, CC0 packs, a kit of the examples or an image
  model: the icon checks, a box on the grid and 3:1 against the backdrop, go
  with it.
- A HUD sprite of one colour does not show on the layer behind it: a check
  of the UI layer's images in `no_overlap()`.
- The example clone updates: rerun the look survey; the numbers in the
  template's comments and the style bullet come from it.
