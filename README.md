# Construct3-RAG

**中文** | [English](README_EN.md)

基于 RAG（检索增强生成）技术的 Construct 3 文档问答助手。

## 功能

- **文档问答**: 回答 Construct 3 使用问题，标注来源与置信度
- **语义搜索**: 基于向量数据库的智能检索，跨集合重排序
- **多轮对话**: 带上下文记忆的连续问答
- **流式输出**: 实时显示 LLM 生成过程
- **防幻觉**: Self-Reflection 验证 + 严格引用模式

## 快速开始

### 1. 准备数据源

所有数据需放在同级目录：

```
Parent Directory/
├── Construct3-RAG/                    # 本项目
├── Construct3-Manual/                 # 官方手册 Markdown 版
└── Construct-Example-Projects/        # 官方示例项目
```

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG.git
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
git clone https://github.com/Scirra/Construct-Example-Projects.git
```

| 数据源 | 获取方式 | 用途 |
|--------|----------|------|
| `zh-CN_r473.csv` | POEditor | ACE Schema 生成 |
| `Construct3-Manual` | [GitHub](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown |
| `Construct-Example-Projects` | [GitHub](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目 |

### 2. 安装依赖

```bash
cd Construct3-RAG
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
# 生成 ACE Schema (可选，已包含在仓库中)
node scripts/generate-schema.js

# 索引数据 (首次约需 15 分钟)
python -m src.ingest.indexer --rebuild
```

### 5. 配置环境变量（可选）

```bash
cp .env.example .env
# 按需编辑 .env（修改 LLM 模型、端口等）
```

> **注意**: 向量数据库数据保存在 Docker volume 中，不包含在 Git 仓库内。首次使用需执行 `--rebuild` 重建索引。

## 技术栈

| 组件       | 选择          | 说明                          |
|-----------|--------------|-------------------------------|
| LLM       | Qwen3.5-9B   | 本地运行，HuggingFace / Ollama |
| 向量数据库 | Qdrant       | 高性能向量搜索                  |
| Embedding | BAAI/bge-m3  | 多语言嵌入模型，1024 维          |
| 分块策略   | H2 语义分块   | 按文档结构切分                  |

## 项目结构

```
Construct3-RAG/
├── data/
│   ├── source/                # 外部资料 (需手动获取)
│   │   └── zh-CN_r473.csv     # 官方翻译文件
│   └── schemas/               # ACE Schema (72 插件 + 31 行为)
├── docs/                      # 设计文档、指南、知识库
├── scripts/                   # 运维脚本 (启动/索引/清理)
├── src/
│   ├── config.py              # 全局配置
│   ├── collections.py         # 集合定义
│   ├── ingest/                # 数据处理与索引
│   ├── rag/                   # RAG 核心
│   └── locale/                # 多语言 (zh/en)
├── tests/                     # 单元测试
├── .env.example               # 环境变量示例
└── requirements.txt
```

## 向量集合

| 集合 | 源目录 | 内容 |
|------|--------|------|
| `c3_guide` | `getting-started/`, `overview/`, `tips-and-guides/` | 入门教程、概述、技巧 |
| `c3_interface` | `interface/` | 编辑器界面、工具栏、对话框 |
| `c3_project` | `project-primitives/` | 事件、对象、时间轴、流程图 |
| `c3_plugins` | `plugin-reference/` | 插件参考 (65 个) |
| `c3_behaviors` | `behavior-reference/`, `system-reference/` | 行为参考 (31 个) |
| `c3_scripting` | `scripting/` | JavaScript/TypeScript API |
| `c3_examples` | 官方示例项目 | 示例事件 (490 项目, 7,148 事件) |

**统计**: 8,328 向量

## 更多文档

- [RAG 详细原理讲解](docs/rag-introduction.md)

## License

[MIT](LICENSE)
