"""The checker's line about a Construct3-RAG clone that is behind its upstream,
against a bare repository on disk as the upstream."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.skill_helpers import SKILL

sys.path.insert(0, str(SKILL / "scripts"))
import c3project as c3  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git is not installed")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True)


@pytest.fixture
def clones(tmp_path, monkeypatch) -> tuple[Path, Path]:
    """A clone the checker reads and another one that pushes to their upstream."""
    monkeypatch.delenv("CONSTRUCT3_RAG_OFFLINE", raising=False)
    monkeypatch.setattr(c3, "FETCH_STAMPS", tmp_path / "stamps")
    upstream, mine, other = tmp_path / "upstream.git", tmp_path / "mine", tmp_path / "other"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(upstream))
    git(tmp_path, "clone", "-q", str(upstream), str(mine))
    git(mine, "commit", "-q", "--allow-empty", "-m", "first")
    git(mine, "push", "-q", "-u", "origin", "main")
    git(tmp_path, "clone", "-q", str(upstream), str(other))
    return mine, other


def test_up_to_date_says_nothing(clones):
    mine, _ = clones
    assert c3.clone_behind(mine) is None


def test_behind_names_the_count_and_the_pull(clones):
    mine, other = clones
    git(other, "commit", "-q", "--allow-empty", "-m", "second")
    git(other, "push", "-q")
    note = c3.clone_behind(mine)
    assert note and "is 1 commit behind origin/main" in note and f'git -C "{mine}" pull --ff-only' in note


def test_fetched_once_a_period(clones):
    """A fetch in the period is not repeated; the line reads what the last fetch brought."""
    mine, other = clones
    assert c3.clone_behind(mine) is None
    git(other, "commit", "-q", "--allow-empty", "-m", "second")
    git(other, "push", "-q")
    assert c3.clone_behind(mine) is None


def test_offline_or_untracked_says_nothing(clones, monkeypatch):
    mine, other = clones
    git(other, "commit", "-q", "--allow-empty", "-m", "second")
    git(other, "push", "-q")
    git(mine, "fetch", "-q")
    monkeypatch.setenv("CONSTRUCT3_RAG_OFFLINE", "1")
    assert c3.clone_behind(mine) is None
    monkeypatch.delenv("CONSTRUCT3_RAG_OFFLINE")
    git(mine, "switch", "-q", "--detach")
    assert c3.clone_behind(mine) is None
    assert c3.clone_behind(mine.parent) is None
