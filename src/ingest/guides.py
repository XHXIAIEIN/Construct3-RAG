"""Scirra's guides an agent reads beside the data, kept as Markdown under ``data/c3-guides/``.

A guide is a page of construct.net, not CDN data of a release. The data
update fetches each page, keeps the article (title, dates, contributors,
license, body) and drops the comments, the side menu and the site's
navigation. A guide's file is written only when its text changed, so a weekly
run with nothing new commits nothing. A failed fetch, or a page without the
article, keeps the committed copy and logs a warning; the rest of the update
goes on.

construct.net may answer a script with a browser check instead of the page.
A page saved from a browser then stands in for the fetch:
``refresh_guides(data_dir, saved=[page.html])``, or
``python scripts/init.py --guides-only --guide-html page.html``.
"""
import logging
import re
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

GUIDES_DIR = "c3-guides"
# file name in data/c3-guides/ (without .md) -> the page
GUIDES = {
    "constructs-project-format": "https://www.construct.net/en/tutorials/constructs-project-format-3275",
}
_USER_AGENT = "Construct3-RAG data update (+https://github.com/XHXIAIEIN/Construct3-RAG)"
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_BLOCKS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "aside", "div", "pre", "blockquote", "table"}
_DATES = re.compile(r"Published on (?P<published>\d{1,2} \w{3,4}, \d{4})\.?"
                    r"(?:\s*Last updated (?P<updated>\d{1,2} \w{3,4}, \d{4}))?")


class GuideError(ValueError):
    """The page holds no guide article: a browser check, an error page, or a layout the extractor does not know."""


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)    # _Node or str

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def find(self, match) -> "_Node | None":
        for child in self.children:
            if isinstance(child, _Node):
                if match(child):
                    return child
                hit = child.find(match)
                if hit is not None:
                    return hit
        return None

    def find_all(self, match) -> list["_Node"]:
        out = []
        for child in self.children:
            if isinstance(child, _Node):
                if match(child):
                    out.append(child)
                out.extend(child.find_all(match))
        return out

    def text(self) -> str:
        return " ".join("".join(c if isinstance(c, str) else " " + c.text() + " " for c in self.children).split())


class _TreeBuilder(HTMLParser):
    """The page as a tree of _Node; an end tag closes the nearest open element of its name."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Node(tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _parse(html: str) -> _Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


class _Markdown:
    """The article body as Markdown: paragraphs, headings, lists, notices as quotes, links made absolute."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def inline(self, node: _Node) -> str:
        parts = []
        for child in node.children:
            if isinstance(child, str):
                parts.append(re.sub(r"\s+", " ", child))
                continue
            if child.tag in ("ul", "ol"):
                continue    # a list inside a list item is rendered by its item
            inner = self.inline(child)
            if child.tag in ("strong", "b") and inner.strip():
                parts.append(f"**{inner.strip()}**")
            elif child.tag in ("em", "i") and inner.strip():
                parts.append(f"*{inner.strip()}*")
            elif child.tag == "code":
                parts.append(f"`{inner.strip()}`")
            elif child.tag == "br":
                parts.append("\n")
            elif child.tag == "a" and inner.strip() and child.attrs.get("href"):
                parts.append(f"[{inner.strip()}]({urljoin(self.base_url, child.attrs['href'])})")
            elif child.tag == "img" and child.attrs.get("src"):
                parts.append(f"![{child.attrs.get('alt', '')}]({urljoin(self.base_url, child.attrs['src'])})")
            else:
                parts.append(inner)
        return "".join(parts)

    def blocks(self, node: _Node, indent: str = "") -> list[str]:
        out: list[str] = []
        loose: list = []    # inline content between blocks

        def flush() -> None:
            text = self.inline(_Node("span", children=list(loose))).strip()
            if text:
                out.append(indent + text)
            loose.clear()

        for child in node.children:
            if isinstance(child, str) or child.tag not in _BLOCKS:
                loose.append(child)
                continue
            flush()
            if child.tag == "p":
                text = self.inline(child).strip()
                if text:
                    out.append(indent + text)
            elif child.tag[0] == "h" and child.tag[1:].isdigit():
                out.append(f"{indent}{'#' * int(child.tag[1:])} {self.inline(child).strip()}")
            elif child.tag in ("ul", "ol"):
                out.append(self.list_items(child, indent))
            elif child.tag in ("aside", "blockquote"):    # the page's notices are asides
                quoted = self.blocks(child)
                if quoted:
                    out.append("\n".join(f"{indent}> {line}" if line else f"{indent}>"
                                         for line in "\n\n".join(quoted).splitlines()))
            elif child.tag == "pre":
                out.append(f"{indent}```\n{child.text()}\n{indent}```")
            else:
                out.extend(self.blocks(child, indent))
        flush()
        return out

    def list_items(self, node: _Node, indent: str) -> str:
        lines = []
        for n, item in enumerate((c for c in node.children if isinstance(c, _Node) and c.tag == "li"), 1):
            marker = f"{n}. " if node.tag == "ol" else "- "
            lines.append(f"{indent}{marker}{self.inline(item).strip()}")
            for sub in (c for c in item.children if isinstance(c, _Node) and c.tag in ("ul", "ol")):
                lines.append(self.list_items(sub, indent + " " * len(marker)))
        return "\n".join(lines)


def _iso(day: str) -> str:
    """'4 Jun, 2026' as 2026-06-04; the page may write September as Sept."""
    return datetime.strptime(day.replace("Sept", "Sep"), "%d %b, %Y").date().isoformat()


def extract_guide(html: str, url: str) -> str:
    """The guide of a construct.net tutorial page as Markdown, opening with its source,
    contributors, license and dates. Raises GuideError when the page has no article."""
    root = _parse(html)
    body = root.find(lambda n: n.attrs.get("id") == "ArticleBody")
    title = root.find(lambda n: n.tag == "h1")
    dates = root.find(lambda n: "tutorialDate" in n.classes())
    if body is None or title is None or dates is None:
        raise GuideError(f"{url}: no tutorial article in the page (a browser check or another layout)")
    found = _DATES.search(dates.text())
    if not found:
        raise GuideError(f"{url}: the dates read {dates.text()!r}")
    published = _iso(found["published"])
    updated = _iso(found["updated"]) if found["updated"] else published

    contributors = root.find(lambda n: n.attrs.get("id") == "ContributorsWrap")
    authors = []
    for item in contributors.find_all(lambda n: n.tag == "li") if contributors else []:
        name_box = item.find(lambda n: "usernameTextWrap" in n.classes())
        name = name_box.find(lambda n: n.tag == "span") if name_box else None
        group = [g.text() for g in item.find_all(lambda n: n.classes() & {"groupName", "groupLabel"})]
        if name is not None and name.text():
            authors.append(name.text() + (f" ({', '.join(group)})" if group else ""))
    license_box = root.find(lambda n: "licenseWrap" in n.classes())
    license_link = license_box.find(lambda n: n.tag == "a") if license_box else None
    if not authors or license_link is None:
        raise GuideError(f"{url}: the page names no contributors or no license")

    text = "\n\n".join(_Markdown(url).blocks(body))
    header = [
        "---",
        f"source: {url}",
        f"title: {title.text()}",
        f"authors: {'; '.join(authors)}",
        f"license: {license_link.text()}, {license_link.attrs.get('href', '')}",
        f"published: {published}",
        f"updated: {updated}",
        "changes: the article converted to Markdown; the page's comments, side menu and navigation left out",
        "---",
    ]
    return "\n".join(header) + f"\n\n# {title.text()}\n\n{text}\n"


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def guide_for_page(html: str) -> str:
    """The name of the guide a saved page is, by the path of its URL in the page."""
    for name, url in GUIDES.items():
        if urlparse(url).path in html:
            return name
    raise GuideError(f"the page is none of {', '.join(GUIDES.values())}")


def refresh_guides(data_dir: Path, saved: Sequence[Path] = (),
                   fetch: Callable[[str], str] = _fetch) -> dict[str, str]:
    """Write each guide to ``data_dir/c3-guides/<name>.md`` when its text changed.

    ``saved`` pages, saved from a browser, stand in for the fetch of the guide
    they are. Returns, per guide, ``written``, ``unchanged`` or ``failed``
    (the fetch or the extraction failed, a warning says why, and the
    committed copy stays).
    """
    pages = {}
    for path in saved:
        html = Path(path).read_text(encoding="utf-8")
        pages[guide_for_page(html)] = html
    out_dir = Path(data_dir) / GUIDES_DIR
    result = {}
    for name, url in GUIDES.items():
        target = out_dir / f"{name}.md"
        try:
            text = extract_guide(pages[name] if name in pages else fetch(url), url)
        except (OSError, UnicodeDecodeError, GuideError) as e:    # URLError and timeouts are OSErrors
            kept = "kept as committed" if target.exists() else "not written"
            hint = ""
            if getattr(e, "code", None) in (403, 503):
                hint = ("; when the site answers scripts with a browser check, save the page from a browser and "
                        "run python scripts/init.py --guides-only --guide-html <saved page>")
            logger.warning(f"[guides] {url} not refreshed, {GUIDES_DIR}/{target.name} {kept}: {e}{hint}")
            result[name] = "failed"
            continue
        if target.exists() and target.read_text(encoding="utf-8") == text:
            result[name] = "unchanged"
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        result[name] = "written"
    return result
