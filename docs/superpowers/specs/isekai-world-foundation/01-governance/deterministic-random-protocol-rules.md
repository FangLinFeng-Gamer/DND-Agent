---
doc_id: isekai.deterministic_random_protocol_rules
status: active
layer: governance
owner: architecture
created_at: 2026-07-14
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
provides:
  - DeterministicRandomProtocol
  - RandomSeedMaterial
  - RandomStreamRef
  - RandomDrawRef
  - WeightedChoiceKernel
  - CandidateOrderingRule
  - DeterministicRandomValidator
---

# 异世界模式确定性随机协议

## 背景

世界生成需要大量随机：地形基础场、天气转移、生态候选、资源数量、聚落状态、历史候选、物品实例等。如果只说“使用 seed”，不同实现仍会在以下位置分叉：

- PRNG 或 hash 算法不同。
- seed 编码不同。
- 不同规则共用同一随机流。
- 候选排序不同。
- 一个候选被 validator 拒绝后是否重抽不同。
- 权重使用浮点、百分比或文本 rarity，导致概率核不同。
- ChunkBaseFields 按遍历顺序读取邻接 chunk，导致并行和串行结果不同。

本设计定义 P0 统一确定性随机协议。所有世界生成器、天气推进、AI proposal 接受后的确定性仲裁、内容包物化和测试夹具，只要需要随机，都必须使用本协议。

## 目标

- 相同 `world_seed + schema_version + registry_hash + rule_bundle_hash + content_pack_hash` 必须得到相同随机结果。
- 不同 rule、随机作用域和 logical draw 必须使用独立随机流，避免新增抽样影响其他抽样。
- 候选排序、去重、权重归一化、零权重 fallback 和 tie-break 必须可机器实现。
- Validator 拒绝某个候选不能改变其他 logical draw 的结果。
- 随机内核必须在有限步内产生确定结果或确定失败，不能依赖“几乎必然成功”的无限循环。
- 所有随机引用必须能进入 `WorldGenerationManifest`，用于审计、重放和 hash 校验。

## 非目标

- 不追求密码安全随机。
- 不模拟连续概率分布。
- 不允许 LLM 直接决定随机结果。
- 不替代业务规则；随机只在规则允许的候选集合内选择。

## 核心原则

### 1. 随机是纯函数

随机结果必须是以下输入的纯函数：

```text
protocol_version
world_seed
schema_version
registry_hash
rule_bundle_hash
content_pack_hash
domain
rule_id
scope_id
logical_draw_id
draw_index
```

不得读取系统时间、执行顺序、线程 ID、数据库自增 ID、内存地址、数组当前插入顺序或 LLM 文本长度。

### 2. 每个 logical draw 独立

一个 logical draw 表示一件逻辑随机决策，例如：

```text
选择某 chunk 的 landform noise 值
选择某 Region 下一段天气
选择某 chunk 的植物候选
选择某聚落是否生成旅店
选择某容器实例 ID 后缀
```

新增、删除或重试另一个 logical draw，不能改变当前 logical draw 的结果。

### 3. 候选先稳定，再抽样

任何随机选择必须先构造 `CandidateSet`：

```text
候选生成
-> candidate_id 规范化
-> 去重
-> 稳定排序
-> 权重计算
-> WeightedChoiceKernel
```

不能从未排序的 map、数据库返回顺序或内容包原始加载顺序中直接抽样。

### 4. Validator 拒绝不触发全局重抽

如果抽中的候选无法通过 validator，生成器只能按该 rule 声明的 `rejection_policy` 处理。它不能消耗下一个全局随机数，也不能改变其他 `logical_draw_id`。

### 5. 所有权重使用整数

P0 禁止使用浮点概率作为抽样输入。所有概率必须转成非负整数权重。

```text
weight_uint: uint32
0 <= weight_uint <= 1_000_000
```

## 随机输入模型

### RandomSeedMaterial

`RandomSeedMaterial` 是所有随机流的根输入。

```json
{
  "protocol_version": "drp.v1",
  "world_seed": "graystone-seed-001",
  "schema_version": "isekai-world-foundation@1",
  "registry_hash": "sha256:registry_hash",
  "rule_bundle_hash": "sha256:rule_bundle_hash",
  "content_pack_hash": "sha256:content_pack_hash"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `protocol_version` | 随机协议版本。P0 固定为 `drp.v1`。 |
| `world_seed` | 玩家或系统提供的世界种子，按 UTF-8 字符串处理。 |
| `schema_version` | 世界底座 schema 版本。 |
| `registry_hash` | enum、registry、FieldSpec 和 schema 的 canonical hash。 |
| `rule_bundle_hash` | 生成规则、validator、resolver 版本的 canonical hash。 |
| `content_pack_hash` | 内容包和 catalog 的 canonical hash。 |

规则：

```text
world_seed 不能为空字符串。
hash 字段必须使用 sha256:<hex> 格式。
RandomSeedMaterial 必须写入 WorldGenerationManifest。
```

## PRF 与抽样算法

### CanonicalBytes

所有参与 hash 或 PRF 的结构必须先转成 canonical JSON：

```text
UTF-8 编码。
对象 key 按 Unicode code point 升序。
数组顺序必须由规则显式给出。
不允许 NaN、Infinity 或浮点权重。
字符串不做本地化大小写折叠。
数字只允许整数或已声明 precision 的定点十进制字符串。
```

### PRF

P0 使用 HMAC-SHA256 作为 PRF：

```text
seed_key = HMAC-SHA256(
  key = "isekai.deterministic_random.drp.v1",
  message = CanonicalBytes(RandomSeedMaterial)
)

draw_digest = HMAC-SHA256(
  key = seed_key,
  message = CanonicalBytes({
    "domain": domain,
    "rule_id": rule_id,
    "scope_id": scope_id,
    "logical_draw_id": logical_draw_id,
    "draw_index": draw_index
  })
)
```

`draw_uint64` 使用 `draw_digest` 前 8 字节按 big-endian 解释为无符号整数。

### random_int_exclusive

`random_int_exclusive(n)` 成功时返回 `[0, n)` 的整数；失败时返回确定性 `random_failure_code`。

规则：

```text
n 必须是整数，且 1 <= n <= 2^64。
使用 rejection sampling 避免 modulo bias。
P0 random_int_exclusive_max_attempts = 32。
limit = floor(2^64 / n) * n。
从 draw_index=0 开始尝试，最多尝试 32 次。
如果 draw_uint64 < limit，结果为 draw_uint64 mod n，并记录接受该结果的 draw_index。
如果 draw_uint64 >= limit，则 draw_index 加 1，重新计算同一个 logical_draw_id。
如果 32 次尝试后仍没有 draw_uint64 < limit，返回 failure_code=random_int_rejection_exhausted。
如果 n 不在合法范围内，返回 failure_code=random_int_invalid_bound，且不得消耗随机 draw。
重试只属于当前 logical_draw，不影响其他 logical_draw。
调用方不能在 random_int_exclusive 失败后切换到 modulo、系统随机数、相邻 logical_draw_id 或未声明 fallback。
```

### random_fixed_unit

需要 0 到 1 定点值时使用：

```text
random_fixed_unit = draw_uint64 / (2^64 - 1)
```

只能用于派生已声明 precision 的定点字段。不能把该值直接当作概率权重参与候选选择。

## RandomStreamRef

`RandomStreamRef` 表示一个随机流。

```json
{
  "protocol_version": "drp.v1",
  "domain": "weather_generation",
  "rule_id": "weather.transition_by_climate_season_terrain",
  "scope_id": "region:north_slope_wilds",
  "seed_material_hash": "sha256:seed_material_hash"
}
```

P0 `domain` 闭集：

```text
world_base
spatial_layout
region_climate
chunk_base_fields
terrain_formation
hydrology_formation
local_climate_derivation
settlement_anchor
origin_history_candidate
static_edge
static_traversal
biome_derivation
resource_formation
flora_formation
fauna_formation
site_placement
object_materialization
settlement_social
origin_history_materialization
weather_generation
environment_derivation
hazard_obstacle
initial_knowledge
runtime_resolver
test_fixture
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `protocol_version` | 随机协议版本。 |
| `domain` | 随机域，必须属于闭集。 |
| `rule_id` | 使用随机的规则 ID。 |
| `scope_id` | 本次随机作用范围。 |
| `seed_material_hash` | `RandomSeedMaterial` 的 canonical hash。 |

`scope_id` 格式：

```text
world:<world_id>
region:<region_id>
chunk:<chunk_id>
chunk_edge:<edge_id>
site:<site_id>
location_node:<location_node_id>
zone:<zone_id>
object:<object_id>
settlement:<settlement_id>
named_npc:<named_npc_id>
event:<event_id>
test:<fixture_id>
```

`RandomStreamRef.scope_id` 表示随机流作用域，不等同于 `FormationRuleContract.target_scope.kind` 或 `GeneratorOutputItem` 的 `target_scope_id`。目标作用域只用于说明规则输出归属、排序、冲突处理和审计；随机作用域必须由规则随机声明和实际抽样语义选择。目标专用类别例如 `resource_node`、`resource_deposit`、`flora_patch`、`population` 不因为出现在 target scope 中就自动成为 DRP scope_id 前缀；需要按这些实体独立拆分随机流时，必须先在本协议版本中登记对应前缀。

在空间基础物化前，`world:<world_id>`、`region:<region_id>` 和 `chunk:<chunk_id>` 可以引用同一 manifest 中已经通过校验的布局候选目标 ID。此时 `GenerationInputRef.input_class` 仍必须是 `candidate`，不能因为 scope_id 使用未来目标 ID 就把它标记成已提交 world_fact。

## RandomDrawRef

`RandomDrawRef` 表示一次具体抽样。

```json
{
  "stream_ref": {
    "protocol_version": "drp.v1",
    "domain": "flora_formation",
    "rule_id": "flora.select_species_for_chunk",
    "scope_id": "chunk:chunk_12_08_02",
    "seed_material_hash": "sha256:seed_material_hash"
  },
  "logical_draw_id": "candidate_species_slot_001",
  "draw_index": 0,
  "draw_kind": "weighted_choice",
  "candidate_set_hash": "sha256:candidate_set_hash",
  "result_id": "plant_species:nightmare_grass"
}
```

P0 `draw_kind` 闭集：

```text
uint64
int_range
fixed_unit
weighted_choice
shuffle_order
id_suffix
```

P0 `random_failure_code` 闭集：

```text
random_int_invalid_bound
random_int_rejection_exhausted
```

规则：

```text
logical_draw_id 必须由规则在 FormationRuleContract.random.random_draws 中显式命名，不能使用循环下标的当前执行顺序。
同一个 GeneratorOutputEnvelope 内，RandomDrawRef 必须按 stream_ref、logical_draw_id、draw_index 排序。
candidate_set_hash 只在 weighted_choice 和 shuffle_order 中必填。
成功抽样时，result_id 必须引用被选中的候选或派生结果。
抽样失败且已消耗合法 draw 时，result_id 必须使用 random_failure:<random_failure_code>，例如 random_failure:random_int_rejection_exhausted。
random_int_invalid_bound 属于调用参数校验失败；不得伪造 RandomDrawRef，应由调用方的 validator 或 failure_behavior 记录确定性失败。
```

## CandidateSet

候选集合必须规范化后才能抽样。

```json
{
  "candidate_set_id": "flora_candidates_chunk_12_08_02",
  "rule_id": "flora.select_species_for_chunk",
  "scope_id": "chunk:chunk_12_08_02",
  "items": [
    {
      "candidate_id": "plant_species:birch",
      "sort_key": "plant_species:birch",
      "weight_uint": 1000,
      "source_ref": "plant_species:birch"
    },
    {
      "candidate_id": "plant_species:nightmare_grass",
      "sort_key": "plant_species:nightmare_grass",
      "weight_uint": 100,
      "source_ref": "plant_species:nightmare_grass"
    }
  ],
  "zero_weight_policy": "select_none",
  "rejection_policy": "reject_output"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `candidate_set_id` | 候选集合 ID。 |
| `rule_id` | 构造候选集合的规则。 |
| `scope_id` | 候选集合作用范围。 |
| `items[].candidate_id` | 稳定候选 ID。 |
| `items[].sort_key` | 稳定排序 key。 |
| `items[].weight_uint` | 非负整数权重。 |
| `items[].source_ref` | 候选来源，例如 catalog、species、rule。 |
| `zero_weight_policy` | 总权重为 0 时的处理。 |
| `rejection_policy` | 抽中候选被 validator 拒绝时的处理。 |

P0 `zero_weight_policy` 闭集：

```text
select_none
select_first_stable
validation_error
```

P0 `rejection_policy` 闭集：

```text
reject_output
select_none
select_first_remaining_stable
```

规则：

```text
candidate_id 必须唯一；重复 candidate_id 必须合并或拒绝，不能保留重复项。
合并时 weight_uint 相加，但总和不能超过 1_000_000。
排序顺序为 sort_key 升序，再 candidate_id 升序。
weight_uint=0 的候选保留在 candidate_set_hash 中，但不参与 weighted_choice。
候选集合为空时，只能 select_none 或 validation_error。
```

## WeightedChoiceKernel

加权选择算法：

```text
1. 过滤 weight_uint > 0 的 candidates。
2. 按 sort_key、candidate_id 稳定排序。
3. total_weight = sum(weight_uint)。
4. 若 total_weight = 0，执行 zero_weight_policy。
5. r = random_int_exclusive(total_weight)。
6. 如果 random_int_exclusive 返回 failure_code，WeightedChoiceKernel 必须返回同一 failure_code，不能改用 modulo 或其他候选选择策略。
7. 从头累计权重，选择第一个 cumulative_weight > r 的候选。
```

Tie-break：

```text
如果多个候选在业务层得分相同，仍只按 sort_key 和 candidate_id 排序。
如果候选需要随机打乱，必须为每个 candidate_id 生成独立 shuffle_key，再按 shuffle_key、candidate_id 排序。
```

## 标准权重表

### rarity_weight

P0 `rarity` 到整数权重的映射：

| rarity | weight_uint |
| --- | ---: |
| `common` | 1000 |
| `uncommon` | 350 |
| `rare` | 100 |
| `very_rare` | 25 |
| `unique` | 1 |

如果内容包使用表外 rarity，validator 必须拒绝。

### abundance_count_band

P0 `abundance` 到数量区间的映射：

| abundance | min_count | max_count |
| --- | ---: | ---: |
| `small` | 1 | 2 |
| `medium` | 3 | 5 |
| `large` | 6 | 10 |
| `rich` | 11 | 20 |

数量区间内的具体值必须使用 `random_int_exclusive(max_count - min_count + 1) + min_count`。

### weather_base_weight

P0 天气基础权重：

| weather_condition | base_weight |
| --- | ---: |
| `clear` | 1000 |
| `cloudy` | 800 |
| `light_rain` | 450 |
| `heavy_rain` | 180 |
| `fog` | 250 |
| `snow` | 220 |
| `strong_wind` | 300 |
| `storm` | 60 |
| `abnormal_mist` | 20 |

天气转移表先过滤合法目标，再应用基础权重和修正。

### weather_modifier_weight

P0 天气修正使用整数加权：

| 条件 | 目标 | weight_delta |
| --- | --- | ---: |
| `wet_temperate` | `light_rain` | 200 |
| `wet_temperate` | `fog` | 120 |
| `wet_temperate` | `heavy_rain` | 80 |
| `marsh_humid` | `fog` | 180 |
| `marsh_humid` | `light_rain` | 120 |
| `cold_temperate+winter` | `snow` | 250 |
| `cold_temperate+winter` | `strong_wind` | 80 |
| `ridge` | `strong_wind` | 180 |
| `highland` | `strong_wind` | 150 |
| `wetland` | `fog` | 160 |
| `abnormal_pressure_high` | `abnormal_mist` | 400 |

修正后的权重下限为 0，上限为 1_000_000。

## 空间布局候选随机规则

`SpatialLayoutCandidateFormation` 使用 `domain=spatial_layout`。P0 必须满足：

```text
region_count、grid 尺寸和 max_chunks_per_region 来自已校验 WorldGenerationParameters。
World、Region、Grid 和 Chunk 目标 ID 必须由稳定规则生成；禁止使用执行时自增序号、系统时间或线程完成顺序。
需要随机选择 Region 类型、相对位置或尺寸 profile 时，每个目标 region_id 使用独立 logical_draw_id。
完整网格坐标按 region_id ASC、coord.z ASC、coord.y ASC、coord.x ASC 枚举。
并行和串行执行必须产生相同 candidate_id 集合、目标 ID 集合和 candidate payload hash。
```

`RegionClimateCandidateFormation` 使用 `domain=region_climate`，每个 `region:<region_id>` 使用独立随机流。增加或删除另一个 Region 不能改变未受影响 Region 的气候抽样。

## ChunkBaseFields 规则

`ChunkBaseFields` 不能因 chunk 遍历顺序不同而变化。

P0 拆成两步：

```text
ChunkBaseRawFieldsCandidateFormation
-> ChunkBaseFieldSmoothing
```

规则：

```text
ChunkBaseRawFieldsCandidate 只读取 RandomSeedMaterial、已验证 RegionClimateCandidate、WorldChunkLayoutCandidate 和 WorldGenerationParameters。
ChunkBaseRawFieldsCandidateFormation 不读取邻接 chunk。
ChunkBaseFieldSmoothing 等待同一 Region 全部 ChunkBaseRawFieldsCandidate 通过校验，再按 chunk_id 升序处理正交相邻候选。
并行生成和串行生成必须得到相同 raw fields 与 smoothed fields。
```

## Validator 规则

1. 所有随机使用点必须记录 `RandomDrawRef`。
2. `RandomDrawRef.stream_ref.domain` 必须属于 P0 `domain` 闭集。
3. `RandomDrawRef.stream_ref.rule_id` 必须存在于规则注册表。
4. `scope_id` 必须能解析到存在实体，或是生成前允许的 scope。
5. `logical_draw_id` 必须属于该 rule 的 `FormationRuleContract.random.random_draws` 列表，且 `draw_kind` 必须等于该 `logical_draw_id` 声明的 `draw_kind`。
6. `candidate_set_hash` 必须可由规范化 CandidateSet 重算。
7. `weighted_choice` 必须使用 `WeightedChoiceKernel`。
8. 所有权重必须是整数，且范围为 0 到 1_000_000。
9. 候选集合必须按 sort_key、candidate_id 稳定排序。
10. validator 拒绝不能触发未声明重抽。
11. `ChunkBaseRawFieldsCandidateFormation` 不能读取邻接 chunk。
12. `ChunkBaseFieldSmoothing` 必须按稳定邻接顺序读取。
13. WeatherFormation 必须使用 `weather_base_weight` 和 `weather_modifier_weight`。
14. EcologyFormation 必须使用 `rarity_weight` 和 `abundance_count_band`。
15. 空间布局候选目标 ID 和坐标枚举不能依赖线程完成顺序。
16. 候选阶段使用未来目标 ID 作为 scope_id 时，必须能解析到同一 manifest 中已验证的布局候选。
17. RegionClimateCandidateFormation 必须按 region_id 拆分随机流。
18. ChunkBaseFieldSmoothing 启动前，同一 Region 的 raw fields 候选集合必须完整。
19. random_int_exclusive 的 n 必须满足 1 <= n <= 2^64。
20. random_int_exclusive 必须在最多 32 次 draw_index 尝试内成功或返回确定性 random_failure_code。
21. RandomDrawRef.result_id 使用 random_failure: 前缀时，后缀必须属于 P0 random_failure_code 闭集。

## 测试清单

```text
test_same_seed_same_hash_for_world_generation
test_rule_bundle_hash_changes_random_stream
test_content_pack_hash_changes_random_stream
test_different_rule_ids_do_not_shift_each_other
test_logical_draw_ids_are_independent
test_random_draw_ref_matches_formation_rule_random_draws
test_candidate_set_sorted_by_sort_key_and_id
test_duplicate_candidate_id_rejected_or_merged_deterministically
test_weighted_choice_uses_integer_weights
test_zero_weight_policy_select_none
test_zero_weight_policy_select_first_stable
test_validator_rejection_does_not_consume_next_global_draw
test_chunk_base_raw_fields_independent_of_neighbor_order
test_chunk_base_smoothing_uses_stable_neighbor_order
test_spatial_layout_candidate_ids_independent_of_thread_order
test_spatial_layout_parallel_and_serial_hash_match
test_spatial_layout_coordinates_use_stable_enumeration
test_candidate_scope_target_id_requires_validated_layout_candidate
test_random_int_exclusive_rejects_invalid_bound_without_draw
test_random_int_exclusive_has_bounded_attempts
test_random_int_exclusive_exhaustion_returns_failure_code
test_random_draw_ref_random_failure_code_is_closed
test_region_climate_stream_is_independent_per_region
test_chunk_base_smoothing_requires_complete_region_raw_set
test_weather_generation_uses_standard_weight_kernel
test_ecology_rarity_maps_to_standard_weights
test_manifest_records_random_draw_refs
```

## 已确认决策

1. P0 随机协议版本为 `drp.v1`。
2. P0 PRF 使用 HMAC-SHA256。
3. 所有随机输入必须 canonical JSON 后参与 PRF。
4. 随机流按 `domain + rule_id + scope_id + logical_draw_id` 拆分。
5. 候选选择只能使用整数权重。
6. validator 拒绝不能改变其他 logical draw。
7. ChunkBaseFields 拆成 raw fields 和 smoothing，避免遍历顺序影响结果。
8. WeatherFormation 和 EcologyFormation 必须使用本文定义的标准权重核。
9. P0 程序空间布局使用独立 `spatial_layout` 随机域和稳定坐标枚举。
10. 候选阶段可以把已验证的未来目标 ID 用作随机 scope，但不能把候选冒充权威 world_fact。
11. Region 气候和 chunk 基础场按各自目标 ID 拆分随机流，执行并行度不能改变结果。
12. random_int_exclusive 是有限步协议：合法输入最多尝试 32 次，非法输入或耗尽尝试都产生确定性失败。
