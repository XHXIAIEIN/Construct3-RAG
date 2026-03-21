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
| `C3_VERSION` | `r476` | Construct 3 editor version for CDN |
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

## API Overview

`POST /search` with `mode`: `auto` | `lookup` | `semantic`

Response splits into:
- `lookup` — structured ACE matches with `en`/`zh` locale (name, desc, display, params)
- `semantic` — vector search results (docs, examples, terms)
- `debug` — timing and collection stats (when `debug=true`)

Full spec: `docs/api-reference.md`

## Construct 3 Knowledge Lookup

When answering questions about Construct 3 (plugins, behaviors, ACEs, events, scripting), use the pre-built schema files for accurate, up-to-date information instead of relying on training data.

### Reading schema files (no setup needed)

Schema data is pre-built and committed to the repo:

```
data/c3-schemas/
  _index.json             — plugin/behavior name index (en/zh mapping + ACE counts)
  plugins/{name}.json     — per-plugin ACE definitions
  behaviors/{name}.json   — per-behavior ACE definitions
```

**Step 1**: Read `data/c3-schemas/_index.json` to find the plugin/behavior name → file path.
**Step 2**: Read the corresponding JSON for full ACE details (conditions, actions, expressions with en/zh names, descriptions, display templates, params).

```bash
# Find which plugin handles collision
grep -l "collision" data/c3-schemas/plugins/*.json

# Read Sprite ACE definitions
cat data/c3-schemas/plugins/sprite.json
```

### API lookup (if server is running)

```bash
# Keyword lookup — instant, no GPU needed
curl -s -X POST http://localhost:${RAG_SERVER_PORT:-8765}/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite collision","mode":"lookup"}'
```

### When to look up vs. answer from knowledge

| Question type | Source |
|--------------|--------|
| Plugin/behavior ACE list | Read `data/c3-schemas/plugins/{name}.json` |
| Specific ACE details | Read schema JSON or API `mode=lookup` |
| How-to questions | API `mode=auto` (if running) |
| General C3 concepts | Training data is fine |

## Related Files

- `CLAUDE.md` in each subdirectory — directory-level details
