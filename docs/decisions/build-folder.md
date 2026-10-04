# The products of a game project go in `.build/`

Date: 2026-10-04

## Problem

`pack_project.py` wrote its `.c3p` to `.tmp/<folder>.c3p` and
`export_project.py` its export to `.tmp/export-web`, in the folder that also
holds screenshots, preview recordings and browser profiles. A generating
agent did not take `.tmp/` for the place of a deliverable, passed `--out`
with a file name in the project root, and the 1.3 MB `.c3p` was committed in
the game's repository.

## Options

- Keep `.tmp/` and say in the docs that products go there: the folder's name
  says scratch, and an agent that wants to keep a file moves it out.
- Refuse an `--out` inside the project: it breaks a user who wants the file
  there on purpose.
- A folder of its own for products, ignored like `.tmp/`, and a note when
  `--out` lands elsewhere in the project.

## Decision

The third. `pack_project.py` writes to `.build/<folder>.c3p` by default and
`export_project.py` to `.build/web`; each writes a `.gitignore` of `*` into
`.build/`, as `open_in_editor.py` does into `.tmp/`, so the folder is
ignored without a line in the project's `.gitignore`. The gitignore block of
`references/generating-a-project.md` names it as well. A pack leaves `.build/`
out, as it leaves out `.git/` and `.tmp/`, and `open_in_editor.py` skips it
when it searches a folder for projects. An `--out` inside the project but
outside `.build/` and `.tmp/` is written, with a note on stdout that Git
commits it. Screenshots, recordings, browser profiles and the copy
`open_in_editor.py` hands the editor stay in `.tmp/`.

`screenshot_sheet.py` writes its pictures of event sheets to
`.build/sheets/` by default, with the same `.gitignore`, because they are
made to be handed to people (`sheet-screenshot.md`).

## Re-evaluate when

A product is still committed from a project root, or a client or engine
convention claims `.build/` for something else.
