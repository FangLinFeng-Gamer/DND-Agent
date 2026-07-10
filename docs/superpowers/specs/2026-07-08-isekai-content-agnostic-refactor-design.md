# 异世界模式内容无关化统一重构设计

## 背景

上一份文档 [2026-07-08-isekai-scene-object-structuring-design.md](./2026-07-08-isekai-scene-object-structuring-design.md) 解决的是“DM 旁白里的具体对象没有进入结构化状态”的问题。继续检查后发现，同类问题不只存在于可互动对象：

- `IsekaiInteractableProjector` 在代码里枚举具体对象。
- `IsekaiActionParser._loose_target_match` 在代码里枚举具体目标词。
- `IsekaiLocationService` 固定了“灰石镇 / 旧炉旅店”的地点图。
- `IsekaiActionResolutionEngine` 写死神庙、森林、哨塔、货袋等发现结果。
- `IsekaiEconomyService` 写死床位和炖菜两个商品。
- `IsekaiQuestService` 写死 `night_wolf_line`，这在 P1 单任务线范围内可接受，但长期也需要内容包化。

这些问题本质相同：

> 通用规则层混入了具体内容。

短期补丁能修复单个存档，但长期会让每个新地点、新商品、新线索、新 NPC 都变成后端代码分支，最终回到“罗列所有可能”的不可维护状态。

## 总目标

将异世界模式重构为“内容无关规则引擎 + 内容包/模型生成内容”的架构。

```text
内容层负责创造具体世界：
地点、对象、NPC、商品、线索、任务阶段、发现表、文本风格。

规则层负责稳定结算：
动作能力、目标绑定、前置条件、时间、生存、经济、奖励、风险、状态写入。
```

核心原则：

- 后端通用服务不再硬编码具体地点名、物品名、线索名、商品名、任务文本。
- 具体内容来自内容包、场景生成器或 LLM proposal。
- LLM 可以提出内容，但不能直接提交最终状态变化。
- 后端只维护抽象类型、动作能力、权限矩阵和校验规则。
- P1 的旧炉旅店和暗夜狼线可以保留，但要迁移成内容包实例，而不是散落在通用服务中。

## 非目标

本阶段不做以下事情：

- 不开放无限 action_type。
- 不让 LLM 直接扣钱、发物品、发钥匙、改任务阶段。
- 不把所有现有剧情内容删除。
- 不要求一步完成独立数据库表迁移。
- 不实现多任务线内容扩张。
- 不创建具体物品、地点、商品、怪物的大清单。

## 当前问题分层

### 1. 场景对象硬编码

当前问题：

- `IsekaiInteractableProjector` 根据中文词生成对象。
- 新场景一换词，就找不到对象。
- 旧逻辑会 fallback 到“周围环境”，导致玩家搜索具体目标时得到泛化反馈。

目标状态：

- 具体对象由 `scene_objects` 写入状态。
- projector 只负责从已落库对象筛选当前可见对象。
- 旧关键词 projector 降级为 legacy fallback。

### 2. 目标匹配硬编码

当前问题：

- `_loose_target_match` 维护“木箱、马车、麋鹿、哨塔、店主、床位”等词表。
- 这会让 action parser 继续承担内容识别职责。

目标状态：

- 目标匹配基于：
  - `SceneObject.name`
  - `SceneObject.aliases`
  - `SceneObject.type`
  - `SceneObject.affordances`
  - 当前地点 scope/presence
- parser 不再维护具体目标词表。

### 3. 地点图硬编码

当前问题：

- `IsekaiLocationService` 内置固定节点：灰石镇、旧炉旅店、后厨、三号房、马厩。
- 随机城镇或随机设施无法复用这套逻辑。

目标状态：

- 地点图来自 `LocationGraph` 内容数据。
- 旧炉旅店是一个 content pack，不是通用地点服务的一部分。
- `LocationService` 只负责节点邻接、进入/离开校验、location_path 更新。

### 4. 探索发现硬编码

当前问题：

- `IsekaiActionResolutionEngine` 根据“神庙 + 木箱”“麋鹿 + 血迹”“哨塔 + 旧火堆”写死发现结果。
- 新地点没有发现表时，又退回泛化结果。

目标状态：

- 发现由 `DiscoveryTable` 或 `SceneObject.hidden/reveal` 提供。
- resolver 只按动作、目标、风险和难度揭示结果。
- 具体发现文本从对象描述或内容包模板生成。

### 5. 经济商品硬编码

当前问题：

- 经济系统只知道 `inn_bed` 和 `stew_meal`。
- 商品名称、价格、权益、交易理由都在 service 中固定。

目标状态：

- 商品和服务来自 `FacilityCatalog` 或 `MerchantInventory`。
- 经济服务只负责铜币换算、余额校验、交易记录、权益写入。
- `purchase` 根据当前商人/设施报价结算，不根据文字猜固定商品。

### 6. 任务线硬编码

当前问题：

- P1 要求只能有 `night_wolf_line`，这是当前阶段约束。
- 但任务阶段推进、线索文本和奖励文本已经散入规则服务。

目标状态：

- P1 仍只允许一个 active quest。
- `night_wolf_line` 迁移为 `QuestContentPack`。
- `IsekaiQuestService` 只负责单任务线约束、阶段合法性、条件校验和状态推进。

## 推荐架构

```text
Content Pack / LLM Proposal
    |
    v
Content Materializers
    - SceneObjectMaterializer
    - LocationGraphMaterializer
    - MerchantInventoryMaterializer
    - DiscoveryMaterializer
    - QuestContentMaterializer
    |
    v
Validators
    - type/affordance validator
    - location graph validator
    - economy offer validator
    - discovery/reward permission validator
    - quest stage validator
    |
    v
Consistency Gates
    - narration object consistency gate
    - state change permission gate
    - P1 single quest gate
    |
    v
Runtime State
    - SceneState.interactables
    - world_state.content_packs
    - world_state.location_graph
    - world_state.facilities
    - world_state.discovery_tables
    - world_state.active_quest
    |
    v
Rule Engines
    - IntentInterpreter
    - ActionGrounder
    - PreconditionService
    - ActionResolutionEngine
    - EconomyService
    - QuestService
    - RewardService
    - NarrationComposer
```

## 内容包定义

新增统一概念：

```text
IsekaiContentPack
```

内容包不是全局大清单，而是一次冒险、一个地点、一个设施或一条任务线的局部内容定义。

示例结构：

```json
{
  "schema_version": "1.0",
  "content_pack_id": "old_furnace_inn_p1",
  "scope": "adventure",
  "source": "built_in_p1",
  "priority": 100,
  "lifecycle": {
    "load_at": "adventure_start",
    "expires": "manual",
    "owner_node_ids": ["old_furnace_inn.front_hall", "old_furnace_inn.kitchen"]
  },
  "conflict_policy": "pack_id_then_priority",
  "locations": [],
  "scene_objects": [],
  "facilities": [],
  "merchant_inventories": [],
  "discovery_tables": [],
  "quest_lines": []
}
```

内容包来源：

- 内置 P1 纵切内容。
- 开局 LLM 生成。
- 当前场景 DM proposal。
- 剧本模板。
- 后续人工编辑器。

内容包边界：

- 可以包含具体对象名。
- 可以包含具体商品名。
- 可以包含具体任务线名称。
- 不能绕过 validator。
- 不能直接修改角色最终状态。

### ContentPack 存储和生命周期决策

第一阶段不新建数据库表，ContentPack 运行态存入：

```text
world_state.content_packs
```

结构：

```json
{
  "content_packs": {
    "old_furnace_inn_p1": {
      "schema_version": "1.0",
      "source": "built_in_p1",
      "status": "active",
      "loaded_turn": 0,
      "expires": "manual",
      "pack": {}
    }
  }
}
```

生命周期规则：

- `source=built_in_p1`：随冒险创建加载，除非迁移或重置，不自动过期。
- `source=llm_proposal`：默认只对当前 node 或当前 turn 生效；通过 validator 后才能升级为 adventure scope。
- `source=scene_update`：只对当前 node 生效，移动地点后进入对象记忆或失效。
- `source=story_template`：随故事模板加载，优先级低于当前冒险 runtime 修正。

加载顺序：

```text
built_in/story_template
-> adventure runtime content_packs
-> current scene_update proposals
-> LLM proposals
```

冲突处理：

- 同一个 `content_pack_id` 后加载版本覆盖旧版本，但必须保留 `previous_version` metadata。
- 同一个 `node_id/object_id/offer_id/quest_id` 冲突时，高 priority 覆盖低 priority。
- priority 相同且字段冲突时，保留已验证 runtime 状态，拒绝新 proposal，并记录 `blocked_reason=content_conflict`。
- 任何覆盖都不能删除玩家已获得的物品、权益、线索和交易记录。

第二阶段如果跨地点内容量和历史版本明显增长，再迁移到独立表：

```text
isekai_content_packs
```

本设计不要求第一阶段建表。

## Validator 权限矩阵

所有内容进入 runtime state 前必须经过对应 validator。validator 不只是 schema 检查，还必须限制内容能影响哪些状态。

| Validator | 允许写入 | 禁止写入 | 必须校验 |
| --- | --- | --- | --- |
| SceneObjectValidator | `SceneState.interactables`、`world_state.scene_object_memory_by_node` | 钱、奖励、任务阶段、NPC 信任最终值 | type 闭集、affordance 闭集、presence/scope、当前地点一致性 |
| LocationGraphValidator | `world_state.location_graph`、`SceneState.location_path` 候选 | 背包、钱、奖励、任务阶段 | node_id 唯一、neighbors 存在、入口对象和 node 对应 |
| OfferValidator | `world_state.facilities`、`world_state.merchant_inventories` | 直接扣钱、直接发物品、直接发权益 | price_copper 为非负整数、grant 类型白名单、merchant 当前可交易 |
| DiscoveryValidator | `world_state.discovery_tables`、hidden/reveal proposal | 直接发钱、直接发钥匙、直接完成任务 | trigger action_type 白名单、target_object_id 存在、reveal_objects 存在或可 materialize |
| QuestContentValidator | `world_state.quest_content_packs`、inactive quest proposal | 直接推进 active stage、直接发奖励 | P1 active quest 白名单、stage transition 合法、reward 交给 RewardService |
| NarrationObjectConsistencyGate | 最终 narration 修正结果和 metadata | 任何最终游戏状态 | narration 中当前可见主要对象必须存在于已验证状态 |

### Offer grants 权限

`Offer.grants` 只能声明 proposal，不能直接落库：

```text
items -> RewardService 校验后入包
entitlements -> EntitlementService 校验后入权益
meal_effect -> ResourceService 校验后改生存状态
relationship_delta -> RelationshipService 校验后改 NPC 态度
```

`purchase` action 且余额足够时，EconomyService 才能扣铜币。扣款成功后，grants 才能进入 Reward/Entitlement/Relationship 服务。余额不足时所有 grants 都必须丢弃。

### Discovery 权限

DiscoveryTable 只能产生：

```text
narration_fact
reveal_objects
risk_delta proposal
clues proposal
next_action_suggestions
```

DiscoveryTable 不允许直接产生：

```text
currency_delta
entitlements
quest_stage=resolved
npc_trust_delta
```

这些必须通过 RewardService、QuestService 或 RelationshipService 的条件校验。

### P1 单任务线门禁

P1 阶段 active quest 白名单固定为：

```text
night_wolf_line
```

规则：

- `world_state.active_quest.quest_id` 只能是 `night_wolf_line`。
- 其他 QuestContentPack 只能作为 `inactive_proposal` 保存，不得显示为当前任务。
- inactive quest 不允许推进 stage。
- inactive quest 不允许发 reward。
- inactive quest 不允许改变当前可互动主线建议。
- 模型 proposal 或内容包试图激活第二条任务线时，记录 `blocked_reason=p1_single_quest_only`。

P1 可以加载其他任务传闻作为线索文本，但这些线索只能是 `clue`，不能成为 active quest。

## 核心数据结构

### SceneObject

沿用上一份文档的结构：

```json
{
  "id": "obj_abc123",
  "type": "clue",
  "name": "被雨水泡软的猎人手札",
  "aliases": ["手札", "猎人笔记"],
  "description": "纸页边缘发黑，夹着几根粗硬兽毛。",
  "visibility": "visible",
  "presence": "current",
  "scope": "current_node",
  "node_id": "forest_watchtower",
  "affordances": ["observe", "search", "take"],
  "tags": ["portable_clue", "quest_hint"],
  "source": "scene_object_materializer"
}
```

实现约束：

- 代码只识别 `type/affordances/tags`。
- 代码不识别“猎人手札”这个具体名称。
- 具体名称只用于展示和自然语言绑定。

### LocationGraph

```json
{
  "graph_id": "graystone_town_graph",
  "nodes": [
    {
      "node_id": "old_furnace_inn.front_hall",
      "region": "灰石镇",
      "site": "旧炉旅店",
      "sublocation": "前厅",
      "display_name": "灰石镇 / 旧炉旅店 / 前厅",
      "environment": "低矮温热的前厅，火塘边有旅人低声交谈。",
      "object_refs": ["innkeeper_01", "kitchen_door_01"],
      "neighbors": ["old_furnace_inn.kitchen", "graystone_town.gate_street"]
    }
  ]
}
```

规则层职责：

- 判断目标 node 是否存在。
- 判断是否邻接。
- 更新 `location_path`。
- 切换对象 `presence`。

规则层不负责：

- 写死灰石镇。
- 写死旧炉旅店。
- 写死后厨。

### Facility

```json
{
  "facility_id": "old_furnace_inn",
  "type": "inn",
  "name": "旧炉旅店",
  "node_ids": ["old_furnace_inn.front_hall", "old_furnace_inn.kitchen"],
  "services": ["lodging", "meal"],
  "owner_npc_id": "innkeeper_01",
  "rules": {
    "requires_lodging_identity": true,
    "can_grant_bed_entitlement": true
  }
}
```

Facility 用来承载“旅店、铁匠铺、药草铺、神庙、码头仓库”等设施语义。新增设施时不改 EconomyService，只新增设施数据。

### MerchantInventory / Offer

```json
{
  "merchant_id": "innkeeper_01",
  "facility_id": "old_furnace_inn",
  "offers": [
    {
      "offer_id": "bed_common_01",
      "kind": "entitlement",
      "name": "二楼三号房床位",
      "price_copper": 3,
      "grants": {
        "entitlements": [
          {
            "id": "inn_room_3_bed",
            "name": "二楼三号房床位",
            "valid_until_rule": "next_morning"
          }
        ],
        "items": ["二楼三号房钥匙"]
      }
    },
    {
      "offer_id": "stew_meal_01",
      "kind": "meal",
      "name": "热炖菜一碗",
      "price_copper": 2,
      "grants": {
        "meal_effect": "warm_meal"
      }
    }
  ]
}
```

EconomyService 只负责：

- `copper_total >= price_copper`
- 扣款。
- 写交易记录。
- 将 grants 交给 RewardService/EntitlementService 校验后落库。

### DiscoveryTable

```json
{
  "target_object_id": "old_firepit_01",
  "entries": [
    {
      "entry_id": "wet_ash_01",
      "trigger": {
        "action_type": "search",
        "min_intensity": "normal"
      },
      "result": {
        "narration_fact": "灰烬还是潮的，说明不久前有人在这里压低火光停留。",
        "reveal_objects": ["hidden_wolf_fur_01"],
        "risk_delta": {"noise": 1},
        "clues": ["有人或某种生物最近使用过哨塔"]
      }
    }
  ]
}
```

ResolutionEngine 只负责：

- 根据 action 和 target 查 DiscoveryTable。
- 判断触发条件。
- reveal 对象。
- 汇总风险和线索 proposal。
- 交给 Reward/StateChange 闸门校验。

### QuestContentPack

```json
{
  "quest_id": "night_wolf_line",
  "allowed_as_active_p1": true,
  "stages": ["not_started", "rumor_heard", "night_event_seen", "prepared", "tracking", "resolved"],
  "transitions": [
    {
      "from": "not_started",
      "to": "rumor_heard",
      "trigger": {
        "source": "clue_added",
        "clue_tag": "night_wolf_rumor"
      },
      "adds_clues": ["夜里镇墙外有异常低嚎"]
    }
  ],
  "rewards": [
    {
      "stage": "resolved",
      "items": ["暗夜狼牙 x1"],
      "currency_delta": 8,
      "relationship_delta": [{"npc_id": "innkeeper_01", "trust": 10}]
    }
  ]
}
```

QuestService 只负责：

- 单任务线约束。
- 当前 stage 是否允许 transition。
- trigger 是否满足。
- reward 是否交给 RewardService。

## 模块重构方案

### 1. IsekaiInteractableProjector -> SceneObjectProjector

现状：

- 通过关键词生成对象。

目标：

- 只从已落库 SceneObject 中投影当前可见对象。

迁移：

- 保留原 projector，改名为 `LegacyKeywordProjector`。
- 只在旧存档、模型缺对象、测试迁移时调用。
- 新内容禁止向 legacy projector 增加具体对象分支。

### 2. IsekaiActionParser / Grounder

现状：

- parser 负责大量关键词分类和 loose target 词表。

目标：

- IntentInterpreter 理解自然语言。
- Grounder 基于 SceneObject 匹配目标。
- Parser 只保留低风险 fallback，不作为主路径。

匹配顺序：

```text
exact id
-> exact name
-> alias match
-> recent reference
-> type + affordance match
-> ambiguity clarification
-> not found clarification
```

禁止：

- 在 parser 中继续添加具体目标词。

### 3. IsekaiLocationService

现状：

- 固定旧炉旅店节点。

目标：

- 接收 `LocationGraph`。
- 只负责图操作。

迁移：

- 把旧炉旅店节点搬到 `old_furnace_inn_p1` content pack。
- `IsekaiLocationService` 从 world_state 或 content pack 读取 graph。
- 没有 graph 时允许模型/开局生成器创建初始 graph。

### 4. IsekaiActionResolutionEngine

现状：

- 写死进入地点默认对象。
- 写死神庙/森林/哨塔发现。
- 写死货袋掉落。

目标：

- 查询 `DiscoveryTable`。
- 查询 `SceneObject.destination_node_id` 或 `LocationGraph`。
- 对结果进行确定性结算。

禁止：

- 通用 resolution 中出现具体地点和物品发现分支。

允许：

- 内容包提供具体 DiscoveryTable。
- 测试 fixture 提供具体场景。

### 5. IsekaiEconomyService

现状：

- 固定 `inn_bed` / `stew_meal`。

目标：

- 从当前 merchant/facility offer 中购买。
- EconomyService 不关心商品是不是床位、炖菜、药草或工具。

迁移：

- 将 `inn_bed` / `stew_meal` 搬到旧炉旅店 content pack。
- `purchase` action 必须绑定 `offer_id`。
- 如果玩家只说“买床位”，Grounder 用当前 merchant inventory 的 offer aliases 匹配。

### 6. IsekaiQuestService

现状：

- `night_wolf_line` 写死在 service。

目标：

- P1 仍只允许 `night_wolf_line`。
- 但阶段、线索、奖励来自 QuestContentPack。

迁移：

- Service 保留：
  - allowed active quest count = 1
  - allowed quest id = content pack 声明的 P1 quest
  - transition 校验
- 内容文本迁移出 service。

### 7. IsekaiNarrationComposer

现状：

- 通过具体 marker 判断是否用自然叙事。

目标：

- 依据 resolved result 类型判断输出风格。
- 不依赖“铁头箭、旧火堆、空香瓶”等具体词。

建议：

```text
if result.has_specific_facts:
    natural narration
else:
    concise structured fallback
```

## 数据流

### 场景生成回合

```text
LLM narration + structured payload
-> materialize scene_objects/location/offers/discoveries
-> validators filter proposals
-> NarrationObjectConsistencyGate repairs narration/object mismatch
-> store runtime state
-> frontend renders validated state
```

硬规则：

- 最终 DM 文本中出现的当前可见主要对象，必须已经进入 `SceneState.interactables` 或 `world_state.scene_object_memory_by_node`。
- 被 validator 拒绝的当前对象不得保留在最终 DM 文本中。
- 如果对象只能作为远景、传闻或气氛存在，narration 必须明确它不可立即互动。
- 流式输出可以先展示草稿文本，但 final event 返回前，最终 message、metadata、current_scene 必须一致。

### 玩家行动回合

```text
player input
-> IntentInterpreter outputs action steps
-> Grounder binds target_id/offer_id/node_id
-> Precondition validates object/location/resources
-> ResolutionEngine executes
-> DiscoveryTable reveals facts/objects
-> Economy/Reward/Quest services commit allowed changes
-> NarrationComposer explains committed consequences
-> NarrationObjectConsistencyGate verifies final narration
```

### 找不到目标

```text
target_text not found
-> search current aliases
-> search recent references
-> search remembered nearby objects
-> optional object extraction from last narration
-> clarification with visible candidates
```

禁止退回泛化执行：

```text
角色快速观察周围。
```

## 内容和规则边界

| 内容包可以定义 | 规则层负责 |
| --- | --- |
| 地点名称 | 地点邻接校验 |
| NPC 名称和态度初值 | NPC 当前是否在场 |
| 商品名称和价格 | 余额校验和扣款 |
| 可互动对象名称 | type/affordance 校验 |
| 隐藏发现文本 | 搜索是否触发 reveal |
| 任务阶段名称 | stage transition 合法性 |
| 奖励 proposal | RewardService 权限闸门 |

## 迁移策略

### P0：加新系统，不删旧系统

- 新增 ContentPack schema。
- 新增 SceneObject/LocationGraph/Offer/DiscoveryTable validator。
- 旧逻辑保留，但加 metadata 标记 `legacy_content_fallback=true`。
- 新测试要求随机对象名不能写入代码分支。

退出条件：

- `SceneObject`、`LocationGraph`、`Offer`、`DiscoveryTable` schema 和 validator 单测通过。
- `world_state.content_packs` 能加载至少一个 content pack。
- 通过 validator 的 scene object 能进入 `SceneState.interactables`。
- metadata 能标记 `content_pack`、`llm_proposal`、`legacy_fallback` 来源。
- 新增对象名不需要修改 `IsekaiInteractableProjector`。

### P1：旧炉旅店内容包化

- 把灰石镇 / 旧炉旅店 / 后厨 / 床位 / 炖菜 / 锅把迁出 service。
- 作为 `old_furnace_inn_p1` content pack 加载。
- 保持 P1 单任务线不变。

退出条件：

- `IsekaiLocationService` 不再内置灰石镇/旧炉旅店节点。
- `IsekaiEconomyService` 不再内置 `inn_bed` / `stew_meal` 商品。
- 旧炉旅店 10 步验收流程仍通过。
- P1 active quest 仍只能是 `night_wolf_line`。
- 其他 quest proposal 被记录为 inactive，不出现在当前任务面板。

### P2：探索发现内容包化

- 神庙木箱、森林麋鹿、哨塔旧火堆等发现迁入 DiscoveryTable fixture。
- 通用 resolution 删除具体发现分支。
- 旧存档通过 migration 或 legacy fallback 补齐。

退出条件：

- `IsekaiActionResolutionEngine` 中不再出现具体地点/对象发现分支。
- 随机 DiscoveryTable 能 reveal 隐藏对象、线索和风险 proposal。
- DiscoveryTable 不能直接发钱、发钥匙、完成任务。
- 找不到目标时返回 clarification，不退回“观察周围”。

### P3：经济和任务完全内容包化

- EconomyService 支持任意 offer。
- QuestService 从 QuestContentPack 推进阶段。
- `night_wolf_line` 仍可作为唯一 active quest，但不再写死文本。

退出条件：

- 任意合法 Offer 可购买并扣铜币，不需要改 EconomyService 常量。
- Offer grants 全部经过 Reward/Entitlement/Relationship 服务。
- QuestService 不包含暗夜狼、梦魇草、旧炉旅店等具体文本判断。
- `night_wolf_line` 的阶段、线索、奖励来自 QuestContentPack。

### P4：删除 legacy 具体对象扩展入口

- 禁止向 LegacyKeywordProjector 添加具体内容。
- 新内容只能通过 content pack 或 LLM proposal。
- CI 增加扫描规则，防止 service 中新增明显内容硬编码。

退出条件：

- CI 扫描覆盖 services 中的已知内容硬编码入口。
- LegacyKeywordProjector 只保留门/入口、容器、水源、NPC、商人、庇护点等通用类别。
- 新场景、新商品、新发现、新地点全部能通过 content pack 或 LLM proposal 接入。
- service 中新增具体内容词会导致扫描测试失败。

## 测试策略

### 架构防回退测试

新增测试：

```text
test_isekai_content_agnostic_boundaries.py
```

覆盖：

- 随机对象名通过 content pack 可交互，不需要改 projector。
- 随机商品通过 offer 可购买，不需要改 EconomyService 常量。
- 随机地点通过 LocationGraph 可进入，不需要改 LocationService。
- 随机发现通过 DiscoveryTable 可 reveal，不需要改 ResolutionEngine。

### 代码扫描测试

新增轻量扫描：

- 禁止 `IsekaiInteractableProjector` 新增具体对象分支。
- 禁止 `IsekaiActionParser._loose_target_match` 新增具体内容词。
- 禁止 `IsekaiActionResolutionEngine` 新增具体地点/物品发现分支。
- 禁止 `IsekaiLocationService` 新增具体地点图节点。
- 禁止 `IsekaiEconomyService` 新增具体商品常量。
- 禁止 `IsekaiQuestService` 新增具体任务文本判断。

允许例外：

- `test/` fixture。
- `content_packs/` 数据。
- migration/legacy fallback 文件。

扫描测试不需要理解所有中文语义，但必须锁住已知风险文件的新增硬编码入口。建议测试对指定文件做快照或 denylist 检查，并要求新具体内容只能出现在 `content_packs/`、测试 fixture 或 migration 文件中。

### 回归验收

用从未出现在代码里的内容跑完整流程：

```text
地点：雾盐渡口 / 倾斜灯塔 / 潮湿储物间
对象：蓝盐水洼 / 虫蚀皮袋 / 倒悬铜镜
商品：苦根汤 / 临时渡船位 / 干蜡绳
任务：只作为 inactive proposal，不允许突破 P1 单任务线
```

验收：

- 前端显示对象。
- 玩家能引用对象。
- 搜索能 reveal 发现。
- 购买能扣铜币。
- 不需要在 service 中新增任何这些具体词。

## 风险和应对

### 风险 1：模型输出对象太多

应对：

- 每轮新增对象上限。
- 按 `salience` 和 `presence` 筛选前端展示。
- 低优先级对象进入 remembered，不进入当前交互面板。

### 风险 2：模型输出非法能力

应对：

- affordance 能力闭集过滤。
- 被过滤项写入 metadata。

### 风险 3：内容包和当前状态冲突

应对：

- validator 检查 node_id、presence、visibility。
- 冲突对象进入 blocked proposals。
- NarrationRepairer 删除明显冲突句。

### 风险 4：旧存档依赖旧逻辑

应对：

- 保留 legacy fallback。
- 输出 metadata 标记旧逻辑来源。
- 逐步通过 migration 修复高频旧状态。

### 风险 5：实现跨度过大

应对：

- 分阶段迁移。
- 先让新内容走新系统。
- 旧内容包化时保持接口兼容。

## 验收标准

1. 新对象不需要写入 `IsekaiInteractableProjector`。
2. 新目标词不需要写入 `_loose_target_match`。
3. 新地点不需要改 `IsekaiLocationService` 代码。
4. 新商品不需要改 `IsekaiEconomyService.PRICE_CONFIGS`。
5. 新探索发现不需要改 `IsekaiActionResolutionEngine`。
6. 旧炉旅店作为 content pack 仍能完成原 P1 流程。
7. 随机对象、随机商品、随机地点、随机发现的回归测试通过。
8. 找不到目标时返回澄清，不再泛化执行。
9. 模型 proposal 不能绕过 validator 改最终状态。
10. metadata 能区分 `content_pack`、`llm_proposal`、`legacy_fallback` 来源。
11. ContentPack 有 `schema_version/source/scope/lifecycle/priority/conflict_policy`。
12. 被拒绝的当前对象不会留在最终 DM 文本中。
13. P1 阶段除 `night_wolf_line` 外没有第二条 active quest。
14. 每个迁移阶段都有自动化退出条件。

## 已定架构决策

开发按以下决策执行，不再作为开放问题处理：

- 第一阶段 ContentPack 存 `world_state.content_packs`，不建独立表。
- `SceneObject`、`LocationGraph`、`Offer`、`DiscoveryTable`、`QuestContentPack` 可以先放在 `backend/src/services/isekai_content.py` 或 `backend/src/services/isekai_content_types.py`；当文件超过 400 行或测试需要独立导入时再拆文件。
- `old_furnace_inn_p1` 是第一个必须迁移的 content pack 样例。
- P1 阶段 active quest 只允许 `night_wolf_line`；其他任务内容只能 inactive proposal。
- CI 扫描必须加入，防止新内容重新写进 service。
- 流式输出可以先发 delta，但 final event 前必须完成 content proposal 校验、状态落库和 narration 一致性修正。
- content proposal 不允许后台异步补齐后再改变刚刚展示给玩家的最终结果；需要补齐时，下一回合作为新发现或 clarification 处理。

## 结论

这次问题不是某个对象缺失，而是异世界模式多处服务把“内容”写进了“规则”。统一重构方向应是：

```text
具体内容进入 ContentPack 或 LLM proposal。
通用服务只处理抽象类型、动作能力、权限、校验和结算。
```

这样才能让异世界模式支持随机生成世界，而不是每新增一个场景就继续补关键词和 if 分支。
