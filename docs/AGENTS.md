# docs/ Directory

Three audiences, three folders. Put a new document where its reader is.

| Folder | Reader | Contents |
|--------|--------|----------|
| `guide/` | People and agents using the data or API | `quick-start.md`, `api-reference.md`, `data-format.md` |
| `dev/` | People and agents changing the code | `architecture.md`, `data-pipeline.md` |
| `decisions/` | Anyone asking why something is the way it is | one record per decision |

`guide/` and `dev/` describe current behavior and change with the code that
alters it.

## Decision records

A record answers why the current design is what it is. It carries `Date`
and, where the data matters, `Schema` lines, then `Problem`, `Evidence` when
it is not in the problem, `Options`, `Decision`, and `Re-evaluate when`.

- A record states what holds now. When a decision changes, rewrite the
  record; do not append a dated update. A record whose subject is gone is
  deleted, and the commit that deletes it says why. Git keeps the history.
- Evidence is the finding that settles the choice, in a sentence or a small
  table, not the log of the runs behind it. Eval iterations, sweeps, raw
  counts and hashes stay in `.local/docs/evidence/`, which `.gitignore`
  excludes; a record may name that folder, and nothing needed to use the
  data or the service lives there.
- A finding from someone's game project is stated generically: no project,
  object or variable names.
- State behavior and cite the manual; a tally over the examples or a
  minified editor name goes stale with the next release.

The agent entry point is `AGENTS.md` at the repository root. Keep its tables
in sync when a document here moves or is added.

## The records

Data and schemas:

| Record | What it settles |
|--------|-----------------|
| `common-aces-from-editor-bundle.md` | Where the structural side of `plugins/_common.json` comes from, and which plugin gets which shared ACE |
| `common-instance-properties.md` | The properties every world instance carries, and where a project file writes them |
| `schema-index-per-locale-split.md` | Why display names live in the per-locale index rather than the root one |
| `version-from-data-manifest.md` | Why the Construct release is read from `data/` and not from a setting |

The project skill and the prompts:

| Record | What it settles |
|--------|-----------------|
| `project-tools-skill.md` | Why the project tools ship as an Agent Skill, and what keeps small models on them |
| `edit-sheet-script.md` | Why events enter a sheet through a checked plan instead of hand-edited JSON |
| `checker-editor-load-rules.md` | How the checker learns the editor's load rules, and the editor opener that checks the rest |
| `event-sheet-design-guidance.md` | The event sheet prompts, the style checks and the generator's placement helpers |
| `published-game-visual-language.md` | Which visual, motion, camera and pacing rules repeated across 38 published Construct games, and which candidate greybox values still need a preview |
| `game-look-from-design-skills.md` | What the design and game-art skills on GitHub do to steady an agent's output, and the palette, text and pixel-art defaults the generator template took from them |
| `bootstrap-from-the-url.md` | How a machine holding only the repository URL reaches a game project with the skill installed |

The lookup service:

| Record | What it settles |
|--------|-----------------|
| `remove-qdrant-full-mode.md` | Why the service is Direct Lookup only, and what `POST /search` answers |
| `remove-compatibility-facades.md` | Why each type has one import path and the request trace is gone |

A new record gets a row in its group here, in the same change that adds it.
