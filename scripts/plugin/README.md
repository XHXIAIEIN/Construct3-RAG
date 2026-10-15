# Construct3

Construct3 lets Claude make and change [Construct 3](https://www.construct.net) games saved as folder projects. It carries every condition, action, expression and effect as the Construct 3 editor defines them, in English and Chinese. It also carries the `construct3-agent-plugin` skill, whose scripts use them. With the skill, Claude:

- looks up the exact JSON of a condition, action or expression before writing it, and the scripting API of a Construct plugin or behavior;
- prints an event sheet as events and changes it from a checked plan;
- starts a new project from the empty one the editor saves, or generates a whole project from a script;
- checks a project against the rules the editor applies when it opens one;
- opens the project in the Construct 3 editor, previews it and exports it.

## Use

Install the plugin, then ask Claude about a Construct 3 project in its folder: a change such as "add a double jump", or a problem such as "why does the editor refuse to open this project". The skill loads on its own for such a request. To start a game, ask for a new project in an empty folder.

The scripts need Python 3.10 or later. Cutting pictures out of an image tool's output needs Pillow.

The plugin also adds the sub-agent type `construct3:project-worker`, for a change or a lookup that the main agent hands over. It has only the tools the scripts need (shell, file reading and editing, search and the skill), so it starts with a fraction of the context a general-purpose sub-agent starts with.

## What runs and what reaches the network

- The scripts run on the machine with Python, on the files of the project and of this plugin.
- Opening, previewing, exporting or taking a picture of a project starts Edge, Chrome or Chromium, or the agent's browser tool, on the Construct 3 editor at `editor.construct.net`, with the project loaded from the machine. A preview runs at `preview.construct.net`. An export uses the Construct account that the user signs in to in that browser; the scripts store no password.
- When the plugin is a Git clone of its repository, the checker fetches that clone's remote at most once an hour to say when it is behind. Set `CONSTRUCT3_RAG_OFFLINE=1` to turn this off; the checker then says that it did not compare the clone.

## Source

The plugin is built from [Construct3-RAG](https://github.com/XHXIAIEIN/Construct3-RAG), which also holds the data pipeline, the tests and the decision records. License: MIT.
