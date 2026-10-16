---
name: lookup-ace
description: Prints the conditions, actions and expressions of an object of the project, of System, or of a plugin or behavior. Each comes with its parameters, the JSON to write and the official examples that use it. Given an effect, it prints the effect's parameters. Used before an ACE is written into an event sheet, in place of opening plugins/system.json.
argument-hint: "OBJECT [WORD ...] [--locale LOCALE]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `lookup_ace.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" lookup_ace $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
