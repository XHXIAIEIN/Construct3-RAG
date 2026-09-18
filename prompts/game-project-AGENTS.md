# AGENTS.md for a Construct 3 project

Nothing in a Construct project points here. The `llm-context.md` Construct
writes into every project describes the folder layout, not this data, so an
agent in the game folder answers from memory: a drag-and-drop interaction
comes back as UID links, `Pick all` and globals.

Copy the block into the project's `AGENTS.md` and fill in the three paths at
the top: this repository and the `Construct3-Manual` and
`Construct-Example-Projects` clones, or symlinks inside the project that
point to them. Nothing else in the block needs editing. Claude Code reads
`CLAUDE.md`, not `AGENTS.md`: give the project a `CLAUDE.md` holding the one
line `@AGENTS.md`, as this repository does, or put the block in both.

```markdown
# Construct 3

- Construct3-RAG: <path-to>/Construct3-RAG
- Construct3-Manual: <path-to>/Construct3-Manual
- Construct-Example-Projects: <path-to>/Construct-Example-Projects

Anything that changes what the game does is event sheet work: a new
mechanic, a fix, a behavior, a variable, a timer, an animation, an edit to
eventSheets/*.json. Do not answer it from memory. Before the first event,
name or edit, read the file for what you are doing:

| Doing | Read first |
|-------|------------|
| Anything, at the start of the session | Construct3-RAG/AGENTS.md |
| Deciding what the events are | Construct3-RAG/prompts/event-sheet-thinking.md, then event-sheet-assistant.md and event-sheet-pitfalls.md next to it |
| Writing a plugin, behavior, ACE, effect or script name | Construct3-RAG/data/c3-schemas/{locale}/ (ACEs every world object shares: plugins/_common.json); scripting: data/c3-ts-defs/ |
| Changing eventSheets/, layouts/, objectTypes/ JSON or clipboard JSON by hand | Construct3-RAG/prompts/references/hand-editing-project-files.md, then its checks before handing over |
| Generating the whole project from a script, or checking generated files | Construct3-RAG/prompts/project-tools/README.md; its build-project.py and check-project.py go in tools/ |
| Following a `[manual: ...]` reference in those files | Construct3-Manual/Construct3-Manual/<that path>. construct.net rejects fetches from an agent |
| Looking for how an official example does it | Construct3-RAG/data/c3-examples/{locale}/*.json filtered on `used-addons`, then Construct-Example-Projects/example-projects/{id}/eventSheets/ |

A runtime fact learned in this project goes into
Construct3-RAG/prompts/event-sheet-pitfalls.md, with a source.
```

The block loads nothing at startup; the agent reads each file when the work
calls for it. If it keeps skipping them, add one line at the end:
`@<path-to>/Construct3-RAG/prompts/event-sheet-thinking.md`. Claude Code
inlines that file into every session of the project, at the cost of its full
length each time; other tools ignore the line.
