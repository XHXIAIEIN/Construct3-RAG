# The Update Pull Request Reports the Release and Waits When It Breaks a Quoted Id

Date: 2026-10-02
Schema: Construct 3 r495.2

## Problem

The update workflow refreshed `data/` for a new Construct release, opened a
pull request whose body was the two release names, and merged it once checks
passed. Nobody saw which addons and ACEs the release added, removed,
deprecated or changed. The repository quotes ACE ids in many places outside
`data/`: the prompts and pitfalls, the `construct3-agent-plugin` skill's checker,
generator and references, the lookup's aliases, the docs. A release that
removes or retypes one of them leaves those places wrong with no failing
check, since only the tests are run and most of these files have none.

## Evidence

Comparing the r476.2 export kept in the CDN cache with the committed r495.2
data finds removed ACEs (the 3D model's rotation expressions), addons and
ACEs the editor deprecated in between, and parameters retyped. Several of
these ids are quoted in the skill's scripts and in the prompts. The two
exports differ in exporter version as well, so the count of changes there
overstates what one release does; the kinds of change are what matter.

## Options

- **Body only, merge as before.** Every release gets a readable report, but
  a breaking one still lands unattended.
- **Hold every release for review.** Safe, but a release that only adds
  ACEs, as most releases do, waits for a person although nothing the
  repository quotes can break.
- **Hold only when a quoted id is affected.** The report lists every quoted
  or backticked mention of an id the release removed, deprecated, or changed
  in a way that can break an event written for the old ACE; auto-merge is
  enabled only when the report lists no mention.

## Decision

The third. `scripts/schema_diff.py` writes the report against the data on
`main` and sets `needs_review`; the workflow uses the report as the pull
request body and skips auto-merge when `needs_review` is true.

What counts as breaking: a parameter removed, added or retyped, a combo item
gone, the parameter order changed, or one of `isTrigger`, `isLooping`,
`isInvertible`, `isCompatibleWithTriggers`, `isAsync`, `returnType` changing
from a recorded value. A rename, a new combo item, a `scriptName` change and
a field the old export did not record are reported but do not hold the
merge: the watched files quote ids, and none of those changes an id's
meaning in an event.

Mentions are found by the id between quotes or backticks, not by display
names: ids are what code and the prompts' examples quote, and names are
reworded between releases without effect. Tests are not scanned, since the
suite runs in the pull request and fails on its own. A short id such as `x`
may match a quote that is not about the ACE; the report says an id shared by
several addons may belong to another one, and a person decides.

## Re-evaluate when

- A breaking release merges with a quoted id the report missed, such as one
  written without quotes or by display name.
- Holding pull requests for mentions that turn out unrelated becomes the
  usual case rather than the exception.
