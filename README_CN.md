# Construct3-RAG

[English](README.md) | **中文**

Construct3-RAG 让 AI agent 制作和修改以项目文件夹保存的 [Construct 3](https://www.construct.net) 游戏。它按编辑器的定义收录了所有条件、动作、表达式和滤镜，都是 agent 和脚本直接读取的 JSON 文件。脚本随 [`construct3-agent-plugin`](skills/construct3-agent-plugin/SKILL.md) skill 提供。agent 用它们查出要写的 JSON，读写事件表。agent 还用它们检查项目，再在 Construct 3 编辑器里打开和预览。

> [!IMPORTANT]
> **AI agent：写任何项目文件之前，先回答这个问题。** 本仓库有没有 clone 到用户的电脑上？你能不能在那里运行 `python <clone 路径>/skills/construct3-agent-plugin/scripts/check_project.py --project <游戏文件夹>`，并读到它的输出？
>
> - 如果能，按[安装](#安装)操作，再按装好的 `SKILL.md` 做。交出项目之前，确认 `check_project.py` 不报任何问题。`.c3p` 一律用 `pack_project.py` 生成。
> - 如果不能，停下。你从网页读到这一页，或者没有终端、没有 Python，都属于这种情况。告诉用户你没法用本仓库生成 Construct 3 项目。然后把[安装](#安装)里的两条命令交给用户运行，或者建议用户换一个有终端的 agent。
>
> 只凭这一页和常识、不经过这些脚本写出的项目，会带上编辑器不认的值，编辑器因此打不开它。

- 要让 agent 接手一个游戏，看[安装](#安装)。
- 要在数据里查 Construct 3 的资料，看[查找](#查找)。
- 要修改本仓库，读 [`AGENTS.md`](AGENTS.md)。

## 安装

1. 安装 Git 和 Python 3.10 以上。
2. 照原样运行这两条命令，在哪个目录都可以：

   ```bash
   git clone https://github.com/XHXIAIEIN/Construct3-RAG $HOME/Construct3/Construct3-RAG
   python $HOME/Construct3/Construct3-RAG/scripts/bootstrap.py --project MyGame
   ```

3. 读 `MyGame/AGENTS.md`，再读装好的 `SKILL.md`。命令输出的最后一行会给出 `SKILL.md` 的路径。

这两条命令把本仓库、[相关仓库](#相关仓库)和 `MyGame` 项目都放进 `$HOME/Construct3`。`MyGame` 自带一个 Git 仓库。然后 `bootstrap.py` 把 skill 装进 `MyGame`。它把 skill 复制到 `.agents/skills/`，在 `AGENTS.md` 里加一段 Construct 3 说明。它还在 `CLAUDE.md` 里加一行 `@AGENTS.md`。

在 `cmd.exe` 里，把 `$HOME` 写成 `%USERPROFILE%`。想放在别的文件夹，就把两条命令里的 `$HOME/Construct3` 都换成那个文件夹。

运行 `bootstrap.py` 时可附加这些参数：

- 要装进已有的游戏，`--project` 后面写游戏文件夹的路径。如果只写名字，命令会在 clone 旁边新建一个同名的空项目。
- 想从自己的空项目开始，加 `--template <文件夹>`。
- 如果 agent 从别的文件夹读 skill，加 `--into <文件夹>`，比如 TRAE 写 `--into .trae/skills`。

要更新时，先在 clone 里运行 `git pull`，再运行一次 `bootstrap.py`，按 clone 更新项目里的 skill。已有的 clone 和指令文件保持原样。clone 落后于上游仓库时，`check_project.py` 会提示，并给出命令。给 `bootstrap.py` 加 `--help` 可以列出全部参数。

如果 agent 的指令文件是 `GEMINI.md` 这样的其他文件，在那个文件里加一行。这一行让 agent 去读 `AGENTS.md`。

### Claude Code

在 Claude Code 里，`construct3` plugin 可以代替上面两条命令。两种只选一种，因为同时用的话，游戏项目里那份 skill 会和 plugin 各自更新。

plugin 就是整个仓库，所以 schemas 一起带上。脚本直接在 plugin 的文件夹里运行。plugin 有三种装法：

- 从 Claude 目录安装，得到 Anthropic 审核过的版本。在 claude.ai 打开 **Customize** > **Plugins**。搜索 Construct3，点 **Add**。如果 Claude Code 用同一账号登录，它下次启动时会下载这个 plugin，名为 `construct3@synced`。每个版本都要等审核，所以这份可能比本仓库落后几个提交。
- 从本仓库安装，跟上最新提交：

  ```bash
  claude plugin marketplace add XHXIAIEIN/Construct3-RAG
  claude plugin install construct3@construct3-rag
  ```

  要把 Claude Code 存的副本更新到最新提交，运行 `claude plugin update construct3@construct3-rag`。
- 从已有的 clone 安装，让下一个会话用上 `git pull` 拉下来的文件：把 clone 链接到 Claude Code 的 skills 文件夹。
  - PowerShell：`New-Item -ItemType Junction -Path ~/.claude/skills/construct3 -Target <clone 路径>`
  - 其他 shell：`ln -s <clone 路径> ~/.claude/skills/construct3`

  要用链接，不要添加指向 clone 的 marketplace。marketplace 会把整个 clone（包括被 Git 忽略的文件）复制进 plugin 缓存。

如果同时也添加了 Claude 目录里的那份，Claude Code 加载从本仓库安装或从 clone 链接的那份。Claude 目录里的那份会被忽略。

## skill 能做什么

[`SKILL.md`](skills/construct3-agent-plugin/SKILL.md) 告诉 agent 什么时候运行哪个脚本。`scripts/` 里的每个脚本加 `--help` 会列出参数和示例。

- `lookup_ace.py` 查项目里某个对象、`System`、某个插件或行为的条件、动作和表达式。每条都带参数、中文或英文的显示文本，以及要写的 JSON。给它一个滤镜，它会列出滤镜的参数。
- `print_sheet.py` 按编辑器的写法和事件编号打印事件表。官方示例也能这样读。
- `edit_sheet.py` 按一份用这些编号写的 JSON 计划，添加、移动、替换或删除事件。写入之前，它先检查结果。
- `check_project.py` 按 schemas 和编辑器打开项目时的规则，检查每个项目文件。每条问题都指出位置，能给出写法时也一并给出。
- `review_design.py` 读取事件表，报告设计上难读或容易出错的地方，比如条件太多的事件、同一个事实存在两处、临时用的全局变量。每条问题都指出事件，并给出应该换成的写法。然后它给 agent 一组固定的问题，让它对照 `print_sheet.py` 的输出回答。
- `check_look.py` 按 `assets/look-manifest.json` 里的硬性规则，检查生成的游戏的占位美术，比如网格、调色板和文字对比度。
- `prepare_art.py` 把 agent 的生图工具画的图接进游戏。它为生成器要的每张图打印一条提示词。然后它把生图工具画好的每张图从背景里抠出来，缩放进对应占位图形的框里。它需要 Pillow。
- `open_in_editor.py` 在 Construct 3 编辑器里打开项目，报告打开成功，或者给出编辑器的提示。加 `--preview` 时，它把游戏运行几秒，报告运行时错误和出错的事件。
- `preview_project.py` 按一份点击、拖动、按键和等待的计划操作预览。它会截图，也会录下运行的片段。录像可以逐帧回看，其中一段可以作为任务交给 agent。
- `review_look.py` 预览项目，逐个进入每个布局并截图。它报告运行时能看出的问题，比如文字被文本框截断、多个实例叠在同一位置。然后它给 agent 一组固定的问题，让它看着截图回答。
- `export_project.py` 用你的订阅账号，让编辑器把项目导出为 Web (HTML5)。
- `pack_project.py` 把项目保存成编辑器能打开的 `.c3p` 或 `.zip`。它也能把 `.c3p` 或 `.zip` 解成项目文件夹。
- `install.py` 把 skill 装进游戏项目，或者按 clone 更新已有的副本。
- `assets/build_project.py` 是一个模板，用来写生成整个项目的 Python 脚本。

### skill 的脚本读写和访问的范围

skill 的脚本读取本仓库的 `data/`，以及你指定的项目和文件。除了需要 Pillow 的 `prepare_art.py`，它们只用 Python 标准库。它们只在两处联网：`check_project.py` 从 clone 的上游仓库 fetch，打开编辑器的脚本在你电脑上的浏览器里打开 Construct 3 编辑器和它的预览。

- **只读**：`lookup_ace.py`、`check_project.py`、`review_design.py`、`check_look.py` 和 `print_sheet.py`。`print_sheet.py` 把打印过的每个事件表的哈希记在系统临时文件夹的 `construct3-sheet-stamps/` 里。`edit_sheet.py` 靠这个哈希发现打印之后、修改之前有没有保存过。`check_project.py` 最多每六小时在 clone 里运行一次 `git fetch`，用来提示 clone 落后于上游仓库。设置了 `CONSTRUCT3_RAG_OFFLINE` 时，它不 fetch。
- **写文件**：
  - `edit_sheet.py` 写入你指定的事件表，它们的哈希也记在 `print_sheet.py` 记的地方。
  - `install.py` 写入 skill 副本、`AGENTS.md` 里的说明和 `CLAUDE.md` 里的那一行。clone 里的 skill 没有的文件，它会从副本里删掉。`--into` 写绝对路径（比如 `~/.agents/skills`）时，副本装在项目之外。加 `--dry-run` 可以先看会改什么。
  - `prepare_art.py` 把处理好的图写进项目的 `art/`。它读取 `art/raw/` 里的原图，不改动它们。
  - `pack_project.py` 写入 `--out` 指定的压缩包或文件夹。默认写到项目 `.build/` 下的一个 `.c3p`，这个文件夹专放构建产物。解包时，默认写到压缩包旁边的文件夹。
  - agent 把 `assets/build_project.py` 复制到项目的 `tools/`，按游戏改写。这份副本运行时，会重写它生成的项目文件，然后运行 `check_project.py`。
- **打开编辑器**：`open_in_editor.py`、`preview_project.py`、`review_look.py` 和 `pack_project.py --open` 启动本机的 Edge、Chrome 或 Chromium。
  - 浏览器默认无头运行，加 `--headed` 才显示窗口。它使用项目 `.tmp/` 下单独的配置目录，`--profile` 可以换到别的文件夹。
  - 浏览器打开 Scirra 提供的编辑器 `https://editor.construct.net/`，预览时还会打开 `https://preview.construct.net`。脚本在浏览器里把项目交给编辑器页面，所以项目文件留在你的电脑上。
  - 脚本通过 `127.0.0.1` 上的 DevTools 端口控制浏览器。计划里的 `js` 和 `until` 步骤会在预览里运行 JavaScript。`--install-addon` 会把 `.c3addon` 装进这个配置目录里的编辑器。
  - 结果、截图和录像保存在项目的 `.tmp/`。如果装了 ffmpeg，录像合成视频；否则如果装了 Pillow，录像合成 GIF。
  - 每次运行前，`preview_project.py` 会清掉之前预览留在配置目录里的存档，除非计划里设了 `keep_saves`。
  - 如果本机没有这几种浏览器，脚本什么也不启动，而是打印步骤，交给 agent 自己的浏览器工具。
- **导出**：`export_project.py` 在有界面的浏览器里操作同一个编辑器。
  - 浏览器的配置目录放在项目所在 Git 仓库的主 clone 的 `.tmp/` 下，脚本用 `git` 查出这个位置。如果项目不在 Git 仓库里，配置目录放在项目的 `.tmp/` 下。
  - 脚本用导出结果替换 `--to` 指定文件夹里原有的内容。默认文件夹是项目的 `.build/web`。如果导出的版本号和 `project.c3proj` 里的不同，脚本会把导出的版本号写回 `project.c3proj`。
  - 项目较大时，编辑器只给订阅账号导出。登录由你自己在那个窗口里完成，浏览器把登录状态保存在这个配置目录里，下次导出直接用。脚本不读取、也不保存你的账号凭据。
  - 加 `--attach` 时，脚本改用你自己开启了远程调试的浏览器，通过 DevTools 连接它。如果只给端口，脚本会找写有这个端口的浏览器 `DevToolsActivePort` 文件。脚本列出浏览器的标签页，只在没有打开项目的标签页里操作。如果没有这样的标签页，脚本会新开一个窗口。

## 查找

在[安装](#安装)时 clone 下来的仓库里运行查找。查条件、动作或表达式（统称 ACE），用 `lookup_ace.py`，后面跟对象名和几个关键词：

```bash
python skills/construct3-agent-plugin/scripts/lookup_ace.py System wait --locale zh-CN
```

它列出每个匹配项的参数、显示文本，以及要写的 JSON。查 `System` 和所有世界对象共有的 ACE 时，用这个脚本。查共有 ACE 时随便写一个世界对象就行，比如 `Sprite overlap`。这些 ACE 所在的 `plugins/system.json` 和 `plugins/_common.json` 太长，大多数读文件工具一次读不完。这类工具只显示文件的前一部分，所以后面的 ACE 看起来就像不存在。

其他内容直接读 `data/` 下的文件。下表路径里的 `{locale}` 是 `en-US` 或 `zh-CN`：

| 路径 | 内容 |
|---|---|
| `c3-schemas/_index.json` | 版本号、语言列表，以及每个插件、行为、滤镜对应的文件和 ACE 数量。不含各语言的名称 |
| `c3-schemas/{locale}/_index.json` | 插件、行为、滤镜在该语言下的名称，键和根索引一致 |
| `c3-schemas/{locale}/plugins/{id}.json` | 条件、动作、表达式、属性 |
| `c3-schemas/{locale}/plugins/_common.json` | 所有世界对象共有的 ACE：重叠、碰撞、实例变量、对象层级、UID、显示顺序。插件文件用 `commonAces` 列出自己有哪些 |
| `c3-schemas/{locale}/behaviors/{id}.json` | 行为的 ACE |
| `c3-schemas/{locale}/effects/{id}.json` | 滤镜的参数和分类 |
| `c3-schemas/{locale}/_deprecated.json` | 编辑器已弃用的插件、行为、滤镜和 ACE；有同名的现行 ACE 时也一并列出 |
| `c3-examples/{locale}/{id}.json` | 示例的名称、描述、标签、用到的插件、打开链接 |
| `c3-lang/{locale}.json` | CDN 上编辑器的语言包，每行一条 |
| `c3-ts-defs/autocomplete-data.json` | 脚本里每个类的方法和属性 |
| `c3-ts-defs/**/*.d.ts` | 完整的 TypeScript 接口定义 |
| `c3-guides/constructs-project-format.md` | Scirra 讲项目文件夹格式的指南，转成 Markdown（CC BY 4.0）。每个项目的 `llm-context.md` 都链接这篇指南 |

字段名和 Construct CDN 保持一致。`id`、`scriptName`、`category`、参数类型这些结构字段在各语言里都一样。所以在一种语言里查到的 ACE，在其他语言里也是同一个 `id`。下面是 `zh-CN/plugins/sprite.json` 里的一个条件：

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

`en-US/plugins/sprite.json` 里同一个 `id` 的条目，`list-name`、`display-text` 和参数名都是英文。[docs/guide/data-format.md](docs/guide/data-format.md) 解释每个字段，并附有完整示例。[`AGENTS.md`](AGENTS.md) 第 2 节是 agent 查资料的流程，包括弃用的 ACE 和示例项目。

## 事件表提示词

如果要做一个帮用户写事件表的助手，把这三份文件一起作为它的 system prompt：

- [`prompts/event-sheet-thinking.md`](prompts/event-sheet-thinking.md)：怎样用 Construct 的思路组织事件，比如选择、家族、关联和 `Else`。
- [`prompts/event-sheet-assistant.md`](prompts/event-sheet-assistant.md)：输出格式，以及每个名称都要和数据核对。
- [`prompts/event-sheet-pitfalls.md`](prompts/event-sheet-pitfalls.md)：凭直觉容易写错的运行时行为，一条一行。`prompts/pitfalls/` 里是每条背后的案例和出处，按主题分文件。事件涉及哪个主题，就读那个主题的文件。

把事件写进项目时，参考 [`prompts/event-sheet-style.md`](prompts/event-sheet-style.md)。它整理了官方示例写事件表的方式：事件组和组内变量、注释、命名、界面文字。只有部分任务用到的材料放在 `prompts/references/`。任务需要时，上面这几份文件会指过去。

## 相关仓库

`bootstrap.py` 会把这几个仓库 clone 到本仓库旁边：

| 仓库 | 内容 | 和本仓库的关系 |
|---|---|---|
| [XHXIAIEIN/Construct3-Manual](https://github.com/XHXIAIEIN/Construct3-Manual) | 官方手册、Addon SDK 指南和 Game Services 文档，Markdown 格式 | `data/c3-schemas/` 给出名称和参数，手册说明它们的作用 |
| [Scirra/Construct-Example-Projects](https://github.com/Scirra/Construct-Example-Projects) | Construct 示例浏览器里的所有示例，以项目文件夹形式保存 | `data/c3-examples/` 是示例的元数据，项目本身在那个仓库里 |
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
.claude-plugin/         Claude Code plugin 和 marketplace 的清单
data/                   提交在仓库里的参考数据，直接读取
  c3-schemas/           ACE 定义和滤镜，每种语言一个文件夹
  c3-examples/          示例项目元数据
  c3-lang/              CDN 语言包
  c3-ts-defs/           TypeScript 脚本接口
  c3-guides/            Scirra 的项目格式指南
  c3-new-project/       编辑器的空项目，新建游戏时复制
prompts/                LLM system prompt
  pitfalls/             易错点背后的案例和出处，按主题分文件
  references/           部分任务才加载的材料
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
