# Construct3-RAG

[English](README.md) | **中文**

[Construct 3](https://www.construct.net) 的结构化双语参考数据：插件、行为、ACE、特效、示例项目、脚本接口和原始语言包。`data/` 下的内容都是已提交的 JSON 和 `.d.ts`，脚本或 LLM 可以直接读取。可选服务在数据之上提供查找和语义检索。

Construct 版本和数据数量以 [`data/c3-schemas/_index.json`](data/c3-schemas/_index.json) 为准。Scirra 发布新的稳定版后，[更新工作流](.github/workflows/update.yml)会自动提出 pull request。

## 相关仓库

本仓库只保存机器可读的数据。文字说明、项目源文件和 SDK 在这些仓库：

| 仓库 | 内容 | 与本仓库的关系 |
|---|---|---|
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 示例浏览器中的全部示例，以文件夹项目形式保存 | `data/c3-examples/` 是元数据，这里是源文件。完整模式下克隆到同级目录即可被索引。 |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | 自定义插件、行为、特效和主题的模板与文档 | `data/c3-ts-defs/sdk/` 是类型接口，这里说明怎么用。 |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册、Addon SDK 指南和 Game Services 文档的 Markdown 版 | 概念和操作说明。完整模式下克隆到同级目录即可被索引。 |
| [XHXIAIEIN/Construct3-Manual-PDF](https://github.com/XHXIAIEIN/Construct3-Manual-PDF) | 同一份手册按章节拆分的 PDF | 离线阅读。 |

"同级目录"指与本仓库并列的目录。路径和选项见 [docs/guide/quick-start.md](docs/guide/quick-start.md)。

## 数据文件

无需安装。选择一个语言目录，`en-US` 或 `zh-CN`，直接读取。所有路径基于 `data/`。

| 路径 | 内容 |
|---|---|
| `c3-schemas/_index.json` | 版本、语言列表，以及每个插件、行为、特效的文件路径和 ACE 数量 |
| `c3-schemas/{locale}/plugins/{id}.json` | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 行为 ACE |
| `c3-schemas/{locale}/effects/{id}.json` | 特效参数和分类 |
| `c3-examples/{locale}/{id}.json` | 示例名称、描述、标签、使用的插件、打开链接 |
| `c3-lang/{locale}.json` | CDN 原始语言包，每行一个字符串，用于对比版本和翻译 |
| `c3-ts-defs/autocomplete-data.json` | 脚本类到方法和属性的映射 |
| `c3-ts-defs/**/*.d.ts` | 完整 TypeScript 接口签名 |

字段名与 Construct CDN 一致。`id`、`scriptName`、`category` 和参数类型等结构字段在所有语言中相同，在一种语言里找到的 ACE 可以直接在另一种语言里读取。字段含义、布局和完整示例见 [docs/guide/data-format.md](docs/guide/data-format.md)。

## 读取数据

1. 在 `_index.json` 中找到插件或行为，条目给出 `file` 路径和 ACE 数量。
2. 打开 `data/c3-schemas/{locale}/{file}`，用 `id` 定位 ACE；条件和动作也可以用 `list-name`，表达式用 `translated-name`。`display-text` 是事件表中的显示文本，`params` 列出参数。
3. 脚本接口先在 `autocomplete-data.json` 中找到类名，再打开对应的 `.d.ts`。

`zh-CN/plugins/sprite.json` 中的一个条件：

```json
{
  "id": "is-animation-playing",
  "list-name": "正在播放",
  "display-text": "正在播放 {0} 动画",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": { "animation": { "type": "animation", "name": "动画", "desc": "..." } }
}
```

`en-US/plugins/sprite.json` 中同一个 `id` 的条目携带英文的 `list-name`、`display-text` 和参数名。

## AI 代理与 LLM

先读 [`AGENTS.md`](AGENTS.md)，它给出仓库地图和逐步的查找流程。要帮用户写事件表，把 [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) 作为 system prompt 加载，其中包含输出格式、命名规范和常见错误。

## 搜索服务（可选）

```bash
pip install -r requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

该命令基于已提交的数据启动确定性、离线的查找服务，不连接 Qdrant，也不加载模型。覆盖 Schema、手册和示例项目的语义检索需要显式启用，依赖 Qdrant 和嵌入模型：

```bash
pip install -r requirements-full.txt
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
python scripts/setup.py --full
```

安装选项、`/search` 与 `/health` 接口和返回结构见 [docs/guide/quick-start.md](docs/guide/quick-start.md) 和 [docs/guide/api-reference.md](docs/guide/api-reference.md)。

## 项目结构

```
AGENTS.md               AI 代理入口：仓库地图、检索 SOP、工作 SOP
data/                   已提交的参考数据，直接读取，无需安装
  c3-schemas/           ACE 定义、特效（en-US + zh-CN）
  c3-examples/          示例项目元数据（en-US + zh-CN）
  c3-lang/              CDN 原始语言包（en-US + zh-CN）
  c3-ts-defs/           TypeScript 脚本接口
prompts/                可直接使用的事件表助手 system prompt
src/                    可选搜索服务（包结构见 src/CLAUDE.md）
scripts/                安装、数据刷新、版本检查
tests/                  离线 pytest 套件、金标集、评估脚本
docs/guide/             面向使用者：快速开始、API 参考、数据格式
docs/dev/               面向贡献者：架构、数据管线
docs/decisions/         审计与决策记录
.github/workflows/      数据更新自动化
```

## 致谢

数据来自 [Scirra Ltd](https://www.scirra.com) 的 [Construct 3](https://www.construct.net)，取自[编辑器 CDN](https://editor.construct.net)。Construct 3 是 Scirra Ltd 的商标。

[MIT](LICENSE)
