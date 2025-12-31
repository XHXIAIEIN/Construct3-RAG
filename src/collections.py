"""
Construct 3 RAG 向量数据库集合配置

修改此文件可调整文档分类和子分类标记
"""

__all__ = [
    # 集合名称
    "COLLECTION_GUIDE",
    "COLLECTION_INTERFACE",
    "COLLECTION_PROJECT",
    "COLLECTION_PLUGINS",
    "COLLECTION_BEHAVIORS",
    "COLLECTION_SCRIPTING",
    "COLLECTION_TERMS",
    "COLLECTION_EXAMPLES",
    # 集合列表
    "DOC_COLLECTIONS",
    "ALL_COLLECTIONS",
    # 映射配置
    "DIR_TO_COLLECTION",
    "SUBCATEGORY_MAPPING",
    "COLLECTION_DESCRIPTIONS",
]

# ============================================================
# 集合定义 (8 个文档集合 + 2 个数据集合)
# ============================================================

COLLECTION_GUIDE = "c3_guide"           # 入门教程 + 概述 + 技巧指南
COLLECTION_INTERFACE = "c3_interface"   # 编辑器界面文档
COLLECTION_PROJECT = "c3_project"       # 项目元素 (事件/对象/时间轴)
COLLECTION_PLUGINS = "c3_plugins"       # 插件参考
COLLECTION_BEHAVIORS = "c3_behaviors"   # 行为 + 系统参考
COLLECTION_SCRIPTING = "c3_scripting"   # 脚本 API 文档
COLLECTION_TERMS = "c3_terms"           # 术语翻译
COLLECTION_EXAMPLES = "c3_examples"     # 示例项目

# 所有文档集合 (不含 terms/examples)
DOC_COLLECTIONS = [
    COLLECTION_GUIDE,
    COLLECTION_INTERFACE,
    COLLECTION_PROJECT,
    COLLECTION_PLUGINS,
    COLLECTION_BEHAVIORS,
    COLLECTION_SCRIPTING,
]

# 所有集合
ALL_COLLECTIONS = DOC_COLLECTIONS + [COLLECTION_TERMS, COLLECTION_EXAMPLES]


# ============================================================
# 目录 → 集合映射
# ============================================================

DIR_TO_COLLECTION = {
    # Guide: 入门 + 概述 + 技巧
    "getting-started": COLLECTION_GUIDE,
    "overview": COLLECTION_GUIDE,
    "tips-and-guides": COLLECTION_GUIDE,

    # Interface: 编辑器界面
    "interface": COLLECTION_INTERFACE,

    # Project: 项目元素
    "project-primitives": COLLECTION_PROJECT,

    # Plugins: 插件参考
    "plugin-reference": COLLECTION_PLUGINS,

    # Behaviors: 行为 + 系统
    "behavior-reference": COLLECTION_BEHAVIORS,
    "system-reference": COLLECTION_BEHAVIORS,

    # Scripting: 脚本 API
    "scripting": COLLECTION_SCRIPTING,
}


# ============================================================
# 子分类映射 (用于 metadata 标记，便于过滤检索)
# ============================================================

SUBCATEGORY_MAPPING = {
    # Plugin Reference 子分类
    "plugin-reference": {
        # Visual 可视化
        "sprite": "visual",
        "tiled-background": "visual",
        "tilemap": "visual",
        "9-patch": "visual",
        "particles": "visual",
        "text": "visual",
        "sprite-font": "visual",
        "drawing-canvas": "visual",
        "svg-picture": "visual",
        "video": "visual",

        # 3D
        "3d-camera": "3d",
        "3d-shape": "3d",
        "shadow-light": "3d",

        # Form Controls 表单控件
        "button": "form",
        "text-input": "form",
        "list": "form",
        "progress-bar": "form",
        "slider-bar": "form",
        "file-chooser": "form",
        "html-element": "form",
        "iframe": "form",

        # Input 输入
        "keyboard": "input",
        "mouse": "input",
        "touch": "input",
        "gamepad": "input",

        # Data & Storage 数据存储
        "array": "data",
        "dictionary": "data",
        "json": "data",
        "xml": "data",
        "csv": "data",
        "binary-data": "data",
        "local-storage": "data",
        "filesystem": "data",

        # Audio 音频
        "audio": "audio",
        "midi": "audio",
        "speech-recognition": "audio",
        "speech-synthesis": "audio",

        # Web & Network 网络
        "ajax": "network",
        "websocket": "network",
        "multiplayer": "network",
        "browser": "network",

        # Media & Devices 媒体设备
        "user-media": "media",
        "video-recorder": "media",
        "geolocation": "media",
        "bluetooth": "media",
        "bbc-micro-bit": "media",

        # Platform Services 平台服务
        "facebook": "platform",
        "google-play": "platform",
        "instant-games": "platform",
        "mobile-advert": "platform",
        "mobile-iap": "platform",
        "construct-game-services": "platform",

        # Utilities 工具
        "function": "utility",
        "date": "utility",
        "advanced-random": "utility",
        "cryptography": "utility",
        "clipboard": "utility",
        "share": "utility",
        "qrcode": "utility",
        "platform-info": "utility",
        "internationalization": "utility",
        "timeline-controller": "utility",
        "flowchart-controller": "utility",
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
    COLLECTION_GUIDE: "入门教程、概述、技巧指南",
    COLLECTION_INTERFACE: "编辑器界面 (工具栏、对话框、调试器)",
    COLLECTION_PROJECT: "项目元素 (事件、对象、时间轴、流程图)",
    COLLECTION_PLUGINS: "插件参考 (Sprite、Audio、Array 等)",
    COLLECTION_BEHAVIORS: "行为参考 (Platform、Physics、Tween 等)",
    COLLECTION_SCRIPTING: "脚本 API (JavaScript/TypeScript)",
    COLLECTION_TERMS: "官方术语翻译",
    COLLECTION_EXAMPLES: "示例项目代码",
}
