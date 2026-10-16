---
name: prepare-art
description: Turns the pictures saved from the session's image tool into a generated game's art. --list prints the next step toward the pictures the generator asks for. Without it, each picture in art/raw is cut out and fitted to its box. Needs Pillow.
argument-hint: "[--list]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `prepare_art.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" prepare_art $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
