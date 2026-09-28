"""The shape of the event sheet pitfalls: an index and its topic files.

The index keeps Picking and Triggers and Else in full and gives every other
group one conclusion line per pitfall, pointing at the topic file under
prompts/pitfalls/ that holds the pitfall with its cases and its source.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROMPTS = REPO / "prompts"
INDEX = PROMPTS / "event-sheet-pitfalls.md"
TOPICS = PROMPTS / "pitfalls"

LINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")
# A source is a bracketed span that is not a Markdown link's text.
SOURCE = re.compile(r"\[[^\]]+\](?!\()")


def bullets(text: str) -> list[str]:
    """Top-level list entries, each with its continuation lines."""
    entries: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            entries.append(line)
        elif line.startswith("#"):
            entries.append("")
        elif entries and entries[-1]:
            entries[-1] += "\n" + line
    return [entry for entry in entries if entry]


def index_groups() -> dict[str, tuple[str, int]]:
    """Topic group of the index to (linked topic file, conclusion lines)."""
    text = INDEX.read_text(encoding="utf-8")
    topics = text.split("\n## Topics\n", 1)[1].split("\n## ", 1)[0]
    groups: dict[str, tuple[str, int]] = {}
    for block in topics.split("\n### ")[1:]:
        title, body = block.split("\n", 1)
        links = [link for link in LINK.findall(body) if link.startswith("pitfalls/")]
        assert len(links) == 1, f"group {title!r} links {links}, not one topic file"
        groups[title] = (links[0], sum(line.startswith("- ") for line in body.splitlines()))
    return groups


def test_every_topic_file_is_linked_from_the_index_and_exists() -> None:
    linked = {path for path, _ in index_groups().values()}
    on_disk = {f"pitfalls/{path.name}" for path in TOPICS.glob("*.md")}
    assert linked - on_disk == set(), "the index links topic files that do not exist"
    assert on_disk - linked == set(), "topic files the index does not link"


def test_each_group_has_one_conclusion_line_per_topic_entry() -> None:
    for title, (path, lines) in index_groups().items():
        entries = len(bullets((PROMPTS / path).read_text(encoding="utf-8")))
        assert lines == entries, (
            f"group {title!r}: {lines} conclusion lines in the index, "
            f"{entries} entries in {path}"
        )


def test_every_entry_names_its_source() -> None:
    inline = INDEX.read_text(encoding="utf-8").split("\n## Topics\n", 1)[0]
    files = {INDEX.name: inline}
    files.update({f"pitfalls/{p.name}": p.read_text(encoding="utf-8") for p in TOPICS.glob("*.md")})
    for name, text in files.items():
        for entry in bullets(text):
            assert SOURCE.search(entry), f"{name}: no source in {entry.splitlines()[0]!r}"


def test_relative_links_of_the_pitfalls_resolve() -> None:
    for path in [INDEX, *TOPICS.glob("*.md")]:
        for link in LINK.findall(path.read_text(encoding="utf-8")):
            if "://" not in link:
                assert (path.parent / link).is_file(), f"{path.name} links {link}, which is missing"
