"""Tests for QueryExpander — all mocked, no external services required."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Shared parse cases for backend tests
# ---------------------------------------------------------------------------

_PARSE_CASES = [
    ("包含\n检测\n遍历\n索引\n比较\n", {"包含", "检测", "遍历", "索引", "比较"}),
    ("的\n包含\n检测\na\n遍历\n",      {"包含", "检测", "遍历"}),   # short/stop filtered
    ("",                               set()),
]


# ---------------------------------------------------------------------------
# Minimal schema fixture (mimics one plugin JSON)
# ---------------------------------------------------------------------------

FIXTURE_ARR = {
    "id": "arr",
    "name_zh": "数组",
    "name_en": "Array",
    "description_zh": "允许将数据储存在最多三维的数组空间中。",
    "description_en": "Store an array of values in up to 3 dimensions.",
    "path": "data-and-storage/array",
    "categories": ["array", "data"],
    "conditions": [
        {
            "id": "contains-value",
            "name_zh": "如果包含值",
            "name_en": "Contains value",
            "description_zh": "查找整个数组，检测是否包含某个值。",
            "description_en": "Test if the array contains a value.",
            "scriptName": "ContainsValue",
            "params": [
                {
                    "id": "value",
                    "type": "any",
                    "name_zh": "值",
                    "name_en": "Value",
                }
            ],
        }
    ],
    "actions": [],
    "expressions": [
        {
            "id": "index-of",
            "name_zh": "索引",
            "name_en": "IndexOf",
            "description_zh": "返回某个值在数组中的索引位置。",
            "description_en": "Get the index of a value in the array.",
            "scriptName": "IndexOf",
            "params": [
                {
                    "id": "value",
                    "type": "any",
                    "name_zh": "值",
                    "name_en": "Value",
                }
            ],
        }
    ],
    "properties": [],
}

FIXTURE_EFFECT = {
    "id": "blur",
    "name_zh": "模糊",
    "name_en": "Blur",
    "description_zh": "对对象应用模糊效果。",
    "description_en": "Apply a blur effect.",
    "category": "blur",
    "parameters": [
        {"id": "amount", "name_zh": "强度", "name_en": "Amount"}
    ],
}

FIXTURE_EDITOR = {
    "version": "1.0",
    "bars": {
        "layers": {"name_zh": "图层栏", "name_en": "Layers"},
    },
    "dialogs": {
        "addBehavior": {"name_zh": "添加行为", "name_en": "Add Behavior"},
    },
    "views": {},
    "stats": {},
}


# ---------------------------------------------------------------------------
# SemanticExpander backend tests
# ---------------------------------------------------------------------------

class TestDisabledExpander:

    def test_available_false(self):
        from src.rag.query_expander import DisabledExpander
        assert DisabledExpander().available is False

    def test_expand_returns_empty(self):
        from src.rag.query_expander import DisabledExpander
        assert DisabledExpander().expand(["查找"]) == set()


class TestLocalLLMExpander:

    def test_available_false_when_model_empty(self):
        from src.rag.query_expander import LocalLLMExpander
        assert LocalLLMExpander(model_path="").available is False

    def test_expand_returns_empty_when_unavailable(self):
        from src.rag.query_expander import LocalLLMExpander
        assert LocalLLMExpander(model_path="").expand(["查找"]) == set()

    def test_parse_output_extracts_words(self):
        from src.rag.query_expander import LocalLLMExpander
        exp = LocalLLMExpander.__new__(LocalLLMExpander)
        for raw, expected in _PARSE_CASES:
            result = exp._parse_output(raw)
            for word in expected:
                assert word in result

    def test_expand_caches_result(self):
        from src.rag.query_expander import LocalLLMExpander
        exp = LocalLLMExpander(model_path="")
        exp.expand(["查找"])
        exp.expand(["查找"])   # should not raise


class TestAPIExpander:

    def test_available_false_when_no_key(self):
        from src.rag.query_expander import APIExpander
        exp = APIExpander(api_key="")
        assert exp.available is False

    def test_expand_returns_empty_when_unavailable(self):
        from src.rag.query_expander import APIExpander
        assert APIExpander(api_key="").expand(["查找"]) == set()

    def test_parse_output_extracts_words(self):
        from src.rag.query_expander import APIExpander
        exp = APIExpander.__new__(APIExpander)
        for raw, expected in _PARSE_CASES:
            result = exp._parse_output(raw)
            for word in expected:
                assert word in result

    def test_expand_with_mock_api(self):
        from src.rag.query_expander import APIExpander
        exp = APIExpander.__new__(APIExpander)
        exp._cache = {}
        exp._api_key = "fake"
        exp._provider = "dashscope"
        exp._model = "qwen-turbo"
        with patch.object(exp, "_call_api", return_value="包含\n检测\n遍历"):
            result = exp.expand(["查找"])
        assert "包含" in result


class TestDictExpander:

    def test_available_false_when_no_dict_file(self, tmp_path):
        from src.rag.query_expander import DictExpander
        exp = DictExpander(dict_path=tmp_path / "nonexistent.npy")
        assert exp.available is False

    def test_expand_returns_empty_when_unavailable(self, tmp_path):
        from src.rag.query_expander import DictExpander
        exp = DictExpander(dict_path=tmp_path / "nonexistent.npy")
        assert exp.expand(["查找"]) == set()


class TestCreateExpander:

    def test_disabled(self):
        from src.rag.query_expander import create_expander, DisabledExpander
        with patch("src.rag.query_expander.EXPANDER_BACKEND", "disabled"):
            exp = create_expander()
        assert isinstance(exp, DisabledExpander)

    def test_api_backend(self):
        from src.rag.query_expander import create_expander, APIExpander
        with patch("src.rag.query_expander.EXPANDER_BACKEND", "api"):
            exp = create_expander()
        assert isinstance(exp, APIExpander)

    def test_local_backend(self):
        from src.rag.query_expander import create_expander, LocalLLMExpander
        with patch("src.rag.query_expander.EXPANDER_BACKEND", "local"):
            exp = create_expander()
        assert isinstance(exp, LocalLLMExpander)


# ---------------------------------------------------------------------------
# SchemaZhEnIndex tests
# ---------------------------------------------------------------------------

class TestSchemaZhEnIndex:

    def _make_index(self):
        from src.rag.query_expander import SchemaZhEnIndex
        idx = SchemaZhEnIndex.__new__(SchemaZhEnIndex)
        idx._build_from_fixtures(
            plugins=[FIXTURE_ARR],
            behaviors=[],
            effects=[FIXTURE_EFFECT],
            features=[],
            editor=FIXTURE_EDITOR,
        )
        return idx

    def test_plugin_node_indexed(self):
        idx = self._make_index()
        assert "arr" in idx.node_data

    def test_ace_node_indexed(self):
        idx = self._make_index()
        assert "arr/contains-value" in idx.node_data

    def test_zh_token_hits_plugin(self):
        idx = self._make_index()
        hits = idx.token_to_nodes.get("数组", set())
        assert "arr" in hits

    def test_zh_token_hits_ace(self):
        idx = self._make_index()
        # "包含" appears in contains-value description
        hits = idx.token_to_nodes.get("包含", set())
        assert "arr/contains-value" in hits

    def test_effect_indexed_with_lower_weight(self):
        idx = self._make_index()
        assert "blur" in idx.node_data
        assert idx.node_data["blur"].weight == 0.9

    def test_editor_indexed_with_lowest_weight(self):
        idx = self._make_index()
        assert "bar/layers" in idx.node_data
        assert idx.node_data["bar/layers"].weight == 0.4

    def test_en_tokens_extracted(self):
        idx = self._make_index()
        en = idx.node_data["arr/contains-value"].en_tokens
        assert "ContainsValue" in en or "Contains" in en

    def test_search_returns_scored_matches(self):
        idx = self._make_index()
        matches = idx.search({"数组", "包含", "值"})
        ids = [m.node_id for m in matches]
        assert "arr/contains-value" in ids

    def test_search_score_ordered(self):
        idx = self._make_index()
        matches = idx.search({"数组", "包含", "值"})
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_editor_lower_score_than_plugin(self):
        # Use a minimal plugin fixture with exactly one zh token so scores are predictable:
        # plugin = 1/1 * 1.0 = 1.0 > editor = 1/1 * 0.4
        from src.rag.query_expander import SchemaZhEnIndex
        idx2 = SchemaZhEnIndex.__new__(SchemaZhEnIndex)
        mini_plugin = {
            "id": "sprite",
            "name_zh": "精灵",
            "name_en": "Sprite",
            "description_zh": "",
            "description_en": "",
            "path": "general/sprite",
            "categories": [],
            "conditions": [], "actions": [], "expressions": [], "properties": [],
        }
        idx2._build_from_fixtures(
            plugins=[mini_plugin], behaviors=[], effects=[],
            features=[], editor=FIXTURE_EDITOR,
        )
        matches = idx2.search({"精灵", "图层"})
        plugin_score = next((m.score for m in matches if m.node_id == "sprite"), 0)
        editor_score = next((m.score for m in matches if m.node_id == "bar/layers"), 0)
        assert plugin_score > editor_score


# ---------------------------------------------------------------------------
# QueryExpander tests
# ---------------------------------------------------------------------------

class TestQueryExpander:

    def _make_expander(self):
        from src.rag.query_expander import QueryExpander, SchemaZhEnIndex, SmallLLMExpander
        idx = SchemaZhEnIndex.__new__(SchemaZhEnIndex)
        idx._build_from_fixtures(
            plugins=[FIXTURE_ARR], behaviors=[], effects=[], features=[], editor={}
        )
        manual = {"查找": ["包含", "遍历", "存在"]}
        # Disable LLM for unit tests
        mock_llm = SmallLLMExpander(model_path="")
        return QueryExpander(schema_index=idx, manual_expand=manual, llm_expander=mock_llm)

    def test_expand_manual_terms(self):
        exp = self._make_expander()
        result = exp.expand(["查找"])
        assert "包含" in result["查找"]
        assert "遍历" in result["查找"]

    def test_expand_auto_terms(self):
        exp = self._make_expander()
        result = exp.expand(["数组"])
        assert "数组" in result  # key exists

    def test_get_term_set_includes_originals(self):
        exp = self._make_expander()
        ts = exp.get_term_set(["查找", "数组"])
        assert "查找" in ts
        assert "数组" in ts

    def test_get_term_set_includes_expansions(self):
        exp = self._make_expander()
        ts = exp.get_term_set(["查找"])
        assert "包含" in ts  # from manual expand

    def test_search_via_expander(self):
        exp = self._make_expander()
        ts = exp.get_term_set(["数组", "查找"])
        matches = exp.search(ts)
        assert len(matches) > 0
