# The Generator Template Keeps Its Helpers, Refreshed in Place

Date: 2026-10-04

## Problem

The generator template, `assets/build_project.py`, is one file: the helpers
(one per ACE, the images, the grid, the layouts, the checks that stop a run)
and a stand-in game. An agent copies it into a game's `tools/` and rewrites
the game in it, so every copy keeps the helpers of the day it was made. Four
generated games read on 2026-10-04 each lacked helpers added since, among
them the guards that print the number to write.

Task: games receive the helpers' fixes, and small models stay as good at
changing a generated game as they are with the template.

## Evidence

Three eval iterations on the five generator cases of `evals/evals.json`
(Haiku 4.5, two runs per case and arm, the template of the day before as the
baseline in the same batch; `.local/docs/evidence/skill-evals/`
`construct3-agent-plugin/iteration-40/` to `iteration-42/`):

| Helpers | Pass rate | Baseline's |
|---------|-----------|------------|
| Imported from the skill, fifteen files by topic | 0.887 | 0.986 |
| Imported from the skill, one module | 0.73 | 0.976 |
| In the file, between two markers | 0.943 | 0.976 |

The runs with the helpers outside the file they edit guessed at the
helpers' interface: an anchor named `top-center`, a missing argument,
`drawn()` on an image that only `write_png()` drew. They ran their
generator 116 times where the template's runs ran it 67 times. The
template's runs read the file they edit three to twelve times, and its
helpers' code and docstrings are how they learn the interface.

Between the markers, the file holds the same helpers in the same words.
Those runs ran their generator 33 times against the template's 49, in
about the same time, and 9 of 10 left the marked part as it was. Their
loss was one case, reveal-the-gradient: one run drew the bar's gradient as
the 16x16 tile `bar_images()` makes, and one stretched a Sprite. In the
template, the bar helpers sit about 50 lines above `build_object_types()`
and `build_layouts()`, where a run writes the bar; in one marked block,
the game's functions sit about 500 lines below them. The two designs that
moved the helpers out of the file lost the same case.

## Options

1. The helpers in the template, copied with it. Small models read them;
   copies fall behind.
2. The helpers imported from the skill, in files by topic. Rejected by the
   evidence.
3. The helpers imported from the skill, in one module. Rejected by the
   evidence.
4. The helpers in the template between two markers, and the part between
   the markers replaced in a game's copy when the skill is refreshed.

## Decision

Option 4.

- The template holds the game's settings first (`PROJECT_NAME`, the
  viewport, the grid, `PALETTE` and the rest of the look), then the helpers
  between a begin and an end marker, then the game (`BEATS`, the
  `build_*()` functions, the `module_*()` functions of the sheet).
- The end marker carries the helpers' version, a date, and a stamp: the
  first 12 hex digits of the SHA-256 of the lines between the markers. A
  copy whose lines still match its stamp was not edited there.
- `install.py`, when it refreshes the skill, replaces the marked part of the
  project's `tools/build_project.py` when it is an older version and
  unedited, and keeps every line outside it, line ends included. An edited
  part stays as it is: the edits are the game's. install.py says to copy
  each changed helper below the end marker, where a def of the same name
  replaces the one between the markers, then to run it again with
  `--replace-edited-helpers`. `--helpers-only` refreshes the generator
  alone, for a project used through the Claude Code plugin, which holds no
  copy of the skill.
- `check_project.py`, and so every run of the generator, warns when the
  helpers are older than the skill's and prints the command that refreshes
  them. A generator copied before the markers is left as it is.
- The helpers import their own modules and read nothing from outside the
  markers but the settings and the game's functions that every generator
  has, because a refreshed game keeps its own settings: a setting that a
  new helper needs gets its default between the markers.
  `tests/test_skill_build_project.py` pins this and the stamp.

## Trade-offs

- In one marked block, the helpers sit apart from the game's functions that
  call them, which cost the reveal-the-gradient case above.
- A refresh can change a helper's interface under the game's code; the
  generator's next run then stops where the game calls it. install.py says
  to run the generator after a refresh.
- Versions are dates. Two versions of one day differ by their stamps only,
  and a refresh takes the skill's either way.

## Re-evaluate when

- A template that keeps its own order, each section of helpers between
  markers of its own, is measured against this one.
- A model in use reads an imported module's interface as readily as the
  file it edits.
- A refresh stops a game's generator because a helper's interface changed.
