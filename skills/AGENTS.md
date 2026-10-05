# `skills/` Directory

Agent Skills in the open format of <https://agentskills.io/specification>:
one folder per skill, a `SKILL.md` with `name` and `description`, and
`scripts/`, `references/` and `assets/` beside it. The folder here is the
source. A game project holds a copy of it, made and refreshed by the skill's
`scripts/install.py`, and the copy reports when it differs from the source.
`plugin/`, the Claude Code plugin, holds another copy, which
`scripts/build_plugin.py` writes and `tests/test_plugin_folder.py` keeps
equal to this folder.

`construct3-agent-plugin/` is the one skill here: the project tools for a
Construct 3 folder project, listed under "Scripts" in its `SKILL.md`, and
the block for the project's instruction file.

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
  reads it too.
- `SKILL.md` stays under 500 lines and the 5000 tokens the specification
  recommends for what loads on activation. Every run reads all of it before
  its first command, so it holds only what every activation needs and no
  script says at the moment it matters. A new script or feature gets one
  row in the table of scripts and, when it needs more, one sentence saying
  when to read its file in `references/`; what a script prints when it is
  needed is not repeated. Evidence: `docs/decisions/project-tools-skill.md`,
  "What holds the design in place".
- Paths inside the skill are relative to its folder. A file of this
  repository is written `Construct3-RAG/<path>`, as the block in the game
  project writes it; a relative link out of the folder breaks in a copy.
  The plugin bullet of `SKILL.md` says where such a path lies in the plugin,
  so the skill's text names no file that the plugin holds only in a bundle.
  A script prints a file of this repository by its absolute path. It prints
  a TypeScript declaration that the plugin holds only in a bundle as the
  `lookup_script_api.py` command that prints it
  (`docs/decisions/plugin-folder.md`).
- Scripts use the standard library, except `prepare_art.py`, which needs
  Pillow to read, cut out and resample pictures (`open_in_editor.py`
  drives the machine's Edge or Chrome over the DevTools protocol, and prints
  its check as steps for the agent's own browser tool where there is
  neither), take everything from flags,
  never prompt, print `--help` with examples and exit codes, and say in
  every error what to write or run next. They find the project from
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
- The generator template keeps its helpers between two marker lines, and
  the end line carries their version and the stamp of the lines between:
  `install.py` replaces that part of a game's `tools/build_project.py` when
  it is older and unedited, and keeps every other line. A change between the
  markers fails `tests/test_skill_build_project.py` until the end line it
  prints is pasted. A helper reads nothing outside the markers but what
  every game's generator has, so a setting a new helper needs gets its
  default between the markers.
- A script that changes a project file checks the result before it writes
  it, writes the whole file or nothing, in the editor's layout (tabs, LF, no
  newline at the end, the editor's keys in the editor's order), and has
  `--dry-run`. `edit_sheet.py` is the one that does; the keys the editor
  writes per kind of event, in order, are its templates.
- The skill's text and its scripts' own wording are English; `--locale`
  switches the schema wording a script prints, not the script's own.
- A rule about what a project file must hold is read from the editor's loader
  as a whole call chain, not from the one message a user pasted: the next
  assertion in the same function costs another round trip through them. What
  the editor writes into every project is measured from the official examples,
  and `tests/test_skill_build_project.py` compares the generated project with
  that measurement, so a key missing from the generator fails here instead of
  in the editor.
- Scirra's guide
  [Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275),
  kept in `data/c3-guides/constructs-project-format.md`,
  states what the format keeps across releases: what `project.c3proj`
  indexes, image file names, the formats of sounds, fonts and icons, which
  files the editor ignores. Read it before a rule about the folder, a file
  name or a file format. The `llm-context.md` the editor writes into every
  project links it; the official examples were saved before the editor wrote
  that file (r477, `Construct3-Manual/releases/beta.json`), so a measurement
  over them shows neither it nor anything the editor started writing since.
- A check becomes an error after the two steps in
  `construct3-agent-plugin/references/checker-rules.md`: the editor's message,
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
  (`construct3-agent-plugin/evals/sweep_outputs.py`). A restructure shows no
  difference; a change of output shows exactly the runs it was meant for.
  `scripts/output_diff.py [REF]` makes the comparison against a git ref in
  one command and prints the first differing line of each case; it covers
  the official examples, `new_project.py` and the generator template, and
  `sweep_outputs.py` also takes the game projects.

## Checks

```bash
python -m pytest tests -q -k test_skill_
python -m compileall -q skills
```

The tests install the skill in a temporary project and run the copy, and
they pin the format's constraints offline.

When the frontmatter of a `SKILL.md` changes, or the specification does, run
the reference validator as well. It checks the frontmatter only: the fields,
the name against the folder, the lengths; whether the skill helps is what
the evals measure. It fetches code from GitHub and runs it:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate skills/construct3-agent-plugin
```

If the session does not allow that, report the validator as not run; the
tests pin the same constraints.

## Evals

The method is <https://agentskills.io/skill-creation/evaluating-skills> and
<https://agentskills.io/skill-creation/optimizing-descriptions>. A change to
`SKILL.md`, to a reference or to what a script prints is a new iteration.

| File in `construct3-agent-plugin/evals/` | Holds |
|-------------------------------------|-------|
| `evals.json` | The test cases: prompt, expected output, assertions a script can check |
| `make_fixtures.py` | One project per case and arm, outside the clone: the stand-in game, an official example or the empty project of `new_project.py`, with this skill, the previous one or none |
| `trace.py` | What a run did, from its transcript: every tool call, the ones it lost, `trace.json` |
| `grade.py` | `grading.json` per run with the evidence, `benchmark.json` per iteration: mean and deviation per case and arm (`<arm>_2` is a second run of `<arm>`), and the difference between arms |
| `measure_design.py` | What each rule of `scripts/review_design.py` finds over the official examples and game projects, with looser variants, and every hit as JSON to read before a rule becomes a finding |
| `sweep_outputs.py` | What the scripts print over every example and game project, a dry run of a small plan included, recorded and compared |
| `sweep_round_trip.py` | Every event of every example put back as `print_sheet.py --show` prints it, and the events after which `edit_sheet.py` would write a different sheet |
| `train_queries.json`, `validation_queries.json` | Trigger queries, a fixed 60/40 split; near misses as the negatives |
| `run_trigger_eval.py` | Trigger rates from `claude -p`, on Windows too |

```bash
# before the change
git worktree add --detach <folder outside the clone>/rag-old HEAD
python skills/construct3-agent-plugin/evals/sweep_outputs.py .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N/sweep-old.json --examples <example-projects> --projects <game folder> ...
# after the change
python skills/construct3-agent-plugin/evals/sweep_outputs.py .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N/sweep-new.json --examples <example-projects> --projects <game folder> ...
python skills/construct3-agent-plugin/evals/sweep_outputs.py --compare .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N/sweep-old.json .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N/sweep-new.json
python skills/construct3-agent-plugin/evals/make_fixtures.py <folder outside the clone>/iteration-N --arms with_skill old_skill --old-clone <folder outside the clone>/rag-old
# after each run has reported
python skills/construct3-agent-plugin/evals/trace.py <transcript>.jsonl --out <run folder>
# after the last run of the iteration
python skills/construct3-agent-plugin/evals/grade.py .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N
python skills/construct3-agent-plugin/scripts/open_in_editor.py .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N --out .local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-N/opened.json
# after a change to the description
python skills/construct3-agent-plugin/evals/run_trigger_eval.py skills/construct3-agent-plugin/evals/train_queries.json --project <game with .claude/skills>
```

- Each run starts clean, one agent per case and arm, and saves
  `outputs/answer.md` with the commands it ran. A baseline started below the
  clone reads its `AGENTS.md` and reaches for the checker, so tell it to use
  nothing outside the project folder. Then read the commands its answer
  lists. If a run broke its arm, put the reason in its
  `void.txt`; `grade.py` does not score that run.
- The previous version of the skill is the baseline of a change to it. Its
  arm, `old_skill`, names a checkout of the previous commit as its clone
  (`--old-clone`), because an old copy pointed at this clone reports that it
  differs and the agent refreshes it.
- Make fixtures from a worktree branch that tracks nothing, or from a clone
  level with its upstream. A fixture names the clone that
  `make_fixtures.py` ran from, and if that clone's branch trails its
  upstream, the checker gives the runs a pull of it in the middle of the
  iteration.
- Read the transcript of every run, not only its answer, because the answer
  lists only the commands a run remembers. Claude Code keeps the transcript
  as `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`.
  When every assertion passes, the lost calls are what is left to improve:
  a lookup that found nothing, an edit that did not match.
- When a run's completion notice arrives, write the tokens and the duration
  it gives into the run's `timing.json`. A run without one has no time or
  tokens in the benchmark; nothing is estimated.
- One run per case and arm gives counts, not a spread. Lay a cell out more
  than once, `--arms with_skill with_skill_2`, before quoting a deviation;
  lost calls vary from 1 to 6 between two runs of the same cell.
- The description changes on the failures of the train queries only, and
  the validation queries choose between descriptions.
