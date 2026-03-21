# Construct3-RAG

**English** | [中文](README_CN.md)

Retrieval service for [Construct 3](https://www.construct.net) documentation. Fetches ACE definitions from the official CDN, provides structured search API with multilingual support.

## Features

- **Structured ACE lookup** — Query Actions, Conditions, Expressions by plugin/behavior/keyword. Returns multilingual names, descriptions, editor display templates, and parameter definitions.
- **Dual-path retrieval** — Lookup (keyword/rule-based, <1ms) + Semantic (vector search, ~1-10s)
- **Live CDN data** — Fetches latest version from `editor.construct.net`, auto-filters deprecated ACEs
- **Pre-built schemas** — `data/c3-schemas/` contains ready-to-read per-plugin JSON files (no setup needed)
- **Multi-mode API** — `mode=list` (ACE name listing) / `mode=lookup` (keyword search) / `mode=semantic` (vector search) / `mode=auto` (lookup + semantic)
- **TypeScript definitions** — `data/c3-ts-defs/` contains full scripting API interfaces (150 `.d.ts` files)
- **Auto-update** — GitHub Action checks for new C3 releases weekly, creates PR with updated API definitions

## Quick Start

### Use data files directly (no install)

Pre-built API definitions are committed to the repo:

```
data/c3-schemas/                              — ACE definitions per plugin/behavior
data/c3-ts-defs/                              — TypeScript scripting interfaces
data/c3-ts-defs/autocomplete-data.json        — 109 classes with method listings
```

### Start the API server

```bash
pip install -r requirements.txt
python scripts/setup.py
```

Open `http://localhost:8765/playground` to test.

## Full Mode (semantic search)

Adds vector-based semantic search across all documentation.

Requirements:
- Docker (for Qdrant vector database)
- ~4GB disk (embedding model + vector index)
- GPU recommended (CPU works but slower, ~10x embedding time)

```bash
# 1. Install full dependencies
pip install -r requirements-full.txt

# 2. Start Qdrant
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 3. Clone data sources (place alongside this project)
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
git clone https://github.com/Scirra/Construct-Example-Projects.git   # optional

# 4. Setup with indexing
python scripts/setup.py --full
```

## API

### POST /search

```bash
# Keyword lookup (instant, no GPU)
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite collision","mode":"lookup"}'
```

### Response — mode=list

```json
{
  "query": "Sprite",
  "mode": "list",
  "ms": 0.5,
  "lookup": {
    "hit": true,
    "plugin": {"id": "sprite", "name": "Sprite"},
    "conditions": ["Is playing", "On finished", "Collisions enabled"],
    "actions": ["Set animation", "Stop", "Start", "Set frame"],
    "expressions": ["AnimationFrame", "AnimationName", "AnimationSpeed"]
  }
}
```

### Response — mode=lookup

```json
{
  "query": "Sprite collision",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": {
    "hit": true,
    "intent": "ace_search",
    "plugin": {"id": "sprite", "name": "Sprite"},
    "matches": [
      {
        "ace_id": "on-collision-with-another-object",
        "ace_type": "condition",
        "plugin_id": "_common",
        "en": {"name": "On collision with another object", "desc": "...", "display": "On collision with {0}"},
        "category": "common",
        "params": [{"name": "Object", "type": "object", "desc": "..."}]
      }
    ]
  }
}
```

Full API reference: [docs/api-reference.md](docs/api-reference.md)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Vector DB | Qdrant |
| Embedding | BAAI/bge-m3 |
| Data | Construct 3 CDN (live) + Markdown manual |
| Tokenizer | jieba (full-mode, synonym expansion) |
| Language | Python 3.11+ |

## Project Structure

```
Construct3-RAG/
├── src/
│   ├── api.py                 # FastAPI service
│   ├── config.py              # Configuration
│   ├── ingest/                # CDN fetching & indexing
│   └── rag/                   # Lookup engine & vector retriever
├── data/
│   └── c3-schemas/            # Pre-built ACE schemas (committed)
├── scripts/
│   ├── setup.py               # One-command setup
│   └── init.py                # CDN data initialization
├── tests/                     # Unit tests (no external services needed)
└── docs/                      # Architecture, API reference, data pipeline
```

## Documentation

- [Quick Start](docs/quick-start.md) — Setup options and configuration
- [Architecture](docs/architecture.md) — System design and lookup engine
- [API Reference](docs/api-reference.md) — Endpoint specs and examples
- [Data Pipeline](docs/data-pipeline.md) — CDN fetching, filtering, indexing

## Credits

This project uses data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com). Construct 3 is a trademark of Scirra Ltd. ACE definitions, TypeScript interfaces, and language files are fetched from the official Construct 3 editor CDN for educational and tooling purposes.

| Source | Usage |
|--------|-------|
| [Construct 3 Editor CDN](https://editor.construct.net) | ACE definitions, TypeScript interfaces, multilingual translations |
| [Construct 3 Manual](https://www.construct.net/en/make-games/manuals/construct-3) | Official documentation (via [Markdown mirror](https://github.com/XHXIAIEIN/Construct3-Manual)) |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Official example projects |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | Chinese synonym dictionary for query expansion |

## License

[MIT](LICENSE)
