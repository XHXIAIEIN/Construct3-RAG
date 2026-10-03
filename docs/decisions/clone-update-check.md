# The Checker Says When the Clone Is Behind Its Upstream

Date: 2026-10-04

## Problem

The skill and the schemas change often, and a game project reads them from a
local clone of this repository. `bootstrap.py` clones a repository only when
its folder is missing, and `install.py` copies the skill from the clone as it
is. Neither fetches, so an agent can work for weeks from a clone that lacks
the checks and data of later commits, and nothing tells it so.

## Decision

`check_project.py`, which the block in a game project runs at the start of
each session, warns when the clone's branch is behind its upstream:

```
warning: Construct3-RAG at <clone> is 3 commits behind origin/main; update it: git -C "<clone>" pull --ff-only, then run this check again
```

- The check fetches the branch's remote at most once every six hours per
  clone, with an eight-second limit. The time of the last attempt is a file
  in `construct3-rag-fetch/` of the system's temporary folder, written before
  the fetch, so that an offline machine waits once per period and not on
  every check. A measured fetch over SSH took about 4 seconds; the checks in
  between cost one `git rev-list`.
- Git runs with `GIT_TERMINAL_PROMPT=0` and, unless the user set
  `GIT_SSH_COMMAND`, `ssh -o BatchMode=yes`, so that a fetch that needs a
  password fails instead of waiting for input.
- Nothing is said for a clone that is not a Git repository (the plugin
  cache), a detached HEAD, a branch with no upstream, a failed fetch, or a
  clone that is only ahead.
- `CONSTRUCT3_RAG_OFFLINE` set to any value skips the check. The tests set
  it, so that a test run reads no network and its output does not depend on
  the remote.
- The line asks for the pull; the checker does not pull. After the pull, the
  existing line about a copy that differs from the clone's skill gives the
  `install.py` command.

## Trade-offs

- The checker is no longer fully offline. The network rule of `AGENTS.md`
  section 5 covers the data path and the lookup service; this fetch is
  limited to the checker and can be turned off.
- Pulling in the checker was rejected: the clone may hold the user's own
  commits or uncommitted work, and a pull belongs to the user or the agent
  that reads the line.
- Only Construct3-RAG is checked. The sibling clones change rarely, and
  their content reaches the agent through this repository's data.
- A commit reaches users only after it is pushed: the check compares with
  the remote.
