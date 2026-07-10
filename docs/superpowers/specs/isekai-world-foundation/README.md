# 异世界模式世界底座设计文档

本目录收纳新版本异世界模式的底层世界逻辑设计。这里的文档不直接定义具体剧情内容，而是定义世界如何存在、物品如何落位、AI 如何对社会状态产生影响。

## 阅读顺序

1. [地点与空间规则](./2026-07-10-isekai-location-space-rules-design.md)

   定义 `World -> Region -> WorldChunk -> Site -> LocationNode -> Zone`，以及对象、NPC、地点入口如何通过 `ObjectPlacement` 进入空间。

2. [气候、地形、生物群系与天气形成规则](./2026-07-11-isekai-climate-terrain-formation-rules-design.md)

   定义气候、地形、水系、生物群系、资源、动植物和天气如何由世界参数、seed、地形场和 validator 形成。

3. [自然生态与资源规则](./2026-07-10-isekai-natural-ecology-rules-design.md)

   定义动物、植物、非生命自然资源如何作为生态 catalog 参与世界生成，以及采集、狩猎、装水后如何转成 `WorldObject`。

4. [WorldObject 规则](./2026-07-10-isekai-world-object-rules-design.md)

   定义非生命对象的统一结构、`object_type`、`placement`、`components`、validator 和事件结算边界。

5. [AI 社会心智](./2026-07-10-isekai-ai-social-mind-design.md)

   定义 AI 在世界中的职责：模拟群体心智和近身个体代理，只输出 proposal，由规则系统验证并结算。

## 配套 Catalog 草案

- [通用小物件 catalog](./2026-07-10-isekai-generic-item-catalog.json)
- [容器 catalog](./2026-07-10-isekai-container-catalog.json)

Catalog 是内容包草案，不是运行时权威状态。运行时对象必须实例化为 `WorldObject`，并经过 `WorldObjectValidator` 后才能进入 `WorldState`。
