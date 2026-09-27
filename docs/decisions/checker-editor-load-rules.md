# The Checker Applies the Editor's Own Load Rules

Date: 2026-09-21
Schema: Construct 3 r495.2, read from the stable editor at
`https://editor.construct.net/`

## Problem

`check_project.py` checked that every ACE, parameter and name exists. A
project that passed could still be refused when the editor opened it, and
the agent learned each rule from an error the user pasted back, one per
round. The editor's message names no event, so a small model changed
something else and the session stalled.

Task: a small model generates a whole project, runs the checker until it
prints `ok`, and the project opens and previews the first time.

## Options

1. Leave the checker at schema membership. Every rule costs a round trip
   through the user.
2. Encode the editor's rules in the checker, each read from the editor and
   proven against the official examples, with a finding that names the event
   and says what to write instead.
3. Drive the real editor and read its error: the only complete oracle, but
   it needs a network and a browser, and shows one dialog at a time.

## Decision

Option 2 as the default, and option 3 as the step after it.

### The checker

- The rules, their messages and what each finding says are listed in
  `skills/construct3-project/references/checker-rules.md`.
- A rule is read from the editor's project loader as a whole call chain,
  located by the message it throws, not from the one message a user pasted:
  the next assertion in the same function would cost another round trip.
  The manual states some of them (`how-events-work.md` "Triggers",
  `sub-events.md`, `conditions.md` "Inverting conditions"), and the Addon SDK
  guide defines the flags they read (`isFakeTrigger`, `isLooping`,
  `isInvertible`, `isCompatibleWithTriggers`).
- A rule becomes an error only after a run over the official examples adds
  no finding. *Trigger once* and *Every X seconds* in a triggered branch
  occur in official examples that open, so they are a warning.
- The exporter writes `isTrigger` for every condition the editor treats as a
  trigger, `isFakeTrigger` and `isFastTrigger` included, and keeps
  `isLooping`, `isInvertible: false` and `isCompatibleWithTriggers: false`.
  *On collision*, *On timer* and the Gamepad button conditions were missing
  the flag before.
- `tests/test_project_tools.py` generates the stand-in project, breaks it one
  rule at a time and reads the finding, and compares the generated project
  with the keys every official example carries at each level.
- A missing key stops the run with one sentence, never a traceback.

The file encodings in `prompts/references/hand-editing-project-files.md`
were read the same way: from the loaders, from files the editor saved, from
the official examples and from `data/c3-lang/`.
`json.dumps(obj, indent="\t", ensure_ascii=False)` reproduces the editor's
bytes.

### The editor opener

The editor checks what the checker does not, the types of an expression
among them. `scripts/open_in_editor.py` drops the project on
editor.construct.net as a `.c3p` and reads the answer: `opened`, or `failed`
with the editor's dialogs and the exceptions it logged. `--preview` then
presses F5, lets the layout run for 5 seconds and prints each uncaught
exception and console error with its place, `Event sheet 1, event 3,
action 1`, the numbering `print_sheet.py` uses.

- Agents come with different browser tools or none, and no Python package
  is on every machine. The script starts the machine's Edge, Chrome or
  Chromium headless and drives it over the DevTools protocol with the
  standard library. With no browser, or with `--steps`, it prints the same
  check as three rounds of calls for the agent's own browser tool, and
  exits 3.
- The file goes through a file input the script puts on the page; it never
  leaves the browser. The editor's own **Open file** button uses a picker
  that no upload action fills.
- The page is read, not the screen: the title, the dialogs, and what the
  editor logs. Start-up dialogs are closed by their buttons in any language.
- A project saved by a newer release than the stable editor opens in
  `editor.construct.net/beta`; `--release` pins one.
- The browser profile lives in `.tmp/editor-browser` of the project, with a
  `.gitignore` of `*`. With the editor's scripts cached a run takes about 4
  seconds; cold, 10 to 40. Background features are switched off, so the
  profile holds the editor's cache alone. The profile path is passed as a
  `\\?\` path: past about 177 characters its IndexedDB exceeded MAX_PATH.
- The preview wraps the runtime's tick once to reach it, as skymen/c3cli
  (MIT) does, and reads the preview page and its workers once at the end.
  It runs without input: it catches what breaks on start, not what a player
  does later.

A passing check ends its `ok:` line with the opener's command. Agents given
the step only in `SKILL.md` often stopped at `ok:` and called the project
ready. `edit_sheet.py` ends a plan with the plain `ok:`: a line printed after
every step is read as routine.

The checker stays first: it is offline and names every finding at once, the
editor one dialog at a time.

The Free edition's limits, listed on construct.net/en/make-games/buy-construct
(25 events as a guest, 50 logged in with a verified email, 2 layers, 2
effects), restrict editing only. A guest opens, previews and runs a project
over them, families included, so they do not narrow what the editor checks.
They stay out of the prompts: a model told the editor caps events trims the
sheet it was asked to write.

## Re-evaluate when

- An official example fails a rule after a data sync: the rule changed in
  that release; find its message in the editor again.
- A generated project passes the checker and the editor refuses it: its
  message is the next rule.
- The opener cannot find the file input, the dialogs or the runtime's tick
  after an editor release: read the page again; the check still has
  `--steps`.
