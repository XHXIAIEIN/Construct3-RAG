"""Regression tests for lossless H2-level Markdown chunking."""

from __future__ import annotations

from src.ingest.markdown_parser import MarkdownParser


def test_substantive_intro_becomes_root_chunk(tmp_path):
    manual = tmp_path / "manual"
    page = manual / "interface" / "demo.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        """---
title: "Demo editor"
---

Open the editor by double-clicking the object.

## Toolbar

The toolbar edits the current image.
""",
        encoding="utf-8",
    )

    chunks = MarkdownParser(base_dir=manual).parse_file(page)

    assert len(chunks) == 2
    assert chunks[0].metadata["h2_heading"] == ""
    assert chunks[0].text.startswith("# Demo editor")
    assert "double-clicking" in chunks[0].text
    assert chunks[1].metadata["h2_heading"] == "Toolbar"
    assert "double-clicking" not in chunks[1].text
    assert "current image" in chunks[1].text


def test_h1_only_before_h2_does_not_create_empty_root_chunk(tmp_path):
    page = tmp_path / "guide" / "demo.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Demo\n\n## Details\n\nUseful details.\n", encoding="utf-8")

    chunks = MarkdownParser(base_dir=tmp_path).parse_file(page)

    assert len(chunks) == 1
    assert chunks[0].metadata["h2_heading"] == "Details"
