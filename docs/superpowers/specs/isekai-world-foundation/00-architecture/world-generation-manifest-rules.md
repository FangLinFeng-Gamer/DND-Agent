---
doc_id: isekai.world_generation_manifest_rules
status: active
layer: architecture
owner: architecture
created_at: 2026-07-13
updated_at: 2026-07-19
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.world_collection_influence_rules
  - isekai.formation_rule_contract_rules
  - isekai.executable_numeric_algorithm_rules
  - isekai.static_world_runtime_rules
  - isekai.world_knowledge_rules
provides:
  - WorldGenerationManifest
  - GenerationStageContract
  - GeneratorOutputEnvelope
  - GeneratorOutputItem
  - GenerationOutputValidator
---

# 异世界模式世界生成输出清单规则

## 背景

世界生成已经拆成空间、地形、水文、生态、资源、历史、聚落、物品、天气、环境、危险、障碍和初始知识等多个生成器。如果每个生成器各自声明“输出”，实现会出现三类问题：

1. 生成器直接写 `WorldState`，绕过字段所有权、ACL 和 EventLog。
2. 候选、权威实体、派生状态、初始知识和快照引用混在同一层。
3. 相同 seed 下无法用统一清单复现“哪个生成器在什么输入下产出了什么”。

本设计定义 `WorldGenerationManifest`。它是世界生成阶段的唯一输出清单格式。所有生成器都必须输出 `GeneratorOutputEnvelope`，再由 `GenerationOutputValidator` 校验并提交为权威状态。

## 目标

- 统一所有生成器的输出格式。
- 明确候选、世界事实、知识事实、事件草案和快照引用的边界。
- 让每个生成阶段的输入、输出、随机流、规则版本和内容包版本可审计。
- 让每个生成阶段必须引用已注册的 FormationRuleContract。
- 让生成器输出能被 FieldSpec、FieldOwnership、WriteACL 和目标实体 validator 机器校验。
- 保证世界生成完成后可以根据 manifest、EventLog 和 Snapshot 复现 canonical hash。

## 非目标

- 不定义每种地形、物品、动物或聚落的具体生成算法。
- 不替代各实体的 canonical schema。
- 不让 manifest 成为玩家、NPC 或 AI 的可见知识。
- 不允许 manifest 绕过 EventLog 或 WorldSnapshot。

## 核心原则

### 1. 生成器不能自由写 WorldState

生成器只能输出 `GeneratorOutputEnvelope`。Envelope 通过 `GenerationOutputValidator` 后，才可以被提交器转换为 `StateTransition` 或 `StateTransitionBatch`；最终 EventLogEntry 必须由 StateTransitionCommitter 在原子提交时生成。

```text
Generator
-> GeneratorOutputEnvelope
-> GenerationOutputValidator
-> StateTransition
-> StateTransitionCommitter
-> EventLogEntry
-> Authoritative WorldState
```

### 2. 候选不是权威实体

候选只能进入 `candidate_outputs`。运行时 resolver、AI、UI 和玩家行动不能消费候选。候选被接受后，必须以新的 `GeneratorOutputItem(output_class=world_fact)` 或 `GeneratorOutputItem(output_class=knowledge_fact)` 物化。

### 3. 世界事实和知识事实分桶输出

生成器输出必须分成不同 bucket：

```text
world_fact_outputs：空间、地形、资源、对象、历史、天气、环境、危险、障碍、社会等世界事实。
knowledge_outputs：KnowledgeState、DiscoveryState、RumorState、SecretState 等认知事实。
event_drafts：准备提交的事件草案。
snapshot_refs：提交后创建或引用的快照。
```

同一个 `GeneratorOutputItem` 只能属于一个 `output_class`。世界事实输出不能携带主体知识字段；知识事实输出不能携带物理世界字段。

### 4. Manifest 是审计物，不是游戏内知识

`WorldGenerationManifest` 可以被调试器、validator、迁移工具和重放系统读取。它不能直接进入 `AgentObservationSnapshot`，也不能被 NPC 或 AI 当成世界记忆。

### 5. 每个阶段只读取已声明输入

`GenerationStageContract` 必须声明阶段能读取哪些 entity、candidate、event boundary 和 content pack。实现不能在生成器内部临时读取未声明集合。

### 6. 每个阶段必须绑定 FormationRuleContract

`GenerationStageContract.rule_id` 必须引用 [FormationRule 合约与注册表规则](./formation-rule-contract-rules.md) 中 `FormationRuleRegistry` 已注册且 `contract_status=complete` 的规则。一个阶段包含多条内部规则时，必须在 `formation_rule_refs[]` 中逐条列出；`GeneratorOutputItem.rule_id` 必须引用其中一条。

## 总体流程

```text
WorldGenerationParameters
-> RandomSeedMaterial + GenerationPlan
-> GenerationStageContract DAG
-> 空间布局 candidate_outputs
-> 气候、基础场、地形、水文、局部气候、生态 candidate_outputs
-> SpatialFoundationValidator
-> SpatialFoundationMaterializer（原子创建 World / Region / WorldChunkGrid / WorldChunk）
-> 后续世界内容和初始动态状态
-> GeneratorOutputEnvelope[]
-> WorldGenerationManifest
-> GenerationOutputValidator
-> StateTransitionBatch
-> StateTransitionCommitter
-> EventLog
-> WorldSnapshot(after_world_generation)
```

## WorldGenerationManifest

`WorldGenerationManifest` 是一次世界生成的顶层清单。

示例：

```json
{
  "manifest_id": "manifest_world_graystone_seed_001",
  "world_id": "world_graystone_001",
  "manifest_version": "1.0.0",
  "schema_version": "isekai-world-foundation@1",
  "seed_material": {
    "protocol_version": "drp.v1",
    "world_seed": "graystone-seed-001",
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "seed_material_hash": "sha256:seed_material_hash",
  "generation_plan_id": "generation_plan_p0_static_world",
  "stage_contract_ids": [
    "stage_contract_governance_bootstrap",
    "stage_contract_field_domain_load",
    "stage_contract_spatial_layout_candidate_formation",
    "stage_contract_spatial_layout_candidate_validation",
    "stage_contract_region_climate_candidate_formation",
    "stage_contract_chunk_base_raw_fields_candidate_formation",
    "stage_contract_chunk_base_field_smoothing",
    "stage_contract_terrain_candidate_formation",
    "stage_contract_hydrology_candidate_formation",
    "stage_contract_local_climate_candidate_derivation",
    "stage_contract_chunk_biome_candidate_derivation",
    "stage_contract_region_biome_candidate_aggregation",
    "stage_contract_spatial_foundation_validation",
    "stage_contract_spatial_foundation_materialization",
    "stage_contract_settlement_anchor_formation",
    "stage_contract_origin_history_candidate_formation",
    "stage_contract_static_chunk_edge_formation",
    "stage_contract_static_traversal_deriver",
    "stage_contract_resource_formation",
    "stage_contract_flora_formation",
    "stage_contract_fauna_formation",
    "stage_contract_site_placement_location_generation",
    "stage_contract_object_materialization",
    "stage_contract_settlement_social_formation",
    "stage_contract_origin_history_materialization",
    "stage_contract_origin_attachment",
    "stage_contract_world_runtime_initialization",
    "stage_contract_weather_formation",
    "stage_contract_environment_derivation",
    "stage_contract_hazard_obstacle_derivation",
    "stage_contract_passability_reduction",
    "stage_contract_world_fact_validation",
    "stage_contract_initial_knowledge_formation",
    "stage_contract_knowledge_validation",
    "stage_contract_after_world_generation_snapshot"
  ],
  "stage_output_ids": [
    "output_governance_bootstrap_001",
    "output_field_domain_load_001",
    "output_spatial_layout_candidate_formation_001",
    "output_spatial_layout_candidate_validation_001",
    "output_region_climate_candidate_formation_001",
    "output_chunk_base_raw_fields_candidate_formation_001",
    "output_chunk_base_field_smoothing_001",
    "output_terrain_candidate_formation_001",
    "output_hydrology_candidate_formation_001",
    "output_local_climate_candidate_derivation_001",
    "output_chunk_biome_candidate_derivation_001",
    "output_region_biome_candidate_aggregation_001",
    "output_spatial_foundation_validation_001",
    "output_spatial_foundation_materialization_001",
    "output_settlement_anchor_formation_001",
    "output_origin_history_candidate_formation_001",
    "output_static_chunk_edge_formation_001",
    "output_static_traversal_deriver_001",
    "output_resource_formation_001",
    "output_flora_formation_001",
    "output_fauna_formation_001",
    "output_site_placement_location_generation_001",
    "output_object_materialization_001",
    "output_settlement_social_formation_001",
    "output_origin_history_materialization_001",
    "output_origin_attachment_001",
    "output_world_runtime_initialization_001",
    "output_weather_formation_001",
    "output_environment_derivation_001",
    "output_hazard_obstacle_derivation_001",
    "output_passability_reduction_001",
    "output_world_fact_validation_001",
    "output_initial_knowledge_formation_001",
    "output_knowledge_validation_001",
    "output_after_world_generation_snapshot_001"
  ],
  "random_stream_refs": [
    {
      "protocol_version": "drp.v1",
      "domain": "chunk_base_fields",
      "rule_id": "chunk_base.raw_fields",
      "scope_id": "chunk:chunk_north_slope_12_08_00",
      "seed_material_hash": "sha256:seed_material_hash"
    }
  ],
  "final_event_sequence": 2048,
  "final_state_hash": "sha256:world_state_hash",
  "snapshot_id": "snapshot_after_world_generation"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `manifest_id` | 本次生成清单 ID。 |
| `world_id` | 被生成的世界 ID。 |
| `manifest_version` | manifest schema 版本。 |
| `schema_version` | 世界底座 schema 版本。 |
| `seed_material` | `RandomSeedMaterial` 对象。 |
| `seed_material.protocol_version` | 确定性随机协议版本，P0 必须是 `drp.v1`。 |
| `seed_material.world_seed` | 世界生成 seed，必须使用确定性随机协议解释。 |
| `seed_material.registry_hash` | enum、registry、FieldSpec 和 schema 的规范化 hash。 |
| `seed_material.rule_bundle_hash` | 生成规则、resolver、validator 版本的规范化 hash。 |
| `seed_material.content_pack_hash` | 参与生成的内容包和 catalog 规范化 hash。 |
| `seed_material_hash` | `RandomSeedMaterial` 的 canonical hash。 |
| `generation_plan_id` | 本次使用的生成计划 ID。 |
| `stage_contract_ids` | 执行过的阶段契约 ID，按阶段顺序排序。 |
| `stage_output_ids` | 阶段输出 envelope ID，按提交顺序排序。 |
| `random_stream_refs` | 本次生成使用过的随机流引用，必须符合确定性随机协议。 |
| `final_event_sequence` | 世界生成结束后的 EventLog sequence。 |
| `final_state_hash` | 生成结束后 Authoritative WorldState 的 canonical hash。 |
| `snapshot_id` | `after_world_generation` 快照 ID。 |

规则：

```text
seed_material_hash 必须能由 seed_material 重算。
manifest_id 必须稳定，可由 world_id + seed_material_hash 派生。
stage_contract_ids 和 stage_output_ids 必须使用稳定顺序。
random_stream_refs 必须按 protocol_version、domain、rule_id、scope_id 排序。
final_state_hash 必须能由提交后的 WorldState 重算。
WorldGenerationManifest 不能包含自由文本结论作为权威事实。
```

## GenerationStageContract

`GenerationStageContract` 描述一个生成阶段的合法输入、输出和权限。

示例：

```json
{
  "stage_contract_id": "stage_contract_initial_knowledge_formation",
  "stage_index": 170,
  "phase": "initial_knowledge",
  "depends_on_stage_contract_ids": [
    "stage_contract_world_fact_validation"
  ],
  "execution_scope": "world",
  "parallelizable": false,
  "atomic_commit_group_id": null,
  "producer": "InitialKnowledgeFormation",
  "rule_id": "knowledge.initial_from_public_world_facts",
  "formation_rule_refs": [
    {
      "rule_id": "knowledge.initial.public_world_fact_discovery.v1",
      "rule_version": "1.0.0",
      "required": true
    }
  ],
  "reads": [
    {
      "input_class": "world_fact",
      "entity_type": "OriginEvent",
      "field_paths": ["origin_event_id", "scope", "severity"],
      "requires_committed": true
    },
    {
      "input_class": "world_fact",
      "entity_type": "WorldObject",
      "field_paths": ["id", "placement", "state.concealment"],
      "requires_committed": true
    },
    {
      "input_class": "event_boundary",
      "boundary_kind": "max_event_sequence"
    }
  ],
  "allowed_output_classes": ["knowledge_fact", "event_draft"],
  "allowed_entity_types": ["KnowledgeState", "DiscoveryState", "RumorState", "SecretState"],
  "allowed_candidate_types": [],
  "allowed_event_types": ["KnowledgeCreated", "DiscoveryCreated", "RumorCreated", "SecretCreated"],
  "allowed_snapshot_reasons": [],
  "random_stream_domain": "initial_knowledge",
  "requires_committed_world_facts": true
}
```

P0 `phase` 闭集：

```text
governance_load
static_base_fact
static_candidate
authority_materialization
initial_dynamic_state
runtime_derivation
initial_knowledge
snapshot
```

P0 `execution_scope` 闭集：

```text
global
world
region
world_chunk
chunk_edge
settlement
site
location_node
object
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `stage_contract_id` | 阶段契约 ID。 |
| `stage_index` | 确定性阶段顺序，整数，越小越早。 |
| `phase` | 阶段类别，必须属于 P0 闭集。 |
| `depends_on_stage_contract_ids` | 当前阶段的直接前置阶段 ID。所有前置阶段的全部分区必须完成且输出通过校验后，当前阶段才可启动。 |
| `execution_scope` | 阶段执行分区：全局、单世界、单 Region 或单 WorldChunk。 |
| `parallelizable` | 是否允许不同 scope ID 的分区并行执行。它不允许同一 scope 被重复并行执行。 |
| `atomic_commit_group_id` | 原子提交组 ID。非空时，同组全部输出必须同时提交或全部不提交。 |
| `producer` | 生成器名称。 |
| `rule_id` | 该阶段执行的规则 ID。 |
| `formation_rule_refs` | 本阶段允许调用的 FormationRuleContract 引用列表。每个引用必须在 FormationRuleRegistry 中存在。 |
| `formation_rule_refs[].rule_id` | FormationRuleContract 的 rule_id。 |
| `formation_rule_refs[].rule_version` | FormationRuleContract 的版本。 |
| `formation_rule_refs[].required` | 是否为该阶段必需规则。true 时本阶段输出必须至少引用一次该 rule_id，除非阶段无输出并记录 deterministic fallback audit。 |
| `reads` | 允许读取的输入引用，必须使用 `GenerationInputRef` 结构。 |
| `allowed_output_classes` | 允许输出的 item 类别。 |
| `allowed_entity_types` | 允许输出的权威实体类型。只适用于 `world_fact` 和 `knowledge_fact`。 |
| `allowed_candidate_types` | 允许输出或读取的候选类型。只适用于 `candidate`。 |
| `allowed_event_types` | 允许输出的事件草案类型。只适用于 `event_draft`。 |
| `allowed_snapshot_reasons` | 允许创建或引用的快照原因。只适用于 `snapshot_ref`。 |
| `random_stream_domain` | 随机流 domain。 |
| `requires_committed_world_facts` | 是否只能读取已经提交的世界事实。 |

阶段依赖规则：

```text
depends_on_stage_contract_ids 必须形成有向无环图。
stage_index 只用于同一合法拓扑层内的稳定排序，不能代替依赖声明。
rule_id 和 formation_rule_refs[].rule_id 必须引用 FormationRuleRegistry 中 contract_status=complete 的规则。
GeneratorOutputItem.rule_id 必须属于当前阶段 formation_rule_refs[]。
一个阶段只有在所有直接前置阶段的全部分区完成并通过 GenerationOutputValidator 后才能启动；这构成阶段屏障。
parallelizable=true 时只能按 execution_scope 的稳定 scope ID 分区；分区不得共享可变本地 PRNG、遍历计数器或未声明临时状态。
同一阶段所有分区的 GeneratorOutputEnvelope 必须按 scope.kind、scope.id、output_id 稳定排序后进入 manifest。
parallelizable=false 且 execution_scope=world 的阶段在同一 GenerationRunState 中只能产生一个 GeneratorOutputEnvelope；该 envelope 的 scope.kind 必须是 world，scope.id 必须是当前 world_id。
world 级不可并行阶段内部调用子作用域 FormationRuleContract 时，子作用域只表示 GeneratorOutputItem 目标实体的派生范围，不能拆出额外的 child-scope GeneratorOutputEnvelope。
atomic_commit_group_id 非空时，组内任一输出校验失败都必须回滚整个组，禁止留下部分权威实体。
```

### GenerationInputRef

`GenerationInputRef` 是 `GenerationStageContract.reads[]` 和 `GeneratorOutputEnvelope.input_refs[]` 共同使用的输入引用结构。Contract 中的 `reads[]` 声明允许读取什么，Envelope 中的 `input_refs[]` 记录本次实际读取了什么。

P0 `input_class` 闭集：

```text
world_fact
knowledge_fact
system_ledger
candidate
content_pack
event_boundary
snapshot_ref
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `input_class` | 输入类别。 |
| `entity_type` | 当输入是权威实体或 system ledger 实体时使用。 |
| `entity_id` | 实际读取的实体 ID；Contract 可省略，Envelope 必填。 |
| `field_paths` | 允许或实际读取的字段路径。 |
| `revision` | 实际读取的权威实体 revision；Envelope 必填。 |
| `state_hash` | 实际读取值的 canonical hash；Envelope 必填。 |
| `candidate_type` | 当 `input_class=candidate` 时使用，例如 `OriginEventCandidate`。 |
| `candidate_output_id` | 产生候选的 `GeneratorOutputEnvelope.output_id`。 |
| `candidate_item_id` | 被读取候选的 `GeneratorOutputItem.item_id`。 |
| `candidate_id` | 候选稳定 ID。 |
| `content_pack_id` | 被读取的内容包 ID。 |
| `content_pack_version` | 被读取的内容包版本。 |
| `catalog_kind` | 被读取的 catalog 类型。 |
| `catalog_version` | 被读取的 catalog 版本。 |
| `catalog_id` | 被读取的 catalog entry ID；读取整个 catalog 时可为空。 |
| `content_pack_hash` | 被读取内容包或 catalog 的 canonical hash。 |
| `boundary_kind` | 事件边界类型，例如 `max_event_sequence`。 |
| `event_sequence` | 实际读取时的 EventLog 序列边界。 |

规则：

```text
阶段不能读取未在 reads 声明的 input_class、实体、字段、候选、内容包或事件边界。
Envelope.input_refs 必须是 contract.reads 的实例化子集。
candidate 输入只能来自已验证但未提交为权威事实的 candidate_outputs。
content_pack 输入必须记录 content_pack_id、content_pack_version、catalog_kind、catalog_version 和 content_pack_hash；读取具体 entry 时必须记录 catalog_id。
event_boundary 输入只能读边界值，不能把 EventLog 内容当作生成器输入。
阶段不能输出未在 allowed_entity_types、allowed_candidate_types、allowed_event_types 或 allowed_snapshot_reasons 声明的内容。
initial_knowledge 阶段必须在被引用世界事实提交后执行。
snapshot 阶段不能创建世界事实或知识事实，只能创建快照引用。
ContentPack Materializer 阶段必须输出 `ContentMaterializationContext` 到 system_ledger，并让被物化实体携带同一 `materialization_id` 的 provenance。
```

### P0 空间基础候选类型

空间基础生成使用以下注册候选类型。候选 schema 分别由地点空间规则和气候地形形成规则定义：

| candidate_type | 含义 | 目标字段或实体 |
| --- | --- | --- |
| `WorldLayoutCandidate` | 世界身份、seed、内容包引用和 chunk 尺寸配置候选。 | `World` |
| `RegionLayoutCandidate` | Region 身份、类型、世界边界和 grid 引用候选。 | `Region` 空间字段 |
| `WorldChunkGridLayoutCandidate` | Region 内离散 chunk 坐标系候选。 | `WorldChunkGrid` |
| `WorldChunkLayoutCandidate` | 完整网格中一个必需 chunk 的身份和坐标候选。 | `WorldChunk` 空间字段 |
| `RegionClimateCandidate` | 一个目标 Region 的长期气候包络候选。 | `Region.climate_profile` |
| `ChunkBaseRawFieldsCandidate` | 单个目标 chunk 尚未平滑的连续基础场。 | 平滑阶段输入 |
| `ChunkBaseFieldsCandidate` | 经过稳定邻接平滑的连续基础场。 | `WorldChunk.base_fields` |
| `ChunkTerrainCandidate` | 由基础场形成的静态地形候选。 | `WorldChunk.terrain` 的非水文字段 |
| `ChunkHydrologyCandidate` | 水体存在形态和后续资源生成支持条件。 | `WorldChunk.terrain.water_presence`、ResourceFormation 输入 |
| `ChunkLocalClimateCandidate` | 地形和水文造成的局部气候修正。 | `WorldChunk.local_climate` |
| `ChunkBiomeCandidate` | 单个目标 chunk 的派生生态标签。 | `WorldChunk.biome_tags` |
| `RegionBiomeCandidate` | 从该 Region 全部 chunk 标签稳定聚合出的区域生态标签。 | `Region.biome_tags` |

候选身份规则：

```text
GeneratorOutputItem.candidate_id 是候选记录自身的稳定 ID，只用于 generation_audit。
候选 payload 中的 world_id、region_id、grid_id、chunk_id 是未来权威实体的目标 ID。
目标 ID 在候选阶段只允许引用同一 manifest 中已经验证的候选，不能伪装成已提交 world_fact reference。
candidate_id 与目标实体 ID 不能互换，物化后也不能让运行时通过 candidate_id 查找世界实体。
空间基础 candidate 输出固定使用 operation=derive、field_path=*、authority_domain=generation_audit。
candidate payload 由 value_ref 指向，value_hash 必须能由规范化 payload 重算。
```

## GeneratorOutputEnvelope

`GeneratorOutputEnvelope` 是单个生成阶段的输出包络。

示例：

```json
{
  "output_id": "output_initial_knowledge_formation_001",
  "stage_contract_id": "stage_contract_initial_knowledge_formation",
  "producer": "InitialKnowledgeFormation",
  "rule_id": "knowledge.initial_from_public_world_facts",
  "scope": {
    "kind": "site",
    "id": "old_furnace_inn"
  },
  "input_refs": [
    {
      "input_class": "world_fact",
      "entity_type": "OriginEvent",
      "entity_id": "origin_old_furnace_fire_001",
      "field_paths": ["origin_event_id", "scope", "severity"],
      "revision": 1,
      "state_hash": "sha256:origin_event_projection_hash"
    },
    {
      "input_class": "event_boundary",
      "boundary_kind": "max_event_sequence",
      "event_sequence": 142,
      "state_hash": "sha256:event_boundary_hash"
    }
  ],
  "input_hash": "sha256:input_hash",
  "random_draw_refs": [
    {
      "stream_ref": {
        "protocol_version": "drp.v1",
        "domain": "initial_knowledge",
        "rule_id": "knowledge.initial_from_public_world_facts",
        "scope_id": "site:old_furnace_inn",
        "seed_material_hash": "sha256:seed_material_hash"
      },
      "logical_draw_id": "public_rumor_select_001",
      "draw_index": 0,
      "draw_kind": "weighted_choice",
      "candidate_set_hash": "sha256:candidate_set_hash",
      "result_id": "knowledge_innkeeper_fire_rumor_001"
    }
  ],
  "candidate_outputs": [],
  "world_fact_outputs": [],
  "knowledge_outputs": [
    {
      "item_id": "item_knowledge_innkeeper_fire_rumor_001",
      "rule_id": "knowledge.initial.public_world_fact_discovery.v1",
      "output_class": "knowledge_fact",
      "operation": "create",
      "entity_type": "KnowledgeState",
      "entity_id": "knowledge_innkeeper_fire_rumor_001",
      "field_path": "*",
      "value_ref": "value_knowledge_innkeeper_fire_rumor_001",
      "value_hash": "sha256:value_knowledge_innkeeper_fire_rumor_001",
      "algorithm_ref": null,
      "authority_domain": "knowledge_runtime"
    }
  ],
  "event_drafts": [
    {
      "item_id": "item_event_knowledge_created_001",
      "rule_id": "knowledge.initial.public_world_fact_discovery.v1",
      "output_class": "event_draft",
      "operation": "create",
      "entity_type": "EventLogEntry",
      "entity_id": "event_draft_knowledge_created_001",
      "field_path": "*",
      "value_ref": "value_event_draft_knowledge_created_001",
      "value_hash": "sha256:value_event_draft_knowledge_created_001",
      "algorithm_ref": null,
      "authority_domain": "event_log",
      "event_type": "KnowledgeCreated",
      "depends_on_item_ids": ["item_knowledge_innkeeper_fire_rumor_001"]
    }
  ],
  "snapshot_refs": [],
  "output_hash": "sha256:output_hash"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `output_id` | 输出 envelope ID。 |
| `stage_contract_id` | 对应阶段契约。 |
| `producer` | 生成器名称。 |
| `rule_id` | 产生输出的规则 ID。 |
| `scope` | 本阶段影响范围。 |
| `input_refs` | 实际读取的 `GenerationInputRef` 列表。 |
| `input_hash` | 输入规范化 hash。 |
| `random_draw_refs` | 使用过的确定性随机抽样引用，必须符合 `RandomDrawRef`。 |
| `candidate_outputs` | 候选输出。数组内元素必须全部是 `GeneratorOutputItem(output_class=candidate)`。 |
| `world_fact_outputs` | 世界事实输出。数组内元素必须全部是 `GeneratorOutputItem(output_class=world_fact)`。 |
| `knowledge_outputs` | 知识事实输出。数组内元素必须全部是 `GeneratorOutputItem(output_class=knowledge_fact)`。 |
| `event_drafts` | 事件草案输出。数组内元素必须全部是 `GeneratorOutputItem(output_class=event_draft)`。 |
| `snapshot_refs` | 快照引用输出。数组内元素必须全部是 `GeneratorOutputItem(output_class=snapshot_ref)`。 |
| `output_hash` | 输出规范化 hash。 |

### World 级单 Envelope 的子作用域输出

当 `GenerationStageContract.execution_scope=world` 且 `parallelizable=false` 时，阶段输出采用单 world envelope。

```text
GeneratorOutputEnvelope.scope.kind = world
GeneratorOutputEnvelope.scope.id = World.id
```

如果该阶段内部的 `FormationRuleContract.target_scope.kind` 是 `world_chunk`、`location_node` 或其他比 world 更细的作用域，这些 target scope 只表示输出实体的目标派生范围，不改变 envelope 粒度。

例如 `EnvironmentDeriver` 在 `environment_derivation` 阶段算出：

```text
env_chunk_a
env_chunk_b
env_node_1
env_node_2
```

这些结果必须作为同一个 `GeneratorOutputEnvelope(scope=world:<world_id>)` 的 `world_fact_outputs[]` 中的四个 `GeneratorOutputItem` 提交。每个 item 的 `value_ref` payload 必须由目标实体 schema 表达实际作用域，例如 `EnvironmentState.scope=world_chunk` 并引用 `chunk_id`，或 `EnvironmentState.scope=site_node` 并引用 `site_id`、`node_id`。

同一 bucket 内的子作用域 item 必须使用稳定顺序：

```text
target_scope_kind_rank,
target_scope_id,
entity_type,
entity_id,
field_path,
item_id
```

`target_scope_kind_rank` 必须使用以下固定顺序：

```text
none = 0
world = 10
region = 20
world_chunk = 30
chunk_edge = 40
settlement = 50
named_npc = 55
site = 60
location_node = 70
site_node = 80
zone = 90
object = 100
population = 110
resource_node = 120
resource_deposit = 130
flora_patch = 140
```

`target_scope_id` 必须由目标实体 payload 中的 canonical scope 字段派生，格式为 `<target_scope.kind>:<canonical_id>`。目标实体 payload 使用 `EnvironmentState.scope=site_node` 时，排序用 `target_scope_kind_rank=site_node`，`target_scope_id=site_node:<node_id>`。目标实体没有 scope 字段时，`target_scope_kind_rank=none`，`target_scope_id=""`。`target_scope_id` 是排序和审计键，不等同于确定性随机协议的 `RandomStreamRef.scope_id`。

子作用域 item 使用随机时，`RandomStreamRef.scope_id` 必须使用实际随机作用范围，例如 `chunk:<chunk_id>` 或 `location_node:<node_id>`；它可以等于、粗于或细于 `target_scope_id`，但必须属于确定性随机协议允许的 `scope_id` 格式，并由规则随机声明解释。这不改变 `GeneratorOutputEnvelope.scope=world:<world_id>`。如果规则确实只进行一次全世界随机抽样，才使用 `world:<world_id>` 作为 `RandomStreamRef.scope_id`。

## GeneratorOutputItem

`GeneratorOutputItem` 表示一次实体创建、字段更新或状态关闭。

P0 `output_class` 闭集：

```text
candidate
world_fact
knowledge_fact
event_draft
snapshot_ref
```

P0 `operation` 闭集是生成阶段专用子集：

```text
create
update
deactivate
materialize
derive
```

生成阶段禁止使用 `propose`、`project_read` 和 `delete_for_migration`。这些 operation 属于 AI proposal、投影读取或迁移工具，不属于世界生成提交协议。

`materialize` 和 `derive` 是生成阶段 operation，不是 EventLog `changes[].op`。进入权威状态前，`GenerationCommitter` 必须按 [静态世界运行规则](../03-runtime/static-world-runtime-rules.md) 的“生成 operation lowering 规则”把它们降低为可重放的 `create/update/deactivate` StateTransition changes；Candidate 或 generation_audit 输出不得伪装成已提交世界事实。

字段说明：

| 字段 | 含义 |
| --- | --- |
| `item_id` | 输出项 ID。 |
| `rule_id` | 产生该输出项的 FormationRuleContract.rule_id。必须属于当前 `GenerationStageContract.formation_rule_refs[].rule_id`，并引用 `FormationRuleRegistry` 中 `contract_status=complete` 的规则。 |
| `output_class` | 输出类别。 |
| `operation` | 写入操作。 |
| `entity_type` | 目标权威实体类型。`output_class=candidate` 时必须为 `null`。 |
| `entity_id` | 目标权威实体 ID。`output_class=candidate` 时必须为 `null`。 |
| `candidate_type` | 候选类型。仅 `output_class=candidate` 时必填。 |
| `candidate_id` | 候选记录的稳定 ID。仅 `output_class=candidate` 时必填。 |
| `field_path` | 目标字段路径，创建完整实体时可为 `*`。 |
| `value_ref` | 规范化 value 存储引用或内联值引用。 |
| `value_hash` | `value_ref` 对应 payload 的 canonical hash。 |
| `algorithm_ref` | 产生该输出的可执行数值算法引用。非数值输出为 `null`；数值生成输出必须填写。 |
| `algorithm_ref.algorithm_id` | NumericAlgorithmRegistry 中的算法 ID。 |
| `algorithm_ref.algorithm_version` | NumericAlgorithmSpec.algorithm_version。必须与实际规则包版本一致。 |
| `algorithm_ref.algorithm_status` | NumericAlgorithmSpec.algorithm_status。进入长期可重放基线时必须为 `ready`。 |
| `authority_domain` | 目标字段对应权威域。 |
| `event_type` | 当 `output_class=event_draft` 时必填，必须属于 `allowed_event_types`。 |
| `snapshot_reason` | 当 `output_class=snapshot_ref` 时必填，必须属于 `allowed_snapshot_reasons`。 |
| `depends_on_item_ids` | 依赖的输出项 ID。 |

规则：

```text
每个 GeneratorOutputItem 必须填写 rule_id，用于输出项级别的规则归属、WriteACL 校验和 replay 审计。
world_fact 输出不能使用 KnowledgeState、DiscoveryState、RumorState、SecretState、AgentObservationSnapshot。
knowledge_fact 输出只能使用 KnowledgeState、DiscoveryState、RumorState、SecretState。
candidate 输出只能使用注册的 Candidate 类型，例如 OriginEventCandidate；不能进入 world_facts 或 knowledge_facts。
candidate 输出必须填写 candidate_type、candidate_id，并把 entity_type、entity_id 设为 null。
非 candidate 输出必须填写 entity_type、entity_id，并把 candidate_type、candidate_id 设为 null。
event_draft 输出的 entity_type 必须是 EventLogEntry，entity_id 是草案 ID，不是最终 EventLogEntry ID；提交器只能把它转换为 StateTransition 字段，最终 sequence、transition_id、changes 和 resulting_state_hash 由 StateTransitionCommitter 生成或校验。
snapshot_ref 输出的 entity_type 必须是 WorldSnapshot；value_ref 只能包含 snapshot_id、reason、event_sequence 和 state_hash 引用，不能内联完整快照内容。
如果输出由 NumericAlgorithmSpec 产生，algorithm_ref 必须存在，并且 algorithm_id、algorithm_version、algorithm_status 能与 NumericAlgorithmRegistry 重算一致。
如果输出 payload 含数值字段且对应 FormationRuleContract.algorithm.status=ready，algorithm_ref 不能为 null。
所有 output bucket 内的元素必须是 GeneratorOutputItem；禁止任何自由格式对象。
```

## GenerationOutputValidator

`GenerationOutputValidator` 必须按以下顺序校验：

```text
1. stage_contract_id 存在，depends_on_stage_contract_ids 形成合法 DAG，且所有直接前置阶段已经完成。
2. GeneratorOutputEnvelope.producer 和 GeneratorOutputEnvelope.rule_id 与 GenerationStageContract 匹配。
3. GeneratorOutputEnvelope.rule_id 必须引用 FormationRuleRegistry 中 contract_status=complete 的规则。
4. input_refs 只读取 contract.reads 和 FormationRuleContract.read_set 允许的 input_class、实体、字段、候选、内容包或事件边界。
5. input_refs 不得命中 FormationRuleContract.forbidden_read_set。
6. 每个 bucket 只能包含与 bucket 名匹配的 GeneratorOutputItem，且每个 GeneratorOutputItem.rule_id 必须属于当前阶段 formation_rule_refs[]。
7. output_class 属于闭集。
8. operation 属于生成阶段 operation 子集。
9. entity_type、candidate_type、event_type 和 snapshot_reason 分别属于 contract allowed 列表。
10. output_class 与 entity_type / authority_domain 分桶一致。
11. 数值生成输出的 algorithm_ref 必须引用 NumericAlgorithmRegistry 中的 ready NumericAlgorithmSpec。
12. value_ref 必须可解析，value_hash 必须能由 canonical value 重算。
13. FieldSpec 校验所有 value。
14. WorldKnowledgeBoundaryValidator 校验世界事实和知识事实禁用字段。
15. EntityAuthorityDomain 和 FieldOwnership 校验字段归属。
16. WriteACL 校验 GeneratorOutputItem.rule_id、EntityType、FieldPath 和 operation。
17. 目标实体 validator 校验完整 post-state。
18. event_drafts 覆盖所有权威状态变化，且不能提前声明最终 EventLog sequence。
19. snapshot_refs 只能引用提交边界之后的 WorldSnapshot。
20. output_hash 与规范化输出一致。
20. random_draw_refs 必须能按确定性随机协议重算。
21. weighted_choice 的 candidate_set_hash 必须能重算。
22. parallelizable 阶段的 scope 分区唯一，envelope 稳定排序与串行执行结果一致。
23. parallelizable=false 且 execution_scope=world 的阶段必须只有一个 world scope envelope；validator 必须拒绝同一 stage 下额外的 child-scope envelope。
24. world 级单 envelope 内的子作用域 item 必须按 target_scope_kind_rank、target_scope_id、entity_type、entity_id、field_path、item_id 稳定排序。
25. atomic_commit_group_id 相同的输出形成完整提交组，且组内不存在缺失或失败项。
```

提交规则：

```text
GenerationCommitter 只能提交已验证的 exact GeneratorOutputItem。
GenerationCommitter 不能改写 value、field_path、entity_type、entity_id、operation 或 GeneratorOutputItem.rule_id。
权威写入许可必须以原始 producer 和 GeneratorOutputItem.rule_id 为准，不能以 GenerationCommitter 身份重新申请更宽权限。
GenerationCommitter 只能把 world_fact_outputs 和 knowledge_outputs 转成 [静态世界运行规则](../03-runtime/static-world-runtime-rules.md) 定义的 StateTransition 或 StateTransitionBatch。
GenerationCommitter 只能把 ContentMaterializationContext 写入 system_ledger.generation_audit，不能提交进 world_facts 或 knowledge_facts。
GenerationCommitter 只能根据 event_drafts 填充 StateTransition 的 event_type、caused_by、summary 和 ordered_changes；最终 EventLogEntry 必须由 StateTransitionCommitter 在原子提交时生成。
GenerationCommitter 只能根据 snapshot_refs 调用 SnapshotWriter 创建或引用 WorldSnapshot，不能把 snapshot 内容写进 GeneratorOutputItem。
candidate_outputs 只能留在 generation_audit 中供后续生成阶段显式读取，不能提交进 world_facts 或 knowledge_facts。
同一 atomic_commit_group_id 的 StateTransition 必须在一个提交事务中全部成功；任一失败时不得追加该组的领域 EventLogEntry，也不得留下部分 WorldState。
```

### SpatialFoundationMaterializer 提交规则

`SpatialFoundationMaterializer` 是 P0 空间基础的唯一初始物化入口：

```text
它只能读取已经通过对应 candidate validator 的空间、气候、基础场、地形、水文、局部气候和生态候选。
它必须在一个 atomic_commit_group_id 中创建一个 World、全部 Region、全部 WorldChunkGrid 和完整网格中的全部 WorldChunk。
每个创建项必须是完整 canonical entity；禁止先提交只有 id/coord 的 WorldChunk，再由后续阶段补必填物理字段。
current_actor_locations、site_slots、danger_tags、factions 和 risk_clocks 可以使用 canonical schema 允许的空集合初值；空集合是合法状态，不是缺失字段。
物化失败时整个空间基础提交组回滚，候选仍只保留在 generation_audit 中供诊断。
```

禁止行为：

```text
生成器绕过 envelope 直接写 WorldState。
生成器使用未登记 RandomDrawRef 的随机结果。
生成器使用系统时间、执行顺序或未排序候选列表产生随机结果。
世界事实输出携带 known_by、discovered_by、rumored_by 等主体知识字段。
知识输出携带 placement、terrain、physical、resource_quantity 等物理事实字段。
event_drafts 使用自由格式对象。
snapshot_refs 缺失或内联完整快照内容。
生成阶段使用 propose、project_read 或 delete_for_migration operation。
候选输出被运行时 resolver、AI 或 UI 直接消费。
一个 stage 隐式读取未声明输入。
```

## 与生成恢复规则的关系

`WorldGenerationManifest` 只记录最终可审计生成结果，不记录恢复控制状态。

```text
GenerationRunState
GenerationStageRunState
GenerationCheckpoint
GenerationResumeToken
```

以上结构属于 [生成失败恢复与断点续生成规则](./generation-recovery-rules.md) 定义的 `generation_control`，不能写入 `WorldGenerationManifest`。Manifest 可以引用最终接受的 `GeneratorOutputEnvelope`、`GeneratorOutputItem`、`RandomDrawRef`、`algorithm_ref` 和 hash，但不能记录 attempt_no、失败重试次数、进程恢复次数或 resume token。

## 与知识规则的关系

世界事实和知识事实可以出现在同一个 `WorldGenerationManifest` 中，但必须位于不同 bucket，并且由不同阶段提交：

```text
世界事实阶段：
OriginEvent / WorldObject / Site / HazardSource / SettlementProfile 等

初始知识阶段：
KnowledgeState / DiscoveryState / RumorState / SecretState
```

`InitialKnowledgeFormation` 可以读取已提交世界事实，生成“谁知道什么”的初始状态。它不能反向修改世界事实。例如，生成“店主知道旧炉旅店曾失火”时，只能创建 `KnowledgeState`，不能修改 `OriginEvent` 或 `Site`。

## 测试清单

```text
test_every_generator_returns_generator_output_envelope
test_generation_stage_contract_rejects_undeclared_reads
test_generation_stage_contract_dependencies_form_dag
test_generation_stage_waits_for_all_dependency_partitions
test_parallel_stage_scope_ids_are_unique
test_parallel_and_serial_envelope_order_are_equivalent
test_atomic_commit_group_rolls_back_on_any_invalid_item
test_generation_stage_contract_declares_candidate_content_pack_and_event_boundary_reads
test_generator_output_item_matches_allowed_entity_types
test_all_output_buckets_contain_generator_output_items
test_event_drafts_use_generator_output_item_shape
test_snapshot_refs_use_generator_output_item_shape
test_world_fact_outputs_reject_knowledge_entity_types
test_knowledge_outputs_reject_world_fact_entity_types
test_world_fact_output_rejects_subject_knowledge_fields
test_knowledge_output_rejects_physical_world_fields
test_generation_output_rejects_propose_project_read_and_delete_for_migration_operations
test_candidate_outputs_not_consumable_by_runtime_resolver
test_candidate_input_requires_declared_candidate_read
test_candidate_output_uses_candidate_identity_not_entity_identity
test_spatial_foundation_materializer_requires_all_candidate_types
test_spatial_foundation_materializer_rejects_missing_grid_coordinate
test_spatial_foundation_materializer_never_commits_partial_world_chunk
test_generator_output_runs_field_spec_and_write_acl
test_generation_manifest_hash_is_stable_for_same_seed_and_versions
test_generation_manifest_records_seed_material_hash
test_generation_manifest_records_random_stream_refs
test_numeric_generation_output_records_algorithm_ref
test_generator_output_random_draw_refs_recompute
test_candidate_set_hash_recomputes_for_weighted_choice
test_world_scope_non_parallel_stage_outputs_single_world_envelope
test_world_envelope_subscope_items_are_stably_sorted
test_world_envelope_random_scope_is_not_inferred_from_target_scope
test_initial_knowledge_requires_committed_world_fact_inputs
test_event_drafts_cover_all_authoritative_generation_changes
test_snapshot_stage_outputs_snapshot_ref_only
```

## 已确认决策

1. `WorldGenerationManifest` 是世界生成阶段的唯一输出清单。
2. 所有生成器都必须输出 `GeneratorOutputEnvelope`。
3. 候选、世界事实、知识事实、事件草案和快照引用必须分桶。
4. 世界事实不能携带主体知识字段。
5. 知识事实不能携带物理世界字段。
6. Manifest 是审计和重放输入，不是游戏内知识。
7. Manifest 通过 validator 后才能提交到 EventLog 和 WorldState。
8. Manifest 必须记录 `RandomSeedMaterial` hash、`RandomStreamRef` 和每个 `RandomDrawRef`。
9. `GenerationStageContract.reads[]` 和 `GeneratorOutputEnvelope.input_refs[]` 必须使用同一套 `GenerationInputRef` 结构。
10. `event_drafts` 和 `snapshot_refs` 也必须使用 `GeneratorOutputItem`，不能使用自由格式对象。
11. 生成阶段 operation 是全局 WriteACL operation 的子集，禁止 `propose`、`project_read` 和 `delete_for_migration`。
12. `WorldGenerationManifest`、`GenerationStageContract`、`GeneratorOutputEnvelope` 和 `GeneratorOutputItem` 属于 `system_ledger.generation_audit`。
13. P0 空间基础采用“候选骨架先生成、完整后物化”；候选不进入 WorldState。
14. `GenerationStageContract.depends_on_stage_contract_ids` 是生成 DAG 的权威依赖，`stage_index` 只用于稳定排序。
15. Region 和 WorldChunk 分区可以并行生成，但后继阶段必须等待前置阶段全部分区通过校验。
16. `World`、`Region`、`WorldChunkGrid` 和 `WorldChunk` 的初始创建属于同一个原子提交组。
17. world 级不可并行阶段采用单 `GeneratorOutputEnvelope(scope=world)` 承载子作用域输出；子作用域不拆成额外 envelope。
