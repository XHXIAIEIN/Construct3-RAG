# Construct3-RAG

Construct 3 documentation retrieval service. Fetches ACE definitions from official CDN, indexes with Qdrant, provides structured search API.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Vector DB | Qdrant |
| Embedding | BAAI/bge-m3 |
| Data source | Construct 3 CDN (live) + Markdown manual |
| Language | Python 3.11+ |

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `src/` | Source code (api, ingest, rag) |
| `src/ingest/` | CDN fetching, parsing, indexing |
| `src/rag/` | Lookup engine, vector retriever, query expander |
| `scripts/` | Setup, init, evaluation |
| `tests/` | Unit tests (no external services required) |
| `docs/` | Architecture, API reference, data pipeline |
| `.cache/c3-cdn/` | CDN cache + exported schemas (auto-generated) |

## Common Commands

```bash
# One-command setup (deps + CDN + index + server)
python scripts/setup.py

# Run tests
python -m pytest tests/ -v

# Rebuild index only
python -m src.ingest.indexer --rebuild

# Start server only
python -m uvicorn src.api:app --port 8765 --reload
```

## Configuration

Environment variables (`.env` file supported), defined in `src/config.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `C3_VERSION` | see `src/config.py` | Construct 3 editor version for CDN |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `RAG_SERVER_PORT` | `8765` | API server port |

## Code Style

- Python PEP 8; `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- `_leading_underscore` for private methods
- Type hints for function signatures
- `pathlib.Path` for file operations
- Functions under 50 lines; return early for error cases
- Catch specific exceptions, not bare `except:`
- Comments only for non-obvious logic

### Imports

```python
# 1. Standard library
# 2. Third-party
# 3. Local (from src.xxx import ...)
```

## Construct 3 Knowledge

This repo contains pre-built Construct 3 API definitions. When answering questions about C3 plugins, behaviors, ACEs, or scripting, **always look up the data files below** instead of guessing from training data.

### Data files (always available, no setup needed)

```
data/c3-schemas/_index.json                — START HERE: plugin/behavior name → file path
data/c3-schemas/plugins/{id}.json          — ACE definitions (conditions, actions, expressions, params, display)
data/c3-schemas/behaviors/{id}.json        — behavior ACE definitions
data/c3-ts-defs/autocomplete-data.json     — scripting API: 109 classes → method/property lists
data/c3-ts-defs/plugins/.../*.d.ts         — full TypeScript interface signatures
data/c3-ts-defs/behaviors/.../*.d.ts       — behavior TypeScript interfaces
data/c3-ts-defs/preview/interfaces/...     — runtime base classes (IInstance, IWorldInstance, etc.)
```

### How to answer C3 questions

**"What actions/conditions/expressions does [plugin] have?"**
→ Read `data/c3-schemas/_index.json`, find the plugin id, read `data/c3-schemas/plugins/{id}.json`

**"How do I use [ACE] in event sheets?"**
→ Read the plugin schema JSON, find the ACE entry. Look at `display_en`/`display_zh` (editor format), `params`, `description_en`.

**"How do I use [plugin] in JavaScript/TypeScript?"**
→ Read `data/c3-ts-defs/autocomplete-data.json` to find the interface class name.
→ Then read the `.d.ts` file for full method signatures.
→ Example: Sprite → `ISpriteInstance` → `data/c3-ts-defs/plugins/general/sprite/c3runtime/ISpriteInstance.d.ts`

**"What is [C3 concept]?" (layouts, event sheets, behaviors, etc.)**
→ General knowledge is fine. No lookup needed.

### API (optional, if server is running)

Full spec: `docs/api-reference.md`

```
POST /search  mode=list     — ACE name listing (grouped by type)
POST /search  mode=lookup   — keyword search with full ACE details
POST /search  mode=auto     — lookup + semantic vector search
```

## Related Files

- `CLAUDE.md` in each subdirectory — directory-level details
