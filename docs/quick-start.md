# Quick Start

## Requirements

- Python 3.11+
- Docker (for Qdrant)
- ~4GB disk (embedding model + vector index)

## Setup

```bash
# 1. Start Qdrant
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. One-command setup (install deps → fetch CDN → build index → start server)
python scripts/setup.py
```

Server starts at `http://localhost:8765`. Open `http://localhost:8765/playground` to test.

### Setup options

```bash
python scripts/setup.py --skip-index    # skip index rebuild, just start server
python scripts/setup.py --skip-deps     # skip pip install
python scripts/setup.py --version r477  # use specific C3 version
python scripts/setup.py --port 9000     # custom port
```

### Manual step-by-step

```bash
pip install -r requirements.txt
python scripts/init.py                          # fetch CDN data
python -m src.ingest.indexer --rebuild          # build vector index
python -m uvicorn src.api:app --port 8765       # start server
```

## Configuration

All config via environment variables (`.env` file supported):

| Variable | Default | Description |
|----------|---------|-------------|
| `C3_VERSION` | `r476` | Construct 3 editor version |
| `C3_CDN_BASE` | `https://editor.construct.net` | CDN base URL |
| `RAG_SERVER_PORT` | `8765` | API server port |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model path |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |

## Test

```bash
python -m pytest tests/ -v    # no external services needed
```
