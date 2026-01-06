# Construct-3 Copilot

**中文** | [English](README_EN.md)

用自然语言生成 Construct 3 事件表 JSON，直接粘贴到编辑器。

## 快速开始

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
cd Construct3-Copilot
claude
```

> 需要安装 [Claude Code CLI](https://claude.ai/download)

## 示例

```
> 创建一个打砖块游戏，球拍用鼠标控制

AI 会生成两个 JSON 文件：
- layout.json  → 粘贴到 Project Bar → Layouts
- events.json  → 粘贴到事件表边缘
```

```
> 添加 WASD 控制的 8 方向移动

AI 会生成事件 JSON → 粘贴到事件表边缘
```

## 功能

| 功能 | 说明 |
|------|------|
| 生成事件 | 游戏逻辑（移动、碰撞、计分等） |
| 生成对象 | Sprite、Text、TiledBackground 等 |
| 生成布局 | 完整场景（对象 + 实例 + 位置） |
| 生成图像 | 有效的 PNG base64 imageData |

## 项目结构

```
Construct3-Copilot/
├── .claude/
│   └── skills/
│       └── construct3-copilot/    # Claude Code Skill
│           ├── SKILL.md           # Skill 入口
│           ├── references/        # 参考文档
│           └── scripts/           # 辅助脚本
└── data/
    └── schemas/                   # ACE Schema (72 插件 + 31 行为)
```

### ACE Schema

由 `source/zh-CN_R466.csv` 通过 `scripts/generate-schema.js` 生成：

```
data/schemas/
├── index.json          # 概要索引
├── plugins/            # 72 插件 (677 条件, 776 动作, 957 表达式)
├── behaviors/          # 31 行为 (115 条件, 248 动作, 138 表达式)
├── effects/            # 89 特效
└── editor/             # 编辑器配置
```

**统计**: 2,911 ACE (792 条件 + 1,024 动作 + 1,095 表达式)

## License

[MIT](LICENSE)
