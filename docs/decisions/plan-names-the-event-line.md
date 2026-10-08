# A Plan Names Each Event by Its Number and Its Printed Line

Date: 2026-10-08
Schema: Construct 3 r495.2

## Problem

A plan of `edit_sheet.py` names events by the numbers `print_sheet.py`
printed. A number from an older print, or a miscounted one, names another
event. The plan then changes, replaces or removes that event, passes the
checker and is written. The hash that `print_sheet.py` keeps catches a save
between the print and the plan. But `edit_sheet.py` keeps the new hash after
its own write, so it does not catch a second plan that uses the first print's
numbers after the first plan was written. It also does not catch a
miscounted number.

## Evidence

- The skill's eval runs (iterations 36 to 47) hold 14 runs that wrote a
  second plan after a first one was written, without a full print in
  between. Every number in them was right. Eight came from the first plan's
  output, which prints the changed events under their new numbers. Six came
  from a print that the first plan had not shifted. In four of the runs, the
  first print's number would have named another event.
- Over the official examples, an event one to three numbers away from
  another prints the same first line about 3 times in 100. A stale number
  passes a check by line only when it lands on such an event.

## Options

1. A hash of the sheet on the first line of the print, which the plan
   carries. It catches every change since the print. It also refuses every
   plan that follows the agent's own write until the agent prints again: in
   the 14 runs, 14 refusals and none needed. If `edit_sheet.py` printed the
   new hash to spare them, an agent could carry that hash with a number from
   the first print, which is the case the hash is for.
2. The line that the print shows for the event, carried by the operation
   that names it. It checks the event that each operation changes, whatever
   moved it: an earlier plan, a save in the editor or a miscount. The agent
   copies the line from beside the number it reads, in a print or in a
   plan's output. A stale number that lands on an event with the same line
   passes.
3. The event's sid. The default print shows none, so the agent reads the
   sheet a second time with `--outline` or `--show`.
4. A stored value that the tool updates to the current sheet. This removes
   the check.

## Decision

Option 2. The hash of the print stays, for a save between the print and the
plan.

- `"line"` belongs to the event that the operation's number names: for
  `move`, the event that moves, and for `after`, `before` and `into`, the
  event the new ones go beside or into. `"into": 0` is the sheet and takes no
  line.
- A line matches when it is one of the lines that the event prints above its
  actions, or a part of one, or of them all in a row. The number, the indent
  and the marks of the print (`[sub-events 4-6]`, `[event disabled]`) do not
  count. The lines are first compared in the locale of the run and then in
  the schemas' other locales, so a line copied from a print with
  `--locale zh-CN` names its event in a run without that option.
- A line that does not match refuses the plan. The message first gives the
  numbers of the events that print the given line now, then the line that
  the plan's number prints. The fix is the number, and a line copied from
  the message would pass the check.
- A plan without `"line"` is carried out, and a `note:` names its operations
  with an example made from the first one. The field stays optional because
  the checker's findings name a place by its number alone, `sheet Game event
  5 condition 1`, and the plans and evals written before it carry none.
- The ready-made operation in the note about a text left in its older form
  carries the line of its event.
- `edit_sheet.py` never writes a plan's line from the sheet, because a value
  that the tool makes current protects nothing.

## Re-evaluate when

- A run is refused for a line that it copied right: a mark or a wording that
  the comparison does not ignore.
- A stale plan lands on an event that prints the same line: carry the first
  action too, or two lines.
- The checker's findings print the line of the event they name: make
  `"line"` required, after an eval shows runs writing it.
