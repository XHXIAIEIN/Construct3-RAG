---
name: review-design
description: Runs the full checker, then prints design findings and questions about the project's event sheets. --check is the step after every change, --sheets selects the changed sheets. references/design-review.md of the main skill explains --prepare and --resume.
argument-hint: "[--check] [--sheets NAME [NAME ...]] [--style]"
disable-model-invocation: true
allowed-tools: Bash(python *) PowerShell(python *)
---

What `review_design.py` printed for the arguments given, with its exit code on the last line:

!`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" review_design $ARGUMENTS`

If the skill `construct3:construct3-agent-plugin` is not loaded in this session, read `${CLAUDE_PLUGIN_ROOT}/skills/construct3-agent-plugin/SKILL.md` before acting on the output.
