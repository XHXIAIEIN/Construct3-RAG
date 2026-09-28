# A Release Is Fetched From Its Own CDN Directory

Date: 2026-09-28
Schema: Construct 3 r495.2

## Problem

`C3Fetcher` built every URL as `https://editor.construct.net/{release}/{path}`
with the release as `versions.json` names it. A patch release such as r495.2
has no `r495.2/` directory, so each request returned 404 and the fetcher took
the same path from the CDN root instead. The root serves whichever release is
stable at the time. While r495.2 is stable the two agree; once a newer stable
ships, `python scripts/init.py --version r495.2` would write the newer
release's ACEs, language packs and editor bundles into `data/` and label them
r495.2. Nothing in the output showed it: the fallback was one log warning per
file.

## Evidence

Probed with GET; HEAD returns 405 on some paths.

- A patch release's directory writes the dot as a dash: `r495-2/`,
  `r476-2/`, `r449-5/`. `versions.json` spells it the same way in the LTS
  `launchURL` (`https://editor.construct.net/r449-5/`) and in every
  `viewDetailsURL`.
- Every path the fetcher reads is served in the release directory, for
  `r495-2`, `r495`, `r503`, `r476-2`, `r449-5`, `r400` and `r300`: both
  `allAces.json`, `allEffects.json`, both `precompiled-{locale}.json`,
  `example-project-data.json`, `pluginList.json`, `behaviorList.json`,
  `offline.json`, `autocomplete-data.json`, `main.js` and both editor bundles.
  Every `.d.ts` that `r495-2/offline.json` lists resolves there too.
- The directory holds that release, not the latest one. `offline.json` names
  its build: 49502 under `r495-2/`, 47602 under `r476-2/`, 50300 under
  `r503/`. Under `r495-2/` each file is byte-identical to the root copy while
  r495.2 is stable.
- `versions.json` is the one file served only at the root.
- A release the CDN does not hold, such as `r999/`, returns 404.
- Refreshing r495.2 through `r495-2/` reproduces the committed `data/`
  exactly.

## Options

1. Keep the root fallback. Correct only while the requested release is the
   current stable one.
2. Request the dash directory and keep the root fallback, with a warning.
   No endpoint needs it, and a warning in a weekly job's log still leaves
   another release in `data/` under the requested name.
3. Request the dash directory and stop on a 404.
4. Take the directory from the `launchURL` of `versions.json`. It lists only
   the current Beta, Stable and LTS releases, and the Stable one's
   `launchURL` is the root, so it names neither an older release nor the
   stable release's own directory.

## Decision

Option 3. `release_directory()` in `src/ingest/c3_fetcher.py` turns the
release name into its directory, `r495.2` into `r495-2`, and
`C3Fetcher.url()` builds every request from it. `fetch()` and `fetch_raw()`
read nothing else: a 404 raises `FileNotFoundError` with the URL and the
release. `export_ts_defs()` logs a `.d.ts` that fails and goes on, as it did
for any error; every other fetch stops the refresh. `versions.json` stays at
the root, read by `latest_stable_version()`.

The release name still labels everything: the `version` of `_index.json`,
the cache directory `.cache/c3-cdn/r495.2/` and the refresh pull request.
`C3Fetcher` refuses a name outside the `r503` and `r495.2` forms. `r495-2`,
the directory's spelling, would fetch the right files and label them with a
release `versions.json` never names.

`scripts/extract_common_aces.py` reads `main.js` and
`plugins/allEditorPlugins.js` from the latest stable release's directory and
records that URL in the `_source` of `common_aces.json`.

## Re-evaluate when

- A fetch stops with a 404 for a release that `versions.json` lists: the CDN
  has changed how it names release directories. Read the new spelling from
  that release's `launchURL` or the editor's script URLs and change
  `release_directory()`.
- `versions.json` names a release outside the `r503` and `r495.2` forms:
  extend the pattern and the directory mapping together.
- The CDN publishes a list of release directories: read it instead of
  deriving the name.
