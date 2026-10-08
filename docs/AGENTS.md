# docs/ Directory

Each folder holds the documents of one reader. Put a new document in the
folder of its reader.

| Folder | Reader | Contents |
|--------|--------|----------|
| `guide/` | People and agents using the data or API | `quick-start.md`, `api-reference.md`, `data-format.md` |
| `dev/` | People and agents changing the code | `architecture.md`, `data-pipeline.md`, `published-game-analysis.md`, `skills-audit.md` |
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

The project skill and the prompts:

| Record | What it settles |
|--------|-----------------|
| `project-tools-skill.md` | Why the project tools ship as an Agent Skill, and what keeps small models on them |
| `generator-helpers-inline.md` | Why the generator template keeps its helpers in the file the agent edits, between markers that let a game's copy take the skill's current ones, and what was measured |
| `instruction-block-refresh.md` | Why the block in a game project's `AGENTS.md` carries a version and a stamp between markers, when `install.py` replaces it, and how an edited block or one from before the markers is treated |
| `record-tables-as-arrays.md` | Why the generator template writes a table of records as an Array file with field names in row 0, and copies it into a Dictionary at start |
| `edit-sheet-script.md` | Why events enter a sheet through a checked plan instead of hand-edited JSON, and how a plan names a variable or a comment |
| `checker-editor-load-rules.md` | How the checker learns the editor's load rules, and the editor opener that checks the rest |
| `clone-update-check.md` | Why the checker fetches the clone and fails when it is behind its upstream, and how plugin users get updates |
| `project-format-guide.md` | Where each statement of Scirra's project format guide, the one `llm-context.md` links, is written and what checks it, and how its copy in `data/c3-guides/` is kept |
| `preview-player.md` | Why a preview is played from a JSON plan of steps, and what the steps cover |
| `sheet-screenshot.md` | Why a picture of an event sheet is taken in the editor by `screenshot_sheet.py`, with its columns fitted and the picture cropped to the sheet |
| `typescript-definitions-from-the-editor.md` | Why the editor writes a project's own TypeScript definitions, through `open_in_editor.py --typescript`, and when the checker warns that they are stale |
| `game-design-prototype.md` | Why a new game starts as a design whose rules a local prototype plays before the build, and how the same tests reach the editor |
| `event-sheet-design-guidance.md` | The event sheet prompts, the style checks and the generator's placement helpers |
| `pitfalls-index-and-topics.md` | Why the pitfalls are an index of one-line conclusions with a topic file per group, and which lessons belong in them |
| `prompt-references-by-task.md` | Which parts of the design and style prompts live in `prompts/references/`, why Native first stays inline, and what a row of Native first holds |
| `borrowed-numbers.md` | Which numbers and rules of other agent frameworks were measured here before the template or a check took them, and the result for each: player height, HUD share, popups, idle motion, coyote time, images of created objects, an editor open while files change, design size, safe area, the first runtime error |
| `published-game-visual-language.md` | Which visual, motion, camera and pacing rules repeated across published Construct games, and which of them the template took |
| `game-look-from-design-skills.md` | What the design and game-art skills on GitHub do to steady an agent's output, and the palette, text and pixel-art defaults the generator template took from them |
| `greybox-blockout.md` | The blockout look a generated game has before its art, and the grids and pacing its level is laid out by |
| `landscape-viewport.md` | Why the generator template starts a game at 1920×1080 landscape, and what follows from it |
| `fill-the-screen.md` | Why a generated game fills the screen with *Scale outer* or *Integer scale outer*, its HUD held to the screen's edges by Anchor, *Viewport fit* left at *Auto*, which keeps the whole viewport visible on a notched phone, and each layer listed back to front |
| `layout-by-name.md` | Why a generated screen is laid out by names, a button with its label, named bands and a main object sized to the stage, with the positions computed and checked as numbers |
| `art-from-the-image-tool.md` | Why a generated game's art comes from the agent's image tool through `art()` and `prepare_art.py`, and is not drawn in code |
| `bootstrap-from-the-url.md` | How a machine holding only the repository URL reaches a game project with the skill installed |
| `skill-and-plugin-names.md` | The names of the skill and the Claude Code plugin |
| `plugin-tracks-commits.md` | How the build sets `plugin.json`'s version so that a change to `plugin/` reaches an install, and why a linked clone needs no copy in the project |
| `directory-listing.md` | Why the plugin is in Claude's directory and also installs from this repository, and why a reviewer publishes each directory version |
| `plugin-folder.md` | Why the plugin is the built folder `plugin/`, what it carries from the repository, and the test that keeps it equal to its sources |
| `build-folder.md` | Why a game project's packed `.c3p`, export and sheet pictures go in `.build/`, apart from the scratch of `.tmp/` |
| `random-uid-allocation.md` | Why the projects this repository starts give new instances random uids |

The lookup service:

| Record | What it settles |
|--------|-----------------|
| `remove-qdrant-full-mode.md` | Why the service is Direct Lookup only, and what `POST /search` answers |
| `query-gold-in-pytest.md` | Why the Direct Lookup gold set runs in the ordinary `pytest` run, what a case holds, and why an effect name is answered only together with an effect word |
| `topic-search-ace-types.md` | Why a topic search keeps every ACE type a noun could mean, which shared ACEs it searches for a plugin, and how equal scores are ordered |
| `remove-compatibility-facades.md` | Why each type has one import path, and why the service keeps no request trace |

A new record gets a row in its group here, in the same change that adds it.
