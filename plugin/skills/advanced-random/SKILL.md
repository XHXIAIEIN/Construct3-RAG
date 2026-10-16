---
name: advanced-random
description: Prints the numbers an Advanced Random object gives after Update seed with the given seed, computed offline as the Advanced Random plugin of Construct 3 does. --table draws from a probability table, --check compares every value with that plugin's own code. Used to design odds and to replay a run.
argument-hint: "[SEED] [--count N] [--table JSON] [--check] [--preview]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `advanced_random.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" advanced_random $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
