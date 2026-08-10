"""Intent execution and compatibility formatting for deterministic Lookup."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import jieba

from src.domain.lookup import ACELocale, LookupIntent, LookupMatch
from src.lookup.examples_index import ExamplesIndex
from src.lookup.formatting import (
    ACE_PREFIX,
    ACE_SORT_ORDER,
    TERM_TABLE_HEADER,
    TERM_TABLE_SEPARATOR,
    TERM_TRANSLATE_HEADER,
    build_zh_line,
    format_condition_sig,
    format_params,
    match_from_item,
)
from src.lookup.schema_index import SchemaIndex
from src.lookup.term_index import TermIndex


class LookupHandlers:
    """Mixin containing the intent-to-result handlers used by LookupEngine."""

    schema_index: SchemaIndex
    term_index: TermIndex
    examples_index: ExamplesIndex
    _trace: Callable[[str, str], None]
    _directed_aliases_provider: Callable[[], Iterable[Any]]

    def _execute(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Execute one classified intent and return context plus typed matches."""
        handlers = {
            "ace_list": self._format_ace_list,
            "prop_list": self._format_prop_list,
            "ace_detail": self._format_ace_detail,
            "ace_search": self._format_ace_search,
            "term_translate": self._format_term_translate,
            "example_find": self._format_example_find,
        }
        handler = handlers.get(intent.intent_type)
        return handler(intent) if handler is not None else ("", [])

    @staticmethod
    def _get_example_tag(schema: dict, intent: LookupIntent) -> str:
        canonical_id = schema.get(
            "originalId",
            schema.get("name_en", intent.plugin_id),
        )
        prefix = "behavior" if intent.is_behavior else "plugin"
        return f"{prefix}-{canonical_id}"

    def _format_ace_list(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        schema = self.schema_index.get_schema(
            intent.plugin_id,
            intent.is_behavior,
        )
        if not schema:
            return "", []

        ace_types = [
            value.strip()
            for value in intent.ace_type.split(",")
            if value.strip()
        ]
        if len(ace_types) > 1:
            contexts = []
            all_matches = []
            for ace_type in ace_types:
                sub_intent = LookupIntent(
                    intent_type="ace_list",
                    plugin_id=intent.plugin_id,
                    ace_type=ace_type,
                    is_behavior=intent.is_behavior,
                    tier=intent.tier,
                    confidence=intent.confidence,
                    matched_tags=intent.matched_tags,
                )
                context, matches = self._format_ace_list(sub_intent)
                if context:
                    contexts.append(context)
                    all_matches.extend(matches)
            return "\n".join(contexts), all_matches

        ace_type = ace_types[0] if ace_types else intent.ace_type
        items = schema.get(ace_type, [])
        if not items:
            return "", []

        singular = {
            "conditions": "condition",
            "actions": "action",
            "expressions": "expression",
        }
        prefix = ACE_PREFIX.get(ace_type, "?")
        plugin_en = schema.get(
            "name_en",
            schema.get("originalId", intent.plugin_id),
        )
        plugin_zh = schema.get("name_zh", "")
        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []
        for item in items:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            description = item.get("description_en", "") or item.get(
                "description_zh", ""
            )
            params = item.get("params", [])
            signature = (
                format_condition_sig(name_en, params)
                if ace_type == "conditions"
                else f"{name_en}({format_params(params)})"
            )
            lines.append(f"{prefix}: {signature}: {description}")
            if name_zh and name_zh != name_en:
                zh_pairs.append((name_en, name_zh))
            matches.append(
                match_from_item(
                    item,
                    singular.get(ace_type, ace_type),
                    intent.plugin_id,
                    plugin_zh,
                    name_en,
                    name_zh,
                    params,
                    collection=(
                        "behaviors" if intent.is_behavior else "plugins"
                    ),
                )
            )

        lines.append(build_zh_line(plugin_en, plugin_zh, zh_pairs))
        example_tag = self._get_example_tag(schema, intent)
        example_records = self.examples_index.search(
            [example_tag],
            max_results=3,
        )
        example_line = ExamplesIndex.format_for_ace(example_records)
        if example_line:
            lines.extend(("", example_line))
        return "\n".join(line for line in lines if line), matches

    def _format_ace_detail(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        schema = self.schema_index.get_schema(
            intent.plugin_id,
            intent.is_behavior,
        )
        if not schema:
            return "", []

        target = intent.ace_name.strip().lower()
        found_item = None
        found_type = ""
        for ace_type in ("actions", "conditions", "expressions"):
            for item in schema.get(ace_type, []):
                if any(
                    target in value
                    for value in (
                        item.get("name_zh", "").lower(),
                        item.get("name_en", "").lower(),
                        item.get("id", "").lower(),
                    )
                ):
                    found_item = item
                    found_type = ace_type
                    break
            if found_item:
                break
        if not found_item:
            return "", []

        singular = {
            "conditions": "condition",
            "actions": "action",
            "expressions": "expression",
        }
        plugin_en = schema.get("name_en", intent.plugin_id)
        plugin_zh = schema.get("name_zh", "")
        name_en = found_item.get("name_en", "")
        name_zh = found_item.get("name_zh", "")
        description = found_item.get("description_en", "") or found_item.get(
            "description_zh", ""
        )
        params = found_item.get("params", [])
        signature = (
            format_condition_sig(name_en, params)
            if found_type == "conditions"
            else f"{name_en}({format_params(params)})"
        )
        lines = [f"{ACE_PREFIX.get(found_type, '?')}: {signature}: {description}"]
        for param in params:
            param_name = param.get("name_en", "")
            param_type = param.get("type", "")
            param_description = param.get("desc_en", "") or param.get(
                "desc_zh", ""
            )
            lines.append(
                f"  - {param_name} ({param_type}): {param_description}"
            )

        zh_pairs = (
            [(name_en, name_zh)]
            if name_zh and name_zh != name_en
            else []
        )
        lines.append(build_zh_line(plugin_en, plugin_zh, zh_pairs))
        example_tag = self._get_example_tag(schema, intent)
        example_records = self.examples_index.search(
            [example_tag],
            max_results=3,
        )
        example_line = ExamplesIndex.format_for_ace(example_records)
        if example_line:
            lines.extend(("", example_line))

        match = match_from_item(
            found_item,
            singular.get(found_type, found_type),
            intent.plugin_id,
            plugin_zh,
            name_en,
            name_zh,
            params,
            collection="behaviors" if intent.is_behavior else "plugins",
        )
        return "\n".join(line for line in lines if line), [match]

    @staticmethod
    def _compact_param(param: dict) -> str:
        name = param.get("name_en") or param.get(
            "name_zh", param.get("id", "")
        )
        value = f"{name}({param.get('type', '')})"
        items_i18n = param.get("items_i18n", {})
        if items_i18n:
            options = [
                item.get("en", key)
                for key, item in list(items_i18n.items())[:5]
            ]
            value += f"[{'/'.join(options)}]"
        elif param.get("items"):
            value += f"[{'/'.join(str(item) for item in param['items'][:5])}]"
        return value

    @staticmethod
    def _supports_common_aces(schema: dict, is_behavior: bool) -> bool:
        if is_behavior:
            return False
        property_ids = {
            prop.get("id", "") for prop in schema.get("properties", [])
        }
        return "initially-visible" in property_ids

    def _scoped_filter_words(
        self,
        filter_words: set[str],
        plugin_id: str,
        ace_type: str,
    ) -> dict[str, float]:
        """Return original terms and weighted one-hop aliases for this scope."""
        expanded = dict.fromkeys(filter_words, 1.0)
        for rule in self._directed_aliases_provider():
            if plugin_id not in rule.plugin_ids or ace_type not in rule.ace_types:
                continue
            triggered = bool(filter_words & rule.triggers)
            if rule.exact and not filter_words <= rule.triggers:
                triggered = False
            if not triggered:
                continue
            for addition in rule.additions:
                expanded[addition] = max(
                    expanded.get(addition, 0.0),
                    rule.weight,
                )
            self._trace(f"Directed alias: {rule.rule_id}", "lookup")
        return expanded

    def _format_ace_search(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        schema = self.schema_index.get_schema(
            intent.plugin_id,
            intent.is_behavior,
        )
        if not schema:
            return "", []

        raw_words = [
            word for word in intent.filter_term.lower().split() if word
        ]
        if not raw_words:
            return "", []
        filter_words = set(raw_words)
        for word in raw_words:
            if any("\u4e00" <= char <= "\u9fff" for char in word):
                filter_words.update(
                    segment
                    for segment in jieba.lcut(word, cut_all=True)
                    if len(segment) >= 2
                )

        ace_types = sorted(
            [
                value.strip()
                for value in intent.ace_type.split(",")
                if value.strip()
            ],
            key=lambda value: ACE_SORT_ORDER.get(value, 99),
        )
        if not ace_types:
            return "", []

        schemas_to_search: list[tuple[str, dict, bool]] = [
            (intent.plugin_id, schema, intent.is_behavior)
        ]
        if self._supports_common_aces(schema, intent.is_behavior):
            common_schema = self.schema_index.get_schema("_common", False)
            if common_schema:
                schemas_to_search.append(("_common", common_schema, False))

        candidates: list[
            tuple[float, int, int, int, int, int, str, dict, str, dict]
        ] = []
        for schema_order, (source_id, current_schema, _) in enumerate(
            schemas_to_search
        ):
            for ace_type in ace_types:
                scoped_words = self._scoped_filter_words(
                    filter_words,
                    source_id,
                    ace_type,
                )
                for item_order, item in enumerate(
                    current_schema.get(ace_type, [])
                ):
                    name_text = " ".join(
                        (
                            item.get("name_zh", ""),
                            item.get("name_en", ""),
                        )
                    ).lower()
                    matched_words = [
                        word for word in scoped_words if word in name_text
                    ]
                    if not matched_words:
                        continue
                    first_position = min(
                        name_text.find(word) for word in matched_words
                    )
                    candidates.append(
                        (
                            sum(scoped_words[word] for word in matched_words),
                            len(matched_words),
                            first_position,
                            schema_order,
                            ACE_SORT_ORDER.get(ace_type, 99),
                            item_order,
                            source_id,
                            current_schema,
                            ace_type,
                            item,
                        )
                    )
        if not candidates:
            return "", []

        best_score = max(candidate[0] for candidate in candidates)
        candidates = [
            candidate
            for candidate in candidates
            if candidate[0] >= best_score / 2
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate[0],
                -candidate[1],
                candidate[2],
                candidate[3],
                candidate[4],
                candidate[5],
            )
        )

        plugin_en = schema.get(
            "name_en",
            schema.get("originalId", intent.plugin_id),
        )
        plugin_zh = schema.get("name_zh", "")
        lines: list[str] = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []
        singular = {
            "conditions": "condition",
            "actions": "action",
            "expressions": "expression",
        }
        for (
            _,
            match_count,
            _,
            _,
            _,
            _,
            source_id,
            current_schema,
            ace_type,
            item,
        ) in candidates:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            description = item.get("description_en", "") or item.get(
                "description_zh", ""
            )
            params = item.get("params", [])
            signature = (
                name_en
                if ace_type == "conditions"
                else f"{name_en}({format_params(params)})"
            )
            line = f"[{ACE_PREFIX.get(ace_type, '?')}] {signature}: {description}"
            display = item.get("display_en") or item.get("display_zh", "")
            if display:
                line += f' display="{display}"'
            if params:
                line += " params=" + ",".join(
                    self._compact_param(param) for param in params
                )
            lines.append(line)
            if name_zh and name_zh != name_en:
                zh_pairs.append((name_en, name_zh))

            match = match_from_item(
                item,
                singular.get(ace_type, ace_type),
                source_id,
                current_schema.get("name_zh", ""),
                name_en,
                name_zh,
                params,
                collection="behaviors" if intent.is_behavior else "plugins",
            )
            match.relevance = match_count
            matches.append(match)

        lines.append(build_zh_line(plugin_en, plugin_zh, zh_pairs))
        return "\n".join(line for line in lines if line), matches

    def _format_prop_list(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        schema = self.schema_index.get_schema(
            intent.plugin_id,
            intent.is_behavior,
        )
        if not schema:
            return "", []
        items = schema.get("properties", [])
        if not items:
            return "", []

        plugin_en = schema.get(
            "name_en",
            schema.get("originalId", intent.plugin_id),
        )
        plugin_zh = schema.get("name_zh", "")
        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []
        for item in items:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            description = item.get("description_en", "") or item.get(
                "description_zh", ""
            )
            lines.append(f"P: {name_en}: {description}")
            if name_zh and name_zh != name_en:
                zh_pairs.append((name_en, name_zh))
            matches.append(
                match_from_item(
                    item,
                    "property",
                    intent.plugin_id,
                    plugin_zh,
                    name_en,
                    name_zh,
                    collection=(
                        "behaviors" if intent.is_behavior else "plugins"
                    ),
                )
            )
        lines.append(build_zh_line(plugin_en, plugin_zh, zh_pairs))
        return "\n".join(line for line in lines if line), matches

    def _format_term_translate(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        results = self.term_index.search(intent.term, max_results=15)
        if not results:
            return "", []

        lines = [
            TERM_TRANSLATE_HEADER.format(
                term=intent.term,
                count=len(results),
            ),
            TERM_TABLE_HEADER,
            TERM_TABLE_SEPARATOR,
        ]
        seen_keys: set[str] = set()
        matches: list[LookupMatch] = []
        for result in results:
            identity = result["key"] or f"{result['zh']}|{result['en']}"
            if identity in seen_keys:
                continue
            seen_keys.add(identity)
            key = result["key"]
            display_key = "..." + key[-47:] if len(key) > 50 else key
            lines.append(
                f"| {len(seen_keys)} | {result['zh']} | {result['en']} | "
                f"`{display_key}` |"
            )
            parts = key.split(".")
            plugin_id = parts[1] if len(parts) >= 2 else ""
            if len(parts) == 3 and parts[2] == "name":
                ace_type = "plugin"
                ace_id = "name"
            elif len(parts) >= 4:
                ace_type = {
                    "actions": "action",
                    "conditions": "condition",
                    "expressions": "expression",
                    "properties": "property",
                }.get(parts[2], parts[2].removesuffix("s"))
                ace_id = parts[3]
            else:
                ace_type = "term"
                ace_id = key or result["en"]
            matches.append(
                LookupMatch(
                    ace_id=ace_id,
                    ace_type=ace_type,
                    plugin_id=plugin_id,
                    collection="terms",
                    en=ACELocale(name=result["en"]),
                    zh=ACELocale(name=result["zh"]),
                )
            )
        lines.append("\n[Source: 1] Construct 3 CDN translation terms")
        return "\n".join(lines), matches

    def _format_example_find(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        results = self.examples_index.search(
            intent.matched_tags or [],
            max_results=5,
        )
        if not results and intent.filter_term:
            results = self.examples_index.search_fallback(
                intent.filter_term,
                max_results=5,
            )
        matches = [
            LookupMatch(
                ace_id=record.get("slug", ""),
                ace_type="example",
                plugin_id="",
                collection="examples",
                en=ACELocale(
                    name=record.get("title", record.get("slug", ""))
                ),
                zh=ACELocale(),
            )
            for record in results
            if record.get("slug")
        ]
        return ExamplesIndex.format_for_find(results), matches
