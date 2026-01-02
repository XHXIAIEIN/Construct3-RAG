"""
从 Construct 3 官方文档中提取 ACE (Actions, Conditions, Expressions) 信息
生成结构化的参考文档，用于增强 RAG 检索
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class ACEItem:
    """单个 ACE 条目"""
    name: str
    category: str  # condition, action, expression
    description: str = ""
    parameters: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "parameters": self.parameters
        }


@dataclass
class ObjectDef:
    """对象定义 (插件或行为)"""
    name: str
    obj_type: str  # plugin, behavior
    description: str = ""
    properties: List[str] = field(default_factory=list)
    conditions: List[ACEItem] = field(default_factory=list)
    actions: List[ACEItem] = field(default_factory=list)
    expressions: List[ACEItem] = field(default_factory=list)


def parse_markdown_doc(filepath: Path) -> Optional[ObjectDef]:
    """解析单个插件/行为的 Markdown 文档"""
    content = filepath.read_text(encoding='utf-8')

    # 提取标题
    title_match = re.search(r'^title:\s*"(.+)"', content, re.MULTILINE)
    if not title_match:
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)

    if not title_match:
        return None

    name = title_match.group(1).strip()

    # 判断类型
    obj_type = "behavior" if "behavior" in str(filepath).lower() else "plugin"

    obj = ObjectDef(name=name, obj_type=obj_type)

    # 按 H2 分割文档
    sections = re.split(r'^## ', content, flags=re.MULTILINE)

    current_category = None

    for section in sections[1:]:  # 跳过第一个空段落
        lines = section.strip().split('\n')
        if not lines:
            continue

        section_title = lines[0].strip().lower()
        section_content = '\n'.join(lines[1:])

        # 识别 section 类型
        if 'properties' in section_title or 'property' in section_title:
            current_category = 'properties'
        elif 'condition' in section_title:
            current_category = 'conditions'
        elif 'action' in section_title:
            current_category = 'actions'
        elif 'expression' in section_title:
            current_category = 'expressions'
        else:
            continue

        # 提取 ACE 条目
        # 匹配 **Name** 或 **Name(params)**
        pattern = r'\*\*([^*]+(?:\([^)]*\))?)\*\*\s*\n(.+?)(?=\n\*\*|\n>|\n##|\Z)'
        matches = re.findall(pattern, section_content, re.DOTALL)

        for match in matches:
            item_name = match[0].strip()
            item_desc = match[1].strip()

            # 清理描述
            item_desc = re.sub(r'\n+', ' ', item_desc)
            item_desc = item_desc[:200] + '...' if len(item_desc) > 200 else item_desc

            # 提取参数 (如果有)
            params = []
            param_match = re.search(r'\(([^)]+)\)', item_name)
            if param_match:
                params = [p.strip() for p in param_match.group(1).split(',')]
                # 清理参数名中的括号
                item_name = re.sub(r'\([^)]*\)', '', item_name).strip()

            ace = ACEItem(
                name=item_name,
                category=current_category,
                description=item_desc,
                parameters=params
            )

            if current_category == 'properties':
                obj.properties.append(item_name)
            elif current_category == 'conditions':
                obj.conditions.append(ace)
            elif current_category == 'actions':
                obj.actions.append(ace)
            elif current_category == 'expressions':
                obj.expressions.append(ace)

    return obj


def generate_ace_reference(objects: List[ObjectDef], output_path: Path):
    """生成结构化的 ACE 参考文档"""

    # 分类
    plugins = [o for o in objects if o.obj_type == 'plugin']
    behaviors = [o for o in objects if o.obj_type == 'behavior']

    content = """# Construct 3 事件表参考

本文档汇总了 Construct 3 中所有可用于事件表的对象及其条件、动作、表达式。

## 对象概览

### 插件 (Plugins)
"""

    # 插件列表
    for p in sorted(plugins, key=lambda x: x.name):
        c_count = len(p.conditions)
        a_count = len(p.actions)
        e_count = len(p.expressions)
        content += f"- **{p.name}**: {c_count} 条件, {a_count} 动作, {e_count} 表达式\n"

    content += "\n### 行为 (Behaviors)\n"

    for b in sorted(behaviors, key=lambda x: x.name):
        c_count = len(b.conditions)
        a_count = len(b.actions)
        e_count = len(b.expressions)
        content += f"- **{b.name}**: {c_count} 条件, {a_count} 动作, {e_count} 表达式\n"

    content += "\n---\n\n"

    # 详细 ACE 列表
    content += "## 插件详细参考\n\n"

    for obj in sorted(plugins, key=lambda x: x.name):
        content += f"### {obj.name}\n\n"

        if obj.conditions:
            content += "**条件 (Conditions)**:\n"
            for c in obj.conditions:
                params = f"({', '.join(c.parameters)})" if c.parameters else ""
                content += f"- `{c.name}{params}` - {c.description[:100]}\n"
            content += "\n"

        if obj.actions:
            content += "**动作 (Actions)**:\n"
            for a in obj.actions:
                params = f"({', '.join(a.parameters)})" if a.parameters else ""
                content += f"- `{a.name}{params}` - {a.description[:100]}\n"
            content += "\n"

        if obj.expressions:
            content += "**表达式 (Expressions)**:\n"
            for e in obj.expressions:
                params = f"({', '.join(e.parameters)})" if e.parameters else ""
                content += f"- `{e.name}{params}` - {e.description[:100]}\n"
            content += "\n"

        content += "---\n\n"

    content += "## 行为详细参考\n\n"

    for obj in sorted(behaviors, key=lambda x: x.name):
        content += f"### {obj.name}\n\n"

        if obj.conditions:
            content += "**条件 (Conditions)**:\n"
            for c in obj.conditions:
                params = f"({', '.join(c.parameters)})" if c.parameters else ""
                content += f"- `{c.name}{params}` - {c.description[:100]}\n"
            content += "\n"

        if obj.actions:
            content += "**动作 (Actions)**:\n"
            for a in obj.actions:
                params = f"({', '.join(a.parameters)})" if a.parameters else ""
                content += f"- `{a.name}{params}` - {a.description[:100]}\n"
            content += "\n"

        if obj.expressions:
            content += "**表达式 (Expressions)**:\n"
            for e in obj.expressions:
                params = f"({', '.join(e.parameters)})" if e.parameters else ""
                content += f"- `{e.name}{params}` - {e.description[:100]}\n"
            content += "\n"

        content += "---\n\n"

    output_path.write_text(content, encoding='utf-8')
    print(f"生成 ACE 参考文档: {output_path}")
    print(f"  - 插件: {len(plugins)} 个")
    print(f"  - 行为: {len(behaviors)} 个")


def generate_json_reference(objects: List[ObjectDef], output_path: Path):
    """生成 JSON 格式的 ACE 参考"""
    data = {
        "plugins": {},
        "behaviors": {}
    }

    for obj in objects:
        obj_data = {
            "name": obj.name,
            "conditions": [c.to_dict() for c in obj.conditions],
            "actions": [a.to_dict() for a in obj.actions],
            "expressions": [e.to_dict() for e in obj.expressions]
        }

        if obj.obj_type == 'plugin':
            data["plugins"][obj.name] = obj_data
        else:
            data["behaviors"][obj.name] = obj_data

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"生成 JSON 参考: {output_path}")


def main():
    from src.config import MARKDOWN_DIR

    plugin_dir = MARKDOWN_DIR / "plugin-reference"
    behavior_dir = MARKDOWN_DIR / "behavior-reference"

    objects = []

    # 解析插件文档
    if plugin_dir.exists():
        for md_file in plugin_dir.glob("*.md"):
            if md_file.name.startswith("common"):
                continue
            obj = parse_markdown_doc(md_file)
            if obj:
                objects.append(obj)
                print(f"解析: {obj.name} ({len(obj.conditions)}C/{len(obj.actions)}A/{len(obj.expressions)}E)")

    # 解析行为文档
    if behavior_dir.exists():
        for md_file in behavior_dir.glob("*.md"):
            if md_file.name.startswith("common"):
                continue
            obj = parse_markdown_doc(md_file)
            if obj:
                objects.append(obj)
                print(f"解析: {obj.name} ({len(obj.conditions)}C/{len(obj.actions)}A/{len(obj.expressions)}E)")

    # 生成输出
    output_dir = Path(__file__).parent.parent.parent / "source"
    output_dir.mkdir(exist_ok=True)

    generate_ace_reference(objects, output_dir / "ace-reference.md")
    generate_json_reference(objects, output_dir / "ace-reference.json")

    print(f"\n总计: {len(objects)} 个对象")


if __name__ == "__main__":
    main()
