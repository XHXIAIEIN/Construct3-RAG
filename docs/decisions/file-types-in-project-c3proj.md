# The Type the Editor Records for a Listed File

Date: 2026-10-16
Schema: Construct 3 r495.2

## Problem

`project.c3proj` lists the project's files under `rootFileFolders`, and each
entry carries a `type`, a MIME string the editor records. The generator
template wrote one of two values for a file under `general`:
`application/json` for a name ending in `.json`, `text/plain` for every
other name. Another toolchain, studied on 2026-10-16, keeps a table of the
type per extension and says it took the values from editor saves; it lists
`.jpg`, `.mp3`, `.mp4`, `.gif`, `.webp` and `.m4a`, which this repository had
no evidence for. The template and the checker should rest on what the
editor wrote in the official examples.

## Evidence

Every entry of every `rootFileFolders` folder of the 544 manifests in
`Construct-Example-Projects/example-projects/*/project.c3proj` (clone at
`a9279d91`), counted by extension and `type`. The editor wrote the same
type for one extension in every folder kind, except for `.js`:

| Extension | `type` | Entries | Examples | Folders |
|-----------|--------|---------|----------|---------|
| `.css` | `text/css` | 12 | 12 | general |
| `.csv` | `text/csv` | 4 | 2 | general |
| `.glb` | `application/octet-stream` | 1 | 1 | general |
| `.html` | `text/html` | 2 | 2 | general |
| `.js` | `application/javascript` | 106 | 75 | script 104, general 2 |
| `.js` | `text/javascript` | 10 | 3 | script 6, general 4 |
| `.json` | `application/json` | 85 | 47 | general |
| `.png` | `image/png` | 3678 | 540 | icon 3662, general 16 |
| `.svg` | `image/svg+xml` | 8 | 4 | general |
| `.ts` | `application/typescript` | 73 | 48 | script 71, general 2 |
| `.txt` | `text/plain` | 65 | 35 | general |
| `.wasm` | `application/wasm` | 3 | 3 | general |
| `.xml` | `text/xml` | 1 | 1 | general |
| `.otf` | `application/font-sfnt` | 2 | 2 | font |
| `.ttf` | `application/font-sfnt` | 42 | 25 | font |
| `.woff` | `application/font-woff` | 1 | 1 | font |
| `.webm` | `audio/webm; codecs=opus` | 538 | 37 | sound 440, music 98 |

- `.js` is the only extension with two types. `text/javascript` comes from
  three examples: `integrated-3d-engine-js` (six scripts and two files in
  Files), `echarts-demo-js` and `loading-script-and-wasm-js`. The
  examples do not show what makes the editor choose it, so that cause is
  unknown.
- The `video` folder is empty in all 544 manifests. No entry has the
  extension `.jpg`, `.jpeg`, `.gif`, `.webp`, `.mp3`, `.m4a` or `.mp4`.
- `FONT_TYPES` of the template (`.woff` `application/font-woff`, `.ttf` and
  `.otf` `application/font-sfnt`) and `AUDIO_TYPE` of the checker
  (`audio/webm; codecs=opus`) agree with the rows. The measurement does not
  contradict them.
- The values come from editor saves, not from a specification. They are as
  old as the oldest example; the examples were saved before the editor wrote
  `llm-context.md` (`skills/AGENTS.md`).

## Options

1. **Keep the two-way choice.** It writes `text/plain` for a `.css` or
   `.html` file, which the editor writes as `text/css` and `text/html`.
2. **Take the other toolchain's table.** Six of its extensions have no
   entry in the examples.
3. **A table of the extensions the examples saved, `application/octet-stream`
   for the rest.** Chosen.

## Decision

- `GENERAL_TYPES` in `assets/build_project.py` maps the twelve extensions
  that the examples saved under `general` to their type, with
  `application/javascript` for `.js`, the type of 106 of the 116 entries.
  `general_file()` writes `application/octet-stream` for any other
  extension. The extension is read in lower case.
- `check_project.py` warns, never fails, when a `general` entry's `type` is
  not one the examples show for its extension, and gives the observed type
  in the message. For `.js` it accepts both types. It says nothing about an
  extension the examples never saved, since it has no evidence for it. The
  editor opens a project with another type, so the finding is a warning
  (`skills/construct3-agent-plugin/references/checker-rules.md`).
- The checker's table and the template's are kept equal by
  `tests/test_skill_build_project.py`.

## Re-evaluate when

- A new example or an editor release saves a type for one of these
  extensions that the table lacks: add it to the table and to this record.
- An example saves `.jpg`, `.mp3`, `.mp4` or another extension under
  `general`: add its row.
- The cause of `text/javascript` is found: the template can write it for
  that case.
