"""A test finds a sibling clone the way the skill's scripts do.

In a worktree, REPO.parent is the main clone's .claude/worktrees folder, so a
sibling path built from it never exists and its test skips in every worktree
session. skill_helpers.EXAMPLES builds it from siblings_folder instead.
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
    assert not found, "use siblings_folder(REPO), as tests/skill_helpers.py does:\n" + "\n".join(found)
