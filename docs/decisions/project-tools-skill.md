# The Project Tools Ship as an Agent Skill

Date: 2026-09-21
Schema: Construct 3 r495.2; the Agent Skills format as
<https://agentskills.io/specification> published it on that date

## Problem

The project tools reached a game project as two files a person copied into
its `tools/`: `build-project.py` and `check-project.py`. The checker had
grown to 1328 lines and held four commands under one name: the checks,
`--print`, `--outline` and `--ace`. Two questions came with that: whether to
split it, and how the tools get into a game project and stay current there
without the user carrying them.

Task: an agent that starts work in a game project puts the tools there
itself, in a form its harness discovers, and a copy that falls behind says
so. The default path calls them on every run: a generated project ends with
the checker, and `AGENTS.md` section 2 sends every agent to the ACE lookup.

## Evidence

Copies on disk, 2026-09-21. Of the seven game projects beside this clone,
three hold `tools/check-project.py`, in three versions: WaterSort 466 lines,
*new project - Doubao* 735, *new project - Doubao - Copy* 1328. The last was
refreshed by hand after the load-rules change
(`checker-editor-load-rules.md`); the others were left for the user to
replace. Nothing in a copy says it is behind.

The file by intent: 106 lines are `--ace`, 110 are `--print` and
`--outline`, about 280 are what every mode stands on (finding the project
and the clone, the schema cache, types, families and behaviors), about 770
are the checks. The modes share the base, and `--print` also shares the
schema lookup of a condition with the checks.

Size cost nothing at run time. On the largest official example
(overloaded-underqualified, 893 images, 511 KB of event sheets) the checks
take 0.37 s, `--print` 0.31 s and `--ace` 0.13 s.

The harnesses the models run in read the format. TRAE discovers
`.trae/skills/` and, once enabled in its settings, `.agents/skills/`
(<https://docs.trae.cn/ide_skills>); Deep Code, a terminal agent for
DeepSeek, `.deepcode/skills/` and `.agents/skills/`
(<https://deepcode.vegamo.cn/en/docs/configuration/agent-skills>); Claude
Code `.claude/skills/` (<https://code.claude.com/docs/en/skills>). The
specification asks for a folder named as the skill, a `SKILL.md` whose
`description` of at most 1024 characters says what and when, under 500
lines, with `scripts/`, `references/` and `assets/` beside it; its guide on
scripts asks for `--help`, no prompts, errors that say what to do, and
documented exit codes.

## Options

1. One file, copied by hand. Nothing to build. Copies go stale in silence,
   the user is the courier, and three commands hide behind the name of a
   fourth.
2. Run the tools from the clone, never copy. No stale copies. Every command
   then carries the clone's absolute path, on this machine with spaces and
   backslashes, which is the string a small model gets wrong; and no harness
   discovers anything.
3. A skill folder in the Agent Skills format, installed by the agent with
   one command, its scripts split by intent over a shared module, each copy
   comparing itself with the clone.
4. Modules in the repository, bundled into one file for distribution. A
   build step and a generated file nobody may edit, to keep a single-file
   constraint that option 3 removes.

## Decision

Option 3. The single file was the right shape while a person copied files;
the unit that ships is now a folder, so the split costs nothing.

- `skills/construct3-project/`: `SKILL.md`; `scripts/check_project.py`,
  `print_sheet.py`, `lookup_ace.py` over `c3project.py`; `install.py`;
  `references/` from the former README; `assets/build_project.py`, the
  generator template, and `assets/game-project-block.md`, the block.
- `install.py` copies the folder into the project's `.agents/skills/`, or
  the folder `--into` names, refreshes every copy the project holds when
  run again, and appends the block to `AGENTS.md` with the clone's path
  filled in when no instruction file names the clone. An instruction file
  that does is left as it is. The unfilled `<path-to>` that stopped the
  checker in three projects (`checker-editor-load-rules.md`) cannot come
  out of it.
- A copy compares its files with the clone's on every run and prints the
  command that refreshes it. Run from a copy, `install.py` hands over to the
  clone's.
- Installing is the agent's step, not an offer, by the maintainer's call of
  this date; `AGENTS.md` section 4 has the wording. What it writes is a
  dot-folder and, where absent, the block; `--no-block` and `--dry-run`
  serve a user who wants it otherwise.
- The generator moves to the game as `tools/build_project.py` and finds the
  checker in the project's skills folders, then the user's.
- `prompts/project-tools/README.md` stays as a pointer: the blocks of the
  two Doubao projects name it, and an agent that follows them lands on the
  install command.

Output did not change. The single file at c542db4 and the new scripts ran
over the 524 official examples and the 7 game projects: checks, `--print`
in en-US on all and in zh-CN on 71, `--outline`, and 36 lookups, 1700 runs.
Exit code, stdout and stderr are identical in all of them. One behavior
differs by design and is outside that set: printing a sheet no longer reads
the layouts first, so a project with a malformed layout still prints. The
reference validator, `skills-ref validate` from agentskills/agentskills at
69ef37e, reports a valid skill; `tests/test_project_tools.py` pins the same
constraints offline and runs every tool from a copy `install.py` made.

Not done, because nothing here shows it is needed:

- Paging `print_sheet.py`. The longest sheet of the examples prints 2583
  lines, and the format's guide warns that harnesses cut tool output at
  10 to 30 thousand characters. No agent has been seen losing the end.
- JSON output. A model reads the findings; no program does.
- The trigger evaluation the format's guide describes for `description`. It
  needs the harnesses, and no missed activation has been observed.
- Turning `prompts/event-sheet-thinking.md` and its references into skills.
  The block routes to them, and moving them breaks the blocks already
  installed.

## Re-evaluate when

- An agent loses the end of a printed sheet to truncation: page by event
  range.
- TRAE or Deep Code does not activate the skill on event sheet work: run the
  trigger evaluation and rewrite `description`.
- A harness in use reads neither `.agents/skills/` nor the block: name its
  folder in `install.py --help` and in `AGENTS.md` section 4.
- No game project's block names `prompts/project-tools/README.md` any more:
  delete the pointer.

## Evaluation 2026-09-22: the validator, three output cases, the trigger queries not run

Schema: Construct 3 r495.2; the guides as <https://agentskills.io> published
them on that date.

The record above left the evaluation of the skill undone. This is what ran,
by <https://agentskills.io/skill-creation/evaluating-skills> and
<https://agentskills.io/skill-creation/optimizing-descriptions>, and what
did not.

### The reference validator

`skills-ref validate`, `read-properties` and `to-prompt`
(agentskills/agentskills, run through `uvx`) accept the skill. The validator
reads the frontmatter only: the fields, the name against the folder, the
lengths. It reads `SKILL.md` with the locale's codec. The file held three
UTF-8 comparison signs, which do not decode under cp936, so `SKILL.md` is
ASCII now and a test pins it. The failure was reproduced by decoding the
bytes as GBK, not by running the validator on a cp936 machine.

### Output quality, iteration 1

Three cases on the stand-in game (`skills/construct3-project/evals/evals.json`),
one run per case and arm, Claude Haiku 4.5 as a subagent, each in a project
folder outside the clone. `evals/grade.py` checks the assertions with the
clone's checker; tokens and seconds are those of each run's completion
notice. The runs are in `skills/construct3-project-workspace/iteration-1/`,
which Git ignores.

| Case | With the skill | Without | What the baseline got wrong |
|------|----------------|---------|-----------------------------|
| add-countdown: a hand edit of the sheet | 7/7, 60136 tokens, 104.6 s | 5/7, 57634 tokens, 95.1 s | gave *Every tick* a parameter `interval`, which the editor refuses, and took 1 off every tick, not every second |
| fix-load-errors: five seeded mistakes, the editor's first message pasted | 8/8, 59981 tokens, 104.8 s | 3/8, 52888 tokens, 72.5 s | repaired the inverted trigger, left the other four, the quoted one among them, and reported the project ready |
| name-the-restart-event: the editor's number of an event | 3/3, 48087 tokens, 30.8 s | 2/3, 49484 tokens, 52.0 s | answered 8, the group, where the editor shows 9 |

What the counts do and do not show:

- One run per cell. These are counts; no spread was measured, and a second
  run may differ.
- Some assertions guard against damage and pass on a project nobody
  touched: graded as laid out, the fixtures score 3/7, 2/8 and 1/3. Read a
  count against that floor: the baseline of fix-load-errors is one
  assertion above it.
- The first baseline of fix-load-errors is void. Started below the clone,
  it read the clone's `AGENTS.md` and ran `check_project.py` from there,
  by its own list of commands, and repaired all five. It was rerun with the
  line "use no script, data file or document from anywhere outside the
  project folder"; the row above is the rerun. The other two baselines ran
  without that line and list no file outside their project. Those lists
  are the runs' own; the harness kept no transcript to check them against.
- The checker is the judge of "opens in the editor", and it is part of the
  skill. No run was opened in Construct.
- Both fixed sheets read `Coin.value` in *On tween finished* of a tween
  that destroys the coin, the move the checker's message suggests. The
  manual says that *Destroy on complete* destroys the instance "when the
  tween finishes" and that *On finished* triggers then
  (`Construct3-Manual/Construct3-Manual/behavior-reference/tween.md`), and
  gives no order.
  Whether the value is still readable there is the preview's to say, and
  the answer belongs in `prompts/event-sheet-pitfalls.md`.
- The first grading had two faults in `grade.py`, corrected before these
  counts: it looked for `interval` where the schema has `interval-seconds`,
  which failed the run with the skill, and it failed "no warning" whenever
  the checker failed, which counted one fault twice against the baseline.

### The trigger evaluation of `description`: not run

The queries exist, 10 that should trigger and 10 near misses, split 12/8
with a fixed seed, and `evals/run_trigger_eval.py` runs them on Windows,
where the guide's shell script and skill-creator's `run_eval.py` cannot. The
`claude` CLI on the machine was signed out ("OAuth session expired and could
not be refreshed"); the runner stops at that with exit code 2 and writes no
rate. Its handling of a Skill call, a read of `SKILL.md`, a signed-out
client and an unreadable stream is tested against a stand-in client; the
shape of a real Skill call in the stream was not seen.

The description is unchanged. Suspected before any measurement: "any other
project file" claims `scripts/*.js` and `files/*.json`, which the tools do
not read, and two of the near misses ask for exactly those.

### What the scripts print

Measured for the first time. `print_sheet.py` without a sheet name exceeds
10 000 characters on 170 of the 524 official examples, 30 000 on 20 and
100 000 on 5 (meowgix, 149 800). `lookup_ace.py System` prints 22 432
characters and an object with a behavior 18 837, both as one line per ACE.
A naming word narrows it, `System wait` to 928; a kind alone does not,
`System action` prints 7 729 and `System expression` 10 172. `--help` is
1 234 to 1 812 characters per script.

Paging stays undone. A third of the official examples print more than the
10 000 characters at which the guide says harnesses start to cut tool
output, but no run of the evals read a sheet that long, and no agent has
been seen losing the end.

### Changes

- `evals/` beside `SKILL.md`: the cases, `make_fixtures.py`, `grade.py`, the
  query files, `run_trigger_eval.py`. `install.py` leaves it out of a copy,
  and a copy does not report it as a difference.
- `SKILL.md` is ASCII.
- `install.py --no-block` says how the scripts find the clone when no
  instruction file names it. The project laid out that way for the trigger
  runs stopped at `Construct3-RAG not found` on its first command.
- `skills/AGENTS.md` has the rules of an eval run.

### Re-evaluate when

- The `claude` CLI is signed in: run `evals/run_trigger_eval.py` on both
  query files, then change `description` from the train failures only. This
  replaces "needs the harnesses" above for Claude Code; TRAE and Deep Code
  need their own way to see that `SKILL.md` was loaded, passed as the
  runner's `--client` with detection to match.
- A case is run several times per arm: report the spread, and extend
  `grade.py`, which has one folder per case and arm.
- `SKILL.md`, a reference or what a script prints changes: a new iteration,
  with the previous skill as the baseline.
