# A Clone Behind Its Upstream Fails the Check

Date: 2026-10-04

## Problem

The skill and the schemas change often, and a game project reads them from a
local clone of this repository, through a copy of the skill that `install.py`
made. `bootstrap.py` clones a repository only when its folder is missing, and
`install.py` copies the skill from the clone as it is. Neither fetches, so an
agent can work for weeks from a clone that lacks the checks and data of later
commits, and nothing tells it so.

## Decision

`check_project.py`, which the block in a game project runs at the start of
each session, fetches the clone and reports a clone that is behind its
upstream as a problem, with the commands that update it:

```
Construct3-RAG at <clone> is 3 commits behind origin/main, so the scripts lack the fixes and checks of those commits. Run git -C "<clone>" pull --ff-only, then python "<clone>/skills/construct3-agent-plugin/scripts/install.py" --into "<game>/.agents/skills", then run this check again
```

- The line is an error, so the check exits 1 and the line is the first
  problem. An agent takes the last line of a passing check, `ok: ...; next,
  ...`, for its next step (`ok_line` in `check_project.py`). Small-model
  runs in the skill evals left a warning that printed on every run unacted,
  so a warning above that last line goes unread.
- One line carries both steps: the pull, and for a game project that holds
  a copy of the skill, the `install.py` that refreshes the copy. Run from the
  clone itself (the Claude Code plugin linked to a clone, or the scripts run
  in place), the line gives the pull alone.
- A copy that differs from the clone it was made from is an error of the
  checker too, with the `install.py` command. The other scripts print it as
  their first line and go on.
- A clone that holds commits or uncommitted changes of its own gets a
  warning instead, which names them and asks the agent to tell the user. A
  pull there could merge into the user's work or refuse over it, and an
  agent told to clear an error may reset the clone to get past it.
- The check fetches the branch's remote at most once an hour per clone,
  with an eight-second limit, so that a commit pushed between two sessions
  reaches the next one. The time of the last attempt is a file in
  `construct3-rag-fetch/` of the system's temporary folder, written before
  the fetch, so that an offline machine waits once per hour and not on
  every check. A measured fetch over SSH took about 4 seconds; the checks in
  between cost one `git rev-list` and, when the clone is behind, one
  `git status`.
- Git runs with `GIT_TERMINAL_PROMPT=0` and, unless the user set
  `GIT_SSH_COMMAND`, `ssh -o BatchMode=yes`, so that a fetch that needs a
  password fails instead of waiting for input.
- Nothing is said for a clone that is not a Git repository (the plugin
  cache), a detached HEAD, a branch with no upstream, a failed fetch, or a
  clone that is only ahead.
- `CONSTRUCT3_RAG_OFFLINE` set to any value skips the check. The tests set
  it, so that a test run reads no network and its output does not depend on
  the remote.

## The Claude Code plugin

A plugin installed from the `construct3-rag` marketplace is a copy in Claude
Code's plugin cache, with no `.git`, so the check above says nothing there.
`plugin.json` has no `version`, so Claude Code takes the commit SHA as the
version and an update brings the latest commit. Claude Code updates a
plugin from a third-party marketplace on its own only when the user turns on
the marketplace's auto-update. The user can also run
`claude plugin update construct3@construct3-rag`. The README gives both
(Claude Code docs, "Keep plugins updated",
`https://code.claude.com/docs/en/plugins/install`). A `version` field would
hold every user on the cached copy until the string changes.

## Trade-offs

- The checker is not fully offline. The network rule of `AGENTS.md`
  section 5 covers the data path and the lookup service; this fetch is
  limited to the checker and can be turned off.
- The checker does not pull: the clone belongs to the user, and the line
  hands the pull to the agent only where it fast-forwards a clone with no
  work of its own.
- A clone behind its upstream fails a check whose project is sound. The
  failure lasts one round trip, the pull and the refresh, and the check
  that follows reads the project with the current rules.
- An eval run follows the line too, so fixtures come from a clone that does
  not trail its upstream (`skills/AGENTS.md`, "Evals").
- Only Construct3-RAG is checked. The sibling clones change rarely, and
  their content reaches the agent through this repository's data.
- A commit reaches users only after it is pushed: the check compares with
  the remote.
