"""
Construct 3 Complete Project Analyzer (Incremental Learning Version)

全面分析 C3 项目的所有组成部分：
- eventSheets: 事件表（条件、动作、参数）
- objectTypes: 对象类型（插件、行为、实例变量）
- layouts: 布局（实例配置、行为属性值）
- project.c3proj: 项目配置
- timelines: 时间轴
- families: 家族

特性：
- 增量学习：只分析新增/修改的文件
- 持久化存储：知识库可累积
- 细粒度分析：每个属性的实际值样例

用法：
  python analyze_projects.py              # 增量学习
  python analyze_projects.py --rebuild    # 完全重建
  python analyze_projects.py --status     # 查看状态
"""

import json
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.config import EXAMPLE_PROJECTS_DIR, SCHEMAS_DIR
except ImportError:
    EXAMPLE_PROJECTS_DIR = Path(__file__).parent.parent.parent / "Construct-Example-Projects" / "example-projects"
    SCHEMAS_DIR = Path(__file__).parent.parent / "data" / "schemas"


# ============================================================
# 工具函数
# ============================================================

def to_hashable(value: Any) -> str:
    """将任意值转为可哈希的字符串"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value) if value is not None else ""


def file_hash(path: Path) -> str:
    """计算文件 MD5"""
    return hashlib.md5(path.read_bytes()).hexdigest()


# ============================================================
# 知识数据结构
# ============================================================

@dataclass
class PropertyKnowledge:
    """属性知识"""
    prop_id: str
    unique_values: Set[str] = field(default_factory=set)
    value_count: int = 0
    samples: List[Dict] = field(default_factory=list)  # {value, source}

    def add_value(self, value: Any, source: str):
        self.value_count += 1
        val_str = to_hashable(value)
        self.unique_values.add(val_str)

        # 保存多样化样例
        if len(self.samples) < 15:
            existing = {to_hashable(s.get("value")) for s in self.samples}
            if val_str not in existing:
                self.samples.append({"value": value, "source": source})

    def merge(self, other: "PropertyKnowledge"):
        self.unique_values.update(other.unique_values)
        self.value_count += other.value_count
        existing = {to_hashable(s.get("value")) for s in self.samples}
        for s in other.samples:
            if to_hashable(s.get("value")) not in existing and len(self.samples) < 15:
                self.samples.append(s)
                existing.add(to_hashable(s.get("value")))

    def to_dict(self) -> Dict:
        return {
            "prop_id": self.prop_id,
            "unique_values": list(self.unique_values)[:30],
            "unique_count": len(self.unique_values),
            "total_count": self.value_count,
            "samples": self.samples[:10]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PropertyKnowledge":
        pk = cls(prop_id=data["prop_id"])
        pk.unique_values = set(data.get("unique_values", []))
        pk.value_count = data.get("total_count", 0)
        pk.samples = data.get("samples", [])
        return pk


@dataclass
class PluginKnowledge:
    """插件使用知识"""
    plugin_id: str
    usage_count: int = 0
    properties: Dict[str, PropertyKnowledge] = field(default_factory=dict)
    behaviors_used: Dict[str, int] = field(default_factory=dict)  # behavior_id -> count
    source_projects: Set[str] = field(default_factory=set)

    def add_property(self, prop_id: str, value: Any, source: str):
        if prop_id not in self.properties:
            self.properties[prop_id] = PropertyKnowledge(prop_id=prop_id)
        self.properties[prop_id].add_value(value, source)

    def merge(self, other: "PluginKnowledge"):
        self.usage_count += other.usage_count
        self.source_projects.update(other.source_projects)
        for bid, count in other.behaviors_used.items():
            self.behaviors_used[bid] = self.behaviors_used.get(bid, 0) + count
        for prop_id, prop in other.properties.items():
            if prop_id in self.properties:
                self.properties[prop_id].merge(prop)
            else:
                self.properties[prop_id] = prop

    def to_dict(self) -> Dict:
        return {
            "plugin_id": self.plugin_id,
            "usage_count": self.usage_count,
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
            "behaviors_used": dict(self.behaviors_used),
            "source_projects": list(self.source_projects)[:20]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PluginKnowledge":
        pk = cls(plugin_id=data["plugin_id"])
        pk.usage_count = data.get("usage_count", 0)
        pk.properties = {k: PropertyKnowledge.from_dict(v) for k, v in data.get("properties", {}).items()}
        pk.behaviors_used = data.get("behaviors_used", {})
        pk.source_projects = set(data.get("source_projects", []))
        return pk


@dataclass
class BehaviorKnowledge:
    """行为使用知识"""
    behavior_id: str
    usage_count: int = 0
    properties: Dict[str, PropertyKnowledge] = field(default_factory=dict)
    attached_to_plugins: Dict[str, int] = field(default_factory=dict)  # plugin_id -> count
    source_projects: Set[str] = field(default_factory=set)

    def add_property(self, prop_id: str, value: Any, source: str):
        if prop_id not in self.properties:
            self.properties[prop_id] = PropertyKnowledge(prop_id=prop_id)
        self.properties[prop_id].add_value(value, source)

    def merge(self, other: "BehaviorKnowledge"):
        self.usage_count += other.usage_count
        self.source_projects.update(other.source_projects)
        for pid, count in other.attached_to_plugins.items():
            self.attached_to_plugins[pid] = self.attached_to_plugins.get(pid, 0) + count
        for prop_id, prop in other.properties.items():
            if prop_id in self.properties:
                self.properties[prop_id].merge(prop)
            else:
                self.properties[prop_id] = prop

    def to_dict(self) -> Dict:
        return {
            "behavior_id": self.behavior_id,
            "usage_count": self.usage_count,
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
            "attached_to_plugins": dict(self.attached_to_plugins),
            "source_projects": list(self.source_projects)[:20]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BehaviorKnowledge":
        bk = cls(behavior_id=data["behavior_id"])
        bk.usage_count = data.get("usage_count", 0)
        bk.properties = {k: PropertyKnowledge.from_dict(v) for k, v in data.get("properties", {}).items()}
        bk.attached_to_plugins = data.get("attached_to_plugins", {})
        bk.source_projects = set(data.get("source_projects", []))
        return bk


@dataclass
class InstanceVariableKnowledge:
    """实例变量知识"""
    var_type: str  # number, string, boolean
    usage_count: int = 0
    names: Set[str] = field(default_factory=set)
    initial_values: Dict[str, PropertyKnowledge] = field(default_factory=dict)  # type -> values

    def add_variable(self, name: str, var_type: str, initial_value: Any, source: str):
        self.usage_count += 1
        self.names.add(name)
        if var_type not in self.initial_values:
            self.initial_values[var_type] = PropertyKnowledge(prop_id=var_type)
        self.initial_values[var_type].add_value(initial_value, source)

    def merge(self, other: "InstanceVariableKnowledge"):
        self.usage_count += other.usage_count
        self.names.update(other.names)
        for vt, prop in other.initial_values.items():
            if vt in self.initial_values:
                self.initial_values[vt].merge(prop)
            else:
                self.initial_values[vt] = prop

    def to_dict(self) -> Dict:
        return {
            "var_type": self.var_type,
            "usage_count": self.usage_count,
            "names": list(self.names)[:50],
            "initial_values": {k: v.to_dict() for k, v in self.initial_values.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "InstanceVariableKnowledge":
        ivk = cls(var_type=data["var_type"])
        ivk.usage_count = data.get("usage_count", 0)
        ivk.names = set(data.get("names", []))
        ivk.initial_values = {k: PropertyKnowledge.from_dict(v) for k, v in data.get("initial_values", {}).items()}
        return ivk


@dataclass
class ACEKnowledge:
    """条件/动作知识（从事件表）"""
    ace_id: str
    ace_type: str
    object_class: str
    behavior_type: Optional[str] = None
    usage_count: int = 0
    params: Dict[str, PropertyKnowledge] = field(default_factory=dict)
    raw_samples: List[Dict] = field(default_factory=list)
    source_projects: Set[str] = field(default_factory=set)

    def add_param(self, param_id: str, value: Any, source: str):
        if param_id not in self.params:
            self.params[param_id] = PropertyKnowledge(prop_id=param_id)
        self.params[param_id].add_value(value, source)

    def merge(self, other: "ACEKnowledge"):
        self.usage_count += other.usage_count
        self.source_projects.update(other.source_projects)
        for param_id, prop in other.params.items():
            if param_id in self.params:
                self.params[param_id].merge(prop)
            else:
                self.params[param_id] = prop
        # 合并样例
        existing = {json.dumps(s, sort_keys=True) for s in self.raw_samples}
        for s in other.raw_samples:
            if json.dumps(s, sort_keys=True) not in existing and len(self.raw_samples) < 5:
                self.raw_samples.append(s)

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
        ak.params = {k: PropertyKnowledge.from_dict(v) for k, v in data.get("params", {}).items()}
        ak.raw_samples = data.get("raw_samples", [])
        ak.source_projects = set(data.get("source_projects", []))
        return ak


@dataclass
class ProjectKnowledge:
    """项目结构知识"""
    # 插件/行为使用统计
    plugin_combinations: Dict[str, int] = field(default_factory=dict)  # "Sprite+Platform+..." -> count
    common_structures: List[Dict] = field(default_factory=list)  # 常见项目结构

    def to_dict(self) -> Dict:
        return {
            "plugin_combinations": dict(sorted(self.plugin_combinations.items(), key=lambda x: -x[1])[:50]),
            "common_structures": self.common_structures[:20]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ProjectKnowledge":
        pk = cls()
        pk.plugin_combinations = data.get("plugin_combinations", {})
        pk.common_structures = data.get("common_structures", [])
        return pk


@dataclass
class CompleteKnowledgeBase:
    """完整知识库"""
    version: str = "2.0"
    last_updated: str = ""

    # 文件追踪
    analyzed_files: Dict[str, str] = field(default_factory=dict)

    # 事件表知识
    conditions: Dict[str, ACEKnowledge] = field(default_factory=dict)
    actions: Dict[str, ACEKnowledge] = field(default_factory=dict)

    # 对象类型知识
    plugins: Dict[str, PluginKnowledge] = field(default_factory=dict)
    behaviors: Dict[str, BehaviorKnowledge] = field(default_factory=dict)
    instance_variables: Dict[str, InstanceVariableKnowledge] = field(default_factory=dict)

    # 项目结构知识
    project_knowledge: ProjectKnowledge = field(default_factory=ProjectKnowledge)

    # 统计
    stats: Dict[str, int] = field(default_factory=dict)

    def save(self, path: Path):
        data = {
            "version": self.version,
            "last_updated": datetime.now().isoformat(),
            "analyzed_files": self.analyzed_files,
            "conditions": {k: v.to_dict() for k, v in self.conditions.items()},
            "actions": {k: v.to_dict() for k, v in self.actions.items()},
            "plugins": {k: v.to_dict() for k, v in self.plugins.items()},
            "behaviors": {k: v.to_dict() for k, v in self.behaviors.items()},
            "instance_variables": {k: v.to_dict() for k, v in self.instance_variables.items()},
            "project_knowledge": self.project_knowledge.to_dict(),
            "stats": self.stats
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path: Path) -> "CompleteKnowledgeBase":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            kb = cls()
            kb.version = data.get("version", "2.0")
            kb.last_updated = data.get("last_updated", "")
            kb.analyzed_files = data.get("analyzed_files", {})
            kb.conditions = {k: ACEKnowledge.from_dict(v) for k, v in data.get("conditions", {}).items()}
            kb.actions = {k: ACEKnowledge.from_dict(v) for k, v in data.get("actions", {}).items()}
            kb.plugins = {k: PluginKnowledge.from_dict(v) for k, v in data.get("plugins", {}).items()}
            kb.behaviors = {k: BehaviorKnowledge.from_dict(v) for k, v in data.get("behaviors", {}).items()}
            kb.instance_variables = {k: InstanceVariableKnowledge.from_dict(v) for k, v in data.get("instance_variables", {}).items()}
            kb.project_knowledge = ProjectKnowledge.from_dict(data.get("project_knowledge", {}))
            kb.stats = data.get("stats", {})
            return kb
        except Exception as e:
            print(f"Warning: Failed to load knowledge base: {e}")
            return cls()

    def merge(self, other: "CompleteKnowledgeBase"):
        self.analyzed_files.update(other.analyzed_files)

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

        for key, plugin in other.plugins.items():
            if key in self.plugins:
                self.plugins[key].merge(plugin)
            else:
                self.plugins[key] = plugin

        for key, behavior in other.behaviors.items():
            if key in self.behaviors:
                self.behaviors[key].merge(behavior)
            else:
                self.behaviors[key] = behavior

        for key, iv in other.instance_variables.items():
            if key in self.instance_variables:
                self.instance_variables[key].merge(iv)
            else:
                self.instance_variables[key] = iv

        for combo, count in other.project_knowledge.plugin_combinations.items():
            self.project_knowledge.plugin_combinations[combo] = \
                self.project_knowledge.plugin_combinations.get(combo, 0) + count

        for k, v in other.stats.items():
            self.stats[k] = self.stats.get(k, 0) + v


# ============================================================
# 分析器
# ============================================================

class CompleteProjectAnalyzer:
    """完整项目分析器"""

    def __init__(self, example_dir: Path, kb_path: Path):
        self.example_dir = example_dir
        self.kb_path = kb_path
        self.kb = CompleteKnowledgeBase.load(kb_path)
        self.session_kb = CompleteKnowledgeBase()
        # 行为名称到 ID 的映射（从 objectTypes 中学习）
        # 例如: "8Direction" -> "EightDir", "Solid" -> "solid"
        # 预定义已知的别名映射（处理 objectType 中未定义但 layout 中使用的情况）
        self.behavior_name_to_id: Dict[str, str] = {
            # Sin 行为的常见别名
            "SineFlash": "Sin",
            "SineVertical": "Sin",
            "SineHorizontal": "Sin",
            "Sine": "Sin",
            "Sine2": "Sin",
            "SineX": "Sin",
            "SineY": "Sin",
            # 其他常见别名
            "8Direction": "EightDir",
            "EightDirection": "EightDir",
            "Solid": "solid",
            "ScrollTo": "scrollto",
            "LineOfSight": "LOS",
            "DragDrop": "DragnDrop",
            "DestroyOutsideLayout": "destroy",
            "BoundToLayout": "bound",
            "Wrap": "wrap",
            "ShadowCaster": "shadowcaster",
            "Jumpthru": "jumpthru",
            "Custom": "custom",
            "CustomMovement": "custom",
        }
        # 对象名称到插件 ID 的映射（从 objectTypes 中学习）
        # 例如: "Player" -> "Sprite", "Background" -> "TiledBg"
        self.object_name_to_plugin_id: Dict[str, str] = {}

    def _should_analyze(self, path: Path, base_dir: Path) -> bool:
        """检查文件是否需要分析"""
        try:
            file_key = str(path.relative_to(base_dir))
            current_hash = file_hash(path)

            if file_key in self.kb.analyzed_files:
                if self.kb.analyzed_files[file_key] == current_hash:
                    return False

            self.session_kb.analyzed_files[file_key] = current_hash
            return True
        except:
            return True

    def _get_ace_key(self, object_class: str, ace_id: str, behavior_type: Optional[str] = None) -> str:
        if behavior_type:
            return f"{object_class}:{behavior_type}.{ace_id}"
        return f"{object_class}.{ace_id}"

    # ----- 事件表分析 -----

    def _analyze_event_ace(self, ace_data: Dict, ace_type: str, project_name: str):
        """分析条件或动作"""
        ace_id = ace_data.get("id", "")
        object_class = ace_data.get("objectClass", "")

        # 处理旧版 Function 插件格式（已弃用）
        # 格式: {"callFunction": "函数名", "parameters": [...]}
        if not ace_id and "callFunction" in ace_data:
            ace_id = "call-function-deprecated"
            object_class = "Function-DEPRECATED"
        elif not ace_id:
            return

        if not object_class:
            object_class = "Unknown"

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

        # 保存样例
        if len(knowledge.raw_samples) < 5:
            sample = {k: v for k, v in ace_data.items() if k != "sid"}
            knowledge.raw_samples.append(sample)

        # 分析参数
        if isinstance(params, dict):
            for param_id, param_value in params.items():
                knowledge.add_param(param_id, param_value, project_name)

    def _process_event(self, event: Dict, project_name: str):
        """处理事件"""
        event_type = event.get("eventType", "")

        if event_type in ("block", "group", "function-block"):
            self.session_kb.stats["events"] = self.session_kb.stats.get("events", 0) + 1

            for cond in event.get("conditions", []):
                self.session_kb.stats["conditions"] = self.session_kb.stats.get("conditions", 0) + 1
                self._analyze_event_ace(cond, "condition", project_name)

            for action in event.get("actions", []):
                self.session_kb.stats["actions"] = self.session_kb.stats.get("actions", 0) + 1
                self._analyze_event_ace(action, "action", project_name)

            for child in event.get("children", []):
                self._process_event(child, project_name)

    def analyze_event_sheet(self, path: Path, project_name: str):
        """分析事件表文件"""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            for event in data.get("events", []):
                self._process_event(event, project_name)
            self.session_kb.stats["event_sheets"] = self.session_kb.stats.get("event_sheets", 0) + 1
        except Exception as e:
            print(f"  Warning: eventSheet {path.name}: {e}")

    # ----- 对象类型分析 -----

    def analyze_object_type(self, path: Path, project_name: str):
        """分析对象类型文件"""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))

            plugin_id = data.get("plugin-id", "Unknown")
            object_name = data.get("name", path.stem)

            # 记录对象名称到插件 ID 的映射
            if object_name and plugin_id != "Unknown":
                self.object_name_to_plugin_id[object_name] = plugin_id

            # 插件使用
            if plugin_id not in self.session_kb.plugins:
                self.session_kb.plugins[plugin_id] = PluginKnowledge(plugin_id=plugin_id)

            plugin = self.session_kb.plugins[plugin_id]
            plugin.usage_count += 1
            plugin.source_projects.add(project_name)

            # 实例变量
            for iv in data.get("instanceVariables", []):
                iv_name = iv.get("name", "")
                iv_type = iv.get("type", "number")
                iv_initial = iv.get("initialValue", "")

                if iv_type not in self.session_kb.instance_variables:
                    self.session_kb.instance_variables[iv_type] = InstanceVariableKnowledge(var_type=iv_type)

                self.session_kb.instance_variables[iv_type].add_variable(
                    iv_name, iv_type, iv_initial, f"{project_name}/{object_name}"
                )

            # 行为
            for bt in data.get("behaviorTypes", []):
                behavior_id = bt.get("behaviorId", "")
                behavior_name = bt.get("name", "")

                if behavior_id:
                    # 记录名称到 ID 的映射
                    if behavior_name:
                        self.behavior_name_to_id[behavior_name] = behavior_id

                    plugin.behaviors_used[behavior_id] = plugin.behaviors_used.get(behavior_id, 0) + 1

                    if behavior_id not in self.session_kb.behaviors:
                        self.session_kb.behaviors[behavior_id] = BehaviorKnowledge(behavior_id=behavior_id)

                    behavior = self.session_kb.behaviors[behavior_id]
                    behavior.usage_count += 1
                    behavior.source_projects.add(project_name)
                    behavior.attached_to_plugins[plugin_id] = behavior.attached_to_plugins.get(plugin_id, 0) + 1

            self.session_kb.stats["object_types"] = self.session_kb.stats.get("object_types", 0) + 1

        except Exception as e:
            print(f"  Warning: objectType {path.name}: {e}")

    # ----- 布局分析 -----

    def analyze_layout(self, path: Path, project_name: str):
        """分析布局文件"""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))

            for layer in data.get("layers", []):
                for instance in layer.get("instances", []):
                    self._analyze_instance(instance, project_name)

            # 非世界实例
            for instance in data.get("nonworld-instances", []):
                self._analyze_instance(instance, project_name)

            self.session_kb.stats["layouts"] = self.session_kb.stats.get("layouts", 0) + 1

        except Exception as e:
            print(f"  Warning: layout {path.name}: {e}")

    def _analyze_instance(self, instance: Dict, project_name: str):
        """分析实例配置"""
        instance_type = instance.get("type", "")

        # 使用 object_name_to_plugin_id 映射将对象名称转换为插件 ID
        # 例如: "Player" -> "Sprite", "Background" -> "TiledBg"
        plugin_id = self.object_name_to_plugin_id.get(instance_type)

        # 插件属性值 - 使用插件 ID 作为键
        properties = instance.get("properties", {})
        if properties and plugin_id:
            if plugin_id not in self.session_kb.plugins:
                self.session_kb.plugins[plugin_id] = PluginKnowledge(plugin_id=plugin_id)
            plugin = self.session_kb.plugins[plugin_id]
            for prop_id, prop_value in properties.items():
                plugin.add_property(prop_id, prop_value, f"{project_name}/{instance_type}")

        # 行为属性值 - 使用行为 ID 作为键（通过名称映射）
        behaviors = instance.get("behaviors", {})
        for behavior_name, behavior_data in behaviors.items():
            behavior_props = behavior_data.get("properties", {})
            if not behavior_props:
                continue

            # 使用 behavior_name_to_id 映射将行为名称转换为 ID
            # 例如: "8Direction" -> "EightDir", "Platform" -> "Platform"
            behavior_key = self.behavior_name_to_id.get(behavior_name, behavior_name)
            if behavior_key not in self.session_kb.behaviors:
                self.session_kb.behaviors[behavior_key] = BehaviorKnowledge(behavior_id=behavior_key)

            behavior = self.session_kb.behaviors[behavior_key]
            for prop_id, prop_value in behavior_props.items():
                behavior.add_property(prop_id, prop_value, f"{project_name}/{instance_type}/{behavior_name}")

        self.session_kb.stats["instances"] = self.session_kb.stats.get("instances", 0) + 1

    # ----- 项目配置分析 -----

    def analyze_project_config(self, path: Path, project_name: str):
        """分析项目配置文件"""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))

            # 使用的插件/行为组合
            used_addons = data.get("usedAddons", [])
            plugins = sorted([a["id"] for a in used_addons if a.get("type") == "plugin"])
            behaviors = sorted([a["id"] for a in used_addons if a.get("type") == "behavior"])

            combo_key = "+".join(plugins) + "|" + "+".join(behaviors)
            self.session_kb.project_knowledge.plugin_combinations[combo_key] = \
                self.session_kb.project_knowledge.plugin_combinations.get(combo_key, 0) + 1

            self.session_kb.stats["projects"] = self.session_kb.stats.get("projects", 0) + 1

        except Exception as e:
            print(f"  Warning: project {path.name}: {e}")

    # ----- 主分析流程 -----

    def analyze_all(self) -> int:
        """分析所有项目"""
        projects_dir = self.example_dir / "example-projects"
        if not projects_dir.exists():
            projects_dir = self.example_dir

        print(f"\nScanning: {projects_dir}")

        # 收集所有文件（使用 **/*.json 搜索子目录）
        all_files = {
            "eventSheets": list(projects_dir.glob("*/eventSheets/**/*.json")),
            "objectTypes": list(projects_dir.glob("*/objectTypes/**/*.json")),
            "layouts": list(projects_dir.glob("*/layouts/**/*.json")),
            "projects": list(projects_dir.glob("*/*.c3proj")),
        }

        total_files = sum(len(v) for v in all_files.values())
        print(f"Found {total_files} files:")
        for k, v in all_files.items():
            print(f"  {k}: {len(v)}")

        new_files = 0
        processed = 0

        # 分析项目配置
        print("\nAnalyzing project configs...")
        for path in all_files["projects"]:
            project_name = path.parent.name
            if self._should_analyze(path, projects_dir):
                self.analyze_project_config(path, project_name)
                new_files += 1
            processed += 1

        # 分析对象类型
        print("Analyzing object types...")
        for i, path in enumerate(all_files["objectTypes"]):
            if (i + 1) % 1000 == 0:
                print(f"  {i + 1}/{len(all_files['objectTypes'])}...")
            project_name = path.parent.parent.name
            if self._should_analyze(path, projects_dir):
                self.analyze_object_type(path, project_name)
                new_files += 1
            processed += 1

        # 分析布局
        print("Analyzing layouts...")
        for path in all_files["layouts"]:
            project_name = path.parent.parent.name
            if self._should_analyze(path, projects_dir):
                self.analyze_layout(path, project_name)
                new_files += 1
            processed += 1

        # 分析事件表
        print("Analyzing event sheets...")
        for path in all_files["eventSheets"]:
            project_name = path.parent.parent.name
            if self._should_analyze(path, projects_dir):
                self.analyze_event_sheet(path, project_name)
                new_files += 1
            processed += 1

        print(f"\nAnalysis complete:")
        print(f"  New/updated files: {new_files}")
        print(f"  Session stats: {dict(self.session_kb.stats)}")

        return new_files

    def save(self):
        """保存知识库"""
        self.kb.merge(self.session_kb)
        self.kb.save(self.kb_path)
        print(f"\nKnowledge base saved: {self.kb_path}")
        print(f"  Total stats: {dict(self.kb.stats)}")
        print(f"  Plugins: {len(self.kb.plugins)}")
        print(f"  Behaviors: {len(self.kb.behaviors)}")
        print(f"  Conditions: {len(self.kb.conditions)}")
        print(f"  Actions: {len(self.kb.actions)}")


# ============================================================
# 报告导出
# ============================================================

class CompleteReportExporter:
    """完整报告导出"""

    def __init__(self, kb: CompleteKnowledgeBase, output_dir: Path):
        self.kb = kb
        self.output_dir = output_dir

    def export_all(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 插件知识
        self._export_json("plugins_knowledge.json",
                          {k: v.to_dict() for k, v in sorted(self.kb.plugins.items(), key=lambda x: -x[1].usage_count)})

        # 行为知识
        self._export_json("behaviors_knowledge.json",
                          {k: v.to_dict() for k, v in sorted(self.kb.behaviors.items(), key=lambda x: -x[1].usage_count)})

        # 条件知识
        self._export_json("conditions_knowledge.json",
                          {k: v.to_dict() for k, v in sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)})

        # 动作知识
        self._export_json("actions_knowledge.json",
                          {k: v.to_dict() for k, v in sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)})

        # 实例变量知识
        self._export_json("instance_variables_knowledge.json",
                          {k: v.to_dict() for k, v in self.kb.instance_variables.items()})

        # 项目结构知识
        self._export_json("project_structures.json", self.kb.project_knowledge.to_dict())

        # 统计摘要
        self._export_json("statistics.json", {
            "files_analyzed": len(self.kb.analyzed_files),
            "plugins": len(self.kb.plugins),
            "behaviors": len(self.kb.behaviors),
            "conditions": len(self.kb.conditions),
            "actions": len(self.kb.actions),
            "stats": self.kb.stats
        })

        # 预排序索引 (Top N)
        self._export_sorted_indexes()

        # ID 映射表
        self._export_id_mappings()

        # System 对象参考 (从 Schema 导入)
        self._export_system_reference()

        # Markdown 文档
        self._export_markdown()

        print(f"Reports exported to: {self.output_dir}")

    def _export_json(self, filename: str, data: Dict):
        path = self.output_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Exported: {filename}")

    def _export_sorted_indexes(self):
        """导出预排序索引，便于快速获取常用模式"""
        indexes = {
            "top_50_actions": [
                {"key": k, "usage_count": v.usage_count, "params": list(v.params.keys())}
                for k, v in sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)[:50]
            ],
            "top_50_conditions": [
                {"key": k, "usage_count": v.usage_count, "params": list(v.params.keys())}
                for k, v in sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)[:50]
            ],
            "top_20_plugins": [
                {"id": k, "usage_count": v.usage_count, "behaviors": list(v.behaviors_used.keys())}
                for k, v in sorted(self.kb.plugins.items(), key=lambda x: -x[1].usage_count)[:20]
            ],
            "top_20_behaviors": [
                {"id": k, "usage_count": v.usage_count, "properties": list(v.properties.keys())}
                for k, v in sorted(self.kb.behaviors.items(), key=lambda x: -x[1].usage_count)[:20]
            ],
        }
        self._export_json("sorted_indexes.json", indexes)

    def _export_id_mappings(self):
        """导出 ID 映射表，支持多格式互转"""
        # 从 Schema 目录加载官方 ID
        schema_dir = Path(__file__).parent.parent / "data" / "schemas"

        plugin_mappings = {}
        behavior_mappings = {}

        # 插件映射
        for schema_file in schema_dir.glob("plugins/*.json"):
            if schema_file.stem == "index":
                continue
            try:
                data = json.loads(schema_file.read_text(encoding='utf-8'))
                schema_id = data.get("id", schema_file.stem)
                name_en = data.get("name_en", "")
                name_zh = data.get("name_zh", "")

                # 查找知识库中对应的 ID
                kb_id = None
                for kid in self.kb.plugins.keys():
                    if kid.lower() == schema_id.lower():
                        kb_id = kid
                        break

                plugin_mappings[schema_id] = {
                    "schema_id": schema_id,
                    "kb_id": kb_id,
                    "name_en": name_en,
                    "name_zh": name_zh,
                }
            except Exception:
                pass

        # 行为映射
        for schema_file in schema_dir.glob("behaviors/*.json"):
            if schema_file.stem == "index":
                continue
            try:
                data = json.loads(schema_file.read_text(encoding='utf-8'))
                schema_id = data.get("id", schema_file.stem)
                name_en = data.get("name_en", "")
                name_zh = data.get("name_zh", "")

                kb_id = None
                for kid in self.kb.behaviors.keys():
                    if kid.lower() == schema_id.lower():
                        kb_id = kid
                        break

                behavior_mappings[schema_id] = {
                    "schema_id": schema_id,
                    "kb_id": kb_id,
                    "name_en": name_en,
                    "name_zh": name_zh,
                }
            except Exception:
                pass

        # 常用别名映射（硬编码）
        alias_mappings = {
            "behaviors": {
                "8Direction": "EightDir",
                "EightDirection": "EightDir",
                "Solid": "solid",
                "ScrollTo": "scrollto",
                "LineOfSight": "LOS",
                "DragDrop": "DragnDrop",
                "DestroyOutsideLayout": "destroy",
                "BoundToLayout": "bound",
                "Wrap": "wrap",
                "ShadowCaster": "shadowcaster",
                "Jumpthru": "jumpthru",
                "Custom": "custom",
                "CustomMovement": "custom",
                "Sine": "Sin",
                "SineFlash": "Sin",
                "SineVertical": "Sin",
                "SineHorizontal": "Sin",
            }
        }

        mappings = {
            "plugins": plugin_mappings,
            "behaviors": behavior_mappings,
            "aliases": alias_mappings,
        }
        self._export_json("id_mappings.json", mappings)

    def _export_system_reference(self):
        """导出 System 对象参考，从 Schema 补充完整的 ACE 定义"""
        schema_dir = Path(__file__).parent.parent / "data" / "schemas"
        system_schema_file = schema_dir / "plugins" / "system.json"

        if not system_schema_file.exists():
            print("  Warning: System schema not found")
            return

        try:
            system_schema = json.loads(system_schema_file.read_text(encoding='utf-8'))

            # 提取条件和动作的简化信息
            conditions_ref = []
            for cond in system_schema.get("conditions", []):
                conditions_ref.append({
                    "id": cond.get("id"),
                    "name_en": cond.get("name_en"),
                    "name_zh": cond.get("name_zh"),
                    "category": cond.get("category"),
                    "params": [
                        {"id": p.get("id"), "type": p.get("type"), "name_en": p.get("name_en")}
                        for p in cond.get("params", [])
                    ]
                })

            actions_ref = []
            for act in system_schema.get("actions", []):
                actions_ref.append({
                    "id": act.get("id"),
                    "name_en": act.get("name_en"),
                    "name_zh": act.get("name_zh"),
                    "category": act.get("category"),
                    "params": [
                        {"id": p.get("id"), "type": p.get("type"), "name_en": p.get("name_en")}
                        for p in act.get("params", [])
                    ]
                })

            expressions_ref = []
            for expr in system_schema.get("expressions", []):
                expressions_ref.append({
                    "id": expr.get("id"),
                    "name_en": expr.get("name_en"),
                    "name_zh": expr.get("name_zh"),
                    "category": expr.get("category"),
                    "returnType": expr.get("returnType"),
                    "params": [
                        {"id": p.get("id"), "type": p.get("type"), "name_en": p.get("name_en")}
                        for p in expr.get("params", [])
                    ]
                })

            # 合并知识库中的使用统计
            system_conditions_usage = {}
            system_actions_usage = {}
            for key, cond in self.kb.conditions.items():
                if key.startswith("System."):
                    ace_id = key.split(".", 1)[1]
                    system_conditions_usage[ace_id] = cond.usage_count

            for key, act in self.kb.actions.items():
                if key.startswith("System."):
                    ace_id = key.split(".", 1)[1]
                    system_actions_usage[ace_id] = act.usage_count

            # 添加使用统计到参考
            for cond in conditions_ref:
                cond["usage_count"] = system_conditions_usage.get(cond["id"], 0)

            for act in actions_ref:
                act["usage_count"] = system_actions_usage.get(act["id"], 0)

            system_ref = {
                "id": "System",
                "name_zh": "系统",
                "name_en": "System",
                "description": "系统对象提供引擎核心功能，无需添加到项目中即可使用",
                "categories": system_schema.get("categories", []),
                "conditions": sorted(conditions_ref, key=lambda x: -x.get("usage_count", 0)),
                "actions": sorted(actions_ref, key=lambda x: -x.get("usage_count", 0)),
                "expressions": expressions_ref,
                "stats": {
                    "conditions": len(conditions_ref),
                    "actions": len(actions_ref),
                    "expressions": len(expressions_ref),
                }
            }

            self._export_json("system_reference.json", system_ref)

        except Exception as e:
            print(f"  Warning: Failed to export System reference: {e}")

    def _export_markdown(self):
        lines = [
            "# Construct 3 Complete Knowledge Base",
            "",
            f"> 最后更新: {self.kb.last_updated}",
            f"> 分析文件数: {len(self.kb.analyzed_files)}",
            "",
            "## 统计概览",
            "",
            f"| 类别 | 数量 |",
            f"|------|------|",
            f"| 项目 | {self.kb.stats.get('projects', 0)} |",
            f"| 对象类型 | {self.kb.stats.get('object_types', 0)} |",
            f"| 布局 | {self.kb.stats.get('layouts', 0)} |",
            f"| 事件表 | {self.kb.stats.get('event_sheets', 0)} |",
            f"| 事件块 | {self.kb.stats.get('events', 0)} |",
            f"| 实例 | {self.kb.stats.get('instances', 0)} |",
            "",
            f"| 知识类型 | 数量 |",
            f"|----------|------|",
            f"| 插件 | {len(self.kb.plugins)} |",
            f"| 行为 | {len(self.kb.behaviors)} |",
            f"| 条件 | {len(self.kb.conditions)} |",
            f"| 动作 | {len(self.kb.actions)} |",
            "",
            "---",
            "",
            "## Top 20 常用插件",
            "",
        ]

        for pid, plugin in sorted(self.kb.plugins.items(), key=lambda x: -x[1].usage_count)[:20]:
            behaviors = ", ".join(sorted(plugin.behaviors_used.keys())[:5])
            lines.append(f"1. **{pid}** ({plugin.usage_count}次) - 常用行为: {behaviors or '无'}")

        lines.extend(["", "## Top 20 常用行为", ""])

        for bid, behavior in sorted(self.kb.behaviors.items(), key=lambda x: -x[1].usage_count)[:20]:
            props = list(behavior.properties.keys())[:3]
            props_str = ", ".join(props) if props else "无属性"
            lines.append(f"1. **{bid}** ({behavior.usage_count}次) - 属性: {props_str}")

        lines.extend(["", "## Top 20 常用条件", ""])

        for key, ace in sorted(self.kb.conditions.items(), key=lambda x: -x[1].usage_count)[:20]:
            params = list(ace.params.keys())[:3]
            params_str = ", ".join(params) if params else "无参数"
            lines.append(f"1. **{key}** ({ace.usage_count}次) - {params_str}")

        lines.extend(["", "## Top 20 常用动作", ""])

        for key, ace in sorted(self.kb.actions.items(), key=lambda x: -x[1].usage_count)[:20]:
            params = list(ace.params.keys())[:3]
            params_str = ", ".join(params) if params else "无参数"
            lines.append(f"1. **{key}** ({ace.usage_count}次) - {params_str}")

        lines.extend([
            "",
            "---",
            "",
            "## ⚠️ 已弃用和被取代的功能",
            "",
            "### 已弃用 (Deprecated)",
            "",
            "以下功能已被弃用，应避免在新项目中使用：",
            "",
            "| 功能 | 状态 | 说明 |",
            "|------|------|------|",
            "| `Function` 插件 | 已弃用 | 使用内置 `Functions` 系统替代 |",
            "",
            "### 被取代 (Superseded)",
            "",
            "以下功能已被更好的替代方案取代，建议新项目使用替代方案：",
            "",
            "| 旧功能 | 替代方案 | 说明 |",
            "|--------|----------|------|",
            "| `Pin` 行为 | Hierarchies (Add child) | 层级系统更可靠，支持对象链 |",
            "| `Fade` 行为 | `Tween` 行为 | Tween 更通用，可控制任意属性 |",
            "| `solid` 行为的 `tags` 属性 | Instance tags | 使用实例标签系统 |",
            "",
            "---",
            "",
            "## 行为属性配置示例",
            "",
        ])

        # 行为属性详情
        for bid, behavior in sorted(self.kb.behaviors.items(), key=lambda x: -x[1].usage_count)[:10]:
            lines.append(f"### {bid}")
            lines.append("")
            if behavior.properties:
                lines.append("| 属性 | 常用值 |")
                lines.append("|------|--------|")
                for prop_id, prop in behavior.properties.items():
                    samples = list(prop.unique_values)[:3]
                    samples_str = ", ".join(f"`{s[:20]}`" for s in samples)
                    lines.append(f"| {prop_id} | {samples_str} |")
                lines.append("")

        path = self.output_dir / "complete_knowledge.md"
        path.write_text("\n".join(lines), encoding='utf-8')
        print(f"  Exported: complete_knowledge.md")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Construct 3 Complete Project Analyzer")
    parser.add_argument("--rebuild", action="store_true", help="完全重建知识库")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--export", action="store_true", help="仅导出报告")
    args = parser.parse_args()

    print("=" * 60)
    print("Construct 3 Complete Project Analyzer")
    print("=" * 60)

    script_dir = Path(__file__).parent
    project_dir = script_dir.parent

    example_dir = Path(EXAMPLE_PROJECTS_DIR).parent
    if not example_dir.exists():
        example_dir = project_dir.parent / "Construct-Example-Projects"

    output_dir = project_dir / "data" / "project_analysis"
    kb_path = output_dir / "complete_knowledge_base.json"

    print(f"\nPaths:")
    print(f"  Examples: {example_dir}")
    print(f"  Output: {output_dir}")

    if not example_dir.exists():
        print(f"\nError: Example projects not found")
        return

    if args.rebuild:
        print("\n[REBUILD MODE] Clearing existing knowledge...")
        kb_path.unlink(missing_ok=True)

    analyzer = CompleteProjectAnalyzer(example_dir, kb_path)

    if args.status:
        print(f"\n--- Knowledge Base Status ---")
        print(f"  Files analyzed: {len(analyzer.kb.analyzed_files)}")
        print(f"  Stats: {analyzer.kb.stats}")
        print(f"  Plugins: {len(analyzer.kb.plugins)}")
        print(f"  Behaviors: {len(analyzer.kb.behaviors)}")
        return

    if args.export:
        exporter = CompleteReportExporter(analyzer.kb, output_dir)
        exporter.export_all()
        return

    new_count = analyzer.analyze_all()

    if new_count > 0:
        analyzer.save()
        exporter = CompleteReportExporter(analyzer.kb, output_dir)
        exporter.export_all()
    else:
        print("\nNo new files to analyze.")

    print("\nDone!")


if __name__ == "__main__":
    main()
