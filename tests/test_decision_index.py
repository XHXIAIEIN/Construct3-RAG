"""The index of the decision records lists every record by its own title.

docs/decisions/README.md holds one line per record, newest first, as
"- [<the record's H1>](<file>.md) — <date>". Nothing is written twice: the
title and the date are the record's own, and this test prints the line to
paste when the index differs.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DECISIONS = REPO / "docs" / "decisions"
INDEX = DECISIONS / "README.md"

# An index line, and the first ISO date of a record's "Date:" line
ENTRY = re.compile(r"^- \[.*\]\(([^)\s]+)\) — \S")
DATE = re.compile(r"^Date: (\d{4}-\d\d-\d\d)", re.MULTILINE)


def records() -> list[Path]:
    return sorted(p for p in DECISIONS.glob("*.md") if p != INDEX)


def expected_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    title = text.splitlines()[0]
    assert title.startswith("# "), f"{path.name}: the first line is not an H1 title"
    date = DATE.search(text)
    assert date, f"{path.name}: no 'Date: YYYY-MM-DD' line"
    return f"- [{title[2:]}]({path.name}) — {date.group(1)}"


def expected_order() -> list[str]:
    """Newest first; records of one date by file name (the sort is stable)."""
    lines = [expected_line(path) for path in records()]
    return sorted(lines, key=lambda line: line.rsplit(" — ", 1)[1], reverse=True)


def index_lines() -> list[str]:
    text = INDEX.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.startswith("- [")]


def test_every_index_line_links_a_record_that_exists() -> None:
    for line in index_lines():
        match = ENTRY.match(line)
        assert match, f"not '- [title](file.md) — date': {line!r}"
        assert (DECISIONS / match.group(1)).is_file(), f"the index links {match.group(1)}, which is missing"


def test_every_record_has_its_own_line_in_the_index() -> None:
    present = set(index_lines())
    for path in records():
        line = expected_line(path)
        assert line in present, f"docs/decisions/README.md lacks or differs on this line:\n{line}"


def test_the_index_lists_each_record_once_newest_first() -> None:
    lines = index_lines()
    expected = expected_order()
    assert len(lines) == len(set(lines)), "a record is listed twice"
    assert lines == expected, "the lines are not newest first, then by file name; the order is:\n" + "\n".join(expected)
