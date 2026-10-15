"""Every relative Markdown link in the repository's own documents resolves.

A link resolves when its file or folder exists beside the linking file and,
when it carries a #fragment, the target Markdown file has a heading with
that GitHub slug. A content review checks facts, not links, so a link to a
heading that was renamed or never written survives without this test.
The build in plugin/ and the template copied into game projects are left
out, because their links resolve where they are installed.
"""
import re
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parent.parent

DOCUMENTS = sorted(
    {
        REPO / "README.md",
        REPO / "README_CN.md",
        REPO / "data" / "AGENTS.md",
        *REPO.glob("*/AGENTS.md"),
        *REPO.glob("AGENTS.md"),
        *REPO.glob(".claude/CLAUDE.md"),
        *REPO.glob(".claude/agents/*.md"),
        *(REPO / "data" / "c3-guides").rglob("*.md"),
        *(REPO / "prompts").rglob("*.md"),
        *(REPO / "skills").rglob("*.md"),
        *(REPO / "docs").rglob("*.md"),
        *(REPO / "scripts" / "plugin").rglob("*.md"),
    }
)

FENCE = re.compile(r"^ {0,3}(```|~~~)")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
# The target of an inline link or image, with an optional title after it
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"")


def prose_lines(text: str) -> list[str]:
    """The lines of a Markdown text outside fenced code blocks."""
    lines, fenced = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            lines.append(line)
    return lines


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: its rendered text, lowercase, punctuation removed, spaces to hyphens."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text).replace("`", "").lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """Every fragment a link can name in a Markdown file, numbering repeated headings as GitHub does."""
    found: set[str] = set()
    seen: dict[str, int] = {}
    for line in prose_lines(path.read_text(encoding="utf-8")):
        found.update(HTML_ANCHOR.findall(line))
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def relative_links(path: Path) -> list[str]:
    links = []
    for line in prose_lines(path.read_text(encoding="utf-8")):
        links += [link for link in LINK.findall(CODE_SPAN.sub("", line)) if not SCHEME.match(link)]
    return links


def broken(path: Path, link: str) -> str | None:
    """Why a link of a document does not resolve, or None when it does."""
    target, _, fragment = link.partition("#")
    file = (path.parent / unquote(target)).resolve() if target else path
    if not file.exists():
        return "the file is missing"
    if fragment and file.suffix == ".md" and unquote(fragment).lower() not in anchors(file):
        return f"{file.relative_to(REPO).as_posix()} has no heading #{fragment}"
    return None


def test_the_documents_are_found() -> None:
    assert REPO / "AGENTS.md" in DOCUMENTS
    assert REPO / "skills" / "construct3-agent-plugin" / "SKILL.md" in DOCUMENTS
    assert all(path.is_file() for path in DOCUMENTS)


def test_slug_follows_github() -> None:
    assert slug("5. Change code or data") == "5-change-code-or-data"
    assert slug("`check_project.py` and the editor") == "check_projectpy-and-the-editor"
    assert slug("Look an ACE up before writing it") == "look-an-ace-up-before-writing-it"
    assert slug("数组 与 字典") == "数组-与-字典"


def test_every_relative_link_resolves() -> None:
    failures = []
    for path in DOCUMENTS:
        for link in relative_links(path):
            reason = broken(path, link)
            if reason:
                failures.append(f"{path.relative_to(REPO).as_posix()} links {link}: {reason}")
    assert failures == [], "\n".join(failures)
