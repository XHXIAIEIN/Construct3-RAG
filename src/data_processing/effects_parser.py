"""
Effects Parser - 解析 Construct 3 的 allEffects.json 文件

数据来源: construct-source/r466/effects/allEffects.json
生成结构化的效果数据用于向量索引
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class EffectParam:
    """效果参数定义"""
    id: str
    type: str
    initial_value: Any = None
    interpolatable: bool = False
    uniform: str = ""


@dataclass
class EffectEntry:
    """单个效果条目"""
    effect_id: str
    category: str
    author: str
    supported_renderers: List[str] = field(default_factory=list)
    blends_background: bool = False
    cross_sampling: bool = False
    preserves_opaqueness: bool = True
    animated: bool = False
    extend_box: Dict[str, int] = field(default_factory=dict)
    params: List[EffectParam] = field(default_factory=list)


class EffectsParser:
    """解析 allEffects.json 文件"""

    def __init__(self, source_dir: Optional[Path] = None):
        if source_dir is None:
            source_dir = Path(__file__).parent.parent.parent / "construct-source" / "r466"
        self.source_dir = source_dir
        self.effects_file = source_dir / "effects" / "allEffects.json"

    def _read_json(self, path: Path) -> Dict:
        """读取 JSON 文件，处理 BOM"""
        content = path.read_text(encoding='utf-8-sig')
        return json.loads(content)

    def _parse_params(self, params_data: List[Dict]) -> List[EffectParam]:
        """解析参数列表"""
        params = []
        for p in params_data:
            param = EffectParam(
                id=p.get("id", ""),
                type=p.get("type", "float"),
                initial_value=p.get("initial-value"),
                interpolatable=p.get("interpolatable", False),
                uniform=p.get("uniform", "")
            )
            params.append(param)
        return params

    def parse_all(self) -> List[EffectEntry]:
        """解析所有效果数据"""
        entries = []

        if not self.effects_file.exists():
            print(f"Effects file not found: {self.effects_file}")
            return entries

        data = self._read_json(self.effects_file)

        for effect_data in data.get("all", []):
            json_data = effect_data.get("json", {})

            entry = EffectEntry(
                effect_id=json_data.get("id", ""),
                category=json_data.get("category", ""),
                author=json_data.get("author", ""),
                supported_renderers=json_data.get("supported-renderers", []),
                blends_background=json_data.get("blends-background", False),
                cross_sampling=json_data.get("cross-sampling", False),
                preserves_opaqueness=json_data.get("preserves-opaqueness", True),
                animated=json_data.get("animated", False),
                extend_box=json_data.get("extend-box", {}),
                params=self._parse_params(json_data.get("parameters", []))
            )
            entries.append(entry)

        return entries

    def export_for_vectordb(self, entries: Optional[List[EffectEntry]] = None) -> List[Dict[str, Any]]:
        """导出为向量数据库格式"""
        if entries is None:
            entries = self.parse_all()

        # Category translations
        category_zh = {
            "color": "颜色",
            "distortion": "变形",
            "blend": "混合",
            "normal-mapping": "法线贴图",
            "3d": "3D",
            "mask": "遮罩",
        }

        # Param type translations
        param_type_zh = {
            "percent": "百分比",
            "float": "浮点数",
            "color": "颜色",
        }

        docs = []
        for entry in entries:
            # 构建文本描述
            text_parts = []

            # 基本信息
            cat_zh = category_zh.get(entry.category, entry.category)
            text_parts.append(f"效果 {entry.effect_id} (分类: {cat_zh})")

            # 渲染器支持
            if entry.supported_renderers:
                text_parts.append(f"支持渲染器: {', '.join(entry.supported_renderers)}")

            # 参数信息
            if entry.params:
                param_strs = []
                for p in entry.params:
                    type_zh = param_type_zh.get(p.type, p.type)
                    param_str = f"{p.id} ({type_zh})"
                    if p.initial_value is not None:
                        param_str += f" 默认: {p.initial_value}"
                    param_strs.append(param_str)
                text_parts.append("参数: " + ", ".join(param_strs))

            # 特性标记
            features = []
            if entry.blends_background:
                features.append("混合背景")
            if entry.cross_sampling:
                features.append("跨采样")
            if entry.animated:
                features.append("动画效果")
            if not entry.preserves_opaqueness:
                features.append("影响透明度")
            if features:
                text_parts.append("特性: " + ", ".join(features))

            text = "\n".join(text_parts)

            doc = {
                "id": f"effect_{entry.effect_id}",
                "text": text,
                "metadata": {
                    "source": "effects-schema",
                    "effect_id": entry.effect_id,
                    "category": entry.category,
                    "author": entry.author,
                    "params_count": len(entry.params),
                    "blends_background": entry.blends_background,
                    "animated": entry.animated,
                    "renderers": ",".join(entry.supported_renderers),
                }
            }
            docs.append(doc)

        return docs

    def get_stats(self, entries: Optional[List[EffectEntry]] = None) -> Dict[str, Any]:
        """获取统计信息"""
        if entries is None:
            entries = self.parse_all()

        stats = {
            "total": len(entries),
            "by_category": {},
            "by_renderer": {},
            "with_params": 0,
            "animated": 0,
        }

        for entry in entries:
            # By category
            cat = entry.category or "unknown"
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            # By renderer
            for renderer in entry.supported_renderers:
                stats["by_renderer"][renderer] = stats["by_renderer"].get(renderer, 0) + 1

            # Features
            if entry.params:
                stats["with_params"] += 1
            if entry.animated:
                stats["animated"] += 1

        return stats


def main():
    """测试解析器"""
    parser = EffectsParser()

    print("=== 解析 Effects 数据 ===")
    entries = parser.parse_all()

    stats = parser.get_stats(entries)
    print(f"\n总计: {stats['total']} 个效果")
    print(f"带参数: {stats['with_params']} 个")
    print(f"动画效果: {stats['animated']} 个")

    print("\n按分类:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"  - {cat}: {count}")

    print("\n按渲染器:")
    for renderer, count in sorted(stats["by_renderer"].items()):
        print(f"  - {renderer}: {count}")

    # 导出示例
    docs = parser.export_for_vectordb(entries)
    print(f"\n生成 {len(docs)} 个向量文档")

    # 显示前 3 个示例
    print("\n=== 示例文档 ===")
    for doc in docs[:3]:
        print(f"\nID: {doc['id']}")
        print(f"Text: {doc['text']}")
        print(f"Metadata: {doc['metadata']}")


if __name__ == "__main__":
    main()
