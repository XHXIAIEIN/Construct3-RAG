# `skills/` Directory

Agent Skills in the open format of <https://agentskills.io/specification>:
one folder per skill, a `SKILL.md` with `name` and `description`, and
`scripts/`, `references/` and `assets/` beside it. The folder here is the
source. A game project holds a copy of it, made and refreshed by the skill's
`scripts/install.py`, and the copy reports when it differs from the source.

| Skill | Carries |
|-------|---------|
| `construct3-project/` | ACE lookup, sheet printer, checker and generator template for a Construct 3 folder project; the block for the project's instruction file |

## Rules

- The folder is what ships: `install.py` mirrors every file in it into the
  game project. Nothing that is not part of the skill lives here, no scratch
  files, outputs or notes.
- `name` is the folder's name, lowercase with hyphens. `description` says
  what the skill does and when to use it, at most 1024 characters, on one
  line and without `: `, so that a client with a plain frontmatter parser
  reads it too. `SKILL.md` stays under 500 lines; what is needed only
  sometimes goes to `references/`, and `SKILL.md` says when to read it.
- Paths inside the skill are relative to its folder. A file of this
  repository is written `Construct3-RAG/<path>`, as the block in the game
  project writes it; a relative link out of the folder breaks in a copy.
- Scripts use the standard library (Pillow is optional), take everything
  from flags, never prompt, print `--help` with examples and exit codes, and
  say in every error what to write or run next. They find the project from
  the current directory upward and this repository through the project's
  `Construct3-RAG:` line; what they share is in `scripts/c3project.py`.
- English only; `--locale` switches the schema wording, not the tool's.
- A check becomes an error after the two steps in
  `construct3-project/references/checker-rules.md`: the editor's message,
  then a run over the official examples that adds no finding.
- A restructure that should not change output is compared, old against new,
  over every official example and the game projects: exit code, stdout and
  stderr (`docs/decisions/project-tools-skill.md`).

## Checks

```bash
python -m pytest tests/test_project_tools.py -q
python -m compileall -q skills
```

The tests install the skill in a temporary project and run the copy, and
they pin the format's constraints offline. The reference validator needs
network:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate skills/construct3-project
```
