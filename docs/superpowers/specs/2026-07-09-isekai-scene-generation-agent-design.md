# 异世界模式场景生成子 Agent 设计

## 背景

异世界模式已经完成了动作解析、确定性结算、场景对象结构化、内容包拆分等基础工作，但当前架构仍存在一个根本问题：

> 玩家行动前，当前场景不一定已经拥有可信的结构化场景状态。

这会导致系统只能退回“周围环境”这类占位对象，或者让 DM agent 在叙事中临时补对象、补地点。结果是：

- 玩家说“检查铁栅栏”，系统找不到铁栅栏。
- DM 文本说有木箱，但 `current_scene.interactables` 没有木箱。
- 玩家点击建议动作后可能进入一个没有合法连接的地点。
- 隐藏区域可能被临时创造，而不是提前作为场景拓扑的一部分存在。
- DM agent 同时负责叙事和世界结构生成，职责混杂。

本设计的目标是把“场景生成”从 DM agent 中拆出，成为独立的 Scene Generation Agent，并将场景结构化变成玩家每轮行动前不可绕过的硬前置步骤。

## 核心结论

玩家与场景互动前，系统必须先保证当前场景是结构化且可交互的。

```text
玩家输入
  -> 读取当前场景
  -> 确保当前场景结构有效
  -> 解析玩家意图
  -> 绑定玩家目标到当前场景对象
  -> 校验行动是否合法
  -> 确定性结算
  -> DM agent 基于结算结果叙事
```

DM agent 不负责生成新场景。DM agent 只负责基于已经生成、校验、落库的场景状态进行叙事。

## 设计原则

### 1. 数据库状态是唯一事实源

当前玩家可互动的对象、出口、NPC、风险、隐藏入口、发现表，都必须来自本局 SQLite 状态。

可使用的状态位置：

- `adventures.current_scene_json`
- `adventures.world_state_json`
- 后续如拆表，可拆到 `isekai_scene_nodes`、`isekai_scene_edges`、`isekai_scene_objects`

DM 文本不能成为唯一事实源。DM 文本里出现的可互动对象必须同步进入结构化状态。

### 2. 移动生成新场景，互动更新当前场景

只有地点事实变化时，才生成新场景。

会生成新场景的动作：

- `enter_location`
- `travel`
- `leave_location`
- 由世界事件导致的强制转移

不会生成新场景的动作：

- `observe`
- `search`
- `open`
- `force_open`
- `short_dialogue`
- `negotiate`
- `eat_food`
- `drink_water`
- `manage_inventory`
- `status_check`
- `rest_short`

这些动作只能更新当前场景对象、对象状态、发现物、NPC 态度、风险、资源、时间和线索。

### 3. 隐藏区域必须提前存在拓扑

隐藏区域可以晚点被玩家发现，但不能晚点才被世界创造出来。

父场景生成时必须同时生成：

- 可见出口
- 隐藏出口
- 被锁入口
- 阻塞入口
- 子场景 stub
- 场景之间的 edge

例如玩家在旧矿道入口时，系统可以隐藏“被碎石遮住的侧缝”，但这个隐藏入口和它连接的 `hidden_drainage_tunnel` stub 必须已经存在于场景拓扑中。

### 4. 没有合法 edge，不能进入新场景

玩家不能凭一句话直接进入当前场景没有连接关系的地点。

这里的 edge 不是限制玩家表达的硬墙，而是限制系统不能瞬移、不能乱切场景。玩家说“离开这里”“回城镇”“回灰橡镇”“找个有人烟的地方”，都应先进入 Navigation Resolution Layer，把自然语言移动意图转换为合法路径、返程路径、找路行动或条件不足反馈。

```text
当前节点 old_mine_entrance
玩家输入 “进入街边旅店”
系统检查 edge
没有 old_mine_entrance -> street_inn
结果：拒绝或澄清，不能切换地点
```

但如果玩家输入：

```text
离开这里
回到城镇
回灰橡镇
找一个有人烟的地方
```

系统不能简单套用“没有当前 edge 就拒绝”。这些输入属于导航意图，必须查询本局状态后再决定：

- 有 `parent/exit/back` edge 时，执行 `leave_current_scene`。
- 目标在 `known_locations` 或 `location_history` 中时，执行 `return_to_known_location` 或 `travel_to_known_location`。
- 目标类型已知但没有具体地点时，执行 `seek_destination`，例如寻找道路、炊烟、水流、人类活动痕迹。
- 目标确定且路径存在，但 edge 被阻断时，返回 `blocked_navigation` 并给出替代行动。
- 只有目标无法绑定、路径无法构造、或存在明确物理阻断时，才要求澄清或返回条件不足。

这些判断必须来自本局结构化状态查询，而不是关键词罗列。

### 5. DM agent 不能绕过 Scene Generation Agent

DM agent 可以描述：

- 行动结果
- 环境氛围
- NPC 反应
- 玩家可感知的风险

DM agent 不能直接创建：

- 新 node
- 新 edge
- 新隐藏区域
- 新可互动对象
- 新发现表
- 新任务线

这些结构只能由 Scene Generation Agent 提出，并由后端校验后落库。

## 术语

### Scene Node

一个可定位、可进入、可持久化的场景节点。

示例：

- 旧矿道入口
- 外层矿道
- 隐藏排水道
- 废弃神庙内厅

### Scene Edge

两个场景节点之间的连接关系。

示例：

```json
{
  "id": "edge_old_mine_to_outer_tunnel",
  "from_node_id": "old_mine_entrance",
  "to_node_id": "mine_outer_tunnel",
  "via_object_id": "rusted_gate",
  "access": "locked",
  "known_to_player": true
}
```

### Scene Stub

尚未完整展开的子场景节点。

它必须有：

- `node_id`
- `parent_node_id`
- `connected_from`
- `relation`
- `known_to_player`
- `generation_status`

但它不一定已经有完整的对象列表。玩家真正进入时，再由 Scene Generation Agent 展开完整场景。

### Scene Object

当前节点内的可互动对象。

示例：

- 生锈铁栅栏
- 旧火把架
- 矿车轨道
- 断裂脚印
- 被碎石遮住的侧缝

### Discovery Table

搜索、观察、打开、撬开等动作触发的发现规则。

Discovery Table 不能凭空创建新地点，只能揭示已经存在的 hidden object、hidden edge 或 hidden clue。

### Navigation Resolution Layer

移动相关输入进入场景切换前，必须先经过导航解析层。

Navigation Resolution Layer 只做一件事：把玩家自然语言中的移动目标，绑定到本局游戏里已经存在或可以合理寻找的世界状态。

它依赖以下状态，而不是关键词罗列：

- `current_scene.node_id`
- `scene_graph.nodes`
- `scene_graph.edges`
- `visible_edges`
- `known_locations`
- `known_routes`
- `location_history`
- `blocked_edges`
- `player_map_memory`
- 当前场景中可感知的道路、出口、路牌、炊烟、水流、脚印、车辙等 navigation clue

推荐输出：

```json
{
  "navigation_intent": "return_to_known_location",
  "target_query": {
    "raw_text": "城镇",
    "target_type": "settlement",
    "target_name": null,
    "is_specific": false
  },
  "target_binding": {
    "status": "resolved",
    "node_id": "grey_oak_town_gate",
    "reason": "nearest_recent_settlement"
  },
  "route_plan": {
    "status": "known_route",
    "edge_ids": ["edge_mine_to_forest_path", "edge_forest_path_to_town_gate"]
  },
  "precondition": {
    "status": "pass"
  }
}
```

`navigation_intent` 建议使用以下闭集：

```text
leave_current_scene
return_to_known_location
travel_to_known_location
seek_destination
enter_adjacent_location
blocked_navigation
clarification
```

目标绑定结果使用以下闭集：

```text
resolved
unknown_target
ambiguous_target
known_target_unknown_route
blocked_route
```

定义：

- `unknown_target`：本局状态中找不到该目标，也没有任何线索支持它存在。
- `ambiguous_target`：存在多个候选地点，系统无法根据最近访问、当前目标、玩家称呼或上下文选出一个。
- `known_target_unknown_route`：目标存在或听说过，但当前没有路线、历史路径或导航线索能构造去法。
- `blocked_route`：目标和路径都明确，但 edge 或入口对象有锁死、塌方、关门、守卫阻拦、洪水、黑暗等阻断状态。

判断流程：

```text
1. Intent Agent 解析玩家移动目标，但不判定是否成功
2. Navigation Resolution Layer 查询本局 known_locations/location_history/scene_graph
3. 如果候选目标为 0：
     转成 seek_destination 或 unknown_target
4. 如果候选目标超过 1：
     尝试用最近访问、当前目标、别名、上下文消歧
     仍不能确定时返回 ambiguous_target
5. 如果目标唯一：
     查询直接 edge、历史路径、已知路线
6. 如果路线存在：
     检查 edge/object 阻断状态
7. 如果阻断：
     返回 blocked_route 和可替代行动
8. 如果通过：
     交给 Action Resolution Engine 结算移动、时间、风险
```

示例：

```text
玩家：“我要回城镇”

known_locations 中存在灰橡镇，location_history 里有旧矿道入口 -> 林间小路 -> 灰橡镇。
结果：return_to_known_location，不要求澄清。
```

```text
玩家：“我要回城镇”

known_locations 中没有 settlement，当前场景也没有道路、炊烟、路牌、车辙等线索。
结果：seek_destination，提示玩家可以寻找道路、爬高观察、沿水流走。
```

```text
玩家：“我要回灰橡镇”

known_locations 中存在灰橡镇，但玩家昏迷后出现在陌生洞穴，location_history 无法连接当前 node，scene_graph 也没有可用 route。
结果：known_target_unknown_route，生成找路行动，不直接移动。
```

```text
玩家：“离开矿道”

scene_graph 中存在当前 node -> 矿道入口的 back edge，但 edge.blocked_by = collapsed_tunnel。
结果：blocked_route，提示清理碎石、寻找侧缝、等待援助或另找出口。
```

## 什么时候生成场景

### 1. 冒险开局生成当前场景

开局时必须生成完整的起始节点。

起始节点至少包含：

- 当前地点
- 环境描述
- 当前目标
- 可见对象
- 可见出口
- 隐藏对象
- 隐藏出口
- scene stubs
- discovery tables
- 初始风险
- 3 到 5 个自然建议行动

如果开局 LLM 只返回文本，没有结构化对象，则本局不能进入正常行动结算。必须先调用 Scene Generation Agent 补齐当前节点结构并写入 SQLite。

### 2. 玩家进入已有 edge 指向的未展开 stub

例如：

```text
当前场景：旧矿道入口
已存在 edge：旧矿道入口 -> 外层矿道
玩家输入：进入矿道
```

如果 `mine_outer_tunnel` 只是 stub，则调用 Scene Generation Agent 生成完整节点。

### 3. 玩家进入已生成过的节点

如果目标 node 已经完整生成过，不再调用 Scene Generation Agent，直接读取 SQLite。

### 4. 世界事件强制改变地点

例如塌方、追逐、巡逻驱赶导致玩家被迫进入另一个相邻节点。

前提仍然是必须存在合法 edge。没有 edge 时，事件只能改变当前场景状态，不能强行传送玩家。

### 5. 当前场景结构缺失或明显无效

这不是生成新地点，而是修复当前节点。

触发条件：

- `interactables` 为空。
- 只有“周围环境”这类占位对象。
- 当前地点与对象明显不一致。
- 位置变了但对象还是上一地点的对象。
- DM 旁白里出现关键对象，但状态没有落库。

修复时只重建当前 node，不改变 location。

## 什么时候不生成场景

以下情况不生成新场景：

```text
观察木箱
搜索祭坛
打开货袋
撬开铁栅栏
和店主说话
吃干粮
喝水
检查背包
听动静
整理装备
休息十分钟
检查脚印是否新鲜
```

这些动作只能触发：

- 对象状态变化
- 新对象被揭示
- 线索进入线索状态
- 物品进入背包
- 时间推进
- 生存资源变化
- 风险变化
- NPC 态度变化
- edge 从 locked/hidden 变为 open/discovered

## 生成的场景必须包含什么

Scene Generation Agent 输出必须包含公开信息和隐藏信息。

### 顶层字段

```json
{
  "schema_version": "isekai_scene_node_v1",
  "node": {},
  "visible_objects": [],
  "hidden_objects": [],
  "visible_edges": [],
  "hidden_edges": [],
  "node_stubs": [],
  "discovery_tables": [],
  "npcs": [],
  "hazards": [],
  "resources": [],
  "pressure_modifiers": [],
  "suggested_actions": []
}
```

### node

```json
{
  "node_id": "mine_outer_tunnel",
  "parent_node_id": "old_mine_entrance",
  "connected_from": "rusted_gate",
  "location_path": {
    "region": "铁炉镇外",
    "site": "旧矿道",
    "sublocation": "外层矿道",
    "display_name": "铁炉镇外 / 旧矿道 / 外层矿道"
  },
  "environment": "矿道里有潮湿铁锈味，轨道向黑暗深处延伸。",
  "current_objective": "确认外层矿道是否稳定，并寻找可用光源。"
}
```

### visible_objects

玩家当前能直接感知和互动的对象。

```json
{
  "id": "old_lantern",
  "type": "item",
  "name": "旧矿灯",
  "aliases": ["矿灯", "旧灯"],
  "description": "一盏积灰的矿灯，灯芯已经发硬。",
  "visibility": "visible",
  "presence": "current",
  "affordances": ["observe", "take"],
  "risk": "拿起时可能发出轻响。"
}
```

### hidden_objects

玩家不能直接看到的对象。它们不能出现在普通 DM 叙事和前端可互动列表中。

```json
{
  "id": "sealed_cache",
  "type": "container",
  "name": "封住的补给暗格",
  "visibility": "hidden",
  "presence": "current",
  "affordances": ["observe", "open"],
  "reveal_condition": {
    "action_type": "search",
    "target_id": "collapsed_track",
    "difficulty": "medium"
  }
}
```

### edges

所有子场景和相邻场景都必须通过 edge 连接。

```json
{
  "id": "edge_outer_to_deep_tunnel",
  "from_node_id": "mine_outer_tunnel",
  "to_node_id": "deep_mine_tunnel",
  "via_object_id": "deep_track",
  "access": "open",
  "known_to_player": true,
  "travel_cost_minutes": 20
}
```

隐藏 edge 示例：

```json
{
  "id": "edge_outer_to_drainage",
  "from_node_id": "mine_outer_tunnel",
  "to_node_id": "hidden_drainage_tunnel",
  "via_object_id": "covered_side_crack",
  "access": "hidden",
  "known_to_player": false,
  "reveal_condition": {
    "action_type": "search",
    "target_id": "rubble_slope"
  }
}
```

### node_stubs

Scene Generation Agent 在生成父场景时，必须为所有 edge 指向的新节点生成 stub。

```json
{
  "node_id": "hidden_drainage_tunnel",
  "parent_node_id": "mine_outer_tunnel",
  "connected_from": "covered_side_crack",
  "relation": "hidden_side_area",
  "known_to_player": false,
  "generation_status": "stub"
}
```

## Scene Generation Agent 输入

Scene Generation Agent 不接收完整消息历史，只接收生成场景所需的结构化上下文。

```json
{
  "adventure_id": 47,
  "mode": "isekai_survival",
  "locale": "zh-CN",
  "generation_reason": "enter_stub",
  "source_node": {},
  "target_stub": {},
  "entry_edge": {},
  "player_action": "进入矿道",
  "character_public_state": {},
  "visible_world_state": {},
  "style_constraints": {
    "genre": "异世界生存探险",
    "avoid": ["普通小镇日常", "现代街边商业感", "无来源地点跳转"]
  }
}
```

禁止传入：

- 与当前场景无关的旧内容包细节。
- 其他存档状态。
- 隐藏奖励结算权限。
- 可让模型直接扣钱、发物品、改任务阶段的权限。

## Scene Generation Agent 输出

输出必须是 JSON，不允许只输出自然语言。

```json
{
  "schema_version": "isekai_scene_node_v1",
  "node": {},
  "visible_objects": [],
  "hidden_objects": [],
  "visible_edges": [],
  "hidden_edges": [],
  "node_stubs": [],
  "discovery_tables": [],
  "suggested_actions": [],
  "public_arrival_narration_seed": "你推开生锈铁栅栏，潮湿铁锈味扑面而来。"
}
```

`public_arrival_narration_seed` 只是给 DM agent 的素材，不是最终 DM 回复。

## 后端校验规则

Scene Validator 必须校验：

### 1. ID 合法性

- `node_id` 必须唯一。
- `object.id` 必须唯一。
- `edge.id` 必须唯一。
- `edge.from_node_id` 必须等于当前 node 或父 node。
- `edge.to_node_id` 必须存在于 node 或 node_stubs 中。

### 2. 拓扑合法性

- 新 node 必须有 `parent_node_id` 或合法 `entry_edge`。
- 子场景必须有入口对象。
- 没有 edge 的 node 不能进入。
- 不允许从矿道入口生成街边旅店这类无连接地点。

### 3. 可见性合法性

- `hidden_objects` 不得进入前端可互动列表。
- `hidden_edges` 不得作为建议行动显示。
- DM agent 普通叙事 prompt 不得包含隐藏对象细节。

### 4. affordance 合法性

对象能力只能来自稳定动作集合：

```text
observe
search
enter
leave
approach
talk
negotiate
purchase
gather
take
open
force_open
refill_water
eat_meal
secure_shelter
hide
avoid
track
repair
read
```

### 5. 类型合法性

对象类型只能来自闭集：

```text
npc
merchant
item
container
clue
place
entrance
obstacle
hazard
resource
water_source
shelter
object
entitlement
```

### 6. 规模限制

单个场景建议限制：

- visible objects：3 到 8 个
- hidden objects：1 到 6 个
- visible edges：1 到 4 个
- hidden edges：0 到 3 个
- suggested actions：3 到 5 个

超过限制的内容应被截断或要求重写。

## DM Agent 工作边界

DM agent 接收到的是已经校验并落库后的公开场景状态。

DM agent 可以使用：

- 当前 node 公开描述。
- visible objects。
- visible edges。
- 当前行动结算结果。
- 资源变化。
- 风险变化。
- NPC 当前态度。
- 已公开线索。

DM agent 不可以使用：

- hidden_objects。
- hidden_edges。
- 未发现 discovery result。
- 未触发奖励。
- 未公开任务阶段信息。

DM agent 输出如果包含新对象，只能作为 `scene_objects proposal` 进入校验，不得直接成为事实。

## 每轮行动前置流程

新增硬前置：

```text
ensure_scene_structured(adventure_id)
```

流程：

```text
1. 读取 current_scene 和 world_state
2. 判断当前 scene 是否结构有效
3. 如果无效：
   3.1 调用 Scene Generation Agent 修复当前 node
   3.2 校验输出
   3.3 写入 SQLite
4. 返回结构化后的 current_scene
5. 进入玩家意图解析
```

结构无效条件：

- `interactables` 为空。
- 只有 `周围环境`。
- 对象与当前地点明显不一致。
- current node 没有任何 visible edge 或 hidden edge。
- 当前位置没有 node_id，且不是兼容旧存档的临时状态。

## 玩家进入新场景流程

```text
玩家输入：“进入矿道”
  -> Intent Agent 解析为 enter_location
  -> Navigation Resolution Layer 绑定移动目标
  -> Action Grounder 绑定目标 rusted_gate
  -> Precondition Service 检查 rusted_gate 是否允许进入
  -> Location Graph 检查 edge 是否存在
  -> 如果 target node 已完整生成：
       读取 node
     否则：
       调用 Scene Generation Agent 生成 target node
       校验并写入 SQLite
  -> Action Resolution Engine 更新时间、资源、风险、当前位置
  -> DM agent 基于新场景公开信息叙事
```

## 玩家离开、返回、找路流程

```text
玩家输入：“离开这里”
  -> Intent Agent 解析为 leave_current_scene
  -> Navigation Resolution Layer 查询 parent/exit/back edge
  -> 如果 edge 可通行：
       切换到父节点或出口节点
     如果 edge 阻断：
       返回 blocked_navigation 和替代行动
     如果当前节点缺少出口但 parent_node_id 存在：
       调用 scene_graph_repair 补齐回退 edge
  -> Action Resolution Engine 结算时间、风险、位置
  -> DM agent 叙事
```

```text
玩家输入：“回到城镇”
  -> Intent Agent 解析为 return_or_travel target_type=settlement
  -> Navigation Resolution Layer 查询 known_locations 和 location_history
  -> 如果只有一个最近已知 settlement：
       绑定该 node
     如果多个 settlement 且无法消歧：
       返回 clarification
     如果没有 settlement：
       转成 seek_destination
  -> 查询直接 edge、历史路径、known_routes
  -> 如果路线存在且未阻断：
       生成 route_plan 并结算 travel
     如果目标存在但路线不存在：
       返回 known_target_unknown_route，建议寻找道路、路标、炊烟、水流或高处观察
     如果路线被阻断：
       返回 blocked_navigation 和替代行动
```

这一流程保证玩家可以自然表达“走、离开、回去、找城镇”，但系统不会因为一句话把角色传送到没有来源的地点。

## 玩家发现隐藏区域流程

```text
玩家输入：“搜索碎石坡”
  -> 绑定目标 rubble_slope
  -> Discovery Table 命中 hidden edge
  -> covered_side_crack.visibility: hidden -> discovered
  -> edge_outer_to_drainage.known_to_player: false -> true
  -> 前端显示“被碎石遮住的侧缝”
  -> 不切换场景
```

玩家随后输入：

```text
进入侧缝
```

系统才沿 edge 进入 `hidden_drainage_tunnel`，如果该 node 仍是 stub，再调用 Scene Generation Agent 生成完整场景。

## 状态存储建议

### P0 可继续使用 JSON 字段

短期可以继续放在：

- `adventures.current_scene_json`
- `adventures.world_state_json.location_graph`
- `adventures.world_state_json.scene_nodes`
- `adventures.world_state_json.scene_edges`
- `adventures.world_state_json.discovery_tables`
- `adventures.world_state_json.known_locations`
- `adventures.world_state_json.known_routes`
- `adventures.world_state_json.location_history`
- `adventures.world_state_json.blocked_edges`
- `adventures.world_state_json.player_map_memory`

### P1 建议拆表

后续可拆成：

```text
isekai_scene_nodes
isekai_scene_edges
isekai_scene_objects
isekai_scene_discoveries
```

所有表必须有 `adventure_id`，禁止跨局共享运行态。

## 失败处理

### Scene Generation Agent 失败

如果生成失败：

- 不推进时间。
- 不改变地点。
- 不修改场景。
- 返回可读错误：“当前场景结构生成失败，请重试或换一个更明确的行动。”

### 输出校验失败

如果 JSON 缺字段或非法：

- 请求模型重写一次。
- 仍失败则中止本轮，不推进状态。

### 没有合法 edge

如果玩家想进入不存在的地点：

```text
你现在所在位置没有通向“街边旅店”的路径。当前可进入的是：外层矿道、返回旧路。
```

不允许强行切换地点。

### 导航目标未知

如果玩家目标无法绑定到本局状态，也没有线索支持该目标存在：

```text
你现在还不知道城镇在哪。你可以先寻找道路、爬到高处观察炊烟，或沿溪流寻找人类活动痕迹。
```

不生成目标地点，不切换位置。可以把行动转成 `seek_destination`，让玩家通过找路、观察、询问、追踪等方式发现路线。

### 导航目标歧义

如果同类候选超过一个，且无法通过最近访问、当前目标、玩家上下文消歧：

```text
你知道两个可返回的聚落：灰橡镇和铁炉镇。你想回哪一个？
```

不推进时间，不改变地点。

### 目标已知但路径不明

如果目标已知，但没有路线、历史路径或当前导航线索：

```text
你知道灰橡镇存在，但现在身处陌生林地，来路已经断了。你需要先辨认方向，或者寻找道路、车辙、溪流下游。
```

不直接进入目标地点。下一步应生成找路、观察、追踪或询问类行动。

### 路径存在但物理阻断

如果目标和路径都明确，但 edge 或入口对象被阻断：

```text
回矿道入口的通道被塌落碎石堵住。你可以清理碎石、寻找侧缝、检查是否有通风孔，或退回当前安全位置。
```

不切换地点，除非玩家执行了能解除阻断或绕路的行动。

## 测试要求

### 场景生成触发

- 新开局如果没有 `interactables`，必须先调用 Scene Generation Agent。
- `observe/search/status_check` 不得生成新 node。
- `enter_location/travel/leave_location` 只有存在 edge 时才生成或切换 node。
- “离开这里”优先使用 parent/exit/back edge，不得被当成无目标闲聊。
- “回到城镇”必须先查 known_locations/location_history，不得直接瞬移，也不得在已有唯一已知城镇时要求澄清。
- 已知目标但无路线时，必须返回找路行动，而不是生成目标地点。
- 路径阻断时必须返回替代行动，不得切换地点。

### 拓扑约束

- 子场景必须有 parent node。
- 子场景必须有 edge。
- 隐藏场景必须先以 stub 存在。
- 没有 edge 时禁止进入。

### 隐藏信息

- hidden object 不出现在前端可互动列表。
- hidden edge 不出现在建议动作。
- discovery 触发后 hidden edge 变为 discovered。

### DM 边界

- DM agent 不能直接新增 node。
- DM agent 不能直接新增 edge。
- DM agent 不能直接公开 hidden object。
- DM agent 的新增对象 proposal 必须经过 Scene Validator。

### 回归用例

必须覆盖：

- 旧矿道入口生成铁栅栏、矿车轨道、旧火把架、矿道入口。
- 玩家搜索碎石坡，发现隐藏侧缝，但不进入新场景。
- 玩家进入侧缝，生成隐藏排水道完整场景。
- 玩家在旧矿道入口输入“进入街边旅店”，系统拒绝，因为没有 edge。
- 当前场景只有“周围环境”时，行动解析前先结构化。
- DM 文本提到木箱但状态没有木箱时，本轮结束前必须落库或移除文本引用。

## 验收标准

一局连续游玩 10 轮后应满足：

- 玩家始终知道自己在哪里。
- 前端可互动内容只来自当前场景。
- 新地点都有合法来源 edge。
- 隐藏区域不是临时编造，而是由父场景拓扑揭示。
- DM agent 不直接生成地点结构。
- 玩家搜索具体对象时，系统能绑定到具体对象。
- 没有“周围环境”占位对象作为主路径。
- SQLite 中能回放每个 node、edge、object 的来源和状态变化。

## 推荐实施顺序

1. 新增 Scene Node / Edge / Stub schema。
2. 新增 `SceneGenerationAgent` 接口和 prompt。
3. 新增 `SceneValidator`。
4. 新增 `ensure_scene_structured(adventure_id)` 硬前置。
5. 新增 `NavigationResolutionLayer`，用本局状态解析离开、返回、找路和已知地点移动。
6. 改造 `enter_location/travel/leave_location`，只能沿合法 edge 或合法 route_plan 切换。
7. 改造 discovery，隐藏区域只能从 hidden edge 揭示。
8. 禁止“周围环境”作为正常 fallback。
9. 前端显示当前 node 的 visible objects 和 visible exits。
10. 增加回归测试和 game/47 类污染存档测试。

## 结论

异世界模式的可玩性不应依赖 DM agent 临场补世界。DM agent 应该主持已经存在的世界，而不是随手创造世界结构。

正确边界是：

```text
Scene Generation Agent 生成世界结构。
Scene Validator 审核世界结构。
SQLite 保存世界结构。
Action Resolution Engine 改变世界结构。
DM agent 描述玩家可感知的结果。
```

这样才能保证玩家行动、场景对象、隐藏区域、地点移动和 DM 叙事都围绕同一个可回放的世界状态运行。
