# AGENTS.md for a Construct 3 project

Nothing in a Construct project links to this repository. The
`llm-context.md` that Construct writes into every project outlines the
folder layout and links Scirra's guide
[Construct's project format](https://www.construct.net/en/tutorials/constructs-project-format-3275),
which says what `project.c3proj` indexes, how image files are named and
which formats the files take. Neither names an ACE, the rules the editor
applies when it opens a project, or how to design events. So an agent in
the game folder answers these from memory and builds a drag-and-drop
interaction from UID links, `Pick all` and globals. This repository keeps
the guide as
[`data/c3-guides/constructs-project-format.md`](../data/c3-guides/constructs-project-format.md),
and "The project folder" in
[`prompts/references/hand-editing-project-files.md`](references/hand-editing-project-files.md)
applies what it states about the files. If the agent adds, renames or moves
a file of the project, the block sends the agent to both.

The game project needs two things: a block in its `AGENTS.md` that names the
file to read for each kind of work, and a copy of the
`construct3-agent-plugin` skill with the tools. One command in the project
folder writes both:

```bash
python <Construct3-RAG>/skills/construct3-agent-plugin/scripts/install.py
```

It copies [`skills/construct3-agent-plugin/`](../skills/construct3-agent-plugin/SKILL.md)
to the project's `.agents/skills/`. If no instruction file of the project
names this repository, it also appends the block to `AGENTS.md`, with the
path of this clone on its `Construct3-RAG:` line. It changes no instruction
file that names this repository. `--into .claude/skills` installs where
Claude Code finds skills, `--into .trae/skills` where TRAE does. Most other
agents read `.agents/skills/`. The block names the installed `SKILL.md`
either way, so an agent without skill support reaches it too.

## The block

The text is
[`skills/construct3-agent-plugin/assets/game-project-block.md`](../skills/construct3-agent-plugin/assets/game-project-block.md).
To place it by hand, copy it into the project's `AGENTS.md`. Then fill in
the one path at the top: this clone, or a symlink in the project that
points to it. Replace `<path-to>` in place, or keep it and add a line
`- path-to = <folder>` above it for the folder that holds the clones; the
skill's scripts read both. The block expects the `Construct3-Manual`,
`Construct-Example-Projects` and `Construct-Addon-SDK` clones beside this
repository, where the README places them; a clone kept elsewhere gets its
own line. Leave the rest of the block as it is.

If the path is left unfilled, the checker in the block's first step stops
and says what to write. The block holds no instructions for a case that
`install.py` cannot produce, because every session of the project reads it.
Claude Code 2.1.277 and later read `AGENTS.md` if the project has no
`CLAUDE.md` (<https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md>).
If the project has a `CLAUDE.md`, it needs the line `@AGENTS.md`, as this
repository's has. Under an earlier version, a project without one needs a
`CLAUDE.md` that holds that line. `claude --version` prints the version.
`install.py` writes that line with the block: it creates `CLAUDE.md` with
it, or appends it to one that lacks it.

## Before the project exists

On a machine with only this clone, run this repository's
`scripts/bootstrap.py --project <folder>`. It clones the three repositories
above beside this one if they are missing, creates the folder as an empty
project, copied from `data/c3-new-project`, if it does not exist, and runs
`install.py`. The README's first section gives it to a reader who has only
the URL.

The block's first step sends the agent to the installed `SKILL.md` before
any project file is opened. It is a step and not a row of the table,
because a small model skips such a row in half the runs and edits the
sheet's JSON by hand (`docs/decisions/project-tools-skill.md`). The same step runs
`check_project.py` once. If the `Construct3-RAG:` path is wrong or the copy
is behind the clone, the checker stops there and says what to fix, before a
script fails to find the schemas. It takes well under a second and prints
at most 10 000 characters of findings. Each row of the table then names the
one file that holds the details of its task, so a change to a tool or a data
path is made in one place.

The block loads no other file at startup; the agent reads each one when its
work needs it. If the agent keeps skipping them, add this line at the end:
`@<path-to>/Construct3-RAG/prompts/event-sheet-thinking.md`. Claude Code
then inlines that file into every session of the project, at the cost of
its full length each time. Other tools ignore the line.
