---
name: export-project
description: Exports the project to Web (HTML5) in the Construct 3 editor and unpacks it into the folder --to names. A string that looks like a secret key stops the export before it starts. The export needs an editor account with a subscription. Used to build the Web version of the finished game.
argument-hint: "[--to FOLDER] [--version VERSION | --bump] [--attach PORT|URL|FILE] [--dry-run]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `export_project.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" export_project $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
