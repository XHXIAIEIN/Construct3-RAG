# Quick Start

The data under `data/` needs no setup: read the files. This page starts the
optional lookup service over them. The service looks up ACE definitions by
keyword. It runs offline, with no model to load and no database to start.

## Setup

```bash
pip install -r src/requirements.txt
python scripts/setup.py
```

To send test queries, open the playground at
`http://localhost:8765/playground`.

## Setup Options

```bash
python scripts/setup.py                 # install deps, start the lookup service
python scripts/setup.py --refresh-data  # explicitly refresh Construct data
python scripts/setup.py --skip-deps     # skip pip install
python scripts/setup.py --version <release>  # refresh data/ from a specific release
python scripts/setup.py --port 9000     # custom port
```

## Configuration

`src/settings/` reads these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `C3_SCHEMA_DIR` | `data/c3-schemas` | Schema directory the service reads |
| `RAG_SERVER_PORT` | `8765` | API server port |
| `C3_CDN_BASE` | `https://editor.construct.net` | Where a data refresh fetches from |
| `C3_CACHE_DIR` | `.cache/c3-cdn` | Where CDN downloads and exported schemas are cached |

## Data refresh

The service reads the committed `data/` directory and reports the release
that its `_index.json` records. So the default `python scripts/setup.py` and
`python -m uvicorn src.api:app --port 8765` make no CDN request.

`python scripts/init.py` and `setup.py --refresh-data` fetch the latest stable
release into `C3_CACHE_DIR`, and `--version` on either fetches the release it
names. A refresh replaces `data/c3-schemas`, `data/c3-examples`,
`data/c3-lang` and `data/c3-ts-defs` with the release's export. Then it
rebuilds `data/c3-example-usage` from the `Construct-Example-Projects` clone,
when the clone lies beside this repository, and writes each guide in
`data/c3-guides/` whose text changed. Only `init.py` then builds `plugin/`
again. Review the result with `git diff` before committing.

## Test

```bash
python -m pytest tests/ -v    # no external services needed
```
