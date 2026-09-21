# Construct3-RAG for AI Agents

## 1. What this repository is

Bilingual Construct 3 reference data under `data/`, read directly, plus an
optional lookup and search service in `src/`, and an agent skill in
`skills/` that carries the project tools (ACE lookup, sheet printer,
checker, generator) into a game project. Version and counts:
`data/c3-schemas/_index.json`, never hardcoded.

Priorities, in order: exact addon, ACE and scripting lookup; citable
English and Chinese data; example projects by topic; works from the
committed files alone; the service tells exact queries from semantic ones.

Tiers: `data/` and the CDN update pipeline are core; the lookup service is
optional; Qdrant retrieval is the optional full mode (`src/AGENTS.md`).
Moving a feature between tiers needs evidence and a record in
`docs/decisions/`.

## 2. SOP: answer a Construct 3 fact question

Answer from the data. An ACE missing from the schema does not exist.

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
| ACEs shared by every world object: overlap, collisions, instance variables, hierarchy, UID, Z order | `data/c3-schemas/{locale}/plugins/_common.json`, in addition to the plugin file |
| Effect parameters | `data/c3-schemas/{locale}/effects/{id}.json` |
| JavaScript or TypeScript API | `data/c3-ts-defs/autocomplete-data.json`, then the `.d.ts` under the plugin or behavior directory of the same name |
| Types for an addon under development | editor `data/c3-ts-defs/sdk/`, runtime `data/c3-ts-defs/preview/interfaces/sdk/`; guide and samples in the `Construct3-Manual` and `Construct-Addon-SDK` clones |
| Example projects for a topic | `data/c3-examples/{locale}/*.json` by `tags` and `used-addons`; event sheets in the `Construct-Example-Projects` clone, `example-projects/{id}/eventSheets/`, read as events with `python skills/construct3-project/scripts/print_sheet.py --project <example folder>` |
| Translation of a string, editor text outside the schemas | `data/c3-lang/{locale}.json`, `text` |
| What a field means before writing an event or a script | `data/AGENTS.md`; full reference `docs/guide/data-format.md` |

Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are
identical across locales. How to structure an interaction is section 3.
`POST /search` on the running service returns the same data
(`docs/guide/api-reference.md`).

`plugins/system.json` and `plugins/_common.json` are thousands of lines
long. A reader that stops at 2000 lines shows part of them, and an ACE below
the cut looks missing. Ask for the part instead:

```bash
python skills/construct3-project/scripts/lookup_ace.py System wait
```

prints the matching conditions, actions and expressions of `System`, of a
plugin or behavior by id or display name, or, run in a game project, of one
of its objects with its behaviors, each with its parameters and the JSON to
write (`skills/construct3-project/SKILL.md`, "Look an ACE up before writing
it").

## 3. SOP: design event sheet logic

Interactions, data storage, timing, animation: read and follow
`prompts/event-sheet-thinking.md`, then verify names with section 2.

- UID links between objects, `Pick all` to reset picking, or a timer,
  tween or table rebuilt from variables: redesign.
- A runtime fact learned from a project goes into
  `prompts/event-sheet-pitfalls.md`, with its source.

## 4. Use from another project

A game project reaches this repository through two things it holds: the
`construct3-project` skill, a copy of `skills/construct3-project/`, and the
block of `prompts/game-project-AGENTS.md` in its instruction file, whose
`Construct3-RAG:` line locates the schemas.

- Working in a game project that has no `construct3-project` folder under
  `.agents/skills/` or another client's skills folder: install it before
  the first project file is read or written, from the project folder:

  ```bash
  python <this repository>/skills/construct3-project/scripts/install.py
  ```

  It copies the skill, and adds the block to the project's `AGENTS.md` when
  no instruction file there names this repository, with the path filled in.
  It changes no other file. Say in one sentence what it wrote, then read the
  installed `SKILL.md`. `--into .claude/skills` for Claude Code,
  `--into .trae/skills` for TRAE; `--no-block` when the user keeps the
  instruction files to themselves; `--dry-run` to see first.
- An installed copy says when it differs from `skills/construct3-project/`
  here and prints the command that refreshes it. Run it.
- The user does not want it in the project: remove the copy, run the
  scripts from this repository in place,
  `python <this repository>/skills/construct3-project/scripts/<script>.py
  --project <game folder>`, and do not install again in the session.

## 5. SOP: change code or data

Before editing:

1. Read the `AGENTS.md` of every directory touched; it holds that area's
   rules and checks. `git status`, keep changes you did not make.
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
- Docs and tests change with the behavior. README: data first, service
  second, English and Chinese identical. `docs/dev/architecture.md`
  describes only what runs. Test totals stay out of docs.

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
python scripts/setup.py                       # lookup server, no Qdrant
python scripts/setup.py --full                # Qdrant + embeddings + index
python scripts/init.py                        # refresh CDN data, export schemas
python -m uvicorn src.api:app --port 8765     # server only
python tests/eval_query_quality.py --strategy all --split all --output query-quality.json
```

## 7. Where to read more

| Need | Document |
|------|----------|
| Install and run | `docs/guide/quick-start.md` |
| HTTP API | `docs/guide/api-reference.md` |
| Data files and fields | `docs/guide/data-format.md` |
| Event sheet design, worked case, sourced pitfalls | `prompts/event-sheet-thinking.md`, `prompts/event-sheet-pitfalls.md`, `docs/decisions/event-sheet-design-guidance.md` |
| Slot case as a program, hand-editing project JSON | `prompts/references/` |
| ACE lookup, sheet printer, checker and generator for a game project; changing and evaluating them | `skills/construct3-project/SKILL.md`, `skills/AGENTS.md` |
| Architecture and package boundaries | `docs/dev/architecture.md`, `src/AGENTS.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed | `docs/decisions/` |
