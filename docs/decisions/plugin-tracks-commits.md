# The Plugin Tracks Commits and Needs No Copy in the Project

Date: 2026-10-02

## Problem

A game project held its own copy of the skill, made by `install.py`. The
copy fell behind the clone between refreshes: on 2026-10-02 one game's copy
lacked five files the clone had changed, and the sessions working in it read
the old `SKILL.md` until the checker's drift line was acted on.

The plugin route had the same problem in another place. `plugin.json`
pinned `"version": "0.1.0"`, and Claude Code computes a plugin's version
from that field before anything else, so `claude plugin update` left every
install on its first copy however many commits followed
(Claude Code docs, "Plugin loading reference", "Versions and updates").

## Decision

- `plugin.json` has no `version`. A GitHub install is versioned by commit,
  and `claude plugin update construct3@construct3-rag` brings it to the
  latest one. `claude plugin validate` warns that no version is set; the
  warning is accepted.
- On a machine with the clone, the marketplace is the clone itself
  (`claude plugin marketplace add <the clone>`). Claude Code loads a
  relative-path plugin of a local-directory marketplace in place, at every
  session start, whatever its version, so a `git pull` reaches the next
  session and there is no copy to fall behind.
- A project used with the plugin holds no copy of the skill; its
  `AGENTS.md` names the scripts under the clone's
  `skills/construct3-agent-plugin/`. `SKILL.md` and `AGENTS.md` section 4
  tell an agent that sees the skill as `construct3:construct3-agent-plugin`
  not to install one.

## Trade-offs

- Without a pinned version, a GitHub install has no release boundary: an
  update takes whatever main holds. The repository has no release process
  for the plugin that a version number would mark.
- `install.py` and the copy stay for other agents and for Claude Code
  without the plugin; nothing about them changed.
- Plugin loading costs no network at session start: the plugin is read from
  the cache or, in place, from the clone.
