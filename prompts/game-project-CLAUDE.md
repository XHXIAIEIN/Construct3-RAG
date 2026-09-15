# CLAUDE.md for a Construct 3 project

Nothing in a Construct project points here: the `llm-context.md` Construct
writes into every project describes the file format, not this data. Without
the lines below an agent in the game folder answers from memory, and a
drag-and-drop interaction comes back as UID links, `Pick all` and globals.

Copy the block into the project's `CLAUDE.md` (or `AGENTS.md`) and replace
`<path-to>` with the directory holding this repository, or with a symlink
inside the project that points to it.

```markdown
# Construct 3

Construct 3 reference data and event sheet rules: <path-to>/Construct3-RAG.
Read its AGENTS.md first.

Before proposing event sheet logic, read prompts/event-sheet-thinking.md,
prompts/event-sheet-assistant.md and prompts/event-sheet-pitfalls.md there
and follow them. Verify every plugin, behavior and ACE name against
data/c3-schemas/ before writing it down; shared world-object ACEs are in
plugins/_common.json.

Write new runtime facts learned in this project back into
prompts/event-sheet-pitfalls.md, with a source.
```

The block loads nothing at startup; the agent reads the three files when it
starts event sheet work. If it keeps skipping them, add one line at the end:
`@<path-to>/Construct3-RAG/prompts/event-sheet-thinking.md`. Claude Code
inlines that file into every session of the project, which costs its full
length each time; other tools ignore the line.
