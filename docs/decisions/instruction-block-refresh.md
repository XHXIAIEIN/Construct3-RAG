# The Instruction Block Is Versioned and Refreshed in Place

Date: 2026-10-08

## Problem

`install.py` writes the Construct 3 block, `assets/game-project-block.md`,
into a game project's `AGENTS.md`. The block is what every session of the
project reads first: its first step sends the agent to the skill and the
checker, and its table names the file for each kind of work
(`project-tools-skill.md`). A block copied into a project keeps the text of
the day it was copied, and the skill's block changed nine times in the
twelve days after `install.py` first wrote it.

Task: a project's block follows the skill's, and a block the project edited
keeps its edits.

## Evidence

The game projects on the maintainer's machine that `install.py` set up held
its block unchanged: two of the newest version, and two of an older one
that lacks the row for adding a file to the project. The other projects
there held a block placed by hand or edited, with wording no version of the
skill wrote. None had markers.

## Options

1. Write the block once and leave it. A project falls behind without
   notice.
2. Write the block again on every install. A project's edits are lost.
3. Mark the block and refresh it when it is unedited, as the generator's
   helpers are (`generator-helpers-inline.md`).
4. Keep the block out of the project and import it from the clone. Only
   Claude Code follows an `@` import, and the block names the folder of the
   project's own copy of the skill.

## Decision

Option 3.

- The block sits between a begin and an end marker, HTML comments of one
  line each, which a rendered `AGENTS.md` does not show. The begin marker
  tells a reader of the raw file to write the project's own instructions
  outside the markers.
- The end marker carries the block's version, which is a date, and a
  stamp: the first 12 hex digits of the SHA-256 of its text. The text leaves
  out the lines that name a clone's folder (`Construct3-RAG:`, the sibling
  clones, `path-to =`) and reads the folder the skill was installed in as
  the template writes it. Filling in the path, a line that names a clone's
  folder that `bootstrap.py` or the user adds, and `--into .claude/skills`
  are not edits. `tests/test_skill_install.py` fails until the template's end
  marker carries the stamp of its text.
- `install.py` replaces an older block whose text matches its stamp, and
  keeps its lines that name a clone's folder and every line outside it. A
  refreshed block names the copy of the skill the project holds, else the
  folder the old block named, under the skill's current name.
  `--block-only` refreshes the block alone, for a project used through the
  Claude Code plugin.
- An edited block is left as it is. `install.py` lists the lines that
  differ: from the block as written, when the clone's Git history holds that
  version, else from the skill's. `--replace-edited-block` takes the
  skill's once the project's own lines are below the end marker. A block of
  a newer version than the skill's asks for an update of the clone.
- A block written before the markers is refreshed when its text is exactly
  one that `install.py` wrote. `PAST_BLOCKS` in `scripts/c3project.py`
  holds the stamps of those texts and their lengths, which find where such a
  block ends; the list is closed, since every later block has markers. Any
  other text that names the clone is the project's: `install.py` leaves it
  and says that no refresh reaches it. A block from before the markers whose
  text is the skill's current one counts as current.
- `check_project.py` warns beside its warning about the generator's
  helpers: an older block, with `install.py --block-only`; an edited one
  with a newer version to take, with the same command, which lists the
  lines, and `--replace-edited-block`. A block whose markers are broken is
  named too, since nothing can refresh it. An edit with nothing newer to
  take, and an instruction file without a block that `install.py` wrote,
  say nothing.

## Trade-offs

- One changed word keeps a block from every refresh until the project's
  lines move below the end marker.
- Without the clone's history, as in the plugin cache, the listing of an
  edited block mixes the project's edits with the skill's own changes.
- A block placed by hand before the markers is never refreshed; replacing
  it with the template, markers included, is the user's step.

## Re-evaluate when

- A client in use shows HTML comments in an instruction file, or drops
  them before a model reads the file.
- Projects need text of their own inside the block, for example a row of
  the table.
