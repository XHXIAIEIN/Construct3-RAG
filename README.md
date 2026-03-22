# Construct3-RAG

**English** | [中文](README_CN.md)

Construct 3 ACE definitions + TypeScript scripting interfaces, fetched from the official CDN. Provides keyword search API and pre-built data files for direct access.

## Data Files

No install needed. Read these directly:

```
data/c3-schemas/_index.json                — plugin/behavior index (name → file path, ACE counts)
data/c3-schemas/plugins/{id}.json          — conditions, actions, expressions, params, display templates
data/c3-schemas/behaviors/{id}.json        — behavior ACE definitions
data/c3-ts-defs/autocomplete-data.json     — 109 scripting classes → method/property lists
data/c3-ts-defs/plugins/.../*.d.ts         — full TypeScript interface signatures per plugin
data/c3-ts-defs/behaviors/.../*.d.ts       — behavior TypeScript interfaces
data/c3-ts-defs/preview/interfaces/...     — runtime base classes (IInstance, IWorldInstance, etc.)
```

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
