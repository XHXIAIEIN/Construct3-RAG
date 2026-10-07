"""
Tests for the query router and direct lookup service.
Uses the resolved committed/cache schema dataset but no external services.
"""
import json

import pytest

from src.domain.lookup import LookupIntent
from src.lookup.examples_index import ExamplesIndex
from src.lookup.intent import IntentClassifier
from src.lookup.schema_index import SchemaIndex
from src.lookup.service import LookupEngine
from src.lookup.term_index import TermIndex
from src.settings import load_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA_DIR = load_settings().schema.directory


def make_schema_index() -> SchemaIndex:
    """Return a SchemaIndex pointing at the configured schema dataset."""
    return SchemaIndex(SCHEMA_DIR)


def make_classifier() -> IntentClassifier:
    return IntentClassifier(schema_index=make_schema_index())


@pytest.fixture(scope="module")
def engine() -> LookupEngine:
    """The engine the tests share; a test that changes it builds its own."""
    return LookupEngine(schema_dir=SCHEMA_DIR)


def result_keys(response) -> list[tuple[str, str, str, str]]:
    """Return stable result identities in production rank order."""
    return [
        (match.collection, match.plugin_id, match.ace_type, match.ace_id)
        for match in response.matches
    ]


# ---------------------------------------------------------------------------
# TestSchemaIndex
# ---------------------------------------------------------------------------

class TestSchemaIndex:
    def test_load_plugins(self):
        idx = make_schema_index()
        pids, bids = idx.get_all_ids()
        assert len(pids) >= 60, f"Expected >= 60 plugins, got {len(pids)}"
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
    """Test deterministic grammar and schema-name classification."""

    def test_ace_list_sprite_actions(self):
        c = make_classifier()
        intent = c.classify("Sprite 有哪些 action")
        assert intent is not None
        assert intent.intent_type == "ace_list"
        assert intent.plugin_id == "sprite"
        assert intent.ace_type == "actions"

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

    def test_ace_detail_params_query(self):
        """'Sprite 的 Set animation 参数是什么' → ace_detail."""
        c = make_classifier()
        intent = c.classify("Sprite 的 Set animation 参数是什么")
        assert intent is not None
        assert intent.intent_type == "ace_detail"
        assert intent.plugin_id == "sprite"

    def test_unknown_compound_entity_does_not_resolve(self):
        """A registered name embedded in an unknown ASCII identifier is not an entity."""
        c = make_classifier()
        intent = c.classify("QuantumSprite 有哪些 actions")
        assert intent is None

    def test_prop_list_via_canshu_keyword(self):
        """'Platform 行为有哪些主要参数' → prop_list."""
        c = make_classifier()
        intent = c.classify("Platform 行为有哪些主要参数")
        assert intent is not None
        assert intent.intent_type == "prop_list"
        assert intent.plugin_id == "platform"
        assert intent.ace_type == "properties"


# ---------------------------------------------------------------------------
# TestLookupEngine — ace_detail formatting
# ---------------------------------------------------------------------------

class TestLookupEngineDetail:
    """Tests for structured ace_detail lookup responses."""

    def test_ace_detail_returns_structured_match(self, engine):
        resp = engine.try_lookup("Sprite 的 Set animation 怎么用")
        assert resp is not None
        assert resp.query_type == "lookup_ace_detail"
        assert result_keys(resp) == [
            ("plugins", "sprite", "action", "set-animation")
        ]
        assert "animation" in resp.context.lower()

    def test_ace_detail_nonexistent_ace_falls_through(self, engine):
        """Query with valid plugin but non-matching ACE name returns None."""
        resp = engine.try_lookup("Sprite 的 NonexistentAce12345 怎么用")
        assert resp is None


# ---------------------------------------------------------------------------
# TestLookupEngine
# ---------------------------------------------------------------------------

class TestLookupEngine:
    """End-to-end tests: query to structured lookup response."""

    def test_ace_list_returns_compact_format(self, engine):
        resp = engine.try_lookup("Sprite 有哪些 action")
        assert resp is not None
        assert resp.query_type == "lookup_ace_list"
        assert result_keys(resp)[0] == (
            "plugins", "sprite", "action", "stop-animation"
        )
        assert "A:" in resp.context  # compact action prefix
        assert "zh:" in resp.context  # zh mapping line
        # The shared actions Sprite's commonAces lists are part of its list.
        assert ("plugins", "_common", "action", "destroy") in result_keys(resp)

    def test_prop_list(self, engine):
        resp = engine.try_lookup("Sprite 有哪些 属性")
        assert resp is not None
        assert resp.query_type == "lookup_prop_list"
        assert result_keys(resp)[0] == (
            "plugins", "sprite", "property", "edit-animations"
        )

    def test_prop_list_platform_canshu(self, engine):
        """'Platform 行为有哪些主要参数' returns properties with jump/speed info."""
        resp = engine.try_lookup("Platform 行为有哪些主要参数")
        assert resp is not None
        assert resp.query_type == "lookup_prop_list"
        assert all(key[0] == "behaviors" for key in result_keys(resp))
        assert "跳跃" in resp.context
        assert "速度" in resp.context

    def test_term_translate_returns_real_structured_terms(self, engine):
        """A translation hit must expose stable term identities, not context alone."""
        resp = engine.try_lookup("翻译 Destroy")
        assert resp is not None
        assert resp.query_type == "lookup_term_translate"
        assert result_keys(resp)[0] == (
            "terms", "_common", "action", "destroy"
        )
        assert resp.matches[0].en.name == "Destroy"
        assert resp.matches[0].zh.name == "销毁对象"

    def test_chinese_tutorial_is_not_translation(self, engine):
        assert engine.try_lookup("中文教程怎么做") is None

    def test_unknown_translation_term_falls_through(self, engine):
        assert engine.try_lookup("翻译 DefinitelyNotATerm999") is None

    def test_solution_question_is_declined(self, engine):
        resp = engine.try_lookup("如何实现存档系统？")
        assert resp is None

    def test_behavior_lookup(self, engine):
        resp = engine.try_lookup("Bullet 有哪些 action")
        assert resp is not None
        assert resp.intent.is_behavior is True
        assert "A:" in resp.context

    def test_unknown_name_containing_sprite_does_not_resolve(self, engine):
        """ASCII entity matching requires identifier boundaries."""
        resp = engine.try_lookup("QuantumSprite 有哪些 actions")
        assert resp is None

    def test_elapsed_ms(self, engine):
        resp = engine.try_lookup("Sprite 有哪些 action")
        assert resp is not None
        assert resp.elapsed_ms >= 0


# ---------------------------------------------------------------------------
# TestKeywordInfer — scoped entity-plus-topic query tests
# ---------------------------------------------------------------------------

class TestKeywordInfer:
    """Test narrow entity-plus-topic lookup without broad category expansion."""

    def test_sprite_collision(self, engine):
        """A collision topic returns the shared condition and Sprite's own action."""
        resp = engine.try_lookup("Sprite 碰撞")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        keys = result_keys(resp)
        assert keys[0] == (
            "plugins", "_common", "condition",
            "on-collision-with-another-object",
        )
        assert ("plugins", "sprite", "action", "set-collisions-enabled") in keys

    def test_common_aces_follow_the_plugin_list(self, engine):
        """Shared ACEs come from the plugin's commonAces, not from being a world object."""
        assert engine.try_lookup("文本碰撞") is None
        resp = engine.try_lookup("Array UID")
        assert resp is not None
        assert ("plugins", "_common", "condition", "pick-by-unique-id") in result_keys(resp)

    def test_array_sort(self, engine):
        """Array sorting resolves to the Sort action."""
        resp = engine.try_lookup("Array 排序")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert result_keys(resp)[0] == (
            "plugins", "arr", "action", "sort2"
        )

    def test_sprite_animation(self, engine):
        """Playing an animation is Set animation, then Start; Stop is the opposite."""
        resp = engine.try_lookup("Sprite 播放 动画")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert resp.intent.ace_type == "actions"
        keys = result_keys(resp)
        assert keys[:2] == [
            ("plugins", "sprite", "action", "set-animation"),
            ("plugins", "sprite", "action", "start-animation"),
        ]
        stop = engine.try_lookup("Sprite 停止播放")
        assert result_keys(stop)[0] == ("plugins", "sprite", "action", "stop-animation")

    def test_concept_question_is_declined(self, engine):
        """'Sprite 是什么' asks for a definition, not an ACE."""
        assert engine.try_lookup("Sprite 是什么") is None

    def test_array_find_returns_contains_and_indexof(self, engine):
        """Finding a value in an Array answers with Contains value and IndexOf."""
        resp = engine.try_lookup("怎么在数组中查找特定数字")
        assert resp is not None
        assert resp.intent.plugin_id == "arr"
        keys = result_keys(resp)
        assert ("plugins", "arr", "condition", "contains-value") in keys[:3]
        assert ("plugins", "arr", "expression", "indexof") in keys[:3]

    def test_array_save_is_declined(self, engine):
        """Save on an Array is Download, AsJSON or Set at X; one word cannot pick, and never Load."""
        assert engine.try_lookup("Array 保存") is None

    def test_collision_howto_answers_like_the_topic(self, engine):
        """'怎么检测' is phrasing: detecting a collision is the shared collision condition."""
        resp = engine.try_lookup("怎么检测Sprite碰撞")
        assert resp is not None
        assert resp.intent.ace_type == "conditions"
        assert result_keys(resp)[0] == (
            "plugins", "_common", "condition", "on-collision-with-another-object"
        )

    def test_compact_mixed_plugin_topic_hits_lookup(self, engine):
        """CJK can delimit an ASCII plugin without accepting identifier substrings."""
        resp = engine.try_lookup("Sprite碰撞")
        assert resp is not None
        assert (
            "plugins", "_common", "condition", "on-collision-with-another-object"
        ) in result_keys(resp)[:3]

    def test_sprite_display_uses_directed_common_alias(self, engine):
        """The scoped one-hop 显示→可见 rule returns only shared set-visible."""
        resp = engine.try_lookup("精灵显示")
        assert resp is not None
        assert result_keys(resp)[0] == (
            "plugins", "_common", "action", "set-visible"
        )

    def test_display_alias_does_not_expand_a_more_specific_text_topic(self, engine):
        """A bare-display alias cannot add visibility noise to a text request."""
        resp = engine.try_lookup("Text 显示中文文本")
        assert resp is not None
        keys = result_keys(resp)
        assert ("plugins", "text", "action", "set-text") in keys[:5]
        assert ("plugins", "_common", "action", "set-visible") not in keys

    def test_sprite_move_answers_with_position_actions(self, engine):
        """A bare move is a change of position; the Z-order actions named 移动到… are not it."""
        z_order = {"move-to-top", "move-to-bottom", "move-to-layer", "move-to-object"}
        for query in ("精灵移动", "怎么让精灵移动", "Sprite move"):
            resp = engine.try_lookup(query)
            assert resp is not None, query
            keys = result_keys(resp)
            assert ("plugins", "_common", "action", "move-forward") in keys[:3], query
            assert ("plugins", "_common", "action", "move-at-angle") in keys[:3], query
            assert not z_order & {key[3] for key in keys}, query

    def test_sprite_move_to_layer_keeps_the_z_order_action(self, engine):
        """Naming the layer is no longer a bare move: the rule does not fire."""
        resp = engine.try_lookup("Sprite 移动到其他图层")
        assert resp is not None
        assert ("plugins", "_common", "action", "move-to-layer") in result_keys(resp)[:3]

    def test_array_store_answers_with_write_actions(self, engine):
        """Storing data in an Array is writing values, whichever question word asks it."""
        for query in ("怎样用数组存储数据", "怎么用数组存储数据", "如何用数组存储数据"):
            resp = engine.try_lookup(query)
            assert resp is not None, query
            keys = result_keys(resp)
            assert ("plugins", "arr", "action", "set-at-x") in keys[:5], query
            assert ("plugins", "arr", "action", "push") in keys[:5], query
            assert ("plugins", "arr", "expression", "asjson") not in keys, query

    def test_game_howto_is_declined(self, engine):
        """'怎么做一个平台跳跃游戏？' asks for a whole game, not an ACE."""
        assert engine.try_lookup("怎么做一个平台跳跃游戏？") is None

    def test_implement_question_is_declined(self, engine):
        """'如何实现存档系统？' asks for a solution; 系统 is not the System plugin here."""
        assert engine.try_lookup("如何实现存档系统？") is None

    def test_behavior_topic(self, engine):
        """'Platform 跳跃' → ace_search on platform behavior."""
        resp = engine.try_lookup("Platform 跳跃")
        assert resp is not None
        assert resp.query_type == "lookup_ace_search"
        assert resp.intent.is_behavior is True
        assert "跳跃" in resp.context

    def test_no_plugin_no_trigger(self, engine):
        """Query with ACE keyword but no plugin → should not trigger."""
        resp = engine.try_lookup("碰撞检测")
        assert resp is None  # no addon names the object

    def test_classifier_keeps_every_ace_type_for_a_noun_topic(self):
        """Collision names no ACE type: Sprite has collision conditions and actions."""
        c = make_classifier()
        intent = c.classify("Sprite 碰撞")
        assert intent is not None
        assert intent.intent_type == "ace_search"
        assert intent.ace_type == "conditions,actions,expressions"
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

    def test_addon_names_match_whole_words(self):
        """Platform is not platforms or Platformer; FileSystem is File system; Arr takes Array."""
        pattern = ExamplesIndex._name_pattern(["Platform"])
        assert pattern.search("a simple platform game")
        assert not pattern.search("mesh platforms")
        assert not pattern.search("rotating platformer")
        assert ExamplesIndex._name_pattern(["FileSystem"]).search("file system text editor")
        assert ExamplesIndex._name_pattern(["Arr", "Array"]).search("an array-based engine")

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

    def test_example_find_returns_structured_matches(self, engine):
        """Example lookup must expose metadata slugs as stable result IDs."""
        resp = engine.try_lookup("Show me a FileSystem example project")
        assert resp is not None
        assert resp.query_type == "lookup_example_find"
        assert result_keys(resp)[0] == (
            "examples", "", "example", "file-system-text-editor"
        )


# ---------------------------------------------------------------------------
# TestACEExampleAttach
# ---------------------------------------------------------------------------

class TestACEExampleAttach:
    def test_ace_list_appends_examples(self, tmp_path):
        """ACE list result should include related examples from a supplied index."""
        index_file = tmp_path / "examples_index.json"
        index_file.write_text(json.dumps({
            "behavior-Tween": [
                {"title": "Tween Demo", "slug": "tween-demo", "genres": ["animation"], "behaviors": ["Tween"]},
            ]
        }), encoding="utf-8")
        engine = LookupEngine(schema_dir=SCHEMA_DIR)
        engine.examples_index = ExamplesIndex(index_path=index_file)
        intent = LookupIntent(
            intent_type="ace_list",
            plugin_id="tween",
            is_behavior=True,
            ace_type="actions",
            filter_term="",
            matched_tags=["behavior-Tween"],
        )
        result, _ = engine._format_ace_list(intent)
        assert "Related examples" in result

    def test_examples_index_builds_from_exported_metadata(self, tmp_path):
        examples_dir = tmp_path / "en-US"
        examples_dir.mkdir()
        (examples_dir / "demo.json").write_text(json.dumps({
            "id": "demo",
            "name": "Demo",
            "tags": ["Animation"],
            "used-addons": {
                "plugins": ["Sprite"],
                "behaviors": ["Tween"],
                "effects": [],
            },
        }), encoding="utf-8")

        index = ExamplesIndex(examples_dir=examples_dir)

        assert index.search(["behavior-tween"])[0]["slug"] == "demo"
        assert index.search(["plugin-SPRITE"])[0]["title"] == "Demo"


# ---------------------------------------------------------------------------
# TestScriptingLookup
# ---------------------------------------------------------------------------

class TestScriptingLookup:
    def test_qualified_class_member_is_top_result(self, engine):
        resp = engine.try_lookup("IRuntime.callFunction")
        assert resp is not None
        assert resp.query_type == "lookup_script_api"
        assert result_keys(resp)[0] == (
            "script_api", "IRuntime", "script_api", "callFunction"
        )


# ---------------------------------------------------------------------------
# TestLookupResponseStructure
# ---------------------------------------------------------------------------

class TestLookupResponseStructure:
    def test_ace_search_returns_matches(self, engine):
        resp = engine.try_lookup("Sprite 动画")
        assert resp is not None
        assert len(resp.matches) > 0
        match = resp.matches[0]
        assert match.ace_id
        assert match.en.name
        assert match.plugin_id

    def test_ace_search_has_context(self, engine):
        resp = engine.try_lookup("Sprite 动画")
        assert resp.context
        assert isinstance(resp.context, str)

    def test_ace_list_returns_matches(self, engine):
        resp = engine.try_lookup("Sprite 有哪些 action")
        assert resp is not None
        assert len(resp.matches) > 0
        assert all(m.ace_type == "action" for m in resp.matches)

    def test_prop_list_returns_matches(self, engine):
        resp = engine.try_lookup("Platform 行为有哪些主要参数")
        assert resp is not None
        assert len(resp.matches) > 0
        assert all(m.collection == "behaviors" for m in resp.matches)
        assert all(m.ace_type == "property" for m in resp.matches)

    def test_context_is_string(self, engine):
        resp = engine.try_lookup("Sprite 有哪些 action")
        assert isinstance(resp.context, str)
        assert len(resp.context) > 0


# ---------------------------------------------------------------------------
# TestEffectLookup
# ---------------------------------------------------------------------------

class TestEffectLookup:
    def test_effect_answers_with_its_parameters_in_both_languages(self, engine):
        resp = engine.try_lookup("膨胀特效有哪些参数")
        assert resp is not None
        assert resp.query_type == "lookup_effect_detail"
        [match] = resp.matches
        assert (match.collection, match.ace_type, match.ace_id) == ("effects", "effect", "bulge")
        assert (match.en.name, match.zh.name) == ("Bulge", "膨胀")
        assert [(p["id"], p["type"], p["name_zh"]) for p in match.params] == [
            ("radius", "percent", "半径"),
            ("scale", "percent", "强度"),
        ]

    def test_a_name_two_effects_share_returns_both(self, engine):
        resp = engine.try_lookup("亮度效果的参数")
        assert resp is not None
        assert [m.ace_id for m in resp.matches] == ["brightness", "lighten"]

    def test_an_effect_without_parameters_says_so(self, engine):
        resp = engine.try_lookup("Lighten effect")
        assert resp is not None
        assert resp.matches[0].params == []
        assert "no parameters" in resp.context

    def test_an_effect_name_without_an_effect_word_is_declined(self, engine):
        assert engine.try_lookup("screen width") is None
        intent = engine.classifier.classify("screen width")
        assert (intent.intent_type, intent.entity_kind) == ("declined", "effect")
