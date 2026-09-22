# Event Sheet Design Guidance

Date: 2026-09-07
Schema: Construct 3 r495.2

## Problem

An agent asked to rework a drag-and-drop interaction in a Construct 3 merge
game produced a program transcribed into events: UID instance variables
linking slots and pieces in both directions, global `DragUID` and `DragFrom`,
`Pick all` in most sub-events of the drop trigger, local variables filled by
one block and compared in an `Else` chain, custom actions whose only job was
to keep two variables agreeing. It took three attempts and explicit user
guidance before it reached the native shape: a family as the second pick of
the same object type, collisions disabled during the drag, `Pick overlapping
point`, trigger then narrowing sub-events then `Else`, slot appearance derived
each tick from the overlap.

The user had this repository available and expected it to prevent that.

## Evidence

From the transcript of that session and this repository before the change:

1. The agent never read this repository. Nothing in the game project points
   here. Its `llm-context.md` is the project-format boilerplate Construct
   writes into every project. The only reference material the agent opened
   was the manual clone and the example projects, and only after the user
   pushed back.
2. The repository had no design content to find. `prompts/event-sheet-
   assistant.md` covered output format and name verification. The schemas are
   a catalog of which ACEs exist, not of when to use them. The failure was at
   the modelling level, relations as pointers instead of relations as
   conditions, and a catalog cannot correct that.
3. `AGENTS.md` had one SOP, fact lookup, and said that event sheets "need no
   lookup". No step led to an example event sheet or a manual chapter.
4. Strict name verification would have failed on the correct answer.
   `Is overlapping another object`, `Pick by unique ID`, `Set value`,
   and the hierarchy conditions live in `plugins/_common.json`, which no
   document mentioned. A reader checking `sprite.json` finds none of them.

The correct solution came from `how-events-work.md` and `families.md` in the
manual, the `testOverlap` note in `iworldinstance.md`, and the drop pattern in
the `family-tree`, `alchemist`, and `place-stickers` examples: `On drop`,
`Is overlapping another object`, narrowing conditions, `Else`, with no UID
variable, no `Pick all`, no global.

## Options

1. **Leave the repository as a fact catalog.** Design stays the agent's
   problem. Rejected: the stated product outcome is a correct event sheet,
   and the failure repeats on every interaction of this shape.
2. **Add a design layer in prose plus a design SOP plus discoverability.**
   A guide that states the picking model with manual sources, ten design
   rules, a smell table, a pre-structure checklist, and the slot case worked
   both ways. An `AGENTS.md` SOP that sends an agent to matching example
   event sheets and manual chapters before drafting. A paste-in snippet for
   the game project's `CLAUDE.md`, because no data change helps a reader who
   never opens the repository. Document `_common.json`.
3. **Build a design-question route in the search service.** Index manual
   chapters and example event sheets, classify "how do I" queries, return
   passages. Rejected for now: the service is optional, the default path must
   stay offline and simple, and there is no evidence that a retrieval step
   beats a short guide that is always loaded. Re-evaluate if option 2 fails
   on new cases.

## Decision

Option 2.

- New `prompts/event-sheet-thinking.md`, loaded together with
  `event-sheet-assistant.md`.
- `prompts/event-sheet-assistant.md`: rule 1 is now "design before you
  write"; name verification names `_common.json`; the data table lists
  shared ACEs and example event sheets.
- `AGENTS.md`: section 3 "SOP: design event sheet logic", section 4 "Use from
  another project", `_common.json` in the lookup table, later sections
  renumbered.
- `prompts/game-project-AGENTS.md` (named `game-project-CLAUDE.md` until
  2026-09-18): the block to copy into a game project's `AGENTS.md`, with the
  reason it is needed.
- `README.md`, `README_CN.md`, `docs/guide/data-format.md` updated to match.

Verification for this record: every ACE name in the guide's worked case was
checked against `data/c3-schemas/en-US/`; the drop pattern was read from the
three example event sheets named above; the manual quotes were read from the
sibling manual clone. What was not done: no fresh agent was run against the
original task with the new guide loaded. That is the re-evaluation test.

## Re-evaluate when

- A fresh agent, given the game project with the snippet from `AGENTS.md`
  section 4 and the original task, still produces UID links or `Pick all`
  inside the drop trigger. Then the guide is not enough and option 3 or a
  worked-case library should be tried.
- The guide grows past a few screens or accumulates cases. Split the worked
  cases into their own file and keep the rules short.
- Construct changes the picking model, `Else` semantics, or family picking.
  The manual pages listed in the guide are the source to re-read.

## Update 2026-09-15

Applied the re-evaluation clause "the guide grows past a few screens": the
prompts were trimmed to what an agent gets wrong without them, following the
Claude Code guidance on instruction files (keep them short, one question per
line: would removing it cause a mistake) and the Agent Skills guidance on
progressive disclosure (core instructions always, reference material named
with the situation that calls for it).

- `event-sheet-thinking.md`: 2024 to 1092 words. Model facts that overlap the
  pitfalls file removed, ten rules merged to eight, source URL table replaced
  by one path-to-URL rule, the transcribed-program half of the worked case
  moved to `prompts/references/worked-case-slot-grid.md`.
- `event-sheet-pitfalls.md` added (2026-09-15) and cut from 1406 to 614 words;
  JSON encodings and editor limits moved to
  `prompts/references/hand-editing-project-files.md`.
- `event-sheet-assistant.md`: 529 to 407 words, rule 1 reduced to a pointer,
  one inline output example; `event-sheet-examples.md` deleted, its remaining
  content restated the rules.
- `AGENTS.md` section 3 and `game-project-AGENTS.md` point at the guide
  instead of repeating its steps; the template no longer inlines the guide
  with `@` by default and says what that line costs.

Not done: no agent run compares the trimmed prompts against the previous
version on the original task. That remains the test named above.

## Evaluation 2026-09-15: trimmed prompts against the previous version

Method from agentskills.io "Evaluating skill output quality": four prompts,
each run once with the previous prompt set (commit 1ec1ccd, 4440 words loaded)
and once with the trimmed set (commit abf57ea, 2113 words), in fresh subagent
contexts that received only the file paths, the data paths and the user text.
Assertions were graded by hand with quoted evidence; ACE names were checked by
script against the r495.2 schema.

| Case | What it tests | Assertions | Old | New |
|------|---------------|-----------:|----:|----:|
| A drop on a slot grid (casual wording) | family as second pick, spatial pick, collisions off, trigger/sub-event/Else shape | 8 | 8 | 8 |
| B tower Timer, nearest enemy in range | For each after On timer, pick nearest relative to the tower, range filter | 5 | 5 | 5 |
| C function called after Create (type) and after merge (family) | Copy picked, act on the family with Self, caveat on family pick after Create | 5 | 5 | 5 |
| D "die or walk" every tick | Else is per block, per-instance branch as two events | 3 | 3 | 3 |

| | Old | New |
|---|---:|---:|
| Pass rate | 21/21 | 21/21 |
| Subagent tokens, four runs | 501,651 | 473,185 (−5.7%) |
| Wall time, four runs | 1634 s | 1631 s |

Reading: the trim removed nothing these tasks needed, and the prompts are not
where the tokens go. Each run spent 100k+ tokens on lookups the guide asks
for: manual pages (5 to 10 per run), schema files (`plugins/system.json` alone
is 148 KB) and example event sheets; two runs touched every file under
`c3-examples/` while filtering on `used-addons`. The prompt-size saving
(about 3k tokens) is inside the run-to-run noise (case A: 138k old, 148k new).

Both arms answered case C with *Pick last created* on the family, a documented
tool this record's guide had not mentioned; added to the pitfalls file.

Not measured: a no-prompt baseline, which is what would show whether the
prompts add value at all on these cases; and repeated runs, so no variance
figure. Next levers if cost matters: tell the agent to search a schema file
for the `list-name` instead of reading it whole, and give the example filter
a script instead of a glob over 549 files.

## Update 2026-09-18: sheet organisation, phases, sequences, feel

The guide covered the shape of one interaction and nothing around it: no
rule for where events go once a project has a menu and levels, none for a
phase switch or a pause, none for *Wait*, and nothing on the effects a player
notices first. One existing row was wrong: "Logic shared by several events"
listed a global mode variable next to pasted action blocks, with Functions as
the replacement for both.

Evidence, from the 432 example projects with event sheets
(`Construct-Example-Projects`, r466 to r502) and the manual clone:

- Groups in 237 projects, toggled at runtime in 50, initially inactive in 19
  (tutorial, debug tools, a boss's AI). Pause is *Set time scale* 0 in the 9
  projects that pause, with *Set object time scale* 1 on the UI
  (airborne-explorer); no project pauses by deactivating a group.
- *Wait* in 133 projects, *Wait for previous actions to complete* in 72,
  most often after a Tween in the same block; Timer in 128. The prompts did
  not mention *Wait*.
- Several sheets in 48 projects, includes in 14, always the same split: a
  sheet per screen, levels sharing one, subsystems included (kiwi-story eMain
  includes nine), globals on one sheet. Group names repeat: camera 84,
  setup 82, player 68, controls 59, restart 45.
- Effects: Scroll To *Shake* in 4 projects, time scale 0.1 for a hit stop
  (segmented-boss-fight), a value tween driving the time scale (samuroof,
  eventide), Timeline actions in 17, Flash from `On collision` in 5, a
  parallax-0 UI layer in 151, global layers in 10.

Changes: the shared-logic row split into shared logic, phase, pause,
sequence-in-one-block and trigger rows plus a HUD-layer row; a "Feel" table
and a "Layout of the sheet" section; two smell rows (a global compared at the
top of many events; a sequence finished by another event); a "Wait and time
scale" section in the pitfalls; `AGENTS.md` section 3 names the new parts.
`event-sheet-thinking.md` is 2652 words, above the 2024 the 2026-09-15 trim
started from, so the next trim pass applies to it.

Withdrawn before writing, for lack of a source: an events-versus-scripts
rule (the manual has none; the 29 examples with scripts are mostly -js/-ts
twins of event versions), positional audio (*Play at object* in 3 projects
against *Play* in 214), and a rule for `Wait 0` (39 projects use it, the
manual does not define it).

Not done: no agent run on a multi-layout task or a pause task compares the
guide with and without these sections.

## Update 2026-09-19: the project template routes, it does not repeat

The 2026-09-15 rule (point at the guide instead of repeating its steps) had
been lost twice. `AGENTS.md` section 3 listed the guide's steps again on
2026-09-18 to name the new sections, and section 4 kept a prose "minimum"
block, the shape commit 29a895a had replaced because it did not fire on
"add a jump". The table in `game-project-AGENTS.md` had the right shape but
each cell repeated details that live in one place already: `_common.json`
(section 2), the `--outline` command (`hand-editing-project-files.md`,
`project-tools/README.md`), the manual path rule (`event-sheet-thinking.md`),
the pitfalls write-back (`project-tools/README.md`). Two of those had already
drifted: `_common.json` was added to both tables in one commit, and the
manual path was `Construct3-Manual/` in the guide and
`Construct3-Manual/Construct3-Manual/` in the template; the template was
right.

Changes: every template row names one file, which says what to read next;
the trigger sentence and the four clone paths stay, since only the project
knows them. Section 3 is the scope, the pointer, the redesign trigger and
the write-back rule. Section 4 drops the prose block. The guide's manual
path note now gives the real nesting and the reason to read the clone
rather than construct.net. A row for writing an addon (Addon SDK guide in
the manual clone, samples in `Construct-Addon-SDK`) and a section 2 row for
the SDK type definitions were missing and are added; `README.md` had listed
the SDK clone since the start.

Same day, the install rule. `README.md` and section 4 told the agent to
add the block to any Construct project it entered without one, and the
block's first row leads back to section 4, so an agent carrying the block
from one project would write it into the next: a config file that spreads
itself. The project's instruction file is the user's, and "add a jump" is
not a request to change it. Section 4 now says: offer once, one sentence,
write only on a yes, append and touch nothing else, a no holds for the
session, and a block read in one project is no reason to write it into
another. The generator flow in `project-tools/` is the exception: the user
chose a workflow whose checker reads the `Construct3-RAG:` line from that
file, so the block is part of the output and the handover says so. A no
has nowhere durable to live (the only file that would remember it is the
one the user declined to change), so the question can recur in a later
session; tying it to the first event sheet edit rather than session start
keeps that rare.

The block had four `<path-to>` placeholders and no rule for a block copied
with them unfilled: the agent's first read fails and nothing says what
comes next, so it goes on from memory, the failure the block exists to
stop. The checker already skips a value containing `<` and falls back to
`$CONSTRUCT3_RAG`; the agent had no equivalent. The block now carries one
path, treats the three clones as siblings of it (where every other document
places them) with an extra line only for one kept elsewhere, and says: use
`$CONSTRUCT3_RAG` if set, otherwise ask and offer to fill the line in,
never guess or continue without the data.

Not done: no agent run checks that a one-file pointer per row is read as
reliably as the inlined detail was.

## Update 2026-09-21: installing is the agent's step, and the tools are a skill

The install rule of 2026-09-19 above (offer once, write only on a yes) no
longer holds. `AGENTS.md` section 4 now has the agent install the
`construct3-project` skill in a game project that lacks it and say in one
sentence what was written; `--no-block` and `--dry-run` serve a user who
wants it otherwise. `project-tools/` and its `README.md`, named above, are
`skills/construct3-project/`, and the template's block is
`skills/construct3-project/assets/game-project-block.md`. The reasons are in
`project-tools-skill.md`.

## Update 2026-09-22: the authoring style of the example corpus

The prompts said what the events are (the guide), which runtime facts to
respect (the pitfalls) and where groups and sheets go ("Layout of the
sheet"). Nothing said how a sheet reads once written: what is named how,
where a variable is declared, what a comment says and where, how objects are
foldered, how the branches of a decision are laid out. A sheet from a small
model showed the cost (Doubao snake project, 2026-09-22): twelve state
globals at the top of the sheet (`touchSX`, `foodX`, `tailUID`, `nextX`), a
`ResetGame` function of 28 actions without a comment, and a swipe read as a
tree three sub-events deep with a `SetDir(n)` call at each leaf. Every
name was valid and the checker passed it.

### Evidence

A survey of the 524 projects in `Construct-Example-Projects` at `3c31b236`
("Update example projects for r476", 2026-03-10; `savedWithRelease` 16800
to 47200), read as JSON with the scripts kept in
`.local/docs/evidence/example-style-survey/` (`survey_style.py`,
`survey_cohort.py`, `render_sheet.py`, their outputs and `cohort-output.txt`).
Two cohorts, told apart by the credits comment at the top of the sheets: 221
projects by Viridino Studios and its successor Forsteri Studios (the demo
games and game templates, median 35 to 57 events) and 303 others, Scirra's feature examples and a few external games (median
2 events). The style below is the studio cohort's; where
the periods differ, r400 and later is quoted.

| Question | Count |
|----------|-------|
| Comments per event, median per project | 1.0 (studio), 0.78 (other); 38 projects have none, all under 10 events |
| Event preceded by a comment, by depth (studio) | 93% at top level, 89%, 74%, 65% one, two, three levels down |
| Comment shape | 93% end with a period, 91% are one sentence, median 48 characters; `#` prefix 31, coloured 51 of 12,958 |
| Comment actions inside action lists | 5,117 in 252 projects; of 837 studio blocks with 8+ actions, 799 have one; longest uncommented run median 3, p90 6 |
| Group description field used | 55 of 1,855 studio groups |
| Groups | 2,160 in 239 projects; every top-level event in a group in 209 of them; studio: 29 loose top-level events against 4,164 in groups; depth 0/1/2/3: 1,609/475/63/13 |
| Group titles | Title Case with spaces 369, PascalCase 39 in r400+ (PascalCase 336 to 0 before r300) |
| Order inside a group | variables first in 202 of 240 groups with variables; functions and custom actions before events in 246 of 400 |
| Variable placement (studio) | 1,288 global, 602 group-local (303 const, 168 plain, 131 static), 316 block-local, 220 function-local; 17 of the 27 projects with 80+ events have more locals than globals |
| Globals by use (r400+, 447) | constants read from one group 104, from 2+ groups 45; state read from one group 75, from 2+ groups 210; unused 13 |
| Variable comments | r400+: 854 of 922; before r300: 0 of 717 (a comment event above the variable instead) |
| Constant names | UPPER 397, UPPER_SNAKE 355 of 802 (studio); prefixes CHAIN_, CAR_, PLAYER_, BGM_, CAM_, SFX_, MINO_ |
| Other variable names (r400+) | camelCase 409, PascalCase 47 |
| Function names (r400+) | camelCase 362, PascalCase 29; description filled 534 of 956, equal to the comment above in 495 |
| Custom actions | 179 in 26 projects, 172 on a type, 7 on a family; names with spaces 93, PascalCase 58; described 162 of 163 (studio) |
| Boolean instance variables | plain adjective or participle 120+47+22, `is`/`has`/`can` prefix 13 |
| Object type names (studio) | PascalCase 5,371 of 5,733; `Text*` 289 of 440 text objects, `Arr*` 40 of 66 arrays, `Dict*` 19 of 20; behaviors renamed 328 of 2,549 |
| Families | 153; PascalCase 147; plural 98 |
| Tags | tween PascalCase 2,163 of 2,240; timer PascalCase 471 of 525 |
| `ObjectRepository` layout | 191 of 221 studio projects, no event sheet in all 191, first in the list 109, second 79 |
| Object folders | 54 projects; 37 of 72 with 30+ types, 15 of 20 with 60+; names System 23, Player 22, Global 18, UI 17, World 16; depth 1/2/3/4: 278/133/56/14 |
| Layers | `Background` 165, `World` 125, `UI` 86, `HUD` 70, `Fader` 62 (studio); parallax 0,0 on 390 layers |
| Manager objects | `GameManager` Sprite with Timer or Tween 68, `Camera` Sprite with Scroll To 32; `Fader` Tiled Background with Tween 56 |
| Conditions (studio) | evaluate-expression 1,412, for-each 564, compare-instance-variable 426, is-boolean-instance-variable-set 402, pick-by-comparison 392, is-overlapping 362, pick-by-evaluate 355, pick-children 339, on-collision 329, pick-by-unique-id 173 (104 inside functions), pick-parent 65, pick-all 31, pick-nearest 22 |
| Trigger blocks | 3,880 of 14,214; 999 with filter conditions in the block, 958 with sub-events |
| Else | 1,779 (studio 1,586); with conditions 792 (studio 753); preceded by a comment 66% (studio); chains of 2+ 152 |
| Sub-event depth below the event (studio) | 0: 48%, 1: 32%, 2: 13%, 3: 4.7%, 4+: 2.4% |
| Phase gates (a block with conditions, no actions, sub-events) | 1,307 (studio); groups inactive at start 28 |
| UI text | `replace(Self.Text, "###", ...)` in 21 projects; literal strings sentence case 139, Title Case 39, all caps 28; labels end `: ` |

### Options

1. Extend `event-sheet-thinking.md`. Rejected: it is 2,690 words, above the
   trim threshold this record set on 2026-09-15, and its subject is what the
   events are, not how the sheet reads.
2. A separate prompt, `prompts/event-sheet-style.md`, routed from the guide
   (header, "Layout of the sheet", step 3), the assistant prompt, `AGENTS.md`
   sections 3 and 7, both READMEs and the generator reference of the skill.
   Chosen.
3. Checker warnings for the three habits (an action list of 8+ without a
   comment action; a state global referenced from one group only; a branch
   tree 3+ sub-events deep whose leaves call one function). Not built: the
   checker reports what the editor refuses, and a warning is a product
   choice for the skill with its own sweep over the examples
   (`skills/AGENTS.md`). The thresholds above are what such warnings would
   use; on the studio corpus the first would fire on 38 of 837 blocks.

### Decision

Option 2. `prompts/event-sheet-style.md` (1,949 words): project layout
(`ObjectRepository`, folders, layers, manager objects, sheets), the sheet
top to bottom, groups as modules (order, which variables are global, the
block-local temporary, the gate event, decoupled input), comments (one per
event, comment actions every three to five actions, descriptions equal to the
comment), names, the events' shape (filters in the trigger, flat branches or
one expression, else-if chains, hierarchy and ID joins, UID as function
parameter), UI text, and a table of the three habits with their replacement.
The pitfalls file lost a bullet that was committed twice (`Self` in a System
condition).

Not done: no agent run compares a sheet written with and without the style
file, on the snake project or another; that is the test. The skill's
`generating-a-project.md` gained one pointer bullet without an eval
iteration (`skills/AGENTS.md` counts a reference change as one). The
game-project block was not changed; it reaches the style file through the
guide.

### Re-evaluate when

- A small model given the style file still writes the three habits. Then
  option 3, the checker warnings, with the thresholds measured here.
- Scirra's own conventions diverge from the studios' in a new example set.
  The survey scripts rerun on the clone; the cohort split is by the credits
  comment.

## Update 2026-09-22: the two skill-creation guides, heading by heading; the style checks

The user asked that the event sheet prompts be held against
<https://agentskills.io/skill-creation/best-practices> and
<https://agentskills.io/skill-creation/optimizing-descriptions> (read in
full the same day), with one concern: 13 000 tokens of prose across
`event-sheet-thinking.md` (4 500), `event-sheet-pitfalls.md` (4 850),
`event-sheet-style.md` (3 200 before this update) and
`event-sheet-assistant.md` (1 000) is a load a small model will not carry,
and the three habits of the morning's update needed a mechanical form.

### Evidence

- What small models read. The 28 Haiku 4.5 runs of iterations 1 to 10 of
  the skill (`.local/docs/evidence/skill-evals/construct3-project/`,
  `trace.txt` of each) opened `SKILL.md` in 25 and a design prompt in 4,
  all four on `add-countdown`, the one case that asks for a mechanic; none
  on `fix-load-errors`. The checker ran in every run that edited a sheet,
  because `edit_sheet.py` runs it. What reaches a small model is the tool's
  output, not the prose; the prose reaches the model that knows it needs
  it.
- Which habits have a mechanical form. Five heuristics were run over the
  524 examples and the game projects before any checker code was written
  (`.local/docs/evidence/example-style-survey/`, `style_lint_dry.py`, and
  the two variants below):

  | Heuristic | Official examples | Doubao snake | Kept |
  |-----------|-------------------|--------------|------|
  | 8+ actions in a row without a comment action | 113 in 50 projects; studio median run 3, p90 6 | 4 | yes |
  | top-level event with no comment above it | 1184 in 278 projects; 93% of studio top-level events commented, demonoire 81, poplab 27, kiwi-story 25 | 21 | yes |
  | sub-events 3+ deep, every leaf calling one function | 3 in 3 projects | 1 (the swipe) | yes |
  | state global read from one group only, in 2 or fewer events | 284 in 140 projects, template-snake 7 | 2 | no: cannot be told from a legitimate global |
  | state global referenced inside one top-level event only | 226 in 116 projects | 2 (`foodX`, `foodY`) | no: same |
  | top-level event outside every group where groups exist | 40 in 12 projects | 0 | no: low value |

  The pile of globals, the habit the user named first, has no mechanical
  form that passes the official corpus; it stays prose, with the
  replacement shapes in the style file's first table.
- The trigger loop of the descriptions guide cannot run: `claude -p`
  answers `Failed to authenticate: OAuth session expired and could not be
  refreshed`, as on 2026-09-21 and 2026-09-22 morning.
- Comment frames. The 10 502 comments of the studio cohort (clone
  `3c31b236`, `.local/docs/evidence/style-checks/measure_comment_frames.py`,
  rerun 2026-09-22 with the same counts): median 8 words, ninetieth
  percentile 18; 257 (2.4%) have a second sentence. By first word:
  imperative 4 634 (44%), the case as a statement 3 162 (30%, `However,
  if` 176 among them), `If`, `When` or `Once` 1 519 (14%), what a variable
  holds 472 (4.5%), an adverb first 363 (3.5%), `Otherwise` 124 (1.2%),
  other 228. A reason is a clause of the same sentence: `so the` 134, `to
  prevent` 56, `since` 48, `to make sure` 47, `to avoid` 23, `because` 12.
  These are the rows of the style file's comment table.

### Best practices, heading by heading

| Heading | Finding | Action |
|---------|---------|--------|
| Start from real expertise | The style file was synthesised from the corpus, the habits from the small-model projects on disk | none |
| Refine with real execution | The style file was not run by any agent; the checker warnings were run over 524 examples and 9 game projects before being kept | the measurements above; a Haiku iteration below |
| Add what the agent lacks, omit what it knows | The first style file carried 40 survey counts a reader cannot act on | counts moved to this record; the file went from 1 950 to 1 020 words |
| Design coherent units | Design, runtime facts, output format, style: four files, each one question | none |
| Aim for moderate detail | The style file described conventions the examples show; a small model pattern-matches a template better than prose | a 25-line sheet in `print_sheet.py` wording replaces three sections |
| Structure large skills with progressive disclosure | The pointers said what the file is, not when to read it ("is how the official examples..."); the guide asks for the trigger | every pointer to the style file is now "before events go into a project or a generator, read..."; `SKILL.md` names it at the point where the check loop ends |
| Match specificity to fragility | The three habits were prose | the shapes are prescribed by the checker and the generator helpers; naming and folders stay guidance |
| Provide defaults, not menus | The generator template had `block()` and `group()` only; a group's layout was the agent's to invent | `module()`, `event()`, `procedure()`, `steps()`, `cases()` make the examples' shape the default |
| Favor procedures over declarations | The style file declared conventions | "one function per group, run, read, next" in the generator reference; the habits table says what to do instead |
| Gotchas | The guide keeps gotchas where the agent reads them before the situation; a small model does not open a style file to check itself | the three habits are checker warnings, which every editing run prints; `SKILL.md` Gotchas unchanged, by the 2026-09-22 rule that Gotchas hold what the tools do not say |
| Templates for output format | None for a sheet | the sheet in "The shape"; the stand-in generator rewritten with the helpers |
| Checklists for multi-step workflows | Generating a whole sheet in one run is the failure mode the user described (long blocks, no structure) | the generator reference: a `module_*()` per group, written and checked one at a time |
| Validation loops | `edit_sheet.py` already checks what a plan writes | style warnings ride in that loop; only the new events are held to them |
| Plan-validate-execute | The plan is the JSON file; the checker validates it before it lands | none |
| Bundling reusable scripts | The survey scripts serve the maintainer, not the agent | kept in `.local/`, not the skill |

### Optimizing descriptions, heading by heading

| Heading | Finding | Action |
|---------|---------|--------|
| How skill triggering works | "Agents only consult skills for tasks beyond what they can handle alone": a small model believes it can write events alone, so the prose is skipped and the tool is not | the change of lever above |
| Writing effective descriptions | `SKILL.md`'s description, 683 characters, imperative second sentence; the prompt files have no description, their "description" is the block's table row and the pointer sentences | pointers rewritten as when-clauses; the description unchanged, by the rule that it changes on train-set failures only |
| Designing trigger eval queries | 12 train, 8 validation, near misses, two languages | none |
| Testing, running multiple times, the loop, applying the result | Not runnable: the client is signed out | not run; the queries stand |

### Changes

- `check_project.py --style`: the three warnings, `STYLE_RUN = 8`,
  `STYLE_TREE = 3`, each naming the event and the JSON to write. Off by
  default: a user's project is not held to the agent's style.
- `edit_sheet.py`: the checker runs with style on, and the warnings new
  after the plan are printed, compared without their event numbers, so an
  insert above the user's uncommented events does not re-list them.
- `assets/build_project.py`: `module()`, `event()`, `procedure()`,
  `steps()`, `cases()`, `flat()`; the stand-in sheet as `module_setup()`,
  `module_input()`, `scoring()`, `module_restart()`, constants under
  `Settings.`; the final check passes `--style`.
- `prompts/event-sheet-style.md` rewritten: the habits table first, then
  the sheet template, then comments, names, project and UI text.
- Pointers in `event-sheet-thinking.md`, `event-sheet-assistant.md`,
  `SKILL.md`; `generating-a-project.md` "Writing the generator";
  `checker-rules.md` "Style, with `--style`" and its duplicated `Self` row
  removed; `skills/AGENTS.md` rule for style findings.
- Tests: the stand-in passes `--style` clean; each warning on a broken
  stand-in; a plan reports the style of what it adds and not of the user's
  events; `make_fixtures.seed_load_errors` and four print expectations
  follow the template's new comments.
- `print_sheet.py`, found by those tests: a part cut at `--limit` could
  stop before the event whose comments and variables it had just printed,
  and the continuation it named started at the same event, forever. The
  rows of one event number now print together and a part stops only before
  a later number. With the old template no test reached the case; the
  stand-in's new comment rows did.

Old against new over 2 050 runs, the final scripts against the commit
before (`.local/docs/evidence/style-checks/sweep-old.json`,
`sweep-new4.json`, `classify_sweep.py`): no `check`, `edit` or `lookup`
run differs; 215 `print` and `outline` runs differ, 122 by the script path
in their last line only, which names the checkout that printed (192
characters shorter, confirmed by a diff of template-snake), 93 by that and
by the part fix: runs cut at `--limit`, whose part now ends before a later
event number and prints 19 to 554 characters less, exit code unchanged. No
run prints more than 10 000 characters. The last change to `edit_sheet.py`,
the refusal, changed no run: `sweep-new3.json` and `sweep-new4.json` are
identical. `check_project.py --style` over the examples: the table above.

### Iteration 11: add-countdown, Haiku 4.5, two runs per arm

Fixtures outside the clone (`make_fixtures.py`), `with_skill` the working
tree with the style warnings, `old_skill` a worktree of the commit before
(42ec5d5), prompts as `skills/AGENTS.md`, Evals, gives them. Runs in
`.local/docs/evidence/skill-evals/construct3-project/iteration-11/`;
`benchmark.json` and the traces were read.

| Arm | Assertions | Tokens | Seconds | Tool calls, lost | Style warnings in the final sheet |
|-----|-----------:|-------:|--------:|-----------------:|----------------------------------:|
| old_skill | 6/7 | 56 198 | 76.6 | 18, 3 | 2 (the two new Timer events have no comment) |
| old_skill_2 | 7/7 | 59 438 | 95.6 | 17, 3 | 2 (same) |
| with_skill | 7/7 | 70 574 | 160.8 | 34, 4 | 1 (wrote `// Restart when time runs out.` and `// Countdown the timer each second.`, the second above the group instead of the event) |
| with_skill_2 | 7/7 | 62 575 | 122.9 | 25, 7 | 3 (three new events, none commented) |

Both with-skill transcripts hold the warnings (`warning: sheet Game event`
four and three times); neither old-skill transcript does. One run acted on
them, one did not. The failed assertion of `old_skill` is the known one
(the `Collect` text left without the time). Two runs per arm: counts, not a
spread; the with-skill runs cost more calls, and this iteration cannot say
whether the warnings or chance did that.

The re-evaluation clause below was met on the first try, so the step it
names was taken the same day: `edit_sheet.py` refuses a plan whose created
events, those with a sid the sheet did not hold before, raise the two
findings whose fix is one comment (no comment above a top-level event;
eight actions in a row without a comment action), printed like problems
with the JSON to write and `nothing was written`; an event the plan moved
or extended is the user's, and a finding on it prints as a warning; the
tree finding stays a warning everywhere, because flattening a decision is a
design change the plan's author must make. `SKILL.md` says so and its plan example carries
the comment; `check_project.py --style` still reports all three. Not
measured: whether a Haiku run given the refusal writes the comment or gives
up. That is the next iteration.

### Iteration 12: add-countdown against the refusal, Haiku 4.5, three runs

Same fixture, prompt and skill path as iteration 11, the working tree at
`11ad3a9`, `with_skill` three times; runs and traces in
`.local/docs/evidence/skill-evals/construct3-project/iteration-12/`.

| Run | Assertions | Tokens | Seconds | Tool calls, lost | Plans refused | Style findings in the final sheet |
|-----|-----------:|-------:|--------:|-----------------:|--------------:|----------------------------------:|
| with_skill | 7/7 | 55 807 | 116.9 | 19, 2 | 1 (`trigger-once` for `trigger-once-while-true`) | 0 |
| with_skill_2 | 7/7 | 61 808 | 164.0 | 20, 2 | 1 (`set` on `actions`) | 0 |
| with_skill_3 | 7/7 | 74 391 | 238.0 | 26, 3 | 3 (`set` on `actions`; an operation with `event`, `into` and `events`; `compare-eventvar` on a Sprite) | 0 |

The style refusal never fired: every plan of the three runs carried a
comment above each created event from its first draft, so the question
the iteration asked, write the comment or give up, has no instance. What
changed against iteration 11, where the two with-skill runs left one and
three findings: `SKILL.md` now says the plan is refused without the
comment and its plan example carries one. Which of the two did it cannot
be told apart here; the observable result is three sheets that pass
`--style`, against none of two. Every refused plan was a guessed operation
shape or ACE id, answered with the form to use, and the run corrected it
on the next try; none abandoned the task.

Not a style matter, seen in the sheets: the third run subtracts from the
countdown under `Every 1 seconds` without setting the text, so the time
shown only moves when the score does (assertion 5 holds, since the action
that sets the text writes both); the second run reads "1.5x" as `Set
scale` to 1.5 on a coin the sheet sizes nowhere. An assertion for "the
displayed time changes every second" would catch the first.

### Not done

- A run in which the refusal fires; three runs did not produce one.
- The trigger evaluation of the description, for lack of a signed-in client.
- Warnings for the pile of globals: no heuristic passes the corpus.
- The pitfalls file (4 850 tokens) was not split into a core and a
  reference; no run has shown a wrong answer that a section-level
  "when to read" would have fixed.

### Re-evaluate when

- A Haiku run given the refusal abandons the task or loops on it: then the
  refusal costs more than the habit, and the two findings go back to
  warnings, with the run as evidence.
- A capable model's plans are refused often: count the refusals in the
  traces of the next iterations; a comment is one row, so more than one
  refusal per run means the message does not say what to write.
- The official corpus gains projects whose style differs: rerun
  `measure_style.py`; the thresholds are constants at the top of
  `check_project.py`.

## Update 2026-09-22: the raft game, two more style checks, panels and animation

### Evidence

The user read the 204-event sheet Doubao wrote for a raft survival game
(RaftSurvivor, generated by its own `tools/` scripts with the skill
installed and `check_project.py --style` passing) and named three things:
a panel hidden by *Set visibility* on each of its six objects in every event
that opens or closes it (events 2, 38 to 55, 112, 113, 172, 193); the state
machine of the `Appearance` group, ten events of one shape; and case
sub-events with no comment on any of them (events 22 and 23, 26 to 28, 116 to
121). The checker had nothing to say: every top-level event carries a
comment, no run reaches eight actions, no tree goes three deep.

Measured over the official examples (checker run over the 524 projects,
`.local/docs/evidence/style-checks/count_style.py`; cohort by the credits
comment, 219 studio projects):

| Shape | Studio games | All 524 | RaftSurvivor |
|-------|-------------:|--------:|-------------:|
| An event with two or more case sub-events and no comment above any of them | 253 of 1605 such events (16%), in 83 projects; 75% of the 4382 cases have their own comment | 435 in 116 projects | 24 of 24 |
| Five or more sibling events of one shape (conditions and actions by ACE, values ignored) | 32 in 20 projects: input ladders (a key per action: eventide, plumber-puzzle, input-sequence) and else-if chains (planet-generator, graphing-calculator-js) | 47 in 31 projects | 6, of 5 to 9 events |

Panels in the studio games: `set-visible` reaches four or more actions in
one block 4 times in the whole corpus; a menu is its own layer, opened with
*Set layer visible* or *Set layer opacity* from a value tween
(airborne-explorer `MenuUI`, `ShopUI`; eventide `PauseUI`, `GameOverUI`,
`NewSkillUI`). The `anim` instance variable the raft game compares before
every *Set animation* guards against nothing: the manual's *Set animation*
note says the action does nothing when that animation is already playing
(plugin-reference/sprite.md).

### Options

1. Prose only: the style file already says "branches as sub-events, one
   comment each" and the thinking prompt's smell table has the ladder of
   `Compare` blocks. Rejected: the raft game was written with both installed
   and shows 24 and 6; what reaches a generator is the checker's line
   ("What small models read", above).
2. Two checker warnings with thresholds from the table, the uncommented
   cases refused by `edit_sheet.py` like the missing comment above an event
   (the fix is one comment), the ladder a warning (an input ladder is a
   legitimate shape). Chosen.
3. A per-case warning: 25% of the studio cases would raise it. Rejected for
   the per-event form, which 16% raise and which names the count.

### Decision

Option 2. `check_project.py --style` reports five kinds: `run`, `comment`,
`cases`, `tree`, `ladder`; `edit_sheet.py` refuses `comment`, `run` and
`cases` on events a plan creates. The style file's habit table has the two
new rows; the thinking prompt's Native table has a row for a panel, menu or
popup (its own layer, *Set layer visible* or *Set layer opacity* from a value
tween), and principle 2 names the animation name among the state the engine
owns; the pitfalls file has an *Animation* section with the *Set animation*
note. The sweep of the scripts over the 524 examples and the raft game shows
0 of 2037 runs differ without `--style`.

### Re-evaluate when

- A generator or a plan is refused for cases that are one event's `Else`
  pair and a comment reads as noise there: count them in the next
  iteration's traces; the refusal can keep the threshold at three cases.
- The ladder fires on input maps in a project the agent wrote and the agent
  rewrites them into a table: the message then needs the key-per-action
  exception spelled out.
