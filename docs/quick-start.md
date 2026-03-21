# Quick Start

## Lite Mode (no Docker, no GPU)

Only needs Python. Provides keyword lookup for ACE definitions — no vector search.

```bash
python scripts/setup.py --lite
```

Requirements: Python 3.11+, internet connection (fetches CDN data once).
Available: `mode=lookup` only. `mode=semantic` returns empty results.

## Full Mode

Adds semantic vector search across all documentation.

```bash
# 1. Start Qdrant (one-time)
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. Full setup (deps → CDN → embedding → index → server)
python scripts/setup.py
```

Requirements: Python 3.11+, Docker, ~4GB disk (embedding model + index).
Available: all modes (`lookup`, `semantic`, `auto`).

## Setup Options

```bash
python scripts/setup.py --lite         # lookup only, no Qdrant/embedding
python scripts/setup.py --skip-index   # skip index rebuild, just start server
python scripts/setup.py --skip-deps    # skip pip install
python scripts/setup.py --version r477 # use specific C3 version
python scripts/setup.py --port 9000    # custom port
```

## Manual Step-by-Step

```bash
pip install -r requirements.txt
python scripts/init.py                     # fetch CDN data
python -m src.ingest.indexer --rebuild     # build vector index (requires Qdrant)
python -m uvicorn src.api:app --port 8765  # start server
```

## Configuration

Environment variables (`.env` file supported), defined in `src/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `C3_VERSION` | `r476` | Construct 3 editor version |
| `C3_CDN_BASE` | `https://editor.construct.net` | CDN base URL |
| `RAG_SERVER_PORT` | `8765` | API server port |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model path |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |

## Test

```bash
python -m pytest tests/ -v    # no external services needed
```
