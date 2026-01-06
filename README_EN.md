# Construct-3 Copilot

[中文](README.md) | **English**

Generate Construct 3 event sheet JSON with natural language, paste directly into editor.

## Quick Start

```bash
git clone https://github.com/XHXIAIEIN/Construct3-Copilot.git
cd Construct3-Copilot
claude
```

> Requires [Claude Code CLI](https://claude.ai/download)

## Examples

```
> Create a breakout game with mouse-controlled paddle

AI generates two JSON files:
- layout.json  → Paste to Project Bar → Layouts
- events.json  → Paste to event sheet margin
```

```
> Add WASD-controlled 8-direction movement

AI generates events JSON → Paste to event sheet margin
```

## Features

| Feature | Description |
|---------|-------------|
| Generate Events | Game logic (movement, collision, scoring, etc.) |
| Generate Objects | Sprite, Text, TiledBackground, etc. |
| Generate Layouts | Complete scenes (objects + instances + positions) |
| Generate Images | Valid PNG base64 imageData |

## Project Structure

```
Construct3-Copilot/
├── .claude/
│   └── skills/
│       └── construct3-copilot/    # Claude Code Skill
│           ├── SKILL.md           # Skill entry point
│           ├── references/        # Reference docs
│           └── scripts/           # Helper scripts
└── data/
    └── schemas/                   # ACE Schema (72 plugins + 31 behaviors)
```

### ACE Schema

Generated from `source/zh-CN_R466.csv` via `scripts/generate-schema.js`:

```
data/schemas/
├── index.json          # Summary index
├── plugins/            # 72 plugins (677 conditions, 776 actions, 957 expressions)
├── behaviors/          # 31 behaviors (115 conditions, 248 actions, 138 expressions)
├── effects/            # 89 effects
└── editor/             # Editor configuration
```

**Statistics**: 2,911 ACE (792 conditions + 1,024 actions + 1,095 expressions)

## License

[MIT](LICENSE)
