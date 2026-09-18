# AGENTS.md for a Construct 3 project

Nothing in a Construct project points here. The `llm-context.md` Construct
writes into every project describes the folder layout, not this data, so an
agent in the game folder answers from memory: a drag-and-drop interaction
comes back as UID links, `Pick all` and globals.

Copy the block into the project's `AGENTS.md` and fill in the paths at the
top: this repository and the `Construct3-Manual`, `Construct-Example-Projects`
and `Construct-Addon-SDK` clones, or symlinks inside the project that point
to them. Nothing else in the block needs editing. Claude Code reads
`CLAUDE.md`, not `AGENTS.md`: give the project a `CLAUDE.md` holding the one
line `@AGENTS.md`, as this repository does, or put the block in both.

```markdown
# Construct 3

- Construct3-RAG: <path-to>/Construct3-RAG
- Construct3-Manual: <path-to>/Construct3-Manual
- Construct-Example-Projects: <path-to>/Construct-Example-Projects
- Construct-Addon-SDK: <path-to>/Construct-Addon-SDK

Anything that changes what the game does is event sheet work: a new
mechanic, a fix, a behavior, a variable, a timer, an animation, an edit to
eventSheets/*.json. Do not answer it from memory. Before the first event,
name or edit, read the file for what you are doing; each one says what to
read next.

| Doing | Read first |
|-------|------------|
| Anything, at the start of the session | Construct3-RAG/AGENTS.md |
| Deciding what the events are | Construct3-RAG/prompts/event-sheet-thinking.md |
| Writing a plugin, behavior, ACE, effect or script name | Construct3-RAG/AGENTS.md section 2 |
| Looking for how an official example does it | Construct3-RAG/AGENTS.md section 2 |
| Writing an addon: a new plugin, behavior, effect or theme for the Addon Manager, not an event that uses one | Construct3-Manual/Construct3-Addon-SDK/index.md, then a sample under Construct-Addon-SDK/ |
| Changing eventSheets/, layouts/, objectTypes/ JSON or clipboard JSON by hand | Construct3-RAG/prompts/references/hand-editing-project-files.md |
| Naming an event, or reading one the user names ("event 15", a screenshot, a Find result) | Construct3-RAG/prompts/references/hand-editing-project-files.md, "Naming an event to the user" |
| Generating the whole project from a script, or checking generated files | Construct3-RAG/prompts/project-tools/README.md |
| Following a `[manual: ...]` reference in those files | Construct3-Manual/Construct3-Manual/<that path> |
```

The block is a router: each row names the one file that owns that task, and
the details live there, so a change to a tool or a data path is made once.
It loads nothing at startup; the agent reads each file when the work calls
for it. If it keeps skipping them, add one line at the end:
`@<path-to>/Construct3-RAG/prompts/event-sheet-thinking.md`. Claude Code
inlines that file into every session of the project, at the cost of its full
length each time; other tools ignore the line.
