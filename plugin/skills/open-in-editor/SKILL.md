---
name: open-in-editor
description: Opens the project in the Construct 3 editor in a headless browser and prints opened, or failed with the editor's message. --preview also runs the game for a few seconds and prints its runtime errors with their events, --state what the runtime holds at the end. Used after the checker passes.
argument-hint: "[PATH ...] [--preview [SECONDS]] [--state [TYPE ...]] [--headed] [--steps]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `open_in_editor.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" open_in_editor $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
