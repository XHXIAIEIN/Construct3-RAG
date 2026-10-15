# Construct3-RAG

**English** | [中文](README_CN.md)

Construct3-RAG is the reference data of [Construct 3](https://www.construct.net) for AI agents: every condition, action, expression and effect as the editor defines them, in two languages, as JSON files that an agent reads directly. It also holds the example index, the editor's language packs, the TypeScript definitions of the scripting API and Scirra's guide to the project format, and the pipeline that refreshes them from the editor's CDN each release.

The tools that make games from this data, the `construct3-agent-plugin` skill, its prompts and the Claude Code plugin `construct3`, live in [Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills). That repository builds its plugin from a clone of this one.

> [!IMPORTANT]
> **AI agents: this repository holds data, not the tools.** To make or change a Construct 3 project, go to [Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills) and follow its README. A project written from this data and general knowledge, without the skill's scripts and checks, gets values that the editor rejects.
>
> To look a Construct 3 fact up in the data, see [Look something up](#look-something-up). To change this repository, read [`AGENTS.md`](AGENTS.md).

## Make a game

Install Git and Python 3.10 or later, then run these two commands as written, from any folder:

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Agent-Skills $HOME/Construct3/Construct3-Agent-Skills
python $HOME/Construct3/Construct3-Agent-Skills/scripts/bootstrap.py --project MyGame
```

They clone that repository, the [related repositories](#related-repositories) and the `MyGame` project into `$HOME/Construct3`, and install the skill in `MyGame`. The README of Construct3-Agent-Skills says what the skill does, how to install its Claude Code plugin, and what its scripts read, write and reach. The plugin carries a copy of this repository's data, so a plugin user needs no clone of this one.

## Look something up

Read the files under `data/`. In the paths below, `{locale}` is one of the `languages` in `c3-schemas/_index.json`, such as `en-US`:

| Path | Content |
|---|---|
| `c3-schemas/_index.json` | Version, locales, and every plugin, behavior and effect with its file path and ACE counts. Language neutral |
| `c3-schemas/{locale}/_index.json` | Addon names in that language, keyed by the same ids |
| `c3-schemas/{locale}/plugins/{id}.json` | Conditions, actions, expressions, properties |
| `c3-schemas/{locale}/plugins/_common.json` | ACEs that every world object shares: overlap, collisions, instance variables, hierarchy, UID, Z order. Each plugin file lists the ones that it gets under `commonAces` |
| `c3-schemas/{locale}/behaviors/{id}.json` | Behavior ACEs |
| `c3-schemas/{locale}/effects/{id}.json` | Effect parameters and categories |
| `c3-schemas/{locale}/_deprecated.json` | Plugins, behaviors, effects and ACEs that the editor has deprecated, with the current ACE of the same name where one exists |
| `c3-examples/{locale}/{id}.json` | Example name, description, tags, used addons, open URL |
| `c3-example-usage/{plugins,behaviors}/{id}.json` | Which official examples use each ACE of the plugin or behavior: their number, and up to three uses as example folder, sheet and events. Built from the event sheets in the `Construct-Example-Projects` repository |
| `c3-lang/{locale}.json` | The editor's language pack from the CDN, one string per line |
| `c3-ts-defs/autocomplete-data.json` | Scripting classes with their methods and properties |
| `c3-ts-defs/**/*.d.ts` | Full TypeScript interface signatures |
| `c3-guides/constructs-project-format.md` | Scirra's guide to the project folder, as Markdown (CC BY 4.0). The `llm-context.md` of every project links this guide |
| `c3-new-project/` | The empty project the editor saves for **Project** > **New**, which the skill copies for a new game |

Field names match the Construct CDN. Structural fields such as `id`, `scriptName`, `category` and the parameter types are the same in every locale. So an ACE found in one locale has the same `id` in every other locale. Here is a condition from `en-US/plugins/sprite.json`:

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

The same `id` in another locale has that language's `list-name`, `display-text` and parameter names. [docs/guide/data-format.md](docs/guide/data-format.md) explains every field, with a worked example. Section 2 of [`AGENTS.md`](AGENTS.md) is the procedure that an agent follows, including deprecated ACEs and example projects.

The files of `System` and of the shared ACEs, `plugins/system.json` and `plugins/_common.json`, are too long for most file tools to read at once. Such a tool shows only the first part of a file, so an ACE after that part looks missing. With the Construct3-Agent-Skills clone beside this one, its lookup script reads them whole, and `--rag .` makes it read this clone's data:

```bash
python ../Construct3-Agent-Skills/plugin/skills/construct3-agent-plugin/scripts/lookup_ace.py --rag . System wait
```

It prints each match with its parameters, its wording and the JSON to write, and the official examples that use it.

## Related repositories

| Repository | Content | How it fits |
|---|---|---|
| [XHXIAIEIN/Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills) | The `construct3-agent-plugin` skill, the event sheet prompts and the Claude Code plugin | The tools that read this data for a game project; its plugin is built from a clone of this repository. |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | The official manual, the Addon SDK guide and the Game Services docs, as Markdown | `data/c3-schemas/` gives the names and parameters; the manual says what they do. |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Every example from the Construct example browser, saved as a folder project | `data/c3-examples/` holds the metadata, and `data/c3-example-usage/` holds which examples use each ACE; the projects are in that repository. |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | Templates and documentation for custom plugins, behaviors, effects and themes | `data/c3-ts-defs/sdk/` holds the typed interface; the SDK shows how to use it. |

## Lookup service (optional)

A program that queries over HTTP can get the same data from a lookup service on your machine. The service is a deterministic keyword lookup that runs offline. It needs Python 3.11 or later:

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

[docs/guide/quick-start.md](docs/guide/quick-start.md) gives the setup options. [docs/guide/api-reference.md](docs/guide/api-reference.md) gives the `/search` and `/health` endpoints and their responses.

## Project structure

```
AGENTS.md               AI agent entry point
.claude/                Claude Code ACE lookup sub-agent and polish workflow
data/                   Committed reference data, read directly
  c3-schemas/           ACE definitions and effects, one folder per locale
  c3-examples/          Example project metadata
  c3-example-usage/     Which examples use each ACE
  c3-lang/              CDN language packs
  c3-ts-defs/           TypeScript scripting interfaces
  c3-guides/            Scirra's guide to the project format
  c3-new-project/       The editor's empty project, copied for a new game
src/                    Optional lookup service (see src/AGENTS.md)
scripts/                Lookup service setup, data refresh and maintenance tools (see scripts/AGENTS.md)
tests/                  Offline pytest suite
docs/guide/             User docs
docs/dev/               Contributor docs
docs/decisions/         Decision records
.github/workflows/      Checks on every push to main and every pull request, data update automation
plugin/, .claude-plugin/   The last plugin built here, frozen until the directory lists the plugin from Construct3-Agent-Skills (docs/decisions/skill-in-agent-skills.md)
```

## Credits

Data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com), fetched from the [editor CDN](https://editor.construct.net). Construct 3 is a trademark of Scirra Ltd.

[MIT](LICENSE)
