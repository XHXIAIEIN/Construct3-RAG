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
  `skills/construct3-agent-plugin/references/checker-rules.md`.
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
- Object class names were probed on 2026-10-03: a family named like an
  object type, like it in another case, or like the Functions object
  stopped the editor with `object class name 'X' already used`, and an
  object type listed twice with `object type name 'X' already used`. The
  sweep added no finding.
- Text literals were probed on 2026-10-03 in a text and a number parameter:
  an empty parameter stopped the editor with `Empty expression`, an
  unclosed literal with `String missing finishing "`, a backslash outside a
  literal with `Unknown character`, and `"a\b"` opened. The sweep added no
  finding.
- A function's return type decides how it is reached, probed on 2026-10-03:
  one returning a number called as an action stopped the editor with
  `function 'Two' has wrong return type`, the same read in an expression
  opened, and one returning none read in an expression stopped it with
  `has a return type of 'None' so cannot be used as an expression`. The
  sweep added no finding.
- A script in a function that read a parameter by its bare name stopped a
  preview on 2026-10-03 with `ReferenceError: string is not defined`, and
  ran with `localVars.string`. It and a *Wait for signal* that nothing
  raises are warnings: the editor opens both. No official example has
  either.
- An action the manual allows only in a user input trigger (*Request
  fullscreen*, *Request install*, *Request permission*, *Request wake lock*,
  a file picker, *Share* and the others its plugin pages name) is a warning
  when no touch, mouse, keyboard or form control condition stands in its
  event or above it, outside a function, which an input trigger may call.
  The browser refuses it there, and the editor opens it. *Request MIDI
  access* is left out: its page says some browsers allow it on startup, and
  the MIDI examples ask there first. Over the official examples the
  warning finds nothing else.
- Traps of the running game that the manual states are warnings too.
  Pathfinding (`behavior-reference/pathfinding.md`): a Solid changed while
  the obstacle map comes from Solids and nothing regenerates it, a path read
  in the same actions as the *Find path* that started it, and *Find path*
  every tick. No official example has any of them: the ones that change
  Solids regenerate, and the ones that find and move in one event wait
  between. A Sprite Font character outside its Character set
  (`plugin-reference/sprite-font.md`) is in a curly apostrophe of one
  example's text and in a game's `###` placeholder. An effect action naming
  an effect its target lacks is in two examples. A preview of a copy with an
  object effect action and a layout effect action naming a missing effect
  raised no error and ran the action after them. A layer action and a
  family's action accept the effects of the layer in any layout and of the
  family's members; neither was probed.
- Repeated ids were probed on 2026-10-03 in copies of one small project, each
  repeating one kind. Two object types with one sid, and a family with an
  object type's sid, stopped the editor with `object class sid already in
  use`, so a sid two object classes share is an error. Two events, two
  instances, an animation and an event, and a layer and its layout sharing a
  sid opened and previewed, so any other repeated sid is a warning; official
  examples that repeat such a sid open in the editor. Two instances with one
  uid opened too, but the preview showed one of them under another uid: the
  editor renumbers it, and a hierarchy link or a *Pick by UID* written for
  one may reach the other, so a repeated uid is an error, as a name the
  editor changes silently is.
- Scirra's guide
  [Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275),
  which the `llm-context.md` the editor writes into every project links,
  states what the folder holds. Its statements below were probed on
  2026-10-03 in the stable editor, each in a copy of an official example. A
  frame whose `width` and `height` differ from its image opened and
  previewed: the editor takes the size from the file, as the guide says, so
  the checker does not compare them. An event sheet file that
  `project.c3proj` does not list, holding an event type the editor refuses,
  opened and previewed: the editor ignores an unlisted file, and the checker
  warns about one outside `scripts/`, where the editor keeps unlisted
  TypeScript files for an external editor. A listed video with no file
  stopped the editor with `missing file path 'videos\clip.webm'`, so `video`
  is among the kinds whose files must be on disk. A sound listed as a WAV
  file opened and previewed, so a sound or music file that is not WebM Opus,
  which the guide requires, is a warning. An image kept in a lossy format is
  found through its `fileType`, as the guide describes; it was not probed.
  A script listed as both `.ts` and `.js` is a warning, since
  Construct runs the `.js` (`typescript-construct.md`). None of these adds a
  finding over the official examples or the game folders.
- The exporter writes `isTrigger` for every condition the editor treats as a
  trigger, `isFakeTrigger` and `isFastTrigger` included, and keeps
  `isLooping`, `isInvertible: false` and `isCompatibleWithTriggers: false`.
  *On collision*, *On timer* and the Gamepad button conditions were missing
  the flag before.
- `tests/test_skill_check_project.py` breaks the stand-in project one rule at
  a time and reads the finding; `tests/test_skill_build_project.py` compares
  the generated project with the keys every official example carries at each
  level.
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
- A generated benchmark project declared a global constant `PHASE` above a
  global variable `phase` and wrote *Add 1 to phase*; the checker passed it
  and the editor refused it with `event variable phase is constant`. The
  loader binds a variable parameter through the same search an expression
  uses: the event's own function parameters, then the parameters and
  variables of each enclosing event from the nearest out, then the top-level
  variables of every sheet, each list in its order, and the first name that
  matches without case wins; the loader does not refuse two names that
  differ only in case. Five probes opened as that order predicts: the
  constant first refused, the variable first opened whichever case the
  action wrote, a local constant refused over a global variable and a local
  variable opened over a global constant. The checker now resolves a
  variable parameter in that order, so it also passes the two probes that
  opened, which it had refused. The official examples and the game folders
  print as before.
- Two variables of one scope whose names match without case are an error at
  the second declaration, although the editor opens such a file: every use
  of the name reaches the first, so the second is never read or written,
  and the editor's variable dialog refuses the name (`The name X is already
  used in this scope`). A global and a local pair, each declared twice in
  one list, opened in the editor. No official example declares one; the
  sweep added eight findings, all in one small model's project, which
  declares its globals at the top of both of its sheets.
- Two expression rules were added after a game project met them and minimal
  projects reproduced them in the r504 editor on 2026-10-02, each beside a
  corrected copy that opened. A function parameter named like a system
  expression is read as that expression, as a variable is: a parameter
  `round` in `"第 " & round & " 轮"` stopped the editor with `'round' does
  not accept 0 parameters`. A function without parameters called with an
  empty pair, `Functions.settling()`, stopped it with `Syntax error: ')'
  can't go here`. None of the 1028 function parameters of the official
  examples is named like a system expression and none of their sheets
  writes the empty pair; the sweep changed no output.
- A generated project held `objectTypes/Functions.json` with the plugin id
  `Functions` and a `usedAddons` entry of that id by Scirra. The checker
  warned that the plugin had no schema and passed; the r495.2 editor
  stopped with `Missing addons ... Plugin Functions (Functions) by Scirra
  (legacy SDK v1)`. Functions are built in: `project.c3proj` names the
  object in `functionsName`, and the official examples write
  `"objectClass": "Functions"` with no object type or `usedAddons` entry
  for it. The checker now refuses an object type named like
  `functionsName`, and a plugin or behavior id that `usedAddons` lists by
  Scirra but the schema index lacks, since the index holds every addon by
  Scirra; an id by another author stays a warning. None of the 524 official
  examples has either finding.
- The same project's `project.c3proj`, copied from the editor's new project,
  listed `Timeline 1` and `Flowchart 1` without the `timelines/` and
  `flowcharts/` folders; the editor stopped with `missing file path
  'timelines\Timeline 1.json'`. The checker read the files of object
  types, families, layouts and sheets but not of these two lists, and now
  refuses a listed timeline or flowchart without its file. The generator
  template writes neither, so it keeps only the names that have a file.
  None of the 524 official examples has the finding.

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
action 1`, the numbering `print_sheet.py` uses. `--state` adds what the
game holds at the end, read through `assets/runtime-probe.js`: global
variables, instance counts and the instances of the types named.

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
- A dialog over the opened project is a refusal unless its id marks a
  notice. `#deprecatedFeaturesDialog` is one: it lists what the editor
  updated or will drop, the legacy Flat export file structure or the
  Normalized Z axis scale, over a project whose title has turned to its
  name. Over the official examples (2026-10-02, stable r495-2) 56 of 524
  were reported `failed` for that dialog alone; they are now `opened` with
  the notice as a `warning:` line, and no other result changed. The notice
  is closed so that `--preview` can go on. The title alone does not decide:
  `#crashReportDialog`, "Oops! Something went wrong", also comes after the
  title has turned. The runs are in
  `.local/docs/evidence/skill-evals/construct3-agent-plugin/opened-2026-10-02/`.
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
  are in `.local/docs/evidence/skill-evals/construct3-agent-plugin/opened-2026-09-28/`.
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
