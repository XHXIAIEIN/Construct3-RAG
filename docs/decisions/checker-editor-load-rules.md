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
- Expression syntax is the editor's parser, not its loader, so the one
  syntax rule was read by opening a project: of `==`, `!=`, `&&`, `||`, `!`,
  `<>`, `&`, `|` and `"a == b"` as text, the editor refused the first five
  with `Syntax error` and took the rest. No official example writes one of
  the five outside a text literal. A Haiku eval run had written
  `Coin.value == 5 ? 1.5 : 1`, which the checker passed and the editor
  refused.
- JavaScript's power `**` was probed the same way on 2026-09-28: `2 ** 3`,
  `2**3` and `x ** 2` stopped the editor with `Syntax error: '*' can't go
  here`, and a preview ran `2 ^ 3` as 8 and `2 ^ -1` as 0.5, so `^` is
  power, not C's exclusive or, and stays allowed. No official example
  writes `**` outside a text literal; 32 parameters write `^`.
- A sound parameter was probed on copies of the audio-scheduling example,
  whose sound file is `sfx1.webm` and whose events write `SFX1`. The editor
  opened `SFX1` and `"SFX1"` in inner quotes, and refused `0`, `sfx1.webm`
  and `Missing` with `missing file '<value>'`. `0` was what `lookup_ace.py`
  wrote for a parameter type it had no entry for, and the checker skipped
  the type. The 277 sound parameters of the official examples all name a
  listed file without its extension, and the sweep changed no finding.
  `lookup_ace.py` now also writes a function, a tilemap brush, an effect,
  tags, an object name and a 3D animation the way the examples do.
- The 91 projects of the eval runs and the game folders that passed the
  checker on 2026-09-28 were opened in the editor. Three failed: a variable
  written by hand without `comment`, and two snapshots whose listed icons
  were not on disk. Probes that took one text key out of each event kind
  of the stand-in, one at a time, found three more keys the editor needs
  and the checker did not ask for (a comment's `text`, a group's
  `description`, a variable's `comment`), and that `functionReturnType`
  and `aceType` stop the open when missing or outside `none`, `number`,
  `string`, `any` and `action`. A function parameter's `comment` and a
  custom action's `functionReturnType`, `functionDescription` and
  `functionCategory` may be left out. Every official example writes all
  five; the sweep changed no finding.
- The one type mismatch among the 91 came from a local text variable named
  like a number variable in scope, under another case: names match without
  case and the nearest scope wins, so the number's expression read the
  text. The checker now refuses a local or function parameter named like a
  variable of another type in scope. None of the 565 sheets of the official
  examples declares one, and the sweep changed no finding. A same-typed
  local only hides the outer value, which the editor accepts. Type
  inference for the rest of an expression was not built: it needs a real
  expression parser, operator rules probed in the editor one by one and
  no new finding over the examples, to catch what the editor opener already
  reports; it is worth building when an open fails on a mismatch the
  shadowing rule does not explain.

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
  profile holds the editor's cache alone. Past about 177 characters the
  files of its IndexedDB exceed MAX_PATH, so a longer profile path is passed
  by its 8.3 short name, else as a `\\?\` path. The browser still opens no
  IndexedDB whose folder path, prefix counted, reaches MAX_PATH: a profile
  too deep for the preview's is refused before the preview, and `--profile`
  puts it in a shorter folder.
- `--jobs` opens each project in a window of its own. Tabs of one window
  are hidden except the front one, headless as well: their timers fire once
  a second and their animation frames not at all. An editor in such a tab
  stayed at "Opening (0%)" past the 85 seconds the script waits for its
  answer, and the project was reported as an error that opened when run
  alone. Over the 84 eval projects with `--preview 5 --jobs 3`, tabs gave 6
  such errors, each on a hidden page; windows gave none in three runs, the
  same answer per project each time, in 5 minutes against 9. The results
  are in `.local/docs/evidence/skill-evals/construct3-project/opened-2026-09-28/`.
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
