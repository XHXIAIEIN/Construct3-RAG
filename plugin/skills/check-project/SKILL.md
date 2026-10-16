---
name: check-project
description: Checks every file of the Construct 3 folder project against the schemas and the rules the editor applies when it opens a project. Each finding is printed with its place and what to write. The last line starts with ok when the project passes. --style adds the warnings of the official examples' style.
argument-hint: "[--style] [--review] [--project FOLDER]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `check_project.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" check_project $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
