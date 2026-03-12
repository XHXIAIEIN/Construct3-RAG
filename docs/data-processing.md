# 数据处理流程

## 数据源概览

| 数据源 | 格式 | 用途 |
|--------|------|------|
| Construct3-Manual/ | Markdown | 主手册文档 |
| zh_r475.csv | CSV | 23,824 条中英翻译 |
| example-projects/ | C3 项目 | 524 个示例项目（r476） |
| data/schemas/ | JSON Schema | ACE Schema（72 插件 + 31 行为） |

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
│ 向量化入库      │  bge-m3 → Qdrant
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
项目目录（524 个，r476）
    │
    ▼
┌──────────────────────┐
│ examples_parser.py   │  browser JSON + project.c3proj
│ 元数据文档（529 条） │  标题/插件/行为/布局/事件表/
│                      │  families/timelines/flowcharts/scripts
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ event_parser.py      │  eventSheets/*.json → 条件/动作块
│ 事件块（1,821 条）   │  IF {条件} THEN {动作} + 注释上下文
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ event_parser.py      │  scripts/*.js / *.ts → 函数级分块
│ 脚本块（783 条）     │
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 向量化入库           │  bge-m3 → Qdrant c3_examples
│ 合计 2,912 向量      │
└──────────────────────┘
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

## 4. 数据统计（实际）

| 集合 | 向量数 | 数据来源 |
|------|--------|---------|
| c3_guide + c3_interface + c3_project + c3_plugins + c3_behaviors + c3_scripting | 1,183 | Markdown 手册（H2 分块） |
| c3_ace | 2,927 | ACE Schema JSON |
| c3_effects | 89 | Effects Schema JSON |
| c3_terms | 23,824 | CSV 翻译词条 |
| c3_examples | 2,912 | 示例元数据 + 事件块 + 脚本 |
| **合计** | **31,935** | — |

## 脚本位置

```
src/ingest/
├── markdown_parser.py  # Markdown 解析 + H2 分块
├── csv_parser.py       # CSV 术语解析
├── schema_parser.py    # ACE Schema 解析
├── examples_parser.py  # 示例元数据（browser JSON + c3proj）
├── event_parser.py     # 事件块 + 脚本代码解析
└── indexer.py          # 向量化入库（统一调度）

scripts/
└── generate-schema.js  # ACE Schema 生成
```
