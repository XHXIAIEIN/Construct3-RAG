# Construct3-RAG

[English](README.md) | **中文**

Construct 3 ACE 定义 + TypeScript 脚本接口，从官方 CDN 获取。提供关键词搜索 API 和预构建数据文件。

## 数据文件（预构建，无需安装）

本仓库自带 Construct 3 API 定义数据（当前版本 **r476**），**每种语言一套独立文件**，使用 CDN 原始字段名。直接读取即可——无需启动服务、无需安装依赖。数据随 C3 新版本通过 GitHub Action 自动更新。

### 文件结构

```
data/c3-schemas/
  _index.json                              — 从这里开始：插件/行为/特效索引
  en/plugins/{id}.json                     — 英文 ACE 定义（条件、动作、表达式）
  zh/plugins/{id}.json                     — 中文 ACE 定义（相同结构，本地化文本）
  en/behaviors/{id}.json                   — 英文行为 ACE 定义
  zh/behaviors/{id}.json                   — 中文行为 ACE 定义
  en/effects/{id}.json                     — 英文特效定义（参数、分类）
  zh/effects/{id}.json                     — 中文特效定义
  en/editor/index.json                     — 编辑器 UI 元素名称（英文）
  zh/editor/index.json                     — 编辑器 UI 元素名称（中文）
  en/examples/{id}.json                     — 英文示例项目元数据（标签、使用的插件）
  zh/examples/{id}.json                     — 中文示例项目元数据（本地化标签）

data/c3-ts-defs/
  autocomplete-data.json                   — 109 个脚本类 → 方法/属性列表
  plugins/.../*.d.ts                       — 每个插件的完整 TypeScript 接口签名
  behaviors/.../*.d.ts                     — 行为 TypeScript 接口
  preview/interfaces/...                   — 运行时基类（IInstance、IWorldInstance 等）
```

### 如何查询 C3 插件/行为信息

**第 1 步** — 读取 `data/c3-schemas/_index.json`，找到插件或行为的 id：
```json
{
  "plugins": {
    "sprite": {
      "originalId": "Sprite",
      "name_en": "Sprite", "name_zh": "精灵",
      "file": "plugins/sprite.json",
      "conditions": 12, "actions": 16, "expressions": 15
    }
  }
}
```

**第 2 步** — 选择语言目录，读取 schema 文件。

`data/c3-schemas/zh/plugins/sprite.json` — 条件示例（CDN 原始字段名）：
```json
{
  "id": "is-animation-playing",
  "list-name": "正在播放",
  "display-text": "正在播放 {0} 动画",
  "description": "检测当前正在播放哪个的动画。",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": {
    "animation": { "type": "animation", "name": "动画", "desc": "要检测的动画名称。" }
  }
}
```

> 字段名与官方 CDN 一致（`list-name`、`display-text`、表达式用 `translated-name`）。
> 结构字段（`id`、`scriptName`、`category`、`params.*.type`）在所有语言中完全相同。

**第 3 步（仅脚本编程需要）** — 查询 JavaScript/TypeScript API 详情：
1. 读取 `data/c3-ts-defs/autocomplete-data.json`，找到接口类名（如 `ISpriteInstance`）
2. 读取对应的 `.d.ts` 文件获取完整方法签名：`data/c3-ts-defs/plugins/general/sprite/c3runtime/ISpriteInstance.d.ts`

### 速查：什么问题看什么文件？

| 问题 | 应读取的文件 |
|------|-------------|
| 有哪些插件/行为/特效？ | `_index.json` |
| X 插件有什么 ACE？ | `en/plugins/{id}.json` 或 `zh/plugins/{id}.json` |
| 某个 ACE 在事件表中长什么样？ | Schema JSON → `display-text` 字段 |
| 某个 ACE 需要什么参数？ | Schema JSON → `params` 对象 |
| 有哪些特效可用？ | `en/effects/{id}.json` |
| 怎么在 JavaScript 中使用 X？ | `autocomplete-data.json` → 然后读 `.d.ts` 文件 |
| 哪些示例项目用了 X 插件？ | `en/examples/{id}.json` → `used-addons` 字段 |

## API

```bash
pip install -r requirements.txt
python scripts/setup.py
# → http://localhost:8765/playground
```

### POST /search

| 参数 | 值 | 默认 |
|------|-----|------|
| `mode` | `list` · `lookup` · `semantic` · `auto` | `auto` |
| `scope` | `eventsheet` · `scripts` · `js` · `ts` · `all` | `eventsheet` |
| `lang` | `en` · `zh` · `ja` · `ko` | 自动检测 |
| `context` | 返回 LLM 可用的文本 | `false` |
| `debug` | 返回耗时分析 | `false` |

响应示例（`mode=lookup`, `lang=zh`）：
```json
{
  "lookup": {
    "hit": true,
    "lang": "zh",
    "plugin": {"id": "sprite", "name": "Sprite", "name_localized": "精灵"},
    "matches": [
      {
        "ace_id": "on-collision-with-another-object",
        "ace_type": "condition",
        "en": {"name": "On collision with another object", "display": "On collision with {0}"},
        "localized": {"name": "碰撞到其他对象", "display": "碰撞到 {0}"},
        "params": [{"name": "Object", "type": "object"}]
      }
    ]
  }
}
```

完整规格：[docs/api-reference.md](docs/api-reference.md)

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
