# 异世界世界底座 P1 数学闭合修订设计

日期：2026-07-29

状态：已完成方案确认，待用户审阅本文后进入实施计划

## 1. 目标

本次修订把现有“异世界世界底座”推进为最小但数学闭合、可执行、可验证、可重放的 P1 基线。

完成后必须满足：

1. 每个权威 schema、candidate schema 和 catalog schema 的完整字段路径都有唯一 `FieldSpec`。
2. 每个参与 P1 世界生成的 producer 都有完整 `FormationRuleContract`。
3. 每个标记为 `ready` 的数值算法都有完整 `NumericAlgorithmSpec`。
4. 每个必填输出字段都有唯一的赋值来源。
5. 每个有限值字段都有闭集或 registry，每个值都声明可用阶段。
6. 每个生成函数对合法输入产生唯一输出，或产生唯一确定性失败。
7. 同一 seed、输入、版本和内容包得到相同输出包、状态、事件日志和快照 hash。
8. 中断、重试和恢复得到相同终态或相同确定性拒绝。

## 2. 非目标

本次修订不做以下工作：

- 不增加逐年历史模拟。
- 不增加复杂气象格点模拟。
- 不增加完整食物网或生态动态模拟。
- 不增加市场供需动态模拟。
- 不增加新的玩家玩法、动作类型或 AI 自主权限。
- 不把展示文本改造成规则字段。
- 不改变候选、世界事实、知识事实、事件草案和快照引用的分桶架构。
- 不让 LLM 直接提交权威状态。
- 不把生成期候选变成运行时权威实体。

## 3. 总体方案

采用分层闭合：

1. 治理层定义字段类型、值域、单位、派生方式、失败行为和验证顺序。
2. 架构层定义阶段、FormationRule、NumericAlgorithm、envelope、恢复和提交边界。
3. 各实体 owner 文档定义本领域的完整字段规范、固定映射和确定性算法。
4. 内容包只提供受控数据，不改变数学语义。
5. validator 按统一顺序组合验证，不由各模块自行猜测。

## 4. 字段治理

### 4.1 FieldSpec 必填字段

每个完整 schema path 必须声明：

```text
path
base_type
required_when
nullable
value_constraints
reference_target
unit
precision
write_policy
derivation_policy
availability_phase
version
```

`required_when` 使用可机读判别条件。例如：

```text
WeatherState.scope=region
-> region_id required
-> chunk_id null
-> parent_weather_state_id null
```

`nullable=true` 只允许显式 `null`。字段可省略与字段可为 null 是两个不同约束。

### 4.2 availability_phase

有限值必须声明允许出现的阶段：

```text
initial_generation
content_materialization
runtime_transition
migration_only
reserved
```

一个值可以属于多个阶段。`reserved` 值不能进入 P1 权威状态，只用于保持未来 schema 兼容。

初始算法没有产生某个合法值不自动构成问题；只有当该值没有任何允许阶段，或文档声称初始可达却没有规则时，才构成不可达。

### 4.3 展示字段

`name`、`description`、`summary`、`notes` 和同类字段登记为 `display_text`。

展示字段：

- 可以参与完整实体 canonical hash。
- 不允许作为 resolver、candidate score、eligibility 或 validator 分支输入。
- 不要求有限闭集。

### 4.4 candidate 验证强度

候选中间产物采用轻量验证：

```text
schema
base type
enum / registry
stable ID
stable ordering
value hash
FormationRule output boundary
```

候选阶段不查询权威 `WriteACL`，也不执行完整世界引用和跨实体业务不变量校验。

候选物化为权威实体时执行：

```text
reference
FieldSpec
WriteACL
business invariants
canonical post-state
atomic commit
```

候选字段的 `write_policy` 指向 producer 和 `FormationRuleContract.output_set`，不指向权威实体 `WriteACL`。

### 4.5 P1 数值编码

所有范围为 `[0,1]` 的权重、置信度、压力、强度和比例字段统一使用 `normalized_milli` 三位小数字符串：

```text
"0.000" .. "1.000"
```

包括但不限于：

```text
KnowledgeState.confidence
RumorState.intensity
SocialGroupState.pressure.*
SocialPressureState.pressure.*
base_fields.*
allowed_loss_ratio
source_to_output_ratio
```

百分比运算使用整数 basis points，10000 表示 100%。计数使用整数；守恒数量使用三位小数字符串。P1 权威 schema、候选和 catalog 中禁止 JSON 浮点数。

## 5. FormationRule 与数值算法

### 5.1 FormationRuleContract 完整性

每个 P1 producer 至少有一个完整契约。

每个 required 输出字段必须由以下来源之一覆盖：

```text
algorithm_assignment
fixed_profile_mapping
declared_default
materialized_input_copy
```

禁止出现已声明输出字段但没有赋值来源的情况。

候选数量必须声明：

```text
min_count
target_count
max_count
```

并满足：

```text
0 <= min_count <= target_count <= max_count
```

所有 eligibility、score、selection、tie-break、priority、merge、reject 和 fallback policy ID 必须解析到版本化策略。

`WriteACL` 唯一键固定为：

```text
(rule_id, EntityType, FieldPath, operation)
```

ACL 表的第一列必须填写 canonical `rule_id`，不能填写 producer 名称。producer 只作为 FormationRuleRegistry 元数据。candidate 不查询 WriteACL。

CandidateSet 中 `candidate_id` 必须唯一；重复 ID 直接 `validation_error`，P1 不提供隐式 merge。恢复记录必须保存完整 CandidateSet payload、candidate set hash 和对应 RandomDrawRef，不能只保存 hash。

### 5.2 ready 状态

只有同时具备以下内容的算法可以标记为 `ready`：

- 完整输入字段。
- 完整输出字段。
- 参数类型、单位、范围、默认值和精度。
- 操作序列。
- 迭代顺序。
- 随机抽样声明。
- 输出量化。
- tie-break。
- 有界拒绝采样。
- 所有失败原因的确定性行为。
- validator 规则。
- 回归测试。

只给出自然语言倾向的算法必须标记为 `contract_only`，不能进入长期可重放基线。

### 5.3 统一失败闭集

`FormationRuleContract` 和 `NumericAlgorithmSpec` 使用同一闭集：

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

每个失败行为必须定义对应的 `GeneratorOutputEnvelope`、audit 和 event draft 形态。

### 5.4 P1 目标 ready registry

owner 文档完成本设计、对应 validator 和 fixture 后，以下算法构成 P1 `ready` 集合：

| algorithm_id | producer / resolver | 本文依据 |
| --- | --- | --- |
| `spatial.layout_strip.v1` | SpatialLayoutCandidateFormation | §7 |
| `climate.region_profile.weighted_choice.v1` | RegionClimateCandidateFormation | §8 |
| `base_field.raw_from_bias_and_noise.fixed_point.v1` | ChunkBaseRawFieldsCandidateFormation | §6、现有数值规范 |
| `base_field.smooth_von_neumann.fixed_point.v1` | ChunkBaseFieldSmoothing | 现有数值规范 |
| `terrain.classify_base_fields.fixed_point.v1` | TerrainCandidateFormation | §9 |
| `hydrology.route_flow.fixed_point.v1` | HydrologyCandidateFormation | §10 |
| `local_climate.derive_offsets.fixed_point.v1` | LocalClimateCandidateDerivation | §10 |
| `biome.derive_tags.matrix.v1` | BiomeCandidateDerivation | §10 |
| `space.chunk_edge_von_neumann.v1` | StaticChunkEdgeFormation | §11 |
| `traversal.static_profile.fixed_point.v1` | StaticTraversalDeriver | §11 |
| `settlement.anchor_score.fixed_point.v1` | SettlementAnchorFormation | §15 |
| `origin.candidate_profile.fixed_point.v1` | OriginHistoryCandidateFormation | §14 |
| `resource.deposit_stock.fixed_point.v1` | ResourceFormation | §13 |
| `flora.patch_from_habitat_score.fixed_point.v1` | FloraFormation | §13 |
| `fauna.population_from_habitat_score.fixed_point.v1` | FaunaFormation | §13 |
| `settlement.archetype_first_match.v1` | SitePlacement | §15、§16 |
| `site.required_institution_assignment.v1` | SitePlacement | §15 |
| `location.single_node_template.v1` | LocationGenerator | §15 |
| `object.materialize_quantity.fixed_point.v1` | ObjectMaterialization | §18 |
| `social.settlement_archetype_materialize.v1` | SettlementSocialFormation | §16 |
| `origin.evidence_materialize.v1` | OriginHistoryMaterialization | §14 |
| `runtime.initial_state.v1` | WorldRuntimeInitialization | §19、现有运行时规范 |
| `weather.transition_by_profile.fixed_point.v1` | WeatherFormation | §12 |
| `environment.derive_local_state.fixed_point.v1` | EnvironmentDeriver | §20 |
| `hazard_obstacle.derive_profile.v1` | HazardObstacleDeriver | §21 |
| `passability.reduce_overrides.v1` | PassabilityReducer | §11、§21 |
| `residual.update_stepwise.v1` | EnvironmentResidualUpdater | §22 |
| `knowledge.initial_visible_scope.v1` | InitialKnowledgeFormation | §23 |
| `snapshot.canonical_state_projection.v1` | SnapshotWriter | §26 |

表中的“ready”是 owner 文档完成后的目标状态，不是对当前仓库状态的提前宣告。任一算法缺少 NumericAlgorithmSpec 必填字段、FormationRule 对齐或测试时，必须保持 `contract_only`。

P1 不把可选地点评分算法 `site.placement_score.fixed_point.v1` 标记为 ready。P1 所需 Site 全部由 archetype.required_institution_kinds 和 `site.required_institution_assignment.v1` 生成；可选 cave、ruin、猎人小屋等扩展地点继续保持 contract_only，直到单独完成其候选数量、位置冲突和失败规则。

### 5.5 验证顺序

```text
schema
-> FieldSpec type/domain
-> candidate producer/output contract
-> deterministic algorithm proof
-> reference
-> materialization completeness
-> WriteACL
-> business invariants
-> canonical ordering/hash
-> atomic commit
```

### 5.6 P1 随机抽样命名

每个 P1 FormationRule 的 `random.random_draws[]` 必须覆盖下表。表中的
`scope_id` 是 DRP（确定性随机协议）随机流作用范围，不是
`FormationRuleContract.target_scope` 或 envelope scope。

| producer | stream domain | scope_id | logical_draw_id | draw_kind |
| --- | --- | --- | --- | --- |
| RegionClimateCandidateFormation | region_climate | `region:<region_id>` | `climate_zone` | weighted_choice |
| ChunkBaseRawFieldsCandidateFormation | base_field_formation | `chunk:<chunk_id>` | `base_field:<field_name>:<chunk_id>` | fixed_unit |
| WeatherFormation | weather_generation | `region:<region_id>` | `condition` | weighted_choice |
| WeatherFormation | weather_generation | `region:<region_id>` | `duration_minutes` | int_range |
| ResourceFormation | resource_formation | `chunk:<chunk_id>` | `resource_select:<selection_index>` | weighted_choice |
| ResourceFormation | resource_formation | `chunk:<chunk_id>` | `resource_abundance_count:<resource_id>` | int_range |
| ResourceFormation | resource_formation | `chunk:<chunk_id>` | `resource_initial_fill:<resource_id>` | fixed_unit |
| FloraFormation | flora_formation | `chunk:<chunk_id>` | `flora_select:<selection_index>` | weighted_choice |
| FloraFormation | flora_formation | `chunk:<chunk_id>` | `flora_initial_fill:<species_id>` | fixed_unit |
| FaunaFormation | fauna_formation | `region:<region_id>` | `fauna_select:<selection_index>` | weighted_choice |
| FaunaFormation | fauna_formation | `region:<region_id>` | `fauna_group_size:<species_id>` | int_range |
| OriginHistoryCandidateFormation | origin_history | candidate 的 `world_chunk:<id>` 或 `settlement:<id>` | `origin_age:<candidate_id>` | weighted_choice |
| OriginHistoryCandidateFormation | origin_history | `region:<region_id>` | `origin_select:<selection_index>` | weighted_choice |

`selection_index` 从 0 开始，表示契约声明的第 N 个无放回选择槽位。每个槽位
都从按 canonical ID 排序、且移除前面已选结果后的 CandidateSet 计算自己的
`candidate_set_hash`；它不等于线程、容器或语言运行时的当前遍历序号。

`fixed_unit` 映射到闭区间整数 basis points 时统一使用：

```text
mapped =
min_bp
+ floor(
    draw_uint64
    * (max_bp - min_bp)
    / (2^64 - 1)
  )
```

乘法使用至少 128-bit 无符号中间整数。`min_bp=max_bp` 时直接返回该值但仍
记录声明过的 draw；不得用浮点运算或本地随机数替代。

每个实际消耗的 draw 都必须产生一个 RandomDrawRef；没有执行到的稳定选择
槽位不伪造引用。envelope 的 `random_draw_refs` 必须与所有输出
`generated_by.random_draw_refs` 的稳定去重并集一致。

## 6. 世界生成参数

P1 值域：

```text
seed: non-empty RandomSeedMaterial.world_seed string
world_profile: frontier_survival
region_count: integer [1,16]
spatial_layout.generation_mode: procedural
spatial_layout.coverage_mode: complete
spatial_layout.default_grid.width_chunks: integer [1,16]
spatial_layout.default_grid.height_chunks: integer [1,16]
spatial_layout.default_grid.min_z: integer [-16,16]
spatial_layout.default_grid.max_z: integer [-16,16]
spatial_layout.max_chunks_per_region: 256
initial_time.absolute_minute: non-negative integer
initial_time.year: positive integer
initial_time.day: positive integer
initial_time.season: spring | summer | autumn | winter
initial_time.season_day: integer [1,90]
initial_time.seasonal_daylight_profile: CalendarProfileRegistry reference
default_history_years: integer [0,1000]
required_start_settlement: boolean, frontier_survival 缺省为 true
climate_bias: stable unique climate_zone array, length [0,7]
terrain_bias: stable unique array of hill | forest | ridge | valley, length [0,4]
civilization_density: low | medium | high
resource_abundance: scarce | normal | abundant
danger_level: low | medium | high
abnormality_level: low | medium | high
```

空间参数必须满足：

```text
min_z <= max_z

width_chunks
* height_chunks
* (max_z - min_z + 1)
<= max_chunks_per_region
```

`initial_time.year/day/season/season_day/seasonal_daylight_profile` 必须等于
§19 由 `absolute_minute` 唯一派生的值；它们不是第二套可独立指定的时钟。

未知值产生 `validation_error`，不能回退到本地默认字符串。

`climate_bias` 只修改对应 climate zone 的候选权重。气候候选基础权重均为
1000；zone 出现在 `climate_bias` 时增加 750；`terrain_bias` 中至少一个值
支持该 zone 时增加 250，多个支持值也只增加一次。支持关系固定为：

```text
highland <- ridge | hill
marsh_humid <- valley
wet_temperate <- forest | valley
dry_steppe <- ridge
```

`abnormal` 的最终权重由 `abnormality_level` 覆盖为
`low=20, medium=80, high=200`。其他权重计算完后 clamp 到
`[0,1000000]`。

`terrain_bias` 使用以下 base-field delta；未列字段增量为 0：

| terrain_bias | elevation | moisture | rockiness | soil_depth | water_flow |
| --- | ---: | ---: | ---: | ---: | ---: |
| hill | 100 | -20 | 60 | -30 | 0 |
| forest | 0 | 100 | -20 | 100 | 20 |
| ridge | 180 | -40 | 140 | -80 | 20 |
| valley | -120 | 120 | -40 | 80 | 140 |

`terrain_bias` 是 stable unique 集合。对每个 base field，按照
`hill, forest, ridge, valley` 的 registry 顺序把所有命中项的 delta
逐项求和；随后与 climate、world parameter、coordinate 和 noise delta
一起求和，最后只执行一次 `[0,1000]` clamp。禁止取数组第一项或按数组输入
顺序覆盖。

`temperate` 气候的 base-field delta 明确为八个 0；它不是缺失映射。

## 7. 空间布局

### 7.1 P1 条带布局

`SpatialLayoutCandidateFormation` 不使用随机抽样。

Region 按 `region_index=0..region_count-1` 排列。

每个 Region 使用一个 grid；每个 chunk 使用：

```text
size_profile = wilderness_100m
width_meters = 100
height_meters = 100
z_step_meters = 20
```

grid 尺寸来自 `WorldGenerationParameters.spatial_layout.default_grid`。

每个 grid 使用局部整数坐标：

```text
min = (0, 0, min_z)
max = (width_chunks - 1, height_chunks - 1, max_z)
```

Region 世界原点：

```text
x = region_index * width_chunks * 100
y = 0
```

物理边界：

```text
min_x = origin_x
min_y = origin_y
max_x = origin_x + width_chunks * 100
max_y = origin_y + height_chunks * 100
min_z_meters = min_z * 20
max_z_meters = (max_z + 1) * 20
```

Region 类型固定为 `wilderness_region`。默认显示名为 `Region 001`、`Region 002`，仅用于展示。

用于跨 Region 邻接的 world-grid 坐标：

```text
world_grid_x = region_index * width_chunks + local_coord.x
world_grid_y = local_coord.y
world_grid_z = local_coord.z
```

`WorldChunk.coord` 仍保存 grid 内局部坐标；world-grid 坐标是 StaticChunkEdgeFormation 的确定性派生值，不新增权威字段。

相邻 Region `i` 和 `i+1` 的边界 chunk 在：

```text
region i: local x = width_chunks - 1
region i+1: local x = 0
相同 local y 和 z
```

上互为正交相邻。P1 不允许生成孤立 Region；region_count>1 时每对连续 Region 必须至少存在一对边界 ChunkEdge。

### 7.2 稳定 ID

P1 统一 ID 函数：

```text
stable_id(prefix, components) =
prefix
+ "_"
+ first_24_lower_hex(
    sha256(canonical_json_utf8(components))
  )
```

本文 ID 公式中的 `canonical scope` 固定表示：

```text
canonical_scope(scope) =
已通过判别式 schema 验证、
ID 数组按 ID ASC 排序、
数值已转为 canonical 定点表示的完整 JSON scope value
```

ID components 中写 `canonical scope` 时实际放入
`canonical_scope(scope)` 这个结构化 JSON value；外层 `stable_id` 再统一
执行一次 `canonical_json_utf8(components)`。不得提前把它变成实现语言的
默认字符串，也不得放显示名或对象内存地址。

各空间 ID 的 components：

```text
Region:
[world_id, "region", region_index, schema_version]

WorldChunkGrid:
[world_id, region_id, "grid", schema_version]

WorldChunk:
[world_id, region_id, grid_id, coord.x, coord.y, coord.z, schema_version]
```

ID 函数不能读取显示名、对象加载顺序或本地文件路径。

每个 grid 的候选 coord 集合必须恰好等于 bounds 三轴整数笛卡尔积。

## 8. 长期气候

### 8.1 profile 闭集

```text
temperature_band: cold | cool | mild | hot
rainfall_band: dry | medium | wet
humidity: low | medium | high
seasonality: weak | moderate | strong
prevailing_wind: north | northeast | east | southeast | south | southwest | west | northwest | variable
snow_months[]: spring | summer | autumn | winter
```

### 8.2 climate_zone 固定映射

| climate_zone | temperature | rainfall | humidity | seasonality | wind | snow_months |
| --- | --- | --- | --- | --- | --- | --- |
| cold_temperate | cold | medium | medium | strong | northwest | winter |
| temperate | mild | medium | medium | moderate | west | 空 |
| wet_temperate | cool | wet | high | moderate | southwest | 空 |
| dry_steppe | hot | dry | low | strong | west | 空 |
| highland | cold | medium | low | strong | northwest | winter |
| marsh_humid | mild | wet | high | weak | south | 空 |
| abnormal | cool | medium | high | weak | variable | 空 |

气候类型继续按整数权重和 `WeightedChoiceKernel` 选择。其余 profile 字段不再额外随机。

## 9. 地形

保留现有 elevation band、slope、soil、landform 和 ground 的阈值及优先级。

### 9.1 rock

`terrain.rock` 表示游戏规则使用的主导浅层基岩分类，不表示完整地质模拟。

闭集：

```text
basalt
limestone
granite
sandstone
shale
mixed_rock
```

按顺序取第一条：

```text
abnormal_pressure>=750 && rockiness>=600 -> basalt
landform=cave && moisture>=500 -> limestone
rockiness>=750 -> granite
moisture<=300 && soil_depth<=400 -> sandstone
soil_depth>=650 && moisture>=500 -> shale
default -> mixed_rock
```

### 9.2 vegetation_cover

闭集：

```text
sparse
shrub
grassland
sparse_forest
dense_forest
marsh_plants
```

按顺序取第一条：

```text
landform=wetland -> marsh_plants
landform=forest && moisture>=700 -> dense_forest
landform=forest -> sparse_forest
soil_depth>=500 && moisture>=350 -> grassland
moisture>=250 -> shrub
default -> sparse
```

### 9.3 visibility、cover 和通行成本

```text
visibility: high | medium | low
cover: none | low | medium | high
base_travel_cost_minutes: integer [5,240]
```

`visibility` 按顺序取第一条：

```text
vegetation_cover=dense_forest -> low
landform=cave -> low
landform=ruin -> medium
vegetation_cover in sparse_forest/marsh_plants -> medium
default -> high
```

`cover` 按顺序取第一条：

```text
landform in cliff/cave/ruin -> high
vegetation_cover=dense_forest -> high
vegetation_cover in sparse_forest/marsh_plants -> medium
landform=ridge -> medium
vegetation_cover=shrub or landform=hill -> low
default -> none
```

通行成本：

```text
base_travel_cost =
  landform_base_minutes
  + slope_modifier_minutes
```

结果 clamp 到 `[5,240]`。

| landform | base minutes |
| --- | ---: |
| plain | 15 |
| forest | 25 |
| hill | 25 |
| ridge | 35 |
| valley | 20 |
| riverbank | 30 |
| wetland | 40 |
| cliff | 240 |
| road | 10 |
| town_block | 10 |
| ruin | 25 |
| cave | 30 |
| lake_shore | 30 |

| slope | modifier minutes |
| --- | ---: |
| flat | 0 |
| gentle | 5 |
| steep | 20 |
| impassable | 200 |

`ground` 在现有规则之前增加最高优先级：

```text
moisture<=180
and soil_depth>=300
and rockiness<=350
-> sand
```

其后继续使用现有 landform 和 gravel 映射。

### 9.4 terrain_tags

按以下条件产生 tag，去重后按 `TerrainTagRegistry` 顺序输出：

| 条件 | tag |
| --- | --- |
| elevation_band=highland 或 landform in ridge/cliff | mountain |
| landform=forest | forest |
| vegetation_cover=dense_forest | dense_forest |
| landform=wetland | wetland |
| landform=cave | cave |
| landform=road | road |
| landform=town_block | settlement |
| landform=ruin | ruin |
| visibility=low | low_visibility |
| landform=ridge 且 vegetation_cover in sparse/shrub | wind_exposed |
| slope=impassable | impassable |

### 9.5 非初始可达值

以下值不由 `TerrainCandidateFormation` 初始产生：

```text
landform.riverbank: content_materialization | runtime_transition
landform.lake_shore: content_materialization | runtime_transition
ground.snow: runtime_transition
ground.stone_floor: content_materialization
```

`ground.sand` 由本节明确阈值产生。

## 10. 水文和 biome

水文物化后的唯一权威水体路径是：

```text
WorldChunk.terrain.water_presence
```

`ChunkHydrologyCandidate.resource_support` 只保存在 generation audit candidate
payload，供 ResourceFormation 和允许读取 candidate 的后续规则使用；它不
物化为 `WorldChunk.hydrology`。

FieldOwnership 和 WriteACL 必须登记：

```text
FieldOwnership(
  WorldChunk,
  WorldChunk.terrain.water_presence
) = terrain_hydrology
```

旧 `WorldChunk.water_presence`、`WorldChunk.hydrology` 及其通配 ACL 路径
必须删除或标为 migration-only alias；P1 新写入必须拒绝。

### 10.1 water_presence 第二遍

第一遍保留现有流量累积和水体分类。

第二遍按 chunk ID 遍历：

```text
if self.water_presence=none
and any orthogonal neighbor in spring/stream/river/pond/well
then self.water_presence=nearby
```

### 10.2 resource_support

```text
spring/stream/river/pond/stagnant/well
-> [{resource_kind: water, source_form: water_presence}]

none/nearby/seasonal
-> []
```

数组按 `resource_kind, source_form` 排序。

### 10.3 local climate

所有同时命中的温度和降水修正求和后 clamp。

`wind_exposure` 使用固定等级：

```text
high > medium > low
```

取所有命中条件中的最大等级。

### 10.4 biome

Biome 业务文档和 NumericAlgorithmSpec 引用同一个版本化条件矩阵。

`predator_habitat` 表示潜在捕食者栖息地，由 `danger_pressure>=650` 产生，不引用尚未生成的捕食者实体。

`water_source_nearby` 在以下水体存在时产生：

```text
spring
stream
river
pond
well
```

完整矩阵：

| 条件 | biome tag |
| --- | --- |
| climate_zone=cold_temperate 且 landform=forest | cold_forest |
| climate_zone=wet_temperate 且 landform=forest | wet_forest |
| elevation_band=highland 且 landform in ridge/hill | rocky_highland |
| landform=valley 且 water_presence in stream/river | creek_valley |
| landform=wetland 或 water_presence=stagnant | marsh |
| landform=town_block 且 civilization_pressure>=500 | settlement |
| landform=road 且 civilization_pressure>=500 | trade_route |
| landform=ruin 且 moisture>=550 | damp_ruin |
| abnormal_pressure>=650 | abnormal_zone |
| danger_pressure>=650 | predator_habitat |
| water_presence in spring/stream/river/pond/well | water_source_nearby |

## 11. 静态边和通行

按 §7 的 world-grid 坐标枚举全部 chunk。同一 z 层 Manhattan distance=1 的 chunk 必须生成两条方向相反的有向 ChunkEdge，包括连续 Region 的边界 chunk。

方向：

```text
delta x=+1 -> east
delta x=-1 -> west
delta y=+1 -> north
delta y=-1 -> south
```

ChunkEdge ID：

```text
stable_id(
  "chunk_edge",
  [world_id, source_chunk_id, target_chunk_id, schema_version]
)
```

基础字段：

```text
source_chunk_id
target_chunk_id
direction
adjacent = true
```

对每条 source -> target 有向边，静态通行状态按顺序取第一条：

```text
source/target 任一 landform=cliff -> blocked
source/target 任一 slope=impassable -> blocked
source/target 任一 water_presence in river/pond/stagnant -> conditional
source/target 任一 water_presence in stream/seasonal -> difficult
source/target 任一 slope=steep -> difficult
default -> open
```

非 blocked 边：

```text
base_time_minutes =
ceil((source.base_travel_cost_minutes
    + target.base_travel_cost_minutes) / 2)
+ passability_modifier_minutes
```

blocked 边的时间为 null。

固定 profile：

| 条件 | movement_type | difficulty | modifier | blocked_reason | risk_tags |
| --- | --- | --- | ---: | --- | --- |
| cliff | climb | extreme | 0 | cliff | fall |
| impassable | climb | extreme | 0 | terrain_impassable | fall |
| river/pond/stagnant | swim | hard | 20 | null | water_crossing |
| stream/seasonal | walk | moderate | 10 | null | wet_crossing |
| steep | climb | hard | 15 | null | fall, fatigue |
| default | walk | easy | 0 | null | 空 |

`conditional` 的条件固定为 `requires_registered_crossing_method`；具体允许的桥、船、涉水或攀爬方法由 resolver registry 决定。

`difficulty` 闭集固定为：

```text
trivial
easy
moderate
hard
extreme
```

完整输出：

```text
base_passability.conditions =
  [requires_registered_crossing_method], state=conditional
  [], 其他

base_traversal.risk_tags = profile risk_tags 按 RiskTagRegistry 顺序

visibility.line_of_sight_from_source =
  source.terrain.visibility != low
  and target.terrain.visibility != low

visibility.description =
  "edge." + direction + "." + base_passability.state

effective_passability = null
effective_traversal = null
```

effective 字段由后续 PassabilityReducer 写入；WorldFactValidator 运行前必须非 null。

PassabilityReducer：

```text
state rank:
open=0
difficult=1
conditional=2
blocked=3

effective rank =
max(base rank, each active override rank)
```

规则：

1. effective=blocked 时 `time_minutes=null`，blocked_reason 按 `priority DESC, source_kind ASC, source_type_id ASC, source_id ASC` 取第一项。ObstacleSource 的 source_type_id 是 obstacle_type；其他 override 使用其 rule/profile ID。
2. effective!=blocked 时：

```text
time_minutes =
clamp(
  base_time_minutes
  + sum(all active non-null time_delta_minutes),
  1,
  1000000
)
```

3. conditional 的 conditions 是 base conditions 和所有 active conditional override conditions 的稳定去重并集。
4. conditional 的 `time_minutes` 表示条件满足后的通行耗时，必须是有限正整数；具体 Actor 是否满足 conditions 由 RouteResolver 判断，不能写入全局 Edge。
5. difficulty 取 base 和 active override 声明值中的最高 difficulty rank；未声明时沿用 base。
6. movement_type 沿用 base，除非唯一最高 priority override 显式声明替代值。
7. risk_tags 取 base 与全部 active override 的稳定去重并集。
8. source_refs 包含 base 和所有参与聚合的 active override ID，按来源类型、ID 排序。

override 失活时必须从 base 和剩余 active override 重算，不能读取上一版 effective 值作为输入。

## 12. 天气

P1 初始 `WeatherFormation` 只生成 Region 级基础天气。

局部 chunk 天气覆盖保留为运行时规则，不进入初始 ready baseline。

### 12.1 完整输出

condition 使用 DRP 加权选择。

固定输出表：

| condition | intensity | wind | visibility modifier | ground effects | duration minutes |
| --- | --- | --- | ---: | --- | --- |
| clear | trace | calm | 0 | 空 | 120-360 |
| cloudy | light | light | 0 | 空 | 120-360 |
| fog | normal | light | -2 | 空 | 30-180 |
| light_rain | normal | moderate | -1 | wet | 60-240 |
| heavy_rain | heavy | strong | -2 | wet,muddy,slippery | 30-180 |
| snow | normal | moderate | -2 | snow_covered,slippery | 60-300 |
| strong_wind | heavy | gale | -1 | 空 | 30-240 |
| storm | severe | gale | -3 | wet,muddy,slippery,fast_water | 15-90 |
| abnormal_mist | abnormal | abnormal | -3 | 空 | 30-240 |

温度：

```text
climate base:
cold=5, cool=10, mild=18, hot=28

season delta:
spring=0, summer=8, autumn=-3, winter=-10

time_band delta:
dawn=-2, day=0, dusk=-1, night=-4, midnight=-5

temperature_c =
clamp(climate_base + season_delta + time_band_delta, -50, 60)
```

持续时间只使用本节逐天气区间表。数值算法文档引用同一个 WeatherDurationProfileRegistry，不得保留第二套概括区间。

区间内抽样使用一个两端都包含的 `int_range(min_minutes,max_minutes)` draw。抽样失败产生 `validation_error`。

每个 Region 级 WeatherState 固定字段：

```text
world_id = current World.id
scope = region
region_id = target Region.id
chunk_id = null
parent_weather_state_id = null
coverage_priority = base_region
condition/intensity/wind/visibility_modifier/ground_effects = 本节 profile
temperature_c = 本节整数公式
valid_for.start_world_minute = current absolute minute
valid_for.end_world_minute = start + sampled duration
generated_by.system = WeatherFormation
generated_by.rule_id = "weather.transition_by_profile.fixed_point.v1"
```

`previous_weather_state_id` 初始片段为 null；后续片段引用同 Region 紧邻的前一片段，且前一片段 end 必须等于当前 start。

WeatherState ID：

```text
stable_id(
  "weather",
  [
    world_id,
    region_id,
    valid_for.start_world_minute,
    condition,
    schema_version
  ]
)
```

WeatherState 的 `generated_by.random_draw_ref` 改为：

```text
generated_by.random_draw_refs: RandomDrawRef[2]
```

两项分别使用 logical_draw_id：

```text
"condition"
"duration_minutes"
```

并按 logical_draw_id ASC、draw_index ASC 排序。condition 记录 `weighted_choice`，duration 记录 `int_range`；任一缺失、重复或与输出不一致均为 `validation_error`。

## 13. 生态

### 13.1 字段闭集

```text
activity_cycle: dawn | day | dusk | night | any
diet: herbivore | carnivore | omnivore | scavenger | filter_feeder
sociality: solitary | pair | pack | herd | flock | swarm | school
danger_level: integer [0,5]
growth_form: individual | patch | shrub | tree | vine | cluster | aquatic_mat
population_pressure: stable | hungry | migrating | territorial | stressed
group_behavior: idle | foraging | traveling | stalking | fleeing | resting | guarding
stock.unit: liter | kg | count | bundle
coverage: sparse | moderate | dense
population_level: small | medium | large
abundance: small | medium | large | rich
```

水资源质量：

```text
clear | stagnant | polluted | unknown
```

非水资源质量：

```text
standard | degraded | contaminated | unknown
```

资源 category 决定合法质量子集。

### 13.2 形成 profile

新增：

```text
PlantFormationProfile[plant_category]
ResourceFormationProfile[resource_category, deposit_kind]
```

每个 profile 声明：

```text
stock_unit
capacity_per_band_milli
initial_fill_min_basis_points
initial_fill_max_basis_points
extraction_min_milli
extraction_max_milli
source_to_output_ratio_milli
allowed_loss_ratio_milli
recoverable
recovery_rate_per_day_milli
```

世界资源丰度修正：

```text
scarce -> 7000 basis points
normal -> 10000 basis points
abundant -> 14000 basis points
```

内容包只能选择 profile ID，不能覆写算法。

植物库存统一使用 `unit=count`，`resource_type=species_id`。coverage 容量：

| coverage | capacity amount |
| --- | ---: |
| sparse | 4.000 |
| moderate | 10.000 |
| dense | 20.000 |

植物初始填充使用一个 `fixed_unit` draw 映射到 5000-10000 basis points。单次提取最小 1.000、最大 3.000，转换比例 1.000，允许损耗 0.000。

| plant category | recovery amount/day |
| --- | ---: |
| tree | 0.050 |
| shrub | 0.250 |
| grass | 1.000 |
| edible_plant | 0.500 |
| medicinal_herb | 0.250 |
| poisonous_plant | 0.250 |
| fiber_plant | 0.500 |
| aquatic_plant | 0.500 |
| fungus | 0.500 |
| abnormal_flora | 0.100 |

资源 profile：

| resource category | unit | yield per abundance count | extraction min | extraction max | base recovery/day |
| --- | --- | ---: | ---: | ---: | ---: |
| water | liter | 10.000 | 0.100 | 2.000 | 10.000 |
| stone | kg | 10.000 | 0.500 | 5.000 | 0.000 |
| metal_ore | kg | 5.000 | 0.500 | 3.000 | 0.000 |
| clay_soil | kg | 10.000 | 0.500 | 5.000 | 0.250 |
| sand_gravel | kg | 15.000 | 0.500 | 5.000 | 0.000 |
| salt_mineral | kg | 5.000 | 0.100 | 2.000 | 0.000 |
| fuel | kg | 10.000 | 0.500 | 3.000 | 1.000 |
| gem_crystal | kg | 1.000 | 0.100 | 0.500 | 0.000 |
| corpse_remain | kg | 5.000 | 0.500 | 3.000 | 0.000 |
| abnormal_resource | kg | 2.000 | 0.100 | 1.000 | 0.000 |

所有资源 profile 共用：

```text
initial_fill_min_basis_points = 7000
initial_fill_max_basis_points = 10000
source_to_output_ratio = "1.000"
allowed_loss_ratio = "0.000"
recovery.cap_amount = stock.capacity_amount
```

`renewability=nonrenewable` 强制 recovery 为 0；`limited` 使用 profile recovery 的四分之一；`renewable` 使用完整 profile recovery。所有除法使用 `floor_nonnegative`。

资源 habitat score 到 abundance：

```text
350..549 -> small
550..699 -> medium
700..849 -> large
850..1000 -> rich
```

`abundance_count_band`：

```text
small -> int_range [1,2]
medium -> int_range [3,5]
large -> int_range [6,9]
rich -> int_range [10,15]
```

具体 abundance count 使用 DRP `abundance_count_band` 抽样。容量：

```text
capacity_milli =
floor(
  abundance_count
  * yield_per_count_milli
  * resource_abundance_basis_points
  / 10000
)
```

初始填充使用一个 `fixed_unit` draw 映射到 7000-10000 basis points。

质量初始值：

```text
water + source_form=spring/stream/river/well -> clear
water + source_form=pond/stagnant -> stagnant
water + source_form=seasonal/nearby -> unknown
abnormal_resource -> contaminated
其他非水资源 -> standard
```

ResourceNode.state.quality 只能由上表赋值。ResourceDeposit 不新增 quality 字段。

资源实例 ID：

```text
ResourceDeposit.id =
stable_id(
  "resource_deposit",
  [world_id, chunk_id, resource_id, deposit_kind, schema_version]
)

ResourceNode.id =
stable_id(
  "resource_node",
  [world_id, chunk_id, resource_id, deposit_kind, schema_version]
)
```

location 固定为 `scope=world_chunk, chunk_id=<target chunk>`；visibility 复制 NaturalResource.visibility，并按 ObjectiveVisibilityState 校验。

FloraPatch ID：

```text
stable_id(
  "flora_patch",
  [world_id, chunk_id, species_id, schema_version]
)
```

FloraPatch.location 固定到目标 chunk；visibility 复制 PlantSpecies.visibility；`state.season` 复制已经验证的 `WorldGenerationParameters.initial_time.season`。`derived.harvested` 和 `derived.depleted` 由库存派生器在同一 atomic batch 写入。

### 13.3 资源和植物选择

ResourceFormation 每 chunk target：

```text
scarce -> 1
normal -> 2
abundant -> 3
```

FloraFormation 每 chunk target：

```text
scarce -> 1
normal -> 2
abundant -> 4
```

两者均按 catalog ID 构造稳定 CandidateSet，使用加权无放回选择。

实际选择数：

```text
min(target_count, eligible_candidate_count)
```

eligible candidate 为空时使用 `emit_no_output_with_audit`。每次选择的 logical_draw_id 使用：

```text
"resource_select:" + selection_index
"flora_select:" + selection_index
```

### 13.4 动物生成

FaunaFormation 每 Region target：

```text
danger low -> 2
danger medium -> 3
danger high -> 4
```

每个选中 species 生成一个 CreaturePopulation。

habitat score 到 population level：

```text
350..549 -> small
550..799 -> medium
800..1000 -> large
```

每个 species 使用一个 `int_range` draw：

```text
group_size =
min_group_size
+ random_int_exclusive(max_group_size - min_group_size + 1)

level_multiplier:
small=1, medium=2, large=3

initial_live_count =
group_size * level_multiplier
```

初始状态：

```text
reserve_count = initial_live_count
group_member_count = 0
active_actor_count = 0
current_live_count = initial_live_count
```

CreaturePopulation ID：

```text
stable_id(
  "creature_population",
  [world_id, region_id, species_id, schema_version]
)
```

`chunk_ids` 是该 Region 中对该 species 的 habitat score >= 350 的 chunk，按 chunk_id 升序；集合为空时该 species 不得进入 CandidateSet。

其他初始字段：

```text
activity_cycle = AnimalSpecies.activity_cycle
pressure = stable
visibility = hidden
derived.group_member_count = 0
derived.active_actor_count = 0
derived.depleted = false
```

CreatureGroup 和 CreatureActor 只由运行时 resolver 从 reserve 中物化。

### 13.5 守恒

```text
current_live_count
= reserve_count
+ sum(active CreatureGroup.count)
+ count(active CreatureActor)
```

```text
depleted = current_amount == 0
harvested =
  current_amount < extraction.min_source_amount
```

恢复：

```text
recovered_milli =
floor(elapsed_world_minutes * rate_amount_per_day_milli / 1440)

new_amount =
min(cap_amount, old_amount + recovered_milli)
```

提取：

```text
source_decrease =
output_increase + declared_loss
```

## 14. 历史候选

### 14.1 OriginEventCandidate

候选 payload 必填：

```text
target_origin_type
scope
age_band
severity
cause_tags
participant_slots
expected_outputs
minimum_evidence_profile_id
supporting_input_refs
score_uint
```

每个 origin type 都必须有 `OriginFormationProfile`：

```text
eligibility predicates
default severity
allowed age bands
participant slots
expected output roles
minimum evidence types/count
score terms
```

当前 origin type 闭集中的每一个值都必须有 profile。

P1 profile：

| origin type | eligibility | allowed age | severity | minimum evidence |
| --- | --- | --- | --- | --- |
| natural_formation | terrain feature 或 hydrology.resource_support 存在 | old,ancient,timeless | trace | 1 TerrainFeature，或 1 ResourceDeposit/ResourceNode |
| settlement_foundation | settlement anchor 存在 | recent,old | medium | 1 SettlementProfile 或 Institution |
| road_trade_activity | road/trade_route 存在 | recent,old | minor | 1 Site 或 Institution |
| resource_discovery | hydrology.resource_support 或 terrain.rock/resource potential 支持 | recent,old | minor | 1 ResourceDeposit 或 Institution |
| resource_extraction | terrain/resource potential 且 civilization_pressure>=400 | recent,old | medium | 1 ResourceDeposit 加 1 WorldObject/Site |
| hunter_activity | forest/ridge 且 predator_habitat 或草食动物 habitat 支持 | fresh,recent | minor | 1 Site 或 WorldObject |
| guard_or_patrol_activity | settlement anchor 且 danger_pressure>=400 或 civilization_pressure>=500 | fresh,recent | minor | 1 Institution 或 SocialGroupState |
| inn_or_service_history | settlement anchor 且 road/trade_route 支持 | recent,old | minor | 1 Institution 加 1 ServiceState |
| accident_site | road/slope/water/danger 任一支持 | fresh,recent | medium | 从 Site/WorldObject/HazardSource 中取 2 个 |
| abandoned_camp | forest/road/valley 或 fuel resource potential 支持 | fresh,recent | minor | 2 个 Site/WorldObject |
| abandoned_vehicle | road/trade_route 支持 | recent | medium | 1 Site 加 1 WorldObject |
| predator_kill_site | predator_habitat 且 prey habitat 支持 | fresh | medium | 1 个 corpse_remain ResourceDeposit/ResourceNode 加 1 个 sign/clue WorldObject |
| monster_attack_trace | abnormal_pressure>=650 且 danger_pressure>=650 | fresh,recent | major | 从 abnormal/corpse ResourceDeposit/ResourceNode、sign/clue WorldObject、HazardSource 中取 2 个 |
| battle_or_skirmish | civilization_pressure>=400 且 road/ruin/settlement anchor 支持 | recent,old | major | 从 WorldObject/Site/corpse_remain ResourceDeposit/ResourceNode 中取 2 个 |
| fire_damage | forest/fuel potential/ruin/settlement anchor 支持 | fresh,recent | medium | 1 个 fire-damage WorldObject 或 HazardSource |
| flood_or_mudslide | water 且 slope!=flat | recent,old | medium | 1 TerrainFeature 或 ObstacleSource |
| structural_collapse | landform in ruin/cave 或 slope=impassable | recent,old | medium | 1 ObstacleSource 或 HazardSource |
| ruin_decay | landform=ruin | old,ancient | medium | 从 ruin Site/WorldObject 中取 2 个 |
| ritual_failure | ruin 且 abnormal_pressure>=650 | old,ancient | major | 从 ritual/abnormal WorldObject、Site、HazardSource 中取 2 个 |
| abnormal_contamination | abnormal_pressure>=650 | recent,old,timeless | major | 1 个 abnormal ResourceDeposit/ResourceNode 或 HazardSource |
| burial_or_corpse_site | danger_pressure>=500 且 landform in forest/valley/ruin/cave | recent,old | medium | 1 个 corpse_remain ResourceDeposit/ResourceNode 或 WorldObject |
| plague_or_sickness | settlement anchor 且 water_presence in pond/stagnant/well | recent,old | major | 从 water/corpse ResourceDeposit/ResourceNode 和 Site 中取 2 个 |
| crime_scene | settlement anchor 且 road/trade_route 支持 | fresh,recent | medium | 2 个 WorldObject/Site 证据 |

`OriginEligibilityPredicateRegistry` 使用以下辅助布尔值。对
`scope.kind=world_chunk`，`scope_chunks=[scope.id]`；对
`scope.kind=settlement`，`scope_chunks=Settlement.chunk_ids`。

```text
has_settlement =
  scope.kind=settlement

has_road =
  any scope chunk.terrain.landform=road

has_trade_route =
  any scope chunk.biome_tags contains trade_route

has_forest =
  any scope chunk.terrain.landform=forest
  or any scope chunk.terrain.vegetation_cover in [sparse_forest,dense_forest]

has_ruin =
  any scope chunk.terrain.landform=ruin

has_cave =
  any scope chunk.terrain.landform=cave

has_water =
  any scope chunk.terrain.water_presence
    in [spring,stream,river,pond,stagnant,well,seasonal]

has_permanent_or_stagnant_water =
  any scope chunk.terrain.water_presence in [pond,stagnant,well]

has_hydrology_support =
  any validated ChunkHydrologyCandidate
    where candidate.chunk_id in scope_chunks
    and candidate.resource_support is non-empty

has_resource_potential =
  has_hydrology_support
  or any scope chunk.terrain.rock
    in [basalt,limestone,granite,sandstone,shale]

has_predator_habitat =
  any scope chunk.biome_tags contains predator_habitat

has_natural_feature =
  any scope chunk.terrain.terrain_tags intersects
    [mountain,forest,dense_forest,wetland,cave]
  or has_hydrology_support

max_civilization =
  max(scope chunk.base_fields.civilization_pressure_milli)

max_danger =
  max(scope chunk.base_fields.danger_pressure_milli)

max_abnormal =
  max(scope chunk.base_fields.abnormal_pressure_milli)
```

每种 origin type 的 exact eligibility：

```text
natural_formation:
  has_natural_feature

settlement_foundation:
  has_settlement

road_trade_activity:
  has_road or has_trade_route

resource_discovery:
  has_resource_potential

resource_extraction:
  has_resource_potential and max_civilization>=400

hunter_activity:
  has_forest and has_predator_habitat

guard_or_patrol_activity:
  has_settlement and (max_danger>=400 or max_civilization>=500)

inn_or_service_history:
  has_settlement and (has_road or has_trade_route)

accident_site:
  has_road
  or has_water
  or max_danger>=500
  or any scope chunk.terrain.slope in [steep,impassable]

abandoned_camp:
  has_forest
  or any scope chunk.terrain.landform in [road,valley]

abandoned_vehicle:
  has_road or has_trade_route

predator_kill_site:
  has_predator_habitat

monster_attack_trace:
  max_abnormal>=650 and max_danger>=650

battle_or_skirmish:
  max_civilization>=400 and (has_road or has_ruin or has_settlement)

fire_damage:
  has_forest or has_ruin or has_settlement

flood_or_mudslide:
  has_water and any scope chunk.terrain.slope!=flat

structural_collapse:
  has_ruin
  or has_cave
  or any scope chunk.terrain.slope=impassable

ruin_decay:
  has_ruin

ritual_failure:
  has_ruin and max_abnormal>=650

abnormal_contamination:
  max_abnormal>=650

burial_or_corpse_site:
  max_danger>=500
  and any scope chunk.terrain.landform in [forest,valley,ruin,cave]

plague_or_sickness:
  has_settlement and has_permanent_or_stagnant_water

crime_scene:
  has_settlement and (has_road or has_trade_route)
```

集合按 chunk ID ASC 枚举；`any/max/intersects` 的结果与遍历顺序无关。
eligibility 只能读取 OriginHistoryCandidateFormation 之前已验证的 terrain、
biome、base pressure、Settlement、WorldGenerationParameters，以及同一
manifest 中按 `chunk_id` 可解析的 verified
`ChunkHydrologyCandidate.resource_support` candidate 引用。它不能把
candidate 伪装成 world fact，也不能读取后续 ResourceDeposit。
表中的 minimum evidence 只在后续物化阶段读取未来实体，不能反向成为候选
准入输入。

minimum evidence 中出现的名称必须解析为 canonical EntityType：
`Hazard` 和 `Obstacle` 之类简称不得进入 profile。`ResourceDeposit/ResourceNode`
的资源类别通过其 `NaturalResource` 引用校验。证据过滤只使用 canonical
字段：

```text
sign/clue WorldObject:
  WorldObject.object_type=clue
  or WorldObject.components.clue_profile exists

fire-damage WorldObject:
  WorldObject.physical.condition in [damaged, broken, ruined]

ruin Site:
  Site.type=abandoned_site

ritual WorldObject/Site:
  WorldObject.object_type in [clue, document, artwork]
  or Site.type in [temple_shrine, abandoned_site]

abnormal ResourceDeposit/ResourceNode:
  referenced NaturalResource.category=abnormal_resource

corpse_remain ResourceDeposit/ResourceNode:
  referenced NaturalResource.category=corpse_remain

water ResourceDeposit/ResourceNode:
  referenced NaturalResource.category=water
```

表中的 `HazardSource` 还必须分别满足相关 profile：fire 使用
`hazard_type=fire_risk`，abnormal 使用
`source_kind=abnormal_field`。这些过滤词不是新 EntityType，也不能由自由
文本或未登记 tag 推断。

“A 或 B”表示两个按表中书写顺序排列的替代证据分支，物化时选择第一个
能够满足最小数量的分支；“从集合中取 N 个”表示把列出的 canonical
EntityType 的合格实例构造为一个并集后取 N 个。不得由实现自行选择替代
分支。

P1 `participant_slots=[]`。自动生成的历史候选不猜测参与者；内容包未来若要声明参与者，必须提供可解析引用或使用允许的 unknown/abnormal slot，并使用独立 profile。

OriginCauseTagRegistry：

| origin type | cause_tags |
| --- | --- |
| natural_formation | natural_process |
| settlement_foundation | settlement_growth |
| road_trade_activity | trade_route |
| resource_discovery | resource_discovery |
| resource_extraction | resource_extraction |
| hunter_activity | hunting |
| guard_or_patrol_activity | patrol |
| inn_or_service_history | service_activity |
| accident_site | accident |
| abandoned_camp | abandonment |
| abandoned_vehicle | abandonment,trade_route |
| predator_kill_site | predation |
| monster_attack_trace | monster_attack,abnormal_influence |
| battle_or_skirmish | armed_conflict |
| fire_damage | fire |
| flood_or_mudslide | flood_or_mudslide |
| structural_collapse | structural_failure |
| ruin_decay | decay |
| ritual_failure | ritual_failure,abnormal_influence |
| abnormal_contamination | abnormal_contamination |
| burial_or_corpse_site | burial |
| plague_or_sickness | sickness |
| crime_scene | crime |

每行 cause_tags 按 registry order 写入。

expected output role 映射：

| evidence entity type | expected_outputs.role |
| --- | --- |
| Site | primary_site |
| WorldObject、TerrainFeature | evidence |
| ResourceDeposit、ResourceNode | resource |
| HazardSource | hazard |
| ObstacleSource | obstacle |
| FloraPatch、CreaturePopulation、CreatureGroup | ecology_change |
| SettlementProfile、Institution、ServiceState、SocialGroupState | social_state |
| sign/clue WorldObject | clue |

每个 profile 的 `expected_outputs` 是 minimum evidence 中允许 entity type 的
稳定去重映射。满足本节 `sign/clue WorldObject` canonical predicate 的对象
优先映射为 clue，其他 WorldObject 映射为 evidence。若同一 Site 只是辅助
证据，profile 可明确把 role 改为 supporting_site；P1 表未声明该覆写。

`default_history_years` 允许的 age：

```text
fresh: always
recent: default_history_years>=1
old: default_history_years>=10
ancient: default_history_years>=100
timeless: always
```

一个 profile 有多个合法 age 时，按 age ID 构造等权 CandidateSet，使用一个 `weighted_choice` draw。

scope 枚举：

```text
需要 settlement anchor 的 profile：
  每个 Settlement 形成一个 scope.kind=settlement 候选，
  scope.id=Settlement.id，
  chunk_ids=Settlement.chunk_ids

其他 profile：
  每个满足 eligibility 的 WorldChunk 形成一个 scope.kind=world_chunk 候选，
  scope.id=WorldChunk.id，
  chunk_ids=[WorldChunk.id]
```

scope 内 `chunk_ids` 按 ID ASC。`scope_id` 等于
`scope.kind + ":" + scope.id`，不使用显示名。

candidate ID：

```text
stable_id(
  "origin_candidate",
  [world_id, region_id, target_origin_type, canonical scope, schema_version]
)
```

`supporting_input_refs` 等于实际命中的 eligibility 输入引用，按 entity type、entity ID、field path 排序；`matched_support_predicate_count` 只计算这些已去重 predicate，不计算未来 minimum evidence。

候选分数：

```text
score_uint =
100
+ 200 * matched_support_predicate_count
+ 25 * severity_rank

severity_rank:
trace=0, minor=1, medium=2, major=3, catastrophic=4
```

结果 clamp 到 `[1,1000000]`。

### 14.2 数量和排序

每个 Region 最多选择两个历史候选。

排序：

```text
score DESC
target_origin_type ASC
scope_id ASC
candidate_id ASC
```

使用加权无放回选择。

实际选择数为 `min(2, eligible_candidate_count)`。每次选择 logical_draw_id 为 `"origin_select:" + selection_index`。

物化时证据不足：

```text
emit_no_output_with_audit
```

不能临时创建证据，也不能重抽其他候选。

证据满足时，每个 minimum evidence 分支先按：

```text
entity_type registry order
entity_id ASC
```

选择达到最小数量的证据，并稳定去重。OriginEvent：

```text
origin_event_id =
stable_id(
  "origin_event",
  [world_id, candidate_id, sorted evidence_entity_ids, schema_version]
)

participants = []
cause_tags = profile cause_tags
expected_outputs = profile expected outputs
evidence_entity_ids = selected evidence IDs
generated_by.rule_id = "origin.evidence_materialize.v1"
```

OriginEvent 与所有证据实体的 OriginMetadata attachment 在同一 atomic batch 提交；任一 attachment 不合法则整批拒绝。

OriginMetadata 改为多链接结构：

```text
origin.links[]:
  origin_event_id
  origin_role
  age_band
  visible_as_evidence
  notes
```

旧字段：

```text
origin.origin_event_ids
origin.origin_role
origin.age_band
origin.visible_as_evidence
origin.discovery_state
origin.notes
```

标记为 `migration_only`。其中 `origin.discovery_state` 不得迁入新世界事实；它必须转换为对应主体的 DiscoveryState，无法确定主体时记录 migration audit 而不猜测 player。

P1 attachment role：

| selected evidence kind | origin_role |
| --- | --- |
| sign/clue WorldObject | clue |
| 其他 WorldObject、Site、TerrainFeature | evidence |
| ResourceDeposit、ResourceNode | resource_trace |
| HazardSource | hazard_source |
| ObstacleSource | obstacle_source |
| FloraPatch、CreaturePopulation、CreatureGroup | remnant |
| SettlementProfile、Institution、ServiceState、SocialGroupState | social_trace |

每条新 link：

```text
origin_event_id = newly materialized OriginEvent.id
origin_role = 上表
age_band = OriginEvent.age_band
visible_as_evidence = true
notes = ""
```

`origin.links` 按 origin_event_id ASC、origin_role ASC 排序，`(origin_event_id,origin_role)` 必须唯一。同一实体由多个 OriginEvent 解释时，每个事件使用独立 link，不共享 role。

## 15. 地点与内部空间物化

### 15.1 Settlement 空间足迹

`SettlementAnchorFormation` 创建的 `Settlement` 是一组相连的 `WorldChunk`，不是单个点。

P1 anchor chunk 必须满足：

```text
coord.z = 0
terrain.slope != impassable
该 chunk 未被其他 Settlement 占用
```

anchor score 沿用 `settlement.anchor_score.fixed_point.v1`。候选按：

```text
score DESC
chunk_id ASC
```

处理。对每个候选执行：

```text
selected = [anchor_chunk]

while count(selected) < 3:
  frontier =
    与 selected 中任一 chunk 正交相邻、
    coord.z 相同、
    slope != impassable、
    未被其他 Settlement 保留、
    尚未在 selected 中的 chunk

  按 [
    到 anchor 的 Manhattan distance ASC,
    chunk_id ASC
  ] 选择第一项

  frontier 为空则放弃该 anchor
```

成功的 Settlement 固定占用 3 个连通 chunk。每个 Region 最多 3 个 Settlement；成功选择后立即保留其 3 个 chunk，后续候选不能重叠。

`Settlement` 初始字段：

```text
id = stable_id("settlement", [world_id, region_id, anchor_chunk_id, schema_version])
name = "Settlement " + 该 Region 内从 001 开始的稳定序号
type = settlement
region_id = anchor 所属 Region
chunk_ids = [anchor, 其余 chunk 按 Manhattan distance ASC、chunk_id ASC]
entry_chunk_ids = [anchor_chunk_id]
settlement_archetype_id = null
```

`settlement_archetype_id` 是 Site 放置与社会画像共用的聚落原型 ID。它在 Settlement 创建时可为 null，但 `SitePlacement` 提交后必须非 null，并属于 SettlementArchetypeRegistry。

`required_start_settlement=true` 且没有候选达到 score 门槛时，允许选择最高分 anchor 并记录 fallback audit；若仍无法形成 3 个连通、非 impassable chunk，则整个生成以 `validation_error` 结束。不得缩成一个 chunk，也不得让多个完整 Site 挤入同一 chunk。

### 15.2 archetype 单一赋值

`SitePlacement` 在读取已提交的 Settlement、道路、水源、ResourceDeposit、危险与异常压力后，按 SettlementArchetypeRegistry 从上到下选择第一条命中的 archetype。

一次选择同时产生：

```text
Settlement.settlement_archetype_id
该 archetype 的 required_institution_kinds 对应的 Site
后续 SettlementProfile.settlement_type 的唯一输入值
```

`SettlementProfileFormation` 必须复制 `Settlement.settlement_archetype_id`，不得重新分类。

找不到 archetype、同一 Settlement 得到多个值、或 Site 阶段与社会阶段值不相等，均为 `validation_error`。

### 15.3 SiteTypeProfileRegistry

P1 `Site.type` 闭集与 required institution kind 使用同一组 ID：

```text
elder_house
well_house
inn
guard_post
market_stall
warehouse
checkpoint
stable
blacksmith
abandoned_site
temple_shrine
hunter_lodge
```

每个 Site profile 完整声明：

| Site type | tags | footprint m | function zone | light | noise | crowding | curfew |
| --- | --- | --- | --- | --- | --- | --- | --- |
| elder_house | elder,administration | 16 x 12 | service_area | dim | low | sparse | false |
| well_house | well,water_source | 10 x 10 | service_area | normal | low | sparse | false |
| inn | inn,lodging | 28 x 22 | service_area | normal | moderate | moderate | true |
| guard_post | guard,security | 20 x 15 | staff_area | normal | moderate | sparse | true |
| market_stall | market,trade | 12 x 8 | service_area | bright | moderate | moderate | true |
| warehouse | warehouse,storage | 24 x 20 | storage_area | dim | low | sparse | true |
| checkpoint | checkpoint,gate | 14 x 10 | staff_area | normal | moderate | sparse | true |
| stable | stable | 24 x 18 | service_area | dim | moderate | sparse | false |
| blacksmith | forge,blacksmith | 18 x 14 | service_area | bright | high | sparse | false |
| abandoned_site | ruin,abandoned | 18 x 14 | storage_area | dark | silent | empty | false |
| temple_shrine | shrine,temple | 18 x 14 | service_area | dim | low | sparse | false |
| hunter_lodge | hunter,hunting | 16 x 12 | service_area | dim | low | sparse | false |

生成的 `Site.local_position` 固定为 `center`。footprint 的宽高是正整数米。

每个 profile 的节点基线都是一个 `LocationNode(type=interior_room)`，含两个 Zone：

```text
Zone 1: type=threshold
Zone 2: type=<profile.function_zone>
```

若 function zone 也是 `threshold`，profile 非法；P1 表中不存在该情况。

### 15.4 Site、Node 和 Zone 物化

对一个 Settlement：

```text
site kinds =
SettlementArchetypeRegistry.required_institution_kinds
按 registry 中声明顺序

target chunks =
[entry chunk] +
[其余 settlement chunks 按到 entry chunk 的 Manhattan distance ASC、chunk_id ASC]
```

第 N 个 Site kind 放到第 N 个 target chunk。P1 archetype 的 required
institution 数必须为 1、2 或 3；不能超过 Settlement 的 3 个 chunk。

每个 target chunk 在该批次开始时必须满足：

```text
site_slots.primary_site_id = null
site_slots.secondary_site_ids = []
```

Site、LocationNode 和 Zone 的 ID：

```text
site_id =
stable_id(
  "site",
  [world_id, settlement_id, site_kind, target_chunk_id, schema_version]
)

node_id =
stable_id(
  "location_node",
  [world_id, site_id, "interior_room", 0, schema_version]
)

threshold_zone_id =
stable_id(
  "zone",
  [world_id, node_id, "threshold", 0, schema_version]
)

function_zone_id =
stable_id(
  "zone",
  [world_id, node_id, function_zone_type, 1, schema_version]
)
```

Site 必填字段：

```text
id = site_id
name = "<site_kind> <Settlement 内从 001 开始的稳定序号>"
type = site_kind
parent_chunk_id = target_chunk_id
local_position = center
footprint = profile footprint
entry_node_ids = [node_id]
tags = profile tags 按 SiteTagRegistry 顺序
state.enterable = true
state.open = site_kind != abandoned_site
state.curfew_sensitive = profile curfew
state.operational_state =
  abandoned, site_kind=abandoned_site
  active, 其他
```

`Site.state.operational_state` 闭集为：

```text
active
closed
abandoned
```

语义：

- `enterable` 表示空间上能否通过 SiteBoundaryEdge 进入。
- `open` 表示机构是否处于正常营业/运作状态，不等于物理可进入。
- `curfew_sensitive` 表示运行时宵禁规则可以改变 open 或服务可用性。
- `operational_state` 表示长期运行状态。

`enterable=true` 时 `entry_node_ids` 必须非空；`operational_state=closed` 时 `open=false`；`operational_state=abandoned` 时 `open=false`，但可以 `enterable=true`。

LocationNode 必填字段：

```text
id = node_id
name = "<Site.name> interior"
type = interior_room
site_id = site_id
parent_id = site_id
display_path = [Settlement.name, Site.name, node.name]
zones = [threshold zone, function zone]
environment.light = profile light
environment.noise = profile noise
environment.crowding = profile crowding
environment.temperature_offset_tenth_c = 0
tags = [indoor, public_area]
```

环境闭集：

```text
light: dark | dim | dusk | normal | bright
noise: silent | low | moderate | high
crowding: empty | sparse | moderate | crowded
```

Zone 必填字段：

```text
id
name
type
access.state = open
access.requires = []
access.blocked_reason = null
```

`Zone.type` P1 闭集：

```text
threshold
service_area
staff_area
rest_area
storage_area
```

`Zone.access.state` 闭集为 `open/restricted/blocked`：

- open：requires 必须为空，blocked_reason 必须为 null。
- restricted：requires 必须非空，blocked_reason 可为 null。
- blocked：blocked_reason 必须非空。

同批次把 `WorldChunk.site_slots.primary_site_id` 更新为对应 site_id。Site、Node、Zone、chunk slot 更新和 `Settlement.settlement_archetype_id` 使用一个 `atomic_commit_group_id`。

### 15.5 PlaceHierarchyRegistry

P1 registry 对每个 Site type 生成一条 depth=40 entry：

```text
allowed_child_types = [interior_room]
allowed_child_count_range = {min: 1, max: 1}
allowed_zone_types = [threshold, <profile.function_zone>]
```

共享 entry：

```text
interior_room:
  hierarchy_depth = 50
  allowed_child_types = [zone]
  allowed_child_count_range = {min: 2, max: 2}
  allowed_zone_types =
    [threshold, service_area, staff_area, rest_area, storage_area]

zone:
  hierarchy_depth = 60
  allowed_child_types = []
  allowed_child_count_range = {min: 0, max: 0}
  allowed_zone_types = []
```

`LocationChildGenerationContext` 是本次生成的 system_ledger 输入，不是运行时空间事实。P1 不调用 LLM；它的 allowed 集合与 count range 必须和上述 registry 完全相等。

### 15.6 边界边和 portal 引用

每个 Site 生成两条有向 SiteBoundaryEdge：

```text
entry: parent_chunk -> threshold zone
exit: threshold zone -> parent_chunk
```

固定字段：

```text
base_passability.state = open
base_passability.conditions = []
base_passability.blocked_reason = null
base_traversal.base_time_minutes = 1
base_traversal.scope = threshold
base_traversal.movement_type = enter | leave
base_traversal.risk_delta = 0
portal_object_id = null
```

ID：

```text
stable_id(
  "site_boundary_edge",
  [world_id, site_id, edge_type, source canonical ref, target canonical ref, schema_version]
)
```

P1 单节点 Site 不生成 LocationEdge。

`portal_object_id` 改为 nullable reference：

- null 表示开放阈值没有独立 WorldObject。
- 非 null 时必须引用 `object_type=portal` 或具备 enter/leave affordance 的 WorldObject。
- 以后绑定实体门必须由独立 `PortalBindingMaterializer` 更新，并形成事件；LocationGenerator 不能预写尚未存在的对象 ID。

`effective_passability` 和 `effective_traversal` 在 LocationGenerator 提交时为 null，由后续 PassabilityReducer 原子写入；运行时开放前必须已经非 null。

WriteACL 中 SitePlacement 的 Site 字段必须改为 canonical：

```text
id
name
type
parent_chunk_id
local_position
footprint
entry_node_ids
tags
state
```

旧的 `anchor_chunk_id/covered_chunk_ids/nodes` 不属于 Site schema，必须从 ACL 删除。

## 16. 聚落社会

### 16.1 SettlementArchetypeRegistry

每个 settlement type 固定声明：

```text
population_band
economy_basis
governance
law_profile
outsider_policy
resource_pressure_defaults
required_institution_kinds
required_social_group_kinds
```

按表格从上到下选择第一条命中项：

| settlement type | eligibility |
| --- | --- |
| ruin_settlement | landform=ruin 且 civilization_pressure>=250 |
| mining_camp | ore ResourceDeposit 存在 |
| fortified_post | civilization_pressure>=650 且 danger_pressure>=650 |
| market_town | civilization_pressure>=750 且 road/trade_route 存在 |
| frontier_town | civilization_pressure>=500 且 road 存在且 danger_pressure>=400 |
| village | civilization_pressure>=450 且永久水源存在 |
| roadside_stop | road 存在 |
| hamlet | settlement anchor 存在 |

分类输入只覆盖 `Settlement.chunk_ids`，精确定义为：

```text
civilization_pressure =
  max(chunk.base_fields.civilization_pressure_milli)

danger_pressure =
  max(chunk.base_fields.danger_pressure_milli)

abnormal_pressure =
  max(chunk.base_fields.abnormal_pressure_milli)

landform=ruin:
  any chunk.terrain.landform=ruin

road exists:
  any chunk.terrain.landform=road

trade_route exists:
  any chunk.biome_tags contains trade_route

permanent water exists:
  any chunk.terrain.water_presence in [spring, stream, river, pond, well]

ore ResourceDeposit exists:
  ResourceDeposit.location.chunk_id in Settlement.chunk_ids
  and referenced NaturalResource.category=metal_ore
```

所有 `any` 按 chunk_id 或 ResourceDeposit.id ASC 枚举；结果是布尔值，不受
首个命中对象之外的遍历顺序影响。表中的 threshold 只读取上述 max 值，
不能只读 anchor chunk，也不能把 3 个 chunk 的 pressure 求和。

archetype：

| type | population | economy | governance | law | outsider policy | required institutions | required groups |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hamlet | tiny | hunting,farming | loose_custom | customary | neutral | elder_house,well_house | local_residents,farmers |
| village | small | farming,herding | elder_council | customary | neutral | elder_house,well_house | local_residents,farmers |
| frontier_town | medium | hunting,road_service,inn_trade | guard_council | curfew_strict | suspicious_taxed | inn,guard_post,well_house | local_residents,guards |
| market_town | large | road_service,inn_trade,ore_trade | merchant_lead | curfew_light | welcoming | inn,market_stall,warehouse | local_residents,merchants |
| fortified_post | small | guard_service,road_service | military_outpost | military_order | restricted | guard_post,checkpoint,well_house | local_residents,guards |
| roadside_stop | tiny | road_service,inn_trade | innkeeper_network | customary | welcoming | inn,stable,well_house | local_residents,innkeepers |
| mining_camp | small | ore_trade,road_service | loose_custom | checkpoint_control | suspicious | blacksmith,warehouse,checkpoint | local_residents,laborers |
| ruin_settlement | tiny | salvage | abandoned | none | hostile | abandoned_site | local_residents,outsiders |

resource pressure defaults：

| type | food | water | lodging | security |
| --- | --- | --- | --- | --- |
| hamlet | low | low | high | medium |
| village | low | low | medium | low |
| frontier_town | medium | low | high | high |
| market_town | low | low | medium | medium |
| fortified_post | medium | low | high | medium |
| roadside_stop | medium | medium | high | high |
| mining_camp | medium | medium | high | high |
| ruin_settlement | high | high | critical | critical |

required institution 必须唯一绑定到
`Site.type=Institution.kind` 且属于同一 Settlement 的 Site。§15.3 的 tags
用于检索和投影，不参与机构身份匹配。缺少匹配 Site、命中多个 Site 或
Site.kind 不相等时，SettlementSocialFormation 产生 `validation_error`；
它不能创建无空间来源的机构。

### 16.2 子阶段

```text
SettlementProfile
-> Institution
-> SocialGroup
-> PolicyAndPressure
-> NamedNPC
-> Service
```

赋值规则：

- SettlementProfile 的 settlement_type 必须复制 `Settlement.settlement_archetype_id`，其余字段由 archetype 完整赋值。
- Institution 按 required kind 和 Site tag 生成。
- SocialGroup 固定包含 local_residents，再增加 archetype 要求群体。
- PolicyAndPressure 直接使用本节 P1 profile；初始化修正固定为 0。
- 每个需要 operator 的 Institution 生成一个稳定 operator NPC。
- Service 由 Institution、provider 和 ServiceProfileRegistry 生成。

整个 settlement 批次使用一个 `atomic_commit_group_id`。

Institution 的 Site tags 校验和 operator role：

| institution kind | Site 必含 tag（校验用） | operator role |
| --- | --- | --- |
| inn | inn 或 lodging | innkeeper |
| guard_post | guard 或 security | guard |
| market_stall | market 或 trade | merchant |
| blacksmith | forge 或 blacksmith | blacksmith |
| stable | stable | stablehand |
| well_house | well 或 water_source | laborer |
| temple_shrine | shrine 或 temple | priest |
| hunter_lodge | hunter 或 hunting | hunter |
| warehouse | warehouse 或 storage | merchant |
| checkpoint | checkpoint 或 gate | gatekeeper |
| elder_house | elder 或 administration | elder |
| abandoned_site | ruin 或 abandoned | 无 |

### 16.3 ServiceProfileRegistry

每个 service type 必须声明：

```text
base price
requirements
grants
risk modifiers
provider requirement
availability rule
resolver
allowed event types
reservation_quantity
reservation_duration_minutes
entitlement_duration_policy nullable
```

新增 requirement：

```text
has_compatible_container
```

新增 grant：

```text
stable_space
```

P1 service profile：

| service | institution | copper price | requirements | grants | risk modifier |
| --- | --- | ---: | --- | --- | --- |
| food | inn/market_stall | 1 | pay_price,provider_present,stock_available,service_open | food_item | local_trust_up |
| lodging | inn | 3 | pay_price,not_banned,provider_present,stock_available,service_open | legal_bed_for_tonight,room_key | curfew_risk_down |
| water_access | well_house/inn | 1 | pay_price,has_compatible_container,service_open | water_refill | local_trust_up |
| stable_service | stable | 2 | pay_price,provider_present,service_open | stable_space | 空 |
| repair | blacksmith | 5 | pay_price,provider_present,service_open | repair_completed | 空 |
| rumor | inn/market_stall | 1 | pay_price,provider_present,social_attitude_not_hostile | rumor_clue | rumor_heat_up |
| trade | market_stall/warehouse | 0 | not_banned,provider_present,service_open | trade_access | 空 |
| medical_help | temple_shrine | 5 | pay_price,provider_present,service_open | medical_treatment | local_trust_up |
| guide | hunter_lodge/inn | 4 | pay_price,provider_present,service_open | guide_route | security_pressure_down |
| protection | guard_post | 10 | pay_price,has_identity,provider_present,service_open | protection_status | security_pressure_down |
| entry_permission | checkpoint/guard_post | 1 | has_identity,provider_present,service_open | entry_permission | curfew_risk_down |

`rumor_heat_up` 加入 risk modifier 闭集。空 risk modifier 序列化为空数组。

所有 P1 ServiceProfile 的 `reservation_quantity=1`、`reservation_duration_minutes=10`。只有 AI `offer_service` 可以使用这两个参数创建 service_use reservation；其他动作不得创建 reservation。

`ServiceState.state.remaining_uses` 是 nullable 非负整数；null 表示 profile 声明的无限次服务。`availability=limited` 时必须是正整数，`sold_out` 时必须为 0。

会创建 `ServiceEntitlementState` 的 P1 grant 使用：

| service | entitlement_type | entitlement_duration_policy |
| --- | --- | --- |
| lodging | legal_bed_for_tonight | until_next_dawn |
| stable_service | stable_space | fixed_minutes:720 |
| trade | trade_access | fixed_minutes:60 |
| protection | protection_status | fixed_minutes:1440 |
| entry_permission | entry_permission | fixed_minutes:1440 |

其他 P1 grant 是对象、状态结算或知识结果，不创建 ServiceEntitlementState，
其 `entitlement_duration_policy=null`。

`until_next_dawn` 表示严格晚于提交 `start_world_minute` 的第一个 daylight
profile `dawn` 区间起点。若当前正处于 dawn，取下一日的 dawn 起点，不取
当前区间起点。

`ServiceEntitlementState` 时间字段统一为：

```text
permanent: boolean
valid_for: GameTimeInterval nullable
```

P1 正常服务只产生 `permanent=false`，此时 `valid_for` 必填且为半开区间
`[start_world_minute,end_world_minute)`：

```text
start_world_minute = 授权 StateTransition.occurred_at.absolute_minute
end_world_minute = entitlement_duration_policy 的确定结果
```

`permanent=true` 时 `valid_for=null`；该值只允许 migration 或另行登记的
永久授权 resolver 产生。旧 `valid_from={day,minute_of_day}` 和
`valid_until={day,minute_of_day}` 标记为 `migration_only`，新 schema、
catalog、proposal 和 resolver 必须拒绝。

`ServiceEntitlementState.valid_scope.kind` 闭集：

```text
settlement
site
site_node
```

每个 kind 的必填 ID 由判别式 schema 约束。

### 16.4 Institution、operator 和 service

每个 required institution kind 恰好创建一个 Institution，并绑定同 kind 的 Site。

Institution ID：

```text
stable_id(
  "institution",
  [world_id, settlement_id, institution_kind, site_id, schema_version]
)
```

控制群体优先映射：

| institution kind | preferred group |
| --- | --- |
| inn | innkeepers |
| guard_post | guards |
| market_stall | merchants |
| blacksmith | laborers |
| stable | laborers |
| well_house | local_residents |
| temple_shrine | religious_group |
| hunter_lodge | hunters |
| warehouse | merchants |
| checkpoint | guards |
| elder_house | local_residents |
| abandoned_site | local_residents |

preferred group 不在该 Settlement 的 required groups 中时，固定回退到 `local_residents`。

Institution service 映射：

| institution kind | services |
| --- | --- |
| inn | food,lodging,rumor,guide |
| guard_post | protection,entry_permission |
| market_stall | food,trade,rumor |
| blacksmith | repair,trade |
| stable | stable_service |
| well_house | water_access |
| temple_shrine | medical_help,rumor |
| hunter_lodge | guide,trade |
| warehouse | trade |
| checkpoint | entry_permission |
| elder_house | rumor |
| abandoned_site | 空 |

services 按 ServiceTypeRegistry 顺序排序。

Institution 字段：

```text
settlement_id = current settlement
kind = required institution kind
site_id = matching Site.id
controlled_by_group_id = 映射后的 group_id
operator_npc_ids = []，直到同批 NamedNPC 子阶段回填
services = 上表
status =
  abandoned, kind=abandoned_site
  open, 其他
generated_by.rule_id =
  "institution.from_settlement_archetype.v1"
```

除 abandoned_site 外，每个 Institution 恰好创建一个 operator NPC。

operator role 使用 §16.2 的 institution-to-role 表；无 role 的 abandoned_site 不创建 NPC。

role profile：

| role | personality_tags |
| --- | --- |
| innkeeper | practical,talkative |
| guard | stern,loyal |
| merchant | practical,greedy |
| blacksmith | practical,proud |
| stablehand | practical,kind |
| hunter | practical,risk_averse |
| elder | practical,loyal |
| priest | kind,secretive |
| laborer | practical,risk_averse |
| gatekeeper | stern,suspicious |

NPC ID：

```text
stable_id(
  "npc",
  [world_id, settlement_id, institution_id, operator_role, 0, schema_version]
)
```

NPC 初始字段：

```text
name = "<operator_role> <Settlement 内稳定序号>"
home_site_id = Institution.site_id
current_location =
  scope=site_node,
  site_id=matching site,
  node_id=该 Site 唯一 node,
  zone_id=该 Site function zone
group_id = Institution.controlled_by_group_id
institution_ids = [Institution.institution_id]
personality_tags = role profile
attitude_to_player = outsider policy 映射
known_services = Institution.services
state_revision = 1
generated_by.rule_id = "npc.operator_for_institution.v1"
```

outsider policy 到初始 attitude：

| outsider policy | attitude |
| --- | --- |
| welcoming | friendly |
| neutral | neutral |
| suspicious | cautious |
| suspicious_taxed | cautious |
| restricted | unknown_suspicious |
| hostile | hostile |

每个 Institution.services 中的 service type 恰好创建一个 ServiceState：

```text
service_id =
stable_id(
  "service",
  [world_id, settlement_id, institution_id, service_type, schema_version]
)

provider_npc_id = Institution 唯一 operator
base_price = ServiceProfileRegistry 的 copper price
availability = available
requirements/grants/risk_modifiers = ServiceProfileRegistry
state.active = true
state.remaining_uses = null
generated_by.rule_id = "service.from_institution_profile.v1"
```

没有 operator 的 Institution.services 必须为空。

### 16.5 SocialGroupState

群体 kind 集合是 archetype.required_social_group_kinds 的稳定去重结果，并强制包含一次 `local_residents`。

群体 ID：

```text
stable_id(
  "social_group",
  [world_id, settlement_id, group_kind, schema_version]
)
```

group profile：

| group kind | population_band | core_interests |
| --- | --- | --- |
| local_residents | majority | security,resource_access |
| innkeepers | significant | lodging_control,reputation |
| guards | significant | security,curfew_order |
| hunters | small | territory,resource_access |
| merchants | significant | trade_profit,reputation |
| craftspeople | small | trade_profit,resource_access |
| farmers | significant | food_price,water_access |
| laborers | significant | resource_access,food_price |
| travelers | small | lodging_control,security |
| outsiders | minority | security,resource_access |
| minority_group | minority | security,reputation |
| religious_group | small | religious_order,reputation |
| criminals | tiny | territory,information_control |
| refugees | small | security,food_price |

初始字段：

```text
home_chunk_ids = Settlement.chunk_ids
associated_site_ids =
  local_residents: Settlement 全部 Site
  其他: controlled_by_group_id 指向本群体的 Institution.site_id
ideology_tags = []
fears = []
attitude_to_player = §16.4 outsider policy 映射
state_revision = 1
generated_by.rule_id = "social_group.from_settlement_archetype.v1"
```

数组均按对应 registry 或 ID 升序排序。

群体 pressure 使用 Settlement 的 SocialPressureState 投影：

```text
security = guard_attention
scarcity = resource_scarcity
xenophobia = outsider_suspicion
fear = fear_of_monsters
anger = "0.000"
trust = local_trust
curiosity = "0.300"
greed =
  "0.400", group_kind=merchants
  "0.200", 其他
```

八个键都必须出现，值使用 normalized_milli 字符串。

### 16.6 LawPolicy

每个 Settlement 最多创建一个初始 LawPolicy。映射：

| law_profile | policy_type | severity | active time bands | effects |
| --- | --- | --- | --- | --- |
| none | 无输出 | - | - | - |
| customary | 无输出 | - | - | - |
| curfew_light | curfew | light | midnight,night | street_action_restricted |
| curfew_strict | curfew | strict | midnight,night | street_action_restricted,guard_questioning_increased |
| checkpoint_control | checkpoint | normal | midnight,night,dawn,day,dusk | service_requires_identity,trade_access_restricted |
| military_order | weapon_restriction | strict | midnight,night,dawn,day,dusk | weapon_carry_risk_up,guard_questioning_increased |
| temple_rule | religious_taboo | normal | midnight,night,dawn,day,dusk | service_requires_identity |

`active_time_band` 使用 CalendarProfile 的 time-band ID，按注册顺序排序。affected_groups 固定为 `[outsiders]`。

`enforced_by_group_id` 优先引用 guards，若不存在则引用 local_residents。

ID：

```text
stable_id(
  "law_policy",
  [world_id, settlement_id, policy_type, schema_version]
)
```

`state.active=true`。

### 16.7 EconomyState

每个 Settlement 恰好创建一个 EconomyState：

```text
economy_state_id =
stable_id("economy", [world_id, settlement_id, schema_version])

currency_standard = copper_silver_gold
```

resource pressure 到 price/scarcity：

| resource pressure | price_level | scarcity |
| --- | --- | --- |
| none | cheap | none |
| low | normal | low |
| medium | normal | medium |
| high | expensive | high |
| critical | unavailable | critical |

字段映射：

```text
price_level.food <- SettlementProfile.resource_pressure.food
price_level.water <- SettlementProfile.resource_pressure.water
price_level.lodging <- SettlementProfile.resource_pressure.lodging

scarcity.food <- resource_pressure.food
scarcity.water <- resource_pressure.water
scarcity.safe_bed <- resource_pressure.lodging

price_level.repair =
  normal, 存在 blacksmith Institution
  unavailable, 否则

price_level.general = normal

scarcity.tools =
  low, 存在 blacksmith
  medium, 不存在 blacksmith 但存在 market_stall 或 warehouse
  high, 其他
```

`outsider_policy=suspicious_taxed` 时创建两条 markup rule：

```text
(service_type=lodging, modifier=markup_minor)
(service_type=trade, modifier=markup_minor)
```

其他 outsider policy 的初始 `social_markup_rules=[]`。规则按 service_type ASC、modifier ASC 排序。

### 16.8 SocialPressureState

每个 Settlement 恰好创建一个 SocialPressureState。

`pressure` 的完整键闭集固定为：

```text
curfew
outsider_suspicion
fear_of_monsters
resource_scarcity
guard_attention
local_trust
rumor_heat
```

七个键都必须存在；不得把 `active_patrol_level` 混入 normalized_milli
pressure object。

| archetype | curfew | outsider suspicion | fear of monsters | resource scarcity | guard attention | local trust | rumor heat | patrol |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| hamlet | 0 | 200 | 300 | 200 | 100 | 500 | 100 | low |
| village | 100 | 150 | 200 | 100 | 100 | 600 | 100 | low |
| frontier_town | 800 | 600 | 700 | 400 | 600 | 200 | 300 | normal |
| market_town | 300 | 100 | 300 | 200 | 400 | 500 | 400 | normal |
| fortified_post | 700 | 700 | 600 | 300 | 800 | 100 | 100 | high |
| roadside_stop | 200 | 100 | 500 | 500 | 200 | 400 | 500 | low |
| mining_camp | 400 | 500 | 600 | 500 | 400 | 200 | 300 | normal |
| ruin_settlement | 0 | 900 | 900 | 900 | 0 | 0 | 200 | none |

表中的整数按 milli 解释并序列化为三位小数字符串。

```text
pressure_state_id =
stable_id("social_pressure", [world_id, settlement_id, schema_version])

active_rumor_ids = []
state_revision = 1
```

P1 初始化修正固定为 0。资源短缺、季节、事件和 AI proposal 造成的变化只能通过运行时 resolver 和 EventLog 更新，不能在初始形成算法中加入未声明修正。

### 16.9 原子闭包

SettlementSocialFormation 的同一 atomic batch 必须包含：

```text
SettlementProfile
SocialGroupState[]
Institution[]
NamedNPCState[]
ServiceState[]
LawPolicy[0..1]
EconomyState
SocialPressureState
Institution.operator_npc_ids 回填
```

批内引用按中间状态验证。任何 required Site、group、operator 或 service 引用缺失时整批拒绝，不允许提交部分社会实体。

## 17. 客观可观察性

实体级标量 `visibility` 使用 `ObjectiveVisibilityState`，表示客观发现难度：

```text
visible
hinted
hidden
removed
```

含义：

- visible：正常观察即可发现。
- hinted：正常观察只会发现迹象。
- hidden：需要 search 或特殊条件。
- removed：实体已不在场。

该字段不表示任何主体已经发现目标。

P1 `ObjectiveVisibilityState` 适用于：

```text
WorldObject.visibility
CreatureGroup.visibility
HazardSource.visibility
ObstacleSource.visibility
```

它不替换下列结构化字段：

```text
ChunkEdge.visibility.line_of_sight_from_source
ChunkEdge.visibility.description
LocationEdge.visibility.visible_from_source
LocationEdge.visibility.visible_from_target
LocationEdge.visibility.hint_text
site_relations[].visibility
```

结构化 visibility 的每个完整 path 使用自己的 FieldSpec；不同 path 不能仅因末级字段同名就共用标量 schema。

`observe` 和 `search` 只创建或更新 DiscoveryState 和 KnowledgeState，不能把 `discovered` 写入世界事实。

## 18. WorldObject

### 18.1 state

P1 新状态只允许：

```text
durability: normalized_milli
opened: boolean
locked: boolean
equipped_by: nullable Actor reference
charges: integer [0,1000000]
```

旧字段：

```text
state.fuel
state.amount
state.quality
components.portal_profile.open_state
components.portal_profile.locked
```

标记为 `migration_only`。

P1 开合和锁定状态的唯一权威字段是 `state.opened` 与 `state.locked`。
迁移器把 portal component 旧值复制到这两个字段后删除旧路径；运行时
resolver、validator、passability 和 catalog 不得同时读取两套状态。
`components.portal_profile` 只保留 portal 的静态连接、视线和声音属性。

### 18.2 component registry

至少建立：

```text
ToolKindRegistry
ToolQualityRegistry
DamageProfileRegistry
ArmorSlotRegistry
ResourceQualityRegistry
WaterQualityRegistry
LightRadiusBandRegistry
ContainerLightTransmissionRegistry
FuelTypeRegistry
SmokeLevelRegistry
NoiseLevelRegistry
DifficultyRegistry
ObjectSlotRule
```

P1 初始值：

```text
tool_kind:
pry | repair | cut | dig | hammer | lockpick | filter

tool_quality:
rough | standard | fine | masterwork

damage_profile:
blunt | pierce | light_slash | heavy_slash | fire

armor_slot:
head | body | hands | legs | feet | shield

resource_quality:
fresh | stale | dry | wet | standard | degraded | contaminated | unknown

water_quality:
clear | stagnant | polluted | unknown

light_radius_band:
self | near | room | far

container_light_transmission:
opaque | transparent

light_level_when_lit:
dim | normal | bright

fuel_type:
none | oil | tallow | wood | coal | magic

smoke_level:
none | low | medium | high

noise_level:
none | low | medium | high

difficulty:
trivial | easy | moderate | hard | extreme
```

每个 registry 条目声明 owner、允许 path、含义和规则影响。不同 path 不得因为都叫 `quality` 而共用不相容的值域。

`components.light_profile` P1 必填：

```text
lit: boolean
light_level_when_lit: dim | normal | bright
light_radius_band: self | near | room | far
heat_output_tenth_c: integer [0,100]
fuel_type
fuel_remaining_minutes: nullable integer [0,1000000]
smoke
```

`lit=true` 且 `fuel_type` 不是 `none/magic` 时，`fuel_remaining_minutes` 必须大于 0。`lit=false` 时光照和热输出均不进入 EnvironmentDeriver。

`light_radius_band` 的空间覆盖：

| light_radius_band | Site 内 | WorldChunk 外部空间 |
| --- | --- | --- |
| self | 仅当光源由位于目标 scope 的 Actor 携带时覆盖 | 仅当光源由位于目标 chunk 的 Actor 携带时覆盖 |
| near | 与光源最终 placement 相同的 Zone | 与光源最终 placement 相同的 chunk |
| room | 与光源最终 placement 相同的 LocationNode | 与 near 相同 |
| far | 与光源最终 placement 相同的 Site | 源 chunk 和正交相邻 chunk |

对象被容器或其他对象承载时，先沿 placement/containment 链解析最终空间
锚点。任一祖先容器满足：

```text
components.container.light_transmission=opaque
and state.opened is absent or state.opened=false
```

时，内部光源不覆盖任何外部 scope。`transparent` 容器不阻挡光；opaque
且 `state.opened=true` 的容器允许光通过。链无法解析或对象处于
`visibility=removed` 时也不覆盖任何 scope。

每个 affordance 必须在 `ActionRoleRequirementRegistry` 中有至少一个完整角色规则和唯一 resolver。

没有角色规则的 affordance 不能进入 catalog。

P1 ActionRoleRequirement：

| action | role | static requirement |
| --- | --- | --- |
| observe | target | 任意 visibility!=removed 的实体 |
| take | target | WorldObject.physical.portable=true |
| equip | target | components.weapon_stats、components.armor_stats 或 components.tool_profile |
| unequip | target | state.equipped_by 非 null |
| attack | tool | components.weapon_stats |
| open | target | components.container、components.portal_profile 或 components.mechanism_profile，且 state.opened 存在 |
| close | target | 与 open 相同 |
| lock | target | components.mechanism_profile 或 physical.traits 含 lockable，且 state.locked 存在 |
| lock | tool | components.key_profile 或 components.tool_profile.tool_kind=lockpick |
| unlock | target | components.mechanism_profile 或 components.portal_profile，且 state.locked=true |
| unlock | tool | 匹配 components.key_profile 或 components.tool_profile.tool_kind=lockpick |
| search | target | components.container/clue_profile/document_profile/art_profile/trap_profile 之一存在，或 visibility=hidden |
| read | target | components.document_profile |
| track | target | components.clue_profile、CreatureGroup 或 CreatureActor |
| repair | target | physical.condition in damaged/broken 或 components.mechanism_profile.operable=false |
| repair | tool | components.tool_profile.tool_kind=repair |
| break | target | physical.traits 含 breakable/brittle，或 physical.condition!=ruined |
| move | target | physical.portable=true、components.furniture_profile.movable_by_player=true 或 components.vehicle_profile.mobility_state=movable |
| push | target | 与 move 相同 |
| pull | target | 与 move 相同 |
| use | target | components.tool_profile/consumable/water_profile/furniture_profile/fixture_profile/portal_profile/document_profile/key_profile/trap_profile/mechanism_profile/vehicle_profile/light_profile 之一存在 |
| gather | source | FloraPatch、ResourceDeposit、ResourceNode 或 components.resource_profile |
| drink | source | components.consumable.consume_action=drink、components.water_profile，或 components.container.quantity_contents 含可饮液体 |
| eat | source | components.consumable.consume_action=eat |
| refill_water | source | NaturalResource.category=water 的 ResourceNode，或 components.water_profile |
| refill_water | target | components.container.capacity.liquid_liters>"0.000" |
| pour | source | components.container.quantity_contents 含 liquid unit 且 amount>"0.000" |
| pour | target | components.container、ResourceNode、LocationNode 或 Zone |
| trade | target | trade_profile 存在 |
| purchase | target | ownership.legal_status=for_sale 且 trade_profile 存在 |
| hide_behind | cover | physical.traits 含 blocks_sight，或 components.furniture_profile.cover_value>none |
| avoid | target | HazardSource、ObstacleSource 或产生二者的对象 |
| disarm | target | components.trap_profile 或 components.mechanism_profile |
| disarm | tool | components.tool_profile.tool_kind in repair/lockpick |
| trigger | target | components.trap_profile 或 components.mechanism_profile |
| enter | target | components.portal_profile 或 components.vehicle_profile |
| leave | target | components.portal_profile 或当前所在 components.vehicle_profile |

P1 action resolver：

| action | resolver_id |
| --- | --- |
| observe | discovery.observe.v1 |
| take | object.take.v1 |
| equip | equipment.equip.v1 |
| unequip | equipment.unequip.v1 |
| attack | combat.attack.v1 |
| open | object.open.v1 |
| close | object.close.v1 |
| lock | object.lock.v1 |
| unlock | object.unlock.v1 |
| search | discovery.search.v1 |
| read | knowledge.read.v1 |
| track | ecology.track.v1 |
| repair | object.repair.v1 |
| break | object.break.v1 |
| move | object.move.v1 |
| push | object.push.v1 |
| pull | object.pull.v1 |
| use | object.use.v1 |
| gather | ecology.gather.v1 |
| drink | consumable.drink.v1 |
| eat | consumable.eat.v1 |
| refill_water | quantity.refill_water.v1 |
| pour | quantity.pour.v1 |
| trade | trade.exchange.v1 |
| purchase | trade.purchase.v1 |
| hide_behind | space.cover.v1 |
| avoid | hazard.avoid.v1 |
| disarm | mechanism.disarm.v1 |
| trigger | mechanism.trigger.v1 |
| enter | space.enter.v1 |
| leave | space.leave.v1 |

每个 action ID 在 registry 中恰好出现一次 resolver_id；一个 resolver 可以实现多个 action，但不能让同一 action 按运行时对象类型选择不同 resolver。

每个 action 的运行时 resolver 继续检查位置、可见性、数量、状态、权限和并发 revision。上表只决定对象能否静态声明该 affordance。

### 18.3 交易

带 `trade` affordance 的 catalog 条目必须声明：

```text
trade_profile.base_price.currency
trade_profile.base_price.amount
trade_profile.price_category
```

`trade_profile` 是 WorldObject 顶层结构，不属于 `components` 白名单。
`affordances` 含 `trade` 或 `purchase`，或
`ownership.legal_status=for_sale` 时它必填；其他对象可省略。

P1：

```text
base_price.currency: copper | silver | gold
base_price.amount: positive integer，单位是对应 currency 的最小整枚货币

1 silver = 10 copper
1 gold = 10 silver = 100 copper
```

价格 modifier 先把金额换算为 copper 整数，完成全部 basis-points 运算并向上
取整；支付 resolver 可以再按 `gold, silver, copper` 顺序找零。无法精确找零
时保留 copper 金额，不允许四舍五入减少应付金额。

`price_category` 闭集：

```text
food
lodging
water
repair
general
```

最终价格从 Settlement EconomyState 的同名 `price_level.<price_category>` 读取；不允许根据 object name、tag 或本地化文本猜测类别。

成交价：

```text
catalog base price
+ Settlement Economy profile modifier
+ LawPolicy registered modifier
```

实际使用乘法 basis points：

```text
price_level:
cheap=7500
normal=10000
expensive=12500
scarce=15000
unavailable=reject

social/policy modifier:
discount_minor=9000
discount_major=7500
markup_minor=11000
markup_major=12500
refuse_service=reject
require_barter=non_currency_resolution

final_amount =
ceil_nonnegative(
  ceil_nonnegative(base_amount * price_level_bp / 10000)
  * social_or_policy_bp
  / 10000
)
```

没有 social/policy modifier 命中时，`social_or_policy_bp=10000`。命中
`refuse_service` 或 `unavailable` 时直接拒绝，不进入数值公式；
`require_barter` 转交非货币结算 resolver，也不把字符串当作 basis points。

同一交易最多应用一个 price level 和一个 social/policy modifier；多个 policy modifier 同时命中时按 `LawPolicy.severity DESC, policy_id ASC` 取第一条，不能叠乘。

LawPolicy effect 到交易 modifier：

```text
price_markup_allowed -> markup_minor
trade_access_restricted -> refuse_service，仅 service_type=trade 或 purchase
其他 effect -> 不产生价格 modifier
```

severity rank：

```text
none=0
light=1
normal=2
strict=3
emergency=4
```

### 18.4 物化

```text
没有显式数量时 quantity=1。
容器初始内容只能来自场景实例。
不允许随机填充隐藏对象。
```

state 默认与 required_when：

```text
durability:
  所有带 physical.condition 的对象必填
  intact="1.000"
  worn="0.750"
  damaged="0.500"
  broken="0.250"
  ruined="0.000"

opened:
  container/portal_profile/mechanism_profile 且可开合时必填
  复制 scene instance initial_opened，缺省 false

locked:
  mechanism_profile 或 lockable trait 时必填
  复制 scene instance initial_locked，缺省 false

equipped_by:
  weapon_stats/armor_stats/tool_profile 时必填，初始 null

charges:
  catalog 声明 charge_capacity 时必填
  复制 initial_charges，且 0 <= initial_charges <= charge_capacity
```

不满足 required_when 的 state 字段必须省略，不能用 null 或 0 伪装成适用。

派生重量和容量由 WeightDeriver 与 ContainerOccupancyDeriver 在同一原子提交中计算。

容器使用：

```text
capacity.liquid_liters
capacity.mass_kg
capacity.slot_count
light_transmission
quantity_contents
contained_object_ids
```

`components.container.light_transmission` 必填，闭集为
`opaque/transparent`。现有 container catalog 的 category default 固定为
`opaque`；只有 catalog entry 或 scene instance 在该闭集内显式覆写时才允许
`transparent`，不能从 name、description 或 tag 猜测。

每个可进入 `quantity_contents` 的 NaturalResource 必须声明：

```text
mass_per_unit_kg: 三位定点正数字符串
```

`unit=kg` 固定为 `"1.000"` kg/kg；water 为 `"1.000"` kg/liter；其他 liter/count/bundle 资源必须由 catalog 显式声明，缺失时物化拒绝。

ObjectSlotRule：

```text
tiny=1
small=1
medium=2
large=4
huge=8
structure=forbidden_in_container
```

对 containment DAG 按子节点优先、object_id ASC 的拓扑序计算：

```text
quantity_mass_milli =
sum(
  floor(
    quantity.amount_milli
    * NaturalResource.mass_per_unit_kg_milli
    / 1000
  )
)

contained_mass_milli =
quantity_mass_milli
+ sum(child.derived.total_weight_kg_milli)

total_weight_milli =
physical.tare_weight_kg_milli
+ contained_mass_milli

occupied_liquid_liters_milli =
sum(quantity.amount_milli where quantity.unit=liter)

occupied_slot_count =
sum(ObjectSlotRule.slot_cost(child.physical.size))
```

每个 child object ID 最多出现在一个父容器的
`contained_object_ids` 中；出现一次时 child 的
`placement.kind` 必须是 `contained_by_parent`，未出现时不得使用该 kind。
父容器由全局反向索引唯一解析，不在 child 上重复存父 ID。

所有结果序列化为三位定点字符串。包含图有环、一个 child 有多个父容器、
placement 与反向索引不一致、引用缺失、或任一 occupancy 超过对应
capacity 时，整个物化批次 `validation_error`。

WriteACL 只允许 WeightDeriver 写：

```text
derived.total_weight_kg
derived.contained_mass_kg
```

只允许 ContainerOccupancyDeriver 写：

```text
derived.occupied_liquid_liters
derived.occupied_slot_count
```

ContainmentTransferResolver 和 QuantityTransferResolver 只能修改权威内容字段并在同一 atomic batch 调用两个 deriver；它们不能直接写 `derived.*`。

## 19. 日历和时间

P1 `CalendarProfile`：

```text
minutes_per_day = 1440
days_per_year = 360
seasons = [spring, summer, autumn, winter]
days_per_season = 90
```

旧值：

```text
early_spring
late_spring
early_summer
late_summer
early_autumn
late_autumn
early_winter
late_winter
```

标记为 `migration_only`。`abnormal_season` 标记为 `runtime_transition`，只能由已注册异常季节 resolver 通过事件写入；WorldRuntimeInitialization 和普通 TimeAdvanceResolver 不得产生。

权威派生：

```text
day_index = floor(absolute_minute / 1440)
minute_of_day = absolute_minute % 1440
year = floor(day_index / 360) + 1
day = day_index + 1
day_of_year = day_index % 360
season_index = floor(day_of_year / 90)
season_day = day_of_year % 90 + 1
season =
  [spring, summer, autumn, winter][season_index]
```

输入中的 year、day、season 和 season_day 必须等于派生值。

每个季节的 daylight profile 使用半开区间，完整覆盖 `[0,1440)`，且不重叠。

P1 profile：

| season | midnight | night before dawn | dawn | day | dusk | night after dusk |
| --- | --- | --- | --- | --- | --- | --- |
| spring | [0,240) | [240,300) | [300,420) | [420,1080) | [1080,1200) | [1200,1440) |
| summer | [0,180) | [180,240) | [240,360) | [360,1140) | [1140,1260) | [1260,1440) |
| autumn | [0,270) | [270,330) | [330,450) | [450,1050) | [1050,1170) | [1170,1440) |
| winter | [0,360) | [360,420) | [420,540) | [540,960) | [960,1080) | [1080,1440) |

season 到 profile ID：

```text
spring -> spring_standard_day
summer -> summer_long_day
autumn -> autumn_standard_day
winter -> winter_short_day
```

`initial_time.seasonal_daylight_profile` 必须等于上表派生值。

`calendar_label` 是展示字段，固定派生为：

```text
"Y" + zero_pad(year, 4) + "-D" + zero_pad(day, 4)
```

它不参与 hash 以外的规则判断；若作为权威快照字段保存，重放时必须能按公式重算。

`time_band` 闭集增加 `midnight`，最终为：

```text
midnight | night | dawn | day | dusk
```

天气温度的 `midnight` 修正为 `-5` 摄氏度；此前定义的 night 修正仍为 `-4`。

## 20. EnvironmentDeriver

每个目标 scope：

```text
light rank:
pitch_dark=0
dark=1
dim=2
dusk=3
normal=4
bright=5

time-band base light:
midnight=pitch_dark
night=dark
dawn=dusk
day=bright
dusk=dusk

weather light reduction steps:
clear=0
cloudy=1
fog=1
light_rain=1
heavy_rain=2
snow=1
strong_wind=0
storm=2
abnormal_mist=special_abnormal

outdoor natural_light =
step_down(time_band_base_light, weather_reduction)

indoor natural_light =
min(outdoor_natural_light, LocationNode.environment.light)

final_light =
max(natural_light, active light source ranks)

ambient_c =
WeatherState.temperature_c
+ location static temperature offset
+ capped active heat source offsets

visibility_modifier =
weather visibility modifier
+ light level modifier

ground_effects =
weather effects union active residual effects
```

`step_down` 只接受整数 reduction，并在 pitch_dark 截断。

`abnormal_mist` 使用独立分支：

```text
internal_natural_light_level = abnormal
final_light = abnormal
```

active light source 仍记录在 `derived_from.light_source_object_ids`，但不能把 abnormal 改写成普通 rank。

内部自然光等级到 `EnvironmentState.light.natural_light`：

| internal level | natural_light |
| --- | --- |
| pitch_dark | none |
| dark,dim | low |
| dusk,normal | medium |
| bright | high |
| abnormal | abnormal |

`EnvironmentState.light.light_level` 写 final_light；`EnvironmentState.light.natural_light` 只写上表的五值闭集。

`LocationNode.environment.light` 是静态自然光上限，闭集为 `dark/dim/dusk/normal/bright`；缺省时，outdoor 为 bright，indoor 为 dim。

`LocationNode.environment.temperature_offset_tenth_c` 新增为静态字段，范围 `[-100,100]`，缺省 0。

active light source 的 rank 取 `light_level_when_lit`。只考虑作用半径覆盖目标 scope、`lit=true` 且燃料有效的对象。

heat source 修正：

```text
heat_offset_tenth_c =
min(
  100,
  sum(active light sources heat_output_tenth_c)
)
```

EnvironmentState.temperature.ambient_c 使用 one-decimal 定点字符串；WeatherState.temperature_c 先转换为 tenth-celsius 再参与加法。

temperature band：

| ambient tenth-celsius | band |
| ---: | --- |
| <= 0 | freezing |
| 1..100 | cold |
| 101..170 | cool |
| 171..220 | mild |
| 221..270 | warm |
| 271..349 | hot |
| >= 350 | extreme |

`abnormal` 只允许显式异常温度规则写入，不能由普通数值区间自动产生。

光照可见度修正：

```text
bright=1
normal=0
dusk=-1
dim=-1
dark=-2
pitch_dark=-4
abnormal=-3
```

`requires_light_source=true` 当且仅当 final_light 为 dark 或 pitch_dark。

集合按 registry 顺序排序。visibility_modifier 的加法结果 clamp 到 `[-10,10]`。

P1 target scope 集合：

```text
全部 Region
全部 WorldChunk
全部 Site
全部 LocationNode
全部 Zone
```

Site 使用 parent chunk 的天气/地形输入，并使用其第一条 entry node 的静态环境 profile；LocationNode 使用自身 profile；Zone 继承父 LocationNode profile。

target 按 EnvironmentScopeRegistry order、target ID ASC 处理。每个 target 恰好产生一条 EnvironmentState；整个 EnvironmentDeriver 阶段只产生一个 world scope GeneratorOutputEnvelope。

EnvironmentState ID：

```text
stable_id(
  "environment",
  [
    world_id,
    target_scope_kind,
    target_scope_id,
    current_absolute_minute,
    weather_state_id,
    schema_version
  ]
)
```

有效期：

```text
start = current absolute minute
end = min(
  weather end,
  current time-band end,
  每个覆盖该 target 的 active light source fuel end,
  每个作用于该 target 的 active residual end
)
```

Region target 不接受局部 WorldObject 光源覆盖；其 active light source 集合固定为空。
不存在覆盖目标的 active fuel 或 residual 时，对应集合不参加 min。weather end
和 current time-band end 必须始终存在且大于 start；否则产生
`validation_error`，不能创建无限有效环境状态。

## 21. Hazard 和 Obstacle

每个产生规则必须引用完整 profile：

```text
source_kind
hazard_type or obstacle_type
severity
visibility
trigger actions/conditions
effects
mitigations or bypass options
passability override
priority
deactivation predicate
```

P1 hazard type profile：

| hazard type | severity | visibility | trigger actions | effects | mitigations |
| --- | --- | --- | --- | --- | --- |
| fall_risk | medium | hinted | travel,move,climb | injury_risk,time_loss | careful_movement,use_rope,alternate_route |
| collapse_risk | high | hinted | enter,move,break | injury_risk,item_damage,time_loss | reinforce,avoid,alternate_route |
| poison_water | medium | hinted | drink,refill_water | poison_risk | filter_water,boil_water,avoid |
| poison_risk | medium | hidden | eat,drink,use,gather | poison_risk | identify,protective_gear,avoid |
| toxic_plant | low | hinted | gather,search | poison_risk | protective_gear,avoid |
| cold_exposure | medium | visible | travel,rest | exposure_risk,time_loss | shelter,heat_source,protective_gear |
| heat_exposure | medium | visible | travel,rest | exposure_risk,time_loss | shelter,water_access,avoid |
| fire_risk | high | visible | enter,use,move | injury_risk,item_damage | extinguish,avoid |
| trap_risk | high | hidden | move,open,trigger | injury_risk,item_damage | observe,disarm,avoid |
| drowning_risk | high | visible | travel,swim | injury_risk,time_loss | registered_crossing_method,avoid |
| infection_risk | medium | hidden | eat,drink,gather | infection_risk | filter_water,protective_gear,avoid |
| low_visibility_risk | low | visible | travel,search | navigation_risk,time_loss | light_source,guide_route,wait |

P1 effect type：

```text
injury_risk
poison_risk
infection_risk
exposure_risk
navigation_risk
time_loss
item_damage
```

`trigger actions` 来自统一 `HazardTriggerActionRegistry`，它覆盖世界移动操作和 WorldObject affordance；其中 `travel/climb/swim/rest` 是运行时行动 ID，不要求出现在 WorldObject.affordances。

`effects[].magnitude` 使用 `low/medium/high/lethal`。默认等于 hazard severity；`time_loss` 和 `navigation_risk` 最大为 high。

每个 effect 的 canonical reason：

```text
"hazard." + hazard_type + "." + effect_type
```

该 reason code 写入 `effects[].reason`；本地化文本只用于投影。

MitigationProfileRegistry：

| method | time_multiplier | risk_delta |
| --- | ---: | ---: |
| careful_movement | "1.500" | -1 |
| use_rope | "1.250" | -2 |
| alternate_route | "2.000" | -3 |
| reinforce | "2.000" | -3 |
| avoid | "1.000" | -4 |
| filter_water | "1.000" | -3 |
| boil_water | "1.500" | -3 |
| identify | "1.250" | -2 |
| protective_gear | "1.000" | -2 |
| shelter | "1.000" | -3 |
| heat_source | "1.000" | -2 |
| water_access | "1.000" | -2 |
| extinguish | "1.500" | -3 |
| observe | "1.250" | -1 |
| disarm | "1.500" | -3 |
| registered_crossing_method | "1.500" | -3 |
| light_source | "1.000" | -2 |
| guide_route | "1.250" | -2 |
| wait | "1.000" | -3 |

`time_multiplier` 使用三位定点字符串。每个 hazard profile 按其 mitigations 列表查表生成完整对象，不允许只写 method。

P1 obstacle type profile：

| obstacle type | visibility | blocks | passability state | time delta | condition/bypass |
| --- | --- | --- | --- | ---: | --- |
| cliff | visible | travel,enter | blocked | null | climb_route 或 alternate_route |
| blocked_path | visible | travel | blocked | null | clear_path 或 alternate_route |
| locked_door | visible | enter,open | conditional | 0 | matching_key、lockpick 或 force_open |
| collapsed_wall | visible | travel,enter | blocked | null | clear_path、repair 或 alternate_route |
| fallen_tree | visible | travel | difficult | 20 | cut、move 或 alternate_route |
| deep_mud | visible | travel | difficult | 15 | prepared_path 或 alternate_route |
| fast_water | visible | travel | conditional | 20 | registered_crossing_method |
| sealed_container | visible | open,search | null | null | unlock、break 或 matching_key |
| jammed_mechanism | hinted | use,open | null | null | repair 或 force_open |
| heavy_object | visible | move,travel | blocked | null | sufficient_capacity、disassemble 或 alternate_route |

ObstacleSource 新增必填 `visibility: ObjectiveVisibilityState`；它与 HazardSource.visibility 使用同一实体级标量闭集。

BypassOptionProfileRegistry：

| bypass ID | action | requires | extra_time_minutes |
| --- | --- | --- | ---: |
| climb_route | climb | climb_capability | 30 |
| alternate_route | travel | alternate_route_exists | 30 |
| clear_path | clear_path | path_clearance_tool | 20 |
| matching_key | unlock | matching_key | 1 |
| lockpick | unlock | tool_kind:lockpick | 10 |
| force_open | break | force_capability | 10 |
| repair | repair | tool_kind:repair | 30 |
| cut | break | tool_kind:cut | 20 |
| move | move | sufficient_capacity | 10 |
| prepared_path | travel | prepared_path | 10 |
| registered_crossing_method | travel | registered_crossing_method | 20 |
| unlock | unlock | can_unlock | 5 |
| break | break | damage_capability | 10 |
| sufficient_capacity | move | sufficient_capacity | 10 |
| disassemble | break | tool_kind:repair | 30 |

表中的 requires 是单元素 predicate ID 数组。每个 obstacle profile 的 bypass 列逐项查表；`target_edge_id` 在 P1 初始化中固定为 null，由动作 resolver 根据当前 obstacle.location 和 route graph 求解，不能由 deriver 猜测替代边。

conditional passability 使用一个聚合 predicate：

```text
locked_door -> can_open_locked_door
fast_water -> registered_crossing_method
```

`passability_override.conditions` 固定为对应单元素数组。blocked_reason 使用：

```text
"obstacle." + obstacle_type + ".blocks_passage"
```

`passability_override` 在且仅在 obstacle 绑定至少一个 edge 时必填；sealed container 和不占路的 jammed mechanism 使用 null。绑定 edge 的 blocked/conditional/difficult profile 必须按上表产生完整 override。

P1 ready 产生规则只包括：

| rule_id | exact eligibility | source/location | output profile |
| --- | --- | --- | --- |
| terrain.steep_slope_to_fall_risk | chunk.slope=steep，且 edge 以该 chunk 为 source | source=[chunk,edge]；location=chunk_edge(edge.id) | fall_risk |
| terrain.cliff_to_fall_risk | chunk.landform=cliff，且 edge 以该 chunk 为 source | source=[chunk,edge]；location=chunk_edge(edge.id) | fall_risk |
| terrain.ruin_or_cave_to_collapse_risk | chunk.landform in ruin/cave | source=[chunk]；location=chunk(chunk.id) | collapse_risk |
| environment.low_temperature | EnvironmentState ambient tenth-celsius <= 0 | source=[EnvironmentState]；location=EnvironmentState.scope | cold_exposure |
| environment.high_temperature | EnvironmentState ambient tenth-celsius >= 350 | source=[EnvironmentState]；location=EnvironmentState.scope | heat_exposure |
| environment.low_visibility | final light in dark/pitch_dark 或 weather in fog/storm/abnormal_mist | source=[EnvironmentState,WeatherState]；location=EnvironmentState.scope | low_visibility_risk |
| water.polluted_water | ResourceNode water quality in polluted/stagnant | source=[ResourceNode]；location=ResourceNode.location | poison_water |
| terrain.cliff_to_obstacle | edge.base_passability.state=blocked 且 blocked_reason=cliff | source=[source chunk,edge]；location=chunk_edge(edge.id) | cliff |
| terrain.impassable_to_blocked_path | source chunk.slope=impassable | source=[source chunk,edge]；location=chunk_edge(edge.id) | blocked_path |
| object.locked_portal | portal WorldObject.state.locked=true，且 edge.portal_object_id=object.id | source=[WorldObject,edge]；location=edge ref | locked_door |
| environment.deep_mud | EnvironmentState.ground_effects 含 deep_mud 或 muddy，且 edge source scope 被该 EnvironmentState 覆盖 | source=[EnvironmentState,edge]；location=edge ref | deep_mud |

同一 source chunk 的 edge 按 edge_id 升序枚举。表外产生规则在 P1 中保持 `contract_only`，即使 hazard/obstacle type 已有 profile，也不能自动产生实例。

所有 profile 的 `priority` 等于 passability 严重度 rank：

```text
blocked=300
conditional=200
difficult=100
open=0
```

同 rank 的原因继续按 source kind、type 和 ID 排序。

实例 ID：

```text
stable_id(
  "hazard",
  [world_id, rule_id, canonical location, sorted source_entity_ids, schema_version]
)

stable_id(
  "obstacle",
  [world_id, rule_id, canonical location, sorted source_entity_ids, schema_version]
)
```

同一 profile 和来源集合只能存在一个 active 实例。

条件消失时执行 deactivate，不直接删除。

PassabilityReducer 只从 base traversal 和当前 active overrides 重算。

每个规则的 `deactivation_predicate` 固定为 eligibility predicate 的逻辑否定；需要额外状态的 trap、mechanism 和 resource 规则再与 `state.active/depleted/armed` 条件合取。文档不得用“情况改善时关闭”作为机器规则。

## 22. 环境残留

P1 rule ID：

```text
environment_residual.light_rain_decay.v1
environment_residual.heavy_rain_decay.v1
environment_residual.storm_decay.v1
environment_residual.snow_melt_decay.v1
environment_residual.spill_water_expire.v1
environment_residual.fire_decay.v1
environment_residual.abnormal_expire.v1
```

P1 支持：

```text
step_down
expire_at_end
```

`linear` 标记为 `reserved`，不能进入 P1 状态。

残留 profile：

| source/effect | initial intensity | total minutes | mode | step minutes |
| --- | --- | ---: | --- | ---: |
| light_rain -> wet/slippery | moderate | 90 | step_down | 30 |
| heavy_rain -> wet/muddy/slippery | heavy | 240 | step_down | 60 |
| storm -> wet/muddy/fast_water/slippery | heavy | 120 | step_down | 30 |
| snow -> snow_covered/slippery | heavy | 240 after melt starts | step_down | 60 |
| spill_water -> wet/slippery | light | 30 | expire_at_end | 30 |
| fire -> smoke_haze/heat_residue | moderate | 90 | step_down | 30 |
| abnormal source -> abnormal_residue | abnormal | 120 | expire_at_end | 120 |

强度下降序列：

```text
severe -> heavy -> moderate -> light -> trace -> expired
abnormal -> expired
```

每个 `effect_type` 创建一条独立 EnvironmentResidualEffectState；例如 heavy_rain 创建 wet、muddy、slippery 三条状态，不能把多个 effect 塞入单值 `effect_type`。

step_down 的 `total_minutes` 必须恰好等于从 initial intensity 到 expired 前的非 expired 强度数量乘以 step_minutes：

```text
moderate: 3 * step
heavy: 4 * step
```

expire_at_end 在整个有效期内保持 initial intensity，到 end 直接进入 expired。

实例 ID：

```text
stable_id(
  "environment_residual",
  [
    world_id,
    decay_rule_id,
    source.source_entity_id,
    source.source_effect,
    effect_type,
    canonical scope,
    initial_start_world_minute,
    schema_version
  ]
)
```

snow 结束后若 `ambient_c<=0`，残留区间只延长到下一个 EnvironmentState 边界且强度不变；每个边界重新验证。首次出现 `ambient_c>0` 时记录 `decay.started_at_world_minute` 并开始固定 240 分钟融化。该字段在非 snow melt profile 中必须为 null。

每次降级、区间延长和过期都更新同一 residual ID，并形成 StateTransition。

active residual、environment、hazard 和 obstacle ID 索引由 reducer 在同一事务中重算并按 ID 排序。

## 23. 知识模型

### 23.1 claim

KnowledgeState 增加：

```text
claim.kind: existence | field_assertion | event_occurrence
claim.target_ref
claim.field_path
claim.operator: exists | equals
claim.asserted_value
claim.value_hash
```

`asserted_value` 必须通过目标字段 FieldSpec，但不写入世界事实。

错误知识使用合法但与权威事实不相等的值，并通过 accuracy 表达。

`target.kind` 增加：

```text
region
world_chunk
zone
chunk_edge
location_edge
site_boundary_edge
```

`withholding_reason` 无原因时使用字符串 `none`，拒绝 null。

### 23.2 传播

合并键：

```text
subject.kind
subject.id
claim canonical hash
```

传播置信度：

```text
received_confidence_milli =
floor(
  source_confidence_milli
  * source_kind_transfer_basis_points
  / 10000
)
```

`source_kind_transfer_basis_points`：

| source.kind | basis points |
| --- | ---: |
| participant | 10000 |
| witnessed_event | 9500 |
| observed_evidence | 9000 |
| official_record | 10000 |
| read_document | 8500 |
| overheard_event | 7000 |
| heard_from_npc | 7500 |
| heard_from_group | 6500 |
| rumor | 5000 |
| ai_proposal_resolved | 8000 |
| system_initial_knowledge | 10000 |

已有知识取更高 confidence。

相同 confidence 时按：

```text
source event sequence DESC
source ID ASC
```

accuracy 复制来源认知，不由传播器改写。

计算结果 clamp 到 `[0,1000]` milli，并序列化为三位小数字符串。

### 23.3 InitialKnowledgeFormation

P1 `InitialKnowledgeFormation` 不使用随机抽样，不自动生成 RumorState 或 SecretState。

输入必须是已经提交的：

```text
player ActorLocation
Region / WorldChunk / Site / LocationNode / Zone
ChunkEdge / LocationEdge / SiteBoundaryEdge
WorldObject
HazardSource / ObstacleSource
EnvironmentState
max_event_sequence boundary
```

初始目标集合按以下规则构造：

1. 玩家位于 world_chunk 时，加入该 WorldChunk 和所属 Region。
2. 玩家位于 site_node 时，加入该 Site、LocationNode 和当前 Zone。
3. 加入 source 等于玩家当前位置且满足对应可见条件的边：
   `ChunkEdge.visibility.line_of_sight_from_source=true`；
   `LocationEdge.visibility.visible_from_source=true`；
   `SiteBoundaryEdge.portal_object_id=null`，或所引用 portal 的 ObjectiveVisibilityState 为 visible。
4. 加入 placement 解析到玩家当前精确 scope、`WorldObject.visibility=visible`，且当前 EnvironmentState 不阻止观察的 WorldObject。
5. 加入 scope 覆盖玩家当前位置、ObjectiveVisibilityState 为 visible 的 HazardSource 和 ObstacleSource。

P1 `InitialKnowledgeFormation` 要求恰好存在一个
`ActorLocation(actor_kind=player, actor_id=player)`；缺失或多于一个时产生
`validation_error`。下文 `subject={kind: player, id: player}` 中第二个
`player` 是该 P1 特例的 canonical 主体 ID，不是从显示名推导的值。

“当前 EnvironmentState 不阻止观察”精确定义为：

```text
EnvironmentState.light.light_level
in [dim, dusk, normal, bright]
```

`pitch_dark`、`dark` 和 `abnormal` 不产生初始自动发现。第 4、5 条都必须
满足该条件；运行时仍可通过 light source、observe 或 search 产生后续发现。

“当前精确 scope”：

```text
world_chunk:
  placement.kind=chunk
  placement.chunk_id=current chunk

site_node:
  placement.kind=zone
  placement.node_id=current node
  placement.zone_id=current zone
```

contained、on_object 或角色携带的对象不因容器外层可见而自动加入；它们必须由运行时 observe/search 规则发现。

目标按：

```text
KnowledgeTargetKindRegistry order
target.id ASC
```

稳定去重。

对每个目标恰好创建一条 DiscoveryState 和一条 KnowledgeState：

```text
discovery_id =
stable_id(
  "discovery",
  [world_id, "player", target.kind, target.id, "initial", schema_version]
)

knowledge_id =
stable_id(
  "knowledge",
  [world_id, "player", target.kind, target.id, "existence", "initial", schema_version]
)
```

DiscoveryState：

```text
subject = {kind: player, id: player}
target = target ref
discovery_level = identified
source_event_id = null
state.active = true
```

`source_event_id` 仅允许 InitialKnowledgeFormation 创建的初始记录为 null；其他创建路径必须引用触发发现的 EventLogEntry。

KnowledgeState：

```text
subject = {kind: player, id: player}
target = target ref
claim.kind = existence
claim.target_ref = target ref
claim.field_path = null
claim.operator = exists
claim.asserted_value = true
claim.value_hash = sha256(canonical_json_utf8(true))
knowledge_level = witnessed
accuracy = true
confidence = "1.000"
source.kind = system_initial_knowledge
source.ref_id = null
visibility.can_tell_player = true
visibility.withholding_reason = none
state.active = true
state.last_updated_sequence = 对应 KnowledgeCreated 的批内预期提交 sequence
```

`source.kind=system_initial_knowledge` 时 `source.ref_id` 必须为 null；其他需要来源实体的 source kind 必须非 null。

每个 DiscoveryState 产生一个 DiscoveryCreated event draft，每个 KnowledgeState 产生一个 KnowledgeCreated event draft。实体和 event drafts 在同一 StateTransitionBatch 中提交。

设阶段输入的 `max_event_sequence boundary=B`，目标按前述稳定顺序编号
`i=0..n-1`。GenerationCommitter 必须使用：

```text
batch.expected_sequence = B

target i:
  DiscoveryCreated group_order = 2*i + 1
  DiscoveryCreated sequence = B + 2*i + 1
  KnowledgeCreated group_order = 2*i + 2
  KnowledgeCreated sequence = B + 2*i + 2
  KnowledgeState.state.last_updated_sequence = B + 2*i + 2
```

每条 event draft 的 `ordered_output_item_ids` 只引用对应的一个 state
create item。提交开始时最新 sequence 不等于 B，或 committer 分配的序号与
上述公式不一致时，整个 batch 必须 CAS 失败；不得改写已经进入
`value_hash` 的 `last_updated_sequence`。

整个阶段使用唯一的 world scope GeneratorOutputEnvelope。细粒度 target 只出现在 item payload 中。

目标集合为空时使用 `emit_empty_candidate_set_with_audit` 的空输出语义，不产生知识事件。

## 24. AI 协议

为当前每个 action type 建立一条完整 `AIActionPolicyEntry`：

```text
spread_rumor
adjust_social_pressure
request_patrol_change
change_group_attitude
offer_service
refuse_service
reveal_known_fact
withhold_known_fact
change_npc_attitude
```

每条 policy 必须填齐：

```text
required targets
argument schema
preconditions
conflict key
resource claim
resolver
partial acceptance
allowed event types
```

P1 policy：

| action | required targets | arguments | resource claim | resolver | partial policy | allowed event |
| --- | --- | --- | --- | --- | --- | --- |
| spread_rumor | knowledge:1, settlement/social_group:1 | intensity_band | none | social_action.spread_rumor.v1 | reject_on_difference | RumorSpreadRequested |
| adjust_social_pressure | pressure_state:1 | pressure_key,direction,intensity_band | none | social_pressure.adjust.v1 | clamp_registered_delta | SocialPressureChanged |
| request_patrol_change | settlement:1 | direction | none | patrol.change.v1 | reject_on_difference | PatrolLevelChanged |
| change_group_attitude | subject social_group:1, actor:1 | target_attitude | none | social_attitude.group_change.v1 | reject_on_difference | SocialAttitudeChanged |
| offer_service | service:1, actor:1 | requested_price_modifier | service_use | social_action.offer_service.v1 | price_modifier_clamp | ServiceOfferCreated |
| refuse_service | service:1, actor:1 | refusal_reason | none | social_action.refuse_service.v1 | reject_on_difference | ServiceRequestRefused |
| reveal_known_fact | knowledge:1, actor:1 | disclosure_style | none | knowledge.disclose.v1 | reject_on_difference | KnowledgeDisclosureResolved |
| withhold_known_fact | knowledge:1, actor:1 | withholding_reason | none | knowledge.withhold.v1 | reject_on_difference | KnowledgeDisclosureResolved |
| change_npc_attitude | subject named_npc:1, actor:1 | target_attitude | none | social_attitude.npc_change.v1 | reject_on_difference | SocialAttitudeChanged |

argument domain：

```text
intensity_band = low | medium | high
direction = increase | decrease
pressure_key = SocialPressureState.pressure 的七键闭集
target_attitude =
  SocialGroupState.attitude_to_player 或 NamedNPCState.attitude_to_player 的闭集
requested_price_modifier =
  discount_major | discount_minor | none | markup_minor | markup_major
refusal_reason =
  closed | sold_out | not_eligible | unsafe | policy_restricted | provider_unavailable
disclosure_style = direct | hint | partial
withholding_reason =
  risk_averse | official_secret | personal_secret | hostile_to_player |
  wants_payment | protecting_someone | fear_of_punishment | does_not_trust_player
```

数值映射：

```text
intensity_band milli:
low=100
medium=200
high=300

rumor intensity:
low=250
medium=500
high=750

requested_price_modifier basis points:
discount_major=7500
discount_minor=9000
none=10000
markup_minor=11000
markup_major=12500
```

`adjust_social_pressure` 对指定 key 加减 intensity milli，并 clamp 到 `[0,1000]`。

`price_modifier_clamp` 把 requested price modifier clamp 到 `[9000,11000]` basis points：discount_major 调整为 discount_minor，markup_major 调整为 markup_minor；其余保持不变。发生 clamp 时结果必须是 `accepted_with_adjustment`。

所有 policy 的基础前置条件依次为：

```text
subject revision matches
observation snapshot sequence matches
targets exist and are visible to subject
target relation matches policy
argument schema passes
decision slot is open
```

再追加 action 专用条件。冲突键：

```text
spread_rumor: decision_tick + claim_hash + scope_id
adjust_social_pressure: decision_tick + pressure_state_id + pressure_key
request_patrol_change: decision_tick + settlement_id
attitude actions: decision_tick + subject_id + actor_id
service actions: decision_tick + service_id + actor_id
knowledge disclosure: decision_tick + claim_hash + actor_id
```

实际 `conflict_key` 是上述字段数组的 canonical JSON SHA-256，不使用字符串直接拼接。

action 专用条件：

| action | additional precondition |
| --- | --- |
| spread_rumor | KnowledgeState.subject 等于 proposal subject，且 can_tell_player=true 或传播目标不是 player；目标 settlement/group 必须等于 subject 所属 settlement/group |
| adjust_social_pressure | pressure_key 已存在，且 pressure_state.settlement_id 等于 proposal subject 所属 settlement_id |
| request_patrol_change | settlement_id 等于 proposal subject 所属 settlement_id，且 direction 后仍落在 none/low/normal/high/lockdown 的相邻一级 |
| change_group_attitude | proposal subject.kind=social_group，且 target social_group.id 等于 proposal subject.id |
| offer_service | ServiceState active 且 availability 为 available/limited，provider 与 subject 相同 |
| refuse_service | provider 与 subject 相同，且 refusal_reason 能由 service、law 或 provider state 证明 |
| reveal_known_fact | KnowledgeState.subject 等于 proposal subject，且 withholding_reason=none |
| withhold_known_fact | KnowledgeState.subject 等于 proposal subject，且 argument withholding_reason 非 none |
| change_npc_attitude | target named_npc 就是 proposal subject |

`request_patrol_change` 每次只移动一级；处于 none 时 decrease、处于 lockdown 时 increase 均为 `precondition_failed`。

attitude action 不做隐式相邻级推断；resolver 必须原样接受 target_attitude 或整条拒绝。

只有 `offer_service` 可以创建 reservation：

```text
reservation_key =
sha256(canonical_json_utf8([
  service_id,
  actor_id,
  decision_tick_id
]))

quantity = ServiceProfile.reservation_quantity
created_at_world_minute = current absolute minute
valid_until_world_minute =
  created_at_world_minute
  + ServiceProfile.reservation_duration_minutes
```

limited ServiceState 的 `remaining_uses < reservation_quantity` 时 offer_service 失败。reservation 到期、proposal rejected 或 resolver 失败时必须释放；服务成功提交时原子消费。

时间字段统一：

```text
created_at_world_minute
valid_until_world_minute
```

该规则适用于 `GroupDecisionProposal`、`NPCActionProposal` 和
`ProposalResourceReservation`，不只适用于 reservation。

`AIDecisionTick` 使用：

```text
scheduled_world_minute =
  创建 tick 时 WorldTimeState.clock.absolute_minute
```

旧 `scheduled_game_time={day,minute_of_day}` 标记为 `migration_only`。
proposal 固定：

```text
created_at_world_minute =
  referenced AIDecisionTick.scheduled_world_minute

valid_until_world_minute =
  created_at_world_minute + 10
```

reservation 的 `valid_until_world_minute` 必须小于等于 proposal 的值，也
必须等于本节 reservation 公式结果。旧 `valid_until_game_time` 及其中的
`day/minute_of_day`、旧 `scheduled_game_time` 标记为 `migration_only`；
P1 新写入必须拒绝。

`accepted_with_adjustment` 必须在同一个 StateTransitionBatch 中进入 `resolved`，不能成为持久悬空状态。

失败原因：

```text
timeout
parse_error
schema_invalid
precondition_failed
conflict_rejected
retry_exhausted
resolver_failed
expired
```

运行时 LLM 天气提议不进入 P1 ready baseline。WeatherResolver 只接受显式合法 condition；非法值直接拒绝。

## 25. EventTypeRegistry

所有文档引用唯一事件类型注册表。

未注册的 `*Event` 名称禁止进入 StateTransition。

旧名称必须：

1. 映射到已有 canonical event type；或
2. 正式加入 registry 并声明 producer、允许实体和 payload 规则。

P1 统一映射：

| old/reference name | canonical event_type |
| --- | --- |
| ObjectMovedEvent | ObjectMoved |
| ObjectStateChangedEvent | ObjectStateChanged |
| ObjectEquippedEvent | ObjectStateChanged |
| ObjectConsumedEvent | ObjectStateChanged |
| ObjectRemovedEvent | ObjectMoved |
| ObjectRevealedEvent | DiscoveryCreated |
| SiteRevealedEvent | DiscoveryCreated |
| CreatureSignDetectedEvent | DiscoveryCreated |
| SearchResolvedEvent | 有新发现时 DiscoveryCreated；无状态变化时不写 EventLog |
| CreatureMovedEvent | CreatureGroupLocationChanged |

`CreatureGroupLocationChanged` 正式加入 EventTypeRegistry，producer 只能是
EcologyMovementResolver，权威 changes 只能修改 `CreatureGroup.location`。
由位置构建的查询索引属于可重建 system index，必须在同一事务中更新，但
不新增 CreaturePopulation 权威字段，也不作为第二个业务 change。

`event_cause_kind` 统一使用：

```text
migration_tool
```

删除同义值 `migration`。

## 26. GeneratorOutputEnvelope 和快照

`execution_scope=world && parallelizable=false` 的阶段只产生一个 world envelope。

InitialKnowledgeFormation 示例必须改为 world scope；细粒度目标由 item payload 表达。

FormationRule 输出类别：

```text
candidate
world_fact
knowledge_fact
event_draft
snapshot_ref
```

SnapshotWriter 使用：

```text
rule_id = snapshot.write_after_generation.v1
algorithm_id = snapshot.canonical_state_projection.v1
```

after_world_generation snapshot 固定 committed boundary：

```text
event_sequence = WorldState.runtime_state.latest_event_sequence
state_hash = WorldStateContentHash(current committed state)
latest_event_hash =
  null, event_sequence=0
  EventLogEntry[event_sequence].event_hash, 其他
reason = after_world_generation
created_at_world_minute = WorldTimeState.clock.absolute_minute
version_lock = current WorldState.version_lock
validation_summary = {valid: true, error_count: 0}
```

WorldFactValidator 或 KnowledgeValidator 未通过时禁止写 snapshot。

snapshot ID：

```text
stable_id(
  "snapshot",
  [
    world_id,
    event_sequence,
    reason,
    state_hash,
    sha256(canonical_json_utf8(version_lock)),
    schema_version
  ]
)
```

`created_at` 增加 `_meta` 前缀并改名为 `_meta.created_at_wall_clock`；`storage.kind/ref` 移到 `_meta.storage`。它们是操作元数据，不进入 snapshot_hash、WorldStateContentHash 或 snapshot ID。

snapshot hash：

```text
canonical_snapshot_without_hash_and_meta =
snapshot canonical payload excluding snapshot_hash and _meta

snapshot_hash =
sha256(canonical_json_utf8([
  "WorldSnapshotHash",
  "isekai-snapshot-hash@1",
  canonical_snapshot_without_hash_and_meta
]))
```

SnapshotWriter 原子写入 snapshot payload、`snapshot_ref` output item 和 `runtime_state.latest_snapshot_id` 恢复索引。失败时三者都不可见。

`target_scope_kind`、`target_scope_kind_rank` 和 `target_scope_id` 是从
`GeneratorOutputItem.value_ref` 所引用的 canonical payload 派生出的计算变量，
不是 `GeneratorOutputItem` 的新增存储字段。

派生函数固定为：

```text
derive_item_target_scope(item):
  payload = resolve_and_validate(item.value_ref, item.value_hash)

  if payload schema declares canonical scope.kind and canonical scope entity ID:
    target_scope_kind = payload.scope.kind
    target_scope_id =
      target_scope_kind + ":" + payload 中该 scope 对应的 canonical entity ID
  else:
    target_scope_kind = none
    target_scope_id = ""

  target_scope_kind_rank =
    TargetScopeKindRankRegistry[target_scope_kind]
```

例如 `EnvironmentState.scope.kind=world_chunk` 且 `chunk_id=chunk_001` 时，
派生结果是：

```text
target_scope_kind = world_chunk
target_scope_kind_rank = 30
target_scope_id = "world_chunk:chunk_001"
```

payload schema 没有 canonical scope 字段时必须返回 `none/0/""`，不能从
`entity_id`、数组遍历位置、随机流 `scope_id` 或实现者猜测中推导。
`GenerationOutputValidator` 必须在计算 `item_id`、检查排序和重算
`output_hash` 前执行该函数。

稳定 ID：

```text
output_id =
"generator_output_" + first_24_lower_hex(sha256(canonical_json_utf8([
  "GeneratorOutputId",
  1,
  generation_run_id,
  stage_contract_id,
  scope.kind,
  scope.id,
  input_hash
])))

item_id =
"item_" + first_24_lower_hex(sha256(canonical_json_utf8([
  output_id,
  bucket_kind,
  target_scope_kind,
  target_scope_id,
  entity_type,
  entity_id,
  candidate_type,
  candidate_id,
  field_path,
  value_hash
])))
```

重试不进入 ID 输入；同一锁定输入的确定性重算必须产生相同 ID。

bucket 顺序固定为：

```text
candidate_outputs
world_fact_outputs
knowledge_outputs
event_drafts
snapshot_refs
```

每个 bucket 内先为每个 item 执行 `derive_item_target_scope`，再按下列元组
升序排序：

```text
(
  target_scope_kind_rank,
  target_scope_id,
  entity_type or "",
  entity_id or "",
  candidate_type or "",
  candidate_id or "",
  field_path,
  item_id
)
```

`input_refs` 使用其协议规定的 canonical 顺序；
`random_draw_refs` 按 `(stream_id, logical_draw_id, draw_index)` 升序。

`output_hash` 精确定义为：

```text
canonical_output_envelope_without_hash = {
  output_id,
  stage_contract_id,
  producer,
  rule_id,
  scope,
  input_refs,
  input_hash,
  random_draw_refs,
  candidate_outputs,
  world_fact_outputs,
  knowledge_outputs,
  event_drafts,
  snapshot_refs
}

output_hash =
sha256(canonical_json_utf8([
  "GeneratorOutputEnvelopeHash",
  1,
  version_context,
  canonical_output_envelope_without_hash
]))
```

上述 bucket 顺序、bucket 内顺序以及每个 item 的 `value_hash` 都属于 hash
协议。`output_hash` 字段自身不得进入计算。

### 26.1 event draft

`event_draft` payload：

```text
draft_id
event_type
occurred_at.absolute_minute
caused_by.kind
caused_by.id
command_id
atomic_commit_group_id
ordered_output_item_ids[]
summary
```

P1 生成阶段的 `summary` 固定等于 `event_type` 的 ASCII registry 值，例如
`KnowledgeCreated`。它是调试展示文本，不作为 resolver 输入；实现可以在
投影层本地化，但不能把本地化文本写回 event draft 或 EventLogEntry。

`ordered_output_item_ids` 只能引用同一 envelope 中将被提交的 `world_fact_outputs` 或 `knowledge_outputs`。GenerationCommitter 按该数组形成 StateTransition.ordered_changes；event draft 不能自带最终 sequence、event ID、event hash 或 resulting state hash。

### 26.2 generation audit

`GenerationAuditRecord`：

```text
generation_run_id
stage_run_id
output_id
item_id nullable
bucket_kind
result_kind
reason_code
validator_rule_ids[]
input_hash
value_hash nullable
output_hash
recorded_at_world_minute
```

`result_kind`：

```text
generated
validated
rejected
skipped
recovered
```

audit 只进入 system ledger，不生成 EventLogEntry。

## 27. 恢复

```text
generation_run_id =
"generation_run_" + first_24_lower_hex(
  sha256(canonical_json_utf8([
    "GenerationRunId",
    1,
    world_id,
    "main",
    generation_plan_id,
    seed_material_hash,
    run_input_hash,
    version_lock
  ]))
)

stage_run_id =
"stage_run_" + first_24_lower_hex(
  sha256(canonical_json_utf8([
    "StageRunId",
    1,
    generation_run_id,
    stage_contract_id,
    scope.kind,
    scope.id
  ]))
)
```

`run_input_hash` 精确定义为：

```text
run_input_hash =
sha256(canonical_json_utf8([
  "GenerationRunInputHash",
  1,
  normalized WorldGenerationParameters,
  enabled content pack refs sorted by
    content_pack_id, content_pack_version, content_pack_hash,
  GenerationStageContract objects sorted by
    stage_index ASC, stage_contract_id ASC
]))
```

stage contracts 必须先通过 DAG validator；`stage_index` 必须与依赖拓扑一致，
同 index 才使用 `stage_contract_id` 作为唯一 tie-break。
`run_input_hash` 不包含任何阶段输出、attempt、checkpoint 或最终
`WorldGenerationManifest.stage_output_ids`。`version_lock` 必须包含
`schema_version`、`registry_hash`、`rule_bundle_hash` 和
`content_pack_hash`。

因此 run ID 在执行任何 stage 前即可确定，不依赖最终 manifest，也不会形成
`run_id -> output_id -> manifest_hash -> run_id` 循环。

`scope` 使用 `GenerationStageContract.execution_scope` 对应的实际执行
分区；world 级单 envelope 阶段固定为
`scope.kind=world, scope.id=World.id`。`FormationRuleContract.target_scope`
不得参与 `stage_run_id` 或 `output_id`。

恢复分类：

- payload 存在但 stored hash 与重算 hash 不一致：`repair_required`。
- payload 缺失、尚未提交且锁定生成器仍可用：允许确定性重算。
- missing checkpoint、checkpoint chain、version、event/hash 冲突：`repair_required`。
- generator crash、临时写失败、允许重算的 missing payload：最多自动重试三次。

repair 类失败不消耗自动重试额度。

完整分类：

| failure code | action |
| --- | --- |
| generator_crash | retry，最多 3 次 |
| io_write_failed | retry，最多 3 次 |
| missing_output_payload | 未提交且版本锁可解析时 retry；否则 repair_required |
| schema_invalid | rejected，不自动重试 |
| validator_rejected | rejected，不自动重试 |
| hash_mismatch | repair_required |
| version_lock_mismatch | repair_required |
| missing_checkpoint | repair_required |
| checkpoint_chain_broken | repair_required |
| output_hash_conflict | repair_required |
| event_log_conflict | repair_required |
| partial_atomic_commit_detected | repair_required |
| state_hash_mismatch | repair_required |
| retry_limit_exceeded | failed |
| manual_abort | failed |

`generated` 状态恢复时，stored output hash 与 payload 重算 hash 不一致一律视为 corruption；即使生成器可以重算，也不能静默覆盖持久输出。

## 28. Catalog 和物化 hash

CatalogEnvelope 必填：

```text
catalog_hash
```

计算：

```text
catalog_hash =
sha256(canonical_json_utf8([
  "CatalogEnvelopeHash",
  1,
  CatalogEnvelope excluding catalog_hash
]))
```

`content_pack_hash` 聚合已经验证的 catalog hash。

```text
content_pack_hash =
sha256(canonical_json_utf8([
  "ContentPackSetHash",
  1,
  catalogs sorted by
    content_pack_id, kind, catalog_version, catalog_hash
]))
```

`materialization_id`：

```text
materialization_context_without_id = [
  world_id,
  target_entity_type,
  content_pack_id,
  content_pack_version,
  catalog_kind,
  catalog_id,
  catalog_version,
  catalog_entry_hash,
  materializer_id,
  materializer_version,
  instance_key,
  target_schema_version,
  registry_hash,
  rule_bundle_hash,
  content_pack_hash
]

materialization_id =
"mat_" + first_24_lower_hex(
  sha256(canonical_json_utf8(materialization_context_without_id))
)
```

运行时实体 ID：

```text
entity_id =
entity_prefix
+ "_"
+ stable_slug(catalog_id)
+ "_"
+ first_16_lower_hex(
  sha256(canonical_json_utf8([
    world_id,
    target_entity_type,
    catalog_kind,
    catalog_id,
    instance_key,
    materializer_id,
    materializer_version
  ]))
)
```

`entity_prefix` 由 `EntityIdPrefixRegistry[target_entity_type]` 唯一确定。
P1 允许的 content materialization 目标和前缀为：

| target_entity_type | entity_prefix |
| --- | --- |
| `WorldObject` | `object` |
| `FloraPatch` | `flora_patch` |
| `CreaturePopulation` | `creature_population` |
| `CreatureGroup` | `creature_group` |
| `NaturalResource` | `natural_resource` |
| `ResourceDeposit` | `resource_deposit` |
| `ResourceNode` | `resource_node` |

未登记的 `target_entity_type` 必须拒绝物化，不能使用类型名小写、类名或
materializer 名称临时生成前缀。新目标类型必须先扩展该 registry、目标
schema、FieldSpec、WriteACL 和对应测试。

P1 `catalog_id` 只允许 ASCII `[a-z0-9._-]+`，并且至少包含一个
`[a-z0-9]`。`stable_slug` 把 `.` 和 `-` 转为 `_`，连续 `_` 合并为一个，
去除首尾 `_`，不做本地化转写。结果为空或与同一物化 namespace 中另一
catalog ID 发生最终 entity ID collision 时，validator 必须拒绝。

字段映射：

```text
default_tags -> WorldObject.tags
default_affordances -> WorldObject.affordances
container_override.light_transmission
  -> WorldObject.components.container.light_transmission
```

unknown catalog path 继续拒绝。

两个现有 catalog 必须迁移到新容器、价格、hash 和 provenance schema。

## 29. 验收和测试

### 29.1 静态完整性

必须验证：

- 每个 schema path 有且只有一个 FieldSpec。
- 每个 enum/registry/reference path 能解析。
- 每个 required 输出字段有赋值来源。
- 每个 ready FormationRule 能解析到 ready NumericAlgorithmSpec。
- 每个 policy ID 能解析到唯一策略。
- 每个 event type 能解析到 EventTypeRegistry。
- 每个 affordance 有 ActionRoleRequirement。
- 每个实际 RandomDrawRef 被唯一 FormationRule.random.random_draws 声明覆盖。
- 每个 content materialization target 能解析到唯一 EntityIdPrefixRegistry 项。
- P1 新写入不存在 `components.portal_profile.open_state/locked`。
- P1 新写入不存在 `WorldChunk.water_presence/WorldChunk.hydrology`。
- P1 新写入不存在 `valid_until_game_time/scheduled_game_time` 或 day/minute 有效期对象。
- 每个 required institution 唯一绑定同 kind Site。

### 29.2 数学性质

必须验证：

- 候选数量不越界。
- 所有排序有最终唯一 tie-break。
- 拒绝采样有界。
- 所有定点计算使用规定舍入。
- 资源和生态数量守恒。
- 时间区间使用半开区间且不重叠。
- 温度分段覆盖全部整数 tenth-celsius 且互不重叠。
- 多个 terrain_bias 的结果与输入数组排列顺序无关。
- Region 边界 ChunkEdge 与单 Region 内边枚举使用同一 world-grid 邻接关系。
- containment 是唯一父节点 DAG，重量和容量由子节点优先拓扑序得到。
- InitialKnowledgeFormation 的批内 sequence 与 last_updated_sequence 一致。
- generation_run_id 不依赖最终 manifest 或任何 stage output。
- GeneratorOutputItem 的 target scope 派生和 bucket 排序可由 payload 重算。
- 状态转移 batch hash 链连续。
- snapshot 能从 EventLog 重放验证。

### 29.3 重放

固定 fixture 至少覆盖：

```text
single region world
multiple region world
empty ecology candidate set
weather fallback
candidate validator rejection
atomic social batch
ruin settlement with one required institution
container quantity transfer
opaque and transparent nested light source
temperature boundary at 34.0, 34.1, 34.9 and 35.0 C
terrain bias permutation
cross-region boundary adjacency
initial knowledge two-event batch sequence
knowledge misinformation
generation crash before output
generation crash after output
same run input with different version lock
checkpoint corruption
snapshot replay
```

每个 fixture 必须断言：

```text
output hash
state hash
event hash sequence
snapshot hash
stable IDs
canonical item and bucket order
failure code or success result
```

### 29.4 文档一致性

所有规范 JSON 示例和两个实际 catalog 必须通过与正式 schema 相同的 validator。

禁止使用“仅为阅读示例”绕过字段类型、闭集、引用和 hash 规则。

## 30. 实施边界

实际修改必须局限于本文确认的缺失部分。

每个 owner 文档只修改其拥有的实体、字段、算法和 validator。

跨文档公共闭集由治理或架构 owner 定义，其他文档只能引用。

不顺手重构无关段落，不修改未确认玩法，不执行 Git reset、历史重写或未授权提交。
