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

In one production game project, general-purpose and workflow sub-agents
answered about 11 500 responses; the eval runs were all general-purpose.

In a same-batch comparison on the case `add-countdown`, three Haiku runs
an arm graded with `grade.py --play`, run in a Linux container because the
command-line client on the owner's machine could not sign in, a
general-purpose run started with 37 200 tokens and a `project-worker` run
with 18 200. The `project-worker` arm cost 1.30 M input-token equivalents
against 2.03 M, over 114 responses against 138.

The first prompt of the type listed the steps (print a sheet, look an ACE
up, write a plan, run the checker and the preview), and its runs took the
list for the route: all three started with `print_sheet.py` where every
general-purpose run started with `check_project.py`, and none reached
`review_look.py`. With a prompt that sends the run to `SKILL.md` and the
scripts' last lines alone, two of three started with the checker, the
check chain reached `review_look.py` in one run of three against two of
three, refused plans were 2 against 3, and 2 of 3 runs passed every
assertion against 1 of 2 (one general-purpose run was void for a file it
wrote outside its folder). At three runs an arm that is within the spread
of the chain between runs, not a measured equality.

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

Eval runs stay general-purpose for now: the comparison above is small, ran
off the owner's machine, and every earlier iteration's runs are
general-purpose, so a switch changes what new runs are compared against.

`SKILL.md`'s plugin bullet names the type for a sheet change or a lookup
handed to a sub-agent. That sentence is an eval iteration
(`skills/AGENTS.md`, "Evals") that sub-agent runs cannot measure, because
a sub-agent cannot start one of its own: it needs runs started as main
sessions, `claude -p` per run, which is owed.

## Re-evaluate when

A comparison on the owner's machine with full cells shows the route
columns of this type within the spread of general-purpose runs: then evals
start their runs as this type. Route columns that fall against
general-purpose runs, there or in a week of production transcripts read
with `token_share.py`, mean a tool the scripts need is missing from the
list, or the prompt is steering the route again. A game project without the plugin that delegates sheet
changes is the case for writing the definition from `install.py`.
