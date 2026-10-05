# The Plugin Is a Folder Built From the Repository

Date: 2026-10-05

## Problem

With the repository root as the plugin folder, the folder that Claude's
directory validates holds the whole repository: the data, the lookup
service, the tests, the docs and the maintainer's `/polish` workflow.
Validation then holds each version for a reviewer on four findings, and each
one comes from a file that a plugin user does not reach through the skill:

- "Files or downloads the validator couldn't inspect": more than 512 files,
  and the two language packs of `data/c3-lang/`, about 2 MiB each.
- "Image or font file that the plugin's code could run": the PNG icons of
  `data/c3-new-project/`, which `scripts/bootstrap.py` copies into a new
  project. The checker, its tests and `checker-rules.md` also name image
  paths of a game project, such as `icons/icon-16.png`; the checklist's rule
  covers images bundled in the plugin, which the icons are and a game
  project's images are not.
- "Uses a credential from the user's machine" and "Contains a download-and-run
  command": `.claude/workflows/polish.js`. The workflow tells its sub-agents
  to fetch documentation pages and to run local commands; it reads no
  credential and runs nothing it fetches.

The directory repeats a hold on each version it picks up, so every release
waits for a reviewer.

## Evidence

Claude's "Plugin pre-submission checklist", "Files in the plugin folder",
holds a version whose plugin folder has more than 512 files, a file other
than an image or a font over 256 KiB, or a script that refers to a bundled
image.

The skill reads these parts of the repository outside its own folder, by the
paths in its scripts, `SKILL.md`, `references/` and the game-project block:

| Part | Read by | Kept as |
|------|---------|---------|
| `data/c3-schemas/` | every script, and agents directly | its files, a few hundred |
| `data/c3-ts-defs/` except `sdk/` | `lookup_script_api.py`, which skips `sdk/` | one bundle |
| `data/c3-examples/` | `search_guides.py`, `check_design.py` | two bundles per locale, from about a thousand small files |
| `data/c3-lang/` | `check_project.py`, two subtrees of about 10 KiB | the two subtrees |
| `data/c3-guides/`, `prompts/` | agents, from `SKILL.md` and the block | their files |
| `skills/construct3-agent-plugin/` except `evals/` | | its files |

Copied as they are, these parts come to well over 512 files, most of them
the examples. The schemas fit as files, and agents open them by path, so
they stay as files.

## Options

- The repository root as the plugin: every version waits for a reviewer.
- A plugin branch that CI builds and pushes, followed by the directory:
  main keeps one copy, but a release depends on a workflow that pushes, and
  the plugin can be validated only after that push.
- A committed subfolder that a script builds and a test checks.

## Decision

`plugin/` is the plugin. `scripts/build_plugin.py` builds it from the
repository, and the result is committed. The marketplace entry's source is
`./plugin`, the directory submission's plugin path is `plugin`, and the
link into `~/.claude/skills/` of `plugin-tracks-commits.md` points at
`<clone>/plugin`.

The build:

- Copies `skills/construct3-agent-plugin/` except `evals/`,
  `data/c3-schemas/`, `data/c3-guides/`, `prompts/` and
  `data/c3-ts-defs/autocomplete-data.json` to the same paths.
  The skill's scripts find `data/` in the folder above them as they do in
  the clone, and an agent opens a schema at the same relative path.
- Writes `data/c3-ts-defs/` except `sdk/`, and each locale of
  `data/c3-examples/`, as bundles: JSON objects from relative path to file
  content, each under 256 KiB. One loader in `c3project.py` reads a data
  folder from its files in the clone and from its bundles in the plugin.
  `lookup_script_api.py`, `search_guides.py` and `check_design.py` read
  through it, so in the plugin the TypeScript definitions and the examples
  are read through those scripts only.
- Writes `data/c3-lang/{locale}.json` with the two subtrees that
  `check_project.py` reads, at the same JSON paths.
- Copies `data/c3-new-project/`, Construct's icons included. A new project
  is made by `new_project.py` of the skill, which copies the empty project
  and gives it its own name and `uniqueId`. The clone and the plugin start a
  project with the same command: `bootstrap.py` calls the same function, and
  `install.py` and the `no project.c3proj` message of `c3project.py` name
  `new_project.py`. The icons are the ones the editor's Project > New
  writes, so a new project looks as one made in the editor.
- Leaves out `bootstrap.py`. It clones the sibling repositories beside the
  folder that holds `data/`, which in the plugin is Claude Code's plugin
  cache, and a script that downloads and runs code holds a version for a
  reviewer. A plugin user works without the siblings, as the skill does
  wherever they are missing.
- Writes `.claude-plugin/plugin.json`, `README.md` and the icon from their
  sources in `scripts/plugin/`, and the repository's `LICENSE`. The icon
  goes at the plugin root, because the plugin manifest reference ("Manifest
  file") keeps only `plugin.json` in `.claude-plugin/`. `plugin.json` names
  it in `icon`, which Claude's directory reads for the listing and Claude
  Code ignores. No text of the plugin writes the icon's path in backticks
  or a code block, which the checklist holds for a reviewer. The README
  describes the plugin route only, and states what the plugin runs and what
  reaches the network: the checker's fetch of a clone, and the browser that
  the scripts open on the Construct editor and its preview. The checklist's
  "Prepare for the security scan" asks the README to describe everything
  the plugin runs, sends or fetches. This repository's README names
  `plugin/` as the plugin folder.

Copied text files are written with LF line endings, as Git stores them, so
a checkout with CRLF files (`lf-line-endings.md`) builds the same folder as
any other.

The skill names a file of this repository as `Construct3-RAG/<path>`. A
game project resolves it through its `Construct3-RAG:` line, which a plugin
user's project often lacks. So the plugin bullet of `SKILL.md` says that
`Construct3-RAG/` before `data/` or `prompts/` stands for
`${CLAUDE_PLUGIN_ROOT}/`, and the skill's text names no file that the
plugin holds only in a bundle. Claude Code replaces that variable with the
plugin's folder in the Markdown body of a skill when it loads the skill
(Claude Code docs, "Plugin manifest reference", "Environment variables").
It does not replace the variable in a reference that the agent reads with
a file tool, and a Bash command does not get it. So only `SKILL.md` can
carry the variable. Its one sentence also covers the paths of the
references, which a build that wrote the variable into `SKILL.md` would not
reach, so the build copies `SKILL.md` unchanged.

The scripts print a file of this repository by its absolute path. A
TypeScript declaration that the plugin holds only in a bundle is printed as
the `lookup_script_api.py` command that prints it.

The result stays under 512 files. A test builds the folder into a temporary
directory and fails when the result differs from `plugin/`, has more than
512 files, holds a binary file other than a PNG or a file over 256 KiB other
than an image, names in `icon` a file it does not hold, or lacks a file or
folder under `data/` or `prompts/` that `SKILL.md`, `references/` or the
game-project block names as `Construct3-RAG/<path>`. Another runs the
plugin's scripts with no clone, and fails when a pitfall path that
`search_guides.py` prints does not open, or when `lookup_script_api.py`
prints a file path instead of a command. `init.py` builds the folder again
after each data refresh, so the update workflow's pull request carries the
build with the data.

`skills/construct3-agent-plugin/` and `data/` stay the source. Edit them,
then run the build; never edit `plugin/` by hand, because the next build
overwrites it and the test fails until then.

## Trade-offs

- A change to the skill or the data is two diffs in one commit, the source
  and the build. Git stores identical content once, so the copied files add
  no size; the bundles add a blob on each change.
- In the plugin, the TypeScript definitions and the examples are read
  through their scripts only. The clone keeps them as files.
- The checker's clone-behind check (`clone-update-check.md`) looks for
  `.git` in the folder that holds `data/`. Run from `<clone>/plugin`, it
  looks one folder up.
- The icons are bundled images that `new_project.py` copies, which the
  checklist holds for a reviewer when a script refers to them. The script
  copies the empty project as a folder and names no image file.
- The room under 512 files shrinks with each new addon, which adds one
  schema file per locale.

## Re-evaluate when

- The plugin folder nears 512 files. The next part to bundle is
  `data/c3-schemas/{locale}/effects/`, the small files of the effects, which
  agents reach through `lookup_ace.py`.
- Re-validation of the built folder still reports a hold that this layout
  should remove. If the icons are the only hold left, the next step is to
  draw placeholder icons in code and bundle no image.
- The directory changes its file limits.
