# What `check_project.py` checks

Read this when a finding needs explaining, when the editor reports an error
the checker let through, or before adding a rule.

## Against the schemas and the project

For every condition and action: the object or family exists, the behavior is
on it, the ACE id is in the plugin's, the behavior's or the shared world
object schema, the parameter keys are the schema's, a combo value is one of
its items, a comparison is an integer 0 to 5, a boolean is a JSON boolean.
Expressions are scanned for object, behavior, expression, instance variable,
function, global, local and parameter names, case-insensitively, as the
editor reads them. Layout instances must carry every instance variable and
behavior block of their type and only properties the schema has. Layers,
layouts, animations, groups, timelines, flowcharts, project files, images and
called functions and custom actions must exist, with the right parameter
count. Uids, and the sids of events, variables, object types and instances,
must be unique; a condition or action that shares a sid is a warning, since
the editor tolerates what its own paste leaves behind. A missing schema (a
third-party addon) is a warning, and its ACEs pass unchecked.

## The rules the editor applies on opening and before preview

They surface here with an event number instead of one at a time in a dialog.
How each was read from the editor and confirmed:
`Construct3-RAG/docs/decisions/checker-editor-load-rules.md`.

| Rule | The editor's message |
|------|----------------------|
| One trigger per event and per branch of sub-events; a function or a custom action counts as one, so neither holds a trigger; an OR block may list several. *On collision* and *On timer* are triggers | `cannot add another trigger to event branch` |
| A trigger, a loop, *Else*, *Trigger once* and the conditions that only pick (*Pick all*, *Pick by comparison*, *Pick nearest/furthest*, *Pick children*) are never inverted | `condition not invertible` |
| *Else* is the first condition of an event that directly follows a plain event: not a trigger, not a loop, not a group or a variable, only comments between | `An Else condition cannot be placed here`, before preview and export |
| A plugin or behavior id is spelled as the editor spells it: `Arr`, `Json`, `TiledBg`, `EightDir`, `Sin`, `solid` | `missing plugin id` |
| An object or family name is not `self`, `true`, `false`, `system` or a system expression (`Floor`, `Time`, `Random`, `Max`) | `name is reserved` |
| `Self` stands only in a parameter of an object's own condition or action; in a System one (*For each ordered*, *Pick by comparison*, *Set variable*) it names nothing, and the finding writes the expression with the object the ACE names | `Invalid use of 'self'` |
| A name has no spaces or punctuation; an instance variable name starts with a letter | the editor renames it silently, and the events that use it fail with `cannot find object` |
| An instance variable, behavior or effect is not named like another one on the object or its families, nor like an expression of the object (`Angle`, `Width`, `Count`, `Text`) | `name already in object class namespace` |
| A key is a key code, a JSON number | `expected finite number` |
| An action does not write a constant | `event variable X is constant` |
| An ease is a built-in id such as `easeoutback`, unless the project has custom eases | the tween keeps no ease and fails later |

*Trigger once* or *Every X seconds* in a triggered branch is a warning: the
editor no longer offers them there, and official examples that do it still
open.

## What a finding says

A finding says what to write where it can: the nearest id, the behavior that
owns an ACE written without `behaviorType`, the editor's id for a display
name (`Array` is `Arr`), the project's object behind a plugin name in an
expression (`JSON.Get` is `Levels.Get`), a combo value written with inner
quotes, a text value written without them. A file that lacks a key the editor
always writes stops the run with the key and the place, exit code 2. A long
report prints the findings that fit 10 000 characters, a third of them
warnings, and counts the rest: fix those and run again, or pass `--limit 0`.

A finding in an event sheet is placed as `sheet Game event 15 action 2`. The
event number is the editor's: the one in the margin of the event sheet and
in the **Where** column of Find results. Blocks, groups and function blocks
are counted per sheet in document order, sub-events included. A variable,
comment or include has no number of its own: the margin leaves it blank and
Find files it under the next numbered event, so the nine locals above event
15 of the Water Sort sheet are `Event 15` too. Conditions and actions count
from 1. `scripts/print_sheet.py --outline Game` prints the numbering of a
sheet with each event's sid, which is what to search the JSON for,
unnumbered rows in parentheses.

## Style, with `--style`

Three warnings the editor never raises, for a project the agent wrote: the
generator template passes `--style`. `edit_sheet.py` holds the events a plan
creates to them, never the sheet's older events: the first two, whose fix
is one comment, refuse the plan like a problem; the third, and any finding
on an event the plan moved or extended, is a warning under its output. Each names the event and says what to write.

| Warning | Threshold | Over the 524 official examples |
|---------|-----------|-------------------------------|
| N actions in a row without a comment action | 8 or more | 113 in 50 projects; the studio games step a block every 3 actions at the median, 6 at the 90th percentile |
| no comment above it (a top-level event, function or custom action with actions or sub-events) | none, variables between allowed | 1184 in 278 projects; 93% of the studio games' top-level events have one, the rest are Scirra's feature demos and external games |
| sub-events N levels deep, every leaf calling one function | 3 levels, 3 or more leaves | 3, in shifting-dungeon, template-ladder-climbing, wall-walking |

The three sheets small models wrote for the evidence set (Doubao snake,
DeepSeek Water Sort) raise 21, 4 and 1; 16 and 7; 4 and 2. The survey behind
the thresholds is `Construct3-RAG/docs/decisions/event-sheet-design-guidance.md`,
2026-09-22. A style warning is never an error: the editor accepts all three,
and an official example may carry one. What the shape should be instead is
`Construct3-RAG/prompts/event-sheet-style.md`.

## What it does not see

What happens at runtime: which instances a condition picks, what order
triggers fire in, whether an expression means what the comment says. The
editor and the preview judge those; the Water Sort observations in
`Construct3-RAG/prompts/event-sheet-pitfalls.md` came from previewing, not
from the checker. Expression syntax, argument counts and types, and
`function`, `template` and `audiofile` parameters are not checked either.

## How the rules were confirmed

Run over the official example projects (saved r184 to r502) with the r495.2
schemas on 2026-09-21, the checker passed 493 of 524. The rest fail on ACEs
and parameters that a later release renamed, on layers and animations the
examples name but no longer have, and on duplicate sids in r184 projects;
each is a real finding, not a false one. None of them breaks an editor rule
of the table above, which is how each rule was confirmed before it became an
error. `Construct3-RAG/tests/test_project_tools.py` generates the stand-in
game, breaks it one rule at a time and reads the finding.

A new rule takes the same two steps: find the editor's message in its
project model, run the rule over the official examples, and only then make
it an error, with a test that breaks the stand-in project.
