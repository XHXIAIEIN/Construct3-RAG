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
the grid, `anchor()`, `hud_text()`, `row()`, `no_overlap()` and `hud_bar()`,
each measured in iterations 15 to 20 of `event-sheet-design-guidance.md`.
Nothing decided how a game looks. The template drew each image with RGB
literals chosen one at a time, wrote every label white Arial at 32 px
whatever the viewport, and left a 320×180 project at the editor's
*Trilinear* sampling and fractional letterbox scale, which blurs pixel art:
the style prompt said *Nearest* and *Letterbox integer scale*, and nothing a
small model runs held it to that.

Task: an agent that generates a game with no art direction gives it a look
that holds together, few colours each with a role and labels that read, at
any viewport, the way it gets a layout that holds together from the grid.

The default path calls it: `SKILL.md`, "Generate a whole project", sends to
`references/generating-a-project.md` and `assets/build_project.py`.

## Evidence

### The skills read

Found by web search for game UI, game art, pixel art, game feel and UI design
skills in the Agent Skills format, and read from shallow clones on
2026-09-26. `game-ui-ux`, `ui-ux-game` and `create-game-assets` were looked
at on 2026-09-22 for the grid (`event-sheet-design-guidance.md`, "placement
on a grid"); this pass reads them again for what they do about the look.

| Repository, commit | Read | What it holds | Evidence of its own effect |
|--------------------|------|---------------|----------------------------|
| openai/plugins `1dc1958`, `game-studio` | `game-ui-frontend`, `game-playtest`, `sprite-pipeline`, `references/frontend-prompts.md`, `playtest-checklist.md`, the three sprite scripts | Visual direction before code (fantasy, material, type, palette, motion) held as CSS variables; a HUD budget in numbers (one primary cluster, at most a fifth to a quarter of the viewport, the centre and lower middle clear); prompt recipes that end in an *Avoid* list; screenshots mandatory for a canvas game, findings in severity order; sprites generated as one strip from one approved seed frame, normalized by script to one scale and a bottom-centre anchor, a preview sheet before approval | None published |
| openai/skills `11c6438^`, `develop-web-game` | `SKILL.md` | Implement, act, pause, observe; `window.render_game_to_text()`, the visible state as JSON; `advanceTime(ms)` for deterministic steps; "treat the screenshots as the source of truth"; `progress.md` for the next agent. Removed from the curated set on 2026-04-23, the same commit that removed `frontend-skill`; `game-studio` covers the ground | None |
| gamedev-skills/awesome-gamedev-agent-skills `44888f2` | `game-ui-ux`, `game-feel`, `create-game-assets` and its brief, reference and `asset_report.py` | Anchors and containers, a reference resolution, safe areas; feedback in importance tiers, small to large, 5 to 8 responses within about 100 ms that return to rest; a technical frame locked first, palette roles with exact swatches, one visual target approved before a set, assets made as families, one change per pass, normalization by script, a report that exits 1 on size, alpha or colour count, a list of drift signals | Tests of the skill files and the asset scripts, not of what agents make |
| Donchitos/Claude-Code-Game-Studios `7ed2c3e` | `art-bible`, `asset-audit`, `agents/art-director.md` | A nine-section art bible written by an art-director agent a section at a time: a one-line visual rule with design tests ("when X is ambiguous, choose Y"), 5 to 7 colours each with a meaning, colour-blind backups; it refuses to start without an approved concept. The audit reports *not assessed* rather than invent a number | None |
| OpusGameLabs/game-creator `4e64b83` | `game-designer`, `visual-catalog.md`, `game-assets`, `pixel-renderer.md` | A score of 1 to 5 on fourteen areas, any area under 4 to be improved; every new value in `Constants.js`; a palette as a system of roles, not hex values; pixel art as a 2D array of palette indices drawn at runtime, one palette for every sprite, silhouette first, a 2 px outline, no rotation below 24 px | None |
| abagames/agentic-gamedev-skills `24a4cdc` | `directing-game-visuals` and its guide, `generating-dot-assets`, `gating-intent-legibility` | One protagonist, one danger, one reward before detail; 3 to 5 colours, each with a gameplay role; a still frame read without HUD text; palette roles and HUD anchors as runtime data a probe reads; pixel assets fitted to a palette file and validated for size and colour count; an isolated agent that never saw the source names the goal from captured frames and predicts one it has not seen, because "judging fun, taste, difficulty, or beauty" is what a blind grader rubber-stamps | Games built with the skills, in a companion repository |
| thedivergentai/GD-Agentic-Skills `4c4d0ff` | `godot-agent-vision` | Screenshots cut to WebP at a 512 px short edge to bound the tokens, scored on about 237 criteria of 0 to 2: contrast at its worst point, 4 to 6 colour roles, an accent on 5% to 15% of the frame, tabular figures on timers | None |
| anthropics/skills `3337550` | `frontend-design` | Ground the design in the subject; five looks generated pages fall into, hex codes included, named as defaults rather than choices; a plan of 4 to 6 named colours, type roles, a layout sketch and principles, reviewed against the brief ("would a similar prompt arrive somewhere similar") before any code; boldness spent in one place; screenshots to critique | Anthropic's article on the skill |
| nextlevelbuilder/ui-ux-pro-max-skill `dcc40ff` | `SKILL.md`, `data/colors.csv`, `products.csv`, `references/pro-rules.md` | CSV tables searched by a script; `--design-system` returns style, palette, type and anti-patterns for a product type, persisted to `MASTER.md` with per-page overrides, never overwritten without `--force`; palettes by role, each with an *On* colour for what sits on it, its provenance file saying not every pair was measured; game product types with role-named palettes ("coin gold + upgrade blue + prestige purple") | None |
| pbakaus/impeccable `9d715cc` | `skill/SKILL.src.md`, `reference/craft-floor.md`, the rule ids of `crates/detect` | `PRODUCT.md` and `DESIGN.md` loaded by one command; a craft floor read before each UI edit; 61 deterministic detectors run by a CLI, a browser extension and a hook after each edit, among them a colour not declared in `DESIGN.md`, low contrast, an overused font; blocks of rules per model family; verification in bounded rounds, at most one after the first | A fixture per detector in its tests |
| Dammyjay93/interface-design `2f9be32` | `SKILL.md`, `reference/system-template.md` | "Intent lives in prose, but code generation pulls from patterns"; swap, squint, signature and token tests; decisions saved to `.interface-design/system.md` and read first next time | None |
| Leonxlnx/taste-skill `c184364` | `taste-skill`, `gpt-tasteskill` | A one-line reading of the brief before code; three dials of 1 to 10 inferred from it; "motion claimed, motion shown" | None |
| ibelick/ui-skills `fd0889b` | `baseline-ui` | MUST, SHOULD and NEVER lines; a review that quotes the line at fault with its fix; one accent colour per view, tabular figures for data | None |
| OneRedOak/claude-code-workflows `6a65344` | `design-review` | A reviewer subagent that uses the live page first, at three widths, and sorts findings into blocker, high, medium and nit, with screenshots | None |
| plugin87/ux-ui-agent-skills `f2e2f7f` | `README.md`, the gate scripts | 44 objective gates behind one command, all or nothing, each held to reject a broken fixture; blind cold-start runs by two subagents given only the kit; an adversarial critic that renders the work, because "a passing gate is never evidence of taste" | The most of the fifteen: both blind runs passed its 14 output gates, and the critic still returned eight rework findings no gate measures (`evals/RESULTS.md`) |

### What they do to get stable, high-quality results

Counted over the fifteen above; a skill counts when its files do it, not
when its README says so.

| Mechanism | Skills | This repository before |
|-----------|-------:|------------------------|
| The look decided first, as a few named values the build reads | 9: `game-ui-frontend`, `frontend-design`, `create-game-assets`, `art-bible`, `game-designer`, `directing-game-visuals`, `interface-design`, `ui-ux-pro-max`, `taste-skill` | Grid and touch size as constants; no colour, type or sampling |
| Every colour has a role, and there are few | 8: `art-bible` 5 to 7, `directing-game-visuals` 3 to 5, `frontend-design` 4 to 6, `godot-agent-vision` 4 to 6, `game-assets` one palette, `create-game-assets`, `ui-ux-pro-max`, `game-designer` | RGB literals per image |
| Look at the rendered result | 9: `develop-web-game`, `game-playtest`, `game-designer`, `design-review`, `frontend-design`, `interface-design`, `godot-agent-vision`, `ux-ui-agent-skills`, `gating-intent-legibility` | `open_in_editor.py` opens the project, and `--shots` saves the editor window; nothing renders the game |
| The defaults named, to be avoided | 7: `frontend-design`, `impeccable`, `taste-skill`, `interface-design`, `game-ui-frontend`, `directing-game-visuals`, `baseline-ui` | The style prompt's habits table, for sheets |
| Decisions kept for the next session | 6: `impeccable`, `interface-design`, `ui-ux-pro-max`, `art-bible`, `directing-game-visuals`, `develop-web-game` | The generator, committed with the game, is the design |
| A check run where the agent writes, that stops on a failure | 5: `impeccable`, `ux-ui-agent-skills`, `create-game-assets`, `generating-dot-assets`, `sprite-pipeline` | The checker, `edit_sheet.py`'s refusals, `no_overlap()` |
| A numeric contrast floor, 4.5:1 for text | 4: `impeccable`, `ui-ux-pro-max`, `design-review`, `godot-agent-vision` (and the gates of `ux-ui-agent-skills`) | None |
| Generated art anchored on one approved frame, normalized by script | 3: `sprite-pipeline`, `create-game-assets`, `generating-dot-assets` | No image generation |
| Feedback scaled by the importance of the event | 3: `game-feel`, `directing-game-visuals`, `game-designer` | The *Feel* table, rows without tiers |
| A judge apart from the builder; taste judged, never scored | 4: `ux-ui-agent-skills`, `gating-intent-legibility`, `design-review`, `game-designer` | Evals graded by script, on structure |
| Dials that vary the result | 2: `taste-skill`, `ui-ux-pro-max` | None, and none wanted: the task is stability |

Three observations from reading them side by side:

1. Fourteen of the fifteen publish no measurement of what they change in
   an agent's output: what they share is a claim, not a result. The one
   that measures, `ux-ui-agent-skills`, and the one with the most
   machinery, `impeccable`, both put a rule where the agent writes, as a
   script held to a fixture it must fail on; and the blind trials found the
   gates held while the critic still sent the work back.
2. The web skills fight one failure, the generic look of a generated page,
   and most of their rules are its catalogue: fonts, gradients, cards,
   eyebrows. None of it names a Construct project's failures. The game skills
   name theirs: colours without a role, text unreadable over play, art at a
   scale that is not whole, the centre of the screen covered.
3. `interface-design` states the finding of this repository's own runs, that
   intent in prose loses to the patterns a model reaches for, which
   `skills/AGENTS.md` answers with the line a script prints and the
   template's defaults (`event-sheet-design-guidance.md`, "What small models
   read").

### What the official examples do

`Construct-Example-Projects` at `03d87043` ("Update example projects for
r495", 2026-07-21), 537 projects, 227 in the studio cohort told apart by the
Viridino or Forsteri credit in a comment of their sheets. Scripts and
outputs in `.local/docs/evidence/look-survey/` (`survey_look.py` over the
JSON, `survey_look.json` sha256 `3726eb0d`; `survey_palette.py` over every
PNG with Pillow, `survey_palette.json` sha256 `ac316410`).

| Question | Studio | The other 310 |
|----------|--------|---------------|
| Sampling and fullscreen mode at a viewport 360 px high or less | 159 projects: *Nearest* in all 159; *Letterbox integer scale* 116, *Letterbox scale* 43 | 55: *Nearest* 45, *Trilinear* 10; integer scale 7 |
| The same above 360 px | 68: *Trilinear* 58, *Nearest* 8, *Bilinear* 2 | 255, *Trilinear* 248 |
| Opaque colours across all the images of a pixel-art project | Median 35, ninetieth percentile 2 399 (painted backdrops); 9 cover 95% of the opaque pixels at the median, 3 at the tenth percentile | Median 74; 19 cover 95% |
| Semi-transparent pixels in a pixel-art project | Median share 0: hard edges | 0 |
| The same above 360 px | Median 34 667 colours, 7.6% semi-transparent: painted art | Median 1 089 |
| Colours per image, median of a pixel-art project | 2 | 6 |
| Sprite instances at a whole-number scale, pixel art | 6 407 of 7 055, 6 231 at 1; every instance whole in 114 of 150 projects | 657 of 846 |
| Text instances | 576 in 64 projects; 151 projects draw text with SpriteFont | 686 in 223 |
| Font | Arial 281, the rest the project's own (PublicPixel 40, Mat Saleh 39, Oswald 37, Pixeltype 15 at 320×180) | Arial 627 |
| Text sizes per project | Median 2, ninetieth percentile 4 | 1 and 2 |
| Text colours per project | Median 2, ninetieth percentile 3; white 382 of 576, black 55 | 1 and 2; black 526 |
| Sizes at 1920×1080 | 24 ×99, 32 ×89, 36 ×58, 48 ×57, 72 ×19; the smallest per project median 32 | |

## Options

1. **Install a third-party design skill beside this one.** Rejected for the
   reason of 2026-09-22: what the web skills hold is the catalogue of a web
   page's failures, and the game skills are prose for other engines; a skill
   that installs others is not the user's to accept.
2. **Prose: a look section in the prompts, with the skills' lists of what to
   avoid.** Kept to one bullet of `event-sheet-style.md`, *Project*, with the
   counts above, for the model that reads it. Alone it is the option this
   repository has measured not to reach a small model.
3. **The look as values of the generator template, and checks where the
   generator writes.** Chosen: what most of the fifteen share, a few named
   values decided first (nine) and a role for every colour (eight), in the
   form of the two that check themselves, a script where the agent writes,
   which is also the form iterations 15 to 20 found a small model follows.
4. **Checker warnings behind `--style`: colours per project, text sizes,
   *Trilinear* at a pixel-art viewport.** Not built. A generated project gets
   the template's checks; an edited one does not change its palette or its
   sampling; and a warning on sampling would fire on 10 of the 55 other
   projects at that size, some of which are not pixel art.
5. **A render-and-look loop**: capture the preview of the running game and
   the positions of its instances, `render_game_to_text` for Construct. The
   mechanism nine skills share and the one with no counterpart here. Not
   built in this change: the editor is out of this sandbox's reach
   (`editor.construct.net` answers 403 through its proxy), so neither the
   capture nor its effect could be run. The next decision.
6. **A critic subagent, or a rubric scored by the model.** Not taken: the
   one skill that measured it says the critic finds what no gate does and
   cannot be scored, and `gating-intent-legibility` says a blind grader
   rubber-stamps beauty. An eval can use one; the flow does not need it.
7. **Dials, image-generation pipelines, feedback tiers.** Dials serve
   variety, and the task is stability. Image pipelines need an image model
   in the session; their invariants (one approved seed, one scale, one
   anchor, a palette file, a size check) are recorded here for when the CC0
   and generation routes of 2026-09-22 are built. Tiers need a measurement of
   the studio's shake, flash and hit-stop magnitudes first.

## Decision

Option 3, with the one bullet of option 2.

`assets/build_project.py`:

- `PALETTE`, the game's colours by role, with the stand-in's colours as
  `background`, `panel`, `outline`, `text`, `reward`, `reward_shade`,
  `good` and `danger`; `rgb(role)`, which stops the run on a role that is
  not there and lists those that are; `rgba()`, a colour as a layout writes
  one, whole channels as integers.
- `write_png()` stops the run on a shown pixel whose colour is not in
  `PALETTE`, naming the pixel, the nearest role and the two ways out: that
  role, or the colour added under the role it plays. Alpha is free.
  `painted=True` lets a picture meant to hold its own colours through, a
  gradient or a photograph.
- No helper that draws art. `pixel_art()`, icons typed as rows of
  characters in the palette's roles, was built, run in iterations 21 and 22
  and taken out again: the icons it gave were not good enough to ship as a
  default (the section after iteration 22). The template draws stand-ins,
  one colour or a plain shape each, and leaves the art to the user or to
  real assets.
- `FONT` and `TEXT_SIZE`, two sizes on the grid, `body` one unit and
  `title` two: 32 and 64 at 720×1280, 8 and 16 at 320×180. `text_inst()` and
  `hud_text()` take their size from it, their colour and backdrop as roles,
  and stop the run below 4.5:1, or 3:1 from the title size up (WCAG 2.2,
  1.4.3), naming the roles that would read on that backdrop.
- `PIXEL_ART`, a viewport 360 px high or less: `build_project()` sets
  *Nearest* sampling and *Letterbox integer scale*.
- `layer()` fills an opaque layer from a role, `background` unless named,
  and a transparent one keeps the editor's white.

The stand-in project it writes is the same as before but for the text
colour and the transparent layers' white, written `1` as the editor writes
them instead of `1.0`.

`prompts/event-sheet-style.md`, *Project*: one bullet with the counts above.
`references/generating-a-project.md`, "Writing the generator": one habit.
`tests/test_project_tools.py`: the palette check and its message, alpha and
`painted`, the contrast check at both sizes and its message, the layers'
colours, the settings of a 320×180 viewport. `evals/evals.json` gains case
9, `readable-on-a-light-background`, graded by
`grade_readable_on_a_light_background()`.

## Iteration 21: two art cases and a light background, Haiku 4.5, three runs per arm

Fixture `coins-generator` (`make_fixtures.py`): `lay-out-the-hud` (a timer,
a pause button, three hearts), `lives-as-hearts` (five hearts, full and
empty, drawn in the generator) and the new
`readable-on-a-light-background` (a sky blue background, a `Left: 6` label,
"everything on screen has to stay easy to read"). `with_skill` is the
template of the decision above with `pixel_art(rel, rows, key, scale)`,
`old_skill` a worktree of `1823a9e`. Each run is a `claude -p` session of
`claude-haiku-4-5` (Claude Code 2.1.283) started in its project folder, so
it loads that folder's instruction file and nothing of this repository's,
given the case's prompt and the line asking for `outputs/answer.md`. Tokens
here are what a session processed, cache reads included, not the
subagent's count of iterations 11 to 20: compare them within these tables
only. Evidence: `.local/docs/evidence/skill-evals/construct3-project/iteration-21/`,
the images measured by `look_measures.py` beside them, `sheet.png` the
images each run drew.

| Case | old_skill | with_skill |
|------|-----------|------------|
| lay-out-the-hud (of 10) | 10, 10, 10 | 10, 7, 7 |
| lives-as-hearts (of 7) | 7, 7, 7 | 7, 7, 7 |
| readable-on-a-light-background (of 6) | 5, 6, 6 | 6, 6, 6 |

| Mean of the three cases | old_skill | with_skill |
|-------------------------|-----------|------------|
| Pass rate | 0.981 | 0.933 |
| Tool calls, lost | 19.2, 3.3 | 28.8, 4.6 |
| Seconds | 111 | 151 |

- Art. Every `with_skill` run that drew art drew it with `pixel_art()`,
  two calls each, in roles of `PALETTE`: none of its images holds a colour
  outside it, none passed `painted=True`, and the colour check of
  `write_png()` never fired. The `old_skill` runs drew with circles and
  distances and brought one or two colours per image of their own. Read
  side by side in `sheet.png`, five of the six `with_skill` hearts can be
  named as hearts, crude ones; of the six `old_skill` ones, a circle, a lump, a blob
  with a notch, two rings on a bar, a bow tie, and one heart a tenth the
  size of its image.
- The empty heart. All three `with_skill` runs of `lives-as-hearts` drew it
  in `outline` alone, 1.2:1 on the background: it is not there. The
  palette offered a role for an edge, and nothing said an edge alone does
  not show on the dark.
- Sizes. Two `lay-out-the-hud` runs sized the sprite from the image a
  scale gave, hearts of 81 and 99 px and buttons of 96×84 and 95×76, off
  the grid and the button under a finger: the three failed assertions of
  each. In `lives-as-hearts` the checker reported frames that did not match
  their files for the same reason. The rest of the extra calls are the rows:
  each run met "rows of [7, 8] characters" once to three times, then spent
  edits that did not match its own ASCII art finding the row.
- Contrast. One `with_skill` run met the check, white on sky blue 1.8:1,
  and changed the role `text` to dark navy, 9.2:1; the other two changed
  `text` with `background` before any check, the palette's comment saying
  labels are read against it. Two `old_skill` runs gave `text_inst()` a
  colour parameter and passed dark text; the third left white at 1.8:1.

So the palette and the contrast check did what they are for, and
`pixel_art()` did better art and worse layout: a scale is a menu, the box
on the grid is the default. Three changes followed the same day:
`pixel_art(rel, rows, key, w, h, on)` draws into its box, `TOUCH` square
unless given, at the largest whole-number scale, centred, and returns the
box; a ragged row is named with its text and length; and an icon none of
whose roles reads 3:1 on the role behind it (WCAG 2.2, 1.4.11) stops the
run with the roles that would.

## Iteration 22: `pixel_art()` in its box, three runs

The same two art cases with the template of those three changes,
`with_skill` three times; the `old_skill` runs of iteration 21 are the
baseline, their template unchanged. Evidence:
`.local/docs/evidence/skill-evals/construct3-project/iteration-22/`.

| Case | old_skill (iteration 21) | with_skill |
|------|--------------------------|------------|
| lay-out-the-hud (of 10) | 10, 10, 10 | 10, 10, 10 |
| lives-as-hearts (of 7) | 7, 7, 7 | 7, 7, 7 |

| Mean per run | lay-out-the-hud, old / new | lives-as-hearts, old / new |
|--------------|----------------------------|----------------------------|
| Tool calls, lost | 15.0, 3.3 / 21.0, 4.3 | 28.7, 6.0 / 34.7, 7.0 |
| Seconds | 76 / 90 | 178 / 185 |

Every image the runs drew is 96×96, the box on the grid, and every one
keeps to `PALETTE`. No run met a ragged row. The 3:1 check stopped five of
the six runs once: all three empty hearts drawn in `outline` alone, the
fault of iteration 21, and two pause buttons in `outline` or `panel`; each
run drew the icon again in a role that shows and passed. One run drew its
pause button with `write_png()` in `panel` alone, about 1.1:1 on the
background, which the check of `pixel_art()` does not see. The shapes
themselves are the model's drawing: two of the three pairs of hearts in
`lives-as-hearts` are hearts, the third two octagons; of the three hearts of
`lay-out-the-hud`, one is lopsided, one a blob, one half a heart.

## Update 2026-09-26: `pixel_art()` taken out

The user read the icons of iterations 21 and 22 and asked that the template
not prescribe images: what the helper drew is too ugly to be the default.
The measurements agree that the helper settled the parts a check can
settle, the colours, the size on the grid, an outline that shows, and not
the part that makes an icon good, its drawing, which varied from a clean
heart to an octagon between runs of one prompt. A template default is what
a small model follows every time (iterations 15 to 20), so a default that
draws crude art spreads crude art.

Taken out: `pixel_art()`, its example in `build_images()`, its test, its
sentence in `generating-a-project.md` and its name in the style bullet.
Kept: the palette and its check in `write_png()`, which draw nothing, the
contrast of labels, the text sizes and the pixel-art settings. An icon is
the user's art or a real asset; until one arrives, a stand-in of one colour
or a plain shape in a role of the palette, as the coin is.

## Re-evaluate when

- A run of a case that asks for art adds colours with `painted=True` to art
  that is flat: the way out is then taken as a way round, and the message
  needs to say when it applies, or the flag goes.
- A generated project's labels pass the contrast check and a user still
  cannot read them over the play: the backdrop of a HUD label is the layer
  behind it, not the layout's background, and the check needs the colours
  under the label's box.
- The editor is reachable from the session that changes this: option 5,
  with the preview's capture and its instances as text, measured on the
  cases of iterations 15 to 23.
- A route to real art is built, CC0 packs or an image model: the icon
  checks that worked in iteration 22, the box on the grid and 3:1 against
  the backdrop, go with it, not with art the template draws.
- A HUD sprite of one colour that does not show on the background, as the
  pause button of iteration 22 drawn in `panel`: a check of the UI layer's
  images against the layer behind, in `no_overlap()`, that lets a bar's
  frame through.
- The example clone updates: rerun the two survey scripts; the numbers in
  the template's comments and the style bullet come from them.
