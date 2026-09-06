# Schema Index Split by Locale

Date: 2026-09-07
Schema: Construct 3 r495.2

## Problem

`data/c3-schemas/_index.json` carried `name_en` and `name_zh` for every
plugin, behavior, and effect, while every other file under `c3-schemas/` is
split by locale. A reader of one locale had to parse the other language, and
a third locale would have meant another `name_*` column in the root index
instead of another directory.

## Evidence

Readers of the root index before the change, from a full search of this
repository and of the downstream repositories Construct3-Copilot and
Construct3-Clipboard (default branches only):

| Reader | Fields used |
|---|---|
| `src/schema_layout.py` | `version`, `languages`, `file` |
| `src/lookup/schema_index.py` | `originalId`; effect `name_en` and `name_zh` for query matching |
| `tests/eval_query_quality.py` | `version` |
| `tests/semantic_eval/cli.py` | whole-file SHA-256, regenerated for each live run |

Every other `name_en` and `name_zh` in the code base is a field of the
in-memory bilingual merge built from the per-locale schema files, not of the
index. `supported_languages` had no reader in code; since the CDN locale
listing started returning 404 it held the same two entries as `languages`.
No external consumer of the index names was found.

## Options

1. Keep the bilingual root index. No work, but the layout stays inconsistent
   and grows a column per locale.
2. Make the root index language neutral and add `{locale}/_index.json` with
   `name` and `file`. One new file per locale, two code readers to update.
3. Drop names from every index and read them from the schema files. Effect
   name matching would then open every effect file per locale at startup.

## Decision

Option 2. The root index keeps `version`, `languages`, `originalId`, `file`,
the ACE counts, effect `category`, and `examples`. `supported_languages` is
removed. Each locale directory gets `_index.json` with `version`,
`language`, and `{name, file}` per addon, keyed by the same ids as the root.

`schema_layout.schema_is_complete` now also requires every locale index to
exist and to list exactly the manifest's ids with non-empty names, so a
snapshot missing one side fails selection instead of loading half named.
`schema_index.py` builds its effect name map from the locale indexes.

One visible data change: the zh-CN name of `_common` used to be `公共`, a
constant the exporter substituted because the zh-CN language pack has no name
for it. The locale index takes the name from the exported file, so it now
says `Common`, the same value `zh-CN/plugins/_common.json` already had.

## Re-evaluate when

- A third locale is exported. The root index should need no change; if it
  does, the split was not clean.
- A downstream consumer reports reading `name_en` or `name_zh` from the root
  index. Restoring them is a small exporter change but reintroduces the
  inconsistency, so prefer pointing the consumer at the locale index.
