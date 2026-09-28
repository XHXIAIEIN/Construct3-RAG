# The Pitfalls Are an Index with Topic Files

Date: 2026-09-28

## Problem

`prompts/event-sheet-pitfalls.md` had grown to 599 lines, about 39 KB,
72 entries in 13 groups. The README loads it as part of the system prompt
and `event-sheet-thinking.md` sends the agent to it before writing events,
so every task paid for all 72 entries while one used two or three groups.

A table of links is not enough: the file holds facts that intuition gets
wrong, so the agent does not know which one it needs. It has to see that
each pitfall exists without opening anything.

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
The runs on the index read about 7 % fewer tokens. Runs and grading:
`.local/docs/evidence/pitfalls-split-2026-09-28/`.

## Decision

Option 3. `prompts/event-sheet-pitfalls.md` keeps its path, its opening
rules, and Picking and Triggers and Else in full, since nearly every sheet
needs them. Each other group is a `###` heading, a when-to-read line linking
`prompts/pitfalls/<topic>.md`, and one conclusion line per entry in the
topic file's order. The index is about 15.5 KB.

A new entry goes into its group's topic file with its source, and its
conclusion into the index. `tests/test_prompts.py` fails when a topic file
is not linked, when a group's conclusion lines and the topic file's entries
differ in number, or when an entry has no source.

## Re-evaluate when

- The index passes about 15 KB again: move Picking and Triggers and Else to
  topic files and keep their conclusion lines.
- An eval shows an agent writing a pitfall's topic without opening its file:
  reword that group's when-to-read line first.
