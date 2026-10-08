"""A failed check fails the job of .github/workflows/checks.yml.

The run step continues on error, so the Report step after it can read the log.
The job then fails only if its last step exits 1. If that step goes, or
`set -o pipefail` goes (the run step would then take the exit code of `tee`,
not of the checks), a failing check passes the job."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "checks.yml"
STEP = "      - "          # a step's first line, under "    steps:" of the one job


def steps() -> list[str]:
    """The text of each step of the job, in order. PyYAML is not among the test
    requirements, and the file's indentation is fixed."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index("    steps:") + 1
    blocks: list[list[str]] = []
    for line in lines[start:]:
        if line.strip() and not line.startswith("      "):
            break
        if line.startswith(STEP):
            blocks.append([])
        if blocks:
            blocks[-1].append(line)
    return ["\n".join(block) for block in blocks]


def key(step: str, name: str) -> str | None:
    """The value of a step's one-line key."""
    match = re.search(rf"^\s*(?:- )?{re.escape(name)}:[ \t]*(.*)$", step, re.MULTILINE)
    return match.group(1).strip() if match else None


def test_a_failed_check_fails_the_job():
    all_steps = steps()
    run = next(s for s in all_steps if "python -m pytest" in s)
    run_id = key(run, "id")
    assert run_id, "the step that runs the checks needs an id for the last step to read its outcome"
    assert key(run, "continue-on-error") == "true"
    assert "set -o pipefail" in run, "without pipefail the step's outcome is tee's, which succeeds"

    last = all_steps[-1]
    assert key(last, "if") == f"steps.{run_id}.outcome == 'failure'", "the last step reads the checks' outcome"
    assert key(last, "run") == "exit 1"
