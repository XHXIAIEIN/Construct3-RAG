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


def _parse(tmp_path, events: list[dict], plugin_map=None) -> list[dict]:
    sheet = tmp_path / "events.json"
    sheet.write_text(
        json.dumps({"name": "Sheet", "events": events}), encoding="utf-8"
    )
    return parse_event_sheet(sheet, {"slug": "t", "title_en": "T"}, plugin_map)


def _custom_action(owner: str, name: str) -> dict:
    return {
        "eventType": "custom-ace-block",
        "aceName": name,
        "objectClass": owner,
        "conditions": [],
        "actions": [],
        "children": [],
    }


def test_custom_action_block_is_indexed_like_a_function_block(tmp_path):
    docs = _parse(tmp_path, [
        {
            "eventType": "function-block",
            "functionName": "applyStats",
            "conditions": [],
            "actions": [],
            "children": [],
        },
        _custom_action("Bases", "applyStats"),
        _block(),
    ])

    func, custom, plain = docs
    assert func["metadata"]["is_function"] is True
    assert func["metadata"]["function_name"] == "applyStats"
    assert func["metadata"]["event_type"] == "function-block"
    assert "function:applyStats" in func["text"]

    assert custom["metadata"]["is_function"] is True
    assert custom["metadata"]["function_name"] == "Bases.applyStats"
    assert custom["metadata"]["event_type"] == "custom-ace-block"
    assert "custom-action:Bases.applyStats" in custom["text"]

    assert plain["metadata"]["is_function"] is False
    assert plain["metadata"]["function_name"] == ""
    assert plain["metadata"]["event_type"] == "block"


def test_custom_action_calls_render_owner_and_family(tmp_path):
    docs = _parse(tmp_path, [
        {
            "eventType": "block",
            "conditions": [],
            "actions": [
                {"customAction": "applyStats", "objectClass": "Bases"},
                {
                    "customAction": "applyStats",
                    "objectClass": "base",
                    "customActionObjectClass": "Bases",
                },
                {
                    "customAction": "Update Combo Text",
                    "objectClass": "TextCombo",
                    "parameters": ["true", "1", "2", "3"],
                },
            ],
            "children": [],
        },
    ], plugin_map={"base": "Sprite"})

    then = docs[0]["text"].split("THEN ", 1)[1]
    assert then == (
        "Bases.applyStats; "
        "Sprite(base).applyStats via Bases; "
        "TextCombo.Update Combo Text(true, 1, 2)"
    )
    assert sorted(docs[0]["metadata"]["action_objs"]) == ["Bases", "Sprite", "TextCombo"]


def test_function_calls_comments_and_scripts_render_readably(tmp_path):
    docs = _parse(tmp_path, [
        {
            "eventType": "block",
            "conditions": [],
            "actions": [
                {"type": "comment", "text": "ignored"},
                {"callFunction": "OffsetHand", "parameters": ["Self.X", "0"]},
                {"type": "script", "script": "console.log(1)"},
            ],
            "children": [],
        },
    ])

    then = docs[0]["text"].split("THEN ", 1)[1]
    assert then == "function:OffsetHand(Self.X, 0); script"
