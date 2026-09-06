"""Regression tests for deterministic event-block identities."""

from __future__ import annotations

import json

from src.ingest.event_parser import parse_event_sheet


def _block(*, children: list[dict] | None = None) -> dict:
    return {
        "eventType": "block",
        "conditions": [],
        "actions": [],
        "children": children or [],
    }


def test_event_ids_include_full_group_and_parent_ancestry(tmp_path):
    sheet = tmp_path / "events.json"
    sheet.write_text(
        json.dumps(
            {
                "name": "Game events",
                "events": [
                    {
                        "eventType": "group",
                        "children": [_block(children=[_block()]), _block()],
                    },
                    {
                        "eventType": "group",
                        "children": [_block(children=[_block()]), _block()],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    project = {"slug": "identity-test", "title_en": "Identity test"}

    first = parse_event_sheet(sheet, project)
    second = parse_event_sheet(sheet, project)
    first_ids = [row["id"] for row in first]

    assert len(first_ids) == 6
    assert len(set(first_ids)) == len(first_ids)
    assert first_ids == [row["id"] for row in second]
    assert any(row["metadata"]["depth"] == 1 for row in first)
