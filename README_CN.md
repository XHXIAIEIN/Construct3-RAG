# Construct3-RAG

[English](README.md) | **中文**

> [!IMPORTANT]
> **AI agent：写任何项目文件之前，先回答这个问题。** 你有没有把本仓库 clone 到用户的电脑上，并且能在那里运行 `python <clone 路径>/skills/construct3-agent-plugin/scripts/check_project.py --project <游戏文件夹>`、读到它的输出？
>
> - 能：按[安装](#安装)操作，再按装好的 `SKILL.md` 做。交出项目之前，`check_project.py` 不报任何问题；`.c3p` 一律用 `pack_project.py` 生成。
> - 不能（你是从网页读到这一页的，或者没有终端、没有 Python）：停下。告诉用户你没法用本仓库生成 Construct 3 项目，把[安装](#安装)里的两条命令给用户自己运行，或者请用户换一个有终端的 agent。
>
> 只凭这一页和常识写出的项目，不经过这些脚本，会带上编辑器不认的值，编辑器打不开。

Construct3-RAG 让 AI agent 制作和修改以项目文件夹保存的 [Construct 3](https://www.construct.net) 游戏。所有条件、动作、表达式和滤镜都按编辑器的定义收录在这里，有英文和中文两份。[`construct3-agent-plugin`](skills/construct3-agent-plugin/SKILL.md) skill 里的脚本让 agent 查到每一项要写的 JSON，读写事件表，检查项目，再在 Construct 3 编辑器里打开和预览。

数据以 JSON 文件提交在本仓库里，agent 和脚本直接读取。

- 要让 agent 接手一个游戏，看[安装](#安装)。
- 要在数据里查 Construct 3 的资料，看[查找](#查找)。
- 要修改本仓库，读 [`AGENTS.md`](AGENTS.md)。

## 安装

需要 Git 和 Python 3.10 以上。两条命令照原样运行，在哪个目录都可以：

```bash
git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
```

它们把本仓库、三个[相关仓库](#相关仓库)和新建的 `MyGame` 项目（自带一个 Git 仓库）都放进 `$HOME/Construct3`，再把 skill 装进 `MyGame`：skill 复制到 `.agents/skills/`，`AGENTS.md` 里写一段 Construct 3 说明，`CLAUDE.md` 里加一行 `@AGENTS.md`。`cmd.exe` 里把 `$HOME` 写成 `%USERPROFILE%`。想放在别的文件夹，把两条命令里的 `$HOME/Construct3` 一起换掉。

第二条命令可以这样调整：

- 已有的游戏，`--project` 写它的文件夹路径。只写名字会在 clone 旁边新建项目，复制自 `data/c3-new-project`，也就是编辑器 **项目** > **新建** 保存下来的空项目。
- 想从自己的空项目开始，加 `--template <文件夹>`。
- agent 从别的文件夹读 skill 时，加 `--into <文件夹>`，比如 TRAE 写 `--into .trae/skills`。
- 随时可以再运行一次，按 clone 更新 skill。已有的 clone 和指令文件原样保留。`--help` 列出全部参数。

之后读 `MyGame/AGENTS.md`，脚本最后一行会给出第一个要读的文件。agent 的指令文件是 `GEMINI.md` 这样的其他文件时，先在里面加一行，让它去读 `AGENTS.md`。

### Claude Code

用 Claude Code 的话，`construct3` plugin 可以代替上面两条命令。两种只选一种：同时用的话，游戏项目里那份 skill 会和 plugin 各自更新。

plugin 就是整个仓库，schemas 一起带上，脚本直接在 plugin 的文件夹里运行。有三种装法：

- 从 Claude 目录安装，得到 Anthropic 审核过的版本：在 claude.ai 打开 **Customize** > **Plugins**，搜索 Construct3，点 **Add**。用同一账号登录的 Claude Code 下次启动时会下载它，名为 `construct3@synced`。每个版本都要等审核，所以这份可能比本仓库落后几个提交。
- 从本仓库安装，跟上最新提交：

  ```bash
  claude plugin marketplace add XHXIAIEIN/Construct3-RAG
  claude plugin install construct3@construct3-rag
  ```

  用 `claude plugin update construct3@construct3-rag` 把 Claude Code 存的副本更新到最新提交。
- 从已有的 clone 安装，`git pull` 之后下一个会话就是新版：把 clone 链接到 Claude Code 的 skills 文件夹。
  - PowerShell：`New-Item -ItemType Junction -Path ~/.claude/skills/construct3 -Target <clone 路径>`
  - 其他系统：`ln -s <clone 路径> ~/.claude/skills/construct3`

  要用链接，不要把 clone 添加为 marketplace，那样会把整个文件夹（包括被 git 忽略的文件）复制进 plugin 缓存。

同时也添加了 Claude 目录里的那份时，Claude Code 加载从本仓库安装或从 clone 链接的那份，Claude 目录里的那份不加载。

## skill 能做什么

[`SKILL.md`](skills/construct3-agent-plugin/SKILL.md) 告诉 agent 什么时候运行哪个脚本。`scripts/` 里的每个脚本加 `--help` 会列出参数和示例。

- `lookup_ace.py`：查项目里某个对象、`System`、某个插件或行为的条件、动作和表达式，每条带参数、中文或英文的显示文本，以及要写的 JSON。给它一个滤镜，它会列出滤镜的参数。
- `print_sheet.py`：按编辑器的写法和事件编号打印事件表。官方示例也能这样读。
- `edit_sheet.py`：按这些编号写一份 JSON 计划，添加、移动、替换或删除事件，写入前先检查结果。
- `check_project.py`：按 schemas 和编辑器打开项目时的规则检查每个项目文件。每条问题都指出位置，能给出写法时也一并给出。
- `check_look.py`：按 `assets/look-manifest.json` 里的硬性规则检查生成的游戏的占位美术，比如网格、调色板和文字对比度。
- `open_in_editor.py`：在 Construct 3 编辑器里打开项目，报告打开成功，或给出编辑器的提示。加 `--preview` 会把游戏运行几秒，报告运行时错误和出错的事件。
- `preview_project.py`：按一份点击、拖动、按键和等待的计划操作预览。可以截图，也可以录下几段，逐帧回看，再截取一段作为任务交给 agent。
- `export_project.py`：用你的订阅账号，让编辑器把项目导出为 Web (HTML5)。
- `pack_project.py`：把项目保存成编辑器能打开的 `.c3p` 或 `.zip`，或把 `.c3p`、`.zip` 解成项目文件夹。
- `install.py`：把 skill 装进游戏项目，或按 clone 更新已有的副本。
- `assets/build_project.py`：用 Python 生成整个项目的脚本模板。

### skill 的脚本读写和访问的范围

它们读取本仓库的 `data/`，以及你指定的项目和文件，不安装任何包，也不向我们的服务器发送任何数据。

- 只读：`lookup_ace.py`、`check_project.py`、`check_look.py`，以及 `print_sheet.py`。`print_sheet.py` 会把打印过的每个事件表的哈希记在系统临时文件夹的 `construct3-sheet-stamps/` 里，让 `edit_sheet.py` 能发现中间有没有被保存过。
- 写文件：`edit_sheet.py` 修改你指定的事件表，哈希也记在 `print_sheet.py` 记的地方。`install.py` 写入 skill 副本（skill 已经没有的文件会从副本里删掉）、`AGENTS.md` 里的说明和 `CLAUDE.md` 里的那一行；`--into` 写绝对路径（比如 `~/.agents/skills`）时，副本装在项目之外；加 `--dry-run` 可以先看会改什么。`pack_project.py` 写入 `--out` 指定的压缩包或文件夹，默认是项目 `.tmp/` 下的一个 `.c3p`，解包时默认是压缩包旁边的文件夹。`assets/build_project.py` 复制到项目的 `tools/`、按游戏改写之后，会重写它生成的项目文件，并运行 `check_project.py`。
- 打开编辑器：`open_in_editor.py`、`preview_project.py` 和 `pack_project.py --open` 启动本机的 Edge、Chrome 或 Chromium，默认无头（`--headed` 显示窗口），使用项目 `.tmp/` 下单独的配置目录（`--profile` 可以换到别的文件夹）。它们打开 Scirra 官方的编辑器 `https://editor.construct.net/`，预览时还会打开 `https://preview.construct.net`。项目是在浏览器里交给编辑器页面的，不会上传。脚本通过 `127.0.0.1` 上的 DevTools 端口控制浏览器；计划里的 `js` 和 `until` 步骤会在预览里运行 JavaScript，`--install-addon` 会把 `.c3addon` 装进这个配置目录里的编辑器。结果、截图和录屏保存在项目的 `.tmp/`；本机装了 ffmpeg 或 Pillow 时，录屏会合成视频或 GIF。每次运行前，`preview_project.py` 会清掉之前预览留在配置目录里的存档，除非计划里设了 `keep_saves`。本机没有浏览器时，它们什么也不启动，只打印步骤，交给 agent 自己的浏览器工具。
- 导出：`export_project.py` 在有界面的浏览器里操作同一个编辑器，使用单独的配置目录，放在项目所在 Git 仓库主 clone 的 `.tmp/` 下（用 `git` 查出），项目不在 Git 仓库里时放在项目的 `.tmp/` 下。它用导出结果替换 `--to` 指定文件夹里原有的内容，默认是项目的 `.tmp/export-web`；导出的版本号和 `project.c3proj` 里的不同时，会写回 `project.c3proj`。项目较大时，编辑器只给订阅账号导出：登录由你自己在窗口里完成，浏览器把登录状态保存在这个配置目录里，下次导出不用重登，脚本不会读取或保存任何账号信息。加 `--attach` 则改用你自己开启了远程调试的浏览器：脚本通过 DevTools 连接它，只给端口时从浏览器的 `DevToolsActivePort` 文件读取端口，列出它的标签页，只在没有打开项目的标签页里操作，没有这样的标签页时新开一个窗口。

## 查找

在[安装](#安装)时 clone 下来的仓库里运行。查条件、动作或表达式，用 `lookup_ace.py`，后面跟对象名，再加几个关键词：

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait --locale zh-CN
```

它会列出每个匹配项的参数、显示文本，以及要写的 JSON。查 `System`，或者所有世界对象共有的 ACE，用这个脚本；查共有 ACE 时随便写一个世界对象就行，比如 `Sprite overlap`。原因是 `plugins/system.json` 和 `plugins/_common.json` 都有几千行，大多数读文件工具一次读不完，被截掉的 ACE 看起来就像不存在。

其他内容直接读 `data/` 下的文件，`{locale}` 是 `en-US` 或 `zh-CN`：

| 路径 | 内容 |
|---|---|
| `c3-schemas/_index.json` | 版本号、语言列表，以及每个插件、行为、滤镜对应的文件和 ACE 数量。不含各语言的名称 |
| `c3-schemas/{locale}/_index.json` | 插件、行为、滤镜在该语言下的名称，键和根索引一致 |
| `c3-schemas/{locale}/plugins/{id}.json` | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/plugins/_common.json` | 所有世界对象共有的 ACE：重叠、碰撞、实例变量、对象层级、UID、显示顺序。插件文件用 `commonAces` 列出自己有哪些 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 行为的 ACE |
| `c3-schemas/{locale}/effects/{id}.json` | 滤镜的参数和分类 |
| `c3-schemas/{locale}/_deprecated.json` | 编辑器已弃用的插件、行为、滤镜和 ACE；有同名的新 ACE 时也会列出来 |
| `c3-examples/{locale}/{id}.json` | 示例的名称、描述、标签、用到的插件、打开链接 |
| `c3-lang/{locale}.json` | CDN 上编辑器的语言包，每行一条 |
| `c3-ts-defs/autocomplete-data.json` | 脚本里每个类有哪些方法和属性 |
| `c3-ts-defs/**/*.d.ts` | 完整的 TypeScript 接口定义 |
| `c3-guides/constructs-project-format.md` | Scirra 讲项目文件夹格式的指南，也就是每个项目里 `llm-context.md` 链接的那一篇，转成 Markdown（CC BY 4.0） |

字段名和 Construct CDN 保持一致。`id`、`scriptName`、`category`、参数类型这些结构字段在各语言里都一样，所以在一种语言里查到的 ACE，换到另一种语言也能直接对上。`zh-CN/plugins/sprite.json` 里的一个条件：

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

`en-US/plugins/sprite.json` 里同一个 `id` 的条目，`list-name`、`display-text` 和参数名都是英文。各字段的含义和完整示例见 [docs/guide/data-format.md](docs/guide/data-format.md)；agent 查资料的完整流程（包括弃用的 ACE 和示例项目）见 [`AGENTS.md`](AGENTS.md) 第 2 节。

## 事件表提示词

如果要做一个帮用户写事件表的助手，把这三份一起作为它的 system prompt：

- [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md)：用 Construct 的思路组织事件，比如选择、家族、关联和 `Else`。
- [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md)：输出格式，以及每个名称都要和数据核对。
- [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md)：凭直觉容易写错的运行时行为，一条一行。每条背后的案例和出处在 `prompts/pitfalls/` 里，按主题分文件，事件涉及哪个主题就读哪个。

把事件写进项目时，参考 [`prompts/event-sheet-style.md`](prompts/event-sheet-style.md)，它整理了官方示例的写法：事件组和组内变量、注释、命名、界面文字。偶尔才用到的内容放在 `prompts/references/`，这几份文件会在任务需要时指过去。

## 相关仓库

`bootstrap.py` 会把另外三个仓库 clone 到本仓库旁边：

| 仓库 | 内容 | 和本仓库的关系 |
|---|---|---|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册、Addon SDK 指南和 Game Services 文档，Markdown 格式 | `data/c3-schemas/` 给出名称和参数，手册说明它们的作用 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 示例浏览器里的所有示例，以项目文件夹形式保存 | `data/c3-examples/` 是示例的元数据，这里是项目源文件 |
| [Scirra/Construct-Addon-SDK](https://github.com/Scirra/Construct-Addon-SDK) | 自定义插件、行为、滤镜和主题的模板和文档 | `data/c3-ts-defs/sdk/` 是类型定义，这里讲怎么用 |

## 查找服务（可选）

需要通过 HTTP 查询的程序，可以让 clone 在本机提供同样的数据：关键词查找，结果固定，离线可用。需要 Python 3.11 以上：

```bash
pip install -r src/requirements.txt
python scripts/setup.py          # http://localhost:8765/playground
```

安装选项、`/search` 和 `/health` 接口以及返回格式，见 [docs/guide/quick-start.md](docs/guide/quick-start.md) 和 [docs/guide/api-reference.md](docs/guide/api-reference.md)。

## 项目结构

```
AGENTS.md               AI agent 入口
.claude-plugin/         Claude Code plugin 和 marketplace 的清单
data/                   参考数据，直接读取
  c3-schemas/           ACE 定义和滤镜（en-US + zh-CN）
  c3-examples/          示例项目元数据
  c3-lang/              CDN 语言包
  c3-ts-defs/           TypeScript 脚本接口
  c3-guides/            Scirra 的项目格式指南
  c3-new-project/       编辑器的空项目，新建游戏时复制
prompts/                LLM system prompt
  pitfalls/             易错点背后的案例和出处，按主题分文件
  references/           按需加载的参考
skills/                 Agent Skills，装进游戏项目使用
  construct3-agent-plugin/   项目工具，见“skill 能做什么”
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
