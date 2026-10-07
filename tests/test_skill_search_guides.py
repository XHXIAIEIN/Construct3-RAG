"""search_guides.py: the pitfall entries and official examples that hold the words."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.skill_helpers import REPO, SKILL, run, tool


def test_the_entry_with_most_of_the_words_comes_first_in_full(built):
    """Words about a click on a button with another behind it print the entry on Pick top/bottom first,
    without its sources."""
    code, out = tool(built, "search_guides", "click", "button", "behind", "--examples", "0")
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "pitfalls:" and lines[1].startswith(f"{REPO.as_posix()}/prompts/pitfalls/input.md:")
    assert "*Pick top/bottom* (top)" in lines[2]
    assert "[manual:" not in out


def test_examples_print_the_command_that_reads_their_events(built):
    code, out = tool(built, "search_guides", "snake", "--pitfalls", "0")
    assert code == 0 and out.startswith("examples:\ntemplate-snake: ") or "\ntemplate-snake: " in out
    assert "print_sheet.py --project" in out or "editor.construct.net/#open=" in out


def test_examples_take_the_locale_and_a_miss_says_what_to_try(built):
    code, out = tool(built, "search_guides", "贪吃蛇", "--locale", "zh-CN", "--pitfalls", "0")
    assert code == 0 and "template-snake: " in out
    code, out = tool(built, "search_guides", "xyzzy")
    assert code == 1 and out.startswith("nothing holds xyzzy; try fewer words")


def fake_rag(folder: Path, snake: bool = False) -> Path:
    """A folder that the scripts take for Construct3-RAG. With snake, it also holds the metadata file of the
    snake example."""
    (folder / "data" / "c3-schemas").mkdir(parents=True)
    (folder / "data" / "c3-schemas" / "_index.json").write_text("{}", encoding="utf-8")
    if snake:
        (folder / "data" / "c3-examples" / "en-US").mkdir(parents=True)
        (folder / "data" / "c3-examples" / "en-US" / "template-snake.json").write_text(
            json.dumps({"id": "template-snake", "name": "Snake", "description": "A snake game.",
                        "open": "https://editor.construct.net/#open=template-snake"}), encoding="utf-8")
    return folder


def snake_output(rag: Path, cwd: Path) -> str:
    code, out = run(cwd, SKILL / "scripts" / "search_guides.py", "snake", "--pitfalls", "0", "--rag", str(rag))
    assert code == 0, out
    return out


def test_examples_are_found_beside_the_clone_when_the_scripts_run_from_its_plugin_folder(tmp_path):
    """Linked into ~/.claude/skills/ as the Claude Code plugin, <clone>/plugin holds the data/ that the
    scripts use. The example projects lie beside <clone>, not beside plugin/."""
    fake_rag(tmp_path / "Construct3-RAG")
    plugin = fake_rag(tmp_path / "Construct3-RAG" / "plugin", snake=True)
    example = tmp_path / "Construct-Example-Projects" / "example-projects" / "template-snake"
    example.mkdir(parents=True)
    out = snake_output(plugin, tmp_path)
    assert f'print_sheet.py --project "{example}"' in out, out


@pytest.mark.skipif(not shutil.which("git"), reason="git is not installed")
def test_examples_are_found_beside_the_main_working_tree_from_a_git_worktree(tmp_path):
    """A worktree of the clone lies inside it, under .claude/worktrees/, and the worktree has its own plugin/
    folder. The example projects lie beside the main working tree, which the worktree's .git file and the
    commondir file in its git folder lead to. Both folders must find them."""
    main = tmp_path / "Construct3-RAG"
    main.mkdir()
    for args in (("init", "-q"), ("commit", "-q", "--allow-empty", "-m", "first"),
                 ("worktree", "add", "-q", "-b", "agent", str(main / ".claude" / "worktrees" / "agent"))):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=main, check=True,
                       capture_output=True, timeout=60)
    worktree = fake_rag(main / ".claude" / "worktrees" / "agent", snake=True)
    plugin = fake_rag(worktree / "plugin", snake=True)
    example = tmp_path / "Construct-Example-Projects" / "example-projects" / "template-snake"
    example.mkdir(parents=True)
    for rag in (worktree, plugin):
        out = snake_output(rag, tmp_path)
        assert f'print_sheet.py --project "{example}"' in out, (rag, out)


def test_examples_without_the_clone_say_how_to_get_it(tmp_path):
    """Without the examples clone each example shows its editor URL, and one line names the clone."""
    rag = fake_rag(tmp_path / "Construct3-RAG", snake=True)
    (rag / "scripts").mkdir()
    (rag / "scripts" / "bootstrap.py").write_text("", encoding="utf-8")
    out = snake_output(rag, tmp_path)
    assert "https://editor.construct.net/#open=template-snake" in out, out
    assert (f"(no Construct-Example-Projects clone at {tmp_path / 'Construct-Example-Projects'}; "
            f"python {(rag / 'scripts' / 'bootstrap.py').as_posix()} clones it") in out, out
    plugin = fake_rag(tmp_path / "Plugin", snake=True)
    assert (f'git clone --depth 1 https://github.com/Scirra/Construct-Example-Projects '
            f'"{(tmp_path / "Construct-Example-Projects").as_posix()}" clones it') in snake_output(plugin, tmp_path)
