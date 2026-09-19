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
running index of structural decisions and is edited in place when a record
changes what is current.

Material that is not published lives in `.local/docs/`, which `.gitignore`
excludes: run outputs and logs behind a decision record, gold snapshots a
comparison ran against, notes and drafts. A record states its numbers and the
hashes of the files it read, then names their `.local/docs/` path. Tracked
documents never link into `.local/`, and nothing there is needed to use the
data or the service.

The agent entry point is `AGENTS.md` at the repository root. Keep its tables
in sync when a document here moves or is added.
