# Construct3-RAG

**English** | [中文](README_CN.md)

Construct3-RAG lets an AI agent make and change [Construct 3](https://www.construct.net) games saved as project folders. Every condition, action, expression and effect is here as the editor defines it. The scripts of the [`construct3-agent-plugin`](skills/construct3-agent-plugin/SKILL.md) skill let the agent look up the JSON of each one, read and edit event sheets, check the project, and open and play it in the Construct 3 editor.

The data is committed here as JSON files, which the agent and the scripts read directly.

- To set an agent up for a game, follow [Set up](#set-up).
- To look a Construct 3 fact up in the data, see [Look something up](#look-something-up).
- To change this repository, read [`AGENTS.md`](AGENTS.md).

## Set up

You need Git and Python 3.10 or later. Run both commands as written, from any folder:

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
```

They put this repository, the three [related repositories](#related-repositories) and a new `MyGame` project with a Git repository of its own in `$HOME/Construct3`, then install the skill in `MyGame`: a copy in `.agents/skills/`, a Construct 3 block in `AGENTS.md` and the line `@AGENTS.md` in `CLAUDE.md`. In `cmd.exe`, write `%USERPROFILE%` for `$HOME`. To keep everything in another folder, write that folder in both commands in place of `$HOME/Construct3`.

To change what the second command does:

- For a game you already have, give `--project` the path of its folder. A name alone creates a new project beside the clones, a copy of `data/c3-new-project`, the empty project the editor saves for **Project** > **New**.
- To start from an empty project of your own, add `--template <folder>`.
- If your agent reads skills from another folder, add `--into <folder>`, such as `--into .trae/skills` for TRAE.
- Run it again at any time to refresh the skill from the clone. Clones and instruction files that exist stay as they are. `--help` lists every option.

Then read `MyGame/AGENTS.md`; the script's last line names the first file to read. If your agent takes its instructions from another file, such as `GEMINI.md`, first add a line there that says to read `AGENTS.md`.

### Claude Code

In Claude Code, the `construct3` plugin takes the place of the two commands. Choose one or the other: with both, the game project holds a copy of the skill that updates apart from the plugin.

The plugin is this whole repository, so the schemas come with it and the scripts run from the plugin's folder. Install it in one of three ways:

- From Claude's directory, the versions Anthropic has reviewed: on claude.ai, open **Customize** > **Plugins**, search for Construct3 and select **Add**. Claude Code signed in with the same account downloads it at its next start, as `construct3@synced`. Each version waits for a review, so this copy can be some commits behind the repository.
- From this repository, to follow its latest commit:

  ```bash
  claude plugin marketplace add XHXIAIEIN/Construct3-RAG
  claude plugin install construct3@construct3-rag
  ```

  `claude plugin update construct3@construct3-rag` brings Claude Code's copy up to the latest commit.
- From a clone you already have, so that a `git pull` reaches the next session: link the clone into Claude Code's skills folder.
  - PowerShell: `New-Item -ItemType Junction -Path ~/.claude/skills/construct3 -Target <the clone>`
  - Elsewhere: `ln -s <the clone> ~/.claude/skills/construct3`

  Link it rather than adding the clone as a marketplace, which copies all of it, ignored files included, into the plugin cache.

If the directory's copy is added as well, Claude Code loads the one installed from this repository or linked from a clone, and leaves the directory's copy unloaded.

## What the skill does

[`SKILL.md`](skills/construct3-agent-plugin/SKILL.md) tells the agent when to run which script. Each script in `scripts/` prints its options and examples with `--help`.

- `lookup_ace.py` looks up the conditions, actions and expressions of an object in the project, of `System`, or of a plugin or behavior, and prints each with its parameters, its event sheet wording and the JSON to write. Given an effect, it prints the effect's parameters.
- `print_sheet.py` prints an event sheet as the editor words it, under the editor's event numbers. It reads the official examples the same way.
- `edit_sheet.py` adds, moves, replaces or removes events from a JSON plan addressed by those numbers, and checks the result before it writes anything.
- `check_project.py` checks every project file against the schemas and the rules the editor applies when it opens a project. Each finding names its place, and what to write where it can.
- `check_look.py` checks the stand-in art of a generated game against the strict rules of `assets/look-manifest.json`, such as the grid, the palette and text contrast.
- `open_in_editor.py` opens the project in the Construct 3 editor and reports that it opened, or the editor's message. With `--preview` it runs the game for a few seconds and reports the runtime errors with their events.
- `preview_project.py` plays a preview from a plan of taps, drags, key presses and waits. It takes screenshots, and records parts you can review frame by frame and copy to the agent as a task.
- `export_project.py` has the editor export the project to Web (HTML5), with your subscribed account.
- `pack_project.py` saves the project as a `.c3p` or `.zip` the editor opens, or unpacks a `.c3p` or `.zip` into a project folder.
- `install.py` installs the skill in a game project, or refreshes a copy from the clone.
- `assets/build_project.py` is a template for a script that generates a whole project from Python.

### What the skill's scripts read, write and reach

They read this repository's `data/` and the projects and files you point them at. They install no package and send nothing to a server of ours.

- Read only: `lookup_ace.py`, `check_project.py`, `check_look.py`, and `print_sheet.py`, which keeps a hash of each sheet it prints in `construct3-sheet-stamps/` of the system's temporary folder, so that `edit_sheet.py` notices a save made in between.
- Writing files: `edit_sheet.py` writes the event sheets you point it at, and their hashes beside those of `print_sheet.py`. `install.py` writes the skill's copy, deleting the files the skill no longer has, the block in `AGENTS.md` and the line in `CLAUDE.md`; an absolute `--into`, such as `~/.agents/skills`, puts the copy outside the project, and `--dry-run` shows the changes first. `pack_project.py` writes the archive or folder named by `--out`, by default a `.c3p` in the project's `.tmp/`, or a folder beside the archive it unpacks. `assets/build_project.py`, once copied to the project's `tools/` and rewritten for the game, rewrites the project files it generates and runs `check_project.py`.
- Opening the editor: `open_in_editor.py`, `preview_project.py` and `pack_project.py --open` start the Edge, Chrome or Chromium on the machine, headless unless `--headed`, with a profile of their own in the project's `.tmp/` unless `--profile` names another folder. They open `https://editor.construct.net/`, the editor Scirra serves, and a preview opens `https://preview.construct.net`. The project is handed to the editor page inside the browser, not uploaded. The scripts drive the browser over a DevTools port on `127.0.0.1`; a plan's `js` and `until` steps run JavaScript in the preview, and `--install-addon` installs a `.c3addon` in the editor of that profile. Results, screenshots and recordings go to the project's `.tmp/`; a recording is joined into a video with ffmpeg, or a GIF with Pillow, where one is installed. Before each run, `preview_project.py` clears the saves that earlier previews left in its profile, unless the plan sets `keep_saves`. Without a browser on the machine they start nothing and print the steps for a browser tool of the agent's.
- Exporting: `export_project.py` drives the same editor in a visible browser, with a profile of its own in `.tmp/` of the main clone of the Git repository that holds the project, found with `git`, or of the project when none does. It replaces the contents of the folder given by `--to`, by default the project's `.tmp/export-web`, with the export, and writes the exported version into `project.c3proj` when it differs. The editor exports a large project only for an account with a subscription: you log in yourself in that window, the browser keeps the session in that profile for the next export, and the script never reads or stores a credential. `--attach` uses a browser of yours with remote debugging turned on instead: the script connects to it over DevTools, reads its port from the browser's `DevToolsActivePort` file when given only a port, lists its tabs, works only in a tab with no project open, and opens a window when no such tab exists.

## Look something up

Lookups run from the clone made in [Set up](#set-up). For a condition, action or expression, run `lookup_ace.py` with the object and a few words of the name:

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait
```

It prints each match with its parameters, its wording and the JSON to write. Use it for `System`, and for the ACEs every world object shares, under any world object, such as `Sprite overlap`: `plugins/system.json` and `plugins/_common.json` run to thousands of lines, more than most file tools read at once, and an ACE past the cut looks missing.

Everything else is read from the files under `data/`, where `{locale}` is one of the `languages` in `c3-schemas/_index.json`, such as `en-US`:

| Path | Content |
|---|---|
| `c3-schemas/_index.json` | Version, locales, and every plugin, behavior and effect with its file path and ACE counts. Language neutral |
| `c3-schemas/{locale}/_index.json` | Addon names in that language, keyed by the same ids |
| `c3-schemas/{locale}/plugins/{id}.json` | Conditions, actions, expressions, properties |
| `c3-schemas/{locale}/plugins/_common.json` | ACEs every world object shares: overlap, collisions, instance variables, hierarchy, UID, Z order. Each plugin file lists the ones it gets under `commonAces` |
| `c3-schemas/{locale}/behaviors/{id}.json` | Behavior ACEs |
| `c3-schemas/{locale}/effects/{id}.json` | Effect parameters and categories |
| `c3-schemas/{locale}/_deprecated.json` | Plugins, behaviors, effects and ACEs the editor has deprecated, with the current ACE of the same name where there is one |
| `c3-examples/{locale}/{id}.json` | Example name, description, tags, used addons, open URL |
| `c3-lang/{locale}.json` | The editor's language pack from the CDN, one string per line |
| `c3-ts-defs/autocomplete-data.json` | Scripting class to methods and properties |
| `c3-ts-defs/**/*.d.ts` | Full TypeScript interface signatures |
| `c3-guides/constructs-project-format.md` | Scirra's guide to the project folder, the one the `llm-context.md` of every project links, as Markdown (CC BY 4.0) |

Field names match the Construct CDN. Structural fields such as `id`, `scriptName`, `category` and parameter types are the same in every locale. A condition from `en-US/plugins/sprite.json`:

```json
{
  "id": "is-animation-playing",
  "list-name": "Is playing",
  "display-text": "Is animation {0} playing",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": { "animation": { "type": "animation", "name": "Animation", "desc": "..." } }
}
```

The same `id` in another locale carries that language's `list-name`, `display-text` and parameter names. [docs/guide/data-format.md](docs/guide/data-format.md) explains every field, with a worked example; section 2 of [`AGENTS.md`](AGENTS.md) is the procedure an agent follows, deprecated ACEs and example projects included.

## Event sheet prompts

To build an assistant that writes event sheets, load these three together as its system prompt:

- [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md): events structured in Construct terms, such as picking, families, containers and `Else`.
- [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md): the output format, and every name checked against the data.
- [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md): runtime behavior that intuition gets wrong, one line each. The cases and sources behind the lines are in `prompts/pitfalls/`, one file per topic, read when the events touch that topic.

For events written into a project, [`prompts/event-sheet-style.md`](prompts/event-sheet-style.md) is how the official examples write a sheet: groups and their variables, comments, names, UI text. Material needed only sometimes is in `prompts/references/`; these files point to it when a task calls for it.

## Related repositories

`bootstrap.py` clones three more repositories beside this one:

| Repository | What it holds | How it fits |
|---|---|---|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | The official manual, Addon SDK guide, and Game Services docs as Markdown | `data/c3-schemas/` is the names and parameters; this is what they do. |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Every example from the Construct example browser, saved as folder projects | `data/c3-examples/` is the metadata; this is the source. |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | Templates and documentation for custom plugins, behaviors, effects, and themes | `data/c3-ts-defs/sdk/` is the typed interface; this shows how to use it. |

## Lookup service (optional)

For a program that queries over HTTP, the clone can serve the same data as a deterministic keyword lookup, offline and on this machine. It needs Python 3.11 or later:

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

Setup options, the `/search` and `/health` endpoints and their responses: [docs/guide/quick-start.md](docs/guide/quick-start.md) and [docs/guide/api-reference.md](docs/guide/api-reference.md).

## Project structure

```
AGENTS.md               AI agent entry point
.claude-plugin/         Claude Code plugin and marketplace manifests
data/                   Committed reference data, read directly
  c3-schemas/           ACE definitions, effects, one folder per locale
  c3-examples/          Example project metadata
  c3-lang/              CDN language packs
  c3-ts-defs/           TypeScript scripting interfaces
  c3-guides/            Scirra's guide to the project format
  c3-new-project/       The editor's empty project, copied for a new game
prompts/                LLM system prompts
  pitfalls/             Cases and sources behind the pitfalls, one file per topic
  references/           Loaded on demand
skills/                 Agent Skills, installed into a game project
  construct3-agent-plugin/   The project tools listed in What the skill does
src/                    Optional lookup service (see src/AGENTS.md)
scripts/                Setup, data refresh, version check
tests/                  Offline pytest suite
docs/guide/             User docs
docs/dev/               Contributor docs
docs/decisions/         Decision records
.github/workflows/      Data update automation
```

## Credits

Data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com), fetched from the [editor CDN](https://editor.construct.net). Construct 3 is a trademark of Scirra Ltd.

[MIT](LICENSE)
