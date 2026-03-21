# Construct3-RAG

**English** | [中文](README_CN.md)

Retrieval service for [Construct 3](https://www.construct.net) documentation. Fetches ACE definitions from the official CDN, provides structured search API with bilingual (English/Chinese) support.

## Features

- **Structured ACE lookup** — Query Actions, Conditions, Expressions by plugin/behavior/keyword. Returns full bilingual names, descriptions, editor display templates, and parameter definitions.
- **Dual-path retrieval** — Lookup (keyword/rule-based, <1ms) + Semantic (vector search, ~1-10s)
- **Live CDN data** — Fetches latest version from `editor.construct.net`, auto-filters deprecated ACEs
- **Pre-built schemas** — `data/c3-schemas/` contains ready-to-read per-plugin JSON files (no setup needed)
- **Multi-mode API** — `mode=lookup` (keyword only, instant) / `mode=semantic` (vector search) / `mode=auto` (both)

## Quick Start

### Zero setup — read schema files directly

Pre-built schema files are committed to the repo. No install needed.

```
data/c3-schemas/
  _index.json             — plugin/behavior name index (en/zh + ACE counts)
  plugins/sprite.json     — Sprite ACE definitions
  behaviors/platform.json — Platform behavior ACE definitions
  ...
```

### Lite mode — lookup API, no Docker/GPU

```bash
python scripts/setup.py --lite
```

Starts API server with keyword lookup only. No Qdrant, no embedding model.

### Full mode — lookup + semantic search

```bash
# 1. Start Qdrant
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. Full setup
python scripts/setup.py
```

Requires: Python 3.11+, Docker, ~4GB disk.

### Data sources

```bash
# Required: official manual (Markdown)
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git

# Optional: example projects
git clone https://github.com/Scirra/Construct-Example-Projects.git
```

Place alongside this project in the same parent directory.

## API

### POST /search

```bash
# Keyword lookup (instant, no GPU)
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite collision","mode":"lookup"}'
```

### Response

```json
{
  "query": "Sprite collision",
  "mode": "auto",
  "latency_ms": 0.3,
  "lookup": {
    "hit": true,
    "tier": 1,
    "confidence": 0.85,
    "plugin": {"id": "sprite", "name": "Sprite", "name_zh": "精灵"},
    "matches": [
      {
        "ace_id": "on-collision-with-another-object",
        "ace_type": "condition",
        "en": {"name": "On collision with another object", "desc": "...", "display": "On collision with {0}"},
        "zh": {"name": "碰撞到其他对象", "desc": "...", "display": "碰撞到 {0}"},
        "params": [{"name": "Object", "type": "object", "desc": "..."}]
      }
    ]
  },
  "semantic": []
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

| Project | Usage |
|---------|-------|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | Official manual in Markdown |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Official example projects |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | Chinese synonym dictionary for query expansion |

## License

[MIT](LICENSE)
