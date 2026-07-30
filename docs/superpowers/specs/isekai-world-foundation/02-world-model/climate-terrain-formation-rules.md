---
doc_id: isekai.climate_terrain_formation_rules
status: active
layer: world-model
owner: architecture
created_at: 2026-07-11
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.location_space_rules
  - isekai.world_generation_manifest_rules
provides:
  - RegionClimateEnvelope
  - RegionClimateCandidate
  - ChunkBaseRawFieldsCandidate
  - ChunkBaseFieldSmoothing
  - ChunkBaseFieldsCandidate
  - TerrainCandidateFormation
  - ChunkTerrainCandidate
  - HydrologyCandidateFormation
  - ChunkHydrologyCandidate
  - LocalClimateCandidateDerivation
  - ChunkLocalClimateCandidate
  - ChunkBiomeCandidateDerivation
  - RegionBiomeCandidateAggregation
  - ChunkBiomeCandidate
  - RegionBiomeCandidate
  - WeatherFormation
---

# 异世界模式气候、地形、生物群系与天气形成规则设计

## 背景

地点/空间规则定义了世界的空间层级，自然生态与资源规则定义了动物、植物和自然资源如何参与世界生成。但生态生成不能凭空匹配标签，必须先有一套规则决定每个 `Region` 和 `WorldChunk` 的气候、地形、水系、生物群系和天气。

本设计定义世界生成时气候、地形、资源、动植物形成的前置规则。它回答：

```text
为什么这个 Region 是寒冷湿润的北坡荒野？
为什么某个 chunk 是山脊、溪谷、湿地或城镇街区？
为什么这里能生成狼、松树、梦魇草、泉眼和铁矿？
为什么相邻 chunk 能不能直接通行？
为什么当前天气会影响搜索、移动、体温和动物活动？
```

## 目标

- 定义气候、地形、生物群系和天气的生成层级。
- 明确 `Region` 负责长期气候包络，`WorldChunk` 负责局部地形事实。
- 明确 `Biome` 是由气候、地形、水源、文明压力和异常标签推导出的生态标签。
- 明确资源、动植物只能在匹配的气候、地形、生物群系条件下生成。
- 明确 `ChunkEdge` 的静态基础通行由地形、坡度和水体决定；天气只能通过运行时环境与 override 影响最终通行。
- 明确 AI 可以提出候选，但形成规则和校验必须由确定性系统执行。

## 非目标

- 不实现 DF 式 tile 级高度图、水流模拟和侵蚀模拟。
- 不生成无限地图；只生成当前世界边界内或被扩展验证通过的 chunk。
- 不让 DM 通过文字直接改变气候、地形、水系或资源分布。
- 不让 `biome_tags` 成为随意手填标签；它必须能追溯到形成输入。
- 不在本阶段定义完整季节系统、灾害系统和气象物理模型。

## 核心原则

### 1. 气候是长期倾向

气候表示一个区域长期像什么地方。它主要属于 `Region`，并可被 `WorldChunk` 做局部修正。

气候影响：

```text
植物候选
动物候选
水源稳定性
天气候选整数权重
体温风险
食物腐败
旅行消耗
道路维护难度
```

### 2. 地形是物理事实

地形表示一个 chunk 物理上怎么走、怎么看、怎么生存。它属于 `WorldChunk`，不能只存在于旁白。

地形影响：

```text
可通行性
移动耗时
视野距离
遮蔽和伏击
迷路风险
水源、矿物、植物、动物的生成条件
site 能否放置
```

### 3. Biome 是推导结果

`Biome` 不应作为任意设定文本，而应由以下输入推导：

```text
气候
地形
水源
植被覆盖
文明压力
危险/异常标签
```

例如：

```text
cold_temperate + wet + forest + slope = cold_slope_forest
wet_temperate + valley + stream = creek_valley
temperate + town_block + civilized = town_settlement
ruin + damp + abnormal = abnormal_damp_ruin
```

### 4. 天气是短期动态状态

天气不是 chunk 的永久属性。天气由 Region 气候和当前时间生成，并在一段时间后变化。

天气影响当前行动：

```text
移动耗时
视野
搜索难度
脚印保留
体温风险
火源使用
声音传播
动物活动
```

### 5. 资源和生态必须由形成条件支持

动物、植物、自然资源不能只因为剧情需要出现。它们必须满足至少一个形成路径：

```text
气候/地形自然支持
文明活动带来
历史事件遗留
异常/魔物污染造成
AI proposal 通过 validator 固化
```

## 生成层级

本文件中的气候和物理形成发生在空间布局候选通过校验之后、权威空间实体物化之前：

```text
WorldGenerationParameters
-> 已验证 World / Region / Grid / Chunk 布局候选
-> RegionClimateCandidateFormation
-> ChunkBaseRawFieldsCandidateFormation
-> [同一 Region 全部 raw fields 完成的阶段屏障]
-> ChunkBaseFieldSmoothing
-> TerrainCandidateFormation
-> HydrologyCandidateFormation
-> LocalClimateCandidateDerivation
-> ChunkBiomeCandidateDerivation
-> RegionBiomeCandidateAggregation
-> SpatialFoundationValidator
-> SpatialFoundationMaterializer
-> Authoritative World / Region / WorldChunkGrid / WorldChunk
-> SettlementAnchorFormation
-> OriginHistoryCandidateFormation
-> StaticChunkEdgeFormation
-> StaticTraversalDeriver
-> ResourceFormation
-> FloraFormation
-> FaunaFormation
-> SitePlacement / LocationGenerator
-> ObjectMaterialization
-> SettlementSocialFormation
-> OriginHistoryMaterialization
-> OriginAttachment
-> WorldRuntimeInitialization
-> WeatherFormation
-> EnvironmentDeriver
-> HazardObstacleDeriver
-> PassabilityReducer
-> WorldFactValidator
-> InitialKnowledgeFormation / KnowledgeValidator
-> after_world_generation Snapshot
-> Authoritative WorldState
```

其中：

```text
RegionClimateEnvelope：Region.climate_profile 的字段结构，不是独立权威实体。
RegionClimateCandidateFormation：为每个 RegionLayoutCandidate 生成长期气候候选。
ChunkBaseRawFieldsCandidateFormation：为每个 WorldChunkLayoutCandidate 独立生成未平滑基础场。
ChunkBaseFieldSmoothing：在 raw fields 全部完成后按稳定邻接顺序生成平滑基础场。
TerrainCandidateFormation：把平滑基础场转换成不含最终水文结论的地形候选。
HydrologyCandidateFormation：按 Region 校验跨 chunk 水流并生成最终 water_presence 候选。
LocalClimateCandidateDerivation：由 Region 气候、地形和水文生成 chunk 局部气候修正。
ChunkBiomeCandidateDerivation：生成 chunk biome_tags 候选。
RegionBiomeCandidateAggregation：从该 Region 全部 chunk biome 稳定聚合 Region.biome_tags 候选。
SpatialFoundationMaterializer：把完整候选合并为 canonical Region 和 WorldChunk。
OriginHistoryCandidateFormation：根据已物化静态空间和压力生成历史候选；候选不是权威 OriginEvent。
ResourceFormation：生成 ResourceDeposit / ResourceNode。
FloraFormation：生成 FloraPatch。
FaunaFormation：生成 CreaturePopulation / CreatureGroup。
OriginHistoryMaterialization：在 Site、WorldObject、Resource、Ecology 和社会证据完成后，把候选物化为权威 OriginEvent。
WorldRuntimeInitialization：在静态世界和历史附着完成后创建 StaticWorldRuntimeState 与 WorldTimeState。
```

## WorldGenerationParameters

世界生成参数决定本次世界的整体倾向。

最小 schema：

```json
{
  "seed": "adv_10_seed",
  "world_profile": "frontier_survival",
  "region_count": 2,
  "spatial_layout": {
    "generation_mode": "procedural",
    "coverage_mode": "complete",
    "default_grid": {
      "width_chunks": 8,
      "height_chunks": 8,
      "min_z": 0,
      "max_z": 0
    },
    "max_chunks_per_region": 256
  },
  "initial_time": {
    "absolute_minute": 0,
    "year": 1,
    "day": 1,
    "season": "spring",
    "season_day": 1,
    "seasonal_daylight_profile": "spring_standard_day"
  },
  "default_history_years": 30,
  "climate_bias": ["cold_temperate", "wet"],
  "terrain_bias": ["hill", "forest", "ridge", "valley"],
  "civilization_density": "low",
  "resource_abundance": "normal",
  "danger_level": "medium",
  "abnormality_level": "low"
}
```

规则：

```text
seed 是 RandomSeedMaterial.world_seed。所有确定性随机必须使用确定性随机协议，不能自行派生本地 seed。
world_profile 决定默认权重，不直接生成事实。
spatial_layout 的字段和边界由地点与空间规则中的 SpatialLayoutParameters 定义；P0 只允许 procedural + complete。
initial_time 是生成输入，不是已提交 WorldTimeState。所有静态生成 event_draft 的 occurred_at 和后续 WorldRuntimeInitialization 必须读取同一份规范化 initial_time；运行时初始化后不得再用参数替代 WorldTimeState。
climate_bias / terrain_bias 只能通过 CandidateSet 的整数权重影响候选，不能绕过 validator。
danger_level / abnormality_level 只能通过标准权重修正影响危险标签和异常生态候选。
```

`initial_time.absolute_minute/year/day/season/season_day/seasonal_daylight_profile` 的逐字段含义和范围由 [静态世界运行规则](../03-runtime/static-world-runtime-rules.md#worldruntimeinitialization) 定义；本文件不重复定义第二套时间 schema。

## RegionClimateEnvelope

`RegionClimateEnvelope` 是权威字段 `Region.climate_profile` 的结构名称，不是独立 EntityType，也不是可以在 Region 尚未存在时直接写入的对象。

初始生成阶段由 `RegionClimateCandidateFormation` 读取已验证的 `RegionLayoutCandidate`、`WorldGenerationParameters` 和 `RandomSeedMaterial`，按 `region_id` 独立生成：

```json
{
  "region_id": "north_slope_wilds",
  "climate_profile": {
    "climate_zone": "cold_temperate",
    "temperature_band": "cold",
    "rainfall_band": "wet",
    "humidity": "medium",
    "seasonality": "strong",
    "prevailing_wind": "northwest",
    "snow_months": ["winter"]
  }
}
```

其中：

```text
GeneratorOutputItem.candidate_type = RegionClimateCandidate
GeneratorOutputItem.candidate_id = candidate_region_climate:<region_id>
payload.region_id = 未来 Region.id，必须匹配已验证 RegionLayoutCandidate.region_id
payload.climate_profile = 物化后写入 Region.climate_profile 的完整值
```

权威 Region 物化后的字段结构为：

```json
{
  "climate_profile": {
    "climate_zone": "cold_temperate",
    "temperature_band": "cold",
    "rainfall_band": "wet",
    "humidity": "medium",
    "seasonality": "strong",
    "prevailing_wind": "northwest",
    "snow_months": ["winter"]
  }
}
```

P0 气候闭集：

```text
cold_temperate
temperate
wet_temperate
dry_steppe
highland
marsh_humid
abnormal
```

气候规则：

| climate_zone | temperature | rainfall | 常见地貌 | 生态倾向 |
| --- | --- | --- | --- | --- |
| cold_temperate | cold/cool | medium/wet | 森林、山坡、溪谷 | 松树、桦树、狼、鹿 |
| temperate | cool/mild | medium | 林地、平原、村镇 | 橡树、野猪、村庄农业 |
| wet_temperate | cool/mild | wet | 溪谷、湿林、湖岸 | 芦苇、水草、鱼、湿泥 |
| dry_steppe | mild/hot | dry | 草原、荒地、盐土 | 荒草、野山羊、盐土 |
| highland | cold | dry/medium | 山脊、岩地、断崖 | 山羊、熊、燧石、矿脉 |
| marsh_humid | mild | wet | 湿地、泥地、水洼 | 蚊虫、水草、泥炭 |
| abnormal | variable | variable | 遗迹、污染地、异常林地 | 异常生物、异常植物、异常资源 |

## ChunkBaseFields

每个未来 `WorldChunk` 先在候选域产生连续基础场。此时权威 `WorldChunk` 尚未创建。

`ChunkBaseRawFieldsCandidate` 最小 payload：

```json
{
  "chunk_id": "chunk_north_slope_12_08_00",
  "region_id": "north_slope_wilds",
  "base_fields": {
    "elevation": 0.72,
    "moisture": 0.63,
    "rockiness": 0.7,
    "soil_depth": 0.3,
    "water_flow": 0.2,
    "civilization_pressure": 0.15,
    "danger_pressure": 0.45,
    "abnormal_pressure": 0.1
  }
}
```

`ChunkBaseFieldsCandidate` 使用相同 payload 字段，但它表示经过稳定邻接平滑后的最终基础场。两个候选类型不能复用同一个 `candidate_id`。

| 字段 | 含义与约束 |
| --- | --- |
| `chunk_id` | 未来 `WorldChunk.id`，必须匹配已验证 `WorldChunkLayoutCandidate.chunk_id`。 |
| `region_id` | 未来 `Region.id`，必须与 chunk layout 和 RegionClimateCandidate 一致。 |
| `base_fields` | 八个 0.0 到 1.0 的归一化连续基础场，字段含义见后文。 |

取值规则：

```text
所有 base field 使用 0.0 到 1.0。
ChunkBaseRawFieldsCandidate 由 RandomSeedMaterial、RegionClimateCandidate、WorldChunkLayoutCandidate 和世界参数生成。
ChunkBaseRawFieldsCandidateFormation 不允许读取邻近 chunk。
ChunkBaseFieldSmoothing 必须等待同一 Region 的全部 ChunkBaseRawFieldsCandidate 通过校验，然后读取相邻候选并按 chunk_id 升序处理邻接列表。
邻接关系只根据同一 grid 中 coord 的正交单位差计算，不读取尚未创建的 ChunkEdge。
相邻 chunk 的 base field 应平滑变化，除非存在断崖、河流、城墙、遗迹边界等硬边界。
base field 不是 UI 展示字段，但必须可调试。
```

## TerrainCandidateFormation

地形候选从平滑后的 `ChunkBaseFieldsCandidate.base_fields` 形成。初始生成阶段的 producer 名称为 `TerrainCandidateFormation`，输出 `ChunkTerrainCandidate`，不直接修改 WorldChunk。

最小 payload：

```json
{
  "chunk_id": "chunk_north_slope_12_08_00",
  "terrain": {
    "landform": "ridge",
    "elevation_band": "highland",
    "slope": "steep",
    "ground": "rocky_soil",
    "soil": "thin",
    "rock": "granite",
    "vegetation_cover": "sparse_forest",
    "visibility": "medium",
    "cover": "medium",
    "base_travel_cost_minutes": 35,
    "terrain_tags": ["mountain", "forest_edge", "wind_exposed"]
  }
}
```

`chunk_id` 必须匹配输入 `ChunkBaseFieldsCandidate.chunk_id`。`ChunkTerrainCandidate.terrain` 故意不包含最终 `water_presence`；该字段由后续 `ChunkHydrologyCandidate` 决定。物化时把两者合并为完整的 `WorldChunk.terrain`。

P0 `landform` 闭集：

```text
plain
forest
hill
ridge
valley
riverbank
wetland
cliff
road
town_block
ruin
cave
lake_shore
```

P0 `slope` 闭集：

```text
flat
gentle
steep
impassable
```

P0 `ground` 闭集：

```text
dirt
grass
rocky_soil
mud
sand
gravel
snow
stone_floor
road_surface
ruined_floor
```

形成规则：

| 条件 | landform 倾向 |
| --- | --- |
| elevation 高 + slope steep + rockiness 高 | ridge / cliff |
| elevation 中 + moisture 中 + vegetation 高 | forest / hill |
| elevation 低 + water_flow 高 | valley / riverbank |
| moisture 高 + soil_depth 高 + water_flow 低 | wetland |
| civilization_pressure 高 | road / town_block |
| abnormal_pressure 高 + civilization_pressure 非零 | ruin；后续 OriginHistoryCandidateFormation 必须解释其来源 |
| rockiness 高 + elevation/slope 支持地下结构 | cave |

## HydrologyCandidateFormation

水系由 moisture、water_flow、elevation、地形和气候共同决定。

初始生成阶段的 producer 名称为 `HydrologyCandidateFormation`。它以 Region 为执行 scope，读取该 Region 全部 `ChunkTerrainCandidate` 和 `ChunkBaseFieldsCandidate`，避免相邻 chunk 各自独立产生互相矛盾的河流。

`ChunkHydrologyCandidate` 最小 payload：

```json
{
  "chunk_id": "chunk_north_slope_12_08_00",
  "region_id": "north_slope_wilds",
  "water_presence": "stream",
  "resource_support": [
    {
      "resource_kind": "water",
      "source_form": "stream"
    }
  ]
}
```

| 字段 | 含义与约束 |
| --- | --- |
| `chunk_id` | 未来 WorldChunk ID，必须匹配同批 terrain 和 base fields 候选。 |
| `region_id` | 未来 Region ID，用于证明跨 chunk 水流只在合法 Region/grid 内连接。 |
| `water_presence` | 该 chunk 的最终水体存在形态，物化后写入 `WorldChunk.terrain.water_presence`。 |
| `resource_support` | 该水文事实允许后续 ResourceFormation 考虑的资源支持条件；它本身不是 ResourceNode。 |
| `resource_support[].resource_kind` | 被支持的自然资源类型，例如 `water`，必须属于资源 registry。 |
| `resource_support[].source_form` | 支持资源的水体形态，必须等于或可由 `water_presence` 推导。 |

该候选本身只输出上面列出的字段。通过校验后，下游阶段按如下方式消费，不得把下游结果伪装成水文候选字段：

```text
SpatialFoundationMaterializer 把 water_presence 写入 WorldChunk.terrain.water_presence。
ResourceFormation 读取 resource_support，再决定是否创建 ResourceNode / ResourceDeposit。
StaticTraversalDeriver 读取 water_presence，再决定过水条件和基础通行代价。
ChunkBiomeCandidateDerivation 读取 water_presence，再推导 aquatic / water_source 相关 biome tag。
```

P0 `water_presence` 闭集：

```text
none
nearby
seasonal
stream
river
spring
pond
well
stagnant
```

形成规则：

| 条件 | 输出 |
| --- | --- |
| water_flow 高 + valley/riverbank | stream 或 river |
| moisture 高 + slope/rock crack | spring |
| moisture 高 + flat/lowland | pond 或 stagnant |
| town_block + civilization_pressure 高 | well |
| dry_steppe + low moisture | none 或 seasonal |

初始静态水文不读取 WeatherState。降雨造成的临时积水、泥泞或湿滑由 `EnvironmentDeriver` 创建 `EnvironmentResidualEffectState`，不能写入永久 `terrain.water_presence`。

水源规则：

```text
water_presence 不是可直接饮用事实。
可饮用或可装水必须生成 ResourceNode。
ResourceNode 必须声明 quality，或由首次观察/检测时确定 quality。
```

## LocalClimateCandidateDerivation

Chunk 可有局部气候修正。

```json
{
  "chunk_id": "chunk_north_slope_12_08_00",
  "local_climate": {
    "temperature_offset_c": -3.0,
    "rainfall_modifier": 1,
    "wind_exposure": "high",
    "fog_likelihood": "medium"
  }
}
```

该 payload 的 candidate_type 是 `ChunkLocalClimateCandidate`。`chunk_id` 必须同时匹配 `WorldChunkLayoutCandidate`、`RegionClimateCandidate`、`ChunkTerrainCandidate` 和 `ChunkHydrologyCandidate` 的目标关系。局部气候只能在地形和水文候选完成后派生，不能作为 `ChunkBaseRawFieldsCandidate` 的输入。

规则：

```text
高地和山脊降低温度、提高 wind_exposure。
溪谷和湿地提高 fog_likelihood。
森林降低 wind_exposure、提高 humidity。
城镇提高温度稳定性、降低野外天气暴露。
异常区域可覆写部分天气候选整数权重，但必须有 `abnormal_pressure` 或已注册异常地形输入支持。
```

## BiomeCandidateDerivation

Biome 是推导出的标签集合。

`ChunkBiomeCandidate` 最小 payload：

```json
{
  "chunk_id": "chunk_north_slope_12_08_00",
  "region_id": "north_slope_wilds",
  "biome_tags": [
    "cold_forest",
    "rocky_highland",
    "predator_habitat",
    "water_source_nearby"
  ]
}
```

| 字段 | 含义与约束 |
| --- | --- |
| `chunk_id` | 未来 WorldChunk ID，必须匹配同批 layout、terrain、hydrology 和 local climate 候选。 |
| `region_id` | 未来 Region ID，必须与目标 chunk 所属 Region 一致。 |
| `biome_tags` | 物化后写入 `WorldChunk.biome_tags` 的派生标签集合；每个标签都必须在 biome tag registry 中，并能由本节允许的输入解释。 |

`RegionBiomeCandidate` 在同一 Region 全部 ChunkBiomeCandidate 完成后稳定聚合：

```json
{
  "region_id": "north_slope_wilds",
  "biome_tags": [
    "cold_forest",
    "rocky_highland",
    "water_source_nearby"
  ],
  "tag_sources": {
    "cold_forest": ["chunk_north_slope_12_08_00"],
    "rocky_highland": ["chunk_north_slope_12_08_00"],
    "water_source_nearby": ["chunk_north_slope_12_08_00"]
  }
}
```

| 字段 | 含义与约束 |
| --- | --- |
| `region_id` | 未来 Region ID。 |
| `biome_tags` | 物化后写入 `Region.biome_tags` 的稳定去重标签集合，按 registry 顺序再按 tag ID 排序。 |
| `tag_sources` | 从每个区域 biome tag 映射到支持该标签的 chunk ID 列表；key 集合必须与 `biome_tags` 完全相同。 |
| `tag_sources.<biome_tag>[]` | 支持该区域标签的 chunk；必须属于同一 Region、引用已验证 ChunkBiomeCandidate，并按 chunk_id 升序去重。 |

`tag_sources` 是受控动态 map：schema 必须用 `propertyNames` 校验 key 属于 BiomeTagRegistry，并把每个 value 限定为非空 chunk ID 数组；不能用开放 `additionalProperties` 接受任意对象。

推导规则：

| 输入 | biome_tags |
| --- | --- |
| cold_temperate + forest | cold_forest |
| wet_temperate + forest | wet_forest |
| highland + ridge | rocky_highland |
| valley + stream | creek_valley |
| wetland + stagnant | marsh |
| town_block + civilization_pressure 高 | settlement |
| road + civilization_pressure 中/高 | trade_route |
| ruin + moisture 高 | damp_ruin |
| abnormal_pressure 高 | abnormal_zone |
| danger_pressure 高 + predator 支持 | predator_habitat |
| water_presence spring/stream | water_source_nearby |

规则：

```text
初始 ChunkBiomeCandidate.biome_tags 必须可由 climate_profile、terrain、water_presence、civilization_pressure、danger_pressure 或 abnormal_pressure 解释，不能读取尚未生成的 OriginEvent。
OriginEvent 物化后允许独立的历史生态更新规则增加可解释标签，但不能反向改写气候、基础场、地形或水文。
手动或 AI 提出的 biome_tags 必须经过 BiomeValidator。
生态生成只能消费 biome_tags，不能反过来篡改地形和气候。
```

## ResourceFormation

自然资源由地形、气候、水系、岩性、历史和异常压力形成。

形成输入：

```text
terrain.landform
terrain.ground
terrain.rock
terrain.water_presence
biome_tags
base_fields.rockiness
base_fields.moisture
civilization_pressure
abnormal_pressure
OriginEventCandidate（仅初始生成阶段，可选）
```

初始 `ResourceFormation` 发生在权威 `OriginEvent` 物化之前，因此只能读取同一 manifest 中已验证的 `OriginEventCandidate` 来调整候选权重，不能读取或伪造尚不存在的 `OriginEvent`。权威历史完成后，运行时若要新增资源，必须走独立规则和事件提交，不能回写本次初始生成结果。

资源生成规则：

| 条件 | 可生成资源 |
| --- | --- |
| stream/river/riverbank | 溪流、砾石、湿泥、河鱼、芦苇 |
| spring + rocky_soil | 泉眼、水晶少量候选 |
| high rockiness + ridge/highland | 花岗岩、燧石、铁矿、铜矿 |
| limestone + cave | 石灰岩、洞穴、水滴、灰蘑菇 |
| wetland + high moisture | 黏土、湿泥、泥炭、水草、蚊虫 |
| forest + dry period | 枯枝堆、干柴 |
| town_block + civilization_pressure | 井水、柴堆、牲畜资源 |
| abnormal_zone + water | 蓝盐、黑血结晶、异常水源 |
| corpse event + predator_habitat | 骨堆、腐肉、兽皮残骸 |

硬规则：

```text
metal_ore 需要 rockiness 中/高和对应 rock/mineral 条件。
water ResourceNode 需要 water_presence 支持。
corpse_remain 需要生物活动、战斗、捕食或历史事件支持。
abnormal_resource 需要 abnormal_zone 或明确异常事件支持。
```

## FloraFormation

植物由气候、地形、水分、土壤、文明压力和异常压力形成。

植物生成规则：

| 条件 | 可生成植物 |
| --- | --- |
| cold_forest | 松树、桦树、矮莓丛、野浆果 |
| temperate forest | 橡树、野葱、野猪生态相关灌木 |
| wetland / creek_valley | 芦苇、水草、湿草、止血草 |
| rocky_highland | 苦根、荒草、少量灌木 |
| town / settlement | 亚麻、农地植物、杂草 |
| damp_ruin / cave | 灰蘑菇、荧光菌 |
| monster_trace / abnormal_zone | 梦魇草、夜光苔、黑脉藤、低语花 |

硬规则：

```text
tree 需要 soil_depth 或 forest biome 支持。
aquatic_plant 需要 water_presence stream/river/pond/wetland。
fungus 需要 damp、cave、ruin 或高湿环境。
medicinal_herb 可以稀有生成，但必须匹配 habitat_tags。
abnormal_flora 必须有 abnormal_zone、monster_trace、ruin 或已验证 OriginEventCandidate 支持；权威 OriginEvent 只用于物化后的独立更新规则。
```

## FaunaFormation

动物由气候、地形、植物、水源、文明压力、危险压力和异常压力形成。

动物生成规则：

| 条件 | 可生成动物 |
| --- | --- |
| grass/forest_edge + low danger | 野兔、田鼠、松鼠 |
| forest + water_source_nearby | 鹿、野猪、乌鸦 |
| rocky_highland | 野山羊、黑熊少量候选 |
| predator_habitat + prey 存在 | 狼、山猫、黑熊 |
| corpse_remain + open terrain | 乌鸦、秃鹫、野狗 |
| stream/pond | 河鱼、泥鳅、蚊虫 |
| settlement | 鸡、羊、牛、马、驴 |
| abnormal_zone + monster_trace | 暗夜狼、腐皮鹿、灰脊兽 |

硬规则：

```text
predator 需要 prey 或 corpse_remain 支持，除非是异常生物。
fish 需要 water_presence stream/river/pond。
livestock 需要 settlement、farm、stable、trade_route 或 NPC/faction 支持。
mount_pack 需要 settlement、road、trade_route 或 faction 支持。
abnormal_beast 必须有 abnormal_zone、monster_trace 或已验证 OriginEventCandidate 支持；权威 OriginEvent 只用于物化后的独立更新规则。
```

## SitePlacement

Site 放置必须参考地形和气候。

规则：

| Site 类型 | 形成条件 |
| --- | --- |
| 旅店 / 民居 | town_block、road、settlement、可达 ChunkEdge |
| 猎人小屋 | forest_edge、water_source_nearby、low/mid civilization_pressure |
| 铁匠铺 | settlement、road、fuel/ore 供应路径 |
| 废弃马车 | road、trade_route、事故或历史事件 |
| 洞穴 | cave、limestone/granite、rockiness 高 |
| 遗迹 | ruin、history event、abnormal 或 abandoned 标签 |
| 水源点 | spring/stream/well/pond 支持 |

硬规则：

```text
Site 必须挂在 WorldChunk 上。
Site 不能放在 terrain.slope=impassable 的 chunk，除非 Site 类型本身是 cliff/cave/ruin 且有入口 LocationEdge。
完整可进入建筑默认占据一个 primary_site。
```

## StaticChunkEdgeFormation

`StaticChunkEdgeFormation` 创建相邻 chunk 之间的 `ChunkEdge` 身份。`ChunkEdge` 的 canonical schema 属于 [地点与空间规则](./location-space-rules.md)；本节只声明形成阶段必须输出哪些 canonical 字段。静态边只表达“这两个 chunk 是否存在物理移动关系”，不读取天气、当前环境或运行时危险。

输入：

```text
source terrain
target terrain
coord delta
elevation difference
slope
water crossing
road presence
danger tags
```

`StaticTraversalDeriver` 在静态边创建后读取 terrain / hydrology / road，派生 `base_passability` 和 `base_traversal`。这仍然属于静态世界生成阶段，不读取 `WeatherState`，也不写最终有效通行。

形成示例：

| 相邻地形 | base_passability.state | base_traversal |
| --- | --- | --- |
| road -> road | open | 低耗时、低迷路 |
| forest -> forest | open | 中耗时、中遮蔽 |
| plain -> ridge | difficult | 高耗时、滑落风险 |
| ridge -> valley | difficult | 需要路径或绕行 |
| plain -> cliff | blocked | blocked_reason=cliff |
| riverbank -> riverbank across river | conditional | 需要桥、浅滩、船或游泳能力 |
| wetland -> forest | difficult | 泥泞、疲劳、迷路风险 |

最小 schema：

```json
{
  "source_chunk_id": "chunk_12_08_02",
  "target_chunk_id": "chunk_12_09_02",
  "direction": "north",
  "adjacent": true,
  "base_passability": {
    "state": "difficult",
    "blocked_reason": null
  },
  "base_traversal": {
    "base_time_minutes": 45,
    "difficulty": "hard",
    "movement_type": "walk",
    "risk_tags": ["slippery_slope", "low_visibility"]
  }
}
```

天气修正不属于 StaticChunkEdgeFormation：

```text
heavy_rain 增加 muddy / slippery 风险。
fog 降低 visibility，增加迷路和遭遇风险。
snow 增加移动耗时和体温风险。
strong_wind 在 ridge/highland 增加风险。
storm 可能临时阻断 cliff/river/wetland crossing。
```

这些修正必须在初始 `WeatherState` 创建后，由 `EnvironmentDeriver` 和 `HazardObstacleDeriver` 生成运行时危险、障碍或 passability override，再由 `PassabilityReducer` 写入最终有效通行。`StaticChunkEdgeFormation` 和 `StaticTraversalDeriver` 不允许读取 `WeatherState`、`EnvironmentState`、`HazardSource`、`ObstacleSource` 或 `effective_passability`。

## WeatherFormation

天气是短期动态状态，不是地形永久属性，也不是 DM 可以临场改写的氛围句。P0 使用“区域天气时间片 + 确定性转移表”：

- 每个 Region 至少维护一个当前 `WeatherState`。
- `WeatherState` 表示一段使用绝对世界分钟的半开天气片段 `[start_world_minute, end_world_minute)`。
- 当目标 `absolute_minute >= 当前 WeatherState.valid_for.end_world_minute` 时，由 `WeatherService.advance` 生成下一段。
- 同样的 world seed、Region、时间和上一段天气必须得到同样的下一段天气。
- 不做天气锋面、云团移动和格点气象模拟。

天气由 `Region.climate_profile`、季节、时间、地形倾向、局部修正、异常压力和上一段天气生成。

P0 schema：

```json
{
  "weather_state": {
    "id": "weather_north_slope_day12_segment03",
    "world_id": "isekai_world_001",
    "scope": "region",
    "region_id": "north_slope_wilds",
    "chunk_id": null,
    "parent_weather_state_id": null,
    "previous_weather_state_id": "weather_north_slope_day12_segment02",
    "coverage_priority": "base_region",
    "condition": "light_rain",
    "intensity": "normal",
    "temperature_c": 7,
    "wind": "moderate",
    "visibility_modifier": -1,
    "ground_effects": ["wet", "muddy"],
    "valid_for": {
      "start_world_minute": 16920,
      "end_world_minute": 17100
    },
    "generated_by": {
      "system": "WeatherFormation",
      "rule_id": "weather.transition_by_climate_season_terrain",
      "random_draw_ref": {
        "stream_ref": {
          "protocol_version": "drp.v1",
          "domain": "weather_generation",
          "rule_id": "weather.transition_by_climate_season_terrain",
          "scope_id": "region:north_slope_wilds",
          "seed_material_hash": "sha256:seed_material_hash"
        },
        "logical_draw_id": "weather_segment_day12_1080",
        "draw_index": 0,
        "draw_kind": "weighted_choice",
        "candidate_set_hash": "sha256:candidate_set_hash",
        "result_id": "weather_condition:light_rain"
      }
    }
  }
}
```

`scope=region` 是 P0 常规天气，必须使用 `coverage_priority=base_region`。`scope=world_chunk` 只用于明确的局部天气覆盖，例如异常雾、山脊局部强风、局部暴雨；此时必须填写 `chunk_id`、`parent_weather_state_id` 和局部覆盖优先级。

P0 天气闭集：

```text
clear
cloudy
light_rain
heavy_rain
fog
snow
strong_wind
storm
abnormal_mist
```

P0 天气强度闭集：

```text
trace
light
normal
heavy
severe
abnormal
```

P0 风力闭集：

```text
calm
light
moderate
strong
gale
abnormal
```

P0 天气地面效果闭集：

```text
wet
muddy
slippery
snow_covered
fast_water
```

P1 天气覆盖优先级闭集由 [静态世界运行规则](../03-runtime/static-world-runtime-rules.md) 定义，WeatherFormation 输出必须使用同一闭集。

天气规则：

| 气候/地形 | 天气倾向 |
| --- | --- |
| wet_temperate / marsh_humid | light_rain、fog、heavy_rain |
| cold_temperate + winter | snow、cloudy、strong_wind |
| highland / ridge | strong_wind、fog |
| dry_steppe | clear、strong_wind |
| abnormal_zone | abnormal_mist、异常降温、低可见度 |

天气转移表：

| 当前天气 | 可以转移到 |
| --- | --- |
| clear | clear, cloudy, fog, strong_wind |
| cloudy | clear, light_rain, heavy_rain, snow, fog |
| light_rain | cloudy, light_rain, heavy_rain, fog |
| heavy_rain | light_rain, cloudy, storm |
| fog | clear, cloudy, light_rain |
| snow | cloudy, snow, strong_wind, storm |
| strong_wind | clear, cloudy, storm |
| storm | heavy_rain, strong_wind, cloudy |
| abnormal_mist | abnormal_mist, fog, cloudy |

权重修正：

```text
天气候选必须先按天气转移表过滤合法目标。
合法目标使用确定性随机协议中的 weather_base_weight。
气候、季节、地形和异常压力只能通过 weather_modifier_weight 增减整数权重。
修正后的权重必须 clamp 到 0 到 1_000_000。
最终选择必须使用 WeightedChoiceKernel。
上一段天气为 storm 时，下一段不能直接跳到 clear，必须先转为 heavy_rain、strong_wind 或 cloudy。
上一段天气为 heavy_rain 时，下一段不能直接跳到 clear，必须先转为 light_rain、cloudy 或 storm。
```

持续时间范围：

| 天气 | 持续时间 |
| --- | --- |
| clear | 120-360 分钟 |
| cloudy | 120-360 分钟 |
| fog | 30-180 分钟 |
| light_rain | 60-240 分钟 |
| heavy_rain | 30-180 分钟 |
| snow | 60-300 分钟 |
| strong_wind | 30-240 分钟 |
| storm | 15-90 分钟 |
| abnormal_mist | 30-240 分钟 |

天气地面效果衰减：

| 来源天气 | 地面效果 | 衰减规则 |
| --- | --- | --- |
| light_rain | wet | 雨停后保留 30-120 分钟，干燥地形取低值，林地/低地取高值。 |
| heavy_rain | wet, muddy, slippery | 雨停后保留 120-360 分钟，wetland/marsh 可更久。 |
| snow | snow_covered, slippery | `temperature_c <= 0` 时保留；升温后 120-360 分钟内衰减。 |
| storm | wet, muddy, fast_water | 风暴结束后河流、湿地、低地风险可继续保留 60-240 分钟。 |
| fog | 无地面残留 | 只通过 visibility_modifier 影响可见度，天气结束后立即重算。 |

天气生成规则 ID：

| rule_id | 入口 | 允许场景 |
| --- | --- | --- |
| `weather.initial_by_climate` | WeatherFormation | 世界生成或 Region 初始化。 |
| `weather.transition_by_climate_season_terrain` | WeatherFormation | 目标 `absolute_minute >= 当前 WeatherState.valid_for.end_world_minute`。 |
| `weather.local_override_by_abnormal_pressure` | WeatherFormation | abnormal_pressure 或异常地形明确支持局部天气。 |
| `weather.resolver_validated_change` | WeatherResolver | 规则事件或 LLM proposal 请求天气变化，并通过校验。 |
| `weather.test_fixture` | TestFixture | 自动化测试夹具。 |

硬规则：

```text
WeatherState 是动态状态，不是地形永久属性。
天气变化必须由 WeatherService.advance 或 WeatherResolver 产生。
天气变化必须形成 WeatherInitialized 或 WeatherChanged StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry。
天气不能直接生成物品，只能影响行动、投影、生态活动和风险。
天气不能直接写 EnvironmentState，必须由 EnvironmentDeriver 将 WeatherState、WorldTimeState、terrain、LocationNode.environment 和光源/热源对象派生成局部环境。
天气结束后的 wet、muddy、slippery、snow_covered、fast_water 残留不能继续挂在旧 WeatherState 上，必须由 EnvironmentDeriver 创建或更新 EnvironmentResidualEffectState。
LLM proposal 不能直接创建 WeatherState，只能提出 weather_change proposal，由 WeatherResolver 校验后决定是否生成新天气片段。
```

## 字段说明

本节解释本文件中出现的数据结构字段。实现时 formation 输出必须使用这些字段名，不能在相邻模块中另起同义字段。

### WorldGenerationParameters 字段

| 字段 | 含义 |
| --- | --- |
| `seed` | 世界生成种子，对应 `RandomSeedMaterial.world_seed`。不能由模块自行派生成本地 seed。 |
| `world_profile` | 世界整体玩法倾向，例如边境生存、城镇调查。它只影响默认权重，不直接等于世界事实。 |
| `region_count` | 本次生成的 Region 数量目标。 |
| `spatial_layout` | P0 空间布局参数，字段、范围和完整网格公式由地点与空间规则定义。 |
| `spatial_layout.generation_mode` | P0 固定为 `procedural`。 |
| `spatial_layout.coverage_mode` | P0 固定为 `complete`。 |
| `spatial_layout.default_grid` | 默认 Region 网格的宽、高和 z 层边界。 |
| `spatial_layout.max_chunks_per_region` | 单 Region chunk 数硬上限，P0 固定为 256。 |
| `default_history_years` | 默认历史模拟年数，用于遗迹、势力、资源消耗和危险来源。 |
| `climate_bias` | 气候倾向权重列表。只能影响候选概率，不能绕过气候闭集和 validator。 |
| `terrain_bias` | 地形倾向权重列表。只能影响候选概率，不能直接写入不符合条件的地形。 |
| `civilization_density` | 文明密度倾向，影响 settlement、road、town_block、livestock、人工资源概率。 |
| `resource_abundance` | 自然资源丰度倾向，影响 ResourceDeposit/ResourceNode 数量和规模。 |
| `danger_level` | 常规危险强度，影响 danger_pressure、危险标签和遭遇概率。 |
| `abnormality_level` | 异常世界强度，影响 abnormal_pressure、异常生态、异常天气和异常资源概率。 |

### climate_profile 字段

| 字段 | 含义 |
| --- | --- |
| `climate_zone` | Region 的长期气候类型，必须属于 P0 气候闭集。 |
| `temperature_band` | 长期温度带，例如 cold、cool、mild、hot。用于植物、生物、天气和水体状态生成。 |
| `rainfall_band` | 长期降水带，例如 dry、medium、wet。用于水系、湿地、植被和天气候选整数权重。 |
| `humidity` | 空气湿度倾向。影响雾、霉菌、腐败、体感和部分生态生成。 |
| `seasonality` | 季节差异强弱。影响温度波动、植物季节、雪季和迁徙。 |
| `prevailing_wind` | 主导风向。用于天气移动、山脊暴露、气味传播和叙事。 |
| `snow_months` | 可能积雪或降雪的季节/月段。为空表示通常无雪季。 |

### base_fields 字段

所有 `base_fields` 取值范围为 `0.0` 到 `1.0`，表示归一化生成倾向，不带现实单位。

| 字段 | 含义 |
| --- | --- |
| `elevation` | 相对海拔。高值更容易形成山脊、高地、断崖和低温修正。 |
| `moisture` | 土壤和环境湿润度。高值更容易形成森林、湿地、泉眼、水洼。 |
| `rockiness` | 岩石裸露和岩层强度。高值支持矿石、燧石、洞穴、断崖。 |
| `soil_depth` | 土层厚度。高值支持农地、森林、湿地；低值支持岩地、荒坡。 |
| `water_flow` | 水流形成倾向。高值支持溪流、河岸、谷地和跨水 ChunkEdge 条件。 |
| `civilization_pressure` | 文明影响强度。高值支持道路、城镇、井、农作物、牲畜和人工资源。 |
| `danger_pressure` | 常规危险压力。高值支持捕食者栖息地、尸骸、陷阱和高风险路径。 |
| `abnormal_pressure` | 异常影响压力。高值支持异常地貌、异常生态、异常天气和异常资源。 |

### terrain 字段

| 字段 | 含义 |
| --- | --- |
| `landform` | chunk 的主地貌，必须属于 P0 `landform` 闭集。 |
| `elevation_band` | 海拔分段，例如 lowland、midland、highland。由 `base_fields.elevation` 推导。 |
| `slope` | 坡度分段，决定通行难度和是否可放置 Site。 |
| `ground` | 地表材质，例如泥地、岩土、道路表面。影响移动、搜索、足迹和天气效果。 |
| `soil` | 土壤状态或厚度描述，用于植物、农地、湿地和采集判断。 |
| `rock` | 主要岩性或矿物基础，用于洞穴、矿石、石材和地貌生成。 |
| `water_presence` | 当前 chunk 的水体存在形态。它不等于可饮用或可装水事实。 |
| `vegetation_cover` | 植被覆盖程度或类型，影响可见度、遮蔽、生态和移动。 |
| `visibility` | 地形导致的基础视野水平。天气、黑夜和室内光照可进一步修正。 |
| `cover` | 地形遮蔽程度，影响躲避、潜行、远程视线和遭遇。 |
| `base_travel_cost_minutes` | 穿越该 chunk 的基础耗时。ChunkEdge 可以基于 source/target 进一步修正。 |
| `terrain_tags` | 地形辅助标签，用于生成检索和叙事。不能替代 `landform` 等权威字段。 |

### local_climate 字段

| 字段 | 含义 |
| --- | --- |
| `temperature_offset_c` | 相对 Region 气候的局部温度修正，单位 celsius，允许负值或正值。P1 建议范围 -15.0 到 15.0，精度 one_decimal。 |
| `rainfall_modifier` | 局部降水修正，叠加在 Region 气候上。 |
| `wind_exposure` | 风暴和强风暴露程度。高地、山脊通常更高。 |
| `fog_likelihood` | 起雾概率倾向。湿地、溪谷和异常区域通常更高。 |

### biome_tags 字段

| 字段 | 含义 |
| --- | --- |
| `biome_tags` | 初始值由气候、地形、水系、文明压力、危险压力和异常压力推导；历史物化后的独立更新可以增加有证据的标签。生态生成不能反向改写地形或气候。 |

### ChunkEdgeFormation 输出字段

| 字段 | 含义 |
| --- | --- |
| `source_chunk_id` | 边的起点 chunk。 |
| `target_chunk_id` | 边的终点 chunk。 |
| `direction` | 从 source 到 target 的方向描述，必须与两个 chunk 的 coord delta 一致。 |
| `adjacent` | 两个 chunk 是否物理接壤。接壤不代表可通行。 |
| `base_passability.state` | 静态基础通行状态：open、difficult、conditional、blocked。 |
| `base_passability.blocked_reason` | 静态阻挡原因。仅在 blocked 或当前条件不满足时需要给出。 |
| `base_traversal.base_time_minutes` | 从 source 到 target 的静态基础耗时。 |
| `base_traversal.difficulty` | 静态路径难度，用于疲劳、失败率和 DM 反馈。 |
| `base_traversal.movement_type` | 默认通行方式，例如 walk、climb、swim。 |
| `base_traversal.risk_tags` | 静态路径风险标签，例如 slippery_slope、low_visibility。 |

### weather_state 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 天气状态 ID。P0 建议按 world、region、day、segment 生成稳定 ID。 |
| `world_id` | 所属 World ID。 |
| `scope` | 天气作用范围。P0 常规值为 region；局部覆盖可用 world_chunk。 |
| `region_id` | 天气所属 Region。 |
| `chunk_id` | 当 `scope=world_chunk` 时引用 WorldChunk；region 天气必须为 null。 |
| `parent_weather_state_id` | 局部天气覆盖的父级 Region WeatherState。region 天气为 null。 |
| `previous_weather_state_id` | 同一 scope 的上一段 WeatherState。初始天气可为 null。 |
| `coverage_priority` | 天气覆盖优先级。Region 基础天气必须为 `base_region`；局部覆盖使用静态运行规则定义的局部优先级闭集。 |
| `condition` | 当前天气类型，必须属于 P0 天气闭集。 |
| `intensity` | 天气强度，必须属于 P0 天气强度闭集。 |
| `temperature_c` | 当前摄氏温度。由气候、季节、地形、时间和局部修正形成。 |
| `wind` | 当前风力描述。影响移动、听觉、气味、体温和远程行动。 |
| `visibility_modifier` | 天气对视野的修正值。负数降低可见度。 |
| `ground_effects` | 天气造成的地表效果，例如 muddy、slippery、snow_covered。 |
| `valid_for.start_world_minute` | 天气片段开始的绝对世界分钟，包含在有效区间内。 |
| `valid_for.end_world_minute` | 天气片段结束的绝对世界分钟，不包含在有效区间内。 |
| `generated_by.system` | 生成系统。P0 必须是 WeatherFormation、WeatherResolver 或 TestFixture。 |
| `generated_by.rule_id` | 天气生成规则 ID，例如 weather.initial_by_climate 或 weather.transition_by_climate_season_terrain。 |
| `generated_by.random_draw_ref` | 本段天气使用的 `RandomDrawRef`，必须符合确定性随机协议。 |

## 形成规则总表

最终形成链路：

| 层级 | 输入 | 输出 | 消费方 |
| --- | --- | --- | --- |
| SpatialLayoutCandidateFormation | 世界参数、RandomSeedMaterial | World/Region/Grid/Chunk layout candidates | SpatialLayoutCandidateValidator |
| RegionClimateCandidateFormation | RegionLayoutCandidate、世界参数、RandomSeedMaterial | RegionClimateCandidate | ChunkBaseRawFieldsCandidateFormation、LocalClimateCandidateDerivation、SpatialFoundationMaterializer |
| ChunkBaseRawFieldsCandidateFormation | WorldChunkLayoutCandidate、RegionClimateCandidate、seed、世界参数 | ChunkBaseRawFieldsCandidate | ChunkBaseFieldSmoothing |
| ChunkBaseFieldSmoothing | 同一 Region 全部 raw fields 候选、稳定 coord 邻接 | ChunkBaseFieldsCandidate | TerrainCandidateFormation |
| TerrainCandidateFormation | ChunkBaseFieldsCandidate | ChunkTerrainCandidate | HydrologyCandidateFormation、LocalClimateCandidateDerivation、ChunkBiomeCandidateDerivation、SpatialFoundationMaterializer |
| HydrologyCandidateFormation | Region 内全部 terrain + moisture + flow | ChunkHydrologyCandidate | LocalClimateCandidateDerivation、ChunkBiomeCandidateDerivation、SpatialFoundationMaterializer、ResourceFormation |
| LocalClimateCandidateDerivation | RegionClimateCandidate + terrain + hydrology | ChunkLocalClimateCandidate | SpatialFoundationMaterializer |
| ChunkBiomeCandidateDerivation | climate + terrain + water + pressure | ChunkBiomeCandidate | RegionBiomeCandidateAggregation、SpatialFoundationMaterializer |
| RegionBiomeCandidateAggregation | Region 全部 ChunkBiomeCandidate | RegionBiomeCandidate | SpatialFoundationMaterializer |
| SpatialFoundationMaterializer | 全部已验证空间基础候选 | World、Region、WorldChunkGrid、WorldChunk | 后续权威世界生成阶段 |
| SettlementAnchorFormation | terrain + hydrology + road + civilization_pressure | RegionFeature / Settlement / TerrainFeature | OriginHistoryCandidate、SitePlacement |
| OriginHistoryCandidateFormation | 静态空间、聚落锚点、资源/生态/猎物/文明/危险/异常压力 | OriginEventCandidate | Resource、Flora、Fauna、Site、Object、Social 形成阶段 |
| ResourceFormation | terrain + biome + rock + 已验证 OriginEventCandidate | ResourceDeposit/Node | FaunaFormation、ObjectMaterialization、Player Action |
| FloraFormation | climate + biome + water + soil + 已验证 OriginEventCandidate | FloraPatch | FaunaFormation、ObjectMaterialization、observe/search/gather |
| FaunaFormation | biome + prey + water + pressure + 已验证 OriginEventCandidate | CreaturePopulation/Group | ObjectMaterialization、observe/track/hunt |
| StaticChunkEdgeFormation | source/target terrain + elevation + adjacency | ChunkEdge identity | StaticTraversalDeriver |
| StaticTraversalDeriver | ChunkEdge + terrain + hydrology + road | base_passability / base_traversal | SitePlacement、PassabilityReducer、HazardObstacleDeriver |
| SitePlacement / LocationGenerator | terrain + road + water + civilization + static reachability + 已验证 OriginEventCandidate | Site / LocationNode / Zone / SiteBoundaryEdge | ObjectMaterialization、SettlementSocialFormation |
| ObjectMaterialization | Site + Resource + Flora + Fauna + catalogs + 已验证 OriginEventCandidate | WorldObject | SettlementSocialFormation、OriginHistoryMaterialization |
| SettlementSocialFormation | Settlement + Site + Resource + WorldObject + 已验证 OriginEventCandidate | 聚落社会状态 | OriginHistoryMaterialization |
| OriginHistoryMaterialization / OriginAttachment | OriginEventCandidate + 已物化证据实体 | OriginEvent + OriginMetadata | WorldRuntimeInitialization |
| WorldRuntimeInitialization | World、初始时间参数、版本锁 | StaticWorldRuntimeState、WorldTimeState | WeatherFormation |
| WeatherFormation | 已提交 Region、WorldTimeState、terrain、previous_weather_state | WeatherState 时间片 | EnvironmentDeriver、Action modifiers |

## Validator 规则

实现时必须加入形成规则 validator，保证：

1. `Region.climate_profile.climate_zone` 属于气候闭集。
2. `WorldChunk.base_fields` 中所有字段必须是 0.0 到 1.0 的归一化倾向值。
3. `WorldChunk.base_fields.temperature_offset` 必须被拒绝。
4. `WorldChunk.local_climate.temperature_offset_c` 必须声明 unit=celsius、range=-15.0 到 15.0、precision=one_decimal。
5. `WorldChunk.terrain.landform` 属于地形闭集。
6. `WorldChunk.terrain.slope` 属于坡度闭集。
7. `WorldChunk.terrain.ground` 属于地表闭集。
8. `WorldChunk.terrain.water_presence` 属于水源闭集。
9. 初始 `biome_tags` 必须能由气候、地形、水源或压力候选解释；历史来源只能在 OriginEvent 已物化后的独立更新中使用。
10. `ResourceDeposit` 和 `ResourceNode` 必须满足资源形成条件。
11. `FloraPatch` 必须满足 PlantSpecies 的 habitat / terrain / biome 条件。
12. `CreaturePopulation` 和 `CreatureGroup` 必须满足 AnimalSpecies 的 habitat / terrain / biome 条件。
13. `predator` 生成必须有 prey、corpse_remain 或异常支持。
14. `livestock` 和 `mount_pack` 生成必须有文明、聚落、道路、贸易或 faction 支持。
15. `abnormal_*` 生态和资源必须有 abnormal_zone、monster_trace、遗迹或历史污染事件支持。
16. `Site` 放置必须满足地形、通行和 chunk 容量规则。
17. `ChunkEdge.base_passability` 必须由相邻地形、水体、坡度和阻挡原因支持。
18. 天气只能影响行动和生态活动，不能直接创建最终物品。
19. `WeatherState.condition`、`intensity`、`wind`、`ground_effects[]` 必须属于 P0 闭集。
20. `WeatherState.scope=region` 时必须引用 Region，且 `chunk_id` 和 `parent_weather_state_id` 必须为 null。
21. `WeatherState.scope=world_chunk` 时必须引用 Region、WorldChunk 和父级 Region WeatherState。
22. `WeatherState.valid_for` 必须使用 `start_world_minute/end_world_minute` 半开区间，结束时间必须晚于开始时间，且持续时间必须落在对应 condition 的持续时间范围内。
23. `WeatherState.scope=region` 时 `coverage_priority` 必须是 `base_region`；同一 Region 的 base_region 天气片段必须连续且不重叠。
24. `WeatherState.scope=world_chunk` 的有效区间必须完全落在父级 Region WeatherState 的有效区间内。
25. `WeatherState.previous_weather_state_id` 不为 null 时，上一段结束时间必须等于当前开始时间，且当前 condition 必须符合天气转移表。
26. `WeatherState.generated_by.rule_id` 必须来自 WeatherFormation 或 WeatherResolver 的允许规则集合。
27. `StaticChunkEdgeFormation` 和 `StaticTraversalDeriver` 不能读取 WeatherState、EnvironmentState、HazardSource、ObstacleSource 或 effective_passability。
28. 天气导致的泥泞、湿滑、低能见度和临时阻断只能通过 EnvironmentDeriver、HazardObstacleDeriver 生成 override，再由 PassabilityReducer 表达为 effective_passability。
29. 天气结束后的地面残留只能通过 EnvironmentResidualEffectState 表达，不能继续依赖过期 WeatherState。
30. AI proposal 提出的气候、地形、资源、生态或天气必须经过 validator 后才能进入 `WorldState`。
31. RegionClimateCandidate、ChunkBaseRawFieldsCandidate、ChunkBaseFieldsCandidate、ChunkTerrainCandidate、ChunkHydrologyCandidate、ChunkLocalClimateCandidate、ChunkBiomeCandidate 和 RegionBiomeCandidate 只能进入 candidate_outputs。
32. `RegionClimateCandidate.region_id` 必须匹配已验证 `RegionLayoutCandidate.region_id`。
33. `ChunkBaseRawFieldsCandidate.chunk_id/region_id` 必须匹配已验证 WorldChunkLayoutCandidate，且不能读取邻接候选。
34. `ChunkBaseFieldSmoothing` 必须等待同一 Region 全部 raw fields 候选通过校验，并按相邻 chunk_id 升序读取。
35. `ChunkTerrainCandidate` 不能填写最终 `water_presence`；该字段只能来自匹配的 ChunkHydrologyCandidate。
36. `HydrologyCandidateFormation` 必须在 Region scope 校验相邻 stream/river 的流向连续性；孤立断流必须有 spring、pond、stagnant、边界流出或明确异常规则支持。
37. `ChunkLocalClimateCandidate` 必须读取匹配的 RegionClimateCandidate、ChunkTerrainCandidate 和 ChunkHydrologyCandidate。
38. `ChunkBiomeCandidate.biome_tags` 必须稳定去重并全部存在于 biome tag registry。
39. `RegionBiomeCandidate.tag_sources` 的 key 集合必须等于 `biome_tags`；每个来源 chunk 必须属于同一 Region，且能解释对应区域 biome tag。
40. `SpatialFoundationValidator` 必须能组合出完整 canonical Region 和 WorldChunk post-state，不能用缺失字段或未声明占位值通过。
41. `SpatialFoundationMaterializer` 必须把 World、全部 Region、全部 Grid 和全部 Chunk 放入同一 atomic_commit_group_id。
42. 初始 WeatherFormation 必须读取已提交 WorldTimeState；WorldTimeState 不存在时禁止生成 WeatherState。
43. TerrainCandidateFormation 不能读取 OriginEvent 或 OriginEventCandidate；遗迹/洞穴先由物理压力形成，后续历史候选负责解释。
44. HydrologyCandidateFormation 不能读取 WeatherState，也不能输出不属于 water_presence 闭集的 puddle/rain_pool。
45. 初始 ResourceFormation、FloraFormation 和 FaunaFormation 只能读取已验证 OriginEventCandidate，不能读取尚未物化的 OriginEvent。

## 测试清单

```text
test_region_climate_candidate_requires_validated_region_layout
test_chunk_raw_fields_require_validated_chunk_layout_and_region_climate
test_chunk_raw_fields_do_not_read_neighbors
test_chunk_smoothing_waits_for_complete_region_raw_field_set
test_chunk_smoothing_parallel_and_serial_results_match
test_terrain_candidate_does_not_claim_final_water_presence
test_hydrology_candidate_rejects_unexplained_cross_chunk_discontinuity
test_local_climate_candidate_requires_terrain_and_hydrology
test_chunk_biome_candidate_tags_are_registered_and_derivable
test_region_biome_candidate_tag_sources_match_biome_tags
test_region_biome_candidate_tag_sources_belong_to_region
test_spatial_foundation_validator_rejects_missing_candidate
test_spatial_foundation_materializer_merges_water_presence_into_terrain
test_initial_weather_requires_world_time_state
test_initial_terrain_candidate_does_not_read_history
test_static_hydrology_rejects_weather_input
test_static_hydrology_rejects_unregistered_puddle_value
test_initial_biome_candidate_does_not_read_origin_event
test_initial_ecology_uses_history_candidate_not_origin_event
```

## 与现有文档关系

本设计依赖：

- [地点与空间规则](./location-space-rules.md)
- [自然生态与资源规则](./natural-ecology-rules.md)
- [WorldObject 规则](./world-object-rules.md)

关系如下：

```text
Climate / Terrain Formation
-> BiomeCandidateDerivation
-> Natural Ecology Formation
-> Resource / Flora / Fauna runtime entities
-> Player Action
-> Deterministic Resolver
-> WorldObject / EventLog / Updated WorldState
```

## 架构决策

1. 气候是长期倾向，主要属于 Region。
2. 地形是物理事实，属于 WorldChunk。
3. Biome 是推导标签，不是任意文本。
4. 天气是短期动态状态，不是地形永久属性。
5. 资源和动植物必须由气候、地形、水源、生物群系、文明压力或异常事件支持。
6. 生态生成先产生运行时生态实体，不直接产生玩家物品。
7. `ChunkEdge.base_passability/base_traversal` 只能由相邻静态地形和水文形成；天气通过运行时环境、障碍 override 和 PassabilityReducer 影响 effective 结果。
8. AI 可以提出候选，但不能绕过形成规则和 validator。
9. 最终事实以 Authoritative WorldState、Validator、Resolver 和 EventLog 为准。
10. 气候和物理形成阶段读取已验证空间布局候选，不要求提前存在半成品 Region 或 WorldChunk。
11. ChunkBaseFields 必须经过 raw fields 全量屏障和稳定邻接平滑。
12. TerrainCandidateFormation 不拥有最终水文结论；`terrain.water_presence` 来自 HydrologyCandidateFormation。
13. 局部气候在地形和水文之后派生，不能混入 raw base fields。
14. 所有空间基础候选完整后，才能原子物化 World、Region、WorldChunkGrid 和 WorldChunk。
