# docs/ Directory

Each folder holds the documents of one reader. Put a new document in the
folder of its reader.

| Folder | Reader | Contents |
|--------|--------|----------|
| `guide/` | People and agents using the data or API | `quick-start.md`, `api-reference.md`, `data-format.md` |
| `dev/` | People and agents changing the code | `architecture.md`, `data-pipeline.md`, `published-game-analysis.md` |
| `decisions/` | Anyone asking why something is the way it is | one record per decision |

`guide/` and `dev/` describe current behavior and change with the code that
alters it. When a document here is added or moves, update the tables of
`AGENTS.md` at the repository root, the agent entry point, to match.

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

## The records

Data and schemas:

| Record | What it settles |
|--------|-----------------|
| `common-aces-from-editor-bundle.md` | Where the structural side of `plugins/_common.json` comes from, and which plugin gets which shared ACE |
| `common-instance-properties.md` | The properties every world instance carries, and where a project file writes them |
| `deprecated-addons-from-editor.md` | Which addons and effects the export leaves out as deprecated, where the flags come from, and which deprecated ACEs the schema keeps and `_deprecated.json` lists |
| `schema-index-per-locale-split.md` | Why display names live in the per-locale index rather than the root one |
| `version-from-data-manifest.md` | Why the Construct release is read from `data/` and not from a setting |
| `cdn-release-directory.md` | Which CDN directory a release is fetched from, and why the root is never read for it |
| `release-schema-diff.md` | What the update pull request reports about a release, and when it waits for a person instead of merging itself |
| `update-fails-visibly.md` | Why a failed version check, a wrong CDN body or a short export fails the update and leaves `data/` as committed |
| `example-usage-index.md` | Which official examples use each ACE: how the index is built from the examples clone and refreshed, and what `lookup_ace.py` prints of it |
| `lf-line-endings.md` | Why every text file is LF in the repository and in every checkout, the CDN's TypeScript definitions included |

The repositories:

| Record | What it settles |
|--------|-----------------|
| `skill-in-agent-skills.md` | Why the `construct3-agent-plugin` skill, the prompts, the plugin and their tests and records live in Construct3-Agent-Skills, what stays here, and why `plugin/` is frozen here for now |

The reference study of published games:

| Record | What it settles |
|--------|-----------------|
| `published-game-visual-language.md` | Which visual, motion, camera and pacing rules repeated across published Construct games, and which of them the generator template in Construct3-Agent-Skills took |

The lookup service:

| Record | What it settles |
|--------|-----------------|
| `remove-qdrant-full-mode.md` | Why the service is Direct Lookup only, and what `POST /search` answers |
| `query-gold-in-pytest.md` | Why the Direct Lookup gold set runs in the ordinary `pytest` run, what a case holds, and why an effect name is answered only together with an effect word |
| `topic-search-ace-types.md` | Why a topic search keeps every ACE type a noun could mean, which shared ACEs it searches for a plugin, and how equal scores are ordered |
| `remove-compatibility-facades.md` | Why each type has one import path, and why the service keeps no request trace |

A new record gets a row in its group here, in the same change that adds it.
