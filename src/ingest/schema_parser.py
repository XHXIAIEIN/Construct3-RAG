"""
Schema Parser - 从 Construct3-Schema 读取数据用于向量索引

数据来源: data/schemas/
包含: plugins, behaviors, effects, editor 的完整双语数据
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ACEEntry:
    """单个 ACE 条目"""
    plugin_name: str           # 插件/行为名称
    plugin_name_zh: str        # 中文名称
    plugin_name_en: str        # 英文名称
    plugin_type: str           # "plugin" or "behavior"
    category: str              # ACE 分类
    ace_type: str              # "action", "condition", "expression"
    ace_id: str                # ACE ID
    name_zh: str               # 中文名称
    name_en: str               # 英文名称
    description_zh: str        # 中文描述
    description_en: str        # 英文描述
    script_name: str = ""      # 脚本名称
    params: List[Dict] = field(default_factory=list)
    return_type: Optional[str] = None
    is_trigger: bool = False
    is_async: bool = False


@dataclass
class EffectEntry:
    """效果条目"""
    id: str
    name_zh: str
    name_en: str
    description_zh: str
    description_en: str
    category: str
    parameters: List[Dict] = field(default_factory=list)


@dataclass
class PropertyEntry:
    """属性条目"""
    plugin_name: str
    plugin_name_zh: str
    plugin_type: str
    prop_id: str
    name_zh: str
    name_en: str
    description_zh: str
    description_en: str
    items: Optional[Dict] = None


class SchemaParser:
    """解析 Construct3-Schema 目录"""

    def __init__(self, schema_dir: Optional[Path] = None):
        if schema_dir is None:
            from src.config import SCHEMA_DIR
            schema_dir = SCHEMA_DIR
        self.schema_dir = schema_dir

    def _read_json(self, path: Path) -> Dict:
        """读取 JSON 文件"""
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def parse_ace_entries(self) -> List[ACEEntry]:
        """解析所有 ACE 数据"""
        entries = []

        # 解析 plugins
        plugins_dir = self.schema_dir / "plugins"
        if plugins_dir.exists():
            for json_file in plugins_dir.glob("*.json"):
                if json_file.name == "index.json":
                    continue
                plugin_data = self._read_json(json_file)
                entries.extend(self._parse_plugin_aces(plugin_data, "plugin"))

        # 解析 behaviors
        behaviors_dir = self.schema_dir / "behaviors"
        if behaviors_dir.exists():
            for json_file in behaviors_dir.glob("*.json"):
                if json_file.name == "index.json":
                    continue
                behavior_data = self._read_json(json_file)
                entries.extend(self._parse_plugin_aces(behavior_data, "behavior"))

        return entries

    def _parse_plugin_aces(self, data: Dict, plugin_type: str) -> List[ACEEntry]:
        """解析单个插件/行为的 ACE"""
        entries = []
        plugin_name = data.get("id", "")
        plugin_name_zh = data.get("name_zh", "")
        plugin_name_en = data.get("name_en", "")

        # 解析 conditions
        for ace in data.get("conditions", []):
            entry = ACEEntry(
                plugin_name=plugin_name,
                plugin_name_zh=plugin_name_zh,
                plugin_name_en=plugin_name_en,
                plugin_type=plugin_type,
                category=ace.get("category", ""),
                ace_type="condition",
                ace_id=ace.get("id", ""),
                name_zh=ace.get("name_zh", ""),
                name_en=ace.get("name_en", ""),
                description_zh=ace.get("description_zh", ""),
                description_en=ace.get("description_en", ""),
                script_name=ace.get("scriptName", ""),
                params=ace.get("params", []),
                is_trigger=ace.get("isTrigger", False)
            )
            entries.append(entry)

        # 解析 actions
        for ace in data.get("actions", []):
            entry = ACEEntry(
                plugin_name=plugin_name,
                plugin_name_zh=plugin_name_zh,
                plugin_name_en=plugin_name_en,
                plugin_type=plugin_type,
                category=ace.get("category", ""),
                ace_type="action",
                ace_id=ace.get("id", ""),
                name_zh=ace.get("name_zh", ""),
                name_en=ace.get("name_en", ""),
                description_zh=ace.get("description_zh", ""),
                description_en=ace.get("description_en", ""),
                script_name=ace.get("scriptName", ""),
                params=ace.get("params", []),
                is_async=ace.get("isAsync", False)
            )
            entries.append(entry)

        # 解析 expressions
        for ace in data.get("expressions", []):
            entry = ACEEntry(
                plugin_name=plugin_name,
                plugin_name_zh=plugin_name_zh,
                plugin_name_en=plugin_name_en,
                plugin_type=plugin_type,
                category=ace.get("category", ""),
                ace_type="expression",
                ace_id=ace.get("id", ""),
                name_zh=ace.get("name_zh", ""),
                name_en=ace.get("name_en", ""),
                description_zh=ace.get("description_zh", ""),
                description_en=ace.get("description_en", ""),
                script_name=ace.get("expressionName", ace.get("scriptName", "")),
                params=ace.get("params", []),
                return_type=ace.get("returnType")
            )
            entries.append(entry)

        return entries

    def parse_effects(self) -> List[EffectEntry]:
        """解析所有效果"""
        entries = []
        effects_dir = self.schema_dir / "effects"

        if not effects_dir.exists():
            return entries

        for json_file in effects_dir.glob("*.json"):
            if json_file.name == "index.json":
                continue
            data = self._read_json(json_file)
            entry = EffectEntry(
                id=data.get("id", ""),
                name_zh=data.get("name_zh", ""),
                name_en=data.get("name_en", ""),
                description_zh=data.get("description_zh", ""),
                description_en=data.get("description_en", ""),
                category=data.get("category", ""),
                parameters=data.get("parameters", [])
            )
            entries.append(entry)

        return entries

    def parse_properties(self) -> List[PropertyEntry]:
        """解析所有属性"""
        entries = []

        for plugin_type, dir_name in [("plugin", "plugins"), ("behavior", "behaviors")]:
            type_dir = self.schema_dir / dir_name
            if not type_dir.exists():
                continue

            for json_file in type_dir.glob("*.json"):
                if json_file.name == "index.json":
                    continue
                data = self._read_json(json_file)
                plugin_name = data.get("id", "")
                plugin_name_zh = data.get("name_zh", "")

                for prop in data.get("properties", []):
                    entry = PropertyEntry(
                        plugin_name=plugin_name,
                        plugin_name_zh=plugin_name_zh,
                        plugin_type=plugin_type,
                        prop_id=prop.get("id", ""),
                        name_zh=prop.get("name_zh", ""),
                        name_en=prop.get("name_en", ""),
                        description_zh=prop.get("description_zh", ""),
                        description_en=prop.get("description_en", ""),
                        items=prop.get("items")
                    )
                    entries.append(entry)

        return entries

    def export_ace_for_vectordb(self, entries: Optional[List[ACEEntry]] = None) -> List[Dict[str, Any]]:
        """导出 ACE 为向量数据库格式"""
        if entries is None:
            entries = self.parse_ace_entries()

        docs = []
        type_zh = {"action": "动作", "condition": "条件", "expression": "表达式"}
        plugin_type_zh = {"plugin": "插件", "behavior": "行为"}

        for entry in entries:
            text_parts = []

            # 标题行：中英文都包含
            text_parts.append(
                f"{plugin_type_zh[entry.plugin_type]} {entry.plugin_name_zh}({entry.plugin_name}) "
                f"的{type_zh[entry.ace_type]}: {entry.name_zh} ({entry.name_en})"
            )

            # 描述
            if entry.description_zh:
                text_parts.append(f"描述: {entry.description_zh}")
            if entry.description_en and entry.description_en != entry.description_zh:
                text_parts.append(f"Description: {entry.description_en}")

            # 脚本名称
            if entry.script_name:
                text_parts.append(f"脚本名称/Script: {entry.script_name}")

            # 参数信息
            if entry.params:
                param_strs = []
                for p in entry.params:
                    param_str = f"{p.get('name_zh', p.get('id', ''))} ({p.get('type', 'any')})"
                    if p.get('items'):
                        items = p.get('items_i18n', {})
                        if items:
                            item_labels = [v.get('zh', k) for k, v in list(items.items())[:3]]
                            param_str += f" 选项: {', '.join(item_labels)}"
                    param_strs.append(param_str)
                text_parts.append("参数: " + ", ".join(param_strs))

            # 返回类型
            if entry.return_type:
                text_parts.append(f"返回类型: {entry.return_type}")

            # 特殊标记
            if entry.is_trigger:
                text_parts.append("[触发器/Trigger]")
            if entry.is_async:
                text_parts.append("[异步/Async]")

            text = "\n".join(text_parts)

            doc = {
                "id": f"ace_{entry.plugin_type}_{entry.plugin_name}_{entry.ace_type}_{entry.ace_id}",
                "text": text,
                "metadata": {
                    "source": "construct3-schema",
                    "plugin_name": entry.plugin_name,
                    "plugin_name_zh": entry.plugin_name_zh,
                    "plugin_name_en": entry.plugin_name_en,
                    "plugin_type": entry.plugin_type,
                    "category": entry.category,
                    "ace_type": entry.ace_type,
                    "ace_id": entry.ace_id,
                    "name_zh": entry.name_zh,
                    "name_en": entry.name_en,
                    "script_name": entry.script_name,
                    "params_count": len(entry.params),
                    "return_type": entry.return_type or "",
                    "is_trigger": entry.is_trigger,
                    "is_async": entry.is_async,
                }
            }
            docs.append(doc)

        return docs

    def export_effects_for_vectordb(self, entries: Optional[List[EffectEntry]] = None) -> List[Dict[str, Any]]:
        """导出效果为向量数据库格式"""
        if entries is None:
            entries = self.parse_effects()

        docs = []
        for entry in entries:
            text_parts = [
                f"效果/Effect: {entry.name_zh} ({entry.name_en})",
                f"分类: {entry.category}"
            ]

            if entry.description_zh:
                text_parts.append(f"描述: {entry.description_zh}")
            if entry.description_en:
                text_parts.append(f"Description: {entry.description_en}")

            if entry.parameters:
                param_names = [f"{p.get('name_zh', p.get('id', ''))}" for p in entry.parameters]
                text_parts.append(f"参数: {', '.join(param_names)}")

            text = "\n".join(text_parts)

            doc = {
                "id": f"effect_{entry.id}",
                "text": text,
                "metadata": {
                    "source": "construct3-schema",
                    "effect_id": entry.id,
                    "name_zh": entry.name_zh,
                    "name_en": entry.name_en,
                    "category": entry.category,
                    "params_count": len(entry.parameters)
                }
            }
            docs.append(doc)

        return docs

    def get_stats(self, ace_entries: Optional[List[ACEEntry]] = None) -> Dict[str, Any]:
        """获取统计信息"""
        if ace_entries is None:
            ace_entries = self.parse_ace_entries()

        effects = self.parse_effects()
        properties = self.parse_properties()

        stats = {
            "total_aces": len(ace_entries),
            "by_type": {"action": 0, "condition": 0, "expression": 0},
            "by_plugin_type": {"plugin": 0, "behavior": 0},
            "plugins": set(),
            "behaviors": set(),
            "effects": len(effects),
            "properties": len(properties),
        }

        for entry in ace_entries:
            stats["by_type"][entry.ace_type] += 1
            stats["by_plugin_type"][entry.plugin_type] += 1
            if entry.plugin_type == "plugin":
                stats["plugins"].add(entry.plugin_name)
            else:
                stats["behaviors"].add(entry.plugin_name)

        stats["plugins"] = len(stats["plugins"])
        stats["behaviors"] = len(stats["behaviors"])

        return stats


def main():
    """测试解析器"""
    parser = SchemaParser()

    print("=== 解析 Construct3-Schema ===\n")

    ace_entries = parser.parse_ace_entries()
    stats = parser.get_stats(ace_entries)

    print(f"ACE 总计: {stats['total_aces']} 条")
    print(f"  - 条件: {stats['by_type']['condition']}")
    print(f"  - 动作: {stats['by_type']['action']}")
    print(f"  - 表达式: {stats['by_type']['expression']}")
    print(f"  - 插件: {stats['plugins']} 个")
    print(f"  - 行为: {stats['behaviors']} 个")
    print(f"\n效果: {stats['effects']} 个")
    print(f"属性: {stats['properties']} 个")

    # 导出示例
    docs = parser.export_ace_for_vectordb(ace_entries)
    print(f"\n生成 {len(docs)} 个 ACE 向量文档")

    # 显示示例
    print("\n=== 示例文档 ===")
    for doc in docs[:2]:
        print(f"\nID: {doc['id']}")
        print(f"Text:\n{doc['text'][:300]}...")


if __name__ == "__main__":
    main()
