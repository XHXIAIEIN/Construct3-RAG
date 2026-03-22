# Construct3-RAG

[English](README.md) | **中文**

Construct 3 ACE 定义 + TypeScript 脚本接口，从官方 CDN 获取。提供关键词搜索 API 和预构建数据文件。

## 数据文件

无需安装，直接读取：

```
data/c3-schemas/_index.json                — 插件/行为索引（名称 → 文件路径，ACE 数量）
data/c3-schemas/plugins/{id}.json          — 条件、动作、表达式、参数、display 模板
data/c3-schemas/behaviors/{id}.json        — 行为 ACE 定义
data/c3-ts-defs/autocomplete-data.json     — 109 个脚本类 → 方法/属性列表
data/c3-ts-defs/plugins/.../*.d.ts         — 每个插件的完整 TypeScript 接口签名
data/c3-ts-defs/behaviors/.../*.d.ts       — 行为 TypeScript 接口
data/c3-ts-defs/preview/interfaces/...     — 运行时基类（IInstance、IWorldInstance 等）
```

## API

```bash
pip install -r requirements.txt
python scripts/setup.py
# → http://localhost:8765/playground
```

### POST /search

```
mode=list      ACE 名称列表（按类型分组）
mode=lookup    关键词搜索，返回完整 ACE 详情
mode=semantic  向量语义搜索（需要 Qdrant）
mode=auto      lookup + semantic
```

```bash
curl -X POST localhost:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Sprite 碰撞","mode":"lookup"}'
```

```json
{
  "query": "Sprite 碰撞",
  "mode": "lookup",
  "ms": 0.5,
  "lookup": {
    "hit": true,
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

参数：`scope` (eventsheet/scripts/all)、`lang` (en/zh/ja/ko)、`include_context`、`debug`。完整规格：[docs/api-reference.md](docs/api-reference.md)

## 语义搜索（可选）

需要 Docker、~4GB 磁盘、推荐 GPU。

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
git clone https://github.com/XHXIAIEIN/Construct3-Manual.git
python scripts/setup.py --full
```

## 项目结构

```
src/api.py              API 服务（FastAPI）
src/ingest/             CDN 拉取、schema 解析、索引构建
src/rag/                Lookup 引擎、向量检索、查询扩展
data/c3-schemas/        预构建 ACE 定义（已提交）
data/c3-ts-defs/        TypeScript 接口（已提交）
tests/                  172 个单元测试 + 17 个评估用例
docs/                   API 参考、架构、数据管线
.github/workflows/      C3 新版本自动更新（每周检查）
```

## 致谢

数据来自 [Scirra Ltd](https://www.scirra.com) 的 [Construct 3](https://www.construct.net)。Construct 3 是 Scirra Ltd 的商标。

| 来源 | 用途 |
|------|------|
| [Construct 3 编辑器 CDN](https://editor.construct.net) | ACE 定义、TypeScript 接口、多语言翻译 |
| [Construct 3 官方手册](https://www.construct.net/en/make-games/manuals/construct-3) | 官方文档 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | 示例项目 |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown 镜像 |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | 中文同义词词典 |

[MIT](LICENSE)
