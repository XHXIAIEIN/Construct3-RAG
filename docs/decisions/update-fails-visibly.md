# The Data Update Fails Instead of Committing Less

Date: 2026-10-07
Schema: Construct 3 r495.2

## Problem

The weekly update could end green while it did less than it should, and
the result could auto-merge:

- The version check ended with `|| echo "changed=false"`. An unreachable
  CDN, an HTML `versions.json` or a renamed field read as "no new release",
  every week, with no signal.
- `fetch_raw()` cached whatever body came with status 200. A CDN or proxy
  error page was kept until the weekly cache expiry, and every refresh in
  that week failed with a JSON error that named no cause.
- One HTTP request had one attempt. With about 150 `.d.ts` requests a run,
  one 503 or timeout failed the export.
- A failed examples export logged a warning and still wrote the schema
  marker. `export_to_data()` deleted and copied each `data/` target in turn,
  with no check of what it copied: a cache without examples left new
  schemas beside an old language pack and no examples; an empty ts-defs
  cache deleted `data/c3-ts-defs` and raised nothing.

## Evidence

Each case was reproduced against the code before the change, with the
network stubbed: the version step's shell line exited 0 and wrote
`changed=false` on a `LookupError`; an HTML 200 body was cached and served
again without a request; a cache missing `examples/` left `data/` with two
releases; an empty ts-defs export removed `data/c3-ts-defs`. Exporting the
cached r495.2 files through the new path reproduces the committed `data/`
exactly.

## Options

1. Keep the warnings and rely on the review of the pull request. A loss in
   `c3-examples` or `c3-ts-defs` is not in the schema report, and a pull
   request with no watched id merges itself.
2. Check the data after `init.py`, in the workflow. A local `init.py` that
   fails midway still leaves `data/` mixed.
3. Check in the exporter and swap `data/` only when the whole export is
   there: a failure leaves `data/` as committed and fails the job, whose
   failure email is the signal.

## Decision

Option 3.

- `scripts/check_c3_version.py --github-output` is the workflow's version
  check. It exits 1 and writes no output when the CDN cannot be read, so no
  data step runs. The step continues on error so that a changed guide still
  opens its pull request, and the last step of the job fails it.
- `fetch_raw()` checks a body before it caches it: a JSON endpoint must
  parse and have its top-level type and key (`fileList` for `offline.json`,
  `text` for a language pack), and a `.d.ts` or `.js` must not be an HTML
  page. A refused body raises `ValueError` with the path and its first 80
  bytes, and nothing is cached.
- `_http_get()` retries an HTTP 5xx, a connection error and a timeout
  twice, one second apart. A 4xx is not retried; a 404 stays the
  `FileNotFoundError` of `cdn-release-directory.md`.
- A failed examples export, a failed `.d.ts` or autocomplete listing, and an
  `offline.json` that lists no `.d.ts` stop the export with no marker.
- `export_to_data()` builds the four targets in a `.data-staging-*` folder
  beside `data/`, checks them against what the CDN lists (complete schemas,
  each example in both locales, both language packs, every `.d.ts` of
  `offline.json`, the autocomplete listing), then renames them in. A failed
  rename puts back the targets already moved. A missing item raises
  `RuntimeError` naming it, and `data/` stays as it was.

What stays as it was: a guide that cannot be fetched keeps its committed
copy (`project-format-guide.md`), and the checks of a release that is
exported but fails them still open a pull request that waits for a person
(`release-schema-diff.md`).

## Re-evaluate when

- The CDN publishes digests of its files: check a body against its digest
  instead of its shape.
- The weekly job fails on transient CDN errors more than once a month: raise
  the retries or the delay.
- An endpoint changes its top-level shape: update `_JSON_SHAPES` in
  `src/ingest/c3_fetcher.py` with the reader that uses the endpoint.
