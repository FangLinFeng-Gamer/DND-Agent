---
doc_id: isekai.formation_rule_contract_rules
status: active
layer: architecture
owner: architecture
created_at: 2026-07-19
updated_at: 2026-07-19
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.world_collection_influence_rules
  - isekai.static_world_runtime_rules
provides:
  - FormationRuleContract
  - FormationRuleRegistry
  - FormationRuleContractValidator
---

# 异世界模式 FormationRule 合约与注册表规则

## 背景

世界生成已经有合法阶段顺序、候选边界、输出清单和 StateTransition 提交协议。但仅有阶段顺序还不够：同一个阶段读取同一组输入后，必须明确“为什么生成这些候选或实体”。否则不同实现会用不同阈值、权重、fallback 或冲突处理，导致相同 seed 和版本生成不同 canonical WorldState。

本文件定义 `FormationRuleContract`。它是每条形成规则的统一合约：规则读什么、不能读什么、输出什么、使用哪些参数、如何抽样、如何处理冲突和 fallback、由哪些 validator 与回归测试约束。

## 目标

- 让每条 formation rule 都有机器可校验的最小完整结构。
- 让 `GenerationStageContract` 只负责阶段 DAG，`FormationRuleContract` 负责阶段内部规则。
- 让规则参数、随机流、冲突处理和 fallback 都有版本。
- 防止各领域文档继续以自由文本补规则，造成实现分叉。
- 为 P1-07 的具体数值算法提供挂载点；可执行公式、定点精度和量化规则由 [可执行数值算法规则](../01-governance/executable-numeric-algorithm-rules.md) 定义。

## 非目标

- 不在本文件指定每个地形、资源、动物、聚落的最终数值公式。
- 不替代各领域实体的 canonical schema。
- 不允许 FormationRuleContract 绕过 `GeneratorOutputEnvelope`、`StateTransition` 或目标实体 validator。
- 不把候选、manifest 或 formation audit 暴露给玩家、NPC 或 AI。

## 核心原则

### 1. StageContract 管顺序，FormationRuleContract 管原因

`GenerationStageContract` 回答“这个阶段什么时候运行、能读什么、能输出什么”。`FormationRuleContract` 回答“这个阶段内部的某条规则如何从输入形成输出”。

```text
GenerationStageContract
-> declares stage, dependencies, allowed read/write classes

FormationRuleContract
-> declares deterministic rule function, parameters, random stream, conflicts, fallback, validators

GeneratorOutputEnvelope
-> records actual inputs, outputs, random draws and rule refs for one run
```

同一个 `GenerationStageContract` 可以引用多条 `FormationRuleContract`。例如 `HydrologyCandidateFormation` 可以包含河流、湖泊、湿地和异常水文多条规则。

### 2. 合约完整不等于数值算法完成

P1-06 只关闭“规则必须怎样声明才算完整”。具体公式、权重核、定点精度和数值阈值属于 P1-07，并必须以 `NumericAlgorithmSpec` 注册。

因此每条规则必须有 `algorithm.status`：

```text
ready：公式、参数、舍入、边界和失败行为均已定义，且 `algorithm_id` 能解析到 `NumericAlgorithmSpec`，可以冻结长期存档。
contract_only：合约完整，但具体数值算法尚未成为 ready，只能用于验证性原型。
deprecated：旧规则，只能用于迁移或旧存档重放。
```

`contract_only` 规则可以进入文档系统，但不能进入长期存档格式冻结、生产 seed 发行或公共 API 承诺。

### 3. 没有注册合约的形成规则不能运行

任何 world generation、runtime initialization 或 initial derivation 阶段，只要会产生候选、权威世界事实、初始动态状态或初始知识，都必须引用已注册的 `FormationRuleContract.rule_id`。

未注册 rule_id 的输出必须被 `GenerationOutputValidator` 拒绝。

### 4. fallback 是规则的一部分

fallback 不能由实现临时决定。每条规则必须声明没有候选、候选全部被拒绝、数量不足、冲突无法合并、随机重试耗尽时的确定性结果。

### 5. 冲突处理必须稳定

多个规则同时命中同一 scope、同一实体或同一字段时，必须有稳定排序、优先级、合并策略或拒绝策略。不能依赖 map 遍历顺序、线程完成顺序、文件加载顺序或 LLM 文本判断。

## FormationRuleContract

示例：

```json
{
  "rule_id": "terrain.candidate_from_base_fields.v1",
  "rule_version": "1.0.0",
  "domain": "terrain",
  "owner_doc_id": "isekai.climate_terrain_formation_rules",
  "stage_contract_id": "stage_contract_terrain_candidate_formation",
  "producer": "TerrainCandidateFormation",
  "contract_status": "complete",
  "algorithm": {
    "algorithm_id": "terrain.classify_base_fields.fixed_point.v1",
    "status": "ready",
    "owner_problem_id": "P1-07"
  },
  "target_scope": {
    "kind": "world_chunk",
    "key_fields": ["region_id", "chunk_id"]
  },
  "function_signature": {
    "name": "TerrainCandidateFormation.run",
    "input_contract": "TerrainCandidateFormationInput@1",
    "output_contract": "ChunkTerrainCandidate@1",
    "determinism": "pure_from_declared_inputs"
  },
  "read_set": [
    {
      "input_class": "candidate",
      "candidate_type": "ChunkBaseFieldsCandidate",
      "field_paths": [
        "chunk_id",
        "base_fields.elevation",
        "base_fields.moisture",
        "base_fields.rockiness",
        "base_fields.soil_depth",
        "base_fields.water_flow",
        "base_fields.civilization_pressure",
        "base_fields.danger_pressure",
        "base_fields.abnormal_pressure"
      ],
      "required": true,
      "cardinality": "one"
    }
  ],
  "forbidden_read_set": [
    {
      "input_class": "world_fact",
      "entity_type": "WeatherState",
      "field_paths": ["*"],
      "reason": "static terrain cannot depend on runtime weather"
    }
  ],
  "output_set": [
    {
      "output_class": "candidate",
      "candidate_type": "ChunkTerrainCandidate",
      "field_paths": [
        "chunk_id",
        "terrain.landform",
        "terrain.elevation_band",
        "terrain.slope",
        "terrain.ground",
        "terrain.soil",
        "terrain.rock",
        "terrain.vegetation_cover",
        "terrain.visibility",
        "terrain.cover",
        "terrain.base_travel_cost_minutes",
        "terrain.terrain_tags"
      ],
      "operation": "derive"
    }
  ],
  "parameters": [
    {
      "parameter_id": "mountain_elevation_threshold",
      "type": "decimal_string",
      "unit": "normalized_0_1",
      "range": {
        "min": "0.000",
        "max": "1.000"
      },
      "default": "0.720",
      "precision": "0.001",
      "versioned": true
    }
  ],
  "random": {
    "uses_random": false,
    "stream_domain": null,
    "draw_policy": "no_random_draws",
    "max_rejection_attempts": 0,
    "random_draws": []
  },
  "candidate_generation": {
    "eligibility_policy_id": "terrain.base_fields_present.v1",
    "score_policy_id": "terrain.base_field_score_terms.v1",
    "target_count": {
      "min": 1,
      "target": 1,
      "max": 1
    },
    "stable_sort_key": ["chunk_id"]
  },
  "candidate_selection": {
    "selection_policy_id": "select.single_required_candidate.v1",
    "tie_break_policy_id": "tie_break.lexicographic_candidate_id.v1"
  },
  "conflict_policy": {
    "conflict_scope": "same_chunk_terrain",
    "priority_policy_id": "terrain.priority_physical_over_abnormal_hint.v1",
    "merge_policy_id": "merge.disjoint_field_union.v1",
    "reject_policy_id": "reject.conflicting_same_field.v1"
  },
  "fallback_policy": {
    "fallback_id": "terrain.fallback_plain_lowland.v1",
    "trigger": "no_candidate_after_validation",
    "output": "emit_default_candidate_with_audit",
    "audit_reason_code": "terrain_no_candidate"
  },
  "validator_rules": [
    "validator.chunk_terrain_candidate_fields_registered",
    "validator.chunk_terrain_candidate_no_water_presence",
    "validator.chunk_terrain_candidate_supported_by_base_fields"
  ],
  "regression_tests": [
    "test_terrain_candidate_contract_has_complete_read_set",
    "test_terrain_candidate_fallback_is_deterministic",
    "test_terrain_candidate_rejects_weather_input"
  ]
}
```

## 字段说明

| 字段 | 含义 |
| --- | --- |
| `rule_id` | 全局唯一规则 ID。必须稳定，不能复用给语义不同的规则。 |
| `rule_version` | 规则合约版本。任何输入、输出、参数、冲突或 fallback 语义变化都必须升级。 |
| `domain` | 规则所属领域，必须属于 `formation_domain` 闭集。 |
| `owner_doc_id` | 该规则实例由哪个权威文档维护。 |
| `stage_contract_id` | 允许调用该规则的生成阶段契约 ID。 |
| `producer` | 产出该规则结果的系统组件名称，必须与 WriteACL / GeneratorOutputEnvelope producer 对齐。 |
| `contract_status` | 合约状态。P1 允许 `complete`、`draft`、`deprecated`。只有 `complete` 可进入实现基线。 |
| `algorithm` | 具体算法引用。`algorithm.algorithm_id` 必须引用 NumericAlgorithmRegistry；P1-07 负责让 `algorithm.status=ready`。 |
| `target_scope` | 规则目标作用域。它表示规则输出或影响的目标实体、空间范围或主体范围；不是阶段执行分区。阶段执行分区只由 `stage_contract_id` 引用的 `GenerationStageContract.execution_scope` 决定。 |
| `target_scope.kind` | 目标作用域类别，必须属于 P1 `target_scope.kind` 闭集。 |
| `target_scope.key_fields` | 从输出 payload 或输入上下文派生目标 ID 的 canonical 字段列表。它只用于目标归属、冲突处理、排序和审计，不参与 `stage_run_id` 派生。 |
| `function_signature` | 规则函数签名。实现可以换函数名，但必须提供等价 adapter。 |
| `read_set` | 允许读取的完整输入集合。实际运行读取必须是它的子集，并记录到 `GeneratorOutputEnvelope.input_refs`。 |
| `forbidden_read_set` | 显式禁止读取的输入集合。用于防止依赖环和领域穿透。 |
| `output_set` | 允许输出的候选、世界事实、知识事实或 event_draft 字段集合。 |
| `parameters` | 规则参数表。每个参数必须声明类型、单位、范围、默认值、精度和是否参与版本。 |
| `random` | 随机使用协议。必须说明是否用随机流、stream domain、draw policy、最大拒绝尝试次数和 DRP logical draw 声明。 |
| `random.random_draws` | 本规则允许使用的 DRP 抽样点列表。`random.uses_random=false` 时必须为空数组；`random.uses_random=true` 时必须非空。 |
| `random.random_draws[].logical_draw_id` | 规则显式命名的逻辑抽样 ID。所有 `RandomDrawRef.logical_draw_id` 必须能在本列表中找到。 |
| `random.random_draws[].draw_kind` | 该逻辑抽样允许的实际 DRP 抽样类型。必须属于确定性随机协议的 `draw_kind` 闭集。 |
| `candidate_generation` | 候选形成策略，包括 eligibility、score、数量目标和稳定排序。 |
| `candidate_selection` | 候选选择策略，包括抽样或确定性选择、tie-break。 |
| `conflict_policy` | 多规则或多候选冲突处理。 |
| `fallback_policy` | 规则失败或无候选时的确定性行为。 |
| `validator_rules` | 必须通过的 validator rule id 列表。 |
| `regression_tests` | 最小回归测试名列表。 |

`FormationRuleContract.target_scope.kind` 可以比对应 `GenerationStageContract.execution_scope` 更细。例如 `resource_formation` 阶段可以按 `region` 调度，但内部规则的 `target_scope.kind` 可以是 `world_chunk`、`resource_deposit` 或 `resource_node`。`target_scope.kind` 不表示要拆分 `GeneratorOutputEnvelope`，也不表示要创建独立 `GenerationStageRunState`；输出封装必须遵守 [世界生成输出清单规则](./world-generation-manifest-rules.md) 的 target scope 排序规则。

## 闭集

P1 `formation_domain` 闭集：

```text
spatial_layout
climate
base_field
terrain
hydrology
local_climate
biome
settlement_anchor
origin_history
chunk_edge
traversal
resource
flora
fauna
site
location_node
zone
world_object
settlement_social
runtime_initialization
weather
environment
hazard_obstacle
initial_knowledge
content_materialization
```

P1 `contract_status` 闭集：

```text
complete
draft
deprecated
```

P1 `algorithm.status` 闭集：

```text
ready
contract_only
deprecated
```

P1 `target_scope.kind` 闭集：

```text
global
world
region
world_chunk
chunk_edge
settlement
named_npc
site
location_node
zone
object
population
resource_node
resource_deposit
flora_patch
```

P1 `cardinality` 闭集：

```text
zero_or_one
one
zero_or_many
one_or_many
all_in_scope
```

P1 `draw_policy` 闭集：

```text
no_random_draws
weighted_integer_choice
weighted_integer_without_replacement
stable_shuffle_then_take
deterministic_score_then_take
```

P1 `fallback_policy.output` 闭集：

```text
emit_default_candidate_with_audit
emit_empty_candidate_set_with_audit
reuse_parent_scope_default
reject_scope_with_reason
defer_to_later_stage
```

P1 `merge_policy_id` 必须引用注册策略。初始允许策略：

```text
merge.disjoint_field_union.v1
merge.priority_overwrite_registered_fields.v1
merge.sum_quantity_by_unit.v1
merge.max_severity.v1
merge.keep_all_as_separate_candidates.v1
```

P1 `reject_policy_id` 必须引用注册策略。初始允许策略：

```text
reject.conflicting_same_field.v1
reject.unsupported_cross_domain_write.v1
reject.count_out_of_range.v1
reject.reference_missing.v1
reject.validator_failure.v1
```

## FormationRuleRegistry

`FormationRuleRegistry` 是当前规则包中所有形成规则的索引。它必须参与 `rule_bundle_hash`，并被 `GenerationOutputValidator`、`FormationRuleContractValidator` 和 replay 工具读取。

示例：

```json
{
  "registry_id": "formation_rule_registry_foundation_p1",
  "registry_version": "1.0.0",
  "rule_bundle_hash": "sha256:rule-bundle-hash",
  "rules": [
    {
      "rule_id": "terrain.candidate_from_base_fields.v1",
      "rule_version": "1.0.0",
      "owner_doc_id": "isekai.climate_terrain_formation_rules",
      "stage_contract_id": "stage_contract_terrain_candidate_formation",
      "contract_status": "complete",
      "algorithm_status": "ready"
    }
  ]
}
```

硬规则：

```text
同一个 rule_id 在同一 registry_version 中只能出现一次。
rule_id、rule_version、owner_doc_id、stage_contract_id、contract_status 和 algorithm_status 必须与对应 FormationRuleContract 一致。
GenerationStageContract.rule_id 必须引用 FormationRuleRegistry 中存在且 contract_status=complete 的 rule。
GeneratorOutputItem.rule_id 必须引用 FormationRuleRegistry 中存在且 contract_status=complete 的 rule。
algorithm_status=contract_only 的规则可以用于验证性原型，但不能用于冻结长期存档格式。
algorithm_status=ready 的规则才允许进入长期可重放世界生成基线。
废弃规则必须保留到所有依赖它的 Snapshot 和 EventLog 都完成迁移或明确不再支持。
```

## P1 必须注册的规则集合

下表是 P1-06 的最小注册清单。具体数值算法可以仍由 P1-07 补齐，但这些规则 ID、owner 和最小输出边界必须先存在。

| rule_id 前缀 | producer | domain | target_scope.kind | owner_doc_id | 最小输出 |
| --- | --- | --- | --- | --- | --- |
| `spatial.layout_candidate.*` | SpatialLayoutCandidateFormation | spatial_layout | world / region / world_chunk | isekai.location_space_rules | World / Region / WorldChunkGrid / WorldChunk layout candidates |
| `climate.region_profile.*` | RegionClimateCandidateFormation | climate | region | isekai.climate_terrain_formation_rules | RegionClimateCandidate |
| `base_field.chunk_raw.*` | ChunkBaseRawFieldsCandidateFormation | base_field | world_chunk | isekai.climate_terrain_formation_rules | ChunkBaseRawFieldsCandidate |
| `base_field.chunk_smoothing.*` | ChunkBaseFieldSmoothing | base_field | region | isekai.climate_terrain_formation_rules | ChunkBaseFieldsCandidate |
| `terrain.candidate.*` | TerrainCandidateFormation | terrain | world_chunk | isekai.climate_terrain_formation_rules | ChunkTerrainCandidate |
| `hydrology.candidate.*` | HydrologyCandidateFormation | hydrology | region | isekai.climate_terrain_formation_rules | ChunkHydrologyCandidate |
| `local_climate.chunk.*` | LocalClimateCandidateDerivation | local_climate | world_chunk | isekai.climate_terrain_formation_rules | ChunkLocalClimateCandidate |
| `biome.chunk_tags.*` | ChunkBiomeCandidateDerivation | biome | world_chunk | isekai.climate_terrain_formation_rules | ChunkBiomeCandidate |
| `biome.region_summary.*` | RegionBiomeCandidateAggregation | biome | region | isekai.climate_terrain_formation_rules | RegionBiomeCandidate |
| `settlement_anchor.static.*` | SettlementAnchorFormation | settlement_anchor | region / world_chunk | isekai.climate_terrain_formation_rules | settlement anchor / road / terrain feature candidates |
| `origin.candidate.*` | OriginHistoryCandidateFormation | origin_history | site / region / world_chunk | isekai.world_origin_history_rules | OriginEventCandidate |
| `edge.static_chunk.*` | StaticChunkEdgeFormation | chunk_edge | chunk_edge | isekai.climate_terrain_formation_rules | ChunkEdge identity |
| `traversal.static_base.*` | StaticTraversalDeriver | traversal | chunk_edge | isekai.climate_terrain_formation_rules | base traversal fields |
| `resource.deposit_node.*` | ResourceFormation | resource | world_chunk / resource_deposit / resource_node | isekai.natural_ecology_rules | NaturalResource / ResourceDeposit / ResourceNode |
| `flora.patch.*` | FloraFormation | flora | world_chunk / flora_patch | isekai.natural_ecology_rules | PlantSpecies refs / FloraPatch |
| `fauna.population_group.*` | FaunaFormation | fauna | region / world_chunk / population | isekai.natural_ecology_rules | CreaturePopulation / CreatureGroup |
| `site.placement.*` | SitePlacement | site | world_chunk / site | isekai.location_space_rules | Site |
| `location.node_generation.*` | LocationGenerator | location_node | site / location_node | isekai.location_space_rules | LocationNode / LocationEdge |
| `zone.generation.*` | LocationGenerator | zone | location_node / zone | isekai.location_space_rules | Zone |
| `object.materialization.*` | ObjectMaterialization | world_object | site / location_node / object | isekai.world_object_rules | WorldObject |
| `settlement.profile.*` | SettlementProfileFormation | settlement_social | settlement | isekai.settlement_social_world_rules | SettlementProfile |
| `settlement.institution.*` | InstitutionFormation | settlement_social | settlement | isekai.settlement_social_world_rules | Institution |
| `settlement.social_group.*` | SocialGroupFormation | settlement_social | settlement | isekai.settlement_social_world_rules | SocialGroupState |
| `settlement.policy_pressure.*` | PolicyAndPressureFormation | settlement_social | settlement | isekai.settlement_social_world_rules | LawPolicy / EconomyState / SocialPressureState |
| `settlement.named_npc.*` | NamedNPCFormation | settlement_social | settlement | isekai.settlement_social_world_rules | NamedNPCState |
| `settlement.service.*` | ServiceFormation | settlement_social | settlement | isekai.settlement_social_world_rules | ServiceState |
| `origin.materialize.*` | OriginHistoryMaterialization | origin_history | site / region / world_chunk | isekai.world_origin_history_rules | OriginEvent |
| `origin.attach_metadata.*` | OriginAttachment | origin_history | object / site / location_node | isekai.world_origin_history_rules | OriginMetadata on evidence entities |
| `runtime.initial_time.*` | WorldRuntimeInitialization | runtime_initialization | world | isekai.static_world_runtime_rules | StaticWorldRuntimeState / WorldTimeState |
| `weather.initial_or_transition.*` | WeatherFormation | weather | region / world_chunk | isekai.climate_terrain_formation_rules | WeatherState |
| `environment.initial.*` | EnvironmentDeriver | environment | world_chunk / location_node | isekai.static_world_runtime_rules | EnvironmentState |
| `hazard_obstacle.initial.*` | HazardObstacleDeriver | hazard_obstacle | world_chunk / chunk_edge / location_node | isekai.static_world_runtime_rules | HazardSource / ObstacleSource |
| `knowledge.initial.*` | InitialKnowledgeFormation | initial_knowledge | world / settlement / named_npc | isekai.world_knowledge_rules | KnowledgeState / DiscoveryState / RumorState / SecretState |

## 合约完整性规则

```text
contract_status=complete 要求：
1. rule_id、rule_version、domain、owner_doc_id、stage_contract_id 和 producer 存在。
2. function_signature 存在，且 input_contract/output_contract 已命名。
3. read_set 覆盖所有会影响输出的字段。
4. forbidden_read_set 覆盖会导致依赖环或领域越权的关键集合。
5. output_set 只包含 stage contract 和 WriteACL 允许的输出。
6. parameters 中每个参数都有类型、单位、范围、默认值、精度和 versioned 标记。
7. target_scope.kind 属于 P1 `target_scope.kind` 闭集，且 target_scope.key_fields 能从输出 payload 或输入上下文解析。
8. random 声明是否使用 DRP；若 uses_random=false，random_draws 必须为空数组；若 uses_random=true，必须有 stream_domain、draw_policy、max_rejection_attempts 和非空 random_draws。
9. candidate_generation 声明 eligibility、score、数量目标和稳定排序。
10. candidate_selection 声明选择策略和 tie-break。
11. conflict_policy 声明冲突 scope、优先级、合并和拒绝策略。
12. fallback_policy 声明触发条件、输出行为和 audit reason code。
13. validator_rules 非空。
14. regression_tests 非空。
```

如果一条规则不产生多个候选，也必须显式填写 `candidate_generation.target_count` 和 `candidate_selection.selection_policy_id`，例如 `select.single_required_candidate.v1`。不能省略后让实现自行判断。

## FormationRuleContractValidator

`FormationRuleContractValidator` 在规则包加载、生成计划构建和输出校验时运行。

必须校验：

```text
1. 每个 FormationRuleContract 的 rule_id 在 FormationRuleRegistry 中存在。
2. 每个 registry item 都能找到对应 FormationRuleContract。
3. 每个 GenerationStageContract.rule_id 都引用 contract_status=complete 的规则。
4. 每个 GeneratorOutputItem.rule_id 都引用 contract_status=complete 的规则。
5. StageContract.reads 必须覆盖 FormationRuleContract.read_set；规则不能读阶段不允许读的输入。
6. FormationRuleContract.output_set 必须是 StageContract allowed outputs 与 WriteACL 的子集。
7. target_scope.kind 必须属于 P1 `target_scope.kind` 闭集；validator 不得把 target_scope.kind 当作 `GenerationStageContract.execution_scope`、`GenerationStageRunState.scope` 或 DRP `RandomStreamRef.scope_id` 的自动来源。
8. random.uses_random=true 时，GeneratorOutputEnvelope 必须记录对应 RandomStreamRef 和 RandomDrawRef；每个 RandomDrawRef.logical_draw_id 必须属于 FormationRuleContract.random.random_draws，且 RandomDrawRef.draw_kind 必须等于该 logical_draw_id 声明的 draw_kind。
9. parameters 的默认值必须在 range 内，precision 必须能无歧义 canonicalize。
10. conflict_policy 和 fallback_policy 必须引用已注册策略 ID。
11. algorithm.status=ready 时，algorithm.algorithm_id 必须能解析到 NumericAlgorithmSpec，且 NumericAlgorithmSpec.algorithm_status=ready。
12. algorithm.status=contract_only 时，生成结果不得标记为 long_term_replay_baseline。
```

## 与其他文档关系

| 文档 | 关系 |
| --- | --- |
| 世界生成输出清单规则 | `GenerationStageContract` 必须引用本文件注册的 rule_id；`GeneratorOutputEnvelope` 必须记录实际使用的 rule_id。 |
| 世界集合与影响规则 | `FormationRuleContract.output_set` 必须通过 FieldOwnership 和 WriteACL。 |
| 确定性随机协议 | 所有随机候选选择必须使用 DRP 和 RandomDrawRef。 |
| 可执行数值算法规则 | `FormationRuleContract.algorithm.algorithm_id` 必须引用 NumericAlgorithmRegistry；ready 规则必须绑定 ready NumericAlgorithmSpec。 |
| 字段域与注册表规则 | 参数、输出字段、enum 和 validator rule id 必须可由治理层校验。 |
| 静态世界运行规则 | 形成规则输出进入权威状态仍必须通过 StateTransitionCommitter。 |
| 各世界模型文档 | 各领域只负责维护自己的 FormationRuleContract 实例和领域算法，不再自定义另一套合约结构。 |

## 推荐实现顺序

1. 实现 `FormationRuleRegistry` 加载器。
2. 实现 `FormationRuleContract` schema validator。
3. 在 `GenerationStageContract` 中加入 `formation_rule_refs` 校验。
4. 在 `GeneratorOutputItem` 校验中强制 `rule_id` 引用注册规则。
5. 为 P1 最小注册清单逐条补 contract 实例。
6. 对 `algorithm.status=contract_only` 的规则加运行门禁：只能跑验证性原型，不能冻结长期存档。
7. 对 `algorithm.status=ready` 的规则校验 `algorithm_id` 必须解析到 ready NumericAlgorithmSpec。

## 测试清单

```text
test_every_generation_stage_references_registered_formation_rule
test_generator_output_rule_id_must_be_registered
test_stage_reads_cover_formation_rule_read_set
test_formation_rule_output_set_must_be_write_acl_subset
test_formation_rule_target_scope_is_not_stage_execution_scope
test_formation_rule_parameters_have_unit_range_default_precision
test_formation_rule_random_requires_random_draw_ref
test_formation_rule_random_draws_cover_drp_draw_refs
test_formation_rule_conflict_policy_is_registered
test_formation_rule_fallback_policy_is_registered
test_contract_only_algorithm_cannot_mark_long_term_replay_baseline
test_ready_algorithm_id_must_resolve_to_numeric_algorithm_spec
test_p1_minimum_formation_rule_registry_has_all_required_rule_prefixes
```

## 已确认决策

1. P1-06 不直接定义所有数值公式；它定义形成规则合约和注册门禁。
2. 具体数值算法、定点精度、舍入和权重核归 P1-07。
3. 没有 `FormationRuleContract` 的生成器输出不能进入权威 WorldState。
4. `algorithm.status=contract_only` 可以支持原型，但不能冻结长期存档格式。
5. `FormationRuleContract.target_scope.kind` 表示规则目标作用域，不参与阶段调度、stage_run_id 派生或 DRP scope_id 自动选择。
