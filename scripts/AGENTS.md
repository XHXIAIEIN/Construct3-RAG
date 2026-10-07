# scripts/ Directory

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `bootstrap.py` | Clone the sibling repositories that are missing, create the game project from the empty project when its folder does not exist, and install the skill in it; the second command of the README's Set up section | `python scripts/bootstrap.py --project <folder>` |
| `build_plugin.py` | Build `plugin/`, the Claude Code plugin, from the skill, the data it reads and the prompts, under the limits of Claude's plugin directory. `--check` compares `plugin/` with a fresh build (`docs/decisions/plugin-folder.md`, `docs/decisions/plugin-tracks-commits.md`) | `python scripts/build_plugin.py` |
| `setup.py` | Install the dependencies and start the lookup server; `--refresh-data` refreshes `data/` from the CDN first | `python scripts/setup.py` |
| `init.py` | Fetch CDN data, export it into the cache, and replace `data/c3-schemas`, `c3-examples`, `c3-lang`, `c3-ts-defs`; then write each of Scirra's guides in `data/c3-guides/` whose text changed, and build `plugin/` again | `python scripts/init.py`; `--guides-only` for the guides alone, `--guide-html <page>` for a page saved from a browser |
| `check_c3_version.py` | Compare the release `data/` holds with the latest stable release on the CDN | `python scripts/check_c3_version.py` |
| `schema_diff.py` | Report what changed between two schema snapshots and which tracked files quote an id the change broke; the body of the update pull request | `python scripts/schema_diff.py [--base <rev or folder>] [--target <rev or folder>]` |
| `output_diff.py` | Run the skill's read-only tools over every official example, a fixed list of lookups, `new_project.py` and the generator template with a ref's scripts and with the working tree's, and list the cases whose output differs. Nothing is written to the repository. Before changing a skill script, read the `skills/AGENTS.md` Rules bullet "A change to a script is compared, old against new" | `python scripts/output_diff.py [REF]`; `--only print_sheet`, `--limit 20` for a quick run |
| `extract_common_aces.py` | Regenerate `src/ingest/common_aces.json` (shared world-object ACEs) from the editor bundle | `python scripts/extract_common_aces.py` |
| `reference_games/` | Download public Construct exports into `.local`, decode their event data, build contact sheets and compare motion statistics | `python -m scripts.reference_games <fetch|decode|atlas|report|all>` |

`init.py` and `setup.py` read the canonical `en-US`/`zh-CN` schema layout from
`src/lookup/schema_layout.py`; do not duplicate locale directory names in new scripts.

Checks: after `init.py`, compare counts and structure in
`data/c3-schemas/_index.json`; `.github/workflows/update.yml` calls `init.py`
and must use the exporter's standard directories.
