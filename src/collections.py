"""
Construct 3 RAG 向量数据库集合配置

基于 Construct 3 r466 源码结构优化
分类数据来源: construct-source/r466/plugins/pluginList.json, behaviorList.json
"""

__all__ = [
    "COLLECTIONS",
    "DOC_COLLECTIONS",
    "ALL_COLLECTIONS",
    "DIR_TO_COLLECTION",
    "SUBCATEGORY_MAPPING",
    "COLLECTION_DESCRIPTIONS",
    "PLUGIN_CATEGORIES",
    "BEHAVIOR_CATEGORIES",
    "ACE_TYPES",
    "ACE_PARAM_TYPES",
]

# ============================================================
# 集合定义
# ============================================================

COLLECTIONS = {
    # === 文档集合 ===
    "guide": "c3_guide",  # 入门教程 + 概述 + 技巧指南
    "interface": "c3_interface",  # 编辑器界面文档
    "project": "c3_project",  # 项目元素 (事件/对象/时间轴)
    "plugins": "c3_plugins",  # 插件参考
    "behaviors": "c3_behaviors",  # 行为 + 系统参考
    "scripting": "c3_scripting",  # 脚本 API 文档
    # === ACE Schema 集合 ===
    # 结构化 ACE 数据 (Actions/Conditions/Expressions)
    "ace": "c3_ace",
    "effects": "c3_effects",  # 效果定义
    # === 工具集合 ===
    "terms": "c3_terms",  # 术语翻译
    "examples": "c3_examples",  # 示例项目
}

# 文档集合 (不含 terms/examples/ace/effects)
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
# Construct 3 官方分类
# ============================================================

# 插件官方分类
PLUGIN_CATEGORIES = {
    "3d": ["3dcamera", "3dmodel", "3dshape"],
    "general": [
        "9patch",
        "particles",
        "shadowlight",
        "sprite",
        "spritefont",
        "svgpicture",
        "text",
        "tiledbg",
        "tilemap",
        "timelinecontroller",
        "flowchartcontroller",
    ],
    "data-and-storage": [
        "array",
        "binarydata",
        "clipboard",
        "cryptography",
        "csv",
        "dictionary",
        "filesystem",
        "json",
        "localstorage",
        "xml",
    ],
    "html-elements": [
        "button",
        "filechooser",
        "htmlelement",
        "iframe",
        "list",
        "progressbar",
        "sliderbar",
        "textinput",
    ],
    "input": ["gamepad", "keyboard", "mouse", "touch"],
    "media": [
        "audio",
        "geolocation",
        "midi",
        "qrcode",
        "speechrecognition",
        "speechsynthesis",
        "usermedia",
        "video",
        "videorecorder",
    ],
    "web": ["ajax", "browser", "constructgameservices", "multiplayer", "websocket"],
    "other": [
        "advancedrandom",
        "bluetooth",
        "date",
        "drawingcanvas",
        "internationalization",
        "platforminfo",
        "share",
    ],
    "monetisation": ["admob2", "iap2"],
    "platform-specific": ["bbc-micro-bit", "facebook", "googleplay", "instantgames"],
    "system": ["system"],
    "deprecated": [
        "arcadev4",
        "function",
        "gamecenter",
        "nwjs",
        "pubcenter",
        "twitter",
        "windowsstore",
        "xboxlive",
    ],
}

# 行为官方分类 (来自 behaviorList.json)
BEHAVIOR_CATEGORIES = {
    "movements": [
        "8direction",
        "bullet",
        "car",
        "custom",
        "follow",
        "moveto",
        "orbit",
        "pathfinding",
        "physics",
        "platform",
        "rotate",
        "sin",
        "tilemovement",
        "turret",
    ],
    "general": [
        "anchor",
        "bound",
        "destroy",
        "dragndrop",
        "fade",
        "flash",
        "los",
        "pin",
        "scrollto",
        "timer",
        "tween",
        "wrap",
    ],
    "attributes": ["jumpthru", "nosave", "persist", "shadowcaster", "solid"],
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
        "3d-model": "3d",
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
        # Data & storage
        "array": "data-and-storage",
        "binary-data": "data-and-storage",
        "clipboard": "data-and-storage",
        "cryptography": "data-and-storage",
        "csv": "data-and-storage",
        "dictionary": "data-and-storage",
        "file-system": "data-and-storage",
        "json": "data-and-storage",
        "local-storage": "data-and-storage",
        "xml": "data-and-storage",
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
        "video": "media",
        "video-recorder": "media",
        # Web
        "ajax": "web",
        "browser": "web",
        "construct-game-services": "web",
        "multiplayer": "web",
        "websocket": "web",
        # Other
        "advanced-random": "other",
        "bluetooth": "other",
        "date": "other",
        "drawing-canvas": "other",
        "internationalization": "other",
        "platform-info": "other",
        "share": "other",
        # Monetisation
        "mobile-advert": "monetisation",
        "mobile-iap": "monetisation",
        # Platform specific
        "bbc-micro-bit": "platform-specific",
        "facebook": "platform-specific",
        "google-play": "platform-specific",
        "instant-games": "platform-specific",
    },
    # Behavior Reference 子分类
    "behavior-reference": {
        # Attributes
        "jump-thru": "attributes",
        "no-save": "attributes",
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
    # System Reference 子分类
    "system-reference": {
        "system-expressions": "expressions",
        "system-conditions": "conditions",
        "system-actions": "actions",
    },
}


# ============================================================
# 集合描述 (用于 UI 显示)
# ============================================================

COLLECTION_DESCRIPTIONS = {
    COLLECTIONS["guide"]: "入门教程、概述、技巧指南",
    COLLECTIONS["interface"]: "编辑器界面 (工具栏、对话框、调试器)",
    COLLECTIONS["project"]: "项目元素 (事件、对象、时间轴、流程图)",
    COLLECTIONS["terms"]: "官方术语翻译",
    COLLECTIONS["plugins"]: "插件参考 (Sprite、Audio、Array 等 72 个)",
    COLLECTIONS["behaviors"]: "行为参考 (Platform、Physics、Tween 等 31 个)",
    COLLECTIONS["effects"]: "效果定义 (Blur、Grayscale 等)",
    COLLECTIONS["ace"]: "ACE Schema (Actions/Conditions/Expressions 2,701 条)",
    COLLECTIONS["scripting"]: "脚本 API (JavaScript/TypeScript)",
    COLLECTIONS["examples"]: "示例项目代码",
}


# ============================================================
# ACE 类型定义
# ============================================================

ACE_TYPES = {
    "action": "动作",
    "condition": "条件",
    "expression": "表达式",
}

# ACE 参数类型
ACE_PARAM_TYPES = {
    "number": "数字",
    "string": "字符串",
    "combo": "下拉选项",
    "object": "对象",
    "layer": "图层",
    "layout": "布局",
    "any": "任意",
    "cmp": "比较运算符",
    "animation": "动画",
    "objectname": "对象名称",
    "eventvariable": "事件变量",
    "instancevariable": "实例变量",
}
