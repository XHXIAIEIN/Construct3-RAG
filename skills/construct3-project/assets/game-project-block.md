# Construct 3

- Construct3-RAG: <path-to>/Construct3-RAG

Construct3-Manual, Construct-Example-Projects and Construct-Addon-SDK are
cloned beside it; add a line like the one above for any that is elsewhere.
`<path-to>` stands for the folder a `path-to = ...` line above gives. If
the path reads `<path-to>` and no such line exists, the block was copied
unfilled: use `$CONSTRUCT3_RAG` if it is set, otherwise ask the user where
the clone is and offer to fill the line in. Do not guess a path, and do not
go on from memory.

Anything that changes what the game does is event sheet work: a new
mechanic, a fix, a behavior, a variable, a timer, an animation, an edit to
eventSheets/*.json. Do not answer it from memory. Before the first event,
name or edit, read the file for what you are doing; each one says what to
read next.

| Doing | Read first |
|-------|------------|
| Anything, at the start of the session | Construct3-RAG/AGENTS.md |
| Deciding what the events are | Construct3-RAG/prompts/event-sheet-thinking.md |
| Writing a plugin, behavior, ACE, effect or script name, or looking for how an official example does it | Construct3-RAG/AGENTS.md section 2 |
| Writing an addon: a new plugin, behavior, effect or theme for the Addon Manager, not an event that uses one | Construct3-Manual/Construct3-Addon-SDK/index.md, then a sample under Construct-Addon-SDK/ |
| Changing eventSheets/, layouts/, objectTypes/ JSON or clipboard JSON by hand; naming an event, or reading one the user names ("event 15", a screenshot, a Find result) | Construct3-RAG/prompts/references/hand-editing-project-files.md; for the event numbers, "Naming an event to the user" |
| Looking an ACE up, reading a sheet as events, putting events into a sheet, checking project files, generating the whole project from a script | the construct3-project skill, `.agents/skills/construct3-project/SKILL.md`; if that folder is missing, Construct3-RAG/AGENTS.md section 4 installs it |
| Following a `[manual: ...]` reference in those files | Construct3-Manual/Construct3-Manual/<that path> |
