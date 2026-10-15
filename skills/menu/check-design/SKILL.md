---
name: check-design
description: Checks a new game's design file before any project file is written. A missing field is named by its path in the file, and the check stops there. Then the design's acceptance tests are played on its rules as a prototype, without the editor.
argument-hint: "DESIGN.json"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `check_design.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" check_design $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
