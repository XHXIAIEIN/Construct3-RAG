# A Map of the Sheets: Which Layouts Run Each, and What It Holds

Date: 2026-10-16
Schema: Construct 3 r495.2

## Problem

A trigger fires only in a sheet the running layout runs: the layout's own
sheet and every sheet that one includes, through any depth
(`prompts/pitfalls/functions.md`, confirmed in a preview on 2026-10-16). A
function runs when called from any sheet. So before an agent adds or edits a
trigger, it needs the layouts that run the sheet. Before it adds a feature,
it needs the sheet that holds the related functions, globals and objects.
`print_sheet.py` prints a sheet, a range, an outline or, for a project over
its limit, a line per sheet; `--find` prints the events that use a name.
None of these says which layouts run a sheet. In a project of several
sheets, an agent finds where a feature lives by printing sheet after sheet.

A tool for another engine's agent, studied on 2026-10-16, builds a map of a
large project from three kinds of edge: includes, global-variable references
and object references in expressions. It discounts the names everything
references. `borrowed-numbers.md` asks for a measurement here before a
borrowed feature is built.

## Evidence

### Navigation reads in the production game's transcripts

The threshold was fixed before the count: build the map if the navigation
reads cost 1% or more of the whole. That is the share each row of
`long-sheet-contents.md` cleared before `--find` was built.

Every Claude Code transcript of one production game was costed with
`skills/construct3-agent-plugin/evals/token_share.py` and counted with
`.local/docs/evidence/sheet-map/measure_nav.py`. The list of transcripts is
the one of `.local/docs/evidence/token-share/baseline-2026-10-14/`: 425 with
a model response, 194 sessions and 231 sub-agents, from 2026-09-01 to
2026-10-07. A transcript navigates when its `print_sheet.py` calls before its
first `edit_sheet.py` run name two or more different sheets, print an
outline, or print the project's sheets. A transcript without an edit counts
over its whole length.

| Count | Of 425 transcripts |
|-------|--------------------|
| Ran `print_sheet.py` | 163 |
| Ran `edit_sheet.py` | 97 |
| Navigated before the first edit | 147 (35%); 80 of them edited later, 82% of the transcripts that edit |
| Navigated by two or more sheets; by an outline; by the project's sheets | 124; 73; 20 |
| Different sheets a navigator printed before its edit | 2 in 43, 3 in 34, 4 in 19, 5 to 7 in 19, 8 to 14 in 9 |

| Reads | Share of the whole cost, 1181.6M units |
|-------|----------------------------------------|
| The navigators' `print_sheet.py` reads before their first edit | 2.72% |
| Every `print_sheet.py` read before a first edit | 2.73% |
| Every `print_sheet.py` read after it | 0.66% |
| Reads of event sheet JSON before a first edit | 0.04% |

The game had one sheet until 2026-10-01 and twelve after. From that day,
106 of 305 transcripts navigated, 53 of the 64 that edit. Their navigation
reads were 2.66% of that period's cost. No transcript used `--find`, which
was added on 2026-10-14, after the last of them.

### The projects at hand

| Project | Sheets | Folders | Layouts | Events | Includes |
|---------|--------|---------|---------|--------|----------|
| The production game | 12 | none | 2 | 1075 | 11: one layout runs `Main`, which includes the other eleven |
| `kiwi-story`, the example with most sheets | 14 | none | 10 | 219 | 13: four layouts' own sheets include `eMain`, which includes nine |
| `breach`, an example with sheet folders | 11 | 3 | 15 | 564 | 5; `SoundEvents`, 29 events, is run by no layout |
| `overloaded-underqualified`, the example with most events | 5 | none | 4 | 466 | 4 |

The map of the production game is 5 800 characters, the map of `kiwi-story`
3 300. Both fit the limit whole.

## Options

1. **Leave navigation to the agent.** The measured habit is to print sheets
   until the feature appears, 2.7% of the whole cost. Nothing tells the agent
   which layouts run the sheet it edits.
2. **A map printed by `print_sheet.py --map`**, one line per sheet, from the
   project's own files: the layout's `eventSheet`, the include events, the
   function and custom action blocks, the root variables, and the object
   names in conditions, actions and expressions. Chosen.
3. **An index file written into the project.** One more file to keep
   current, and an agent must be told to read it. The map is computed from
   the files it would index.
4. **The borrowed graph with weighted edges and discounted hubs.** Its
   references are what `--find` prints per name. A weighting would need its
   own measurement.

## Decision

`print_sheet.py --map` prints one line per sheet, under the folder
`project.c3proj` keeps it in. The line gives the sheet's events and its size
as events; the layouts that run it; the sheets that include it; the sheets it
includes; the functions and custom actions it defines; the globals it
declares; and the objects it touches most, in its conditions, actions and
expressions. System, the functions object and an object every sheet touches
are left out of the objects, as the studied tool discounts the names
everything references. A sheet no layout runs says so. With sheet names,
`--map` prints their lines.

The map stays under the limit in stages. The object lists go first, then
more than three layouts become a count, then the names of what a sheet
defines, then the includes. When the lines still do not fit, the map stops,
and its last line names the `--map` command for the sheets left. The names
of what a sheet defines go late because they say where a feature lives. The
layouts go early because most lines repeat them.

Without a sheet name, a project whose sheets together pass the limit prints
the map. The map carries each sheet's events, size and includes, so no
separate list of the sheets is needed. `--find` ends each sheet's block with
the layouts that run it, or with the line that no layout does, so that the
sheet an agent is about to edit says whether its triggers fire.

`SKILL.md`, "Read a sheet as events", says to find where a feature lives
with `--map` and `--find` before printing a sheet.

## Re-evaluate when

- `token_share.py` over a later month of the production transcripts, with
  `measure_nav.py` beside it, shows navigation reads that do not fall, or
  `--map` prints followed by the same sheet-after-sheet reads. Then the
  map's lines leave out what the agent looked for: add it, or print the map
  by default when a project has more than one sheet.
- A project with hundreds of sheets prints a map that stops before most of
  them. Then add a folder filter, or print the folders alone first.
- An agent edits a trigger in a sheet whose `--find` block said no layout
  runs it. Then the line's wording did not reach the edit: move it to the top
  of the block, or make `edit_sheet.py` say it.
