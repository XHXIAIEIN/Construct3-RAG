# event_generator.py
"""
Construct 3 Event Sheet JSON Generator

Zero-hallucination event sheet generation with:
1. Schema-driven ACE validation
2. Structured JSON output (clipboard format)
3. Copy-paste ready for Construct 3

剪贴板格式说明：
- 无需 sid（与项目文件格式不同）
- 所有参数值为字符串格式
- objectClass 对应项目中的对象类型名称
- behaviorType 对应行为的 name 字段
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .prompts import CLIPBOARD_FORMAT_REFERENCE, EVENT_JSON_GENERATION_PROMPT

# ============================================================
# Schema Loader & Cache
# ============================================================


@dataclass
class ACEParam:
    """ACE parameter definition"""

    id: str
    type: str
    name_zh: str
    name_en: str
    initial_value: Optional[str] = None
    items: Optional[List[str]] = None  # for combo type


@dataclass
class ACEDefinition:
    """Action/Condition/Expression definition"""

    id: str
    name_zh: str
    name_en: str
    description_zh: str
    description_en: str
    params: List[ACEParam] = field(default_factory=list)
    is_trigger: bool = False
    category: Optional[str] = None


@dataclass
class PluginSchema:
    """Plugin or Behavior schema"""

    id: str
    original_id: str
    name_zh: str
    name_en: str
    conditions: Dict[str, ACEDefinition] = field(default_factory=dict)
    actions: Dict[str, ACEDefinition] = field(default_factory=dict)
    expressions: Dict[str, ACEDefinition] = field(default_factory=dict)


class SchemaLoader:
    """Load and cache Construct 3 ACE schemas"""

    def __init__(self, schema_dir: str = None):
        if schema_dir is None:
            from src.config import SCHEMA_DIR

            schema_dir = SCHEMA_DIR
        self.schema_dir = Path(schema_dir)
        self._plugin_cache: Dict[str, PluginSchema] = {}
        self._behavior_cache: Dict[str, PluginSchema] = {}
        self._all_plugins_loaded = False
        self._all_behaviors_loaded = False
        # Dynamic keyword index built from schema files
        self._keyword_index: Dict[
            str, Tuple[str, str]
        ] = {}  # keyword -> (schema_id, type)
        self._keyword_index_built = False

    def _parse_params(self, params_data: List[Dict]) -> List[ACEParam]:
        """Parse parameter definitions"""
        result = []
        for p in params_data:
            param = ACEParam(
                id=p.get("id", ""),
                type=p.get("type", "any"),
                name_zh=p.get("name_zh", ""),
                name_en=p.get("name_en", ""),
                initial_value=p.get("initialValue"),
                items=p.get("items"),
            )
            result.append(param)
        return result

    def _parse_ace_list(self, ace_list: List[Dict]) -> Dict[str, ACEDefinition]:
        """Parse a list of ACE definitions"""
        result = {}
        for item in ace_list:
            ace = ACEDefinition(
                id=item.get("id", ""),
                name_zh=item.get("name_zh", ""),
                name_en=item.get("name_en", ""),
                description_zh=item.get("description_zh", ""),
                description_en=item.get("description_en", ""),
                params=self._parse_params(item.get("params", [])),
                is_trigger=item.get("isTrigger", False),
                category=item.get("category"),
            )
            result[ace.id] = ace
        return result

    def _load_schema_file(self, filepath: Path) -> Optional[PluginSchema]:
        """Load a single schema file"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            schema = PluginSchema(
                id=data.get("id", ""),
                original_id=data.get("originalId", ""),
                name_zh=data.get("name_zh", ""),
                name_en=data.get("name_en", ""),
                conditions=self._parse_ace_list(data.get("conditions", [])),
                actions=self._parse_ace_list(data.get("actions", [])),
                expressions=self._parse_ace_list(data.get("expressions", [])),
            )
            return schema
        except Exception as e:
            print(f"Error loading schema {filepath}: {e}")
            return None

    def load_plugin(self, plugin_id: str) -> Optional[PluginSchema]:
        """Load a specific plugin schema"""
        plugin_id = plugin_id.lower()
        if plugin_id in self._plugin_cache:
            return self._plugin_cache[plugin_id]

        filepath = self.schema_dir / "plugins" / f"{plugin_id}.json"
        if filepath.exists():
            schema = self._load_schema_file(filepath)
            if schema:
                self._plugin_cache[plugin_id] = schema
                return schema
        return None

    def load_behavior(self, behavior_id: str) -> Optional[PluginSchema]:
        """Load a specific behavior schema"""
        behavior_id = behavior_id.lower()
        if behavior_id in self._behavior_cache:
            return self._behavior_cache[behavior_id]

        filepath = self.schema_dir / "behaviors" / f"{behavior_id}.json"
        if filepath.exists():
            schema = self._load_schema_file(filepath)
            if schema:
                self._behavior_cache[behavior_id] = schema
                return schema
        return None

    def load_all_plugins(self) -> Dict[str, PluginSchema]:
        """Load all plugin schemas"""
        if self._all_plugins_loaded:
            return self._plugin_cache

        plugins_dir = self.schema_dir / "plugins"
        if plugins_dir.exists():
            for f in plugins_dir.glob("*.json"):
                if f.name != "index.json":
                    plugin_id = f.stem
                    self.load_plugin(plugin_id)

        self._all_plugins_loaded = True
        return self._plugin_cache

    def load_all_behaviors(self) -> Dict[str, PluginSchema]:
        """Load all behavior schemas"""
        if self._all_behaviors_loaded:
            return self._behavior_cache

        behaviors_dir = self.schema_dir / "behaviors"
        if behaviors_dir.exists():
            for f in behaviors_dir.glob("*.json"):
                if f.name != "index.json":
                    behavior_id = f.stem
                    self.load_behavior(behavior_id)

        self._all_behaviors_loaded = True
        return self._behavior_cache

    def build_keyword_index(self) -> Dict[str, Tuple[str, str]]:
        """
        Build keyword index from all schema files dynamically.
        Maps keywords (name_zh, name_en, id) to (schema_id, schema_type).
        """
        if self._keyword_index_built:
            return self._keyword_index

        self.load_all_plugins()
        self.load_all_behaviors()

        # Build index from plugins
        for schema_id, schema in self._plugin_cache.items():
            # Add schema name as keyword
            if schema.name_zh:
                self._keyword_index[schema.name_zh.lower()] = (schema_id, "plugin")
            if schema.name_en:
                self._keyword_index[schema.name_en.lower()] = (schema_id, "plugin")
            self._keyword_index[schema_id.lower()] = (schema_id, "plugin")

        # Build index from behaviors
        for schema_id, schema in self._behavior_cache.items():
            if schema.name_zh:
                self._keyword_index[schema.name_zh.lower()] = (schema_id, "behavior")
            if schema.name_en:
                self._keyword_index[schema.name_en.lower()] = (schema_id, "behavior")
            self._keyword_index[schema_id.lower()] = (schema_id, "behavior")

        self._keyword_index_built = True
        return self._keyword_index

    def find_schema_by_keyword(self, keyword: str) -> Optional[Tuple[str, str]]:
        """
        Find schema by keyword.
        Returns: (schema_id, schema_type) or None
        """
        self.build_keyword_index()
        keyword_lower = keyword.lower()

        # Exact match
        if keyword_lower in self._keyword_index:
            return self._keyword_index[keyword_lower]

        # Partial match
        for k, v in self._keyword_index.items():
            if keyword_lower in k or k in keyword_lower:
                return v

        return None

    def search_ace(
        self, query: str, ace_type: str = "all"
    ) -> List[Tuple[str, str, ACEDefinition]]:
        """
        Search for ACE by keyword
        Returns: [(plugin_id, ace_type, ace_def), ...]
        """
        self.load_all_plugins()
        self.load_all_behaviors()

        query_lower = query.lower()
        results = []

        for plugin_id, schema in {**self._plugin_cache, **self._behavior_cache}.items():
            if ace_type in ("all", "condition"):
                for ace in schema.conditions.values():
                    if (
                        query_lower in ace.id
                        or query_lower in ace.name_zh
                        or query_lower in ace.name_en.lower()
                    ):
                        results.append((plugin_id, "condition", ace))

            if ace_type in ("all", "action"):
                for ace in schema.actions.values():
                    if (
                        query_lower in ace.id
                        or query_lower in ace.name_zh
                        or query_lower in ace.name_en.lower()
                    ):
                        results.append((plugin_id, "action", ace))

            if ace_type in ("all", "expression"):
                for ace in schema.expressions.values():
                    if (
                        query_lower in ace.id
                        or query_lower in ace.name_zh
                        or query_lower in ace.name_en.lower()
                    ):
                        results.append((plugin_id, "expression", ace))

        return results


# ============================================================
# Clipboard JSON Validator
# ============================================================


class ClipboardValidator:
    """Validate Construct 3 clipboard JSON format"""

    VALID_CLIPBOARD_TYPES = {"events", "conditions", "actions"}
    VALID_EVENT_TYPES = {"comment", "variable", "group", "block", "function-block"}
    VALID_VAR_TYPES = {"number", "string", "boolean"}
    VALID_FUNCTION_RETURN_TYPES = {"none", "number", "string", "any"}
    COMPARISON_OPERATORS = {0, 1, 2, 3, 4, 5}  # =, !=, <, <=, >, >=

    def __init__(self, schema_loader: SchemaLoader):
        self.schema = schema_loader
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, json_str: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate clipboard JSON
        Returns: (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON 解析错误: {e}")
            return False, self.errors, self.warnings

        # Check clipboard header
        if not data.get("is-c3-clipboard-data"):
            self.errors.append("缺少 'is-c3-clipboard-data': true")

        clip_type = data.get("type")
        if clip_type not in self.VALID_CLIPBOARD_TYPES:
            self.errors.append(f"无效的剪贴板类型: {clip_type}")

        items = data.get("items", [])
        if not isinstance(items, list):
            self.errors.append("'items' 必须是数组")
            return False, self.errors, self.warnings

        # Validate items based on type
        if clip_type == "events":
            for i, item in enumerate(items):
                self._validate_event(item, f"items[{i}]")
        elif clip_type == "conditions":
            for i, item in enumerate(items):
                self._validate_condition(item, f"items[{i}]")
        elif clip_type == "actions":
            for i, item in enumerate(items):
                self._validate_action(item, f"items[{i}]")

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_event(self, event: Dict, path: str):
        """Validate a single event"""
        event_type = event.get("eventType")

        if event_type not in self.VALID_EVENT_TYPES:
            self.errors.append(f"{path}: 无效的 eventType: {event_type}")
            return

        if event_type == "comment":
            if "text" not in event:
                self.errors.append(f"{path}: comment 缺少 'text' 字段")

        elif event_type == "variable":
            self._validate_variable(event, path)

        elif event_type == "group":
            self._validate_group(event, path)

        elif event_type == "block":
            self._validate_block(event, path)

        elif event_type == "function-block":
            self._validate_function_block(event, path)

    def _validate_variable(self, var: Dict, path: str):
        """Validate variable definition"""
        if "name" not in var:
            self.errors.append(f"{path}: variable 缺少 'name'")

        var_type = var.get("type")
        if var_type not in self.VALID_VAR_TYPES:
            self.errors.append(f"{path}: 无效的变量类型: {var_type}")

        if "initialValue" not in var:
            self.warnings.append(f"{path}: variable 建议设置 'initialValue'")

    def _validate_group(self, group: Dict, path: str):
        """Validate event group"""
        if "title" not in group:
            self.errors.append(f"{path}: group 缺少 'title'")

        children = group.get("children", [])
        for i, child in enumerate(children):
            self._validate_event(child, f"{path}.children[{i}]")

    def _validate_block(self, block: Dict, path: str):
        """Validate event block"""
        conditions = block.get("conditions", [])
        actions = block.get("actions", [])

        for i, cond in enumerate(conditions):
            self._validate_condition(cond, f"{path}.conditions[{i}]")

        for i, action in enumerate(actions):
            self._validate_action(action, f"{path}.actions[{i}]")

        children = block.get("children", [])
        for i, child in enumerate(children):
            self._validate_event(child, f"{path}.children[{i}]")

    def _validate_function_block(self, func: Dict, path: str):
        """Validate function definition"""
        if "functionName" not in func:
            self.errors.append(f"{path}: function-block 缺少 'functionName'")

        ret_type = func.get("functionReturnType", "none")
        if ret_type not in self.VALID_FUNCTION_RETURN_TYPES:
            self.errors.append(f"{path}: 无效的返回类型: {ret_type}")

        # Validate conditions, actions, children
        self._validate_block(func, path)

    def _validate_condition(self, cond: Dict, path: str):
        """Validate a condition"""
        # Check for required fields
        if "id" not in cond and "callFunction" not in cond:
            self.errors.append(f"{path}: condition 缺少 'id'")
            return

        if "objectClass" not in cond and "callFunction" not in cond:
            self.errors.append(f"{path}: condition 缺少 'objectClass'")

        # Validate comparison parameter if present
        params = cond.get("parameters", {})
        if "comparison" in params:
            comp = params["comparison"]
            if comp not in self.COMPARISON_OPERATORS:
                self.errors.append(f"{path}: 无效的比较操作符: {comp}")

    def _validate_action(self, action: Dict, path: str):
        """Validate an action"""
        # Inline comment in actions
        if action.get("type") == "comment":
            if "text" not in action:
                self.errors.append(f"{path}: action comment 缺少 'text'")
            return

        # Function call
        if "callFunction" in action:
            return  # Function calls are valid with just callFunction

        # Regular action
        if "id" not in action:
            self.errors.append(f"{path}: action 缺少 'id'")
            return

        if "objectClass" not in action:
            self.errors.append(f"{path}: action 缺少 'objectClass'")


# ============================================================
# JSON Extractor (from LLM response)
# ============================================================


def extract_json_from_response(response: str) -> Optional[str]:
    """
    Extract JSON from LLM response
    Handles markdown code blocks and raw JSON
    """
    # Try to find JSON in code blocks
    code_block_pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
    matches = re.findall(code_block_pattern, response)

    if matches:
        # Return the first valid JSON
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

    # Try to find raw JSON (starting with { and ending with })
    json_pattern = r'(\{"is-c3-clipboard-data"[\s\S]*?\}\s*\]?\s*\})'
    matches = re.findall(json_pattern, response)

    if matches:
        for match in matches:
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

    return None


# ============================================================
# Event Generator
# ============================================================


class EventGenerator:
    """Generate Construct 3 event sheet JSON"""

    def __init__(self, schema_dir: str = None):
        self.schema_loader = SchemaLoader(schema_dir)
        self.validator = ClipboardValidator(self.schema_loader)

    def get_relevant_schema(self, requirement: str) -> str:
        """
        Extract relevant schema based on user requirement.
        Uses dynamic keyword index built from Schema files.
        Returns formatted schema context for LLM
        """
        # Keywords to search for
        keywords = self._extract_keywords(requirement)

        # Always include System plugin (most commonly used)
        relevant_schemas: Set[Tuple[str, str]] = {("system", "plugin")}

        # Use dynamic keyword index from schema files
        for keyword in keywords:
            result = self.schema_loader.find_schema_by_keyword(keyword)
            if result:
                relevant_schemas.add(result)

        # Load and format schemas
        schema_text = []

        for schema_id, schema_type in relevant_schemas:
            # Load based on type
            if schema_type == "plugin":
                schema = self.schema_loader.load_plugin(schema_id)
                type_label = "插件"
            else:
                schema = self.schema_loader.load_behavior(schema_id)
                type_label = "行为"

            if schema:
                schema_text.append(self._format_schema_for_prompt(schema, type_label))

        return "\n\n".join(schema_text) if schema_text else "（无相关 Schema）"

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from requirement text"""
        # Simple keyword extraction
        # In production, could use NLP or more sophisticated methods
        keywords = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", text)
        return [k for k in keywords if len(k) > 1]

    def _format_schema_for_prompt(self, schema: PluginSchema, schema_type: str) -> str:
        """Format schema for LLM prompt"""
        lines = [f"### {schema_type}: {schema.name_zh} ({schema.name_en})"]

        # Format conditions
        if schema.conditions:
            lines.append("\n**条件 (Conditions):**")
            for cond_id, cond in list(schema.conditions.items())[:10]:  # Limit to 10
                params_str = ", ".join([f"{p.id}: {p.type}" for p in cond.params])
                lines.append(f"- `{cond_id}`: {cond.name_zh} ({params_str})")

        # Format actions
        if schema.actions:
            lines.append("\n**动作 (Actions):**")
            for act_id, act in list(schema.actions.items())[:15]:  # Limit to 15
                params_str = ", ".join([f"{p.id}: {p.type}" for p in act.params])
                lines.append(f"- `{act_id}`: {act.name_zh} ({params_str})")

        return "\n".join(lines)

    def build_prompt(self, requirement: str) -> str:
        """Build the full prompt for LLM"""
        schema_context = self.get_relevant_schema(requirement)

        return EVENT_JSON_GENERATION_PROMPT.format(
            schema_context=schema_context,
            format_reference=CLIPBOARD_FORMAT_REFERENCE,
            user_requirement=requirement,
        )

    def validate_output(self, json_str: str) -> Tuple[bool, List[str], List[str]]:
        """Validate generated JSON"""
        return self.validator.validate(json_str)

    def process_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Process LLM response: extract JSON and validate
        Returns: {
            "success": bool,
            "json": str or None,
            "errors": List[str],
            "warnings": List[str]
        }
        """
        # Extract JSON from response
        json_str = extract_json_from_response(llm_response)

        if not json_str:
            return {
                "success": False,
                "json": None,
                "errors": ["无法从回复中提取有效的 JSON"],
                "warnings": [],
            }

        # Validate
        is_valid, errors, warnings = self.validate_output(json_str)

        # Format JSON for output
        try:
            parsed = json.loads(json_str)
            formatted_json = json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            formatted_json = json_str

        return {
            "success": is_valid,
            "json": formatted_json,
            "errors": errors,
            "warnings": warnings,
        }


# ============================================================
# Convenience functions
# ============================================================


def generate_event_prompt(requirement: str, schema_dir: str = None) -> str:
    """Generate prompt for event sheet generation"""
    generator = EventGenerator(schema_dir)
    return generator.build_prompt(requirement)


def validate_clipboard_json(
    json_str: str, schema_dir: str = None
) -> Tuple[bool, List[str], List[str]]:
    """Validate clipboard JSON"""
    loader = SchemaLoader(schema_dir)
    validator = ClipboardValidator(loader)
    return validator.validate(json_str)
