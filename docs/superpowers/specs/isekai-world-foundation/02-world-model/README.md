# 02 World Model

本层定义世界中长期存在的模型和生成规则。它回答：

- 世界空间如何组织。
- 地形、水文、气候、生物群系如何形成。
- 动物、植物、自然资源如何作为世界事实存在。
- 遗迹、废弃地点、事故现场、污染和社会压力如何拥有可验证来历。
- WorldObject 如何落位、可见、可交互。

## 当前文档

- [地点与空间规则](./location-space-rules.md)
- [气候、地形、生物群系与天气形成规则](./climate-terrain-formation-rules.md)
- [自然生态与资源规则](./natural-ecology-rules.md)
- [聚落与社会世界生成规则](./settlement-social-world-rules.md)
- [历史来历与世界痕迹规则](./world-origin-history-rules.md)
- [WorldObject 规则](./world-object-rules.md)

## 规则

```text
本层定义“世界里有什么”。
本层可以定义生成规则，但运行时状态变化必须交给 03-runtime。
本层不能让 LLM 或 DM 文本直接写权威状态。
```
