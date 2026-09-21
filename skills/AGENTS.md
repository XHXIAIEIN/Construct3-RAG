# `skills/` Directory

Agent Skills in the open format of <https://agentskills.io/specification>:
one folder per skill, a `SKILL.md` with `name` and `description`, and
`scripts/`, `references/` and `assets/` beside it. The folder here is the
source. A game project holds a copy of it, made and refreshed by the skill's
`scripts/install.py`, and the copy reports when it differs from the source.

| Skill | Carries |
|-------|---------|
| `construct3-project/` | ACE lookup, sheet printer, checker and generator template for a Construct 3 folder project; the block for the project's instruction file |

## Rules

- The folder is what ships: `install.py` mirrors every file in it into the
  game project, except `evals/`, which tests the skill from here. Nothing
  else lives in it, no scratch files, outputs or notes. What an eval run
  leaves goes to `<skill>-workspace/iteration-N/` beside the folder, which
  Git ignores.
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
- English only; `--locale` switches the schema wording, not the tool's.
- A check becomes an error after the two steps in
  `construct3-project/references/checker-rules.md`: the editor's message,
  then a run over the official examples that adds no finding.
- A restructure that should not change output is compared, old against new,
  over every official example and the game projects: exit code, stdout and
  stderr (`docs/decisions/project-tools-skill.md`).

## Checks

```bash
python -m pytest tests/test_project_tools.py -q
python -m compileall -q skills
```

The tests install the skill in a temporary project and run the copy, and
they pin the format's constraints offline. The reference validator needs
network:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate skills/construct3-project
```

It checks the frontmatter only: the fields, the name against the folder,
the lengths. Whether the skill helps is what the evals measure.

## Evals

The method is <https://agentskills.io/skill-creation/evaluating-skills> and
<https://agentskills.io/skill-creation/optimizing-descriptions>. A change to
`SKILL.md`, to a reference or to what a script prints is a new iteration.

| File in `construct3-project/evals/` | Holds |
|-------------------------------------|-------|
| `evals.json` | The test cases: prompt, expected output, assertions a script can check |
| `make_fixtures.py` | One project per case and arm, outside the clone |
| `grade.py` | `grading.json` per run with the evidence, `benchmark.json` per iteration |
| `train_queries.json`, `validation_queries.json` | Trigger queries, a fixed 60/40 split; near misses as the negatives |
| `run_trigger_eval.py` | Trigger rates from `claude -p`, on Windows too |

```bash
python skills/construct3-project/evals/make_fixtures.py <folder outside the clone>/iteration-N
python skills/construct3-project/evals/grade.py skills/construct3-project-workspace/iteration-N
python skills/construct3-project/evals/run_trigger_eval.py skills/construct3-project/evals/train_queries.json --project <game with .claude/skills>
```

- Each run starts clean, one agent per case and arm, and saves `answer.md`
  with the commands it ran. A baseline started below the clone reads its
  `AGENTS.md` and reaches for the checker: tell it to use nothing outside
  the project folder, read its commands, and give a run that broke its arm
  a `void.txt` with the reason. `grade.py` does not score it.
- `timing.json` holds the tokens and the duration of the run's completion
  notice, written when it arrives. A run without one has none; nothing is
  estimated.
- One run per case and arm gives counts, not a spread. Repeat the runs
  before quoting a deviation.
- The description changes on the failures of the train queries only, and
  the validation queries choose between descriptions.
