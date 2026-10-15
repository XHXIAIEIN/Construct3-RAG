---
name: screenshot-sheet
description: Saves a picture of an event sheet, or of one group of it, as the Construct 3 editor shows it, cropped to the sheet. Used for a forum post, a bug report or a document.
argument-hint: "[SHEET] [--group TITLE] [--scale {1,2,3}] [--dark] [--out FOLDER]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `screenshot_sheet.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" screenshot_sheet $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
