---
name: preview-project
description: Previews the project in the editor and plays it from a plan of steps, such as taps, holds, drags, key presses, waits and screenshots. It prints one line per step with the runtime errors. --keep saves a passing plan in tools/plans, --all replays every kept plan. Used to check what a player does.
argument-hint: "[PLAN.json] [--keep NAME] [--all] [--headed]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `preview_project.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" preview_project $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
