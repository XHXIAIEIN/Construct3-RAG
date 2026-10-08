# Construct3-RAG

**English** | [中文](README_CN.md)

Construct3-RAG lets an AI agent make and change [Construct 3](https://www.construct.net) games that are saved as project folders. It holds every condition, action, expression and effect as the editor defines them, in JSON files that the agent and the scripts read directly. The scripts come with the [`construct3-agent-plugin`](skills/construct3-agent-plugin/SKILL.md) skill. With them, the agent looks up the JSON to write and reads and edits event sheets. It also checks the project, and opens and plays it in the Construct 3 editor.

> [!IMPORTANT]
> **AI agents: answer this question before you write a project file.** Is this repository cloned on the user's machine? Can you run `python <clone>/skills/construct3-agent-plugin/scripts/check_project.py --project <game folder>` there and read its output?
>
> - If yes, follow [Set up](#set-up), then the installed `SKILL.md`. Before you hand over a project, make sure that `check_project.py` reports no problems. Write every `.c3p` with `pack_project.py`.
> - If no, stop. This is the case when you read this page from the web, or when you have no shell or no Python. Tell the user that you cannot build a Construct 3 project from this repository. Then give them the two commands of [Set up](#set-up) to run, or suggest an agent with a terminal.
>
> A project written from this page and general knowledge, without the scripts, gets values that the editor rejects. The editor then refuses to open it.

- To set an agent up for a game, follow [Set up](#set-up).
- To look up a Construct 3 fact in the data, see [Look something up](#look-something-up).
- To change this repository, read [`AGENTS.md`](AGENTS.md).

## Set up

1. Install Git and Python 3.10 or later.
2. Run these two commands as written, from any folder:

   ```bash
   git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
   python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
   ```

3. Read `MyGame/AGENTS.md`, then the installed `SKILL.md`. The last line that `bootstrap.py` prints gives the path of `SKILL.md`.

The commands put this repository, the [related repositories](#related-repositories) and the `MyGame` project into `$HOME/Construct3`. `MyGame` gets a Git repository of its own. Then `bootstrap.py` installs the skill in `MyGame`. It copies the skill to `.agents/skills/` and adds a Construct 3 block to `AGENTS.md`. It also adds the line `@AGENTS.md` to `CLAUDE.md`.

In `cmd.exe`, write `%USERPROFILE%` in place of `$HOME`. To keep everything in another folder, write that folder in both commands in place of `$HOME/Construct3`.

You can add these options to `bootstrap.py`:

- For a game that you already have, pass the path of its folder to `--project`. If you give a name alone, the command creates an empty project of that name beside the clones.
- To start from an empty project of your own, add `--template <folder>`.
- If your agent reads skills from another folder, add `--into <folder>`, such as `--into .trae/skills` for TRAE.

To update, run `git pull` in the clone, then run `bootstrap.py` again to refresh the skill in the project. It leaves the clones and instruction files that exist as they are. When the clone is behind its upstream and holds no work of your own, `check_project.py` reports it as a problem and gives the commands that update the clone and the skill in the project. Add `--help` to `bootstrap.py` to see every option.

If your agent reads its instructions from another file, such as `GEMINI.md`, add a line there. The line tells the agent to read `AGENTS.md`.

### Claude Code

In Claude Code, the `construct3` plugin replaces the two commands. Use one or the other, because with both, the game project holds a copy of the skill that updates separately from the plugin.

The plugin is the [`plugin/`](plugin/README.md) folder, which `scripts/build_plugin.py` builds from the skill and the data it reads, so the schemas come with it. The scripts run from the plugin's folder. Install the plugin in one of three ways:

- From Claude's directory, for the versions that Anthropic has reviewed. On claude.ai, open **Customize** > **Plugins**. Search for Construct3 and select **Add**. Claude Code downloads the plugin as `construct3@synced` at its next start, if it is signed in to the same account. Each version waits for a review, so this copy can be some commits behind the repository.
- From this repository, to follow its released versions:

  ```bash
  claude plugin marketplace add XHXIAIEIN/Construct3-RAG
  claude plugin install construct3@construct3-rag
  ```

  To bring Claude Code's copy up to the version in the repository's `plugin.json`, run `claude plugin update construct3@construct3-rag`. A change to the plugin's skill, data or prompts raises that version. Claude Code updates it on its own only when auto-update is on for the marketplace, and auto-update is off by default for a marketplace that Anthropic does not run. To turn it on, run `/plugin` in a session, open the **Marketplaces** tab, select `construct3-rag`, then select **Enable auto-update**. An update applies from the next session.
- From a clone that you have, so that the next session uses what `git pull` fetched: link the clone into Claude Code's skills folder.
  - PowerShell: `New-Item -ItemType Junction -Path ~/.claude/skills/construct3 -Target <the clone>/plugin`
  - Other shells: `ln -s <the clone>/plugin ~/.claude/skills/construct3`

  Use a link, not a marketplace that points at the clone. A marketplace installs a copy, which a `git pull` does not change.

If you also add the copy from Claude's directory, Claude Code loads the plugin from this repository or from the linked clone. It ignores the directory's copy.

## What the skill does

[`SKILL.md`](skills/construct3-agent-plugin/SKILL.md) tells the agent which script to run and when. Every script below except the `assets/build_project.py` template prints its options and examples with `--help`.

- `lookup_ace.py` looks up the conditions, actions and expressions of an object in the project, of `System`, or of a plugin or behavior. It prints each one with its parameters, its event sheet wording, the JSON to write, and the official examples that use it with the command that prints each use. For an effect, it prints the effect's parameters.
- `lookup_script_api.py` looks up the scripting API. Given an interface, a plugin or a behavior, it prints the members. Given a member, it prints the declaration, the interface that declares it and the file and line, inherited members included.
- `search_guides.py` searches the event sheet pitfalls and the official examples by words. It prints the matching pitfall entries in full, and for each matching example the command that prints its events.
- `print_sheet.py` prints an event sheet in the editor's words, with the editor's event numbers. It reads the official examples the same way.
- `edit_sheet.py` adds, moves, replaces or removes events from a JSON plan that uses those numbers. It checks the result before it writes anything.
- `print_layout.py` prints the layers of each layout from bottom to top, and the instances on each layer in Z order. Each instance comes with its box, size, opacity and text. A text also names the object that it lies on, so the output shows a label that misses its button.
- `check_project.py` checks every project file against the schemas and against the rules that the editor applies when it opens a project. Each finding names its place and, where it can, what to write. With `--review`, for a project that someone asks about, it and `print_sheet.py` end with what a review reports: what the project does first, and only the problems that stop something from working.
- `review_design.py` reads the event sheets and reports where their design is hard to read or fragile, such as an event with too many conditions, one fact kept in two places or a scratch global. Each finding names the event and the form to write instead. Then it asks the agent fixed questions to answer from `print_sheet.py`.
- `check_design.py` checks the design of a new game before any project file is written: the user's request in their words, what this round leaves for later, the core loop, the state table, the inputs, the rules, win and lose, and acceptance tests. Then it plays the tests on the rules themselves, as a prototype that runs without the editor, and refuses a game that a player wins by doing nothing, unless the design says that waiting is the win. Each finding names its place in the design, and a failed test names the step and the values that the state held. When the design passes, the last line repeats the request and what is left for later.
- `play_design.py` plays the same tests in the Construct 3 editor on the game built from the design. First it checks the names and start values of the design against the project files. Each failure names the test, the step and the rules whose events to compare.
- `check_look.py` checks the files of a generated game against the strict rules in `assets/look-manifest.json`, such as a clean alpha channel, instances on the grid and a hit shown as a colour.
- `prepare_art.py` brings in art from the agent's image tool. It prints a prompt for each picture that the generator asks for. Then it cuts each picture that the tool made out of its background and fits it to the box of its stand-in shape. It needs Pillow.
- `open_in_editor.py` opens the project in the Construct 3 editor and reports that it opened, or gives the editor's message. With `--preview`, it runs the game for a few seconds and reports the runtime errors with their events. With `--typescript`, the editor writes the project's TypeScript definitions into `scripts/ts-defs/`.
- `preview_project.py` plays a preview from a plan of taps, drags, key presses and waits. It takes screenshots and records parts of the run. You can review a recording frame by frame and give a part of it to the agent as a task.
- `review_look.py` previews the project, visits every layout and takes a screenshot of each. It reports what the runtime shows wrong there, such as a text that its box cuts or instances stacked on one spot. Then it asks the agent fixed questions to answer from the screenshots.
- `screenshot_sheet.py` takes a picture of an event sheet, or of one group in it, as the editor shows it, for a forum post, a bug report or a document. The picture is in English and cropped to the sheet, and each column is as wide as its longest line.
- `export_project.py` makes the editor export the project to Web (HTML5), with your subscribed account.
- `pack_project.py` saves the project as a `.c3p` or `.zip` that the editor opens. It also unpacks a `.c3p` or `.zip` into a project folder.
- `new_project.py` starts a game project in an empty folder from the empty project that the editor saves for **Project** > **New**.
- `install.py` installs the skill in a game project, or refreshes a copy from the clone. It also brings the helpers in a game's `tools/build_project.py` up to date, and `--helpers-only` does only that.
- `assets/build_project.py` is a template for a Python script that generates a whole project. Its helpers sit between two markers, apart from the game's settings above them and the game below them.

### What the skill's scripts read, write and reach

The skill's scripts read this repository's `data/` and the projects and files that you give them. They run on the Python standard library, except `prepare_art.py`, which needs Pillow. They reach the network in two ways: `check_project.py` fetches the clone's upstream, and the editor scripts open the Construct 3 editor and its preview in a browser on your machine.

- **Read only**: `lookup_ace.py`, `lookup_script_api.py`, `search_guides.py`, `check_project.py`, `review_design.py`, `check_design.py`, `check_look.py` and `print_sheet.py`. `print_sheet.py` keeps a hash of each sheet that it prints, in `construct3-sheet-stamps/` of the system's temporary folder. With this hash, `edit_sheet.py` notices a save made between the print and the edit. `check_project.py` runs `git fetch` in the clone at most once an hour, to say when the clone is behind its upstream. If `CONSTRUCT3_RAG_OFFLINE` is `1`, it skips the fetch and says so.
- **Writing files**:
  - `edit_sheet.py` writes the event sheets that you give it, and their hashes beside those of `print_sheet.py`.
  - `install.py` writes the skill's copy, the block in `AGENTS.md` and the line in `CLAUDE.md`. In the copy, it deletes the files that the clone's skill does not have. An absolute `--into`, such as `~/.agents/skills`, puts the copy outside the project. In the project's `tools/build_project.py`, it replaces the helpers between the two markers with the skill's when they are an older version that nobody edited there, and keeps the rest of the file. `--dry-run` shows the changes first.
  - `play_design.py --adopt-starts` writes the start values of the project into the design file, when the prototype still passes with them.
  - `prepare_art.py` writes the fitted pictures into the project's `art/`. It reads the pictures in `art/raw/` and changes none of them.
  - `screenshot_sheet.py` writes its pictures in the project's `.build/sheets/`, or in the folder that `--out` names.
  - `pack_project.py` writes the archive or folder that `--out` names. By default, it writes a `.c3p` in the project's `.build/`, the folder for build products. When it unpacks, it writes a folder beside the archive by default.
  - The agent copies `assets/build_project.py` to the project's `tools/` and adapts it to the game. When it runs, the copy rewrites the project files that it generates, then runs `check_project.py`.
- **Opening the editor**: `open_in_editor.py`, `preview_project.py`, `play_design.py`, `review_look.py`, `screenshot_sheet.py` and `pack_project.py --open` start Edge, Chrome or Chromium on the machine.
  - The browser runs headless unless you add `--headed`. It uses a profile of its own in the project's `.tmp/`, unless `--profile` names another folder.
  - The browser opens `https://editor.construct.net/`, the editor that Scirra serves. A preview opens `https://preview.construct.net`. The scripts pass the project to the editor page inside the browser, so the project files stay on your machine.
  - The scripts drive the browser over a DevTools port on `127.0.0.1`. The `js` and `until` steps of a plan run JavaScript in the preview. `--install-addon` installs a `.c3addon` in the editor of that profile.
  - Results, screenshots and recordings go to the project's `.tmp/`. If ffmpeg is installed, a recording becomes a video. Otherwise, if Pillow is installed, it becomes a GIF. Either one also joins its key frames into a contact sheet for the agent to judge the motion from.
  - Before each run, `preview_project.py` clears the saves that earlier previews left in its profile, unless the plan sets `keep_saves`.
  - If the machine has none of these browsers, the scripts start nothing. They print the steps for a browser tool of the agent instead.
- **Exporting**: `export_project.py` drives the same editor in a visible browser.
  - The browser profile is in `.tmp/` of the main clone of the Git repository that holds the project, which the script finds with `git`. If no Git repository holds the project, the profile is in the project's `.tmp/`.
  - The script replaces the contents of the folder that `--to` names with the export. The default folder is the project's `.build/web`. If the exported version differs from the version in `project.c3proj`, the script writes the exported version into `project.c3proj`.
  - The editor exports a large project only for an account with a subscription. You log in yourself in that window, and the browser keeps the session in that profile for the next export. The script does not read or store your credentials.
  - With `--attach`, the script uses a browser of yours that has remote debugging turned on, and connects to it over DevTools. If you give only a port, the script looks for the browser's `DevToolsActivePort` file that names that port. The script lists the browser's tabs and works only in a tab with no project open. If no such tab exists, it opens a window.

## Look something up

Run lookups from the clone that [Set up](#set-up) makes. For a condition, action or expression (an ACE), run `lookup_ace.py` with the object and a few words of the name:

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait
```

It prints each match with its parameters, its wording and the JSON to write. Under each match printed in full, it gives the number of official examples that use it, and a `print_sheet.py` command for each of up to three uses, the smallest sheets first. Seven or more matches print one line each, without counts. Use it for `System` and for the ACEs that every world object shares. Look a shared ACE up under any world object, such as `Sprite overlap`. The files of these ACEs, `plugins/system.json` and `plugins/_common.json`, are too long for most file tools to read at once. Such a tool shows only the first part of a file, so an ACE after that part looks missing.

Read everything else from the files under `data/`. In the paths below, `{locale}` is one of the `languages` in `c3-schemas/_index.json`, such as `en-US`:

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

## Event sheet prompts

To build an assistant that writes event sheets, load these three files together as its system prompt:

- [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md): how to structure events in Construct terms, such as picking, families, containers and `Else`.
- [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md): the output format, and a check of every name against the data.
- [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md): runtime behavior that intuition gets wrong, one line each. `prompts/pitfalls/` holds the cases and sources behind the lines, one file per topic. When the events touch a topic, read the file of that topic.

For events written into a project, [`prompts/event-sheet-style.md`](prompts/event-sheet-style.md) describes how the official examples write a sheet: groups and their variables, comments, names and UI text. `prompts/references/` holds material that only some tasks need. The files above point to it when a task needs it.

## Related repositories

`bootstrap.py` clones these repositories beside this one:

| Repository | Content | How it fits |
|---|---|---|
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
.claude-plugin/         Claude Code marketplace manifest
plugin/                 The Claude Code plugin, built by scripts/build_plugin.py
.claude/                Claude Code ACE lookup sub-agent and polish workflow
data/                   Committed reference data, read directly
  c3-schemas/           ACE definitions and effects, one folder per locale
  c3-examples/          Example project metadata
  c3-example-usage/     Which examples use each ACE
  c3-lang/              CDN language packs
  c3-ts-defs/           TypeScript scripting interfaces
  c3-guides/            Scirra's guide to the project format
  c3-new-project/       The editor's empty project, copied for a new game
prompts/                LLM system prompts
  pitfalls/             Cases and sources behind the pitfalls, one file per topic
  references/           Material that some tasks load
skills/                 Agent Skills, installed into a game project
  construct3-agent-plugin/   The project tools of "What the skill does"
src/                    Optional lookup service (see src/AGENTS.md)
scripts/                Bootstrap, plugin build, lookup service setup, data refresh, version check, schema diff, published-game analyzer
tests/                  Offline pytest suite
docs/guide/             User docs
docs/dev/               Contributor docs
docs/decisions/         Decision records
.github/workflows/      Data update automation
```

## Credits

Data from [Construct 3](https://www.construct.net) by [Scirra Ltd](https://www.scirra.com), fetched from the [editor CDN](https://editor.construct.net). Construct 3 is a trademark of Scirra Ltd.

[MIT](LICENSE)
