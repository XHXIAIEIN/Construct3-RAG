# Construct3-RAG

**English** | [中文](README_CN.md)

Everything you need to answer questions about [Construct 3](https://www.construct.net) — the complete game engine knowledge base in structured JSON. What does each plugin do? What actions, conditions, and expressions are available? What parameters do they take? It's all here, in English and Chinese, ready to read without any setup.

66 plugins · 31 behaviors · 89 effects · 481 examples · 150 TypeScript definitions

> Current data version: **r476** · Auto-updated weekly via [GitHub Action](.github/workflows/update-c3-data.yml)

> **For LLMs:** Read [`data/LLM_PROMPT.md`](data/LLM_PROMPT.md) before answering Construct 3 questions — it defines how to look up and reference ACEs accurately. Data is in `data/c3-schemas/{lang}/`.

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
| `c3-schemas/{lang}/plugins/{id}.json` | 66 | Conditions, actions, expressions, properties |
| `c3-schemas/{lang}/behaviors/{id}.json` | 31 | Behavior ACE definitions |
| `c3-schemas/{lang}/effects/{id}.json` | 89 | Effect parameters, categories |
| `c3-examples/{lang}/{id}.json` | 481 | Name, description, tags, used-addons, open URL |
| `c3-ts-defs/autocomplete-data.json` | 109 | Scripting classes → methods/properties |
| `c3-ts-defs/**/*.d.ts` | 150 | Full TypeScript interface signatures |

All paths are under `data/`. Schema files use CDN-native field names (`list-name`, `display-text`, `translated-name`).

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
| What ACEs does X have? | `{lang}/plugins/{id}.json` |
| How does an ACE look in the event sheet? | `display-text` field |
| What parameters does an ACE take? | `params` object |
| What effects are available? | `{lang}/effects/{id}.json` |
| Example projects using X? | `c3-examples/{lang}/*.json` → `used-addons` |
| JavaScript/TypeScript API? | `autocomplete-data.json` → `.d.ts` |

## LLM Integration

If you're building an LLM that helps users write event sheets, see [`data/LLM_PROMPT.md`](data/LLM_PROMPT.md) — a ready-to-use system prompt with output format, naming rules, and common pitfalls.

## Search API (optional)

```bash
pip install -r requirements.txt
python scripts/setup.py          # → http://localhost:8765/playground
```

### POST /search

| Parameter | Values | Default |
|-----------|--------|---------|
| `mode` | `list` · `lookup` · `semantic` · `auto` | `auto` |
| `scope` | `eventsheet` · `scripts` · `js` · `ts` · `all` | `eventsheet` |
| `lang` | `en` · `zh` · `ja` · `ko` | auto-detect |
| `context` | include LLM-ready text | `false` |

Full spec: [docs/api-reference.md](docs/api-reference.md)

### Semantic search

Requires Qdrant + embedding model. GPU recommended.

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
python scripts/setup.py --full
```

## Project Structure

```
src/api.py              FastAPI service
src/ingest/             CDN fetching, schema export, indexing
src/rag/                Lookup engine, vector retriever, query expander
data/c3-schemas/        ACE definitions, effects (en + zh)
data/c3-examples/       Example project metadata (en + zh)
data/c3-ts-defs/        TypeScript interfaces
tests/                  173 tests
docs/                   API reference, architecture, data pipeline
.github/workflows/      Weekly auto-update
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
