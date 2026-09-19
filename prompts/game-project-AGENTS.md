# AGENTS.md for a Construct 3 project

Nothing in a Construct project points here. The `llm-context.md` Construct
writes into every project describes the folder layout, not this data, so an
agent in the game folder answers from memory: a drag-and-drop interaction
comes back as UID links, `Pick all` and globals.

Copy the block into the project's `AGENTS.md` and fill in the one path at
the top, or a symlink inside the project that points here. The
`Construct3-Manual`, `Construct-Example-Projects` and `Construct-Addon-SDK`
clones are expected beside this repository, where the README places them;
a clone kept elsewhere gets its own line. Nothing else in the block needs
editing, and the block says what the agent does if the path was left
unfilled. Claude Code 2.1.277 and later read `AGENTS.md` when the project
has no `CLAUDE.md`; an earlier version, or a project that already has a
`CLAUDE.md`, needs that `CLAUDE.md` to hold the line `@AGENTS.md`, as this
repository's does.

```markdown
# Construct 3

- Construct3-RAG: <path-to>/Construct3-RAG

Construct3-Manual, Construct-Example-Projects and Construct-Addon-SDK are
cloned beside it; add a line like the one above for any that is elsewhere.
If the path still reads `<path-to>`, the block was copied unfilled: use
`$CONSTRUCT3_RAG` if it is set, otherwise ask the user where the clone is
and offer to fill the line in. Do not guess a path, and do not go on from
memory.

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
