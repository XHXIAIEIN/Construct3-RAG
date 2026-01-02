# 数据处理流程

## 数据源概览

| 数据源 | 格式 | 用途 |
|--------|------|------|
| Construct3-Manual/ | Markdown | 主手册文档 (334 文件) |
| Construct3-Addon-SDK/ | Markdown | 插件开发文档 (62 文件) |
| zh-CN_R466.csv | CSV | 23,513 条中英翻译 |
| example-projects/ | C3 项目 | 490 个示例项目 |

## 1. Markdown 手册处理

### 处理流程

```
Markdown 文件
    │
    ▼
┌─────────────────┐
│ 目录遍历        │  按 collections.py 映射
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ H2 语义分块     │  按 H2 标题切分
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 元数据添加      │  来源文件、集合、分类
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 向量化入库      │  bge-m3 -> Qdrant
└─────────────────┘
```

### 输出格式

```json
{
  "text": "The Sprite object is used to display...",
  "metadata": {
    "source": "plugin-reference/sprite.md",
    "collection": "c3_plugins",
    "category": "general",
    "title": "Sprite"
  }
}
```

## 2. i18n 翻译词条处理

### 原始格式

```
term_key,中文翻译,,,英文原文
text.behaviors.eightdir.actions.stop.list-name,停止移动,,,,Stop
```

### 处理流程

```
CSV 文件
    │
    ▼
┌─────────────────┐
│ 逐行解析        │  分隔符: 逗号
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 路径层级解析     │  text.behaviors.eightdir.actions.stop
│                 │  -> ["behaviors", "eightdir", "actions", "stop"]
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 分类标注        │  behavior/plugin/system/condition/action/expression
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 双索引构建      │  向量索引 + BM25 索引
└─────────────────┘
```

### 输出格式

```json
{
  "term_key": "text.behaviors.eightdir.actions.stop.list-name",
  "path": ["behaviors", "eightdir", "actions", "stop"],
  "category": "behaviors",
  "type": "action",
  "zh": "停止移动",
  "en": "Stop",
  "full_text": "停止移动 | Stop"
}
```

## 3. 示例项目处理

### 项目结构

```
example-projects/
├── stealth-example/
│   ├── project.c3proj         # 项目配置
│   ├── eventSheets/           # 事件表
│   │   └── eMain.json
│   ├── objectTypes/           # 对象类型
│   │   └── Player.json
│   ├── layouts/               # 布局
│   │   └── Main.json
│   └── scripts/               # 脚本
│       └── main.js
```

### 处理流程

```
项目目录
    │
    ▼
┌─────────────────┐
│ 遍历 490 项目   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 解析 c3proj     │  提取项目描述、插件依赖
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 解析事件表      │  eventSheets/*.json
│                 │  提取条件、动作、表达式
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 语义化转换      │  JSON -> 自然语言描述
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 向量化入库      │
└─────────────────┘
```

### 事件表 JSON 示例

原始 JSON:
```json
{
  "eventType": "block",
  "conditions": [
    {"id": "on-start-of-layout", "objectClass": "System"}
  ],
  "actions": [
    {"id": "set-position", "objectClass": "Player", "parameters": {"x": "100", "y": "200"}}
  ]
}
```

转换为自然语言:
```
当布局开始时:
  - 设置 Player 位置为 (100, 200)
```

## 4. 数据统计预估

| 数据类型 | 原始条目 | 分块后条目 | 向量维度 |
|----------|----------|-----------|---------|
| 手册文档 | ~500 页 | ~2,000 chunks | 1024 |
| 术语表 | 23,513 条 | 23,513 条 | 1024 |
| 示例项目 | 490 项目 | ~5,000 事件 | 1024 |
| **总计** | - | ~30,500 向量 | - |

## 脚本位置

```
src/data_processing/
├── markdown_parser.py # Markdown 解析 + H2 分块
├── csv_parser.py      # CSV 术语解析 (RAG 检索用)
├── schema_parser.py   # ACE Schema 解析
├── project_parser.py  # 示例项目解析
└── indexer.py         # 向量化入库

scripts/
├── generate-schema.js           # 核心 Schema 生成
├── generate-enhanced-schema.js  # 增强版 Schema 生成
└── generate-editor-schema.js    # 编辑器 Schema 生成
```
