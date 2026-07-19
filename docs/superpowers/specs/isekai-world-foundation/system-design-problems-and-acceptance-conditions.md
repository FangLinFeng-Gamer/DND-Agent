---
doc_id: isekai.system_design_problems_and_acceptance_conditions
status: active
layer: architecture
owner: architecture
created_at: 2026-07-11
updated_at: 2026-07-18
depends_on:
  - isekai.world_collection_influence_rules
  - isekai.field_domain_registry_rules
  - isekai.location_space_rules
  - isekai.climate_terrain_formation_rules
  - isekai.natural_ecology_rules
  - isekai.world_object_rules
  - isekai.static_world_runtime_rules
  - isekai.world_knowledge_rules
  - isekai.world_generation_manifest_rules
  - isekai.ai_social_mind_rules
provides:
  - system_design_problem_registry
  - system_design_acceptance_conditions
  - implementation_baseline_gate
---

# 异世界世界底座系统问题与设计准入条件

## 文档作用

本文是异世界世界底座的跨层设计审计和实现准入门禁。它有三个作用：

1. 记录当前有效设计文档之间已经确认的结构性缺陷。
2. 定义整个系统成为可实现、可验证、可重放基线之前必须满足的条件。
3. 为架构评审、实现计划、schema 冻结、测试验收和迁移提供统一检查入口。

本文不替代空间、生态、对象、运行时或 AI 等权威规则文档。发现冲突时，必须修改对应权威文档、schema、registry 和测试，不能只在实现代码中增加特殊分支绕过问题。

在本文所有 P0 问题关闭或明确移出当前版本范围之前：

```text
现有 active 文档可以继续表达设计方向。
现有 active 文档不能被视为已经冻结的实现基线。
可以制作验证性原型，但原型输出不能作为长期存档格式或权威兼容承诺。
```

## 审查范围

本次审查覆盖：

- 世界集合、权威边界和跨集合影响。
- 字段域、registry、schema、reference 和 validator。
- 空间层级、图可达性、对象 placement 和容器。
- 地形、水文、生态、资源和 seeded generation。
- 时间、天气、环境、危险、障碍、EventLog 和 Snapshot。
- AI 群体心智、NPC proposal 和确定性结算边界。
- ContentPack catalog 和 materializer。

审查判断标准不是“概念是否合理”，而是：

```text
两个独立实现是否会得到相同的合法状态？
同一 RandomSeedMaterial 和规则版本是否会得到相同的世界？
任意权威状态是否可以验证来源并可靠重放？
任何状态转化是否保持引用、数量、单位和空间不变量？
AI 输出是否只能影响被明确授权的状态？
```

## 严重度与关闭规则

| 严重度 | 含义 | 准入影响 |
| --- | --- | --- |
| P0 | 规范彼此矛盾，或不存在可同时满足全部规则的实现。 | 阻断实现基线、schema 冻结和长期存档承诺。 |
| P1 | 实现可以自行补充假设，但不同实现可能产生不同结果。 | 阻断对应子系统进入稳定版本。 |
| P2 | 不立即破坏正确性，但会造成扩展、性能、可维护性或体验风险。 | 必须在对应功能进入正式范围前关闭或明确降级范围。 |

问题状态使用以下闭集：

```text
open
resolved
accepted_limited_scope
```

`resolved` 必须同时满足：

1. 权威设计文档已经修正。
2. schema、registry 和规则表保持一致。
3. 已增加能够复现原问题的测试。
4. 相关确定性、重放或不变量测试通过。

`accepted_limited_scope` 只能用于明确移出当前版本范围的能力，必须写出禁止输入和降级行为，不能表示“暂时不处理但实现仍可自由解释”。

## 当前 P0 问题

### P0-01 FieldDomainKind 不能表达真实字段约束

状态：`open`

设计修复状态：`completed`

问题：治理层要求每个字段属于一个 `FieldDomainKind`，但当前字段约束不是互斥分类。例如：

- `rule_id` 的定义位置和引用位置必须按完整 schema path 区分：规则表或规则注册表定义位置需要 `id_format` 和唯一性；运行时 `generated_by.rule_id` 等引用位置需要 `registry` 或规则表存在性。
- `catalog_id` 在定义位置需要 `id_format`，在引用位置需要 `reference`。
- `biome_tags` 的值域必须是 `biome_tag registry` 的子集；初始 chunk/region 标签分别由 `ChunkBiomeCandidateDerivation` 和 `RegionBiomeCandidateAggregation` 派生，再由 `SpatialFoundationMaterializer` 写入权威实体，不能由内容包或 LLM 直接手填最终值。
- `time_band` 的值域必须属于 `time_band enum`，同时字段值必须由 `minute_of_day`、`season` 和 `seasonal_daylight_profile` 派生或校验，不能由内容包、LLM 或手工写入直接决定最终值。

证据来源：[字段域与注册表规则](./01-governance/field-domain-registry-rules.md)。

影响：如果 validator 只按短字段名选择字段域，`FieldDomainValidator` 无法从规范编译出唯一且完整的字段约束，内容包、LLM proposal、迁移和 EventLog 可能使用不同解释。

关闭条件：用正交 `FieldSpec` 替代单一分类：

```text
FieldSpec(path) = {
  base_type,
  value_constraints[],
  reference_target,
  write_policy,
  derivation_policy,
  unit,
  precision,
  version
}
```

所有约束取交集，定义字段和引用字段必须按完整 schema path 分别声明。

设计修复结果：

- [字段域与注册表规则](./01-governance/field-domain-registry-rules.md) 已新增 `FieldSpec(path)` 作为字段治理的最小权威单元。
- `FieldDomainKind` 已降级为 `FieldSpec.value_constraints[].kind` 的闭集，只表达某一种值约束，不再承担字段完整语义。
- `rule_id`、`catalog_id`、`biome_tags`、`time_band` 已写入定义路径、引用路径、派生策略和值域约束示例。
- Validator 规则已改为检查完整 `FieldSpec`：`base_type`、`value_constraints[]`、`reference_target`、`write_policy`、`derivation_policy`、`unit`、`precision` 和 `version`。
- 推荐实现和验收已新增 `FieldSpec` 覆盖测试、定义/引用路径分离测试、`time_band` 派生测试和 `biome_tags` 派生测试。

工程关闭剩余项：

- 实现 FieldSpec schema、registry 和 validator。
- 增加并通过能够复现原问题的测试。

### P0-02 权威集合与字段所有权没有形成可验证分区

状态：`open`

设计修复状态：`completed`

问题：当前“世界大集合”只能说明一类内容大致属于哪个系统，不能直接作为写权限边界。

本文中的术语含义如下：

```text
权威集合：可以决定游戏结算和存档结果的真实状态集合，例如 WorldChunk、WeatherState、WorldObject、EventLog。
字段所有权：某个实体的某条字段路径由哪个系统负责写入和维护。
可验证分区：validator 能只凭 rule_id、EntityType、FieldPath 和 operation 判定一次写入允许或拒绝。
```

当前文档的问题是：集合表混合了实体、嵌套字段、非权威 catalog 和 proposal。只把实体放进大集合，不能说明实体内部字段由谁拥有。例如：

```text
WorldChunk.id / WorldChunk.coord
-> 空间系统拥有。

WorldChunk.terrain / WorldChunk.base_fields
-> 地形水文系统拥有。

WorldChunk.biome_tags
-> ChunkBiomeCandidateDerivation / RegionBiomeCandidateAggregation 负责派生，BiomeValidator 负责校验。
```

因此，不能因为 `WorldChunk` 属于空间集合，就允许任意空间规则器直接写 `WorldChunk.terrain`。同理，`WeatherState` 和 `EnvironmentState` 都位于气候时间天气集合，但它们的写入者不同：

```text
WeatherResolver 可以生成或更新 WeatherState。
EnvironmentDeriver 才能写 EnvironmentState.temperature / light / ground_effects。
WeatherResolver 不能直接写 EnvironmentState.temperature。
```

如果只检查“是否跨集合写入”，上述非法写入会因为目标仍在同一个大集合内而被放行。

证据来源：[世界集合与影响规则](./00-architecture/world-collection-influence-rules.md)。

影响：Resolver、Deriver 和 Materializer 的合法写入边界不能由机器判定。“任意被允许目标集合”会成为无界权威入口，导致规则器可以越过本应存在的派生链，直接改写权威状态。

关闭条件：分别定义并实现：

```text
EntityAuthorityDomain: EntityType -> AuthorityDomain
FieldOwnership: (EntityType, FieldPath) -> AuthorityDomain
WriteACL: (rule_id, EntityType, FieldPath, operation) -> allow/deny
```

最小可接受形态：

```text
EntityAuthorityDomain(WorldChunk) = space
FieldOwnership(WorldChunk.terrain) = terrain_hydrology
FieldOwnership(WorldChunk.biome_tags) = climate_terrain_derivation
FieldOwnership(EnvironmentState.temperature) = environment_derivation

WriteACL(TerrainCandidateFormation, ChunkTerrainCandidate.*, derive) = allow
WriteACL(TerrainCandidateFormation, WorldChunk.terrain, create/update/derive) = deny
WriteACL(SpatialFoundationMaterializer, WorldChunk.*, create) = allow
WriteACL(WeatherResolver, WeatherState, create/update) = allow
WriteACL(EnvironmentDeriver, EnvironmentState.temperature, update) = allow
WriteACL(WeatherResolver, EnvironmentState.temperature, update) = deny
```

所有写入都必须检查 `WriteACL`，默认拒绝；不能只在跨集合时检查。

设计修复结果：

- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已新增 `AuthorityDomain` 闭集。
- 已新增 `EntityAuthorityDomain(EntityType) -> AuthorityDomain`，用于声明实体身份归属。
- 已新增 `FieldOwnership(EntityType, FieldPath) -> AuthorityDomain`，用于声明实体内部字段的维护系统。
- 已新增 `WriteACL(rule_id, EntityType, FieldPath, operation) -> allow/deny`，所有权威写入默认拒绝。
- 已明确 `WorldChunk.coord` 属于 `space`，`WorldChunk.terrain` 属于 `terrain_hydrology`，`WorldChunk.biome_tags` 属于 `climate_terrain_derivation`。
- 已明确 `WeatherResolver` 可以写 `WeatherState`，但不能写 `EnvironmentState.temperature/light/ground_effects`；这些字段必须由 `EnvironmentDeriver` 写入。
- Validator、实现顺序和测试清单已加入字段级 ACL 检查、同集合非法写入检查、Projection 禁写检查和默认拒绝检查。

工程关闭剩余项：

- 实现 AuthorityDomain、EntityAuthorityDomain、FieldOwnership 和 WriteACL 表。
- 所有权威写入接入 WriteACL 默认拒绝检查。
- 增加并通过字段级 ACL、同集合非法写入、Projection 禁写和默认拒绝测试。

### P0-03 世界生成依赖图不存在合法拓扑序

状态：`open`

设计修复状态：`completed`

原问题：`ChunkEdgeFormation` 声明读取 WeatherState，但生成顺序先创建 ChunkEdge、后创建 WeatherState；SitePlacement 的部分形成条件依赖可达 ChunkEdge，但 Site 又先于 ChunkEdge 生成；自然生态投影还可能读取尚未创建的 Site/LocationNode。进一步检查还发现旧顺序直接从 RegionClimateEnvelope 开始，却没有先产生 World、Region、WorldChunkGrid 或 WorldChunk 的可引用空间身份；WeatherFormation 也没有明确的 WorldTimeState 初始化前置阶段。

证据来源：[世界集合与影响规则](./00-architecture/world-collection-influence-rules.md)、[气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md)、[自然生态与资源规则](./02-world-model/natural-ecology-rules.md)、[聚落与社会世界生成规则](./02-world-model/settlement-social-world-rules.md)、[历史来历与世界痕迹规则](./02-world-model/world-origin-history-rules.md)。

影响：不同实现必须自行改变步骤、使用未初始化状态或运行额外隐式 pass，因此同一输入可能生成不同世界。

关闭条件：生成规则必须形成有向无环图，并显式区分：

```text
静态基础事实
-> 静态候选
-> 权威实体物化
-> 初始动态状态
-> 运行时派生状态
-> 最终 Validator
-> 初始 Snapshot
```

每个阶段只能读取已完成阶段；候选不是权威实体，不能被运行时 Resolver 直接消费。

设计修复结果：

- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已将 P0 世界生成顺序改成带提交边界的拓扑 DAG。
- P0 已确定使用“程序生成、小型完整网格、候选骨架先生成、完整后物化”：先生成 WorldLayoutCandidate、RegionLayoutCandidate、WorldChunkGridLayoutCandidate 和完整网格的 WorldChunkLayoutCandidate，再生成气候与物理候选。
- [地点与空间规则](./02-world-model/location-space-rules.md) 已逐字段定义四种空间布局候选、完整网格笛卡尔覆盖公式、单 Region 256 chunk 上限和 SpatialLayoutCandidateValidator。
- [气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md) 已定义 RegionClimateCandidate、raw/smoothed base fields、terrain、hydrology、local climate、chunk/region biome 候选及其依赖。
- `SpatialFoundationMaterializer` 只能在全部候选通过校验后，用同一 atomic_commit_group_id 原子创建 World、全部 Region、全部 WorldChunkGrid 和全部 WorldChunk；禁止提交只有 ID/coord 的半成品 chunk。
- `GenerationStageContract` 已增加 `depends_on_stage_contract_ids`、`execution_scope`、`parallelizable` 和 `atomic_commit_group_id`；中央规则已给出完整 P0 直接依赖表。
- `ChunkEdgeFormation` 已拆成 `StaticChunkEdgeFormation` 和 `StaticTraversalDeriver`；二者不能读取 WeatherState、EnvironmentState、HazardSource 或 ObstacleSource。
- `SitePlacement` 已移动到静态 ChunkEdge 和 `base_passability/base_traversal` 提交之后，读取的是已提交静态可达图。
- 生态生成已明确只生成 FloraPatch、CreaturePopulation、CreatureGroup、ResourceDeposit、ResourceNode 等权威事实；Site / LocationNode 可互动目标由后续 `EcologyInteractionProjection` 只读生成。
- `OriginHistoryFormation` 已拆成 `OriginHistoryCandidateFormation` 和 `OriginHistoryMaterialization`；候选可以影响权重，权威 OriginEvent 必须在证据实体物化后提交。
- `SettlementSocialFormation` 已明确可以消费 OriginEventCandidate，但不要求权威 OriginEvent 已经提交，避免社会生成和历史证据形成环。
- `SettlementSocialFormation` 内部子阶段已固定为 SettlementProfile -> Institution -> SocialGroup -> PolicyAndPressure -> NamedNPC -> Service；NamedNPC 读取 Institution.services，不再读取尚未生成的 ServiceState，整批通过 Validator 后原子提交。
- ResourceFormation、FloraFormation、FaunaFormation 和 SitePlacement 已显式依赖 OriginHistoryCandidateFormation；初始生成只能读取已验证 OriginEventCandidate，不能读取尚未物化的 OriginEvent。
- `WorldRuntimeInitialization` 已成为 WeatherFormation 的强制前置阶段，原子创建 StaticWorldRuntimeState 和 WorldTimeState；时间段由初始绝对分钟、季节和昼夜配置派生。

工程关闭剩余项：

- 实现 `GenerationStageContract` DAG 校验，拒绝阶段读取未完成阶段。
- 实现空间候选完整网格、候选目标引用和 256 chunk 上限校验。
- 实现 SpatialFoundationMaterializer 原子提交与任一 chunk 缺失候选时整组回滚测试。
- 实现并行/串行 candidate hash 等价和阶段全量屏障测试。
- 实现 WeatherFormation 缺少已提交 WorldTimeState 时拒绝启动的测试。
- 实现 `StaticChunkEdgeFormation` 不允许读取 WeatherState 的测试。
- 实现 `SitePlacement` 必须读取已提交 static traversal 的测试。
- 实现生态生成不读取 Site / LocationNode 投影的测试。
- 实现 `OriginEventCandidate` 不能被 runtime resolver、AI 或 UI 消费的测试。
- 实现社会子阶段 DAG、NamedNPC 禁止读取 ServiceState 和社会实体整批原子提交测试。
- 实现初始 Resource/Ecology/Site 只能读取 OriginEventCandidate、不能读取 OriginEvent 的测试。
- 实现 `OriginHistoryMaterialization` 证据未物化时拒绝提交 OriginEvent 的测试。

### P0-04 Seed 不是完整的确定性随机协议

状态：`open`

设计修复状态：`completed`

问题：规范只要求 seed 参与随机过程，没有规定 PRNG/KDF、seed 编码、随机流拆分、候选排序、重采样行为、规则版本和 catalog 版本。ChunkBaseFields 还依赖邻接 chunk，结果可能随遍历顺序和并行度变化；天气权重和生态 rarity 也没有数值概率核。

证据来源：[确定性随机协议](./01-governance/deterministic-random-protocol-rules.md)、[世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md)、[气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md)、[自然生态与资源规则](./02-world-model/natural-ecology-rules.md)。

影响：相同 seed 不能保证相同 WorldState、EventLog 或 Snapshot hash，增加一个候选或一次失败重试可能改变后续全部结果。

关闭条件：定义版本化随机协议：

```text
random_stream = PRF(
  world_seed,
  rule_bundle_hash,
  content_pack_hash,
  domain,
  rule_id,
  scope_id,
  logical_draw_id
)
```

候选必须按稳定 ID 排序和去重；不同规则使用独立随机流；Validator 拒绝不得改变其他逻辑抽样；所有概率使用明确的整数权重、归一化、零权重 fallback 和稳定 tie-break。

设计修复结果：

- [确定性随机协议](./01-governance/deterministic-random-protocol-rules.md) 已定义 P0 `drp.v1` 协议、`RandomSeedMaterial`、`RandomStreamRef`、`RandomDrawRef`、`CandidateSet` 和 `WeightedChoiceKernel`。
- P0 PRF 固定为 HMAC-SHA256，输入使用 canonical JSON。
- 随机流已按 `domain + rule_id + scope_id + logical_draw_id + draw_index` 拆分。
- 已定义候选稳定排序、去重、整数权重、零权重 fallback、validator 拒绝策略和 tie-break。
- 已定义 `rarity_weight`、`abundance_count_band`、`weather_base_weight` 和 `weather_modifier_weight`。
- `ChunkBaseFields` 已拆成 `ChunkBaseRawFieldsCandidate` 和 `ChunkBaseFieldSmoothing`；平滑阶段必须等待同一 Region 全部 raw 候选，并按稳定邻接顺序处理。
- 程序空间布局使用独立 `spatial_layout` 随机域，完整网格按 region_id、z、y、x 稳定枚举；Region 气候按 region_id 拆分随机流。
- [世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md) 已要求 manifest 记录 `RandomSeedMaterial`、`seed_material_hash`、`RandomStreamRef` 和每个 `RandomDrawRef`。
- 气候、天气和生态文档已改为引用确定性随机协议，不再允许本地 seed、浮点概率或口头 rarity 概率。

工程关闭剩余项：

- 实现 canonical JSON、HMAC-SHA256 PRF、`random_int_exclusive` 和 rejection sampling。
- 实现 `RandomSeedMaterial`、`RandomStreamRef`、`RandomDrawRef` schema。
- 所有生成器接入 `RandomDrawRef` 记录。
- 实现 CandidateSet 稳定排序、去重、candidate_set_hash 和 WeightedChoiceKernel。
- 实现 validator 拒绝不改变其他 logical draw 的测试。
- 实现 ChunkBaseRawFields 与 ChunkBaseFieldSmoothing 的顺序无关测试。
- 实现空间候选并行/串行目标 ID、坐标集合和 payload hash 一致测试。
- 实现天气和生态标准权重核测试。

### P0-05 EventLog、WorldState 与 Snapshot 不是原子可重放协议

状态：`open`

问题包括：

- 治理层和运行时文档定义了不同的 `change_op` 闭集。
- event_type 闭集缺少对象揭示、生态变化、环境变化和社会变化等已要求事件。
- `create` 示例只保存实体片段，无法从日志重建完整实体。
- 行动流程先修改 WorldState、后写 EventLog，失败时会产生双写分叉。
- Snapshot 的 event sequence 同时被要求“等于”和“不得大于”当前 sequence。
- EventLog 自身属于权威集合，但未说明追加日志是否豁免“所有权威变化再写一条日志”，形成自记录悖论。

证据来源：[字段域与注册表规则](./01-governance/field-domain-registry-rules.md)、[静态世界运行规则](./03-runtime/static-world-runtime-rules.md)、[WorldObject 规则](./02-world-model/world-object-rules.md)。

影响：日志只能用于部分审计，不能保证恢复、并发提交、幂等重试或分支存档正确。

关闭条件：定义单一提交协议：

```text
StateTransition = {
  world_id,
  timeline_id,
  command_id,
  idempotency_key,
  expected_sequence,
  expected_entity_revisions,
  preconditions,
  ordered_changes,
  resulting_state_hash,
  rule_bundle_hash
}
```

完整 post-state 必须先通过所有 Validator，再使用 CAS 原子提交状态与事件。`create.value` 必须是完整规范化实体；明确 path/array 操作和同事件内顺序。EventLog append 是提交包络自身，不再为追加行为递归生成事件。Snapshot 只能指向已提交边界，并从 `event_sequence + 1` 开始重放。

当前仍缺少：

- `StateTransition` 的 canonical schema。
- `create/update/deactivate/materialize/derive` 的完整 change payload 结构。
- `expected_sequence`、`expected_entity_revisions`、`preconditions` 和 CAS 原子提交规则。
- `resulting_state_hash`、snapshot hash 和 event replay hash 的固定计算规则。
- 从任意 Snapshot 之后重放事件并恢复同一 canonical world hash 的验收样例。

### P0-06 同一实体存在互不兼容的权威 schema

状态：`open`

设计修复状态：`completed`

问题：修复前，`CreatureGroup` 在空间文档中使用 `species`、结构化 `visibility` 和 `behavior`，在生态文档中使用 `species_id`、字符串 `visibility` 和 `behavior_state`。`ChunkEdge` 在空间文档和形成文档中也使用不同字段组合，例如 `direction/adjacent` 与 `relation`。

证据来源：[跨集合影响规则](./00-architecture/world-collection-influence-rules.md)、[地点与空间规则](./02-world-model/location-space-rules.md)、[自然生态与资源规则](./02-world-model/natural-ecology-rules.md)、[气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md)。

影响：在 `additionalProperties=false` 下，同一实体不可能同时通过两套 Validator；投影、Resolver 和 EventLog 也无法共享稳定 schema。

关闭条件：每个 `EntityType` 只能有一个 canonical schema 和 owner 文档。其他文档只能引用该 schema 或声明阶段性 candidate/output 类型，不能重新定义同名权威实体。

设计修复结果：

- [跨集合影响规则](./00-architecture/world-collection-influence-rules.md) 已新增 `CanonicalEntitySchemaRegistry(EntityType) -> owner_doc + canonical_section`。
- 已明确非 owner 文档只能引用 canonical schema，或声明独立后缀类型，例如 `CreatureGroupProjection`、`WeatherFormationOutput`、`ChunkEdgeCandidate`。
- `CreatureGroup` 的 canonical owner 确认为 [自然生态与资源规则](./02-world-model/natural-ecology-rules.md)。
- [地点与空间规则](./02-world-model/location-space-rules.md) 已删除对 `CreatureGroup` 的第二套字段定义，改为只声明空间系统如何读取 `CreatureGroup.location` 并生成 `creature_awareness` 投影。
- `ChunkEdge` 的 canonical owner 确认为 [地点与空间规则](./02-world-model/location-space-rules.md)。
- [气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md) 中 `StaticChunkEdgeFormation` 已改为输出 canonical 字段 `source_chunk_id`、`target_chunk_id`、`direction`、`adjacent`，不再输出 `relation`。
- `FieldOwnership` 和 `WriteACL` 中 `ChunkEdge` 字段已与空间文档对齐为 `direction`、`adjacent`。

工程关闭剩余项：

- 实现 `CanonicalEntitySchemaRegistry` 可加载表。
- 实现 `test_every_entity_type_has_one_canonical_schema_owner`。
- 实现 `test_non_owner_doc_cannot_define_authoritative_entity_schema`。
- 实现 `test_creature_group_schema_owner_is_ecology`。
- 实现 `test_location_space_creature_group_projection_does_not_write_creature_group_fields`。
- 实现 `test_chunk_edge_formation_uses_canonical_direction_and_adjacent_fields`。
- 实现 `test_chunk_edge_relation_field_is_rejected`。

### P0-07 空间图的方向、成本和距离分级不闭合

状态：`open`

设计修复状态：`completed`

问题包括：

- ChunkEdge 未明确是有向边、无向边还是可反向解释的单条边。
- LocationEdge 可以声明 bidirectional，但 Resolver 示例只按 source 到 target 查询。
- 邻接但不可达的 chunk 同时可能命中 `near` 和 `blocked_or_unknown`。
- 距离区间在 10、30、90 分钟处重叠。
- blocked edge 的成本为 null，但示例仍可能返回有限 route time。
- 未限制可通行边成本为有限正数，最短路算法前提不成立。

证据来源：[地点与空间规则](./02-world-model/location-space-rules.md)。

影响：可达性、移动、感知和附近生物投影会随实现解释变化。

关闭条件：

1. 权威图统一存储有向 arc；双向连接展开为两条 arc。
2. 每条 arc 可以有独立成本、条件和风险。
3. 可通行 arc 的有效成本必须有限且大于零；blocked 为正无穷或 null，不能进入可达路径。
4. 分离 geometric proximity、perceptual proximity 和 reachable route time。
5. 所有距离 band 使用无重叠半开区间。
6. 同成本路径使用稳定 edge ID 序列作为 tie-break。

设计修复结果：

- [地点与空间规则](./02-world-model/location-space-rules.md) 已规定 `ChunkEdge` 和 `LocationEdge` 在权威状态中都表示有向 arc，只表达 `source -> target`。
- 双向外部路径必须物化成两条反向 `ChunkEdge`；双向内部路径必须物化成两条反向 `LocationEdge`。
- `LocationEdge.direction` 不再允许使用 `bidirectional` 表示双向；反向通行必须有独立 edge。
- RouteResolver 只允许把 `open`、`difficult`，或条件满足的 `conditional` edge 放入最短路。
- 可入图 edge 的 `effective_traversal.time_minutes` 必须是有限正数。
- `blocked` 和条件不满足的 `conditional` edge 的 effective cost 为 `Infinity`，不能进入可达路径。
- 外部投影已拆分 `geometric_proximity`、`route_proximity` 和 `perceptual_proximity`。
- `route_band` 只在 `route_state=reachable` 时存在；blocked、unknown 或条件不满足时必须为 `null`。
- 距离 band 已改为无重叠半开区间。
- 同成本路径已规定按 edge_id 序列字典序稳定 tie-break。

工程关闭剩余项：

- 实现 `ChunkEdge` 和 `LocationEdge` 有向 arc validator。
- 实现双向连接 materializer，把设计层的双向连接展开成两条有向 edge。
- 实现 RouteResolver 的可入图 edge 过滤和 effective cost 计算。
- 实现同成本路径 edge_id 序列 tie-break。
- 实现 route/geometric/perceptual proximity 分离投影。
- 实现 `test_chunk_edge_is_directed_arc`。
- 实现 `test_chunk_edge_reverse_requires_separate_edge`。
- 实现 `test_location_edge_is_directed_arc`。
- 实现 `test_location_edge_rejects_bidirectional_direction`。
- 实现 `test_blocked_edge_is_not_used_by_route_resolver`。
- 实现 `test_open_edge_requires_positive_finite_cost`。
- 实现 `test_conditional_unmet_edge_has_infinite_effective_cost`。
- 实现 `test_same_cost_routes_use_edge_id_sequence_tiebreak`。
- 实现 `test_route_bands_are_half_open_and_non_overlapping`。
- 实现 `test_geometric_route_and_perceptual_proximity_are_separate`。

### P0-08 passability 存在多写者和派生反馈环

状态：`open`

设计修复状态：`completed`

问题：地形、天气、Portal、ObstacleSource 和 Resolver 都可能影响 Edge.passability，但没有唯一 reducer。部分 ObstacleSource 规则读取当前 passability 生成障碍，障碍又回写 passability，可能在原始原因消失后继续自我支撑。

证据来源：[气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md)、[静态世界运行规则](./03-runtime/static-world-runtime-rules.md)、[WorldObject 规则](./02-world-model/world-object-rules.md)。

影响：关闭一个临时障碍可能错误地打开仍被其他来源阻挡的边，最终状态取决于 Deriver 运行顺序。

关闭条件：

```text
base_passability = StaticEdgeDeriver(static facts)
active_overrides = all active obstacle/portal/environment overrides
effective_passability = PassabilityReducer(base_passability, active_overrides)
```

只有 `PassabilityReducer` 能写 effective 值。至少规定 `blocked > conditional > difficult > open` 的聚合顺序、条件组合、原因稳定排序和恢复规则。Deriver 必须读取基础事实或来源状态，不能读取自己的最终输出作为存在依据。

设计修复结果：

- [地点与空间规则](./02-world-model/location-space-rules.md) 已拆分 `base_passability/base_traversal` 和 `effective_passability/effective_traversal`。
- [气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md) 已规定静态地形、水文、道路推导只能写 base 字段。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已定义 `PassabilityReducer` 为 effective 通行字段唯一写者。
- `ObstacleSource`、portal、mechanism、environment 影响移动时只能产出 `passability_override`，不能直接写 Edge effective 字段。
- `PassabilityReducer` 已规定 `blocked > conditional > difficult > open` 聚合顺序、条件组合、原因稳定排序和恢复规则。
- Hazard/Obstacle Deriver 已明确不能读取 `effective_passability` 作为自身生成依据。
- RouteResolver、DM Projection、UI Projection 已明确只能读取 effective 通行字段。

工程关闭剩余项：

- 实现 `PassabilityReducer`。
- 实现 FieldOwnership / WriteACL 校验，拒绝非 `PassabilityReducer` 写 effective 字段。
- 实现 `StaticTraversalDeriver` 只写 `base_passability/base_traversal`。
- 实现 `ObstacleSource.passability_override.target_edge_ids` 引用校验。
- 实现 active override 变化触发 reducer 重算。
- 实现 reducer 从 base + active overrides 重算，不能从旧 effective 反推恢复。
- 实现 `test_static_traversal_writes_only_base_passability`。
- 实现 `test_passability_reducer_is_only_effective_writer`。
- 实现 `test_obstacle_override_is_reflected_by_passability_reducer`。
- 实现 `test_passability_reducer_restores_from_base_when_override_removed`。
- 实现 `test_passability_reducer_combines_multiple_overrides_by_priority`。
- 实现 `test_deriver_cannot_read_effective_passability_for_source_generation`。
- 实现 `test_route_resolver_reads_effective_passability_only`。

### P0-09 ContentPack 物化结果会被目标 Validator 拒绝

状态：`open`

设计修复状态：`completed`

问题：液体容器 catalog 默认带有 `drink/refill_water` affordance；WorldObjectValidator 又要求 `refill_water` 具备 `water_profile`；容器 catalog 同时禁止非 container 组件。物化出的水囊只有 `components.container`，因此无法同时满足全部规则。

证据来源：[容器 catalog](./05-content-packs/catalogs/container-catalog.json)、[WorldObject 规则](./02-world-model/world-object-rules.md)。

影响：P0 容器 catalog 的合法实例无法通过规定的二次校验。

关闭条件：动作约束必须按参数角色定义。例如：

```text
refill_water.source -> ResourceNode 或 WorldObject.water_profile
refill_water.target -> WorldObject.container，且 capacity.liquid_liters > 0
drink.source -> 可饮用资源或含可饮用 quantity_contents 的液体容器
```

组件兼容表必须改为机器可读的 required/allowed/forbidden 矩阵；未知 affordance 必须拒绝输入，不能删除后写入未声明的 `blocked_affordances` 字段。

设计修复结果：

- [WorldObject 规则](./02-world-model/world-object-rules.md) 已明确 `affordances` 是可尝试动作，不是成功承诺。
- 未知 affordance 已改为 validator 直接拒绝；不允许静默删除，也不允许写入 `blocked_affordances`。
- 已新增 `ActionRoleRequirement`，将 `refill_water.source`、`refill_water.target`、`drink.source` 等动作角色分开校验。
- `refill_water.source` 需要 ResourceNode 或 `WorldObject.components.water_profile`。
- `refill_water.target` 需要 `WorldObject.components.container.capacity.liquid_liters > 0`。
- `drink.source` 可以是 drink consumable、水源，或具备液体容量且有可饮用 `quantity_contents` 的容器；空容器在 resolver 阶段失败，不在物化阶段失败。
- `object_type_component_matrix` 已改成机器可读 `required/recommended/allowed/forbidden_policy` 结构。
- `container_catalog` 已明确 liquid_vessel 可以带 `drink/refill_water/pour`，实例化后仍只能有 `components.container`，不得自动添加 `water_profile`。

工程关闭剩余项：

- 实现 `ActionRoleRequirement` registry。
- 修改 `WorldObjectValidator`，取消 affordance 到单一组件的硬编码映射。
- 修改 `ContainerMaterializer`，保持 liquid_vessel 只生成 `components.container`。
- 修改未知 affordance 策略为拒绝输入，不生成 `blocked_affordances`。
- 实现 `test_unknown_affordance_is_rejected_without_blocked_affordances`。
- 实现 `test_affordance_requires_at_least_one_static_action_role`。
- 实现 `test_refill_water_source_requires_resource_node_or_water_profile`。
- 实现 `test_refill_water_target_accepts_liquid_container_without_water_profile`。
- 实现 `test_drink_from_empty_container_fails_in_resolver_not_validator`。
- 实现 `test_container_liquid_vessel_refill_water_affordance_passes_without_water_profile`。

### P0-10 AI 社会模拟没有可执行的权威状态和提案协议

状态：`open`

设计修复状态：`completed`

问题：AI 社会模拟此前只有方向性边界，没有形成完整可实现协议。虽然已经定义聚落社会状态、主体知识状态和 AgentObservationSnapshot，但调度频率、统一 proposal schema、冲突排序、资源预留、反馈循环上限和完整测试仍未闭合。

证据来源：[AI 社会心智规则](./04-ai-simulation/ai-social-mind-rules.md)、[聚落与社会世界生成规则](./02-world-model/settlement-social-world-rules.md)、[知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md)。

影响：AI proposal 无合法目标字段和事件类型；过期 proposal、重复重试、多个群体冲突、隐藏信息泄漏和反馈循环没有确定性处理规则。

已完成的设计修复：

- `SocialGroupState`、`NamedNPCState`、`ServiceState`、`LawPolicy`、`EconomyState`、`SocialPressureState` 已在聚落社会世界文档中定义。
- `KnowledgeState`、`DiscoveryState`、`RumorState`、`SecretState`、`AgentObservationSnapshot` 已在知识规则文档中定义。
- AI 文档已明确 AI 只能读取主体可知的 `AgentObservationSnapshot`，不能直接读取全量 WorldState、OriginEvent 或 EventLog。
- 已把 P0 边界限制为一次可立即结算的单步社会行动；长期 Goal/Plan/PlanStep 明确延后到 P1。
- 已定义 `AIDecisionTick` 的 trigger 闭集、系统优先级、群体 60 分钟周期和近身 NPC 事件调度/冷却规则。
- 已定义 `AIProposalEnvelope`，由 `GroupDecisionProposal` 和 `NPCActionProposal` 共享。
- 已拆分字段所有权：LLM 只能写 action payload；proposal ID、revision、snapshot、event sequence、read set、幂等键、有效期、因果上下文、优先级、冲突键和 resource claims 全部由系统生成。
- 已定义 proposal_kind、action_type、target_ref.kind、arguments、status 和状态机闭集。
- 已定义 `AIActionPolicyRegistry`，将每个 action_type 的目标数量、参数 schema、前置条件、冲突键、资源声明、resolver、部分接受和允许事件绑定为唯一机器可读条目。
- 已定义 revision/read set/有效期/知识可见性/空间/机构职权/服务权限等前置条件。
- 已定义 decision slot、幂等键、最多一次重试和每个 decision slot 最多结算一次。
- 已定义 conflict_key、固定排序、`ProposalResourceReservation`、资源预留有效期和释放规则。
- 已定义部分接受边界：只能缩小压力 delta 或 discount/markup，巡逻和态度必须精确合法，且不能改写 action_type、主体、目标和资源。
- 已定义 causal depth=4、每层强度乘 0.5、群体/NPC 冷却、流言传播限制、24 小时压力变化上限和阈值滞回。
- 已将 decision tick、proposal 和 reservation 登记到 system_ledger、CanonicalEntitySchemaRegistry、FieldOwnership 和 WriteACL。
- 已补充 AI 社会审计事件和社会状态事件类型，并列出必须实现的完整测试。

关闭条件：至少定义：

- SocialGroupState、NamedNPCState 和社会影响状态的 canonical schema。
- `proposal_id`、`idempotency_key`、`based_on_event_sequence`、主体 revision、有效期和前置条件。
- 主体可见的 `AgentObservationSnapshot`，禁止向 AI 暴露不可知事实。
- proposal 类型、目标引用和数值范围闭集。
- 同一 decision tick 内的冲突键、资源预留、确定性排序和部分接受规则。
- 因果深度、去重、冷却、衰减、滞回和最大放大率。

设计关闭结论：以上关闭条件均已在设计文档中明确，P0-10 的设计问题关闭；工程状态保持 `open`，直到以下实现和测试完成。

工程关闭剩余项：

- 实现 AIDecisionTick、AIProposalEnvelope、GroupDecisionProposal、NPCActionProposal 和 ProposalResourceReservation schema。
- 实现 AISocialScheduler、AgentObservationBuilder 扩展、AIProposalRecorder 和 AIProposalAuditWriter。
- 实现 action policy registry、AIProposalValidator、冲突排序和 reservation 事务。
- 实现 P0 社会 action resolver、SocialFallbackResolver、KnowledgePropagation 接口和 EventLog 事件。
- 实现 proposal/system_ledger 的存档恢复与确定性 replay。
- 实现 AI 社会心智规则文档列出的全部 P0 测试。

### P0-11 知识状态和世界事实缺少强制隔离

状态：`open`

设计修复状态：`completed`

问题：虽然已经定义了 `KnowledgeState`、`DiscoveryState`、`RumorState` 和 `SecretState`，但如果没有强制命名空间和字段边界，开发仍可能把“谁知道了某件事”写回世界实体，例如在 `WorldObject` 上添加 `known_by`，或在 `OriginEvent` 上添加 `discovered_by`。反过来，也可能把物理事实塞进知识实体，例如在 `KnowledgeState` 中写 `placement`、`locked` 或 `resource_quantity`。

证据来源：[知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md)、[静态世界运行规则](./03-runtime/static-world-runtime-rules.md)、[世界集合与影响规则](./00-architecture/world-collection-influence-rules.md)。

影响：主体认知会污染世界真相，NPC 可能天然全知；Snapshot 和 AI 输入也可能把“事实存在”和“主体知道”混成一件事，导致状态重放、社会反应和玩家可见信息不一致。

关闭条件：必须定义并实现：

```text
AuthoritativeWorldState.world_facts
AuthoritativeWorldState.knowledge_facts
AuthoritativeWorldState.system_ledger
```

世界事实实体禁止主体认知字段；知识事实实体禁止物理世界字段。`AgentObservationSnapshot` 只能由主体可知内容构建，不能反向写入世界事实或知识事实。

设计修复结果：

- [知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md) 已新增 `AuthoritativeWorldState` 三段命名空间。
- 已定义 P0 世界事实实体类型和 P0 知识事实实体类型。
- 已列出世界事实实体禁止字段：`known_to_player`、`known_by`、`discovered_by`、`rumored_by`、`secret_holders`、`ai_context` 等。
- 已列出知识事实实体禁止字段：`placement`、`location`、`terrain`、`physical`、`components`、`resource_quantity`、`passability`、`temperature`、`locked` 等。
- [地点与空间规则](./02-world-model/location-space-rules.md) 已移除 `WorldChunk`、`ChunkEdge`、`RegionFeature`、`Settlement`、`Site` 和 `LocationEdge` 示例与字段说明中的 `known_to_player`；空间 `visibility` 只表达客观可观察线索。
- [知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md) 已明确 chunk、路径、入口、地点、阻挡或对象的发现状态必须写 `DiscoveryState` / `KnowledgeState`。
- [字段域注册规则](./01-governance/field-domain-registry-rules.md) 已定义主体认知字段禁用集和知识事实物理字段禁用集，并要求 FieldDomainValidator 按 path segment 拒绝。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已增加不可覆盖 WriteACL deny：world_facts 禁止主体认知字段，knowledge_facts 禁止物理世界字段。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已要求 WorldSnapshot 保存和恢复时保留 `world_facts`、`knowledge_facts`、`system_ledger` 边界。

工程关闭剩余项：

- 实现 world_facts、knowledge_facts、system_ledger 命名空间。
- 实现世界事实禁止主体认知字段测试。
- 实现知识事实禁止物理世界字段测试。
- 实现 Snapshot 恢复后的命名空间校验。
- 实现 AgentObservationSnapshot 只读投影校验。
- 实现文档/schema 扫描测试，确保 world_facts canonical schema 不再声明 `known_to_player` 或其他主体认知字段。

### P0-12 生成器输出清单没有统一协议

状态：`open`

设计修复状态：`completed`

问题：空间、地形、水文、生态、资源、历史、聚落、物品、天气、环境、危险、障碍和初始知识各自使用“输出”描述，但缺少统一 envelope。实现时可能出现生成器直接写 `WorldState`、候选被运行时消费、世界事实和知识事实混在同一输出、随机流和输入 hash 无法审计的问题。

证据来源：[世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md)、[世界集合与影响规则](./00-architecture/world-collection-influence-rules.md)、[气候地形形成规则](./02-world-model/climate-terrain-formation-rules.md)、[自然生态与资源规则](./02-world-model/natural-ecology-rules.md)、[历史来历与世界痕迹规则](./02-world-model/world-origin-history-rules.md)。

影响：相同 seed 和版本无法保证同一生成输出；生成器边界无法机器校验；EventLog 和 Snapshot 不能证明某个世界事实来自哪个生成阶段。

关闭条件：必须定义并实现：

```text
WorldGenerationManifest
GenerationStageContract
GeneratorOutputEnvelope
GeneratorOutputItem
GenerationOutputValidator
```

所有生成器必须返回 `GeneratorOutputEnvelope`。候选、世界事实、知识事实、事件草案和快照引用必须分桶。Envelope 必须通过 FieldSpec、FieldOwnership、WriteACL、目标实体 validator 和 output hash 校验后才能提交。

设计修复结果：

- 已新增 [世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md)。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已新增生成输出集合和 `generation_audit` 权威域。
- 已将 `WorldGenerationManifest`、`GenerationStageContract`、`GeneratorOutputEnvelope`、`GeneratorOutputItem` 加入 EntityAuthorityDomain、FieldOwnership 和 WriteACL。
- 生成阶段顺序已改为每个阶段输出 `GeneratorOutputEnvelope`，再由 `GenerationOutputValidator` 和 `GenerationCommitter` 提交。
- `GenerationStageContract.reads[]` 已统一为 `GenerationInputRef`，可以声明 world_fact、knowledge_fact、system_ledger、candidate、content_pack、event_boundary 和 snapshot_ref 输入。
- `GeneratorOutputEnvelope` 已补齐 `snapshot_refs` bucket；candidate、world_fact、knowledge_fact、event_draft 和 snapshot_ref bucket 都必须只包含 `GeneratorOutputItem`。
- `event_drafts` 已从自由格式改为 `GeneratorOutputItem(output_class=event_draft)`；`snapshot_refs` 使用 `GeneratorOutputItem(output_class=snapshot_ref)`。
- 生成阶段 operation 已收窄为 `create`、`update`、`deactivate`、`materialize`、`derive`，禁止 `propose`、`project_read` 和 `delete_for_migration`。
- [知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md) 已将 `GenerationStageContract`、`GeneratorOutputEnvelope` 和 `GeneratorOutputItem` 放入 `AuthoritativeWorldState.system_ledger`。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已要求 Snapshot 保存和恢复 `system_ledger.generation_audit`。
- 测试清单已新增生成器 envelope、世界事实/知识事实分桶、WriteACL 校验和 manifest hash 稳定性测试。

工程关闭剩余项：

- 实现 manifest schema 和 stage contract schema。
- 实现 35 个生成阶段的 canonical JSON 或等价机器可加载实例。
- 实现每个 `GenerationStageContract.reads[]` 和 outputs bucket 的完整 schema。
- 改造所有生成器返回 `GeneratorOutputEnvelope`。
- 实现 `GenerationOutputValidator`。
- 实现读取未完成阶段、跨阶段越权读取、候选被 runtime resolver、AI 或 UI 消费等非法情况的机器校验。
- 实现每个阶段的 input hash、output hash、candidate_set_hash 和 manifest hash 固定计算样例。
- 实现并行执行与串行执行得到同一阶段 hash 的验收样例。
- 实现同 seed、同版本 manifest hash 稳定性测试。
- 实现 `event_drafts` 和 `snapshot_refs` 必须使用 `GeneratorOutputItem` 结构的 schema 测试。
- 实现生成阶段 operation 子集校验。

## 当前 P1 问题

### P1-01 时间区间、天气链和残留环境效果不完整

状态：`open`

设计修复状态：`completed`

问题：天气过期使用“超过 until”而未定义端点；active weather 没有同 Region 唯一性、连续性和父子区间约束；EnvironmentState 只有日内分钟，无法区分不同日期；雨停后 wet/muddy/slippery 的残留没有独立来源和到期状态。

关闭条件：统一使用绝对整数世界分钟和半开区间 `[start, end)`；每个 Region 在任意时间恰好有一个基础天气片段；局部覆盖必须有明确优先级和父级生命周期；残留效果必须使用带来源、开始、结束和衰减规则的状态表示，或可从保留历史纯函数派生。

设计修复结果：

- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已新增 `GameTimeInterval`，所有运行时有效期统一为绝对整数世界分钟和半开区间 `[start_world_minute, end_world_minute)`。
- `WorldTimeState` 已新增 `clock.absolute_minute`，并要求 `minute_of_day = absolute_minute % 1440`。
- `WeatherState` 已新增 `coverage_priority`，并规定 Region 基础天气在任意 absolute_minute 恰好命中一个 `base_region` 片段；同 Region 基础天气必须连续且不重叠。
- 局部 `scope=world_chunk` 天气覆盖必须引用父级 Region WeatherState，且生命周期必须完全落在父级区间内。
- 已新增 `EnvironmentResidualEffectState`，用于表达雨停、雪停、风暴结束、泼水、燃烧、异常场消退后的 wet/muddy/slippery/snow_covered/fast_water 等残留。
- 已新增环境残留来源映射、衰减规则表、残留状态闭集和 validator 要求。
- [气候、地形、生物群系与天气形成规则](./02-world-model/climate-terrain-formation-rules.md) 已同步 WeatherFormation 输出结构，禁止继续使用旧式 `from_day/from_minute_of_day/until_day/until_minute_of_day`。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已把 `EnvironmentResidualEffectState` 纳入气候时间天气集合、`environment_derivation` 权威域、CanonicalEntitySchemaRegistry、FieldOwnership、WriteACL 和运行时影响链。
- [知识、发现与事件知情规则](./03-runtime/world-knowledge-rules.md) 已把 `EnvironmentResidualEffectState` 明确列入 `world_facts`，避免与知识状态混写。

工程关闭剩余项：

- 实现 `GameTimeInterval` schema 和旧字段拒绝测试。
- 实现 `WorldTimeState.clock.absolute_minute` 与 `minute_of_day` 一致性校验。
- 实现 Region 基础天气唯一性、连续性和不重叠校验。
- 实现局部天气父级生命周期和优先级冲突校验。
- 实现 `EnvironmentResidualEffectState` schema、来源映射、衰减规则和重叠区间校验。
- 改造 `WeatherService.advance`，按半开区间边界逐段生成 WeatherChanged 事件。
- 改造 `EnvironmentDeriver`，在天气结束后创建、衰减或过期残留，并用当前 WeatherState + active 残留派生 EnvironmentState。
- 补齐 `test_game_time_interval_rejects_legacy_valid_for_fields`、`test_weather_base_region_unique_per_region_minute`、`test_weather_local_override_must_fit_parent_interval`、`test_environment_state_wet_after_rain_requires_residual_effect` 等回归测试。

### P1-02 数值、单位、容量和重量缺少守恒规则

状态：`open`

设计修复状态：`completed`

问题：容器容量同时使用 liter、kg、slot；内容既可以存在于 `components.container.contents`，也可以作为 inside_object 子对象；`physical.weight_kg` 未说明是皮重还是总重。当前规范也出现 `temperature_offset=-0.1` 与“所有 base field 为 0 到 1”的直接冲突。

关闭条件：每个数值字段必须声明单位、上下界、整数/定点精度和端点语义；容器必须定义各类内容的容量占用和质量换算；总重量使用统一递归公式；所有转换在同一事务中保持源减量、目标增量和允许损耗守恒。

设计修复结果：

- [WorldObject 规则](./02-world-model/world-object-rules.md) 已明确不新增 `Container` EntityType，只演进 `WorldObject.components.container`。
- `physical.weight_kg` 已迁移为 `physical.tare_weight_kg`；当前总重改由 `WeightDeriver` 写入 `derived.total_weight_kg`。
- 容器容量从旧 `{amount, unit}` 改为多维容量：`capacity.liquid_liters`、`capacity.mass_kg`、`capacity.slot_count`。
- 容器内容分账：数量资源使用 `quantity_contents`；离散物品使用父容器 `contained_object_ids`。
- `inside_object` 已降级为旧版迁移字段；新状态中被包含对象使用 `placement.kind=contained_by_parent`，父容器由 `contained_object_ids` 反查。
- 物品移动只能通过 `ContainmentTransferResolver.move_object` 原子执行；数量资源转移只能通过 `QuantityTransferResolver.move_quantity_resource` 原子执行。
- [气候、地形、生物群系与天气形成规则](./02-world-model/climate-terrain-formation-rules.md) 已把 `temperature_offset` 从 `base_fields` 移出，改为 `local_climate.temperature_offset_c`。
- [字段域与注册表规则](./01-governance/field-domain-registry-rules.md) 已补 P1 数值字段的 unit、range、precision 和 derived 字段声明。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已补 `WeightDeriver`、`ContainerOccupancyDeriver`、`ContainmentTransferResolver`、`QuantityTransferResolver` 的 FieldOwnership/WriteACL 和运行链路。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已补 `ObjectDerivedPhysicalChanged`、`ContainerObjectTransferred`、`QuantityResourceTransferred` 事件类型。
- [自然生态与资源规则](./02-world-model/natural-ecology-rules.md) 已把 `refill_water` 从直接修改旧 `contents` 改为调用 `QuantityTransferResolver.move_quantity_resource` 写入 `quantity_contents`。

工程关闭剩余项：

- 实现 WorldObject schema migration：`weight_kg -> tare_weight_kg`、`contents -> quantity_contents`、`inside_object -> contained_by_parent + parent.contained_object_ids`。
- 实现 `WeightDeriver` 和 `ContainerOccupancyDeriver`。
- 实现 `ContainmentTransferResolver.move_object` 原子事务。
- 实现 `QuantityTransferResolver.move_quantity_resource` 原子事务和守恒校验。
- 实现 `ResourceMassRegistry` / `ObjectSlotRule`，用于质量、液体体积和槽位换算。
- 实现旧 `{capacity.amount, capacity.unit}` 的拒绝或迁移。
- 实现 `base_fields.temperature_offset` 拒绝和 `local_climate.temperature_offset_c` 校验。
- 补齐 `test_move_object_is_atomic_state_transition`、`test_quantity_resource_transfer_conserves_amount`、`test_total_weight_is_derived_recursively`、`test_base_fields_reject_temperature_offset` 等回归测试。

### P1-03 生态种群和资源没有数量守恒

状态：`open`

设计修复状态：`completed`

问题：CreaturePopulation 只有规模分级，CreatureGroup 有整数 count，升级成 CreatureActor 时没有扣减规则；ResourceDeposit 只有 abundance 和 depleted，无法定义单次产量、部分耗尽和 renewable 恢复。

关闭条件：种群必须记录可验证的整数总量、群体占用和 Actor 占用；升级、死亡、迁移和降级必须是原子数量转移。资源必须记录 capacity/current units、提取成本、产出比例、恢复率和上限，并满足非负约束。

设计修复结果：

- [自然生态与资源规则](./02-world-model/natural-ecology-rules.md) 已为 `CreaturePopulation` 增加 `counts.initial_live_count`、`counts.current_live_count`、`counts.reserve_count`，并要求 `current_live_count = reserve_count + sum(active CreatureGroup.count) + count(active CreatureActor)`。
- `CreatureGroup.count`、`CreatureActor.population_id`、`CreatureActor.source_group_id`、`CreatureActor.count_weight` 和生命周期状态已纳入数量守恒规则。
- 已定义 `NaturalResourceStock` 作为 `FloraPatch.stock`、`ResourceDeposit.stock`、`ResourceNode.stock` 的共用库存结构，包含 `capacity_amount`、`current_amount`、提取上下限、产出比例、允许损耗、恢复速率和恢复上限。
- `FloraPatch.state.harvested`、`ResourceDeposit.state.depleted`、`ResourceNode.state.depleted` 已降级为旧存档迁移字段；新状态使用 `derived.harvested` / `derived.depleted`。
- 已定义 `EcologyPopulationTransferResolver`，动物群体生成、拆分、合并、升级 Actor、死亡、迁移都必须原子提交。
- 已定义 `EcologyResourceExtractionResolver`，采集、挖掘、捕鱼、采药、装水必须同时扣减源库存、生成或修改目标资源，并记录允许损耗。
- 已定义 `EcologyRecoveryResolver`，可恢复资源只能按世界时间和恢复上限恢复。
- [字段域与注册表规则](./01-governance/field-domain-registry-rules.md) 已补生态 counts 和 stock 数值字段的单位、范围和精度。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已补 `EcologyPopulationTransferResolver`、`EcologyResourceExtractionResolver`、`EcologyRecoveryResolver`、`EcologyQuantityValidator` 的 FieldOwnership/WriteACL 和运行顺序。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已补生态数量和资源库存相关 EventLog 事件类型。

工程关闭剩余项：

- 实现 `CreaturePopulation.counts`、`CreatureGroup.count`、`CreatureActor` 数量守恒 schema 和 migration。
- 实现 `NaturalResourceStock` schema，并迁移旧 `harvested/depleted/abundance` 依赖。
- 实现 `EcologyPopulationTransferResolver` 原子事务。
- 实现 `EcologyResourceExtractionResolver.extract` 原子事务，并与 `QuantityTransferResolver` 对接装水场景。
- 实现 `EcologyRecoveryResolver`，按 `absolute_minute` 和半开时间区间恢复库存。
- 实现 `EcologyQuantityValidator`，在每次生态相关 StateTransition 后校验不变量。
- 补齐 `test_population_count_conservation_after_group_spawn`、`test_actor_materialization_decrements_group_count`、`test_dead_actor_decrements_live_count_once`、`test_resource_extraction_conserves_stock_and_output`、`test_refill_water_decrements_resource_node_stock_and_increments_container_quantity`、`test_resource_recovery_caps_at_recovery_cap`、`test_legacy_depleted_fields_rejected_for_new_state` 等回归测试。

### P1-04 空间包含关系和入口规则不足

状态：`open`

设计修复状态：`completed`

问题：LocationNode.parent_id 可以指向其他节点，但未要求无环或同 Site；ActorLocation 的 site/node/zone 未要求逐级一致；进入 Site、离开 Site 和 approach Zone 的流程可以绕过入口、出口或 Zone access；移动载具内部空间与固定挂在 chunk 的 Site 模型冲突。

关闭条件：内部父图必须是以 Site 为根的同 Site DAG；entry node、zone、actor location 必须逐级匹配；进入和离开必须经过显式 SiteEntryEdge/Portal；P0 要么禁止可进入载具移动，要么引入从载具 placement 派生世界根的 MobileSite。

设计修复结果：

- [地点与空间规则](./02-world-model/location-space-rules.md) 已将修复重点从“生成后检查所有不一致”改为“生成时由 `PlaceHierarchyRegistry` 和 `LocationChildGenerationContext` 限制子地点类型”。
- 已定义 `PlaceHierarchyRegistry`：每个 `place_type` 声明 `hierarchy_depth`、`allowed_child_types`、`allowed_child_count_range` 和 `allowed_zone_types`。
- 已定义 `LocationChildGenerationContext`：生成子地点时由系统提供 parent、allowed child set 和 id_prefix；LLM 只能建议 `child_type/name/features`，不能自由写最终 `site_id/node_id/zone_id/parent_id`。
- 已定义 `SiteBoundaryEdge`，用于表达 `world_chunk <-> site_node` 的显式入口/出口；`Site.parent_chunk_id` 只保留物理锚点语义，不得被 `enter_site/leave_site` 当作隐式传送规则。
- `enter_site` 已改为通过 `SiteBoundaryResolver` 读取 `SiteBoundaryEdge(edge_type=site_entry)` 结算。
- `leave_site` 已改为通过 `SiteBoundaryResolver` 读取 `SiteBoundaryEdge(edge_type=site_exit)` 结算。
- `approach` 已改为通过 `ZoneAccessResolver` 检查 `Zone.access`；`search` 与 `approach` 共用同一访问检查。
- `ActorLocation` 已明确不能由 LLM proposal、DM 文本或通用 patch 自由拼接，只能由移动相关 resolver 根据边和 zone access 生成。
- [WorldObject 规则](./02-world-model/world-object-rules.md) 已明确 P1 禁止可进入载具移动：`vehicle_profile.entry_node_ids` 非空时，`mobility_state` 必须为 static、disabled 或 anchored；可移动载具不能拥有内部 LocationNode / Site。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已将 `SiteBoundaryEdge`、`PlaceHierarchyRegistry`、`LocationChildGenerationContext` 纳入 canonical schema、FieldOwnership、WriteACL 和运行结算顺序。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已补 `SiteBoundaryEdgeGenerated`、`ChunkTravelEvent`、`SiteEnteredEvent`、`SiteLeftEvent`、`LocationChangedEvent`、`ZoneChangedEvent` 事件类型。

工程关闭剩余项：

- 实现 `PlaceHierarchyRegistry` 和 `LocationChildGenerationContext` schema。
- 改造地点生成器，使子地点只能来自父级 `allowed_child_types`，最终 ID 由 `LocationMaterializer` 分配。
- 实现 `SiteBoundaryEdge` schema，并迁移 `enter_site/leave_site` 流程。
- 实现 `SiteBoundaryResolver`，禁止直接用 `Site.parent_chunk_id` 改写 ActorLocation。
- 实现 `ZoneAccessResolver`，并让 `approach/search` 共用。
- 实现 `ActorLocationValidator`，校验 `scope=world_chunk` 和 `scope=site_node` 的字段互斥与逐级匹配。
- 实现 P1 载具限制：可进入载具必须 static/disabled/anchored，可移动载具不能有 `entry_node_ids`。
- 补齐 `test_location_child_generation_uses_allowed_child_types`、`test_location_materializer_assigns_child_ids_under_parent_context`、`test_actor_location_cannot_be_llm_written`、`test_enter_site_requires_site_boundary_entry_edge`、`test_leave_site_requires_site_boundary_exit_edge`、`test_approach_zone_checks_zone_access`、`test_search_and_approach_share_zone_access_resolver`、`test_enterable_vehicle_must_be_static_disabled_or_anchored`、`test_movable_vehicle_cannot_have_entry_node_ids` 等回归测试。

### P1-05 Catalog、registry、规则和快照版本不足

状态：`resolved`

设计修复状态：`completed`

问题：Materializer 只说明大致合并顺序，没有定义对象深合并、数组替换或并集、去重和实例 ID；Snapshot 只记录部分 schema version 和 content pack ID，没有固定 registry、规则与内容摘要。

关闭条件：Materializer 必须是版本化纯函数，规定所有 merge 和排序规则；运行态实体保存 pack/catalog/version provenance；WorldState、EventLog 和 Snapshot 固定 `schema_version`、`registry_hash`、`rule_bundle_hash`、`content_pack_hash`，升级只能经过迁移事件。

设计修复结果：

- 新增 [内容包、Catalog 与物化版本规则](./05-content-packs/content-pack-materialization-rules.md)，定义 `ContentPackEnvelope`、`CatalogEnvelope`、`ContentMaterializationContext`、`MaterializationProvenance`、canonical hash、合并规则、实例 ID 和迁移规则。
- [内容包说明](./05-content-packs/README.md) 已要求 catalog 必须包含 `schema_version/content_pack_id/content_pack_version/kind/catalog_version`，Materializer 必须是版本化纯函数。
- [通用小物件 catalog](./05-content-packs/catalogs/generic-item-catalog.json) 和 [容器 catalog](./05-content-packs/catalogs/container-catalog.json) 已补 `content_pack_version` 和 `catalog_version`。
- [WorldObject 规则](./02-world-model/world-object-rules.md) 已将运行时对象来源从旧 `source` 字符串升级为 `provenance`，并要求 content pack 物化对象记录 pack、catalog、materializer、schema、registry、rule bundle 和 content pack hash。
- [自然生态与资源规则](./02-world-model/natural-ecology-rules.md) 已要求动物、植物、自然资源 catalog 也使用同一 `CatalogEnvelope` 和 provenance 规则。
- [字段域与注册表规则](./01-governance/field-domain-registry-rules.md) 已补 RegistryBundle 和 RuleBundle 版本规则，明确 `registry_hash` 与 `rule_bundle_hash` 的覆盖范围。
- [世界生成输出清单规则](./00-architecture/world-generation-manifest-rules.md) 已要求 content_pack input 记录 pack/catalog 版本，Materializer 阶段输出 `ContentMaterializationContext`，物化实体携带同一 `materialization_id` 的 provenance。
- [静态世界运行规则](./03-runtime/static-world-runtime-rules.md) 已定义 `WorldState.version_lock`、`EventLogEntry.version_context` 和 `WorldSnapshot.version_lock`，并要求版本不一致时必须走迁移流程。
- [世界集合与影响规则](./00-architecture/world-collection-influence-rules.md) 已将内容包物化规则纳入 owner、FieldOwnership、WriteACL 和跨集合影响边界。

工程剩余事项：

- 实现 `CatalogEnvelopeValidator` 和 `ContentPackHashCalculator`。
- 实现 `ContentMaterializationContext` 构造器和 materializer 纯函数协议。
- 实现 `MaterializationProvenance` 写入和 `WorldObjectValidator` 校验。
- 实现 `WorldState.version_lock`、`EventLogEntry.version_context`、`WorldSnapshot.version_lock` schema。
- 实现 Snapshot 恢复时的 version_lock 对比和迁移入口。

必须补齐的回归测试：

- `test_catalog_envelope_requires_versions`
- `test_catalog_payload_kind_must_match`
- `test_materializer_is_stable_across_dict_order`
- `test_materializer_is_stable_across_thread_count`
- `test_materializer_id_uses_instance_key_not_iteration_order`
- `test_materialized_entity_requires_provenance`
- `test_provenance_hashes_match_world_version_lock`
- `test_eventlog_version_context_matches_world_version_lock`
- `test_snapshot_version_lock_matches_world_version_lock`
- `test_snapshot_rejects_version_lock_mismatch_without_migration`
- `test_schema_migration_creates_before_and_after_snapshots`
- `test_migration_cannot_change_version_lock_without_eventlog`

### P1-06 各领域形成规则仍是部分设计

状态：`open`

设计完成度：`partial_design`

问题：世界生成阶段已经确定“先生成什么、读取什么、输出什么”，但部分领域还没有把“为什么会形成这个结果”写成足够精确的规则。这里的形成规则包括气候、地形、水文、生物群系、资源、植物、动物、聚落、Site、LocationNode、WorldObject、历史候选和社会状态等。

影响：实现可以自行补充假设，但不同实现会用不同阈值、权重、fallback 或冲突处理得到不同世界。即使 P0 DAG 合法，相同 seed 和版本也可能无法得到同一 canonical WorldState。

当前已完成：

- 已确定这些领域在 P0 世界生成 DAG 中的位置。
- 已确定候选、权威实体、EventLog 草案、snapshot 引用和审计输出的边界。
- 已明确生成器必须使用 `RandomSeedMaterial`、`RandomStreamRef`、`RandomDrawRef` 和 `GeneratorOutputEnvelope`。
- 已明确候选实体不能被 runtime resolver、AI 或 UI 直接消费。

关闭条件：每个 formation rule 必须补齐函数签名、输入字段、输出字段、参数表、冲突处理、fallback、validator 条件和最小回归测试。没有补齐前，对应领域只能做验证性原型，不能冻结长期存档格式。

设计关闭剩余项：

- 每类候选的数值参数表、取值范围、默认值和版本。
- 形成条件的明确阈值。例如什么坡度、湿度、海拔和邻接水体组合会产生沼泽、湿地、山地、河谷或特定 biome tag。
- 多个规则同时命中时的优先级、合并规则和拒绝规则。
- 没有候选命中时的 fallback 行为。
- 每个 Region / WorldChunk 的最小、最大和目标数量规则，例如资源点数量、植物 patch 数量、动物种群数量、Site 数量。
- 跨领域约束，例如历史候选如何改变资源权重、聚落如何影响道路或 Site，但不能反向破坏已提交空间基础。

### P1-07 可执行数值算法未完成

状态：`open`

设计完成度：`design_incomplete`

问题：确定性随机协议已经定义了“随机数怎么可重放”，但还没有完整定义“这些随机数怎样变成气候、地形、水文、生态和聚落结果”。Seed 负责抽样可重放；数值算法负责把输入、参数和抽样结果变成可验证世界事实。

影响：两个实现即使使用相同 `drp.v1`、相同 seed、相同 content pack 和相同 stage contract，也可能因为公式、舍入、边界处理或重采样策略不同而生成不同世界。

当前已完成：

- 已规定 P0 使用 `drp.v1`、HMAC-SHA256、canonical JSON、稳定候选排序、整数权重和稳定 tie-break。
- 已拆分 raw fields、smoothing、terrain、hydrology、local climate、chunk biome 和 region biome 的阶段顺序。
- 已禁止使用本地 seed、浮点概率或没有版本的口头 rarity 概率。

关闭条件：所有数值算法必须声明单位、范围、精度、舍入规则、稳定排序、tie-break、最大重采样次数和失败行为。任何使用浮点的实现都必须规定 canonical quantization，否则不能进入可重放基线。

设计关闭剩余项：

- `ChunkBaseRawFieldsCandidate` 的具体生成公式。
- `ChunkBaseFieldSmoothing` 的邻接核、边界处理、迭代次数和定点精度。
- terrain 分类公式，例如 elevation、slope、wetness、roughness 如何映射为 terrain type。
- hydrology 路由、河流形成、湖泊/湿地形成和排水约束。
- local climate 修正规则，例如高度、水体、植被、风向如何影响温度、湿度和风。
- biome tag 推导矩阵和冲突处理。
- weather 初始状态和转移权重核。
- resource/flora/fauna 密度、数量、恢复率和 rarity 权重到实际数量的转换。
- settlement/site/object placement 的评分函数、拒绝采样上限和 fallback。

### P1-08 失败恢复与断点续生成尚未设计

状态：`open`

设计完成度：`not_designed`

问题：当前文档定义了正常生成路径，但还没有定义生成过程中断、校验失败、程序崩溃、重复提交或升级规则版本时如何继续。没有这部分，长流程生成只能依赖“一次跑完”，不能支持可靠恢复。

影响：验证性原型可以从头重跑；但只要系统声明支持生产级世界生成、断点续生成或长流程可靠恢复，就必须解决该问题。否则重复运行同一阶段可能造成候选重复、manifest hash 冲突、随机抽样漂移或半提交状态。

关闭条件：必须定义 `GenerationRunState`、`GenerationStageRunState`、checkpoint schema、resume 协议、重试规则、回滚规则和崩溃注入测试。如果 P0 明确只支持一次性验证性原型，本项可以被降级为当前版本外的 `accepted_limited_scope`，但必须写明不支持断点续生成。

设计关闭剩余项：

- 生成阶段状态机，例如 `pending -> running -> generated -> validated -> committed`，以及 `rejected`、`failed`、`rolled_back` 的语义。
- checkpoint 写入时机和内容。
- `resume_token`、`attempt_id`、`idempotency_key`、`stage_run_id` 和 output hash 的关系。
- 一个阶段失败后，哪些 random draw 可以保留，哪些候选必须作废。
- `atomic_commit_group_id` 失败时如何回滚或重试。
- 重复执行同一 stage 时如何判定是幂等成功、重复提交、hash 冲突还是需要人工干预。
- 规则版本或 content pack 版本变化后，已完成阶段是否可复用。
- 生成审计损坏、缺失或 hash 不一致时的拒绝和修复策略。

## 系统设计必须满足的条件

以下条件是跨层硬约束。任何子系统设计不得通过降低 Validator 严格度或增加隐式默认值绕过它们。

### 条件 A：结构闭合

1. 每个权威 EntityType 只有一个 canonical schema 和一个 owner 文档。
2. 每个字段都有完整 FieldSpec，不依赖字段短名猜测语义。
3. 每个引用都有明确目标类型和命名空间。
4. 每个 enum、registry、rule_id、event_type 和 affordance 都有机器可读闭集或版本化注册表。
5. `additionalProperties=false` 下的示例必须能通过自己的 schema 和 Validator。

验收证明：

```text
所有 schema 可以编译。
所有当前示例和 catalog 可以通过语义校验。
不存在同一 EntityType 的冲突定义。
不存在未声明字段、tag、rule_id、event_type 或 affordance。
```

### 条件 B：唯一权威与最小写权限

1. 每个权威字段有唯一 owner 和允许 producer 集合。
2. 每个 rule_id 只能修改 WriteACL 明确允许的 entity/path/op。
3. Catalog、Projection、DM 文本和 AI proposal 不是权威状态。
4. Derived 字段只能由指定 Deriver 写入。
5. 同一事实不能在多个字段中独立维护；其他表达必须是派生投影。

验收证明：任意状态变化都能回答“谁、基于什么输入、使用哪个版本规则、修改哪个字段、写入哪个事件”。

### 条件 C：确定性与可复现

必须满足：

```text
Generate(seed, rule_bundle_hash, content_pack_hash) -> canonical WorldState
Replay(snapshot, ordered events) -> canonical WorldState
```

相同输入必须产生相同 canonical hash，不受线程数、遍历顺序、机器平台、字典顺序、缓存访问历史和失败重试影响。

验收证明：顺序扰动测试、并行度扰动测试、重复运行测试和跨进程 hash 测试结果一致。

### 条件 D：原子状态转换与可靠重放

1. 命令、前置条件、状态变化和 EventLog 必须作为一个原子提交处理。
2. 每个命令具有幂等键和 expected sequence/revision。
3. 日志中的 create 必须携带完整实体；update 必须使用确定的 patch 语义。
4. 每次提交后运行完整 post-state Validator，而不是只校验单个新值。
5. Snapshot 只能建立在已提交序列边界，哈希必须使用规范化序列化。

验收证明：在提交任意步骤注入崩溃后，系统只能恢复到提交前或提交后，不能出现中间状态。

### 条件 E：图模型可计算

1. 空间图使用有向 arc；双向关系显式展开。
2. 可通行 arc 的成本有限且大于零。
3. 动态成本必须绑定 actor、状态快照和出发时间，并满足所选路径算法的前提。
4. 可达性、几何邻近和感知邻近分别计算。
5. 父子包含图必须无环并保持同一空间根。
6. 距离区间无重叠，blocked 路径不返回有限通行时间。

验收证明：图连通性、反向通行、负成本拒绝、稳定最短路、父图环和跨 Site 非法边均有测试。

### 条件 F：时间与状态机连续

1. 所有运行时区间使用绝对时间和 `[start, end)`。
2. 同一 scope 的状态片段不得重叠或留空洞，除非显式定义 fallback。
3. 状态转移必须来自闭合转移图和确定的概率核或确定规则。
4. 长时间跳转必须等价于逐片段推进。
5. 临时效果必须有来源、生命周期和确定性衰减。

验收证明：跨午夜、恰好位于端点、一次长跳与多次短跳、局部覆盖跨父天气边界等测试结果一致。

### 条件 G：派生过程收敛且与顺序无关

1. 每个 derived state 有唯一 producer、完整输入集合和输入 revision/hash。
2. Deriver 重复执行必须幂等。
3. 多来源影响必须由唯一 reducer 一次性聚合全部 active source。
4. Deriver 不能依赖自己的最终输出证明自身仍应存在。
5. 派生实体使用稳定 identity key，并采用 desired-set reconciliation 执行 create/update/deactivate。

验收证明：以不同合法顺序运行独立 Deriver，最终 canonical state 必须一致。

### 条件 H：数量、单位和资源守恒

1. 所有数值有单位、范围和精度。
2. 物品转移、资源采集、容器装填、货币交易和生物升级使用原子守恒式。
3. 数量和容量不能为负，输出不能超过来源可用量或目标容量。
4. renewable 资源恢复使用绝对时间、上限和可重放规则。
5. 分级字段可以用于投影，但不能替代需要结算的权威数值。

验收证明：重复采集、并发购买、Actor 升级、容器嵌套和部分消耗不能复制或丢失资源。

### 条件 I：ContentPack 物化是版本化纯函数

1. Catalog 只提供候选和默认值，不直接写权威状态。
2. 合并顺序、对象深合并、数组规则、去重和稳定排序必须明确。
3. 实例 ID 由稳定输入生成，不依赖运行时遍历顺序。
4. 物化结果必须通过 FieldDomainValidator 和目标实体 Validator。
5. 运行态实体必须保存可追溯到 pack、catalog entry 和版本摘要的 provenance。

验收证明：同一 catalog 在重复物化、不同线程数和不同字典顺序下产生相同实例内容和 ID。

### 条件 J：AI 只能在受控观察与提案边界内工作

1. AI 只读取主体可知的结构化 ObservationSnapshot。
2. 玩家文本、描述和记忆摘要按不可信数据处理，不能成为系统指令。
3. Proposal 使用严格 schema、类型化引用、版本、时效、幂等键和前置条件。
4. AI 自报 confidence 不能覆盖硬规则或获得写入优先权。
5. 多个 proposal 的冲突由确定性 Resolver 基于权威状态和资源约束解决。
6. 社会反馈必须有因果去重、上限、冷却、衰减和滞回。

验收证明：过期、重复、提示注入、隐藏事实、群体/NPC 冲突和反馈循环测试均不能绕过权威边界。

### 条件 K：设计可验证并支持迁移

1. 每条硬规则至少有一个正例、一个反例和一个边界测试。
2. 每个 P0/P1 问题必须有回归测试后才能关闭。
3. Schema、registry 和规则版本变化必须提供显式迁移。
4. 迁移前后创建 Snapshot，并验证重放后的 canonical hash。
5. 文档、schema、registry、规则表和测试必须在同一变更中保持一致。

## 实现准入门禁

### Gate 0：设计闭合

必须满足：

- 本文所有 P0 问题均为 `resolved` 或确实移出版本范围的 `accepted_limited_scope`。
- 没有未决内容、含糊规则或互相冲突的 active 规则。
- 生成 DAG、AuthorityDomain、FieldSpec、WriteACL 和 canonical schema 已确定。

未通过 Gate 0 时，只允许验证性原型，不允许冻结数据库、存档或公共 API。

### Gate 1：Schema 与 Registry 闭合

必须满足：

- 所有 schema、enum、registry、tag、rule_id、event_type 和 affordance 可被机器加载。
- 所有当前文档示例和 catalog 通过语义 Validator。
- 所有 reference、ID namespace 和 discriminated union 校验通过。

### Gate 2：生成确定性

必须满足：

- 相同 seed、规则摘要和内容包摘要得到相同 WorldState hash。
- 改变遍历顺序和并行度不改变结果。
- Weather、Ecology、Resource 和 Site 候选抽样通过统计与确定性测试。

### Gate 3：事件与恢复

必须满足：

- 任意提交均满足原子性和幂等性。
- 从初始状态或任意 Snapshot 重放得到相同 canonical hash。
- 崩溃注入、重复提交、并发 sequence 冲突和迁移测试通过。

### Gate 4：运行时不变量

必须满足：

- 空间图、时间片、passability、placement、数量和容量不变量持续成立。
- 所有 Deriver 幂等且顺序扰动后收敛到相同状态。
- 缓存内容不影响权威 hash，或缓存被作为确定性物化状态记录。

### Gate 5：AI 社会模拟

必须满足：

- SocialGroupState、NPCState、Proposal 和社会事件 schema 完整。
- 观察边界、冲突仲裁、资源预算、反馈阻尼和安全测试通过。
- 禁用 AI 时，世界底层状态仍可由确定性规则正常运行。

## 推荐修订顺序

1. 重构治理层：FieldSpec、AuthorityDomain、WriteACL、ID namespace、registry version。
2. 统一 EventLog、StateTransition、Snapshot、canonical hash 和迁移协议。
3. 重排世界生成 DAG，并将 `GenerationStageContract`、manifest 和版本化随机协议落成机器可加载 registry。
4. 定义 `GenerationRunState`、checkpoint、resume、重试和回滚协议。
5. 补齐世界生成的领域形成规则、数值算法、参数表、fallback 和冲突处理。
6. 统一 CreatureGroup、ChunkEdge、Portal、WorldObject state 等 canonical schema。
7. 拆分 base/effective passability，并为所有多来源影响定义 reducer。
8. 补齐时间区间、天气核、残留效果、生态和资源守恒。
9. 修正 Catalog affordance/component 契约和 Materializer 纯函数语义。
10. 最后补全 AI 社会状态、ObservationSnapshot、Proposal 和仲裁协议。

该顺序不能倒置。AI、生态或内容包实现不得先于治理、事务、确定性和 canonical schema 自行固化隐式规则。

## 回归测试最低清单

```text
test_every_field_has_orthogonal_field_spec
test_every_authoritative_path_has_one_owner
test_every_rule_write_matches_write_acl
test_generation_graph_is_acyclic
test_generation_stage_contract_registry_is_machine_loadable
test_generation_stage_rejects_uncommitted_reads
test_generation_stage_rejects_candidate_runtime_consumption
test_seeded_generation_is_order_independent
test_seeded_generation_is_parallelism_independent
test_generation_stage_hash_is_parallelism_independent
test_formation_rule_parameters_are_versioned
test_formation_rule_fallback_is_deterministic
test_numeric_algorithm_uses_canonical_quantization
test_chunk_base_smoothing_is_order_independent
test_generation_run_resume_is_idempotent
test_generation_checkpoint_rejects_hash_conflict
test_event_create_contains_complete_entity
test_state_and_event_commit_is_atomic
test_event_replay_matches_canonical_hash
test_snapshot_replay_starts_at_next_sequence
test_canonical_entity_schema_is_unique
test_every_entity_type_has_one_canonical_schema_owner
test_non_owner_doc_cannot_define_authoritative_entity_schema
test_creature_group_schema_owner_is_ecology
test_location_space_creature_group_projection_does_not_write_creature_group_fields
test_chunk_edge_formation_uses_canonical_direction_and_adjacent_fields
test_chunk_edge_relation_field_is_rejected
test_chunk_and_location_edge_direction_is_explicit
test_chunk_edge_is_directed_arc
test_chunk_edge_reverse_requires_separate_edge
test_location_edge_is_directed_arc
test_location_edge_rejects_bidirectional_direction
test_blocked_edge_is_not_used_by_route_resolver
test_open_edge_requires_positive_finite_cost
test_conditional_unmet_edge_has_infinite_effective_cost
test_same_cost_routes_use_edge_id_sequence_tiebreak
test_route_bands_are_half_open_and_non_overlapping
test_geometric_route_and_perceptual_proximity_are_separate
test_blocked_edge_has_no_finite_route_time
test_proximity_bands_do_not_overlap
test_passability_reducer_is_order_independent
test_deriver_is_idempotent
test_derived_entity_reconciliation_does_not_duplicate
test_container_capacity_and_total_weight_are_conserved
test_population_group_actor_counts_are_conserved
test_resource_extraction_cannot_duplicate_output
test_weather_intervals_are_contiguous_and_non_overlapping
test_long_time_jump_matches_segmented_advance
test_surface_effect_decay_is_replayable
test_catalog_materialization_is_deterministic
test_catalog_instance_passes_target_validator
test_ai_proposal_rejects_stale_revision
test_ai_proposal_is_idempotent
test_ai_observation_excludes_hidden_facts
test_ai_feedback_loop_is_bounded
```

## 已确认决策

1. 本文是跨层规范门禁，不是仅供参考的审计记录。
2. P0 未关闭前，当前文档不能作为冻结的实现和长期存档基线。
3. 问题必须在权威设计、schema、registry、规则和测试中共同修复。
4. 系统正确性的核心标准是结构闭合、唯一权威、确定性、原子性、可重放、可收敛和守恒。
5. AI 负责提出社会判断和行动建议，不拥有任何权威状态写权限。
6. 任何实现便利都不能成为绕过不变量、WriteACL 或 EventLog 的理由。
