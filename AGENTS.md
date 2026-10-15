# Construct3-RAG for AI Agents

## 1. What this repository is

This repository holds bilingual Construct 3 reference data under `data/`,
which an agent reads directly. It also holds an optional lookup service in
`src/` and, in `skills/`, an agent skill that carries the project tools into
a game project. Do not write the Construct 3 version or the counts into
text, because every data refresh changes them; read them from
`data/c3-schemas/_index.json`.

The priorities, in order:

1. Look up addons, ACEs and the scripting API exactly.
2. Give English and Chinese data that an answer can cite.
3. Find example projects by topic.
4. Keep the data usable from the committed files alone.
5. Let the service answer exact queries and decline the rest.

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
| JavaScript or TypeScript API | `python skills/construct3-agent-plugin/scripts/lookup_script_api.py NAME` prints an interface, a plugin or behavior, or a member from the `.d.ts` files of `data/c3-ts-defs/`; global names are in `data/c3-ts-defs/autocomplete-data.json` |
| Types for an addon under development | editor `data/c3-ts-defs/sdk/`, runtime `data/c3-ts-defs/preview/interfaces/sdk/`; the guide and the samples are in the `Construct3-Manual` and `Construct-Addon-SDK` clones |
| Example projects for a topic | `python skills/construct3-agent-plugin/scripts/search_guides.py WORD ...`, which also prints the pitfall entries that hold the words; or `data/c3-examples/{locale}/*.json` by `tags` and `used-addons`. The event sheets are in the `Construct-Example-Projects` clone, `example-projects/{id}/eventSheets/`; read them as events with `python skills/construct3-agent-plugin/scripts/print_sheet.py --project <example folder>` |
| Official examples that use an ACE | `lookup_ace.py` ends each entry it prints in full with the number of those examples and the `print_sheet.py` commands of up to three uses, from `data/c3-example-usage/` |
| Translation of a string, editor text outside the schemas | `data/c3-lang/{locale}.json`, `text` |
| What a project folder holds: what `project.c3proj` lists, image file names, the formats of sounds, fonts and icons, which files the editor ignores | `data/c3-guides/constructs-project-format.md`, Scirra's guide that the `llm-context.md` of every project links; how this repository applies it is in `prompts/references/hand-editing-project-files.md`, "The project folder" |
| What a field means before writing an event or a script | `data/AGENTS.md`; the full reference is `docs/guide/data-format.md` |

The structural fields (`id`, `scriptName`, `category`, `params.*.type`) are
identical across locales. To the user, an ACE is its `display-text` in their
language ("Array: Set value at 0 to 1", "数组: 设置数组 0 值为 1"), with the
object's name and the parameters in words. The ids and any internal notation
stay in the data and the tools. Section 3 says how to structure an
interaction. `POST /search` on the running service returns the same data
(`docs/guide/api-reference.md`).

`plugins/system.json` and `plugins/_common.json` run to thousands of lines. A
reader that stops at 2000 lines shows only part of them, so an ACE below the
cut looks missing. Ask the script for the part instead:

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait
```

It prints the matching conditions, actions and expressions of `System`, or
of a plugin or behavior given by id or display name. Run in a game project,
it does the same for one of the project's objects with its behaviors. Each
entry comes with its parameters and the JSON to write
(`skills/construct3-agent-plugin/SKILL.md`, "Look an ACE up before writing
it"). Given an effect's id or name, it prints the effect's parameters.

## 3. Design event sheet logic

Before you design an interaction, data storage, timing or animation, read
and follow `prompts/event-sheet-thinking.md`. Then verify the names with
section 2.

- If a project shows a runtime behaviour of events that changes which
  events are written, record it in the topic file of its group under
  `prompts/pitfalls/`, with its source, and record its conclusion as one
  line in `prompts/event-sheet-pitfalls.md`. A lesson about the project file
  format, the editor, the preview or the look goes where "Adding an entry"
  there says.
- Events written into a project or a generator follow
  `prompts/event-sheet-style.md`, which describes how the official examples
  organise, name and comment a sheet.

## 4. Use from another project

A game project reaches this repository through two things it holds. One is
the `construct3-agent-plugin` skill, a copy of
`skills/construct3-agent-plugin/`. The other is the block of
`skills/construct3-agent-plugin/assets/game-project-block.md` in its
instruction file; the block's `Construct3-RAG:` line locates the schemas.
Before you place the block by hand or change it, read
`prompts/game-project-AGENTS.md`.

- If Claude Code runs with the `construct3` plugin enabled (the skill is
  listed as `construct3:construct3-agent-plugin`), the project needs no
  copy. Its instruction file names the scripts in the plugin's folder, and
  nothing is installed.
- If the game project has no `construct3-agent-plugin` folder under
  `.agents/skills/` or another client's skills folder, and no plugin,
  install the skill before you read or write the first project file. Run
  this command from the project folder:

  ```bash
  python <this repository>/skills/construct3-agent-plugin/scripts/install.py
  ```

  It copies the skill. When no instruction file there names this
  repository, it adds the block to the project's `AGENTS.md` with the path
  filled in, and the line `@AGENTS.md` to `CLAUDE.md`. The block sits
  between markers. The helpers of `tools/build_project.py` in a game
  generated from the template sit between markers too. `install.py`
  replaces the block or the helpers with the current version when they are
  older and nobody edited them. It changes no other file. Say in one
  sentence what it wrote, then read the installed `SKILL.md`. Use
  `--into .claude/skills` for Claude Code, `--into .trae/skills` for TRAE,
  `--no-block` when the user keeps the instruction files to themselves, and
  `--dry-run` to see first.
- If the sibling clones are missing, or there is no game project yet, run
  `python <this repository>/scripts/bootstrap.py --project <folder>`. It
  clones what is missing beside this repository, creates the folder as an
  empty project when it does not exist, and runs `install.py` on it. The
  README's first section gives the two commands for a machine that has only
  the URL.
- An installed copy says when it differs from
  `skills/construct3-agent-plugin/` here and prints the command that
  refreshes it. `check_project.py` also fails when this repository's clone
  is behind its upstream and holds no work of the user's, and prints the
  fast-forward and the refresh. Run what they print.
- If the user does not want the skill in the project, remove the copy and
  run the scripts from this repository in place:
  `python <this repository>/skills/construct3-agent-plugin/scripts/<script>.py
  --project <game folder>`. Do not install again in the session.

## 5. Change code or data

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
- `plugin/` is built from `skills/construct3-agent-plugin/`, `data/` and
  `prompts/` by `python scripts/build_plugin.py`, and committed with them.
  Edit the source, then build, because the next build overwrites an edit
  inside `plugin/`, and `tests/test_plugin_folder.py` fails until the build
  is run. The build sets the plugin's version and raises its patch itself.
  Raise `version` in `scripts/plugin/plugin.json` only for a minor or major
  release (`docs/decisions/plugin-tracks-commits.md`). If a merge leaves
  conflicts in `plugin/`, resolve the sources, run the build, stage
  `plugin/`, then commit the merge. The end marker line of
  `skills/construct3-agent-plugin/assets/build_project.py` conflicts
  whenever both sides changed its helpers, because it carries their stamp.
  Keep either side. Before the build, paste the end line that
  `tests/test_skill_build_project.py` prints. During a merge the build
  compares with the commit the merge will share with `origin/main`, so one
  run writes the right version.
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
python -m compileall -q src scripts tests skills
git diff --check
```

Also run the checks in the `AGENTS.md` of the touched directories.
`.github/workflows/checks.yml` runs the first two commands and
`build_plugin.py --check` on every push to `main` and every pull request,
and the update workflow calls that workflow.

Done means: an observable problem is solved; the default path was run live,
with its failure and fallback explained; old paths, dead configuration,
orphaned tests and stale docs are removed; the report is split into
verified, unverified, risk and next decision.

## 6. Entry points

```bash
python scripts/setup.py                       # lookup service
python scripts/init.py                        # refresh CDN data, export schemas
python -m uvicorn src.api:app --port 8765     # service only
python -m pytest tests/test_query_gold.py -q   # Direct Lookup gold set
```

## 7. Where to read more

| Need | Document |
|------|----------|
| Install and run | `docs/guide/quick-start.md` |
| HTTP API | `docs/guide/api-reference.md` |
| Data files and fields | `docs/guide/data-format.md` |
| Event sheet design, sourced pitfalls, the examples' authoring style | `prompts/event-sheet-thinking.md`, `prompts/event-sheet-pitfalls.md` and its topic files in `prompts/pitfalls/`, `prompts/event-sheet-style.md`, `docs/decisions/event-sheet-design-guidance.md` |
| Complete design questions, answer validation and conservative static reuse | `skills/construct3-agent-plugin/references/design-review.md`, `docs/decisions/design-review-packets.md` |
| The visual language of published games, their motion statistics and the reproducible analyzer | `docs/decisions/published-game-visual-language.md`, `docs/dev/published-game-analysis.md`, `scripts/reference_games/` |
| Design tokens of the tool pages (the recording review page and the API playground): palettes, type scale, motion and the contrast contract | `docs/decisions/design-tokens.md`, `docs/decisions/preview-player.md` |
| Slot case as a program, hand-editing project JSON, bars and life counters by the art they have, feel recipes, an attack's timing, animation and hit effects, sounds and placeholder audio, sequences and dialogue run from a data file, menus steered by keys or a gamepad | `prompts/references/` |
| A new project's sheets, layers, objects and look: the paper-and-ink default and its font, colours by role, text, pixel art, what other design skills do, and where its art comes from | `prompts/references/new-project.md`, `docs/decisions/paper-and-ink-look.md`, `docs/decisions/game-look-from-design-skills.md`, `docs/decisions/art-from-the-image-tool.md` |
| The project tools the skill carries into a game project: what each does, and changing and evaluating them | `skills/construct3-agent-plugin/SKILL.md`, `skills/AGENTS.md` |
| Architecture and package boundaries | `docs/dev/architecture.md`, `src/AGENTS.md` |
| Project and skill audit findings, reproduction boundaries and repair priorities | `docs/dev/skills-audit.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed | `docs/decisions/` |
| Delegating an ACE lookup or check to a Claude Code sub-agent | `.claude/agents/ace-lookup.md` |
| Polishing instruction files, docs, records, prompts and code in one verified run; start it when no other session edits the repository | `.claude/workflows/polish.js` |
