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
up, and its report on this repository lists two findings that hold a
version for a reviewer and two warnings. The limits behind them are in
Claude's "Plugin pre-submission checklist".

Held for a reviewer:

- More than 512 files in the plugin folder, and files over 256 KiB. The
  plugin folder is the repository root, so `data/` counts, and the schemas
  are what the plugin is for.
- Files that name images of a game project: the icons of
  `data/c3-new-project/project.c3proj`, and the image paths that
  `check_project.py`, its tests and `checker-rules.md` read. A Construct
  project is made of such files.

Warnings:

- No `version` in `plugin.json` (`plugin-tracks-commits.md`).
- `CLAUDE.md` at the root is not loaded by the plugin. It is the entry
  point for agents working in this repository, not context for the plugin.

The portal therefore reports that auto-publish does not apply.

## Options

- Directory only: one listing, but every change waits for a review.
- Marketplace only: tracks main, but nobody finds it outside the README.
- Both, the directory as the default route and the marketplace or a linked
  clone for following main.

## Decision

Both. The repository root is submitted as Construct3 and listed on
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
- The plugin folder falls under the file-count and file-size limits, for
  example as a subfolder that carries only the skill and the data it reads.
  The skill's scripts find `data/` in the folder above them that holds
  `data/c3-schemas/_index.json`, so that is a change to the scripts too.
  The image-path finding stays as long as the checker reads a project's
  images.
