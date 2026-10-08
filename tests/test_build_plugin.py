"""The version build_plugin.py writes into plugin.json: the published one while the plugin's files are
the published files, its patch raised by one once they differ, never below the floor
(docs/decisions/plugin-tracks-commits.md)."""
from pathlib import Path

from scripts import build_plugin
from scripts.build_plugin import release_version
from tests.skill_helpers import NEEDS_GIT, git

PUBLISHED = {"README.md": "a1", "skills/x/SKILL.md": "b1"}


def test_no_published_version_gives_the_floor():
    assert release_version(None, {}, PUBLISHED, "1.1.0") == "1.1.0"


def test_the_published_files_keep_the_published_version():
    """A fresh clone, where the published plugin is the one in HEAD."""
    assert release_version("1.1.0", PUBLISHED, dict(PUBLISHED), "1.1.0") == "1.1.0"


def test_changed_files_raise_the_patch_once_however_often_the_branch_builds():
    """Each build of a branch compares with the same published plugin, not with the last build."""
    first = {**PUBLISHED, "README.md": "a2"}
    again = {**first, "skills/x/SKILL.md": "b2"}
    assert release_version("1.1.0", PUBLISHED, first, "1.1.0") == "1.1.1"
    assert release_version("1.1.0", PUBLISHED, again, "1.1.0") == "1.1.1"


def test_a_branch_merged_after_another_was_published_takes_the_next_patch():
    """Two branches both write 1.1.1; once one is published, the other's merge differs from it."""
    published_branch = {**PUBLISHED, "README.md": "a2"}
    merged = {**published_branch, "skills/x/SKILL.md": "b2"}
    assert release_version("1.1.1", published_branch, merged, "1.1.0") == "1.1.2"


def test_a_higher_floor_wins_and_versions_compare_as_numbers():
    assert release_version("1.0.0", {}, PUBLISHED, "1.1.0") == "1.1.0"
    assert release_version("1.1.4", PUBLISHED, PUBLISHED, "2.0.0") == "2.0.0"
    assert release_version("1.9.0", PUBLISHED, {}, "1.10.0") == "1.10.0"
    assert release_version("1.10.0", PUBLISHED, {}, "1.9.0") == "1.10.1"


def test_blob_id_is_the_id_git_gives():
    assert build_plugin.blob_id(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def commit(repo: Path, files: dict[str, bytes], message: str) -> None:
    for rel, data in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(data)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@NEEDS_GIT
def test_published_reads_the_commit_shared_with_origin_main_or_head(tmp_path, monkeypatch):
    monkeypatch.setattr(build_plugin, "ROOT", tmp_path)
    git(tmp_path, "init", "-q", "-b", "main")
    commit(tmp_path, {".claude-plugin/plugin.json": b'{"version": "1.0.0"}\n'}, "the plugin in the root")
    git(tmp_path, "switch", "-q", "-c", "pushed")
    commit(tmp_path, {"plugin/.claude-plugin/plugin.json": b'{"version": "1.1.0"}\n',
                      "plugin/README.md": b"hello\n"}, "the plugin in plugin/")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(tmp_path, "switch", "-q", "main")
    commit(tmp_path, {"plugin/README.md": b"local\n"}, "a local change")
    in_plugin = ("1.1.0", {"README.md": build_plugin.blob_id(b"hello\n")})
    # HEAD and origin/main share the first commit, which holds the plugin in the root and no plugin/
    assert build_plugin.published() == ("1.0.0", {})
    # Merging origin/main stops on a conflict in plugin/; the merge commit will share origin/main
    git(tmp_path, "merge", "-q", "origin/main", check=False)
    assert (tmp_path / ".git" / "MERGE_HEAD").exists()
    assert build_plugin.published() == in_plugin
    git(tmp_path, "merge", "--abort")
    # No origin/main: HEAD, without its manifest among the files
    git(tmp_path, "update-ref", "-d", "refs/remotes/origin/main")
    git(tmp_path, "switch", "-q", "pushed")
    assert build_plugin.published() == in_plugin
