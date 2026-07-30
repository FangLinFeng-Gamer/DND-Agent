---
doc_id: isekai.location_space_rules
status: active
layer: world-model
owner: architecture
created_at: 2026-07-10
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.world_generation_manifest_rules
provides:
  - World
  - Region
  - WorldChunkGrid
  - WorldChunk
  - WorldLayoutCandidate
  - RegionLayoutCandidate
  - WorldChunkGridLayoutCandidate
  - WorldChunkLayoutCandidate
  - SpatialLayoutCandidateValidator
  - SpatialFoundationMaterializer
  - ChunkEdge
  - RegionFeature
  - Settlement
  - TerrainFeature
  - Site
  - PlaceHierarchyRegistry
  - LocationChildGenerationContext
  - LocationNode
  - Zone
  - LocationEdge
  - SiteBoundaryEdge
  - ObjectPlacement
  - ActorLocation
  - SiteBoundaryResolver
  - ZoneAccessResolver
  - LocationHierarchyValidator
---

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
      -> Ecology entities by location reference
```

核心规则：

```text
WorldChunk 是外部空间的基本单位。
LocationNode/Zone 是进入 Site 后的内部空间单位。
Site 必须挂在 WorldChunk 上。
地点生成必须由父地点的 allowed_child_types 限制，不能让模型自由拼接子地点 ID。
进入和离开 Site 必须通过 SiteBoundaryEdge，不能把 parent_chunk_id 当成隐式入口或出口。
村庄、城镇、山脊、河谷是一组 WorldChunk，不是单个模糊字符串。
相邻 chunk 只表示物理接壤，能不能通行必须看 ChunkEdge。
CreatureGroup 等生态实体的 canonical schema 不属于空间文档；空间系统只读取它们的 location。
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
猎人小屋 -> chunk_north_slope_12_08_00 -> 北坡荒野
旧炉旅店 -> chunk_graystone_10_10_0 -> 灰石镇区域
```

### 4. 相邻不等于可通行

两个 chunk 坐标相邻，只表示物理接壤。能不能走、需要多久、有什么风险，必须由 `ChunkEdge.effective_passability` 和 `ChunkEdge.effective_traversal` 决定。

例如：

```text
城镇街道 chunk -> 城镇街道 chunk：可通行
平原 chunk -> 森林 chunk：可通行但耗时增加
平原 chunk -> 断崖 chunk：直接阻挡
山脊 chunk -> 下方谷地 chunk：需要路径、攀爬能力或绕路
```

### 5. 边统一是有向 arc

`ChunkEdge` 和 `LocationEdge` 在权威状态中都表示一条有向 arc，只表达 `source -> target` 这一方向的移动可能性。双向道路、双向门、双向楼梯必须物化成两条独立 edge。

```text
edge_A_to_B：只表示 A -> B
edge_B_to_A：只表示 B -> A
```

反向 edge 可以拥有不同耗时、条件、风险和阻挡原因。上坡、下坡、进门、出门、从断崖下撤回等情况不能由同一条 edge 反向猜测。

### 6. 路径成本必须可计算

Edge 的静态基础通行和最终有效通行必须分开：

```text
base_passability / base_traversal：由静态地形、水文、道路和结构基础事实产生。
passability_override 集合：由障碍、portal、环境和动作结果产生的覆盖来源。
effective_passability / effective_traversal：由 PassabilityReducer 聚合 base 和 active overrides 后写入。
```

移动 resolver 和投影服务只能读取 `effective_passability` 与 `effective_traversal`，并把“当前可通行”的 edge 放入最短路：

```text
open / difficult：effective_traversal.time_minutes 必须是有限正数。
conditional 且条件满足：effective_traversal.time_minutes 必须是有限正数。
conditional 但条件不满足：effective_cost_minutes = Infinity。
blocked：effective_cost_minutes = Infinity，不能进入可达路径。
```

`effective_traversal.time_minutes=null` 只允许出现在 `blocked` 或当前条件不满足的 `conditional` edge 上。最短路不能把 `null` 当成 0、默认值或有限时间。

### 7. 一个 chunk 默认只能承载一个完整主 Site

一个 `WorldChunk` 至少要大到能容纳一个最小可进入 `Site`。默认一个 chunk 只能有一个 `primary_site`。

如果一个 chunk 内存在多个 site，必须显式定义 `site_relations`。没有 `site_relations` 的多个 site 必须被 validator 拒绝。

### 8. 地点层级回答“属于哪里”

`parent_id` 只表达归属关系，例如：

```text
前厅 属于 旧炉旅店
旧炉旅店 属于 chunk_graystone_10_10_0
chunk_graystone_10_10_0 属于 灰石镇区域
```

归属关系不表示玩家可以直接移动。

### 9. 地点边回答“能去哪里”

玩家从当前内部地点能否去另一个内部地点，必须由 `LocationEdge` 决定。门、楼梯、破口、地窖口等连接实体必须建成 `portal` 对象，并由 `LocationEdge.portal_object_id` 引用。

外部 `WorldChunk` 和内部 `Site` 之间的进入、离开不能由 `Site.parent_chunk_id` 隐式完成，必须由 `SiteBoundaryEdge` 决定。`parent_chunk_id` 只表示 Site 的物理锚点，不表示玩家能从 chunk 任意位置进入，也不表示玩家能从 Site 任意节点离开。

### 10. 对象不属于地点层级

对象通过 `ObjectPlacement` 挂载到 chunk、zone、其他对象、角色身上或玩家物品栏。对象可以递归挂载，但最终必须能追溯到一个 `WorldChunk` 或 `LocationNode + Zone`，除非它在玩家背包、角色携带、远处传闻或已移除状态。

### 11. 细节由 Placement 和 Relation 表达

更细的空间描述，例如“柜台后”“酒桶旁”“破毯子下面”“车厢破口边”，优先通过以下结构表达：

- `Zone`
- `local_position`
- `ObjectPlacement`
- `SpatialRelation`
- `access_sides`
- `visibility`

### 12. 地点生成由父级上下文限制

地点生成器不能从全局地点池中自由选择子地点。每次生成子地点时，必须由系统提供 `LocationChildGenerationContext`：

```text
parent_id
parent_type
parent_depth
allowed_child_types
allowed_child_count_range
allowed_zone_types
id_prefix
```

LLM 或内容包只能建议 `child_type`、显示名、氛围标签和局部特征，不能自由写最终 `site_id`、`node_id` 或 `zone_id`。最终 ID、`parent_id`、`site_id` 和默认入口 zone 必须由 `LocationMaterializer` 根据父级上下文生成。

层级深度使用 `hierarchy_depth` 表示，数值越大越细：

```text
0 World
10 Region
20 RegionFeature / Settlement / TerrainFeature
30 District / Street / WildernessArea
40 Site
50 NodeGroup / LocationNode
60 Zone
```

子地点的 `hierarchy_depth` 必须大于父地点。`Zone` 是叶子节点，不能继续生成子地点。

示例：

```text
town -> street / district / market_square / gate / site
street -> inn / shop / house / stall / alley
inn -> front_hall / kitchen / guest_room / corridor / stair_landing / stable
front_hall -> zone
zone -> no children
```

禁止：

```text
old_furnace_inn -> blacksmith_shop_front_room
old_furnace_inn -> region
front_hall -> town
zone -> room
```
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

## P0 初始空间生成

P0 采用“程序生成、小型完整网格、候选骨架先生成、完整后物化”。这里的“候选”是 `system_ledger.generation_audit` 中的生成中间结果，不是权威世界实体，运行时 Resolver、AI、UI 和玩家行动不能读取。

```text
WorldGenerationParameters.spatial_layout
-> SpatialLayoutCandidateFormation
-> WorldLayoutCandidate
-> RegionLayoutCandidate[]
-> WorldChunkGridLayoutCandidate[]
-> WorldChunkLayoutCandidate[]
-> SpatialLayoutCandidateValidator
-> 后续气候和物理候选
-> SpatialFoundationValidator
-> SpatialFoundationMaterializer
-> Authoritative World / Region / WorldChunkGrid / WorldChunk
```

### SpatialLayoutParameters

`WorldGenerationParameters.spatial_layout` 决定 P0 程序空间骨架的规模，不直接成为世界事实。

```json
{
  "generation_mode": "procedural",
  "coverage_mode": "complete",
  "default_grid": {
    "width_chunks": 8,
    "height_chunks": 8,
    "min_z": 0,
    "max_z": 0
  },
  "max_chunks_per_region": 256
}
```

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| `generation_mode` | enum | P0 固定为 `procedural`，表示 Region、Grid 和 chunk 坐标由确定性规则生成。 |
| `coverage_mode` | enum | P0 固定为 `complete`，表示网格边界内每个整数坐标都必须物化。 |
| `default_grid.width_chunks` | integer | Region 默认横向 chunk 数，范围 1 到 16。 |
| `default_grid.height_chunks` | integer | Region 默认纵向 chunk 数，范围 1 到 16。 |
| `default_grid.min_z` | integer | 默认最低 chunk 层坐标。 |
| `default_grid.max_z` | integer | 默认最高 chunk 层坐标，必须大于等于 `min_z`。 |
| `max_chunks_per_region` | integer | 单个 Region 完整网格的硬上限，P0 固定为 256。 |

示例的 8 × 8 × 1 产生 64 个 chunk；8 × 8 只是示例输入，不是固定世界尺寸。任何参数都必须满足：

```text
width_chunks * height_chunks * (max_z - min_z + 1) <= max_chunks_per_region
```

### 候选包装与目标 ID

四种空间布局候选都必须放入 `GeneratorOutputItem(output_class=candidate)`：

```text
GeneratorOutputItem.candidate_id：候选记录自身 ID，只用于生成审计。
payload.world_id / region_id / grid_id / chunk_id：未来权威实体使用的目标 ID。
```

候选阶段的目标 ID 只允许引用同一 manifest 中已经验证的候选。它们尚未进入 `WorldState`，因此不能标记成 `input_class=world_fact`。

### WorldLayoutCandidate

`WorldLayoutCandidate` 描述未来 World 的身份、版本和 chunk 尺寸配置，不包含 Region、气候或地形。

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| `world_id` | string | 未来 `World.id`，必须满足 ID 格式、在 manifest 中唯一，并等于 `WorldGenerationManifest.world_id`。 |
| `name` | string | 未来 `World.name`，仅用于显示。 |
| `seed` | string | 必须等于 `RandomSeedMaterial.world_seed`。 |
| `version_lock.schema_version` | string | 本次生成使用的世界 schema 版本。 |
| `version_lock.registry_hash` | hash | 本次生成使用的 registry bundle canonical hash。 |
| `version_lock.rule_bundle_hash` | hash | 本次生成使用的规则和 validator bundle canonical hash。 |
| `version_lock.content_pack_hash` | hash | 本次生成启用内容包集合的 canonical hash。 |
| `active_content_pack_refs` | array | 启用内容包引用，必须与 manifest 锁定内容一致。 |
| `active_content_pack_refs[].content_pack_id` | string | 内容包 ID。 |
| `active_content_pack_refs[].content_pack_version` | string | 内容包版本。 |
| `active_content_pack_refs[].content_pack_hash` | hash | 单个内容包 canonical hash。 |
| `chunk_size_profiles` | map | 允许使用的 chunk 尺寸表，key 是 profile ID。 |
| `chunk_size_profiles.*.width_meters` | positive integer | 一个 chunk 在 x 方向的物理宽度。 |
| `chunk_size_profiles.*.height_meters` | positive integer | 一个 chunk 在 y 方向的物理高度。 |
| `chunk_size_profiles.*.z_step_meters` | positive integer | z 坐标每变化 1 的高度差。 |

### RegionLayoutCandidate

`RegionLayoutCandidate` 描述未来 Region 的空间身份和物理边界，不包含气候、生态、势力或风险。

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| `region_id` | string | 未来 `Region.id`，在目标 World 中唯一。 |
| `name` | string | Region 显示名。 |
| `type` | enum | Region 类型，例如 `wilderness_region`，必须属于 Region 类型闭集。 |
| `world_id` | string | 必须匹配同批 `WorldLayoutCandidate.world_id`。 |
| `bounds_world.origin_meters` | `{x,y}` integer | `origin_chunk` 对应的世界米制坐标。 |
| `bounds_world.min_meters` | `{x,y}` integer | Region x/y 半开物理区间的最小坐标，包含该坐标。 |
| `bounds_world.max_meters` | `{x,y}` integer | Region x/y 半开物理区间的最大坐标，不包含该坐标。 |
| `bounds_world.z_range.min` | integer | Region 允许的最低 z 层，包含端点。 |
| `bounds_world.z_range.max` | integer | Region 允许的最高 z 层，包含端点。 |
| `grid_id` | string | 未来 `WorldChunkGrid.id`；P0 每个 Region 恰好一个 grid。 |

### WorldChunkGridLayoutCandidate

`WorldChunkGridLayoutCandidate` 描述 Region 的离散坐标尺，不是地点或地貌。

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| `grid_id` | string | 未来 `WorldChunkGrid.id`。 |
| `region_id` | string | 必须匹配同批 `RegionLayoutCandidate.region_id`。 |
| `size_profile` | string | 默认 chunk 尺寸，必须是 `WorldLayoutCandidate.chunk_size_profiles` 中的 key。 |
| `origin_chunk` | `{x,y,z}` integer | 与 `RegionLayoutCandidate.bounds_world.origin_meters` 对齐的 chunk 坐标。 |
| `bounds_chunk.min` | `{x,y,z}` integer | 每个坐标轴允许的最小 chunk 坐标，包含端点。 |
| `bounds_chunk.max` | `{x,y,z}` integer | 每个坐标轴允许的最大 chunk 坐标，包含端点。 |

### WorldChunkLayoutCandidate

`WorldChunkLayoutCandidate` 表示完整网格中必须存在的一格，只回答“这格在哪里”，不回答“这格是什么地形”。

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| `chunk_id` | string | 未来 `WorldChunk.id`，必须由 `region_id + coord` 按注册规则稳定生成。 |
| `grid_id` | string | 必须匹配同批 `WorldChunkGridLayoutCandidate.grid_id`。 |
| `region_id` | string | 必须同时匹配 grid 和 Region 候选。 |
| `coord.x` | integer | 横向网格坐标，必须位于 `bounds_chunk` 内。 |
| `coord.y` | integer | 纵向网格坐标，必须位于 `bounds_chunk` 内。 |
| `coord.z` | integer | 垂直层坐标，必须位于 `bounds_chunk` 内。 |
| `size_profile` | string | P0 初始生成必须等于 grid 的 `size_profile`；运行时 schema 仍保留未来覆盖能力。 |

它不能包含 `base_fields`、`terrain`、`local_climate`、`biome_tags` 或 `site_slots`。这些字段由后续候选阶段产生。

### SpatialLayoutCandidateValidator

完整网格必须满足：

```text
expected_chunk_count =
  (max.x - min.x + 1)
  * (max.y - min.y + 1)
  * (max.z - min.z + 1)

实际 WorldChunkLayoutCandidate 数量必须等于 expected_chunk_count。
实际 coord 集合必须恰好等于 bounds_chunk 三轴整数坐标的笛卡尔积。
同一 grid 中 coord 和 chunk_id 都必须唯一。
每个 Region 恰好引用一个 grid，每个 grid 恰好属于一个 Region。
Region x/y 物理跨度必须等于 chunk 数量乘以 size profile 米制尺寸。
```

### SpatialFoundationMaterializer

空间基础物化必须使用以下字段来源：

| 权威实体 | 必须合并的来源 | 合法空集合初值 |
| --- | --- | --- |
| `World` | WorldLayoutCandidate | `current_actor_locations={}` |
| `Region` | RegionLayoutCandidate + RegionClimateCandidate + RegionBiomeCandidate | `danger_tags=[]`、`factions=[]`、`risk_clocks={}` |
| `WorldChunkGrid` | WorldChunkGridLayoutCandidate | 无 |
| `WorldChunk` | WorldChunkLayoutCandidate + ChunkBaseFieldsCandidate + ChunkTerrainCandidate + ChunkHydrologyCandidate + ChunkLocalClimateCandidate + ChunkBiomeCandidate | `site_slots.primary_site_id=null`、`site_slots.secondary_site_ids=[]`、`tags=[]` |

这四类实体必须使用同一个 `atomic_commit_group_id`。任何目标实体缺少必填候选、字段校验失败、引用不闭合或网格不完整时，整个提交组回滚。禁止先创建只有 `id/coord` 的 `WorldChunk` 再逐步补字段。

## 数据模型

### World

```json
{
  "id": "isekai_world_001",
  "name": "当前异世界",
  "seed": "adv_10_seed",
  "version_lock": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "active_content_pack_refs": [
    {
      "content_pack_id": "old_furnace_inn_p1",
      "content_pack_version": "2026-07-18.1",
      "content_pack_hash": "sha256:old_furnace_inn_pack_hash"
    }
  ],
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
    "max_meters": { "x": 1600, "y": 1600 },
    "z_range": { "min": 0, "max": 0 }
  },
  "grid_id": "grid_north_slope_wilds",
  "climate_profile": {
    "climate_zone": "cold_temperate",
    "temperature_band": "cold",
    "rainfall_band": "wet",
    "humidity": "medium",
    "seasonality": "strong",
    "prevailing_wind": "northwest",
    "snow_months": ["winter"]
  },
  "biome_tags": ["cold_forest", "rocky_highland", "water_source_nearby", "predator_habitat"],
  "danger_tags": ["night_wolf_activity"],
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
    "max": { "x": 15, "y": 15, "z": 0 }
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
  "id": "chunk_north_slope_12_08_00",
  "grid_id": "grid_north_slope_wilds",
  "region_id": "north_slope_wilds",
  "coord": {
    "x": 12,
    "y": 8,
    "z": 0
  },
  "size_profile": "wilderness_100m",
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
  },
  "base_fields": {
    "elevation": "0.720",
    "moisture": "0.350",
    "rockiness": "0.800",
    "soil_depth": "0.250",
    "water_flow": "0.100",
    "civilization_pressure": "0.150",
    "danger_pressure": "0.550",
    "abnormal_pressure": "0.050"
  },
  "local_climate": {
    "temperature_offset_c": -3.0
  },
  "biome_tags": ["cold_forest", "rocky_highland", "predator_habitat"],
  "site_slots": {
    "primary_site_id": "hunter_cabin_01",
    "secondary_site_ids": []
  },
  "tags": ["ridge", "outdoor", "wind_exposed"]
}
```

### ChunkEdge

`ChunkEdge` 是 chunk 之间移动关系的有向 arc。坐标相邻不能自动推导可通行；从 target 回到 source 必须存在独立反向 `ChunkEdge`。

```json
{
  "id": "edge_chunk_12_08_00_to_13_08_00",
  "source_chunk_id": "chunk_north_slope_12_08_00",
  "target_chunk_id": "chunk_north_slope_13_08_00",
  "direction": "east",
  "adjacent": true,
  "base_passability": {
    "state": "blocked",
    "blocked_reason": "东侧是断崖，不能直接通行"
  },
  "base_traversal": {
    "base_time_minutes": null,
    "difficulty": "impassable",
    "movement_type": "walk",
    "risk_tags": ["fall"]
  },
  "effective_passability": {
    "state": "blocked",
    "blocked_reason": "东侧是断崖，不能直接通行",
    "source_refs": ["base_passability"]
  },
  "effective_traversal": {
    "time_minutes": null,
    "difficulty": "impassable",
    "movement_type": "walk",
    "risk_tags": ["fall"],
    "source_refs": ["base_traversal"]
  },
  "visibility": {
    "line_of_sight_from_source": true,
    "description": "东侧地面忽然断开，岩壁直落进雾里"
  }
}
```

可通行示例：

```json
{
  "id": "edge_chunk_11_08_00_to_12_08_00",
  "source_chunk_id": "chunk_north_slope_11_08_00",
  "target_chunk_id": "chunk_north_slope_12_08_00",
  "direction": "east",
  "adjacent": true,
  "base_passability": {
    "state": "open"
  },
  "base_traversal": {
    "base_time_minutes": 8,
    "difficulty": "moderate",
    "movement_type": "walk",
    "risk_tags": ["loose_stone", "wolf_scent"]
  },
  "effective_passability": {
    "state": "open",
    "source_refs": ["base_passability"]
  },
  "effective_traversal": {
    "time_minutes": 8,
    "difficulty": "moderate",
    "movement_type": "walk",
    "risk_tags": ["loose_stone", "wolf_scent"],
    "source_refs": ["base_traversal"]
  },
  "visibility": {
    "line_of_sight_from_source": true,
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
    "chunk_north_slope_11_08_00",
    "chunk_north_slope_12_08_00",
    "chunk_north_slope_13_08_00"
  ],
  "dominant_terrain": "rocky_ridge"
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
  "entry_chunk_ids": ["chunk_graystone_10_10_0"]
}
```

### Site

`Site` 必须挂在 `WorldChunk` 上。`region_id` 可作为查询索引，但真正空间父级是 `parent_chunk_id`。

```json
{
  "id": "hunter_cabin_01",
  "name": "猎人小屋",
  "type": "shelter_site",
  "parent_chunk_id": "chunk_north_slope_12_08_00",
  "local_position": "east_edge",
  "footprint": {
    "width_meters": 12,
    "height_meters": 8
  },
  "entry_node_ids": ["hunter_cabin_outside"],
  "tags": ["shelter", "abandoned"],
  "state": {
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

### PlaceHierarchyRegistry

`PlaceHierarchyRegistry` 是生成和校验地点层级的规则表。它不是运行时地点实例，但必须作为版本化 registry 固定在 rule bundle 中。

```json
{
  "registry_id": "default_place_hierarchy_v1",
  "entries": [
    {
      "place_type": "town",
      "hierarchy_depth": 20,
      "allowed_child_types": ["district", "street", "market_square", "gate", "site"],
      "allowed_child_count_range": { "min": 1, "max": 40 }
    },
    {
      "place_type": "street",
      "hierarchy_depth": 30,
      "allowed_child_types": ["inn", "shop", "house", "stall", "alley"],
      "allowed_child_count_range": { "min": 0, "max": 20 }
    },
    {
      "place_type": "inn",
      "hierarchy_depth": 40,
      "allowed_child_types": ["front_hall", "kitchen", "guest_room", "corridor", "stair_landing", "stable", "storage_room"],
      "allowed_zone_types": ["threshold", "service_area", "staff_area", "rest_area", "storage_area"]
    },
    {
      "place_type": "front_hall",
      "hierarchy_depth": 50,
      "allowed_child_types": ["zone"],
      "allowed_zone_types": ["threshold", "service_area", "staff_area", "rest_area"]
    },
    {
      "place_type": "zone",
      "hierarchy_depth": 60,
      "allowed_child_types": []
    }
  ]
}
```

### LocationChildGenerationContext

生成任意子地点前，系统必须先创建 `LocationChildGenerationContext`，限制本次生成的合法输出空间。

```json
{
  "parent_id": "old_furnace_inn",
  "parent_type": "inn",
  "parent_depth": 40,
  "parent_site_id": "old_furnace_inn",
  "id_prefix": "old_furnace_inn",
  "allowed_child_types": ["front_hall", "kitchen", "guest_room", "corridor", "stair_landing", "stable", "storage_room"],
  "allowed_zone_types": ["threshold", "service_area", "staff_area", "rest_area", "storage_area"],
  "allowed_child_count_range": { "min": 1, "max": 20 }
}
```

LLM proposal 在此上下文中只能输出：

```json
{
  "child_type": "kitchen",
  "name": "后厨",
  "features": ["smoke", "hanging_pots"]
}
```

最终 `node_id`、`site_id`、`parent_id` 和 `zones[].id` 必须由 `LocationMaterializer` 生成。

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

`LocationEdge` 是 Site 内部或相邻 `LocationNode` 之间通行关系的有向 arc。双向门必须物化成两条 `LocationEdge`，不能在单条 edge 上用 `bidirectional` 表示。

```json
{
  "id": "edge_front_hall_to_kitchen",
  "source_node_id": "old_furnace_inn_front_hall",
  "target_node_id": "old_furnace_inn_kitchen",
  "relation": "doorway",
  "portal_object_id": "kitchen_door_01",
  "direction": "toward_kitchen",
  "base_passability": {
    "state": "open"
  },
  "base_traversal": {
    "base_time_minutes": 2,
    "scope": "indoor",
    "movement_type": "walk",
    "risk_delta": 0
  },
  "effective_passability": {
    "state": "conditional",
    "conditions": [
      {
        "type": "permission",
        "required": "innkeeper_allows_kitchen_access"
      }
    ],
    "blocked_reason": "店主没有允许你进入后厨",
    "source_refs": ["permission:innkeeper_allows_kitchen_access"]
  },
  "effective_traversal": {
    "time_minutes": null,
    "scope": "indoor",
    "movement_type": "walk",
    "risk_delta": 0,
    "source_refs": ["base_traversal", "permission:innkeeper_allows_kitchen_access"]
  },
  "visibility": {
    "visible_from_source": true,
    "visible_from_target": true,
    "hint_text": "柜台侧后方有一扇通往后厨的门"
  }
}
```

同一扇门的反向 arc 必须单独存在：

```json
{
  "id": "edge_kitchen_to_front_hall",
  "source_node_id": "old_furnace_inn_kitchen",
  "target_node_id": "old_furnace_inn_front_hall",
  "relation": "doorway",
  "portal_object_id": "kitchen_door_01",
  "direction": "toward_front_hall",
  "base_passability": {
    "state": "open"
  },
  "base_traversal": {
    "base_time_minutes": 2,
    "scope": "indoor",
    "movement_type": "walk",
    "risk_delta": 0
  },
  "effective_passability": {
    "state": "open"
  },
  "effective_traversal": {
    "time_minutes": 2,
    "scope": "indoor",
    "movement_type": "walk",
    "risk_delta": 0,
    "source_refs": ["base_traversal"]
  },
  "visibility": {
    "visible_from_source": true,
    "visible_from_target": true,
    "hint_text": "前厅的火光从门缝里透进来"
  }
}
```

### SiteBoundaryEdge

`SiteBoundaryEdge` 表示外部 `WorldChunk` 和内部 `Site` 入口/出口之间的有向 arc。它和 `ChunkEdge`、`LocationEdge` 平级：

```text
ChunkEdge：world_chunk -> world_chunk
LocationEdge：site_node -> site_node
SiteBoundaryEdge：world_chunk -> site_node 或 site_node -> world_chunk
```

进入 Site 的边：

```json
{
  "id": "entry_street_to_old_furnace_inn_front_hall",
  "edge_type": "site_entry",
  "source": {
    "scope": "world_chunk",
    "chunk_id": "chunk_graystone_10_10_0",
    "local_position": "inn_front_door"
  },
  "target": {
    "scope": "site_node",
    "site_id": "old_furnace_inn",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "entrance"
  },
  "portal_object_id": "old_furnace_inn_front_door",
  "base_passability": {
    "state": "open"
  },
  "base_traversal": {
    "base_time_minutes": 1,
    "scope": "threshold",
    "movement_type": "enter",
    "risk_delta": 0
  },
  "effective_passability": {
    "state": "open"
  },
  "effective_traversal": {
    "time_minutes": 1,
    "scope": "threshold",
    "movement_type": "enter",
    "risk_delta": 0,
    "source_refs": ["base_traversal"]
  }
}
```

离开 Site 的边必须单独存在：

```json
{
  "id": "exit_old_furnace_inn_front_hall_to_street",
  "edge_type": "site_exit",
  "source": {
    "scope": "site_node",
    "site_id": "old_furnace_inn",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "entrance"
  },
  "target": {
    "scope": "world_chunk",
    "chunk_id": "chunk_graystone_10_10_0",
    "local_position": "outside_inn_front_door"
  },
  "portal_object_id": "old_furnace_inn_front_door",
  "base_passability": {
    "state": "open"
  },
  "base_traversal": {
    "base_time_minutes": 1,
    "scope": "threshold",
    "movement_type": "leave",
    "risk_delta": 0
  },
  "effective_passability": {
    "state": "open"
  },
  "effective_traversal": {
    "time_minutes": 1,
    "scope": "threshold",
    "movement_type": "leave",
    "risk_delta": 0,
    "source_refs": ["base_traversal"]
  }
}
```

`Site.parent_chunk_id` 只用于物理锚点和默认查询，不得被 `enter_site` 或 `leave_site` 当作隐式传送目标。

### Portal Object

门、楼梯、破口、道路、地窖口必须也是对象：

```json
{
  "id": "kitchen_door_01",
  "name": "后厨门",
  "object_type": "portal",
  "visibility": "visible",
  "placement": {
    "kind": "zone",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "front_counter_area",
    "local_position": "behind_counter_side",
    "relation": "at_edge",
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
| inside_object | 旧版容器包含关系。P1-02 后只允许迁移读取，新状态不得写入。 |
| contained_by_parent | 被父容器包含。具体父容器由 `WorldObject.components.container.contained_object_ids` 反查。 |
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
  "object_type": "fixture",
  "visibility": "visible",
  "placement": {
    "kind": "zone",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "front_counter_area",
    "local_position": "north_side",
    "relation": "occupies",
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
  "object_type": "clue",
  "visibility": "visible",
  "placement": {
    "kind": "chunk",
    "chunk_id": "chunk_north_slope_12_08_00",
    "local_position": "west_edge",
    "relation": "standing",
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
  "object_type": "food",
  "visibility": "visible",
  "placement": {
    "kind": "on_object",
    "object_id": "counter_01",
    "surface": "customer_side",
    "relation": "on",
    "reachability": "reachable"
  },
  "ownership": {
    "owner_id": "innkeeper_01",
    "faction_id": "graystone_town",
    "legal_status": "for_sale"
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
    "chunk_id": "chunk_north_slope_12_08_00",
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

### CreatureGroup 空间引用

`CreatureGroup` 的 canonical schema 属于 [自然生态与资源规则](./natural-ecology-rules.md)。本文件只规定空间系统如何读取 `CreatureGroup.location`，不能重新定义 `CreatureGroup` 的字段集合。

空间投影读取的最小字段：

```json
{
  "id": "night_wolf_pack_01",
  "species_id": "night_wolf",
  "count": 3,
  "location": {
    "scope": "world_chunk",
    "region_id": "north_slope_wilds",
    "chunk_id": "chunk_north_slope_13_08_00",
    "local_position": "west_edge"
  },
  "behavior_state": "stalking",
  "visibility": "hinted",
  "signs": ["howl", "tracks"]
}
```

规则：

```text
SpaceProjection 可以根据 CreatureGroup.location 计算 route_proximity、geometric_proximity、perceptual_proximity、direction_hint 和 dm_hint。
SpaceProjection 不得把 projection-only 的 name、disposition、awareness_state、distance_band 写回 CreatureGroup。
CreatureGroup 的物种、数量、行为和可见性字段以自然生态文档为准。
```

## 字段说明

本节解释本文件中出现的数据结构字段。实现时以本节为 schema 字段语义来源；JSON 示例只用于展示组合方式。

### 命名约定

| 字段 | 含义 |
| --- | --- |
| `type` | 只用于空间结构或 canonical schema 明确声明该字段的非 WorldObject 实体，例如 `Region.type`、`Site.type`、`LocationNode.type`、`Zone.type`。它回答“这个空间/实体是什么类别”。`CreatureGroup` 不在本文件定义 `type`。 |
| `object_type` | 只用于 `WorldObject` 的规则分类，例如 `portal`、`fixture`、`food`、`clue`。它回答“这个对象按哪套对象规则结算”。 |
| `id` | 稳定唯一标识。不能依赖中文名，不能因本地化、改名或玩家未知而改变。 |
| `name` | 显示名。是否向玩家或 AI 投影由 `DiscoveryState`、`KnowledgeState` 和 Projection 决定。 |
| `tags` | 非权威分类标签，只用于检索、生成权重、叙事和规则辅助判断。不能替代 `type`、`object_type` 或权威状态字段。 |

### 空间事实与主体发现边界

空间实体只表达客观事实：在哪里、如何连接、能否通行、物理上是否可见、有哪些观察线索。

以下字段不得出现在 `WorldChunk`、`ChunkEdge`、`RegionFeature`、`Settlement`、`Site`、`LocationNode`、`Zone` 或 `LocationEdge` 这类世界事实中：

```text
known_to_player
known_by
discovered_by
seen_by
visible_to_subjects
player_memory
npc_memory
ai_context
```

玩家、NPC 或群体是否知道某个 chunk、路径、入口、地点、阻挡或对象，必须写入 `DiscoveryState` 或 `KnowledgeState`。`SpaceProjection` 和 `AgentObservationSnapshot` 可以读取这些知识事实，再结合客观 `visibility`、`base_passability` 和 `effective_passability` 生成玩家或 AI 可见内容。

### World 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 当前世界实例 ID。一个存档或一次冒险应只有一个当前权威 World。 |
| `name` | 世界显示名。 |
| `seed` | 世界生成种子，对应 `RandomSeedMaterial.world_seed`。相同 RandomSeedMaterial 和规则版本下应生成一致结果。 |
| `version_lock` | 当前世界使用的 schema、registry、rule bundle 和内容包版本锁；必须与生成 manifest 及运行时入口一致。 |
| `version_lock.schema_version` | 世界底座 schema 版本。 |
| `version_lock.registry_hash` | registry bundle canonical hash。 |
| `version_lock.rule_bundle_hash` | 生成规则、validator 和 resolver bundle canonical hash。 |
| `version_lock.content_pack_hash` | 当前启用内容包集合 canonical hash。 |
| `active_content_pack_refs` | 当前世界启用的内容包引用列表。世界生成、对象实例化、生态目录都只能引用启用内容包。 |
| `active_content_pack_refs[].content_pack_id` | 内容包 ID。 |
| `active_content_pack_refs[].content_pack_version` | 内容包版本。 |
| `active_content_pack_refs[].content_pack_hash` | 内容包 canonical hash。 |
| `chunk_size_profiles` | 区块尺寸配置表，key 是尺寸 profile ID，例如 `wilderness_100m`。 |
| `chunk_size_profiles.*.width_meters` | 一个 chunk 在 x 方向代表的物理宽度。 |
| `chunk_size_profiles.*.height_meters` | 一个 chunk 在 y 方向代表的物理高度。 |
| `chunk_size_profiles.*.z_step_meters` | z 坐标每上升或下降 1 格代表的高度差。 |
| `current_actor_locations` | 当前所有需要精确追踪位置的 actor 位置表。key 是 actor ID，例如 `player`。 |

### Region 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 大区域 ID。 |
| `name` | 大区域显示名。 |
| `type` | 大区域类型，例如荒野、城镇区域、地下区域。 |
| `world_id` | 所属 World ID。 |
| `bounds_world` | Region 在世界米制坐标中的边界。x/y 使用半开区间 `[min_meters, max_meters)`，z_range 使用包含两端的整数层。 |
| `bounds_world.origin_meters` | Region 网格原点对应的世界坐标。 |
| `bounds_world.min_meters` | Region 覆盖范围的最小 x/y 米制坐标，包含端点。 |
| `bounds_world.max_meters` | Region 覆盖范围的最大 x/y 米制坐标，不包含端点。 |
| `bounds_world.z_range` | Region 允许的 z 层范围。 |
| `grid_id` | Region 使用的 `WorldChunkGrid` ID。 |
| `climate_profile` | 长期气候包络。具体字段见气候地形形成规则文档。 |
| `biome_tags` | 由气候、地形、水系、文明压力等推导出的生态标签。不能由 LLM 随意写入。 |
| `danger_tags` | 区域危险倾向标签，用于生态、遭遇和风险时钟生成。 |
| `factions` | 对该 Region 有影响力的势力列表。 |
| `factions[].id` | 势力 ID。 |
| `factions[].influence` | 势力在该 Region 的影响强度。 |
| `risk_clocks` | 区域级风险时钟表，key 是风险 ID。 |
| `risk_clocks.*.value` | 当前风险进度。 |
| `risk_clocks.*.max` | 风险触发或升级阈值。 |

### WorldChunkGrid 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 网格 ID。 |
| `region_id` | 所属 Region ID。 |
| `size_profile` | 该网格默认使用的 chunk 尺寸 profile。 |
| `origin_chunk` | 网格原点 chunk 坐标。 |
| `bounds_chunk` | 网格允许的 chunk 坐标范围。 |
| `bounds_chunk.min` | 最小 x/y/z chunk 坐标，包含端点。 |
| `bounds_chunk.max` | 最大 x/y/z chunk 坐标，包含端点。 |

### WorldChunk 字段

| 字段 | 含义 |
| --- | --- |
| `id` | chunk ID。 |
| `grid_id` | 所属 `WorldChunkGrid` ID。 |
| `region_id` | 所属 Region ID。 |
| `coord` | chunk 的 x/y/z 网格坐标。 |
| `size_profile` | 该 chunk 使用的尺寸 profile。允许覆盖 grid 默认值，但必须引用已定义 profile。 |
| `terrain` | chunk 的权威地形事实。字段含义见气候地形形成规则文档。 |
| `base_fields` | 世界生成阶段产生的连续基础场。字段含义见气候地形形成规则文档。 |
| `local_climate` | 相对 Region 长期气候的局部修正。由地形和水文候选派生，字段含义见气候地形形成规则文档。 |
| `biome_tags` | 该 chunk 的生态标签。由 formation/validator 推导。 |
| `site_slots` | chunk 上的 site 承载槽位。 |
| `site_slots.primary_site_id` | 该 chunk 的主 Site。空间基础物化时允许为 `null`；SitePlacement 创建完整可进入建筑后再填入对应 Site ID。 |
| `site_slots.secondary_site_ids` | 附属微型 Site 列表，例如井、告示牌、马槽。 |
| `tags` | chunk 的辅助标签。不能替代 `terrain` 或 `biome_tags`。 |

### ChunkEdge 字段

| 字段 | 含义 |
| --- | --- |
| `id` | chunk 边 ID。 |
| `source_chunk_id` | 有向 arc 的出发 chunk。 |
| `target_chunk_id` | 有向 arc 的目标 chunk。 |
| `direction` | 从 source 到 target 的方向描述。它是显示和校验辅助字段，不表示可自动反向通行。 |
| `adjacent` | 两个 chunk 是否物理接壤。接壤不代表可通行。 |
| `base_passability` | 静态基础通行状态，由静态地形、水文、道路和结构基础事实产生。 |
| `base_passability.state` | 静态通行枚举：`open`、`difficult`、`conditional`、`blocked`。 |
| `base_passability.conditions` | 静态条件，例如桥、浅滩、攀爬能力。 |
| `base_passability.blocked_reason` | 静态阻挡原因。 |
| `base_traversal` | 静态基础通行成本和风险。 |
| `base_traversal.base_time_minutes` | 静态基础耗时。静态可通行时必须是有限正数；静态 blocked 时可以为 `null`。 |
| `base_traversal.difficulty` | 静态移动难度。 |
| `base_traversal.movement_type` | 默认移动方式，例如步行、攀爬、游泳。 |
| `base_traversal.risk_tags` | 静态移动风险标签。 |
| `effective_passability` | 最终有效通行状态，只能由 `PassabilityReducer` 写入。 |
| `effective_passability.state` | 最终通行枚举：`open`、`difficult`、`conditional`、`blocked`。 |
| `effective_passability.conditions` | 当前仍需满足的条件，由 reducer 聚合。 |
| `effective_passability.blocked_reason` | 当前最终阻挡原因，由 reducer 稳定排序后生成。 |
| `effective_passability.source_refs` | 参与聚合的 base 或 override 来源引用。 |
| `effective_traversal` | 最终有效通行成本和风险，只能由 `PassabilityReducer` 写入。 |
| `effective_traversal.time_minutes` | 当前有效耗时。可达时必须是有限正数；不可达时为 `null`。 |
| `effective_traversal.difficulty` | 当前有效移动难度。 |
| `effective_traversal.movement_type` | 当前有效移动方式。 |
| `effective_traversal.risk_tags` | 当前有效风险标签。 |
| `effective_traversal.source_refs` | 参与聚合的 base 或 override 来源引用。 |
| `visibility` | 这条边的客观可观察线索，不表示某个主体已经知道它。 |
| `visibility.line_of_sight_from_source` | 从 source chunk 是否能直接看到目标方向或阻挡。 |
| `visibility.description` | DM 可用的路径/阻挡描述。 |

### RegionFeature / Settlement / TerrainFeature 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 区域特征 ID。 |
| `name` | 显示名。 |
| `type` | 特征类型，例如 `terrain_feature` 或 `settlement`。 |
| `region_id` | 所属 Region。 |
| `chunk_ids` | 组成该特征的一组 chunk。 |
| `dominant_terrain` | 主要地貌描述，用于叙事和生成权重。 |
| `entry_chunk_ids` | 可作为进入该 settlement 或特征的入口 chunk。 |

### Site 与 site_relations 字段

| 字段 | 含义 |
| --- | --- |
| `id` | Site ID。 |
| `name` | Site 显示名。 |
| `type` | Site 类型，例如旅店、小屋、井、遗迹。 |
| `parent_chunk_id` | Site 所在 chunk。Site 的空间父级必须是 chunk。 |
| `local_position` | Site 在 chunk 内的粗略局部位置，例如中心、东侧、路边。 |
| `footprint` | Site 占用的近似物理尺寸。 |
| `footprint.width_meters` | Site 宽度。 |
| `footprint.height_meters` | Site 高度。 |
| `entry_node_ids` | 可进入 Site 时的入口 `LocationNode` 列表。 |
| `tags` | Site 辅助标签。 |
| `state` | Site 当前状态，例如是否开放、是否可进入、是否受宵禁影响。 |
| `primary_site_id` | chunk 的主 Site。 |
| `secondary_site_ids` | chunk 内附属 Site。 |
| `site_relations` | 同一 chunk 内多个 Site 之间的局部关系。 |
| `site_relations[].source_site_id` | 关系源 Site。 |
| `site_relations[].target_site_id` | 关系目标 Site。 |
| `site_relations[].relation` | 空间关系，例如 behind、across_street。 |
| `site_relations[].distance_meters` | 两个 Site 的近似距离。 |
| `site_relations[].base_time_minutes` | 两个 Site 之间移动的基础耗时。 |
| `site_relations[].visibility` | 从源 Site 能否看到目标 Site。 |
| `site_relations[].passability` | 两个 Site 之间的通行状态。 |

### PlaceHierarchyRegistry / LocationChildGenerationContext 字段

| 字段 | 含义 |
| --- | --- |
| `registry_id` | 地点层级 registry 版本 ID。必须固定在 rule bundle 中。 |
| `entries[].place_type` | 地点类型，例如 town、street、inn、front_hall、zone。 |
| `entries[].hierarchy_depth` | 层级深度。数值越大表示越细的地点。 |
| `entries[].allowed_child_types` | 该地点类型允许生成的子地点类型闭集。 |
| `entries[].allowed_child_count_range` | 该父类型允许生成的子地点数量范围。 |
| `entries[].allowed_zone_types` | 该地点类型允许生成的 Zone 类型闭集。 |
| `parent_id` | 本次生成的父地点 ID。 |
| `parent_type` | 父地点类型，必须存在于 `PlaceHierarchyRegistry`。 |
| `parent_depth` | 父地点层级深度。 |
| `parent_site_id` | 若父级在 Site 内部，指向所属 Site。 |
| `id_prefix` | 子地点 ID 前缀。由系统提供，LLM 不能覆盖。 |
| `allowed_child_types` | 本次生成允许的子地点类型。来自 registry 和父实例状态。 |
| `allowed_zone_types` | 本次生成允许的 Zone 类型。 |

### LocationNode / Zone 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 内部地点节点 ID。 |
| `name` | 内部地点显示名。 |
| `type` | 内部地点类型，例如房间、走廊、楼梯平台、入口。 |
| `site_id` | 所属 Site。 |
| `parent_id` | 父级空间 ID。简单建筑可直接指向 Site；复杂建筑可指向上层 LocationNode。 |
| `display_path` | UI 和 DM 使用的显示路径，不作为权威空间父子关系。 |
| `zones` | 该节点内的局部区域列表。Zone 不再继续嵌套。 |
| `zones[].id` | Zone ID。 |
| `zones[].name` | Zone 显示名。 |
| `zones[].type` | Zone 类型，例如门口、柜台区、员工区。 |
| `zones[].access` | Zone 访问限制。为空表示默认可接近。 |
| `zones[].access.state` | 访问状态，例如 open、restricted、blocked。 |
| `zones[].access.requires` | 进入或使用该 Zone 需要满足的状态/权限 ID。 |
| `zones[].access.blocked_reason` | 当前无法接近时给 DM 使用的原因。 |
| `environment` | 该 LocationNode 的环境状态。 |
| `environment.light` | 光照水平。 |
| `environment.noise` | 噪音水平。 |
| `environment.crowding` | 拥挤程度。 |
| `tags` | 内部地点辅助标签。 |

### LocationEdge 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 内部地点边 ID。 |
| `source_node_id` | 有向 arc 的出发 LocationNode。 |
| `target_node_id` | 有向 arc 的目标 LocationNode。 |
| `relation` | 两个节点的连接关系，例如 doorway、stairs、corridor。 |
| `portal_object_id` | 表示这条连接的门、楼梯、破口等 `WorldObject` ID。 |
| `direction` | 从 source 到 target 的方向描述，例如 toward_kitchen、toward_front_hall、upstairs、downstairs。不能使用 bidirectional 表示双向。 |
| `base_passability` | 静态基础通行状态，语义与 `ChunkEdge.base_passability` 一致。 |
| `base_traversal` | 静态基础通行成本和风险。 |
| `effective_passability` | 最终有效通行状态，只能由 `PassabilityReducer` 写入。 |
| `effective_passability.conditions[].type` | 条件类型，例如 permission、key、state。 |
| `effective_passability.conditions[].required` | 需要满足的条件 ID。 |
| `effective_traversal.time_minutes` | 当前有效内部移动耗时。可达时必须是有限正数；不可达时为 `null`。 |
| `effective_traversal.scope` | 移动范围，例如 indoor、town、wilderness。 |
| `effective_traversal.movement_type` | 移动方式。 |
| `effective_traversal.risk_delta` | 移动带来的风险增量。 |
| `visibility` | 这条内部连接的客观可观察线索，不表示某个主体已经知道它。 |
| `visibility.visible_from_source` | 从 source 节点是否物理可见。 |
| `visibility.visible_from_target` | 从 target 节点是否物理可见。 |
| `visibility.hint_text` | 未直接进入时可给出的提示文本。 |

### SiteBoundaryEdge 字段

| 字段 | 含义 |
| --- | --- |
| `id` | Site 边界边 ID。 |
| `edge_type` | 边界边类型。P1 闭集为 `site_entry`、`site_exit`。 |
| `source.scope` | source 位置范围。`site_entry` 必须为 `world_chunk`，`site_exit` 必须为 `site_node`。 |
| `source.chunk_id` | 外部 source chunk。仅 `source.scope=world_chunk` 时存在。 |
| `source.site_id` | 内部 source Site。仅 `source.scope=site_node` 时存在。 |
| `source.node_id` | 内部 source LocationNode。 |
| `source.zone_id` | 内部 source Zone。 |
| `source.local_position` | 外部或内部入口附近的粗略位置。 |
| `target.scope` | target 位置范围。`site_entry` 必须为 `site_node`，`site_exit` 必须为 `world_chunk`。 |
| `target.chunk_id` | 外部 target chunk。仅 `target.scope=world_chunk` 时存在。 |
| `target.site_id` | 内部 target Site。仅 `target.scope=site_node` 时存在。 |
| `target.node_id` | 内部 target LocationNode。 |
| `target.zone_id` | 内部 target Zone。 |
| `target.local_position` | 进入或离开后的粗略位置。 |
| `portal_object_id` | 表示入口/出口的门、洞口、梯子、窗户、破口等 WorldObject ID。 |
| `base_passability` | 静态基础通行状态，语义与 `ChunkEdge` 和 `LocationEdge` 一致。 |
| `base_traversal` | 静态基础通行成本和风险。 |
| `effective_passability` | 最终有效通行状态，只能由 `PassabilityReducer` 写入。 |
| `effective_traversal` | 最终有效通行成本，只能由 `PassabilityReducer` 写入。 |

### ObjectPlacement 字段

| 字段 | 含义 |
| --- | --- |
| `kind` | 对象位置类型，例如 `zone`、`chunk`、`on_object`、`contained_by_parent`。 |
| `chunk_id` | 当 `kind=chunk` 时，对象所在 chunk。 |
| `node_id` | 当 `kind=zone` 时，对象所在 LocationNode。 |
| `zone_id` | 当 `kind=zone` 时，对象所在 Zone。 |
| `object_id` | 当对象在另一个对象上、下、旁或附着时，被引用的承载对象 ID。`contained_by_parent` 不允许携带 `object_id`。 |
| `surface` | 当对象位于另一个对象表面时，表面名称。 |
| `local_position` | 在 chunk、node 或 zone 内的粗略局部位置。 |
| `relation` | 对象与承载空间或承载对象的空间关系。 |
| `reachability` | 当前是否可触达。可见不等于可触达。 |

对象是否可见由 `WorldObject.visibility` 决定，不写在 `placement` 内。

### ActorLocation 字段

| 字段 | 含义 |
| --- | --- |
| `actor_id` | 被定位的角色 ID。玩家使用 `player`。 |
| `location.scope` | 位置范围：`world_chunk` 表示外部 chunk，`site_node` 表示 Site 内部节点。 |
| `location.region_id` | 外部位置所属 Region。 |
| `location.chunk_id` | 外部位置所在 chunk。 |
| `location.site_id` | 内部位置所属 Site。 |
| `location.node_id` | 内部位置所在 LocationNode。 |
| `location.zone_id` | 内部位置所在 Zone。 |
| `location.local_position` | 在当前 chunk/node/zone 内的粗略位置。 |

`ActorLocation` 不能由 LLM proposal、DM 文本或通用 patch 自由拼接。运行时位置只能由 `ChunkTravelResolver`、`SiteBoundaryResolver`、`LocationMovementResolver` 或 `ZoneAccessResolver` 根据已存在的 edge、zone 和 access 规则生成。

### CreatureGroup 空间读取规则

`CreatureGroup` 的字段解释见 [自然生态与资源规则](./natural-ecology-rules.md)。空间文档只声明读取和投影规则：

| 读取项 | 含义 |
| --- | --- |
| `CreatureGroup.location` | 群体当前位置，结构必须与 ActorLocation 的 `location` 一致。 |
| `CreatureGroup.location.scope` | 群体位于外部 chunk 还是 Site 内部节点。 |
| `CreatureGroup.location.chunk_id` | 外部位置所在 chunk。 |
| `CreatureGroup.location.node_id` | 内部位置所在 LocationNode。 |
| `CreatureGroup.location.zone_id` | 内部位置所在 Zone。 |
| `CreatureGroup.visibility` | 生态权威可见性。SpaceProjection 只能读取并映射为 awareness_state。 |
| `CreatureGroup.signs` | 生态权威痕迹。SpaceProjection 可以投影为 dm_hint。 |

Projection-only 字段：

| 字段 | 含义 |
| --- | --- |
| `creature_awareness[].name` | 根据 species catalog 或 DM 本地化生成的显示名，不写回 CreatureGroup。 |
| `creature_awareness[].disposition` | 基于生态、社会或遭遇规则推导的临时立场提示，不写回 CreatureGroup。 |
| `creature_awareness[].awareness_state` | 对玩家当前感知状态的投影结果，不写回 CreatureGroup。 |
| `creature_awareness[].route_proximity` | 基于可通行有向 ChunkEdge 路径计算的可达关系，不写回 CreatureGroup。 |
| `creature_awareness[].geometric_proximity` | 基于 chunk 坐标和物理相邻关系计算的几何接近关系，不写回 CreatureGroup。 |
| `creature_awareness[].perceptual_proximity` | 基于声音、视线、气味、痕迹和知识状态计算的感知接近关系，不写回 CreatureGroup。 |
| `creature_awareness[].dm_hint` | 叙事提示，不写回 CreatureGroup。 |

### SpaceProjection 返回字段

| 字段 | 含义 |
| --- | --- |
| `location.scope` | 当前投影范围。 |
| `location.display_name` | 玩家可见地点名。 |
| `location.display_path` | 玩家可见路径，不作为权威层级。 |
| `visible_sites` | 当前可见或可感知的 Site 列表。 |
| `visible_sites[].type` | Site 类型。Site 不是 WorldObject，因此使用 `type`。 |
| `visible_actors` | 当前可见或可感知的 NPC、角色或具名生物列表。 |
| `visible_actors[].entity_type` | 非物品实体类型，例如 npc。它不是 `WorldObject.object_type`。 |
| `visible_objects` | 当前可见或可交互的对象列表。 |
| `visible_objects[].object_type` | 对象规则类型。只用于 WorldObject。 |
| `visible_objects[].where` | 给玩家看的相对位置描述。 |
| `visible_objects[].affordances` | 玩家可尝试的动作。 |
| `exits` | 当前可见或已知出口/路径列表。 |
| `exits[].passable` | 当前是否可直接通行。 |
| `exits[].route_state` | 该出口当前可达状态：reachable、blocked、conditional_unmet、unknown。 |
| `exits[].blocked_reason` | 不可通行时的原因。 |
| `creature_awareness` | 玩家当前对生物/群体的感知投影。 |
| `creature_awareness[].route_proximity` | 基于当前可通行有向 ChunkEdge 路径的可达关系。 |
| `creature_awareness[].geometric_proximity` | 基于 chunk 坐标和物理相邻关系的几何接近关系。 |
| `creature_awareness[].perceptual_proximity` | 基于声音、视线、气味、痕迹和知识状态的感知接近关系。 |
| `creature_awareness[].dm_hint` | DM 可用的感知描述。 |
| `hidden_system_notes` | 不直接展示给玩家，但供 DM 和动作解析使用的隐藏事实。 |

## 空间不变量

实现时必须加入 validator，保证以下规则成立：

1. 外部空间权威层级为 `World -> Region -> WorldChunk -> Site`。
2. 内部空间权威层级为 `Site -> LocationNode -> Zone`。
3. 地点生成必须读取 `PlaceHierarchyRegistry` 和 `LocationChildGenerationContext`；生成器输出的 `child_type` 必须属于 `allowed_child_types`。
4. 子地点 `hierarchy_depth` 必须大于父地点 `hierarchy_depth`；`Zone` 必须是叶子节点。
5. LLM proposal 不得直接写最终 `site_id`、`node_id`、`zone_id`、`parent_id` 或 `id_prefix`；这些字段必须由 `LocationMaterializer` 写入。
6. `Region.bounds_world` 必须存在，并且 `max_meters` 大于 `min_meters`。
7. `Region.grid_id` 必须引用属于该 Region 的 `WorldChunkGrid`。
8. `WorldChunkGrid.size_profile` 必须引用已定义尺寸 profile。
9. `WorldChunkGrid.bounds_chunk` 必须能被 `Region.bounds_world` 和 size profile 容纳。
10. `WorldChunk.grid_id` 必须引用存在的 `WorldChunkGrid`。
11. `WorldChunk.region_id` 必须等于其 grid 所属 Region。
12. `WorldChunk.coord(x,y,z)` 必须落在 `WorldChunkGrid.bounds_chunk` 内。
13. `WorldChunk.coord(x,y,z)` 在同一 grid 内唯一。
14. `WorldChunk.size_profile` 必须等于所属 grid 的 `size_profile`。
15. `Site.parent_chunk_id` 必须引用存在的 `WorldChunk`。
16. `Region` 不能直接承载 `Site`。
17. 一个 chunk 默认只能有一个 `primary_site`。
18. `secondary_site` 只能是附属、小型、不可复杂进入的 site。
19. chunk 内存在多个 site 时必须定义 `site_relations`。
20. 两个完整可进入建筑不能放在同一个 chunk。
21. 没有 `site_relations` 的多个 site 数据必须被 validator 拒绝。
22. `ChunkEdge.source_chunk_id` 和 `target_chunk_id` 必须引用存在的 `WorldChunk`。
23. `ChunkEdge` 两端 chunk 必须属于同一个 grid，除非 edge 显式声明 `edge_scope=cross_region`。
24. `cross_region` edge 必须连接两个 Region 边界 chunk。
25. 坐标相邻不能自动生成通行结果，移动必须通过 `ChunkEdge`。
26. `LocationEdge.source_node_id` 和 `target_node_id` 必须引用存在的 `LocationNode`。
27. `LocationEdge.portal_object_id` 必须引用一个 `object_type=portal` 或具备 `enter/leave` 相关 affordance 的对象。
28. `ChunkEdge` 和 `LocationEdge` 都是有向 arc，不得被 resolver 自动反向解释。
29. 双向外部路径必须存在两条反向 `ChunkEdge`。
30. 双向内部路径必须存在两条反向 `LocationEdge`。
31. `LocationEdge.direction` 不能使用 `bidirectional`；双向必须展开成两条 arc。
32. `SiteBoundaryEdge.edge_type` 必须属于 `site_entry`、`site_exit`。
33. `site_entry` 必须从 `source.scope=world_chunk` 指向 `target.scope=site_node`。
34. `site_exit` 必须从 `source.scope=site_node` 指向 `target.scope=world_chunk`。
35. `SiteBoundaryEdge.portal_object_id` 必须引用存在的 `object_type=portal` 或具备 `enter/leave` affordance 的对象。
36. `SiteBoundaryEdge` 内部端的 `site_id/node_id/zone_id` 必须逐级匹配：node 属于 site，zone 属于 node。
37. `Site.entry_node_ids` 中每个 node 必须至少有一条可用于进入的 `SiteBoundaryEdge(edge_type=site_entry)` 指向它。
38. `enter_site` 和 `leave_site` 不得直接使用 `Site.parent_chunk_id` 改写 ActorLocation。
39. `base_passability` 和 `base_traversal` 只能由静态边生成/静态通行派生阶段写入。
40. `effective_passability` 和 `effective_traversal` 只能由 `PassabilityReducer` 写入。
41. `effective_passability.state=open` 或 `difficult` 时，`effective_traversal.time_minutes` 必须是有限正数。
42. `effective_passability.state=conditional` 且条件满足时，`effective_traversal.time_minutes` 必须是有限正数。
43. `effective_passability.state=blocked` 时，`effective_traversal.time_minutes` 必须为 `null` 或被 RouteResolver 解释为 `Infinity`，不能进入可达路径。
44. `conditional` 条件不满足时，effective cost 必须是 `Infinity`，不能进入可达路径。
45. RouteResolver 必须按有向 edge 搜索，且只能读取 `effective_passability` 和 `effective_traversal`。
46. RouteResolver 不能因为 chunk 坐标相邻或 LocationNode parent 相同而推导通行。
47. 同成本路径必须按 edge_id 序列字典序选择稳定结果。
48. `route_band` 只能在 `route_state=reachable` 时存在；blocked、unknown 或条件不满足时必须为 `null`。
49. `route_band` 的时间区间必须是无重叠半开区间。
50. `geometric_proximity`、`route_proximity` 和 `perceptual_proximity` 必须分开计算，不能互相覆盖。
51. `Zone` 不能包含子 `Zone`。
52. `Object` 不能通过 `parent_id` 进入空间层级，只能通过 `placement` 定位。
53. `chunk` placement 必须引用存在的 `chunk_id`。
54. `zone` placement 必须引用存在的 `node_id` 和 `zone_id`。
55. `on_object`、`under_object`、`attached_to_object`、`near_object` 必须引用存在的 `object_id`；新状态不得写入 `inside_object`。
56. `contained_by_parent` 不允许携带 `object_id`，其父容器必须能通过唯一一个 `components.container.contained_object_ids` 反查得到。
57. 对象位置链不能形成循环。
58. 可见/可互动对象的位置链必须能解析到当前 `WorldChunk`、当前 `LocationNode + Zone`，或当前空间内角色携带。
59. 玩家外部移动只能通过 `ChunkEdge` 成功结算。
60. 玩家内部移动只能通过 `LocationEdge` 成功结算。
61. 玩家进入或离开 Site 只能通过 `SiteBoundaryEdge` 成功结算。
62. `ActorLocation.location.scope=world_chunk` 时必须存在 `region_id/chunk_id`，且不得携带 `site_id/node_id/zone_id`。
63. `ActorLocation.location.scope=site_node` 时必须存在 `site_id/node_id/zone_id`，且不得把 `chunk_id` 当作当前内部位置。
64. `ActorLocation` 的 `node_id` 必须属于 `site_id`，`zone_id` 必须属于 `node_id.zones`。
65. `approach` 只能定位到当前 node 内存在的 Zone。
66. `approach` 和 `search` 必须共用 `ZoneAccessResolver`；`access.state=restricted` 时必须满足 `requires`，`access.state=blocked` 时不得改变 `zone_id`。
67. DM 最终旁白中的当前可见主要对象、site、出口、附近生物，必须在同轮返回前进入状态或对应空间记忆。
68. 交易、拾取、消耗、破坏后，相关对象的 `placement` 必须同步变化。
69. P0 初始空间生成只允许 `generation_mode=procedural` 和 `coverage_mode=complete`。
70. `WorldLayoutCandidate`、`RegionLayoutCandidate`、`WorldChunkGridLayoutCandidate` 和 `WorldChunkLayoutCandidate` 只能存在于 generation_audit，不能进入 world_facts。
71. 候选 payload 中的目标 ID 必须引用同一 manifest 内已验证候选，不能伪装成已提交实体引用。
72. 每个 P0 Region 的 `expected_chunk_count` 必须小于等于 256。
73. `WorldChunkLayoutCandidate.coord` 集合必须恰好等于所属 grid 边界内三轴整数坐标的笛卡尔积。
74. P0 初始 `WorldChunkLayoutCandidate.size_profile` 必须等于所属 grid 的 `size_profile`。
75. Region x/y 半开物理跨度必须等于对应 chunk 数量乘以尺寸 profile；z_range 必须覆盖 grid 的 z 坐标范围。
76. `SpatialFoundationMaterializer` 只能读取已经通过 validator 的完整候选集合。
77. `World`、全部 `Region`、全部 `WorldChunkGrid` 和全部 `WorldChunk` 必须属于同一原子提交组。
78. 任一 `WorldChunk` 缺少 `base_fields`、`terrain`、`local_climate` 或 `biome_tags` 时，空间基础物化必须整体失败。
79. `World.version_lock` 必须与 `RandomSeedMaterial`、WorldGenerationManifest 和 `StaticWorldRuntimeState.version_lock` 一致。

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
    "chunk_id": "chunk_north_slope_12_08_00",
    "display_name": "北坡脊线，猎人小屋附近",
    "coord": { "x": 12, "y": 8, "z": 0 },
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
      "object_type": "clue",
      "where": "西侧岩路旁",
      "affordances": ["observe", "read"]
    }
  ],
  "exits": [
    {
      "edge_id": "edge_chunk_11_08_00_to_12_08_00",
      "target_chunk_id": "chunk_north_slope_11_08_00",
      "name": "沿脊线回到西侧岩台",
      "direction": "west",
      "route_state": "reachable",
      "passable": true,
      "base_time_minutes": 8
    },
    {
      "edge_id": "edge_chunk_12_08_00_to_13_08_00",
      "target_chunk_id": "chunk_north_slope_13_08_00",
      "name": "东侧断崖",
      "direction": "east",
      "route_state": "blocked",
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
      "route_proximity": {
        "route_state": "blocked",
        "route_band": null,
        "route_time_minutes": null
      },
      "geometric_proximity": {
        "band": "adjacent"
      },
      "perceptual_proximity": {
        "band": "near",
        "evidence": ["sound"]
      },
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
  "visible_actors": [
    {
      "id": "innkeeper_01",
      "name": "店主",
      "entity_type": "npc",
      "where": "柜台后",
      "affordances": ["talk", "negotiate", "purchase"]
    }
  ],
  "visible_objects": [
    {
      "id": "counter_01",
      "name": "旧木柜台",
      "object_type": "fixture",
      "where": "柜台区",
      "affordances": ["observe"]
    },
    {
      "id": "stew_bowl_01",
      "name": "热炖菜一碗",
      "object_type": "food",
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

### 外部距离与可达性分级

空间投影必须分离三类关系：

| 类型 | 来源 | 用途 |
| --- | --- | --- |
| `geometric_proximity` | chunk 坐标、同 chunk、相邻关系、视线几何 | 判断物理上近不近，不代表能走到。 |
| `route_proximity` | 只使用当前可通行有向 `ChunkEdge` 的最短路径 | 判断玩家能否走到、要多久。 |
| `perceptual_proximity` | 光照、视线、声音、气味、痕迹、遮挡和知识状态 | 判断玩家能感知到什么，不暴露上帝视角。 |

`route_proximity` 的最短路规则：

```text
输入 edge：只使用 source -> target 方向。
可入图 edge：effective_passability=open、difficult，或 conditional 且当前条件满足。
不可入图 edge：effective_passability=blocked，或 conditional 但条件不满足。
edge cost：effective_traversal.time_minutes，必须是有限正数。
blocked / 条件不满足 cost：Infinity，不进入可达路径。
同成本路径 tie-break：按 edge_id 序列字典序升序选择。
```

`route_band` 只在 `route_state=reachable` 时计算。无可达路径或玩家没有足够信息时，不使用距离 band 表示，而是使用 `route_state=blocked` 或 `route_state=unknown`。

| route_band | 半开区间 | 玩家表述 |
| --- | --- | --- |
| same_chunk | 同一 chunk，route_time_minutes = 0 | 同一区块，可能直接遭遇 |
| near | 不同 chunk，route_time_minutes >= 0 且 < 10 | 很近，短时间内可接触 |
| nearby | route_time_minutes >= 10 且 < 30 | 较近，能听见或发现明显痕迹 |
| far | route_time_minutes >= 30 且 < 90 | 较远，需要赶路或追踪 |
| distant | route_time_minutes >= 90 | 很远，只能通过传闻、远声或痕迹感知 |

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
  "route_proximity": {
    "route_state": "blocked",
    "route_band": null,
    "route_time_minutes": null,
    "blocking_edge_id": "edge_chunk_12_08_00_to_13_08_00",
    "blocking_reason": "东侧是断崖，不能直接通行"
  },
  "geometric_proximity": {
    "band": "adjacent",
    "line_of_sight": false
  },
  "perceptual_proximity": {
    "band": "near",
    "evidence": ["sound"],
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
-> 从 current chunk 出发读取 source_chunk_id=current 的有向 ChunkEdge
-> 过滤可入图 edge：open/difficult，或 conditional 且条件满足
-> blocked / conditional 条件不满足 edge 不进入可达路径
-> 按 effective_traversal.time_minutes 计算最短路径
-> 同成本路径按 edge_id 序列字典序 tie-break
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
确认 player location.scope=world_chunk
-> 查找 source=当前 chunk 且 target.site_id=hunter_cabin_01 的 SiteBoundaryEdge(edge_type=site_entry)
-> 检查 site state.enterable
-> 检查 portal object 状态
-> 检查 SiteBoundaryEdge.effective_passability
-> 确认 edge.target.node_id 属于 target_site.entry_node_ids
-> 更新 player location.scope = site_node
-> 将 player location 更新为 edge.target.site_id / node_id / zone_id
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

成功后位置由显式 `SiteBoundaryEdge(edge_type=site_exit)` 决定，不能直接回到 `Site.parent_chunk_id`：

```json
{
  "scope": "world_chunk",
  "chunk_id": "chunk_graystone_10_10_0",
  "local_position": "near_site:old_furnace_inn"
}
```

结算步骤：

```text
确认 player location.scope=site_node
-> 查找 source=当前 site_id/node_id/zone_id 的 SiteBoundaryEdge(edge_type=site_exit)
-> 检查 portal object 状态
-> 检查 SiteBoundaryEdge.effective_passability
-> 将 player location 更新为 edge.target.chunk_id / local_position
-> 刷新 SpaceProjection
-> 写入 SiteLeftEvent
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
-> 查找 source_node_id=current 且 target_node_id=target 的有向 LocationEdge
-> 检查 portal object 状态
-> 检查 effective_passability.conditions
-> blocked / conditional 条件不满足 edge 不进入可达路径
-> 计算 effective_traversal 时间、风险和资源变化
-> 成功后更新 player current node_id / zone_id
-> 刷新 SpaceProjection
-> 形成 event_type=LocationChangedEvent 的 StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry
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

结算必须通过 `ZoneAccessResolver`：

```text
读取 actor.current_node_id
-> 确认 target_zone_id 属于 current_node.zones
-> 读取 target_zone.access
-> access.state=open 时允许靠近
-> access.state=restricted 时检查 requires 是否满足
-> access.state=blocked 时拒绝并输出 blocked_reason
-> 成功后只更新 current_zone_id，不改变 current_node_id
-> 形成 event_type=ZoneChangedEvent 的 StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry
```

时间通常为 1-3 分钟，可能改变可见性、可达性和 NPC 反应。

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
通过 ZoneAccessResolver 检查 Zone access
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

- [2026-07-08-isekai-scene-object-structuring-design.md](../../2026-07-08-isekai-scene-object-structuring-design.md)
- [2026-07-08-isekai-content-agnostic-refactor-design.md](../../2026-07-08-isekai-content-agnostic-refactor-design.md)
- [2026-07-08-isekai-llm-intent-resolution-design.md](../../2026-07-08-isekai-llm-intent-resolution-design.md)

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
- `PlaceHierarchyRegistry`、`LocationChildGenerationContext`、`SiteBoundaryEdge` schema。
- 位置链解析器 `resolve_object_placement(object_id)`。
- `SiteBoundaryResolver`、`ZoneAccessResolver`、`LocationHierarchyValidator`。

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
- `enter_site` 必须通过 `SiteBoundaryEdge(edge_type=site_entry)`。
- `leave_site` 必须通过 `SiteBoundaryEdge(edge_type=site_exit)`。
- `enter_location` 必须通过 `LocationEdge`。
- `approach` 必须通过 `ZoneAccessResolver`，成功后只改变 `current_zone_id`。
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
- `test_p0_spatial_layout_is_procedural_complete_grid`
- `test_spatial_layout_candidate_not_committed_as_world_fact`
- `test_candidate_target_reference_stays_inside_manifest`
- `test_complete_grid_count_matches_cartesian_product`
- `test_complete_grid_rejects_missing_coordinate`
- `test_complete_grid_rejects_duplicate_coordinate`
- `test_complete_grid_rejects_more_than_256_chunks_per_region`
- `test_region_physical_bounds_match_grid_and_size_profile`
- `test_spatial_foundation_materialization_is_atomic`
- `test_spatial_foundation_rejects_chunk_missing_physical_candidates`
- `test_world_version_lock_matches_generation_manifest`
- `test_region_requires_world_bounds`
- `test_world_chunk_grid_requires_chunk_bounds`
- `test_world_chunk_coord_must_be_inside_grid_bounds`
- `test_world_chunk_grid_region_must_match_chunk_region`
- `test_site_requires_parent_chunk`
- `test_region_cannot_directly_contain_site`
- `test_adjacent_chunks_are_not_passable_without_chunk_edge`
- `test_chunk_edge_is_directed_arc`
- `test_chunk_edge_reverse_requires_separate_edge`
- `test_location_edge_is_directed_arc`
- `test_location_edge_rejects_bidirectional_direction`
- `test_non_cross_region_chunk_edge_cannot_cross_grid`
- `test_cross_region_chunk_edge_requires_boundary_chunks`
- `test_blocked_chunk_edge_does_not_change_current_chunk`
- `test_blocked_edge_is_not_used_by_route_resolver`
- `test_open_edge_requires_positive_finite_cost`
- `test_conditional_unmet_edge_has_infinite_effective_cost`
- `test_same_cost_routes_use_edge_id_sequence_tiebreak`
- `test_route_bands_are_half_open_and_non_overlapping`
- `test_geometric_route_and_perceptual_proximity_are_separate`
- `test_chunk_rejects_multiple_primary_sites`
- `test_chunk_multiple_sites_require_site_relations`
- `test_two_full_enterable_sites_cannot_share_chunk`
- `test_object_placement_chain_resolves_chunk_root`
- `test_object_placement_chain_resolves_zone_root`
- `test_object_placement_cycle_is_rejected`
- `test_current_space_query_does_not_advance_time`
- `test_observe_reveals_hinted_object_site_or_creature_sign`
- `test_travel_requires_chunk_edge`
- `test_location_child_generation_uses_allowed_child_types`
- `test_location_materializer_assigns_child_ids_under_parent_context`
- `test_location_hierarchy_rejects_child_depth_not_greater_than_parent`
- `test_actor_location_cannot_be_llm_written`
- `test_actor_location_site_node_zone_chain_must_match`
- `test_enter_site_requires_site_boundary_entry_edge`
- `test_leave_site_requires_site_boundary_exit_edge`
- `test_enter_site_blocked_when_boundary_portal_locked`
- `test_leave_site_from_second_floor_requires_explicit_exit_edge`
- `test_enter_location_requires_location_edge`
- `test_approach_zone_checks_zone_access`
- `test_approach_restricted_zone_without_permission_does_not_change_zone`
- `test_search_and_approach_share_zone_access_resolver`
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
18. P0 初始空间使用程序生成的小型完整网格；示例默认值为 8 × 8 × 1，单 Region 硬上限为 256 个 chunk。
19. 空间布局先以四种独立 Candidate 形成，候选不属于权威 WorldState。
20. `World`、`Region`、`WorldChunkGrid` 和 `WorldChunk` 只能在气候及物理候选完整后原子物化。
21. 初始空间物化不允许创建只有 ID 和坐标、缺少物理字段的半成品 WorldChunk。
