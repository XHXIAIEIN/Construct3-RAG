"""
从 Construct 3 编辑器的 allEditorPlugins.js 和 allEditorBehaviors.js 中提取 ACE 信息
这些文件是混淆的，但 ACE ID 字符串是保留的
"""
import re
import json
from pathlib import Path
from typing import Dict, List, Set
from dataclasses import dataclass, field


@dataclass
class PluginACE:
    """插件的 ACE 定义"""
    name: str
    plugin_type: str  # plugin or behavior
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    expressions: List[str] = field(default_factory=list)


def extract_aces_from_js(content: str) -> Dict[str, PluginACE]:
    """从混淆的 JS 中提取 ACE 信息"""
    plugins = {}

    # 1. 提取插件名称和类型
    # 模式: const X="PluginName", ... 或类似结构
    plugin_matches = re.findall(
        r'const \w+=self\.t,\w+=self\.lang,\w+="([^"]+)",\w+="[\d.]+",\w+="([^"]+)"',
        content
    )

    for name, category in plugin_matches:
        plugins[name] = PluginACE(name=name, plugin_type="plugin")

    # 2. 提取所有 ACE ID
    # ACE ID 通常是 kebab-case 格式
    all_ids = set(re.findall(r'"([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"', content))

    # 3. 根据命名模式分类
    condition_patterns = [
        'is-', 'on-', 'compare-', 'has-', 'every-', 'for-each',
        'trigger', 'collides', 'overlaps', 'touching', 'clicked',
        'pressed', 'down', 'released', 'playing', 'finished',
        'exists', 'enabled', 'visible', 'looping', 'at-', 'between-'
    ]

    action_patterns = [
        'set-', 'add-', 'subtract-', 'multiply-', 'divide-',
        'go-to', 'create-', 'destroy-', 'spawn-', 'load-', 'save-',
        'play-', 'stop-', 'pause-', 'resume-', 'start-', 'wait-',
        'move-', 'reset-', 'clear-', 'remove-', 'insert-', 'push-',
        'pop-', 'scroll-', 'flash-', 'fade-', 'tween-', 'enable-',
        'disable-', 'toggle-', 'request-', 'send-', 'call-', 'invoke-'
    ]

    # 常见的表达式名称（通常是名词或简短词）
    expression_patterns = [
        'x', 'y', 'z', 'width', 'height', 'angle', 'opacity', 'speed',
        'count', 'size', 'length', 'value', 'index', 'name', 'id', 'uid',
        'dt', 'time', 'frame', 'animation', 'layer', 'layout', 'object'
    ]

    conditions = set()
    actions = set()
    expressions = set()

    for ace_id in all_ids:
        is_condition = any(ace_id.startswith(p) or f'-{p}' in ace_id
                          for p in condition_patterns)
        is_action = any(ace_id.startswith(p) for p in action_patterns)

        if is_condition and not is_action:
            conditions.add(ace_id)
        elif is_action:
            actions.add(ace_id)
        elif len(ace_id) < 20 and '-' not in ace_id:
            # 短名称可能是表达式
            expressions.add(ace_id)

    return plugins, conditions, actions, expressions


def parse_all_editor_files():
    """解析所有编辑器文件"""
    source_dir = Path(__file__).parent.parent.parent / "source"

    plugins_file = source_dir / "allEditorPlugins.js"
    behaviors_file = source_dir / "allEditorBehaviors.js"

    all_conditions = set()
    all_actions = set()
    all_expressions = set()
    all_plugins = {}

    # 解析插件文件
    if plugins_file.exists():
        content = plugins_file.read_text(encoding='utf-8')
        plugins, conds, acts, exprs = extract_aces_from_js(content)
        all_plugins.update(plugins)
        all_conditions.update(conds)
        all_actions.update(acts)
        all_expressions.update(exprs)
        print(f"从 allEditorPlugins.js 提取:")
        print(f"  - 插件: {len(plugins)}")
        print(f"  - 条件: {len(conds)}")
        print(f"  - 动作: {len(acts)}")
        print(f"  - 表达式: {len(exprs)}")

    # 解析行为文件
    if behaviors_file.exists():
        content = behaviors_file.read_text(encoding='utf-8')
        plugins, conds, acts, exprs = extract_aces_from_js(content)
        for name, plugin in plugins.items():
            plugin.plugin_type = "behavior"
            all_plugins[name] = plugin
        all_conditions.update(conds)
        all_actions.update(acts)
        all_expressions.update(exprs)
        print(f"\n从 allEditorBehaviors.js 提取:")
        print(f"  - 行为: {len(plugins)}")
        print(f"  - 条件: {len(conds)}")
        print(f"  - 动作: {len(acts)}")
        print(f"  - 表达式: {len(exprs)}")

    # 生成输出
    output = {
        "plugins": {name: {"type": p.plugin_type} for name, p in all_plugins.items()},
        "conditions": sorted(all_conditions),
        "actions": sorted(all_actions),
        "expressions": sorted(all_expressions)
    }

    output_file = source_dir / "editor-aces.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n输出: {output_file}")

    # 生成 Markdown 参考
    md_content = """# Construct 3 内置 ACE 参考

从编辑器文件中提取的条件、动作、表达式 ID。

## 插件列表

"""
    for name, plugin in sorted(all_plugins.items()):
        md_content += f"- **{name}** ({plugin.plugin_type})\n"

    md_content += f"\n## 条件 ({len(all_conditions)} 个)\n\n"
    for c in sorted(all_conditions):
        md_content += f"- `{c}`\n"

    md_content += f"\n## 动作 ({len(all_actions)} 个)\n\n"
    for a in sorted(all_actions):
        md_content += f"- `{a}`\n"

    md_content += f"\n## 表达式 ({len(all_expressions)} 个)\n\n"
    for e in sorted(all_expressions):
        md_content += f"- `{e}`\n"

    md_file = source_dir / "editor-aces.md"
    md_file.write_text(md_content, encoding='utf-8')
    print(f"输出: {md_file}")

    return output


if __name__ == "__main__":
    parse_all_editor_files()
