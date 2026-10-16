---
name: print-layout
description: Prints a layout's layers bottom to top and each instance in Z order with its object, box, size, opacity and text, and the object under a text. Used to say where things are and what covers what, and after a layout is generated.
argument-hint: "[LAYOUT ...] [--layer NAME] [--locale LOCALE]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `print_layout.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" print_layout $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
