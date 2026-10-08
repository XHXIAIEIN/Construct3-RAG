# A refusal the checker passed becomes a report the user sends

Date: 2026-10-08

## Problem

The checker learns each load rule from a message of the editor
(`checker-editor-load-rules.md`). When the editor refuses a project that
`check_project.py` passes, that message is the next rule, and it reaches this
repository only if a user posts it. The message, the exception and the event
behind them carry the names of the user's game, paths of the user's machine
and the text of its strings, so they leave the machine only when the user
sends them.

## Options

- The script files the issue itself: the user does not see what leaves the
  machine.
- A sentence telling the agent to tell the user: the message stays in the
  conversation, with the project's names in it.
- A report written for the repository, with the project's names taken out,
  and the command that files it, which the user runs or asks for.

## Decision

The third. The report comes when `open_in_editor.py` opened one folder
project, the editor refused it, and `check_project.py` finds no problem in
it. A refusal is the dialog that stopped the open, or the crash report the
editor showed while it built the preview.

The run then ends with a `report:` line, the report, and the
`gh issue create` command that files it, or the repository's new-issue page
to paste it into. The report is also written to
`.tmp/editor-report-<fingerprint>.md`. The script sends nothing. Its line
tells the agent to show the report and to send nothing unless the user says
yes, because the report comes from the user's project.

The report holds these fields and no others:

- the editor's message, and the first line of the exception it logged;
- the event the message names, `Game, event 12`, as `print_sheet.py` prints
  it;
- the editor's release and the release that saved the project;
- the checker's version, the plugin's version or the clone's commit, and the
  release of the schemas;
- the fingerprint.

In each of them:

- Every name the project's files give is a placeholder of its kind,
  `<object 1>`, `<variable 2>`: sheets, layouts, object types and families,
  variables and parameters, functions and custom actions, groups, layers,
  behaviors, effects, animations, files and the project itself. A name of one
  character stays, since it identifies nothing and the placeholder would
  break the message.
- Text in quotes is `"…"`: a string in an expression may hold what the player
  reads, an address or a key.
- The project's folder is `<project folder>` and the home folder `~`.
- The exception's stack, the window title, the editor's warnings and the
  screenshot stay out.

The redaction replaces what the files name. A word of the game that is no
such name stays as the editor wrote it, so the user reads the report before
sending it, and can edit a name that remains or write a name back.

The fingerprint is a hash of the redacted message and exception with every
number written as `N`: the same refusal at another event is the same report.
`.tmp/editor-reports.json` keeps each fingerprint with the date of its offer,
and a later run with the same fingerprint prints one line that says it was
offered and not to offer it again.

There is no report in four cases:

- The message names an addon by another author that the project uses. The
  user installs it in the editor, and the checker cannot know it.
- The checker reports a problem, which comes first, or stops on a file.
- The project is a `.c3p`, which the checker does not read.
- One run opened several projects, as an eval iteration does.

## Re-evaluate when

- A filed report carries a name of the game the redaction missed: read that
  name's source as well.
- The repository moves: `REPOSITORY` in `open_in_editor.py` and the source in
  `SKILL.md`'s metadata change together, and a test keeps them equal.
