# The Generator Template Keeps Its Helpers

Date: 2026-10-04

## Problem

The generator template, `assets/build_project.py`, is one file: the helpers
(one per ACE, the images, the grid, the layouts, the checks that stop a run)
and a stand-in game. An agent copies it into a game's `tools/` and rewrites
the game in it, so every copy keeps the helpers of the day it was made. Four
generated games read on 2026-10-04 each lacked helpers added since, among
them the guards that print the number to write. The largest generator held
2791 lines, past the 2000 lines a file tool shows at once.

Task: games receive the helpers' fixes, and small models stay as good at
changing a generated game as they are with the template.

## Evidence

Two eval iterations on the five generator cases of `evals/evals.json`
(Haiku 4.5, two runs per case and arm, the template as the baseline in the
same batch; `.local/docs/evidence/skill-evals/construct3-agent-plugin/`
`iteration-40/` and `iteration-41/`):

| Helpers | Pass rate | Template's pass rate |
|---------|-----------|----------------------|
| Imported from the skill, fifteen files by topic | 0.887 | 0.986 |
| Imported from the skill, one module | 0.73 | 0.976 |

The runs with the helpers outside the file they edit guessed at the
helpers' interface: an anchor named `top-center`, a missing argument,
`drawn()` on an image that only `write_png()` drew. They ran their
generator 116 times where the template's runs ran it 67 times. The
template's runs read the file they edit three to twelve times, and its
helpers' code and docstrings are how they learn the interface.

## Options

1. The helpers in the template, copied with it. Small models read them;
   copies fall behind.
2. The helpers imported from the skill, in files by topic. Rejected by the
   evidence.
3. The helpers imported from the skill, in one module. Rejected by the
   evidence.
4. The helpers in the template between two markers, and the part between
   the markers replaced in a game's copy when the skill is refreshed. The
   file the model reads stays as it is. Not built.

## Decision

Option 1: the helpers stay in the file that the agent edits. Option 4 is
the route for copies that fall behind.

## Re-evaluate when

- Option 4 is built and evaluated.
- A model in use reads an imported module's interface as readily as the
  file it edits.
