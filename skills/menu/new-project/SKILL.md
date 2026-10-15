---
name: new-project
description: Creates a new Construct 3 folder project in an empty folder, copied from the empty project the editor saves for Project > New, with its own name and uniqueId. --dry-run shows what it would write. Used for a game that has no project yet.
argument-hint: "folder [--dry-run]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `new_project.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" new_project $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
