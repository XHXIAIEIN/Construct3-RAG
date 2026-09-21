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
notice. The runs are in
`.local/docs/evidence/skill-evals/construct3-project/iteration-1/`, which Git
ignores.

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
  (It did, in another folder: the second pass below reads them.)
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

## Evaluation 2026-09-22, second pass: the four guides, heading by heading

Schema: Construct 3 r495.2; the guides as <https://agentskills.io> published
them on that date: `skill-creation/best-practices`,
`optimizing-descriptions`, `evaluating-skills`, `using-scripts`.

The first evaluation took the layout, the test cases and the trigger queries
from the guides. This pass holds the skill against every heading of the
four. A heading changed something, with the evidence, or it did not, with
the reason.

### What the transcripts show

Claude Code keeps the transcript of a subagent as
`~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`, with its
description in `agent-<id>.meta.json`. The 0-byte files of the first
evaluation were the task output files, another thing. `evals/trace.py`
prints a transcript call by call and counts the calls a run lost.

- An answer lists the commands a run remembers. The answer of add-countdown
  with the skill names three; its transcript holds seven script runs.
- Lookups by meaning miss. With the previous skill 4 of 8 lookups found
  nothing, in both runs of add-countdown: `System timer`,
  `Coin scale size`, `System wait time frame`, `Coin scale width`. A word
  was matched against ids and names only, every word had to match, and the
  miss named the nearest id of the words joined, `time, trim`.
- Edits fail on tabs. 22 of the 60 Edit calls of the eight runs that edited
  a sheet failed with "String to replace not found", in every arm: a match
  of several lines with one tab too many, in files indented 7 to 17 tabs
  deep inside an event.

### What the scripts did to their reader

- Size. Over the 524 official examples and the 7 game projects
  (`evals/sweep_outputs.py`), `print_sheet.py` printed more than 10 000
  characters on 173 and more than 30 000 on 21, the outline on 42 and 8,
  the checker on 2 (glokar 24 930, of which 166 lines warn that a parameter
  is omitted), `lookup_ace.py System` 22 432. WaterSort, the game
  the generator came from, prints 49 253. Claude Code replaced a print of
  37 KB with its first 2 KB and the path of a file; the run read the file,
  39 756 characters in one call, and answered. A harness that cuts without
  keeping the file loses the end of the sheet, and says so or does not.
- Encoding. A piped Python on Windows writes the ANSI code page. With
  `PYTHONIOENCODING=cp936` the Chinese wording of a sheet reached this
  harness as mojibake; with `cp1252` the script stopped at exit 2 under the
  sentence about a missing key. Both were produced by setting the variable:
  the ANSI code page of this machine is UTF-8. The tests had set
  `PYTHONIOENCODING=utf-8` for every run, which is why none saw it.
- A guess. `lookup_ace.py Platform jump` answered "nothing matches": a near
  match had read `Platform` as the plugin Platform Info, ahead of the
  behavior of that name.
- The scripts run under CPython 3.10.19, the version `compatibility` names.
  Not checked before.

### Heading by heading

Best practices:

| Heading | Finding | Action |
|---------|---------|--------|
| Start from real expertise | The rules and gotchas come from Water Sort, mergeGame and the load errors of the DeepSeek and Doubao projects (`checker-editor-load-rules.md`) | none |
| Refine with real execution | Iteration 1 read answers, not traces | `evals/trace.py`; the findings above |
| Add what the agent lacks, omit what it knows | `<new sid>` was never explained, and the encodings of a function block, a call, a `projectfile` parameter were one file away with nothing pointing there | two sentences in `SKILL.md` |
| Design coherent units | One unit: the JSON of a folder project. Designing the events stays in `prompts/`, which installed blocks name | none |
| Aim for moderate detail | 169 lines, about 2 400 tokens, under the 500 lines and 5 000 tokens of the specification | none |
| Progressive disclosure | Both references say when to read them; the hand-editing reference of the clone was not named at all | named in `SKILL.md`, with its when |
| Match specificity to fragility | The check loop and the way a parameter is written are prescribed; design is left to the guide it points to | none |
| Provide defaults, not menus | `.agents/skills` with the clients' folders as the exception; generate or hand-edit is decided by who owns the project | none |
| Favor procedures over declarations | The three traces of iteration 1 print, look up, edit, check and print again in that order without being told | no checklist added |
| Gotchas | Each is a failure seen in a game project. A gotcha on tab-deep edits was tried in iteration 2: 8 of 19 edits failed with it, 14 of 41 without | taken out again |
| Templates for output format | The `write:` line is the template of what is written most. No hand-over template: nobody has reviewed the answers yet | see Not done |
| Checklists for multi-step workflows | As "procedures" above | none |
| Validation loops | "Check after every change" is that loop; the checker caught `iif` in a run of iteration 2 and the run fixed it | none |
| Plan-validate-execute | The destructive step is regenerating over files the editor touched; the reference says to move them aside first | see Not done |
| Bundling reusable scripts | The baseline of name-the-restart-event wrote its own numbering script, which is `print_sheet.py`. The old-against-new sweep was rewritten in every session | `evals/sweep_outputs.py` |

Using scripts:

| Heading | Finding | Action |
|---------|---------|--------|
| One-off commands | The validator command in `skills/AGENTS.md` names no commit | see Not done |
| Referencing scripts | Listed in a table, paths relative to the skill's folder | none |
| Self-contained scripts | Standard library only; Pillow optional, and a declared dependency would make the first run need a network | no PEP 723 block |
| Avoid interactive prompts | None | none |
| Document usage with `--help` | 1 455 to 2 229 characters, examples and exit codes | the new flags are in it |
| Write helpful error messages | A lookup miss did not say what to try | it lists the entries that have some of the words, or the categories |
| Use structured output | The readers are a model and two programs that read the exit code and the `warning:` prefix | no JSON output |
| Idempotency | `install.py` and a seeded generator repeat themselves | none |
| Input constraints | A near name was taken for a plugin | an exact id or display name, or the nearest names and exit 1 |
| Dry-run support | `install.py --dry-run`; the generator has none | see Not done |
| Meaningful exit codes | Documented in every `--help`. 1 is findings and also "not found"; 2 is a malformed file and also argparse's usage error | see Not done |
| Safe defaults | `install.py` writes a dot-folder and, where absent, a block | none |
| Predictable output size | The measurements above | `--limit`, 10 000 by default, in the three scripts |

Evaluating skills:

| Heading | Finding | Action |
|---------|---------|--------|
| Designing test cases | Three cases on one 9-event sheet; none reads a long sheet, generates a project or lacks the clone | `find-in-a-long-sheet` on the official example abductractor |
| Workspace structure, spawning runs | As the guide lays it out. The previous skill as baseline needs its own clone: pointed at this one the old copy reports a difference and the agent refreshes it | `make_fixtures.py --arms old_skill --old-clone`, a git worktree of the previous commit |
| Capturing timing data | From the completion notices, when they arrive | none |
| Writing assertions, grading | By script, with evidence | a grader for the new case |
| Aggregating results | `benchmark.json` had no difference between arms | `delta`, with tool calls and lost calls where a run has a `trace.json` |
| Analyzing patterns | 18 of 18 with the skill: the assertions no longer tell two versions apart. What differs is in the traces | lost calls per run |
| Reviewing results with a human | Not done in either iteration; no `feedback.json` | the maintainer's step |
| Iterating on the skill | Failed assertions: none. Human feedback: none. Transcripts: read | the changes below |

Optimizing descriptions:

| Heading | Finding | Action |
|---------|---------|--------|
| Writing effective descriptions | 683 of 1 024 characters; imperative second sentence; names what users say. The first sentence speaks of schemas and load rules, the mechanism, not the intent | none before a measurement, by the rule in `skills/AGENTS.md` |
| Designing trigger eval queries | 10 and 10, near misses as negatives, two languages, file paths, typos | none |
| Testing, running multiple times, the loop | `claude -p` answers "OAuth session expired and could not be refreshed", as on the day before. A subagent of this session is no substitute: it reads this repository's `AGENTS.md`, which names the skill | not run |

### Changes

- `print_sheet.py --events A-B` prints a range under the events it sits in,
  marked `[context]`. A print over `--limit` stops at an event and ends
  with the command that continues; without a sheet name, sheets that do not
  fit are listed with their sizes and includes.
- `lookup_ace.py`: a word may be a category (`System time` lists *Every X
  seconds*, *Wait* and `dt`); names match first, so that `Physics force` is
  still three entries in full with the rest of its category named below; a
  miss lists the entries that have some of the words, names before
  categories, or the categories; a list over the limit becomes counts per
  kind and category; OBJECT is an exact id or display name.
- `check_project.py`: a report over the limit prints the findings that fit,
  warnings in a third of it, and counts the rest. The last line always
  prints.
- Every script writes UTF-8 and replaces what a chosen codec cannot encode.
- `SKILL.md`: the limit and `--events`, how words match, `<new sid>`, when to
  read the hand-editing reference.
- `evals/`: `trace.py`, `sweep_outputs.py`, the old-skill arm and official
  examples as fixtures in `make_fixtures.py`, `delta` and lost calls in
  `grade.py`, the fourth case.

Old against new over 1 618 runs: with `--limit 0`, 6 differ, all lookups and
all meant (`System timer`, `Sprite scale size`, `Sprite animation`,
`Platform jump`, `Physics force`, `NoSuchAddon`). With the default limit 225
differ: the 173 prints, 42 outlines and 2 checks that had passed 10 000
characters, and 8 lookups. Nothing within 10 000 characters changed, and no
run prints more than 9 879.

### Iteration 2

Claude Haiku 4.5 subagents, one run per case and arm, projects outside the
clone. `with_skill` is the working tree; `old_skill` is eac319f, installed
from a worktree of that commit which its block names as the clone. Runs in
`.local/docs/evidence/skill-evals/construct3-project/iteration-2/`.

| Case | With the skill | Previous skill |
|------|----------------|----------------|
| add-countdown | 7/7, 68 723 tokens, 167.9 s, 33 calls, 6 lost | 7/7, 65 405 tokens, 140.8 s, 31 calls, 6 lost |
| fix-load-errors | 8/8, 58 896 tokens, 103.0 s, 18 calls, 4 lost | iteration 1: 8/8, 59 981 tokens, 104.8 s, 22 calls, 6 lost |
| name-the-restart-event | 3/3, 48 795 tokens, 29.2 s, 5 calls, 0 lost | iteration 1: 3/3, 48 087 tokens, 30.8 s, 5 calls, 0 lost |
| find-in-a-long-sheet | 5/5, 55 180 tokens, 54.7 s, 8 calls, 0 lost | 5/5, 66 345 tokens, 49.7 s, 7 calls, 0 lost |

- No assertion failed in either arm. One run per cell: counts, no spread.
- The long sheet. The previous skill printed 37 KB, the harness kept 2 KB
  and a file, the run read the file whole. The skill now printed the
  outline in parts, searched it with `--limit 0` through a pipe, and read
  events 102 to 108 with `--events`: 11 165 tokens fewer. Both answered
  103, 104, 105 and 108. This harness keeps the file; one that does not
  was not tried.
- Lookups: 1 of 4 missed with the skill, `System timer`, against 2 of 4 in
  each run of the previous one. The run went on to `System every`, not to
  the category the miss had listed.
- Edits: 4 of 10 and 4 of 9 failed with the sentence about tabs in
  `SKILL.md`. It bought nothing and is out again, which is the one
  difference between the `SKILL.md` that ran and the one committed.
- add-countdown costs the same in both arms; its time goes into edits.

### Not done, and why

- A script that inserts or replaces an event by its number, written as
  JSON by the agent and checked before it lands. It is what the failed
  edits point to, and what the guide calls plan, validate, execute: about
  a third of all Edit calls are lost, in every arm. It is a new tool with
  its own design, so a decision of its own.
- A guard in the generator against overwriting files the editor changed
  since the last build, and a `--dry-run`. The reference asks the agent to
  move such files aside; no lost edit has been reported.
- Separate exit codes for findings, not found and usage. Every caller
  reads 0 or not 0, and every message says which it was.
- JSON output: still no program reads the findings.
- A hand-over template. It is a matter of what the maintainer wants to
  read, and the answers of two iterations are unreviewed.
- The description, for lack of a measurement.
- `skills-ref validate` on this state: the permission mode of the session
  refused code fetched from GitHub. The frontmatter did not change, and
  `tests/test_project_tools.py` pins the same constraints. Pinning the
  command in `skills/AGENTS.md` to 69ef37e waits for a run that shows the
  short hash resolves.

### Re-evaluate when

- The maintainer has read the answers in `iteration-2/*/*/outputs/` and
  written `feedback.json`: that, not the assertions, is the next signal.
- The `claude` CLI is signed in: the trigger evaluation, unchanged from the
  section above.
- A harness in use cuts output below 10 000 characters: lower `LIMIT` in
  `scripts/c3project.py`.
- An agent is seen reading a long sheet part by part where one read of a
  file would do: print to a file with `--limit 0` and say so in `SKILL.md`.
- Edits are to get cheaper: the event-insert script above, measured by lost
  calls on add-countdown and fix-load-errors.

## Update 2026-09-22: the event script

Built the same day as `scripts/edit_sheet.py`; its design, the counts behind
it and iterations 3 and 4 of the evals are in `edit-sheet-script.md`. The
assertion of name-the-restart-event that allowed no number but 9 failed a
correct answer which also named the group, event 8; it now allows another
number on a line that calls it the group, and the baseline that answered 8
still fails it.

## Update 2026-09-22: the pointer is deleted

`prompts/project-tools/README.md` is removed, on the maintainer's decision.
The two projects whose block still names it, `new project - Doubao` and its
copy, are small-model test outputs that no agent works in again, and they
keep their old block. Nothing else in this repository or in the other game
projects named the file.
