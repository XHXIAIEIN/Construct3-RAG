# Construct3-RAG

[English](README.md) | **中文**

帮 AI agent 做 [Construct 3](https://www.construct.net) 游戏：查到准确的条件、动作和表达式，读写事件表，检查项目，再放进编辑器里确认能打开。这些工具打包成 [`construct3-agent-plugin`](skills/construct3-agent-plugin/SKILL.md) skill，装进游戏项目里使用。

如何开始：

- 要让 agent 接手一个游戏项目，看[安装](#安装)。
- 要在本仓库里查 Construct 3 的资料，看[查找](#查找)。
- 要修改本仓库，读 [`AGENTS.md`](AGENTS.md)。

## 安装

需要 Git 和 Python 3.10 以上。两条命令照原样运行，在哪个目录都可以：

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
```

它们把本仓库、三个[相关仓库](#相关仓库)和 `MyGame` 项目都放进 `$HOME/Construct3`，再把 skill 装进 `MyGame`：skill 复制到 `.agents/skills/`，`AGENTS.md` 里写一段 Construct 3 说明，`CLAUDE.md` 里加一行 `@AGENTS.md`。`cmd.exe` 里把 `$HOME` 写成 `%USERPROFILE%`；想放在别处，把两条命令里的 `$HOME/Construct3` 一起换掉。

已有的游戏项目，`--project` 写项目文件夹的路径；只写名字会在 `$HOME/Construct3` 下新建项目。新项目复制自 `data/c3-new-project`，也就是编辑器 **项目** > **新建** 后 **另存为** > **保存为项目文件夹** 得到的空项目，加 `--template <文件夹>` 可以换成你自己保存的空项目。agent 从别的目录读 skill 时加 `--into <目录>`，比如 TRAE 写 `--into .trae/skills`。再次运行时，已有的 clone 和指令文件原样保留，skill 按 clone 更新；`--help` 列出全部参数。

之后读 `MyGame/AGENTS.md`，脚本最后一行会给出第一个要读的文件。agent 的项目指令文件是 `GEMINI.md` 这类时，先在里面加一行，让它去读 `AGENTS.md`。

### Claude Code plugin

用 Claude Code 的话，也可以改装 plugin，代替上面两条命令。两种只选一种，同时装会有两份 skill 各自更新。

```bash
claude plugin marketplace add XHXIAIEIN/Construct3-RAG
claude plugin install construct3@construct3-rag
```

plugin 装的是整个仓库，schemas 一起带上，skill 的脚本直接在 plugin 的文件夹里运行。Claude Code 存的是一份副本，用 `claude plugin update construct3@construct3-rag` 更新到最新提交。

如果本地已经 clone 了本仓库，可以不用上面两条命令，而是把 clone 链接到 Claude Code 的 skills 目录。这样 plugin 直接读 clone，`git pull` 之后，下一个会话就是新版：

- PowerShell：`New-Item -ItemType Junction -Path ~/.claude/skills/construct3 -Target <clone 路径>`
- 其他系统：`ln -s <clone 路径> ~/.claude/skills/construct3`

把本地 clone 添加为 marketplace 的话，整个文件夹（包括被 git 忽略的文件）都会复制进 plugin 缓存。

### skill 的脚本会做什么、访问哪里

脚本只读本仓库的 `data/` 和游戏项目，不安装任何包，也不向我们的服务器发送任何数据。

- `lookup_ace.py`、`print_sheet.py`、`check_project.py`、`check_look.py`：只读文件。
- `edit_sheet.py`：修改你指定的游戏项目里的事件表。
- `install.py`：把 skill 复制到游戏项目，并在 `AGENTS.md` 和 `CLAUDE.md` 里加一段说明；加 `--dry-run` 可以先看会改什么。
- `open_in_editor.py`：以无头模式启动本机的 Edge、Chrome 或 Chromium，使用游戏项目 `.tmp/` 下单独的配置目录，打开 Scirra 官方的编辑器 `https://editor.construct.net/`。项目是在浏览器里交给编辑器页面的，不会上传。脚本通过 `127.0.0.1` 上的 DevTools 端口控制浏览器。
- `preview_project.py`：用同样的方式打开项目并预览，然后按你或 agent 写好的计划，在预览窗口里点击、拖动、按键。截图和录屏保存在游戏项目的 `.tmp/preview/`。本机装了 ffmpeg 或 Pillow 时，录屏会合成视频，并生成一个回看页面，可以逐帧查看，也可以截取一段作为任务交给 agent；同目录的 `index.html` 列出所有录像。每次运行前，它会清掉之前预览留在浏览器里的存档。
- `export_project.py`：在有界面的浏览器里操作编辑器，把项目导出为 Web (HTML5)，再把 zip 解压到你指定的文件夹。项目较大时，编辑器需要订阅账号才能导出；登录由你自己在窗口里完成，脚本不会读取或保存任何账号信息。加 `--attach` 会连接你自己开启了远程调试的浏览器，并且只在没有打开项目的标签页里操作。

## 查找

在[安装](#安装)时 clone 下来的仓库里运行，需要 Python 3.10 以上。查条件、动作或表达式，用 `lookup_ace.py`，后面跟插件、行为或滤镜的名字，再加几个关键词。它会列出每个匹配项的参数、对应语言的显示文本，以及写进项目要用的 JSON：

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait --locale zh-CN
```

查 `System` 的 ACE，或者所有世界对象共有的 ACE，一定要用这个脚本。查共有 ACE 时随便写一个世界对象就行，比如 `Sprite overlap`。原因是 `plugins/system.json` 和 `plugins/_common.json` 都有几千行，大多数读文件工具一次读不完，被截掉的 ACE 看起来就像不存在。

其他内容直接读文件。下表路径都在 `data/` 下，语言目录有 `en-US` 和 `zh-CN`。

| 路径 | 内容 |
|---|---|
| `c3-schemas/_index.json` | 版本号、语言列表，以及每个插件、行为、滤镜对应的文件和 ACE 数量。不含各语言的名称 |
| `c3-schemas/{locale}/_index.json` | 插件、行为、滤镜在该语言下的名称，键和根索引一致 |
| `c3-schemas/{locale}/plugins/{id}.json` | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/plugins/_common.json` | 所有世界对象共有的 ACE：重叠、碰撞、实例变量、对象层级、UID、显示顺序。这些只存一份，不在每个插件文件里重复；插件文件用 `commonAces` 列出自己有哪些 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 行为的 ACE |
| `c3-schemas/{locale}/effects/{id}.json` | 滤镜的参数和分类 |
| `c3-schemas/{locale}/_deprecated.json` | 编辑器已弃用的插件、行为、滤镜和 ACE，不管 schema 里还有没有；有同名的新 ACE 时也会列出来 |
| `c3-examples/{locale}/{id}.json` | 示例的名称、描述、标签、用到的插件、打开链接 |
| `c3-lang/{locale}.json` | CDN 上的原始语言包，每行一条，用来对比版本和翻译 |
| `c3-ts-defs/autocomplete-data.json` | 脚本里每个类有哪些方法和属性 |
| `c3-ts-defs/**/*.d.ts` | 完整的 TypeScript 接口定义 |
| `c3-guides/constructs-project-format.md` | Scirra 讲项目文件夹格式的指南，也就是每个项目里 `llm-context.md` 链接的那一篇，转成 Markdown（CC BY 4.0）：`project.c3proj` 列出什么、图像文件怎么命名、各类文件用什么格式 |

字段名和 Construct CDN 保持一致。`id`、`scriptName`、`category`、参数类型这些结构字段在各语言里都一样，所以在一种语言里查到的 ACE，换到另一种语言也能直接对上。

在文件里查 ACE 的步骤：

1. 在 `c3-schemas/_index.json` 里找到插件、行为或滤镜，条目里的 `file` 就是文件路径。只知道中文名时，先到 `{locale}/_index.json` 里查出 id。
2. 打开 `c3-schemas/{locale}/{file}`，按 `id` 找 ACE；条件和动作也可以按 `list-name` 找，表达式按 `translated-name` 找。`display-text` 是事件表里显示的文字，`params` 是参数。世界对象的 ACE 在自己的文件里找不到时，去 `plugins/_common.json` 里找。
3. 查脚本接口时，先在 `autocomplete-data.json` 的 `properties` 里找到类名，比如 `ISpriteInstance`，再到同名插件或行为的文件夹里打开对应的 `.d.ts`，比如 `c3-ts-defs/plugins/general/sprite/c3runtime/ISpriteInstance.d.ts`。

`zh-CN/plugins/sprite.json` 里的一个条件：

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

`en-US/plugins/sprite.json` 里同一个 `id` 的条目，`list-name`、`display-text` 和参数名都是英文。各字段的含义和完整示例见 [docs/guide/data-format.md](docs/guide/data-format.md)。agent 查资料的完整流程（包括弃用的 ACE 和示例项目）见 [`AGENTS.md`](AGENTS.md) 第 2 节。

## 事件表提示词

如果要做一个帮用户写事件表的助手，把 [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md)、[`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md) 和 [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md) 一起作为 system prompt。第一份讲怎么用 Construct 的思路组织事件（选择、家族、关联、`Else`），第二份规定输出格式和名称核对，第三份列出凭直觉容易写错的运行时行为，一条一行。每条背后的案例和出处在 `prompts/pitfalls/` 里，按主题分文件，写到相关主题时再去读。[`prompts/event-sheet-style.md`](prompts/event-sheet-style.md) 整理了官方示例的写法（事件组和组内变量、注释、命名、界面文字），把事件写进项目时参考。偶尔才用到的内容放在 `prompts/references/`，这几份文件会在需要时指过去，平时不占上下文。

## 相关仓库

`bootstrap.py` 会把另外三个仓库 clone 到本仓库旁边：

| 仓库 | 内容 | 和本仓库的关系 |
|---|---|---|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册、Addon SDK 指南和 Game Services 文档，Markdown 格式 | `data/c3-schemas/` 给出名称和参数，手册说明它们的作用 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 示例浏览器里的所有示例，以项目文件夹形式保存 | `data/c3-examples/` 是示例的元数据，这里是项目源文件 |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | 自定义插件、行为、滤镜和主题的模板和文档 | `data/c3-ts-defs/sdk/` 是类型定义，这里讲怎么用 |

## 查找服务（可选）

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

这会在本地启动一个关键词查找服务，数据来自仓库里的文件，结果固定、离线可用，适合需要通过 HTTP 查询的程序。

安装选项、`/search` 和 `/health` 接口以及返回格式，见 [docs/guide/quick-start.md](docs/guide/quick-start.md) 和 [docs/guide/api-reference.md](docs/guide/api-reference.md)。

## 项目结构

```
AGENTS.md               AI agent 入口
data/                   参考数据，直接读取
  c3-schemas/           ACE 定义和滤镜（en-US + zh-CN）
  c3-examples/          示例项目元数据
  c3-lang/              CDN 语言包
  c3-ts-defs/           TypeScript 脚本接口
  c3-guides/            Scirra 的项目格式指南
prompts/                LLM system prompt
  references/           按需加载的参考
skills/                 Agent Skills，装进游戏项目使用
  construct3-agent-plugin/   ACE 查询、事件表打印和编辑、检查、编辑器打开验证、预览试玩、项目打包、生成器模板
src/                    可选的查找服务（见 src/AGENTS.md）
scripts/                安装、数据更新、版本检查
tests/                  离线 pytest 测试
docs/guide/             使用文档
docs/dev/               开发文档
docs/decisions/         决策记录
.github/workflows/      数据自动更新
```

## 致谢

数据来自 [Scirra Ltd](https://www.scirra.com) 的 [Construct 3](https://www.construct.net)，从[编辑器 CDN](https://editor.construct.net) 获取。Construct 3 是 Scirra Ltd 的商标。

[MIT](LICENSE)
