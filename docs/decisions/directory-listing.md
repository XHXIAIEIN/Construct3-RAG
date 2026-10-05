# The Plugin Is Listed in Claude's Directory

Date: 2026-10-03

## Problem

The plugin reached Claude Code through this repository as a marketplace,
two commands that a reader had to find in the README. Claude's directory
lists plugins on claude.ai, in Cowork and in Claude Code, and adds one to
the account with a single click, but it serves only versions Anthropic has
reviewed.

## Evidence

The directory's submission portal validates and scans each commit it picks
up. Its holds for a reviewer come from the checklist's limits on the
plugin folder, the file count, the file size and bundled images, in
Claude's "Plugin pre-submission checklist"; `plugin/` is built to them
(`plugin-folder.md`). Its report on the repository root also gave two
warnings.

Warnings, both cleared on 2026-10-05:

- No `version` in `plugin.json`. It now has one
  (`plugin-tracks-commits.md`).
- A `CLAUDE.md` at the root, which a plugin does not load. The file is the
  entry point for agents working in this repository, so it moved to
  `.claude/CLAUDE.md`, which Claude Code loads as project instructions
  from the same place, and imports `../AGENTS.md`.

The portal reports that auto-publish does not apply to a version held for
a reviewer; whether it applies to `plugin/` waits for its re-validation.

## Options

- Directory only: one listing, but every change waits for a review.
- Marketplace only: tracks main, but nobody finds it outside the README.
- Both, the directory as the default route and the marketplace or a linked
  clone for following main.

## Decision

Both. The plugin folder `plugin/` is submitted as Construct3 and listed on
claude.ai, in Cowork and in Claude Code. The directory receives each commit
on the default branch through the GitHub push webhook, and a reviewer
publishes each version.

- A person adds it on claude.ai under Customize > Plugins. Claude Code
  signed in with that account downloads it at its next start and loads it
  as `construct3@synced`; its skill is `construct3:construct3-agent-plugin`
  as with every other route.
- `construct3@construct3-rag` from this repository and the clone linked
  under `~/.claude/skills/` stay for following main. When one of them is
  present, Claude Code loads it and reports the synced copy as not loaded
  (Claude Code docs, "Plugin loading reference", "Name conflicts"), so the
  routes do not stack.
- The directory serves the version a reviewer last published, which can
  be behind main by as long as a review takes. The README says so.

## Re-evaluate when

- The portal offers auto-publish for this plugin.
- Re-validation of `plugin/` still reports a hold (`plugin-folder.md`).
