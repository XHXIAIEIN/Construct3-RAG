# Construct3-RAG

[English](README.md) | **中文**

[Construct 3](https://www.construct.net) 的结构化双语参考数据：插件、行为、ACE、特效、示例项目、脚本接口和原始语言包。`data/` 下的内容都是已提交的 JSON 和 `.d.ts`，脚本或 LLM 可以直接读取。可选服务在数据之上提供关键词查找。

## 从这个链接开始

两条命令照原样运行，在哪个目录都可以：

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
```

它们把这个 clone、它要读的仓库和 `MyGame` 项目放在同一个 `$HOME/Construct3` 里，并把 `construct3-project` skill 连同 `AGENTS.md` 和 `CLAUDE.md` 装进 `MyGame`。已经存在的都原样保留，所以这两条可以重复运行；`--help` 列出参数。`cmd.exe` 里把 `$HOME` 写成 `%USERPROFILE%`。想放在别处，就把两条命令里的 `$HOME/Construct3` 一起换成那个文件夹。

`MyGame` 从 `data/c3-new-project` 复制而来，即编辑器用 **项目** > **新建** 创建、再用 **另存为** > **保存为项目文件夹** 保存的空项目。想改用本机已保存的空项目，在第二条命令后加 `--template <那个文件夹>`。

之后读 `MyGame/AGENTS.md`。

## 相关仓库

另外三个仓库，`bootstrap.py` 会把它们 clone 到本仓库旁边：

| 仓库 | 内容 | 与本仓库的关系 |
|---|---|---|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册、Addon SDK 指南和 Game Services 文档的 Markdown 版 | `data/c3-schemas/` 是名称和参数，这里说明它们做什么。 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 示例浏览器中的全部示例，以文件夹项目形式保存 | `data/c3-examples/` 是元数据，这里是源文件。 |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | 自定义插件、行为、特效和主题的模板与文档 | `data/c3-ts-defs/sdk/` 是类型接口，这里说明怎么用。 |

## 数据文件

无需安装。选择一个语言目录，`en-US` 或 `zh-CN`，直接读取。所有路径基于 `data/`。

| 路径 | 内容 |
|---|---|
| `c3-schemas/_index.json` | 版本、语言列表，以及每个插件、行为、特效的文件路径和 ACE 数量。不含本地化名称 |
| `c3-schemas/{locale}/_index.json` | 该语言下的插件、行为、特效名称，键与根索引相同 |
| `c3-schemas/{locale}/plugins/{id}.json` | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/plugins/_common.json` | 所有世界对象共有的 ACE：重叠、碰撞、实例变量、层级、UID、Z 序。只导出一次，不在各插件文件中重复；各插件文件在 `commonAces` 中列出自己拥有的那些 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 行为 ACE |
| `c3-schemas/{locale}/effects/{id}.json` | 特效参数和分类 |
| `c3-examples/{locale}/{id}.json` | 示例名称、描述、标签、使用的插件、打开链接 |
| `c3-lang/{locale}.json` | CDN 原始语言包，每行一个字符串，用于对比版本和翻译 |
| `c3-ts-defs/autocomplete-data.json` | 脚本类到方法和属性的映射 |
| `c3-ts-defs/**/*.d.ts` | 完整 TypeScript 接口签名 |

字段名与 Construct CDN 一致。`id`、`scriptName`、`category` 和参数类型等结构字段在所有语言中相同，在一种语言里找到的 ACE 可以直接在另一种语言里读取。字段含义、布局和完整示例见 [docs/guide/data-format.md](docs/guide/data-format.md)。

## 读取数据

1. 在 `_index.json` 中找到插件或行为，条目给出 `file` 路径和 ACE 数量。只知道中文名时，先在 `{locale}/_index.json` 中查到 id。
2. 打开 `data/c3-schemas/{locale}/{file}`，用 `id` 定位 ACE；条件和动作也可以用 `list-name`，表达式用 `translated-name`。`display-text` 是事件表中的显示文本，`params` 列出参数。世界对象的 ACE 如果不在自己的文件里，就在 `plugins/_common.json`；Sprite 的完整 ACE 列表是自己的文件加上这一份。
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

先读 [`AGENTS.md`](AGENTS.md)，它给出事实查找流程、事件表设计流程和改代码的规则。要帮用户写事件表，把 [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md)、[`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) 和 [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md) 一起作为 system prompt 加载：前者用 Construct 的方式决定结构（拾取、族、容器、`Else`），中间一份规定输出格式和名称核对，后者是带出处、凭直觉容易写错的运行时事实。[`prompts/event-sheet-style.md`](prompts/event-sheet-style.md) 是官方示例的书写风格（文件夹、事件组及其变量、注释、命名、界面文案），用于把事件写进项目时。只在特定场景才需要的内容放在 `prompts/references/`，由这几份文件按需指引，平时不进上下文。

游戏项目里的 agent 通过 [`construct3-project`](skills/construct3-project/SKILL.md) skill 到达本仓库：一个 [Agent Skills](https://agentskills.io) 格式的文件夹，里面是 ACE 查询、事件表打印、事件表编辑、检查器、编辑器打开验证和生成器模板。顶部的两条命令会安装它；项目里没有它时的规则见 `AGENTS.md` 第 4 节。

## 查找服务（可选）

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

该命令基于已提交的数据启动确定性、离线的查找服务，不需要数据库、模型和网络。

安装选项、`/search` 与 `/health` 接口和返回结构见 [docs/guide/quick-start.md](docs/guide/quick-start.md) 和 [docs/guide/api-reference.md](docs/guide/api-reference.md)。

## 项目结构

```
AGENTS.md               AI 代理入口
data/                   已提交的参考数据，直接读取
  c3-schemas/           ACE 定义、特效（en-US + zh-CN）
  c3-examples/          示例项目元数据
  c3-lang/              CDN 语言包
  c3-ts-defs/           TypeScript 脚本接口
prompts/                LLM system prompt
  references/           按需加载
skills/                 Agent Skills，安装到游戏项目里
  construct3-project/   ACE 查询、事件表打印、事件表编辑、检查器、编辑器打开验证、生成器模板
src/                    可选查找服务（见 src/AGENTS.md）
scripts/                安装、数据刷新、版本检查
tests/                  离线 pytest 套件
docs/guide/             使用者文档
docs/dev/               贡献者文档
docs/decisions/         决策记录
.github/workflows/      数据更新自动化
```

## 致谢

数据来自 [Scirra Ltd](https://www.scirra.com) 的 [Construct 3](https://www.construct.net)，取自[编辑器 CDN](https://editor.construct.net)。Construct 3 是 Scirra Ltd 的商标。

[MIT](LICENSE)
