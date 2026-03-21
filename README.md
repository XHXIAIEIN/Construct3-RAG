# Construct3-RAG

**中文** | [English](README_EN.md)

Construct 3 文档检索服务。从 Construct 3 官方 CDN 实时获取 ACE 定义、双语翻译、示例项目元数据，结合向量语义检索，提供结构化的查询 API。

## 功能

- **结构化 ACE 查询**: 按插件/行为/关键词查找 Actions、Conditions、Expressions，返回完整的中英文名称、描述、编辑器 display 模板、参数定义
- **双路检索**: Lookup（关键词/规则，<1ms）+ Semantic（向量语义，~1-10s）
- **CDN 数据源**: 从 `editor.construct.net` 自动获取最新版本数据，自动过滤废弃 ACE
- **同义词扩展**: `碰撞` 自动关联 `重叠/collision/overlap`，jieba 分词避免跨词边界噪声
- **多模式 API**: `mode=lookup`（纯关键词，极速）/ `mode=semantic`（向量搜索）/ `mode=auto`（两者结合）

## 快速开始

### 准备数据源

```
Parent Directory/
├── Construct3-RAG/                    # 本项目
├── Construct3-Manual/                 # 官方手册 Markdown 版
└── Construct-Example-Projects/        # 官方示例项目（可选）
```

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG.git
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
git clone https://github.com/Scirra/Construct-Example-Projects.git  # 可选
```

### 一键启动

```bash
# 1. 启动 Qdrant（首次）
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. 安装依赖 → 拉取 CDN 数据 → 构建索引 → 启动服务
python scripts/setup.py
```

打开 `http://localhost:8765/playground` 测试。

### 配置

通过 `.env` 文件或环境变量配置：

```bash
C3_VERSION=r476                              # Construct 3 版本
EMBEDDING_MODEL=BAAI/bge-m3                  # Embedding 模型
RAG_SERVER_PORT=8765                         # API 端口
```

完整配置项见 `src/config.py`。

## API

### POST /search

```bash
# 关键词查询（<1ms，不需要 GPU）
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite collision","mode":"lookup"}'

# 语义搜索
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"how to detect collision","mode":"auto"}'
```

### 响应结构

```json
{
  "query": "Sprite collision",
  "mode": "auto",
  "latency_ms": 0.3,
  "lookup": {
    "hit": true,
    "tier": 1,
    "confidence": 0.85,
    "intent": "ace_search",
    "plugin": {"id": "sprite", "name": "Sprite", "name_zh": "精灵"},
    "keywords": ["collision"],
    "matches": [
      {
        "ace_id": "on-collision-with-another-object",
        "ace_type": "condition",
        "plugin_id": "_common",
        "en": {"name": "On collision with another object", "desc": "...", "display": "On collision with {0}"},
        "zh": {"name": "碰撞到其他对象", "desc": "...", "display": "碰撞到 {0}"},
        "params": [{"name": "Object", "type": "object", "desc": "..."}]
      }
    ],
    "context": "[C] On collision with another object: ... display=\"On collision with {0}\" params=Object(object)"
  },
  "semantic": []
}
```

- `lookup` — 关键词/规则匹配结果，结构化 ACE 数据
- `semantic` — 向量语义搜索结果（文档、示例、术语）
- `context` — 紧凑纯文本，供 LLM 消费

完整 API 文档见 [docs/api-reference.md](docs/api-reference.md)。

## 技术栈

| 组件 | 技术 |
|------|------|
| 向量数据库 | Qdrant |
| Embedding | BAAI/bge-m3 |
| 数据源 | Construct 3 CDN（实时） + Markdown 手册 + 示例项目 |
| 分词 | jieba（全模式，同义词扩展） |
| 语言 | Python 3.11+ |

## 向量集合

| 集合 | 内容 | 向量数 |
|------|------|--------|
| `c3_ace` | ACE 定义（条件/动作/表达式） | ~2,761 |
| `c3_plugins` | 插件参考文档 | ~424 |
| `c3_behaviors` | 行为参考文档 | ~157 |
| `c3_guide` | 入门教程、技巧指南 | ~120 |
| `c3_interface` | 编辑器界面文档 | ~151 |
| `c3_project` | 项目元素（事件、对象） | ~137 |
| `c3_scripting` | 脚本 API 文档 | ~238 |
| `c3_effects` | 特效定义 | ~89 |
| `c3_terms` | 中英术语对照 | ~25,362 |
| `c3_examples` | 示例项目元数据 + 事件块 | ~7,119 |

## 项目结构

```
Construct3-RAG/
├── src/
│   ├── config.py              # 全局配置
│   ├── collections.py         # 向量集合定义
│   ├── api.py                 # FastAPI 服务
│   ├── ingest/                # 数据获取与索引
│   │   ├── c3_fetcher.py      # CDN 数据拉取与缓存
│   │   ├── schema_parser.py   # ACE 解析（CDN → 向量文档）
│   │   ├── indexer.py         # 索引构建
│   │   └── ...
│   └── rag/                   # 检索核心
│       ├── lookup.py          # 关键词查询引擎（3 tier）
│       ├── retriever.py       # 向量检索 + Reranker
│       ├── query_expander.py  # 查询扩展
│       └── ...
├── scripts/
│   ├── setup.py               # 一键安装启动
│   ├── init.py                # CDN 数据初始化
│   └── ...
├── tests/                     # 单元测试（203 个，无需外部服务）
├── docs/                      # 文档
└── .cache/c3-cdn/             # CDN 缓存（自动生成）
```

## 更多文档

- [快速开始](docs/quick-start.md) — 详细安装步骤与配置
- [系统架构](docs/architecture.md) — 检索流程、Lookup 引擎、设计决策
- [API 参考](docs/api-reference.md) — 完整端点规格与示例
- [数据管线](docs/data-pipeline.md) — CDN 拉取、废弃过滤、索引流程

## 参考与致谢

| 项目 | 用途 |
|------|------|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown 版，文档集合数据来源 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目，示例集合数据来源 |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | 哈工大同义词词林，查询扩展同义词字典 |
| [explodinggradients/ragas](https://github.com/explodinggradients/ragas) | 评估指标体系参考 |

## License

[MIT](LICENSE)
