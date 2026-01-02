#!/usr/bin/env python3
"""
Quick test script for Event Generator module
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.eventsheet_generator import (
    EventGenerator,
    SchemaLoader,
    validate_clipboard_json,
    extract_json_from_response
)


def test_schema_loader():
    """Test schema loading and keyword index"""
    print("=" * 60)
    print("1. Schema Loader Test")
    print("=" * 60)

    loader = SchemaLoader()

    # Load all schemas
    plugins = loader.load_all_plugins()
    behaviors = loader.load_all_behaviors()

    print(f"✓ Loaded {len(plugins)} plugins, {len(behaviors)} behaviors")

    # Build keyword index
    index = loader.build_keyword_index()
    print(f"✓ Built keyword index with {len(index)} entries")

    # Test keyword search
    test_keywords = ["键盘", "platform", "精灵", "tween", "子弹"]
    print("\nKeyword search:")
    for kw in test_keywords:
        result = loader.find_schema_by_keyword(kw)
        print(f"  '{kw}' → {result}")

    return True


def test_prompt_generation():
    """Test prompt generation with different requirements"""
    print("\n" + "=" * 60)
    print("2. Prompt Generation Test")
    print("=" * 60)

    gen = EventGenerator()

    test_cases = [
        "按空格键让玩家跳跃",
        "每秒生成一个敌人",
        "玩家碰到金币加分",
    ]

    for req in test_cases:
        print(f"\n需求: {req}")
        prompt = gen.build_prompt(req)

        # Extract schema section
        schema_start = prompt.find("## 可用 Schema")
        schema_end = prompt.find("## 剪贴板格式参考")
        schema_section = prompt[schema_start:schema_end].strip()

        # Count schemas found
        schema_count = schema_section.count("### ")
        print(f"✓ 检索到 {schema_count} 个相关 Schema")

    return True


def test_json_validation():
    """Test JSON validation"""
    print("\n" + "=" * 60)
    print("3. JSON Validation Test")
    print("=" * 60)

    # Valid examples
    valid_cases = [
        # Simple comment
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "comment", "text": "Hello"}]}', "简单注释"),

        # Variable (note: comment field is required)
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}]}', "变量定义"),

        # Event block
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "block", "conditions": [{"id": "every-tick", "objectClass": "System"}], "actions": []}]}', "事件块"),

        # Variable + event block in same items (variable defined before use)
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}, {"eventType": "block", "conditions": [{"id": "on-start-of-layout", "objectClass": "System"}], "actions": [{"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "Score", "value": "100"}}]}]}', "变量+事件块"),

        # Variable as child of block
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "block", "conditions": [{"id": "on-start-of-layout", "objectClass": "System"}], "actions": [], "children": [{"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": "", "isStatic": false, "isConstant": false}, {"eventType": "block", "conditions": [], "actions": [{"id": "set-eventvar-value", "objectClass": "System", "parameters": {"variable": "Score", "value": "100"}}]}]}]}', "变量作为子事件"),
    ]

    print("\n有效 JSON 测试:")
    for json_str, desc in valid_cases:
        is_valid, errors, _ = validate_clipboard_json(json_str)
        status = "✓" if is_valid else "✗"
        print(f"  {status} {desc}")
        if errors:
            for e in errors:
                print(f"      Error: {e}")

    # Invalid examples
    invalid_cases = [
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "unknown"}]}', "无效 eventType"),
        ('{"type": "events", "items": []}', "缺少 is-c3-clipboard-data"),
        ('{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "variable"}]}', "变量缺少 name"),
    ]

    print("\n无效 JSON 测试:")
    for json_str, desc in invalid_cases:
        is_valid, errors, _ = validate_clipboard_json(json_str)
        status = "✓" if not is_valid else "✗ (应该失败)"
        print(f"  {status} {desc}")
        for e in errors[:2]:  # Show first 2 errors
            print(f"      → {e}")

    return True


def test_json_extraction():
    """Test JSON extraction from LLM response"""
    print("\n" + "=" * 60)
    print("4. JSON Extraction Test")
    print("=" * 60)

    # Simulate LLM responses
    responses = [
        # Markdown code block
        '''好的，这是事件表 JSON：

```json
{"is-c3-clipboard-data": true, "type": "events", "items": [{"eventType": "comment", "text": "Test"}]}
```

你可以直接复制粘贴到 C3。''',

        # Raw JSON
        '''{"is-c3-clipboard-data": true, "type": "events", "items": []}''',
    ]

    for i, resp in enumerate(responses):
        json_str = extract_json_from_response(resp)
        status = "✓" if json_str else "✗"
        print(f"  {status} Response {i+1}: {'提取成功' if json_str else '提取失败'}")
        if json_str:
            print(f"      → {json_str[:60]}...")

    return True


def test_full_workflow():
    """Test full workflow simulation"""
    print("\n" + "=" * 60)
    print("5. Full Workflow Simulation")
    print("=" * 60)

    gen = EventGenerator()

    # User requirement
    requirement = "按空格键让玩家跳跃"
    print(f"\n用户需求: {requirement}")

    # Generate prompt
    prompt = gen.build_prompt(requirement)
    print(f"✓ Prompt 生成完成 ({len(prompt)} 字符)")

    # Simulate LLM response
    mock_llm_response = '''
好的，根据你的需求，这是事件表 JSON：

```json
{
  "is-c3-clipboard-data": true,
  "type": "events",
  "items": [
    {"eventType": "comment", "text": "玩家跳跃控制"},
    {
      "eventType": "block",
      "conditions": [
        {
          "id": "on-key-pressed",
          "objectClass": "Keyboard",
          "parameters": {"key": 32}
        }
      ],
      "actions": [
        {
          "id": "simulate-control",
          "objectClass": "Player",
          "behaviorType": "Platform",
          "parameters": {"control": "jump"}
        }
      ]
    }
  ]
}
```

说明：
- 按空格键（keycode 32）触发
- 使用 Platform 行为的 simulate-control 动作模拟跳跃
'''

    # Process response
    result = gen.process_response(mock_llm_response)

    print(f"✓ LLM 响应处理完成")
    print(f"  Valid: {result['success']}")

    if result['errors']:
        print(f"  Errors: {result['errors']}")

    if result['success']:
        print(f"\n生成的 JSON (可直接粘贴到 C3):")
        print("-" * 40)
        print(result['json'])

    return result['success']


def main():
    print("\n🎮 Construct 3 Event Generator Test\n")

    tests = [
        ("Schema Loader", test_schema_loader),
        ("Prompt Generation", test_prompt_generation),
        ("JSON Validation", test_json_validation),
        ("JSON Extraction", test_json_extraction),
        ("Full Workflow", test_full_workflow),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} failed with error: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
