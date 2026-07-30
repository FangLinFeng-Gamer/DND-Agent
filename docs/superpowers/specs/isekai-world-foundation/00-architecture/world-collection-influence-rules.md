---
doc_id: isekai.world_collection_influence_rules
status: active
layer: architecture
owner: architecture
created_at: 2026-07-11
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.content_pack_materialization_rules
provides:
  - WorldCollectionRegistry
  - CanonicalEntitySchemaRegistry
  - WorldGenerationManifestRegistry
  - AuthorityDomain
  - EntityAuthorityDomain
  - FieldOwnership
  - WriteACL
  - PassabilityReducer
  - cross_collection_influence_rules
  - runtime_derivation_chain
---

# 异世界模式世界集合与影响规则

## 背景

世界底座已经定义了空间、地形、水文、气候、天气、生态、资源、对象、危险、障碍、事件日志和 AI proposal。若这些内容只作为零散 schema 存在，开发实现时会很容易把“天气影响世界”“生态影响资源”“对象产生障碍”写成临时逻辑。

本设计定义世界中的大集合、集合之间的影响边界、集合内部的允许状态转化，以及所有影响必须经过的 Deriver / Resolver。

## 目标

- 明确当前所有内容属于哪个世界大集合。
- 明确集合之间只能通过哪些规则器产生影响。
- 明确集合内部允许哪些状态转化。
- 明确哪些变化必须形成 StateTransition，并由 StateTransitionCommitter 生成 EventLog。
- 防止 DM 文本、LLM proposal 或内容包直接绕过规则修改世界。

## 非目标

- 不新增具体世界内容。
- 不定义新的物品、动物、植物、地形或天气。
- 不做复杂生态模拟、社会模拟或物理模拟。
- 不替代各子文档的数据结构细节。

## 核心原则

### 1. 集合不能随意互相写状态

一个集合不能直接修改另一个集合的权威状态。跨集合影响必须通过 Deriver、Resolver、Validator、StateTransition 和 StateTransitionCommitter，最终由 EventLog 记录。

同一集合内部也不能随意写字段。所有权威写入必须同时通过 `FieldOwnership` 和 `WriteACL`。

### 2. 生成规则和运行时规则分开

世界生成阶段负责“世界初始如何形成”。运行时阶段负责“时间推进、行动结算或规则事件发生后，世界如何变化”。

### 3. 影响链必须可追踪

任何跨集合影响都必须能回答：

```text
输入事实是什么？
使用了哪个规则器？
输出了哪个实体或状态？
写了哪条 EventLog？
哪些投影需要刷新？
```

### 4. LLM 只能提出 proposal

LLM 可以建议某个集合发生变化，但不能直接写 WeatherState、WorldObject、HazardSource、ObstacleSource、EventLog 或任何权威状态。

### 5. 写权限默认拒绝

集合归属只能用于架构分组，不能作为写权限。任何 rule、resolver、deriver、materializer、migration 或 test fixture 写权威状态时，都必须按 `rule_id + EntityType + FieldPath + operation` 查询 `WriteACL`。未声明即拒绝。

## 世界大集合

| 集合 | 包含内容 | 权威文档 | 说明 |
| --- | --- | --- | --- |
| 字段域集合 | enum、registry、reference、numeric_range、tag registry | `01-governance/field-domain-registry-rules.md` | 约束所有字段值是否合法。 |
| 空间集合 | World、Region、WorldChunkGrid、WorldChunk、ChunkEdge、RegionFeature、Settlement、TerrainFeature、Site、LocationNode、Zone、LocationEdge、SiteBoundaryEdge、ObjectPlacement、ActorLocation | `02-world-model/location-space-rules.md` | 承载世界中所有对象、生态、资源、危险和障碍。 |
| 地形水文集合 | elevation、slope、landform、ground、water_presence、river、pond、well | `02-world-model/climate-terrain-formation-rules.md` | 定义世界物理底板。 |
| 气候时间天气集合 | ClimateProfile、WorldTimeState、WeatherState、EnvironmentState、EnvironmentResidualEffectState | `02-world-model/climate-terrain-formation-rules.md`、`03-runtime/static-world-runtime-rules.md` | 定义长期气候、当前时间、短期天气、局部环境和天气结束后的环境残留。 |
| 历史来历集合 | OriginEvent、OriginMetadata、OriginEvidence | `02-world-model/world-origin-history-rules.md` | 定义静态历史来源、证据和世界痕迹。 |
| 生态集合 | BiomeTag、AnimalSpecies、PlantSpecies、FloraPatch、CreaturePopulation、CreatureGroup、CreatureActor | `02-world-model/natural-ecology-rules.md` | 定义生命系统和生态候选。 |
| 自然资源集合 | NaturalResource、ResourceDeposit、ResourceNode | `02-world-model/natural-ecology-rules.md` | 定义非生命自然资源和可采集资源点。 |
| 世界对象集合 | WorldObject、components、placement、physical、state | `02-world-model/world-object-rules.md` | 定义可见、可交互、可移动或可结算对象。 |
| 危险障碍集合 | HazardSource、ObstacleSource、passability override、PassabilityReducer 输出 | `03-runtime/static-world-runtime-rules.md` | 定义风险来源、通行阻挡和最终有效通行派生。 |
| 事件快照集合 | EventLog、WorldSnapshot | `03-runtime/static-world-runtime-rules.md` | 定义权威状态账本和恢复边界。 |
| 生成输出集合 | WorldGenerationManifest、GenerationStageContract、GeneratorOutputEnvelope、GeneratorOutputItem | `00-architecture/world-generation-manifest-rules.md` | 定义世界生成阶段的统一输出清单、阶段契约和审计边界。 |
| 知识认知集合 | KnowledgeState、DiscoveryState、RumorState、SecretState、AgentObservationSnapshot | `03-runtime/world-knowledge-rules.md` | 定义主体知道、发现、误解、传播或隐瞒了什么。 |
| 聚落社会集合 | SettlementProfile、Institution、SocialGroupState、NamedNPCState、ServiceState、ServiceEntitlementState、LawPolicy、EconomyState、SocialPressureState | `02-world-model/settlement-social-world-rules.md` | 定义聚落、群体、具名 NPC、服务、权益、制度、经济与社会压力的权威状态。 |
| AI proposal 集合 | AIDecisionTick、GroupDecisionProposal、NPCActionProposal、ProposalResourceReservation、weather_change proposal | `04-ai-simulation/ai-social-mind-rules.md` | 定义 AI 可以提出什么建议、如何调度和审计，以及不能直接改什么。 |
| 内容包集合 | ContentPackEnvelope、CatalogEnvelope、CatalogEntry、materializer input、MaterializationProvenance | `05-content-packs/content-pack-materialization-rules.md` | 定义可复用内容输入、版本化物化协议和 provenance。 |

本表只是架构分组，不是写权限表。实现不能只凭“目标实体属于某个集合”判断写入是否合法。字段级写入必须继续由 `FieldOwnership` 和 `WriteACL` 判定：同一个实体内部的不同字段可以属于不同权威域，例如 `WorldChunk.coord` 属于空间权威，`WorldChunk.terrain` 属于地形水文权威，`WorldChunk.biome_tags` 属于生物群系派生权威。

## 权威域与字段所有权

### AuthorityDomain

`AuthorityDomain` 是字段所有权的闭集。它表示某类权威状态由哪个系统维护，不等于文档目录或 UI 分组。

P0 `AuthorityDomain` 闭集：

```text
governance
space
terrain_hydrology
climate_terrain_derivation
origin_history
weather_runtime
environment_derivation
ecology
natural_resource
world_object
hazard_obstacle
event_log
snapshot
generation_audit
knowledge_runtime
social_world
ai_proposal
content_pack
projection
```

含义：

| AuthorityDomain | 含义 |
| --- | --- |
| `governance` | 字段域、registry、schema 和校验规则。 |
| `space` | World、Region、WorldChunkGrid、WorldChunk、ChunkEdge、RegionFeature、Settlement、TerrainFeature、Site、LocationNode、Zone、LocationEdge、SiteBoundaryEdge、ObjectPlacement、ActorLocation 的空间身份和连接关系。 |
| `terrain_hydrology` | 地形、水文和基础物理场。 |
| `climate_terrain_derivation` | 由气候、地形、水文和压力派生出的 biome、通行候选等结果。 |
| `origin_history` | 静态历史来源、证据关系和 OriginMetadata 附着。 |
| `weather_runtime` | 当前或短期 WeatherState。 |
| `environment_derivation` | 由时间、天气、环境残留、局部空间、光源、热源派生的 EnvironmentState 和 EnvironmentResidualEffectState。 |
| `ecology` | 植物群落、动物种群和生物活动状态。 |
| `natural_resource` | 自然资源、资源矿床、资源节点和水源状态。 |
| `world_object` | WorldObject 的实例、placement、components、physical 和 state。 |
| `hazard_obstacle` | HazardSource、ObstacleSource、passability override 和 PassabilityReducer effective 输出。 |
| `event_log` | EventLog 追加协议。 |
| `snapshot` | WorldSnapshot 生成和恢复边界。 |
| `generation_audit` | 世界生成阶段输出清单、阶段契约、输出包络、输出项和审计 hash。它属于 `system_ledger`，不是 `world_facts` 或 `knowledge_facts`。 |
| `knowledge_runtime` | 主体知识、发现、流言、秘密和 AI 观察快照。 |
| `social_world` | 聚落、机构、群体、具名 NPC、服务、权益、制度、经济和社会压力的权威状态。 |
| `ai_proposal` | AI decision tick、proposal 和 reservation 的权威 system_ledger；可审计、可重放，但不是 world_facts 或 knowledge_facts。 |
| `content_pack` | ContentPackEnvelope、CatalogEnvelope、CatalogEntry、materializer input 和 provenance 规则。catalog 不是运行时权威 WorldState。 |
| `projection` | Narration/UI/State Projection，只读权威状态。 |

### EntityAuthorityDomain

`EntityAuthorityDomain(EntityType) -> AuthorityDomain` 表示实体身份归属。它只回答“这个实体作为一个整体由哪个域登记”，不代表该实体所有字段都由同一域写入。

P0 最小映射：

| EntityType | EntityAuthorityDomain |
| --- | --- |
| `World` | `space` |
| `Region` | `space` |
| `WorldChunkGrid` | `space` |
| `WorldChunk` | `space` |
| `WorldLayoutCandidate` | `generation_audit` |
| `RegionLayoutCandidate` | `generation_audit` |
| `WorldChunkGridLayoutCandidate` | `generation_audit` |
| `WorldChunkLayoutCandidate` | `generation_audit` |
| `RegionClimateCandidate` | `generation_audit` |
| `ChunkBaseRawFieldsCandidate` | `generation_audit` |
| `ChunkBaseFieldsCandidate` | `generation_audit` |
| `ChunkTerrainCandidate` | `generation_audit` |
| `ChunkHydrologyCandidate` | `generation_audit` |
| `ChunkLocalClimateCandidate` | `generation_audit` |
| `ChunkBiomeCandidate` | `generation_audit` |
| `RegionBiomeCandidate` | `generation_audit` |
| `ChunkEdge` | `space` |
| `RegionFeature` | `space` |
| `Settlement` | `space` |
| `TerrainFeature` | `space` |
| `Site` | `space` |
| `LocationNode` | `space` |
| `Zone` | `space` |
| `LocationEdge` | `space` |
| `SiteBoundaryEdge` | `space` |
| `ObjectPlacement` | `space` |
| `ActorLocation` | `space` |
| `PlaceHierarchyRegistry` | `governance` |
| `LocationChildGenerationContext` | `space` |
| `OriginEvent` | `origin_history` |
| `StaticWorldRuntimeState` | `weather_runtime` |
| `WorldTimeState` | `weather_runtime` |
| `WeatherState` | `weather_runtime` |
| `EnvironmentState` | `environment_derivation` |
| `EnvironmentResidualEffectState` | `environment_derivation` |
| `FloraPatch` | `ecology` |
| `CreaturePopulation` | `ecology` |
| `CreatureGroup` | `ecology` |
| `CreatureActor` | `ecology` |
| `NaturalResource` | `natural_resource` |
| `ResourceDeposit` | `natural_resource` |
| `ResourceNode` | `natural_resource` |
| `WorldObject` | `world_object` |
| `HazardSource` | `hazard_obstacle` |
| `ObstacleSource` | `hazard_obstacle` |
| `EventLogEntry` | `event_log` |
| `WorldSnapshot` | `snapshot` |
| `WorldGenerationManifest` | `generation_audit` |
| `GenerationStageContract` | `generation_audit` |
| `GeneratorOutputEnvelope` | `generation_audit` |
| `GeneratorOutputItem` | `generation_audit` |
| `KnowledgeState` | `knowledge_runtime` |
| `DiscoveryState` | `knowledge_runtime` |
| `RumorState` | `knowledge_runtime` |
| `SecretState` | `knowledge_runtime` |
| `AgentObservationSnapshot` | `knowledge_runtime` |
| `SettlementProfile` | `social_world` |
| `Institution` | `social_world` |
| `SocialGroupState` | `social_world` |
| `NamedNPCState` | `social_world` |
| `ServiceState` | `social_world` |
| `ServiceEntitlementState` | `social_world` |
| `LawPolicy` | `social_world` |
| `EconomyState` | `social_world` |
| `SocialPressureState` | `social_world` |
| `AIDecisionTick` | `ai_proposal` |
| `GroupDecisionProposal` | `ai_proposal` |
| `NPCActionProposal` | `ai_proposal` |
| `ProposalResourceReservation` | `ai_proposal` |
| `ContentPackEnvelope` | `content_pack` |
| `CatalogEnvelope` | `content_pack` |
| `CatalogEntry` | `content_pack` |
| `ContentMaterializationContext` | `generation_audit` |

### CanonicalEntitySchemaRegistry

`CanonicalEntitySchemaRegistry(EntityType) -> owner_doc + canonical_section` 表示某个权威实体只能由一个文档定义 schema。它解决的是“同名实体谁说了算”，不替代 `EntityAuthorityDomain`、`FieldOwnership` 或 `WriteACL`。

规则：

```text
每个权威 EntityType 必须且只能存在一条 CanonicalEntitySchemaRegistry 记录。
owner_doc 是唯一允许定义该 EntityType canonical schema 的文档。
非 owner 文档只能引用该 schema，或声明带后缀的阶段性类型，例如 CreatureGroupProjection、WeatherFormationOutput、ChunkEdgeCandidate。
非 owner 文档不得在 JSON 示例或字段表中重新定义同名权威 EntityType 的字段集合。
provides 中列出的权威 EntityType 必须能在本表中找到唯一 owner_doc。
Candidate、FormationOutput、Projection、Proposal 不是同名权威实体，必须使用独立类型名。
```

P0 canonical schema owner 表：

| EntityType | owner_doc | canonical_section |
| --- | --- | --- |
| `World` | `02-world-model/location-space-rules.md` | `World` |
| `Region` | `02-world-model/location-space-rules.md` | `Region` |
| `WorldChunkGrid` | `02-world-model/location-space-rules.md` | `WorldChunkGrid` |
| `WorldChunk` | `02-world-model/location-space-rules.md` | `WorldChunk` |
| `ChunkEdge` | `02-world-model/location-space-rules.md` | `ChunkEdge` |
| `RegionFeature` | `02-world-model/location-space-rules.md` | `RegionFeature / Settlement / TerrainFeature` |
| `Settlement` | `02-world-model/location-space-rules.md` | `RegionFeature / Settlement / TerrainFeature` |
| `TerrainFeature` | `02-world-model/location-space-rules.md` | `RegionFeature / Settlement / TerrainFeature` |
| `Site` | `02-world-model/location-space-rules.md` | `Site` |
| `LocationNode` | `02-world-model/location-space-rules.md` | `LocationNode` |
| `Zone` | `02-world-model/location-space-rules.md` | `LocationNode / Zone` |
| `LocationEdge` | `02-world-model/location-space-rules.md` | `LocationEdge` |
| `SiteBoundaryEdge` | `02-world-model/location-space-rules.md` | `SiteBoundaryEdge` |
| `PlaceHierarchyRegistry` | `02-world-model/location-space-rules.md` | `PlaceHierarchyRegistry` |
| `LocationChildGenerationContext` | `02-world-model/location-space-rules.md` | `LocationChildGenerationContext` |
| `ObjectPlacement` | `02-world-model/location-space-rules.md` | `ObjectPlacement` |
| `ActorLocation` | `02-world-model/location-space-rules.md` | `ActorLocation` |
| `AnimalSpecies` | `02-world-model/natural-ecology-rules.md` | `AnimalSpecies` |
| `PlantSpecies` | `02-world-model/natural-ecology-rules.md` | `PlantSpecies` |
| `NaturalResource` | `02-world-model/natural-ecology-rules.md` | `NaturalResource` |
| `CreaturePopulation` | `02-world-model/natural-ecology-rules.md` | `CreaturePopulation` |
| `CreatureGroup` | `02-world-model/natural-ecology-rules.md` | `CreatureGroup` |
| `CreatureActor` | `02-world-model/natural-ecology-rules.md` | `CreatureActor` |
| `FloraPatch` | `02-world-model/natural-ecology-rules.md` | `FloraPatch` |
| `ResourceDeposit` | `02-world-model/natural-ecology-rules.md` | `ResourceDeposit` |
| `ResourceNode` | `02-world-model/natural-ecology-rules.md` | `ResourceNode` |
| `WorldObject` | `02-world-model/world-object-rules.md` | `WorldObject` |
| `OriginEvent` | `02-world-model/world-origin-history-rules.md` | `OriginEvent` |
| `OriginMetadata` | `02-world-model/world-origin-history-rules.md` | `OriginMetadata` |
| `StaticWorldRuntimeState` | `03-runtime/static-world-runtime-rules.md` | `StaticWorldRuntimeState` |
| `WorldTimeState` | `03-runtime/static-world-runtime-rules.md` | `WorldTimeState` |
| `WeatherState` | `03-runtime/static-world-runtime-rules.md` | `WeatherState` |
| `EnvironmentState` | `03-runtime/static-world-runtime-rules.md` | `EnvironmentState` |
| `EnvironmentResidualEffectState` | `03-runtime/static-world-runtime-rules.md` | `EnvironmentResidualEffectState` |
| `HazardSource` | `03-runtime/static-world-runtime-rules.md` | `HazardSource` |
| `ObstacleSource` | `03-runtime/static-world-runtime-rules.md` | `ObstacleSource` |
| `EventLogEntry` | `03-runtime/static-world-runtime-rules.md` | `EventLogEntry` |
| `WorldSnapshot` | `03-runtime/static-world-runtime-rules.md` | `WorldSnapshot` |
| `KnowledgeState` | `03-runtime/world-knowledge-rules.md` | `KnowledgeState` |
| `DiscoveryState` | `03-runtime/world-knowledge-rules.md` | `DiscoveryState` |
| `RumorState` | `03-runtime/world-knowledge-rules.md` | `RumorState` |
| `SecretState` | `03-runtime/world-knowledge-rules.md` | `SecretState` |
| `AgentObservationSnapshot` | `03-runtime/world-knowledge-rules.md` | `AgentObservationSnapshot` |
| `SettlementProfile` | `02-world-model/settlement-social-world-rules.md` | `SettlementProfile` |
| `Institution` | `02-world-model/settlement-social-world-rules.md` | `Institution` |
| `SocialGroupState` | `02-world-model/settlement-social-world-rules.md` | `SocialGroupState` |
| `NamedNPCState` | `02-world-model/settlement-social-world-rules.md` | `NamedNPCState` |
| `ServiceState` | `02-world-model/settlement-social-world-rules.md` | `ServiceState` |
| `ServiceEntitlementState` | `02-world-model/settlement-social-world-rules.md` | `ServiceEntitlementState` |
| `LawPolicy` | `02-world-model/settlement-social-world-rules.md` | `LawPolicy` |
| `EconomyState` | `02-world-model/settlement-social-world-rules.md` | `EconomyState` |
| `SocialPressureState` | `02-world-model/settlement-social-world-rules.md` | `SocialPressureState` |
| `WorldGenerationManifest` | `00-architecture/world-generation-manifest-rules.md` | `WorldGenerationManifest` |
| `GenerationStageContract` | `00-architecture/world-generation-manifest-rules.md` | `GenerationStageContract` |
| `GeneratorOutputEnvelope` | `00-architecture/world-generation-manifest-rules.md` | `GeneratorOutputEnvelope` |
| `GeneratorOutputItem` | `00-architecture/world-generation-manifest-rules.md` | `GeneratorOutputItem` |
| `ContentPackEnvelope` | `05-content-packs/content-pack-materialization-rules.md` | `ContentPackEnvelope / CatalogEnvelope` |
| `CatalogEnvelope` | `05-content-packs/content-pack-materialization-rules.md` | `CatalogEnvelope` |
| `CatalogEntry` | `05-content-packs/content-pack-materialization-rules.md` | `CatalogEnvelope` |
| `ContentMaterializationContext` | `05-content-packs/content-pack-materialization-rules.md` | `ContentMaterializationContext` |
| `AIDecisionTick` | `04-ai-simulation/ai-social-mind-rules.md` | `AIDecisionTick` |
| `GroupDecisionProposal` | `04-ai-simulation/ai-social-mind-rules.md` | `GroupDecisionProposal` |
| `NPCActionProposal` | `04-ai-simulation/ai-social-mind-rules.md` | `NPCActionProposal` |
| `ProposalResourceReservation` | `04-ai-simulation/ai-social-mind-rules.md` | `ProposalResourceReservation` |

### FieldOwnership

`FieldOwnership(EntityType, FieldPath) -> AuthorityDomain` 表示某个实体内部字段由哪个权威域维护。字段路径必须使用完整 schema path，不允许只写短字段名。

P0 最小字段所有权：

| EntityType | FieldPath | FieldOwnership |
| --- | --- | --- |
| `World` | `id`、`name`、`seed`、`chunk_size_profiles` | `space` |
| `World` | `version_lock` | `generation_audit` |
| `World` | `active_content_pack_refs` | `content_pack` |
| `World` | `current_actor_locations` | `space` |
| `Region` | `id`、`name`、`type`、`world_id`、`bounds_world`、`grid_id` | `space` |
| `Region` | `climate_profile` | `terrain_hydrology` |
| `Region` | `biome_tags` | `climate_terrain_derivation` |
| `Region` | `danger_tags`、`risk_clocks` | `hazard_obstacle` |
| `Region` | `factions` | `social_world` |
| `WorldChunkGrid` | `*` | `space` |
| `WorldChunk` | `id`、`grid_id`、`coord`、`region_id`、`size_profile`、`site_slots`、`tags` | `space` |
| `WorldChunk` | `base_fields`、`terrain`、`water_presence`、`hydrology` | `terrain_hydrology` |
| `WorldChunk` | `local_climate` | `climate_terrain_derivation` |
| `WorldChunk` | `biome_tags` | `climate_terrain_derivation` |
| `WorldChunk` | `danger_tags`、`risk_tags` | `hazard_obstacle` |
| `ChunkEdge` | `source_chunk_id`、`target_chunk_id`、`direction`、`adjacent` | `space` |
| `ChunkEdge` | `base_passability`、`base_traversal` | `terrain_hydrology` |
| `ChunkEdge` | `effective_passability`、`effective_traversal` | `hazard_obstacle` |
| `LocationEdge` | `source_node_id`、`target_node_id`、`relation`、`portal_object_id`、`direction` | `space` |
| `LocationEdge` | `base_passability`、`base_traversal` | `space` |
| `LocationEdge` | `effective_passability`、`effective_traversal` | `hazard_obstacle` |
| `SiteBoundaryEdge` | `edge_type`、`source`、`target`、`portal_object_id` | `space` |
| `SiteBoundaryEdge` | `base_passability`、`base_traversal` | `space` |
| `SiteBoundaryEdge` | `effective_passability`、`effective_traversal` | `hazard_obstacle` |
| `PlaceHierarchyRegistry` | `*` | `governance` |
| `LocationChildGenerationContext` | `*` | `space` |
| `RegionFeature` | `*` | `space` |
| `Settlement` | `*` | `space` |
| `TerrainFeature` | `*` | `space` |
| `Site` | `id`、`anchor_chunk_id`、`covered_chunk_ids`、`nodes` | `space` |
| `LocationNode` | `id`、`parent_id`、`neighbors`、`zones` | `space` |
| `LocationNode` | `affordances`、`visibility` | `space` |
| `ActorLocation` | `*` | `space` |
| `OriginEvent` | `*` | `origin_history` |
| `StaticWorldRuntimeState` | `world_id` | `space` |
| `StaticWorldRuntimeState` | `version_lock` | `generation_audit` |
| `StaticWorldRuntimeState` | `runtime_state.time_state_id`、`runtime_state.active_weather_state_ids` | `weather_runtime` |
| `StaticWorldRuntimeState` | `runtime_state.active_environment_state_ids`、`runtime_state.active_environment_residual_effect_ids` | `environment_derivation` |
| `StaticWorldRuntimeState` | `runtime_state.active_hazard_ids`、`runtime_state.active_obstacle_ids` | `hazard_obstacle` |
| `StaticWorldRuntimeState` | `runtime_state.latest_event_sequence` | `event_log` |
| `StaticWorldRuntimeState` | `runtime_state.latest_snapshot_id` | `snapshot` |
| `WorldTimeState` | `*` | `weather_runtime` |
| `WeatherState` | `*` | `weather_runtime` |
| `EnvironmentState` | `*` | `environment_derivation` |
| `EnvironmentResidualEffectState` | `*` | `environment_derivation` |
| `FloraPatch` | `*` | `ecology` |
| `CreaturePopulation` | `*` | `ecology` |
| `CreatureGroup` | `*` | `ecology` |
| `CreatureActor` | `*` | `ecology` |
| `NaturalResource` | `*` | `natural_resource` |
| `ResourceDeposit` | `*` | `natural_resource` |
| `ResourceNode` | `*` | `natural_resource` |
| `WorldObject` | `id`、`object_type`、`components`、`placement`、`physical`、`state`、`provenance` | `world_object` |
| `WorldObject` | `derived.total_weight_kg`、`derived.contained_mass_kg`、`derived.occupied_liquid_liters`、`derived.occupied_slot_count` | `world_object` |
| `HazardSource` | `*` | `hazard_obstacle` |
| `ObstacleSource` | `*` | `hazard_obstacle` |
| `EventLogEntry` | `*` | `event_log` |
| `WorldSnapshot` | `*` | `snapshot` |
| `WorldGenerationManifest` | `*` | `generation_audit` |
| `GenerationStageContract` | `*` | `generation_audit` |
| `GeneratorOutputEnvelope` | `*` | `generation_audit` |
| `GeneratorOutputItem` | `*` | `generation_audit` |
| `WorldLayoutCandidate`、`RegionLayoutCandidate`、`WorldChunkGridLayoutCandidate`、`WorldChunkLayoutCandidate` | `*` | `generation_audit` |
| `RegionClimateCandidate`、`ChunkBaseRawFieldsCandidate`、`ChunkBaseFieldsCandidate`、`ChunkTerrainCandidate`、`ChunkHydrologyCandidate`、`ChunkLocalClimateCandidate`、`ChunkBiomeCandidate`、`RegionBiomeCandidate` | `*` | `generation_audit` |
| `ContentPackEnvelope` | `*` | `content_pack` |
| `CatalogEnvelope` | `*` | `content_pack` |
| `CatalogEntry` | `*` | `content_pack` |
| `ContentMaterializationContext` | `*` | `generation_audit` |
| `KnowledgeState` | `*` | `knowledge_runtime` |
| `DiscoveryState` | `*` | `knowledge_runtime` |
| `RumorState` | `*` | `knowledge_runtime` |
| `SecretState` | `*` | `knowledge_runtime` |
| `AgentObservationSnapshot` | `*` | `knowledge_runtime` |
| `SettlementProfile` | `*` | `social_world` |
| `Institution` | `*` | `social_world` |
| `SocialGroupState` | `*` | `social_world` |
| `NamedNPCState` | `*` | `social_world` |
| `ServiceState` | `*` | `social_world` |
| `ServiceEntitlementState` | `*` | `social_world` |
| `LawPolicy` | `*` | `social_world` |
| `EconomyState` | `*` | `social_world` |
| `SocialPressureState` | `*` | `social_world` |
| `AIDecisionTick` | `*` | `ai_proposal` |
| `GroupDecisionProposal` | `*` | `ai_proposal` |
| `NPCActionProposal` | `*` | `ai_proposal` |
| `ProposalResourceReservation` | `*` | `ai_proposal` |

规则：

```text
FieldOwnership 必须覆盖所有权威 schema 字段。
字段路径未登记时默认不可写。
通配符 * 只能用于字段结构完全由同一个权威域维护的实体。
若实体未来出现跨域字段，必须拆出显式 FieldPath，不能继续依赖 *。
FieldOwnership 只说明字段归谁维护，不说明某条规则是否可写；最终还要查 WriteACL。
FieldOwnership 的通配符不能覆盖治理禁用字段。world_facts 的任意字段路径只要命中主体认知字段禁用集，就必须由 FieldDomainValidator 拒绝。
主体认知字段包括 `known_to_player`、`known_by`、`discovered_by`、`seen_by`、`heard_by`、`rumored_by`、`visible_to_subjects`、`npc_memory`、`player_memory` 和 `ai_context`。
玩家、NPC 或群体是否知道空间事实，必须写入 `DiscoveryState` / `KnowledgeState`，不能写入 `WorldChunk`、`ChunkEdge`、`Site`、`LocationNode`、`LocationEdge`、`SiteBoundaryEdge`、`ObjectPlacement`、`ActorLocation` 或 `WorldObject`。
`World.version_lock` 属于生成审计域，用于把当前 WorldState 固定到 schema、registry、rule bundle 和 content pack 版本摘要。
```

### WriteACL

`WriteACL(rule_id, EntityType, FieldPath, operation) -> allow/deny` 是所有权威写入的最终许可表。

P0 `operation` 闭集：

```text
create
update
deactivate
delete_for_migration
materialize
derive
propose
project_read
```

本节 `operation` 是 WriteACL 权限域，用来判断某类规则是否允许写某类字段；它不是 EventLog 的 `changes[].op`。EventLog `change_op` 的唯一权威定义在 [字段域与注册表规则](../01-governance/field-domain-registry-rules.md)，`materialize`、`derive`、`propose`、`project_read` 等上游语义必须在提交前降低为可重放的 `create/update/deactivate` changes，不能直接进入 `changes[].op`。

规则：

```text
默认 deny。
同一写入同时命中宽路径和窄路径时，先取最具体 FieldPath；同等具体度下 deny 优先于 allow。
create 必须覆盖实体创建时写入的所有必填字段。
update / derive 必须逐字段检查 FieldPath。
materialize 只允许从已验证 catalog 生成实体，不允许跳过目标实体 validator。
propose 只能写 AI proposal 集合，不能写权威 WorldState。
project_read 只能读权威状态生成投影，不能写权威状态。
delete_for_migration 只允许 migration_tool 使用，必须进入迁移 StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry。
生成阶段 `GeneratorOutputItem.operation` 只能使用 `create`、`update`、`deactivate`、`materialize`、`derive`；即使全局 WriteACL 支持，生成阶段也必须拒绝 `propose`、`project_read` 和 `delete_for_migration`。
```

P0 最小 ACL：

| rule_id | EntityType | FieldPath | operation | result |
| --- | --- | --- | --- | --- |
| 任意 `rule_id` | 任意 `world_facts` EntityType | 主体认知字段禁用集 | `create/update/derive/materialize` | `deny` |
| 任意 `rule_id` | `KnowledgeState`、`DiscoveryState`、`RumorState`、`SecretState` | 物理世界字段禁用集 | `create/update/derive/materialize` | `deny` |
| `SpatialLayoutCandidateFormation` | `WorldLayoutCandidate`、`RegionLayoutCandidate`、`WorldChunkGridLayoutCandidate`、`WorldChunkLayoutCandidate` | `*` | `derive` | `allow` |
| `RegionClimateCandidateFormation` | `RegionClimateCandidate` | `*` | `derive` | `allow` |
| `ChunkBaseRawFieldsCandidateFormation` | `ChunkBaseRawFieldsCandidate` | `*` | `derive` | `allow` |
| `ChunkBaseFieldSmoothing` | `ChunkBaseFieldsCandidate` | `*` | `derive` | `allow` |
| `TerrainCandidateFormation` | `ChunkTerrainCandidate` | `*` | `derive` | `allow` |
| `HydrologyCandidateFormation` | `ChunkHydrologyCandidate` | `*` | `derive` | `allow` |
| `LocalClimateCandidateDerivation` | `ChunkLocalClimateCandidate` | `*` | `derive` | `allow` |
| `ChunkBiomeCandidateDerivation` | `ChunkBiomeCandidate` | `*` | `derive` | `allow` |
| `RegionBiomeCandidateAggregation` | `RegionBiomeCandidate` | `*` | `derive` | `allow` |
| `SpatialFoundationValidator` | `World`、`Region`、`WorldChunkGrid`、`WorldChunk` | `*` | `create/update/derive/materialize` | `deny` |
| `SpatialFoundationMaterializer` | `World` | `id`、`name`、`seed`、`active_content_pack_refs`、`chunk_size_profiles`、`current_actor_locations`、`version_lock` | `create` | `allow` |
| `SpatialFoundationMaterializer` | `Region` | `id`、`name`、`type`、`world_id`、`bounds_world`、`grid_id`、`climate_profile`、`biome_tags`、`danger_tags`、`factions`、`risk_clocks` | `create` | `allow` |
| `SpatialFoundationMaterializer` | `WorldChunkGrid` | `id`、`region_id`、`size_profile`、`origin_chunk`、`bounds_chunk` | `create` | `allow` |
| `SpatialFoundationMaterializer` | `WorldChunk` | `id`、`grid_id`、`region_id`、`coord`、`size_profile`、`terrain`、`base_fields`、`local_climate`、`biome_tags`、`site_slots`、`tags` | `create` | `allow` |
| `RegionClimateCandidateFormation` | `Region` | `climate_profile` | `create/update/derive` | `deny` |
| `ChunkBaseRawFieldsCandidateFormation`、`ChunkBaseFieldSmoothing` | `WorldChunk` | `base_fields` | `create/update/derive` | `deny` |
| `TerrainCandidateFormation` | `WorldChunk` | `terrain` | `create/update/derive` | `deny` |
| `HydrologyCandidateFormation` | `WorldChunk` | `terrain.water_presence` | `create/update/derive` | `deny` |
| `LocalClimateCandidateDerivation` | `WorldChunk` | `local_climate` | `create/update/derive` | `deny` |
| `ChunkBiomeCandidateDerivation` | `WorldChunk` | `biome_tags` | `create/update/derive` | `deny` |
| `RegionBiomeCandidateAggregation` | `Region` | `biome_tags` | `create/update/derive` | `deny` |
| `StaticChunkEdgeFormation` | `ChunkEdge` | `source_chunk_id`、`target_chunk_id`、`direction`、`adjacent` | `create` | `allow` |
| `StaticTraversalDeriver` | `ChunkEdge` | `base_passability`、`base_traversal` | `derive/update` | `allow` |
| `PassabilityReducer` | `ChunkEdge`、`LocationEdge` | `effective_passability`、`effective_traversal` | `derive/update` | `allow` |
| `PassabilityReducer` | `SiteBoundaryEdge` | `effective_passability`、`effective_traversal` | `derive/update` | `allow` |
| `HazardObstacleDeriver` | `ChunkEdge`、`LocationEdge`、`SiteBoundaryEdge` | `effective_passability`、`effective_traversal` | `derive/update` | `deny` |
| `SettlementAnchorFormation` | `RegionFeature`、`Settlement`、`TerrainFeature` | `*` | `create/update` | `allow` |
| `SitePlacement` | `Site` | `id`、`anchor_chunk_id`、`covered_chunk_ids`、`nodes` | `create` | `allow` |
| `PlaceHierarchyRegistryLoader` | `PlaceHierarchyRegistry` | `*` | `create/update` | `allow` |
| `LocationGenerator` | `LocationChildGenerationContext` | `*` | `create/update` | `allow` |
| `LocationGenerator` | `LocationNode`、`Zone` | `*` | `create/update` | `allow` |
| `LocationGenerator` | `LocationEdge` | `source_node_id`、`target_node_id`、`relation`、`portal_object_id`、`direction`、`base_passability`、`base_traversal` | `create/update` | `allow` |
| `LocationGenerator` | `SiteBoundaryEdge` | `edge_type`、`source`、`target`、`portal_object_id`、`base_passability`、`base_traversal` | `create/update` | `allow` |
| `WorldGenerationOrchestrator` | `World` | `version_lock` | `create/update` | `deny` |
| `MigrationTool` | `World` | `version_lock` | `update` | `allow` |
| 任意 `LLMProposal` | `World` | `version_lock` | `create/update` | `deny` |
| `ChunkTravelResolver` | `World`、`ActorLocation` | `current_actor_locations`、`*` | `update` | `allow` |
| `SiteBoundaryResolver` | `World`、`ActorLocation` | `current_actor_locations`、`*` | `update` | `allow` |
| `LocationMovementResolver` | `World`、`ActorLocation` | `current_actor_locations`、`*` | `update` | `allow` |
| `ZoneAccessResolver` | `World`、`ActorLocation` | `current_actor_locations`、`*` | `update` | `allow` |
| 任意 `LLMProposal` | `World`、`ActorLocation` | `current_actor_locations`、`*` | `create/update` | `deny` |
| `OriginHistoryFormation` | `OriginEvent` | `*` | `create/update` | `allow` |
| `OriginAttachment` | `Site`、`WorldObject`、`HazardSource`、`ObstacleSource`、`ResourceDeposit`、`ResourceNode`、`FloraPatch`、`CreatureGroup`、`CreatureActor` | `origin` | `update` | `allow` |
| `WorldRuntimeInitialization` | `StaticWorldRuntimeState`、`WorldTimeState` | `*` | `create` | `allow` |
| `WorldRuntimeInitialization` | `WeatherState`、`EnvironmentState`、`HazardSource`、`ObstacleSource` | `*` | `create/update` | `deny` |
| `WeatherFormation` | `WeatherState` | `*` | `create` | `allow` |
| `WeatherFormation`、`WeatherResolver` | `StaticWorldRuntimeState` | `runtime_state.active_weather_state_ids` | `update` | `allow` |
| `WeatherResolver` | `WeatherState` | `*` | `create/update` | `allow` |
| `WeatherResolver` | `EnvironmentState` | `temperature`、`light`、`ground_effects` | `update` | `deny` |
| `WeatherResolver` | `EnvironmentResidualEffectState` | `*` | `create/update/deactivate` | `deny` |
| `EnvironmentDeriver` | `EnvironmentState` | `*` | `derive/update/create` | `allow` |
| `EnvironmentDeriver` | `EnvironmentResidualEffectState` | `*` | `create/update/deactivate` | `allow` |
| `EnvironmentDeriver` | `StaticWorldRuntimeState` | `runtime_state.active_environment_state_ids`、`runtime_state.active_environment_residual_effect_ids` | `update` | `allow` |
| `FloraFormation` | `FloraPatch` | `*` | `create/update` | `allow` |
| `FaunaFormation` | `CreaturePopulation`、`CreatureGroup` | `*` | `create/update` | `allow` |
| `ResourceFormation` | `NaturalResource`、`ResourceDeposit`、`ResourceNode` | `*` | `create/update` | `allow` |
| `EcologyPopulationTransferResolver` | `CreaturePopulation` | `counts.*`、`derived.*` | `update` | `allow` |
| `EcologyPopulationTransferResolver` | `CreatureGroup` | `count`、`location`、`behavior_state`、`lifecycle_state`、`visibility`、`signs` | `create/update/deactivate` | `allow` |
| `EcologyPopulationTransferResolver` | `CreatureActor` | `*` | `create/update/deactivate` | `allow` |
| `EcologyResourceExtractionResolver` | `FloraPatch`、`ResourceDeposit`、`ResourceNode` | `stock.current_amount`、`derived.*`、`state` | `update` | `allow` |
| `EcologyResourceExtractionResolver` | `WorldObject` | `*` | `create/update` | `allow` |
| `EcologyRecoveryResolver` | `FloraPatch`、`ResourceDeposit`、`ResourceNode` | `stock.current_amount`、`derived.*` | `update` | `allow` |
| `EcologyQuantityValidator` | `FloraPatch`、`CreaturePopulation`、`CreatureGroup`、`CreatureActor`、`ResourceDeposit`、`ResourceNode` | `*` | `create/update/derive/materialize` | `deny` |
| `Materializer` | `WorldObject` | `*` | `materialize/create` | `allow` |
| `Materializer` | `WorldObject` | `derived.*` | `materialize/create/update` | `deny` |
| `Materializer` | `WorldObject` | `provenance` | `update` | `deny` |
| 任意 `LLMProposal` | `WorldObject` | `provenance` | `create/update` | `deny` |
| `ContentPackLoader` | `ContentPackEnvelope`、`CatalogEnvelope`、`CatalogEntry` | `*` | `create/update` | `allow` |
| `Materializer` | `ContentMaterializationContext` | `*` | `create` | `allow` |
| `WeightDeriver` | `WorldObject` | `derived.total_weight_kg`、`derived.contained_mass_kg` | `derive/update` | `allow` |
| `ContainerOccupancyDeriver` | `WorldObject` | `derived.occupied_liquid_liters`、`derived.occupied_slot_count` | `derive/update` | `allow` |
| `ContainmentTransferResolver` | `WorldObject` | `components.container.contained_object_ids`、`placement`、`derived.*` | `update` | `allow` |
| `QuantityTransferResolver` | `WorldObject`、`ResourceNode` | `components.container.quantity_contents`、`derived.*`、`state` | `update` | `allow` |
| `HazardObstacleDeriver` | `HazardSource`、`ObstacleSource` | `*` | `create/update/deactivate` | `allow` |
| `HazardObstacleDeriver` | `StaticWorldRuntimeState` | `runtime_state.active_hazard_ids`、`runtime_state.active_obstacle_ids` | `update` | `allow` |
| `DeterministicResolver` | `WorldObject`、`ResourceNode`、`HazardSource`、`ObstacleSource`、`EnvironmentResidualEffectState` | `WriteACL 显式列出的字段` | `update/deactivate/create` | `allow` |
| `WorldGenerationOrchestrator` | `WorldGenerationManifest`、`GenerationStageContract` | `*` | `create/update` | `allow` |
| `GeneratorStageRunner` | `GeneratorOutputEnvelope`、`GeneratorOutputItem` | `*` | `create/update` | `allow` |
| `GenerationOutputValidator` | 任意权威 EntityType | `WriteACL 显式列出的字段` | `create/update/derive/materialize` | `deny` |
| `GenerationCommitter` | 生成 manifest 已验证的 EntityType | `GenerationOutputValidator 已通过的 FieldPath` | `create/update/derive/materialize` | `allow` |
| `GenerationCommitter` | 任意 EntityType | `*` | `propose/project_read/delete_for_migration` | `deny` |
| `GenerationCommitter` | `EventLogEntry` | `*` | `create` | `deny` |
| `GenerationCommitter` | `StaticWorldRuntimeState` | `runtime_state.latest_event_sequence` | `update` | `deny` |
| `StateTransitionCommitter` | `StateTransitionValidator 已通过的 EntityType` | `StateTransitionValidator 已通过的 FieldPath` | `create/update/deactivate/delete_for_migration` | `allow` |
| `StateTransitionCommitter` | `EventLogEntry` | `*` | `create` | `allow` |
| `StateTransitionCommitter` | `StaticWorldRuntimeState` | `runtime_state.latest_event_sequence` | `update` | `allow` |
| `SnapshotWriter` | `WorldSnapshot` | `*` | `create` | `allow` |
| `SnapshotWriter` | `StaticWorldRuntimeState` | `runtime_state.latest_snapshot_id` | `update` | `allow` |

`components.container.contained_object_ids`、`components.container.quantity_contents`、`CreaturePopulation.counts`、`CreatureGroup.count`、`CreatureActor.state.lifecycle_state`、`FloraPatch.stock`、`ResourceDeposit.stock` 和 `ResourceNode.stock` 不允许通用 patch 写入。除上表显式 allow 的转移/提取/恢复 resolver、迁移工具和测试夹具外，其他 rule_id 命中默认拒绝。
| `SettlementProfileFormation` | `SettlementProfile` | `*` | `create/update` | `allow` |
| `InstitutionFormation` | `Institution` | `*` | `create/update` | `allow` |
| `SocialGroupFormation` | `SocialGroupState` | `*` | `create/update` | `allow` |
| `NamedNPCFormation` | `NamedNPCState` | `*` | `create/update` | `allow` |
| `ServiceFormation` | `ServiceState` | `*` | `create/update` | `allow` |
| `PolicyAndPressureFormation` | `LawPolicy`、`EconomyState`、`SocialPressureState` | `*` | `create/update` | `allow` |
| `InitialKnowledgeFormation` | `KnowledgeState`、`DiscoveryState`、`RumorState`、`SecretState` | `*` | `create/update` | `allow` |
| `KnowledgePropagation` | `KnowledgeState`、`DiscoveryState`、`RumorState`、`SecretState` | `*` | `create/update/deactivate` | `allow` |
| `KnowledgePropagation` | `EventLogEntry` | `*` | `create` | `deny` |
| `AgentObservationBuilder` | `AgentObservationSnapshot` | `*` | `create/update` | `allow` |
| `AISocialScheduler` | `AIDecisionTick` | `*` | `create` | `allow` |
| `AISocialScheduler` | `AIDecisionTick` | `status` | `update` | `allow` |
| `AIProposalRecorder` | `GroupDecisionProposal`、`NPCActionProposal` | `*` | `propose/create` | `allow` |
| `AIProposalValidator` | `AIDecisionTick` | `status` | `update` | `allow` |
| `AIProposalValidator` | `GroupDecisionProposal`、`NPCActionProposal` | `computed_policy`、`status`、`validation` | `update` | `allow` |
| `AIProposalValidator` | `KnowledgeState`、`DiscoveryState`、`RumorState`、`SecretState`、任意 world_facts | `*` | `create/update/deactivate` | `deny` |
| `AIProposalConflictResolver` | `GroupDecisionProposal`、`NPCActionProposal` | `status`、`validation` | `update` | `allow` |
| `AIProposalConflictResolver` | `AIDecisionTick` | `status` | `update` | `allow` |
| `AIProposalConflictResolver` | `ProposalResourceReservation` | `*` | `create/update` | `allow` |
| `AIProposalAuditWriter` | `EventLogEntry` | `*` | `create` | `deny` |
| `SocialActionResolver` | `GroupDecisionProposal`、`NPCActionProposal` | `status`、`resolution` | `update` | `allow` |
| `SocialActionResolver` | `AIDecisionTick` | `status`、`result` | `update` | `allow` |
| `SocialActionResolver` | `ProposalResourceReservation` | `status` | `update` | `allow` |
| `SocialActionResolver` | `SocialPressureState` | `pressure.*`、`active_patrol_level`、`state_revision` | `update` | `allow` |
| `SocialActionResolver` | `SocialGroupState`、`NamedNPCState` | `attitude_to_player`、`state_revision` | `update` | `allow` |
| `SocialActionResolver` | `EventLogEntry` | `*` | `create` | `deny` |
| `SocialActionResolver` | `KnowledgeState`、`RumorState`、`SecretState` | `*` | `create/update/deactivate` | `deny` |
| `SocialFallbackResolver` | `AIDecisionTick` | `status`、`result` | `update` | `allow` |
| `SocialFallbackResolver` | `EventLogEntry` | `*` | `create` | `deny` |
| `SocialRumorIndexReducer` | `SocialPressureState` | `active_rumor_ids`、`state_revision` | `update` | `allow` |
| `SocialRumorIndexReducer` | `EventLogEntry` | `*` | `create` | `deny` |
| `AIProposalExpiryResolver` | `GroupDecisionProposal`、`NPCActionProposal`、`ProposalResourceReservation` | `status` | `update` | `allow` |
| `Projection` | 任意权威 EntityType | `*` | `update/create/deactivate` | `deny` |
| `MigrationTool` | 迁移计划列出的 EntityType | 迁移计划列出的 FieldPath | `delete_for_migration/update/create` | `allow` |

`GenerationCommitter` 不是新的自由写入口。它只能提交已经由 `GenerationOutputValidator` 验证通过的 exact `GeneratorOutputItem`；字段许可仍以输出项中的原始 `producer + rule_id + EntityType + FieldPath + operation` 为准，不能用 `GenerationCommitter` 自己的身份扩大写权限。

`StateTransitionCommitter` 也不是新的业务写权限主体。它只负责把已经由 `StateTransitionValidator` 按原始 `producer + rule_id + EntityType + FieldPath + operation` 校验通过的 changes 原子落盘；不能自行创建、改写或补充业务 changes。

`GenerationCommitter` 只能把 `world_fact_outputs` 和 `knowledge_outputs` 转成权威 StateTransition；只能根据 `event_drafts` 填充 StateTransition 的 `event_type`、`caused_by`、`summary` 和 `ordered_changes`；最终 `EventLogEntry`、`sequence`、`previous_event_hash` 和 `resulting_state_hash` 必须由 `StateTransitionCommitter` 在原子提交时生成。`GenerationCommitter` 只能根据 `snapshot_refs` 调用 SnapshotWriter 创建或引用 `WorldSnapshot`。`candidate_outputs` 只能保存在 `system_ledger.generation_audit` 供后续生成阶段显式读取，不能提交进 `world_facts` 或 `knowledge_facts`。

`AIProposalAuditWriter` 只能形成 `event_type=AIDecisionTickCreated`、`AIDecisionTickStatusChanged`、`AIProposalRecorded`、`AIProposalStatusChanged`、`ProposalReservationCreated` 和 `ProposalReservationStateChanged` 的审计 StateTransition，且 `ordered_changes` 只能引用 AI proposal 集合中的 system_ledger 实体。社会后果必须由 `SocialActionResolver` 或对应领域 resolver 产生独立领域 StateTransition。

`SocialActionResolver` 只能形成 `event_type=SocialPressureChanged`、`PatrolLevelChanged`、`SocialAttitudeChanged`、`ServiceOfferCreated`、`ServiceRequestRefused`、`KnowledgeDisclosureResolved` 和 `RumorSpreadRequested` 的 StateTransition。`KnowledgeCreated`、`KnowledgeUpdated`、`RumorCreated` 和 `SecretUpdated` 只能由 `KnowledgePropagation` 形成 StateTransition；`SocialRumorIndexChanged` 只能由 `SocialRumorIndexReducer` 形成 StateTransition。

`SocialFallbackResolver` 只能形成 `event_type=ServiceOfferCreated` 或 `ServiceRequestRefused` 的 StateTransition，且只允许用于 `AIDecisionTick.result.kind=fallback` 的 `service_request` 回退；其他回退必须是无世界状态变化的 `no_op`。

写入检查顺序：

```text
1. FieldDomainValidator 校验 FieldSpec 和字段值。
2. WorldKnowledgeBoundaryValidator 校验 world_facts / knowledge_facts / system_ledger 命名空间和禁用字段。
3. EntityAuthorityDomain 确认 EntityType 已登记。
4. FieldOwnership 确认 FieldPath 已登记并属于预期 AuthorityDomain。
5. WriteACL 使用 rule_id、EntityType、FieldPath、operation 判定 allow/deny。
6. 生成阶段写入必须先进入 GeneratorOutputEnvelope。
7. GenerationOutputValidator 校验输出清单。
8. Producer、resolver、迁移工具或 GenerationCommitter 只能形成 StateTransition 或 StateTransitionBatch。
9. StateTransitionValidator 在内存中校验并计算 post-state hash。
10. StateTransitionCommitter 原子写入 WorldState、EventLogEntry 和 latest_event_sequence；失败时不得留下部分状态。
```

## 跨集合影响总图

```text
字段域集合
-> 约束所有集合字段值

空间集合
-> 承载地形水文、生态、资源、对象、危险、障碍

地形水文集合
-> 影响气候局部修正、生态、资源、通行、危险、障碍

气候时间天气集合
-> 派生 EnvironmentState
-> 影响行动、危险、障碍、生态活动、投影

生态集合
-> 产生 FloraPatch / CreaturePopulation / CreatureGroup
-> 支持采集、狩猎、痕迹、风险

自然资源集合
-> 产生 ResourceDeposit / ResourceNode
-> 支持采集、装水、危险、障碍

世界对象集合
-> 产生可互动内容、危险、障碍、光源、热源

危险障碍集合
-> 修改行动风险、通行状态和 UI 可选项

事件快照集合
-> 记录所有权威状态变化

生成输出集合
-> 统一记录生成器阶段契约、输出包络和审计 hash
-> 通过 GenerationOutputValidator 后才能提交权威状态

AI proposal 集合
-> 只能请求变化
-> Validator / Resolver 决定是否进入权威状态
```

## 跨集合规则表

第四列区分两种记录：候选校验只写 `system_ledger.generation_audit` 的审计结果；已经进入权威状态的变更才使用 EventLog。`GenerationOutputValidated`、`GenerationOutputRejected` 和 `SpatialLayoutCandidatesValidated` 是审计结果名，不是 `event_type`，不得写入 EventLog。

| 输入集合 | 规则器 | 输出集合 | 审计 / EventLog |
| --- | --- | --- | --- |
| 世界参数、RandomSeedMaterial | SpatialLayoutCandidateFormation | 生成输出集合中的空间布局候选 | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| 空间布局候选 | SpatialLayoutCandidateValidator | 生成输出集合中的已验证完整网格 | generation_audit: SpatialLayoutCandidatesValidated / GenerationOutputRejected |
| RegionLayoutCandidate、世界参数、seed | RegionClimateCandidateFormation | RegionClimateCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| WorldChunkLayoutCandidate、RegionClimateCandidate、seed | ChunkBaseRawFieldsCandidateFormation | ChunkBaseRawFieldsCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| 完整 Region 的 raw fields 候选 | ChunkBaseFieldSmoothing | ChunkBaseFieldsCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| ChunkBaseFieldsCandidate | TerrainCandidateFormation | ChunkTerrainCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| Region 内全部 terrain 候选、moisture、water_flow | HydrologyCandidateFormation | ChunkHydrologyCandidate（含 ResourceFormation 支持条件） | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| terrain、水文、Region 气候 | LocalClimateCandidateDerivation | ChunkLocalClimateCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| climate、terrain、water、pressure | ChunkBiomeCandidateDerivation / RegionBiomeCandidateAggregation | ChunkBiomeCandidate / RegionBiomeCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| 全部已验证空间基础候选 | SpatialFoundationMaterializer | World、Region、WorldChunkGrid、WorldChunk | WorldGenerated / RegionGenerated / ChunkGenerated |
| terrain、hydrology、road、civilization_pressure | SettlementAnchorFormation | 空间集合 | SettlementAnchorCreated |
| terrain、road、resource_pressure、ecology_pressure、settlement anchors、danger、abnormal | OriginHistoryCandidateFormation | OriginEventCandidate | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| terrain、biome、rock、已验证 OriginEventCandidate | ResourceFormation | 自然资源集合 | ResourceGenerated |
| climate、biome、water、soil、已验证 OriginEventCandidate | FloraFormation | 生态集合 | FloraGenerated |
| biome、prey、water、pressure、已验证 OriginEventCandidate | FaunaFormation | 生态集合 | FaunaGenerated |
| CreaturePopulation / CreatureGroup / CreatureActor | EcologyPopulationTransferResolver | 生态集合 | CreaturePopulationCountChanged / CreatureGroupCountChanged / CreatureActorLifecycleChanged |
| FloraPatch / ResourceDeposit / ResourceNode、玩家行动、目标容器或 inventory | EcologyResourceExtractionResolver | 生态集合、自然资源集合、世界对象集合 | EcologyResourceExtracted / EcologyResourceStockChanged / ObjectCreated / QuantityResourceTransferred |
| WorldTimeState、FloraPatch / ResourceDeposit / ResourceNode.stock.recovery | EcologyRecoveryResolver | 生态集合、自然资源集合 | EcologyResourceRecovered / EcologyResourceStockChanged |
| source chunk、target chunk、terrain adjacency | StaticChunkEdgeFormation | 空间集合 | ChunkEdgeGenerated |
| ChunkEdge、terrain、hydrology、road | StaticTraversalDeriver | 空间集合 | EdgeBaseTraversalDerived |
| terrain、road、water、civilization、static ChunkEdge reachability、已验证 OriginEventCandidate、PlaceHierarchyRegistry | SitePlacement / LocationGenerator | 空间集合 | SitePlaced / SiteBoundaryEdgeGenerated |
| Site、LocationNode、Zone、Resource、Flora、Fauna、ContentPack catalog、ContentMaterializationContext | ObjectMaterialization | 世界对象集合、生成输出集合 | ObjectCreated |
| WorldObject.components.container、physical.tare_weight_kg、ResourceMassRegistry | WeightDeriver / ContainerOccupancyDeriver | 世界对象集合 | ObjectDerivedPhysicalChanged |
| Settlement Site、LocationNode、Resource、road、history candidates | SettlementSocialFormation | 社会世界事实 | SettlementSocialStateCreated |
| OriginEventCandidate、已物化证据实体 | OriginHistoryMaterialization | 历史来历集合 | OriginEventCreated |
| OriginEvent、证据实体 | OriginAttachment | 历史来历集合 | OriginMetadataAttached |
| World、RandomSeedMaterial、初始时间参数、origin_attachment 阶段完成边界 | WorldRuntimeInitialization | StaticWorldRuntimeState、WorldTimeState | TimeInitialized |
| climate、season、time、terrain、previous WeatherState | WeatherFormation | 气候时间天气集合 | WeatherInitialized / WeatherChanged |
| WeatherState 结束、weather ground_effects、terrain、temperature | EnvironmentDeriver | 气候时间天气集合 | EnvironmentResidualEffectCreated / EnvironmentResidualEffectStateChanged |
| WeatherState、EnvironmentResidualEffectState、WorldTimeState、terrain、LocationNode、光源、热源 | EnvironmentDeriver | 气候时间天气集合 | EnvironmentStateChanged |
| EnvironmentState、terrain、water、flora、resource、object、structure | HazardObstacleDeriver | 危险障碍集合 | HazardCreated / ObstacleCreated / HazardStateChanged / ObstacleStateChanged |
| edge base_passability/base_traversal、active passability overrides | PassabilityReducer | 危险障碍集合 | EdgeEffectivePassabilityDerived |
| GenerationStageContract、各生成器输出 | GenerationOutputValidator | 生成输出集合 | generation_audit: GenerationOutputValidated / GenerationOutputRejected |
| EventLog、OriginEvent、WorldObject、SocialGroupState、空间投影 | KnowledgePropagation / InitialKnowledgeFormation | 知识认知集合 | KnowledgeCreated / KnowledgeUpdated / DiscoveryCreated / RumorCreated / SecretCreated / SecretUpdated |
| KnowledgeState、DiscoveryState、RumorState、SecretState、空间投影 | AgentObservationBuilder | 知识认知集合 | ObservationSnapshotCreated |
| ContentPack catalog、ContentMaterializationContext | Materializer | 世界对象集合、生态集合、自然资源集合、生成输出集合 | ObjectCreated 或生成阶段事件 |
| Player action / rule event | DeterministicResolver | `WriteACL` 允许的 EntityType + FieldPath | 对应状态变化事件 |
| LLM proposal | ProposalValidator + Resolver | proposal 只能写 AI proposal；权威字段只能由 Resolver 按 `WriteACL` 写入 | 对应状态变化事件 |

## 生成阶段顺序

P0 世界生成必须按以下顺序：

```text
0. WorldGenerationOrchestrator 创建 RandomSeedMaterial、WorldGenerationManifest 和 GenerationStageContract。
1. FieldDomainValidator 加载 enum / registry / schema 字段域，输出 GeneratorOutputEnvelope。
2. SpatialLayoutCandidateFormation 程序生成 WorldLayoutCandidate、RegionLayoutCandidate、WorldChunkGridLayoutCandidate 和完整网格中的全部 WorldChunkLayoutCandidate；只输出 candidate_outputs。
3. SpatialLayoutCandidateValidator 校验目标 ID、引用、边界、坐标唯一性和完整笛卡尔覆盖；失败时不进入气候阶段。
4. RegionClimateCandidateFormation 按 region_id 独立并行生成 RegionClimateCandidate；输入是已验证 RegionLayoutCandidate、世界参数和 RandomSeedMaterial。
5. ChunkBaseRawFieldsCandidateFormation 按 chunk_id 独立并行生成 ChunkBaseRawFieldsCandidate；禁止读取邻接 chunk。
6. ChunkBaseFieldSmoothing 等待同一 Region 的全部 raw fields 候选完成，再按稳定邻接顺序并行生成 ChunkBaseFieldsCandidate。
7. TerrainCandidateFormation 按 chunk_id 并行生成 ChunkTerrainCandidate。
8. HydrologyCandidateFormation 按 Region 读取完整 terrain 候选，校验跨 chunk 水流连续性后生成 ChunkHydrologyCandidate；其中的 resource_support 只为后续 ResourceFormation 提供条件，不是权威 ResourceNode。
9. LocalClimateCandidateDerivation 按 chunk_id 并行生成 ChunkLocalClimateCandidate。
10. ChunkBiomeCandidateDerivation 按 chunk_id 并行生成 ChunkBiomeCandidate；RegionBiomeCandidateAggregation 在全部 chunk biome 完成后生成 RegionBiomeCandidate。
11. SpatialFoundationValidator 校验每个目标 World、Region、WorldChunkGrid 和 WorldChunk 的完整 canonical post-state。
12. SpatialFoundationMaterializer 使用同一个 atomic_commit_group_id，一次性创建 World、全部 Region、全部 WorldChunkGrid 和完整网格中的全部 WorldChunk；禁止提交空间半成品。
13. SettlementAnchorFormation 读取已提交 terrain / hydrology / civilization_pressure，生成 RegionFeature / Settlement / TerrainFeature 空间锚点。
14. OriginHistoryCandidateFormation 生成 OriginEventCandidate，输出 candidate_outputs，不提交权威 OriginEvent。
15. StaticChunkEdgeFormation 生成 ChunkEdge 身份和方向关系。
16. StaticTraversalDeriver 读取 terrain / hydrology / road / ChunkEdge，生成 `base_passability` / `base_traversal`。
17. ResourceFormation 读取已验证 OriginEventCandidate 调整候选权重，生成 ResourceDeposit / ResourceNode；不能读取尚未物化的 OriginEvent。
18. FloraFormation 读取已验证 OriginEventCandidate、气候和静态生态条件，生成 FloraPatch。
19. FaunaFormation 读取已验证 OriginEventCandidate、Flora 和 Resource，生成 CreaturePopulation / CreatureGroup。
20. SitePlacement 和 LocationGenerator 读取已提交静态 ChunkEdge 可达性、已验证 OriginEventCandidate、PlaceHierarchyRegistry 和 LocationChildGenerationContext，生成 Site / LocationNode / Zone / SiteBoundaryEdge。
21. ObjectMaterialization 读取 ContentPack catalog、Site、Resource、Flora、Fauna 和 OriginEventCandidate，创建 ContentMaterializationContext，生成带 provenance 的 WorldObject。
22. SettlementSocialFormation 读取已提交 Site / LocationNode / Resource / WorldObject 和候选历史，生成聚落社会状态。
23. OriginHistoryMaterialization 读取 OriginEventCandidate 和已物化证据实体，生成权威 OriginEvent。
24. OriginAttachment 为相关实体附加 OriginMetadata。
25. WorldRuntimeInitialization 在 OriginAttachment 及全部静态生成阶段完成后创建 StaticWorldRuntimeState 和 WorldTimeState；初始 active weather/environment/hazard/obstacle ID 集合为空，且 time_band 必须由初始分钟、季节和昼夜配置派生。
26. WeatherFormation 读取已提交 Region、WorldTimeState 和 terrain，生成覆盖当前 absolute_minute 的初始 WeatherState。
27. EnvironmentDeriver 读取 WeatherState / WorldTimeState / terrain / LocationNode / 光源 / 热源，生成初始 EnvironmentState；若已有合法残留来源，同时生成 EnvironmentResidualEffectState。
28. HazardObstacleDeriver 读取 EnvironmentState 和已提交世界事实，生成初始 HazardSource / ObstacleSource / passability_override。
29. PassabilityReducer 读取 edge base 值和 active overrides，生成 `effective_passability` / `effective_traversal`。
30. WorldFactValidator 对已提交世界事实运行最终校验。
31. InitialKnowledgeFormation 读取已提交世界事实，生成初始 KnowledgeState / DiscoveryState / RumorState / SecretState。
32. KnowledgeValidator 对初始知识事实运行最终校验。
33. WorldSnapshot 写入 after_world_generation 快照。
```

### P0 GenerationStageContract 依赖基线

下表列的是直接依赖，不是把所有前序阶段重复列出。表中 `stage_key` 对应实际 ID `stage_contract_<stage_key>`；实现必须把完整 ID 写入 `depends_on_stage_contract_ids`。编号只作为合法拓扑序中的稳定排序。

| stage_key | execution_scope | parallelizable | 直接依赖 stage_key |
| --- | --- | --- | --- |
| `governance_bootstrap` | world | false | 无 |
| `field_domain_load` | global | false | governance_bootstrap |
| `spatial_layout_candidate_formation` | world | false | field_domain_load |
| `spatial_layout_candidate_validation` | world | false | spatial_layout_candidate_formation |
| `region_climate_candidate_formation` | region | true | spatial_layout_candidate_validation |
| `chunk_base_raw_fields_candidate_formation` | world_chunk | true | spatial_layout_candidate_validation、region_climate_candidate_formation |
| `chunk_base_field_smoothing` | world_chunk | true | chunk_base_raw_fields_candidate_formation |
| `terrain_candidate_formation` | world_chunk | true | chunk_base_field_smoothing |
| `hydrology_candidate_formation` | region | true | terrain_candidate_formation |
| `local_climate_candidate_derivation` | world_chunk | true | region_climate_candidate_formation、terrain_candidate_formation、hydrology_candidate_formation |
| `chunk_biome_candidate_derivation` | world_chunk | true | region_climate_candidate_formation、chunk_base_field_smoothing、terrain_candidate_formation、hydrology_candidate_formation |
| `region_biome_candidate_aggregation` | region | true | chunk_biome_candidate_derivation |
| `spatial_foundation_validation` | world | false | spatial_layout_candidate_validation、region_climate_candidate_formation、chunk_base_field_smoothing、terrain_candidate_formation、hydrology_candidate_formation、local_climate_candidate_derivation、chunk_biome_candidate_derivation、region_biome_candidate_aggregation |
| `spatial_foundation_materialization` | world | false | spatial_foundation_validation |
| `settlement_anchor_formation` | region | true | spatial_foundation_materialization |
| `origin_history_candidate_formation` | region | true | settlement_anchor_formation |
| `static_chunk_edge_formation` | region | true | spatial_foundation_materialization |
| `static_traversal_deriver` | region | true | static_chunk_edge_formation、settlement_anchor_formation |
| `resource_formation` | region | true | spatial_foundation_materialization、origin_history_candidate_formation |
| `flora_formation` | region | true | spatial_foundation_materialization、origin_history_candidate_formation |
| `fauna_formation` | region | true | spatial_foundation_materialization、origin_history_candidate_formation、flora_formation、resource_formation |
| `site_placement_location_generation` | region | true | settlement_anchor_formation、origin_history_candidate_formation、static_traversal_deriver |
| `object_materialization` | site | true | site_placement_location_generation、resource_formation、flora_formation、fauna_formation、origin_history_candidate_formation |
| `settlement_social_formation` | settlement | true | site_placement_location_generation、object_materialization、resource_formation、origin_history_candidate_formation |
| `origin_history_materialization` | world | false | origin_history_candidate_formation、object_materialization、settlement_social_formation |
| `origin_attachment` | world | false | origin_history_materialization |
| `world_runtime_initialization` | world | false | origin_attachment |
| `weather_formation` | region | true | world_runtime_initialization |
| `environment_derivation` | world | false | weather_formation、object_materialization |
| `hazard_obstacle_derivation` | world | false | environment_derivation、resource_formation、flora_formation、fauna_formation、object_materialization、site_placement_location_generation |
| `passability_reduction` | world | false | hazard_obstacle_derivation、static_traversal_deriver |
| `world_fact_validation` | world | false | passability_reduction、origin_attachment、settlement_social_formation |
| `initial_knowledge_formation` | world | false | world_fact_validation |
| `knowledge_validation` | world | false | initial_knowledge_formation |
| `after_world_generation_snapshot` | world | false | knowledge_validation |

`chunk_base_field_smoothing` 的依赖边表示等待 raw fields 阶段的全部 Region/chunk 分区，而不是“某个 chunk 的 raw 完成就立刻平滑”。`region_biome_candidate_aggregation` 和 `spatial_foundation_materialization` 同样具有全量阶段屏障。

`settlement_social_formation` 的内部顺序也是 DAG：SettlementProfile -> Institution -> SocialGroup -> PolicyAndPressure -> NamedNPC -> Service -> Validator/atomic commit。NamedNPC 读取 `Institution.services`，不能读取尚未生成的 ServiceState；Service 必须等待政策、经济、压力和提供者完成。

每个生成阶段都必须遵守 [世界生成输出清单规则](./world-generation-manifest-rules.md)。形成规则文档中的“输出”只表示该阶段期望生成的实体类型，不是自由格式；实现必须包进 `GeneratorOutputEnvelope` 并写入 `WorldGenerationManifest`。

每个生成阶段的权威输出在通过 `GenerationOutputValidator` 后形成提交边界。后续阶段只能读取已经提交的世界事实或显式声明的 candidate_outputs。`WeatherState`、`EnvironmentState`、`EnvironmentResidualEffectState`、`HazardSource` 和 `ObstacleSource` 不能作为 `StaticChunkEdgeFormation` 或 `SitePlacement` 的输入。

`WorldTimeState` 物化前，静态生成阶段若创建 event_draft，`occurred_at` 只能来自规范化 `WorldGenerationParameters.initial_time`。`WorldRuntimeInitialization` 必须用同一输入创建 WorldTimeState 和 TimeInitialized；从该提交边界开始，后续事件只能读取已提交 WorldTimeState，不能继续把生成参数当作运行时时钟。

并行只发生在阶段契约明确声明的不同 scope 分区之间。P0 至少允许 RegionClimateCandidateFormation 按 Region 并行，以及 raw fields、平滑、terrain、local climate、chunk biome 按 WorldChunk 并行。`ChunkBaseFieldSmoothing` 必须等待同一 Region 的全部 raw fields；`RegionBiomeCandidateAggregation` 必须等待全部 chunk biome；`SpatialFoundationMaterializer` 必须等待全部空间基础候选通过校验。

所有生成阶段只要使用随机，必须使用 [确定性随机协议](../01-governance/deterministic-random-protocol-rules.md)，并把 `RandomStreamRef` 与 `RandomDrawRef` 写入 `WorldGenerationManifest` 和对应 `GeneratorOutputEnvelope`。禁止任何生成器使用本地 PRNG、系统时间、未排序候选列表或 validator 失败后的全局重抽。

## 运行时影响顺序

时间推进必须按以下顺序：

```text
1. TimeService 推进 WorldTimeState，形成 TimeAdvanced StateTransition，并由 StateTransitionCommitter 原子提交。
2. WeatherService 用 `absolute_minute` 检查 WeatherState 是否过期。
3. 如天气变化，形成 WeatherChanged StateTransition，并由 StateTransitionCommitter 原子提交。
4. EnvironmentDeriver 为天气结束后的地面效果创建、衰减或过期 EnvironmentResidualEffectState。
5. EnvironmentDeriver 读取当前 WeatherState 和 active EnvironmentResidualEffectState，重算受影响空间的 EnvironmentState。
6. EcologyRecoveryResolver 按 elapsed_minutes 恢复可恢复 FloraPatch / ResourceDeposit / ResourceNode 库存。
7. HazardObstacleDeriver 重算依赖环境和资源库存的危险、障碍和 passability_override。
8. PassabilityReducer 重算受影响 ChunkEdge / LocationEdge / SiteBoundaryEdge 的 `effective_passability` / `effective_traversal`。
9. UI Projection 和 Narration Projection 刷新。
```

行动结算必须按以下顺序：

```text
1. IntentPlan / ActionPlan 确认行动目标。
2. DeterministicResolver 检查空间、对象、危险、障碍和资源条件。
3. 进入或离开 Site 只能由 `SiteBoundaryResolver` 根据 `SiteBoundaryEdge` 应用。
4. 靠近 Zone 只能由 `ZoneAccessResolver` 根据 `Zone.access` 应用。
5. 动物数量变化只能由 `EcologyPopulationTransferResolver` 作为单一 StateTransition 应用。
6. 采集、挖掘、捕鱼、采药、装水等生态资源提取只能由 `EcologyResourceExtractionResolver.extract` 作为单一 StateTransition 应用。
7. 容器离散物品移动只能由 `ContainmentTransferResolver.move_object` 作为单一 StateTransition 应用。
8. 数量资源转移只能由 `QuantityTransferResolver.move_quantity_resource` 作为单一 StateTransition 应用；装水场景必须与 `EcologyResourceExtractionResolver` 同事务。
9. Resolver 形成允许的 StateTransition 或 StateTransitionBatch。
10. StateTransitionValidator 校验空间、对象、资源、数量守恒和字段域不变量，并计算 post-state hash。
11. StateTransitionCommitter 原子提交 WorldState、EventLogEntry 和 latest_event_sequence。
12. WeightDeriver / ContainerOccupancyDeriver 重算受影响 WorldObject 的派生重量和容量占用。
13. EcologyQuantityValidator 校验动物数量和资源库存守恒。
14. 受影响集合的其他 Deriver 重算派生状态。
15. Projection 层输出 DM 文本和 UI 可互动内容。
```

## 集合内部状态转化

### 天气集合

```text
clear -> cloudy -> light_rain -> heavy_rain -> storm
storm -> heavy_rain / strong_wind / cloudy
heavy_rain -> light_rain / cloudy / storm
fog -> clear / cloudy / light_rain
abnormal_mist -> abnormal_mist / fog / cloudy
```

禁止：

```text
storm -> clear
heavy_rain -> clear
LLM proposal -> WeatherState
```

### EnvironmentState

```text
valid -> expired -> rederived
weather_changed -> rederived
time_changed -> rederived
light_source_changed -> rederived
heat_source_changed -> rederived
```

禁止：

```text
DM 文本直接写 EnvironmentState。
EnvironmentState 自己发明 weather condition。
```

### 自然资源集合

```text
stock_available -> derived.depleted
clean_water -> polluted_water
stable_deposit -> unstable_deposit
hidden -> discovered
```

禁止：

```text
天气直接生成最终物品。
采集动作绕过 resolver 直接写 inventory。
```

### 生态集合

P0 只做轻量状态：

```text
present -> disturbed
stock_available -> derived.depleted
hidden -> observed
```

P0 不做：

```text
繁殖模拟
完整迁徙模拟
细粒度捕食链模拟
```

### 世界对象集合

```text
closed -> open
open -> closed
locked -> unlocked
armed -> triggered
armed -> disarmed
lit -> burned_out
intact -> damaged -> broken
contained -> placed -> carried
```

禁止：

```text
description 暗示对象能力但 components 不支持。
LLM proposal 直接改 placement、ownership、state。
```

### 危险集合

```text
inactive -> active
active -> inactive
low -> medium -> high
hidden -> visible
untriggered -> triggered
```

禁止：

```text
HazardSource 直接修改玩家状态。
HazardSource 没有 source_entity_ids。
```

### 障碍集合

```text
passability_override.blocked -> passability_override.conditional -> passability_override.difficult
passability_override.difficult -> passability_override.blocked
ObstacleSource.active -> ObstacleSource.inactive
```

规则：

```text
ObstacleSource 如果影响移动，只能产出或更新 passability_override；最终 `ChunkEdge`、`LocationEdge` 或 `SiteBoundaryEdge` 的 `effective_passability` 必须由 `PassabilityReducer` 统一写入。
ObstacleSource 只表达阻挡语义，不替代具体 WorldObject 或地形事实。
```

### 事件快照集合

```text
EventLog.sequence n -> n + 1
WorldSnapshot(event_sequence=n) -> restore -> validator
```

禁止：

```text
EventLog.summary 作为恢复状态来源。
跳号或重复 sequence。
```

## 投影规则

世界权威状态不能直接等于 DM 文本或 UI 列表。必须经过投影：

```text
WorldState
-> State Projection
-> Narration Projection
-> UI Projection
```

Projection 可以读取：

```text
Location
ChunkEdge/LocationEdge/SiteBoundaryEdge effective fields
EnvironmentState
WorldObject
HazardSource
ObstacleSource
ResourceNode
FloraPatch
CreatureGroup
EventLog summary
```

Projection 不能写：

```text
WorldState
WeatherState
EnvironmentState
HazardSource
ObstacleSource
WorldObject
EventLog
```

## Validator 规则

实现时必须增加 `WorldCollectionInfluenceValidator`，保证：

1. 跨集合变化必须通过允许的规则器。
2. 同一集合内部写入也必须检查 `FieldOwnership` 和 `WriteACL`。
3. 所有 EntityType 必须存在唯一 `EntityAuthorityDomain`。
4. 所有权威 FieldPath 必须存在 `FieldOwnership`。
5. 所有权威写入必须按 `rule_id + EntityType + FieldPath + operation` 查询 `WriteACL`，未命中默认拒绝。
6. `WeatherResolver` 只能写 `WeatherState`，不能写 `EnvironmentState.temperature/light/ground_effects`。
7. `EnvironmentDeriver` 才能写 `EnvironmentState.temperature/light/ground_effects/visibility_modifier`。
8. LLM proposal 不能直接修改权威集合。
9. WeatherState 变化必须触发 EnvironmentState 重新派生或校验证明无需重算。
10. EnvironmentState 变化必须触发相关 HazardSource / ObstacleSource 校验。
11. ObstacleSource 影响移动时必须触发 PassabilityReducer 重算，不能直接写 Edge effective 值。
12. Catalog 实例化不能绕过 FieldDomainValidator 和目标实体 Validator。
13. EventLog 必须覆盖所有权威状态变化。
14. Projection 层不得写 WorldState。
15. 空间基础 candidate producer 只能写对应 Candidate；直接写 Region.climate_profile、Region.biome_tags、WorldChunk.base_fields/terrain/local_climate/biome_tags 必须拒绝，初始权威值只能由 SpatialFoundationMaterializer 从已验证候选原子创建。
16. WorldTimeState 创建前的静态生成 event_draft 必须引用本次生成规范化的 WorldGenerationParameters.initial_time；TimeInitialized 之后的事件必须引用已提交 WorldTimeState。

## 推荐实现顺序

### P0.1：权威域与字段所有权表

- 建立 `AuthorityDomain` 闭集。
- 建立 `EntityAuthorityDomain` 表。
- 建立 `FieldOwnership` 表。
- 建立 `WriteACL` 表。

验收：

```text
任何 EntityType 必须能映射到唯一 AuthorityDomain。
任何权威 EntityType 必须能映射到唯一 CanonicalEntitySchemaRegistry.owner_doc。
任何权威 schema 字段必须能映射到唯一 FieldOwnership。
WeatherResolver 写 EnvironmentState.temperature 会被拒绝。
EnvironmentDeriver 写 EnvironmentState.temperature 会被允许。
非 owner 文档重新定义 CreatureGroup 字段会被拒绝。
Projection 写任意 WorldState 字段会被拒绝。
未登记 rule_id、EntityType、FieldPath 或 operation 的写入默认拒绝。
```

### P0.2：集合注册表

- 建立 `WorldCollectionRegistry`。
- 注册字段域、空间、地形水文、气候时间天气、历史来历、生态、资源、对象、危险障碍、事件快照、知识认知、AI proposal、内容包集合。

验收：

```text
任何实体类型必须能映射到唯一集合。
未知集合名会被 validator 拒绝。
```

### P0.3：影响规则表

- 建立跨集合规则表。
- 每条规则声明 input collection、producer、output collection、event_type。
- 每条会写权威状态的规则必须声明对应 `WriteACL`。

验收：

```text
WeatherState 不能直接产生 WorldObject。
WeatherState 只能通过 EnvironmentDeriver 影响 EnvironmentState。
同集合内非法字段写入也会被拒绝。
```

### P0.4：运行时派生链

- TimeService、WeatherService、EnvironmentDeriver、HazardObstacleDeriver、PassabilityReducer 串联。
- 每一步写或校验 EventLog。

验收：

```text
天气从 light_rain 变 cloudy 后，EnvironmentState 被重新派生。
湿地 muddy 残留可以继续产生 deep_mud ObstacleSource。
```

### P0.5：Projection 边界

- Narration Projection 和 UI Projection 只能读 WorldState。
- Projection 输出不能回写权威状态。

验收：

```text
DM 文本写“门开了”但 WorldObject.state 未改变时，权威状态仍认为门未开。
```

## 测试清单

```text
test_every_entity_type_belongs_to_one_collection
test_every_entity_type_has_one_canonical_schema_owner
test_non_owner_doc_cannot_define_authoritative_entity_schema
test_every_entity_type_has_entity_authority_domain
test_every_authoritative_field_has_field_ownership
test_authoritative_write_requires_write_acl
test_write_acl_default_deny
test_weather_resolver_cannot_write_environment_temperature
test_environment_deriver_can_write_environment_temperature
test_cross_collection_change_requires_registered_deriver
test_same_collection_field_write_requires_write_acl
test_weather_state_cannot_create_world_object
test_weather_change_requires_environment_rederive
test_environment_change_requires_hazard_obstacle_revalidate
test_obstacle_source_requires_passability_reducer_recompute
test_catalog_materialization_runs_field_domain_validator
test_llm_proposal_cannot_write_authoritative_collection
test_projection_cannot_write_world_state
test_event_log_covers_authoritative_state_change
test_cross_collection_event_names_exist_in_event_type_registry
test_every_generator_returns_generator_output_envelope
test_generation_manifest_separates_world_fact_and_knowledge_outputs
test_generation_output_item_matches_write_acl
test_generation_manifest_hash_is_stable
test_world_fact_write_acl_denies_subject_cognition_fields
test_knowledge_fact_write_acl_denies_physical_world_fields
test_field_ownership_wildcard_does_not_allow_known_to_player
test_world_generation_stage_contract_has_topological_order
test_spatial_layout_candidates_exist_before_region_climate_candidates
test_spatial_layout_candidate_grid_is_complete_and_unique
test_chunk_base_raw_fields_read_layout_candidate_not_world_chunk
test_chunk_base_smoothing_waits_for_all_region_raw_fields
test_spatial_foundation_materialization_is_atomic
test_spatial_foundation_rejects_incomplete_world_chunk_post_state
test_spatial_candidate_producer_cannot_write_canonical_world_chunk_fields
test_spatial_foundation_materializer_is_only_initial_physical_field_writer
test_world_runtime_initialization_precedes_weather_formation
test_weather_formation_requires_committed_world_time_state
test_static_chunk_edge_formation_rejects_weather_state_input
test_site_placement_reads_committed_static_traversal
test_ecology_generation_does_not_read_site_projection
test_resource_ecology_and_site_depend_on_origin_history_candidate_stage
test_settlement_social_internal_stage_graph_is_acyclic
test_named_npc_formation_does_not_read_service_state
test_origin_event_candidate_not_consumed_by_runtime_resolver
test_origin_history_materialization_requires_materialized_evidence
test_static_generation_event_time_uses_generation_parameters_initial_time
test_post_time_initialized_event_time_uses_world_time_state
test_every_random_generation_step_records_random_draw_ref
test_random_generation_uses_drp_v1_protocol
test_validator_rejection_does_not_shift_other_draws
```

## 已确认决策

1. 世界内容必须按集合管理，而不是按零散字段管理。
2. 集合之间不能任意互写状态。
3. 集合归属不是写权限，字段级写入必须通过 FieldOwnership 和 WriteACL。
4. 天气影响世界必须通过 EnvironmentState。
5. 生态、资源、对象可以产生危险或障碍，但必须通过 Deriver。
6. Projection 只能读，不写权威状态。
7. EventLog 是所有权威变化的账本。
8. 所有世界生成器必须输出 GeneratorOutputEnvelope，不能各自定义自由输出格式。
9. 世界事实和知识事实可以在同一个 WorldGenerationManifest 中审计，但必须分桶、分阶段提交。
10. 世界生成 DAG 必须有合法拓扑序；每个阶段只能读取已提交事实或显式 candidate。
11. WeatherState 不能作为 StaticChunkEdgeFormation、StaticTraversalDeriver 或 SitePlacement 的输入。
12. OriginEventCandidate 不是权威事实，必须在证据实体物化后才能生成 OriginEvent。
13. 所有生成随机必须使用确定性随机协议，并写入 manifest 审计。
14. P0 不做复杂生态、物理和社会动态模拟。
15. 每个权威 EntityType 只能有一个 canonical schema owner；非 owner 文档只能引用、投影或声明独立后缀类型。
16. P0 空间布局采用程序生成的小型完整网格，不使用按探索惰性创建的稀疏 chunk。
17. `WorldLayoutCandidate`、`RegionLayoutCandidate`、`WorldChunkGridLayoutCandidate` 和 `WorldChunkLayoutCandidate` 必须先于气候和基础场生成。
18. 空间布局、气候、基础场、地形、水文、局部气候和生态标签在候选域内闭合后，才能原子物化 `World`、`Region`、`WorldChunkGrid` 和 `WorldChunk`。
19. `WorldRuntimeInitialization` 必须先创建 `WorldTimeState`，`WeatherFormation` 才能生成初始天气。
