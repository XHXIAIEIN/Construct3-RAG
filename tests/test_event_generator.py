"""
Tests for Event Sheet JSON Generator.
Uses real schema files but no LLM or external services.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.eventsheet_generator import (
    EventGenerator,
    SchemaLoader,
    ClipboardValidator,
    extract_json_from_response,
    validate_clipboard_json,
)

DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_json(items: list) -> str:
    """Build a minimal valid clipboard JSON string."""
    return json.dumps({
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": items,
    })


def _make_loader() -> SchemaLoader:
    return SchemaLoader(DATA_DIR / "schemas")


def _make_generator() -> EventGenerator:
    return EventGenerator(DATA_DIR / "schemas")


# ---------------------------------------------------------------------------
# TestSchemaLoader
# ---------------------------------------------------------------------------

class TestSchemaLoader:
    def test_load_plugin(self):
        loader = _make_loader()
        schema = loader.load_plugin("sprite")
        assert schema is not None
        assert schema.id == "sprite"
        assert len(schema.actions) > 0

    def test_load_behavior(self):
        loader = _make_loader()
        schema = loader.load_behavior("platform")
        assert schema is not None
        assert schema.id == "platform"

    def test_load_nonexistent_returns_none(self):
        loader = _make_loader()
        assert loader.load_plugin("nonexistent_xyz") is None
        assert loader.load_behavior("nonexistent_xyz") is None

    def test_load_all_plugins(self):
        loader = _make_loader()
        plugins = loader.load_all_plugins()
        assert len(plugins) >= 70

    def test_load_all_behaviors(self):
        loader = _make_loader()
        behaviors = loader.load_all_behaviors()
        assert len(behaviors) >= 20

    def test_caching(self):
        loader = _make_loader()
        s1 = loader.load_plugin("sprite")
        s2 = loader.load_plugin("sprite")
        assert s1 is s2  # same object, from cache

    def test_keyword_index(self):
        loader = _make_loader()
        index = loader.build_keyword_index()
        assert len(index) > 0
        assert "sprite" in index

    def test_find_schema_by_keyword_exact(self):
        loader = _make_loader()
        result = loader.find_schema_by_keyword("sprite")
        assert result is not None
        assert result[0] == "sprite"
        assert result[1] == "plugin"

    def test_find_schema_by_keyword_chinese(self):
        loader = _make_loader()
        result = loader.find_schema_by_keyword("精灵")
        assert result is not None
        assert result[0] == "sprite"

    def test_find_schema_by_keyword_behavior(self):
        loader = _make_loader()
        result = loader.find_schema_by_keyword("platform")
        assert result is not None
        assert result[1] == "behavior"

    def test_find_schema_by_keyword_miss(self):
        loader = _make_loader()
        assert loader.find_schema_by_keyword("xyznonexistent") is None

    def test_search_ace(self):
        loader = _make_loader()
        results = loader.search_ace("destroy", ace_type="action")
        assert len(results) > 0
        assert any(r[1] == "action" for r in results)


# ---------------------------------------------------------------------------
# TestClipboardValidator
# ---------------------------------------------------------------------------

class TestClipboardValidator:
    def test_valid_comment(self):
        ok, errors, _ = validate_clipboard_json(
            _valid_json([{"eventType": "comment", "text": "Hello"}])
        )
        assert ok is True
        assert errors == []

    def test_valid_variable(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "variable",
            "name": "Score",
            "type": "number",
            "initialValue": "0",
            "comment": "",
            "isStatic": False,
            "isConstant": False,
        }]))
        assert ok is True

    def test_valid_block(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [{"id": "every-tick", "objectClass": "System"}],
            "actions": [],
        }]))
        assert ok is True

    def test_valid_function_block(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "function-block",
            "functionName": "MyFunc",
            "functionReturnType": "none",
            "conditions": [],
            "actions": [],
        }]))
        assert ok is True

    def test_valid_group_with_children(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "group",
            "title": "Main",
            "children": [{"eventType": "comment", "text": "child"}],
        }]))
        assert ok is True

    def test_valid_block_with_children(self):
        """Block with sub-events (e.g. else branch) should validate recursively."""
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [{"id": "every-tick", "objectClass": "System"}],
            "actions": [],
            "children": [{
                "eventType": "block",
                "conditions": [{"id": "else", "objectClass": "System"}],
                "actions": [{"id": "set-text", "objectClass": "Text"}],
            }],
        }]))
        assert ok is True
        assert errors == []

    def test_block_children_invalid_propagates(self):
        """Errors in nested block children should be caught."""
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [],
            "actions": [],
            "children": [{
                "eventType": "block",
                "conditions": [{"objectClass": "System"}],  # missing 'id'
                "actions": [],
            }],
        }]))
        assert ok is False
        assert any("id" in e for e in errors)

    def test_valid_action_comment(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [],
            "actions": [{"type": "comment", "text": "inline note"}],
        }]))
        assert ok is True

    def test_valid_call_function_action(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [],
            "actions": [{"callFunction": "MyFunc"}],
        }]))
        assert ok is True

    def test_invalid_json_parse(self):
        ok, errors, _ = validate_clipboard_json("{broken json")
        assert ok is False
        assert any("JSON" in e for e in errors)

    def test_missing_clipboard_header(self):
        ok, errors, _ = validate_clipboard_json(
            '{"type": "events", "items": []}'
        )
        assert ok is False
        assert any("is-c3-clipboard-data" in e for e in errors)

    def test_invalid_event_type(self):
        ok, errors, _ = validate_clipboard_json(
            _valid_json([{"eventType": "unknown_type"}])
        )
        assert ok is False
        assert any("eventType" in e for e in errors)

    def test_variable_missing_name(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "variable",
            "type": "number",
        }]))
        assert ok is False
        assert any("name" in e for e in errors)

    def test_variable_invalid_type(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "variable",
            "name": "X",
            "type": "invalid_type",
        }]))
        assert ok is False

    def test_comment_missing_text(self):
        ok, errors, _ = validate_clipboard_json(
            _valid_json([{"eventType": "comment"}])
        )
        assert ok is False

    def test_group_missing_title(self):
        ok, errors, _ = validate_clipboard_json(
            _valid_json([{"eventType": "group"}])
        )
        assert ok is False

    def test_function_missing_name(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "function-block",
            "conditions": [],
            "actions": [],
        }]))
        assert ok is False

    def test_function_invalid_return_type(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "function-block",
            "functionName": "F",
            "functionReturnType": "invalid",
            "conditions": [],
            "actions": [],
        }]))
        assert ok is False

    def test_condition_missing_id(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [{"objectClass": "System"}],
            "actions": [],
        }]))
        assert ok is False

    def test_condition_missing_object(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [{"id": "some-cond"}],
            "actions": [],
        }]))
        assert ok is False

    def test_action_missing_id(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [],
            "actions": [{"objectClass": "System"}],
        }]))
        assert ok is False

    def test_action_missing_object(self):
        ok, errors, _ = validate_clipboard_json(_valid_json([{
            "eventType": "block",
            "conditions": [],
            "actions": [{"id": "some-action"}],
        }]))
        assert ok is False

    def test_variable_missing_initial_warns(self):
        """Missing initialValue is a warning, not an error."""
        ok, _, warnings = validate_clipboard_json(_valid_json([{
            "eventType": "variable",
            "name": "X",
            "type": "number",
            "comment": "",
        }]))
        assert ok is True
        assert any("initialValue" in w for w in warnings)


# ---------------------------------------------------------------------------
# TestExtractJson
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_markdown_code_block(self):
        response = '说明：\n\n```json\n{"is-c3-clipboard-data": true, "type": "events", "items": []}\n```\n\n完成。'
        result = extract_json_from_response(response)
        assert result is not None
        data = json.loads(result)
        assert data["is-c3-clipboard-data"] is True

    def test_code_block_without_json_tag(self):
        response = '```\n{"is-c3-clipboard-data": true, "type": "events", "items": []}\n```'
        result = extract_json_from_response(response)
        assert result is not None

    def test_raw_json(self):
        response = '{"is-c3-clipboard-data": true, "type": "events", "items": []}'
        result = extract_json_from_response(response)
        assert result is not None

    def test_raw_json_with_surrounding_text(self):
        response = 'Here is the JSON: {"is-c3-clipboard-data": true, "type": "events", "items": []} Copy it.'
        result = extract_json_from_response(response)
        assert result is not None

    def test_no_json_returns_none(self):
        assert extract_json_from_response("No JSON here.") is None

    def test_invalid_json_in_code_block_returns_none(self):
        response = '```json\n{broken\n```'
        assert extract_json_from_response(response) is None

    def test_nested_json(self):
        nested = json.dumps({
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{"eventType": "block", "conditions": [], "actions": []}],
        })
        response = f"```json\n{nested}\n```"
        result = extract_json_from_response(response)
        assert result is not None
        assert json.loads(result)["items"][0]["eventType"] == "block"


# ---------------------------------------------------------------------------
# TestEventGenerator
# ---------------------------------------------------------------------------

class TestEventGenerator:
    def test_build_prompt_contains_schema(self):
        gen = _make_generator()
        prompt = gen.build_prompt("按空格键让玩家跳跃")
        assert "Schema" in prompt or "schema" in prompt
        assert "System" in prompt  # System plugin always included

    def test_build_prompt_finds_keyboard(self):
        gen = _make_generator()
        prompt = gen.build_prompt("按键盘空格键跳跃")
        assert "keyboard" in prompt.lower() or "键盘" in prompt

    def test_get_relevant_schema_always_includes_system(self):
        gen = _make_generator()
        schema_text = gen.get_relevant_schema("随便什么需求")
        assert "System" in schema_text or "system" in schema_text.lower()

    def test_process_response_valid(self):
        gen = _make_generator()
        llm_response = '```json\n{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "comment", "text": "test"}]}\n```'
        result = gen.process_response(llm_response)
        assert result["success"] is True
        assert result["json"] is not None
        assert result["errors"] == []

    def test_process_response_no_json(self):
        gen = _make_generator()
        result = gen.process_response("Sorry, I cannot generate that.")
        assert result["success"] is False
        assert result["json"] is None
        assert len(result["errors"]) > 0

    def test_process_response_invalid_json(self):
        gen = _make_generator()
        bad_json = '```json\n{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "unknown"}]}\n```'
        result = gen.process_response(bad_json)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_process_response_formats_output(self):
        gen = _make_generator()
        compact = '```json\n{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"comment","text":"hi"}]}\n```'
        result = gen.process_response(compact)
        assert result["success"] is True
        assert "\n" in result["json"]  # should be pretty-printed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
