"""
Schema Parser - 从 CDN 读取 Construct 3 ACE/effect/property 数据用于向量索引

数据来源: C3Fetcher CDN (allAces.json, allEffects.json, lang files)
包含: plugins, behaviors, effects 的完整双语数据
"""
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
    """Parse Construct 3 ACE/effect/property data from CDN.

    Requires a C3Fetcher instance. Reads allAces.json + precompiled lang from CDN.
    """

    def __init__(self, fetcher):
        self._fetcher = fetcher

    def parse_ace_entries(self) -> List[ACEEntry]:
        """Parse all ACE data from CDN."""
        return self._parse_ace_from_cdn()

    def _parse_ace_from_cdn(self) -> List[ACEEntry]:
        """CDN mode: join allAces + en-US lang + zh-CN lang."""
        aces_data = self._fetcher.fetch_all_aces()
        en_text = self._fetcher.fetch_lang("en-US").get("text", {})
        zh_text = self._fetcher.fetch_lang("zh-CN").get("text", {})

        entries = []
        type_map = {"plugins": "plugin", "behaviors": "behavior"}

        # _common ACEs (shared by all World instances: collision, position, etc.)
        # Not in allAces.json, but lang files have the full list.
        en_common = en_text.get("plugins", {}).get("_common", {})
        zh_common = zh_text.get("plugins", {}).get("_common", {})
        if en_common:
            for ace_type_plural in ("conditions", "actions", "expressions"):
                en_aces = en_common.get(ace_type_plural, {})
                zh_aces = zh_common.get(ace_type_plural, {})
                for ace_id, en_ace in en_aces.items():
                    zh_ace = zh_aces.get(ace_id, {})
                    if ace_type_plural == "expressions":
                        name_en = en_ace.get("translated-name", ace_id)
                        name_zh = zh_ace.get("translated-name", name_en)
                    else:
                        name_en = en_ace.get("list-name", ace_id)
                        name_zh = zh_ace.get("list-name", name_en)
                    entries.append(ACEEntry(
                        plugin_name="_common",
                        plugin_name_zh="公共",
                        plugin_name_en="Common",
                        plugin_type="plugin",
                        category="common",
                        ace_type=ace_type_plural[:-1],
                        ace_id=ace_id,
                        name_zh=name_zh,
                        name_en=name_en,
                        description_zh=zh_ace.get("description", ""),
                        description_en=en_ace.get("description", ""),
                        script_name=ace_id,
                        params=[],
                    ))

        for addon_type, plugin_type in type_map.items():
            for plugin_id, categories in aces_data.get(addon_type, {}).items():
                pid_lower = plugin_id.lower()
                en_plugin = en_text.get(addon_type, {}).get(pid_lower, {})
                zh_plugin = zh_text.get(addon_type, {}).get(pid_lower, {})
                plugin_name_en = en_plugin.get("name", plugin_id)
                plugin_name_zh = zh_plugin.get("name", plugin_name_en)

                for category, ace_types in categories.items():
                    for ace_type in ("conditions", "actions", "expressions"):
                        for ace in ace_types.get(ace_type, []):
                            ace_id = ace.get("id", "")
                            en_ace = en_plugin.get(ace_type, {}).get(ace_id, {})
                            zh_ace = zh_plugin.get(ace_type, {}).get(ace_id, {})

                            # Expression names use "translated-name", not "list-name"
                            if ace_type == "expressions":
                                name_en = en_ace.get("translated-name", ace_id)
                                name_zh = zh_ace.get("translated-name", name_en)
                            else:
                                name_en = en_ace.get("list-name", ace_id)
                                name_zh = zh_ace.get("list-name", name_en)

                            # Build params with zh names
                            params = []
                            for p in ace.get("params", []):
                                pid_param = p.get("id", "")
                                en_p = en_ace.get("params", {}).get(pid_param, {})
                                zh_p = zh_ace.get("params", {}).get(pid_param, {})
                                param = {
                                    "id": pid_param,
                                    "type": p.get("type", "any"),
                                    "name_en": en_p.get("name", pid_param),
                                    "name_zh": zh_p.get("name", en_p.get("name", pid_param)),
                                }
                                if "items" in p:
                                    param["items"] = p["items"]
                                params.append(param)

                            entries.append(ACEEntry(
                                plugin_name=plugin_id,
                                plugin_name_zh=plugin_name_zh,
                                plugin_name_en=plugin_name_en,
                                plugin_type=plugin_type,
                                category=category,
                                ace_type=ace_type[:-1],  # "conditions"→"condition"
                                ace_id=ace_id,
                                name_zh=name_zh,
                                name_en=name_en,
                                description_zh=zh_ace.get("description", ""),
                                description_en=en_ace.get("description", ""),
                                script_name=ace.get("scriptName", ace.get("expressionName", "")),
                                params=params,
                                return_type=ace.get("returnType"),
                                is_trigger=ace.get("isTrigger", False),
                                is_async=ace.get("isAsync", False),
                            ))
        return entries

    def parse_effects(self) -> List[EffectEntry]:
        """Parse all effects from CDN."""
        return self._parse_effects_from_cdn()

    def _parse_effects_from_cdn(self) -> List[EffectEntry]:
        """CDN mode: parse effects from allEffects.json + lang files."""
        effects_raw = self._fetcher.fetch_effects()
        en_text = self._fetcher.fetch_lang("en-US").get("text", {}).get("effects", {})
        zh_text = self._fetcher.fetch_lang("zh-CN").get("text", {}).get("effects", {})
        entries = []
        for item in effects_raw:
            data = item.get("json", item)
            eid = data.get("id", "")
            en_fx = en_text.get(eid, {})
            zh_fx = zh_text.get(eid, {})
            entries.append(EffectEntry(
                id=eid,
                name_en=en_fx.get("name", eid),
                name_zh=zh_fx.get("name", en_fx.get("name", eid)),
                description_en=en_fx.get("description", ""),
                description_zh=zh_fx.get("description", ""),
                category=data.get("category", ""),
                parameters=data.get("parameters", []),
            ))
        return entries

    def parse_properties(self) -> List[PropertyEntry]:
        """Parse all properties. CDN properties not yet implemented; returns empty list."""
        return []

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

    def export_properties_for_vectordb(self, entries: Optional[List[PropertyEntry]] = None) -> List[Dict[str, Any]]:
        """导出属性为向量数据库格式"""
        if entries is None:
            entries = self.parse_properties()

        plugin_type_zh = {"plugin": "插件", "behavior": "行为"}
        docs = []
        for entry in entries:
            text_parts = [
                f"{plugin_type_zh.get(entry.plugin_type, entry.plugin_type)} "
                f"{entry.plugin_name_zh}({entry.plugin_name}) 的属性: "
                f"{entry.name_zh} ({entry.name_en})"
            ]
            if entry.description_zh:
                text_parts.append(f"描述: {entry.description_zh}")
            if entry.description_en and entry.description_en != entry.description_zh:
                text_parts.append(f"Description: {entry.description_en}")
            if entry.items:
                item_labels = [str(v) for v in list(entry.items.values())[:5]]
                text_parts.append(f"选项: {', '.join(item_labels)}")

            docs.append({
                "id": f"prop_{entry.plugin_type}_{entry.plugin_name}_{entry.prop_id}",
                "text": "\n".join(text_parts),
                "metadata": {
                    "source": "construct3-schema",
                    "plugin_name": entry.plugin_name,
                    "plugin_name_zh": entry.plugin_name_zh,
                    "plugin_type": entry.plugin_type,
                    "prop_id": entry.prop_id,
                    "name_zh": entry.name_zh,
                    "name_en": entry.name_en,
                    "section_type": "properties",
                }
            })
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
    from src.config import C3_VERSION, C3_CDN_BASE, C3_CACHE_DIR
    from src.ingest.c3_fetcher import C3Fetcher
    fetcher = C3Fetcher(version=C3_VERSION, base_url=C3_CDN_BASE, cache_dir=C3_CACHE_DIR)
    parser = SchemaParser(fetcher=fetcher)

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
