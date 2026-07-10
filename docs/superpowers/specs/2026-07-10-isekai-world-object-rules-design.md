# 异世界模式 WorldObject 规则设计

## 背景

地点/空间规则已经确定：外部世界用 `WorldChunk` 表示，进入具体地点后使用 `Site -> LocationNode -> Zone`，所有对象通过位置链挂在 chunk、zone、其他对象、角色或玩家物品栏上。

下一步需要统一世界中的非生命对象。水壶、铠甲、战斧、肖像画、柜台、门、捕兽夹、货箱、井、告示牌、钥匙、货币都不能只存在于 DM 文本里，也不能靠具体名称硬编码规则。

本设计将非生命对象统一定义为 `WorldObject`。`WorldObject` 是可被描述、观察、移动、拾取、购买、装备、打开、破坏、修理、阅读、消耗或作为空间锚点引用的权威对象。

## 目标

- 建立所有非生命对象共用的最小 schema。
- 让对象必须有稳定 ID、类型、位置、可见性、物理属性、所有权、可尝试动作和生命周期字段。
- 让对象能力由 `object_type + components + affordances + resolver` 决定，而不是由具体中文名称决定。
- 让 DM 旁白、UI 可互动列表和动作目标绑定都引用已落库 `WorldObject`。
- 支持水壶、铠甲、战斧、肖像画这类内容扩展，而不新增后端硬编码分支。

## 非目标

- 不一次性实现完整装备、战斗、工艺、经济、制造系统。
- 不按具体物品名建立类型，例如不允许 `red_kettle`、`wolf_axe`、`old_portrait` 作为 `object_type`。
- 不让 LLM 直接发放最终物品、扣钱、装备角色或修改资源。
- 不把所有可想象物品属性塞进基础 schema。特殊能力通过 components 扩展。
- 不替代地点/空间规则；对象位置必须遵守地点/空间规则文档。

## 核心原则

### 1. 对象必须是真实状态

DM 最终旁白中出现的当前可见主要非生命对象，必须已经存在于 `WorldObject` 状态，或在同轮通过 validator 写入状态。

### 2. 对象类型是规则语义，不是内容名称

`object_type` 只表达稳定规则语义。新增“缺口战斧”“褪色肖像画”“蓝盐水壶”这类内容时，不得新增类型；它们应由 `name`、`aliases`、`tags`、`description` 和 components 表达。

### 3. 位置是权威字段

所有 `WorldObject` 必须有 `placement`。对象不允许只靠 DM 文本、UI 文案或父级字符串表达位置。

### 4. affordance 是可尝试动作，不是成功承诺

`affordances` 表示玩家可以合理尝试的动作。真正成功、失败、耗时、风险和状态变化，由 deterministic resolver 决定。

### 5. 特殊能力走组件

基础 schema 只放所有对象都需要的字段。容器、装备、武器、护甲、钥匙、陷阱、文档、艺术品、光源等能力使用组件扩展。

## P0 最小 Schema

P0 必填字段：

```json
{
  "id": "water_kettle_01",
  "name": "凹陷水壶",
  "object_type": "container",
  "placement": {
    "kind": "zone",
    "node_id": "hunter_cabin_inside",
    "zone_id": "old_stove",
    "local_position": "beside_stove"
  },
  "visibility": "visible",
  "physical": {
    "size": "small",
    "weight_kg": 0.8,
    "portable": true,
    "condition": "worn"
  },
  "affordances": ["observe", "take", "drink", "refill_water"],
  "state": {},
  "created_turn": 0,
  "updated_turn": 0
}
```

P0 推荐字段：

```json
{
  "aliases": ["水壶", "壶"],
  "description": "壶身被撞凹，壶嘴有干涸的水垢。",
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "tags": ["water_container", "metal"],
  "source": "content_pack"
}
```

完整 P0 示例：

```json
{
  "id": "water_kettle_01",
  "name": "凹陷水壶",
  "aliases": ["水壶", "壶"],
  "description": "壶身被撞凹，壶嘴有干涸的水垢。",
  "object_type": "container",
  "placement": {
    "kind": "zone",
    "node_id": "hunter_cabin_inside",
    "zone_id": "old_stove",
    "local_position": "beside_stove"
  },
  "visibility": "visible",
  "physical": {
    "size": "small",
    "weight_kg": 0.8,
    "portable": true,
    "condition": "worn"
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "drink", "refill_water"],
  "state": {
    "opened": true
  },
  "tags": ["water_container", "metal"],
  "source": "content_pack",
  "created_turn": 0,
  "updated_turn": 0
}
```

## 字段定义

### id

稳定唯一 ID，不依赖对象中文名称。对象被改名或本地化后，`id` 不变。

```json
"id": "battle_axe_01"
```

### name

玩家可见名称。

```json
"name": "缺口战斧"
```

### aliases

用于玩家自然语言目标绑定。可为空数组。

```json
"aliases": ["战斧", "斧头", "旧斧"]
```

### description

短描述，用于 DM 叙事和观察反馈。描述不能包含未经落库的其他当前可互动对象。

```json
"description": "斧刃有两处缺口，木柄缠着旧皮条。"
```

### object_type

抽象对象类型。P0 允许类型：

```text
item
weapon
armor
tool
container
resource
food
water_source
furniture
fixture
portal
clue
document
artwork
trap
mechanism
currency
key
vehicle
material
light_source
```

类型扩展规则：

```text
只有新增规则语义时才能扩展 object_type。
新增具体内容名时不得扩展 object_type。
```

### placement

权威位置。必须符合地点/空间规则文档的 `ObjectPlacement`。

允许的 `placement.kind`：

```text
chunk
zone
on_object
inside_object
under_object
attached_to_object
near_object
carried_by_actor
player_inventory
offscreen
removed
```

### visibility

玩家当前可见性：

```text
visible：当前能直接看到。
hinted：有线索暗示，但对象未完全确认。
hidden：隐藏，普通投影不显示。
discovered：已被发现，可被玩家指代。
removed：已消失、消耗或销毁。
```

### physical

最小物理属性：

```json
{
  "size": "medium",
  "weight_kg": 3.5,
  "portable": true,
  "condition": "worn"
}
```

`size` 枚举：

```text
tiny
small
medium
large
huge
structure
```

`condition` 枚举：

```text
intact
worn
damaged
broken
ruined
```

规则：

```text
portable=false 的对象不能直接进入玩家物品栏。
condition=broken 的对象不能执行正常使用类动作，除非 resolver 允许修理、拆解或强行使用。
condition=ruined 的对象不能恢复为正常使用状态，除非专门规则允许。
```

### ownership

所有权和合法状态。P0 推荐必填，允许 `owner_id=null`。

```json
{
  "owner_id": "innkeeper_01",
  "faction_id": "graystone_town",
  "legal_status": "owned"
}
```

`legal_status` 枚举：

```text
owned：有主人，拿走算偷。
for_sale：可购买。
abandoned：废弃，可拿但仍可能有风险。
public：公共物。
quest_locked：任务锁定。
unknown：所有权不明。
```

### affordances

玩家可以合理尝试的动作能力。P0 允许能力：

```text
observe
take
equip
unequip
attack
open
close
lock
unlock
search
read
repair
break
move
push
pull
drink
eat
refill_water
pour
trade
purchase
hide_behind
disarm
trigger
enter
leave
```

不在允许集合内的 affordance 必须被 validator 删除，并写入 `blocked_affordances`。

### state

对象当前状态，轻量 key-value。P0 允许常用键：

```text
durability
opened
locked
equipped_by
charges
fuel
amount
quality
```

规则：

```text
state 不能承载位置、所有权和可见性；这些必须写入专用字段。
resolver 可以修改 state，LLM proposal 不能直接提交最终 state 变更。
```

### tags

用于搜索、叙事、规则分类和内容过滤，不参与核心结算。

```json
"tags": ["rusty", "two_handed", "hunter_cabin"]
```

### source

对象来源，用于调试和回放。

```text
content_pack
llm_proposal
dm_scene_proposal
resolver_created
legacy_fallback
```

### created_turn / updated_turn

生命周期追踪。对象创建和每次状态变化后必须更新。

## 组件扩展

基础 schema 不为每种对象加专用字段。特殊能力通过 `components` 扩展。

```json
{
  "components": {
    "container": {},
    "weapon_stats": {},
    "armor_stats": {}
  }
}
```

### container

```json
{
  "components": {
    "container": {
      "capacity": {
        "amount": 2,
        "unit": "liter"
      },
      "contents": [
        {
          "resource_type": "water",
          "amount": 0.4,
          "unit": "liter",
          "quality": "stale"
        }
      ]
    }
  }
}
```

### weapon_stats

```json
{
  "components": {
    "weapon_stats": {
      "damage_profile": "heavy_slash",
      "hands": 2,
      "range": "melee",
      "noise": "medium"
    }
  }
}
```

### armor_stats

```json
{
  "components": {
    "armor_stats": {
      "slot": "body",
      "armor_rating": 3,
      "mobility_penalty": 1,
      "noise": "medium"
    }
  }
}
```

### art_profile

```json
{
  "components": {
    "art_profile": {
      "subject": "一名戴银扣斗篷的猎人",
      "value_hint": "low",
      "hidden_detail": "画框背面刻着北坡旧猎径的符号"
    }
  }
}
```

### key_profile

```json
{
  "components": {
    "key_profile": {
      "opens_lock_ids": ["inn_room_03_lock"],
      "single_use": false
    }
  }
}
```

### trap_profile

```json
{
  "components": {
    "trap_profile": {
      "trigger_condition": "step_near",
      "severity": "medium",
      "disarm_difficulty": "moderate",
      "armed": true
    }
  }
}
```

P0 组件白名单：

```text
container
weapon_stats
armor_stats
consumable
currency_value
key_profile
trap_profile
document_profile
art_profile
light_profile
```

## 示例

### 战斧

```json
{
  "id": "battle_axe_01",
  "name": "缺口战斧",
  "aliases": ["战斧", "斧头", "旧斧"],
  "description": "斧刃有两处缺口，木柄缠着旧皮条。",
  "object_type": "weapon",
  "placement": {
    "kind": "inside_object",
    "object_id": "weapon_chest_01",
    "visibility": "hidden",
    "reachability": "requires_open_container"
  },
  "visibility": "hidden",
  "physical": {
    "size": "medium",
    "weight_kg": 3.5,
    "portable": true,
    "condition": "worn"
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "equip", "attack", "repair"],
  "components": {
    "weapon_stats": {
      "damage_profile": "heavy_slash",
      "hands": 2,
      "range": "melee",
      "noise": "medium"
    }
  },
  "state": {
    "durability": 62,
    "equipped_by": null
  },
  "tags": ["two_handed", "hunter_cabin"],
  "source": "content_pack",
  "created_turn": 0,
  "updated_turn": 0
}
```

### 铠甲

```json
{
  "id": "rusted_chainmail_01",
  "name": "生锈锁子甲",
  "aliases": ["锁子甲", "铠甲"],
  "object_type": "armor",
  "placement": {
    "kind": "on_object",
    "object_id": "cabin_armor_stand_01",
    "relation": "hanging_on",
    "visibility": "visible",
    "reachability": "reachable"
  },
  "visibility": "visible",
  "physical": {
    "size": "medium",
    "weight_kg": 9.0,
    "portable": true,
    "condition": "damaged"
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "equip", "repair"],
  "components": {
    "armor_stats": {
      "slot": "body",
      "armor_rating": 3,
      "mobility_penalty": 1,
      "noise": "medium"
    }
  },
  "state": {
    "durability": 41,
    "equipped_by": null
  },
  "source": "content_pack",
  "created_turn": 0,
  "updated_turn": 0
}
```

### 肖像画

```json
{
  "id": "old_portrait_01",
  "name": "褪色肖像画",
  "aliases": ["肖像画", "画像", "画"],
  "object_type": "artwork",
  "placement": {
    "kind": "attached_to_object",
    "object_id": "cabin_north_wall_01",
    "relation": "hanging_on",
    "visibility": "visible",
    "reachability": "reachable"
  },
  "visibility": "visible",
  "physical": {
    "size": "medium",
    "weight_kg": 1.2,
    "portable": true,
    "condition": "worn"
  },
  "ownership": {
    "owner_id": null,
    "legal_status": "abandoned"
  },
  "affordances": ["observe", "take", "search"],
  "components": {
    "art_profile": {
      "subject": "一名戴银扣斗篷的猎人",
      "value_hint": "low",
      "hidden_detail": "画框背面刻着北坡旧猎径的符号"
    }
  },
  "state": {},
  "tags": ["family_history", "hidden_clue"],
  "source": "content_pack",
  "created_turn": 0,
  "updated_turn": 0
}
```

## 权威操作规则

### 观察

`observe` 不改变对象位置。它可以把 `visibility=hinted` 改为 `visible`，并写入 `ObjectRevealedEvent`。

### 拾取

`take` 成功后必须修改 `placement`：

```text
zone/on_object/inside_object
-> player_inventory
```

如果 `physical.portable=false`，resolver 必须拒绝直接拾取，并给出移动、拆解、推拉或搜索等替代方案。

### 购买

`purchase` 必须同时满足：

```text
ownership.legal_status = for_sale
玩家货币足够
卖方或设施在当前 projection 中可交互
```

成功后：

```text
扣钱
写交易事件
修改 ownership 或 placement
刷新 projection
```

### 装备

`equip` 必须检查：

```text
object_type = weapon 或 armor 或 tool
对象在玩家物品栏或当前可触及位置
装备槽未冲突
condition 不为 broken/ruined
```

成功后写入 `ObjectEquippedEvent`，并更新 `state.equipped_by`。

### 消耗

`eat`、`drink`、`use_consumable` 成功后必须修改资源、对象 state 或 placement：

```text
amount 减少
durability/fuel/charges 减少
对象耗尽后 placement=removed 或 visibility=removed
```

### 打开和搜索

`open` 和 `search` 对容器、机关、画框、柜子等对象生效。搜索结果必须来自：

```text
inside_object contents
hidden child objects
DiscoveryTable
```

不能由 DM 临场凭空发放最终物品。

## Validator 规则

实现时必须加入 `WorldObjectValidator`，保证：

1. `id` 全局唯一。
2. `name` 非空。
3. `object_type` 属于允许集合。
4. `placement.kind` 属于允许集合。
5. `placement` 引用的 chunk、node、zone、object、actor 必须存在。
6. 对象位置链不能形成循环。
7. `visibility=removed` 时，`placement.kind` 必须是 `removed` 或对象不得出现在当前 projection。
8. `physical.size` 和 `physical.condition` 属于允许集合。
9. `physical.weight_kg` 不能为负数。
10. `physical.portable=false` 的对象不能被 resolver 直接放入 `player_inventory`。
11. `ownership.legal_status` 属于允许集合。
12. `affordances` 必须属于允许集合。
13. `components` 必须属于组件白名单。
14. 组件和 `object_type` 必须兼容，例如 `armor_stats` 只能用于 `armor` 或被明确允许的 `tool`。
15. LLM proposal 不能直接提交 placement、ownership、state 的最终变更，必须经过 resolver。

## 与其他文档关系

本设计依赖：

- [2026-07-10-isekai-location-space-rules-design.md](./2026-07-10-isekai-location-space-rules-design.md)
- [2026-07-08-isekai-scene-object-structuring-design.md](./2026-07-08-isekai-scene-object-structuring-design.md)
- [2026-07-08-isekai-content-agnostic-refactor-design.md](./2026-07-08-isekai-content-agnostic-refactor-design.md)
- [2026-07-08-isekai-llm-intent-resolution-design.md](./2026-07-08-isekai-llm-intent-resolution-design.md)

数据流：

```text
ContentPack / LLM Proposal
-> WorldObject Materializer
-> WorldObject Validator
-> Authoritative WorldState
-> SpaceProjectionService
-> ActionGrounder
-> Deterministic Resolver
-> EventLog
-> Narration Projection
-> UI Projection
```

## 推荐实现顺序

### P0.1：基础 schema 与 validator

交付内容：

- `WorldObject` schema。
- `WorldObjectValidator`。
- object_type、visibility、placement.kind、condition、legal_status、affordance、component 白名单。

验收：

- 缺少 `id/name/object_type/placement/visibility/physical/affordances/state/created_turn/updated_turn` 会被拒绝。
- 非法 object_type 会被拒绝。
- 非法 placement 引用会被拒绝。
- 对象位置链循环会被拒绝。

### P0.2：对象投影

交付内容：

- 将 `WorldObject` 投影接入 `SpaceProjectionService`。
- 当前 chunk/node/zone 可见对象查询。
- hidden/hinted/removed 过滤。

验收：

- `visibility=hidden` 的对象不出现在 visible projection。
- `visibility=hinted` 只作为线索出现，不作为可直接拾取对象。
- `placement=removed` 的对象不出现在可互动列表。

### P0.3：对象状态变更事件

交付内容：

- `ObjectMovedEvent`
- `ObjectRevealedEvent`
- `ObjectStateChangedEvent`
- `ObjectEquippedEvent`
- `ObjectConsumedEvent`
- `ObjectRemovedEvent`

验收：

- 拾取成功后 placement 变成 `player_inventory`。
- 消耗成功后 amount/charges/fuel 或 placement 正确变化。
- 装备成功后 `state.equipped_by` 正确变化。

### P0.4：组件接入

交付内容：

- container
- weapon_stats
- armor_stats
- consumable
- key_profile
- trap_profile
- document_profile
- art_profile

验收：

- 容器打开后才能显示内部 hidden contents。
- 武器和护甲能被装备，但不能绕过装备槽/condition 校验。
- 肖像画搜索能揭示画框背后的线索对象，而不是 DM 直接发放未落库线索。

## 回归测试要求

新增测试：

- `test_world_object_requires_minimum_fields`
- `test_world_object_rejects_unknown_object_type`
- `test_world_object_rejects_invalid_placement_reference`
- `test_world_object_placement_cycle_is_rejected`
- `test_hidden_object_not_in_visible_projection`
- `test_removed_object_not_in_interactable_projection`
- `test_take_moves_portable_object_to_player_inventory`
- `test_take_rejects_non_portable_object`
- `test_purchase_requires_for_sale_and_balance`
- `test_equip_requires_valid_component_and_condition`
- `test_consumed_object_updates_amount_or_removed`
- `test_container_contents_revealed_only_after_open_or_search`
- `test_llm_proposal_cannot_directly_grant_world_object`

## 架构决策

1. 非生命对象统一建模为 `WorldObject`。
2. `WorldObject` 的基础 schema 只放所有对象都必须有的字段。
3. 具体对象能力通过 components 扩展。
4. `object_type` 是闭集，具体内容名不得成为类型。
5. 所有对象必须有 `placement`。
6. 所有对象必须能通过位置链追溯到 chunk、zone、actor、玩家物品栏、offscreen 或 removed。
7. `affordance` 是可尝试动作，不是成功承诺。
8. 对象状态变化必须写事件。
9. LLM 可以提出对象，但不能直接提交最终状态变化。
