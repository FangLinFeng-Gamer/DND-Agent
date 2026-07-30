# 异世界模式世界底座文档系统

本目录是异世界模式的长期世界底座文档系统。它不直接写剧情内容，而是定义世界如何存在、如何生成、如何运行、AI 如何提出影响、内容包如何进入世界。

## 阅读顺序

0. [系统问题与设计准入条件](./system-design-problems-and-acceptance-conditions.md)

   先阅读跨层设计审计、当前已知问题和实现准入门禁。该文档定义整个世界底座成为可实现、可验证、可重放基线之前必须满足的条件。

1. [架构总览](./00-architecture/README.md)

   先理解世界底座的分层方式、大集合、跨集合影响和文档组织规则。

2. [治理规则](./01-governance/README.md)

   再理解字段域、注册表、schema、validator、EventLog 等元规则。后续所有文档都必须遵守这一层。

3. [世界模型](./02-world-model/README.md)

   阅读空间、地形、水文、生态、资源和 WorldObject。这里定义“世界里有什么”。

4. [运行时规则](./03-runtime/README.md)

   阅读时间、天气、局部环境、危险、障碍、事件日志和快照。这里定义“世界状态如何变化”。

5. [AI 模拟边界](./04-ai-simulation/README.md)

   阅读 AI 群体心智和近身个体代理的 proposal 边界。AI 只能建议，不能直接修改权威状态。

6. [内容包](./05-content-packs/README.md)

   阅读 catalog 和内容包如何作为输入，通过 validator 和 materializer 进入 WorldState。

7. [实现计划](./06-implementation-plans/README.md)

   后续开发拆解放这里，避免污染架构设计文档。

## P0 世界生成基线

当前确认的初始世界生成方案是：

```text
空间来源：程序生成
地图范围：小型完整网格，单 Region 最多 256 个 WorldChunk
权威策略：候选骨架先生成，气候与物理字段完整后原子物化
运行时启动：先初始化 WorldTimeState，再生成 WeatherState
```

主依赖链：

```text
WorldGenerationParameters + RandomSeedMaterial
-> World / Region / WorldChunkGrid / WorldChunk 布局候选
-> 完整网格校验
-> Region 气候候选
-> chunk raw fields
-> 全量屏障与稳定邻接平滑
-> terrain
-> hydrology
-> local climate
-> chunk / region biome
-> 原子物化 World / Region / WorldChunkGrid / WorldChunk
-> 聚落/地貌空间锚点
-> OriginEventCandidate（历史候选，不是权威历史事实）
-> 静态 ChunkEdge 与基础通行
-> Resource / Flora / Fauna
-> Site / LocationNode / Zone / WorldObject
-> 聚落社会状态
-> OriginEvent 物化与 OriginMetadata 附着
-> StaticWorldRuntimeState + WorldTimeState
-> WeatherState、EnvironmentState、HazardSource / ObstacleSource、最终通行状态
-> 世界事实校验、初始知识、after_world_generation Snapshot
```

权威阶段顺序和直接依赖见 [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md)；候选、并行屏障和原子提交协议见 [世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md)；生成失败恢复、checkpoint 和 resume 协议见 [生成失败恢复与断点续生成规则](./00-architecture/generation-recovery-rules.md)；阶段内部形成规则的统一合约见 [FormationRule 合约与注册表规则](./00-architecture/formation-rule-contract-rules.md)；形成规则引用的可重放数值算法见 [可执行数值算法规则](./01-governance/executable-numeric-algorithm-rules.md)；空间候选字段见 [地点与空间规则](./02-world-model/location-space-rules.md)；气候与物理候选字段见 [气候、地形、生物群系与天气形成规则](./02-world-model/climate-terrain-formation-rules.md)。

## 当前有效文档

### 跨层审计与准入

- [系统问题与设计准入条件](./system-design-problems-and-acceptance-conditions.md)

### 00-architecture

- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md)
- [世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md)
- [生成失败恢复与断点续生成规则](./00-architecture/generation-recovery-rules.md)
- [FormationRule 合约与注册表规则](./00-architecture/formation-rule-contract-rules.md)

### 01-governance

- [字段域与注册表规则](./01-governance/field-domain-registry-rules.md)
- [确定性随机协议](./01-governance/deterministic-random-protocol-rules.md)
- [可执行数值算法规则](./01-governance/executable-numeric-algorithm-rules.md)

### 02-world-model

- [地点与空间规则](./02-world-model/location-space-rules.md)
- [气候、地形、生物群系与天气形成规则](./02-world-model/climate-terrain-formation-rules.md)
- [自然生态与资源规则](./02-world-model/natural-ecology-rules.md)
- [聚落与社会世界生成规则](./02-world-model/settlement-social-world-rules.md)
- [历史来历与世界痕迹规则](./02-world-model/world-origin-history-rules.md)
- [WorldObject 规则](./02-world-model/world-object-rules.md)

### 03-runtime

- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md)
- [知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md)

### 04-ai-simulation

- [AI 社会心智规则](./04-ai-simulation/ai-social-mind-rules.md)

### 05-content-packs

- [内容包说明](./05-content-packs/README.md)
- [内容包、Catalog 与物化版本规则](./05-content-packs/content-pack-materialization-rules.md)
- [通用小物件 catalog](./05-content-packs/catalogs/generic-item-catalog.json)
- [容器 catalog](./05-content-packs/catalogs/container-catalog.json)

## 文档分层原则

```text
根目录跨层门禁：记录系统级问题、设计硬约束和实现准入条件。
00-architecture：世界底座总纲和集合影响关系。
01-governance：字段、schema、validator、EventLog 等元规则。
02-world-model：空间、地形、生态、资源、对象等世界模型。
03-runtime：时间、天气、环境、危险、障碍、快照等运行时状态。
04-ai-simulation：AI proposal 与社会心智边界。
05-content-packs：内容包、catalog、materializer 输入。
06-implementation-plans：开发实施计划。
99-archive：废弃或被替代的旧方案。
```

## 设计准入规则

[系统问题与设计准入条件](./system-design-problems-and-acceptance-conditions.md) 是所有层级共同遵守的设计门禁。它不替代各子系统的权威规则，而是判断这些规则是否已经结构闭合、彼此一致，并能够成为实现基线。

```text
新增或修改规则前，必须检查是否违反跨层设计条件。
进入实现计划前，必须确认相关 P0 问题已经关闭或明确移出当前版本范围。
关闭问题时，必须同时更新权威文档、schema、registry、规则表和回归测试。
P0 未关闭时，可以制作验证性原型，但不能冻结长期存档、数据库或公共 API。
```

## 命名规则

- 当前有效文档使用稳定语义名，不使用日期前缀。
- 历史日期保留在文档内容、git 历史或 archive 中。
- 新增设计文档必须放入对应层级目录。
- 新增字段、tag、rule_id、event_type 必须先通过治理层文档定义。

## 新增文档要求

每篇规则文档应尽量包含：

```text
背景
目标
非目标
核心原则
数据模型
字段说明
规则
Validator 规则
与其他文档关系
推荐实现顺序
测试清单
已确认决策
```

不适用的章节可以省略，但不能留下 TODO、TBD 或模糊占位。

## 权威边界

Catalog 是内容包草案，不是运行时权威状态。运行时对象必须实例化为 `WorldObject`，并经过 `FieldDomainValidator` 和目标实体 validator 后才能进入 `WorldState`。

LLM proposal 不是权威状态。所有 AI 输出必须经过 proposal validator 和 deterministic resolver，形成 StateTransition 后由 StateTransitionCommitter 生成 EventLog。
