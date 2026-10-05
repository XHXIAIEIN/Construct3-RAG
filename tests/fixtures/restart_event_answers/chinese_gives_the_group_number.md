# 重启游戏的事件分析

## 答案

**事件编号**: **事件 8**（在 Construct 编辑器的事件表边栏中显示为 **8**）

**所属组**: Restart（重启组）

## 触发条件

该事件需要同时满足以下两个条件才会触发：

1. **`Coin.Count = 0`** （条件 1）
   - `System` 对象的系统表达式，检测当金币数量等于 0 时
   
2. **`仅触发一次`** （条件 2）
   - `System` 对象的 `trigger-once-while-true` 行为
   - 这意味着一旦该事件首次满足第一个条件并运行后，它会变成不触发状态

## 触发时的动作

当事件触发时，它会按顺序执行以下动作：

1. **`System: 设置变量 beat`** 
   - 将 `beat` 设置为 `(beat + 1) % tokencount(ROUND_COINS, ",")`
   - 切换到下一首曲目（循环）

2. **`System: 等待 1 秒`**
   - 使用游戏时间倍速

3. **`System: 重载场景`**
   - `restart-layout` 动作，重新加载当前布局以开始新的一轮

## 逻辑说明

这个事件组实现了"当最后一枚金币被收集完毕后（Coin.Count = 0），在延迟 1 秒后重新开始游戏"的功能。使用 `仅触发一次` 条件确保了即使 Coin.Count 保持为 0，该事件也只会执行一次，避免无限循环触发。

---

## Commands run

```bash
python <run>/project/.agents/skills/construct3-agent-plugin/scripts/check_project.py --project <run>/project
```

```bash
python <run>/project/.agents/skills/construct3-agent-plugin/scripts/review_design.py --project <run>/project
```

```bash
python <run>/project/.agents/skills/construct3-agent-plugin/scripts/print_sheet.py Game --events 1-60 --locale zh-CN --project <run>/project
```

```bash
python <run>/project/.agents/skills/construct3-agent-plugin/scripts/print_sheet.py Game --show 8 --project <run>/project
```
