# AGENTS.md for a Construct 3 project

Nothing in a Construct project points here. The `llm-context.md` Construct
writes into every project describes the folder layout, not this data, so an
agent in the game folder answers from memory: a drag-and-drop interaction
comes back as UID links, `Pick all` and globals.

Two things in the game project change that: a block in its `AGENTS.md` that
routes each kind of work to the file that owns it, and a copy of the
`construct3-project` skill with the tools. One command writes both, run in
the project folder:

```bash
python <Construct3-RAG>/skills/construct3-project/scripts/install.py
```

It copies [`skills/construct3-project/`](../skills/construct3-project/SKILL.md)
to the project's `.agents/skills/` and, when no instruction file of the
project names this repository yet, appends the block to `AGENTS.md` with the
path of this clone on its `Construct3-RAG:` line. An instruction file that
already names the clone is left as it is. `--into .claude/skills` installs
where Claude Code discovers skills, `--into .trae/skills` where TRAE does;
`.agents/skills/` is the folder most other agents read, and the block names
the installed `SKILL.md` either way, so an agent without skill support
reaches it too.

## The block

The text is
[`skills/construct3-project/assets/game-project-block.md`](../skills/construct3-project/assets/game-project-block.md).
To place it by hand, copy it into the project's `AGENTS.md` and fill in the
one path at the top, or a symlink inside the project that points here.
Replace `<path-to>` in place, or keep it and add a line
`- path-to = <folder>` above it for the folder that holds the clones; the
block and the skill's scripts read both. The `Construct3-Manual`,
`Construct-Example-Projects` and `Construct-Addon-SDK` clones are expected
beside this repository, where the README places them; a clone kept elsewhere
gets its own line. Nothing else in the block needs editing, and the block
says what the agent does if the path was left unfilled. Claude Code 2.1.277
and later read `AGENTS.md` when the project has no `CLAUDE.md`
(<https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>). A
project that has a `CLAUDE.md` needs the line `@AGENTS.md` in it, as this
repository's has; under an earlier version, a project without one needs a
`CLAUDE.md` that holds that line. `install.py` writes that line when it
writes the block: it creates `CLAUDE.md` with it, or appends it to one that
lacks it. `claude --version` prints the version.

## Before the project exists

`scripts/bootstrap.py --project <folder>` in this repository covers the
machine that has only the clone: it clones the three repositories above
beside it when they are missing, creates the folder as an empty project,
copied from the `Construct3-New-Project` repository, when it does not
exist, and runs `install.py`. The README's first section gives it to a
reader who has only the URL.

The block is a router. Its first step sends to the installed `SKILL.md`
before any project file is opened; as a row of the table, a small model
passed it over in half the runs and edited the sheet's JSON by hand
(`docs/decisions/project-tools-skill.md`). The same step runs
`check_project.py` once: a wrong `Construct3-RAG:` path or a copy behind
the clone stops there with what to fix, instead of surfacing later as a
script that cannot find the schemas. It takes well under a second and prints
the findings, at most 10 000 characters. Each row of the table then names
the one file that owns that task, and the details live there, so a change to
a tool or a data path is made once.
The block loads nothing else at startup; the agent reads each file when the
work calls for it. If it keeps skipping them, add one line at the end:
`@<path-to>/Construct3-RAG/prompts/event-sheet-thinking.md`. Claude Code
inlines that file into every session of the project, at the cost of its full
length each time; other tools ignore the line.
