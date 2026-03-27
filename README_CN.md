# Construct3-RAG

[English](README.md) | **中文**

从 [Construct 3](https://www.construct.net) 官方 CDN 提取的预构建 API 数据。66 个插件、31 个行为、89 个特效、481 个示例——按语言分离，CDN 原始字段名，开箱即读。

> 当前数据版本：**r476** · 通过 [GitHub Action](.github/workflows/update-c3-data.yml) 每周自动更新

## 数据文件

无需安装。选择语言目录直接读取。

```
data/c3-schemas/
  _index.json                    — 总索引（所有插件、行为、特效）
  {lang}/
    plugins/{id}.json            — 66 个插件：条件、动作、表达式
    behaviors/{id}.json          — 31 个行为：ACE 定义
    effects/{id}.json            — 89 个特效：参数、分类
    examples/{id}.json           — 481 个示例：名称、描述、标签、使用的插件
    editor/index.json            — 编辑器 UI：工具栏、对话框、视图
  （lang = en, zh）

data/c3-ts-defs/
  autocomplete-data.json         — 109 个脚本类 → 方法/属性
  plugins/.../*.d.ts             — 150 个 TypeScript 接口文件
  behaviors/.../*.d.ts
  preview/interfaces/...         — 运行时基类（IInstance、IWorldInstance 等）
```

## 使用方法

### 1. 找到插件/行为

读取 `_index.json`：
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

### 2. 读取 ACE 定义

`zh/plugins/sprite.json` — 条件条目：
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

字段名与官方 CDN 一致：条件/动作用 `list-name`、`display-text`；表达式用 `translated-name`。结构字段（`id`、`scriptName`、`category`、`params.*.type`）在所有语言中完全相同。

### 3. JavaScript/TypeScript API

1. `autocomplete-data.json` → 找到类名（如 `ISpriteInstance`）
2. 读取 `plugins/general/sprite/c3runtime/ISpriteInstance.d.ts` 获取完整签名

### 速查

| 问题 | 去哪找 |
|------|--------|
| 有哪些插件/行为/特效？ | `_index.json` |
| X 有什么 ACE？ | `{lang}/plugins/{id}.json` |
| ACE 在事件表中长什么样？ | `display-text` 字段 |
| ACE 需要什么参数？ | `params` 对象 |
| 有哪些特效？ | `{lang}/effects/{id}.json` |
| 哪些示例用了 X？ | `{lang}/examples/*.json` → `used-addons` |
| JavaScript/TypeScript API？ | `autocomplete-data.json` → `.d.ts` |

## 搜索 API（可选）

```bash
pip install -r requirements.txt
python scripts/setup.py          # → http://localhost:8765/playground
```

### POST /search

| 参数 | 值 | 默认 |
|------|-----|------|
| `mode` | `list` · `lookup` · `semantic` · `auto` | `auto` |
| `scope` | `eventsheet` · `scripts` · `js` · `ts` · `all` | `eventsheet` |
| `lang` | `en` · `zh` · `ja` · `ko` | 自动检测 |
| `context` | 返回 LLM 可用的文本 | `false` |

完整规格：[docs/api-reference.md](docs/api-reference.md)

### 语义搜索

需要 Qdrant + 嵌入模型，推荐 GPU。

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
python scripts/setup.py --full
```

## 项目结构

```
src/api.py              FastAPI 服务
src/ingest/             CDN 拉取、schema 导出、索引构建
src/rag/                Lookup 引擎、向量检索、查询扩展
data/c3-schemas/        预构建 API 数据（en + zh）
data/c3-ts-defs/        TypeScript 接口
tests/                  173 个测试
docs/                   API 参考、架构、数据管线
.github/workflows/      每周自动更新
```

## 致谢

数据来自 [Scirra Ltd](https://www.scirra.com) 的 [Construct 3](https://www.construct.net)。Construct 3 是 Scirra Ltd 的商标。

| 来源 | 用途 |
|------|------|
| [Construct 3 编辑器 CDN](https://editor.construct.net) | ACE 定义、特效、示例、TypeScript 接口、多语言翻译 |
| [Construct 3 官方手册](https://www.construct.net/en/make-games/manuals/construct-3) | 官方文档 |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册 Markdown 镜像 |
| [huyingxi/Synonyms](https://github.com/huyingxi/Synonyms) | 中文同义词词典 |

[MIT](LICENSE)
