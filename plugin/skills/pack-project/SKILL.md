---
name: pack-project
description: Saves the project as a .c3p or .zip, or unpacks a .c3p or .zip into a project folder, with project.c3proj at the archive's root as the editor needs it. The pack is made only after the checker passed the files, unless --unchecked is given. Used to hand the project over as one file.
argument-hint: "[SOURCE] [--out FILE|FOLDER] [--open] [--unchecked]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `pack_project.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" pack_project $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
