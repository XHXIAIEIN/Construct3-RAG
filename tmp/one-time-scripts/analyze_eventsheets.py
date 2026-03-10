"""
Construct 3 Event Sheet Deep Analyzer (Incremental Learning Version)

特性：
- 增量学习：只分析新增/修改的文件
- 持久化存储：知识库可累积
- 可进化：添加新示例后快速学习
- 细粒度分析：每个参数的实际值格式

用法：
  python analyze_eventsheets.py              # 增量学习（默认）
  python analyze_eventsheets.py --rebuild    # 完全重建
  python analyze_eventsheets.py --status     # 查看学习状态
  python analyze_eventsheets.py --export     # 仅导出报告（不分析）
"""

import json
import re
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.config import EXAMPLE_PROJECTS_DIR, SCHEMAS_DIR
except ImportError:
    EXAMPLE_PROJECTS_DIR = Path(__file__).parent.parent.parent / "Construct-Example-Projects" / "example-projects"
    SCHEMAS_DIR = Path(__file__).parent.parent / "data" / "schemas"


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ParamKnowledge:
    """参数的学习知识"""
    param_id: str
    schema_type: Optional[str] = None
    schema_items: List[str] = field(default_factory=list)

    # 累积的值样例（去重）
    unique_values: Set[str] = field(default_factory=set)

    # 值格式模式统计
    value_patterns: Dict[str, int] = field(default_factory=dict)

    # 代表性样例（保留最多 20 个）
    samples: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "param_id": self.param_id,
            "schema_type": self.schema_type,
            "schema_items": self.schema_items,
            "unique_values": list(self.unique_values),
            "value_patterns": self.value_patterns,
            "samples": self.samples[:20]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ParamKnowledge":
        pk = cls(param_id=data["param_id"])
        pk.schema_type = data.get("schema_type")
        pk.schema_items = data.get("schema_items", [])
        pk.unique_values = set(data.get("unique_values", []))
        pk.value_patterns = data.get("value_patterns", {})
        pk.samples = data.get("samples", [])
        return pk

    def merge(self, other: "ParamKnowledge") -> None:
        """合并另一个参数知识"""
        self.unique_values.update(other.unique_values)
        for pattern, count in other.value_patterns.items():
            self.value_patterns[pattern] = self.value_patterns.get(pattern, 0) + count
        # 合并样例（保持多样性）
        def _hashable(v):
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False, sort_keys=True)
            return v
        existing_values = {_hashable(s.get("value")) for s in self.samples}
        for s in other.samples:
            v_hash = _hashable(s.get("value"))
            if v_hash not in existing_values and len(self.samples) < 20:
                self.samples.append(s)
                existing_values.add(v_hash)


@dataclass
class ACEKnowledge:
    """条件/动作的学习知识"""
    ace_id: str
    ace_type: str  # "condition" | "action"
    object_class: str
    behavior_type: Optional[str] = None

    # 使用统计
    usage_count: int = 0

    # 参数知识
    params: Dict[str, ParamKnowledge] = field(default_factory=dict)

    # 原始 JSON 样例
    raw_samples: List[Dict] = field(default_factory=list)

    # 来源项目
    source_projects: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict:
        return {
            "ace_id": self.ace_id,
            "ace_type": self.ace_type,
            "object_class": self.object_class,
            "behavior_type": self.behavior_type,
            "usage_count": self.usage_count,
            "params": {k: v.to_dict() for k, v in self.params.items()},
            "raw_samples": self.raw_samples[:5],
            "source_projects": list(self.source_projects)[:20]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ACEKnowledge":
        ak = cls(
            ace_id=data["ace_id"],
            ace_type=data["ace_type"],
            object_class=data["object_class"],
            behavior_type=data.get("behavior_type")
        )
        ak.usage_count = data.get("usage_count", 0)
        ak.params = {k: ParamKnowledge.from_dict(v) for k, v in data.get("params", {}).items()}
        ak.raw_samples = data.get("raw_samples", [])
        ak.source_projects = set(data.get("source_projects", []))
        return ak

    def merge(self, other: "ACEKnowledge") -> None:
        """合并另一个 ACE 知识"""
        self.usage_count += other.usage_count
        self.source_projects.update(other.source_projects)

        # 合并参数
        for param_id, param in other.params.items():
            if param_id in self.params:
                self.params[param_id].merge(param)
            else:
                self.params[param_id] = param

        # 合并样例
        existing_samples = {json.dumps(s, sort_keys=True) for s in self.raw_samples}
        for s in other.raw_samples:
            s_key = json.dumps(s, sort_keys=True)
            if s_key not in existing_samples and len(self.raw_samples) < 5:
                self.raw_samples.append(s)
                existing_samples.add(s_key)


@dataclass
class KnowledgeBase:
    """可持久化的知识库"""
    version: str = "1.0"
    last_updated: str = ""

    # 已分析的文件 -> 哈希值
    analyzed_files: Dict[str, str] = field(default_factory=dict)

    # ACE 知识 (key: "{object}.{ace_id}" 或 "{object}:{behavior}.{ace_id}")
    conditions: Dict[str, ACEKnowledge] = field(default_factory=dict)
    actions: Dict[str, ACEKnowledge] = field(default_factory=dict)

    # 统计
    total_events: int = 0
    total_conditions: int = 0
    total_actions: int = 0

    def save(self, path: Path) -> None:
        """保存知识库"""
        data = {
            "version": self.version,
            "last_updated": datetime.now().isoformat(),
            "analyzed_files": self.analyzed_files,
            "conditions": {k: v.to_dict() for k, v in self.conditions.items()},
            "actions": {k: v.to_dict() for k, v in self.actions.items()},
            "statistics": {
                "total_events": self.total_events,
                "total_conditions": self.total_conditions,
                "total_actions": self.total_actions,
                "unique_conditions": len(self.conditions),
                "unique_actions": len(self.actions),
                "analyzed_files_count": len(self.analyzed_files)
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path: Path) -> "KnowledgeBase":
        """加载知识库"""
        if not path.exists():
            return cls()

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            kb = cls()
            kb.version = data.get("version", "1.0")
            kb.last_updated = data.get("last_updated", "")
            kb.analyzed_files = data.get("analyzed_files", {})
            kb.conditions = {k: ACEKnowledge.from_dict(v) for k, v in data.get("conditions", {}).items()}
            kb.actions = {k: ACEKnowledge.from_dict(v) for k, v in data.get("actions", {}).items()}

            stats = data.get("statistics", {})
            kb.total_events = stats.get("total_events", 0)
            kb.total_conditions = stats.get("total_conditions", 0)
            kb.total_actions = stats.get("total_actions", 0)

            return kb
        except Exception as e:
            print(f"Warning: Failed to load knowledge base: {e}")
            return cls()

    def merge(self, other: "KnowledgeBase") -> None:
        """合并另一个知识库"""
        self.analyzed_files.update(other.analyzed_files)
        self.total_events += other.total_events
        self.total_conditions += other.total_conditions
        self.total_actions += other.total_actions

        for key, ace in other.conditions.items():
            if key in self.conditions:
                self.conditions[key].merge(ace)
            else:
                self.conditions[key] = ace

        for key, ace in other.actions.items():
            if key in self.actions:
                self.actions[key].merge(ace)
            else:
                self.actions[key] = ace


# ============================================================
# Schema 加载器
# ============================================================

class SchemaLoader:
    """加载 Schema 定义"""

    def __init__(self, schemas_dir: Path):
        self.schemas_dir = schemas_dir
        self.plugins: Dict[str, Dict] = {}
        self.behaviors: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self):
        """加载所有 Schema"""
        plugins_dir = self.schemas_dir / "plugins"
        if plugins_dir.exists():
            for f in plugins_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding='utf-8'))
                    plugin_id = data.get("id", f.stem)
                    self.plugins[plugin_id] = data
                    self.plugins[plugin_id.lower()] = data
                    if "originalId" in data:
                        self.plugins[data["originalId"].lower()] = data
                except Exception:
                    pass

        behaviors_dir = self.schemas_dir / "behaviors"
        if behaviors_dir.exists():
            for f in behaviors_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding='utf-8'))
                    behavior_id = data.get("id", f.stem)
                    self.behaviors[behavior_id] = data
                    self.behaviors[behavior_id.lower()] = data
                    if "originalId" in data:
                        self.behaviors[data["originalId"].lower()] = data
                except Exception:
                    pass

        print(f"Loaded schemas: {len(self.plugins)} plugins, {len(self.behaviors)} behaviors")

    def find_ace_definition(self, object_class: str, ace_id: str,
                           ace_type: str, behavior_type: Optional[str] = None) -> Optional[Dict]:
        """查找条件/动作的 Schema 定义"""
        if behavior_type:
            schema = self.behaviors.get(behavior_type.lower())
            if not schema:
                for val in self.behaviors.values():
                    if val.get("originalId", "").lower() == behavior_type.lower():
                        schema = val
                        break
        else:
            schema = self.plugins.get(object_class.lower())
            if not schema:
                for val in self.plugins.values():
                    if val.get("originalId", "").lower() == object_class.lower():
                        schema = val
                        break

        if not schema:
            return None

        ace_list_key = "conditions" if ace_type == "condition" else "actions"
        for ace in schema.get(ace_list_key, []):
            if ace.get("id") == ace_id:
                return ace

        return None


# ============================================================
# 分析器
# ============================================================

class IncrementalAnalyzer:
    """增量学习分析器"""

    # 值格式模式
    VALUE_PATTERNS = {
        "quoted_string": re.compile(r'^".*"$'),
        "number_literal": re.compile(r'^-?\d+(\.\d+)?$'),
        "expression_dot": re.compile(r'^[A-Za-z_]\w*\.[A-Za-z_]'),
        "expression_call": re.compile(r'^[A-Za-z_]\w*\('),
        "combo_kebab": re.compile(r'^[a-z]+(-[a-z]+)+$'),
    }

    def __init__(self, example_dir: Path, schemas_dir: Path, kb_path: Path):
        self.example_dir = example_dir
        self.schema_loader = SchemaLoader(schemas_dir)
        self.kb_path = kb_path

        # 加载现有知识库
        self.kb = KnowledgeBase.load(kb_path)

        # 本次分析的临时知识库
        self.session_kb = KnowledgeBase()

    def _file_hash(self, path: Path) -> str:
        """计算文件哈希"""
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()

    def _classify_value(self, value: Any) -> str:
        """分类参数值的格式模式"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number_native"
        if not isinstance(value, str):
            return f"other:{type(value).__name__}"

        if value == "":
            return "empty_string"
        if self.VALUE_PATTERNS["quoted_string"].match(value):
            return "quoted_string"
        if self.VALUE_PATTERNS["number_literal"].match(value):
            return "number_string"
        if self.VALUE_PATTERNS["expression_dot"].match(value):
            return "expression_dot"
        if self.VALUE_PATTERNS["expression_call"].match(value):
            return "expression_call"
        if self.VALUE_PATTERNS["combo_kebab"].match(value):
            return "combo_kebab"
        if value in ("true", "false"):
            return "boolean_string"

        return "plain_string"

    def _get_ace_key(self, object_class: str, ace_id: str,
                     behavior_type: Optional[str] = None) -> str:
        """生成 ACE 的唯一键"""
        if behavior_type:
            return f"{object_class}:{behavior_type}.{ace_id}"
        return f"{object_class}.{ace_id}"

    def _analyze_ace(self, ace_data: Dict, ace_type: str,
                     project_name: str, sheet_name: str) -> None:
        """分析单个条件或动作"""
        ace_id = ace_data.get("id", "")
        if not ace_id:
            if "callFunction" in ace_data:
                ace_id = "callFunction"
            else:
                return

        object_class = ace_data.get("objectClass", "Unknown")
        behavior_type = ace_data.get("behaviorType")
        params = ace_data.get("parameters", {})

        key = self._get_ace_key(object_class, ace_id, behavior_type)

        storage = self.session_kb.conditions if ace_type == "condition" else self.session_kb.actions

        if key not in storage:
            storage[key] = ACEKnowledge(
                ace_id=ace_id,
                ace_type=ace_type,
                object_class=object_class,
                behavior_type=behavior_type
            )

        knowledge = storage[key]
        knowledge.usage_count += 1
        knowledge.source_projects.add(project_name)

        # 保存原始样例
        if len(knowledge.raw_samples) < 5:
            # 简化样例，移除 sid
            sample = {k: v for k, v in ace_data.items() if k != "sid"}
            knowledge.raw_samples.append(sample)

        # 分析参数
        if isinstance(params, dict):
            for param_id, param_value in params.items():
                self._analyze_param(knowledge, param_id, param_value,
                                   object_class, ace_id, ace_type, behavior_type,
                                   project_name)

    def _analyze_param(self, knowledge: ACEKnowledge, param_id: str, param_value: Any,
                       object_class: str, ace_id: str, ace_type: str,
                       behavior_type: Optional[str], project_name: str) -> None:
        """分析单个参数"""
        if param_id not in knowledge.params:
            # 从 Schema 获取定义
            schema_def = self.schema_loader.find_ace_definition(
                object_class, ace_id, ace_type, behavior_type
            )

            schema_type = None
            schema_items = []

            if schema_def:
                for p in schema_def.get("params", []):
                    if p.get("id") == param_id:
                        schema_type = p.get("type")
                        schema_items = p.get("items", [])
                        break

            knowledge.params[param_id] = ParamKnowledge(
                param_id=param_id,
                schema_type=schema_type,
                schema_items=schema_items
            )

        param_knowledge = knowledge.params[param_id]

        # 记录值（确保可哈希）
        if isinstance(param_value, (dict, list)):
            value_str = json.dumps(param_value, ensure_ascii=False, sort_keys=True)
        else:
            value_str = str(param_value) if not isinstance(param_value, str) else param_value
        param_knowledge.unique_values.add(value_str)

        # 分类模式
        pattern = self._classify_value(param_value)
        param_knowledge.value_patterns[pattern] = param_knowledge.value_patterns.get(pattern, 0) + 1

        # 保存样例
        if len(param_knowledge.samples) < 20:
            def _to_str(v):
                if isinstance(v, (dict, list)):
                    return json.dumps(v, ensure_ascii=False, sort_keys=True)
                return str(v) if v is not None else ""
            existing_values = {_to_str(s.get("value")) for s in param_knowledge.samples}
            if value_str not in existing_values:
                param_knowledge.samples.append({
                    "value": param_value,
                    "project": project_name,
                    "pattern": pattern
                })

    def _process_event(self, event: Dict, project_name: str, sheet_name: str) -> None:
        """处理单个事件"""
        event_type = event.get("eventType", "")

        if event_type == "block":
            self.session_kb.total_events += 1

            for cond in event.get("conditions", []):
                self.session_kb.total_conditions += 1
                self._analyze_ace(cond, "condition", project_name, sheet_name)

            for action in event.get("actions", []):
                self.session_kb.total_actions += 1
                self._analyze_ace(action, "action", project_name, sheet_name)

            for child in event.get("children", []):
                self._process_event(child, project_name, sheet_name)

        elif event_type in ("group", "function-block"):
            for cond in event.get("conditions", []):
                self.session_kb.total_conditions += 1
                self._analyze_ace(cond, "condition", project_name, sheet_name)
            for action in event.get("actions", []):
                self.session_kb.total_actions += 1
                self._analyze_ace(action, "action", project_name, sheet_name)
            for child in event.get("children", []):
                self._process_event(child, project_name, sheet_name)

    def analyze_incremental(self) -> int:
        """增量分析，返回新分析的文件数"""
        projects_dir = self.example_dir / "example-projects"
        if not projects_dir.exists():
            projects_dir = self.example_dir

        print(f"\nScanning: {projects_dir}")

        event_sheets = list(projects_dir.glob("**/eventSheets/*.json"))
        print(f"Found {len(event_sheets)} event sheet files")

        new_files = 0
        updated_files = 0
        skipped_files = 0

        for i, sheet_path in enumerate(event_sheets):
            if (i + 1) % 100 == 0:
                print(f"  Checked {i + 1}/{len(event_sheets)}...")

            file_key = str(sheet_path.relative_to(projects_dir))
            current_hash = self._file_hash(sheet_path)

            # 检查是否需要分析
            if file_key in self.kb.analyzed_files:
                if self.kb.analyzed_files[file_key] == current_hash:
                    skipped_files += 1
                    continue
                updated_files += 1
            else:
                new_files += 1

            # 分析文件
            try:
                data = json.loads(sheet_path.read_text(encoding='utf-8'))
                project_name = sheet_path.parent.parent.name
                sheet_name = data.get("name", sheet_path.stem)

                for event in data.get("events", []):
                    self._process_event(event, project_name, sheet_name)

                # 记录已分析
                self.session_kb.analyzed_files[file_key] = current_hash

            except Exception as e:
                print(f"  Warning: Failed to parse {sheet_path.name}: {e}")

        print(f"\nAnalysis summary:")
        print(f"  New files: {new_files}")
        print(f"  Updated files: {updated_files}")
        print(f"  Skipped (unchanged): {skipped_files}")
        print(f"  This session - Events: {self.session_kb.total_events}, "
              f"Conditions: {self.session_kb.total_conditions}, "
              f"Actions: {self.session_kb.total_actions}")

        return new_files + updated_files

    def save_knowledge(self) -> None:
        """合并并保存知识库"""
        self.kb.merge(self.session_kb)
        self.kb.save(self.kb_path)
        print(f"\nKnowledge base saved: {self.kb_path}")
        print(f"  Total events learned: {self.kb.total_events}")
        print(f"  Unique conditions: {len(self.kb.conditions)}")
        print(f"  Unique actions: {len(self.kb.actions)}")
        print(f"  Files analyzed: {len(self.kb.analyzed_files)}")

    def get_status(self) -> Dict:
        """获取知识库状态"""
        return {
            "last_updated": self.kb.last_updated,
            "files_analyzed": len(self.kb.analyzed_files),
            "total_events": self.kb.total_events,
            "unique_conditions": len(self.kb.conditions),
            "unique_actions": len(self.kb.actions),
            "total_conditions": self.kb.total_conditions,
            "total_actions": self.kb.total_actions,
        }


# ============================================================
# 报告导出
# ============================================================

class ReportExporter:
    """导出分析报告"""

    def __init__(self, kb: KnowledgeBase, output_dir: Path):
        self.kb = kb
        self.output_dir = output_dir

    def export_all(self) -> None:
        """导出所有报告"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._export_conditions()
        self._export_actions()
        self._export_param_type_mapping()
        self._export_frequency_report()
        self._export_markdown_doc()
        self._export_json_templates()

        print(f"\nReports exported to: {self.output_dir}")

    def _export_conditions(self) -> None:
        """导出条件分析"""
        result = {k: v.to_dict() for k, v in
                  sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)}

        path = self.output_dir / "conditions_knowledge.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Exported: {path.name}")

    def _export_actions(self) -> None:
        """导出动作分析"""
        result = {k: v.to_dict() for k, v in
                  sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)}

        path = self.output_dir / "actions_knowledge.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Exported: {path.name}")

    def _export_param_type_mapping(self) -> None:
        """导出参数类型映射规则"""
        type_mapping: Dict[str, Dict] = defaultdict(lambda: {
            "value_patterns": defaultdict(int),
            "sample_values": [],
            "ace_usage": []
        })

        for storage, ace_type in [(self.kb.conditions, "condition"), (self.kb.actions, "action")]:
            for key, ace in storage.items():
                for param_id, param in ace.params.items():
                    schema_type = param.schema_type or "unknown"
                    mapping = type_mapping[schema_type]

                    for pattern, count in param.value_patterns.items():
                        mapping["value_patterns"][pattern] += count

                    for val in list(param.unique_values)[:5]:
                        if val not in mapping["sample_values"]:
                            mapping["sample_values"].append(val)

                    if len(mapping["ace_usage"]) < 15:
                        mapping["ace_usage"].append({
                            "ace": key,
                            "param": param_id,
                            "type": ace_type
                        })

        # 生成规则描述
        result = {}
        for schema_type, data in sorted(type_mapping.items()):
            patterns = dict(data["value_patterns"])
            dominant_pattern = max(patterns.items(), key=lambda x: x[1])[0] if patterns else "unknown"

            result[schema_type] = {
                "dominant_pattern": dominant_pattern,
                "value_patterns": patterns,
                "sample_values": data["sample_values"][:20],
                "total_occurrences": sum(patterns.values()),
                "ace_usage_examples": data["ace_usage"],
                "rule_hint": self._generate_rule_hint(schema_type, dominant_pattern, data["sample_values"])
            }

        path = self.output_dir / "param_type_mapping.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Exported: {path.name}")

    def _generate_rule_hint(self, schema_type: str, dominant_pattern: str, samples: List[str]) -> str:
        """生成参数类型的使用规则提示"""
        hints = {
            "combo": "使用 Schema 中定义的 items 值（kebab-case 字符串）",
            "number": "数字字符串或表达式，如 \"100\" 或 \"Player.X\"",
            "string": "带内嵌引号的字符串，如 \"\\\"Hello\\\"\" 或表达式",
            "layer": "图层索引字符串 \"0\" 或带引号的名称 \"\\\"UI\\\"\"",
            "object": "对象类型名称，如 \"Sprite\" 或 \"Player\"",
            "animation": "带内嵌引号的动画名，如 \"\\\"Walk\\\"\"",
            "cmp": "比较运算符索引：0(=) 1(≠) 2(<) 3(≤) 4(>) 5(≥)",
            "any": "任意值，通常是字符串或数字表达式",
            "boolean": "布尔值或字符串 \"true\"/\"false\"",
        }

        if schema_type in hints:
            return hints[schema_type]

        if dominant_pattern == "quoted_string":
            return "带内嵌引号的字符串值"
        if dominant_pattern == "number_string":
            return "数字字符串"
        if dominant_pattern == "expression_dot":
            return "对象属性表达式，如 \"Object.Property\""
        if dominant_pattern == "combo_kebab":
            return "kebab-case 枚举值"

        return f"参考样例值：{', '.join(samples[:3])}"

    def _export_frequency_report(self) -> None:
        """导出使用频率报告"""
        top_conditions = sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)[:50]
        top_actions = sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)[:50]

        result = {
            "top_conditions": [
                {
                    "key": key,
                    "ace_id": a.ace_id,
                    "object_class": a.object_class,
                    "behavior_type": a.behavior_type,
                    "usage_count": a.usage_count,
                    "params": list(a.params.keys())
                }
                for key, a in top_conditions
            ],
            "top_actions": [
                {
                    "key": key,
                    "ace_id": a.ace_id,
                    "object_class": a.object_class,
                    "behavior_type": a.behavior_type,
                    "usage_count": a.usage_count,
                    "params": list(a.params.keys())
                }
                for key, a in top_actions
            ],
            "statistics": {
                "unique_conditions": len(self.kb.conditions),
                "unique_actions": len(self.kb.actions),
                "total_events": self.kb.total_events,
                "files_analyzed": len(self.kb.analyzed_files)
            }
        }

        path = self.output_dir / "frequency_report.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Exported: {path.name}")

    def _export_json_templates(self) -> None:
        """导出 JSON 模板（用于代码生成）"""
        templates = {
            "conditions": {},
            "actions": {}
        }

        # 取使用最多的条件/动作作为模板
        for key, ace in sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)[:100]:
            if ace.raw_samples:
                # 清理模板，保留结构
                sample = ace.raw_samples[0].copy()
                sample.pop("sid", None)

                # 添加参数类型信息
                param_types = {p_id: p.schema_type for p_id, p in ace.params.items()}

                templates["conditions"][key] = {
                    "template": sample,
                    "param_types": param_types,
                    "usage_count": ace.usage_count
                }

        for key, ace in sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)[:100]:
            if ace.raw_samples:
                sample = ace.raw_samples[0].copy()
                sample.pop("sid", None)

                param_types = {p_id: p.schema_type for p_id, p in ace.params.items()}

                templates["actions"][key] = {
                    "template": sample,
                    "param_types": param_types,
                    "usage_count": ace.usage_count
                }

        path = self.output_dir / "json_templates.json"
        path.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Exported: {path.name}")

    def _export_markdown_doc(self) -> None:
        """导出 Markdown 文档"""
        lines = [
            "# Construct 3 Event Sheet Knowledge Base",
            "",
            f"> 最后更新: {self.kb.last_updated}",
            f"> 分析文件数: {len(self.kb.analyzed_files)}",
            "",
            "## 统计概览",
            "",
            f"- 事件块总数: {self.kb.total_events:,}",
            f"- 条件使用次数: {self.kb.total_conditions:,} ({len(self.kb.conditions)} 种)",
            f"- 动作使用次数: {self.kb.total_actions:,} ({len(self.kb.actions)} 种)",
            "",
            "---",
            "",
            "## 参数类型规则",
            "",
            "| Schema 类型 | 主要格式 | 示例 | 规则说明 |",
            "|-------------|----------|------|----------|",
        ]

        # 收集类型信息
        type_info = defaultdict(lambda: {"patterns": defaultdict(int), "samples": []})
        for storage in [self.kb.conditions, self.kb.actions]:
            for ace in storage.values():
                for param in ace.params.values():
                    if param.schema_type:
                        info = type_info[param.schema_type]
                        for p, c in param.value_patterns.items():
                            info["patterns"][p] += c
                        info["samples"].extend(list(param.unique_values)[:3])

        for schema_type, info in sorted(type_info.items()):
            if info["patterns"]:
                dominant = max(info["patterns"].items(), key=lambda x: x[1])[0]
                samples = list(set(info["samples"]))[:2]
                samples_str = ", ".join(f"`{s[:20]}`" for s in samples)
                rule = self._generate_rule_hint(schema_type, dominant, samples)
                lines.append(f"| `{schema_type}` | {dominant} | {samples_str} | {rule[:50]} |")

        lines.extend([
            "",
            "---",
            "",
            "## Top 30 常用条件",
            "",
        ])

        for key, ace in sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)[:30]:
            params = [f"`{p}:{k.schema_type}`" for p, k in ace.params.items()]
            params_str = ", ".join(params) if params else "无参数"
            lines.append(f"1. **{key}** ({ace.usage_count}次) - {params_str}")

        lines.extend([
            "",
            "## Top 30 常用动作",
            "",
        ])

        for key, ace in sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)[:30]:
            params = [f"`{p}:{k.schema_type}`" for p, k in ace.params.items()]
            params_str = ", ".join(params) if params else "无参数"
            lines.append(f"1. **{key}** ({ace.usage_count}次) - {params_str}")

        # 详细示例
        lines.extend([
            "",
            "---",
            "",
            "## 详细 JSON 示例",
            "",
        ])

        # Top 10 条件和动作的详细示例
        for title, storage in [("条件", self.kb.conditions), ("动作", self.kb.actions)]:
            lines.append(f"### {title}")
            lines.append("")

            for key, ace in sorted(storage.items(), key=lambda x: -x[1].usage_count)[:10]:
                lines.append(f"#### `{key}`")
                lines.append("")

                if ace.params:
                    lines.append("| 参数 | 类型 | 示例值 |")
                    lines.append("|------|------|--------|")
                    for param_id, param in ace.params.items():
                        samples = list(param.unique_values)[:3]
                        samples_str = ", ".join(f"`{s[:25]}`" for s in samples)
                        lines.append(f"| {param_id} | {param.schema_type or '?'} | {samples_str} |")
                    lines.append("")

                if ace.raw_samples:
                    lines.append("<details>")
                    lines.append("<summary>JSON 模板</summary>")
                    lines.append("")
                    lines.append("```json")
                    sample = ace.raw_samples[0].copy()
                    sample.pop("sid", None)
                    lines.append(json.dumps(sample, ensure_ascii=False, indent=2))
                    lines.append("```")
                    lines.append("</details>")
                    lines.append("")

        path = self.output_dir / "eventsheet_knowledge.md"
        path.write_text("\n".join(lines), encoding='utf-8')
        print(f"  Exported: {path.name}")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Construct 3 Event Sheet Deep Analyzer (Incremental Learning)"
    )
    parser.add_argument("--rebuild", action="store_true",
                        help="完全重建知识库（忽略已分析的文件）")
    parser.add_argument("--status", action="store_true",
                        help="显示知识库状态")
    parser.add_argument("--export", action="store_true",
                        help="仅导出报告（不分析）")

    args = parser.parse_args()

    print("=" * 60)
    print("Construct 3 Event Sheet Deep Analyzer")
    print("Incremental Learning Version")
    print("=" * 60)

    # 路径设置
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent

    example_dir = Path(EXAMPLE_PROJECTS_DIR).parent
    if not example_dir.exists():
        example_dir = project_dir.parent / "Construct-Example-Projects"

    schemas_dir = Path(SCHEMAS_DIR)
    if not schemas_dir.exists():
        schemas_dir = project_dir / "data" / "schemas"

    output_dir = project_dir / "data" / "eventsheet_analysis"
    kb_path = output_dir / "knowledge_base.json"

    print(f"\nPaths:")
    print(f"  Examples: {example_dir}")
    print(f"  Schemas: {schemas_dir}")
    print(f"  Knowledge base: {kb_path}")

    if not example_dir.exists():
        print(f"\nError: Example projects not found at {example_dir}")
        return

    # 创建分析器
    if args.rebuild:
        print("\n[REBUILD MODE] Clearing existing knowledge...")
        kb_path.unlink(missing_ok=True)

    analyzer = IncrementalAnalyzer(example_dir, schemas_dir, kb_path)

    # 显示状态
    if args.status:
        status = analyzer.get_status()
        print(f"\n--- Knowledge Base Status ---")
        for k, v in status.items():
            print(f"  {k}: {v}")
        return

    # 仅导出
    if args.export:
        exporter = ReportExporter(analyzer.kb, output_dir)
        exporter.export_all()
        return

    # 执行增量分析
    new_count = analyzer.analyze_incremental()

    if new_count > 0:
        analyzer.save_knowledge()

        # 自动导出报告
        exporter = ReportExporter(analyzer.kb, output_dir)
        exporter.export_all()
    else:
        print("\nNo new files to analyze. Knowledge base is up to date.")
        print("Use --rebuild to force a complete re-analysis.")

    print("\nDone!")


if __name__ == "__main__":
    main()
