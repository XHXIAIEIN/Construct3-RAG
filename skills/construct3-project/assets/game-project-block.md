# Construct 3

- Construct3-RAG: <path-to>/Construct3-RAG

Construct3-Manual, Construct-Example-Projects and Construct-Addon-SDK are
cloned beside it; add a line like the one above for any that is elsewhere.
Never guess this path: the checker in step 1 stops when it does not reach
the clone, and says what to write.

Anything that changes what the game does is event sheet work: a new
mechanic, a fix, a behavior, a variable, a timer, an animation, an edit to
eventSheets/*.json. Do not answer it from memory.

1. Before opening a project file, read
   `.agents/skills/construct3-project/SKILL.md`. Its scripts print an event
   sheet as events, look an ACE up with the JSON to write, change a sheet
   from a plan, check the project and generate one from a script; eventSheets/
   is read and changed through them. If that folder is missing,
   Construct3-RAG/AGENTS.md section 4 installs it. Then run
   `python .agents/skills/construct3-project/scripts/check_project.py` once:
   it stops with what to fix when the path above does not reach the clone or
   the copy is behind it, and its findings are the state of the project.
2. Before the first event, name or edit, read the file for what you are
   doing; each one says what to read next.

| Doing | Read first |
|-------|------------|
| Deciding what the events are | Construct3-RAG/prompts/event-sheet-thinking.md |
| Writing a plugin, behavior, ACE, effect or script name, or looking for how an official example does it | Construct3-RAG/AGENTS.md section 2 |
| Writing an addon: a new plugin, behavior, effect or theme for the Addon Manager, not an event that uses one | Construct3-Manual/Construct3-Addon-SDK/index.md, then a sample under Construct-Addon-SDK/ |
| Changing eventSheets/, layouts/, objectTypes/ JSON or clipboard JSON by hand; naming an event, or reading one the user names ("event 15", a screenshot, a Find result) | Construct3-RAG/prompts/references/hand-editing-project-files.md; for the event numbers, "Naming an event to the user" |
| Following a `[manual: ...]` reference in those files | Construct3-Manual/Construct3-Manual/<that path> |
