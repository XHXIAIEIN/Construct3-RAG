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
python scripts/setup.py --version <release>  # specific C3 version
python scripts/setup.py --port 9000     # custom port
```

## Configuration

Environment variables (`src/.env` file supported, copy from `src/.env.example`), defined in `src/settings/`:

| Variable | Default | Description |
|----------|---------|-------------|
| `C3_VERSION` | see config | Construct 3 editor version |
| `C3_SCHEMA_DIR` | auto-resolved | Explicit schema directory override |
| `RAG_SERVER_PORT` | `8765` | API server port |
| `C3_CDN_BASE` | `https://editor.construct.net` | Where a data refresh fetches from |
| `C3_CACHE_DIR` | `.cache/c3-cdn` | Where CDN downloads and exported schemas are cached |

The service reads the committed `data/` directory. Default setup and direct
Uvicorn startup therefore make no CDN request. `scripts/init.py`,
`--refresh-data`, and `--version` fetch the release into `C3_CACHE_DIR` and
replace `data/c3-schemas`, `c3-examples`, `c3-lang`, and `c3-ts-defs`; review
the result with `git diff` before committing. The cache is read directly only
when `C3_VERSION` names a release that `data/` does not yet hold.

## Test

```bash
python -m pytest tests/ -v    # no external services needed
```
