# Construct3-RAG for AI Agents

Read this first. It tells you what is in the repository, how to answer a
Construct 3 question from committed data, and how to change the code safely.
Claude Code also loads `CLAUDE.md`, which holds the project charter and the
detailed product rules. Nothing here overrides that charter.

## 1. What this repository is

A versioned, bilingual reference dataset for Construct 3 plus an optional
search service on top of it. The data works without installing anything.

| Area | Path | Role |
|------|------|------|
| Data | `data/` | Committed JSON and `.d.ts` files. Read directly. |
| Prompts | `prompts/` | System prompts for LLMs that write event sheets. |
| Service | `src/` | FastAPI lookup service and optional Qdrant retrieval. |
| Operations | `scripts/` | Setup, CDN refresh, version check. |
| Tests | `tests/` | Offline pytest suite, gold sets, evaluation runners. |
| Docs | `docs/guide/` | For users: quick start, API reference, data format. |
| Docs | `docs/dev/` | For contributors: architecture, data pipeline. |
| Docs | `docs/decisions/` | Audits and decision records. Read only when relevant. |

Version and counts live in `data/c3-schemas/_index.json`. Do not hardcode them.

## 2. SOP: answer a Construct 3 fact question

Use the data. Do not answer plugin, behavior, ACE, effect, or scripting
questions from memory when the repository can be checked.

1. Open `data/c3-schemas/_index.json`. Find the plugin, behavior, or effect id
   under `plugins`, `behaviors`, or `effects`. Each entry gives `file` and
   the ACE counts.
2. Pick a locale directory listed in `_index.json` under `languages`
   (`en-US` or `zh-CN`). Read `data/c3-schemas/{locale}/{file}`.
3. Inside the file, find the ACE by `id`, `list-name`, or `translated-name`.
   Report `display-text` for event sheet wording, `params` for parameters,
   and `scriptName` when the user asks about scripting.

| Question | Where to look |
|----------|---------------|
| Which plugins, behaviors, effects exist | `data/c3-schemas/_index.json` |
| ACEs of a plugin | `data/c3-schemas/{locale}/plugins/{id}.json` |
| ACEs of a behavior | `data/c3-schemas/{locale}/behaviors/{id}.json` |
| Effect parameters | `data/c3-schemas/{locale}/effects/{id}.json` |
| JavaScript or TypeScript API | `data/c3-ts-defs/autocomplete-data.json`, then the matching `.d.ts` |
| Example projects for a topic | `data/c3-examples/{locale}/*.json`, filter `tags` and `used-addons` |
| Data field meanings | `docs/guide/data-format.md` |

Rules that matter:

- Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are the
  same in every locale. Only text differs.
- If an ACE is not in the schema, say so. Do not invent a plausible name.
- Expressions use `translated-name`; conditions and actions use `list-name`.
- General concepts such as layouts or event sheets need no lookup.

When the API server is running, `POST /search` gives the same data with
lookup and optional semantic modes. See `docs/guide/api-reference.md`.

## 3. SOP: change code or data

Before editing:

1. Read the `CLAUDE.md` in every directory you touch.
2. Run `git status` and keep changes you did not make.
3. Trace the real call chain from `src/api.py` or `scripts/`. Do not infer
   behavior from file names.
4. Decide whether the feature is default, optional, experimental, or legacy.
   `src/rag/` and the compatibility modules named in `src/CLAUDE.md` are
   facades only.

While editing:

- Keep the default path offline and deterministic. No network, model loading,
  or CDN refresh during import or a normal query.
- Keep the `en-US` and `zh-CN` layout. `src/schema_layout.py` owns layout logic.
- Fix generators, not generated files. Regenerate `data/` through
  `scripts/init.py` rather than hand editing many JSON files.
- Update docs and tests in the same change when behavior moves.

Before finishing:

```bash
python -m pytest -q
python -m compileall -q src scripts tests
git diff --check
```

Report what was verified, what was not, and any external service you could
not run. A mocked test is not a live verification.

## 4. Entry points

```bash
python scripts/setup.py                       # lookup server, no Qdrant
python scripts/setup.py --full                # Qdrant + embeddings + index
python scripts/init.py                        # refresh CDN data, export schemas
python -m uvicorn src.api:app --port 8765     # server only
python tests/eval_query_quality.py --strategy all --split all --output query-quality.json
```

## 5. Where to read more

| Need | Document |
|------|----------|
| Install and run | `docs/guide/quick-start.md` |
| HTTP API | `docs/guide/api-reference.md` |
| Data files and fields | `docs/guide/data-format.md` |
| Runtime architecture and package boundaries | `docs/dev/architecture.md`, `src/CLAUDE.md` |
| CDN fetch, export, update workflow | `docs/dev/data-pipeline.md`, `.github/workflows/update.yml` |
| Why features were kept or removed | `docs/decisions/` |
| Product rules and definition of done | `CLAUDE.md` |
