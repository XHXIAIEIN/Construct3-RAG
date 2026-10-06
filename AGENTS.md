# Construct3-RAG for AI Agents

## 1. What this repository is

Bilingual Construct 3 reference data under `data/`, read directly, plus an
optional lookup service in `src/`, and an agent skill in `skills/` that
carries the project tools into a game project. Version and counts:
`data/c3-schemas/_index.json`, never hardcoded.

Priorities, in order: exact addon, ACE and scripting lookup; citable
English and Chinese data; example projects by topic; works from the
committed files alone; the service answers exact queries and declines the rest.

Tiers: `data/` and the CDN update pipeline are core; the lookup service is
optional (`src/AGENTS.md`). Moving a feature between tiers needs evidence and
a record in `docs/decisions/`.

## 2. SOP: answer a Construct 3 fact question

Answer from the data. An ACE missing from the schema does not exist, unless
`data/c3-schemas/{locale}/_deprecated.json` lists it: the editor deprecated
it, still opens old projects that use it, and a new project should not.

1. Id: `data/c3-schemas/_index.json` under `plugins`, `behaviors` or
   `effects`; the entry gives `file` and ACE counts. Localized name to id:
   `data/c3-schemas/{locale}/_index.json`.
2. File: `data/c3-schemas/{locale}/{file}`, locale from `languages`
   (`en-US`, `zh-CN`).
3. ACE: by `id`, `list-name` (conditions, actions) or `translated-name`
   (expressions). `display-text` is the event sheet wording, `params` the
   parameters, `scriptName` the scripting name.

| Question | Where |
|----------|-------|
| Which plugins, behaviors, effects exist | `data/c3-schemas/_index.json` |
| Addon names in one language | `data/c3-schemas/{locale}/_index.json` |
| ACEs of a plugin | `data/c3-schemas/{locale}/plugins/{id}.json` |
| ACEs of a behavior | `data/c3-schemas/{locale}/behaviors/{id}.json` |
| ACEs shared by every world object: overlap, collisions, instance variables, hierarchy, UID, Z order | `data/c3-schemas/{locale}/plugins/_common.json`, in addition to the plugin file, whose `commonAces` lists the ones that plugin gets |
| Effect parameters | `data/c3-schemas/{locale}/effects/{id}.json` |
| Whether an addon or ACE is deprecated, and the current ACE of the same name | `data/c3-schemas/{locale}/_deprecated.json`; a deprecated ACE the schema kept also has `isDeprecated` |
| JavaScript or TypeScript API | `python skills/construct3-agent-plugin/scripts/lookup_script_api.py NAME`: an interface, a plugin or behavior, or a member, from the `.d.ts` files of `data/c3-ts-defs/`; global names in `data/c3-ts-defs/autocomplete-data.json` |
| Types for an addon under development | editor `data/c3-ts-defs/sdk/`, runtime `data/c3-ts-defs/preview/interfaces/sdk/`; guide and samples in the `Construct3-Manual` and `Construct-Addon-SDK` clones |
| Example projects for a topic | `python skills/construct3-agent-plugin/scripts/search_guides.py WORD ...`, which also prints the pitfall entries that hold the words, or `data/c3-examples/{locale}/*.json` by `tags` and `used-addons`; event sheets in the `Construct-Example-Projects` clone, `example-projects/{id}/eventSheets/`, read as events with `python skills/construct3-agent-plugin/scripts/print_sheet.py --project <example folder>` |
| Translation of a string, editor text outside the schemas | `data/c3-lang/{locale}.json`, `text` |
| What a project folder holds: what `project.c3proj` lists, image file names, the formats of sounds, fonts and icons, which files the editor ignores | `data/c3-guides/constructs-project-format.md`, Scirra's guide that the `llm-context.md` of every project links; how this repository applies it: `prompts/references/hand-editing-project-files.md`, "The project folder" |
| What a field means before writing an event or a script | `data/AGENTS.md`; full reference `docs/guide/data-format.md` |

Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are
identical across locales. To the user, an ACE is its `display-text` in
their language ("Array: Set value at 0 to 1", "数组: 设置数组 0 值为 1"), with the
object's name and the parameters in words; ids and any internal notation
stay in the data and the tools. How to structure an interaction is section 3.
`POST /search` on the running service returns the same data
(`docs/guide/api-reference.md`).

`plugins/system.json` and `plugins/_common.json` are thousands of lines
long. A reader that stops at 2000 lines shows part of them, and an ACE below
the cut looks missing. Ask for the part instead:

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait
```

prints the matching conditions, actions and expressions of `System`, of a
plugin or behavior by id or display name, or, run in a game project, of one
of its objects with its behaviors, each with its parameters and the JSON to
write (`skills/construct3-agent-plugin/SKILL.md`, "Look an ACE up before writing
it"). Given an effect's id or name, it prints the effect's parameters.

## 3. SOP: design event sheet logic

Interactions, data storage, timing, animation: read and follow
`prompts/event-sheet-thinking.md`, then verify names with section 2.

- UID links between objects, `Pick all` followed by a pick from a stored
  link, or a timer, tween or table rebuilt from variables: redesign.
- A runtime behaviour of events learned from a project, one that changes
  which events are written, goes into the topic file of its group under
  `prompts/pitfalls/`, with its source, and its conclusion goes into
  `prompts/event-sheet-pitfalls.md` as one line. A lesson about the project
  file format, the editor, the preview or the look goes where "Adding an
  entry" there says.
- Events written into a project or a generator follow
  `prompts/event-sheet-style.md`: how the official examples organise, name
  and comment a sheet.

## 4. Use from another project

A game project reaches this repository through two things it holds: the
`construct3-agent-plugin` skill, a copy of `skills/construct3-agent-plugin/`,
and, in its instruction file, the block of
`skills/construct3-agent-plugin/assets/game-project-block.md`, whose
`Construct3-RAG:` line locates the schemas. Before placing the block by
hand or changing it, read `prompts/game-project-AGENTS.md`.

- Claude Code with the `construct3` plugin enabled (the skill is listed as
  `construct3:construct3-agent-plugin`): the project needs no copy. Its
  instruction file names the scripts in the plugin's folder, and nothing
  is installed.
- Working in a game project that has no `construct3-agent-plugin` folder under
  `.agents/skills/` or another client's skills folder, and no plugin: install it before
  the first project file is read or written, from the project folder:

  ```bash
  python <this repository>/skills/construct3-agent-plugin/scripts/install.py
  ```

  It copies the skill, adds the block to the project's `AGENTS.md` when
  no instruction file there names this repository, with the path filled in,
  and the line `@AGENTS.md` to `CLAUDE.md`. In a game generated from the
  template it also replaces the helpers between the markers of
  `tools/build_project.py` when they are an older version left unedited.
  It changes no other file. Say in one sentence what it wrote, then read
  the installed `SKILL.md`.
  `--into .claude/skills` for Claude Code, `--into .trae/skills` for TRAE;
  `--no-block` when the user keeps the instruction files to themselves;
  `--dry-run` to see first.
- The sibling clones are missing, or there is no game project yet:
  `python <this repository>/scripts/bootstrap.py --project <folder>` clones
  what is missing beside this repository, creates the folder as an empty
  project when it does not exist, and runs `install.py` on it. The README's
  first section gives the two commands for a machine that has only the URL.
- An installed copy says when it differs from `skills/construct3-agent-plugin/`
  here and prints the command that refreshes it. `check_project.py` also
  fails when the clone is behind its upstream and holds no work of the
  user's, and prints the pull and the refresh. Run what they print.
- The user does not want it in the project: remove the copy, run the
  scripts from this repository in place,
  `python <this repository>/skills/construct3-agent-plugin/scripts/<script>.py
  --project <game folder>`, and do not install again in the session.

## 5. SOP: change code or data

Before editing:

1. Read the `AGENTS.md` of every directory touched; it holds that area's
   rules and checks. Run `git status` and keep the changes you did not make.
2. Trace the call chain from `src/api.py` or `scripts/`.
3. Classify the feature: default, optional, experimental, legacy.
4. Significant feature or refactor: write down the user task, whether the
   default path calls it today, the evidence (queries, logs, benchmark) and
   why the simpler option, or reading the data directly, does not do. Then
   keep, simplify, rewrite or delete. No evidence: baseline and experiment
   first, production path untouched.

Rules:

- Observable outcome first, simpler baseline before the complex version.
- A test pins an expectation, not its correctness: fix a wrong expectation,
  then the test.
- A product choice with visible effect gets evidence, options and
  trade-offs in `docs/decisions/`.
- Default path offline and deterministic: no network, model loading or CDN
  refresh during import or a query.
- Every configuration value has a caller. Removing a feature removes its
  configuration, dependencies, tests and docs in the same change, with the
  reason in `docs/decisions/`.
- Type hints, `pathlib.Path`, specific exceptions logged at the boundary.
- `plugin/` is built from `skills/construct3-agent-plugin/`, `data/` and
  `prompts/` by `python scripts/build_plugin.py`, and committed with them.
  Edit the source, then build; an edit inside `plugin/` is lost at the next
  build, and `tests/test_plugin_folder.py` fails until the build is run.
  The build sets the plugin's version and raises its patch itself. Raise
  `version` in `scripts/plugin/plugin.json` only for a minor or major
  release (`docs/decisions/plugin-tracks-commits.md`). If a merge leaves
  conflicts in `plugin/`, resolve the sources, run the build, stage
  `plugin/`, then commit the merge. During a merge the build compares with
  the commit the merge will share with `origin/main`, so one run writes the
  right version.
- Docs and tests change with the behavior. README: data first, service
  second. `README_CN.md` carries the content of `README.md`; `README.md`
  names no Chinese text or locale besides its link to `README_CN.md`, and
  the Chinese examples stay in `README_CN.md`. `docs/dev/architecture.md`
  describes only what runs. Test totals stay out of docs.
- A commit message or PR text names an issue of another repository in
  words or as a URL in backticks, never as `owner/repo#N` or `#N`: GitHub
  turns those into a public cross-reference on that issue's timeline, which
  cannot be taken back. A source line in a document may use the short form;
  only commits, issues and PRs are parsed.

Before finishing, plus the checks in the touched directories' `AGENTS.md`:

```bash
python -m pytest -q
python -m compileall -q src scripts tests skills
git diff --check
```

Done: an observable problem solved; the default path run live, failure and
fallback explained; old paths, dead configuration, orphaned tests and stale
docs removed; the report split into verified, unverified, risk, next
decision.

## 6. Entry points

```bash
python scripts/setup.py                       # lookup server
python scripts/init.py                        # refresh CDN data, export schemas
python -m uvicorn src.api:app --port 8765     # server only
python -m pytest tests/test_query_gold.py -q   # Direct Lookup gold set
```

## 7. Where to read more

| Need | Document |
|------|----------|
| Install and run | `docs/guide/quick-start.md` |
| HTTP API | `docs/guide/api-reference.md` |
| Data files and fields | `docs/guide/data-format.md` |
| Event sheet design, sourced pitfalls, the examples' authoring style | `prompts/event-sheet-thinking.md`, `prompts/event-sheet-pitfalls.md` and its topic files in `prompts/pitfalls/`, `prompts/event-sheet-style.md`, `docs/decisions/event-sheet-design-guidance.md` |
| Published-game visual language, motion statistics and the reproducible analyzer | `docs/decisions/published-game-visual-language.md`, `docs/dev/published-game-analysis.md`, `scripts/reference_games/` |
| Slot case as a program, hand-editing project JSON, bars and life counters by the art they have, feel recipes, sounds and placeholder audio, sequences and dialogue run from a data file | `prompts/references/` |
| A new project's sheets, layers, objects and look: colours by role, text, pixel art, what other design skills do, and where its art comes from | `prompts/references/new-project.md`, `docs/decisions/game-look-from-design-skills.md`, `docs/decisions/art-from-the-image-tool.md` |
| The project tools the skill carries into a game project: what each does, and changing and evaluating them | `skills/construct3-agent-plugin/SKILL.md`, `skills/AGENTS.md` |
| Architecture and package boundaries | `docs/dev/architecture.md`, `src/AGENTS.md` |
| Project and skill audit findings, reproduction boundaries and repair priorities | `docs/dev/skills-audit.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed | `docs/decisions/` |
| Delegating an ACE lookup or check to a Claude Code sub-agent | `.claude/agents/ace-lookup.md` |
| Polishing instruction files, docs, records, prompts and code in one verified run; start it when no other session edits the repository | `.claude/workflows/polish.js` |
