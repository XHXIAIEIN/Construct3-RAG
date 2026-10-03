# Scirra's Project Format Guide Is a Source of Rules

Date: 2026-10-03

## Problem

The editor writes `llm-context.md` into every project it saves (from r477,
"Add llm-context.md to saved projects" in
`Construct3-Manual/releases/beta.json`). It outlines the folder and links
Scirra's guide
[Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275)
(CC BY 4.0), which states what the format keeps across releases: what
`project.c3proj` indexes, how files are named, which formats they take,
which files the editor ignores.

The editor's loader and the official examples do not show those things. The
loader shows what stops an open, not what the editor ignores or how it names
a file, and the examples in the clone were saved before r477, so a
measurement over them shows neither `llm-context.md` nor anything the editor
writes since. A rule taken from those two alone can refuse what the editor
opens, a frame whose JSON size differs from its image, or leave out what the
examples lack, the folders of videos, 3D models, palettes and tilemap
brushes.

## Evidence

The probes are in `checker-editor-load-rules.md`, under the bullet on the
guide: an image's size comes from its file, an unlisted file is ignored, a
listed video with no file stops the editor, a WAV sound opens. The rules
taken from the guide add no finding over the official examples.

## Options

1. Keep the loader and the examples as the only sources.
2. Read the guide as a third one. Each statement goes to the file that owns
   it; it becomes a checker rule only when it is precise enough to check, a
   probe in the editor agrees with it and the official examples add no
   finding.

## Decision

Option 2. Where each statement of the guide lives:

| The guide states | Where it is written | What checks it |
|------------------|---------------------|----------------|
| The format has no published specification and changes between releases; an invalid edit can leave a project that does not open | `prompts/references/hand-editing-project-files.md`, "The project folder" | the checker, then `open_in_editor.py` (`checker-editor-load-rules.md`) |
| `project.c3proj` indexes the project; a file it does not list is ignored | the same section | `check_project.py`: a warning, `scripts/` aside |
| Each JSON resource is in its folder, under the subfolders the listing names | the same section | the checker reads a resource by its listing |
| Images are in `images/` without subfolders, named `<type>-<animation>-<frame>.png` or `<type>.png` in lower case | the same section; `skills/construct3-agent-plugin/references/checker-rules.md` | the checker: a missing image is an error |
| An image imported in a lossy format and not edited keeps it, named by `fileType` | the same | the checker finds it through `fileType` |
| An image's `width` and `height` in its entry are ignored; the size comes from the file | the same | the checker does not compare them |
| A uid is any value, unique; six-digit random numbers suit source control | the same, "Encodings"; `random-uid-allocation.md` | the checker: a repeated uid is an error |
| A sid is a 15-digit random number | "Encodings" | `edit_sheet.py` and the generator write them; a repeated sid is a finding |
| Script, sound, music, video, font, icon and general files are in their folders and used as they are | `skills/construct3-agent-plugin/references/checker-rules.md`, the table | the checker: a listed file missing from its folder, `video` included, is an error |
| Sound and music are WebM Opus | "The project folder"; `prompts/references/sound.md` | the checker: a warning |
| Fonts are best WOFF, icons PNG, video MP4 with H.264 | "The project folder" | not checked: the editor also takes TTF and OTF fonts, and the rest is a choice made in the editor |
| TypeScript is `.ts` alone or `.js` alone | "The project folder" | the checker: both of one script listed is a warning |
| UI state files and `uistate` folders can be deleted; palettes and tilemap brushes have root folders | "The project folder" | `data/c3-new-project/` leaves UI state out; `pack_project.py` packs all of these |
| A `.c3p` is the project folder zipped | `pack_project.py` | it writes `project.c3proj` at the archive's root |
| Layouts hold a tree of layers, event sheets a tree of blocks | `skills/construct3-agent-plugin/references/checker-rules.md` | the checker walks sub-layers and sub-events |

`llm-context.md` is the editor's file: `data/c3-new-project/` keeps it, and
`pack_project.py` packs it. A rule about the folder, a file name or a file
format starts from the guide (`skills/AGENTS.md`).

### The copy in `data/`

The guide is kept as `data/c3-guides/constructs-project-format.md`, so an
agent reads it from the clone, and the game project's block sends a new,
renamed or moved file there. It sits beside the release data, outside the
directories the export replaces, because it changes when Scirra edits the
page and not with a release; it has no locale folder because the page is
English only. The front matter carries what CC BY 4.0 asks for: the source,
the authors, the license and what was changed. The update fetches it every
week and writes it only when its text changed (`docs/dev/data-pipeline.md`).

construct.net answers a script with a browser check (HTTP 403) and serves
the page to a browser. The committed copy is extracted from the page a
browser received; `tests/fixtures/constructs-project-format.html` is that
page cut down for the extractor's tests, the parts it reads as the server
sent them. While the check stays, the weekly fetch logs a warning and keeps
the copy, and a person refreshes it from a saved page with
`python scripts/init.py --guides-only --guide-html <page>`. The script makes
no attempt to pass the check.

## Re-evaluate when

- The guide's last-updated date moves: compare it with the table.
- The weekly fetch gets the page, or the browser check also stops a saved
  page from a browser: the hand refresh goes, or needs another source.
- The official examples include projects saved by r477 or later: what the
  editor writes since then can be measured over them.
