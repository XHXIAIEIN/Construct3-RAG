# Scirra's Project Format Guide Is a Source of Rules

Date: 2026-10-03

## Problem

Since r477 the editor writes `llm-context.md` into every project it saves.
It outlines the folder and links Scirra's guide
[Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275)
(CC BY 4.0), which states what the format keeps across releases: what
`project.c3proj` indexes, how files are named, which formats they take,
which files the editor ignores.

The checker's rules come from the editor's loader and the official
examples, and the examples in the clone were all saved before r477: a
measurement over them never shows `llm-context.md`, nor anything the editor
started writing since. The instruction files read `llm-context.md` only as a
router, one that does not point to this repository, so the guide it links
was cited nowhere. Two things followed from that. The checker refused, as an
error, a frame whose JSON size differs from its image, which the editor
opens; and the project packer left out the folders the examples happen not
to have.

## Evidence

The probes are in `checker-editor-load-rules.md`, under the bullet on the
guide: an image's size comes from its file, an unlisted file is ignored, a
listed video with no file stops the editor, a WAV sound opens. Over the
official examples every sound and music file is WebM Opus, every image a
PNG in lower case directly under `images/`, every file in a resource folder
or a file folder is listed, and no script is listed as both `.ts` and
`.js`; fonts are mostly TTF.

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
| Images are in `images/` without subfolders, named `<type>-<animation>-<frame>.png` or `<type>.png` in lower case | the same section; `references/checker-rules.md` | the checker: a missing image is an error |
| An image imported in a lossy format and not edited keeps it, named by `fileType` | the same | the checker finds it through `fileType` |
| An image's `width` and `height` in its entry are ignored; the size comes from the file | the same | the checker does not compare them |
| A uid is any value, unique; six-digit random numbers suit source control | the same, "Encodings"; `random-uid-allocation.md` | the checker: a repeated uid is an error |
| A sid is a 15-digit random number | "Encodings" | `edit_sheet.py` and the generator write them; a repeated sid is a finding |
| Script, sound, music, video, font, icon and general files are in their folders and used as they are | `references/checker-rules.md`, the table | the checker: a listed file missing from its folder, `video` included, is an error |
| Sound and music are WebM Opus | "The project folder"; `prompts/references/sound.md` | the checker: a warning |
| Fonts are best WOFF, icons PNG, video MP4 with H.264 | "The project folder" | not checked: the examples use TTF and OTF fonts, which the editor takes, and the rest is a choice made in the editor |
| TypeScript is `.ts` alone or `.js` alone | "The project folder" | the checker: both of one script listed is a warning |
| UI state files and `uistate` folders can be deleted; palettes and tilemap brushes have root folders | "The project folder" | `data/c3-new-project/` leaves UI state out; `pack_project.py` packs all of these |
| A `.c3p` is the project folder zipped | `pack_project.py` | it writes `project.c3proj` at the archive's root |
| Layouts hold a tree of layers, event sheets a tree of blocks | `references/checker-rules.md` | the checker walks sub-layers and sub-events |

`llm-context.md` is the editor's file: `data/c3-new-project/` keeps it, and
`pack_project.py` packs it. A rule about the folder, a file name or a file
format starts from the guide (`skills/AGENTS.md`).

## Re-evaluate when

- The guide's last-updated date moves: compare it with the table.
- The official examples include projects saved by r477 or later: what the
  editor writes since then can be measured over them.
