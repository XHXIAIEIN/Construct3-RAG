# The Plugin's `/` Menu Lists Each Script; the Model Routes Through One Skill

Date: 2026-10-16
Schema: Construct 3 r495.2

## Problem

The `construct3` plugin gives Claude Code one skill,
`construct3:construct3-agent-plugin`, so its `/` menu shows one row. The
scripts the skill carries are listed only inside `SKILL.md`, which a
person does not open from the menu. Anthropic's own plugins list each
capability as a row of its own, and a person who wants to run one script,
`lookup_ace.py System wait` or `check_project.py`, has to know the script's
path or ask Claude in words.

The goal is one menu row per script, with no change to what the model
reads when it routes on its own.

## Evidence

The model's route is one skill. Reading that one `SKILL.md` is what decides
whether a run uses the plan and check chain: the block's first step sends
the agent to it, and the runs that opened it used `edit_sheet.py` while
the others edited JSON by hand (`project-tools-skill.md`, "What holds the
design in place"). Guidance split over files reached fewer runs than the
one text: the route table and the per-task dispatcher were tried in the
eval iterations and taken back, and the skill is re-attached after a
compaction as one text with a 5000-token budget (`skill-body-budget.md`).
So the thin skills carry no guidance, and the menu does not change
`skills/construct3-agent-plugin/SKILL.md`.

A skill with `disable-model-invocation: true` is a menu row that costs the
model nothing. The Claude Code skills page, "Control who invokes a skill",
gives the table: default, "Description always in context, full skill loads
when invoked"; `disable-model-invocation: true`, "Description not in
context, full skill loads when invoked"; `user-invocable: false`,
"Description always in context, full skill loads when invoked". The
frontmatter reference says the field also keeps the skill from being
preloaded into sub-agents and from running as a scheduled task's prompt.
A plugin skill is listed as `/plugin-name:skill-name` ("Where skills
live"), so the rows sort together under `construct3:`.

The same page gives the two substitutions the rows need: `$ARGUMENTS`,
"All arguments passed when invoking the skill", and `${CLAUDE_PLUGIN_ROOT}`,
"Substituted only in plugin skills", in "the skill's markdown content, and
Bash rules in the `allowed-tools` frontmatter". The `` !`command` `` syntax
"runs shell commands before the skill content is sent to Claude. The
command output replaces the placeholder".

What a row's command may be is set by two rules of the same page and by
the permission check, measured with the built plugin loaded under another
name through `claude -p "/<plugin>:lookup-ace System wait" --plugin-dir
<copy>` and the session's transcript read back:

- `${CLAUDE_PLUGIN_ROOT}` becomes the plugin's absolute path with forward
  slashes, and `$ARGUMENTS` the text typed after the row. The command's
  output reaches the model as the skill's text, followed by the sentence
  on the main skill. The skills attachment of the request lists the main
  skill and Claude Code's own skills, and none of the rows.
- Outside auto mode, a command whose permission check "returns anything
  other than allow" aborts the invocation, and "A failed command aborts
  the entire skill invocation", any non-zero exit counting as a failure.
- The permission check refuses an expansion in the command, `echo "exit
  code $?"` ("Command contains expandable strings with embedded
  expressions"), and a chain around `python`, `|| true` ("python appears
  inside a control-flow or chain statement ... requires manual approval").
  On Windows with the PowerShell tool on, the command runs through the
  PowerShell tool, which a `Bash(python *)` rule does not cover; the check
  passes with `allowed-tools: Bash(python *) PowerShell(python *)`.
- A script that exits 2 outside a project, `open_in_editor.py --steps`,
  reaches the model through the runner below as its `no project.c3proj`
  line and `exit code 2`.

The scripts exit non-zero on a finding, a miss, a refusal or a usage error,
and that output is what the person asked to read. A chain or an expansion
that would keep the exit code is refused, as above. So the rows run their
script through `skills/menu/run.py`, which passes the script's output
through, prints `exit code N` as its last line and exits 0.

The plugin folder's limits (`plugin-folder.md`): the menu adds one file per
script and the runner, about 17 KiB in all, and the build stays under the
file count and the size that record gives. On 2026-10-16 the build held 494
files and 6,968,547 bytes. The size limit is read off two scans, so the
margin under it is not known; the next cuts are in `plugin-folder.md`,
"Re-evaluate when".

## Options

1. Split the main skill into one skill per script, each with its own
   guidance. One row per script, but the model routes on twenty
   descriptions and reads a part of the guidance; the evidence above says
   that reaches fewer runs.
2. Thin menu skills beside the main one, `disable-model-invocation: true`,
   each running its script with the user's arguments and pointing a
   session without the main skill at `SKILL.md`. One row per script, the
   model's context unchanged, and the person's typed row runs the script
   as the skill's own commands do. Costs: one file per script of the 512,
   a runner, and a description per script to keep in step with the script.
3. Do nothing: the menu stays one row, and the scripts stay reachable
   through Claude in words or by path.

Where the thin skills live: written by hand under `skills/menu/`, or
generated by the build from each script's `--help`. The generated form
keeps one source for the arguments, but a menu row needs a description in
the third person of about two sentences, which no `--help` holds, and a
hint of the positional arguments and the main flags, which a usage line
of twenty groups is not. So the rows are written by hand, and the test
holds the parts that `--help` decides: the hint's positional groups equal
the usage line's, in order, and every flag group of the hint is a group of
the usage line.

## Decision

Option 2, under `skills/menu/<name>/SKILL.md`, the name the script's stem
with hyphens, so the rows group by prefix: `lookup-ace`,
`lookup-script-api`, `search-guides`; `print-sheet`, `print-layout`;
`new-project`, `edit-sheet`; `check-project`, `open-in-editor`,
`preview-project`; `review-design`, `review-look`; and the rest.
Each row:

- `disable-model-invocation: true`; a `description` of what the script
  prints and when, in the third person; an `argument-hint` of groups of
  the script's usage line, in double quotes, because a hint that starts
  with `[` is a flow sequence to a YAML parser and the text after it a
  parse error; `allowed-tools: Bash(python *) PowerShell(python *)`, so
  that the row runs under the default permission mode whichever tool
  Claude Code runs it through. `argument-hint` and
  `disable-model-invocation` are Claude Code's fields, not the open
  format's, so the reference validator of `skills/AGENTS.md` fails on a
  row by design; `tests/test_plugin_folder.py` pins the frontmatter
  instead.
- A body of one line before the command, the command
  `` !`python "${CLAUDE_PLUGIN_ROOT}/skills/run.py" <script> $ARGUMENTS` ``,
  and one sentence: if `construct3:construct3-agent-plugin` is not loaded
  in this session, read its `SKILL.md` before acting on the output.

`scripts/build_plugin.py` copies `skills/menu/<name>/SKILL.md` to
`plugin/skills/<name>/SKILL.md` and `skills/menu/run.py` to
`plugin/skills/run.py`, and fails when a script under
`skills/construct3-agent-plugin/scripts/` has no row, a row names no
script, or a row exists for a script that `NOT_IN_MENU` of the build
names. That set holds the modules the scripts import and `install.py`,
which copies the skill into a game project, a copy a plugin user does not
need (`plugin-tracks-commits.md`). The generator template,
`assets/build_project.py`, has no row: it is copied into the game as
`tools/build_project.py` and rewritten there, so the plugin holds no
script to run.

`tests/test_plugin_folder.py` pins the set of rows against the scripts,
the frontmatter, the command, the sentence on the main skill, the hint
against the usage line, and the runner's pass-through and exit code.

## Trade-offs

- A description written by hand goes stale when a script's purpose
  changes; the test catches a changed usage line, not a changed purpose.
  The row of `skills/AGENTS.md` names the file to change with the script.
- The runner adds a process per row. The scripts take tenths of a second;
  the editor scripts take seconds, as before.
- `allowed-tools` grants `python` with any arguments for the turn that
  invokes the row. The row's own command is the only one the turn runs
  before the model speaks, and the person's own permission rules govern
  what the model runs after.
- The rows run under the default `bash` shell on a machine with Git Bash
  and under the PowerShell tool elsewhere on Windows; on a Windows machine
  with neither, the skills page says the invocation fails before the
  command runs.
- Each script costs one file of the directory's 512; the effects are the
  next part to bundle (`plugin-folder.md`, "Re-evaluate when").

## Re-evaluate when

- An eval iteration runs with the menu in the plugin (a plugin arm,
  `skills/AGENTS.md`, "Evals"): the claim that the rows cost the model
  nothing rests on the attachment of one request, not on a run.
- A signed-in CLI runs `claude -p "/construct3:check-project"` in a game
  project: the model's reply to a row's text has not been read.
- Claude Code changes what `disable-model-invocation` keeps out of
  context, or the permission check on injected commands.
- A script is added or removed: the build names the row to add or delete.
- The plugin folder nears 512 files or the directory refuses a build.
