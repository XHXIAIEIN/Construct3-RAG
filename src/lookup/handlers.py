"""Intent execution and compatibility formatting for deterministic Lookup."""

from __future__ import annotations

from typing import NamedTuple

from src.domain.lookup import ACELocale, LookupIntent, LookupMatch
from src.locale.resources import ACE_DIRECTED_ALIASES
from src.lookup.examples_index import ExamplesIndex
from src.lookup.formatting import (
    ACE_PREFIX,
    ACE_SORT_ORDER,
    TERM_TABLE_HEADER,
    TERM_TABLE_SEPARATOR,
    TERM_TRANSLATE_HEADER,
    build_zh_line,
    format_params,
    format_signature,
    match_from_item,
)
from src.lookup.intent import expand_cjk_tokens
from src.lookup.schema_index import SchemaIndex
from src.lookup.schema_layout import SCHEMA_ACE_TYPES
from src.lookup.term_index import TermIndex


# The ace_type of a match, per ACE list of a schema file.
_SINGULAR = {
    "conditions": "condition",
    "actions": "action",
    "expressions": "expression",
}

# The ace_type of a translated term, per list its key names.
_TERM_SINGULAR = {**_SINGULAR, "properties": "property"}


def _ace_types_of(intent: LookupIntent) -> list[str]:
    """The ACE lists an intent names, from its comma-separated ``ace_type``."""
    return [value.strip() for value in intent.ace_type.split(",") if value.strip()]


def _collection(intent: LookupIntent) -> str:
    return "behaviors" if intent.is_behavior else "plugins"


def _description(item: dict) -> str:
    return item.get("description_en", "") or item.get("description_zh", "")


def _plugin_en(schema: dict, plugin_id: str) -> str:
    return schema.get("name_en", schema.get("originalId", plugin_id))


def _zh_line(schema: dict, plugin_id: str, zh_pairs: list[tuple[str, str]]) -> str:
    """The compatibility mapping line of an addon's result, empty when nothing maps."""
    return build_zh_line(_plugin_en(schema, plugin_id), schema.get("name_zh", ""), zh_pairs)


class _Candidate(NamedTuple):
    """One ACE whose name holds a filter word, with what ranks it."""

    score: float
    match_count: int
    first_position: int
    schema_order: int
    type_order: int
    item_order: int
    source_id: str
    schema: dict
    ace_type: str
    item: dict


class LookupHandlers:
    """Mixin containing the intent-to-result handlers used by LookupEngine."""

    schema_index: SchemaIndex
    term_index: TermIndex
    examples_index: ExamplesIndex

    def _execute(self, intent: LookupIntent) -> tuple[str, list[LookupMatch]]:
        """Execute one classified intent and return context plus typed matches."""
        handlers = {
            "ace_list": self._format_ace_list,
            "prop_list": self._format_prop_list,
            "ace_detail": self._format_ace_detail,
            "ace_search": self._format_ace_search,
            "term_translate": self._format_term_translate,
            "example_find": self._format_example_find,
            "effect_detail": self._format_effect_detail,
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

    def _example_line(self, schema: dict, intent: LookupIntent) -> str:
        """The "Related examples" line of an addon, empty when none uses it."""
        example_records = self.examples_index.search(
            [self._get_example_tag(schema, intent)],
            max_results=3,
            names=[schema.get("name_en", "")],
        )
        return ExamplesIndex.format_for_ace(example_records)

    def _common_schema_of(self, schema: dict) -> dict | None:
        """The part of ``_common`` the schema's ``commonAces`` lists, or None."""
        if not schema.get("commonAces"):
            return None
        common_schema = self.schema_index.get_schema("_common", False)
        if not common_schema:
            return None
        return self._plugin_common_aces(common_schema, schema)

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

        example_line = self._example_line(schema, intent)
        contexts: list[str] = []
        matches: list[LookupMatch] = []
        for ace_type in _ace_types_of(intent) or [intent.ace_type]:
            context, type_matches = self._ace_list_of_type(
                schema, intent, ace_type, example_line
            )
            if context:
                contexts.append(context)
                matches.extend(type_matches)
        return "\n".join(contexts), matches

    def _ace_list_of_type(
        self,
        schema: dict,
        intent: LookupIntent,
        ace_type: str,
        example_line: str,
    ) -> tuple[str, list[LookupMatch]]:
        # The complete list is the addon's own ACEs, then the shared ones its
        # commonAces lists from _common.json, keyed there.
        sources: list[tuple[str, str, list[dict]]] = [
            (intent.plugin_id, schema.get("name_zh", ""), schema.get(ace_type, []))
        ]
        common_schema = self._common_schema_of(schema)
        if common_schema:
            sources.append((
                "_common",
                common_schema.get("name_zh", ""),
                common_schema.get(ace_type, []),
            ))
        if not any(items for _, _, items in sources):
            return "", []

        prefix = ACE_PREFIX.get(ace_type, "?")
        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []
        for source_id, source_zh, items in sources:
            for item in items:
                name_en = item.get("name_en", "")
                name_zh = item.get("name_zh", "")
                params = item.get("params", [])
                signature = format_signature(ace_type, name_en, params)
                lines.append(f"{prefix}: {signature}: {_description(item)}")
                if name_zh and name_zh != name_en:
                    zh_pairs.append((name_en, name_zh))
                matches.append(
                    match_from_item(
                        item,
                        _SINGULAR.get(ace_type, ace_type),
                        source_id,
                        source_zh,
                        name_en,
                        name_zh,
                        params,
                        collection=_collection(intent),
                    )
                )

        lines.append(_zh_line(schema, intent.plugin_id, zh_pairs))
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
        found = next(
            (
                (ace_type, item)
                for ace_type in ("actions", "conditions", "expressions")
                for item in schema.get(ace_type, [])
                if any(
                    target in item.get(key, "").lower()
                    for key in ("name_zh", "name_en", "id")
                )
            ),
            None,
        )
        if found is None:
            return "", []
        found_type, found_item = found

        plugin_zh = schema.get("name_zh", "")
        name_en = found_item.get("name_en", "")
        name_zh = found_item.get("name_zh", "")
        params = found_item.get("params", [])
        signature = format_signature(found_type, name_en, params)
        lines = [
            f"{ACE_PREFIX.get(found_type, '?')}: {signature}: {_description(found_item)}"
        ]
        for param in params:
            param_description = param.get("desc_en", "") or param.get("desc_zh", "")
            lines.append(
                f"  - {param.get('name_en', '')} ({param.get('type', '')}): "
                f"{param_description}"
            )

        zh_pairs = (
            [(name_en, name_zh)]
            if name_zh and name_zh != name_en
            else []
        )
        lines.append(_zh_line(schema, intent.plugin_id, zh_pairs))
        example_line = self._example_line(schema, intent)
        if example_line:
            lines.extend(("", example_line))

        match = match_from_item(
            found_item,
            _SINGULAR.get(found_type, found_type),
            intent.plugin_id,
            plugin_zh,
            name_en,
            name_zh,
            params,
            collection=_collection(intent),
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
    def _plugin_common_aces(common_schema: dict, schema: dict) -> dict:
        """The part of `_common` the plugin's `commonAces` lists, by ACE type."""
        plugin_common = {
            key: value
            for key, value in common_schema.items()
            if key not in SCHEMA_ACE_TYPES
        }
        for ace_type, ace_ids in schema.get("commonAces", {}).items():
            listed = set(ace_ids)
            plugin_common[ace_type] = [
                item
                for item in common_schema.get(ace_type, [])
                if item.get("id") in listed
            ]
        return plugin_common

    def _scoped_filter_words(
        self,
        filter_words: set[str],
        plugin_id: str,
        ace_type: str,
    ) -> tuple[dict[str, float], set[str]]:
        """Return original terms and weighted one-hop aliases for this scope,
        and the ACE ids the triggered rules rule out."""
        expanded = dict.fromkeys(filter_words, 1.0)
        excluded: set[str] = set()
        for rule in ACE_DIRECTED_ALIASES:
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
            excluded |= rule.exclude_ids
        return expanded, excluded

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

        raw_words = intent.filter_term.lower().split()
        if not raw_words:
            return "", []
        filter_words = expand_cjk_tokens(raw_words)

        ace_types = sorted(
            _ace_types_of(intent),
            key=lambda value: ACE_SORT_ORDER.get(value, 99),
        )
        if not ace_types:
            return "", []

        schemas_to_search: list[tuple[str, dict]] = [(intent.plugin_id, schema)]
        common_schema = self._common_schema_of(schema)
        if common_schema:
            schemas_to_search.append(("_common", common_schema))

        candidates: list[_Candidate] = []
        for schema_order, (source_id, current_schema) in enumerate(schemas_to_search):
            for ace_type in ace_types:
                scoped_words, excluded_ids = self._scoped_filter_words(
                    filter_words,
                    source_id,
                    ace_type,
                )
                for item_order, item in enumerate(
                    current_schema.get(ace_type, [])
                ):
                    if item.get("id") in excluded_ids:
                        continue
                    names = (
                        item.get("name_zh", "").lower(),
                        item.get("name_en", "").lower(),
                    )
                    matched_words = [
                        word
                        for word in scoped_words
                        if any(word in name for name in names)
                    ]
                    if not matched_words:
                        continue
                    # Where the word sits in the name that holds it, so a
                    # long Chinese name does not push the English one back.
                    first_position = min(
                        name.find(word)
                        for word in matched_words
                        for name in names
                        if word in name
                    )
                    candidates.append(
                        _Candidate(
                            score=sum(scoped_words[word] for word in matched_words),
                            match_count=len(matched_words),
                            first_position=first_position,
                            schema_order=schema_order,
                            type_order=ACE_SORT_ORDER.get(ace_type, 99),
                            item_order=item_order,
                            source_id=source_id,
                            schema=current_schema,
                            ace_type=ace_type,
                            item=item,
                        )
                    )
        if not candidates:
            return "", []

        best_score = max(candidate.score for candidate in candidates)
        candidates = [
            candidate
            for candidate in candidates
            if candidate.score >= best_score / 2
        ]
        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                -candidate.match_count,
                candidate.type_order,
                candidate.first_position,
                candidate.schema_order,
                candidate.item_order,
            )
        )

        lines: list[str] = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []
        for candidate in candidates:
            item = candidate.item
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            params = item.get("params", [])
            signature = (
                name_en
                if candidate.ace_type == "conditions"
                else f"{name_en}({format_params(params)})"
            )
            line = (
                f"[{ACE_PREFIX.get(candidate.ace_type, '?')}] {signature}: "
                f"{_description(item)}"
            )
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
                _SINGULAR.get(candidate.ace_type, candidate.ace_type),
                candidate.source_id,
                candidate.schema.get("name_zh", ""),
                name_en,
                name_zh,
                params,
                collection=_collection(intent),
            )
            match.relevance = candidate.match_count
            matches.append(match)

        lines.append(_zh_line(schema, intent.plugin_id, zh_pairs))
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

        plugin_zh = schema.get("name_zh", "")
        lines = []
        zh_pairs: list[tuple[str, str]] = []
        matches: list[LookupMatch] = []
        for item in items:
            name_en = item.get("name_en", "")
            name_zh = item.get("name_zh", "")
            lines.append(f"P: {name_en}: {_description(item)}")
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
                    collection=_collection(intent),
                )
            )
        lines.append(_zh_line(schema, intent.plugin_id, zh_pairs))
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
                ace_type = _TERM_SINGULAR.get(parts[2], parts[2].removesuffix("s"))
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

    def _addon_display_names(self, tags: list[str]) -> list[str]:
        """English names of the addons an example tag names: Arr is Array."""
        names = []
        for tag in tags:
            resolved = self.schema_index.resolve_name(tag.split("-", 1)[-1])
            if resolved:
                schema = self.schema_index.get_schema(*resolved) or {}
                names.append(schema.get("name_en", ""))
        return [name for name in names if name]

    def _format_example_find(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        tags = intent.matched_tags or []
        results = self.examples_index.search(
            tags,
            max_results=5,
            names=self._addon_display_names(tags),
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

    def _format_effect_detail(
        self,
        intent: LookupIntent,
    ) -> tuple[str, list[LookupMatch]]:
        effect_ids = [
            tag.removeprefix("effect-")
            for tag in intent.matched_tags
            if tag.startswith("effect-")
        ] or [intent.plugin_id]
        lines: list[str] = []
        matches: list[LookupMatch] = []
        for effect_id in effect_ids:
            effect = self.schema_index.get_effect(effect_id)
            if effect is None:
                continue
            params = effect["params"]
            lines.append(
                f"[Effect] {effect['name_en']} ({effect['name_zh']}): "
                f"{effect['description_en']}"
            )
            lines.extend(
                f"  {param['name_en']} ({param['name_zh']}, {param['type']}): "
                f"{param['desc_en']}"
                for param in params
            )
            if not params:
                lines.append("  no parameters")
            matches.append(
                LookupMatch(
                    ace_id=effect_id,
                    ace_type="effect",
                    plugin_id=effect_id,
                    collection="effects",
                    en=ACELocale(
                        name=effect["name_en"], desc=effect["description_en"]
                    ),
                    zh=ACELocale(
                        name=effect["name_zh"], desc=effect["description_zh"]
                    ),
                    category=effect["category"],
                    params=params,
                )
            )
        return "\n".join(lines), matches
