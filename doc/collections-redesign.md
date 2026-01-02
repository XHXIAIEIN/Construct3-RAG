# Collections 重新设计方案

基于 Construct 3 r466 源码分析的 collections 优化方案。

## 当前问题

1. **子分类不完整**: 当前 `SUBCATEGORY_MAPPING` 是手动维护的，缺少部分插件/行为
2. **ACE 数据未充分利用**: `allAces.json` 包含完整的结构化 ACE 数据，但未被直接使用
3. **分类与官方不一致**: 当前分类与 Construct 3 内部分类路径不完全匹配

## Construct 3 官方分类 (来自 pluginList.json / behaviorList.json)

### 插件分类 (72 个插件)

| 分类 | 数量 | 插件 |
|------|------|------|
| `general` | 11 | Sprite, Text, Particles, Tilemap, Timeline, Flowchart... |
| `data-and-storage` | 10 | Array, JSON, Dictionary, LocalStorage, BinaryData... |
| `media` | 9 | Audio, Video, MIDI, SpeechSynthesis... |
| `html-elements` | 8 | Button, TextInput, List, SliderBar... |
| `web` | 5 | AJAX, Browser, Multiplayer, WebSocket |
| `input` | 4 | Keyboard, Mouse, Touch, Gamepad |
| `other` | 7 | AdvancedRandom, Date, DrawingCanvas... |
| `platform-specific` | 4 | Facebook, GooglePlay, InstantGames... |
| `3d` | 3 | Camera3D, Shape3D, Model3D |
| `monetisation` | 2 | Advert, IAP |
| `system` | 1 | System (内置) |
| `deprecated` | 8 | 废弃插件 |

### 行为分类 (31 个行为)

| 分类 | 数量 | 行为 |
|------|------|------|
| `movements` | 14 | Platform, 8Direction, Bullet, Physics, Pathfinding... |
| `general` | 12 | Tween, Timer, Pin, Fade, Anchor, Drag&Drop... |
| `attributes` | 5 | Solid, JumpThru, Persist, ShadowCaster |

---

## 新的 Collections 结构

### 方案 A: 细分插件集合 (推荐)

将插件按官方分类拆分，提高检索精度：

```python
COLLECTIONS = {
    # === 文档集合 (保持不变) ===
    "guide": "c3_guide",
    "interface": "c3_interface",
    "project": "c3_project",
    "scripting": "c3_scripting",

    # === 插件集合 (按官方分类拆分) ===
    "plugins_core": "c3_plugins_core",      # general + system (12)
    "plugins_data": "c3_plugins_data",      # data-and-storage (10)
    "plugins_media": "c3_plugins_media",    # media (9)
    "plugins_web": "c3_plugins_web",        # web + html-elements (13)
    "plugins_input": "c3_plugins_input",    # input (4)
    "plugins_3d": "c3_plugins_3d",          # 3d (3)
    "plugins_other": "c3_plugins_other",    # other + monetisation + platform (13)

    # === 行为集合 (保持一个，用 metadata 区分) ===
    "behaviors": "c3_behaviors",

    # === ACE Schema 集合 (新增) ===
    "ace": "c3_ace",                        # 结构化 ACE 数据

    # === 效果集合 (新增) ===
    "effects": "c3_effects",                # 效果定义

    # === 工具集合 (保持不变) ===
    "terms": "c3_terms",
    "examples": "c3_examples",
}
```

**优点**:
- 检索更精确 (问 Sprite 不会搜到 Array)
- 符合用户心智模型 (按功能分类)
- 单个集合向量数更少，检索更快

**缺点**:
- 集合数量增加
- 跨集合检索需要多次查询

### 方案 B: 保持大集合 + 增强 metadata (保守)

保持现有结构，但使用官方分类路径作为 metadata：

```python
COLLECTIONS = {
    # 文档集合 (保持不变)
    "guide": "c3_guide",
    "interface": "c3_interface",
    "project": "c3_project",
    "plugins": "c3_plugins",        # 所有插件
    "behaviors": "c3_behaviors",    # 所有行为
    "scripting": "c3_scripting",

    # 新增集合
    "ace": "c3_ace",                # 结构化 ACE 数据
    "effects": "c3_effects",        # 效果定义

    # 工具集合
    "terms": "c3_terms",
    "examples": "c3_examples",
}

# 使用官方分类路径作为 subcategory
SUBCATEGORY_MAPPING = {
    "plugin-reference": {
        # 直接使用 pluginList.json 的 path 分类
        "sprite": "general",
        "array": "data-and-storage",
        "audio": "media",
        "ajax": "web",
        # ... 从 pluginList.json 自动生成
    }
}
```

---

## 新增: ACE Schema 集合

从 `allAces.json` 生成结构化的 ACE 向量集合：

### 数据结构

```json
{
    "plugin": "Sprite",
    "category": "general",
    "ace_type": "action",
    "ace_id": "spawn-another-object",
    "ace_name": "Spawn another object",
    "ace_name_zh": "生成另一个对象",
    "params": [
        {"id": "object", "type": "object"},
        {"id": "layer", "type": "layer"},
        {"id": "image-point", "type": "string"}
    ],
    "description": "Create a new instance of an object type..."
}
```

### 向量化策略

每个 ACE 条目生成一个向量，包含：
- 插件/行为名称
- ACE 类型 (action/condition/expression)
- ACE 名称 (中英文)
- 参数信息
- 描述文本

### 检索示例

```
用户: "如何让 Sprite 生成子弹？"
→ 检索 c3_ace 集合
→ 返回: Sprite > Spawn another object action
→ 包含完整参数说明
```

---

## 新增: Effects 集合

从 `allEffects.json` 生成效果向量集合：

```json
{
    "effect_id": "grayscale",
    "effect_name": "Grayscale",
    "effect_name_zh": "灰度",
    "category": "color",
    "params": [...],
    "blend_modes": [...]
}
```

---

## 迁移计划

### Phase 1: 数据准备
1. 解析 `allAces.json` 生成 ACE Schema JSON
2. 解析 `allEffects.json` 生成 Effects JSON
3. 更新 `SUBCATEGORY_MAPPING` 使用官方分类

### Phase 2: 集合重建
1. 创建 `c3_ace` 集合
2. 创建 `c3_effects` 集合
3. (方案A) 拆分插件集合 或 (方案B) 更新 metadata

### Phase 3: 检索优化
1. 更新 retriever.py 支持新集合
2. 添加 ACE 专用检索逻辑
3. 优化多集合检索策略

---

## 预期效果

| 场景 | 当前 | 改进后 |
|------|------|--------|
| "Sprite 有哪些动作?" | 搜索文档，结果分散 | 直接查 ACE 集合，返回完整列表 |
| "如何播放音效?" | 可能混入不相关插件 | 精确搜索 media 类插件 |
| "Tween 怎么用?" | 搜索行为文档 | ACE 集合 + 行为文档双重结果 |
| "灰度效果参数?" | 无法回答 | 直接查 effects 集合 |

---

## 文件变更

```
src/
├── collections.py           # 更新集合定义
├── data_processing/
│   ├── ace_parser.py        # 新增: 解析 allAces.json
│   ├── effects_parser.py    # 新增: 解析 allEffects.json
│   └── indexer.py           # 更新: 支持新集合
└── rag/
    └── retriever.py         # 更新: ACE 检索逻辑
```
