# Construct3-RAG for AI Agents

Read this first. It tells you what is in the repository, what it is for, how
to answer a Construct 3 question from committed data, and how to change the
code safely. Each directory you work in has its own `AGENTS.md` with its
layout and local rules; those add detail and never contradict this file.
`CLAUDE.md` holds only the import `@AGENTS.md`, so Claude Code reads this
file through it, and nothing else lives there.

## 1. What this repository is

A versioned, bilingual reference dataset for Construct 3 plus an optional
search service on top of it. The data is the product: LLMs, scripts and other
applications read the committed files directly, with no database, model or
API server to start first. The service is optional. Direct Lookup answers
exact queries it can prove; Qdrant, embeddings and the reranker are the
optional full mode for questions that need semantic retrieval.

| Area | Path | Role |
|------|------|------|
| Data | `data/` | Committed JSON and `.d.ts` files. Read directly. |
| Prompts | `prompts/` | System prompts for LLMs that design and write event sheets. |
| Service | `src/` | FastAPI lookup service and optional Qdrant retrieval. |
| Operations | `scripts/` | Setup, CDN refresh, version check. |
| Tests | `tests/` | Offline pytest suite, gold sets, evaluation runners. |
| Docs | `docs/guide/` | For users: quick start, API reference, data format. |
| Docs | `docs/dev/` | For contributors: architecture, data pipeline. |
| Docs | `docs/decisions/` | Audits and decision records. Read only when relevant. |

Version and counts live in `data/c3-schemas/_index.json`. Do not hardcode them.

What the project must do well, in this order:

1. Find plugins, behaviors, ACEs, effects and scripting interfaces exactly.
2. Return official English and Chinese data that can be checked and cited.
3. Find the official example projects for a plugin, behavior or topic.
4. Work from the committed files alone, with nothing installed.
5. When the search service runs, tell an exact query apart from a question
   that needs semantic retrieval.

It is not a general chatbot, and stacking common RAG techniques is not a goal.

| Capability | Standing |
|------------|----------|
| Schemas, examples, script interfaces and language packs committed under `data/` | Core. Readable without any service. |
| CDN fetch, export and the update workflow | Core. Maintains the data. |
| Schema Direct Lookup and the FastAPI service | Optional. Catch specific exceptions only. |
| Qdrant retrieval, multi-collection routing, reranker | Optional full mode. Stays only while a same-gold-set benchmark shows a gain over simple retrieval. |

Changing a row takes product evidence and a decision record. QueryExpander,
Lookup Tier 2/3 and Semantic Chain/HyDE were removed for the reasons in
`docs/decisions/refactoring-audit.md`; anything that complex comes back only
after a separate experiment and benchmark prove it.

## 2. SOP: answer a Construct 3 fact question

Use the data. Do not answer plugin, behavior, ACE, effect, or scripting
questions from memory when the repository can be checked.

1. Open `data/c3-schemas/_index.json`. Find the plugin, behavior, or effect id
   under `plugins`, `behaviors`, or `effects`. Each entry gives `file` and
   the ACE counts. If you only have a localized name, find the id in
   `data/c3-schemas/{locale}/_index.json` first.
2. Pick a locale directory listed in `_index.json` under `languages`
   (`en-US` or `zh-CN`). Read `data/c3-schemas/{locale}/{file}`.
3. Inside the file, find the ACE by `id`, `list-name`, or `translated-name`.
   Report `display-text` for event sheet wording, `params` for parameters,
   and `scriptName` when the user asks about scripting.

| Question | Where to look |
|----------|---------------|
| Which plugins, behaviors, effects exist | `data/c3-schemas/_index.json` |
| Addon names in one language | `data/c3-schemas/{locale}/_index.json` |
| ACEs of a plugin | `data/c3-schemas/{locale}/plugins/{id}.json` |
| ACEs of a behavior | `data/c3-schemas/{locale}/behaviors/{id}.json` |
| ACEs every world object shares: overlap, collisions, instance variables, hierarchy, UID, Z order | `data/c3-schemas/{locale}/plugins/_common.json` |
| Effect parameters | `data/c3-schemas/{locale}/effects/{id}.json` |
| JavaScript or TypeScript API | `data/c3-ts-defs/autocomplete-data.json`, then the matching `.d.ts` |
| Types for an addon under development | editor side `data/c3-ts-defs/sdk/`, runtime side `data/c3-ts-defs/preview/interfaces/sdk/`; the guide and samples are in the `Construct3-Manual` and `Construct-Addon-SDK` clones (README) |
| Example projects for a topic | `data/c3-examples/{locale}/*.json`, filter `tags` and `used-addons`; the event sheets are in the `Construct-Example-Projects` clone under `example-projects/{id}/eventSheets/` |
| How a string is translated, or editor text outside the schemas | `data/c3-lang/{locale}.json` under `text` |
| Data field meanings | `docs/guide/data-format.md` |

Rules that matter:

- Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are the
  same in every locale. Only text differs.
- If an ACE is not in the schema, say so. Do not invent a plausible name.
- Expressions use `translated-name`; conditions and actions use `list-name`.
- General concepts such as layouts or event sheets need no fact lookup.
  How to structure an interaction is a design question: use section 3.

When the API server is running, `POST /search` gives the same data with
lookup and optional semantic modes. See `docs/guide/api-reference.md`.

## 3. SOP: design event sheet logic

Use this when the user asks how to build an interaction, where to keep data
(levels, tables, saves), or how to time or animate something, not only which
ACE exists. Read `prompts/event-sheet-thinking.md` and follow it; it links
the writing format and the runtime facts it relies on. Only then verify
names with section 2. A draft that links objects through UIDs, resets
picking with `Pick all`, or rebuilds a timer, tween or table from variables
is a redesign, not a patch. A runtime fact learned from a project goes into
`prompts/event-sheet-pitfalls.md`, with a source.

## 4. Use from another project

Nothing in a Construct project points here. An agent in a game folder finds
this repository only when the project's `AGENTS.md` carries the block from
`prompts/game-project-AGENTS.md`; that file says how to install it, and when
Claude Code also needs a `CLAUDE.md` beside it.

The project's instruction file belongs to the user. If the block is missing
where the agent is about to do event sheet work, offer it once, in one
sentence, and write it only on a yes: the block, or for Claude Code the
`@AGENTS.md` line, appended to the file the tool reads, nothing else in it
touched. A no ends it for the session, and a block seen in one project is
no reason to write it into another.

When the agent generates the whole project, `prompts/project-tools/README.md`
is the workflow. There the block is part of the output, because the checker
reads its `Construct3-RAG:` line to find the schemas.

## 5. SOP: change code or data

Before editing:

1. Read the `AGENTS.md` in every directory you touch.
2. Run `git status` and keep changes you did not make.
3. Trace the real call chain from `src/api.py` or `scripts/`. Do not infer
   behavior from file names.
4. Decide whether the feature is default, optional, experimental, or legacy.
   `src/rag/` and the compatibility modules named in `src/AGENTS.md` are
   facades only.
5. For a significant feature or refactor, answer first: which real user task
   it solves; whether the default run path calls it today; what real queries,
   logs, user feedback or benchmark data support it; whether a simpler
   implementation, or reading the data directly, would do the same; whether
   the gain covers the code, dependencies, deployment and maintenance. The
   outcome is keep, simplify, rewrite or delete. Without evidence, research
   first, build a baseline and an experiment, and leave the production path
   alone.

That code, configuration, tests or docs exist is no reason to keep what they
implement: the original problem may have been misdefined, and later patches,
tests and comments inherit the error. A test proves that the code meets the
expectation written into it, not that the expectation is right. When a test
pins wrong product behavior, fix the expectation first, then the test.

When designing, state the outcome the user can observe before choosing
modules and algorithms; build the simpler baseline before the complex
version; look for the cause in data quality, field weights, routing or
product scope before adding keywords, prompts or a model layer. When a
product choice would produce visibly different results, put the evidence,
options and trade-offs in `docs/decisions/`.

While editing:

- Keep the default path offline, deterministic and explainable. No network,
  model loading or CDN refresh during import or a normal query; refreshing
  CDN data is an explicit maintenance step.
- External services and experimental features are configured explicitly,
  detectable, switchable off, and fall back safely. An LLM result never
  overrides a high-confidence deterministic result.
- Every configuration value has a real caller at run time. When removing a
  feature, remove its configuration, dependencies, tests and docs in the same
  change and record why in `docs/decisions/`. "Might be useful later" keeps
  nothing.
- A new keyword, prompt or model starts from a failing case with a checkable
  expected result. Query-understanding work starts with
  `docs/decisions/query-understanding-refactor-requirements.md`: its product
  direction review is the gate before keywords, expansion or prompts change,
  and it owns the rules for expansion, synonyms, LLM checks and metrics.
- A public API change updates the models, docs and compatibility tests
  together. Internal structures promise no compatibility.
- Keep the `en-US` and `zh-CN` layout. `src/lookup/schema_layout.py` owns layout logic.
- Fix generators, not generated files. Regenerate `data/` through
  `scripts/init.py` rather than hand editing many JSON files.
- Use type hints and `pathlib.Path`. Catch specific exceptions and log the
  context at the boundary. Comments explain reasons and limits, not what the
  code does. Private data and machine-local configuration stay out of the
  repository.
- Update docs and tests in the same change when behavior moves. The README
  explains direct use of the data before the optional service, and the
  English and Chinese READMEs describe the same behavior with the same terms
  and paths. `docs/dev/architecture.md` describes only the architecture that
  runs.
- The Playground is a debugging page. Keep it plain and in the existing
  style, with no decorative components.

Before finishing:

```bash
python -m pytest -q
python -m compileall -q src scripts tests
git diff --check
```

The suite runs without Qdrant, a GPU or network. These three commands are
the floor; add the checks the change touches:

- Data layout: run the relevant path of `scripts/init.py` and check schema
  counts and structure.
- Direct Lookup: run representative English and Chinese queries against the
  committed data.
- API: check `/health` and `/search`, and tell schema readiness apart from
  Qdrant status.
- Qdrant or the reranker: claim a live check only when the service really ran.
- Update workflow: parse the YAML and confirm it uses the exporter's standard
  directories.
- Query quality: run the gold sets listed in `tests/AGENTS.md` and check the
  required and forbidden results.

Do not hardcode test totals in docs. A third-party deprecation warning is
noted, not a failure.

A task is done only when all of these hold:

1. It solves a problem the user can observe, not only moves code or adapts
   tests.
2. It fits the product direction and was compared with a simpler baseline.
3. The real default run path was exercised, not only imported or built, and
   the failure and fallback behavior can be explained.
4. The checks above pass, and old paths, old collection names and dead
   configuration were searched for leftovers.
5. No dead configuration, orphaned test or stale document remains; every
   document the behavior change touches is updated.
6. The report separates verified, unverified, remaining risk and the next
   decision. A mocked test is not a live verification, and neither is a
   service that did not run.

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
| Event sheet design rules and the worked case | `prompts/event-sheet-thinking.md`, `docs/decisions/event-sheet-design-guidance.md` |
| Sourced runtime facts and pitfalls | `prompts/event-sheet-pitfalls.md` |
| Loaded on demand from the prompts: the slot case as a transcribed program, hand-editing project JSON | `prompts/references/` |
| Generating a whole project from a script and checking it before the editor opens it | `prompts/project-tools/README.md` |
| Runtime architecture and package boundaries | `docs/dev/architecture.md`, `src/AGENTS.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed | `docs/decisions/` |
