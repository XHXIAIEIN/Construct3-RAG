---
name: search-guides
description: Prints the event sheet pitfall entries and the official example projects that hold the given words. Each example comes with the command that prints its events. Used before an interaction is written, and when events do not behave as expected.
argument-hint: "WORD [WORD ...] [--locale LOCALE]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `search_guides.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" search_guides $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
