# Construct3-RAG

**English** | [中文](README_CN.md)

Structured, bilingual reference data for [Construct 3](https://www.construct.net): plugins, behaviors, ACEs, effects, example projects, scripting interfaces, and the raw language packs. Everything under `data/` is committed JSON and `.d.ts` that a script or an LLM can read directly. An optional service adds lookup and semantic search on top.

The Construct version and dataset counts live in [`data/c3-schemas/_index.json`](data/c3-schemas/_index.json). [The update workflow](.github/workflows/update.yml) opens a pull request when Scirra ships a new stable release.

## Related repositories

This repository holds the machine-readable data. The prose, the project sources, and the SDK live elsewhere:

| Repository | What it holds | How it fits |
|---|---|---|
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Every example from the Construct example browser, saved as folder projects | `data/c3-examples/` is the metadata; this is the source. Full mode indexes it when cloned alongside. |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | Templates and documentation for custom plugins, behaviors, effects, and themes | `data/c3-ts-defs/sdk/` is the typed interface; this shows how to use it. |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | The official manual, Addon SDK guide, and Game Services docs as Markdown | Concepts and how-to text. Full mode indexes it when cloned alongside. |
| [XHXIAIEIN/Construct3-Manual-PDF](https://github.com/XHXIAIEIN/Construct3-Manual-PDF) | The same manual split into chapter PDFs | Offline reading. |

"Cloned alongside" means a sibling directory of this repository. Paths and options are in [docs/guide/quick-start.md](docs/guide/quick-start.md).

## Data files

No install needed. Pick a locale, `en-US` or `zh-CN`, and read. All paths are under `data/`.

| Path | Content |
|---|---|
| `c3-schemas/_index.json` | Version, locales, and every plugin, behavior, and effect with its file path and ACE counts |
| `c3-schemas/{locale}/plugins/{id}.json` | Conditions, actions, expressions, properties |
| `c3-schemas/{locale}/behaviors/{id}.json` | Behavior ACEs |
| `c3-schemas/{locale}/effects/{id}.json` | Effect parameters and categories |
| `c3-examples/{locale}/{id}.json` | Example name, description, tags, used addons, open URL |
| `c3-lang/{locale}.json` | Raw CDN language pack, one string per line, for diffing releases and translations |
| `c3-ts-defs/autocomplete-data.json` | Scripting class to methods and properties |
| `c3-ts-defs/**/*.d.ts` | Full TypeScript interface signatures |

Field names match the Construct CDN. Structural fields such as `id`, `scriptName`, `category`, and parameter types are identical in every locale, so an ACE found in one language can be read in the other. Field meanings, layout, and worked examples: [docs/guide/data-format.md](docs/guide/data-format.md).

## Reading the data

1. Find the addon in `_index.json`. Its entry gives the `file` path and the ACE counts.
2. Open `data/c3-schemas/{locale}/{file}` and locate the ACE by `id`, by `list-name` for conditions and actions, or by `translated-name` for expressions. `display-text` is the event sheet wording and `params` lists the parameters.
3. For scripting, look the class up in `autocomplete-data.json`, then open the matching `.d.ts`.

A condition from `en-US/plugins/sprite.json`:

```json
{
  "id": "is-animation-playing",
  "list-name": "Is playing",
  "display-text": "Is animation {0} playing",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": { "animation": { "type": "animation", "name": "Animation", "desc": "..." } }
}
```

The same `id` in `zh-CN/plugins/sprite.json` carries the Chinese `list-name`, `display-text`, and parameter names.

## For AI agents and LLMs

Start with [`AGENTS.md`](AGENTS.md): a repository map and the step-by-step lookup procedure. To help users write event sheets, load [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) as a system prompt. It covers output format, naming rules, and common pitfalls.

## Search service (optional)

```bash
pip install -r requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

This runs the deterministic offline lookup service over the committed data. It does not connect to Qdrant or load a model. Semantic search over the schemas, the manual, and the example projects is an explicit opt-in that needs Qdrant and an embedding model:

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
python scripts/setup.py --full
```

Setup options, the `/search` and `/health` endpoints, and response shapes: [docs/guide/quick-start.md](docs/guide/quick-start.md) and [docs/guide/api-reference.md](docs/guide/api-reference.md).

## Project structure

```
AGENTS.md               Entry point for AI agents: repo map, retrieval SOP, work SOP
data/                   Committed reference data. Read directly, no install
  c3-schemas/           ACE definitions, effects (en-US + zh-CN)
  c3-examples/          Example project metadata (en-US + zh-CN)
  c3-lang/              Raw CDN language packs (en-US + zh-CN)
  c3-ts-defs/           TypeScript scripting interfaces
prompts/                Ready-to-use LLM system prompts for event sheet help
src/                    Optional search service (see src/CLAUDE.md for packages)
scripts/                Setup, data refresh, version check
tests/                  Offline pytest suite, gold sets, evaluation runners
docs/guide/             For users: quick start, API reference, data format
docs/dev/               For contributors: architecture, data pipeline
docs/decisions/         Audits and decision records
.github/workflows/      Data update automation
```

## Credits

Data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com), fetched from the [editor CDN](https://editor.construct.net). Construct 3 is a trademark of Scirra Ltd.

[MIT](LICENSE)
