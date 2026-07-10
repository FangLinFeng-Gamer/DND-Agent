# 异世界模式地点与空间规则设计

## 背景

当前异世界模式的主要一致性问题不是 DM 文本不够丰富，而是世界状态缺少稳定空间模型：

- 玩家已经进入某个地点，界面和后端仍可能显示上一个地点的对象。
- DM 旁白提到柜台、钥匙、后厨门、马车破口，但这些对象没有明确位置。
- 玩家问“这里有什么”时，系统容易让模型从文本里猜，而不是从世界状态查询。
- 玩家尝试进入、靠近、搜索、拾取时，目标可能被当成地点、区域、物品或泛化环境，导致结算不一致。

本设计将地点/空间从模糊字符串改成可查询、可校验、可投影的权威状态。它借鉴《矮人要塞》的核心原则：世界先存在，行为在世界上结算，叙事只是世界状态的投影。但本项目不复刻 DF 的 tile 级模拟，而采用适合文字 DM 的语义空间图。

## 目标

- 建立一套权威地点层级：`World -> Region -> Site -> LocationNode -> Zone`。
- 用 `LocationEdge` 表示地点之间的通行关系，不能用 `parent_id` 推导能否移动。
- 用 `ObjectPlacement` 表示物体、NPC、设施、门、容器、线索在空间中的具体位置。
- 让“当前空间有什么”“能去哪里”“能看见什么”“能摸到什么”全部来自确定性空间投影查询。
- 让 DM 旁白、UI 可互动列表、动作目标绑定共用同一份空间投影结果。
- 允许 LLM 提出地点、对象和空间关系，但必须经过后端 validator 后才进入权威世界状态。

## 非目标

- 不实现 DF 式 tile 网格、z-level、液体流动、逐格寻路和完整物理模拟。
- 不把每个“旁边、角落、背后、左侧”都升格成地点层级。
- 不让 LLM 直接创建最终地点、移动玩家、发放物品或修改资源。
- 不通过硬编码具体地点名、物品名、NPC 名来解决空间一致性。
- 不要求本阶段重建数据库表；第一阶段可继续存入 `world_state_json`。

## 核心原则

### 1. 世界状态是唯一事实源

DM 可以描述世界，但不能让描述本身成为事实。最终 DM 旁白中出现的当前可见对象、地点入口、NPC、可拾取物，必须已经存在于权威世界状态，或在本轮通过 validator 后写入状态。

### 2. 地点层级回答“属于哪里”

`parent_id` 只表达归属关系，例如：

```text
前厅 属于 旧炉旅店
旧炉旅店 属于 灰石镇
```

归属关系不表示玩家可以直接移动。

### 3. 地点边回答“能去哪里”

玩家从当前地点能否去另一个地点，必须由 `LocationEdge` 决定。门、楼梯、破口、道路、地窖口等连接实体必须建成 `portal` 对象，并由 `LocationEdge.portal_object_id` 引用。

### 4. 对象不属于地点层级

对象通过 `ObjectPlacement` 挂载到 `Zone`、其他对象、角色身上或玩家物品栏。对象可以递归挂载，但最终必须能追溯到一个 `LocationNode + Zone`，除非它在玩家背包、角色携带、远处传闻或已移除状态。

### 5. 细节由 Zone、Placement 和 Relation 表达

权威空间层级保持稳定。更细的空间描述，例如“柜台后”“酒桶旁”“破毯子下面”“车厢破口边”，优先通过以下结构表达：

- `Zone`
- `ObjectPlacement`
- `SpatialRelation`
- `access_sides`
- `visibility`
- `reachability`

不要把每个局部描述都新建成 `LocationNode`。

## 权威空间层级

第一阶段固定使用 5 层：

```text
World
-> Region
-> Site
-> LocationNode
-> Zone
```

对象不算空间层级。

### 层级职责

| 层级 | 职责 | 示例 |
| --- | --- | --- |
| World | 一局冒险的世界容器、随机种子、内容包加载范围 | 当前异世界 |
| Region | 大区域、气候、生态、势力、总体风险 | 灰石镇、北坡荒野 |
| Site | 具体据点、建筑、野外点、废墟、资源点 | 旧炉旅店、废弃马车、猎人小屋 |
| LocationNode | 玩家可进入/停留/切换场景的实际空间 | 前厅、后厨、二楼走廊、马车外侧 |
| Zone | 场景内部局部区域，支持靠近、观察、搜索和权限 | 柜台区、炉火旁、黑暗角落、破口边 |

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

## 数据模型

### World

```json
{
  "id": "isekai_world_001",
  "name": "当前异世界",
  "seed": "adv_10_seed",
  "active_content_pack_ids": ["old_furnace_inn_p1"],
  "current_actor_locations": {
    "player": {
      "node_id": "old_furnace_inn_front_hall",
      "zone_id": "entrance"
    }
  }
}
```

### Region

```json
{
  "id": "graystone_town_region",
  "name": "灰石镇",
  "type": "settlement_region",
  "world_id": "isekai_world_001",
  "tags": ["town", "curfew", "outsider_pressure"],
  "risk_clocks": {
    "curfew": {
      "value": 2,
      "max": 6
    }
  }
}
```

### Site

```json
{
  "id": "old_furnace_inn",
  "name": "旧炉旅店",
  "type": "inn",
  "region_id": "graystone_town_region",
  "entry_node_ids": ["old_furnace_inn_front_hall"],
  "tags": ["facility", "merchant", "shelter"],
  "state": {
    "open": true,
    "curfew_sensitive": true
  }
}
```

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

`LocationEdge` 是地点之间通行关系的权威数据。

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

隐藏线索示例：

```json
{
  "id": "loose_floorboard_01",
  "name": "松动的地板",
  "type": "clue",
  "placement": {
    "kind": "near_object",
    "object_id": "wine_barrel_01",
    "relation": "beside",
    "visibility": "hidden",
    "reveal_condition": "observe_behind_counter"
  },
  "affordances": ["observe", "search"]
}
```

### Actor Location

角色位置使用与玩家相同的空间结构：

```json
{
  "id": "innkeeper_01",
  "name": "店主",
  "type": "npc",
  "location": {
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "behind_counter"
  },
  "attitude": "cautious",
  "affordances": ["talk", "negotiate", "purchase"]
}
```

## 空间不变量

实现时必须加入 validator，保证以下规则成立：

1. `World -> Region -> Site -> LocationNode -> Zone` 是唯一权威空间层级。
2. `Zone` 不能包含子 `Zone`。
3. `Object` 不能通过 `parent_id` 进入空间层级，只能通过 `placement` 定位。
4. `zone` placement 必须引用存在的 `node_id` 和 `zone_id`。
5. `on_object`、`inside_object`、`under_object`、`attached_to_object`、`near_object` 必须引用存在的 `object_id`。
6. 对象位置链不能形成循环。
7. 可见/可互动对象的位置链必须能解析到当前 `LocationNode + Zone`，或解析到当前空间内角色携带。
8. `LocationEdge.source_node_id` 和 `target_node_id` 必须引用存在的 `LocationNode`。
9. `LocationEdge.portal_object_id` 必须引用一个 `type=portal` 或具备 `enter/leave` 相关 affordance 的对象。
10. 玩家移动只能通过 `LocationEdge` 成功结算，不能通过 `parent_id`、`display_path` 或 DM 文本直接改地点。
11. DM 最终旁白中的当前可见主要对象，必须在同轮返回前进入 `current_scene.interactables` 或对应空间记忆。
12. 交易、拾取、消耗、破坏后，相关对象的 `placement` 必须同步变化。

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
| observe | 推进 1-3 分钟 | 可揭示 hinted 对象 | 玩家主动观察 |
| search | 推进 15-30 分钟 | 可揭示 hidden 对象、风险和发现 | 玩家主动搜索 |

### 查询流程

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

### 返回结构

```json
{
  "location": {
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

## 动作结算规则

### 进入地点

玩家说“进入后厨”：

```text
IntentPlan: enter_location
target_node_id: old_furnace_inn_kitchen
```

结算步骤：

```text
读取 current_node_id
-> 查找 source -> target 的 LocationEdge
-> 检查 portal object 状态
-> 检查 passability.conditions
-> 计算 traversal 时间、风险和资源变化
-> 成功后更新 player current_node_id / current_zone_id
-> 刷新 SpaceProjection
-> 写入 LocationChangedEvent
```

失败时：

```text
不改变 current_node_id
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

玩家说“我仔细观察前厅”：

```text
scope=observe
推进 1-3 分钟
可把 hinted 对象改为 visible
写入 ObjectRevealedEvent
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

- 新地点 proposal
- 新对象 proposal
- 对象描述、别名、标签
- 空间关系建议
- 可见性建议
- DM 叙事草稿

LLM 不能直接输出最终生效的：

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

最终 DM 旁白只能引用已提交或同轮已通过 validator 的地点和对象。

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

### P0.1：空间 schema 与 validator

交付内容：

- `WorldSpatialState` 数据结构。
- `Region`、`Site`、`LocationNode`、`Zone`、`LocationEdge`、`ObjectPlacement` schema。
- `SpatialGraphValidator`。
- 位置链解析器 `resolve_object_placement(object_id)`。

验收：

- 非法 node/zone 引用会被拒绝。
- 对象位置链循环会被拒绝。
- `LocationEdge` 引用不存在节点会被拒绝。
- `on_object` 最终不能追溯到空间根时会被拒绝。

### P0.2：SpaceProjectionService

交付内容：

- `query_current_space(actor_id, scope)`。
- `visible`、`interactive`、`observe` 三个 scope。
- 当前地点可见对象、可互动对象、出口和 blocked reason 输出。

验收：

- 玩家问“这里有什么”不推进时间、不改变状态。
- 玩家主动观察可推进 1-3 分钟并揭示 hinted 对象。
- UI 可互动列表和 DM 旁白使用同一份 projection。

### P0.3：移动和靠近结算

交付内容：

- `enter_location` 必须通过 `LocationEdge`。
- `approach` 只改变 `current_zone_id`。
- `LocationChangedEvent` 和 `ZoneChangedEvent`。

验收：

- 没有 edge 时不能进入目标地点。
- edge 被权限阻挡时不改变当前位置。
- 进入新节点后可互动对象立即刷新。

### P0.4：对象位置变更

交付内容：

- 拾取、购买、消耗、丢弃、NPC 携带的 placement 更新。
- `ObjectMovedEvent`、`ObjectRemovedEvent`。

验收：

- 玩家购买钥匙后，钥匙从店主/柜台移动到玩家物品或权益状态。
- 玩家吃掉炖菜后，炖菜不能继续显示在柜台上。
- DM 文本、UI、世界状态三者一致。

## 验收流程

使用固定流程测试：

```text
进入灰石镇
进入旧炉旅店前厅
询问这里有什么
靠近柜台
和店主讨价还价
购买炖菜
吃炖菜
请求去后厨
获得允许后进入后厨
回到前厅
上二楼进入三号房
```

每一步必须满足：

- `current_node_id` 等于结算后的权威节点。
- `current_zone_id` 等于结算后的权威区域。
- `display_path` 与当前位置一致。
- 当前 SpaceProjection 只包含当前地点和相邻可见内容。
- 可互动对象来自对象位置链解析。
- DM 旁白只引用已落库对象和地点。
- 交易、消耗、拾取后对象 placement 已同步变化。
- 失败移动保持原地并给出场景内替代方案。

## 回归测试要求

新增测试覆盖：

- `test_spatial_graph_rejects_missing_node_edge`
- `test_object_placement_chain_resolves_zone_root`
- `test_object_placement_cycle_is_rejected`
- `test_current_space_query_does_not_advance_time`
- `test_observe_reveals_hinted_object_with_small_time_cost`
- `test_enter_location_requires_location_edge`
- `test_blocked_edge_does_not_change_current_node`
- `test_approach_changes_zone_not_node`
- `test_purchase_moves_object_or_grants_entitlement`
- `test_consumed_object_removed_from_projection`
- `test_narration_cannot_reference_uncommitted_visible_object`

## 架构决策

1. 第一阶段采用语义空间图，不采用 DF tile 网格。
2. 权威空间层级固定为 `World -> Region -> Site -> LocationNode -> Zone`。
3. 对象不进入空间层级，通过 `ObjectPlacement` 表达位置。
4. 地点移动必须通过 `LocationEdge`，不能通过 `parent_id` 推导。
5. Portal 必须是对象，地点边引用 portal。
6. “这里有什么”是确定性投影查询，不是 LLM 生成。
7. LLM 只做 proposal 和叙事草稿，不能提交最终状态。
8. DM 旁白、UI 可互动列表、动作目标绑定必须共享 `SpaceProjection`。
