---
doc_id: isekai.field_domain_registry_rules
status: active
layer: governance
owner: architecture
created_at: 2026-07-11
updated_at: 2026-07-18
depends_on: []
provides:
  - FieldSpec
  - FieldDomainKind
  - FieldDomainValidator
  - TagRegistry
  - schema_authoring_rules
---

# 异世界模式字段域与注册表规则设计

## 背景

地点、空间、物品、生态、气候、天气、危险、障碍、事件日志已经定义了大量字段。若字段值可以由内容包、LLM 或开发临时发明，世界规则会逐渐失去一致性。

本设计定义所有字段的取值域治理规则。它不新增玩法内容，只规定：

- 哪些字段必须是闭集。
- 哪些字段可以走注册表。
- 哪些字段必须引用已存在实体。
- 哪些字段必须由规则派生。
- 哪些字段可以是自由文本。
- LLM proposal、Catalog、WorldState、EventLog 如何接受字段值。

## 目标

- 所有进入 `WorldState` 的字段必须有明确字段域。
- 所有参与规则判断的字段必须是闭集、注册表、引用、数值范围或派生值。
- 所有 `tags` 必须从对应 tag registry 中选择。
- 所有 `rule_id` 必须来自规则注册表。
- 所有 catalog 条目必须经过字段域 validator。
- 所有 schema 默认拒绝未声明字段。
- 自由文本只能用于展示和解释，不能驱动 resolver。

## 非目标

- 不定义新的地形、物品、生态或天气内容。
- 不扩展世界生成玩法。
- 不把所有文本都改成枚举。
- 不要求 `name`、`description` 这类展示文本进入闭集。
- 不允许为了方便而把规则判断塞进自由文本。

## 核心原则

### 1. 每个字段必须声明 FieldSpec

每个 schema 字段都必须声明一个完整的 `FieldSpec(path)`。没有声明 FieldSpec 的字段不能进入 `WorldState`、Catalog 或 LLM proposal 输出 schema。

FieldSpec 必须绑定到完整 schema path，不能只绑定到短字段名。同名字段在不同位置可以承担不同角色，必须分别声明。例如规则表中定义规则的 `rule_id` 与运行时状态中引用规则的 `generated_by.rule_id` 不是同一个字段声明。

### 2. 规则字段必须受控

只要字段会影响生成、校验、行动结算、风险、障碍、可见内容、资源变化、地点变化或事件日志，它就不能是自由文本。

### 3. 展示文本不能驱动规则

`name`、`aliases`、`description`、`summary`、`notes`、`reasoning_summary` 可以是文本，但 resolver 不能根据这些字段直接判断规则结果。

### 4. tags 不是自由字符串

所有 `*_tags` 都必须属于对应 tag registry。`tags` 可以辅助检索、生成权重和叙事，但不能替代权威字段，例如 `object_type`、`terrain.landform`、`weather_condition`。

### 5. LLM 只能选择，不能发明

LLM proposal 可以从已注册字段值中选择，或给出自由文本解释。它不能新增 `object_type`、`hazard_type`、`tag`、`rule_id`、`event_type` 或 schema 字段。

### 6. Catalog 也必须受控

Catalog 不是运行时权威状态，但它会实例化为 WorldState 实体。因此 catalog 字段也必须经过字段域 validator。

### 7. schema 默认拒绝额外字段

所有权威 schema 默认 `additionalProperties=false`。未声明字段必须被拒绝，或进入迁移工具的 warning，不得静默写入。

## FieldSpec(path)

`FieldSpec(path)` 是字段治理的最小权威单元。`FieldDomainKind` 只表示某一种值约束，不再表示字段的完整规则。一个字段可以同时拥有多个约束，validator 必须取所有约束的交集。

字段声明结构：

```json
{
  "path": "WeatherState.generated_by.rule_id",
  "base_type": "string",
  "value_constraints": [
    {
      "kind": "registry",
      "registry": "weather_rule_id"
    },
    {
      "kind": "id_format",
      "format": "dot_separated_rule_id"
    }
  ],
  "reference_target": "WeatherRuleRegistry.rule_id",
  "write_policy": {
    "allowed_writers": ["WeatherFormation", "WeatherResolver", "TestFixture"],
    "allowed_operations": ["create", "update"],
    "default": "deny"
  },
  "derivation_policy": {
    "kind": "produced_by_rule",
    "producer_field": "generated_by.system"
  },
  "unit": null,
  "precision": null,
  "version": "2026-07-11"
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `path` | 完整 schema path，例如 `WorldChunk.biome_tags`。不能只写短字段名。 |
| `base_type` | JSON 或领域基础类型，例如 `string`、`integer`、`number`、`boolean`、`array<string>`、`object`。 |
| `value_constraints` | 字段必须同时满足的值约束列表，元素的 `kind` 来自 `FieldDomainKind`。 |
| `reference_target` | 当字段引用其他实体、catalog 或 registry 时，声明目标集合和目标字段。无引用时为 `null`。 |
| `write_policy` | 字段级写入策略。最终写入还必须通过架构层 `WriteACL`。 |
| `derivation_policy` | 字段是否必须由确定性规则派生、由 validator 校验或允许手填。 |
| `unit` | 数值单位，例如 `minute`、`meter`、`celsius`、`kg`。非数值字段为 `null`。 |
| `precision` | 数值精度或取整规则，例如 `integer`、`one_decimal`、`two_decimal`。无要求时为 `null`。 |
| `version` | 字段声明版本，用于迁移和重放校验。 |

### 定义字段与引用字段必须分开

短字段名不能决定字段规则。定义一个 ID 的位置和引用一个已定义 ID 的位置必须使用不同完整 schema path 声明。

| schema path | FieldSpec 要点 |
| --- | --- |
| `RuleRegistryEntry.rule_id` | `base_type=string`，`value_constraints=[id_format, unique_in_rule_registry]`，`reference_target=null`。 |
| `WeatherState.generated_by.rule_id` | `base_type=string`，`value_constraints=[registry, id_format]`，`reference_target=WeatherRuleRegistry.rule_id`。 |
| `HazardSource.generated_by.rule_id` | `base_type=string`，`value_constraints=[registry, id_format]`，`reference_target=HazardRuleRegistry.rule_id`。 |
| `ObstacleSource.generated_by.rule_id` | `base_type=string`，`value_constraints=[registry, id_format]`，`reference_target=ObstacleRuleRegistry.rule_id`。 |
| `CatalogEntry.catalog_id` | `base_type=string`，`value_constraints=[id_format, unique_in_content_pack_catalog]`，`reference_target=null`。 |
| `WorldObject.source.catalog_id` | `base_type=string`，`value_constraints=[reference, id_format]`，`reference_target=ContentPackCatalog.catalog_id`。 |
| `ChunkBiomeCandidate.biome_tags` | `base_type=array<string>`，`value_constraints=[registry]`，`reference_target=BiomeTagRegistry.tag`，`derivation_policy=derived_by(ChunkBiomeCandidateDerivation)`。 |
| `RegionBiomeCandidate.biome_tags` | `base_type=array<string>`，`value_constraints=[registry]`，`reference_target=BiomeTagRegistry.tag`，`derivation_policy=derived_by(RegionBiomeCandidateAggregation)`。 |
| `RegionBiomeCandidate.tag_sources` | `base_type=object`，`value_constraints=[structured_object]`；key 必须等于 `RegionBiomeCandidate.biome_tags`，value 是同 Region 已验证 ChunkBiomeCandidate 的目标 chunk ID 有序集合。 |
| `WorldChunk.biome_tags` | `base_type=array<string>`，`value_constraints=[registry]`，`reference_target=BiomeTagRegistry.tag`，`derivation_policy=materialized_from(ChunkBiomeCandidate.biome_tags)`。 |
| `Region.biome_tags` | `base_type=array<string>`，`value_constraints=[registry]`，`reference_target=BiomeTagRegistry.tag`，`derivation_policy=materialized_from(RegionBiomeCandidate.biome_tags)`。 |
| `WorldTimeState.clock.time_band` | `base_type=string`，`value_constraints=[enum]`，`reference_target=null`，`derivation_policy=derived_from(minute_of_day, season, seasonal_daylight_profile)`。 |

规则：

```text
FieldSpec.path 必须唯一。
同名短字段出现在不同 path 时必须分别声明。
value_constraints 内所有约束都必须通过。
derived 字段的派生输出仍必须继续通过 enum、registry、reference、numeric_range 等值约束。
definition path 和 reference path 不能共用同一个 FieldSpec。
```

## FieldDomainKind

`FieldDomainKind` 是 `FieldSpec.value_constraints[].kind` 的闭集，用来表达某一种约束类型。它不能单独决定字段是否可写、是否派生、引用哪里、单位是什么，也不能替代字段所有权。

### enum

字段值来自文档内明确列出的有限闭集。

适用字段：

- `object_type`
- `weather_condition`
- `hazard_type`
- `obstacle_type`
- `event_type`
- `season`
- `time_band`
- `placement.kind`
- `visibility`
- `legal_status`

规则：

```text
值必须完全匹配闭集。
内容包和 LLM proposal 不能新增 enum 值。
新增 enum 值必须修改设计文档、schema 和 validator。
```

### registry

字段值来自注册表。注册表可扩展，但必须通过内容包审核、迁移或设计文档更新。

适用字段：

- 引用已登记规则的 `generated_by.rule_id` 或 LLM proposal rule 选择字段
- `generated_by.system`
- `terrain_tags`
- `biome_tags`
- `risk_tags`
- `danger_tags`
- `habitat_tags`
- `sign_tags`
- `default_tags`
- `cause_tags`
- `catalog.category`

规则：

```text
值必须存在于对应 registry。
registry 条目必须声明 owner、含义、允许使用位置和规则影响。
内容包可以请求新增 registry 条目，但不能绕过 validator。
LLM proposal 不能创建 registry 条目。
```

### reference

字段值引用已存在实体或 catalog 条目。

适用字段：

- `world_id`
- `region_id`
- `chunk_id`
- `site_id`
- `node_id`
- `zone_id`
- `object_id`
- `weather_state_id`
- `source_entity_ids`
- `content_pack_id`
- `active_content_pack_refs[].content_pack_id`
- 引用 catalog 条目的完整字段路径
- `parent_id`
- `previous_weather_state_id`

规则：

```text
引用必须能解析到同一 WorldState、Catalog 或 ContentPack 中的实体。
跨文档引用必须声明目标类型。
引用不存在时 validator 必须拒绝，除非该字段明确允许 nullable。
```

### canonical_hash

字段值是 canonical hash，用于证明内容、registry、规则或状态没有被静默改变。

适用字段：

- `registry_hash`
- `rule_bundle_hash`
- `content_pack_hash`
- `catalog_hash`
- `catalog_entry_hash`
- `state_hash`
- `value_hash`
- `input_hash`
- `output_hash`
- `seed_material_hash`
- `candidate_set_hash`
- `active_content_pack_refs[].content_pack_hash`

规则：

```text
canonical_hash 必须使用 "sha256:<hex>" 格式。
canonical_hash 必须能由对应 payload 按规范化协议重算。
canonical_hash 不能引用文件路径、mtime、加载顺序或注释。
LLM proposal 和内容包不能自报 registry_hash 或 rule_bundle_hash。
```

### id_format

字段是实体 ID，本身不是枚举，但必须满足格式、唯一性和命名空间规则。

适用字段：

- `id`
- `event_id`
- `snapshot_id`
- catalog 条目定义位置的 `catalog_id`
- 规则表或规则注册表定义位置的 `rule_id`

规则：

```text
ID 必须满足 snake_case 或指定前缀格式。
同一命名空间内必须唯一。
ID 不能包含自然语言句子。
ID 不能承载规则含义，规则含义必须放在显式字段中。
```

### numeric_range

字段是数值，必须有单位、范围和精度要求。

适用字段：

- `x`、`y`、`z`
- `hierarchy_depth`
- `allowed_child_count_range.min`
- `allowed_child_count_range.max`
- `minute_of_day`
- `temperature_c`
- `temperature_offset_c`
- `tare_weight_kg`
- `total_weight_kg`
- `contained_mass_kg`
- `capacity.liquid_liters`
- `capacity.mass_kg`
- `capacity.slot_count`
- `quantity_contents[].amount`
- `counts.initial_live_count`
- `counts.current_live_count`
- `counts.reserve_count`
- `CreatureGroup.count`
- `CreatureActor.count_weight`
- `stock.capacity_amount`
- `stock.current_amount`
- `stock.extraction.min_source_amount`
- `stock.extraction.max_source_amount`
- `stock.extraction.source_to_output_ratio`
- `stock.extraction.allowed_loss_ratio`
- `stock.recovery.rate_amount_per_day`
- `stock.recovery.cap_amount`
- `visibility_modifier`
- `civilization_pressure`
- `danger_pressure`
- `abnormal_pressure`
- `confidence`

规则：

```text
必须声明单位。
必须声明最小值、最大值或可接受范围。
浮点字段必须声明是否允许小数。
压力、置信度和归一化倾向默认使用 0.0 到 1.0。
现实物理量不得混入归一化倾向字段；例如温度偏移必须使用 `temperature_offset_c`，不能写入 `base_fields.temperature_offset`。
参与随机抽样的权重不得使用浮点，必须使用确定性随机协议的 weight_uint 整数权重。
```

P1 数值字段最小声明：

| schema path | unit | range | precision | 端点 |
| --- | --- | --- | --- | --- |
| `PlaceHierarchyRegistry.entries[].hierarchy_depth` | hierarchy_depth | 0 到 100 | integer | 双端包含 |
| `PlaceHierarchyRegistry.entries[].allowed_child_count_range.min` | count | 0 到 1000 | integer | 双端包含 |
| `PlaceHierarchyRegistry.entries[].allowed_child_count_range.max` | count | min 到 1000 | integer | 双端包含 |
| `WorldChunk.local_climate.temperature_offset_c` | celsius | -15.0 到 15.0 | one_decimal | 双端包含 |
| `WorldObject.physical.tare_weight_kg` | kg | 0.000 到 100000.000 | three_decimal_string | 双端包含 |
| `WorldObject.derived.total_weight_kg` | kg | 0.000 到 1000000.000 | three_decimal_string | 双端包含，derived |
| `WorldObject.derived.contained_mass_kg` | kg | 0.000 到 1000000.000 | three_decimal_string | 双端包含，derived |
| `WorldObject.derived.occupied_liquid_liters` | liter | 0.000 到 1000000.000 | three_decimal_string | 双端包含，derived |
| `WorldObject.derived.occupied_slot_count` | count | 0 到 1000000 | integer | 双端包含，derived |
| `WorldObject.components.container.capacity.liquid_liters` | liter | 0.000 到 1000000.000 | three_decimal_string | 双端包含 |
| `WorldObject.components.container.capacity.mass_kg` | kg | 0.000 到 1000000.000 | three_decimal_string | 双端包含 |
| `WorldObject.components.container.capacity.slot_count` | count | 0 到 1000000 | integer | 双端包含 |
| `WorldObject.components.container.quantity_contents[].amount` | by `unit` | >= 0 | three_decimal_string 或 integer | 双端包含 |
| `CreaturePopulation.counts.initial_live_count` | count | 0 到 1000000 | integer | 双端包含 |
| `CreaturePopulation.counts.current_live_count` | count | 0 到 1000000 | integer | 双端包含 |
| `CreaturePopulation.counts.reserve_count` | count | 0 到 1000000 | integer | 双端包含 |
| `CreatureGroup.count` | count | 1 到 1000000 | integer | 双端包含 |
| `CreatureActor.count_weight` | count | P1 固定为 1 | integer | 双端包含 |
| `FloraPatch.stock.capacity_amount`、`ResourceDeposit.stock.capacity_amount`、`ResourceNode.stock.capacity_amount` | by `stock.unit` | 0.000 到 1000000000.000 | three_decimal_string | 双端包含 |
| `FloraPatch.stock.current_amount`、`ResourceDeposit.stock.current_amount`、`ResourceNode.stock.current_amount` | by `stock.unit` | 0.000 到 capacity_amount | three_decimal_string | 双端包含 |
| `*.stock.extraction.min_source_amount` | by `stock.unit` | 0.000 到 capacity_amount | three_decimal_string | 双端包含 |
| `*.stock.extraction.max_source_amount` | by `stock.unit` | min_source_amount 到 capacity_amount | three_decimal_string | 双端包含 |
| `*.stock.extraction.source_to_output_ratio` | ratio | 0.001 到 1000.000 | three_decimal_string | 双端包含 |
| `*.stock.extraction.allowed_loss_ratio` | ratio | 0.000 到 1.000 | three_decimal_string | 双端包含 |
| `*.stock.recovery.rate_amount_per_day` | by `stock.unit` per 1440 minutes | 0.000 到 1000000000.000 | three_decimal_string | 双端包含 |
| `*.stock.recovery.cap_amount` | by `stock.unit` | 0.000 到 capacity_amount | three_decimal_string | 双端包含 |

### derived

字段不能手填，必须由确定性规则派生。

适用字段：

- `biome_tags`
- `EnvironmentState.light`
- `EnvironmentState.temperature`
- `EnvironmentState.ground_effects`
- `ChunkEdge.base_passability`
- `ChunkEdge.base_traversal`
- `ChunkEdge.effective_passability`
- `ChunkEdge.effective_traversal`
- `LocationEdge.base_passability`
- `LocationEdge.base_traversal`
- `LocationEdge.effective_passability`
- `LocationEdge.effective_traversal`
- `WeatherState.valid_for`
- `time_band`
- `WorldObject.derived.total_weight_kg`
- `WorldObject.derived.contained_mass_kg`
- `WorldObject.derived.occupied_liquid_liters`
- `WorldObject.derived.occupied_slot_count`
- `CreaturePopulation.derived.group_member_count`
- `CreaturePopulation.derived.active_actor_count`
- `CreaturePopulation.derived.depleted`
- `FloraPatch.derived.harvested`
- `FloraPatch.derived.depleted`
- `ResourceDeposit.derived.depleted`
- `ResourceNode.derived.depleted`

规则：

```text
必须记录派生来源。
派生输出仍必须满足该字段的值域约束；例如 biome_tags 的派生结果必须全部存在于 biome_tag registry，time_band 的派生结果必须属于 time_band enum。
手动写入或 LLM 写入必须被拒绝。
迁移工具可以回填，但权威状态变化必须通过 StateTransition 提交并生成 EventLog；仅不改变权威状态的说明性补录可以写 migration note。
```

### boolean

字段只能是 true 或 false。

适用字段：

- `state.active`
- `state.depleted`
- `removable`
- `portable`
- `locked`
- `requires_light_source`

规则：

```text
不能用 yes/no、1/0、open/closed 替代 boolean。
如果状态超过二值，必须改用 enum。
```

### structured_object

字段是结构化对象，内部字段仍必须逐一声明字段域。

适用字段：

- `placement`
- `physical`
- `components`
- `generated_by`
- `valid_for`
- `derived_from`
- `trigger`
- `effects`
- `mitigations`
- `changes`

规则：

```text
结构字段必须有 schema。
结构内部默认 additionalProperties=false。
不能把未知内容塞进 arbitrary_data、metadata、extra、payload。
确需扩展时必须新增明确字段。
```

### display_text

字段是展示文本或说明文本。

适用字段：

- `name`
- `aliases`
- `description`
- `summary`
- `notes`
- `reason`
- `reasoning_summary`
- `calendar_label`

规则：

```text
可以是自然语言。
不能作为 resolver 输入。
不能作为 validator 判断依据。
可以被 DM/UI 使用。
如果文本中包含规则事实，必须同步写入权威字段。
```

## P0 字段域总表

| 字段族 | FieldSpec 约束 | 说明 |
| --- | --- | --- |
| schema 类型 | `value_constraints=[enum]` | `object_type`、地点 `type`、`weather_condition`、`hazard_type`、`obstacle_type`。 |
| 状态类型 | enum 或 boolean | 多状态用 enum，二值状态用 boolean。 |
| 规则 ID 定义 | `value_constraints=[id_format, unique]` | 规则表或规则注册表中定义的 `rule_id` 必须满足命名格式并在规则命名空间内唯一。 |
| 规则 ID 引用 | `value_constraints=[registry, id_format]`，`reference_target=对应规则表` | `generated_by.rule_id` 等引用字段必须来自对应规则表或规则注册表。 |
| 生成系统 | `value_constraints=[registry]` | `generated_by.system` 必须来自 producer 注册表。 |
| 事件类型 | `value_constraints=[enum]` | `EventLog.event_type` 必须属于事件闭集。 |
| 空间 ID 定义 | `value_constraints=[id_format, unique]` | `World.id`、`Region.id`、`WorldChunk.id`、`Site.id`、`LocationNode.id`、`Zone.id` 定义位置必须唯一。 |
| 空间 ID 引用 | `value_constraints=[reference, id_format]`，`reference_target=目标实体 id` | `region_id`、`chunk_id`、`site_id`、`node_id`、`zone_id` 引用位置必须可解析。 |
| 候选记录 ID 定义 | `value_constraints=[id_format, unique]` | `GeneratorOutputItem.candidate_id` 在同一 WorldGenerationManifest 中唯一，只标识 generation_audit 候选记录。 |
| 候选目标 ID 定义 | `value_constraints=[id_format, unique]` | layout candidate payload 中的 `world_id`、`region_id`、`grid_id`、`chunk_id` 是未来权威实体 ID；在同一目标命名空间唯一。 |
| 候选目标 ID 引用 | `value_constraints=[reference, id_format]`，`reference_target=同一 manifest 已验证候选的目标 ID` | 物化前的 region_id/grid_id/chunk_id 只能解析到同一 manifest 候选，不能解析到不存在的 world_fact。 |
| 候选群系标签 | `value_constraints=[registry]`，并声明 derivation_policy | ChunkBiomeCandidate / RegionBiomeCandidate 的标签必须由指定 deriver 产生，且每个结果仍必须存在于 BiomeTagRegistry。 |
| 区域群系来源映射 | `value_constraints=[structured_object]` | RegionBiomeCandidate.tag_sources 的 key 与 biome_tags 完全一致；每个值是同 Region 候选 chunk ID 的稳定有序集合。 |
| 阶段依赖引用 | `value_constraints=[reference, id_format]`，`reference_target=WorldGenerationManifest.stage_contract_ids` | `depends_on_stage_contract_ids[]` 必须引用本 manifest 阶段，并额外通过 DAG 校验。 |
| 阶段执行 scope | `value_constraints=[enum]` | `GenerationStageContract.execution_scope` 必须属于生成协议闭集。 |
| 阶段并行开关 | `value_constraints=[boolean]` | `GenerationStageContract.parallelizable` 只能表示是否允许不同 scope ID 分区并行。 |
| 原子提交组 ID | `value_constraints=[id_format]` | `atomic_commit_group_id` 在同一 manifest 内标识全有或全无的提交组；不为空时组内至少两个输出项。 |
| 对象 ID 定义 | `value_constraints=[id_format, unique]` | `WorldObject.id` 定义位置必须唯一。 |
| 对象 ID 引用 | `value_constraints=[reference, id_format]`，`reference_target=WorldObject.id` | `object_id`、`source_entity_ids` 引用位置必须可解析。 |
| catalog ID 定义 | `value_constraints=[id_format, unique]` | catalog 条目定义位置的 `catalog_id` 必须在内容包 catalog 内唯一。 |
| catalog ID 引用 | `value_constraints=[reference, id_format]`，`reference_target=ContentPackCatalog.catalog_id` | 引用 catalog 条目的字段必须解析到已启用 ContentPack 中的 catalog 条目。 |
| tags | `value_constraints=[registry]` | 所有 `*_tags` 和 `tags` 必须属于对应 tag registry。 |
| 数值 | `value_constraints=[numeric_range]`，必须声明 `unit` 与 `precision` | 坐标、时间、温度、重量、容量、压力、非随机权重、置信度必须有范围；随机抽样权重必须走 `weight_uint`。 |
| 派生字段 | `derivation_policy=derived_by(...)`，并叠加具体值约束 | 不能由 LLM 或内容包直接写入最终值。 |
| 展示文本 | `value_constraints=[display_text]` | 允许自然语言，但不能驱动规则。 |

## Tag Registry

### 统一规则

所有 tag registry 条目必须包含：

```json
{
  "tag": "wind_exposed",
  "registry": "terrain_tag",
  "meaning": "暴露在强风影响下的地形或空间",
  "allowed_on": ["LocationNode.tags"],
  "produced_by": ["LocationGenerator"],
  "consumed_by": ["WeatherFormation", "HazardObstacleDeriver"],
  "rule_effect": "提高 strong_wind 权重，并支持风暴相关风险",
  "owner_doc": "02-world-model/climate-terrain-formation-rules.md"
}
```

规则：

```text
同一个 tag 只能属于一个主 registry。
同名 tag 不能在不同 registry 中表达不同含义。
tag 不能代替权威字段。
tag 的 rule_effect 必须明确，没有规则影响的 tag 只能用于检索或叙事。
```

### P0 registry 分类

| registry | 用途 | 典型字段 |
| --- | --- | --- |
| `terrain_tag` | 地形辅助标签 | `terrain_tags`、`LocationNode.tags` 中的地形类标签。 |
| `biome_tag` | 生态环境标签 | `biome_tags`、`habitat_tags`。 |
| `danger_tag` | 区域危险倾向 | `danger_tags`。 |
| `risk_tag` | 行动或路径风险 | `risk_tags`、`trigger.conditions` 中的可验证风险标签。 |
| `object_tag` | 对象辅助标签 | `WorldObject.tags`、catalog `default_tags`。 |
| `social_tag` | 未来社会系统标签 | AI 社会心智和 faction 相关标签。 |
| `origin_tag` | 静态来历标签 | `origin.cause_tags`。 |
| `sign_tag` | 痕迹和线索标签 | 生态 catalog `sign_tags`。 |
| `catalog_category` | catalog 分类 | `generic_item_catalog.category`、`container_catalog.category`。 |

## Registry 条目生命周期

### 新增流程

```text
1. 提出新增字段值或 tag。
2. 指定 registry。
3. 写明 meaning、allowed_on、produced_by、consumed_by、rule_effect。
4. 更新对应设计文档。
5. 更新 validator。
6. 增加测试。
7. 只有通过 validator 后才能进入内容包或 WorldState。
```

### 禁止流程

```text
不得由 LLM proposal 新增 registry 条目。
不得由 DM 文本新增 registry 条目。
不得因为 catalog 里出现新字符串就自动注册。
不得把无法分类的字段放进 misc、extra、metadata。
```

## LLM Proposal 字段域规则

LLM proposal 的字段分为四类。AI 社会 proposal 的 canonical schema 和 action 闭集由 `04-ai-simulation/ai-social-mind-rules.md` 定义；本节定义字段域总约束。

### 系统拥有字段

以下字段只能由 scheduler、snapshot builder、proposal recorder、validator、conflict resolver 或 deterministic resolver 写入。LLM 输出任一同名字段时必须拒绝整个 payload，不能采信或静默删除该字段后继续执行：

```text
proposal_id
proposal_kind
decision_tick_id
decision_slot_key
attempt_no
subject
subject_state_revision
observation_snapshot_id
based_on_event_sequence
read_set
idempotency_key
valid_until_game_time
causal_context
computed_policy
status
validation
resolution
trigger_priority
conflict_keys
required_preconditions
resource_claims
```

### 可选择字段

必须从已注册值中选择：

```text
action_type
target_refs[].kind
target_refs[].id
object_type
weather_condition
hazard_type
obstacle_type
rule_id
tag
event_type
```

### 可引用字段

必须引用已存在实体：

```text
world_id
region_id
chunk_id
site_id
node_id
zone_id
object_id
npc_id
source_entity_ids
```

### 可自由文本字段

只允许用于解释，不能驱动规则：

```text
reason
reasoning_summary
narration_hint
summary
```

### LLM 可提交的 AI 社会行动字段

P0 LLM payload 只能包含：

```text
action_type
target_refs
arguments
reasoning_summary
confidence_basis_points
```

`LLMDecisionAdapter` 校验成功后，才把以上五个字段映射到 `AIProposalEnvelope.action.*`。`arguments` 不是开放对象；它必须命中对应 `action_type` 的参数 schema，未知参数、额外参数和嵌套自由对象必须拒绝。`reasoning_summary` 只能用于审计和叙事风格，不能转换为 StateTransition。

AI 社会 proposal 的关键 FieldSpec 引用关系：

| schema path | 字段域 |
| --- | --- |
| `AIProposalEnvelope.action.action_type` | registry，引用 `AIActionPolicyRegistry.action_type` |
| `AIProposalEnvelope.action.target_refs[].kind` | enum，引用 AI 社会心智规则的 `target_ref.kind` 闭集 |
| `AIProposalEnvelope.action.target_refs[].id` | reference，目标类型由同元素 kind 判别 |
| `AIProposalEnvelope.action.arguments` | schema_ref，由对应 `AIActionPolicyEntry.argument_schema_id` 唯一选择 |
| `AIProposalEnvelope.action.confidence_basis_points` | numeric_range，integer，0 到 10000 |
| `AIActionPolicyEntry.*_rule_id / resolver_id` | registry + id_format，必须引用对应规则注册表 |
| `AIActionPolicyEntry.allowed_event_types[]` | enum，引用 event_type 闭集 |

每个 active `action_type` 必须且只能有一个 active `AIActionPolicyEntry`，并参与 `rule_bundle_hash`。内容包和 LLM 都不能新增或覆盖 action policy。

LLM proposal validator 必须拒绝：

```text
未知字段。
未知 enum 值。
未知 registry 值。
不存在的 reference。
试图直接写 WorldState 的字段。
试图提交系统拥有字段。
action_type 不属于当前 AgentObservationSnapshot.available_actions。
target_refs 不属于当前 AgentObservationSnapshot.available_target_refs。
arguments 超出当前 AgentObservationSnapshot.action_argument_domains。
试图通过 reason、summary、description 让 resolver 执行规则变化。
```

## Catalog 字段域规则

Catalog 条目必须同时满足 catalog schema 和字段域 schema。

Catalog envelope 必须满足版本字段要求：

```text
schema_version 必须存在。
content_pack_id 必须满足 id_format。
content_pack_version 必须存在，并参与 content_pack_hash。
kind 必须属于 catalog_kind 闭集。
catalog_version 必须存在，并参与 content_pack_hash。
payload 根字段必须与 kind 对应。
```

P0 要求：

```text
catalog_id 必须满足 id_format。
object_type 必须属于闭集。
category 必须属于 catalog_category registry。
default_tags 必须属于 object_tag registry。
default_affordances 必须属于 affordance 闭集。
physical_override 内部字段必须逐一声明字段域。
container_override 内部字段必须逐一声明字段域。
Catalog 不能包含未声明字段。
Catalog 不能通过 description 暗示规则能力。
Catalog 实例化后必须再次运行 WorldObjectValidator。
Catalog、registry 和 rule bundle 的 canonical hash 必须使用同一规范化协议。
```

示例：

```json
{
  "catalog_id": "container_waterskin",
  "name": "水囊",
  "object_type": "container",
  "category": "liquid_container",
  "default_tags": ["leather", "water_container"]
}
```

其中：

```text
CatalogEntry.catalog_id -> id_format
name -> display_text
object_type -> enum
category -> catalog_category registry
default_tags -> object_tag registry
```

## Registry 与 Rule Bundle 版本规则

所有 enum、registry、FieldSpec、schema、WriteACL、event_type、affordance 和 action policy 都必须能进入版本锁。

### RegistryBundle

`registry_hash` 必须覆盖：

```text
FieldSpec registry
enum registry
tag registry
reference registry
CanonicalEntitySchemaRegistry
EntityAuthorityDomain
FieldOwnership
WriteACL
event_type enum
affordance enum
catalog_kind enum
```

规则：

```text
同一 registry_id + registry_version 只能产生一个 canonical hash。
registry entry 的排序必须稳定。
registry hash 不得包含文件 mtime、加载路径、注释或运行环境。
registry_hash 变化后，旧 Snapshot 不能直接按新 registry 解释，必须通过迁移或兼容校验。
```

### RuleBundle

`rule_bundle_hash` 必须覆盖：

```text
WorldGenerator rule versions
Deriver rule versions
Resolver rule versions
Validator versions
Materializer versions
AIActionPolicyRegistry
Migration rule versions
Deterministic random protocol version
```

规则：

```text
任何会改变生成结果、校验结果、物化结果或行动结算结果的规则变更，都必须改变 rule_bundle_hash。
内容包和 LLM 不能声明或覆盖 rule_bundle_hash。
运行时加载 Snapshot 时，runtime.rule_bundle_hash 与 snapshot.version_lock.rule_bundle_hash 不一致，必须进入迁移或拒绝恢复。
```

## EventLog 字段域规则

EventLog 是权威状态账本，字段域必须严格。

```text
event_type 必须属于 event_type enum。
caused_by.kind 必须属于 event_cause_kind enum。
caused_by.id 必须引用 producer、resolver、AI runtime component、migration、test fixture 或用户动作记录。
changes[].op 必须属于 change_op enum。
changes[].entity_type 必须属于 entity_type registry。
changes[].entity_id 必须满足 reference 或 create 语义。
changes[].path 必须是 schema 注册路径。
changes[].value 必须通过目标字段域 validator。
summary 是 display_text，不能作为状态恢复依据。
```

P0 `change_op` 闭集：

```text
create
update
deactivate
delete_for_migration
```

`change_op` 的唯一权威定义只能出现在本节。运行时、世界模型、生成清单和具体 resolver 文档只能引用本闭集，不得重新定义第二套 `changes[].op` 值域。

`change_op` 只用于 EventLog `changes[].op`。WriteACL `operation` 和生成阶段 `GeneratorOutputItem.operation` 是上游权限/生成语义，不是 EventLog change payload 语义；`materialize`、`derive`、`propose`、`project_read` 不能出现在 `changes[].op` 中。

语义边界：

```text
create：创建完整规范化实体。
update：更新已存在实体的已注册字段。
deactivate：把可停用实体切换为 inactive/expired/depleted 等 schema 允许的非活动状态。
delete_for_migration：仅迁移工具可用，用于删除旧 schema 下不可保留的字段或实体。
```

`move`、`link`、`unlink`、`consume`、`open`、`close`、`equip` 等都是业务语义，不是底层 `change_op`。它们必须通过 `event_type`、`caused_by.id`、resolver 名称和一组确定的 `update/create/deactivate` changes 表达。

P0 `event_cause_kind` 闭集：

```text
world_generator
time_service
weather_service
resolver
ai_runtime
migration_tool
test_fixture
user_action
```

## Schema 规则

所有权威 schema 必须满足：

```text
additionalProperties=false。
required 字段必须明确。
nullable 字段必须显式声明。
数组字段必须声明 item 字段域。
字典字段必须声明 key 格式和 value 字段域。
所有 enum 和 registry 字段必须大小写敏感。
所有 display_text 字段必须禁止作为 resolver 输入。
```

新增字段必须写入字段说明表：

```text
完整 schema path
base_type
value_constraints[]
允许值或引用目标
write_policy
derivation_policy
unit
precision
是否可为空
是否可由 LLM proposal 提交
是否可由 content pack 提交
是否可由 resolver 修改
是否进入 EventLog
```

### 主体认知字段禁用集

主体认知字段回答“谁知道、看见、听说、记住或可以被告知某件事”。这类字段只能出现在 `KnowledgeState`、`DiscoveryState`、`RumorState`、`SecretState` 或 `AgentObservationSnapshot` 等知识/投影实体中，不能出现在世界事实 schema 中。

P0 禁用字段名闭集：

```text
known_to_player
known_by
unknown_to
discovered_by
seen_by
heard_by
rumored_by
secret_holders
visible_to_subjects
can_tell_player
withholding_reason
npc_memory
player_memory
ai_context
```

规则：

```text
如果 EntityType 属于 world_facts，FieldDomainValidator 必须拒绝任何 path segment 命中主体认知字段禁用集的字段。
该拒绝优先于 FieldOwnership、WriteACL、catalog、generator envelope 和 EventLog。
WorldChunk.known_to_player、ChunkEdge.visibility.known_to_player、Site.state.known_to_player 必须全部被拒绝。
如果需要表达“主体知道空间事实”，必须创建或更新 DiscoveryState / KnowledgeState。
```

### 知识事实物理字段禁用集

知识事实只能引用世界事实、历史事件或运行事件，不能复制或替代物理世界状态。

P0 禁用字段名闭集：

```text
placement
location
terrain
water_presence
hydrology
physical
components
container
contents
resource_quantity
passability
travel_cost
weather_type
temperature
light
hit_points
damage_state
locked
enterable
```

规则：

```text
如果 EntityType 属于 knowledge_facts，FieldDomainValidator 必须拒绝任何 path segment 命中知识事实物理字段禁用集的字段。
KnowledgeState.target.locked、DiscoveryState.target.placement、RumorState.target.resource_quantity 必须全部被拒绝。
如果主体知道“门被锁了”，世界事实仍写 WorldObject.state.locked=true，主体认知只写 KnowledgeState / DiscoveryState 对该目标的引用和认知等级。
```

## Validator 规则

实现时必须增加 `FieldDomainValidator`，并作为所有 validator 的前置或公共依赖。

必须保证：

1. 所有完整 schema path 都能找到 FieldSpec 声明。
2. FieldSpec.path 必须唯一，definition path 和 reference path 必须分别声明。
3. FieldSpec.value_constraints 内所有约束都必须通过，不能只通过其中一个。
4. enum 字段必须属于闭集。
5. registry 字段必须存在于对应 registry。
6. reference 字段必须能解析到 FieldSpec.reference_target 指向的目标实体、catalog 或 registry。
7. id_format 字段必须满足命名规范和唯一性。
8. numeric_range 字段必须满足范围、单位和精度。
9. derived 字段不能由 LLM proposal 或 content pack 直接写入最终值，且派生输出必须继续通过 enum、registry、reference、numeric_range 等值域校验。
10. boolean 字段只能是 true 或 false。
11. structured_object 内部字段必须逐一校验。
12. display_text 字段不能被 resolver 作为规则输入。
13. schema 未声明字段必须被拒绝。
14. catalog 条目必须运行字段域 validator。
15. LLM proposal 必须运行字段域 validator。
16. EventLog.changes[].value 必须运行目标字段域 validator。
17. 同名字段出现在不同 schema path 时，validator 必须按 path 选择 FieldSpec，不能按短字段名猜测语义。
18. world_facts 实体的任意 schema path segment 命中主体认知字段禁用集时必须被拒绝。
19. knowledge_facts 实体的任意 schema path segment 命中知识事实物理字段禁用集时必须被拒绝。
20. candidate_id 与候选 payload 的未来目标 ID 必须使用不同 FieldSpec path，不能互相替代。
21. 候选目标 ID 引用必须解析到同一 manifest 中已经验证的对应 layout candidate。
22. `depends_on_stage_contract_ids` 除 reference 校验外还必须通过无环和前置完成校验。
23. `atomic_commit_group_id` 相同的输出必须通过原子组完整性校验。

## 推荐实现顺序

### P0.1：FieldSpec 声明表

- 为现有核心 schema 建立 FieldSpec 声明表。
- 覆盖 World、Region、WorldChunk、空间基础 Candidate、GenerationStageContract、GeneratorOutputItem、Site、LocationNode、Zone、WorldObject、WorldTimeState、WeatherState、EnvironmentState、HazardSource、ObstacleSource、EventLog。

验收：

```text
任一 schema 字段找不到 FieldSpec 会被测试拒绝。
新增字段未登记会被测试拒绝。
definition path 和 reference path 共用声明会被测试拒绝。
FieldSpec.value_constraints 未全部通过会被测试拒绝。
time_band 缺少 enum 或 derivation_policy 会被测试拒绝。
biome_tags 缺少 registry 或 derivation_policy 会被测试拒绝。
```

### P0.2：Tag Registry

- 建立 terrain_tag、biome_tag、danger_tag、risk_tag、object_tag、origin_tag、sign_tag、catalog_category registry。
- 先收录现有文档和 catalog 已使用的 tag。
- 未能解释的 tag 不能进入 registry。

验收：

```text
WorldObject.tags 使用未注册 object_tag 会被拒绝。
WorldChunk.terrain_tags 使用未注册 terrain_tag 会被拒绝。
Catalog.default_tags 使用未注册 object_tag 会被拒绝。
```

### P0.3：Catalog 字段域校验

- GenericItemCatalogValidator 接入 FieldDomainValidator。
- ContainerCatalogValidator 接入 FieldDomainValidator。
- catalog 条目禁止未声明字段。

验收：

```text
catalog 条目新增 random_power 字段会被拒绝。
catalog 条目 category 不在 catalog_category registry 会被拒绝。
catalog 条目 default_tags 不在 object_tag registry 会被拒绝。
```

### P0.4：LLM Proposal 字段域校验

- 所有 LLM proposal 输出先过 FieldDomainValidator。
- LLM proposal 只能选择已注册值或引用已存在实体。
- display_text 字段不能转成状态变更。

验收：

```text
LLM proposal 提出新 object_type 会被拒绝。
LLM proposal 提出新 tag 会被拒绝。
LLM proposal 在 reason 中要求发钥匙，不会直接写 WorldState。
```

### P0.5：EventLog 变更值校验

- EventLog.changes[].value 必须按目标 schema 字段域校验。
- EventLog.summary 不能作为恢复状态来源。

验收：

```text
EventLog 尝试写未知 enum 值会被拒绝。
EventLog.changes[].path 指向未注册字段会被拒绝。
```

## 测试清单

```text
test_all_schema_fields_have_field_domain_kind
test_unknown_schema_field_is_rejected
test_enum_field_rejects_unknown_value
test_registry_field_rejects_unknown_value
test_reference_field_rejects_missing_entity
test_numeric_range_rejects_out_of_range
test_derived_field_rejects_llm_write
test_display_text_cannot_drive_resolver
test_catalog_rejects_unknown_field
test_catalog_rejects_unknown_tag
test_llm_proposal_rejects_new_enum_value
test_llm_proposal_rejects_new_registry_value
test_event_log_change_value_runs_target_validator
test_world_fact_rejects_subject_cognition_field_path_segment
test_world_fact_rejects_known_to_player_under_nested_visibility
test_knowledge_fact_rejects_physical_field_path_segment
test_candidate_record_id_and_target_entity_id_use_distinct_field_specs
test_candidate_target_reference_requires_same_manifest_candidate
test_chunk_biome_candidate_tag_must_exist_in_biome_registry
test_region_biome_candidate_tag_sources_match_tag_keys
test_region_biome_candidate_tag_sources_reference_same_region_chunks
test_stage_dependency_reference_requires_manifest_stage_contract
test_stage_dependency_graph_rejects_cycle
test_atomic_commit_group_id_rejects_partial_group
```

## 已确认决策

1. 不是所有字段都必须是有限 enum。
2. 所有规则字段必须受控。
3. 所有引用字段必须可解析。
4. 所有数值字段必须有范围。
5. 所有自由文本字段只能展示或解释，不能驱动规则。
6. 所有 tag 必须进入对应 registry。
7. Catalog 不是权威状态，但必须接受字段域校验。
8. LLM proposal 不能新增字段值、tag、rule_id 或 schema 字段。
9. 权威 schema 默认拒绝未声明字段。
10. 候选记录身份和未来权威实体身份是不同字段域，不能因字符串相同而混用。
11. 生成阶段依赖和原子提交组属于可校验治理字段，不能只依赖文档段落约定。
