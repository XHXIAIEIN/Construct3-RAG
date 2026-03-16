"""
Tests for the Query Routing & Direct Lookup System.
Uses real JSON schemas from CDN cache but no external services.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.lookup import (
    SchemaIndex, TermIndex, IntentClassifier, LookupEngine,
    LookupIntent, ExamplesIndex,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

from src.config import SCHEMA_DIR


def make_schema_index() -> SchemaIndex:
    """Return a SchemaIndex pointing at schema data (CDN cache)."""
    return SchemaIndex(SCHEMA_DIR)


def make_classifier(embedder=None) -> IntentClassifier:
    return IntentClassifier(
        schema_index=make_schema_index(),
        embedder=embedder,
    )


def make_engine(embedder=None) -> LookupEngine:
    return LookupEngine(
        schema_dir=SCHEMA_DIR,
        embedder=embedder,
    )


# ---------------------------------------------------------------------------
# TestSchemaIndex
# ---------------------------------------------------------------------------

class TestSchemaIndex:
    def test_load_plugins(self):
        idx = make_schema_index()
        pids, bids = idx.get_all_ids()
        assert len(pids) >= 70, f"Expected >= 70 plugins, got {len(pids)}"
        assert len(bids) >= 20, f"Expected >= 20 behaviors, got {len(bids)}"

    def test_resolve_by_id(self):
        idx = make_schema_index()
        result = idx.resolve_name("sprite")
        assert result is not None
        assert result[0] == "sprite"
        assert result[1] is False  # not a behavior

    def test_resolve_by_english_name(self):
        idx = make_schema_index()
        result = idx.resolve_name("Sprite")
        assert result is not None
        assert result[0] == "sprite"

    def test_resolve_by_chinese_name(self):
        idx = make_schema_index()
        result = idx.resolve_name("精灵")
        assert result is not None
        assert result[0] == "sprite"

    def test_resolve_case_insensitive(self):
        idx = make_schema_index()
        result = idx.resolve_name("SPRITE")
        assert result is not None
        assert result[0] == "sprite"

    def test_resolve_behavior(self):
        idx = make_schema_index()
        result = idx.resolve_name("bullet")
        assert result is not None
        pid, is_beh = result
        assert pid == "bullet"
        assert is_beh is True

    def test_resolve_behavior_chinese(self):
        idx = make_schema_index()
        result = idx.resolve_name("子弹")
        assert result is not None
        pid, is_beh = result
        assert pid == "bullet"
        assert is_beh is True

    def test_resolve_nonexistent(self):
        idx = make_schema_index()
        result = idx.resolve_name("nonexistent_plugin_xyz")
        assert result is None

    def test_get_ace_list(self):
        idx = make_schema_index()
        actions = idx.get_ace_list("sprite", "actions")
        assert len(actions) > 0
        assert "name_zh" in actions[0]

    def test_get_properties(self):
        idx = make_schema_index()
        props = idx.get_ace_list("sprite", "properties")
        assert len(props) > 0


# ---------------------------------------------------------------------------
# TestIntentClassifier
# ---------------------------------------------------------------------------

class TestIntentClassifier:
    """Test Tier 1 (rule-based) classification only — no embedder needed."""

    def test_ace_list_sprite_actions(self):
        c = make_classifier()
        intent = c.classify("Sprite 有哪些 action")
        assert intent is not None
        assert intent.intent_type == "ace_list"
        assert intent.plugin_id == "sprite"
        assert intent.ace_type == "actions"
        assert intent.tier == 1

    def test_ace_list_chinese(self):
        c = make_classifier()
        intent = c.classify("精灵 有哪些 动作")
        assert intent is not None
        assert intent.intent_type == "ace_list"
        assert intent.plugin_id == "sprite"
        assert intent.ace_type == "actions"

    def test_ace_list_conditions(self):
        c = make_classifier()
        intent = c.classify("Sprite 有哪些 condition")
        assert intent is not None
        assert intent.ace_type == "conditions"

    def test_ace_list_expressions(self):
        c = make_classifier()
        intent = c.classify("列出 Sprite 的 expression")
        assert intent is not None
        assert intent.ace_type == "expressions"

    def test_prop_list(self):
        c = make_classifier()
        intent = c.classify("Sprite 有哪些 属性")
        assert intent is not None
        assert intent.intent_type == "prop_list"
        assert intent.ace_type == "properties"

    def test_behavior_ace_list(self):
        c = make_classifier()
        intent = c.classify("Bullet 有哪些 action")
        assert intent is not None
        assert intent.plugin_id == "bullet"
        assert intent.is_behavior is True

    def test_term_translate_zh(self):
        c = make_classifier()
        intent = c.classify("翻译 Destroy")
        assert intent is not None
        assert intent.intent_type == "term_translate"
        assert "Destroy" in intent.term

    def test_term_translate_en(self):
        c = make_classifier()
        intent = c.classify("Destroy 中文是什么")
        assert intent is not None
        assert intent.intent_type == "term_translate"

    def test_not_lookup_general_question(self):
        """General questions should NOT be classified as lookup."""
        c = make_classifier()
        intent = c.classify("如何实现存档系统？")
        assert intent is None

    def test_not_lookup_how_to(self):
        c = make_classifier()
        intent = c.classify("怎么做一个平台跳跃游戏？")
        assert intent is None

    def test_not_lookup_explanation(self):
        c = make_classifier()
        intent = c.classify("Sprite 和 Tiled Background 有什么区别？")
        assert intent is None

    def test_ace_list_suffix_pattern(self):
        """Test 'Sprite action 列表' pattern."""
        c = make_classifier()
        intent = c.classify("Sprite action 列表")
        assert intent is not None
        assert intent.intent_type == "ace_list"
        assert intent.ace_type == "actions"

    def test_ace_detail_usage_query(self):
        """'Sprite 的 Destroy 怎么用' → ace_detail."""
        c = make_classifier()
        intent = c.classify("Sprite 的 Destroy 怎么用")
        assert intent is not None
        assert intent.intent_type == "ace_detail"
        assert intent.plugin_id == "sprite"
        assert "destroy" in intent.ace_name.lower()
        assert intent.tier == 1

    def test_ace_detail_params_query(self):
        """'Sprite 的 Set animation 参数是什么' → ace_detail."""
        c = make_classifier()
        intent = c.classify("Sprite 的 Set animation 参数是什么")
        assert intent is not None
        assert intent.intent_type == "ace_detail"
        assert intent.plugin_id == "sprite"

    def test_ace_detail_nonexistent_plugin(self):
        """ace_detail with fake plugin falls through."""
        c = make_classifier()
        intent = c.classify("FakeXYZ 的 Destroy 怎么用")
        assert intent is None

    def test_prop_list_via_canshu_keyword(self):
        """'Platform 行为有哪些主要参数' → prop_list."""
        c = make_classifier()
        intent = c.classify("Platform 行为有哪些主要参数？")
        assert intent is not None
        assert intent.intent_type == "prop_list"
        assert intent.plugin_id == "platform"
        assert intent.ace_type == "properties"


# ---------------------------------------------------------------------------
# TestLookupEngine — ace_detail formatting
# ---------------------------------------------------------------------------

class TestLookupEngineDetail:
    """Tests for ace_detail lookup responses."""

    def test_ace_detail_returns_markdown(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite 的 Set animation 怎么用")
        assert resp is not None
        assert resp.query_type == "lookup_ace_detail"
        assert "animation" in resp.answer.lower()

    def test_ace_detail_nonexistent_ace_falls_through(self):
        """Query with valid plugin but non-matching ACE name returns None."""
        engine = make_engine()
        resp = engine.try_lookup("Sprite 的 NonexistentAce12345 怎么用")
        assert resp is None


# ---------------------------------------------------------------------------
# TestLookupEngine
# ---------------------------------------------------------------------------

class TestLookupEngine:
    """End-to-end tests: query → markdown output."""

    def test_ace_list_returns_compact_format(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite 有哪些 action")
        assert resp is not None
        assert resp.query_type == "lookup_ace_list"
        assert "A:" in resp.answer  # compact action prefix
        assert "zh:" in resp.answer  # zh mapping line

    def test_prop_list(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite 有哪些 属性")
        assert resp is not None
        assert resp.query_type == "lookup_prop_list"

    def test_prop_list_platform_canshu(self):
        """'Platform 行为有哪些主要参数' returns properties with jump/speed info."""
        engine = make_engine()
        resp = engine.try_lookup("Platform 行为有哪些主要参数？")
        assert resp is not None
        assert resp.query_type == "lookup_prop_list"
        assert "跳跃" in resp.answer
        assert "速度" in resp.answer

    def test_term_translate_with_cdn_terms(self):
        """Term translate works when CDN terms are provided."""
        terms = [
            {"term_key": "text.plugins.sprite.name", "zh": "精灵", "en": "Sprite"},
            {"term_key": "text.plugins.sprite.actions.destroy.list-name", "zh": "销毁", "en": "Destroy"},
        ]
        engine = LookupEngine(terms=terms)
        resp = engine.try_lookup("翻译 Sprite")
        assert resp is not None
        assert resp.query_type == "lookup_term_translate"
        assert "|" in resp.answer

    def test_rag_fallthrough(self):
        """Non-lookup queries should return None."""
        engine = make_engine()
        resp = engine.try_lookup("如何实现存档系统？")
        assert resp is None

    def test_behavior_lookup(self):
        engine = make_engine()
        resp = engine.try_lookup("Bullet 有哪些 action")
        assert resp is not None
        assert resp.intent.is_behavior is True
        assert "A:" in resp.answer

    def test_nonexistent_plugin_falls_through(self):
        """Query with fake plugin name should fallback to RAG."""
        engine = make_engine()
        resp = engine.try_lookup("FakePlugin12345 有哪些 action")
        assert resp is None

    def test_elapsed_ms(self):
        engine = make_engine()
        resp = engine.try_lookup("Sprite 有哪些 action")
        assert resp is not None
        assert resp.elapsed_ms >= 0


# ---------------------------------------------------------------------------
# TestKeywordInfer — Tier 1.5 fuzzy query tests
# ---------------------------------------------------------------------------

class TestKeywordInfer:
    """Test Tier 1.5 keyword inference: plugin + topic → ace_search."""

    def test_sprite_collision(self):
        """'Sprite 碰撞' → ace_search with conditions (碰撞 is a conditions keyword)."""
        engine = make_engine()
        resp = engine.try_lookup("Sprite 碰撞")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert "碰撞" in resp.answer  # appears in zh: mapping line
        assert ("C:" in resp.answer or "A:" in resp.answer)  # compact format

    def test_array_sort(self):
        """'Array 排序' → ace_search with actions (排序 is an actions keyword)."""
        engine = make_engine()
        resp = engine.try_lookup("Array 排序")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert "排序" in resp.answer

    def test_sprite_animation(self):
        """'Sprite 动画' → ace_search, may span multiple ACE types."""
        engine = make_engine()
        resp = engine.try_lookup("Sprite 播放 动画")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert "动画" in resp.answer

    def test_no_keyword_fallthrough(self):
        """'Sprite 是什么' contains skip word → should NOT trigger ace_search."""
        engine = make_engine()
        resp = engine.try_lookup("Sprite 是什么")
        assert resp is None  # falls through to RAG

    def test_array_find_howto_hits_schema(self):
        """'怎么在数组中查找特定数字？' — '怎么' is now SOFT_SKIP.
        Plugin 'Array' is found → Tier1.5 runs and hits find/indexOf ACEs.
        Result is injected as schema_context into LLM, not returned directly to user."""
        engine = make_engine()
        resp = engine.try_lookup("怎么在数组中查找特定数字？")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert resp.intent.plugin_id == "arr"
        assert ("C:" in resp.answer or "A:" in resp.answer or "E:" in resp.answer)

    def test_array_find_without_howto(self):
        """'数组 查找数字' (no 怎么) → ace_search on Array, still triggers lookup."""
        engine = make_engine()
        resp = engine.try_lookup("数组 查找数字")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert resp.intent.plugin_id == "arr"
        assert ("C:" in resp.answer or "A:" in resp.answer or "E:" in resp.answer)

    def test_howto_with_plugin_hits_schema(self):
        """'怎么检测Sprite碰撞' — plugin 'Sprite' found + '怎么' is SOFT_SKIP.
        Tier1.5 runs and hits collision-related ACEs for schema_context injection."""
        engine = make_engine()
        resp = engine.try_lookup("怎么检测Sprite碰撞")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert resp.intent.plugin_id == "sprite"
        assert ("C:" in resp.answer or "A:" in resp.answer or "E:" in resp.answer)

    def test_zenyang_fallthrough(self):
        """'怎样用数组存储数据' — '怎样' is also a how-to word → should fall through."""
        engine = make_engine()
        resp = engine.try_lookup("怎样用数组存储数据")
        assert resp is None  # falls through to RAG

    def test_howto_fallthrough(self):
        """'怎么做一个平台跳跃游戏？' is a how-to → should NOT trigger ace_search."""
        engine = make_engine()
        resp = engine.try_lookup("怎么做一个平台跳跃游戏？")
        assert resp is None  # falls through to RAG

    def test_general_howto_fallthrough(self):
        """'如何实现存档系统？' is a general how-to → should NOT trigger ace_search."""
        engine = make_engine()
        resp = engine.try_lookup("如何实现存档系统？")
        assert resp is None  # falls through to RAG

    def test_behavior_topic(self):
        """'Platform 跳跃' → ace_search on platform behavior."""
        engine = make_engine()
        resp = engine.try_lookup("Platform 跳跃")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert resp.intent.is_behavior is True
        assert "跳跃" in resp.answer

    def test_no_plugin_no_trigger(self):
        """Query with ACE keyword but no plugin → should not trigger."""
        engine = make_engine()
        resp = engine.try_lookup("碰撞检测")
        assert resp is None  # no plugin name → falls through

    def test_classifier_tier(self):
        """Verify keyword infer sets tier=1."""
        c = make_classifier()
        intent = c.classify("Sprite 碰撞")
        assert intent is not None
        assert intent.intent_type == "ace_search"
        assert intent.tier == 1
        assert "碰撞" in intent.filter_term


# ---------------------------------------------------------------------------
# TestExamplesIndex
# ---------------------------------------------------------------------------

class TestExamplesIndex:
    def setup_method(self):
        self.index = ExamplesIndex()

    def test_search_by_behavior_tag(self):
        results = self.index.search(["behavior-Tween"])
        assert isinstance(results, list)

    def test_search_returns_records_with_slug(self):
        results = self.index.search(["behavior-Tween"])
        if results:
            assert "slug" in results[0]
            assert "title" in results[0]

    def test_search_empty_tags(self):
        results = self.index.search([])
        assert results == []

    def test_search_unknown_tag(self):
        results = self.index.search(["behavior-Nonexistent99999"])
        assert results == []

    def test_format_for_ace_context(self):
        records = [
            {"title": "Cave Bridge", "slug": "cave-bridge", "genres": ["adventure"], "behaviors": ["Tween"]},
            {"title": "Kiwi Story", "slug": "kiwi-story", "genres": ["platformer"], "behaviors": ["Platform"]},
        ]
        result = ExamplesIndex.format_for_ace(records)
        assert "Cave Bridge" in result
        assert "cave-bridge" in result
        assert "Kiwi Story" in result

    def test_format_for_example_find(self):
        records = [
            {"title": "Cave Bridge", "slug": "cave-bridge", "genres": ["adventure"], "behaviors": ["Tween"]},
        ]
        result = ExamplesIndex.format_for_find(records)
        assert "Cave Bridge" in result
        assert "cave-bridge" in result
        assert "adventure" in result.lower()


# ---------------------------------------------------------------------------
# TestACEExampleAttach
# ---------------------------------------------------------------------------

class TestACEExampleAttach:
    def test_ace_list_appends_examples(self, tmp_path):
        """ACE list result should include Related examples when examples_index has data."""
        import json
        index_file = tmp_path / "examples_index.json"
        index_file.write_text(json.dumps({
            "behavior-Tween": [
                {"title": "Tween Demo", "slug": "tween-demo", "genres": ["animation"], "behaviors": ["Tween"]},
            ]
        }), encoding="utf-8")
        engine = LookupEngine()
        engine.examples_index = ExamplesIndex(index_path=index_file)
        intent = LookupIntent(
            intent_type="ace_list",
            plugin_id="tween",
            is_behavior=True,
            ace_type="actions",
            filter_term="",
            matched_tags=["behavior-Tween"],
        )
        result = engine._format_ace_list(intent)
        assert "Related examples" in result
