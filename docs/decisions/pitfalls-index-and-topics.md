# The Pitfalls Are an Index with Topic Files

Date: 2026-09-29

## Problem

`prompts/event-sheet-pitfalls.md` had grown to 599 lines, about 39 KB,
72 entries in 13 groups. The README loads it as part of the system prompt
and `event-sheet-thinking.md` sends the agent to it before writing events,
so every task paid for all 72 entries while one used two or three groups.

A table of links is not enough: the file holds facts that intuition gets
wrong, so the agent does not know which one it needs. It has to see that
each pitfall exists without opening anything.

Once split, the index kept growing, by about 30 entries between 2026-09-20
and 2026-09-29. The instructions sent every lesson a preview taught to the
pitfalls, so the index also collected how a project file is written, what
the editor's preview starts from, how a script drives a preview, and how art
should be painted. None of those changes the events an agent writes, and
each one costs every task a line.

## Options

1. One file. Every task reads 39 KB, and the file grows with every preview
   that teaches something.
2. An index of links to topic files. Small, but the agent has to guess
   which topic hides the fact it does not know it is missing.
3. An index that states every pitfall's conclusion in one line, grouped
   under a line that says when to open the group's topic file, which holds
   the entries with their cases and sources.

## Evidence

Three tasks, each hinging on a pitfall outside the inline groups (a global
kept across *Restart layout*, a 44 pt line in a 46 px Text box, *Wait 0*
after *Create object*), one Haiku run per task on the single file and one on
the index. Every run on the index opened the topic file its task needed,
from the when-to-read line, and every run in both arms avoided the pitfall.
The runs on the index read about 7 % fewer tokens.

Picking and Triggers and Else were then tried as topic files too, on three
tasks hinging on them (a family's container, a tween finished inside a
function, *Else* per instance). No run opened either topic file: "when the
events pick" and "when they use a trigger" hold for every sheet, and the
agent took the conclusion line as the whole fact. On the tween task the line
kept the prohibition and lost the fix the full entry gives, and the run built
a sequence that destroys the gem before its tween ends. Tokens did not move.
Runs and grading: `.local/docs/evidence/pitfalls-split-2026-09-28/` and
`pitfalls-split-2026-09-29/`.

By 2026-09-30 the index was 19.5 KB again, 8 KB of it the two inline groups,
whose entries carry long sources and observations. The two groups became
topic files a second time, with a change that answers the failure above:
each conclusion line keeps the fix and not only the prohibition.

## Decision

Option 3. `prompts/event-sheet-pitfalls.md` keeps its path and its opening
rules. Each group is a `###` heading, a when-to-read line linking
`prompts/pitfalls/<topic>.md`, and one conclusion line per entry in the
topic file's order, Picking and Triggers and Else included. A conclusion
keeps the fix: "a tween's *On finished* is a top-level event of its own
that calls the next function", not only "no trigger inside a function". The
index is about 14.5 KB.

A pitfall is a runtime behaviour of events that changes which events an
agent writes: without the line, the agent would write them wrong. Other
lessons have their own homes, named in the index's "Adding an entry" and in
every place that routes a lesson (the root `AGENTS.md`, the
`construct3-agent-plugin` skill's `SKILL.md`, `generating-a-project.md` and
`checker-rules.md`):

| Lesson | Home |
|--------|------|
| How a project file is written | `prompts/references/hand-editing-project-files.md`, or a checker rule when a script can test it |
| What the editor, the preview or a script driving them does | `skills/construct3-agent-plugin/references/`, `editor-and-preview.md` for the preview |
| Which cases to play to check a change, and how to reach and read them | `skills/construct3-agent-plugin/references/verifying-a-change.md` |
| How the game looks, its art and colours | `prompts/references/new-project.md`, or the look documents in the root `AGENTS.md` |

By that test, where the preview starts and how a script drags in it went to
`editor-and-preview.md`, and the Local Storage key that a rewritten
`project.c3proj` must keep went to `hand-editing-project-files.md`; the
group they left is *Storage and export*. A sprite drawn facing right
stays: given art that faces up, the agent writes every *Set angle* wrong
without it. An entry the checker also enforces stays too, since the prompts
serve as a system prompt where no checker runs.

A new entry goes into its group's topic file with its source, and its
conclusion into the index. `tests/test_prompts.py` fails when a topic file
is not linked, when a group's conclusion lines and the topic file's entries
differ in number, or when an entry has no source.

## Re-evaluate when

- The index passes about 20 KB: first move out what fails the scope test,
  then shorten conclusion lines, or merge groups that are always read
  together.
- An agent writes a sheet that breaks a Picking or Triggers and Else entry
  whose fix its conclusion line states: the two groups are read by
  nearly every sheet and are not opened, so bring the entry back in full
  and cut elsewhere. Nine runs on the conclusion lines that keep the fix
  (three tasks, three runs each, Haiku 4.5, 2026-09-30) broke none: eight
  opened a topic file, all three tween runs wrote the tween's *On finished*
  as its own top-level event, and all three family runs picked through the
  type (`.local/docs/evidence/pitfalls-fix-lines-2026-09-30/`). The line
  does not replace the file: with `pitfalls/triggers-and-else.md` deleted,
  three tween runs gave one top-level *On finished*, one *Wait* route with
  format errors and one trigger nested in the function.
- An eval shows an agent writing a pitfall's topic without opening its file:
  reword that group's when-to-read line first.
- An agent repeats a mistake that a moved lesson describes, because it did
  not read the lesson's home: bring the lesson back, or point to it from
  where that agent does read.
