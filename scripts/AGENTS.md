# scripts/ Directory

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `bootstrap.py` | Clone the sibling repositories that are missing, create a game project from the empty one when the folder does not exist, and install the skill in it; the two-command start of the README | `python scripts/bootstrap.py --project <folder>` |
| `setup.py` | Install the dependencies and start the lookup server; `--refresh-data` fetches the CDN first | `python scripts/setup.py` |
| `init.py` | Fetch CDN data, export it into the cache, and replace `data/c3-schemas`, `c3-examples`, `c3-lang`, `c3-ts-defs` | `python scripts/init.py` |
| `check_c3_version.py` | Check latest C3 version on CDN | `python scripts/check_c3_version.py` |
| `extract_common_aces.py` | Regenerate `src/ingest/common_aces.json` (shared world-object ACEs) from the editor bundle | `python scripts/extract_common_aces.py` |

`init.py` and `setup.py` read the canonical `en-US`/`zh-CN` schema layout from
`src/lookup/schema_layout.py`; do not duplicate locale directory names in new scripts.

Checks: after `init.py`, compare counts and structure in
`data/c3-schemas/_index.json`; `.github/workflows/update.yml` calls `init.py`
and must use the exporter's standard directories.
