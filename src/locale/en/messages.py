"""
English UI labels, error messages, and display strings.
"""

# ---------------------------------------------------------------------------
# ACE section labels — long form with English in parentheses
# ---------------------------------------------------------------------------

ACE_SECTION_LABELS: dict[str, str] = {
    "conditions": "Conditions",
    "actions": "Actions",
    "expressions": "Expressions",
    "properties": "Properties",
    "scripting": "Scripting",
}


# ---------------------------------------------------------------------------
# ACE section labels — short form
# ---------------------------------------------------------------------------

ACE_SECTION_LABELS_SHORT: dict[str, str] = {
    "conditions": "Condition",
    "actions": "Action",
    "expressions": "Expression",
    "properties": "Property",
}


# ---------------------------------------------------------------------------
# Tier labels for lookup analysis display
# ---------------------------------------------------------------------------

TIER_LABELS: dict[int, str] = {
    1: "Rule match",
    2: "Embedding similarity",
    3: "Ollama classification",
}


# ---------------------------------------------------------------------------
# Language labels
# ---------------------------------------------------------------------------

LANG_LABELS: dict[str, str] = {
    "zh": "Chinese",
    "en": "English",
}


# ---------------------------------------------------------------------------
# Plugin/behavior kind labels
# ---------------------------------------------------------------------------

PLUGIN_KIND_LABELS: dict[str, str] = {
    "plugin": "plugin",
    "behavior": "behavior",
}


# ---------------------------------------------------------------------------
# Clipboard JSON validation error templates
# ---------------------------------------------------------------------------

VALIDATION_ERRORS: dict[str, str] = {
    "json_parse": "JSON parse error: {error}",
    "missing_clipboard_header": "Missing 'is-c3-clipboard-data': true",
    "invalid_clipboard_type": "Invalid clipboard type: {type}",
    "items_not_array": "'items' must be an array",
    "invalid_event_type": "{path}: Invalid eventType: {type}",
    "comment_missing_text": "{path}: comment missing 'text' field",
    "variable_missing_name": "{path}: variable missing 'name'",
    "invalid_var_type": "{path}: Invalid variable type: {type}",
    "variable_suggest_initial": "{path}: variable should set 'initialValue'",
    "variable_suggest_comment": "{path}: variable should add 'comment' field (can be empty string)",
    "group_missing_title": "{path}: group missing 'title'",
    "function_missing_name": "{path}: function-block missing 'functionName'",
    "invalid_return_type": "{path}: Invalid return type: {type}",
    "condition_missing_id": "{path}: condition missing 'id'",
    "condition_missing_object": "{path}: condition missing 'objectClass'",
    "invalid_comparison": "{path}: Invalid comparison operator: {value}",
    "action_comment_missing_text": "{path}: action comment missing 'text'",
    "action_missing_id": "{path}: action missing 'id'",
    "action_missing_object": "{path}: action missing 'objectClass'",
    "no_json_extracted": "Unable to extract valid JSON from response",
    "no_schema": "(No matching Schema)",
}


# ---------------------------------------------------------------------------
# No available model label (used in models.py dropdown)
# ---------------------------------------------------------------------------

NO_MODEL_LABEL: str = "No available models"


# ---------------------------------------------------------------------------
# Context formatting labels (from chain.py)
# ---------------------------------------------------------------------------

CONTEXT_HEADER: str = "## References ({count} items)"
CONTEXT_HEADER_STRICT: str = "## References (answers must be based on these sources)"
SOURCE_LABEL: str = "Source: {source}"


# ---------------------------------------------------------------------------
# ACE list formatting (from lookup.py)
# ---------------------------------------------------------------------------

ACE_LIST_HEADER: str = "**{name_zh} ({name_en})** {kind} {type_label}, {count} items:\n"
ACE_TABLE_HEADER: str = "| # | Name | English | Description |"
ACE_TABLE_SEPARATOR: str = "|---|------|---------|-------------|"


# ---------------------------------------------------------------------------
# ACE detail formatting (from lookup.py)
# ---------------------------------------------------------------------------

ACE_DETAIL_HEADER: str = "**{name_zh} ({name_en})** — {type_label}: **{item_zh}** ({item_en})\n"
ACE_DESCRIPTION_LABEL: str = "Description: {description}"
ACE_SCRIPT_NAME: str = "\nScript name: `{script}`"
ACE_TRIGGER_TYPE: str = "\nType: Trigger"
ACE_PARAMS_HEADER: str = "\n**Parameters** ({count}):\n"
ACE_PARAM_TABLE_HEADER: str = "| # | Name | English | Type |"
ACE_PARAM_TABLE_SEPARATOR: str = "|---|------|---------|------|"
ACE_NO_PARAMS: str = "\nNo parameters."


# ---------------------------------------------------------------------------
# ACE search formatting (from lookup.py)
# ---------------------------------------------------------------------------

ACE_SEARCH_HEADER: str = '**{name_zh} ({name_en})** {kind} features related to "{filter_term}", {count} items:\n'


# ---------------------------------------------------------------------------
# Term translation formatting (from lookup.py)
# ---------------------------------------------------------------------------

TERM_TRANSLATE_HEADER: str = '**"{term}"** translation results, {count} items:\n'
TERM_TABLE_HEADER: str = "| # | Chinese | English | Key |"
TERM_TABLE_SEPARATOR: str = "|---|---------|---------|-----|"
