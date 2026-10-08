# A refusal the checker passed becomes a report the user sends

Date: 2026-10-08

## Problem

The checker learns each load rule from a message of the editor
(`checker-editor-load-rules.md`). When the editor refuses a project that
`check_project.py` passes, that message is the next rule, and it reaches this
repository only if a user posts it. `open_in_editor.py` told the agent to pass
the message on to the user, and there it stopped. The message, the exception
and the event behind them carry the names of the user's game, paths of the
user's machine and the text of its strings, so they leave the machine only
when the user sends them.

## Options

- The script files the issue itself: the user does not see what leaves the
  machine.
- A sentence telling the agent to tell the user: the message stays in the
  conversation, with the project's names in it.
- A report written for the repository, with the project's names taken out,
  and the command that files it, which the user runs or asks for.

## Decision

The third. When `open_in_editor.py` opened one folder project, the editor
refused it, by the dialog that stopped the open or by the crash report it
showed while it built the preview, and `check_project.py` finds no problem in
it, the run ends with a `report:` line, the report, and the
`gh issue create` command that files it, or the repository's new-issue page
to paste it into. The report is also written to
`.tmp/editor-report-<fingerprint>.md`. The script sends nothing; its line
tells the agent to show the report and to send nothing unless the user says
yes.

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
such name stays as the editor wrote it, so the user reads the report, a dozen
lines, before it is sent, and may also write names back into the file.

The fingerprint is a hash of the redacted message and exception with every
number written as `N`: the same refusal at another event is the same report.
`.tmp/editor-reports.json` keeps each fingerprint with the date of its offer,
and a later run with the same fingerprint prints one line that says it was
offered and not to offer it again.

There is no report when the message names an addon by another author that
the project uses, which the user installs in the editor and the checker
cannot know; when the checker reports a problem, which comes first, or stops
on a file; for a `.c3p`, which the checker does not read; and when one run
opened several projects, as an eval iteration does.

## Re-evaluate when

- A filed report carries a name of the game the redaction missed: read that
  name's source as well.
- The repository moves: `REPOSITORY` in `open_in_editor.py` and the source in
  `SKILL.md`'s metadata change together, and a test keeps them equal.
