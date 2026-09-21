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
