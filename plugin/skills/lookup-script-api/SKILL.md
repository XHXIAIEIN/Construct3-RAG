---
name: lookup-script-api
description: Prints an interface of the Construct 3 scripting API with its members, or a member with its declaration and the file and line it is on. Used before a script calls an API, and before a call in a script is declared missing.
argument-hint: "NAME [NAME ...] [--locale LOCALE]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `lookup_script_api.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" lookup_script_api $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
