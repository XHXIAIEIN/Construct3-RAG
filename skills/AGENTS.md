# `skills/` Directory

Agent Skills in the open format of <https://agentskills.io/specification>:
one folder per skill, a `SKILL.md` with `name` and `description`, and
`scripts/`, `references/` and `assets/` beside it. The folder here is the
source. A game project holds a copy of it, made and refreshed by the skill's
`scripts/install.py`, and the copy reports when it differs from the source.

`construct3-project/` is the one skill here: the ACE lookup, sheet printer,
sheet editor, checker and generator template for a Construct 3 folder
project, and the block for the project's instruction file.

## Rules

- The folder is what ships: `install.py` mirrors every file in it into the
  game project, except `evals/`, which tests the skill from here. Nothing
  else lives in it, no scratch files, outputs or notes. What an eval run
  leaves goes to `.local/docs/evidence/skill-evals/<skill>/iteration-N/`,
  which Git ignores (`docs/AGENTS.md`).
- `SKILL.md` is ASCII: the reference validator and plain clients read it
  with the locale's codec, and under cp936 a UTF-8 sign stops them.
- `name` is the folder's name, lowercase with hyphens. `description` says
  what the skill does and when to use it, at most 1024 characters, on one
  line and without `: `, so that a client with a plain frontmatter parser
  reads it too. `SKILL.md` stays under 500 lines; what is needed only
  sometimes goes to `references/`, and `SKILL.md` says when to read it.
- Paths inside the skill are relative to its folder. A file of this
  repository is written `Construct3-RAG/<path>`, as the block in the game
  project writes it; a relative link out of the folder breaks in a copy.
- Scripts use the standard library (Pillow is optional), take everything
  from flags, never prompt, print `--help` with examples and exit codes, and
  say in every error what to write or run next. They find the project from
  the current directory upward and this repository through the project's
  `Construct3-RAG:` line; what they share is in `scripts/c3project.py`.
- What a script prints is read by a harness, not a terminal. It is UTF-8
  whatever the code page (`utf8_output`), and it stops at `--limit`, about
  10 000 characters, with a last line that says how to get the rest: a
  harness cuts longer output, not always at the end and not always saying
  so. A miss lists what comes near. A name that is not spelled out is
  refused with the nearest ones, not taken for one of them. It all prints on
  stdout, a miss and a note as much as a hit: PowerShell wraps a line of
  stderr in an error record, and a harness that shows stdout alone shows
  nothing. Only what stops the run before it answers, an unusable flag, a
  project or clone that was not found, goes to stderr with the exit code.
- A script that changes a project file checks the result before it writes
  it, writes the whole file or nothing, in the editor's layout (tabs, LF, no
  newline at the end, the editor's keys in the editor's order), and has
  `--dry-run`. `edit_sheet.py` is the one that does; what the editor writes
  per kind of event is counted in `docs/decisions/edit-sheet-script.md`.
- English only; `--locale` switches the schema wording, not the tool's.
- A check becomes an error after the two steps in
  `construct3-project/references/checker-rules.md`: the editor's message,
  then a run over the official examples that adds no finding. A style
  finding, one the editor accepts, is a warning behind `--style` and in what
  `edit_sheet.py` adds, never an error; its threshold comes from a
  measurement over the official examples, recorded with the finding.
- Guidance meant for a small model goes where that model reads: the line a
  script prints (a finding that names the event and the JSON to write) or
  the generator's helpers, which make the good shape the default. Prose
  reaches only the model that knows it needs it, so a prompt keeps a
  when-clause pointer, not the rule. A habit with no mechanical form that
  passes the official corpus stays prose. Evidence: the runs read in
  `docs/decisions/event-sheet-design-guidance.md`, "What small models read".
- A change to a script is compared, old against new, over every official
  example and the game projects: exit code, stdout and stderr
  (`construct3-project/evals/sweep_outputs.py`). A restructure shows no
  difference; a change of output shows exactly the runs it was meant for.

## Checks

```bash
python -m pytest tests/test_project_tools.py -q
python -m compileall -q skills
```

The tests install the skill in a temporary project and run the copy, and
they pin the format's constraints offline.

When the frontmatter of a `SKILL.md` changes, or the specification does, run
the reference validator as well. It fetches code from GitHub and runs it:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate skills/construct3-project
```

If the session does not allow that, report it as not run; the tests pin the
same constraints. It checks the frontmatter only: the fields, the name
against the folder, the lengths. Whether the skill helps is what the evals
measure.

## Evals

The method is <https://agentskills.io/skill-creation/evaluating-skills> and
<https://agentskills.io/skill-creation/optimizing-descriptions>. A change to
`SKILL.md`, to a reference or to what a script prints is a new iteration.

| File in `construct3-project/evals/` | Holds |
|-------------------------------------|-------|
| `evals.json` | The test cases: prompt, expected output, assertions a script can check |
| `make_fixtures.py` | One project per case and arm, outside the clone: the stand-in game or an official example, with this skill, the previous one or none |
| `trace.py` | What a run did, from its transcript: every tool call, the ones it lost, `trace.json` |
| `grade.py` | `grading.json` per run with the evidence, `benchmark.json` per iteration: mean and deviation per case and arm (`<arm>_2` is a second run of `<arm>`), and the difference between arms |
| `sweep_outputs.py` | What the scripts print over every example and game project, a dry run of a small plan included, recorded and compared |
| `train_queries.json`, `validation_queries.json` | Trigger queries, a fixed 60/40 split; near misses as the negatives |
| `run_trigger_eval.py` | Trigger rates from `claude -p`, on Windows too |

```bash
# before the change
git worktree add --detach <folder outside the clone>/rag-old HEAD
python skills/construct3-project/evals/sweep_outputs.py .local/docs/evidence/skill-evals/construct3-project/iteration-N/sweep-old.json --examples <example-projects> --projects <game folder> ...
# after the change
python skills/construct3-project/evals/sweep_outputs.py .local/docs/evidence/skill-evals/construct3-project/iteration-N/sweep-new.json --examples <example-projects> --projects <game folder> ...
python skills/construct3-project/evals/sweep_outputs.py --compare .local/docs/evidence/skill-evals/construct3-project/iteration-N/sweep-old.json .local/docs/evidence/skill-evals/construct3-project/iteration-N/sweep-new.json
python skills/construct3-project/evals/make_fixtures.py <folder outside the clone>/iteration-N --arms with_skill old_skill --old-clone <folder outside the clone>/rag-old
# after each run has reported
python skills/construct3-project/evals/trace.py <transcript>.jsonl --out <run folder>
# after the last run of the iteration
python skills/construct3-project/evals/grade.py .local/docs/evidence/skill-evals/construct3-project/iteration-N
# after a change to the description
python skills/construct3-project/evals/run_trigger_eval.py skills/construct3-project/evals/train_queries.json --project <game with .claude/skills>
```

- Each run starts clean, one agent per case and arm, and saves `answer.md`
  with the commands it ran. A baseline started below the clone reads its
  `AGENTS.md` and reaches for the checker: tell it to use nothing outside
  the project folder, read its commands, and give a run that broke its arm
  a `void.txt` with the reason. `grade.py` does not score it.
- The previous version of the skill is the baseline of a change to it. Its
  arm names a checkout of the previous commit as its clone: pointed at this
  one, the old copy reports that it differs and the agent refreshes it.
- Read the transcript of every run, not only its answer. Claude Code keeps
  it as `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`;
  the answer lists the commands a run remembers. When every assertion
  passes, the lost calls are what is left to improve: a lookup that found
  nothing, an edit that did not match.
- `timing.json` holds the tokens and the duration of the run's completion
  notice, written when it arrives. A run without one has none; nothing is
  estimated.
- One run per case and arm gives counts, not a spread. Lay a cell out more
  than once, `--arms with_skill with_skill_2`, before quoting a deviation;
  lost calls vary from 1 to 6 between two runs of the same cell.
- The description changes on the failures of the train queries only, and
  the validation queries choose between descriptions.
