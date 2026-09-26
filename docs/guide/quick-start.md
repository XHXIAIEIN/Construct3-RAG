# Quick Start

The data under `data/` needs no setup: read the files. This page starts the
optional lookup service over them.

## Setup

```bash
pip install -r src/requirements.txt
python scripts/setup.py
```

Provides keyword lookup for ACE definitions. It runs offline and loads no
model; there is no database to start.

Open `http://localhost:8765/playground` to test.

## Setup Options

```bash
python scripts/setup.py                 # install deps, start the lookup server
python scripts/setup.py --refresh-data  # explicitly refresh Construct data
python scripts/setup.py --skip-deps     # skip pip install
python scripts/setup.py --version <release>  # refresh data/ from a specific release
python scripts/setup.py --port 9000     # custom port
```

## Configuration

Environment variables, defined in `src/settings/`:

| Variable | Default | Description |
|----------|---------|-------------|
| `C3_SCHEMA_DIR` | `data/c3-schemas` | Schema directory the service reads |
| `RAG_SERVER_PORT` | `8765` | API server port |
| `C3_CDN_BASE` | `https://editor.construct.net` | Where a data refresh fetches from |
| `C3_CACHE_DIR` | `.cache/c3-cdn` | Where CDN downloads and exported schemas are cached |

The service reads the committed `data/` directory and reports the release its
`_index.json` records. Default setup and direct Uvicorn startup therefore make
no CDN request. `scripts/init.py` and `--refresh-data` fetch the latest stable
release, `--version` a named one, into `C3_CACHE_DIR` and replace
`data/c3-schemas`, `c3-examples`, `c3-lang`, and `c3-ts-defs`; review the
result with `git diff` before committing.

## Test

```bash
python -m pytest tests/ -v    # no external services needed
```
