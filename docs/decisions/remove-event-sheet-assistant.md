# The Hand-Entry Format Prompt Is Removed

Date: 2026-10-15

## Problem

`prompts/event-sheet-assistant.md` told an agent to write events for a user
who builds them in the editor by hand: each event as a Markdown table of
object, `list-name` and parameters, and every name verified with
`lookup_ace.py`. No tool or instruction file loaded it; it was reached only
through a pointer in `prompts/event-sheet-thinking.md` and the README. Its
intended reader was a chat window, the QQ bot, which does not render
Markdown tables, so the format had no display surface either.

## Evidence

A scratch project gives the same check without the prompt: `new_project.py`,
an object type file, `edit_sheet.py` and `print_sheet.py --locale` found an
unknown object, a missing animation and the missing case comments in the
prompt's own example. That route costs three hand steps per object and words
a condition from `display-text`, not the add dialog's `list-name`. No user
asked for hand-entry output, so neither the route nor a script mode for it
has a caller.

## Decision

- The prompt is deleted.
- Name verification is step 6 of `prompts/event-sheet-thinking.md`, which
  names `lookup_ace.py` directly.
- Its rule on names in one language is in `prompts/event-sheet-style.md`.
- Its sections on locale and on where data lives repeated section 2 of
  `AGENTS.md`, and went with it.
- No script prints a hand-entry format.

## Re-evaluate when

A chat surface needs events to show a user. Start from what
`print_sheet.py` prints, one line per condition and action in the editor's
wording, because it needs no table rendering.
