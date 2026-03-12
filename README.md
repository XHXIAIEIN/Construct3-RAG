# Construct3-RAG

**中文** | [English](README_EN.md)

基于 RAG（检索增强生成）技术的 Construct 3 文档问答助手。

## 功能

- **文档问答**: 回答 Construct 3 使用问题，标注来源与置信度
- **混合检索**: 向量语义检索 + BM25 关键词检索 + 跨集合 RRF 重排序
- **查询扩展**: 自动将中文查询扩展为 ACE Schema 术语，提升检索精度
- **多轮对话**: 带上下文记忆的连续问答
- **流式输出**: 实时显示 LLM 生成过程
- **防幻觉**: Self-Reflection 验证 + 严格引用模式
- **评估系统**: 启发式 + RAGAS 语义指标，综合得分 0.96–0.98

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
| `zh_r475.csv` | POEditor | ACE Schema 生成 |
| `Construct3-Manual` | [GitHub](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown |
| `Construct-Example-Projects` | [GitHub](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目 |

### 2. 安装依赖

```bash
cd Construct3-RAG
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 启动 Qdrant

```bash
docker run -d -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### 4. 配置 LLM

选择以下任一方式：

**方式 A：HuggingFace 本地模型（默认）**
```bash
# 下载模型（示例：Qwen3.5-9B）
# 推荐放在 D:/Models/ 或其他本地路径
```
`.env` 配置：
```
LLM_PROVIDER=huggingface
LLM_MODEL=D:/Models/Qwen3.5-9B
```

**方式 B：Ollama**
```bash
ollama pull qwen2.5:7b   # 或 qwen3:8b、qwen3:30b
```
`.env` 配置：
```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434
```

**方式 C：OpenAI 兼容 API**
```
LLM_PROVIDER=openai
LLM_MODEL=your-model-name
LLM_BASE_URL=https://your-api-endpoint
LLM_API_KEY=your-api-key
```

### 5. 索引数据

```bash
# 生成 ACE Schema (可选，已包含在仓库中)
node scripts/generate-schema.js

# 索引数据 (首次约需 15 分钟)
python -m src.ingest.indexer --rebuild
```

### 6. 启动对话

```bash
python scripts/chat.py
```

> **注意**: 向量数据库数据保存在 Docker volume 中，不包含在 Git 仓库内。首次使用需执行步骤 5 重建索引。

## 技术栈

| 组件       | 选择          | 说明                          |
|-----------|--------------|-------------------------------|
| LLM       | Qwen3.5-9B   | 本地运行，HuggingFace / Ollama / OpenAI 兼容 |
| 向量数据库 | Qdrant       | 高性能向量搜索                  |
| Embedding | BAAI/bge-m3  | 多语言嵌入模型，1024 维          |
| 分块策略   | H2 语义分块   | 按文档结构切分                  |
| 混合检索   | BM25 + 向量  | 关键词 + 语义双路召回             |

## 项目结构

```
Construct3-RAG/
├── data/
│   ├── source/                # 外部资料 (需手动获取)
│   │   └── zh_r475.csv     # 官方翻译文件
│   └── schemas/               # ACE Schema (72 插件 + 31 行为)
├── docs/                      # 设计文档、指南、知识库
├── scripts/                   # 运维脚本 (启动/索引/评估)
│   ├── chat.py                # 对话客户端入口
│   └── evaluate.py            # 评估系统入口
├── src/
│   ├── config.py              # 全局配置
│   ├── collections.py         # 集合定义
│   ├── ingest/                # 数据处理与索引
│   ├── rag/                   # RAG 核心
│   └── locale/                # 多语言 (zh/en)
├── tests/                     # 单元测试 (206 个)
├── .env.example               # 环境变量示例
└── requirements.txt
```

## 向量集合

| 集合 | 内容 | 向量数 |
|------|------|--------|
| `c3_guide` | 入门教程、概述、技巧 | 124 |
| `c3_interface` | 编辑器界面、工具栏、对话框 | 146 |
| `c3_project` | 事件、对象、时间轴、流程图 | 136 |
| `c3_plugins` | 插件参考 (65 个) | 420 |
| `c3_behaviors` | 行为参考 (31 个) | 156 |
| `c3_effects` | 特效参考 | 89 |
| `c3_scripting` | JavaScript/TypeScript API | 201 |
| `c3_ace` | ACE Schema（动作/条件/表达式定义） | 2,927 |
| `c3_terms` | 术语对照表（中英文） | 23,824 |
| `c3_examples` | 官方示例事件（490 个项目） | 7,148 |

**统计**: 35,171 向量，10 个集合

## 评估结果

在 15 个典型问题上的评估结果（启发式指标，Qwen3.5-9B，smart 模式）：

| 指标 | 得分 |
|------|------|
| 综合得分 | **0.96–0.98** |
| 等级分布 | 15/15 A |

## 更多文档

- [RAG 详细原理讲解](docs/rag-introduction.md)

## 参考与致谢

以下项目对本系统的设计与实现提供了直接参考：

| 项目 | 用途 |
|------|------|
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | 哈工大同义词词林（`cilin.txt`），用于查询扩展器的同义词字典（`DictExpander`） |
| [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh) | 反 AI 写作风格指南，内化到 `SYSTEM_MESSAGE` Prompt 以降低回答的模板感 |
| [Anthropic: Lessons from Building Claude Code](https://www.anthropic.com/engineering/claude-code-lessons) | 上下文感知分块策略（Contextual Chunking，49% 检索精度提升）与渐进式检索设计灵感 |
| [explodinggradients/ragas](https://github.com/explodinggradients/ragas) | 评估指标体系参考（faithfulness / answer_relevance / context_precision 等），`RagasEvaluator` 基于相同指标用本地 LLM + 余弦相似度自行实现 |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | Construct 3 官方手册 Markdown 版，所有文档类集合（guide / interface / project / plugins / behaviors / scripting）的原始数据来源 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 3 官方示例项目，`c3_examples` 集合（490 个项目，7,148 个向量）的数据来源 |

## License

[MIT](LICENSE)
