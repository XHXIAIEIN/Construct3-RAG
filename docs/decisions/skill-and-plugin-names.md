# The Skill Is `construct3-agent-plugin`, the Plugin `construct3`

Date: 2026-10-02

## Problem

The skill folder `skills/construct3-project/` is also what a Claude Code
plugin lists. A plugin named `construct3-project` would show the skill as
`construct3-project:construct3-project`. The plugin name is permanent once
submitted to the directory, so it was settled first.

## Decision

- Plugin `construct3`, marketplace `construct3-rag`: `construct3@construct3-rag`
  installs it.
- Skill `construct3-agent-plugin`, folder and `name` alike, as the Agent
  Skills format requires. Its full name is `construct3:construct3-agent-plugin`.

## Consequence

A copy installed in a game project under the old folder name,
`construct3-project`, keeps working but no longer finds its source in the
clone, so it prints no drift message. Run `install.py` from the clone once
to get the renamed copy and delete the old folder.
