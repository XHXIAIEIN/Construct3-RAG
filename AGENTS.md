# Construct3-RAG for AI Agents

## 1. What this repository is

This repository holds bilingual Construct 3 reference data under `data/`,
which an agent reads directly, the pipeline that refreshes it from the
editor's CDN, and an optional lookup service in `src/`. The Construct 3
version and the counts stay in `data/c3-schemas/_index.json`, because every
data refresh changes them. A reply reads them from there, and a document
names the file instead of the numbers.

The tools that make games from this data live in
[Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills):
the `construct3-agent-plugin` skill, the event sheet prompts, the Claude
Code plugin `construct3` built from them, and their tests and decision
records. Clone that repository beside this one, as the `Construct3-Manual`,
`Construct-Example-Projects` and `Construct-Addon-SDK` clones are, before
you run a script of the skill:

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Agent-Skills ../Construct3-Agent-Skills
```

Its build reads this clone's `data/`. Why:
`docs/decisions/skill-in-agent-skills.md`.

The priorities, in order:

1. Hold every addon, ACE and scripting API exactly, in English and Chinese,
   so that an answer can cite the data.
2. Refresh the data each release without a person, and report what the
   release changed.
3. Keep the data usable from the committed files alone.
4. Let the service answer exact queries and decline the rest.

`data/` and the CDN update pipeline are the core tier. The lookup service is
optional (`src/AGENTS.md`). Moving a feature between the tiers needs evidence
and a record in `docs/decisions/`.

## 2. Answer a Construct 3 fact question

Answer from the data. An ACE missing from the schema does not exist, unless
`data/c3-schemas/{locale}/_deprecated.json` lists it. In that case the
editor deprecated it: it still opens old projects that use it, and a new
project should not use it.

1. Find the id in `data/c3-schemas/_index.json` under `plugins`, `behaviors`
   or `effects`; the entry gives `file` and the ACE counts. A localized name
   leads to its id through `data/c3-schemas/{locale}/_index.json`.
2. Open `data/c3-schemas/{locale}/{file}`, with the locale from `languages`
   (`en-US`, `zh-CN`).
3. Find the ACE by `id`, by `list-name` (conditions, actions) or by
   `translated-name` (expressions). `display-text` is the event sheet wording
   and `params` the parameters. `scriptName` is the JavaScript name of a
   condition or action, and the name a project file holds for an expression.

| Question | Where |
|----------|-------|
| Which plugins, behaviors, effects exist | `data/c3-schemas/_index.json` |
| Addon names in one language | `data/c3-schemas/{locale}/_index.json` |
| ACEs of a plugin | `data/c3-schemas/{locale}/plugins/{id}.json` |
| ACEs of a behavior | `data/c3-schemas/{locale}/behaviors/{id}.json` |
| ACEs shared by every world object: overlap, collisions, instance variables, hierarchy, UID, Z order | `data/c3-schemas/{locale}/plugins/_common.json`, read beside the plugin file, whose `commonAces` lists the ones that plugin gets |
| Effect parameters | `data/c3-schemas/{locale}/effects/{id}.json` |
| Whether an addon or ACE is deprecated, and the current ACE of the same name | `data/c3-schemas/{locale}/_deprecated.json`; a deprecated ACE the schema kept also has `isDeprecated` |
| JavaScript or TypeScript API | the `.d.ts` files of `data/c3-ts-defs/`; global names in `data/c3-ts-defs/autocomplete-data.json`; `lookup_script_api.py` of the sibling clone prints an interface, a plugin or behavior, or a member |
| Types for an addon under development | editor `data/c3-ts-defs/sdk/`, runtime `data/c3-ts-defs/preview/interfaces/sdk/`; the guide and the samples are in the `Construct3-Manual` and `Construct-Addon-SDK` clones |
| Example projects for a topic | `data/c3-examples/{locale}/*.json` by `tags` and `used-addons`; the event sheets are in the `Construct-Example-Projects` clone, `example-projects/{id}/eventSheets/` |
| Official examples that use an ACE | `data/c3-example-usage/{plugins,behaviors}/{id}.json` |
| Translation of a string, editor text outside the schemas | `data/c3-lang/{locale}.json`, `text` |
| What a project folder holds: what `project.c3proj` lists, image file names, the formats of sounds, fonts and icons, which files the editor ignores | `data/c3-guides/constructs-project-format.md`, Scirra's guide that the `llm-context.md` of every project links |
| What a field means | `data/AGENTS.md`; the full reference is `docs/guide/data-format.md` |
| How to write an event, design event sheet logic, check or change a game project | Construct3-Agent-Skills: its `AGENTS.md`, `prompts/` and the skill |

The structural fields (`id`, `scriptName`, `category`, `params.*.type`) are
identical across locales. To the user, an ACE is its `display-text` in their
language ("Array: Set value at 0 to 1", "数组: 设置数组 0 值为 1"), with the
object's name and the parameters in words. The ids and any internal notation
stay in the data and the tools. `POST /search` on the running service
returns the same data (`docs/guide/api-reference.md`).

`plugins/system.json` and `plugins/_common.json` run to thousands of lines. A
reader that stops at 2000 lines shows only part of them, so an ACE below the
cut looks missing. Ask the sibling clone's script for the part instead.
`--rag .` makes it read this clone's data, which can be newer than the
plugin's copy:

```bash
python ../Construct3-Agent-Skills/plugin/skills/construct3-agent-plugin/scripts/lookup_ace.py --rag . System wait
```

It prints the matching conditions, actions and expressions of `System`, or
of a plugin or behavior given by id or display name, each with its
parameters, the JSON to write and the official examples that use it. Given
an effect's id or name, it prints the effect's parameters. From a worktree
of this repository, write the clone's absolute path in place of `..`. The
`ace-lookup` sub-agent of `.claude/agents/` does the same lookups for a
session that wants the schema files out of its context. Without the clone,
read the schema file in parts with Grep and Read.

## 3. Use from a game project

A game project reaches this data through Construct3-Agent-Skills: its
`plugin/` folder carries a built copy of `data/`, and the skill's scripts
find it through the project's `Construct3-RAG:` line, `--rag` or
`CONSTRUCT3_RAG`. Section 4 of that repository's `AGENTS.md` says how to
install the skill or the plugin. A game project needs no clone of this
repository.

## 4. Change code or data

Before you edit:

1. Read the `AGENTS.md` of every directory you touch, because it holds that
   area's rules and checks. Run `git status` and keep the changes you did
   not make.
2. Trace the call chain from `src/api.py` or `scripts/`.
3. Classify the feature: default, optional, experimental or legacy.
4. For a significant feature or a refactor, write down the user task,
   whether the default path calls it today, the evidence (queries, logs, a
   benchmark) and why the simpler option, or reading the data directly, is
   not enough. Then keep, simplify, rewrite or delete it. Without evidence,
   run a baseline and an experiment first, and leave the production path
   untouched.

Rules:

- Start from the observable outcome, and build the simpler baseline before
  the complex version.
- A test pins an expectation, not its correctness. If the expectation is
  wrong, fix it first, then the test.
- A product choice with a visible effect gets its evidence, options and
  trade-offs in `docs/decisions/`.
- The default path runs offline and deterministically: importing a module
  or running a query starts no network request, model loading or CDN
  refresh.
- Every configuration value has a caller. Removing a feature removes its
  configuration, dependencies, tests and docs in the same change, with the
  reason in `docs/decisions/`.
- Use type hints and `pathlib.Path`, and log specific exceptions at the
  boundary.
- A change to `data/` reaches the plugin through Construct3-Agent-Skills.
  Its daily workflow builds the plugin from this repository's `main` and
  runs the skill's tests on the build. A change that renames or removes a
  field the skill reads is made in both repositories, the skill first.
- Docs and tests change with the behavior. The README puts the data first
  and the service second. `README_CN.md` carries the content of `README.md`;
  `README.md` names no Chinese text or locale besides its link to
  `README_CN.md`, and the Chinese examples stay in `README_CN.md`.
  `docs/dev/architecture.md` describes only what runs. Test totals stay out
  of the docs.
- A commit message or PR text names an issue of another repository in words
  or as a URL in backticks, never as `owner/repo#N` or `#N`, because GitHub
  turns those into a public cross-reference on that issue's timeline, which
  cannot be taken back. A source line in a document may use the short form,
  because GitHub parses only commits, issues and PRs.

Before you finish, run these:

```bash
python -m pytest -q
python -m compileall -q src scripts tests
git diff --check
```

Also run the checks in the `AGENTS.md` of the touched directories.
`.github/workflows/checks.yml` runs the first two commands on every push to
`main` and every pull request, and the update workflow calls that workflow.

Done means: an observable problem is solved; the default path was run live,
with its failure and fallback explained; old paths, dead configuration,
orphaned tests and stale docs are removed; the report is split into
verified, unverified, risk and next decision.

## 5. Entry points

```bash
python scripts/setup.py                       # lookup service
python scripts/init.py                        # refresh CDN data, export schemas
python -m uvicorn src.api:app --port 8765     # service only
python -m pytest tests/test_query_gold.py -q   # Direct Lookup gold set
```

## 6. Where to read more

| Need | Document |
|------|----------|
| Install and run | `docs/guide/quick-start.md` |
| HTTP API | `docs/guide/api-reference.md` |
| Data files and fields | `docs/guide/data-format.md` |
| Make or change a game, design event sheet logic, the skill's tools and their evals, the Claude Code plugin | Construct3-Agent-Skills, cloned beside this repository: its `README.md`, `AGENTS.md`, `prompts/` and `docs/decisions/` |
| The visual language of published games, their motion statistics and the reproducible analyzer | `docs/decisions/published-game-visual-language.md`, `docs/dev/published-game-analysis.md`, `scripts/reference_games/` |
| Architecture and package boundaries | `docs/dev/architecture.md`, `src/AGENTS.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed | `docs/decisions/README.md`, the index of the records |
| Delegating an ACE lookup or check to a Claude Code sub-agent | `.claude/agents/ace-lookup.md` |
| Polishing instruction files, docs, records and code in one verified run; start it when no other session edits the repository | `.claude/workflows/polish.js` |
