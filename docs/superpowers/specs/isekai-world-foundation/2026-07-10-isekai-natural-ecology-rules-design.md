# 异世界模式自然生态与资源规则设计

## 背景

地点/空间规则已经定义世界在哪里，WorldObject 规则已经定义非生命对象如何落位和结算。世界生成在此之上还需要一层自然生态输入：哪些动物、植物和非生命自然资源会自然出现在不同地形、气候、风险和文明压力下。

本设计定义世界生成前置 catalog 和运行时生态实体。它回答：

```text
山地为什么有狼和山羊？
溪谷为什么有鱼、芦苇和黏土？
森林为什么有浆果、草药、枯枝和野兽痕迹？
矿脉、水源、植物和动物如何在玩家交互后转成 WorldObject？
```

## 目标

- 定义动物、植物、非生命自然资源的基础 catalog。
- 定义这些 catalog 如何参与 Region / WorldChunk / Site 生成。
- 区分“生态存在”和“玩家持有物品”。
- 定义 `CreaturePopulation`、`CreatureGroup`、`FloraPatch`、`ResourceDeposit` 等运行时生态实体。
- 定义采集、狩猎、捕鱼、装水、搜索后如何生成或修改 `WorldObject`。
- 保证自然生态也遵守地点/空间规则和权威 `WorldState`。

## 非目标

- 不实现完整战斗系统。
- 不实现制作、合成、配方和打造系统。
- 不为每只普通动物建立独立 AI。
- 不把所有植物都建成可拾取物品。
- 不把每一棵树、每一株草、每一块石头都实例化为 `WorldObject`。
- 不让 DM 通过叙事直接发放肉、草药、矿石、水或稀有材料。

## 核心原则

### 1. 生态存在不等于背包物品

动物、活体植物、水源、矿脉、土壤和地貌资源先属于世界生态，不属于玩家物品栏。

```text
鹿在森林里 != 玩家拥有鹿肉
梦魇草长在北坡 != 玩家拥有梦魇草
铁矿在山里 != 玩家拥有铁锭
溪流经过 chunk != 玩家水囊已装满
```

只有经过规则结算后，生态实体才会产生 `WorldObject` 或修改已有 `WorldObject`。

### 2. Catalog 是生成输入，不是运行时事实

`AnimalSpeciesCatalog`、`PlantSpeciesCatalog`、`NaturalResourceCatalog` 只定义物种和资源的基础规则。运行时真实存在的是：

```text
CreaturePopulation
CreatureGroup
CreatureActor
FloraPatch
ResourceDeposit
ResourceNode
WorldObject
```

### 3. 大多数动物用群体或种群表示

普通动物不应逐个实例化。世界生成先创建种群和小群体，只有靠近玩家、进入冲突、被追踪、被驯养、成为剧情关键时，才升级为具体 `CreatureActor`。

```text
AnimalSpeciesCatalog
-> CreaturePopulation
-> CreatureGroup
-> CreatureActor
```

### 4. 植物默认用片区表示

植物首先以 `FloraPatch` 存在，例如一片松林、一簇灌木、一小片药草。玩家观察或搜索时可以投影为可互动目标；采集成功后才生成 `WorldObject(resource/food/material)`。

```text
PlantSpeciesCatalog
-> FloraPatch
-> HarvestResult
-> WorldObject
```

### 5. 非生命自然资源用资源点或矿藏表示

水源、矿脉、石料、黏土、盐土、干柴、尸骨等用 `ResourceDeposit` 或 `ResourceNode` 表示。它们可以被观察、搜索、采集或消耗，但产出必须由 resolver 写入状态。

```text
NaturalResourceCatalog
-> ResourceDeposit / ResourceNode
-> ExtractionResult
-> WorldObject 或已有 WorldObject 状态变化
```

### 6. 生态必须挂到空间

所有运行时生态实体都必须能解析到空间位置：

```text
WorldChunk
LocationNode + Zone
near_object / inside_object / under_object
offscreen
removed
```

生态实体不允许只存在于 DM 文本。

## Catalog 类型

### AnimalSpecies

动物物种定义。

最小 schema：

```json
{
  "species_id": "wolf",
  "name": "狼",
  "aliases": ["野狼", "灰狼"],
  "category": "predator",
  "habitat_tags": ["forest", "mountain", "cold"],
  "terrain_tags": ["forest", "ridge", "valley"],
  "activity_cycle": "night",
  "diet": "carnivore",
  "sociality": "pack",
  "danger_level": 3,
  "sign_tags": ["tracks", "howl", "fur", "carcass"],
  "population_rules": {
    "min_group_size": 2,
    "max_group_size": 8,
    "rarity": "uncommon"
  },
  "harvest_outputs": [
    {
      "object_type": "food",
      "name": "生肉",
      "tags": ["meat"]
    },
    {
      "object_type": "material",
      "name": "兽皮",
      "tags": ["hide"]
    }
  ]
}
```

字段规则：

```text
species_id 必须唯一。
category 必须属于动物分类闭集。
habitat_tags / terrain_tags 用于世界生成匹配。
danger_level 只表示生态风险，不直接等于战斗数值。
harvest_outputs 只表示可能产出，不能直接进入玩家物品栏。
```

### PlantSpecies

植物物种定义。

最小 schema：

```json
{
  "species_id": "nightmare_grass",
  "name": "梦魇草",
  "aliases": ["梦魇草", "黑梦草"],
  "category": "medicinal_herb",
  "habitat_tags": ["cold", "shaded", "monster_trace"],
  "terrain_tags": ["forest", "slope", "ruin_edge"],
  "growth_form": "patch",
  "visibility": "hinted",
  "rarity": "rare",
  "risk_tags": ["misidentification"],
  "harvest_outputs": [
    {
      "object_type": "resource",
      "name": "梦魇草",
      "tags": ["herb", "medicine"]
    }
  ]
}
```

字段规则：

```text
species_id 必须唯一。
category 必须属于植物分类闭集。
growth_form 用于投影和叙事，不创建空间层级。
rarity 影响生成概率。
harvest_outputs 只表示成功采集后 resolver 可以生成的 WorldObject。
```

### NaturalResource

非生命自然资源定义。

最小 schema：

```json
{
  "resource_id": "spring_water",
  "name": "泉眼",
  "aliases": ["泉水", "小泉眼"],
  "category": "water",
  "terrain_tags": ["slope", "valley", "forest"],
  "deposit_kind": "resource_node",
  "renewability": "renewable",
  "visibility": "visible",
  "access_rules": {
    "requires_tool": false,
    "requires_container": true
  },
  "extraction_outputs": [
    {
      "operation": "refill_water",
      "target_object_type": "container",
      "resource_type": "water"
    }
  ]
}
```

字段规则：

```text
resource_id 必须唯一。
category 必须属于自然资源分类闭集。
deposit_kind 决定运行时使用 ResourceDeposit 还是 ResourceNode。
extraction_outputs 表示可结算操作，不直接修改玩家状态。
```

## 动物分类

动物分类闭集：

```text
small_prey
large_prey
predator
scavenger
bird
fish
insect
livestock
mount_pack
abnormal_beast
```

P0 动物目录：

| species_id | 名称 | 分类 | 典型环境 | 主要作用 |
| --- | --- | --- | --- | --- |
| rabbit | 野兔 | small_prey | 草地、林缘 | 食物、脚印、低风险狩猎 |
| field_mouse | 田鼠 | small_prey | 草地、农田 | 生态信号、捕食链 |
| squirrel | 松鼠 | small_prey | 森林 | 林地生态、轻量痕迹 |
| deer | 鹿 | large_prey | 森林、溪谷 | 肉、皮、追踪目标 |
| wild_goat | 野山羊 | large_prey | 山坡、岩地 | 肉、皮、山地生态 |
| boar | 野猪 | large_prey | 森林、灌木 | 食物来源、中风险遭遇 |
| wolf | 狼 | predator | 森林、山地、寒冷区 | 风险、狼嚎、追踪压力 |
| wildcat | 山猫 | predator | 林地、山坡 | 小型捕食者、潜伏风险 |
| black_bear | 黑熊 | predator | 森林、山地 | 高风险遭遇、领地压力 |
| crow | 乌鸦 | bird | 城镇、腐败地、森林 | 尸体线索、氛围信号 |
| night_owl | 夜枭 | bird | 夜间森林 | 夜间提示、预警 |
| vulture | 秃鹫 | scavenger | 荒地、尸体附近 | 腐肉线索 |
| stray_dog | 野狗 | scavenger | 城镇边缘、废墟 | 腐败生态、低阶威胁 |
| river_fish | 河鱼 | fish | 河流、溪谷 | 食物资源 |
| loach | 泥鳅 | fish | 泥水、浅溪 | 低级食物、水域生态 |
| bee | 蜂 | insect | 林地、花丛 | 蜂巢、蜂蜜线索 |
| mosquito_swarm | 蚊虫群 | insect | 湿地、水边 | 疾病和不适压力 |
| beetle | 甲虫 | insect | 腐木、湿土 | 腐败生态信号 |
| chicken | 鸡 | livestock | 村庄、城镇 | 文明食物来源 |
| sheep | 羊 | livestock | 牧场、村庄 | 肉、毛、文明资源 |
| cattle | 牛 | livestock | 村庄、农地 | 食物、劳力、经济 |
| horse | 马 | mount_pack | 城镇、道路、马厩 | 运输和文明信号 |
| donkey | 驴 | mount_pack | 村庄、商路 | 运输、商队 |
| night_wolf | 暗夜狼 | abnormal_beast | 异常森林、北坡夜间 | 核心危险、任务线索 |
| rot_hide_deer | 腐皮鹿 | abnormal_beast | 腐败森林 | 异常生态、污染线索 |
| gray_spine_beast | 灰脊兽 | abnormal_beast | 山地、断崖 | 高风险异兽 |

## 植物分类

植物分类闭集：

```text
tree
shrub
grass
edible_plant
medicinal_herb
poisonous_plant
fiber_plant
aquatic_plant
fungus
abnormal_flora
```

P0 植物目录：

| species_id | 名称 | 分类 | 典型环境 | 主要作用 |
| --- | --- | --- | --- | --- |
| pine_tree | 松树 | tree | 寒冷森林、山坡 | 木材、林地识别、遮蔽 |
| birch_tree | 桦树 | tree | 寒冷森林 | 木材、地貌识别 |
| oak_tree | 橡树 | tree | 温带森林 | 木材、坚果、文明边缘 |
| dead_tree | 枯木 | tree | 森林、腐败地 | 干柴、腐朽线索 |
| thorn_bush | 刺灌木 | shrub | 林缘、荒地 | 阻挡、刮伤风险、遮蔽 |
| dwarf_berry_bush | 矮莓丛 | shrub | 林地、溪谷 | 果实线索、采集目标 |
| dry_grass | 荒草 | grass | 平原、荒地 | 地表覆盖、火险 |
| wet_grass | 湿草 | grass | 溪边、湿地 | 水源线索 |
| wild_berries | 野浆果 | edible_plant | 林地、灌木 | 食物采集 |
| red_berries | 红浆果 | edible_plant | 林地、灌木 | 食物或误判风险 |
| wild_onion | 野葱 | edible_plant | 草地、林缘 | 食物采集 |
| edible_root | 块根 | edible_plant | 草地、坡地 | 食物采集 |
| nightmare_grass | 梦魇草 | medicinal_herb | 阴冷林地、魔物痕迹 | 药草、任务线索 |
| bloodroot | 止血草 | medicinal_herb | 林地、溪边 | 治疗线索 |
| bitter_root | 苦根 | medicinal_herb | 山坡、贫瘠土 | 药用资源 |
| poison_redberry | 毒红莓 | poisonous_plant | 灌木、腐败森林 | 误食风险 |
| numbing_mushroom | 麻痹菇 | poisonous_plant | 潮湿阴影 | 中毒风险 |
| flax | 亚麻 | fiber_plant | 村庄、农地 | 纤维来源 |
| reed | 芦苇 | aquatic_plant | 溪谷、湖边 | 水源、纤维、遮蔽 |
| waterweed | 水草 | aquatic_plant | 溪流、池塘 | 水域生态 |
| gray_mushroom | 灰蘑菇 | fungus | 潮湿森林、洞穴 | 食物或风险 |
| glow_fungus | 荧光菌 | fungus | 洞穴、异常湿地 | 光源线索、异界感 |
| night_moss | 夜光苔 | abnormal_flora | 遗迹、阴暗石面 | 异常光源、线索 |
| black_vein_vine | 黑脉藤 | abnormal_flora | 腐败森林、遗迹 | 阻挡、异常生态 |
| whisper_flower | 低语花 | abnormal_flora | 异常林地 | 精神压力、线索 |

## 非生命自然资源分类

自然资源分类闭集：

```text
water
stone
metal_ore
clay_soil
sand_gravel
salt_mineral
fuel
gem_crystal
corpse_remain
abnormal_resource
```

P0 自然资源目录：

| resource_id | 名称 | 分类 | 典型环境 | 主要作用 |
| --- | --- | --- | --- | --- |
| stream_water | 溪流 | water | 溪谷、森林 | 饮水、装水、路径 |
| spring_water | 泉眼 | water | 山坡、森林 | 安全水源候选 |
| puddle_water | 水洼 | water | 雨后、低地 | 临时水源、污染风险 |
| well_water | 井水 | water | 村庄、城镇 | 文明水源 |
| rain_pool | 雨水积坑 | water | 岩地、废墟 | 临时水源 |
| granite | 花岗岩 | stone | 山地 | 地貌、石料 |
| limestone | 石灰岩 | stone | 山地、洞穴 | 地貌、洞穴线索 |
| flint | 燧石 | stone | 河滩、山地 | 小物件、工具线索 |
| slate | 板岩 | stone | 山坡、河谷 | 地貌、建筑材料 |
| iron_ore | 铁矿 | metal_ore | 山地、矿脉 | 矿产、文明资源 |
| copper_ore | 铜矿 | metal_ore | 山地、丘陵 | 矿产、经济 |
| silver_ore | 银矿 | metal_ore | 山地、深层矿脉 | 稀有矿产 |
| clay | 黏土 | clay_soil | 河岸、湿地 | 陶土、泥地线索 |
| wet_mud | 湿泥 | clay_soil | 水边、雨后 | 脚印、痕迹 |
| sand | 沙 | sand_gravel | 河滩、荒地 | 地貌、通行 |
| gravel | 砾石 | sand_gravel | 河滩、山脚 | 地貌、道路 |
| salt_chunk | 盐块 | salt_mineral | 盐地、洞穴 | 食物保存、贸易 |
| salty_soil | 盐土 | salt_mineral | 荒地、干涸水边 | 资源线索 |
| dry_firewood | 干柴 | fuel | 森林、营地 | 燃料 |
| dead_branch_pile | 枯枝堆 | fuel | 林地、废墟 | 燃料、搜索产出 |
| peat | 泥炭 | fuel | 湿地 | 燃料 |
| coal | 煤 | fuel | 山地、矿脉 | 燃料、工业资源 |
| quartz_crystal | 水晶 | gem_crystal | 洞穴、山地 | 稀有资源、线索 |
| obsidian_shard | 黑曜石碎片 | gem_crystal | 火山性地貌 | 稀有资源、异常地貌 |
| bone_pile | 骨堆 | corpse_remain | 荒地、巢穴、战场 | 危险线索 |
| carrion | 腐肉 | corpse_remain | 腐败地、尸体附近 | 疾病、食腐动物 |
| hide_remain | 兽皮残骸 | corpse_remain | 捕猎点、巢穴 | 猎物线索 |
| blue_salt | 蓝盐 | abnormal_resource | 异常水源、盐地 | 异界资源 |
| whisper_stone | 低语石 | abnormal_resource | 遗迹、异常山地 | 精神压力、线索 |
| black_blood_crystal | 黑血结晶 | abnormal_resource | 魔物尸迹、腐败地 | 危险资源、线索 |

## 运行时生态实体

### CreaturePopulation

表示某个物种在一个或多个 chunk 内的稳定种群。

```json
{
  "id": "pop_wolf_north_slope_01",
  "species_id": "wolf",
  "region_id": "north_slope_wilds",
  "chunk_ids": ["chunk_north_slope_12_08_02", "chunk_north_slope_12_09_02"],
  "population_level": "small",
  "activity_cycle": "night",
  "pressure": "hungry",
  "visibility": "hidden"
}
```

规则：

```text
CreaturePopulation 不直接出现在可互动列表。
CreaturePopulation 用于生成痕迹、遭遇概率和 CreatureGroup。
```

### CreatureGroup

表示可移动、可追踪、可遭遇的一群生物。

```json
{
  "id": "group_wolf_pack_01",
  "species_id": "wolf",
  "population_id": "pop_wolf_north_slope_01",
  "count": 5,
  "location": {
    "scope": "world_chunk",
    "chunk_id": "chunk_north_slope_12_09_02",
    "local_position": "tree_line"
  },
  "behavior_state": "stalking",
  "visibility": "hinted",
  "signs": ["howl", "tracks"]
}
```

规则：

```text
CreatureGroup 必须有 location。
CreatureGroup 可被 observe/search/track 揭示。
CreatureGroup 靠近玩家、进入冲突、被驯服或成为剧情对象时，才能升级为 CreatureActor。
```

### CreatureActor

表示单个或具名动物/异兽。

```json
{
  "id": "creature_night_wolf_alpha_01",
  "species_id": "night_wolf",
  "name": "暗夜狼首领",
  "location": {
    "scope": "world_chunk",
    "chunk_id": "chunk_north_slope_12_09_02",
    "local_position": "ridge_shadow"
  },
  "state": {
    "injured": false,
    "hostile": true
  }
}
```

规则：

```text
CreatureActor 不是 WorldObject。
CreatureActor 的死亡、逃跑、驯服、追踪结果必须写事件。
死亡或采集成功后，resolver 可以生成 WorldObject，例如 meat、hide、bone。
```

### FloraPatch

表示一片植物生态。

```json
{
  "id": "flora_nightmare_grass_patch_01",
  "species_id": "nightmare_grass",
  "location": {
    "scope": "world_chunk",
    "chunk_id": "chunk_north_slope_12_08_02",
    "local_position": "shaded_slope"
  },
  "coverage": "sparse",
  "visibility": "hinted",
  "state": {
    "harvested": false,
    "season": "late_autumn"
  }
}
```

规则：

```text
FloraPatch 不是 WorldObject。
FloraPatch 可被 observe/search 揭示。
采集成功后，resolver 根据 PlantSpecies.harvest_outputs 生成 WorldObject。
```

### ResourceDeposit

表示矿脉、石料、盐土、干柴堆、骨堆等资源集合。

```json
{
  "id": "deposit_dry_firewood_01",
  "resource_id": "dry_firewood",
  "location": {
    "scope": "world_chunk",
    "chunk_id": "chunk_north_slope_12_08_02",
    "local_position": "under_pines"
  },
  "abundance": "small",
  "visibility": "visible",
  "state": {
    "depleted": false
  }
}
```

规则：

```text
ResourceDeposit 不等于玩家已获得资源。
采集或装水成功后，resolver 修改 deposit state 或生成 WorldObject。
```

### ResourceNode

表示可直接交互的单个资源点，例如泉眼、井、水洼。

```json
{
  "id": "node_spring_water_01",
  "resource_id": "spring_water",
  "location": {
    "scope": "world_chunk",
    "chunk_id": "chunk_north_slope_12_08_02",
    "local_position": "rock_crack"
  },
  "visibility": "visible",
  "state": {
    "quality": "clear",
    "depleted": false
  }
}
```

规则：

```text
ResourceNode 可作为 drink/refill_water/search 的目标。
给容器装水必须同时存在可交互 ResourceNode 和可用 container WorldObject。
```

## 字段说明

本节解释自然生态 catalog 和运行时生态实体的字段。生态实体不是 `WorldObject`；只有采集、狩猎、装水、挖掘等动作成功结算后，resolver 才能生成或修改 `WorldObject`。

### AnimalSpecies 字段

| 字段 | 含义 |
| --- | --- |
| `species_id` | 动物物种 ID，全局唯一。运行时种群和群体必须引用它。 |
| `name` | 物种显示名。 |
| `aliases` | 玩家自然语言可能使用的别名。用于观察、追踪和目标绑定。 |
| `category` | 动物分类，必须属于动物分类闭集。 |
| `habitat_tags` | 适宜生态标签。用于根据 `biome_tags` 和 `climate_tags` 匹配生成候选。 |
| `terrain_tags` | 适宜地形标签。用于根据 chunk 地形匹配生成候选。 |
| `activity_cycle` | 活动周期，例如 day、night、dusk。影响遭遇和痕迹刷新。 |
| `diet` | 食性，例如 herbivore、carnivore、omnivore。用于生态合理性校验。 |
| `sociality` | 社会性，例如 solitary、pair、pack、herd。影响 CreatureGroup 数量。 |
| `danger_level` | 生态危险等级。它不是战斗数值，只影响风险、遭遇和 DM 反馈。 |
| `sign_tags` | 该物种可能留下的痕迹，例如足迹、叫声、毛发、尸骸。 |
| `population_rules` | 种群生成规则。 |
| `population_rules.min_group_size` | 单个群体最小数量。 |
| `population_rules.max_group_size` | 单个群体最大数量。 |
| `population_rules.rarity` | 生成稀有度。 |
| `harvest_outputs` | 狩猎、尸体处理或采集成功后可能产生的 WorldObject 模板片段。 |
| `harvest_outputs[].object_type` | 产出对象的 `WorldObject.object_type`。 |
| `harvest_outputs[].name` | 产出对象显示名。 |
| `harvest_outputs[].tags` | 产出对象辅助标签。 |

### PlantSpecies 字段

| 字段 | 含义 |
| --- | --- |
| `species_id` | 植物物种 ID，全局唯一。FloraPatch 必须引用它。 |
| `name` | 植物显示名。 |
| `aliases` | 玩家可能使用的别名。 |
| `category` | 植物分类，必须属于植物分类闭集。 |
| `habitat_tags` | 适宜生态标签。 |
| `terrain_tags` | 适宜地形标签。 |
| `growth_form` | 生长形态，例如单株、片区、藤蔓、菌簇。影响投影和叙事。 |
| `visibility` | 默认可见性，例如 visible、hinted、hidden。 |
| `rarity` | 生成稀有度。 |
| `risk_tags` | 采集或误认风险标签。 |
| `harvest_outputs` | 采集成功后可能产生的 WorldObject 模板片段。 |
| `harvest_outputs[].object_type` | 产出对象的规则类型。 |
| `harvest_outputs[].name` | 产出对象显示名。 |
| `harvest_outputs[].tags` | 产出对象辅助标签。 |

### NaturalResource 字段

| 字段 | 含义 |
| --- | --- |
| `resource_id` | 自然资源 ID，全局唯一。ResourceDeposit 和 ResourceNode 必须引用它。 |
| `name` | 资源显示名。 |
| `aliases` | 玩家可能使用的别名。 |
| `category` | 资源分类，例如 water、ore、stone、fuel、clay。 |
| `terrain_tags` | 支持该资源形成的地形标签。 |
| `deposit_kind` | 运行时承载形态：`resource_deposit` 表示资源集合，`resource_node` 表示可直接交互点。 |
| `renewability` | 是否会自然恢复，例如 renewable、limited、nonrenewable。 |
| `visibility` | 默认可见性。 |
| `access_rules` | 获取或使用该资源的条件。 |
| `access_rules.requires_tool` | 是否需要工具。 |
| `access_rules.requires_container` | 是否需要容器。 |
| `extraction_outputs` | 提取、装水、挖掘或采集成功后的输出规则。 |
| `extraction_outputs[].operation` | 触发的操作类型，例如 refill_water。 |
| `extraction_outputs[].target_object_type` | 操作目标需要的 WorldObject 类型。 |
| `extraction_outputs[].resource_type` | 被提取的资源类别。 |

### CreaturePopulation 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 种群实例 ID。 |
| `species_id` | 引用的 AnimalSpecies。 |
| `region_id` | 种群所在 Region。 |
| `chunk_ids` | 种群活动范围覆盖的 chunk。 |
| `population_level` | 种群规模分级，例如 small、medium、large。 |
| `activity_cycle` | 当前种群活动周期，默认来自 AnimalSpecies，可被季节或事件修正。 |
| `pressure` | 种群状态压力，例如 hungry、migrating、territorial。 |
| `visibility` | 玩家对该种群的认知状态。种群通常不直接进入可互动列表。 |

### CreatureGroup 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 可移动群体 ID。 |
| `species_id` | 引用的 AnimalSpecies。 |
| `population_id` | 来源 CreaturePopulation。 |
| `count` | 群体数量。 |
| `location` | 群体当前位置。结构遵循地点/空间规则中的 ActorLocation location 字段。 |
| `location.scope` | 位置范围，例如 world_chunk 或 site_node。 |
| `location.chunk_id` | 外部位置所在 chunk。 |
| `location.local_position` | chunk 内粗略位置。 |
| `behavior_state` | 当前行为状态，例如 stalking、foraging、fleeing。 |
| `visibility` | 玩家对该群体的可见性。 |
| `signs` | 玩家可感知或已发现的痕迹。 |

### CreatureActor 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 单个或具名生物 ID。 |
| `species_id` | 引用的 AnimalSpecies。 |
| `name` | 具名生物显示名。 |
| `location` | 当前位置，结构遵循地点/空间规则。 |
| `state` | 单体状态。 |
| `state.injured` | 是否受伤。 |
| `state.hostile` | 当前是否敌对。 |

### FloraPatch 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 植物片区 ID。 |
| `species_id` | 引用的 PlantSpecies。 |
| `location` | 片区位置，结构遵循地点/空间规则。 |
| `coverage` | 覆盖程度，例如 sparse、moderate、dense。 |
| `visibility` | 玩家对该植物片区的可见性。 |
| `state` | 片区运行时状态。 |
| `state.harvested` | 是否已被采集。 |
| `state.season` | 当前季节状态，用于判断可采集性和描述。 |

### ResourceDeposit 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 资源集合 ID。 |
| `resource_id` | 引用的 NaturalResource。 |
| `location` | 资源集合位置，结构遵循地点/空间规则。 |
| `abundance` | 资源丰度，例如 small、medium、large。 |
| `visibility` | 玩家对资源集合的可见性。 |
| `state` | 资源集合运行时状态。 |
| `state.depleted` | 是否已耗尽。 |

### ResourceNode 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 可直接交互资源点 ID。 |
| `resource_id` | 引用的 NaturalResource。 |
| `location` | 资源点位置，结构遵循地点/空间规则。 |
| `visibility` | 玩家对资源点的可见性。 |
| `state` | 资源点运行时状态。 |
| `state.quality` | 资源质量，例如 clear、stagnant、polluted、unknown。 |
| `state.depleted` | 是否暂时或永久耗尽。 |

### 世界生成输入字段

| 字段 | 含义 |
| --- | --- |
| `terrain_tags` | 来自 WorldChunk terrain 的地形辅助标签。 |
| `climate_tags` | 来自 Region climate_profile 的气候辅助标签。 |
| `water_presence` | 来自 WorldChunk terrain 的水体存在形态。 |
| `civilization_pressure` | 来自 base_fields 的文明压力。实现中应使用数值，示例中的 low/medium/high 只是可读分级。 |
| `danger_tags` | 来自 Region 或 chunk 的危险倾向标签。 |
| `biome_tags` | 由气候地形形成规则推导的生态标签。 |

## 与 WorldObject 的转换关系

生态实体不会自动进入物品系统。只有以下行为成功结算后，才会生成或修改 `WorldObject`：

| 行为 | 输入 | 输出 |
| --- | --- | --- |
| gather | FloraPatch / ResourceDeposit | `WorldObject(resource/food/material)` |
| hunt | CreatureGroup / CreatureActor | `WorldObject(food/material)` 或逃跑/受伤事件 |
| fish | fish 类 CreaturePopulation / ResourceNode | `WorldObject(food)` |
| refill_water | ResourceNode + container WorldObject | 修改 `components.container.contents` |
| collect_firewood | ResourceDeposit | `WorldObject(resource)` |
| mine | ResourceDeposit | `WorldObject(material)` |
| inspect_trace | CreatureGroup / ResourceDeposit / FloraPatch | `clue` 或 revealed state |

转换规则：

```text
转换必须由 deterministic resolver 执行。
转换必须写 EventLog。
转换结果必须经过 WorldObjectValidator。
生态实体 state 必须同步更新，例如 harvested/depleted/disturbed。
DM 不能通过叙事直接把生态产物加入玩家物品栏。
```

## 世界生成使用规则

每个 `WorldChunk` 应至少具备自然生成输入：

```json
{
  "terrain_tags": ["forest", "slope"],
  "climate_tags": ["cold", "wet"],
  "water_presence": "nearby",
  "civilization_pressure": "low",
  "danger_tags": ["predator", "monster_trace"],
  "biome_tags": ["north_slope_forest"]
}
```

生成器按以下顺序应用自然生态：

```text
1. 根据 terrain_tags / climate_tags / biome_tags 选择候选动物、植物、资源。
2. 根据 water_presence 加入水源、水生植物、鱼类和湿地资源。
3. 根据 civilization_pressure 加入 livestock、井水、干柴、农作物、道路边资源。
4. 根据 danger_tags 加入 predator、scavenger、abnormal_beast、abnormal_flora、corpse_remain。
5. 根据 rarity 和 abundance 生成 CreaturePopulation、FloraPatch、ResourceDeposit。
6. 根据当前 Site/LocationNode 需要投影少量可互动生态目标。
7. 运行 Validator，拒绝不符合空间、地形或规则的生态实体。
```

示例映射：

| 地形组合 | 推荐生成 |
| --- | --- |
| forest + slope + cold | 松树、桦树、野兔、鹿、狼、泉眼、燧石、枯枝堆 |
| valley + water | 溪流、河鱼、泥鳅、芦苇、水草、湿泥、黏土、砾石 |
| town + civilized | 井水、鸡、羊、马、干柴、亚麻、粮食相关资源 |
| ruin + damp | 灰蘑菇、荧光菌、骨堆、腐肉、水洼、低语石 |
| forest + monster_trace | 暗夜狼、腐皮鹿、梦魇草、夜光苔、黑血结晶 |

## Validator 规则

实现时必须加入自然生态 validator，保证：

1. `AnimalSpecies.species_id`、`PlantSpecies.species_id`、`NaturalResource.resource_id` 全局唯一。
2. 所有 category 必须属于对应闭集。
3. `CreaturePopulation.species_id` 必须引用存在的 AnimalSpecies。
4. `CreatureGroup.species_id` 必须引用存在的 AnimalSpecies。
5. `FloraPatch.species_id` 必须引用存在的 PlantSpecies。
6. `ResourceDeposit.resource_id` 和 `ResourceNode.resource_id` 必须引用存在的 NaturalResource。
7. 所有运行时生态实体必须有可解析 location。
8. 生态实体 location 必须引用存在的 chunk、node 或 zone。
9. 生态实体不能通过 description 暗示未落库的可采集产物。
10. 动物、植物、自然资源 catalog 不得直接写入玩家 inventory。
11. 采集、狩猎、捕鱼、装水产物必须经过 resolver 和 WorldObjectValidator。
12. 生物群、植物片区、资源点被采集或惊动后，必须更新 state 或写事件。
13. 生成器不能在不匹配地形的 chunk 中生成资源，除非有明确异常标签。
14. `abnormal_beast`、`abnormal_flora`、`abnormal_resource` 必须需要危险、异常、遗迹或魔物痕迹标签支持。
15. 水源类 ResourceNode 必须声明 quality 或由 resolver 在首次观察时确定 quality。

## 与现有文档关系

本设计依赖：

- [地点与空间规则](./2026-07-10-isekai-location-space-rules-design.md)
- [气候、地形、生物群系与天气形成规则](./2026-07-11-isekai-climate-terrain-formation-rules-design.md)
- [WorldObject 规则](./2026-07-10-isekai-world-object-rules-design.md)

关系如下：

```text
Natural Ecology Catalog
-> CreaturePopulation / FloraPatch / ResourceDeposit
-> SpaceProjectionService
-> Player Action
-> Deterministic Resolver
-> WorldObject / EventLog / Updated Ecology State
```

## 架构决策

1. 动物、植物、非生命自然资源先作为生态 catalog 存在。
2. 生态 catalog 不等于运行时事实。
3. 运行时生态实体必须进入 `WorldState` 并有空间位置。
4. 动物优先用种群和群体表示，不默认实例化为单个 Actor。
5. 植物优先用片区表示，不默认实例化为单个 WorldObject。
6. 非生命自然资源优先用资源点或资源藏表示。
7. 生态产物必须通过 resolver 转换为 `WorldObject`。
8. 世界生成必须根据地形、气候、水源、文明压力和危险标签生成生态。
9. AI 可以提出生态候选，但不能直接把生态候选写成最终事实。
10. 最终事实以权威 `WorldState`、Validator、Resolver 和 EventLog 为准。
