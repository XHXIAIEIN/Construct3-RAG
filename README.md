# Construct3-RAG

**English** | [中文](README_CN.md)

Structured, bilingual reference data for [Construct 3](https://www.construct.net): plugins, behaviors, ACEs, effects, example projects, scripting interfaces, and the raw language packs. Everything under `data/` is committed JSON and `.d.ts` that a script or an LLM can read directly. An optional service adds keyword lookup on top.

## Set up from this link

Run both commands as written, from any directory:

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
```

They put this clone, the repositories it reads and the `MyGame` project together in `$HOME/Construct3`, and install the `construct3-project` skill in `MyGame` with its `AGENTS.md` and `CLAUDE.md`. Whatever is already there is left as it is, so the two are safe to run again; `--help` lists the flags. In `cmd.exe`, write `%USERPROFILE%` for `$HOME`. To keep everything somewhere else, write that folder into both commands in place of `$HOME/Construct3`.

`MyGame` starts as a copy of `data/c3-new-project`, the empty project the editor creates with **Project** > **New** and saves with **Save as** > **Save as project folder**. To start from an empty project saved on this machine instead, add `--template <that folder>` to the second command.

Then read `MyGame/AGENTS.md`.

## Related repositories

Three more repositories, which `bootstrap.py` clones beside this one:

| Repository | What it holds | How it fits |
|---|---|---|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | The official manual, Addon SDK guide, and Game Services docs as Markdown | `data/c3-schemas/` is the names and parameters; this is what they do. |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Every example from the Construct example browser, saved as folder projects | `data/c3-examples/` is the metadata; this is the source. |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | Templates and documentation for custom plugins, behaviors, effects, and themes | `data/c3-ts-defs/sdk/` is the typed interface; this shows how to use it. |

## Data files

No install needed. Pick a locale, `en-US` or `zh-CN`, and read. All paths are under `data/`.

| Path | Content |
|---|---|
| `c3-schemas/_index.json` | Version, locales, and every plugin, behavior, and effect with its file path and ACE counts. Language neutral |
| `c3-schemas/{locale}/_index.json` | Addon names in that language, keyed by the same ids |
| `c3-schemas/{locale}/plugins/{id}.json` | Conditions, actions, expressions, properties |
| `c3-schemas/{locale}/plugins/_common.json` | ACEs every world object shares: overlap, collisions, instance variables, hierarchy, UID, Z order. Exported once, not repeated per plugin |
| `c3-schemas/{locale}/behaviors/{id}.json` | Behavior ACEs |
| `c3-schemas/{locale}/effects/{id}.json` | Effect parameters and categories |
| `c3-examples/{locale}/{id}.json` | Example name, description, tags, used addons, open URL |
| `c3-lang/{locale}.json` | Raw CDN language pack, one string per line, for diffing releases and translations |
| `c3-ts-defs/autocomplete-data.json` | Scripting class to methods and properties |
| `c3-ts-defs/**/*.d.ts` | Full TypeScript interface signatures |

Field names match the Construct CDN. Structural fields such as `id`, `scriptName`, `category`, and parameter types are identical in every locale, so an ACE found in one language can be read in the other. Field meanings, layout, and worked examples: [docs/guide/data-format.md](docs/guide/data-format.md).

## Reading the data

1. Find the addon in `_index.json`. Its entry gives the `file` path and the ACE counts. If you only have a localized name, look it up in `{locale}/_index.json` first.
2. Open `data/c3-schemas/{locale}/{file}` and locate the ACE by `id`, by `list-name` for conditions and actions, or by `translated-name` for expressions. `display-text` is the event sheet wording and `params` lists the parameters. If a world object's ACE is not in its file, it is in `plugins/_common.json`; the full list for a Sprite is its own file plus that one.
3. For scripting, look the class up in `autocomplete-data.json`, then open the matching `.d.ts`.

A condition from `en-US/plugins/sprite.json`:

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

The same `id` in `zh-CN/plugins/sprite.json` carries the Chinese `list-name`, `display-text`, and parameter names.

## For AI agents and LLMs

Start with [`AGENTS.md`](AGENTS.md): the fact lookup procedure, the event sheet design procedure, and the rules for changing the code. To help users write event sheets, load [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md), [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) and [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md) together as the system prompt: structure in Construct terms (picking, families, containers, `Else`), output format and name verification, and sourced runtime facts that intuition gets wrong. [`prompts/event-sheet-style.md`](prompts/event-sheet-style.md) is the authoring style of the official examples (folders, groups and their variables, comments, names, UI text), for events written into a project. Each points to `prompts/references/` for material needed only sometimes, so that stays out of context until a task calls for it.

An agent inside a game project reaches this repository through the [`construct3-project`](skills/construct3-project/SKILL.md) skill, a folder in the [Agent Skills](https://agentskills.io) format with the ACE lookup, the sheet printer, the sheet editor, the checker and the generator template. The two commands at the top install it; `AGENTS.md` section 4 has the rule for a project that lacks it.

## Lookup service (optional)

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

This runs the deterministic offline lookup service over the committed data. It needs no database, no model and no network.

Setup options, the `/search` and `/health` endpoints, and response shapes: [docs/guide/quick-start.md](docs/guide/quick-start.md) and [docs/guide/api-reference.md](docs/guide/api-reference.md).

## Project structure

```
AGENTS.md               AI agent entry point
data/                   Committed reference data, read directly
  c3-schemas/           ACE definitions, effects (en-US + zh-CN)
  c3-examples/          Example project metadata
  c3-lang/              CDN language packs
  c3-ts-defs/           TypeScript scripting interfaces
prompts/                LLM system prompts
  references/           Loaded on demand
skills/                 Agent Skills, installed into a game project
  construct3-project/   ACE lookup, sheet printer, sheet editor, checker, generator template
src/                    Optional lookup service, own .env (see src/AGENTS.md)
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
