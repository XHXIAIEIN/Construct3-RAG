# scripts/ Directory

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup.py` | Install the dependencies and start the lookup service; `--refresh-data` refreshes `data/` from the CDN first, `--version <release>` from that release | `python scripts/setup.py` |
| `init.py` | Fetch CDN data of the latest stable release, or of `--version <release>`, export it into the cache, and replace `data/c3-schemas`, `c3-examples`, `c3-lang`, `c3-ts-defs`; then index which official examples use each ACE into `data/c3-example-usage/`, and write each of Scirra's guides in `data/c3-guides/` whose text changed | `python scripts/init.py`; `--guides-only` for the guides alone, `--guide-html <page>` for a page saved from a browser |
| `example_usage.py` | Index which official examples use each condition, action and expression, from the event sheets of the `Construct-Example-Projects` clone, into `data/c3-example-usage/`; without the clone the committed index stays (`docs/decisions/example-usage-index.md`) | `python scripts/example_usage.py`; `--clone <folder>` for a clone elsewhere |
| `check_c3_version.py` | Compare the release `data/` holds with the latest stable release on the CDN | `python scripts/check_c3_version.py` |
| `schema_diff.py` | Report what changed between two schema snapshots and which tracked files quote an id the change broke; the body of the update pull request | `python scripts/schema_diff.py [--base <rev or folder>] [--target <rev or folder>]` |
| `extract_common_aces.py` | Regenerate `src/ingest/common_aces.json` (shared world-object ACEs) from the editor bundle | `python scripts/extract_common_aces.py` |
| `reference_games/` | Download public Construct exports into `.local`, decode their event data, build contact sheets and compare motion statistics | `python -m scripts.reference_games <fetch|decode|atlas|report|all>` |

## Rules

- `src/lookup/schema_layout.py` holds the canonical schema layout, with the
  locales `en-US` and `zh-CN`, and `init.py` and `setup.py` read it from
  there. In a script you add, take the locale directory names from that
  module instead of writing them again.

## Checks

- After `init.py`, compare the counts and structure in
  `data/c3-schemas/_index.json` with the committed copy:
  `python scripts/schema_diff.py` reports the difference from `HEAD`.
- `.github/workflows/update.yml` calls `init.py` and must use the exporter's
  standard directories.
