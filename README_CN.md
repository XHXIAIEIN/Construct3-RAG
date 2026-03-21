# Construct3-RAG

[English](README.md) | **中文**

[Construct 3](https://www.construct.net) 文档检索服务。从官方 CDN 获取 ACE 定义，提供结构化搜索 API，支持中英双语。

## 功能

- **结构化 ACE 查询** — 按插件/行为/关键词查找 Actions、Conditions、Expressions，返回完整的中英文名称、描述、编辑器 display 模板、参数定义
- **双路检索** — Lookup（关键词/规则，<1ms）+ Semantic（向量语义，~1-10s）
- **CDN 实时数据** — 从 `editor.construct.net` 获取最新版本数据，自动过滤废弃 ACE
- **预构建 Schema** — `data/c3-schemas/` 包含即用的 per-plugin JSON 文件（无需安装）
- **多模式 API** — `mode=lookup`（纯关键词，极速）/ `mode=semantic`（向量搜索）/ `mode=auto`（两者结合）

## 快速开始

### 零配置 — 直接读 Schema 文件

预构建的 Schema 文件已提交到仓库，无需安装任何依赖。

```
data/c3-schemas/
  _index.json             — 插件/行为名称索引（中英文 + ACE 数量）
  plugins/sprite.json     — Sprite ACE 定义
  behaviors/platform.json — Platform 行为 ACE 定义
  ...
```

### Lite 模式 — Lookup API，无需 Docker/GPU

```bash
python scripts/setup.py --lite
```

启动仅支持关键词查找的 API 服务。无需 Qdrant，无需 Embedding 模型。

### 完整模式 — Lookup + 语义搜索

```bash
# 1. 启动 Qdrant
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. 完整安装
python scripts/setup.py
```

需要：Python 3.11+、Docker、~4GB 磁盘空间。

### 数据源

```bash
# 必需：官方手册 Markdown 版
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git

# 可选：官方示例项目
git clone https://github.com/Scirra/Construct-Example-Projects.git
```

与本项目放在同一父目录下。

## API

### POST /search

```bash
# 关键词查询（<1ms，无需 GPU）
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite 碰撞检测","mode":"lookup"}'
```

### 响应

```json
{
  "query": "Sprite 碰撞检测",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": {
    "hit": true,
    "tier": 1,
    "confidence": 0.85,
    "intent": "ace_search",
    "lang": "zh",
    "plugin": {"id": "sprite", "name": "Sprite", "name_localized": "精灵"},
    "matches": [
      {
        "ace_id": "on-collision-with-another-object",
        "ace_type": "condition",
        "plugin_id": "_common",
        "en": {"name": "On collision with another object", "desc": "...", "display": "On collision with {0}"},
        "localized": {"name": "碰撞到其他对象", "desc": "...", "display": "碰撞到 {0}"},
        "script_name": "on-collision-with-another-object",
        "category": "common",
        "params": [{"name": "Object", "type": "object", "desc": "..."}]
      }
    ]
  }
}
```

完整 API 文档：[docs/api-reference.md](docs/api-reference.md)

## 技术栈

| 组件 | 技术 |
|------|------|
| 向量数据库 | Qdrant |
| Embedding | BAAI/bge-m3 |
| 数据源 | Construct 3 CDN（实时）+ Markdown 手册 |
| 分词 | jieba（全模式，同义词扩展） |
| 语言 | Python 3.11+ |

## 项目结构

```
Construct3-RAG/
├── src/
│   ├── api.py                 # FastAPI 服务
│   ├── config.py              # 配置
│   ├── ingest/                # CDN 拉取与索引
│   └── rag/                   # Lookup 引擎与向量检索
├── data/
│   └── c3-schemas/            # 预构建 ACE Schema（已提交）
├── scripts/
│   ├── setup.py               # 一键安装启动
│   └── init.py                # CDN 数据初始化
├── tests/                     # 单元测试（无需外部服务）
└── docs/                      # 架构、API 参考、数据管线
```

## 文档

- [快速开始](docs/quick-start.md) — 安装选项与配置
- [系统架构](docs/architecture.md) — 系统设计与 Lookup 引擎
- [API 参考](docs/api-reference.md) — 端点规格与示例
- [数据管线](docs/data-pipeline.md) — CDN 拉取、过滤、索引

## 致谢

| 项目 | 用途 |
|------|------|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown 版 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目 |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | 哈工大同义词词林，查询扩展 |

## License

[MIT](LICENSE)
