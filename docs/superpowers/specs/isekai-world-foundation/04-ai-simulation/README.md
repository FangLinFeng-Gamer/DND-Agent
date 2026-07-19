# 04 AI Simulation

本层定义 AI 在世界中的职责边界。它回答：

- AI 可以模拟哪些社会或个体意图。
- AI proposal 的输出边界是什么。
- AI proposal 如何进入 validator 和 resolver。
- AI 为什么不能直接修改 WorldState。

## 当前文档

- [AI 社会心智规则](./ai-social-mind-rules.md)

## 规则

```text
AI 只能提出 proposal。
AI 只能读取主体对应的 AgentObservationSnapshot。
LLM 只填写单步 action payload；proposal 元数据、优先级、冲突键和资源预留由系统生成。
AI 不能直接写 WorldState、EventLog、WeatherState、WorldObject、HazardSource 或 ObstacleSource。
AI 输出必须经过字段域、proposal validator 和 deterministic resolver。
P0 不实现 GoalState、PlanState、PlanStep 或跨地点长期计划。
```
