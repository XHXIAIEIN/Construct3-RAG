"""The checker's line about a Construct3-RAG clone that is behind its upstream,
against a bare repository on disk as the upstream."""
from pathlib import Path

import pytest

from tests.skill_helpers import NEEDS_GIT, git, script_module

c3 = script_module("c3project")

pytestmark = NEEDS_GIT


@pytest.fixture
def clones(tmp_path, monkeypatch) -> tuple[Path, Path]:
    """A clone the checker reads and another one that pushes to their upstream."""
    monkeypatch.delenv("CONSTRUCT3_RAG_OFFLINE", raising=False)
    monkeypatch.setattr(c3, "FETCH_STAMPS", tmp_path / "stamps")
    upstream, mine, other = tmp_path / "upstream.git", tmp_path / "mine", tmp_path / "other"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    git(tmp_path, "clone", "-q", str(upstream), str(mine))
    (mine / "notes.txt").write_text("first\n", encoding="utf-8")
    git(mine, "add", "notes.txt")
    git(mine, "commit", "-q", "-m", "first")
    git(mine, "push", "-q", "-u", "origin", "main")
    git(tmp_path, "clone", "-q", str(upstream), str(other))
    return mine, other


def push_one(other: Path) -> None:
    git(other, "commit", "-q", "--allow-empty", "-m", "second")
    git(other, "push", "-q")


def test_up_to_date_says_nothing(clones):
    mine, _ = clones
    assert c3.clone_behind(mine) is None


def test_behind_gives_the_pull_for_the_agent(clones):
    mine, other = clones
    push_one(other)
    line, agent_updates = c3.clone_behind(mine)
    assert agent_updates and "is 1 commit behind origin/main" in line
    assert f'git -C "{mine}" pull --ff-only, then run this check again' in line


def test_behind_with_a_copy_of_the_skill_gives_its_refresh_too(clones, monkeypatch):
    """One line takes the agent through both steps, instead of a second check finding the copy stale."""
    mine, other = clones
    push_one(other)
    monkeypatch.setattr(c3, "refresh_command", lambda rag: "python install.py --into skills")
    line, agent_updates = c3.clone_behind(mine)
    assert agent_updates and "pull --ff-only, then python install.py --into skills, then run this check again" in line


@pytest.mark.parametrize("own", ["commit", "change"])
def test_behind_with_the_users_own_work_is_the_users(clones, own):
    """A pull could merge into or refuse over the user's work: the line asks for the user, not the pull."""
    mine, other = clones
    push_one(other)
    if own == "commit":
        git(mine, "commit", "-q", "--allow-empty", "-m", "mine")
    else:
        (mine / "notes.txt").write_text("edited\n", encoding="utf-8")
    line, agent_updates = c3.clone_behind(mine)
    assert not agent_updates and "is 1 commit behind origin/main" in line and "pull" not in line
    assert ("1 commit of its own" if own == "commit" else "uncommitted changes of its own") in line
    assert "tell the user" in line


def test_fetched_once_a_period(clones):
    """A fetch in the period is not repeated; the line reads what the last fetch brought."""
    mine, other = clones
    assert c3.clone_behind(mine) is None
    push_one(other)
    assert c3.clone_behind(mine) is None


def test_offline_or_untracked_says_nothing(clones, monkeypatch):
    mine, other = clones
    push_one(other)
    git(mine, "fetch", "-q")
    monkeypatch.setenv("CONSTRUCT3_RAG_OFFLINE", "1")
    assert c3.clone_behind(mine) is None
    monkeypatch.delenv("CONSTRUCT3_RAG_OFFLINE")
    git(mine, "switch", "-q", "--detach")
    assert c3.clone_behind(mine) is None
    assert c3.clone_behind(mine.parent) is None
