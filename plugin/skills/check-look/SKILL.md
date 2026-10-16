---
name: check-look
description: Confirms the strict rules of the skill's look manifest on a project built from the generator template. Used after the generator's own check ends with ok.
argument-hint: "[--painted [FILE ...]] [--unit PX]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `check_look.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" check_look $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
