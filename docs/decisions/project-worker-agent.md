# A sub-agent type that carries only the tools the scripts need

Date: 2026-10-14

## Problem

A main agent that hands a sheet change or a lookup to a sub-agent starts a
general-purpose one, and every eval run is a general-purpose sub-agent. Such
a sub-agent starts with every tool, every connected server and the lists of
skills and agents of the session before its first step. A sub-agent type
whose definition names its tools starts with the definitions of those tools
alone.

## Evidence

First context of the sub-agent transcripts stored on one machine, by type,
measured with `evals/token_share.py --files`:

| Type | Transcripts | Median first context, tokens |
|------|-------------|------------------------------|
| general-purpose | 1 210 | 42 400 |
| workflow sub-agent | 1 362 | 52 000 |
| Explore | 9 | 34 200 |
| writing-reviewer, its tools named | 147 | 13 000 |
| ace-lookup, Bash, Read, Grep and Glob | 2 | 12 800 |

In one production game project, most sub-agent responses came from
general-purpose and workflow sub-agents, and every eval run was
general-purpose.

A comparison on one eval case ran three Haiku runs an arm, graded with
`grade.py --play`, in a Linux container off the owner's machine. The
`project-worker` arm started with half the context, 18 200 against 37 200
tokens, and cost about a third less. The route is what the comparison
watched: the first script a run calls, whether the check chain reaches
`review_look.py`, and how many plans were refused. A prompt that listed the
steps became the route, and its runs skipped `review_look.py`, which the
list left out. With a prompt that sends the run to `SKILL.md` and the
scripts' last lines, the route stayed within the spread of the
general-purpose runs. Three runs an arm, one of them void, cannot show the
two routes equal. The runs are in
`.local/docs/evidence/skill-evals/construct3-agent-plugin/`.

## Options

- Keep general-purpose sub-agents: nothing to ship, and every response of a
  sub-agent reads the whole session's tool list again.
- A sub-agent type in the plugin's `agents/` folder, its tools named
  (chosen). Claude Code reads it from the plugin; `tools` is a list of the
  tools it may use, and a plugin's agent cannot set servers, hooks or a
  permission mode of its own.
- The same definition written by `install.py` into a game project's
  `.claude/agents/`: it reaches a project that holds a copy of the skill and
  no plugin, but it is one more file `install.py` keeps current.

## Decision

The plugin ships `agents/project-worker.md`, built from
`scripts/plugin/agents/` by `build_plugin.py`, shown as
`construct3:project-worker`. Its tools are Bash, PowerShell, Read, Edit,
Write, Grep, Glob and Skill: the shells the scripts run in, the reads and
edits of project files and plans, search, and the Skill tool for the
plugin's skill. Its prompt sends it to the skill's `SKILL.md` before the
first project file and keeps its files inside the project.

Eval runs stay general-purpose: the comparison above is small and ran off
the owner's machine, and the runs of every iteration before it are
general-purpose, so a switch changes what new runs are compared against.

`SKILL.md`'s plugin bullet names the type for a sheet change or a lookup
handed to a sub-agent. That sentence is an eval iteration
(`skills/AGENTS.md`, "Evals") that sub-agent runs cannot measure, because
a sub-agent cannot start one of its own: it needs runs started as main
sessions, `claude -p` per run.

## Re-evaluate when

A comparison on the owner's machine with every run valid shows this type's
route within the spread of general-purpose runs: then evals start their
runs as this type. A route that falls short of the general-purpose runs',
there or in a week of production transcripts read with `token_share.py`,
means a tool the scripts need is missing from the list, or the prompt is
steering the route again. A game project without
the plugin that delegates sheet changes is the case for writing the
definition from `install.py`.
