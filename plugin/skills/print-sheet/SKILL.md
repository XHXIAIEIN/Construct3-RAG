---
name: print-sheet
description: Prints the project's event sheets, or a range of events, as the editor words them, under the editor's event numbers. --map lists the sheets with the layouts that run them, --find the events that use a name, --since what changed since a commit. Used before and after an edit, and to read an official example as events.
argument-hint: "[SHEET ...] [--events A-B] [--find NAME] [--map] [--since COMMIT] [--locale LOCALE]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `print_sheet.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" print_sheet $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
