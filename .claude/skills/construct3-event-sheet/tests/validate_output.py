#!/usr/bin/env python3
"""
Construct 3 Event Sheet JSON Validator

用于验证生成的事件表 JSON 是否符合 C3 剪贴板格式规范。
可以在 Construct 3 编辑器中实际粘贴测试前，先用此脚本验证格式。

Usage:
    python validate_output.py '{"is-c3-clipboard-data":true,...}'
    python validate_output.py input.json
    echo '{"is-c3-clipboard-data":true,...}' | python validate_output.py
"""

import json
import sys
import re
from typing import Any

class ValidationError(Exception):
    pass

class C3ClipboardValidator:
    """验证 Construct 3 剪贴板 JSON 格式"""

    VALID_TYPES = {"events", "conditions", "actions", "object-types", "world-instances", "layouts", "event-sheets"}
    VALID_EVENT_TYPES = {"block", "variable", "comment", "group", "function-block"}
    COMPARISON_OPERATORS = {0, 1, 2, 3, 4, 5}  # =, ≠, <, ≤, >, ≥

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate(self, data: dict) -> bool:
        """主验证入口"""
        self.errors = []
        self.warnings = []

        # 1. 基础结构检查
        if not isinstance(data, dict):
            self.errors.append("根元素必须是对象")
            return False

        if not data.get("is-c3-clipboard-data"):
            self.errors.append("缺少 'is-c3-clipboard-data': true")
            return False

        if "type" not in data:
            self.errors.append("缺少 'type' 字段")
            return False

        if data["type"] not in self.VALID_TYPES:
            self.errors.append(f"无效的 type: {data['type']}，有效值: {self.VALID_TYPES}")
            return False

        if "items" not in data:
            self.errors.append("缺少 'items' 字段")
            return False

        if not isinstance(data["items"], list):
            self.errors.append("'items' 必须是数组")
            return False

        # 2. 根据类型验证 items
        if data["type"] == "events":
            self._validate_events(data["items"])
        elif data["type"] == "conditions":
            self._validate_conditions(data["items"])
        elif data["type"] == "actions":
            self._validate_actions(data["items"])

        return len(self.errors) == 0

    def _validate_events(self, items: list):
        """验证事件数组"""
        for i, item in enumerate(items):
            prefix = f"events[{i}]"

            if not isinstance(item, dict):
                self.errors.append(f"{prefix}: 必须是对象")
                continue

            event_type = item.get("eventType")
            if not event_type:
                self.errors.append(f"{prefix}: 缺少 'eventType'")
                continue

            if event_type not in self.VALID_EVENT_TYPES:
                self.errors.append(f"{prefix}: 无效的 eventType: {event_type}")
                continue

            if event_type == "block":
                self._validate_block(item, prefix)
            elif event_type == "variable":
                self._validate_variable(item, prefix)
            elif event_type == "function-block":
                self._validate_function_block(item, prefix)

    def _validate_block(self, block: dict, prefix: str):
        """验证事件块"""
        if "conditions" not in block:
            self.errors.append(f"{prefix}: 缺少 'conditions' 数组")
        elif isinstance(block["conditions"], list):
            self._validate_conditions(block["conditions"], f"{prefix}.conditions")

        if "actions" not in block:
            self.errors.append(f"{prefix}: 缺少 'actions' 数组")
        elif isinstance(block["actions"], list):
            self._validate_actions(block["actions"], f"{prefix}.actions")

        # 验证子事件
        if "children" in block and isinstance(block["children"], list):
            for i, child in enumerate(block["children"]):
                self._validate_events([child])

    def _validate_variable(self, var: dict, prefix: str):
        """验证变量定义"""
        if "name" not in var:
            self.errors.append(f"{prefix}: 变量缺少 'name'")

        if "comment" not in var:
            self.errors.append(f"{prefix}: 变量缺少 'comment' 字段（可以为空字符串）")

    def _validate_function_block(self, func: dict, prefix: str):
        """验证函数定义"""
        if "functionName" not in func:
            self.errors.append(f"{prefix}: 函数缺少 'functionName'")

    def _validate_conditions(self, conditions: list, prefix: str = "conditions"):
        """验证条件数组"""
        for i, cond in enumerate(conditions):
            cond_prefix = f"{prefix}[{i}]"

            if not isinstance(cond, dict):
                self.errors.append(f"{cond_prefix}: 必须是对象")
                continue

            if "id" not in cond:
                self.errors.append(f"{cond_prefix}: 缺少 'id'")

            if "objectClass" not in cond:
                self.errors.append(f"{cond_prefix}: 缺少 'objectClass'")

            if "parameters" not in cond:
                self.errors.append(f"{cond_prefix}: 缺少 'parameters'")

            # 检查 ID 格式
            if "id" in cond:
                self._validate_ace_id(cond["id"], cond_prefix)

            # 检查参数
            if "parameters" in cond and isinstance(cond["parameters"], dict):
                self._validate_parameters(cond["parameters"], cond_prefix)

    def _validate_actions(self, actions: list, prefix: str = "actions"):
        """验证动作数组"""
        for i, action in enumerate(actions):
            action_prefix = f"{prefix}[{i}]"

            if not isinstance(action, dict):
                self.errors.append(f"{action_prefix}: 必须是对象")
                continue

            # 函数调用特殊处理
            if "callFunction" in action:
                if "parameters" not in action:
                    self.warnings.append(f"{action_prefix}: callFunction 建议包含 'parameters' 数组")
                continue

            if "id" not in action:
                self.errors.append(f"{action_prefix}: 缺少 'id'")

            if "objectClass" not in action:
                self.errors.append(f"{action_prefix}: 缺少 'objectClass'")

            if "parameters" not in action:
                self.errors.append(f"{action_prefix}: 缺少 'parameters'")

            # 检查 ID 格式
            if "id" in action:
                self._validate_ace_id(action["id"], action_prefix)

            # 检查参数
            if "parameters" in action and isinstance(action["parameters"], dict):
                self._validate_parameters(action["parameters"], action_prefix)

    def _validate_ace_id(self, ace_id: str, prefix: str):
        """验证 ACE ID 格式"""
        # 应该是 kebab-case
        if not re.match(r'^[a-z][a-z0-9-]*$', ace_id):
            self.warnings.append(f"{prefix}: ID '{ace_id}' 可能格式不正确，应使用 kebab-case")

    def _validate_parameters(self, params: dict, prefix: str):
        """验证参数"""
        for key, value in params.items():
            param_prefix = f"{prefix}.parameters.{key}"

            # 检查 comparison 参数
            if key == "comparison":
                if isinstance(value, int):
                    if value not in self.COMPARISON_OPERATORS:
                        self.errors.append(f"{param_prefix}: 无效的比较运算符 {value}，有效值: 0-5")
                elif isinstance(value, str):
                    self.warnings.append(f"{param_prefix}: comparison 应该是数字而非字符串")

            # 检查字符串参数是否有内嵌引号
            if key in ("animation", "text", "tag", "audio-file-name", "folder"):
                if isinstance(value, str) and value and not value.startswith('"'):
                    if not any(c in value for c in ['+', '&', '(', '.']):  # 不是表达式
                        self.warnings.append(f"{param_prefix}: 字符串参数可能缺少内嵌引号，当前: {value}")

def main():
    # 读取输入
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.endswith('.json'):
            with open(arg, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = arg
    else:
        content = sys.stdin.read()

    # 解析 JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        sys.exit(1)

    # 验证
    validator = C3ClipboardValidator()
    is_valid = validator.validate(data)

    # 输出结果
    if is_valid:
        print("✅ 验证通过！JSON 格式符合 C3 剪贴板规范")
    else:
        print("❌ 验证失败！发现以下错误:")
        for error in validator.errors:
            print(f"  • {error}")

    if validator.warnings:
        print("\n⚠️  警告:")
        for warning in validator.warnings:
            print(f"  • {warning}")

    # 统计
    if is_valid and "items" in data:
        items = data["items"]
        blocks = sum(1 for i in items if i.get("eventType") == "block")
        variables = sum(1 for i in items if i.get("eventType") == "variable")
        print(f"\n📊 统计: {len(items)} 项 ({blocks} 个事件块, {variables} 个变量)")

    sys.exit(0 if is_valid else 1)

if __name__ == "__main__":
    main()
