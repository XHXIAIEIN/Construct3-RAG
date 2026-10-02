# Setting a Machine Up from the URL Alone

Date: 2026-09-22
Schema: Construct 3 r495.2

## Problem

A user new to Git gives an agent the address of this repository and nothing
else: no clone, no game project, often no instruction file. The agent can
clone, but nothing told it what to clone and what to run afterwards, and a
small model does not assemble four clones and an install from prose; it
follows a command block it is given.

## Decision

- The first section of both READMEs, after three lines that route the
  reader to setup, lookup or `AGENTS.md`, opens with two commands in one
  block: clone this repository into `$HOME/Construct3`, then run
  `$HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame`.
  The cases that change the command (an existing project as a path,
  `--into`, `--template`) follow as one paragraph, and the last line says
  to read the project's `AGENTS.md`, with the pointer from another
  instruction file such as `GEMINI.md` in that same line: a small model
  given the README alone skipped that pointer while it sat in a paragraph
  among the options, and acts on the line that says what to read next.
- The folder is written out because the working directory is what varies
  between sessions: a clone that lands somewhere new gets a second set of
  siblings, over a gigabyte, and neither side finds the other. Run again,
  the commands stop at `git clone`, which refuses a folder that holds files.
  `~` is not the spelling: PowerShell hands it to Git unexpanded, and Git
  makes a folder named `~`. `$HOME` is expanded by PowerShell, bash and zsh;
  `cmd.exe` has `%USERPROFILE%`. A user who keeps repositories elsewhere
  writes that folder into both commands.
- `--project` takes a name or a path. A bare name is created beside the
  clones; a path with a separator, a drive, `~` or `.` is read from the
  working directory.
- `scripts/bootstrap.py` clones the missing siblings beside this repository,
  `Construct-Example-Projects` with `--depth 1`, creates the project folder
  when it does not exist, and runs the skill's `install.py`. A clone that is
  present is left alone, so the script can run again. Without Git it says
  what to install or download and exits 1. `--no-examples` skips the largest
  clone; on Windows a deep `--beside` folder needs Git's `core.longpaths`
  for the manual.
- The empty project is `data/c3-new-project/`, the files the editor saves
  for **Project** > **New** as a project folder, without its
  `*.uistate.json`. A new project needs no network. The copy gets the
  folder's name and a fresh `uniqueId`. It has no scripts folder: the
  editor's Scripts menu adds one when a project needs it.
- `install.py` writes `@AGENTS.md` into `CLAUDE.md`, creating the file, when
  it writes the block: a novice does not act on a note that the line is
  needed.

Refreshing `data/c3-new-project/` by driving the editor was tried and
dropped: the editor sometimes closed the New project dialog without making a
project, and a run that reported success could save a file short. When a
release changes what the editor writes, save a new empty project from the
editor as a folder over it, leave out the `*.uistate.json`, and check that
`savedWithRelease` moved.

## Not verified

- A small model starting from the URL alone in a harness with a shell.
