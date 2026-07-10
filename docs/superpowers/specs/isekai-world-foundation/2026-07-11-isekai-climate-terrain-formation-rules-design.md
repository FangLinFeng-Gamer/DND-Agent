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
- 明确 `ChunkEdge` 的通行成本和风险必须由地形、坡度、水体、天气共同决定。
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
天气概率
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

世界生成顺序：

```text
WorldGenerationParameters
-> RegionClimateEnvelope
-> ChunkBaseFields
-> TerrainFormation
-> HydrologyFormation
-> LocalClimateModifiers
-> BiomeDerivation
-> ResourceFormation
-> FloraFormation
-> FaunaFormation
-> SitePlacement
-> ChunkEdgeFormation
-> WeatherInitialization
-> Validator
-> Authoritative WorldState
```

其中：

```text
RegionClimateEnvelope：区域长期气候。
ChunkBaseFields：粗粒度高度、水分、地表、文明压力、异常压力。
TerrainFormation：把 base fields 转成 landform / slope / ground / vegetation。
HydrologyFormation：生成溪流、泉眼、水洼、井、湖岸等水系事实。
BiomeDerivation：生成 biome_tags。
ResourceFormation：生成 ResourceDeposit / ResourceNode。
FloraFormation：生成 FloraPatch。
FaunaFormation：生成 CreaturePopulation / CreatureGroup。
```

## WorldGenerationParameters

世界生成参数决定本次世界的整体倾向。

最小 schema：

```json
{
  "seed": "adv_10_seed",
  "world_profile": "frontier_survival",
  "region_count": 2,
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
seed 必须参与所有确定性随机。
world_profile 决定默认权重，不直接生成事实。
climate_bias / terrain_bias 只能影响候选权重，不能绕过 validator。
danger_level / abnormality_level 影响危险标签和异常生态概率。
```

## RegionClimateEnvelope

`Region` 必须有长期气候包络。

最小 schema：

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

每个 `WorldChunk` 生成时先产生基础场。

最小 schema：

```json
{
  "base_fields": {
    "elevation": 0.72,
    "moisture": 0.63,
    "temperature_offset": -0.1,
    "rockiness": 0.7,
    "soil_depth": 0.3,
    "water_flow": 0.2,
    "civilization_pressure": 0.15,
    "danger_pressure": 0.45,
    "abnormal_pressure": 0.1
  }
}
```

取值规则：

```text
所有 base field 使用 0.0 到 1.0。
base field 由 seed、Region climate、邻近 chunk 和世界参数生成。
相邻 chunk 的 base field 应平滑变化，除非存在断崖、河流、城墙、遗迹边界等硬边界。
base field 不是 UI 展示字段，但必须可调试。
```

## TerrainFormation

地形从 `base_fields` 形成。

WorldChunk 必须持久化 terrain：

```json
{
  "terrain": {
    "landform": "ridge",
    "elevation_band": "highland",
    "slope": "steep",
    "ground": "rocky_soil",
    "soil": "thin",
    "rock": "granite",
    "water_presence": "none",
    "vegetation_cover": "sparse_forest",
    "visibility": "medium",
    "cover": "medium",
    "base_travel_cost_minutes": 35,
    "terrain_tags": ["mountain", "forest_edge", "wind_exposed"]
  }
}
```

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
| abnormal_pressure 高 + 历史遗迹事件 | ruin |
| rockiness 高 + 地下入口/历史事件 | cave |

## HydrologyFormation

水系由 moisture、water_flow、elevation、地形和气候共同决定。

水系输出：

```text
water_presence
ResourceNode(water)
ChunkEdge crossing requirements
wet ground effects
aquatic biome tags
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
| rain weather + low ground | puddle / rain_pool |
| dry_steppe + low moisture | none 或 seasonal |

水源规则：

```text
water_presence 不是可直接饮用事实。
可饮用或可装水必须生成 ResourceNode。
ResourceNode 必须声明 quality，或由首次观察/检测时确定 quality。
```

## LocalClimateModifiers

Chunk 可有局部气候修正。

```json
{
  "local_climate": {
    "temperature_modifier": -1,
    "rainfall_modifier": 1,
    "wind_exposure": "high",
    "fog_likelihood": "medium"
  }
}
```

规则：

```text
高地和山脊降低温度、提高 wind_exposure。
溪谷和湿地提高 fog_likelihood。
森林降低 wind_exposure、提高 humidity。
城镇提高温度稳定性、降低野外天气暴露。
异常区域可覆写部分天气概率，但必须有 abnormal 标签。
```

## BiomeDerivation

Biome 是推导出的标签集合。

最小输出：

```json
{
  "biome_tags": [
    "cold_forest",
    "north_slope",
    "predator_habitat",
    "spring_nearby"
  ]
}
```

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
biome_tags 必须可由 climate_profile、terrain、water_presence、civilization_pressure、danger_pressure、abnormal_pressure 或历史事件解释。
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
history_events
```

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
abnormal_flora 必须有 abnormal_zone、monster_trace、ruin 或历史污染事件支持。
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
abnormal_beast 必须有 abnormal_zone、monster_trace 或相关历史事件支持。
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

## ChunkEdgeFormation

`ChunkEdge` 决定相邻 chunk 是否可通行，以及需要多久。

输入：

```text
source terrain
target terrain
elevation difference
slope
water crossing
road presence
weather state
danger tags
```

形成示例：

| 相邻地形 | passability.state | traversal |
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
  "relation": "adjacent",
  "passability": {
    "state": "difficult",
    "blocked_reason": null
  },
  "traversal": {
    "base_time_minutes": 45,
    "difficulty": "hard",
    "movement_type": "walk",
    "risk_tags": ["slippery_slope", "low_visibility"]
  }
}
```

天气修正：

```text
heavy_rain 增加 muddy / slippery 风险。
fog 降低 visibility，增加迷路和遭遇风险。
snow 增加移动耗时和体温风险。
strong_wind 在 ridge/highland 增加风险。
storm 可能临时阻断 cliff/river/wetland crossing。
```

## WeatherFormation

天气由 `Region.climate_profile`、季节、时间、地形和局部修正生成。

最小 schema：

```json
{
  "weather_state": {
    "condition": "light_rain",
    "temperature_c": 7,
    "wind": "moderate",
    "visibility_modifier": -1,
    "ground_effects": ["muddy"],
    "duration_minutes": 180
  }
}
```

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

天气规则：

| 气候/地形 | 天气倾向 |
| --- | --- |
| wet_temperate / marsh_humid | light_rain、fog、heavy_rain |
| cold_temperate + winter | snow、cloudy、strong_wind |
| highland / ridge | strong_wind、fog |
| dry_steppe | clear、strong_wind |
| abnormal_zone | abnormal_mist、异常降温、低可见度 |

硬规则：

```text
weather_state 是动态状态，不是地形永久属性。
天气变化必须写 WeatherChangedEvent，或由时间推进服务可重算。
天气不能直接生成物品，只能影响行动、投影、生态活动和风险。
```

## 字段说明

本节解释本文件中出现的数据结构字段。实现时 formation 输出必须使用这些字段名，不能在相邻模块中另起同义字段。

### WorldGenerationParameters 字段

| 字段 | 含义 |
| --- | --- |
| `seed` | 世界生成种子。所有确定性随机都必须从该值或其派生值产生。 |
| `world_profile` | 世界整体玩法倾向，例如边境生存、城镇调查。它只影响默认权重，不直接等于世界事实。 |
| `region_count` | 本次生成的 Region 数量目标。 |
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
| `rainfall_band` | 长期降水带，例如 dry、medium、wet。用于水系、湿地、植被和天气概率。 |
| `humidity` | 空气湿度倾向。影响雾、霉菌、腐败、体感和部分生态生成。 |
| `seasonality` | 季节差异强弱。影响温度波动、植物季节、雪季和迁徙。 |
| `prevailing_wind` | 主导风向。用于天气移动、山脊暴露、气味传播和叙事。 |
| `snow_months` | 可能积雪或降雪的季节/月段。为空表示通常无雪季。 |

### base_fields 字段

所有 `base_fields` 取值范围为 `0.0` 到 `1.0`，除非后续规则显式扩展。

| 字段 | 含义 |
| --- | --- |
| `elevation` | 相对海拔。高值更容易形成山脊、高地、断崖和低温修正。 |
| `moisture` | 土壤和环境湿润度。高值更容易形成森林、湿地、泉眼、水洼。 |
| `temperature_offset` | 相对 Region 气候的局部温度修正。可为负值或正值。 |
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
| `temperature_modifier` | 局部温度修正，叠加在 Region 气候上。 |
| `rainfall_modifier` | 局部降水修正，叠加在 Region 气候上。 |
| `wind_exposure` | 风暴和强风暴露程度。高地、山脊通常更高。 |
| `fog_likelihood` | 起雾概率倾向。湿地、溪谷和异常区域通常更高。 |

### biome_tags 字段

| 字段 | 含义 |
| --- | --- |
| `biome_tags` | 由气候、地形、水系、文明压力、危险压力、异常压力和历史事件推导出的生态标签集合。生态生成只能消费该字段，不能反向改写地形或气候。 |

### ChunkEdgeFormation 输出字段

| 字段 | 含义 |
| --- | --- |
| `source_chunk_id` | 边的起点 chunk。 |
| `target_chunk_id` | 边的终点 chunk。 |
| `relation` | 两个 chunk 的关系，P0 主要使用 `adjacent`。 |
| `passability.state` | 通行状态：open、difficult、conditional、blocked。 |
| `passability.blocked_reason` | 阻挡原因。仅在 blocked 或当前条件不满足时需要给出。 |
| `traversal.base_time_minutes` | 从 source 到 target 的基础耗时。 |
| `traversal.difficulty` | 路径难度，用于疲劳、失败率和 DM 反馈。 |
| `traversal.movement_type` | 默认通行方式，例如 walk、climb、swim。 |
| `traversal.risk_tags` | 路径风险标签，例如 slippery_slope、low_visibility。 |

### weather_state 字段

| 字段 | 含义 |
| --- | --- |
| `condition` | 当前天气类型，必须属于 P0 天气闭集。 |
| `temperature_c` | 当前摄氏温度。由气候、季节、地形、时间和局部修正形成。 |
| `wind` | 当前风力描述。影响移动、听觉、气味、体温和远程行动。 |
| `visibility_modifier` | 天气对视野的修正值。负数降低可见度。 |
| `ground_effects` | 天气造成的地表效果，例如 muddy、slippery、snow_covered。 |
| `duration_minutes` | 预计持续时间。时间推进后可减少或触发天气变化。 |

## 形成规则总表

最终形成链路：

| 层级 | 输入 | 输出 | 消费方 |
| --- | --- | --- | --- |
| RegionClimateEnvelope | 世界参数、seed | climate_profile | ChunkBaseFields、Weather |
| ChunkBaseFields | seed、Region、邻接 chunk | elevation/moisture/rockiness 等 | TerrainFormation |
| TerrainFormation | base_fields | terrain | Hydrology、Biome、ChunkEdge |
| HydrologyFormation | terrain + moisture + flow | water_presence、ResourceNode 候选 | Biome、Resource |
| BiomeDerivation | climate + terrain + water + pressure | biome_tags | Ecology |
| ResourceFormation | terrain + biome + rock + history | ResourceDeposit/Node | Player Action |
| FloraFormation | climate + biome + water + soil | FloraPatch | observe/search/gather |
| FaunaFormation | biome + prey + water + pressure | CreaturePopulation/Group | observe/track/hunt |
| SitePlacement | terrain + road + water + civilization | Site | Location generation |
| ChunkEdgeFormation | source/target terrain + weather | passability/traversal | Travel resolver |
| WeatherFormation | climate + season + terrain | weather_state | Action modifiers |

## Validator 规则

实现时必须加入形成规则 validator，保证：

1. `Region.climate_profile.climate_zone` 属于气候闭集。
2. `WorldChunk.terrain.landform` 属于地形闭集。
3. `WorldChunk.terrain.slope` 属于坡度闭集。
4. `WorldChunk.terrain.ground` 属于地表闭集。
5. `WorldChunk.terrain.water_presence` 属于水源闭集。
6. `biome_tags` 必须能由气候、地形、水源、压力或历史事件解释。
7. `ResourceDeposit` 和 `ResourceNode` 必须满足资源形成条件。
8. `FloraPatch` 必须满足 PlantSpecies 的 habitat / terrain / biome 条件。
9. `CreaturePopulation` 和 `CreatureGroup` 必须满足 AnimalSpecies 的 habitat / terrain / biome 条件。
10. `predator` 生成必须有 prey、corpse_remain 或异常支持。
11. `livestock` 和 `mount_pack` 生成必须有文明、聚落、道路、贸易或 faction 支持。
12. `abnormal_*` 生态和资源必须有 abnormal_zone、monster_trace、遗迹或历史污染事件支持。
13. `Site` 放置必须满足地形、通行和 chunk 容量规则。
14. `ChunkEdge.passability` 必须由相邻地形、水体、坡度和阻挡原因支持。
15. 天气只能影响行动和生态活动，不能直接创建最终物品。
16. AI proposal 提出的气候、地形、资源或生态必须经过 validator 后才能进入 `WorldState`。

## 与现有文档关系

本设计依赖：

- [地点与空间规则](./2026-07-10-isekai-location-space-rules-design.md)
- [自然生态与资源规则](./2026-07-10-isekai-natural-ecology-rules-design.md)
- [WorldObject 规则](./2026-07-10-isekai-world-object-rules-design.md)

关系如下：

```text
Climate / Terrain Formation
-> BiomeDerivation
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
7. `ChunkEdge` 通行规则必须由相邻地形和天气修正。
8. AI 可以提出候选，但不能绕过形成规则和 validator。
9. 最终事实以 Authoritative WorldState、Validator、Resolver 和 EventLog 为准。
