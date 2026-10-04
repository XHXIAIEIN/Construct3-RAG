# Analyze Published Construct Games

Contents: [Run the study](#run-the-study), [Read the output](#read-the-output),
[Maintain the decoder](#maintain-the-decoder),
[Update the catalog](#update-the-catalog),
[Interpret the evidence](#interpret-the-evidence).

The reference-game analyzer turns public Construct web exports into local,
searchable evidence about project structure, event sheets, palettes and motion.
It writes all downloaded and generated material under the ignored
`.local/docs/evidence/c3-reference-games/` directory.

Use it for comparative research. Do not commit or redistribute downloaded game
files, fonts, images, decoded event sheets or contact sheets.

Nothing that identifies a studied game belongs in a tracked file: no game or
author name, source slug, download URL, query parameter, CDN identifier, local
path, manifest or run metadata. The game list, `catalog.json`, is one of these
and lives in the ignored evidence directory. Aggregate rules go into records
without saying which games they came from.

## Run the study

Run the complete catalog from the repository root:

```bash
python -m scripts.reference_games all
```

This downloads the exports listed in the local
`.local/docs/evidence/c3-reference-games/catalog.json`, decodes them, builds image contact
sheets and writes the aggregate reports.

Run one stage when the downloads already exist:

```bash
python -m scripts.reference_games decode
python -m scripts.reference_games atlas
python -m scripts.reference_games report
```

To restrict a stage, pass sources to `fetch` and downloaded folder names to
`decode` or `atlas`:

```bash
python -m scripts.reference_games fetch <kind>:<id> <kind>:<id>
python -m scripts.reference_games decode <folder> <folder>
python -m scripts.reference_games atlas <folder>
```

Atlas generation requires Pillow. Fetching, decoding and statistics use the
Python standard library and the repository’s schema data.

## Read the output

The analyzer creates this local structure:

```text
.local/docs/evidence/c3-reference-games/
├── catalog.json
├── downloads/<game>/
│   └── manifest.json
├── decoded/<game>/
│   ├── sheets/*.txt
│   ├── aces.jsonl
│   ├── summary.json
│   ├── summary.md
│   ├── images.png
│   └── palette.json
└── stats/
    ├── stats.json
    ├── stats.md
    └── compare_authors.txt
```

Use `summary.json` for project structure, `aces.jsonl` for aggregate action
counts, and the decoded sheets for individual sequences. Treat `images.png` as
a contact sheet for visual inspection, not a source asset.

## Maintain the decoder

The decoder reads the object reference and expression tables from each game’s
own runtime. A minified export may keep those tables under mangled names. In
that case, the output preserves object names, variables, groups and constants
but prints numbered ACEs and expressions.

Resolve parameter labels from `data/c3-schemas/en-US`, then resolve ordered
combo values from the cached editor `allAces.json`. The schema’s `items` map is
localized data in the language pack’s order. An export stores a combo as an
index into the order of the editor’s ACE definition, so the schema’s order
cannot decode it.

Read Tween’s one-property list from the sampled game’s runtime. Its order
changed across Construct releases. Applying the current editor order to an old
export shifts every property after Y: a width tween can be mislabeled as Z, an
opacity tween as depth, and a color tween as angle. Validate suspicious labels
against tags and end values: opacity commonly ends at 0, while color ends at an
`rgb` expression or packed color value.

Construct 2 and Construct 3 share enough project-array structure to recover
objects, layouts, groups and literals. Do not claim readable action semantics
when the runtime reference table cannot be recovered.

## Update the catalog

Add a source, an output folder and an author to the local `catalog.json`, a
list of `{"source", "folder", "author"}` objects. Keep collaborations as separate author
groups so aggregate statistics do not assign one implementation to the wrong
studio.

Regenerate the local reports, inspect errors in each `manifest.json`, and state
the sample size in the decision that uses the data; hashes and raw counts stay
in the evidence folder.

## Interpret the evidence

Separate three levels of confidence:

- Direct facts come from an event action, object property, effect parameter or
  image measurement with readable source data.
- Structural inferences combine names, constants and repeated arrangements when
  an ACE name is unavailable.
- Feel judgments require a live preview with input and audio and remain
  unverified until that preview is run.

Do not infer visible color frequency from raw instance-tint counts without
checking layouts. Palette storage objects can contribute hundreds of hidden
color swatches. Do not infer on-screen content from top-level layers alone;
some projects place the level inside sublayers.

Keep rules that survive across themes: proportional outline and shadow values,
motion durations, camera-region fields and pacing structures. Leave characters,
finished assets, exact palettes, third-party effects and platform integrations
with their original games.
