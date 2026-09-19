# scripts/ Directory

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup.py` | Default setup (CDN + lookup server) | `python scripts/setup.py` |
| `setup.py --full` | Full setup (+ Qdrant + embedding + index) | `python scripts/setup.py --full` |
| `init.py` | Fetch CDN data; export schemas, examples, language packs, and terms | `python scripts/init.py` |
| `check_c3_version.py` | Check latest C3 version on CDN | `python scripts/check_c3_version.py` |
| `extract_common_aces.py` | Regenerate `src/ingest/common_aces.json` (shared world-object ACEs) from the editor bundle | `python scripts/extract_common_aces.py` |

`init.py` and `setup.py` read the canonical `en-US`/`zh-CN` schema layout from
`src/lookup/schema_layout.py`; do not duplicate locale directory names in new scripts.

Qdrant lifecycle commands are documented in `docs/guide/quick-start.md`. Keep database
deletion out of helper scripts unless it enumerates the live collection registry
from `src/qdrant/collections.py` and requires an explicit confirmation.
