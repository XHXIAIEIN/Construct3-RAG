# A long sheet prints its groups, and --find names the events that use a name

Date: 2026-10-14

## Problem

`print_sheet.py` stopped a sheet longer than its limit, about 10 000
characters, after the first part and named the `--events` range that went
on. That part says nothing about where the rest of the sheet is. So a
model looking for one event of a sheet of a few hundred events printed the
whole sheet with `--limit 0`, or its whole outline, where every comment
printed in full; in Chinese a comment costs about a token a character. A
result over about 30 000 characters is kept by the harness in a file, with
its first 2 000 characters shown, and the model reads that file again in
pieces.

## Evidence

Shares of the whole cost of one production game's Claude Code transcripts,
425 sessions and sub-agents, measured with
`skills/construct3-agent-plugin/evals/token_share.py`:

| What was read | Share |
|---------------|-------|
| `print_sheet.py --limit 0 --events A-B` | 1.14% |
| `print_sheet.py --limit 0`, a whole sheet | 1.00% |
| `print_sheet.py --outline --limit 0` | 0.83% |
| `print_sheet.py` at its limit, cut | 0.22% |
| The files the harness kept of long results | 1.4% |

The game's largest sheet, printed whole, is 178 000 characters and its
outline 59 000; the list of its groups and functions is 4 500. Cutting the
outline's comments to 30 characters takes less than a tenth off that
outline.

A sheet within the limit prints its events and no list. A sheet over the
limit prints a list that stays within the limit. Reading a sheet a little
over the limit whole takes the list and two parts, one call more than a
part and the rest.

The eval case `find-in-a-big-sheet` gave no verdict. Its runs passed
`--limit 0` on their first read of the sheet, so none of them met the
list, and most of them were void. They ran in a Linux container, off the
user's machine. The runs are in
`.local/docs/evidence/skill-evals/construct3-agent-plugin/iteration-58/`,
the counts over the official examples in
`.local/docs/evidence/long-sheet-contents/`.

## Options

- Keep the first part and the line that names the next one. Cheapest for a
  sheet a little over the limit that is read whole; it tells the model
  nothing about where an event is.
- Print the list of groups and functions with the events each spans, and
  add `--find NAME` for the events that use a variable, function or object.
- Raise the limit. The harness keeps and cuts long results at about 30 000
  characters anyway, and a whole long sheet is still more than one event.
- Write an index of the sheets into the project. It is one more file to
  keep current, and a model must be told to read it.

## Decision

A sheet over the limit, printed whole and alone, prints one line per group,
function and custom action: its name and the event numbers it spans.
Nested groups are indented, and the deepest are left out while the list
would pass the limit. The list ends with the `--events` command of its
first group or function and the `--find` command. A sheet that fits prints
its events, and `--events` prints a part and names the next one.

`--find NAME` prints the events whose conditions, actions, parameters or
expressions name it, in upper or lower case. A name in quoted text, a
comment or a description does not count. Each event prints under the first
lines of the events it sits in, which are marked `[context]`. With
`--events` it reads one range, and a long result stops at an event and
names the range that continues. It replaces a whole print read for one
name, and a search of the sheet's JSON.

`--outline` keeps the first 30 characters of a comment: the outline is read
for its numbers and sids.

`scripts/output_diff.py` compares `print_sheet_limit`, the print at the
script's own limit, so a change to the list shows in its report.

The change to what `print_sheet.py` prints, and `--find` in the scripts
table of `SKILL.md`, are one eval iteration (`skills/AGENTS.md`, "Evals"):
the case `find-in-a-big-sheet` asks for one event of a sheet of 410 events
with Chinese comments that `evals/make_fixtures.py` builds, and the metric
is `print_sheet_chars` of `trace.py`, the characters the calls that ran
`print_sheet.py` returned, with `whole_sheet_prints`, the calls that passed
`--limit 0` for whole sheets, beside it.

## Re-evaluate when

- Runs that pass `--limit 0` before their first print never meet the list:
  change the sentence of `SKILL.md` that offers `--limit 0` for a file or a
  pipe.
- Runs on the user's machine, or `token_share.py` over a later week of the
  production transcripts, show whole-sheet prints that do not fall, or more
  calls per run on sheets just over the limit: bring back the first part
  for a sheet under twice the limit, and print the list only above that.
