# 中文语境支持

## 1. schemas（优先）

```bash
grep -r "八方向" data/schemas/
→ "name_zh": "八方向", "id": "eightdir"
```

## 2. CSV

```bash
CSV=$(ls source/zh-CN*.csv)
```

```bash
grep "跳跃" $CSV | head -10
```

Key 结构：`text.{plugins|behaviors}.{objectName}.{conditions|actions}.{aceId}`

示例：`text.behaviors.platform.conditions.is-jumping` → Platform 行为的 `is-jumping` 条件

通用 ACE 在 `_common`：
```bash
grep "_common.*destroy" $CSV
grep "_common.*collision" $CSV
```

## 3. 复杂需求

中文搜索不精准时，用英文 ACE ID：
```bash
grep "on-collision-with" $CSV
grep "simulate-control" $CSV
```
