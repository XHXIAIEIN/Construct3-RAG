# A Game Project's Long Documents Are Read in Parts

Date: 2026-10-14

## Problem

A game project made with this repository often keeps its design in
Markdown files next to the project. An agent reads such a file whole, and
the whole file then stays in the context: each later turn of the session
reads it again from the cache. A session that runs for hundreds of turns
pays for that one read hundreds of times.

Task: an agent in a game project reads only the part of a long document
that its work needs.

## Evidence

The cost of every Claude Code transcript of one game project's sessions
(425 transcripts, 28,858 responses) was shared out among what filled each
response's context, from the usage the API returned: the growth of the
context between two responses is what was added in between, and each item
costs its first write plus a cache read on every later response
(`skills/construct3-agent-plugin/evals/token_share.py`). The shares add up
to the cost computed from the usage directly.

- Whole reads of the project's design and plan documents were 10.7% of all
  cost, the largest item after the starting context. The two document
  folders held about 920,000 characters each, mostly Chinese; the largest
  file was about 119,000 characters.
- 59% of the responses ran with more than 200,000 tokens of context, so an
  early whole read was read again many times.
- Reads of this repository's own references and prompts were about 3%.

## Options

1. Leave reading to the agent. The measured habit is the whole file.
2. A line in the block: list a long file's headings first, then read the
   section. Every session of the project reads the block, and the rule
   costs about 70 tokens there.
3. A script that prints a section by heading. It adds a tool for a task
   that `grep -n '^#'` and a ranged read already do.
4. Split the project's documents. That is the project's own choice; the
   block cannot make it.

## Decision

Option 2. The rule names the project's own long Markdown files and gives
the command for Bash and for PowerShell. It leaves out the files of this
repository that the block's table names: each says what to read next, and
the wording of `prompts/event-sheet-thinking.md` has changed what a small
model writes, so reading it in parts is a separate decision that needs an
eval.

The context-size setting of Claude Code (`autoCompactWindow`) cannot come
from here: a plugin's `settings.json` takes only `agent` and
`subagentStatusLine`, and `install.py` writes no settings file. A project
sets it in its own `.claude/settings.json`.

## Re-evaluate when

The same measurement over the project's sessions after the block is in
place shows no drop in whole reads of its documents, or an agent misses a
rule because it read only part of a document.
