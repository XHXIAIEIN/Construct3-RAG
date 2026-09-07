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
- `prompts/game-project-CLAUDE.md`: the block to copy into a game project's
  `CLAUDE.md`, with the reason it is needed.
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
