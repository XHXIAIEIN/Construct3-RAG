---
name: play-design
description: Plays a design's acceptance tests in the Construct 3 editor on the game built from the design, then compares the first screen with the prototype. Each failure names the test, the step and the rules to compare.
argument-hint: "DESIGN.json [--plan-only OUT.json] [--adopt-starts]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `play_design.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" play_design $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
