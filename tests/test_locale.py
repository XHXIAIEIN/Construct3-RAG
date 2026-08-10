"""Contracts for aligned locale JSON consumed by production lookup paths."""

import json
import re
from pathlib import Path

from src.locale.resources import (
    ACE_DIRECTED_ALIASES,
    ACE_INTENT_KEYWORDS,
    ACE_TYPE_ALIASES,
    CATALOG,
    CATALOG_PATH,
    DETAIL_QUERY_PATTERNS,
    DirectedAliasRule,
    HOWTO_HARD_SKIP_ZH,
    HOWTO_SOFT_SKIP_ZH,
    LIST_QUERY_PATTERNS,
    SCOPED_ACE_TYPE_RULES_ZH_EN,
    SUPPORTED_LOCALES,
    TRANSLATE_QUERY_PATTERNS,
    format_ace_title_zh_en,
    format_effect_title_zh_en,
)


def test_catalog_stores_localized_values_side_by_side():
    parsed = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert parsed == CATALOG
    locale_keys = set(SUPPORTED_LOCALES)
    for resource in CATALOG["query"]["ace_types"].values():
        assert set(resource["aliases"]) == locale_keys
        assert set(resource["intent_keywords"]) == locale_keys
    for rule in CATALOG["query"]["scoped_ace_type_rules"].values():
        assert set(rule["terms"]) == locale_keys
    hints = CATALOG["index"]["common_ace_semantic_hints"]["values"]
    for hint in hints.values():
        assert set(hint) == locale_keys


def _catalog_resources():
    query = CATALOG["query"]
    yield from query["ace_types"].values()
    for rules in query["grammar"].values():
        yield from rules.values()
    yield from query["howto"].values()
    yield query["example_keywords"]
    yield from query["tokenization"].values()
    yield from query["ambiguity"].values()
    yield from query["scoped_ace_type_rules"].values()
    yield from CATALOG["expansion"]["directed_aliases"].values()
    yield from CATALOG["index"].values()


def test_every_catalog_resource_explains_origin_usage_and_coverage():
    required = {"purpose", "source", "consumers", "tests"}
    resources = list(_catalog_resources())
    assert resources
    assert all(required <= set(resource) for resource in resources)
    assert all(resource["purpose"] for resource in resources)
    assert all(resource["source"] for resource in resources)
    assert all(resource["consumers"] for resource in resources)
    assert all(resource["tests"] for resource in resources)
    repo_root = Path(__file__).parent.parent
    for resource in resources:
        for reference in resource["tests"]:
            test_path = reference.partition("::")[0]
            assert (repo_root / test_path).is_file(), reference


def test_catalog_references_canonical_consumers_not_compatibility_facades():
    resources = list(_catalog_resources())
    consumers = {
        consumer
        for resource in resources
        for consumer in resource["consumers"]
    }
    legacy_consumers = sorted(
        consumer
        for consumer in consumers
        if consumer.startswith("src.rag.") or consumer == "src.api._clean_content"
    )
    assert legacy_consumers == []

    sources = {
        source
        for resource in resources
        for source in resource["source"]
    }
    assert "contract:src.api._clean_content" not in sources


def test_gold_provenance_references_existing_case_ids():
    fixture = Path(__file__).with_name("fixtures") / "query_gold.jsonl"
    case_ids = {
        json.loads(line)["id"]
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    referenced = {
        source.removeprefix("gold:")
        for resource in _catalog_resources()
        for source in resource["source"]
        if source.startswith("gold:")
    }
    assert referenced
    assert referenced <= case_ids


def test_ace_intent_resources_only_target_supported_structural_types():
    supported = {"conditions", "actions", "expressions", "properties"}
    assert set(ACE_INTENT_KEYWORDS) == supported
    assert set(ACE_TYPE_ALIASES.values()) == supported
    assert all(set(rule.ace_types) <= supported for rule in SCOPED_ACE_TYPE_RULES_ZH_EN)


def test_query_grammar_patterns_are_anchored_and_compilable():
    for pattern in (*LIST_QUERY_PATTERNS, *DETAIL_QUERY_PATTERNS, *TRANSLATE_QUERY_PATTERNS):
        assert pattern.startswith(r"^\s*")
        assert pattern.endswith(r"\s*$")
        assert "{ace_type}" not in pattern
        re.compile(pattern, re.IGNORECASE)


def test_howto_hard_and_soft_markers_have_distinct_routing_semantics():
    assert HOWTO_HARD_SKIP_ZH.isdisjoint(HOWTO_SOFT_SKIP_ZH)
    assert "怎么实现" in HOWTO_HARD_SKIP_ZH
    assert "怎么" in HOWTO_SOFT_SKIP_ZH


def test_directed_aliases_are_scoped_weighted_single_hop_rules():
    assert ACE_DIRECTED_ALIASES
    assert all(isinstance(rule, DirectedAliasRule) for rule in ACE_DIRECTED_ALIASES)
    assert all(rule.rule_id for rule in ACE_DIRECTED_ALIASES)
    assert all(rule.triggers and rule.additions for rule in ACE_DIRECTED_ALIASES)
    assert all(rule.plugin_ids and rule.ace_types for rule in ACE_DIRECTED_ALIASES)
    assert all(0 < rule.weight <= 1 for rule in ACE_DIRECTED_ALIASES)
    assert all(not rule.allow_chaining for rule in ACE_DIRECTED_ALIASES)


def test_bilingual_index_format_stays_compatible():
    assert format_ace_title_zh_en(
        addon_type="plugin",
        addon_zh="精灵",
        addon_en="Sprite",
        ace_type="action",
        ace_zh="设置动画",
        ace_en="Set animation",
    ) == "插件 精灵(Sprite) 的动作: 设置动画 (Set animation)"
    assert format_effect_title_zh_en("膨胀", "Bulge") == "效果/Effect: 膨胀 (Bulge)"
