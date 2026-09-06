# Construct3-RAG

[English](README.md) | **中文**

面向 Construct 3 问答的结构化参考数据与检索 API，覆盖插件、行为、ACE、特效、示例项目和脚本接口。仓库内的数据可以直接读取；可选服务提供关键词与语义检索。

> 当前 Construct 版本与数据数量以 [`data/c3-schemas/_index.json`](data/c3-schemas/_index.json) 为准；[数据更新工作流](.github/workflows/update.yml)负责提出更新。

> **LLM 请注意：** 回答 Construct 3 问题前，先读 [`data/LLM_PROMPT.md`](data/LLM_PROMPT.md)——定义了如何查找和准确引用 ACE。数据在 `data/c3-schemas/{locale}/`，其中 `locale` 为 `en-US` 或 `zh-CN`。

## 核心概念

[Construct 3](https://www.construct.net) 是一个可视化游戏引擎。游戏通过**事件表**（可视化的 if/then 逻辑）而非代码来构建。

- **插件（Plugin）** — 对象类型（Sprite、Audio、Keyboard 等）
- **行为（Behavior）** — 附加到插件的可复用逻辑（Platform、Tween、Physics 等）
- **ACE** — Actions、Conditions、Expressions 的缩写，是事件表的构建块：
  - **条件（Condition）** — 判断条件（`正在播放动画`、`碰撞到...`）
  - **动作（Action）** — 执行操作（`设置动画`、`销毁`）
  - **表达式（Expression）** — 读取数值（`AnimationFrame`、`X`、`Y`）
- **特效（Effect）** — 视觉着色器（模糊、着色、发光等）

Schema 文件中每个 ACE 条目的字段含义：

| 字段 | 含义 |
|------|------|
| `list-name` | "添加条件/动作"对话框中显示的名称 |
| `display-text` | 事件表中显示的模板（如 `设置动画为 {0}`） |
| `translated-name` | 表达式标识符（仅表达式，如 `AnimationFrame`） |
| `scriptName` | JavaScript API 方法名（用于脚本编程，非事件表） |
| `description` | 提示 / 帮助文本 |
| `params` | 参数定义（`{id: {type, name, desc}}`） |

## 数据文件

无需安装。选择数据目录（`en-US` 或 `zh-CN`）直接读取。

| 路径 | 数量 | 内容 |
|------|-----:|------|
| `c3-schemas/_index.json` | — | 总索引：id → 名称、文件路径、ACE 数量 |
| `c3-schemas/{locale}/plugins/{id}.json` | 见索引 | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 见索引 | 行为 ACE 定义 |
| `c3-schemas/{locale}/effects/{id}.json` | 见索引 | 特效参数、分类 |
| `c3-examples/{locale}/{id}.json` | 随版本变化 | 名称、描述、标签、使用的插件、打开链接 |
| `c3-ts-defs/autocomplete-data.json` | 随版本变化 | 脚本类 → 方法/属性 |
| `c3-ts-defs/**/*.d.ts` | 随版本变化 | 完整 TypeScript 接口签名 |

所有路径基于 `data/`。Schema 文件使用 CDN 原始字段名（`list-name`、`display-text`、`translated-name`）。

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

`zh-CN/plugins/sprite.json` — 条件条目：
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
| X 有什么 ACE？ | `{locale}/plugins/{id}.json` |
| ACE 在事件表中长什么样？ | `display-text` 字段 |
| ACE 需要什么参数？ | `params` 对象 |
| 有哪些特效？ | `{locale}/effects/{id}.json` |
| 哪些示例用了 X？ | `c3-examples/{locale}/*.json` → `used-addons` |
| JavaScript/TypeScript API？ | `autocomplete-data.json` → `.d.ts` |

## LLM 集成

如果你在构建一个帮用户写事件表的 LLM，参见 [`data/LLM_PROMPT.md`](data/LLM_PROMPT.md)——现成的 system prompt，包含输出格式、命名规范和常见错误。

## 搜索 API（可选）

```bash
pip install -r requirements.txt
python scripts/setup.py          # → http://localhost:8765/playground
```

该命令启动确定性、离线的 Direct Lookup，不连接 Qdrant，也不加载嵌入模型。
`mode=auto` 只有在显式启用完整模式时才会追加语义结果。默认使用本地已有
Schema 快照；只有明确需要刷新 CDN 数据时才传入 `--refresh-data`。

### POST /search

| 参数 | 值 | 默认 |
|------|-----|------|
| `mode` | `list` · `lookup` · `semantic` · `auto` | `auto` |
| `scope` | `eventsheet` · `scripts` · `js` · `ts` · `all` | `eventsheet` |
| `lang` | `en` · `zh` · `ja` · `ko` | 自动检测 |
| `context` | 返回 LLM 可用的文本 | `false` |

完整规格：[docs/api-reference.md](docs/api-reference.md)

### 语义搜索（显式启用）

需要 Qdrant + 嵌入模型，推荐 GPU。

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
python scripts/setup.py --full
```

`--full` 会检查 Qdrant、构建向量索引（除非跳过），并以
`LITE_MODE=false` 启动服务；普通 setup 始终保持 lookup-only。

## 项目结构

```
src/api.py              FastAPI 轻量装配入口
src/interfaces/http/    HTTP DTO 与响应映射（规范实现）
src/application/        搜索与健康检查 SOP 工作流
src/domain/             与传输无关的 Lookup/Retrieval 数据
src/lookup/             离线查询服务、处理器与四类索引
src/retrieval/          语义适配器、策略、稳定 ID 与精确去重
src/vector/             共享稠密/稀疏向量适配器
src/ingest/             解析器、契约与四阶段发布管线
src/observability/      请求级跟踪（规范实现）
src/rag/                仅保留旧导入兼容层
data/c3-schemas/        ACE 定义、特效（en-US + zh-CN）
data/c3-examples/       示例项目元数据（en-US + zh-CN）
data/c3-ts-defs/        TypeScript 接口
tests/                  单元测试与回归测试
docs/                   API 参考、架构、数据管线
.github/workflows/      数据更新自动化
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
