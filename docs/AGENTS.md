# docs/ Directory

Three audiences, three folders. Put a new document where its reader is.

| Folder | Reader | Contents |
|--------|--------|----------|
| `guide/` | People and agents using the data or API | `quick-start.md`, `api-reference.md`, `data-format.md` |
| `dev/` | People and agents changing the code | `architecture.md`, `data-pipeline.md` |
| `decisions/` | Anyone asking why something exists or was removed | `refactoring-audit.md`, `query-understanding-*.md` |

`guide/` and `dev/` describe current behavior and must be updated with the
change that alters it. `decisions/` records are dated evidence; append a new
record rather than rewriting history.

The agent entry point is `AGENTS.md` at the repository root. Keep its tables
in sync when a document here moves or is added.
