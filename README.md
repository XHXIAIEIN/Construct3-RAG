# Construct3-RAG

**English** | [中文](README_CN.md)

Structured Construct 3 reference data and a retrieval API for answering questions about plugins, behaviors, ACEs, effects, examples, and scripting interfaces. The committed reference files can be read directly; the optional service adds keyword and semantic search.

> The current Construct version and dataset counts are recorded in [`data/c3-schemas/_index.json`](data/c3-schemas/_index.json). Updates are proposed by [the data workflow](.github/workflows/update.yml).

> **For AI agents:** Start with [`AGENTS.md`](AGENTS.md). It maps the repository and gives the lookup procedure. To help users write event sheets, load [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) as a system prompt. Data is in `data/c3-schemas/{locale}/`, where `locale` is `en-US` or `zh-CN`.

## Key Concepts

[Construct 3](https://www.construct.net) is a visual game engine. Games are built with **event sheets** (visual if/then logic) rather than code.

- **Plugin** — an object type (Sprite, Audio, Keyboard, etc.)
- **Behavior** — reusable logic attached to plugins (Platform, Tween, Physics, etc.)
- **ACE** — Actions, Conditions, Expressions. The building blocks of event sheets:
  - **Condition** — a test (`Is animation playing`, `On collision with...`)
  - **Action** — something that happens (`Set animation`, `Destroy`)
  - **Expression** — a value to read (`AnimationFrame`, `X`, `Y`)
- **Effect** — a visual shader (blur, tint, glow, etc.)

Each ACE entry in the schema files has:

| Field | Meaning |
|-------|---------|
| `list-name` | Name shown in the "Add condition/action" dialog |
| `display-text` | Template shown in the event sheet (e.g. `Set animation to {0}`) |
| `translated-name` | Expression identifier (expressions only, e.g. `AnimationFrame`) |
| `scriptName` | JavaScript API method name (for scripting, not event sheets) |
| `description` | Tooltip / help text |
| `params` | Parameter definitions (`{id: {type, name, desc}}`) |

## Data Files

No install needed. Pick a language (`en-US` or `zh-CN`) and read.

| Path | Count | Content |
|------|------:|---------|
| `c3-schemas/_index.json` | — | Master index: id → name, file path, ACE counts |
| `c3-schemas/{locale}/plugins/{id}.json` | indexed | Conditions, actions, expressions, properties |
| `c3-schemas/{locale}/behaviors/{id}.json` | indexed | Behavior ACE definitions |
| `c3-schemas/{locale}/effects/{id}.json` | indexed | Effect parameters, categories |
| `c3-examples/{locale}/{id}.json` | per release | Name, description, tags, used-addons, open URL |
| `c3-lang/{locale}.json` | per release | Raw CDN language pack, pretty printed for diffing translations |
| `c3-ts-defs/autocomplete-data.json` | per release | Scripting classes → methods/properties |
| `c3-ts-defs/**/*.d.ts` | per release | Full TypeScript interface signatures |

All paths are under `data/`. Schema files use CDN-native field names (`list-name`, `display-text`, `translated-name`). Field meanings and file layout: [docs/guide/data-format.md](docs/guide/data-format.md).

## Usage

### 1. Find a plugin/behavior

Read `_index.json`:
```json
{
  "plugins": {
    "sprite": {
      "originalId": "Sprite",
      "name_en": "Sprite", "name_zh": "精灵",
      "file": "plugins/sprite.json",
      "conditions": 12, "actions": 16, "expressions": 15
    }
  }
}
```

### 2. Read its ACE definitions

`en-US/plugins/sprite.json` — a condition entry:
```json
{
  "id": "is-animation-playing",
  "list-name": "Is playing",
  "display-text": "Is animation {0} playing",
  "description": "Test which of the object's animations is currently playing.",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": {
    "animation": { "type": "animation", "name": "Animation", "desc": "..." }
  }
}
```

`zh-CN/plugins/sprite.json` — same ACE, Chinese:
```json
{
  "id": "is-animation-playing",
  "list-name": "正在播放",
  "display-text": "正在播放 {0} 动画",
  "description": "检测当前正在播放哪个的动画。",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": {
    "animation": { "type": "animation", "name": "动画", "desc": "要检测的动画名称。" }
  }
}
```

Field names match the official CDN: `list-name`, `display-text` for conditions/actions; `translated-name` for expressions. Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are identical across languages.

### 3. JavaScript/TypeScript API

1. `autocomplete-data.json` → find the class (e.g. `ISpriteInstance`)
2. Read `plugins/general/sprite/c3runtime/ISpriteInstance.d.ts` for full signatures

### Quick reference

| Question | Where to look |
|----------|---------------|
| What plugins/behaviors/effects exist? | `_index.json` |
| What ACEs does X have? | `{locale}/plugins/{id}.json` |
| How does an ACE look in the event sheet? | `display-text` field |
| What parameters does an ACE take? | `params` object |
| What effects are available? | `{locale}/effects/{id}.json` |
| Example projects using X? | `c3-examples/{locale}/*.json` → `used-addons` |
| JavaScript/TypeScript API? | `autocomplete-data.json` → `.d.ts` |

## LLM Integration

If you're building an LLM that helps users write event sheets, see [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) — a ready-to-use system prompt with output format, naming rules, and common pitfalls.

## Search API (optional)

```bash
pip install -r requirements.txt
python scripts/setup.py          # → http://localhost:8765/playground
```

This starts the deterministic offline lookup service. It does not connect to
Qdrant or load an embedding model. `mode=auto` adds semantic results only when
full mode has been explicitly enabled. It uses an existing local schema snapshot;
pass `--refresh-data` only when a CDN refresh is intended.

### POST /search

| Parameter | Values | Default |
|-----------|--------|---------|
| `mode` | `list` · `lookup` · `semantic` · `auto` | `auto` |
| `scope` | `eventsheet` · `scripts` · `js` · `ts` · `all` | `eventsheet` |
| `lang` | `en` · `zh` · `ja` · `ko` | auto-detect |
| `context` | include LLM-ready text | `false` |

Full spec: [docs/guide/api-reference.md](docs/guide/api-reference.md)

### Semantic search (explicit opt-in)

Requires Qdrant + embedding model. GPU recommended.

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
python scripts/setup.py --full
```

`--full` verifies Qdrant, builds the vector index unless skipped, and starts the
server process with `LITE_MODE=false`. A normal setup remains lookup-only.

## Project Structure

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
docs/guide/             For users: quick start, API reference
docs/dev/               For contributors: architecture, data pipeline
docs/decisions/         Audits and decision records
.github/workflows/      Data update automation
```

## Credits

Data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com). Construct 3 is a trademark of Scirra Ltd.

| Source | Usage |
|--------|-------|
| [Construct 3 Editor CDN](https://editor.construct.net) | ACE definitions, effects, examples, TypeScript interfaces, translations |
| [Construct 3 Manual](https://www.construct.net/en/make-games/manuals/construct-3) | Official documentation |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | Markdown mirror of official manual |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | Chinese synonym dictionary |

[MIT](LICENSE)
