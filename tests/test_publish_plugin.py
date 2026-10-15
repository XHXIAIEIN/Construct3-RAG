"""publish_plugin.py makes the plugin/ of a clone of the plugin repository equal to plugin/ here, writes its
marketplace manifest, leaves the clone's other files alone, and refuses a folder that is not such a clone
(docs/decisions/plugin-repository.md)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build_plugin, publish_plugin
from tests.skill_helpers import REPO


def git(folder: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True)


@pytest.fixture
def small_plugin(tmp_path, monkeypatch):
    """A two-file plugin folder in place of plugin/."""
    out = tmp_path / "plugin"
    (out / ".claude-plugin").mkdir(parents=True)
    manifest = {"name": "construct3", "version": "1.2.3", "description": "A plugin.", "author": {"name": "XHXIAIEIN"}}
    (out / ".claude-plugin" / "plugin.json").write_bytes(json.dumps(manifest).encode())
    (out / "skills").mkdir()
    (out / "skills" / "SKILL.md").write_bytes(b"# Skill\n")
    monkeypatch.setattr(build_plugin, "OUT", out)
    return out


@pytest.fixture
def clone(tmp_path):
    """A clone of a bare repository named as the plugin repository: a README of its own, and an old plugin/
    with a file the plugin no longer has."""
    bare = tmp_path / "Construct3-Agent-Skills.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(bare), str(clone))
    git(clone, "config", "user.name", "test")
    git(clone, "config", "user.email", "test@example.com")
    (clone / "README.md").write_bytes(b"# The repository's own file\n")
    (clone / "plugin" / "stray").mkdir(parents=True)
    (clone / "plugin" / "stray" / "old.txt").write_bytes(b"old\n")
    (clone / "plugin" / "skills").mkdir()
    (clone / "plugin" / "skills" / "SKILL.md").write_bytes(b"# Old skill\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "old")
    git(clone, "push", "-q", "origin", "HEAD:main")
    return clone


def test_sync_makes_the_plugin_folder_equal_and_leaves_the_rest_of_the_clone(small_plugin, clone):
    files = publish_plugin.wanted()
    assert set(files) == {"plugin/.claude-plugin/plugin.json", "plugin/skills/SKILL.md", ".claude-plugin/marketplace.json"}
    market = json.loads(files[".claude-plugin/marketplace.json"])
    assert market["plugins"] == [{"name": "construct3", "source": "./plugin", "description": "A plugin.",
                                  "category": "game-development"}]
    assert sorted(publish_plugin.changes(clone, files)) == sorted(
        ["write plugin/.claude-plugin/plugin.json", "write .claude-plugin/marketplace.json",
         "write plugin/skills/SKILL.md", "remove plugin/stray/old.txt"])
    publish_plugin.sync(clone, files)
    assert {rel: p.read_bytes() for rel, p in publish_plugin.held(clone).items()} == files
    assert not (clone / "plugin" / "stray").exists()
    assert (clone / "README.md").read_bytes() == b"# The repository's own file\n"
    assert publish_plugin.changes(clone, files) == []


def test_the_command_refuses_a_folder_that_is_not_the_plugin_repository(tmp_path):
    other = tmp_path / "other"
    git(tmp_path, "init", "-q", str(other))
    git(other, "remote", "add", "origin", "git@github.com:someone/elsewhere.git")
    p = subprocess.run([sys.executable, str(REPO / "scripts" / "publish_plugin.py"), "--clone", str(other), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert p.returncode == 1
    assert "not XHXIAIEIN/Construct3-Agent-Skills" in p.stdout or "differs from a fresh build" in p.stdout
