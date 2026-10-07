# Data Pipeline

Contents: [Data Sources](#data-sources),
[CDN Fetching](#cdn-fetching-c3fetcher) (release directory, cache, export,
deprecation filter), [Scirra's Guides](#scirras-guides),
[Version Update](#version-update).

## Data Sources

| Source | Origin | Format | Updates |
|--------|--------|--------|---------|
| ACE definitions | `editor.construct.net/{ver}/plugins/allAces.json`, `behaviors/allAces.json` | JSON | Each C3 release |
| Language (en/zh) | `editor.construct.net/{ver}/loader/lang/precompiled-{lang}.json` | JSON | Each C3 release |
| Effects | `editor.construct.net/{ver}/effects/allEffects.json` | JSON | Each C3 release |
| Example metadata | `editor.construct.net/{ver}/media/example-project-data.json` | JSON | Each C3 release |
| TypeScript definitions | the `.d.ts` files that `editor.construct.net/{ver}/offline.json` lists, and `media/autocomplete-data.json` | TypeScript, JSON | Each C3 release |
| Shared world-object ACEs | `editor.construct.net/{ver}/main.js` of the latest stable release, extracted by `scripts/extract_common_aces.py` into `src/ingest/common_aces.json` | JSON | When a release adds a shared ACE |
| Deprecated plugins and behaviors | `editor.construct.net/{ver}/main.js`, `plugins/allEditorPlugins.js`, `behaviors/allEditorBehaviors.js`, read by `src/ingest/deprecated_addons.py` | JS | Each C3 release |
| Scirra's guide "Construct's project format" | `www.construct.net/en/tutorials/constructs-project-format-3275`, read by `src/ingest/guides.py` | HTML page | When Scirra edits it; fetched every week |

`{ver}` is the release's CDN directory: the release name, with the dot of a
patch release written as a dash, `r495-2` for r495.2. `versions.json`, which
names the current Beta, Stable and LTS releases, is the one file at the root.

The manual, the Addon SDK samples and the example projects are separate clones
(`Construct3-Manual`, `Construct-Addon-SDK`, `Construct-Example-Projects`).
Nothing here reads or copies them; `AGENTS.md` section 2 says where an agent
finds them.

## CDN Fetching (C3Fetcher)

`src/ingest/c3_fetcher.py` fetches and caches CDN data.

### Release Directory

Every file of a release comes from its own directory, `r495-2/` for r495.2.
If that directory returns 404, the fetch stops: the root serves whichever
release is stable now, so reading it would mix releases under one name.
`C3Fetcher` takes the release as `versions.json` names it, `r495.2`, and
refuses the directory spelling. See
`docs/decisions/cdn-release-directory.md`.

### Cache Strategy

- Cache directory: `.cache/c3-cdn/{release}/`, keyed by the release name (`r495.2`), not the directory
- Expiry: every Wednesday 08:00 Beijing time (aligned with Scirra's Tuesday UK evening releases)
- Within one cache period, each endpoint is fetched at most once
- `force=True` bypasses cache

### Schema Export

`C3Fetcher.export_schemas()` merges CDN structural data (`allAces.json`,
`allEffects.json`, `example-project-data.json`) with per-locale text
(`precompiled-{locale}.json`) into **per-language** schema files using
CDN-native field names. It writes `schemas/` and `examples/` in the cache,
`export_lang()` writes `lang/`, and `export_ts_defs()` writes `ts-defs/`:

```
.cache/c3-cdn/{release}/schemas/
  _index.json                  — language-neutral index (plugin/behavior/effect counts, originalId)
  en-US/_index.json            — English names + file paths, same ids as the root index
  zh-CN/_index.json            — Chinese equivalent
  en-US/_deprecated.json       — deprecated addons and ACEs, kept in the schema or not
  en-US/plugins/sprite.json       — English Sprite ACE definitions
  zh-CN/plugins/sprite.json       — Chinese Sprite ACE definitions
  en-US/behaviors/platform.json   — English Platform behavior ACEs
  en-US/effects/alphaclamp.json   — English effect definitions
  zh-CN/...                     — Chinese equivalents (same structure)

.cache/c3-cdn/{release}/examples/
  en-US/{id}.json               — English example project metadata
  zh-CN/{id}.json               — Chinese equivalent

.cache/c3-cdn/{release}/lang/
  en-US.json                    — raw precompiled language pack, re-indented
  zh-CN.json                    — Chinese equivalent

.cache/c3-cdn/{release}/ts-defs/
  **/*.d.ts                     — the TypeScript definitions offline.json lists
  autocomplete-data.json        — scripting classes with their members
```

The `lang/` files are the CDN text unchanged apart from indentation, so a
release-to-release diff of `data/c3-lang/` shows exactly which strings
Scirra added, removed, or retranslated.

`export_ts_defs()` skips a `.d.ts` file that is already in the cache, so each
cached file is written beside its place and then moved in: a run that stops
during a write leaves no partial file. If a file fails to download, the export
tries the rest, then stops with an error that names each failed file and writes
no `.exported` marker. `export_to_data()` replaces `data/c3-ts-defs` whole, so
a file that only logged a warning would drop out of the commit. The next run
downloads only the files that are still missing.

Each plugin/behavior file uses CDN field names:
- Conditions/actions: `list-name`, `display-text`, `description`
- Expressions: `translated-name`, `description`
- Params: `{param_id: {type, name, desc, items, initialValue}}` (an object
  keyed by param id; `items` for a combo, `initialValue` where the CDN
  records one)
- Structural fields from allAces: `scriptName`, `isTrigger`, `isFakeTrigger`,
  `isLooping`, `isInvertible`, `isCompatibleWithTriggers`, `isAsync`,
  `isDeprecated`, `returnType`, `isVariadicParameters`, `category`.
  `isTrigger` is also written for a CDN `isFakeTrigger` or `isFastTrigger`,
  since the editor holds all three to the same rules

`plugins/_common.json` goes through the same merge. Its structural side is
not on any CDN endpoint: the editor registers the shared ACEs in `main.js`,
and `scripts/extract_common_aces.py` copies that block into
`src/ingest/common_aces.json` in the `allAces` shape, with the release it was
taken from. The same script records which plugin gets which shared ACE: the
guards of that block (`AddCommonAppearanceACEs`, `SetSupportsColor` ...) as
`requires`, and the flags each built-in plugin's constructor sets in
`plugins/allEditorPlugins.js` as `plugins`. The export writes the result into
each plugin file as `commonAces`. The export stops when the language pack
names a shared ACE or parameter the file does not define; rerun the script,
review the diff and commit it with the data. See
`docs/decisions/common-aces-from-editor-bundle.md`.

The ACE counts in `_index.json` are those of the written files, after the
deprecation filter below.

Consumers that need both languages use `_merge_bilingual()` in
`src/lookup/schema_index.py`, which merges the `en-US` and `zh-CN` files
into one in-memory format. `src/lookup/schema_layout.py` owns the typed
`SchemaManifest`, the canonical locale names, manifest loading, the
completeness check and counts. Before changing what the export writes into
`_index.json` or a locale directory, read "Schema snapshot contract" in
`docs/dev/architecture.md`.

### Deprecation Filter

The editor hides a deprecated addon or ACE from its dialogs and keeps loading
projects that use it. `C3Fetcher.export_schemas()` leaves out:

- **Plugins and behaviors** whose editor constructor calls
  `SetIsDeprecated(true)`. `src/ingest/deprecated_addons.py` finds the minified
  name of that call in `main.js` and reads it from each constructor in
  `allEditorPlugins.js` and `allEditorBehaviors.js`. An addon of `allAces.json`
  the bundle does not construct stops the export. An addon the zh-CN pack does
  not name is left out too, since every locale file takes its ACE list from
  that pack.
- **Effects** with `"is-deprecated": true` in `allEffects.json`.
- **ACEs** absent from the zh-CN pack (e.g. `Browser/devicepixelratio`,
  replaced by `PlatformInfo/device-pixel-ratio`). This is not the editor's
  `isDeprecated` flag, and the two disagree on 28 ACEs of r495.2. A deprecated
  ACE the pack still names is kept and written with `isDeprecated: true`.

`{locale}/_deprecated.json` lists every deprecated addon and ACE, kept or
not, with the current ACE of the same name where there is exactly one;
`deprecated_list()` in `src/ingest/deprecated_addons.py` builds it. The
export clears its schema directory first, so what it leaves out does not
survive from an earlier export of the same release. See
`docs/decisions/deprecated-addons-from-editor.md`.

## Scirra's Guides

`src/ingest/guides.py` keeps a copy of each page it lists under
`data/c3-guides/`, one Markdown file named after the page:
`constructs-project-format.md` for the guide the editor's `llm-context.md`
links. A guide is a page of construct.net, not a file of a release, so it
lives beside the release data instead of in a directory the export replaces,
and has no locale: the page is English only.

`refresh_guides()` fetches the page, keeps the article and writes Markdown
that opens with front matter: the source URL, the title, the contributors as
the page lists them, the license (CC BY 4.0), and the published and
last-updated dates. The comments, the side menu and the site navigation are
left out. The file is written only when its text differs from the committed
one, so a week with no edit commits nothing.

A fetch that fails, or a page without the article, keeps the committed copy
and logs a warning; the rest of the refresh goes on. When construct.net
answers the script with a browser check (HTTP 403), the copy is refreshed by
hand from the page saved in a browser:

```bash
python scripts/init.py --guides-only --guide-html <saved page>
```

`scripts/init.py` refreshes the guides after the release data;
`--guides-only` refreshes them alone, which the update workflow runs every
week before it checks for a release. A changed guide opens a pull request,
which waits for a person: compare it with
`docs/decisions/project-format-guide.md`. Nothing reads the network on import
or on a query.

## Version Update

`data/c3-schemas/_index.json` records the release `data/` holds.
`scripts/check_c3_version.py` compares it with the latest stable release in
the CDN's `versions.json`. When Construct 3 releases a new version:

```bash
# Fetch the latest stable release (or --version <release>), replace data/,
# then build plugin/ again from it
python scripts/init.py

# What the release changed against the committed data, and which tracked
# files quote an id it broke; review them, then commit data/ and plugin/
python scripts/schema_diff.py
```

`scripts/schema_diff.py` compares two schema snapshots, each a folder or a git
revision, by the structural fields of the primary locale: addons and ACEs
added, removed or deprecated, and per ACE the parameters (added, removed,
retyped, combo items) and the flags `scriptName`, `isTrigger`, `isLooping`,
`isInvertible`, `isCompatibleWithTriggers`, `isAsync` and `returnType`. A
removal, a deprecation, or a change an event written for the old release can
trip on (a parameter removed, added or retyped, a combo item gone, a flag that
had a value and changed) is watched: the script lists every quoted or
backticked mention of the id in tracked prompts, skill files, code and docs.
Tests are not scanned, since the suite fails on its own.

`C3Fetcher.export_to_data()` is the one place that maps the cache onto
`data/`: it replaces `c3-schemas`, `c3-examples`, `c3-lang`, and `c3-ts-defs`
whole, leaving cache markers behind. The TypeScript definitions are written
as the CDN ships them, some with CRLF; `.gitattributes` stores every text
file as LF, so a refresh changes only what the release changed
(`docs/decisions/lf-line-endings.md`). `scripts/init.py` and the update workflow
both call it, so generated and committed layouts stay identical. The workflow
runs the checks of `AGENTS.md` (pytest, compileall, `build_plugin.py --check`)
in its own job, because a pull request opened with `GITHUB_TOKEN` starts no
other workflow. It then opens a pull request with the result and the
`schema_diff.py` report, against the data on `main`, as its body. It enables
auto-merge only when its checks passed, the report watches no mentioned id
and no guide changed, and every other check on the pull request passed within
10 minutes; otherwise the pull request waits for a person, with the end of the
check log in its body when the checks failed. See
`docs/decisions/release-schema-diff.md`.
