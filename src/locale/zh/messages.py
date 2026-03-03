"""
Chinese UI labels, error messages, and display strings.

All values are Chinese text shown to end users — they must stay in Chinese.
"""

# ---------------------------------------------------------------------------
# ACE section labels — long form with English in parentheses
# Used in chain.py, lookup.py, formatters.py, eventsheet_generator.py
# ---------------------------------------------------------------------------

ACE_SECTION_LABELS: dict[str, str] = {
    "conditions": "条件 (Conditions)",
    "actions": "动作 (Actions)",
    "expressions": "表达式 (Expressions)",
    "properties": "属性 (Properties)",
    "scripting": "脚本 (Scripting)",
}


# ---------------------------------------------------------------------------
# ACE section labels — short form (Chinese only)
# Used in lookup.py for compact display
# ---------------------------------------------------------------------------

ACE_SECTION_LABELS_SHORT: dict[str, str] = {
    "conditions": "条件",
    "actions": "动作",
    "expressions": "表达式",
    "properties": "属性",
}


# ---------------------------------------------------------------------------
# Tier labels for lookup analysis display
# ---------------------------------------------------------------------------

TIER_LABELS: dict[int, str] = {
    1: "规则匹配",
    2: "Embedding 相似度",
    3: "Ollama 分类",
}


# ---------------------------------------------------------------------------
# Language labels
# ---------------------------------------------------------------------------

LANG_LABELS: dict[str, str] = {
    "zh": "中文",
    "en": "英文",
}


# ---------------------------------------------------------------------------
# Plugin/behavior kind labels
# ---------------------------------------------------------------------------

PLUGIN_KIND_LABELS: dict[str, str] = {
    "plugin": "插件",
    "behavior": "行为",
}


# ---------------------------------------------------------------------------
# Clipboard JSON validation error templates
# ---------------------------------------------------------------------------

VALIDATION_ERRORS: dict[str, str] = {
    "json_parse": "JSON 解析错误: {error}",
    "missing_clipboard_header": "缺少 'is-c3-clipboard-data': true",
    "invalid_clipboard_type": "无效的剪贴板类型: {type}",
    "items_not_array": "'items' 必须是数组",
    "invalid_event_type": "{path}: 无效的 eventType: {type}",
    "comment_missing_text": "{path}: comment 缺少 'text' 字段",
    "variable_missing_name": "{path}: variable 缺少 'name'",
    "invalid_var_type": "{path}: 无效的变量类型: {type}",
    "variable_suggest_initial": "{path}: variable 建议设置 'initialValue'",
    "variable_suggest_comment": "{path}: variable 建议添加 'comment' 字段 (可为空字符串)",
    "group_missing_title": "{path}: group 缺少 'title'",
    "function_missing_name": "{path}: function-block 缺少 'functionName'",
    "invalid_return_type": "{path}: 无效的返回类型: {type}",
    "condition_missing_id": "{path}: condition 缺少 'id'",
    "condition_missing_object": "{path}: condition 缺少 'objectClass'",
    "invalid_comparison": "{path}: 无效的比较操作符: {value}",
    "action_comment_missing_text": "{path}: action comment 缺少 'text'",
    "action_missing_id": "{path}: action 缺少 'id'",
    "action_missing_object": "{path}: action 缺少 'objectClass'",
    "no_json_extracted": "无法从回复中提取有效的 JSON",
    "no_schema": "（无相关 Schema）",
}


# ---------------------------------------------------------------------------
# No available model label (used in models.py dropdown)
# ---------------------------------------------------------------------------

NO_MODEL_LABEL: str = "无可用模型"


# ---------------------------------------------------------------------------
# Context formatting labels (from chain.py)
# ---------------------------------------------------------------------------

CONTEXT_HEADER: str = "## 参考资料（共 {count} 条）"
CONTEXT_HEADER_STRICT: str = "## 参考资料（回答必须基于这些来源）"
SOURCE_LABEL: str = "来源: {source}"


# ---------------------------------------------------------------------------
# ACE list formatting (from lookup.py)
# ---------------------------------------------------------------------------

ACE_LIST_HEADER: str = "**{name_zh} ({name_en})** {kind}的{type_label}，共 {count} 项：\n"
ACE_TABLE_HEADER: str = "| # | 名称 | 英文名 | 说明 |"
ACE_TABLE_SEPARATOR: str = "|---|------|--------|------|"


# ---------------------------------------------------------------------------
# ACE detail formatting (from lookup.py)
# ---------------------------------------------------------------------------

ACE_DETAIL_HEADER: str = "**{name_zh} ({name_en})** — {type_label}: **{item_zh}** ({item_en})\n"
ACE_DESCRIPTION_LABEL: str = "说明：{description}"
ACE_SCRIPT_NAME: str = "\n脚本名称：`{script}`"
ACE_TRIGGER_TYPE: str = "\n类型：触发器 (Trigger)"
ACE_PARAMS_HEADER: str = "\n**参数** ({count} 个)：\n"
ACE_PARAM_TABLE_HEADER: str = "| # | 参数名 | 英文名 | 类型 |"
ACE_PARAM_TABLE_SEPARATOR: str = "|---|--------|--------|------|"
ACE_NO_PARAMS: str = "\n无参数。"


# ---------------------------------------------------------------------------
# ACE search formatting (from lookup.py)
# ---------------------------------------------------------------------------

ACE_SEARCH_HEADER: str = '**{name_zh} ({name_en})** {kind}与"{filter_term}"相关的功能，共 {count} 项：\n'


# ---------------------------------------------------------------------------
# Term translation formatting (from lookup.py)
# ---------------------------------------------------------------------------

TERM_TRANSLATE_HEADER: str = '**"{term}"** 的翻译结果，共 {count} 条：\n'
TERM_TABLE_HEADER: str = "| # | 中文 | 英文 | Key |"
TERM_TABLE_SEPARATOR: str = "|---|------|------|-----|"
