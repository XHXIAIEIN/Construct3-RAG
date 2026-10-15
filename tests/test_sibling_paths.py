"""A test finds a sibling clone beside the main working tree.

In a worktree, REPO.parent is the main clone's .claude/worktrees folder, so a
sibling path built from it never exists and its test skips in every worktree
session. scripts/example_usage.py builds it from the main working tree, which
`git rev-parse --git-common-dir` gives.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SIBLING_FROM_PARENT = re.compile(r"\b(?:REPO|ROOT)\.parent\s*/")


def test_no_test_builds_a_sibling_path_from_the_repository_parent():
    found = [
        f"{path.name}:{number}: {line.strip()}"
        for path in sorted(TESTS.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if SIBLING_FROM_PARENT.search(line) and path != Path(__file__).resolve()
    ]
    assert not found, "build a sibling path from the main working tree, as scripts/example_usage.py does:\n" + "\n".join(found)
