# 异世界模式地点与空间规则设计

## 背景

当前异世界模式的主要一致性问题不是 DM 文本不够丰富，而是世界状态缺少稳定空间模型：

- 玩家已经进入某个地点，界面和后端仍可能显示上一个地点的对象。
- DM 旁白提到柜台、钥匙、后厨门、马车破口，但这些对象没有明确位置。
- 玩家问“这里有什么”时，系统容易让模型从文本里猜，而不是从世界状态查询。
- 玩家尝试进入、靠近、搜索、拾取时，目标可能被当成地点、区域、物品或泛化环境，导致结算不一致。
- 野外和城镇外部缺少粗粒度坐标，导致“猎人小屋离玩家多远”“狼群在附近还是很远”“两个相邻区域能不能直接走过去”无法确定性回答。

本设计将地点/空间从模糊字符串改成可查询、可校验、可投影的权威状态。它借鉴《矮人要塞》的核心原则：世界先存在，行为在世界上结算，叙事只是世界状态的投影。但本项目不复刻 DF 的 tile 级模拟，而采用适合文字 DM 的粗粒度 xyz 区块。

## 总体方案

外部世界使用粗粒度 `WorldChunk(x, y, z)` 表示。一个 chunk 是野外、城镇街区、村庄边缘、山脊、河谷等外部空间的最小定位单位。进入具体建筑、洞穴、马车、房间后，再切换到 `Site -> LocationNode -> Zone` 的局部空间模型。

```text
World
-> Region
   -> WorldChunkGrid
      -> WorldChunk
         -> Site
            -> LocationNode
               -> Zone
                  -> ObjectPlacement
      -> ChunkEdge
      -> RegionFeature / Settlement / TerrainFeature
      -> CreatureGroup
```

核心规则：

```text
WorldChunk 是外部空间的基本单位。
LocationNode/Zone 是进入 Site 后的内部空间单位。
Site 必须挂在 WorldChunk 上。
村庄、城镇、山脊、河谷是一组 WorldChunk，不是单个模糊字符串。
相邻 chunk 只表示物理接壤，能不能通行必须看 ChunkEdge。
```

## 目标

- 建立一套权威空间模型：`World -> Region -> WorldChunk -> Site -> LocationNode -> Zone`。
- 用 `WorldChunk.coord(x, y, z)` 表示外部空间粗坐标。
- 用 `ChunkEdge` 表示 chunk 之间的通行关系、耗时、风险和阻挡原因。
- 用 `LocationEdge` 表示 Site 内部或相邻 LocationNode 之间的通行关系。
- 用 `ObjectPlacement` 表示物体、NPC、设施、门、容器、线索在空间中的具体位置。
- 让“当前空间有什么”“能去哪里”“离目标多远”“附近有什么生物”全部来自确定性空间投影查询。
- 让 DM 旁白、UI 可互动列表、动作目标绑定共用同一份空间投影结果。
- 允许 LLM 提出 chunk、site、对象和空间关系，但必须经过后端 validator 后才进入权威世界状态。

## 非目标

- 不实现 DF 式小 tile、液体流动、逐格寻路和完整物理模拟。
- 不让一个 chunk 变成黑箱，塞入多个完整 site 却不描述彼此关系。
- 不把每个“旁边、角落、背后、左侧”都升格成空间层级。
- 不让 LLM 直接创建最终地点、移动玩家、发放物品或修改资源。
- 不通过硬编码具体地点名、物品名、NPC 名来解决空间一致性。
- 不要求本阶段重建数据库表；第一阶段可继续存入 `world_state_json`。

## 核心原则

### 1. 世界状态是唯一事实源

DM 可以描述世界，但不能让描述本身成为事实。最终 DM 旁白中出现的当前可见对象、地点入口、NPC、可拾取物、附近生物和可通行方向，必须已经存在于权威世界状态，或在本轮通过 validator 后写入状态。

### 2. 粗区块回答“外部空间在哪里”

野外、村庄、城镇街区、山脊、河谷、道路、断崖、溪流等外部空间，必须落到 `WorldChunk(x, y, z)` 上。玩家和生物在外部世界的位置不能只写成“北坡荒野”或“灰石镇附近”。

### 3. Site 必须挂在 chunk 上

`Site` 不能直接挂在 `Region` 上。猎人小屋、旧炉旅店、铁匠铺、废弃马车、冷溪取水点都必须有 `parent_chunk_id`。

```text
猎人小屋 -> chunk_north_slope_12_08_02 -> 北坡荒野
旧炉旅店 -> chunk_graystone_10_10_0 -> 灰石镇区域
```

### 4. 相邻不等于可通行

两个 chunk 坐标相邻，只表示物理接壤。能不能走、需要多久、有什么风险，必须由 `ChunkEdge.passability` 和 `ChunkEdge.traversal` 决定。

例如：

```text
城镇街道 chunk -> 城镇街道 chunk：可通行
平原 chunk -> 森林 chunk：可通行但耗时增加
平原 chunk -> 断崖 chunk：直接阻挡
山脊 chunk -> 下方谷地 chunk：需要路径、攀爬能力或绕路
```

### 5. 一个 chunk 默认只能承载一个完整主 Site

一个 `WorldChunk` 至少要大到能容纳一个最小可进入 `Site`。默认一个 chunk 只能有一个 `primary_site`。

如果一个 chunk 内存在多个 site，必须显式定义 `site_relations`。没有 `site_relations` 的多个 site 必须被 validator 拒绝。

### 6. 地点层级回答“属于哪里”

`parent_id` 只表达归属关系，例如：

```text
前厅 属于 旧炉旅店
旧炉旅店 属于 chunk_graystone_10_10_0
chunk_graystone_10_10_0 属于 灰石镇区域
```

归属关系不表示玩家可以直接移动。

### 7. 地点边回答“能去哪里”

玩家从当前内部地点能否去另一个内部地点，必须由 `LocationEdge` 决定。门、楼梯、破口、地窖口等连接实体必须建成 `portal` 对象，并由 `LocationEdge.portal_object_id` 引用。

### 8. 对象不属于地点层级

对象通过 `ObjectPlacement` 挂载到 chunk、zone、其他对象、角色身上或玩家物品栏。对象可以递归挂载，但最终必须能追溯到一个 `WorldChunk` 或 `LocationNode + Zone`，除非它在玩家背包、角色携带、远处传闻或已移除状态。

### 9. 细节由 Placement 和 Relation 表达

更细的空间描述，例如“柜台后”“酒桶旁”“破毯子下面”“车厢破口边”，优先通过以下结构表达：

- `Zone`
- `local_position`
- `ObjectPlacement`
- `SpatialRelation`
- `access_sides`
- `visibility`
- `reachability`

不要把每个局部描述都新建成 `LocationNode` 或 `WorldChunk`。

## 空间层级

第一阶段固定使用以下结构：

```text
World
-> Region
   -> WorldChunk
      -> Site
         -> LocationNode
            -> Zone
               -> Object
```

横向关系：

```text
WorldChunk <-> ChunkEdge <-> WorldChunk
LocationNode <-> LocationEdge <-> LocationNode
RegionFeature / Settlement / TerrainFeature -> chunk_ids[]
```

### 层级职责

| 层级 | 职责 | 示例 |
| --- | --- | --- |
| World | 一局冒险的世界容器、随机种子、内容包加载范围 | 当前异世界 |
| Region | 大区域规则、气候、生态、势力、总体风险 | 灰石镇周边、北坡荒野 |
| WorldChunk | 外部空间最小定位单位，带 xyz、尺寸、地形、通行边界 | 城镇街角、山脊区块、溪谷区块 |
| Site | chunk 上可进入或可交互的具体地点 | 旧炉旅店、铁匠铺、猎人小屋、废弃马车 |
| LocationNode | 进入 Site 后可进入/停留/切换场景的实际空间 | 前厅、后厨、小屋外、小屋内、车厢边 |
| Zone | LocationNode 内部局部区域，支持靠近、观察、搜索和权限 | 柜台区、炉火旁、黑暗角落、破口边 |
| Object | 物品、NPC、门、容器、线索、固定物 | 柜台、炖菜、后厨门、捕兽夹 |

### Chunk 尺寸

第一阶段采用固定尺寸 profile，避免每个 chunk 自定义尺寸导致距离和路径复杂化。

```text
town_50m: 50m x 50m，z_step 5m
wilderness_100m: 100m x 100m，z_step 20m
```

推荐默认：

```text
城镇、村庄：town_50m
野外、山地、河谷、森林：wilderness_100m
室内：不使用 WorldChunk，进入 Site 后使用 LocationNode/Zone
```

一个 chunk 必须至少能容纳一个最小可进入 site 加周边活动空间。完整建筑和重要资源点默认占据一个 primary chunk。

### 显示路径不是权威层级

如果需要展示更长背景，例如“旧王国边境 / 灰石镇辖区 / 西街区 / 旧炉旅店 / 前厅”，使用 `display_path`：

```json
{
  "id": "old_furnace_inn_front_hall",
  "name": "旧炉旅店前厅",
  "type": "interior_room",
  "parent_id": "old_furnace_inn",
  "display_path": ["旧王国边境", "灰石镇", "旧炉旅店", "前厅"]
}
```

`display_path` 只用于叙事和 UI 展示，不参与移动、可达性、对象查询和状态结算。

### Region 与 WorldChunkGrid 边界

`Region` 必须定义世界坐标边界，`WorldChunkGrid` 必须定义 chunk 坐标边界。两者职责不同：

```text
Region.bounds_world：这个区域在世界米制坐标里占多大。
WorldChunkGrid.bounds_chunk：这个区域内允许哪些 chunk 坐标存在。
```

`Region` 是地理、生态、势力和风险区域。`WorldChunkGrid` 是该 Region 的离散坐标尺。`WorldChunk` 必须落在某个 grid 的边界内。

## 数据模型

### World

```json
{
  "id": "isekai_world_001",
  "name": "当前异世界",
  "seed": "adv_10_seed",
  "active_content_pack_ids": ["old_furnace_inn_p1"],
  "chunk_size_profiles": {
    "town_50m": {
      "width_meters": 50,
      "height_meters": 50,
      "z_step_meters": 5
    },
    "wilderness_100m": {
      "width_meters": 100,
      "height_meters": 100,
      "z_step_meters": 20
    }
  },
  "current_actor_locations": {
    "player": {
      "scope": "site_node",
      "site_id": "old_furnace_inn",
      "node_id": "old_furnace_inn_front_hall",
      "zone_id": "entrance"
    }
  }
}
```

### Region

```json
{
  "id": "north_slope_wilds",
  "name": "北坡荒野",
  "type": "wilderness_region",
  "world_id": "isekai_world_001",
  "bounds_world": {
    "origin_meters": { "x": 0, "y": 0 },
    "min_meters": { "x": 0, "y": 0 },
    "max_meters": { "x": 5000, "y": 4000 },
    "z_range": { "min": 0, "max": 8 }
  },
  "grid_id": "grid_north_slope_wilds",
  "climate": {
    "temperature": "cold",
    "rainfall": "moderate",
    "season": "late_autumn"
  },
  "ecology": {
    "dominant_biomes": ["pine_forest", "rocky_ridge", "cold_stream"],
    "common_threats": ["night_wolf", "parasite_carrion"]
  },
  "factions": [
    {
      "id": "graystone_hunters",
      "influence": "low"
    }
  ],
  "risk_clocks": {
    "night_wolf_activity": {
      "value": 2,
      "max": 6
    }
  }
}
```

### WorldChunkGrid

`WorldChunkGrid` 表示某个 Region 内部的离散区块坐标系。它不是地点，也不是地貌本身，而是该区域的地图网格规则。

```json
{
  "id": "grid_north_slope_wilds",
  "region_id": "north_slope_wilds",
  "size_profile": "wilderness_100m",
  "origin_chunk": { "x": 0, "y": 0, "z": 0 },
  "bounds_chunk": {
    "min": { "x": 0, "y": 0, "z": 0 },
    "max": { "x": 49, "y": 39, "z": 8 }
  }
}
```

它回答：

```text
这个 Region 切成多大的格子？
chunk 坐标从哪里到哪里？
一个 chunk 的物理尺寸是多少？
某个 chunk 坐标的有效性。
两个 chunk 的网格归属。
```

### WorldChunk

`WorldChunk` 是外部世界的基本定位单位。

```json
{
  "id": "chunk_north_slope_12_08_02",
  "grid_id": "grid_north_slope_wilds",
  "region_id": "north_slope_wilds",
  "coord": {
    "x": 12,
    "y": 8,
    "z": 2
  },
  "size_profile": "wilderness_100m",
  "terrain": {
    "primary": "rocky_ridge",
    "secondary": ["thin_pines", "loose_stone"],
    "slope": "steep",
    "ground": "unstable"
  },
  "environment": {
    "visibility": "wide",
    "cover": "sparse",
    "water": "none",
    "light": "dusk"
  },
  "site_slots": {
    "primary_site_id": "hunter_cabin_01",
    "secondary_site_ids": []
  },
  "known_to_player": true,
  "tags": ["ridge", "outdoor", "wind_exposed"]
}
```

### ChunkEdge

`ChunkEdge` 是 chunk 之间移动关系的权威数据。坐标相邻不能自动推导可通行。

```json
{
  "id": "edge_chunk_12_08_02_to_13_08_02",
  "source_chunk_id": "chunk_north_slope_12_08_02",
  "target_chunk_id": "chunk_north_slope_13_08_02",
  "direction": "east",
  "adjacent": true,
  "passability": {
    "state": "blocked",
    "blocked_reason": "东侧是断崖，不能直接通行"
  },
  "traversal": {
    "base_time_minutes": null,
    "difficulty": "impassable",
    "movement_type": "walk",
    "risk_tags": ["fall"]
  },
  "visibility": {
    "known_to_player": true,
    "line_of_sight": true,
    "description": "东侧地面忽然断开，岩壁直落进雾里"
  }
}
```

可通行示例：

```json
{
  "id": "edge_chunk_11_08_02_to_12_08_02",
  "source_chunk_id": "chunk_north_slope_11_08_02",
  "target_chunk_id": "chunk_north_slope_12_08_02",
  "direction": "east",
  "adjacent": true,
  "passability": {
    "state": "open"
  },
  "traversal": {
    "base_time_minutes": 8,
    "difficulty": "moderate",
    "movement_type": "walk",
    "risk_tags": ["loose_stone", "wolf_scent"]
  },
  "visibility": {
    "known_to_player": true,
    "line_of_sight": true,
    "description": "猎人小屋在东侧稀疏松林后，沿脊线走过去约十分钟"
  }
}
```

### RegionFeature / Settlement / TerrainFeature

村庄、城镇、山脊、河谷、森林等不是单个空间点，而是一组 chunk 的集合。

```json
{
  "id": "north_slope_ridge_feature",
  "name": "北坡脊线",
  "type": "terrain_feature",
  "region_id": "north_slope_wilds",
  "chunk_ids": [
    "chunk_north_slope_11_08_02",
    "chunk_north_slope_12_08_02",
    "chunk_north_slope_13_08_02"
  ],
  "dominant_terrain": "rocky_ridge",
  "known_to_player": true
}
```

```json
{
  "id": "graystone_town",
  "name": "灰石镇",
  "type": "settlement",
  "region_id": "graystone_town_region",
  "chunk_ids": [
    "chunk_graystone_10_10_0",
    "chunk_graystone_11_10_0",
    "chunk_graystone_10_11_0",
    "chunk_graystone_11_11_0"
  ],
  "entry_chunk_ids": ["chunk_graystone_10_10_0"],
  "known_to_player": true
}
```

### Site

`Site` 必须挂在 `WorldChunk` 上。`region_id` 可作为查询索引，但真正空间父级是 `parent_chunk_id`。

```json
{
  "id": "hunter_cabin_01",
  "name": "猎人小屋",
  "type": "shelter_site",
  "parent_chunk_id": "chunk_north_slope_12_08_02",
  "local_position": "east_edge",
  "footprint": {
    "width_meters": 12,
    "height_meters": 8
  },
  "entry_node_ids": ["hunter_cabin_outside"],
  "tags": ["shelter", "abandoned"],
  "state": {
    "known_to_player": true,
    "enterable": true
  }
}
```

城镇示例：

```json
{
  "id": "old_furnace_inn",
  "name": "旧炉旅店",
  "type": "inn",
  "parent_chunk_id": "chunk_graystone_10_10_0",
  "local_position": "center",
  "footprint": {
    "width_meters": 28,
    "height_meters": 22
  },
  "entry_node_ids": ["old_furnace_inn_front_hall"],
  "tags": ["facility", "merchant", "shelter"],
  "state": {
    "open": true,
    "curfew_sensitive": true
  }
}
```

### Chunk 内多个 Site

默认一个 chunk 只能有一个 `primary_site`。允许 `secondary_site` 仅限两类：

```text
微型附属 site：井、告示牌、路边摊、马槽、路标。
复合 site 的附属设施：旅店后院水井、旅店院内马厩、铁匠铺外煤棚。
```

只要一个 chunk 内出现多个 site，就必须定义 `site_relations`：

```json
{
  "chunk_id": "chunk_graystone_10_10_0",
  "primary_site_id": "old_furnace_inn",
  "secondary_site_ids": ["inn_well_01", "notice_board_01"],
  "site_relations": [
    {
      "source_site_id": "old_furnace_inn",
      "target_site_id": "inn_well_01",
      "relation": "behind",
      "distance_meters": 18,
      "base_time_minutes": 1,
      "visibility": "visible_from_front_yard",
      "passability": "open"
    },
    {
      "source_site_id": "old_furnace_inn",
      "target_site_id": "notice_board_01",
      "relation": "across_street",
      "distance_meters": 25,
      "base_time_minutes": 1,
      "visibility": "visible_from_front_door",
      "passability": "open"
    }
  ]
}
```

两个完整可进入建筑不能放在同一个 chunk。旧炉旅店和铁匠铺必须拆成相邻 chunk，并用 `ChunkEdge` 表示街道连接。

### LocationNode

```json
{
  "id": "old_furnace_inn_front_hall",
  "name": "旧炉旅店前厅",
  "type": "interior_room",
  "site_id": "old_furnace_inn",
  "parent_id": "old_furnace_inn",
  "display_path": ["灰石镇", "旧炉旅店", "前厅"],
  "zones": [
    {
      "id": "entrance",
      "name": "门口",
      "type": "threshold"
    },
    {
      "id": "front_counter_area",
      "name": "柜台区",
      "type": "service_area"
    },
    {
      "id": "behind_counter",
      "name": "柜台后",
      "type": "staff_area",
      "access": {
        "state": "restricted",
        "requires": ["innkeeper_allows_counter_access"],
        "blocked_reason": "店主还在柜台后盯着你"
      }
    },
    {
      "id": "hearth_side",
      "name": "炉火旁",
      "type": "rest_area"
    }
  ],
  "environment": {
    "light": "dim",
    "noise": "low",
    "crowding": "sparse"
  },
  "tags": ["indoor", "public_area"]
}
```

### LocationEdge

`LocationEdge` 是 Site 内部或相邻 `LocationNode` 之间通行关系的权威数据。

```json
{
  "id": "edge_front_hall_to_kitchen",
  "source_node_id": "old_furnace_inn_front_hall",
  "target_node_id": "old_furnace_inn_kitchen",
  "relation": "doorway",
  "portal_object_id": "kitchen_door_01",
  "direction": "bidirectional",
  "passability": {
    "state": "conditional",
    "conditions": [
      {
        "type": "permission",
        "required": "innkeeper_allows_kitchen_access"
      }
    ],
    "blocked_reason": "店主没有允许你进入后厨"
  },
  "traversal": {
    "base_time_minutes": 2,
    "scope": "indoor",
    "movement_type": "walk",
    "risk_delta": 0
  },
  "visibility": {
    "known_to_player": true,
    "visible_from_source": true,
    "visible_from_target": true,
    "hint_text": "柜台侧后方有一扇通往后厨的门"
  }
}
```

### Portal Object

门、楼梯、破口、道路、地窖口必须也是对象：

```json
{
  "id": "kitchen_door_01",
  "name": "后厨门",
  "type": "portal",
  "placement": {
    "kind": "zone",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "front_counter_area",
    "local_position": "behind_counter_side",
    "relation": "at_edge",
    "visibility": "visible",
    "reachability": "reachable"
  },
  "affordances": ["observe", "enter", "knock"]
}
```

### ObjectPlacement

每个对象同一时间只能有一种权威位置。

允许的 `placement.kind`：

| kind | 含义 |
| --- | --- |
| chunk | 直接位于某个 `WorldChunk` 的局部位置 |
| zone | 直接位于某个 `LocationNode` 的某个 `Zone` |
| on_object | 放在某个对象上 |
| inside_object | 在容器、房间内对象、包裹或抽屉里 |
| under_object | 在某对象下方 |
| attached_to_object | 挂在、钉在、绑在某对象上 |
| near_object | 在某对象旁边；只表达局部关系，不创建新地点 |
| carried_by_actor | 被 NPC、怪物或其他角色携带 |
| player_inventory | 在玩家物品栏 |
| offscreen | 已知但不在当前可查询空间 |
| removed | 已被消耗、销毁、带走或不再存在 |

固定物示例：

```json
{
  "id": "counter_01",
  "name": "旧木柜台",
  "type": "fixture",
  "placement": {
    "kind": "zone",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "front_counter_area",
    "local_position": "north_side",
    "relation": "occupies",
    "visibility": "visible",
    "reachability": "partially_reachable"
  },
  "spatial": {
    "fixed": true,
    "size": "large",
    "access_sides": ["customer_side", "staff_side"],
    "blocks_movement": true
  },
  "affordances": ["observe", "place_item", "search_if_allowed"]
}
```

外部对象示例：

```json
{
  "id": "ridge_warning_post_01",
  "name": "歪斜的警示木牌",
  "type": "clue",
  "placement": {
    "kind": "chunk",
    "chunk_id": "chunk_north_slope_12_08_02",
    "local_position": "west_edge",
    "relation": "standing",
    "visibility": "visible",
    "reachability": "reachable"
  },
  "affordances": ["observe", "read"]
}
```

小物件示例：

```json
{
  "id": "stew_bowl_01",
  "name": "热炖菜一碗",
  "type": "food",
  "placement": {
    "kind": "on_object",
    "object_id": "counter_01",
    "surface": "customer_side",
    "relation": "on",
    "visibility": "visible",
    "reachability": "reachable"
  },
  "ownership": {
    "owner_actor_id": "innkeeper_01",
    "requires_purchase": true
  },
  "affordances": ["observe", "purchase", "eat_meal"]
}
```

### Actor Location

角色位置使用统一结构。外部世界位置：

```json
{
  "actor_id": "player",
  "location": {
    "scope": "world_chunk",
    "region_id": "north_slope_wilds",
    "chunk_id": "chunk_north_slope_12_08_02",
    "local_position": "center"
  }
}
```

进入 Site 后的位置：

```json
{
  "actor_id": "player",
  "location": {
    "scope": "site_node",
    "site_id": "old_furnace_inn",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "entrance"
  }
}
```

离开 Site 后，回到 Site 所在 chunk：

```json
{
  "actor_id": "player",
  "location": {
    "scope": "world_chunk",
    "region_id": "graystone_town_region",
    "chunk_id": "chunk_graystone_10_10_0",
    "local_position": "near_site:old_furnace_inn"
  }
}
```

### CreatureGroup

生物和 NPC 群体也使用 chunk 或 node/zone 定位。敌对和非敌对生物使用同一套位置结构，区别在 `disposition` 和 `behavior`。

```json
{
  "id": "night_wolf_pack_01",
  "name": "暗夜狼群",
  "type": "creature_group",
  "disposition": "hostile",
  "species": "night_wolf",
  "count": 3,
  "location": {
    "scope": "world_chunk",
    "region_id": "north_slope_wilds",
    "chunk_id": "chunk_north_slope_13_08_02",
    "local_position": "west_edge"
  },
  "visibility": {
    "state": "unseen",
    "known_to_player": false,
    "last_known_chunk_id": null,
    "confidence": 0.0,
    "signs": []
  },
  "behavior": {
    "state": "hunting",
    "movement_intent": "patrol",
    "route_chunk_ids": [
      "chunk_north_slope_13_08_02",
      "chunk_north_slope_12_08_02",
      "chunk_north_slope_12_09_02"
    ],
    "aggression": "stalking"
  }
}
```

## 空间不变量

实现时必须加入 validator，保证以下规则成立：

1. 外部空间权威层级为 `World -> Region -> WorldChunk -> Site`。
2. 内部空间权威层级为 `Site -> LocationNode -> Zone`。
3. `Region.bounds_world` 必须存在，并且 `max_meters` 大于 `min_meters`。
4. `Region.grid_id` 必须引用属于该 Region 的 `WorldChunkGrid`。
5. `WorldChunkGrid.size_profile` 必须引用已定义尺寸 profile。
6. `WorldChunkGrid.bounds_chunk` 必须能被 `Region.bounds_world` 和 size profile 容纳。
7. `WorldChunk.grid_id` 必须引用存在的 `WorldChunkGrid`。
8. `WorldChunk.region_id` 必须等于其 grid 所属 Region。
9. `WorldChunk.coord(x,y,z)` 必须落在 `WorldChunkGrid.bounds_chunk` 内。
10. `WorldChunk.coord(x,y,z)` 在同一 grid 内唯一。
11. `WorldChunk.size_profile` 必须等于所属 grid 的 `size_profile`。
12. `Site.parent_chunk_id` 必须引用存在的 `WorldChunk`。
13. `Region` 不能直接承载 `Site`。
14. 一个 chunk 默认只能有一个 `primary_site`。
15. `secondary_site` 只能是附属、小型、不可复杂进入的 site。
16. chunk 内存在多个 site 时必须定义 `site_relations`。
17. 两个完整可进入建筑不能放在同一个 chunk。
18. 没有 `site_relations` 的多个 site 数据必须被 validator 拒绝。
19. `ChunkEdge.source_chunk_id` 和 `target_chunk_id` 必须引用存在的 `WorldChunk`。
20. `ChunkEdge` 两端 chunk 必须属于同一个 grid，除非 edge 显式声明 `edge_scope=cross_region`。
21. `cross_region` edge 必须连接两个 Region 边界 chunk。
22. 坐标相邻不能自动生成通行结果，移动必须通过 `ChunkEdge`。
23. `LocationEdge.source_node_id` 和 `target_node_id` 必须引用存在的 `LocationNode`。
24. `LocationEdge.portal_object_id` 必须引用一个 `type=portal` 或具备 `enter/leave` 相关 affordance 的对象。
25. `Zone` 不能包含子 `Zone`。
26. `Object` 不能通过 `parent_id` 进入空间层级，只能通过 `placement` 定位。
27. `chunk` placement 必须引用存在的 `chunk_id`。
28. `zone` placement 必须引用存在的 `node_id` 和 `zone_id`。
29. `on_object`、`inside_object`、`under_object`、`attached_to_object`、`near_object` 必须引用存在的 `object_id`。
30. 对象位置链不能形成循环。
31. 可见/可互动对象的位置链必须能解析到当前 `WorldChunk`、当前 `LocationNode + Zone`，或当前空间内角色携带。
32. 玩家外部移动只能通过 `ChunkEdge` 成功结算。
33. 玩家内部移动只能通过 `LocationEdge` 成功结算。
34. DM 最终旁白中的当前可见主要对象、site、出口、附近生物，必须在同轮返回前进入状态或对应空间记忆。
35. 交易、拾取、消耗、破坏后，相关对象的 `placement` 必须同步变化。

## 空间投影查询

玩家问“这个空间有哪些东西”时，不让 LLM 自由回答。系统调用：

```text
SpaceProjectionService.query_current_space(actor_id, scope)
```

### scope

| scope | 时间推进 | 状态变化 | 用途 |
| --- | --- | --- | --- |
| visible | 不推进 | 不改变 | 玩家问“这里有什么”“我现在看到什么” |
| interactive | 不推进 | 不改变 | UI 可互动列表、动作绑定 |
| observe | 推进 1-3 分钟 | 可揭示 hinted 对象、site 或生物痕迹 | 玩家主动观察 |
| search | 推进 15-30 分钟 | 可揭示 hidden 对象、风险和发现 | 玩家主动搜索 |

### 外部 chunk 查询流程

```text
读取 actor 当前 chunk_id
-> 找到当前 WorldChunk
-> 查询当前 chunk 上的 primary_site / secondary_site
-> 查询当前 chunk 中对象
-> 查询当前 chunk 的 ChunkEdge
-> 查询同 chunk 和可感知范围内 CreatureGroup
-> 解析对象 placement 链
-> 过滤 visibility
-> 过滤 reachability
-> 过滤 ownership / permission
-> 生成 SpaceProjection
-> 供 DM / UI / ActionGrounder 使用
```

### 内部 node 查询流程

```text
读取 actor 当前 node_id / zone_id
-> 找到当前 LocationNode
-> 找到当前 Zone
-> 查询当前 node 中对象
-> 解析对象 placement 链
-> 过滤 visibility
-> 过滤 reachability
-> 过滤 ownership / permission
-> 合并 LocationEdge 和 portal objects
-> 生成 SpaceProjection
-> 供 DM / UI / ActionGrounder 使用
```

### 外部返回结构

```json
{
  "location": {
    "scope": "world_chunk",
    "chunk_id": "chunk_north_slope_12_08_02",
    "display_name": "北坡脊线，猎人小屋附近",
    "coord": { "x": 12, "y": 8, "z": 2 },
    "size_profile": "wilderness_100m"
  },
  "visible_sites": [
    {
      "id": "hunter_cabin_01",
      "name": "猎人小屋",
      "type": "shelter_site",
      "where": "区块东侧",
      "affordances": ["observe", "approach", "enter"]
    }
  ],
  "visible_objects": [
    {
      "id": "ridge_warning_post_01",
      "name": "歪斜的警示木牌",
      "type": "clue",
      "where": "西侧岩路旁",
      "affordances": ["observe", "read"]
    }
  ],
  "exits": [
    {
      "edge_id": "edge_chunk_11_08_02_to_12_08_02",
      "target_chunk_id": "chunk_north_slope_11_08_02",
      "name": "沿脊线回到西侧岩台",
      "direction": "west",
      "passable": true,
      "base_time_minutes": 8
    },
    {
      "edge_id": "edge_chunk_12_08_02_to_13_08_02",
      "target_chunk_id": "chunk_north_slope_13_08_02",
      "name": "东侧断崖",
      "direction": "east",
      "passable": false,
      "blocked_reason": "东侧是断崖，不能直接通行"
    }
  ],
  "creature_awareness": [
    {
      "creature_id": "night_wolf_pack_01",
      "name": "暗夜狼群",
      "disposition": "hostile",
      "awareness_state": "signs_only",
      "proximity_band": "near",
      "dm_hint": "东侧断崖上方传来低沉狼嚎，距离很近，但你还看不见它们。"
    }
  ],
  "hidden_system_notes": []
}
```

### 内部返回结构

```json
{
  "location": {
    "scope": "site_node",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "entrance",
    "display_name": "旧炉旅店前厅",
    "display_path": ["灰石镇", "旧炉旅店", "前厅"]
  },
  "visible_objects": [
    {
      "id": "innkeeper_01",
      "name": "店主",
      "type": "npc",
      "where": "柜台后",
      "affordances": ["talk", "negotiate", "purchase"]
    },
    {
      "id": "counter_01",
      "name": "旧木柜台",
      "type": "fixture",
      "where": "柜台区",
      "affordances": ["observe"]
    },
    {
      "id": "stew_bowl_01",
      "name": "热炖菜一碗",
      "type": "food",
      "where": "旧木柜台上",
      "affordances": ["purchase", "eat_meal"]
    }
  ],
  "exits": [
    {
      "edge_id": "edge_front_hall_to_kitchen",
      "target_node_id": "old_furnace_inn_kitchen",
      "name": "后厨",
      "portal_object_id": "kitchen_door_01",
      "relation": "doorway",
      "passable": false,
      "blocked_reason": "店主没有允许你进入后厨"
    }
  ],
  "hidden_system_notes": [
    {
      "id": "room_key_03",
      "reason": "在店主腰包里，当前未被明确看见"
    }
  ]
}
```

`hidden_system_notes` 只供系统判断和调试，不直接展示给玩家。

## 生物距离与感知投影

生物真实位置用 `chunk_id` 或 `node_id/zone_id` 存。和玩家的远近不存死，而是通过 chunk graph 或 LocationNode 关系实时计算。

```text
CreatureAwarenessService.project_creatures_near_actor(actor_id)
```

### 外部距离分级

优先使用 `ChunkEdge` 最短路径的累计时间：

| band | 规则 | 玩家表述 |
| --- | --- | --- |
| same_chunk | 同一 chunk | 同一区块，可能直接遭遇 |
| near | 相邻 chunk 或 0-10 分钟 | 很近，短时间内可接触 |
| nearby | 10-30 分钟 | 较近，能听见或发现明显痕迹 |
| far | 30-90 分钟 | 较远，需要赶路或追踪 |
| distant | 超过 90 分钟 | 很远，只能通过传闻、远声或痕迹感知 |
| blocked_or_unknown | 无可达路径或玩家没有感知 | 不显示或只显示不确定线索 |

如果生物不可见，DM 和 UI 只能展示感知投影，不能暴露上帝视角坐标。

```json
{
  "creature_id": "night_wolf_pack_01",
  "player_awareness": {
    "state": "signs_only",
    "known_location": "uncertain",
    "confidence": 0.45,
    "signs": ["低沉狼嚎", "碎石滚落声"]
  },
  "proximity": {
    "band": "near",
    "route_time_minutes": 8,
    "line_of_sight": false,
    "can_interact_now": false
  },
  "dm_hint": "东侧断崖上方传来低沉狼嚎，距离很近，但你还看不见它们。"
}
```

## 动作结算规则

### 外部移动

玩家说“去猎人小屋”：

```text
IntentPlan: travel
target_site_id: hunter_cabin_01
```

结算步骤：

```text
读取 player current chunk_id
-> 查 hunter_cabin_01.parent_chunk_id
-> 计算 current chunk 到 target chunk 的 ChunkEdge 路径
-> 检查每条 ChunkEdge.passability
-> 计算时间、风险、疲劳、口渴
-> 成功后更新 player location.scope = world_chunk
-> 更新 player chunk_id = target chunk
-> 更新 local_position = near_site:hunter_cabin_01
-> 刷新 SpaceProjection
-> 写入 ChunkTravelEvent
```

失败时：

```text
不改变 chunk_id
输出 blocked_reason
给出当前 chunk 内或相邻 chunk 的替代方案
```

### 进入 Site

玩家到达 Site 所在 chunk 后，说“进入猎人小屋”：

```text
IntentPlan: enter_site
target_site_id: hunter_cabin_01
```

结算步骤：

```text
确认 player current chunk_id 等于 hunter_cabin_01.parent_chunk_id
-> 查 target_site.entry_node_ids
-> 检查 site state.enterable
-> 更新 player location.scope = site_node
-> 更新 site_id / node_id / zone_id
-> 刷新 SpaceProjection
-> 写入 SiteEnteredEvent
```

到达小屋所在 chunk 和进入小屋是两个动作。玩家可以先远远观察、绕到背风处、听里面动静，再决定进入或离开。

### 离开 Site

玩家说“离开旧炉旅店”：

```text
IntentPlan: leave_site
source_site_id: old_furnace_inn
```

成功后位置回到 Site 所在 chunk：

```json
{
  "scope": "world_chunk",
  "chunk_id": "chunk_graystone_10_10_0",
  "local_position": "near_site:old_furnace_inn"
}
```

### 内部移动

玩家说“进入后厨”：

```text
IntentPlan: enter_location
target_node_id: old_furnace_inn_kitchen
```

结算步骤：

```text
读取 current node_id
-> 查找 source -> target 的 LocationEdge
-> 检查 portal object 状态
-> 检查 passability.conditions
-> 计算 traversal 时间、风险和资源变化
-> 成功后更新 player current node_id / zone_id
-> 刷新 SpaceProjection
-> 写入 LocationChangedEvent
```

失败时：

```text
不改变 node_id
输出 blocked_reason
给出当前场景内替代方案
```

### 靠近区域

玩家说“靠近柜台”：

```text
IntentPlan: approach
target_zone_id: front_counter_area
```

结算只更新 `current_zone_id`，不改变 `current_node_id`。时间通常为 1-3 分钟，可能改变可见性、可达性和 NPC 反应。

### 观察空间

玩家问“这里有什么”：

```text
scope=visible
不推进时间
不揭示隐藏对象
不生成新对象
```

玩家说“我仔细观察前厅”或“我观察这个区块”：

```text
scope=observe
推进 1-3 分钟
可把 hinted 对象、site 或生物痕迹改为 visible/signs_only
写入 ObjectRevealedEvent / SiteRevealedEvent / CreatureSignDetectedEvent
```

### 搜索对象或区域

玩家说“搜索柜台后”：

```text
IntentPlan: search
target_zone_id: behind_counter
```

结算步骤：

```text
检查 Zone access
确认玩家已靠近目标区域或具备进入权限
推进 15-30 分钟
按 DiscoveryTable / hidden objects 揭示结果
应用风险和压力变化
写入 SearchResolvedEvent / ObjectRevealedEvent
```

### 拾取、购买、消耗

拾取或购买成功后必须移动对象位置：

```text
stew_bowl_01: on_object counter_01
-> player_inventory 或 removed
```

经济服务扣钱、权益服务发钥匙、物品服务改 placement，三者必须在同一个 deterministic resolution 里完成。DM 不能只写“你拿到了钥匙”，却不修改对象状态。

## 与 LLM 的边界

LLM 可以输出：

- 新 chunk proposal
- 新 ChunkEdge proposal
- 新 Site proposal
- 新对象 proposal
- 生物位置和感知线索 proposal
- 对象描述、别名、标签
- 空间关系建议
- 可见性建议
- DM 叙事草稿

LLM 不能直接输出最终生效的：

- `current_chunk_id`
- `current_node_id`
- `current_zone_id`
- `currency_delta`
- `inventory` 增删
- `entitlements`
- `quest_stage`
- `risk_clock` 最终值

所有 proposal 必须经过：

```text
Materializer
-> Validator
-> Consistency Gate
-> WorldState Commit
```

最终 DM 旁白只能引用已提交或同轮已通过 validator 的 chunk、site、地点、对象和生物感知投影。

## 与现有文档关系

本设计是以下文档的空间基础层：

- [2026-07-08-isekai-scene-object-structuring-design.md](./2026-07-08-isekai-scene-object-structuring-design.md)
- [2026-07-08-isekai-content-agnostic-refactor-design.md](./2026-07-08-isekai-content-agnostic-refactor-design.md)
- [2026-07-08-isekai-llm-intent-resolution-design.md](./2026-07-08-isekai-llm-intent-resolution-design.md)

关系如下：

```text
ContentPack / LLM Proposal
-> Spatial Materializer
-> Spatial Validator
-> Authoritative WorldState
-> SpaceProjectionService
-> IntentPlan grounding
-> Deterministic Resolver
-> EventLog
-> Narration Projection
-> UI Projection
```

## 推荐实现顺序

### P0.1：WorldChunk schema 与 validator

交付内容：

- `WorldSpatialState` 数据结构。
- `Region`、`WorldChunkGrid`、`WorldChunk`、`ChunkEdge`、`RegionFeature`、`Settlement`、`TerrainFeature` schema。
- `Site.parent_chunk_id` schema。
- `SpatialGraphValidator`。

验收：

- Region 缺少 `bounds_world` 会被拒绝。
- WorldChunkGrid 缺少 `bounds_chunk` 会被拒绝。
- chunk 坐标超出 grid bounds 会被拒绝。
- chunk 的 grid 和 region 不一致会被拒绝。
- 重复 coord 会被拒绝。
- `Site` 没有 `parent_chunk_id` 会被拒绝。
- `Region` 直接承载 `Site` 会被拒绝。
- `ChunkEdge` 引用不存在 chunk 会被拒绝。
- 非 `cross_region` ChunkEdge 连接两个 grid 会被拒绝。
- 没有 `ChunkEdge` 时，相邻 coord 不能自动通行。

### P0.2：chunk-site 基数规则

交付内容：

- `primary_site_id`、`secondary_site_ids`、`site_relations`。
- 完整可进入建筑互斥校验。
- `secondary_site` 类型白名单或规则校验。

验收：

- 一个 chunk 中两个完整建筑会被拒绝。
- 多个 site 但没有 `site_relations` 会被拒绝。
- 井、告示牌、马槽这类附属 site 必须有和 primary site 的距离/可见/通行关系。

### P0.3：内部空间 schema 与 validator

交付内容：

- `LocationNode`、`Zone`、`LocationEdge`、`ObjectPlacement` schema。
- 位置链解析器 `resolve_object_placement(object_id)`。

验收：

- 非法 node/zone 引用会被拒绝。
- 对象位置链循环会被拒绝。
- `LocationEdge` 引用不存在节点会被拒绝。
- `on_object` 最终不能追溯到 chunk 或内部空间根时会被拒绝。

### P0.4：SpaceProjectionService

交付内容：

- `query_current_space(actor_id, scope)`。
- 支持 `world_chunk` 和 `site_node` 两种 actor location。
- `visible`、`interactive`、`observe` 三个 scope。
- 当前 chunk/site 可见对象、可互动对象、出口、blocked reason、生物感知投影输出。

验收：

- 玩家问“这里有什么”不推进时间、不改变状态。
- 玩家主动观察可推进 1-3 分钟并揭示 hinted 对象、site 或生物痕迹。
- UI 可互动列表和 DM 旁白使用同一份 projection。

### P0.5：移动和进入结算

交付内容：

- `travel` 必须通过 `ChunkEdge`。
- `enter_site` 必须从 Site 所在 chunk 进入。
- `leave_site` 必须回到 Site 所在 chunk。
- `enter_location` 必须通过 `LocationEdge`。
- `approach` 只改变 `current_zone_id`。
- `ChunkTravelEvent`、`SiteEnteredEvent`、`SiteLeftEvent`、`LocationChangedEvent`、`ZoneChangedEvent`。

验收：

- 没有 ChunkEdge 时不能移动到目标 chunk。
- ChunkEdge 阻挡时不改变当前位置。
- 玩家到达猎人小屋所在 chunk 后不会自动进入小屋。
- 离开旧炉旅店后位置回到 `chunk_graystone_10_10_0` 的 `near_site:old_furnace_inn`。
- 进入新节点后可互动对象立即刷新。

### P0.6：对象和生物位置变更

交付内容：

- 拾取、购买、消耗、丢弃、NPC 携带的 placement 更新。
- 生物 `CreatureMovementSystem.tick(minutes_elapsed)`。
- `CreatureAwarenessService.project_creatures_near_actor(actor_id)`。
- `ObjectMovedEvent`、`ObjectRemovedEvent`、`CreatureMovedEvent`、`CreatureSignDetectedEvent`。

验收：

- 玩家购买钥匙后，钥匙从店主/柜台移动到玩家物品或权益状态。
- 玩家吃掉炖菜后，炖菜不能继续显示在柜台上。
- 狼群从相邻 chunk 移动到玩家 chunk 后能触发遭遇候选。
- 未被发现的敌对生物不能在 DM 文本中暴露精确 chunk_id。
- DM 文本、UI、世界状态三者一致。

## 验收流程

使用固定流程测试：

```text
在北坡脊线西侧 chunk 查看周围
沿可通行 ChunkEdge 前往猎人小屋所在 chunk
观察猎人小屋但不进入
听到相邻 chunk 的狼群动静
尝试走向东侧断崖，被 ChunkEdge 阻挡
回到猎人小屋 chunk
进入猎人小屋
搜索小屋内部黑暗角落
离开猎人小屋回到所在 chunk
返回灰石镇旧炉旅店 chunk
进入旧炉旅店前厅
询问这里有什么
靠近柜台
购买炖菜
吃炖菜
离开旧炉旅店回到街道 chunk
```

每一步必须满足：

- 玩家外部位置使用 `scope=world_chunk` 和权威 `chunk_id`。
- 玩家内部位置使用 `scope=site_node` 和权威 `node_id/zone_id`。
- `display_path` 与当前位置一致。
- 外部移动只通过 `ChunkEdge`。
- 内部移动只通过 `LocationEdge`。
- Site 只从所属 chunk 进入，离开 Site 回到所属 chunk。
- 当前 SpaceProjection 只包含当前 chunk/site 和可感知相邻内容。
- 可互动对象来自对象位置链解析。
- 生物远近来自 chunk graph 投影，不是 DM 自由描述。
- DM 旁白只引用已落库对象、site、chunk 和感知投影。
- 交易、消耗、拾取后对象 placement 已同步变化。
- 失败移动保持原地并给出场景内替代方案。

## 回归测试要求

新增测试覆盖：

- `test_world_chunk_coord_unique_within_grid`
- `test_region_requires_world_bounds`
- `test_world_chunk_grid_requires_chunk_bounds`
- `test_world_chunk_coord_must_be_inside_grid_bounds`
- `test_world_chunk_grid_region_must_match_chunk_region`
- `test_site_requires_parent_chunk`
- `test_region_cannot_directly_contain_site`
- `test_adjacent_chunks_are_not_passable_without_chunk_edge`
- `test_non_cross_region_chunk_edge_cannot_cross_grid`
- `test_cross_region_chunk_edge_requires_boundary_chunks`
- `test_blocked_chunk_edge_does_not_change_current_chunk`
- `test_chunk_rejects_multiple_primary_sites`
- `test_chunk_multiple_sites_require_site_relations`
- `test_two_full_enterable_sites_cannot_share_chunk`
- `test_object_placement_chain_resolves_chunk_root`
- `test_object_placement_chain_resolves_zone_root`
- `test_object_placement_cycle_is_rejected`
- `test_current_space_query_does_not_advance_time`
- `test_observe_reveals_hinted_object_site_or_creature_sign`
- `test_travel_requires_chunk_edge`
- `test_enter_site_requires_actor_in_parent_chunk`
- `test_leave_site_returns_to_parent_chunk`
- `test_enter_location_requires_location_edge`
- `test_approach_changes_zone_not_node`
- `test_purchase_moves_object_or_grants_entitlement`
- `test_consumed_object_removed_from_projection`
- `test_creature_proximity_uses_chunk_graph`
- `test_unseen_creature_does_not_expose_true_chunk_to_narration`
- `test_narration_cannot_reference_uncommitted_visible_object`

## 架构决策

1. 第一阶段采用粗粒度 xyz `WorldChunk`，不采用 DF 小 tile 网格。
2. 外部空间基本单位是 `WorldChunk`，不是字符串地点，也不是无尺寸地标点。
3. `WorldChunk` 使用固定尺寸 profile：城镇 50m，野外 100m。
4. `Site` 必须挂在 `WorldChunk` 上，不能直接挂在 `Region` 上。
5. 一个 chunk 默认只能承载一个完整主 Site。
6. chunk 内存在多个 site 时必须定义 `site_relations`。
7. 两个完整可进入建筑不能放在同一个 chunk。
8. 村庄、城镇、山脊、河谷是一组 chunk。
9. 相邻 chunk 不等于可通行，外部移动必须通过 `ChunkEdge`。
10. 进入 Site 后使用 `LocationNode/Zone` 表达内部空间。
11. 内部移动必须通过 `LocationEdge`，不能通过 `parent_id` 推导。
12. Portal 必须是对象，地点边引用 portal。
13. 对象不进入空间层级，通过 `ObjectPlacement` 表达位置。
14. 生物真实位置用 chunk 或 node/zone 存，玩家看到的是感知投影。
15. “这里有什么”是确定性投影查询，不是 LLM 生成。
16. LLM 只做 proposal 和叙事草稿，不能提交最终状态。
17. DM 旁白、UI 可互动列表、动作目标绑定必须共享 `SpaceProjection`。
