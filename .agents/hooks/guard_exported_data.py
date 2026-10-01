"""PreToolUse hook: keep hand edits out of the data the export writes.

`scripts/init.py` replaces `data/c3-schemas`, `c3-examples`, `c3-lang` and
`c3-ts-defs` whole on every refresh, so a hand edit there is lost on the next
release and can leave the two locales disagreeing. A change to that data is a
change to the export in `src/ingest/`, then a run of `scripts/init.py`.
Exit code 2 blocks the edit and shows stderr to the agent.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EXPORTED = ("c3-schemas", "c3-examples", "c3-lang", "c3-ts-defs")


def exported_dir(file_path: str, project: Path) -> str | None:
    path = Path(file_path)
    if not path.is_absolute():
        path = project / path
    try:
        parts = path.resolve().relative_to(project.resolve()).parts
    except ValueError:
        return None
    if len(parts) > 2 and parts[0] == "data" and parts[1] in EXPORTED:
        return parts[1]
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        # Exit 1 lets the tool run and shows the message to the user.
        print(f"{Path(__file__).name}: stdin is not a hook event, nothing checked: {error}", file=sys.stderr)
        return 1
    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    folder = exported_dir(file_path, project)
    if folder is None:
        return 0
    print(
        f"Blocked: data/{folder} is written by scripts/init.py and replaced on "
        "every refresh. Change the export in src/ingest/ and run "
        "`python scripts/init.py` instead (docs/dev/data-pipeline.md).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
