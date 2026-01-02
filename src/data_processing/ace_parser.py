"""
ACE Parser - 解析 Construct 3 的 allAces.json 文件

数据来源: construct-source/r466/plugins/allAces.json, behaviors/allAces.json
生成结构化的 ACE (Actions/Conditions/Expressions) 数据用于向量索引
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ACEParam:
    """ACE 参数定义"""
    id: str
    type: str
    initial_value: Optional[str] = None
    items: Optional[List[str]] = None  # for combo type


@dataclass
class ACEEntry:
    """单个 ACE 条目"""
    plugin_name: str           # 插件/行为名称
    plugin_type: str           # "plugin" or "behavior"
    category: str              # ACE 分类 (如 "appearance", "size", etc.)
    ace_type: str              # "action", "condition", "expression"
    ace_id: str                # ACE ID (如 "set-size")
    script_name: str           # 脚本名称 (如 "SetSize")
    params: List[ACEParam] = field(default_factory=list)
    return_type: Optional[str] = None  # for expressions
    is_trigger: bool = False   # for conditions
    is_async: bool = False     # for actions


class ACEParser:
    """解析 allAces.json 文件"""

    def __init__(self, source_dir: Optional[Path] = None):
        if source_dir is None:
            source_dir = Path(__file__).parent.parent.parent / "construct-source" / "r466"
        self.source_dir = source_dir
        self.plugins_aces_file = source_dir / "plugins" / "allAces.json"
        self.behaviors_aces_file = source_dir / "behaviors" / "allAces.json"

    def _read_json(self, path: Path) -> Dict:
        """读取 JSON 文件，处理 BOM"""
        content = path.read_text(encoding='utf-8-sig')
        return json.loads(content)

    def _parse_params(self, params_data: List[Dict]) -> List[ACEParam]:
        """解析参数列表"""
        params = []
        for p in params_data:
            param = ACEParam(
                id=p.get("id", ""),
                type=p.get("type", "any"),
                initial_value=p.get("initialValue"),
                items=p.get("items")
            )
            params.append(param)
        return params

    def _parse_ace_category(
        self,
        plugin_name: str,
        plugin_type: str,
        category: str,
        category_data: Dict
    ) -> List[ACEEntry]:
        """解析单个分类的 ACE"""
        entries = []

        # Parse conditions
        for cond in category_data.get("conditions", []):
            entry = ACEEntry(
                plugin_name=plugin_name,
                plugin_type=plugin_type,
                category=category,
                ace_type="condition",
                ace_id=cond.get("id", ""),
                script_name=cond.get("scriptName", ""),
                params=self._parse_params(cond.get("params", [])),
                is_trigger=cond.get("isTrigger", False)
            )
            entries.append(entry)

        # Parse actions
        for act in category_data.get("actions", []):
            entry = ACEEntry(
                plugin_name=plugin_name,
                plugin_type=plugin_type,
                category=category,
                ace_type="action",
                ace_id=act.get("id", ""),
                script_name=act.get("scriptName", ""),
                params=self._parse_params(act.get("params", [])),
                is_async=act.get("isAsync", False)
            )
            entries.append(entry)

        # Parse expressions
        for expr in category_data.get("expressions", []):
            entry = ACEEntry(
                plugin_name=plugin_name,
                plugin_type=plugin_type,
                category=category,
                ace_type="expression",
                ace_id=expr.get("id", ""),
                script_name=expr.get("expressionName", ""),
                params=self._parse_params(expr.get("params", [])),
                return_type=expr.get("returnType", "any")
            )
            entries.append(entry)

        return entries

    def parse_all(self) -> List[ACEEntry]:
        """解析所有 ACE 数据"""
        all_entries = []

        # Parse plugins
        if self.plugins_aces_file.exists():
            data = self._read_json(self.plugins_aces_file)
            for plugin_name, categories in data.items():
                for category, category_data in categories.items():
                    entries = self._parse_ace_category(
                        plugin_name, "plugin", category, category_data
                    )
                    all_entries.extend(entries)

        # Parse behaviors
        if self.behaviors_aces_file.exists():
            data = self._read_json(self.behaviors_aces_file)
            for behavior_name, categories in data.items():
                for category, category_data in categories.items():
                    entries = self._parse_ace_category(
                        behavior_name, "behavior", category, category_data
                    )
                    all_entries.extend(entries)

        return all_entries

    def export_for_vectordb(self, entries: Optional[List[ACEEntry]] = None) -> List[Dict[str, Any]]:
        """导出为向量数据库格式"""
        if entries is None:
            entries = self.parse_all()

        docs = []
        for entry in entries:
            # 构建文本描述
            text_parts = []

            # 基本信息
            type_zh = {"action": "动作", "condition": "条件", "expression": "表达式"}
            plugin_type_zh = {"plugin": "插件", "behavior": "行为"}

            text_parts.append(
                f"{plugin_type_zh[entry.plugin_type]} {entry.plugin_name} 的{type_zh[entry.ace_type]}: {entry.ace_id}"
            )

            if entry.script_name:
                text_parts.append(f"脚本名称: {entry.script_name}")

            # 参数信息
            if entry.params:
                param_strs = []
                for p in entry.params:
                    param_str = f"{p.id} ({p.type})"
                    if p.items:
                        param_str += f" 选项: {', '.join(p.items[:5])}"
                        if len(p.items) > 5:
                            param_str += "..."
                    param_strs.append(param_str)
                text_parts.append("参数: " + ", ".join(param_strs))

            # 返回类型
            if entry.return_type:
                text_parts.append(f"返回类型: {entry.return_type}")

            # 特殊标记
            if entry.is_trigger:
                text_parts.append("[触发器]")
            if entry.is_async:
                text_parts.append("[异步]")

            text = "\n".join(text_parts)

            doc = {
                "id": f"ace_{entry.plugin_type}_{entry.plugin_name}_{entry.ace_type}_{entry.ace_id}",
                "text": text,
                "metadata": {
                    "source": "ace-schema",
                    "plugin_name": entry.plugin_name,
                    "plugin_type": entry.plugin_type,
                    "category": entry.category,
                    "ace_type": entry.ace_type,
                    "ace_id": entry.ace_id,
                    "script_name": entry.script_name,
                    "params_count": len(entry.params),
                    "return_type": entry.return_type or "",
                    "is_trigger": entry.is_trigger,
                    "is_async": entry.is_async,
                }
            }
            docs.append(doc)

        return docs

    def get_stats(self, entries: Optional[List[ACEEntry]] = None) -> Dict[str, Any]:
        """获取统计信息"""
        if entries is None:
            entries = self.parse_all()

        stats = {
            "total": len(entries),
            "by_type": {"action": 0, "condition": 0, "expression": 0},
            "by_plugin_type": {"plugin": 0, "behavior": 0},
            "plugins": set(),
            "behaviors": set(),
        }

        for entry in entries:
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
    parser = ACEParser()

    print("=== 解析 ACE 数据 ===")
    entries = parser.parse_all()

    stats = parser.get_stats(entries)
    print(f"\n总计: {stats['total']} 条 ACE")
    print(f"  - 条件: {stats['by_type']['condition']}")
    print(f"  - 动作: {stats['by_type']['action']}")
    print(f"  - 表达式: {stats['by_type']['expression']}")
    print(f"  - 插件: {stats['plugins']} 个")
    print(f"  - 行为: {stats['behaviors']} 个")

    # 导出示例
    docs = parser.export_for_vectordb(entries)
    print(f"\n生成 {len(docs)} 个向量文档")

    # 显示前 3 个示例
    print("\n=== 示例文档 ===")
    for doc in docs[:3]:
        print(f"\nID: {doc['id']}")
        print(f"Text: {doc['text'][:200]}...")
        print(f"Metadata: {doc['metadata']}")


if __name__ == "__main__":
    main()
