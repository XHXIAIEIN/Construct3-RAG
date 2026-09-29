# Design and Style Prompts Keep What Every Task Reads

Date: 2026-09-30

## Problem

`prompts/event-sheet-thinking.md` (20 492 bytes) and
`prompts/event-sheet-style.md` (15 019 bytes) are read whole for every event
design, and style.md again before events go into a project. About a third
of the two served one kind of task: how a new project is laid out and how it
looks (style.md *Project*, thinking.md *Layout of the sheet*), the examples'
feel recipes (thinking.md *Feel*), and the slot-grid worked case. A task that
adds one interaction to an existing sheet paid for all of it.

## Evidence

The pitfalls split (`pitfalls-index-and-topics.md`) showed that an agent
opens a split-out file only when its read-when line names a narrow feature
the task visibly has. So a section moves only when the task that needs it is
visible from the start: generating a project, a stated effect, a drag onto
slots. Native first stays inline: which row applies shows only while
drafting.

Four tasks, two Haiku runs per task and arm, each run confined to its arm's
`prompts/` (a new game, one interaction added to an existing sheet, a design
that rests on Native first, a drag onto a slot grid). In the new arm, every
run that needed a moved file opened it from its read-when line, and the
answers scored the same as the old arm's against the guidance; the mistakes
that recurred (walking on *On key pressed*, a graphics sprite copied every
tick, a counter mirroring an instance count) came from rules that stayed
inline, in both arms. Tokens were 1 to 6 % lower in every cell, within the
spread of two runs. Runs and grading:
`.local/docs/evidence/prompt-trim-2026-09-29/`.

## Options

1. Keep both files whole. Every design task reads 35 KB.
2. Move each section whose reader is a visible kind of task to
   `prompts/references/`, leaving a read-when line that names the task.
3. Also move Native first, the largest section. Its rows are needed while
   drafting, when the agent does not yet know it needs them; the pitfalls
   split showed that a line a task does not visibly trigger is not followed.

## Decision

Option 2. thinking.md is 16 499 bytes, style.md 9 680.

| Moved | To | Read when |
|-------|----|-----------|
| style.md *Project*, thinking.md *Layout of the sheet* | `prompts/references/new-project.md` | generating a project, or adding a layout, layer, event sheet, group or object type to one; how the game looks |
| thinking.md *Feel* | `prompts/references/feel.md` | generating a game, or events for screen shake, hit stop, squash, hit flash, a choreographed sequence, a following camera or a fade between layouts |
| thinking.md's native slot-grid case | `prompts/references/worked-case-slot-grid.md`, before the transcribed version | dragging pieces onto slots or a grid, or a draft that hit the smell table |

The sections moved word for word. Each source keeps its heading with the
read-when line, so step 3 of "Before proposing a structure" and the readers
in the skill and the root `AGENTS.md` still find them.

## Re-evaluate when

- An agent generating a project, or adding a layer or object type, writes
  it without opening `new-project.md`: reword the read-when line, then bring
  the part it missed back inline.
- A task names one of the effects and the run skips `feel.md`: the same.
- thinking.md grows back to about 20 KB, or style.md to 15 KB: look for the
  next section whose reader is a visible kind of task.
