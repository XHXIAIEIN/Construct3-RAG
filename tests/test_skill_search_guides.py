"""search_guides.py: the pitfall entries and official examples that hold the words."""
from tests.skill_helpers import REPO, tool


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
