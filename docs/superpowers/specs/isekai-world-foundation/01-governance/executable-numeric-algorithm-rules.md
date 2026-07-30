---
doc_id: isekai.executable_numeric_algorithm_rules
status: active
layer: governance
owner: architecture
created_at: 2026-07-19
updated_at: 2026-07-19
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
provides:
  - NumericAlgorithmSpec
  - NumericAlgorithmRegistry
  - FixedPointKernel
  - NumericAlgorithmValidator
---

# 异世界模式可执行数值算法规则

## 背景

确定性随机协议已经定义“随机数怎样可重放”，FormationRuleContract 已经定义“每条形成规则读什么、写什么、如何处理冲突和 fallback”。但只做到这里仍然不够：同一个 seed、同一个规则 ID 和同一组输入，如果不同实现使用不同浮点精度、舍入方式、阈值、排序或重采样策略，仍会生成不同世界。

本文件解决 P1-07：所有会把输入、参数和随机 draw 转成世界候选、世界事实、库存数量、生态数量、天气状态或聚落放置结果的算法，都必须有可执行、可校验、可重放的 `NumericAlgorithmSpec`。

## 目标

- 让每个 `FormationRuleContract.algorithm.algorithm_id` 都能解析到一个已注册的 `NumericAlgorithmSpec`。
- 统一定点数表示、范围、精度、舍入、clamp、排序、tie-break、重采样和失败行为。
- 让气候、基础场、地形、水文、生态、资源、聚落、Site 和天气的 P1 最小算法都进入注册清单。
- 禁止长期可重放基线使用未声明浮点、未声明公式、未声明候选排序或无限重试。
- 让开发可以用 validator 判断某条规则是 `ready`，还是只能作为 `contract_only` 原型运行。

## 非目标

- 不追求真实地理模拟精度。
- 不模拟连续噪声、流体力学、生态繁殖或经济系统的完整现实模型。
- 不允许内容包覆盖算法语义；内容包只能提供已注册参数、catalog 候选和权重输入。
- 不让 LLM 输出数值算法、公式、阈值或随机结果。

## 核心原则

### 1. 长期可重放基线禁止隐式浮点

`algorithm_status=ready` 的算法不得依赖运行语言的 float/double 结果。所有中间值必须使用整数或本文件定义的定点类型。

允许展示层把定点值渲染成小数文本，但权威候选、WorldState、EventLog、Snapshot 和 manifest hash 使用 canonical 定点字符串或整数。

### 2. 算法是纯函数

`NumericAlgorithmSpec` 的输出只能由以下输入决定：

```text
NumericAlgorithmSpec.algorithm_id/version
FormationRuleContract.rule_id/version
RandomSeedMaterial hash
RandomDrawRef
declared input fields
declared parameters
declared catalog/registry entries
```

不得读取系统时间、线程顺序、数据库返回顺序、对象内存地址、当前帧率、LLM 文本长度或未写入 manifest 的全局变量。

### 3. 所有输出先量化，再校验

算法输出必须先按 `output_quantization` 转成 canonical 值，再交给目标 candidate/world_fact validator。validator 看到的必须已经是最终精度，不能校验高精度临时值。

### 4. 排序和 tie-break 是算法的一部分

任何遍历集合、选择候选、处理同分、合并冲突或选择 fallback 时，都必须声明稳定排序。默认排序不能来自 map、set、数据库或文件加载顺序。

### 5. 重采样必须有上限

拒绝采样、候选重抽和 fallback 都必须有固定最大次数。达到上限后必须产生确定性失败、空输出或默认输出，不能继续抽到成功为止。

### 6. 内容包不能改变数学语义

内容包可以提供 species、resource、object、site 类型、rarity、habitat_tags 和允许范围内的参数覆盖。内容包不能提供新公式、新舍入规则、新随机流或新 tie-break。

## FixedPointKernel

`FixedPointKernel` 是所有 P1 ready 算法的数值内核。

### 数值类型闭集

| type_id | 内部表示 | canonical 输出 | 范围 | 用途 |
| --- | --- | --- | --- | --- |
| `normalized_milli` | integer | 三位小数字符串 | 0 到 1000 | base_fields、score、强度、覆盖率 |
| `signed_normalized_milli` | integer | 三位带符号小数字符串 | -1000 到 1000 | 修正量、偏移量 |
| `basis_points` | integer | integer | 0 到 10000 | 百分比、比例、填充率 |
| `weight_uint` | integer | integer | 0 到 1000000 | 随机候选权重 |
| `score_int` | integer | integer | -1000000 到 1000000 | 候选评分和排序 |
| `count_int` | integer | integer | 0 到 1000000 | 数量、群体规模、库存 count |
| `minute_int` | integer | integer | 0 到 5256000 | 时间成本、持续时间 |
| `meter_int` | integer | integer | 0 到 1000000000 | 距离、空间跨度 |
| `celsius_tenth` | integer | 一位小数字符串 | -1000 到 1000 | 温度与温度偏移，单位摄氏度 |
| `three_decimal_quantity` | integer | 三位小数字符串 | 0 到 1000000000000 | kg、liter、bundle 等资源数量 |

规则：

```text
normalized_milli=720 输出为 "0.720"。
signed_normalized_milli=-35 输出为 "-0.035"。
celsius_tenth=-30 输出为 "-3.0"。
three_decimal_quantity=400 输出为 "0.400"。
所有 canonical 小数字符串必须保留固定小数位。
```

### 运算规则

```text
clamp(value, min, max)：小于 min 取 min，大于 max 取 max。
round_divide_nonnegative(n, d)：d > 0，返回 floor((n + floor(d / 2)) / d)。
round_divide_signed(n, d)：对 abs(n) 使用 round_divide_nonnegative，再恢复符号。
mul_scaled_nonnegative(a, b, scale)：返回 round_divide_nonnegative(a * b, scale)。
mul_scaled_signed(a, b, scale)：返回 round_divide_signed(a * b, scale)。
```

规则：

```text
除数必须为正整数。
中间乘法必须使用至少 64 位有符号整数；可能超过 64 位的算法必须改写为分步加权和。
P1 ready 算法不得产生 NaN、Infinity、科学计数法字符串或本地化小数分隔符。
最终输出必须按字段 FieldSpec 的 unit、range 和 precision 再校验一次。
```

### 随机定点转换

需要从 `RandomDrawRef.draw_kind=fixed_unit` 得到 `normalized_milli` 时，使用：

```text
normalized_milli = floor(draw_uint64 * 1001 / 2^64)
```

输出范围为 0 到 1000，包含两端。该转换只允许用于已声明使用 `normalized_milli` 的算法，不能绕过 `WeightedChoiceKernel` 做概率选择。

## NumericAlgorithmSpec

示例：

```json
{
  "algorithm_id": "terrain.classify_base_fields.fixed_point.v1",
  "algorithm_version": "1.0.0",
  "algorithm_status": "ready",
  "owner_doc_id": "isekai.executable_numeric_algorithm_rules",
  "owner_problem_id": "P1-07",
  "used_by_rule_ids": ["terrain.candidate_from_base_fields.v1"],
  "input_fields": [
    {
      "path": "ChunkBaseFieldsCandidate.base_fields.elevation",
      "numeric_type": "normalized_milli",
      "required": true
    }
  ],
  "output_fields": [
    {
      "path": "ChunkTerrainCandidate.terrain.landform",
      "value_kind": "enum",
      "required": true
    }
  ],
  "parameters": [
    {
      "parameter_id": "ridge_elevation_min",
      "numeric_type": "normalized_milli",
      "default": "0.700",
      "range": {
        "min": "0.000",
        "max": "1.000"
      }
    }
  ],
  "operation_sequence": [
    {
      "step_id": "derive_slope_milli",
      "operation": "max_abs_neighbor_delta",
      "inputs": ["base_fields.elevation"],
      "output": "derived.slope_milli"
    },
    {
      "step_id": "classify_landform",
      "operation": "ordered_threshold_table",
      "inputs": ["base_fields", "derived.slope_milli"],
      "output": "terrain.landform"
    }
  ],
  "iteration_order": {
    "scope": "world_chunk",
    "sort_key": ["region_id", "chunk_id"]
  },
  "random_draws": [],
  "output_quantization": [
    {
      "path": "derived.slope_milli",
      "numeric_type": "normalized_milli",
      "rounding": "round_divide_nonnegative",
      "clamp": {
        "min": "0.000",
        "max": "1.000"
      }
    }
  ],
  "tie_break": {
    "policy_id": "tie_break.ordered_rule_then_candidate_id.v1",
    "sort_key": ["priority_order", "candidate_id"]
  },
  "rejection": {
    "max_attempts": 0,
    "on_exhausted": "emit_fallback_candidate"
  },
  "failure_behavior": {
    "missing_required_input": "validation_error",
    "invalid_parameter": "validation_error",
    "empty_candidate_set": "emit_fallback_candidate",
    "numeric_overflow": "validation_error",
    "random_exhausted": "validation_error",
    "rejection_exhausted": "emit_fallback_candidate",
    "validator_rejected": "validation_error"
  },
  "validator_rules": [
    "validator.numeric_algorithm_spec_registered",
    "validator.terrain_candidate_quantized"
  ],
  "regression_tests": [
    "test_terrain_classification_uses_fixed_point_thresholds",
    "test_terrain_classification_tie_break_is_stable"
  ]
}
```

### 字段说明

| 字段 | 含义 |
| --- | --- |
| `algorithm_id` | 全局唯一算法 ID。必须被 `FormationRuleContract.algorithm.algorithm_id` 引用。 |
| `algorithm_version` | 算法版本。公式、阈值、舍入、排序或失败行为变化必须升级。 |
| `algorithm_status` | 算法状态。闭集为 `ready`、`contract_only`、`deprecated`。 |
| `owner_doc_id` | 维护该算法的权威文档。 |
| `owner_problem_id` | 该算法关闭的系统问题 ID。P1-07 算法必须写 `P1-07`。 |
| `used_by_rule_ids` | 使用该算法的 FormationRuleContract.rule_id 列表。 |
| `input_fields` | 算法实际读取字段。必须是对应 FormationRuleContract.read_set 的子集。 |
| `output_fields` | 算法输出字段。必须是对应 FormationRuleContract.output_set 的子集。 |
| `parameters` | 算法参数。必须声明数值类型、默认值、范围和版本。 |
| `operation_sequence` | 有序步骤。每一步必须引用本文件允许的 operation 或在同文档显式定义。 |
| `iteration_order` | 多实体执行顺序。必须声明 scope 和 sort_key。 |
| `random_draws` | 使用 DRP 的 logical draw 声明。无随机时为空数组。 |
| `output_quantization` | 每个数值输出如何量化、舍入和 clamp。 |
| `tie_break` | 同分、同权重、同候选优先级时的稳定选择。 |
| `rejection` | 拒绝采样上限和耗尽行为。 |
| `failure_behavior` | `failure_reason_kind -> failure_behavior_kind` 的闭集映射，描述缺输入、空候选、数值溢出等失败的确定性行为。 |
| `validator_rules` | 加载和运行时必须通过的 validator。 |
| `regression_tests` | 最小回归测试名。 |

### 失败原因与失败行为闭集

`failure_behavior` 必须是闭集映射，禁止自由文本、实现私有字符串或内容包新增行为。

P1 `failure_reason_kind` 闭集：

```text
missing_required_input
invalid_parameter
empty_candidate_set
numeric_overflow
random_exhausted
rejection_exhausted
validator_rejected
```

P1 `failure_behavior_kind` 闭集：

```text
validation_error
emit_no_output_with_audit
emit_fallback_candidate
emit_default_candidate_with_audit
emit_empty_candidate_set_with_audit
reuse_parent_scope_default
reject_scope_with_reason
defer_to_later_stage
```

输出形态：

| failure_behavior_kind | GeneratorOutputEnvelope / audit / event_draft 形态 |
| --- | --- |
| `validation_error` | 当前输出必须被 validator 拒绝，记录 `GenerationOutputRejected` 审计结果；不得产生新的 `GeneratorOutputItem` 或 `event_draft`。 |
| `emit_no_output_with_audit` | 受影响 rule/scope 不产生 `GeneratorOutputItem`，对应 output bucket 保持空或不新增 item；必须记录 `GenerationOutputValidated` 审计结果 payload；不得产生 `event_draft`。 |
| `emit_fallback_candidate` | 必须在 `candidate_outputs` 产生一个由 FormationRuleContract.output_set 允许的 fallback candidate；candidate payload 必须包含 fallback 来源和 reason code；不得产生 `event_draft`。 |
| `emit_default_candidate_with_audit` | 必须在 `candidate_outputs` 产生一个默认 candidate，并记录 `GenerationOutputValidated` 审计结果 payload；candidate_type、field_path 和 operation 必须被 FormationRuleContract.output_set 允许。 |
| `emit_empty_candidate_set_with_audit` | 不产生候选 item；必须记录空候选集合的 `GenerationOutputValidated` 审计结果 payload；不得产生 `event_draft`。 |
| `reuse_parent_scope_default` | 必须输出由父 scope 默认值派生的 item；父 scope 输入必须出现在 `GeneratorOutputEnvelope.input_refs`，输出字段必须被 FormationRuleContract.output_set 允许。 |
| `reject_scope_with_reason` | 拒绝当前 rule/scope 的输出并记录 `GenerationOutputRejected` 审计结果；不得写入 WorldState、knowledge_facts 或 EventLog。 |
| `defer_to_later_stage` | 当前 rule/scope 不产生输出；必须记录 defer 审计结果，并且 FormationRuleContract 必须声明后续 stage 或 fallback policy；不得产生 `event_draft`。 |

`GenerationOutputValidated` 或 `GenerationOutputRejected` 的数值算法失败审计 payload 至少包含：

```text
failure_reason_kind
failure_behavior_kind
algorithm_id
algorithm_version
rule_id
scope_id
input_hash
random_draw_refs
attempt_count
audit_reason_code
```

失败行为本身不能创建 EventLogEntry。只有正常生成输出进入 `world_fact_outputs`、`knowledge_outputs` 或显式允许的 `event_drafts` 后，才可以由 GenerationCommitter 和 StateTransitionCommitter 生成 EventLog。

## NumericAlgorithmRegistry

`NumericAlgorithmRegistry` 是算法 ID 的权威注册表。P1 任何 `algorithm_status=ready` 的 FormationRuleContract 都必须引用这里存在的算法。

### P1 最小算法注册清单

| algorithm_id | status | 使用领域 | 最小输出 |
| --- | --- | --- | --- |
| `climate.region_profile.weighted_choice.v1` | ready | climate | RegionClimateCandidate |
| `base_field.raw_from_bias_and_noise.fixed_point.v1` | ready | base_field | ChunkBaseRawFieldsCandidate |
| `base_field.smooth_von_neumann.fixed_point.v1` | ready | base_field | ChunkBaseFieldsCandidate |
| `terrain.classify_base_fields.fixed_point.v1` | ready | terrain | ChunkTerrainCandidate |
| `hydrology.route_flow.fixed_point.v1` | ready | hydrology | ChunkHydrologyCandidate |
| `local_climate.derive_offsets.fixed_point.v1` | ready | local_climate | ChunkLocalClimateCandidate |
| `biome.derive_tags.matrix.v1` | ready | biome | ChunkBiomeCandidate / RegionBiomeCandidate |
| `weather.transition_by_profile.fixed_point.v1` | ready | weather | WeatherState |
| `resource.deposit_stock.fixed_point.v1` | ready | resource | ResourceDeposit / ResourceNode |
| `flora.patch_from_habitat_score.fixed_point.v1` | ready | flora | FloraPatch |
| `fauna.population_from_habitat_score.fixed_point.v1` | ready | fauna | CreaturePopulation / CreatureGroup |
| `settlement.anchor_score.fixed_point.v1` | ready | settlement_anchor | settlement anchor candidates |
| `site.placement_score.fixed_point.v1` | ready | site | Site |
| `object.materialize_quantity.fixed_point.v1` | ready | world_object | WorldObject 初始数量与容器内容 |

## P1 默认可执行算法

本节给出 P1 长期可重放基线允许使用的默认算法。后续更真实的算法必须新增 `algorithm_id` 或升级 `algorithm_version`，不能静默替换。

### 1. RegionClimateCandidateFormation

`climate.region_profile.weighted_choice.v1`

输入：

```text
RegionLayoutCandidate.region_id
WorldGenerationParameters.climate_bias
WorldGenerationParameters.terrain_bias
RandomSeedMaterial
```

算法：

```text
1. 构造候选 climate_zone 闭集：cold_temperate、temperate、wet_temperate、dry_steppe、highland、marsh_humid、abnormal。
2. 每个 climate_zone 的基础 weight_uint 为 1000。
3. 如果 climate_zone 出现在 climate_bias 中，weight_uint += 750。
4. 如果 terrain_bias 支持该 climate_zone，weight_uint += 250。
   highland <- ridge/hill
   marsh_humid <- wetland/valley
   wet_temperate <- forest/valley
   dry_steppe <- plain/ridge
5. abnormality_level=low 时 abnormal weight_uint = 20；medium 为 80；high 为 200。
6. weight_uint clamp 到 0 到 1000000。
7. 按 climate_zone 字典序构造 CandidateSet，使用 WeightedChoiceKernel。
8. temperature_band、rainfall_band、humidity、seasonality、prevailing_wind 和 snow_months 由 climate_zone 固定映射表派生。
```

失败行为：

```text
候选集合为空：validation_error。
总权重为 0：select_first_stable，输出 cold_temperate。
```

### 2. ChunkBaseRawFieldsCandidateFormation

`base_field.raw_from_bias_and_noise.fixed_point.v1`

输入：

```text
RegionClimateCandidate.climate_profile
WorldChunkLayoutCandidate.coord
WorldChunkGrid.bounds_chunk
WorldGenerationParameters.terrain_bias
WorldGenerationParameters.civilization_density
WorldGenerationParameters.danger_level
WorldGenerationParameters.abnormality_level
RandomDrawRef fixed_unit
```

字段：

```text
elevation
moisture
rockiness
soil_depth
water_flow
civilization_pressure
danger_pressure
abnormal_pressure
```

算法：

```text
1. 每个字段 baseline_milli = 500。
2. 从 climate_profile 应用 climate_delta_milli。
3. 从 terrain_bias 应用 terrain_delta_milli。
4. 从世界参数应用 world_param_delta_milli。
5. 计算坐标项：
   x_milli = floor((x - min_x) * 1000 / max(1, width_chunks - 1))
   y_milli = floor((y - min_y) * 1000 / max(1, height_chunks - 1))
   z_delta_milli = clamp(z * 100, -300, 300)
6. 每个字段读取一个 logical_draw_id：
   base_field:<field_name>:<chunk_id>
   noise_delta_milli = fixed_unit_to_normalized_milli(draw) - 500
7. 输出：
   value_milli = clamp(baseline + climate_delta + terrain_delta + world_param_delta + coordinate_delta + noise_delta, 0, 1000)
8. canonical 输出为三位小数字符串。
```

默认 delta 表：

| 输入 | elevation | moisture | rockiness | soil_depth | water_flow | civilization | danger | abnormal |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cold_temperate` | 50 | 80 | 20 | 20 | 40 | 0 | 30 | 0 |
| `wet_temperate` | 0 | 180 | -20 | 80 | 100 | 0 | 0 | 0 |
| `dry_steppe` | 40 | -220 | 80 | -80 | -120 | 0 | 20 | 0 |
| `highland` | 220 | -60 | 180 | -120 | 30 | -50 | 80 | 0 |
| `marsh_humid` | -120 | 240 | -80 | 120 | 80 | -30 | 40 | 0 |
| `abnormal` | 0 | 0 | 0 | 0 | 0 | -50 | 120 | 300 |
| `terrain_bias=ridge` | 180 | -40 | 140 | -80 | 20 | 0 | 40 | 0 |
| `terrain_bias=forest` | 0 | 100 | -20 | 100 | 20 | 0 | 20 | 0 |
| `terrain_bias=valley` | -120 | 120 | -40 | 80 | 140 | 0 | 20 | 0 |
| `civilization_density=low` | 0 | 0 | 0 | 0 | 0 | -150 | 0 | 0 |
| `civilization_density=medium` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `civilization_density=high` | 0 | 0 | 0 | 0 | 0 | 180 | -30 | 0 |
| `danger_level=low` | 0 | 0 | 0 | 0 | 0 | 0 | -150 | 0 |
| `danger_level=medium` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `danger_level=high` | 0 | 0 | 0 | 0 | 0 | 0 | 200 | 0 |
| `abnormality_level=low` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | -100 |
| `abnormality_level=medium` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 50 |
| `abnormality_level=high` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 220 |

坐标项：

```text
elevation += round_divide_signed(y_milli - 500, 5) + z_delta_milli
moisture += round_divide_signed(500 - y_milli, 10)
water_flow += round_divide_signed(500 - abs(x_milli - 500), 8)
civilization_pressure += round_divide_signed(500 - abs(x_milli - 500), 12)
```

### 3. ChunkBaseFieldSmoothing

`base_field.smooth_von_neumann.fixed_point.v1`

输入：同一 Region 内全部 `ChunkBaseRawFieldsCandidate`。

算法：

```text
1. 邻接只使用同一 z 层、同一 Region、正交四方向 chunk。
2. 邻接列表按 neighbor.chunk_id 升序。
3. P1 迭代次数固定为 2。
4. 每轮对每个字段计算：
   numerator = self_value * 4 + sum(neighbor_value)
   denominator = 4 + neighbor_count
   next_value = round_divide_nonnegative(numerator, denominator)
5. 每轮读取上一轮完整结果，不允许边算边覆盖。
6. 边界缺失邻居不补镜像值。
7. 输出 clamp 到 0 到 1000，并序列化为三位小数字符串。
```

失败行为：

```text
同 Region raw field 不完整：validation_error。
重复 chunk_id：validation_error。
```

### 4. TerrainCandidateFormation

`terrain.classify_base_fields.fixed_point.v1`

派生：

```text
slope_milli = max(abs(self.elevation - neighbor.elevation))
邻居集合与 smoothing 相同；没有邻居时 slope_milli=0。
```

分类：

```text
elevation_band:
0..329 -> lowland
330..669 -> midland
670..1000 -> highland

slope:
0..80 -> flat
81..180 -> gentle
181..350 -> steep
351..1000 -> impassable

soil:
soil_depth 0..299 -> thin
300..699 -> normal
700..1000 -> deep
```

landform 按以下优先级选择第一条命中的规则：

| priority | 条件 | landform |
| ---: | --- | --- |
| 10 | slope=impassable 且 rockiness>=650 | cliff |
| 20 | elevation>=700 且 rockiness>=550 | ridge |
| 30 | water_flow>=650 且 elevation<=650 | valley |
| 40 | moisture>=720 且 soil_depth>=550 | wetland |
| 50 | civilization_pressure>=800 | town_block |
| 60 | civilization_pressure>=650 | road |
| 70 | abnormal_pressure>=750 且 civilization_pressure>=250 | ruin |
| 80 | rockiness>=780 且 elevation>=500 | cave |
| 90 | moisture>=450 且 soil_depth>=500 | forest |
| 100 | elevation>=520 | hill |
| 110 | default | plain |

ground：

```text
cliff/ridge/cave -> rocky_soil
road -> road_surface
town_block -> dirt
ruin -> ruined_floor
wetland -> mud
moisture<=250 and soil_depth<=300 -> gravel
default forest/plain/hill/valley -> grass
```

输出 `terrain_tags` 按 tag registry 顺序排序，不按发现顺序排序。

### 5. HydrologyCandidateFormation

`hydrology.route_flow.fixed_point.v1`

输入：同一 Region 全部 terrain、base fields 和 climate。

算法：

```text
1. 对每个 chunk 计算 downhill_neighbor：
   只考虑同 Region、同 z 层、正交邻居。
   只选择 elevation 更低的邻居。
   候选按 elevation 升序、chunk_id 升序排序，取第一。
   没有更低邻居则为 null。
2. 处理顺序为 elevation 降序、chunk_id 升序。
3. initial_flow = water_flow。
4. 每个 chunk 的 flow_accum = clamp(initial_flow + sum(upstream_contribution), 0, 3000)。
5. upstream_contribution = round_divide_nonnegative(upstream.flow_accum, 2)。
6. 每个 chunk 只把自己的 contribution 传给 downhill_neighbor 一次。
7. water_score = flow_accum + moisture + climate_rainfall_bonus。
```

`climate_rainfall_bonus`：

| rainfall_band | bonus |
| --- | ---: |
| dry | -250 |
| medium | 0 |
| wet | 200 |

water_presence：

| 条件 | 输出 |
| --- | --- |
| civilization_pressure>=780 且 landform=town_block | well |
| flow_accum>=1600 且 landform in valley/riverbank/plain | river |
| flow_accum>=1050 | stream |
| moisture>=800 且 rockiness>=500 | spring |
| moisture>=760 且 slope=flat | pond |
| moisture>=700 且 landform=wetland | stagnant |
| water_score>=650 | seasonal |
| default | none |

规则：

```text
P1 不在 hydrology 阶段直接创建 ResourceNode。
ResourceNode 只能由 ResourceFormation 根据 resource_support 创建。
water_presence 输出后不可被天气回写。
```

### 6. LocalClimateCandidateDerivation

`local_climate.derive_offsets.fixed_point.v1`

算法：

```text
temperature_offset_tenth =
  elevation_bonus
  + water_bonus
  + vegetation_bonus
  + wind_bonus
  + abnormal_bonus

输出 clamp 到 -150 到 150，序列化为 celsius_tenth。
```

默认表：

| 条件 | temperature_offset_tenth | rainfall_modifier | wind_exposure |
| --- | ---: | ---: | --- |
| elevation_band=highland | -30 | 0 | high |
| landform=ridge | -10 | 0 | high |
| landform=valley | 5 | 1 | low |
| water_presence in stream/river/pond/spring | -5 | 1 | medium |
| landform=forest | -5 | 1 | low |
| landform=town_block | 5 | -1 | low |
| abnormal_pressure>=700 | 0 | 1 | medium |

`fog_likelihood`：

```text
high: water_presence != none 且 moisture>=700
medium: moisture>=550 或 landform=valley/wetland
low: default
```

### 7. BiomeCandidateDerivation

`biome.derive_tags.matrix.v1`

算法：

```text
1. 按固定矩阵产生候选 tag。
2. 每个 tag 必须能引用至少一个支持输入。
3. ChunkBiomeCandidate.biome_tags 按 BiomeTagRegistry 顺序排序。
4. RegionBiomeCandidate 读取同 Region chunk tags：
   chunk_count_by_tag >= 1 即进入 Region.biome_tags。
   tag_sources[tag] 为支持该 tag 的 chunk_id 升序列表。
```

固定矩阵：

| 条件 | tag |
| --- | --- |
| climate_zone=cold_temperate 且 landform=forest | cold_forest |
| climate_zone=wet_temperate 且 landform=forest | wet_forest |
| elevation_band=highland 且 landform in ridge/hill | rocky_highland |
| landform=valley 且 water_presence in stream/river | creek_valley |
| landform=wetland 或 water_presence=stagnant | marsh |
| landform=town_block | settlement |
| landform=road | trade_route |
| landform=ruin 且 moisture>=550 | damp_ruin |
| abnormal_pressure>=650 | abnormal_zone |
| danger_pressure>=650 | predator_habitat |
| water_presence in spring/stream/river/pond/well | water_source_nearby |

### 8. WeatherFormation

`weather.transition_by_profile.fixed_point.v1`

输入：

```text
Region.climate_profile
WorldTimeState.season
WorldChunk.local_climate
previous WeatherState（天气转移时必填，初始天气为空）
RandomDrawRef weighted_choice
```

算法：

```text
1. 从确定性随机协议的 weather_base_weight 建立候选。
2. 过滤不合法天气：
   snow 需要 season=winter 或 temperature_band=cold 或 elevation_band=highland。
   heavy_rain/storm 需要 rainfall_band != dry。
   fog 需要 fog_likelihood != low 或 humidity != low。
3. 应用 climate、season、local_climate 的整数 weight_delta。
4. 如果 previous condition 与目标相同，weight_uint += 150。
5. 所有 weight_uint clamp 到 0 到 1000000。
6. 按 weather_condition 字典序构造 CandidateSet，使用 WeightedChoiceKernel。
7. valid_for_minutes 从区间表抽样：
   clear/cloudy: 90 到 180
   rain/fog/snow/wind: 45 到 120
   storm/abnormal_mist: 15 到 60
```

失败行为：

```text
合法候选为空：输出 cloudy，audit_reason_code=weather_no_legal_candidate。
valid_for 抽样失败：validation_error。
```

### 9. ResourceFormation

`resource.deposit_stock.fixed_point.v1`

算法：

```text
1. 从 NaturalResource catalog 取候选，候选必须满足 terrain_tags、water_presence、biome_tags 和 hard requirements。
2. habitat_score_milli =
   300 * terrain_match
   + 250 * biome_match
   + 250 * water_match
   + 100 * climate_match
   + 100 * origin_or_abnormal_match
   其中每个 match 为 0 或 1。
3. habitat_score_milli < 350 时候选不进入 CandidateSet。
4. weight_uint = rarity_weight * max(1, habitat_score_milli)。
5. 使用 WeightedChoiceKernel 选择资源种类；每个 chunk P1 最多生成 3 个 resource entity。
6. abundance_count 使用 deterministic-random-protocol 的 abundance_count_band。
7. capacity_amount = abundance_count * catalog.unit_yield_milli。
8. current_amount = capacity_amount * initial_fill_basis_points / 10000。
   initial_fill_basis_points 由 fixed_unit draw 映射到 7000 到 10000。
9. 输出三位小数字符串。
```

失败行为：

```text
没有合法资源候选：emit_no_output_with_audit。
候选被目标 validator 拒绝：最多重试 8 次，耗尽后 emit_no_output_with_audit。
```

### 10. FloraFormation

`flora.patch_from_habitat_score.fixed_point.v1`

算法：

```text
1. 从 PlantSpecies catalog 取候选，habitat_tags 与 biome_tags 至少命中 1 个。
2. hard requirements 必须满足：tree 需要 soil_depth>=350 或 forest tag；aquatic_plant 需要水体；fungus 需要 damp_ruin/cave/high moisture。
3. habitat_score_milli = 400*habitat_match + 250*terrain_match + 200*moisture_match + 150*climate_match。
4. score < 300 不进入 CandidateSet。
5. weight_uint = rarity_weight * score，clamp 到 1000000。
6. 每个 chunk P1 最多生成 4 个 FloraPatch。
7. coverage：
   score 300..499 -> sparse
   500..749 -> moderate
   750..1000 -> dense
8. stock.capacity_amount = coverage_yield * abundance_multiplier，输出三位小数字符串。
```

失败行为：无候选时 `emit_no_output_with_audit`。

### 11. FaunaFormation

`fauna.population_from_habitat_score.fixed_point.v1`

算法：

```text
1. 从 AnimalSpecies catalog 取候选。
2. hard requirements：
   predator 需要 prey tag、corpse resource 或 abnormal_zone。
   fish 需要 water_presence stream/river/pond。
   livestock 需要 settlement/farm/stable/trade_route。
3. habitat_score_milli = 350*habitat_match + 250*food_or_prey_match + 200*water_match + 100*climate_match + 100*danger_or_civilization_match。
4. score < 350 不进入 CandidateSet。
5. weight_uint = rarity_weight * score，clamp 到 1000000。
6. 每个 Region 每个 species P1 最多生成 1 个 CreaturePopulation。
7. population_level:
   score 350..549 -> small
   550..799 -> medium
   800..1000 -> large
8. initial_live_count 从 species min/max group size 和 population_level multiplier 派生：
   small=1 组，medium=2 组，large=3 组。
9. reserve_count = initial_live_count。
10. P1 初始 CreatureGroup 只在玩家起点邻近生态需要时物化；否则保持 reserve。
```

失败行为：无候选时 `emit_no_output_with_audit`。

### 12. SettlementAnchorFormation

`settlement.anchor_score.fixed_point.v1`

算法：

```text
settlement_score =
  civilization_pressure * 3
  + road_or_town_landform_bonus
  + water_source_bonus
  + flat_or_gentle_slope_bonus
  - danger_pressure
  - abnormal_pressure
```

常量：

```text
road_or_town_landform_bonus=300
water_source_bonus=200
flat_or_gentle_slope_bonus=150
```

规则：

```text
score >= 1800 才能生成 settlement anchor。
同 Region 多个 anchor 按 score 降序、chunk_id 升序选择。
P1 每个 Region 最多 3 个 settlement anchor。
没有合法 anchor 时 emit_no_output_with_audit；玩家起点需要聚落时由 WorldGenerationParameters 显式要求 required_start_settlement=true，此时 fallback 选择最高 score chunk 并记录 audit。
```

### 13. SitePlacement

`site.placement_score.fixed_point.v1`

算法：

```text
1. 从 SiteType catalog 取候选。
2. hard requirements 必须先满足，例如 cave 需要 landform=cave，inn 需要 settlement/trade_route，water_source_site 需要 water_presence。
3. placement_score =
   400*required_landform_match
   + 250*biome_match
   + 200*access_match
   + 100*origin_match
   + 50*resource_support_match
4. score < 400 不进入 CandidateSet。
5. 同 chunk 内 primary_site 最多 1 个；secondary site 最多 3 个。
6. 排序：score 降序、site_type_id 升序、chunk_id 升序。
7. 拒绝采样最多 16 次；耗尽后 emit_no_output_with_audit。
```

### 14. ObjectMaterialization

`object.materialize_quantity.fixed_point.v1`

算法：

```text
1. WorldObject 模板来自已验证 catalog。
2. 离散对象数量使用 count_int，数量资源使用 three_decimal_quantity。
3. 容器初始 quantity_contents 必须由场景实例规则或资源规则写入，catalog 默认必须为空。
4. 初始数量抽样：
   count = random_int_exclusive(max_count - min_count + 1) + min_count。
   quantity = min_quantity_milli + random_int_exclusive(max_quantity_milli - min_quantity_milli + 1)。
5. 输出进入 WorldObjectValidator 和 QuantityConservationValidator。
```

失败行为：

```text
模板不合法：validation_error。
容量不足：拒绝该对象实例，最多重试 8 次，耗尽后 emit_no_output_with_audit。
```

## 与 FormationRuleContract 的关系

规则：

```text
FormationRuleContract.algorithm.algorithm_id 必须引用 NumericAlgorithmRegistry。
FormationRuleContract.algorithm.status 必须等于 NumericAlgorithmSpec.algorithm_status。
NumericAlgorithmSpec.input_fields 必须是 FormationRuleContract.read_set 的子集。
NumericAlgorithmSpec.output_fields 必须是 FormationRuleContract.output_set 的子集。
NumericAlgorithmSpec.random_draws 必须被 FormationRuleContract.random.random_draws 覆盖；覆盖关系至少按 logical_draw_id + draw_kind 精确匹配。
NumericAlgorithmSpec.rejection.max_attempts 必须小于等于 FormationRuleContract.random.max_rejection_attempts。
NumericAlgorithmSpec.rejection.on_exhausted 必须属于 failure_behavior_kind 闭集。
会产生 candidate、默认值或父级默认输出的 failure_behavior 必须被 FormationRuleContract.output_set 和 fallback_policy 允许。
```

如果任一条件不成立，`FormationRuleContractValidator` 和 `NumericAlgorithmValidator` 都必须拒绝该规则进入 ready 基线。

## NumericAlgorithmValidator

必须校验：

```text
1. 每个 ready FormationRuleContract.algorithm.algorithm_id 在 NumericAlgorithmRegistry 中存在。
2. NumericAlgorithmSpec.algorithm_status=ready 时，operation_sequence 非空。
3. 所有 input_fields 和 output_fields 都有 FieldSpec。
4. 所有数值 input/output/parameter 都使用本文件数值类型闭集。
5. output_quantization 覆盖每个数值 output_fields。
6. iteration_order 存在，且 sort_key 字段可由输入或 scope 唯一确定。
7. random_draws 只能使用 DRP 声明的 draw_kind。
8. uses_random=true 的算法必须记录 RandomDrawRef。
9. rejection.max_attempts 为 0 到 32 的整数。
10. rejection.on_exhausted 属于 failure_behavior_kind 闭集。
11. failure_behavior 必须覆盖全部 P1 failure_reason_kind，且每个值都属于 failure_behavior_kind 闭集。
12. 使用 DRP 的算法遇到 random_int_invalid_bound 时，必须映射到 failure_behavior.invalid_parameter；遇到 random_int_rejection_exhausted 时，必须映射到 failure_behavior.random_exhausted。
13. failure_behavior 对应的 GeneratorOutputEnvelope / audit / event_draft 形态必须符合本文件输出形态表。
14. algorithm_status=ready 的算法不得使用 float、double、Math.random、本地 seed 或未声明权重。
15. P1 最小算法注册清单中的 algorithm_id 全部存在。
```

## 回归测试

必须实现：

```text
test_numeric_algorithm_registry_has_p1_minimum_algorithms
test_ready_formation_rule_algorithm_id_resolves_to_numeric_algorithm_spec
test_numeric_algorithm_uses_canonical_fixed_point_types
test_numeric_algorithm_rejects_float_output_in_replay_baseline
test_numeric_algorithm_declares_output_quantization_for_every_numeric_field
test_numeric_algorithm_iteration_order_is_stable
test_numeric_algorithm_random_draws_use_drp_refs
test_numeric_algorithm_random_draws_covered_by_formation_rule_random_draws
test_numeric_algorithm_rejection_attempts_are_bounded
test_numeric_algorithm_failure_reason_keys_are_closed
test_numeric_algorithm_failure_behavior_values_are_closed
test_numeric_algorithm_random_exhaustion_maps_to_failure_behavior
test_numeric_algorithm_failure_behavior_output_shape_is_valid
test_base_field_raw_generation_replays_same_seed
test_base_field_smoothing_uses_von_neumann_previous_round
test_terrain_classification_threshold_edges_are_stable
test_hydrology_downhill_tiebreak_uses_chunk_id
test_weather_transition_empty_candidates_falls_back_to_cloudy
test_resource_stock_quantity_is_three_decimal_and_conserved
test_site_placement_same_score_uses_site_type_then_chunk_id
```

## 关闭条件

P1-07 设计关闭要求：

```text
1. 本文件存在且被治理 README 和根 README 引用。
2. P1 最小算法注册清单中的算法全部有 algorithm_id、status、输入、输出、量化、排序、失败行为和测试。
3. FormationRuleContract.algorithm_id 必须能绑定 NumericAlgorithmSpec。
4. ready 算法禁止隐式浮点和无限重采样。
5. 世界生成 manifest 能记录使用过的 rule_id、algorithm_id、algorithm_version 和 RandomDrawRef。
```

工程实现完成前，P1-07 的系统问题状态仍为 `open`；设计完成度可以标记为 `numeric_protocol_completed`。
