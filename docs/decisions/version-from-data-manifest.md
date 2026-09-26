# The Construct Release Comes From the Data, Not From a Setting

Date: 2026-09-26
Schema: Construct 3 r495.2

## Problem

The release number lived in three places: the CDN's `versions.json` (the
latest stable release), `data/c3-schemas/_index.json` (the release `data/`
holds) and a `C3_VERSION` setting, defaulted in `src/settings/__init__.py`
and overridable from `src/.env`. The update workflow rewrote the default with
a regular expression before each refresh.

The setting said nothing the other two did not. It could only disagree with
them: a `C3_VERSION` that `data/` did not hold sent the service to an export
in the cache instead of the committed data. After the Qdrant full mode was
removed (`remove-qdrant-full-mode.md`), the local `src/.env` held only keys
nothing read, and `C3_VERSION` was the reason the dotenv loading remained.

## Decision

- The service's release is `schema_version()` of the schema directory it
  reads: `data/c3-schemas`, or `C3_SCHEMA_DIR`.
- A refresh (`scripts/init.py`, `scripts/setup.py --refresh-data`) fetches
  the latest stable release from `versions.json`; `--version` names another.
  It replaces `data/` as before, so the service never reads the cache.
- `scripts/extract_common_aces.py` fetches the language pack of the latest
  stable release, the release its `main.js` comes from.
- `scripts/check_c3_version.py` compares `_index.json` with the CDN and
  prints the refresh command; `--update`, which wrote `C3_VERSION` into
  `src/.env`, is gone.
- The workflow reads the current release from the data and no longer edits
  source.

Removed with it: `C3_VERSION`, `select_schema_dir()` and the
`bundled_dir`/`generated_dir` settings, `src/.env.example`, every
`load_dotenv()` call and `python-dotenv`. `C3_SCHEMA_DIR`, `RAG_SERVER_PORT`,
`C3_CDN_BASE` and `C3_CACHE_DIR` stay environment variables; each has a reader.

## Trade-off

A refresh without `--version` now needs `versions.json` to answer. It needed
the network for everything else it fetches anyway.
