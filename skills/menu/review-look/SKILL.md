---
name: review-look
description: Previews the project and visits every layout. For each it saves a screenshot and prints its path, the runtime faults seen on it, and a set of yes or no questions to answer from the screenshots. Used once the preview passes, as the last step before the hand-over.
argument-hint: "[PATH ...] [--layouts NAME [NAME ...]] [--design DESIGN.json] [--headed]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `review_look.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" review_look $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
