#!/usr/bin/env python3
"""
Construct 3 Event Sheet JSON Validator

Validates generated event sheet JSON against C3 clipboard format specification.
Use this script to verify format before pasting into the Construct 3 editor.

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
    """Validates Construct 3 clipboard JSON format"""

    VALID_TYPES = {"events", "conditions", "actions"}  # Only these 3 are valid for clipboard paste
    VALID_EVENT_TYPES = {"block", "variable", "comment", "group", "function-block"}
    COMPARISON_OPERATORS = {0, 1, 2, 3, 4, 5}  # =, ≠, <, ≤, >, ≥

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate(self, data: dict) -> bool:
        """Main validation entry point"""
        self.errors = []
        self.warnings = []

        # 1. Basic structure check
        if not isinstance(data, dict):
            self.errors.append("Root element must be an object")
            return False

        if not data.get("is-c3-clipboard-data"):
            self.errors.append("Missing 'is-c3-clipboard-data': true")
            return False

        if "type" not in data:
            self.errors.append("Missing 'type' field")
            return False

        if data["type"] not in self.VALID_TYPES:
            self.errors.append(f"Invalid type: {data['type']}, valid values: {self.VALID_TYPES}")
            return False

        if "items" not in data:
            self.errors.append("Missing 'items' field")
            return False

        if not isinstance(data["items"], list):
            self.errors.append("'items' must be an array")
            return False

        # 2. Validate items by type
        if data["type"] == "events":
            self._validate_events(data["items"])
        elif data["type"] == "conditions":
            self._validate_conditions(data["items"])
        elif data["type"] == "actions":
            self._validate_actions(data["items"])

        return len(self.errors) == 0

    def _validate_events(self, items: list):
        """Validate events array"""
        for i, item in enumerate(items):
            prefix = f"events[{i}]"

            if not isinstance(item, dict):
                self.errors.append(f"{prefix}: must be an object")
                continue

            event_type = item.get("eventType")
            if not event_type:
                self.errors.append(f"{prefix}: missing 'eventType'")
                continue

            if event_type not in self.VALID_EVENT_TYPES:
                self.errors.append(f"{prefix}: invalid eventType: {event_type}")
                continue

            if event_type == "block":
                self._validate_block(item, prefix)
            elif event_type == "variable":
                self._validate_variable(item, prefix)
            elif event_type == "function-block":
                self._validate_function_block(item, prefix)

    def _validate_block(self, block: dict, prefix: str):
        """Validate event block"""
        if "conditions" not in block:
            self.errors.append(f"{prefix}: missing 'conditions' array")
        elif isinstance(block["conditions"], list):
            self._validate_conditions(block["conditions"], f"{prefix}.conditions")

        if "actions" not in block:
            self.errors.append(f"{prefix}: missing 'actions' array")
        elif isinstance(block["actions"], list):
            self._validate_actions(block["actions"], f"{prefix}.actions")

        # Validate sub-events
        if "children" in block and isinstance(block["children"], list):
            for i, child in enumerate(block["children"]):
                self._validate_events([child])

    def _validate_variable(self, var: dict, prefix: str):
        """Validate variable definition"""
        if "name" not in var:
            self.errors.append(f"{prefix}: variable missing 'name'")

        if "comment" not in var:
            self.errors.append(f"{prefix}: variable missing 'comment' field (can be empty string)")

    def _validate_function_block(self, func: dict, prefix: str):
        """Validate function definition"""
        if "functionName" not in func:
            self.errors.append(f"{prefix}: function missing 'functionName'")

    def _validate_conditions(self, conditions: list, prefix: str = "conditions"):
        """Validate conditions array"""
        for i, cond in enumerate(conditions):
            cond_prefix = f"{prefix}[{i}]"

            if not isinstance(cond, dict):
                self.errors.append(f"{cond_prefix}: must be an object")
                continue

            if "id" not in cond:
                self.errors.append(f"{cond_prefix}: missing 'id'")

            if "objectClass" not in cond:
                self.errors.append(f"{cond_prefix}: missing 'objectClass'")

            if "parameters" not in cond:
                self.errors.append(f"{cond_prefix}: missing 'parameters'")

            # Check ID format
            if "id" in cond:
                self._validate_ace_id(cond["id"], cond_prefix)

            # Check parameters
            if "parameters" in cond and isinstance(cond["parameters"], dict):
                self._validate_parameters(cond["parameters"], cond_prefix)

    def _validate_actions(self, actions: list, prefix: str = "actions"):
        """Validate actions array"""
        for i, action in enumerate(actions):
            action_prefix = f"{prefix}[{i}]"

            if not isinstance(action, dict):
                self.errors.append(f"{action_prefix}: must be an object")
                continue

            # Special handling for function calls
            if "callFunction" in action:
                if "parameters" not in action:
                    self.warnings.append(f"{action_prefix}: callFunction should include 'parameters' array")
                continue

            if "id" not in action:
                self.errors.append(f"{action_prefix}: missing 'id'")

            if "objectClass" not in action:
                self.errors.append(f"{action_prefix}: missing 'objectClass'")

            if "parameters" not in action:
                self.errors.append(f"{action_prefix}: missing 'parameters'")

            # Check ID format
            if "id" in action:
                self._validate_ace_id(action["id"], action_prefix)

            # Check parameters
            if "parameters" in action and isinstance(action["parameters"], dict):
                self._validate_parameters(action["parameters"], action_prefix)

    def _validate_ace_id(self, ace_id: str, prefix: str):
        """Validate ACE ID format"""
        # Should be kebab-case
        if not re.match(r'^[a-z][a-z0-9-]*$', ace_id):
            self.warnings.append(f"{prefix}: ID '{ace_id}' may be incorrectly formatted, use kebab-case")

    def _validate_parameters(self, params: dict, prefix: str):
        """Validate parameters"""
        for key, value in params.items():
            param_prefix = f"{prefix}.parameters.{key}"

            # Check comparison parameter
            if key == "comparison":
                if isinstance(value, int):
                    if value not in self.COMPARISON_OPERATORS:
                        self.errors.append(f"{param_prefix}: invalid comparison operator {value}, valid: 0-5")
                elif isinstance(value, str):
                    self.warnings.append(f"{param_prefix}: comparison should be a number, not string")

            # Check string parameters for nested quotes
            if key in ("animation", "text", "tag", "audio-file-name", "folder"):
                if isinstance(value, str) and value and not value.startswith('"'):
                    if not any(c in value for c in ['+', '&', '(', '.']):  # Not an expression
                        self.warnings.append(f"{param_prefix}: string parameter may be missing nested quotes, got: {value}")

def main():
    # Read input
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.endswith('.json'):
            with open(arg, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = arg
    else:
        content = sys.stdin.read()

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        sys.exit(1)

    # Validate
    validator = C3ClipboardValidator()
    is_valid = validator.validate(data)

    # Output results
    if is_valid:
        print("✅ Validation passed! JSON format conforms to C3 clipboard spec")
    else:
        print("❌ Validation failed! Found the following errors:")
        for error in validator.errors:
            print(f"  • {error}")

    if validator.warnings:
        print("\n⚠️  Warnings:")
        for warning in validator.warnings:
            print(f"  • {warning}")

    # Statistics
    if is_valid and "items" in data:
        items = data["items"]
        blocks = sum(1 for i in items if i.get("eventType") == "block")
        variables = sum(1 for i in items if i.get("eventType") == "variable")
        print(f"\n📊 Stats: {len(items)} items ({blocks} event blocks, {variables} variables)")

    sys.exit(0 if is_valid else 1)

if __name__ == "__main__":
    main()
