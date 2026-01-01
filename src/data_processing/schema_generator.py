"""
将 ACE 参考数据拆分为独立的 Schema 文件
每个插件/行为一个 JSON 文件，便于 RAG 检索
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# 插件分类映射
PLUGIN_CATEGORIES = {
    # Visual Objects (可视对象)
    "visual": [
        "Sprite", "Tiled Background", "9-patch", "Text", "Spritefont",
        "Particles", "Tilemap", "Drawing canvas", "3D shape", "3D camera",
        "Video", "Iframe", "HTML Element", "SVG Picture", "Shadow light"
    ],
    # Form Controls (表单控件)
    "form": [
        "Button", "Text input", "List", "Slider bar", "Progress bar",
        "File chooser", "Dropdown"
    ],
    # Input (输入)
    "input": [
        "Keyboard", "Mouse", "Touch", "Gamepad", "Speech recognition"
    ],
    # Audio/Media (音频媒体)
    "media": [
        "Audio", "Speech synthesis", "MIDI", "User media", "Video recording"
    ],
    # Data & Storage (数据存储)
    "data": [
        "Array", "Dictionary", "JSON", "CSV", "Binary data", "XML",
        "Local storage", "File system", "IndexedDB"
    ],
    # Network (网络)
    "network": [
        "AJAX", "WebSocket", "Bluetooth", "Multiplayer"
    ],
    # System (系统)
    "system": [
        "System", "Browser", "Platform info", "Date", "Geolocation",
        "Clipboard", "Share", "Permissions"
    ],
    # Advanced (高级)
    "advanced": [
        "Function", "Timeline", "Flowchart", "Advanced random",
        "Cryptography"
    ],
    # Ads & Services (广告服务)
    "services": [
        "Construct Game Services", "Mobile Advert", "In-app purchase"
    ]
}

# 行为分类映射
BEHAVIOR_CATEGORIES = {
    # Movement (移动)
    "movement": [
        "Platform", "Bullet", "8 Direction", "Car", "Orbit", "Pathfinding",
        "Move to", "Follow", "Jump thru", "Scroll To", "Line-of-sight",
        "Custom Movement", "Turret", "Rotate", "Physics", "Tile movement"
    ],
    # Effects (效果)
    "effects": [
        "Fade", "Flash", "Tween", "Anchor", "Wrap", "Bound to layout",
        "Destroy outside layout", "Drag & Drop", "Pin", "Solid"
    ],
    # Logic (逻辑)
    "logic": [
        "Timer", "No Save", "Persist"
    ],
    # Instance (实例)
    "instance": [
        "Sine", "Shadow caster", "Hierarchy", "LOS Obstacle"
    ]
}


def get_category(name: str, obj_type: str) -> str:
    """获取对象分类"""
    categories = PLUGIN_CATEGORIES if obj_type == "plugin" else BEHAVIOR_CATEGORIES
    for cat, names in categories.items():
        if name in names or any(n.lower() == name.lower() for n in names):
            return cat
    return "other"


def normalize_filename(name: str) -> str:
    """转换为安全的文件名"""
    # 转小写，空格变连字符
    name = name.lower().replace(" ", "-")
    # 移除 behavior/plugin 后缀
    name = re.sub(r"-?behavior$", "", name)
    name = re.sub(r"-?plugin$", "", name)
    # 移除特殊字符
    name = re.sub(r"[^\w\-]", "", name)
    return name


def split_ace_reference():
    """拆分 ace-reference.json 为独立文件"""
    source_dir = Path(__file__).parent.parent.parent / "source"
    schema_dir = source_dir / "Construct3-Schema"

    # 确保目录存在
    (schema_dir / "plugins").mkdir(parents=True, exist_ok=True)
    (schema_dir / "behaviors").mkdir(parents=True, exist_ok=True)
    (schema_dir / "system").mkdir(parents=True, exist_ok=True)

    # 读取源数据
    ace_file = source_dir / "ace-reference.json"
    if not ace_file.exists():
        print(f"错误: {ace_file} 不存在")
        return

    with open(ace_file, encoding="utf-8") as f:
        data = json.load(f)

    index = {
        "version": "1.0",
        "plugins": {},
        "behaviors": {},
        "system": {}
    }

    # 处理插件
    plugins = data.get("plugins", {})
    for name, info in plugins.items():
        category = get_category(name, "plugin")

        # System 对象特殊处理
        if name.lower() == "system":
            target_dir = schema_dir / "system"
            index["system"][name] = {
                "file": f"system/{normalize_filename(name)}.json",
                "category": "system"
            }
        else:
            target_dir = schema_dir / "plugins"
            index["plugins"][name] = {
                "file": f"plugins/{normalize_filename(name)}.json",
                "category": category
            }

        # 构建 Schema 对象
        schema = {
            "name": name,
            "type": "plugin",
            "category": category,
            "conditions": info.get("conditions", []),
            "actions": info.get("actions", []),
            "expressions": info.get("expressions", [])
        }

        # 统计
        stats = {
            "conditions_count": len(schema["conditions"]),
            "actions_count": len(schema["actions"]),
            "expressions_count": len(schema["expressions"])
        }
        schema["stats"] = stats

        # 写入文件
        filename = normalize_filename(name) + ".json"
        filepath = target_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)

        print(f"  {name} -> {filepath.relative_to(schema_dir)}")

    # 处理行为
    behaviors = data.get("behaviors", {})
    for name, info in behaviors.items():
        category = get_category(name, "behavior")

        index["behaviors"][name] = {
            "file": f"behaviors/{normalize_filename(name)}.json",
            "category": category
        }

        schema = {
            "name": name,
            "type": "behavior",
            "category": category,
            "conditions": info.get("conditions", []),
            "actions": info.get("actions", []),
            "expressions": info.get("expressions", [])
        }

        stats = {
            "conditions_count": len(schema["conditions"]),
            "actions_count": len(schema["actions"]),
            "expressions_count": len(schema["expressions"])
        }
        schema["stats"] = stats

        filename = normalize_filename(name) + ".json"
        filepath = schema_dir / "behaviors" / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)

        print(f"  {name} -> behaviors/{filename}")

    # 写入索引
    index_file = schema_dir / "index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n索引文件: {index_file}")
    print(f"插件: {len(index['plugins'])} 个")
    print(f"行为: {len(index['behaviors'])} 个")
    print(f"系统: {len(index['system'])} 个")


if __name__ == "__main__":
    print("拆分 ACE 参考数据...\n")
    split_ace_reference()
    print("\n完成!")
