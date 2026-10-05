# The Plugin's Version and Why a Project Needs No Copy

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

- `plugin.json` carries a `version`, `1.0.0` since 2026-10-05. Until then
  it had none, so that a GitHub install was versioned by commit and
  `claude plugin update construct3@construct3-rag` reached every commit.
  Claude's directory warns about a plugin without a version
  (`directory-listing.md`), so the field came back. A change that a
  marketplace install should receive raises the version; without that,
  `claude plugin update` keeps the install where it is.
- On a machine with the clone, the clone's plugin folder, `<clone>/plugin`
  (`plugin-folder.md`), is linked as `~/.claude/skills/construct3` (a
  junction on Windows). Claude Code loads a plugin directory under
  `~/.claude/skills/` in place as `construct3@skills-dir`, so a `git pull`
  reaches the next session and there is no copy to fall behind. The docs
  say a local-directory marketplace loads in place too, but Claude Code
  2.1.287 copied the whole clone, 3.0 GB with the ignored `.cache/` and
  `.local/`, into `~/.claude/plugins/cache/` when the clone was added as a
  marketplace whose plugin source was the repository root.
- A project used with the plugin holds no copy of the skill; its
  `AGENTS.md` names the scripts under the plugin's
  `skills/construct3-agent-plugin/`. `SKILL.md` and `AGENTS.md` section 4
  tell an agent that sees the skill as `construct3:construct3-agent-plugin`
  not to install one.

## Trade-offs

- A marketplace install lags main until someone raises the version, and
  the repository has no release process that would raise it. The linked
  clone does not depend on the version and follows every `git pull`.
- `install.py` and the copy serve other agents and Claude Code without the
  plugin.
- Plugin loading costs no network at session start: the plugin is read from
  the cache or, through the link, from the clone. `claude plugin details
  construct3@skills-dir` lists one skill and about 240 always-on tokens.
