"""
Construct 3 RAG 向量数据库集合配置

修改此文件可调整文档分类和子分类标记
"""

__all__ = [
    "COLLECTIONS",
    "DOC_COLLECTIONS",
    "ALL_COLLECTIONS",
    "DIR_TO_COLLECTION",
    "SUBCATEGORY_MAPPING",
    "COLLECTION_DESCRIPTIONS",
]

# ============================================================
# 集合定义
# ============================================================

COLLECTIONS = {
    "guide": "c3_guide",           # 入门教程 + 概述 + 技巧指南
    "interface": "c3_interface",   # 编辑器界面文档
    "project": "c3_project",       # 项目元素 (事件/对象/时间轴)
    "plugins": "c3_plugins",       # 插件参考
    "behaviors": "c3_behaviors",   # 行为 + 系统参考
    "scripting": "c3_scripting",   # 脚本 API 文档
    "terms": "c3_terms",           # 术语翻译
    "examples": "c3_examples",     # 示例项目
}

# 文档集合 (不含 terms/examples)
DOC_COLLECTIONS = [
    COLLECTIONS["guide"],
    COLLECTIONS["interface"],
    COLLECTIONS["project"],
    COLLECTIONS["plugins"],
    COLLECTIONS["behaviors"],
    COLLECTIONS["scripting"],
]

# 所有集合
ALL_COLLECTIONS = list(COLLECTIONS.values())


# ============================================================
# 目录 → 集合映射
# ============================================================

DIR_TO_COLLECTION = {
    # Guide: 入门 + 概述 + 技巧
    "getting-started": COLLECTIONS["guide"],
    "overview": COLLECTIONS["guide"],
    "tips-and-guides": COLLECTIONS["guide"],

    # Interface: 编辑器界面
    "interface": COLLECTIONS["interface"],

    # Project: 项目元素
    "project-primitives": COLLECTIONS["project"],

    # Plugins: 插件参考
    "plugin-reference": COLLECTIONS["plugins"],

    # Behaviors: 行为 + 系统
    "behavior-reference": COLLECTIONS["behaviors"],
    "system-reference": COLLECTIONS["behaviors"],

    # Scripting: 脚本 API
    "scripting": COLLECTIONS["scripting"],
}


# ============================================================
# 子分类映射 (用于 metadata 标记，便于过滤检索)
# ============================================================

SUBCATEGORY_MAPPING = {
    # Plugin Reference 子分类
    "plugin-reference": {
        # 3D
        "3d-camera": "3d",
        "3d-shape": "3d",

        # Data & storage
        "array": "data",
        "binary-data": "data",
        "clipboard": "data",
        "cryptography": "data",
        "dictionary": "data",
        "file-system": "data",
        "json": "data",
        "local-storage": "data",
        "xml": "data",

        # General
        "9-patch": "general",
        "flowchart-controller": "general",
        "particles": "general",
        "shadow-light": "general",
        "sprite": "general",
        "sprite-font": "general",
        "svg-picture": "general",
        "text": "general",
        "tiled-background": "general",
        "tilemap": "general",
        "timeline-controller": "general",

        # HTML elements
        "button": "html-elements",
        "file-chooser": "html-elements",
        "html-element": "html-elements",
        "iframe": "html-elements",
        "list": "html-elements",
        "progress-bar": "html-elements",
        "slider-bar": "html-elements",
        "text-input": "html-elements",

        # Input
        "gamepad": "input",
        "keyboard": "input",
        "mouse": "input",
        "touch": "input",

        # Media
        "audio": "media",
        "geolocation": "media",
        "midi": "media",
        "qrcode": "media",
        "speech-recognition": "media",
        "speech-synthesis": "media",
        "user-media": "media",
        "video-recorder": "media",

        # Other
        "advanced-random": "other",
        "bluetooth": "other",
        "date": "other",
        "drawing-canvas": "other",
        "internationalization": "other",
        "platform-info": "other",
        "share": "other",

        # Platform specific
        "bbc-micro-bit": "platform-specific",

        # Web
        "ajax": "web",
        "browser": "web",
        "construct-game-services": "web",
        "multiplayer": "web",
        "websocket": "web",
    },

    # Behavior Reference 子分类
    "behavior-reference": {
        # Attributes
        "jump-thru": "attributes",
        "persist": "attributes",
        "shadow-caster": "attributes",
        "solid": "attributes",

        # General
        "anchor": "general",
        "bound-to-layout": "general",
        "destroy-outside-layout": "general",
        "drag-drop": "general",
        "fade": "general",
        "flash": "general",
        "line-of-sight": "general",
        "pin": "general",
        "scroll-to": "general",
        "timer": "general",
        "tween": "general",
        "wrap": "general",

        # Movements
        "8-direction": "movements",
        "bullet": "movements",
        "car": "movements",
        "custom": "movements",
        "follow": "movements",
        "move-to": "movements",
        "orbit": "movements",
        "pathfinding": "movements",
        "physics": "movements",
        "platform": "movements",
        "rotate": "movements",
        "sine": "movements",
        "tile-movement": "movements",
        "turret": "movements",
    },

    # Scripting 子分类
    "scripting": {
        "using-scripting": "using",
        "guides": "guides",
        "scripting-reference": "api",
    },

    # Interface 子分类
    "interface": {
        "bars": "bars",
        "dialogs": "dialogs",
        "debugger": "debugger",
        "file-editors": "editors",
    },

    # Project Primitives 子分类
    "project-primitives": {
        "events": "events",
        "objects": "objects",
        "timelines": "timelines",
        "flowcharts": "flowcharts",
    },
}


# ============================================================
# 集合描述 (用于 UI 显示)
# ============================================================

COLLECTION_DESCRIPTIONS = {
    COLLECTIONS["guide"]: "入门教程、概述、技巧指南",
    COLLECTIONS["interface"]: "编辑器界面 (工具栏、对话框、调试器)",
    COLLECTIONS["project"]: "项目元素 (事件、对象、时间轴、流程图)",
    COLLECTIONS["plugins"]: "插件参考 (Sprite、Audio、Array 等)",
    COLLECTIONS["behaviors"]: "行为参考 (Platform、Physics、Tween 等)",
    COLLECTIONS["scripting"]: "脚本 API (JavaScript/TypeScript)",
    COLLECTIONS["terms"]: "官方术语翻译",
    COLLECTIONS["examples"]: "示例项目代码",
}
