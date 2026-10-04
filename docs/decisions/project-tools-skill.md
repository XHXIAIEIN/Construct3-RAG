# The Project Tools Ship as an Agent Skill

Date: 2026-09-21
Schema: Construct 3 r495.2; the Agent Skills format as
<https://agentskills.io/specification> describes it

## Problem

The project tools reached a game project as files a person copied into its
`tools/`. Copies fell behind in silence, the user carried them, and one
checker file held four commands under one name.

Task: an agent that starts work in a game project puts the tools there
itself, in a form its harness discovers, and a copy that falls behind says
so. The default path calls them on every run: a generated project ends with
the checker, and `AGENTS.md` section 2 sends every agent to the ACE lookup.

## Options

1. One file, copied by hand. Copies go stale unseen.
2. Run the tools from the clone, never copy. Every command then carries the
   clone's absolute path, the string a small model gets wrong, and no
   harness discovers anything.
3. A skill folder in the Agent Skills format, installed by the agent with
   one command, its scripts split by intent over a shared module, each copy
   comparing itself with the clone.
4. Modules bundled into one file for distribution: a build step to keep a
   single-file constraint that option 3 removes.

## Decision

Option 3. TRAE reads `.trae/skills/` and `.agents/skills/`, Deep Code
`.deepcode/skills/` and `.agents/skills/`, Claude Code `.claude/skills/`. A
project used with the Claude Code plugin holds no copy
(`plugin-tracks-commits.md`).

- `skills/construct3-agent-plugin/`: `SKILL.md`; `scripts/`, one script per
  intent, each named in `SKILL.md`, over the shared `c3project.py`, and
  `check_design.py` and `play_design.py` also over `game_model.py`;
  `references/`; `assets/`, among them `build_project.py`, the generator
  template, and `game-project-block.md`, the block for the project's
  instruction file; `evals/`, which stays in this repository.
- `install.py` copies the folder into `.agents/skills/`, or the folder
  `--into` names, refreshes every copy the project holds when run again, and
  appends the block to `AGENTS.md` with the clone's path filled in when no
  instruction file names the clone. Installing is the agent's step, by the
  maintainer's call; `--no-block` and `--dry-run` serve a user who wants it
  otherwise.
- A copy compares its files with the clone's on every run. While it differs,
  the first line of every script's output is the command that refreshes it.
- The generator is copied into the game as `tools/build_project.py` and
  finds the checker in a skills folder of the project or of the user's home
  folder. `install.py` replaces its helpers, between two markers, with the
  skill's current ones (`generator-helpers-inline.md`).

## What holds the design in place

Each of these was a failure seen in an eval run or a game project.

- The block's first step sends the agent to `SKILL.md` before any project
  file, says in one sentence what its scripts do, and runs `check_project.py`
  once. As a table row the skill was skipped by half the runs, which then
  edited the sheet's JSON by hand; with the step every run read it. Without
  the sentence on what the scripts do, fewer runs opened `SKILL.md`, and only
  runs that opened it used `edit_sheet.py`. The check's exit shows at once
  whether the `Construct3-RAG:` line reaches the clone and whether the copy
  is current.
- `SKILL.md` is ASCII. The reference validator and plain clients read it
  with the locale's codec, and a UTF-8 sign does not decode under cp936.
- Every script writes UTF-8 whatever the code page, and stops at `--limit`,
  10 000 characters by default, with a last line that says how to get the
  rest. A third of the official examples print a sheet longer than that, and
  a harness cuts long output, not always saying so.
- A miss prints on stdout, like a hit, and lists what comes near. PowerShell
  wraps each line of stderr in an error record, and a harness that shows
  stdout alone shows nothing. A lookup that missed under System or a plugin
  also searches `plugins/_common.json`: two runs took a miss for "this
  version has no such ACE" when the ACE was every world object's.
- An object name is an exact id or display name, or the run stops with the
  nearest ones: a near match once read `Platform` as Platform Info.
- `SKILL.md` holds what every activation needs and no tool says at the
  moment it matters. What a script prints when it is needed, or what one
  kind of task needs, is a line that says when to read a reference. Taken
  out on this rule, and the runs did no worse without them: Gotchas a
  finding or a lookup already prints; then the lookup's word matching, the
  export steps, the browser-tool fallback of exit code 3 and where a lesson
  goes, about 570 tokens (iteration 35, Haiku, `add-countdown` and
  `fix-load-errors`, three runs an arm: 47 of 48 assertions against 48 of
  48, the one miss a `replace` that dropped the sids of the sub-events it
  rewrote, as in runs before the change).

## Open

- The trigger evaluation of `description` has not run: it needs a
  signed-in `claude` CLI, and a subagent of this repository inherits its
  `AGENTS.md`, which names the skill. `evals/run_trigger_eval.py` and the
  query files are ready. Change `description` only from its train failures.
- No one has reviewed the eval answers by hand; the assertions are at
  ceiling, so that review is the next signal.
- Paging beyond the `--events` range that `print_sheet.py` gives, JSON
  output, separate exit codes for findings and not-found, and a generator
  guard against overwriting files the editor changed: no eval run or game
  project has needed them.

## Re-evaluate when

- An agent loses the end of a printed sheet to truncation, or a harness in
  use cuts below 10 000 characters: lower `LIMIT` in `scripts/c3project.py`.
- A run started from the block edits a sheet's JSON by hand: read its trace
  for what it opened instead of `SKILL.md`.
- A harness in use reads neither `.agents/skills/` nor the block: name its
  folder in `install.py --help` and `AGENTS.md` section 4.
- A project shows a wrong `behaviorType`, addon id or *Else* that the
  finding did not repair in one round: the Gotcha goes back, with the case.
- Runs look a behavior's ACE up under System (`System tween two properties`)
  and lose the call: the miss under System names the behavior and an object
  of the project that has it.
