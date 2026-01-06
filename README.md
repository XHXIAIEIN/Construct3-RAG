# Construct 3 RAG 助手

基于 RAG（检索增强生成）技术的 Construct 3 游戏引擎知识库助手。

## 功能

- **文档问答**: 回答 Construct 3 使用相关问题，并标注来源
- **术语翻译**: 中英术语查询，保持与官方翻译一致
- **代码生成**: 根据需求生成 Construct 3 事件表代码
- **ACE 参考**: 查询插件/行为的 Actions、Conditions、Expressions
- **Claude Code Skill**: 使用 AI 生成可直接粘贴到 C3 编辑器的 JSON

---

## Claude Code Skills

本项目包含 Claude Code Skills，可以让 AI 直接生成 Construct 3 剪贴板格式的 JSON。

### 快速开始

1. 安装 [Claude Code CLI](https://claude.com/claude-code)
2. 在项目目录中运行 `claude`
3. 用自然语言描述你想要的游戏逻辑

### 示例

```
> 创建一个打砖块游戏，球拍用鼠标控制

AI 会生成两个 JSON 文件：
- layout.json  → 粘贴到 Project Bar → Layouts
- events.json  → 粘贴到事件表边缘
```

```
> 添加 WASD 控制的 8 方向移动

AI 会生成事件 JSON → 粘贴到事件表边缘
```

### Skill 功能

| 功能 | 说明 |
|------|------|
| 生成事件 | 游戏逻辑（移动、碰撞、计分等） |
| 生成对象 | Sprite、Text、TiledBackground 等 |
| 生成布局 | 完整场景（对象 + 实例 + 位置） |
| 生成图像 | 有效的 PNG base64 imageData |

### 可用脚本

```bash
# 生成 imageData
python3 .claude/skills/construct3-event-sheet/scripts/generate_imagedata.py --color red -W 32 -H 32

# 生成完整布局
python3 .claude/skills/construct3-event-sheet/scripts/generate_layout.py --preset breakout -o layout.json

# 查询 ACE Schema
python3 .claude/skills/construct3-event-sheet/scripts/query_schema.py plugin sprite set-animation
```

详细文档: [.claude/skills/construct3-event-sheet/SKILL.md](.claude/skills/construct3-event-sheet/SKILL.md)

---

## RAG 原理

**RAG = Retrieval-Augmented Generation（检索增强生成）**

| 方式 | 问题 |
|------|------|
| 纯 LLM | AI 只能凭"记忆"回答，可能过时或瞎编 |
| RAG | AI 先去"翻书"找到相关资料，再基于资料回答 |

RAG 就像给 AI 配了一个**即时查阅资料库的能力**。

### 工作流程

```
用户提问 ──→ ① 检索 ──→ ② 增强 ──→ ③ 生成 ──→ 回答
              │          │          │
              ↓          ↓          ↓
           向量数据库   拼接上下文    LLM
```

### 数据准备（离线，只做一次）

```
原始文档              分块                   向量化                存储
(Markdown/CSV)  ──→  按 H2 标题切分  ──→  转成数字向量  ──→  Qdrant 数据库
```

### 什么是向量化？

**向量化 = 把文字转换成一串数字（语义指纹）**

```
"苹果"  →  [0.12, -0.45, 0.78, ...]   (1024个数字)
"水果"  →  [0.15, -0.42, 0.75, ...]   (很接近！)
"汽车"  →  [0.89, 0.12, -0.56, ...]   (完全不同)
```

意思相近的词，向量距离近；意思不同的词，向量距离远。

搜索时，把用户问题也转成向量，找数据库里最接近的文档——这就是**语义搜索**。

### 什么是分块？

**分块 = 把长文档切成小段落**

本项目按 H2 标题切分，每个 H2 段落成为一个独立的"文档块"：

```markdown
# Sprite                              ← H1（文件级别）

## Sprite properties（属性）          ← H2 → 第 1 块
## Sprite conditions（条件）          ← H2 → 第 2 块
## Sprite actions（动作）             ← H2 → 第 3 块
```

每个块保留元数据（来源、标题、分类），回答时可以标注出处。

---

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                      Gradio Web 界面                      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    RAGChain (chain.py)                   │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ 问题分类      │ → │ 检索上下文    │ → │ LLM 生成   │ │
│  │ (qa/翻译/代码)│    │ (多集合搜索)  │    │ (Qwen3)   │ │
│  └──────────────┘    └──────────────┘    └───────────┘ │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              HybridRetriever (retriever.py)              │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Qdrant 向量数据库                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │c3_guide │ │c3_plugins│ │c3_terms │ │c3_examples│      │
│  │入门教程  │ │插件参考  │ │术语翻译  │ │示例代码   │      │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## 数据源

所有数据来自以下仓库/文件，需放在同级目录：

```
Parent Directory/
├── Construct3-LLM/                    # 本项目
│   ├── source/
│   │   └── zh-CN_R466.csv             # 官方翻译文件 (来自 POEditor)
│   └── data/
│       └── schemas/                   # ACE Schema (自动生成)
│
├── Construct3-Manual/                 # 官方手册 Markdown 版
│   ├── Construct3-Manual/             # 手册文档 (334 文件)
│   └── Construct3-Addon-SDK/          # SDK 文档 (62 文件)
│
└── Construct-Example-Projects-main/   # 官方示例项目
    └── example-projects/              # 示例项目 (490 个)
```

| 数据源 | 获取方式 | 用途 |
|--------|----------|------|
| `zh-CN_R466.csv` | POEditor | 术语翻译 + ACE Schema 生成 |
| `Construct3-Manual` | [Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown |
| `Construct-Example-Projects` | [Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目 |

---

## 向量集合

### 文档集合

来源：`../Construct3-Manual/Construct3-Manual/`

| 集合 | 源目录 | 内容 |
|------|--------|------|
| `c3_guide` | `getting-started/`, `overview/`, `tips-and-guides/` | 入门教程、概述、技巧 |
| `c3_interface` | `interface/` | 编辑器界面、工具栏、对话框 |
| `c3_project` | `project-primitives/` | 事件、对象、时间轴、流程图 |
| `c3_plugins` | `plugin-reference/` | 插件参考 (65 个) |
| `c3_behaviors` | `behavior-reference/`, `system-reference/` | 行为参考 (31 个) |
| `c3_scripting` | `scripting/` | JavaScript/TypeScript API |

<details>
<summary><b>插件子分类</b></summary>

| 分类 | 插件 |
|------|------|
| 3D | 3D camera, 3D shape |
| Data & storage | Array, Binary Data, Dictionary, JSON, Local storage, XML... |
| General | Sprite, Text, Particles, Tilemap, Timeline controller... |
| HTML elements | Button, Text input, List, Slider bar... |
| Input | Keyboard, Mouse, Touch, Gamepad |
| Media | Audio, Video recorder, Speech synthesis... |
| Web | AJAX, Browser, Multiplayer, WebSocket... |

</details>

<details>
<summary><b>行为子分类</b></summary>

| 分类 | 行为 |
|------|------|
| Attributes | Solid, Jump-thru, Persist, Shadow caster |
| General | Anchor, Pin, Fade, Timer, Tween, Drag & Drop... |
| Movements | Platform, 8 Direction, Bullet, Physics, Pathfinding... |

</details>

### 特殊集合

| 集合 | 来源 | 内容 |
|------|------|------|
| `c3_terms` | `source/zh-CN_R466.csv` | 官方术语翻译 (23,255 条) |
| `c3_examples` | `../Construct-Example-Projects-main/example-projects/` | 示例事件 (490 项目, 7,148 事件) |

### ACE Schema

结构化 ACE 数据（双语）：

```
data/schemas/
├── index.json          # 概要索引
├── plugins/            # 72 插件 (677 条件, 776 动作, 957 表达式)
│   ├── sprite.json
│   ├── keyboard.json
│   └── ...
├── behaviors/          # 31 行为 (115 条件, 248 动作, 138 表达式)
│   ├── platform.json
│   └── ...
├── effects/            # 89 特效
└── editor/             # 编辑器配置
```

**统计**: 2,911 ACE (792 条件 + 1,024 动作 + 1,095 表达式)

---

## 技术栈

| 组件 | 选择 | 说明 |
|------|------|------|
| LLM | Qwen3:30b | 本地运行，通过 Ollama |
| 向量数据库 | Qdrant | 高性能向量搜索 |
| Embedding | BAAI/bge-m3 | 多语言嵌入模型，1024 维 |
| 分块策略 | H2 语义分块 | 按文档结构切分 |
| 框架 | LangChain | RAG 编排框架 |
| 前端 | Gradio | 快速搭建 Web 界面 |

---

## 快速开始

```bash
# 1. 克隆相关仓库 (放在同级目录，见「数据源」章节)
git clone https://github.com/<your-fork>/Construct3-LLM.git
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git Construct3-Manual
git clone https://github.com/Scirra/Construct-Example-Projects.git Construct-Example-Projects-main

# 2. 安装依赖
cd Construct3-LLM
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. 启动 Qdrant (Docker)
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 4. 安装 Ollama 并拉取模型
ollama pull qwen2.5:7b   # 或 qwen3:30b (更强但更慢)

# 5. 生成 ACE Schema (可选，已包含在仓库中)
node scripts/generate-schema.js

# 6. 索引数据 (首次约需 15 分钟)
python -m src.data_processing.indexer --rebuild

# 7. 启动 Web 界面
python -m src.app.gradio_ui
```

> **注意**: 向量数据库数据保存在 Docker volume 中，不包含在 Git 仓库内。
> 首次使用需执行 `--rebuild` 重建索引。

---

## 项目结构

```
Construct3-LLM/
├── source/                    # 外部资料 (需手动获取)
│   └── zh-CN_R466.csv         # 官方翻译文件
├── data/                      # 生成的数据
│   └── schemas/               # ACE Schema (72 插件 + 31 行为)
├── scripts/                   # Schema 生成脚本
│   └── generate-schema.js     # Schema 生成 (插件/行为/特效/编辑器)
├── src/
│   ├── config.py              # 全局配置 (统一管理所有路径)
│   ├── collections.py         # 集合定义 + 目录映射 + 子分类
│   ├── data_processing/
│   │   ├── csv_parser.py      # CSV 术语解析 (RAG 检索用)
│   │   ├── markdown_parser.py # Markdown 解析 + H2 分块
│   │   ├── project_parser.py  # 示例项目解析
│   │   ├── schema_parser.py   # Schema 解析器
│   │   ├── indexer.py         # 向量索引
│   │   └── _archive/          # 已归档的旧脚本
│   ├── rag/
│   │   ├── retriever.py       # 多集合检索
│   │   ├── chain.py           # RAG 链
│   │   ├── prompts.py         # 提示词模板
│   │   └── eventsheet_generator.py  # 事件表 JSON 生成
│   └── app/
│       └── gradio_ui.py       # Web 界面
├── tests/                     # 测试文件
├── doc/guides/
│   └── rag-introduction.md    # RAG 详细原理讲解
└── requirements.txt
```

## 关键组件

| 组件 | 文件 | 作用 |
|------|------|------|
| 配置 | `config.py` | 模型路径、数据库地址 |
| 集合定义 | `collections.py` | 向量集合名称、目录映射、子分类 |
| 解析器 | `markdown_parser.py` | Markdown → 小块文本 |
| Schema 解析 | `schema_parser.py` | 读取 ACE Schema 用于向量索引 |
| 索引器 | `indexer.py` | 文本 → 向量 → 存入 Qdrant |
| 检索器 | `retriever.py` | 问题 → 向量 → 搜索相似文档 |
| 生成链 | `chain.py` | 组合检索结果 + LLM 生成回答 |
| 事件生成 | `eventsheet_generator.py` | 生成 C3 剪贴板格式 JSON |
| 界面 | `gradio_ui.py` | Web 交互界面 |

### 向量数据库统计

索引完成后的向量数量：

| 集合 | 向量数 | 内容 |
|------|--------|------|
| c3_guide | 121 | 入门教程 |
| c3_interface | 146 | 编辑器界面 |
| c3_project | 136 | 项目元素 |
| c3_plugins | 420 | 插件参考 |
| c3_behaviors | 156 | 行为参考 |
| c3_scripting | 201 | 脚本 API |
| c3_terms | 23,255 | 术语翻译 |
| c3_examples | 7,148 | 示例代码 |
| **总计** | **31,583** | |

---

## 更多文档

- [RAG 详细原理讲解](doc/guides/rag-introduction.md) - 向量化、分块、检索的深入解释

## License

[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
