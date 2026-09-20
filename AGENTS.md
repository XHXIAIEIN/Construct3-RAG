# Construct3-RAG for AI Agents

Sections 1 to 4 are for using the data; section 5 is for changing the code.

## 1. What this repository is

A versioned, bilingual reference dataset for Construct 3, plus an optional
search service. The data is the product: LLMs and scripts read the files
under `data/` directly, with no database, model or server to start. Version
and counts live in `data/c3-schemas/_index.json`; never hardcode them.

What it must do well, in this order:

1. Find plugins, behaviors, ACEs, effects and scripting interfaces exactly.
2. Return official English and Chinese data that can be checked and cited.
3. Find the official example projects for a plugin, behavior or topic.
4. Work from the committed files alone, with nothing installed.
5. When the service runs, tell an exact query apart from a question that
   needs semantic retrieval.

It is not a general chatbot, and stacking RAG techniques is not a goal.

- Core: the files under `data/`, and the CDN fetch, export and update
  workflow that maintain them.
- Optional: Direct Lookup and the FastAPI service over the same files.
- Optional full mode: Qdrant semantic retrieval. Its standing, the removed
  retrieval features and the rules for that code are in `src/AGENTS.md`.
- Moving a feature between tiers takes evidence and a decision record;
  `docs/decisions/refactoring-audit.md` is the running index.

## 2. SOP: answer a Construct 3 fact question

Do not answer plugin, behavior, ACE, effect or scripting questions from
memory when the data can be checked. If an ACE is not in the schema, say so;
do not invent a plausible name.

1. Find the addon id in `data/c3-schemas/_index.json` under `plugins`,
   `behaviors` or `effects`; the entry gives `file` and the ACE counts. From
   a localized name, get the id in `data/c3-schemas/{locale}/_index.json`.
2. Read `data/c3-schemas/{locale}/{file}` for a locale listed under
   `languages` (`en-US`, `zh-CN`).
3. Find the ACE by `id`, by `list-name` (conditions, actions) or by
   `translated-name` (expressions). Report `display-text` for event sheet
   wording, `params` for parameters, `scriptName` for scripting.

| Question | Where to look |
|----------|---------------|
| Which plugins, behaviors, effects exist | `data/c3-schemas/_index.json` |
| Addon names in one language | `data/c3-schemas/{locale}/_index.json` |
| ACEs of a plugin | `data/c3-schemas/{locale}/plugins/{id}.json` |
| ACEs of a behavior | `data/c3-schemas/{locale}/behaviors/{id}.json` |
| ACEs every world object shares: overlap, collisions, instance variables, hierarchy, UID, Z order | `data/c3-schemas/{locale}/plugins/_common.json`; a Sprite's full list is its own file plus this one |
| Effect parameters | `data/c3-schemas/{locale}/effects/{id}.json` |
| JavaScript or TypeScript API | `data/c3-ts-defs/autocomplete-data.json`, then the matching `.d.ts` |
| Types for an addon under development | editor side `data/c3-ts-defs/sdk/`, runtime side `data/c3-ts-defs/preview/interfaces/sdk/`; guide and samples in the `Construct3-Manual` and `Construct-Addon-SDK` clones (README) |
| Example projects for a topic | `data/c3-examples/{locale}/*.json`, filter `tags` and `used-addons`; event sheets in the `Construct-Example-Projects` clone under `example-projects/{id}/eventSheets/` |
| How a string is translated, or editor text outside the schemas | `data/c3-lang/{locale}.json` under `text` |
| Data field meanings | `docs/guide/data-format.md` |

Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are the
same in every locale; only text differs. General concepts such as layouts or
event sheets need no lookup, and how to structure an interaction is a design
question: section 3. The API's `POST /search` returns the same data; see
`docs/guide/api-reference.md`.

## 3. SOP: design event sheet logic

For "how do I build this interaction", "where do I keep levels, tables or
saves" or "how do I time or animate this", not only "which ACE exists":

- Read and follow `prompts/event-sheet-thinking.md`; it links the writing
  format and the runtime facts. Verify names with section 2 after the design.
- A draft that links objects through UIDs, resets picking with `Pick all`,
  or rebuilds a timer, tween or table from variables is a redesign, not a
  patch.
- A runtime fact learned from a project goes into
  `prompts/event-sheet-pitfalls.md`, with a source.

## 4. Use from another project

Nothing in a Construct project points here; an agent in a game folder finds
this repository only through the block from `prompts/game-project-AGENTS.md`,
which says how to install it and when Claude Code also needs a `CLAUDE.md`.

- The project's instruction file belongs to the user. If the block is missing
  where event sheet work is about to start, offer it once, in one sentence.
- Write it only on a yes: the block, or for Claude Code the `@AGENTS.md`
  line, appended to the file the tool reads, nothing else touched. A no ends
  it for the session; a block seen in one project is no reason to write it
  into another.
- When the agent generates the whole project, follow
  `prompts/project-tools/README.md`; there the block is part of the output,
  because the checker reads its `Construct3-RAG:` line to find the schemas.

## 5. SOP: change code or data

Before editing:

1. Read the `AGENTS.md` in every directory you touch. Run `git status` and
   keep changes you did not make.
2. Trace the real call chain from `src/api.py` or `scripts/`; do not infer
   behavior from file names.
3. Decide whether the feature is default, optional, experimental or legacy.
4. For a significant feature or refactor, write down first: the user task it
   solves, whether the default run path calls it today, the queries, logs or
   benchmark data behind it, and why a simpler implementation or reading the
   data directly would not do. Keep, simplify, rewrite or delete. Without
   evidence, build a baseline and an experiment first and leave the
   production path alone.

Rules:

- State the outcome the user can observe before choosing modules or
  algorithms, and build the simpler baseline before the complex version.
- Existing code, tests or docs are no reason to keep what they implement. A
  test proves the code meets the expectation written into it, not that the
  expectation is right; fix a wrong expectation first, then the test.
- A product choice with visibly different results gets its evidence, options
  and trade-offs in `docs/decisions/`.
- The default path is offline, deterministic and explainable: no network,
  model loading or CDN refresh during import or a normal query. Refreshing
  CDN data is an explicit maintenance step.
- Every configuration value has a caller at run time. Removing a feature
  removes its configuration, dependencies, tests and docs in the same change,
  with the reason in `docs/decisions/`. "Might be useful later" keeps nothing.
- Fix generators, not generated files: regenerate `data/` with
  `scripts/init.py` instead of editing JSON by hand.
- Type hints, `pathlib.Path`, specific exceptions logged at the boundary.
- Docs and tests change with the behavior. The README explains direct use of
  the data before the optional service; the English and Chinese READMEs say
  the same things with the same terms and paths; `docs/dev/architecture.md`
  describes only the architecture that runs.

Before finishing, run the floor, which needs no Qdrant, GPU or network:

```bash
python -m pytest -q
python -m compileall -q src scripts tests
git diff --check
```

Then the checks the change touches; `src/AGENTS.md` lists the service's own:

- Data layout: `scripts/init.py` on the relevant path; check schema counts and structure.
- Direct Lookup: representative English and Chinese queries against the committed data.
- Update workflow: parse the YAML; confirm the exporter's standard directories.
- Query quality: the gold sets in `tests/AGENTS.md`; check required and forbidden results.

Do not hardcode test totals in docs. A third-party deprecation warning is
noted, not a failure.

Done means: the change solves a problem the user can observe, not only moves
code or adapts tests; the real default run path was exercised and its failure
and fallback behavior can be explained; old paths, dead configuration,
orphaned tests and stale documents were searched for and removed; the report
separates verified, unverified, remaining risk and the next decision.

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
| Event sheet design rules, the worked case, sourced pitfalls | `prompts/event-sheet-thinking.md`, `prompts/event-sheet-pitfalls.md`, `docs/decisions/event-sheet-design-guidance.md` |
| Loaded on demand from the prompts: the slot case as a program, hand-editing project JSON | `prompts/references/` |
| Generating a whole project from a script and checking it before the editor opens it | `prompts/project-tools/README.md` |
| Runtime architecture and package boundaries | `docs/dev/architecture.md`, `src/AGENTS.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed; open a record only when a rule cites it or the change touches that decision | `docs/decisions/` |
