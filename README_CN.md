# Construct3-RAG

[English](README.md) | **中文**

Construct3-RAG 是给 AI agent 用的 [Construct 3](https://editor.construct.net/) 参考数据。它按编辑器的定义收录所有条件、动作、表达式和滤镜，中英双语，都是 agent 直接读取的 JSON 文件。它还放着示例索引、编辑器的语言包、脚本 API 的 TypeScript 定义和 Scirra 的项目格式指南。管线在每个版本从编辑器 CDN 刷新它们。

用这些数据做游戏的工具，也就是 `construct3-agent-plugin` skill、它的 prompts 和 Claude Code plugin `construct3`，放在 [Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills)。那个仓库用本仓库的 clone 构建它的 plugin。

> [!IMPORTANT]
> 本仓库只存数据，不提供制作工具。要新建或修改 Construct 3 项目，请查看 [Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills) 仓库，按其 README 操作，并使用仓库提供的脚本进行校验，不要只凭本仓库的数据和常识写项目，容易漏掉某些不支持的值，被编辑器拒绝打开项目。
>
> 把那个仓库 clone 到本仓库旁边，像[相关仓库](#相关仓库)那样，它的脚本才能读本 clone 的 `data/`：`git clone https://github.com/XHXIAIEIN/Construct3-Agent-Skills ../Construct3-Agent-Skills`。
>
> 要在数据里查 Construct 3 的资料，看[查找](#查找)。要修改本仓库，读 [`AGENTS.md`](AGENTS.md)。

## 做游戏

安装 Git 和 Python 3.10 以上，然后照原样运行这两条命令，在哪个目录都可以：

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Agent-Skills $HOME/Construct3/Construct3-Agent-Skills
python $HOME/Construct3/Construct3-Agent-Skills/scripts/bootstrap.py --project MyGame
```

它们把那个仓库、[相关仓库](#相关仓库)和 `MyGame` 项目都放进 `$HOME/Construct3`，再把 skill 装进 `MyGame`。Construct3-Agent-Skills 的 README 说明 skill 能做什么、怎么安装它的 Claude Code plugin，以及它的脚本读写和访问的范围。plugin 自带一份本仓库的数据，所以用 plugin 的人不需要 clone 本仓库（Construct3-RAG）。

## 查找

直接读 `data/` 下的文件。下面路径里的 `{locale}` 是 `c3-schemas/_index.json` 的 `languages` 之一，比如 `en-US`：

| 路径 | 内容 |
|---|---|
| `c3-schemas/_index.json` | 版本、语言，以及每个插件、行为和滤镜的文件路径和 ACE 数量。与语言无关 |
| `c3-schemas/{locale}/_index.json` | 该语言的插件名称，用同样的 id 索引 |
| `c3-schemas/{locale}/plugins/{id}.json` | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/plugins/_common.json` | 所有世界对象共有的 ACE：重叠、碰撞、实例变量、层级、UID、Z 顺序。每个插件文件在 `commonAces` 下列出自己拥有的那些 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 行为的 ACE |
| `c3-schemas/{locale}/effects/{id}.json` | 滤镜参数和分类 |
| `c3-schemas/{locale}/_deprecated.json` | 编辑器已弃用的插件、行为、滤镜和 ACE，有同名现行 ACE 的一并给出 |
| `c3-examples/{locale}/{id}.json` | 示例名称、描述、标签、用到的插件、打开链接 |
| `c3-example-usage/{plugins,behaviors}/{id}.json` | 插件或行为的每个 ACE 被哪些官方示例用到：数量，以及最多三处用法（示例文件夹、事件表、事件）。从 `Construct-Example-Projects` 仓库的事件表里统计 |
| `c3-lang/{locale}.json` | CDN 上的编辑器语言包，一行一条 |
| `c3-ts-defs/autocomplete-data.json` | 脚本类及其方法和属性 |
| `c3-ts-defs/**/*.d.ts` | 完整的 TypeScript 接口签名 |
| `c3-guides/constructs-project-format.md` | Scirra 的项目文件夹指南，Markdown 格式（CC BY 4.0）。每个项目的 `llm-context.md` 都链接到这篇指南 |
| `c3-new-project/` | 编辑器 **Project** > **New** 保存的空项目，skill 新建游戏时复制它 |

字段名与 Construct CDN 一致。`id`、`scriptName`、`category` 和参数类型这些结构字段在每种语言里都相同，所以在一种语言里找到的 ACE，在其他语言里也是同一个 `id`。下面是 `en-US/plugins/sprite.json` 里的一个条件：

```json
{
  "id": "is-animation-playing",
  "list-name": "Is playing",
  "display-text": "Is animation {0} playing",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": { "animation": { "type": "animation", "name": "Animation", "desc": "..." } }
}
```

同一个 `id` 在 `zh-CN/plugins/sprite.json` 里是中文的 `list-name`、`display-text` 和参数名：

```json
{
  "id": "is-animation-playing",
  "list-name": "正在播放",
  "display-text": "动画 {0} 正在播放",
  "scriptName": "IsAnimPlaying",
  "category": "animations",
  "params": { "animation": { "type": "animation", "name": "动画", "desc": "..." } }
}
```

[docs/guide/data-format.md](docs/guide/data-format.md) 解释每个字段，并带一个完整例子。[`AGENTS.md`](AGENTS.md) 第 2 节是 agent 查找时遵循的流程，包括已弃用的 ACE 和示例项目。

`System` 和共有 ACE 的文件 `plugins/system.json`、`plugins/_common.json` 太长，多数文件工具一次读不完。这种工具只显示文件的前一部分，后面的 ACE 看起来就像不存在。把 Construct3-Agent-Skills clone 到本仓库旁边。它的查找脚本能整个读完，`--rag .` 让它读本 clone 的数据：

```bash
python ../Construct3-Agent-Skills/plugin/skills/construct3-agent-plugin/scripts/lookup_ace.py --rag . System wait
```

它打印每个匹配项的参数、措辞和要写的 JSON，以及用到它的官方示例。

## 相关仓库

| 仓库 | 内容 | 和本仓库的关系 |
|---|---|---|
| [XHXIAIEIN/Construct3-Agent-Skills](https://github.com/XHXIAIEIN/Construct3-Agent-Skills) | `construct3-agent-plugin` skill、事件表 prompts 和 Claude Code plugin | 为游戏项目读取这些数据的工具；它的 plugin 用本仓库的 clone 构建 |
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册、Addon SDK 指南和 Game Services 文档，Markdown 格式 | `data/c3-schemas/` 给出名称和参数，手册说明它们的作用 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 案例库里的所有示例，以项目文件夹形式保存 | `data/c3-examples/` 是示例的元数据，`data/c3-example-usage/` 记录每个 ACE 被哪些示例用到，项目本身在那个仓库里 |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | 自定义插件、行为、滤镜和主题的模板和文档 | `data/c3-ts-defs/sdk/` 是类型定义，SDK 讲怎么用 |

## 查找服务（可选）

需要通过 HTTP 查询的程序，可以从本机的查找服务拿到同样的数据。这个服务做关键词查找，结果固定，离线运行。它需要 Python 3.11 以上：

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

[docs/guide/quick-start.md](docs/guide/quick-start.md) 给出安装选项。[docs/guide/api-reference.md](docs/guide/api-reference.md) 给出 `/search` 和 `/health` 接口及返回格式。

## 项目结构

```
AGENTS.md               AI agent 入口
.claude/                Claude Code 的 ACE 查找子 agent 和 polish 工作流
data/                   提交在仓库里的参考数据，直接读取
  c3-schemas/           ACE 定义和滤镜，每种语言一个文件夹
  c3-examples/          示例项目元数据
  c3-example-usage/     每个 ACE 被哪些示例用到
  c3-lang/              CDN 语言包
  c3-ts-defs/           TypeScript 脚本接口
  c3-guides/            Scirra 的项目格式指南
  c3-new-project/       编辑器的空项目，新建游戏时复制
src/                    可选的查找服务（见 src/AGENTS.md）
scripts/                查找服务启动、数据更新和维护脚本（见 scripts/AGENTS.md）
tests/                  离线 pytest 测试
docs/guide/             使用文档
docs/dev/               开发文档
docs/decisions/         决策记录
.github/workflows/      每次推送到 main 和每个 pull request 的检查，数据自动更新
```

## 致谢

数据来自 [Scirra Ltd](https://www.scirra.com) 的 [Construct 3](https://www.construct.net)，从[编辑器 CDN](https://editor.construct.net) 获取。Construct 3 是 Scirra Ltd 的商标。

[MIT](LICENSE)
