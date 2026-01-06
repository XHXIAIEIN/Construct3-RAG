# Construct-3 Copilot

**中文** | [English](README_EN.md)

基于 RAG（检索增强生成）技术的 Construct 3 游戏引擎知识库助手。

## 功能

- **文档问答**: 回答 Construct 3 使用问题，标注来源
- **事件表生成**: 用自然语言描述需求，生成可直接粘贴到编辑器的 JSON

---

## 快速开始

### 1. 准备数据源

所有数据需放在同级目录：

```
Parent Directory/
├── Construct3-Copilot/                    # 本项目
├── Construct3-Manual/                 # 官方手册 Markdown 版
└── Construct-Example-Projects-main/   # 官方示例项目
```

```bash
# 克隆相关仓库
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git Construct3-Manual
git clone https://github.com/Scirra/Construct-Example-Projects.git Construct-Example-Projects-main
```

| 数据源 | 获取方式 | 用途 |
|--------|----------|------|
| `zh-CN_R466.csv` | POEditor | ACE Schema 生成 |
| `Construct3-Manual` | [GitHub](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown |
| `Construct-Example-Projects` | [GitHub](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目 |

### 2. 安装依赖

```bash
cd Construct3-Copilot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 启动服务

```bash
# 启动 Qdrant (Docker)
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 安装 Ollama 并拉取模型
ollama pull qwen2.5:7b   # 或 qwen3:30b (更强但更慢)
```

### 4. 索引数据

```bash
# 生成 ACE Schema (可选，已包含在仓库中。依赖文件: source/zh-CN_R466.csv )
node scripts/generate-schema.js

# 索引数据 (首次约需 15 分钟)
python -m src.data_processing.indexer --rebuild
```

### 5. 启动应用

```bash
python -m src.app.gradio_ui
```

> **注意**: 向量数据库数据保存在 Docker volume 中，不包含在 Git 仓库内。首次使用需执行 `--rebuild` 重建索引。

---

## 项目结构

```
Construct3-Copilot/
├── source/                    # 外部资料 (需手动获取)
│   └── zh-CN_R466.csv         # 官方翻译文件
├── data/
│   └── schemas/               # ACE Schema (72 插件 + 31 行为)
├── scripts/
│   └── generate-schema.js     # Schema 生成脚本
├── src/
│   ├── config.py              # 全局配置
│   ├── collections.py         # 集合定义
│   ├── data_processing/       # 数据处理
│   ├── rag/                   # RAG 核心
│   └── app/                   # Web 界面
├── .claude/
│   └── skills/                # Claude Code Skills
└── requirements.txt
```

---

## Claude Code Skill

本项目包含 Claude Code Skill，可以让 AI 直接生成 Construct 3 剪贴板格式的 JSON。

### 使用方法

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

### 功能

| 功能 | 说明 |
|------|------|
| 生成事件 | 游戏逻辑（移动、碰撞、计分等） |
| 生成对象 | Sprite、Text、TiledBackground 等 |
| 生成布局 | 完整场景（对象 + 实例 + 位置） |
| 生成图像 | 有效的 PNG base64 imageData |

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

## 向量集合

### 文档集合

| 集合 | 源目录 | 内容 |
|------|--------|------|
| `c3_guide` | `getting-started/`, `overview/`, `tips-and-guides/` | 入门教程、概述、技巧 |
| `c3_interface` | `interface/` | 编辑器界面、工具栏、对话框 |
| `c3_project` | `project-primitives/` | 事件、对象、时间轴、流程图 |
| `c3_plugins` | `plugin-reference/` | 插件参考 (65 个) |
| `c3_behaviors` | `behavior-reference/`, `system-reference/` | 行为参考 (31 个) |
| `c3_scripting` | `scripting/` | JavaScript/TypeScript API |

### 特殊集合

| 集合 | 来源 | 内容 |
|------|------|------|
| `c3_examples` | 官方示例项目 | 示例事件 (490 项目, 7,148 事件) |

### ACE Schema

由 `source/zh-CN_R466.csv` 通过 `scripts/generate-schema.js` 生成：

```
data/schemas/
├── index.json          # 概要索引
├── plugins/            # 72 插件 (677 条件, 776 动作, 957 表达式)
├── behaviors/          # 31 行为 (115 条件, 248 动作, 138 表达式)
├── effects/            # 89 特效
└── editor/             # 编辑器配置
```

**统计**: 2,911 ACE (792 条件 + 1,024 动作 + 1,095 表达式)

### 向量数据库统计

| 集合 | 向量数 | 内容 |
|------|--------|------|
| c3_guide | 121 | 入门教程 |
| c3_interface | 146 | 编辑器界面 |
| c3_project | 136 | 项目元素 |
| c3_plugins | 420 | 插件参考 |
| c3_behaviors | 156 | 行为参考 |
| c3_scripting | 201 | 脚本 API |
| c3_examples | 7,148 | 示例代码 |
| **总计** | **8,328** | |

---

## RAG 原理

**RAG = Retrieval-Augmented Generation（检索增强生成）**

| 方式 | 问题 |
|------|------|
| 纯 LLM | AI 只能凭"记忆"回答，可能过时或瞎编 |
| RAG | AI 先去"翻书"找到相关资料，再基于资料回答 |

### 工作流程

```
用户提问 ──→ ① 检索 ──→ ② 增强 ──→ ③ 生成 ──→ 回答
              │          │          │
              ↓          ↓          ↓
           向量数据库   拼接上下文    LLM
```

### 什么是向量化？

**向量化 = 把文字转换成一串数字（语义指纹）**

```
"苹果"  →  [0.12, -0.45, 0.78, ...]   (1024个数字)
"水果"  →  [0.15, -0.42, 0.75, ...]   (很接近！)
"汽车"  →  [0.89, 0.12, -0.56, ...]   (完全不同)
```

意思相近的词，向量距离近；意思不同的词，向量距离远。搜索时，把用户问题也转成向量，找数据库里最接近的文档——这就是**语义搜索**。

### 什么是分块？

**分块 = 把长文档切成小段落**

本项目按 H2 标题切分，每个 H2 段落成为一个独立的"文档块"：

```markdown
# Sprite                              ← H1（文件级别）

## Sprite properties（属性）          ← H2 → 第 1 块
## Sprite conditions（条件）          ← H2 → 第 2 块
## Sprite actions（动作）             ← H2 → 第 3 块
```

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
│  │ (qa/代码)    │    │ (多集合搜索)  │    │ (Qwen3)   │ │
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
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                   │
│  │c3_guide │ │c3_plugins│ │c3_examples│                  │
│  │入门教程  │ │插件参考  │ │示例代码   │                  │
│  └─────────┘ └─────────┘ └─────────┘                   │
└─────────────────────────────────────────────────────────┘
```

---

## 更多文档

- [RAG 详细原理讲解](doc/guides/rag-introduction.md) - 向量化、分块、检索的深入解释

## License

[MIT](LICENSE)
