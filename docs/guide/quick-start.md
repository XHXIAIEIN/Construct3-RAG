# Quick Start

## Default Setup

```bash
pip install -r requirements.txt
python scripts/setup.py
```

Provides keyword lookup for ACE definitions. No Docker, no GPU needed.
The launched server is explicitly given `LITE_MODE=true`; `mode=auto` therefore
returns lookup results and safe fallbacks without attempting vector retrieval.

Open `http://localhost:8765/playground` to test.

## Full Setup (semantic search)

Adds vector search across all documentation. Requires Docker, ~4GB disk, GPU recommended.

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

## Setup Options

```bash
python scripts/setup.py               # default: lookup only
python scripts/setup.py --full        # full: Qdrant + embedding + index
python scripts/setup.py --refresh-data  # explicitly refresh Construct data
python scripts/setup.py --skip-index  # skip index rebuild
python scripts/setup.py --skip-deps   # skip pip install
python scripts/setup.py --version <release>  # specific C3 version
python scripts/setup.py --port 9000    # custom port
```

## Configuration

Environment variables (`.env` file supported), defined in `src/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `C3_VERSION` | see config | Construct 3 editor version |
| `C3_SCHEMA_DIR` | auto-resolved | Explicit schema directory override |
| `RAG_SERVER_PORT` | `8765` | API server port |
| `LITE_MODE` | `true` | Lookup-only default; set false only for a prepared full semantic service |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | Embedding model (full mode) |
| `QDRANT_HOST` | `localhost` | Qdrant host (full mode) |

Schema lookup first uses a complete cache for `C3_VERSION`, then falls back to
the committed `data/c3-schemas` dataset. Default setup and direct Uvicorn startup
therefore do not trigger a CDN download. Use `--refresh-data`, `--version`, or
`scripts/init.py` only when deliberately refreshing data; `--full` also refreshes
before building its version-matched vector index.

## Test

```bash
python -m pytest tests/ -v    # no external services needed
```
