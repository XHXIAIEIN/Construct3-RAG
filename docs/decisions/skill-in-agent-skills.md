# The Skill, the Prompts and the Plugin Live in Construct3-Agent-Skills

Date: 2026-10-16

## Problem

This repository held two things with different readers and cadences. One
was the Construct 3 reference data with its update pipeline and lookup
service. The other was the `construct3-agent-plugin` skill with its
prompts, its tests and the Claude Code plugin built from them. Most of the
tests and most of the decision records were the skill's. A person who
looked the plugin up landed in the repository of the data pipeline. The
plugin's own repository, Construct3-Agent-Skills, was a mirror that a
workflow pushed after each change, and a mirror falls behind when its
workflow does not run.

The owner decided that the sources should live with the plugin. This
repository keeps the data, the pipeline and the service, and points agents
at the other repository as it points at the Construct3-Manual clone.

## Evidence

- No skill script or skill test imported the service. The build imported
  one tuple from `src/lookup/schema_layout.py`, the two locales, which the
  data's index also states.
- The skill reads `data/` from the folder its `Construct3-RAG:` line names.
  It finds the sibling clones beside the clone that holds it. A clone of
  this repository beside Construct3-Agent-Skills is read the same way.

## Options

- Keep the sources here and the mirror there. One build and one test
  suite, but the plugin's repository stays a copy, and a change to the
  skill is made in one repository and shipped from another.
- Move the sources there and give that repository a clone of this one
  beside it for the data. Each repository holds one thing; the build and
  the skill's tests need the second clone.
- Move the sources there with this repository as a Git submodule. A pinned
  data commit, but every checkout carries this repository's history, and a
  data refresh is a submodule bump plus a build.

## Decision

The second option. The skill, the plugin's sources, the skill's tests, the
build and the records of those live in Construct3-Agent-Skills. The event
sheet guides, which moved there as `plugin/prompts/`, have since moved again
to their own repository, Construct3-Cookbook (`guides/`), so that a new
pitfall reaches users without a plugin release (Construct3-Agent-Skills'
`docs/decisions/guides-in-cookbook.md`).
Its build reads `data/` from a clone of this repository beside it, and its
daily workflow rebuilds the plugin when the data changed. The history of
the moved files up to the move is in this repository's Git history.

This repository keeps:

- `data/`, `src/`, `scripts/init.py` and the update workflow, the docs and
  the records of those, and `scripts/reference_games/`, the study of
  published games, with its record.
- `README.md`, `README_CN.md` and `AGENTS.md`, which send an agent that
  wants to make a game to Construct3-Agent-Skills, and keep the data
  lookup here. Section 2 of `AGENTS.md` runs `lookup_ace.py` from the
  sibling clone's `plugin/` with `--rag .`, so the long schema files are
  still read through the script, against this clone's data.
- `scripts/example_usage.py`, which indexes the official examples with the
  skill's reader of event sheets, `c3project.py` of the sibling clone's
  `plugin/`. Without that clone it keeps the committed index.
- `.claude/agents/ace-lookup.md`, which runs the sibling clone's script.

The listing that serves the plugin, and its marketplace manifest, belong to
Construct3-Agent-Skills, whose records cover the submission and the
version.

The update pull request builds no plugin, and `schema_diff.py` scans
`src/`, `scripts/`, `docs/` and `AGENTS.md` for the ids a release broke.
The prompts and the skill, which quote ids too, are checked by the other
repository's checks on the plugin built from the merged data.

## Trade-offs

- An ACE lookup in this repository needs the Construct3-Agent-Skills clone
  beside it. Without it, an agent reads the schema files directly and has
  to read `plugins/system.json` and `plugins/_common.json` in parts.
- A release that breaks an id quoted in a prompt or a skill file is found
  by the other repository's daily refresh, a day after the merge here,
  instead of in this repository's update pull request.

## Re-evaluate when

- The update pull request should report the ids a release breaks in the
  prompts and the skill: have `schema_diff.py` scan the sibling clone too.
