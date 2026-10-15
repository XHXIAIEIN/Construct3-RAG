---
name: edit-sheet
description: Changes an event sheet from a plan. The plan is a JSON file of operations addressed by the editor's event numbers. The whole project is checked with the change in place before anything is written, and a plan that adds a problem changes nothing. --dry-run shows the result without writing, --new creates the sheet first.
argument-hint: "SHEET PLAN.json [--dry-run] [--new]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `edit_sheet.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" edit_sheet $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
