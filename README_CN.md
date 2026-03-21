# Construct3-RAG

[English](README.md) | **中文**

[Construct 3](https://www.construct.net) 文档检索服务。从官方 CDN 获取 ACE 定义，提供结构化搜索 API，支持多语言。

## 功能

- **结构化 ACE 查询** — 按插件/行为/关键词查找 Actions、Conditions、Expressions，返回完整的中英文名称、描述、编辑器 display 模板、参数定义
- **双路检索** — Lookup（关键词/规则，<1ms）+ Semantic（向量语义，~1-10s）
- **CDN 实时数据** — 从 `editor.construct.net` 获取最新版本数据，自动过滤废弃 ACE
- **预构建 Schema** — `data/c3-schemas/` 包含即用的 per-plugin JSON 文件（无需安装）
- **多模式 API** — `mode=list`（ACE 名称列表）/ `mode=lookup`（关键词搜索）/ `mode=semantic`（向量搜索）/ `mode=auto`（lookup + semantic）
- **TypeScript 定义** — `data/c3-ts-defs/` 包含完整的脚本 API 接口（150 个 `.d.ts` 文件）
- **自动更新** — GitHub Action 每周检查 C3 新版本，自动创建 PR 更新 API 定义

## 快速开始

### 直接读 Schema 文件

预构建的 API 定义已提交到仓库，无需安装：

```
data/c3-schemas/                              — 每个插件/行为的 ACE 定义
data/c3-ts-defs/                              — TypeScript 脚本 API 接口
data/c3-ts-defs/autocomplete-data.json        — 109 个类的方法列表
```

### 启动 API 服务

```bash
pip install -r requirements.txt
python scripts/setup.py
```

打开 `http://localhost:8765/playground` 测试。

## 完整模式（语义搜索）

在关键词查找基础上增加向量语义搜索。

环境要求：
- Docker（用于 Qdrant 向量数据库）
- ~4GB 磁盘空间（embedding 模型 + 向量索引）
- 推荐 GPU（CPU 可用但较慢，embedding 耗时约 10 倍）

```bash
# 1. 安装全部依赖
pip install -r requirements-full.txt

# 2. 启动 Qdrant
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 3. 克隆数据源（与本项目放在同一父目录下）
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
git clone https://github.com/Scirra/Construct-Example-Projects.git   # 可选

# 4. 完整安装
python scripts/setup.py --full
```

## API

### POST /search

```bash
# 关键词查询（<1ms，无需 GPU）
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite 碰撞检测","mode":"lookup"}'
```

### 响应 — mode=list

```json
{
  "query": "Sprite",
  "mode": "list",
  "ms": 0.5,
  "lookup": {
    "hit": true,
    "lang": "zh",
    "plugin": {"id": "sprite", "name": "Sprite", "name_localized": "精灵"},
    "conditions": ["Is playing", "On finished", "Collisions enabled"],
    "actions": ["Set animation", "Stop", "Start"],
    "expressions": ["AnimationFrame", "AnimationName", "AnimationSpeed"]
  }
}
```

### 响应 — mode=lookup

```json
{
  "query": "Sprite 碰撞检测",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": {
    "hit": true,
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

本项目使用了 [Scirra Ltd](https://www.scirra.com) 开发的 [Construct 3](https://www.construct.net) 的数据。Construct 3 是 Scirra Ltd 的商标。ACE 定义、TypeScript 接口和语言文件从官方 Construct 3 编辑器 CDN 获取，用于教育和工具开发目的。

| 来源 | 用途 |
|------|------|
| [Construct 3 编辑器 CDN](https://editor.construct.net) | ACE 定义、TypeScript 接口、多语言翻译 |
| [Construct 3 官方手册](https://www.construct.net/en/make-games/manuals/construct-3) | 官方文档（通过 [Markdown 镜像](https://github.com/XHXIAIEIN/Construct3-Manual)） |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | 官方示例项目 |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | 哈工大同义词词林，查询扩展 |

## License

[MIT](LICENSE)
