"""src/ingest/guides.py: Scirra's project format guide as Markdown, from a saved copy of its page."""
import logging
import urllib.error
from pathlib import Path

import pytest

from src.ingest.guides import GUIDES, GUIDES_DIR, GuideError, extract_guide, guide_for_page, refresh_guides

FIXTURE = Path(__file__).parent / "fixtures" / "constructs-project-format.html"
NAME = "constructs-project-format"
URL = GUIDES[NAME]


@pytest.fixture
def page() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_the_guide_opens_with_its_source_authors_license_and_dates(page):
    text = extract_guide(page, URL)
    assert text.splitlines()[:9] == [
        "---",
        f"source: {URL}",
        "title: Construct's project format",
        "authors: Ashley (Construct Team, Founder); DiegoM (Construct Team, Construct 3 Developer)",
        "license: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/",
        "published: 2026-03-12",
        "updated: 2026-06-04",
        "changes: the article converted to Markdown; the page's comments, side menu and navigation left out",
        "---",
    ]
    assert "\n# Construct's project format\n" in text


def test_the_article_keeps_its_sections_lists_notices_and_links(page):
    text = extract_guide(page, URL)
    for heading in ("## The main project file", "## Construct content", "### Object images",
                    "### Additional information", "## Additional project files", "## UI state files", "## Summary"):
        assert f"\n{heading}\n" in text
    assert "\n- Sound and music must be in WebM Opus format (with the file extension .webm).\n" in text
    assert "\n  1. Use only .ts files in the Construct project" in text      # a list inside a list item
    assert "\n> Note that the Construct project format does not have any published specification." in text
    assert "The file named `project.c3proj` is the main project file." in text
    assert "[Video plugin](https://www.construct.net/en/make-games/manuals/construct-3/plugin-reference/video)" in text
    assert "*player-default-000.png*" in text and "**Object types**" in text


def test_comments_side_menu_and_navigation_are_left_out(page):
    text = extract_guide(page, URL)
    for line in ("Commenter", "A comment on the tutorial", "Comments", "favourites", "visits", "Tagged",
                 "Create a translation", "chars in", "Pricing", "Game Making Software", "Tutorials"):
        assert line not in text


@pytest.mark.parametrize("html", [
    "<html><head><title>Just a moment...</title></head><body>Checking your browser</body></html>",
    "",
])
def test_a_page_without_the_article_is_refused(html):
    with pytest.raises(GuideError):
        extract_guide(html, URL)


def test_a_guide_is_written_only_when_its_text_changed(tmp_path, page):
    fetched = []

    def fetch(url):
        fetched.append(url)
        return page
    assert refresh_guides(tmp_path, fetch=fetch) == {NAME: "written"}
    target = tmp_path / GUIDES_DIR / f"{NAME}.md"
    written = target.read_bytes()
    assert b"\r\n" not in written
    assert refresh_guides(tmp_path, fetch=fetch) == {NAME: "unchanged"}
    assert fetched == [URL, URL]
    changed = page.replace("Last updated 4 Jun, 2026", "Last updated 5 Jun, 2026")
    assert refresh_guides(tmp_path, fetch=lambda url: changed) == {NAME: "written"}
    assert "updated: 2026-06-05" in target.read_text(encoding="utf-8")


@pytest.mark.parametrize("failure", [
    urllib.error.HTTPError(URL, 403, "Forbidden", {}, None),
    urllib.error.URLError("no network"),
    TimeoutError("timed out"),
])
def test_a_failed_fetch_keeps_the_committed_copy_and_warns(tmp_path, page, caplog, failure):
    target = tmp_path / GUIDES_DIR / f"{NAME}.md"
    target.parent.mkdir()
    target.write_text("committed copy", encoding="utf-8")

    def fetch(url):
        raise failure
    with caplog.at_level(logging.WARNING, logger="src.ingest.guides"):
        assert refresh_guides(tmp_path, fetch=fetch) == {NAME: "failed"}
    assert target.read_text(encoding="utf-8") == "committed copy"
    assert f"{URL} not refreshed, {GUIDES_DIR}/{NAME}.md kept as committed" in caplog.text
    assert ("--guide-html" in caplog.text) == (getattr(failure, "code", None) == 403)


def test_a_browser_check_instead_of_the_page_keeps_the_committed_copy(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.ingest.guides"):
        result = refresh_guides(tmp_path, fetch=lambda url: "<html><title>Just a moment...</title></html>")
    assert result == {NAME: "failed"} and "no tutorial article in the page" in caplog.text
    assert not (tmp_path / GUIDES_DIR).exists()


def test_a_page_saved_from_a_browser_stands_in_for_the_fetch(tmp_path, page):
    def fetch(url):
        raise AssertionError("a saved page is read instead")
    assert guide_for_page(page) == NAME
    assert refresh_guides(tmp_path, saved=[FIXTURE], fetch=fetch) == {NAME: "written"}
    with pytest.raises(GuideError):
        guide_for_page("<html>another page</html>")
