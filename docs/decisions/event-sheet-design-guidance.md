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
