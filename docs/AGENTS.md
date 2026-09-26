# docs/ Directory

Three audiences, three folders. Put a new document where its reader is.

| Folder | Reader | Contents |
|--------|--------|----------|
| `guide/` | People and agents using the data or API | `quick-start.md`, `api-reference.md`, `data-format.md` |
| `dev/` | People and agents changing the code | `architecture.md`, `data-pipeline.md` |
| `decisions/` | Anyone asking why something exists or was removed | `refactoring-audit.md` and one dated record per decision |

`guide/` and `dev/` describe current behavior and must be updated with the
change that alters it. `decisions/` records are dated evidence; append a new
record rather than rewriting history. A new record carries `Date` and
`Schema` lines, then `Problem`, `Evidence`, `Options`, `Decision`, and
`Re-evaluate when`; later changes to the same decision go in dated `Update`
sections at the end. `refactoring-audit.md` is the exception: it is the
running index of the lookup service's structural decisions and is edited in
place when a record changes what is current.

Material that is not published lives in `.local/docs/`, which `.gitignore`
excludes: run outputs and logs behind a decision record, gold snapshots a
comparison ran against, notes and drafts. A record states its numbers and the
hashes of the files it read, then names their `.local/docs/` path. Tracked
documents never link into `.local/`, and nothing there is needed to use the
data or the service.

The agent entry point is `AGENTS.md` at the repository root. Keep its tables
in sync when a document here moves or is added.

## The records

Data and schemas:

| Record | What it settles |
|--------|-----------------|
| `common-aces-from-editor-bundle.md` | Where the structural side of `plugins/_common.json` comes from, and what to rerun when a release changes it |
| `common-instance-properties.md` | The properties every world instance carries, and which file holds them |
| `schema-index-per-locale-split.md` | Why display names live in the per-locale index rather than the root one |

The project skill and the prompts:

| Record | What it settles |
|--------|-----------------|
| `project-tools-skill.md` | Why the project tools ship as an Agent Skill, and what each evaluation iteration changed |
| `edit-sheet-script.md` | Why events enter a sheet through a checked plan instead of hand-edited JSON |
| `checker-editor-load-rules.md` | Which of the editor's load rules the checker applies, and where they were read from |
| `event-sheet-design-guidance.md` | The event sheet prompts, the authoring style taken from the examples, and their evaluations |
| `game-look-from-design-skills.md` | What the design and game-art skills on GitHub do to steady an agent's output, and the palette, text and pixel-art defaults the generator template took from them |
| `bootstrap-from-the-url.md` | How a machine holding only the repository URL reaches a game project with the skill installed |

The lookup service:

| Record | What it settles |
|--------|-----------------|
| `refactoring-audit.md` | The running index of the service's structural decisions, and the boundaries left open |
| `remove-qdrant-full-mode.md` | What `POST /search` answers now that the optional full mode is gone |
| `query-understanding-refactor-requirements.md` | The requirements the query-understanding stages were run against, written before stage zero |
| `query-understanding-stage-zero-audit.md` | The product-direction review of the real `/search` path |
| `query-understanding-stage-one-baseline.md` | The 72-query gold set and the lookup baseline measured on it |
| `query-understanding-stage-two-semantic-evaluation.md` | The live comparison of the semantic strategies, on the mode since removed |

A new record gets a row in its group here, in the same change that adds it.
