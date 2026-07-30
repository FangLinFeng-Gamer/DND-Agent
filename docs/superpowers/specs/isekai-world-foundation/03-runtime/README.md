# 03 Runtime

本层定义世界运行时状态。它回答：

- 时间如何推进。
- 天气如何变化。
- 局部 EnvironmentState 如何派生。
- 危险和障碍如何生成、关闭、同步通行状态。
- EventLog 和 Snapshot 如何保证一致性。
- 玩家、NPC 和社会群体如何知道、误解、传播或隐瞒事件。

## 当前文档

- [静态世界运行规则](./static-world-runtime-rules.md)
- [知识、发现与事件知情规则](./world-knowledge-rules.md)

## 规则

```text
本层定义“世界状态如何变化”。
任何权威状态变化必须通过 StateTransition 提交，并由 StateTransitionCommitter 生成 EventLog。
运行时派生状态必须能追溯输入事实。
EventLog 不是游戏内记忆，主体知情必须通过 KnowledgeState 表达。
Projection 只能读运行时状态，不能写 WorldState。
```
