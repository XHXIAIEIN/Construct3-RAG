# Construct3-RAG

**English** | [中文](README_CN.md)

Construct 3 ACE definitions + TypeScript scripting interfaces, fetched from the official CDN. Provides keyword search API and pre-built data files for direct access.

## Data Files (pre-built, no install needed)

This repo ships pre-built Construct 3 API definitions (currently **r476**) in **per-language** files using CDN-native field names. Read them directly — no server, no dependencies. Updated automatically by GitHub Action on new C3 releases.

### File layout

```
data/c3-schemas/
  _index.json                              — START HERE: plugin/behavior/effect index
  en/plugins/{id}.json                     — English ACE definitions (conditions, actions, expressions)
  zh/plugins/{id}.json                     — Chinese ACE definitions (same structure, localized text)
  en/behaviors/{id}.json                   — English behavior ACE definitions
  zh/behaviors/{id}.json                   — Chinese behavior ACE definitions
  en/effects/{id}.json                     — English effect definitions (parameters, categories)
  zh/effects/{id}.json                     — Chinese effect definitions
  en/editor/index.json                     — Editor UI element names (English)
  zh/editor/index.json                     — Editor UI element names (Chinese)
  en/examples/{id}.json                     — English example project metadata (tags, used addons)
  zh/examples/{id}.json                     — Chinese example project metadata (localized tags)

data/c3-ts-defs/
  autocomplete-data.json                   — 109 scripting classes → method/property lists
  plugins/.../*.d.ts                       — full TypeScript interface signatures per plugin
  behaviors/.../*.d.ts                     — behavior TypeScript interfaces
  preview/interfaces/...                   — runtime base classes (IInstance, IWorldInstance, etc.)
```

### How to look up C3 plugin/behavior info

**Step 1** — Read `data/c3-schemas/_index.json` to find the plugin or behavior id:
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

**Step 2** — Pick a language directory and read the schema file.

`data/c3-schemas/en/plugins/sprite.json` — condition example (CDN-native field names):
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

`data/c3-schemas/zh/plugins/sprite.json` — same ACE in Chinese:
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

> Field names match the official CDN (`list-name`, `display-text`, `translated-name` for expressions).
> Structural fields (`id`, `scriptName`, `category`, `params.*.type`) are identical across languages.

**Step 3 (scripting only)** — For JavaScript/TypeScript API details:
1. Read `data/c3-ts-defs/autocomplete-data.json` to find the interface class name (e.g. `ISpriteInstance`)
2. Read the `.d.ts` file for full method signatures: `data/c3-ts-defs/plugins/general/sprite/c3runtime/ISpriteInstance.d.ts`

### Quick reference: which file answers which question?

| Question | File to read |
|----------|-------------|
| What plugins/behaviors/effects exist? | `_index.json` |
| What ACEs does plugin X have? | `en/plugins/{id}.json` or `zh/plugins/{id}.json` |
| How does an ACE appear in the event sheet? | Schema JSON → `display-text` field |
| What parameters does an ACE take? | Schema JSON → `params` object |
| What effects are available? | `en/effects/{id}.json` |
| How do I use X in JavaScript? | `autocomplete-data.json` → then `.d.ts` file |
| What example projects use plugin X? | `en/examples/{id}.json` → `used-addons` field |

## API

```bash
pip install -r requirements.txt
python scripts/setup.py
# → http://localhost:8765/playground
```

### POST /search

| Parameter | Values | Default |
|-----------|--------|---------|
| `mode` | `list` · `lookup` · `semantic` · `auto` | `auto` |
| `scope` | `eventsheet` · `scripts` · `js` · `ts` · `all` | `eventsheet` |
| `lang` | `en` · `zh` · `ja` · `ko` | auto-detect |
| `context` | include LLM-ready text | `false` |
| `debug` | timing breakdown | `false` |

Response example (`mode=list`):
```json
{
  "lookup": {
    "hit": true,
    "plugin": {"id": "sprite", "name": "Sprite"},
    "conditions": ["Is playing", "On finished", "Collisions enabled"],
    "actions": ["Set animation", "Stop", "Start", "Set frame"],
    "expressions": ["AnimationFrame", "AnimationName", "AnimationSpeed"]
  }
}
```

Full spec: [docs/api-reference.md](docs/api-reference.md)

## Semantic Search (optional)

Requires Docker, ~4GB disk, GPU recommended.

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
python scripts/setup.py --full
```

## Project Structure

```
src/api.py              API service (FastAPI)
src/ingest/             CDN fetching, schema parsing, indexing
src/rag/                Lookup engine, vector retriever, query expander
data/c3-schemas/        Pre-built ACE definitions (committed)
data/c3-ts-defs/        TypeScript interfaces (committed)
tests/                  172 unit tests + 17 eval cases
docs/                   API reference, architecture, data pipeline
.github/workflows/      Auto-update on new C3 releases (weekly check)
```

## Credits

Data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com). Construct 3 is a trademark of Scirra Ltd.

| Source | Usage |
|--------|-------|
| [Construct 3 Editor CDN](https://editor.construct.net) | ACE definitions, TypeScript interfaces, translations |
| [Construct 3 Manual](https://www.construct.net/en/make-games/manuals/construct-3) | Official documentation |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Example projects |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | Markdown mirror of official manual |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | Chinese synonym dictionary |

[MIT](LICENSE)
