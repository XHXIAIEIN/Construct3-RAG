# The Check Loop Stays Inside the First 5000 Tokens of SKILL.md

Date: 2026-10-16
Schema: Construct 3 r495.2

## Problem

Claude Code keeps a skill across a compaction by re-attaching it: "Claude
Code re-attaches the most recent invocation of each skill after the
summary, keeping the first 5,000 tokens of each. Re-attached skills share a
combined budget of 25,000 tokens", filled from the most recently invoked
skill (<https://code.claude.com/docs/en/skills>, "Skill content
lifecycle"). The body of `skills/construct3-agent-plugin/SKILL.md` ran
past that budget, and "Check after every change" was its last section but
one. So the first compaction of a long session dropped the six steps of
the check loop, the `stop:` rule and the hand-over order, and kept the
sections on looking an ACE up and reading a sheet. The recorded eval
transcripts hold no compaction (`evals/token_share.py`), so the evals
never showed it.

`skills/AGENTS.md` credited the 5000 tokens to "the specification". The
Agent Skills specification sets no token budget. The 500-line rule is
Anthropic's skill guidance ("Keep SKILL.md under 500 lines", the same page,
"Add supporting files"); the 5000 tokens are Claude Code's re-attach.

## Evidence

Which tokenizer the cut uses is not published. Two proxies were at hand:

- tiktoken's `cl100k_base`: about 4.06 characters a token on this file.
  Claude Code's count is Claude's, not OpenAI's.
- Anthropic's glossary
  (<https://platform.claude.com/docs/en/about-claude/glossary>, "Tokens"):
  on the models before Claude 4.7 a token is about 3.5 English characters,
  and Claude 4.7 and later produce about 30 percent more tokens for the
  same text. So about 2.7 characters a token on the models the user runs,
  half again the cl100k count.

A direct measurement, `claude -p` with and without the body and the
difference of the usage, needs a signed-in CLI or an API key. Until one
measures it, the test estimates at 2.7 characters a token, the
conservative proxy, and prints the cl100k count beside it so the numbers
compare with earlier measurements.

The body before and after this change, in tokens at 2.7 characters a token
(the cl100k count in brackets):

| | Before | After |
|--|--------|-------|
| The body | 9536 (6336) | 7181 (4762) |
| Where "Check after every change" ends | 9008 (6000) | 4886 (3246) |
| What the 5000-token cut leaves out | from "Read a sheet as events" on, the check loop included | the three sections on the tools and the generator |

What the body held and where it went:

- The grammar of a plan for `edit_sheet.py`: the operations, where new
  events go, what an event carries, how `replace` and sub-events behave,
  the comment rules the script refuses on. It is the `operations:` and
  `what is checked:` parts of `edit_sheet.py --help`, read once before the
  first plan. `SKILL.md` keeps the rule every change needs: a plan, numbers
  of the current print with `"line"`, nothing written unless the whole
  plan holds, `--dry-run`.
- Rows of the Scripts table repeated flags and outputs that each script's
  `--help` lists; the rows keep what picks the script. Two earlier trims of
  this kind lost nothing in the evals (`project-tools-skill.md`, "What
  holds the design in place": iterations 35, 64 and 65).
- Step 5 of the check loop repeated `--headed`, `--state` and exit code 3
  from the `open_in_editor.py` row and its `--help`. The optional design
  review batches of steps 2 and 4 are reached through the
  `review_design.py` row and `references/design-review.md`.
- The sentence on editing `tools/build_project.py` in place moved from
  "Before the first command" to "Generate a whole project", where the
  generator is.

## Options

1. Keep the order and bring the whole body under 5000 cl100k tokens.
   Moving the plan grammar alone gets there by cl100k. By the 2.7 estimate
   the loop still ends about 7200 tokens in, so on the models the user runs
   the first compaction still drops it.
2. Put "Check after every change" right after the Scripts table, and hold
   its end, not the body's, inside 5000 tokens at 2.7 characters a token.
   What follows it teaches tools whose output teaches it again: a lookup
   prints the `write:` line, a print the numbered events, `edit_sheet.py
   --help` the plan, and a compacted session has run them already. It
   costs the trims listed above beyond the move.
3. Keep the order and bring the whole body under 5000 tokens at 2.7
   characters a token: about half the body. Every section loses a third or
   more, and no eval can run here to show what that costs.
4. Measure Claude's count first and decide after. The measurement needs a
   login this machine lacks, and the loop is dropped meanwhile.

## Decision

Option 2. `tests/test_skill_spec.py` holds it:
`test_the_check_loop_survives_a_compaction` fails when the end of "Check
after every change" passes 5000 tokens at 2.7 characters a token, and
names the line of the cut and the sections after it. The 500-line test
stays, credited to Anthropic's guidance. `skills/AGENTS.md` names both
sources.

The order of `SKILL.md` is: what to do before the first command, the
Scripts table, the check loop, the three sections on the tools, the
generator. The loop's end sits about a hundred tokens under the budget, so
the next sentence the loop needs moves one out, as the rule in
`skills/AGENTS.md` says.

## Re-evaluate when

- A signed-in `claude` CLI or an API key is at hand: measure the body with
  `claude -p` twice, with and without it, and replace 2.7 with the measured
  ratio in the test and here.
- An eval iteration runs on the reordered text (`skills/AGENTS.md`,
  "Evals"): the trims rest on the earlier iterations, not on a run of this
  text.
- The Claude Code page changes the 5000 or the 25,000, or names the
  tokenizer.
- A compaction appears in a recorded transcript: `evals/token_share.py`
  can then show what was re-attached.
