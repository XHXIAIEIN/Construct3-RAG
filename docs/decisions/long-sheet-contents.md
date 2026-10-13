# A long sheet prints its groups, and --find names the events that use a name

Date: 2026-10-14

## Problem

`print_sheet.py` stopped a sheet longer than its limit, about 10 000
characters, after the first part and named the `--events` range that went
on. That part says nothing about where the rest of the sheet is. A model
looking for one event of a sheet of a few hundred then printed the whole
sheet with `--limit 0`, or its whole outline, where every comment printed
in full; in Chinese a comment costs about a token a character. A result over
about 30 000 characters is kept by the harness in a file, with its first
2 000 characters shown, and the model reads that file again in pieces.

## Evidence

Shares of the whole cost of one production game's Claude Code transcripts,
425 sessions and subagents, measured with `evals/token_share.py`:

| What was read | Share |
|---------------|-------|
| `print_sheet.py --limit 0 --events A-B` | 1.14% |
| `print_sheet.py --limit 0`, a whole sheet | 1.00% |
| `print_sheet.py --outline --limit 0` | 0.83% |
| `print_sheet.py` at its limit, cut | 0.22% |
| The files the harness kept of long results | 1.4% |

The game's largest sheet holds 474 events: printed whole it is 178 000
characters, its outline 59 000. The list of its groups and functions is
4 500 characters, most of it the names of 89 functions; the outline with
comments cut to 30 characters is 55 000.

Over the 565 sheets of the official examples at the default limit, the 449
that fit print byte for byte as before. The 116 that do not printed their
first part, 9 300 characters on average, and now print the list of their
groups and functions, a median of 1 000 characters and at most 3 000. Of
those 116, 75 are under twice the limit: reading one of them whole now
takes the list and two parts where it took a part and the rest.

The first eval of the change, iteration 58 (one case, three Haiku runs an
arm, run in a Linux container because the CLI on the user's machine could
not sign in), found the event in all six runs. Every run read
`print_sheet.py --help` first and passed `--limit 0` on its first read of
the sheet, which the task called huge, so no run met the list; two of the
three runs with the change used `--find`. The characters `print_sheet.py`
returned per run were 20 900 with the change and 19 100 without, and four
of the six runs were void for a scratch file written outside their folder:
no verdict.

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
function and custom action, by name, with the event numbers it spans,
nested groups indented, the deepest left out while the list would pass the
limit; then the `--events` command of its first group and the `--find`
command. A sheet that fits prints as before, and `--events` still prints a
part and names the next one.

`--find NAME` prints the events whose conditions, actions, parameters or
expressions name it, in any case, without quoted text, comments and
descriptions, each under the first lines of the events it sits in, marked
`[context]`; with `--events` it reads one range, and a long result stops
at an event and names the range that continues. It replaces a whole print
read for one name, and a search of the sheet's JSON.

`--outline` keeps the first 30 characters of a comment: the outline is read
for its numbers and sids. Its output changes for every sheet with a longer
comment, 213 of the official examples' sheets that fit.

`scripts/output_diff.py` gained `print_sheet_limit`, the print at the
script's own limit, so that a later change to the list is compared too.

The change to what `print_sheet.py` prints, and `--find` in the scripts
table of `SKILL.md`, are one eval iteration (`skills/AGENTS.md`, "Evals"):
the case `find-in-a-big-sheet` asks for one event of a sheet of 410 events
with Chinese comments that `evals/make_fixtures.py` builds, and the metric
is `print_sheet_chars` of `trace.py`, the characters the calls that ran
`print_sheet.py` returned, with `whole_sheet_prints`, the calls that passed
`--limit 0` for whole sheets, beside it.

## Re-evaluate when

Runs that pass `--limit 0` before their first print never meet the list,
as in iteration 58: then the lever is the sentence of `SKILL.md` that
offers `--limit 0` for a file or a pipe, which its trim (tracker item I5)
takes up. Once runs on the user's machine or `token_share.py` over the
production transcripts of a later week can be read, whole-sheet prints that
do not fall, or more calls per run on sheets just over the limit, bring
back the first part for a sheet under twice the limit, the list only above.
