# CLAUDE.md for a Construct 3 project

Copy the block below into `CLAUDE.md` (or `AGENTS.md`) at the root of the
game project and replace `<path-to>` with the directory that holds this
repository. Nothing in a Construct project points here on its own: the
`llm-context.md` that Construct writes into every project describes the file
format, not this data. Without these lines an agent working in the game
folder answers from memory, and a drag-and-drop interaction comes back as
UID links, `Pick all`, and global variables.

The `@` line is Claude Code syntax. It inlines the design guide into the
project's context so the picking rules are present before the first event is
proposed. Other tools ignore it.

```markdown
# Construct 3

Construct 3 reference data and event sheet rules live in
<path-to>/Construct3-RAG. Read its AGENTS.md first.

Before proposing event sheet logic, load prompts/event-sheet-thinking.md and
prompts/event-sheet-assistant.md from that repository and follow them:
relations are conditions, families, containers, or hierarchy, not UID
variables; the trigger's picked instance is used directly; the draft is
checked against the smell table before it is shown.

Verify every plugin, behavior, and ACE name against
<path-to>/Construct3-RAG/data/c3-schemas/ before writing it down. Shared
world-object ACEs are in plugins/_common.json.

@<path-to>/Construct3-RAG/prompts/event-sheet-thinking.md
```
