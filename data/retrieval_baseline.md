# Retrieval Evaluation Report

- **Date**: 2026-03-14 20:52
- **Top-K**: 10
- **Cases**: 15

## Summary

| Metric | Value |
|--------|-------|
| Recall@10 | 64.4% |
| MRR | 0.45 |
| Hit Rate | 92% (12/13) |
| Avg Latency | 1583ms |

- **easy**: recall=75%, hit_rate=100% (n=4)
- **medium**: recall=61%, hit_rate=83% (n=6)
- **hard**: recall=57%, hit_rate=100% (n=3)

## Per-Case Results

| ID | Difficulty | Recall | MRR | Hit | Missed Sources | Collections |
|----|-----------|--------|-----|-----|----------------|-------------|
| B01 | easy | 50% | 0.12 | Y | plugin-reference/sprite.md | ace, examples, plugins, project, terms |
| B02 | easy | 100% | 0.20 | Y | - | ace, examples, guide, project, terms |
| B03 | medium | 33% | 0.50 | Y | project-primitives/objects/instance-variables.md, project-primitives/events.md | ace, examples, project, terms |
| B04 | easy | 100% | 1.00 | Y | - | ace, behaviors, examples, terms |
| B05 | easy | 50% | 1.00 | Y | behavior-reference/tween.md | ace, terms |
| B06 | medium | 100% | 0.33 | Y | - | ace, examples, plugins, terms |
| B07 | medium | 67% | 1.00 | Y | system-reference/system-conditions.md | ace, examples, guide, interface, project, terms |
| B08 | hard | 100% | 1.00 | Y | - | ace, behaviors, examples, terms |
| B09 | medium | 100% | 0.11 | Y | - | ace, behaviors, terms |
| B10 | hard | 50% | 0.10 | Y | plugin-reference/keyboard.md, plugin-reference/sprite.md | ace, behaviors, examples, plugins, terms |
| B11 | medium | 67% | 0.25 | Y | plugin-reference/sprite.md | ace, examples, plugins, terms |
| B12 | hard | 20% | 0.17 | Y | project-primitives/events.md, plugin-reference/text.md, project-primitives/objects/instance-variables.md, project-primitives/events/variables.md | ace, examples, plugins |
| B13 | medium | 0% | 0.00 | **N** | scripting/scripting-reference, scripting-api | ace, behaviors, interface, project, terms |
| B14 | hard | n/a | n/a | Y | - | examples, terms, ace, guide, plugins, project |
| B15 | hard | n/a | n/a | Y | - | terms, guide |

## Miss Analysis

Cases where expected sources were NOT found in top-K:

### B01: Sprite 对象是什么？它的主要用途是什么？
- Missed: plugin-reference/sprite.md
- Found instead:
  - [terms] c3_terms (0.5355)
  - [terms] c3_terms (0.525)
  - [plugins] plugin-reference\svg-picture.md (0.4937)
  - [plugins] plugin-reference\particles.md (0.4717)
  - [examples] event_block (0.4668)

### B03: 实例变量和全局变量的区别是什么？
- Missed: project-primitives/objects/instance-variables.md, project-primitives/events.md
- Found instead:
  - [examples] script_code (0.5655)
  - [project] project-primitives\events\variables.md (0.5515)
  - [ace] construct3-schema (0.544)
  - [terms] c3_terms (0.5413)
  - [terms] c3_terms (0.5404)

### B05: 补间(Tween) 行为怎么用？如何让对象移动到指定位置？
- Missed: behavior-reference/tween.md
- Found instead:
  - [ace] construct3-schema (0.6232)
  - [terms] c3_terms (0.6104)
  - [terms] c3_terms (0.5992)
  - [ace] construct3-schema (0.5987)
  - [terms] c3_terms (0.58)

### B07: 系统(System) 对象的遍历(For each) 条件如何使用？
- Missed: system-reference/system-conditions.md
- Found instead:
  - [ace] construct3-schema (0.5972)
  - [examples] event_block (0.5633)
  - [examples] event_block (0.5444)
  - [project] project-primitives\events\how-events-work.md (0.5421)
  - [examples] event_block (0.5373)

### B10: 如何让玩家按空格键跳跃？并且播放跳跃动画？
- Missed: plugin-reference/keyboard.md, plugin-reference/sprite.md
- Found instead:
  - [examples] event_block (0.703)
  - [examples] event_block (0.6956)
  - [examples] event_block (0.6695)
  - [examples] event_block (0.6668)
  - [examples] event_block (0.6663)

### B11: 如何实现碰撞检测？Sprite 和 Sprite 碰撞时触发事件
- Missed: plugin-reference/sprite.md
- Found instead:
  - [ace] construct3-schema (0.6426)
  - [ace] construct3-schema (0.6122)
  - [ace] construct3-schema (0.5929)
  - [plugins] plugin-reference\common-features\common-conditions.md (0.5758)
  - [examples] event_block (0.5629)

### B12: 如何用事件表实现分数系统？包括变量定义和 UI 更新
- Missed: project-primitives/events.md, plugin-reference/text.md, project-primitives/objects/instance-variables.md, project-primitives/events/variables.md
- Found instead:
  - [examples] event_block (0.5863)
  - [examples] event_block (0.5799)
  - [examples] event_block (0.5585)
  - [examples] event_block (0.5565)
  - [examples] event_block (0.5565)

### B13: 在 Construct 3 脚本中如何获取一个对象的实例？
- Missed: scripting/scripting-reference, scripting-api
- Found instead:
  - [ace] construct3-schema (0.6289)
  - [ace] construct3-schema (0.5869)
  - [ace] construct3-schema (0.5817)
  - [ace] construct3-schema (0.5573)
  - [interface] interface\debugger\inspect-tab.md (0.5527)
