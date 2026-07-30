---
doc_id: isekai.settlement_social_world_rules
status: active
layer: world-model
owner: architecture
created_at: 2026-07-13
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.location_space_rules
  - isekai.static_world_runtime_rules
provides:
  - SettlementProfile
  - Institution
  - SocialGroupState
  - NamedNPCState
  - ServiceState
  - ServiceEntitlementState
  - LawPolicy
  - EconomyState
  - SocialPressureState
  - SettlementSocialWorldValidator
---

# 异世界模式聚落与社会世界生成规则设计

## 背景

地点与空间规则已经定义 `Settlement` 可以作为一组 `WorldChunk` 存在，但空间集合只能回答“灰石镇在哪里”，不能回答“谁住在这里、靠什么生存、谁掌权、旅店为什么营业、守卫为什么巡逻、外乡人为什么被排斥、价格为什么上涨”。

如果聚落只是一组 chunk，DM 很容易把社会压力、价格、住宿、服务、NPC 态度和流言写成旁白。这样玩家会感觉世界在说话，但系统没有真正记住选择。

本设计将聚落社会世界变成权威 `WorldState` 的一部分。调度器和 snapshot builder 可以读取这些状态；LLM 只能读取由它们生成的 `AgentObservationSnapshot` 并提出社会判断 proposal，不能直接读取权威状态或创造社会事实。

## 目标

- 让聚落不只是空间集合，而是空间、人口、机构、服务、制度、经济和压力的组合实体。
- 定义世界生成阶段必须生成哪些社会状态。
- 定义聚落如何从地形、道路、水源、资源、危险、文明压力和 Site 中形成。
- 定义少量关键 NPC 如何从社会群体和机构中生成。
- 定义服务、价格、权限、床位、钥匙、流言、巡逻和盘问等社会后果落到哪些权威状态。
- 让 AI 社会心智有明确读取对象和合法 proposal 目标。
- 保持 P0 轻量，不做完整政治、人口、税收、战争和供需经济模拟。

## 非目标

- 不实现全镇 NPC 独立 AI。
- 不生成每个普通居民的个人状态。
- 不实现完整政治模拟、阵营战争和人口迁移。
- 不实现完整供需经济、生产链和税收系统。
- 不让 AI 直接扣钱、发钥匙、授予住宿、改变服务、移动守卫或修改社会状态。
- 不把社会压力写成每回合固定旁白。
- 不替代地点/空间规则；所有机构、NPC 和服务都必须能追溯到空间位置。

## 核心原则

### 1. 聚落是社会实体，不只是空间实体

`Settlement` 仍由地点与空间规则定义，表示一组 chunk。但社会世界必须在其上生成 `SettlementProfile`，表达聚落为什么存在、如何运作、对外来者如何反应。

### 2. 人群优先于个体

普通居民、旅客、劳工、镇民和巡逻者默认使用 `SocialGroupState` 表示。只有玩家附近、提供服务、承担权力、掌握线索或进入持续关系的人，才生成 `NamedNPCState`。

### 3. 服务和权益必须是权威状态

“店主同意住宿”“付了 3 铜”“获得钥匙”“今晚有合法床位”不能只存在于 DM 文本。它们必须由 `ServiceState`、`EconomyState`、`NamedNPCState`、`WorldObject`、`Entitlement` 或 EventLog 表达。

P0 使用轻量 `ServiceEntitlementState` 表达服务权益。它不替代未来完整身份、财产或任务系统，只解决服务结果必须可见、可校验、可过期的问题。

### 4. AI 负责判断，规则负责落地

AI 可以判断某个群体或 NPC 会如何看待玩家行为，并提出 proposal。最终是否涨价、拒绝服务、增加巡逻、散播流言、改变态度，必须由 deterministic resolver 根据权威状态决定。

### 5. 聚落压力通过事件体现

社会压力不能每回合重复解释规则。它应通过价格变化、盘问、服务门槛、巡逻密度、流言、NPC 态度、宵禁限制和庇护意愿体现。

## 总体模型

```text
Settlement
-> SettlementProfile
-> Institution
-> SocialGroupState
-> NamedNPCState
-> ServiceState
-> ServiceEntitlementState
-> LawPolicy
-> EconomyState
-> SocialPressureState
-> AI Proposal
-> Validator
-> Resolver
-> EventLog
```

## P0 生成对象

P0 聚落社会世界生成必须至少支持：

```text
SettlementProfile：聚落画像。
Institution：机构、组织或经营体。
SocialGroupState：社会群体。
NamedNPCState：少量关键 NPC。
ServiceState：可交易、可请求或可获得的服务。
ServiceEntitlementState：服务成功后授予的轻量权益。
LawPolicy：当前聚落规则。
EconomyState：基础价格和资源压力。
SocialPressureState：社会压力和外乡人风险。
```

## SettlementProfile

`SettlementProfile` 表示聚落的社会画像。它引用地点/空间规则中的 `Settlement`，不替代 `Settlement`。

最小 schema：

```json
{
  "settlement_id": "graystone_town",
  "name": "灰石镇",
  "settlement_type": "frontier_town",
  "region_id": "graystone_town_region",
  "chunk_ids": [
    "chunk_graystone_10_10_0",
    "chunk_graystone_11_10_0"
  ],
  "population_band": "small",
  "economy_basis": ["hunting", "ore_trade", "road_service"],
  "governance": "guard_council",
  "law_profile": "curfew_strict",
  "outsider_policy": "suspicious_taxed",
  "resource_pressure": {
    "food": "medium",
    "water": "low",
    "lodging": "high",
    "security": "high"
  },
  "generated_by": {
    "system": "SettlementSocialFormation",
    "rule_id": "settlement.profile_from_space_resource_pressure"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `settlement_id` | 引用地点与空间规则中的 `Settlement.id`。 |
| `name` | 展示名，不能驱动规则。 |
| `settlement_type` | 聚落类型闭集。 |
| `region_id` | 聚落所属 Region。 |
| `chunk_ids` | 聚落覆盖的 chunk，必须与 `Settlement.chunk_ids` 一致或是其子集。 |
| `population_band` | 粗粒度人口规模，不表示精确人口数。 |
| `economy_basis` | 聚落生存和交易基础。 |
| `governance` | 聚落权力结构。 |
| `law_profile` | 聚落默认法律/秩序模型。 |
| `outsider_policy` | 对外乡人、异族、无身份者的默认政策。 |
| `resource_pressure` | 食物、水、住宿、安全等资源压力。 |
| `generated_by` | 生成系统和规则来源。 |

P0 `settlement_type` 闭集：

```text
hamlet
village
frontier_town
market_town
fortified_post
roadside_stop
mining_camp
ruin_settlement
```

P0 `population_band` 闭集：

```text
tiny
small
medium
large
```

P0 `economy_basis` 闭集：

```text
hunting
farming
herding
fishing
ore_trade
road_service
inn_trade
woodcutting
herbal_trade
guard_service
salvage
religious_pilgrimage
abnormal_resource_trade
```

P0 `governance` 闭集：

```text
elder_council
guard_council
merchant_lead
innkeeper_network
temple_authority
military_outpost
loose_custom
abandoned
```

P0 `law_profile` 闭集：

```text
none
customary
curfew_light
curfew_strict
checkpoint_control
military_order
temple_rule
```

P0 `outsider_policy` 闭集：

```text
welcoming
neutral
suspicious
suspicious_taxed
restricted
hostile
```

P0 `resource_pressure` 分级闭集：

```text
none
low
medium
high
critical
```

## Institution

`Institution` 表示聚落中的机构、组织或经营体。它可以绑定到一个 `Site`，也可以作为无明确建筑的社会组织存在。P0 推荐所有可交易和可交互机构都绑定 `site_id`。

示例：

```json
{
  "institution_id": "old_furnace_inn_business",
  "settlement_id": "graystone_town",
  "kind": "inn",
  "site_id": "old_furnace_inn",
  "controlled_by_group_id": "graystone_innkeepers",
  "operator_npc_ids": ["innkeeper_01"],
  "services": ["food", "lodging", "rumor"],
  "status": "open",
  "generated_by": {
    "system": "InstitutionFormation",
    "rule_id": "institution.inn_from_road_service"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `institution_id` | 机构 ID。 |
| `settlement_id` | 所属聚落。 |
| `kind` | 机构类型闭集。 |
| `site_id` | 机构绑定的 Site。P0 可为空，但提供服务的机构必须填写。 |
| `controlled_by_group_id` | 控制或代表该机构的社会群体。 |
| `operator_npc_ids` | 直接提供服务或交互的具名 NPC。 |
| `services` | 机构可提供的服务类型。 |
| `status` | 当前机构状态。 |
| `generated_by` | 生成系统和规则来源。 |

P0 `institution.kind` 闭集：

```text
inn
guard_post
market_stall
blacksmith
stable
well_house
temple_shrine
hunter_lodge
warehouse
checkpoint
elder_house
abandoned_site
```

P0 `institution.status` 闭集：

```text
open
restricted
closed
abandoned
damaged
under_watch
```

## SocialGroupState

`SocialGroupState` 表示一群人的共同身份、利益、恐惧、态度和压力。它是 AI 群体心智读取的主要对象，也是社会影响落地的主要目标之一。

示例：

```json
{
  "group_id": "graystone_locals",
  "settlement_id": "graystone_town",
  "kind": "local_residents",
  "population_band": "majority",
  "home_chunk_ids": ["chunk_graystone_10_10_0"],
  "associated_site_ids": ["old_furnace_inn"],
  "ideology_tags": ["protect_own", "distrust_outsiders"],
  "core_interests": ["security", "food_price", "curfew_order"],
  "fears": ["night_wolf", "tax_collector", "unknown_foreigners"],
  "attitude_to_player": "unknown_suspicious",
  "pressure": {
    "security": 0.7,
    "scarcity": 0.4,
    "xenophobia": 0.6
  },
  "state_revision": 1,
  "generated_by": {
    "system": "SocialGroupFormation",
    "rule_id": "social_group.locals_from_settlement_profile"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `group_id` | 社会群体 ID。 |
| `settlement_id` | 群体所属聚落。 |
| `kind` | 群体类型闭集。 |
| `population_band` | 群体相对规模。 |
| `home_chunk_ids` | 群体通常活动或居住的 chunk。 |
| `associated_site_ids` | 群体关联的 Site。 |
| `ideology_tags` | 群体倾向标签，必须来自 social ideology registry。 |
| `core_interests` | 群体核心利益闭集。 |
| `fears` | 群体恐惧对象或压力来源闭集/registry。 |
| `attitude_to_player` | 群体对玩家的当前态度。 |
| `pressure` | 群体当前压力数值，范围 0.0 到 1.0。 |
| `state_revision` | 状态修订号，AI proposal 必须引用。 |
| `generated_by` | 生成系统和规则来源。 |

P0 `SocialGroup.kind` 闭集：

```text
local_residents
innkeepers
guards
hunters
merchants
craftspeople
farmers
laborers
travelers
outsiders
minority_group
religious_group
criminals
refugees
```

P0 `population_band` 闭集：

```text
tiny
minority
small
significant
majority
dominant
```

P0 `core_interests` 闭集：

```text
security
food_price
water_access
lodging_control
trade_profit
curfew_order
territory
reputation
religious_order
resource_access
outsider_control
information_control
```

P0 `attitude_to_player` 闭集：

```text
unknown
unknown_suspicious
neutral
cautious
friendly
trusting
hostile
fearful
protective
exploitative
```

P0 `pressure` 数值键闭集：

```text
security
scarcity
xenophobia
fear
anger
trust
curiosity
greed
```

## NamedNPCState

`NamedNPCState` 表示少量具名 NPC。它不是所有居民的集合，也不替代 `WorldObject`。NPC 的空间位置使用地点与空间规则中的 actor location 结构。

示例：

```json
{
  "npc_id": "innkeeper_01",
  "name": "旧炉旅店店主",
  "role": "innkeeper",
  "settlement_id": "graystone_town",
  "home_site_id": "old_furnace_inn",
  "current_location": {
    "scope": "site_node",
    "site_id": "old_furnace_inn",
    "node_id": "old_furnace_inn_front_hall",
    "zone_id": "counter_area"
  },
  "group_id": "graystone_innkeepers",
  "institution_ids": ["old_furnace_inn_business"],
  "personality_tags": ["practical", "risk_averse"],
  "attitude_to_player": "cautious",
  "known_services": ["food", "lodging", "rumor"],
  "state_revision": 1,
  "generated_by": {
    "system": "NamedNPCFormation",
    "rule_id": "npc.service_provider_for_institution"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `npc_id` | NPC ID。 |
| `name` | 展示名，不能驱动规则。 |
| `role` | NPC 角色闭集。 |
| `settlement_id` | 所属聚落。 |
| `home_site_id` | 常驻或负责的 Site。 |
| `current_location` | 当前空间位置，必须能解析到 chunk 或 Site 内部节点。 |
| `group_id` | 来源或所属社会群体。 |
| `institution_ids` | NPC 关联的机构。 |
| `personality_tags` | 个性标签，用于 AI 生成对话和 proposal。 |
| `attitude_to_player` | NPC 对玩家的当前态度。 |
| `known_services` | NPC 可代表机构提供的服务类型。 |
| `state_revision` | 状态修订号，NPC proposal 必须引用。 |
| `generated_by` | 生成系统和规则来源。 |

P0 `NPC.role` 闭集：

```text
innkeeper
guard
merchant
blacksmith
stablehand
hunter
elder
priest
laborer
traveler
informant
gatekeeper
healer
ferryman
```

P0 `personality_tags` registry 初始值：

```text
practical
risk_averse
greedy
kind
suspicious
proud
fearful
curious
loyal
secretive
stern
talkative
```

## ServiceState

`ServiceState` 表示玩家或 NPC 可以请求、购买、交换或通过条件获得的服务。它解决“服务是否存在、谁提供、价格多少、需要什么、成功后授予什么”的问题。

示例：

```json
{
  "service_id": "old_furnace_lodging",
  "institution_id": "old_furnace_inn_business",
  "settlement_id": "graystone_town",
  "provider_npc_id": "innkeeper_01",
  "service_type": "lodging",
  "base_price": {
    "currency": "copper",
    "amount": 3
  },
  "availability": "limited",
  "requirements": ["not_banned", "pay_price"],
  "grants": ["legal_bed_for_tonight", "room_key"],
  "risk_modifiers": ["curfew_risk_down"],
  "state": {
    "active": true,
    "remaining_uses": 3
  },
  "generated_by": {
    "system": "ServiceFormation",
    "rule_id": "service.lodging_from_inn"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `service_id` | 服务 ID。 |
| `institution_id` | 提供服务的机构。 |
| `settlement_id` | 服务所属聚落。 |
| `provider_npc_id` | 直接提供或授权服务的 NPC。 |
| `service_type` | 服务类型闭集。 |
| `base_price` | 基础价格。P0 只允许 copper、silver、gold 三种货币单位。 |
| `availability` | 可用性。 |
| `requirements` | 请求服务前置条件闭集。 |
| `grants` | 成功后应授予的权益、对象或状态类型。 |
| `risk_modifiers` | 成功后对风险或社会压力的影响。 |
| `state` | 服务运行状态，例如 active、remaining_uses。 |
| `generated_by` | 生成系统和规则来源。 |

P0 `service_type` 闭集：

```text
food
lodging
water_access
stable_service
repair
rumor
trade
medical_help
guide
protection
entry_permission
```

P0 `availability` 闭集：

```text
available
limited
restricted
closed
sold_out
requires_permission
```

P0 `requirements` 闭集：

```text
pay_price
not_banned
before_curfew
has_identity
has_recommendation
provider_present
stock_available
service_open
social_attitude_not_hostile
```

P0 `grants` 闭集：

```text
food_item
water_refill
legal_bed_for_tonight
room_key
rumor_clue
repair_completed
entry_permission
trade_access
medical_treatment
guide_route
protection_status
```

P0 `risk_modifiers` 闭集：

```text
curfew_risk_down
curfew_risk_up
security_pressure_down
security_pressure_up
outsider_suspicion_down
outsider_suspicion_up
local_trust_up
local_trust_down
```

## ServiceEntitlementState

`ServiceEntitlementState` 表示服务成功后授予的轻量权益。它用于记录住宿权、入场许可、交易资格、庇护状态等社会结果。

它只记录“权利或许可”本身。实体物品仍应使用 `WorldObject`，例如房间钥匙、通行牌、纸质契约。

示例：

```json
{
  "entitlement_id": "entitlement_player_bed_old_furnace_day12",
  "holder_actor_id": "player",
  "settlement_id": "graystone_town",
  "institution_id": "old_furnace_inn_business",
  "service_id": "old_furnace_lodging",
  "entitlement_type": "legal_bed_for_tonight",
  "valid_scope": {
    "kind": "site",
    "site_id": "old_furnace_inn",
    "node_id": "old_furnace_room_03"
  },
  "valid_from": {
    "day": 12,
    "minute_of_day": 1080
  },
  "valid_until": {
    "day": 13,
    "minute_of_day": 480
  },
  "linked_object_ids": ["old_furnace_room_03_key"],
  "source_event_id": "event_paid_for_lodging_001",
  "state": {
    "active": true,
    "consumed": false
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `entitlement_id` | 权益 ID。 |
| `holder_actor_id` | 权益持有人，P0 可为玩家或具名 NPC。 |
| `settlement_id` | 权益所属聚落。 |
| `institution_id` | 授予权益的机构。 |
| `service_id` | 来源服务。 |
| `entitlement_type` | 权益类型闭集。 |
| `valid_scope` | 权益有效空间范围。 |
| `valid_from` | 权益开始时间。 |
| `valid_until` | 权益结束时间。可永久有效的权益必须显式使用 `permanent=true`，不能省略时间。 |
| `linked_object_ids` | 与权益相关的 WorldObject，例如钥匙或凭证。 |
| `source_event_id` | 产生权益的 EventLog。 |
| `state` | 当前是否有效、是否已消耗。 |

P0 `entitlement_type` 闭集：

```text
legal_bed_for_tonight
room_access
entry_permission
trade_access
water_access
stable_space
protection_status
service_credit
rumor_access
medical_care_claim
```

规则：

```text
ServiceEntitlementState 必须由 resolver 创建，AI proposal 不能直接创建。
ServiceEntitlementState.source_event_id 必须引用存在 EventLog。
权益授予如果伴随钥匙、通行牌或票据，必须额外创建或更新 WorldObject。
过期权益不能继续满足 ServiceState.requirements。
```

## LawPolicy

`LawPolicy` 表示聚落当前制度规则。P0 只做轻量规则，不做完整法律系统。

示例：

```json
{
  "law_policy_id": "graystone_curfew_policy",
  "settlement_id": "graystone_town",
  "policy_type": "curfew",
  "severity": "strict",
  "active_time_band": ["night"],
  "affected_groups": ["outsiders", "unknown_visitors"],
  "enforced_by_group_id": "graystone_guards",
  "effects": ["street_action_restricted", "guard_questioning_increased"],
  "state": {
    "active": true
  }
}
```

P0 `policy_type` 闭集：

```text
curfew
outsider_tax
checkpoint
weapon_restriction
market_rule
lodging_registry
religious_taboo
quarantine
```

P0 `severity` 闭集：

```text
none
light
normal
strict
emergency
```

P0 `policy.effects` 闭集：

```text
street_action_restricted
guard_questioning_increased
price_markup_allowed
service_requires_identity
weapon_carry_risk_up
trade_access_restricted
lodging_requires_registry
rumor_spread_up
```

## EconomyState

`EconomyState` 表示聚落的轻量经济环境。P0 不做供需曲线，只提供服务价格修正和资源压力。

示例：

```json
{
  "economy_state_id": "graystone_economy",
  "settlement_id": "graystone_town",
  "currency_standard": "copper_silver_gold",
  "price_level": {
    "food": "normal",
    "lodging": "expensive",
    "water": "normal",
    "repair": "normal"
  },
  "scarcity": {
    "food": "medium",
    "water": "low",
    "safe_bed": "high",
    "tools": "medium"
  },
  "social_markup_rules": [
    {
      "condition": "outsider_policy=suspicious_taxed",
      "service_type": "lodging",
      "modifier": "markup_minor"
    }
  ]
}
```

P0 `price_level` 闭集：

```text
cheap
normal
expensive
scarce
unavailable
```

P0 `scarcity` 闭集：

```text
none
low
medium
high
critical
```

P0 `modifier` 闭集：

```text
discount_minor
discount_major
markup_minor
markup_major
refuse_service
require_barter
```

## SocialPressureState

`SocialPressureState` 表示聚落当前社会压力。它可以由初始生成、EventLog、AI proposal 经 resolver 或玩家行为产生变化。

示例：

```json
{
  "pressure_state_id": "graystone_social_pressure",
  "settlement_id": "graystone_town",
  "pressure": {
    "curfew": 0.8,
    "outsider_suspicion": 0.6,
    "fear_of_monsters": 0.7,
    "resource_scarcity": 0.4,
    "guard_attention": 0.5
  },
  "active_rumor_ids": [],
  "active_patrol_level": "normal",
  "state_revision": 1
}
```

P0 `pressure` 数值键闭集：

```text
curfew
outsider_suspicion
fear_of_monsters
resource_scarcity
guard_attention
local_trust
rumor_heat
```

P0 `active_patrol_level` 闭集：

```text
none
low
normal
high
lockdown
```

## 生成规则

### SettlementProfileFormation

输入：

```text
Settlement chunk_ids
Region climate_profile
WorldChunk terrain / water_presence
road / trade_route / civilization_pressure
ResourceDeposit / ResourceNode
danger_pressure / abnormal_pressure
nearby Site
```

输出：

```text
SettlementProfile
```

规则：

```text
settlement_type 必须能由 chunk 数量、道路、水源、文明压力和 Site 支持。
economy_basis 必须能由道路、资源、生态或机构支持。
law_profile 必须能由治理、危险压力或文明压力支持。
outsider_policy 必须能由 law_profile、danger_pressure、social pressure 或 history 支持。
```

### InstitutionFormation

输入：

```text
SettlementProfile
Site
road / trade_route
resource_pressure
economy_basis
law_profile
```

输出：

```text
Institution
```

规则：

```text
inn 必须有 road_service、inn_trade、market_town、frontier_town 或 roadside_stop 支持。
guard_post 必须有 curfew、checkpoint、security pressure、fortified_post 或 military_order 支持。
blacksmith 必须有 ore_trade、road_service、craftspeople 或 mining_camp 支持。
well_house 必须有 well_water、水源 Site 或水资源压力支持。
```

### SocialGroupFormation

输入：

```text
SettlementProfile
Institution
economy_basis
law_profile
outsider_policy
resource_pressure
```

输出：

```text
SocialGroupState
```

规则：

```text
每个 P0 聚落至少生成 2 个 SocialGroupState。
frontier_town 至少应有 local_residents 和 guards 或 merchants。
inn 存在时可以生成 innkeepers 或 travelers。
road_service 或 market_town 存在时可以生成 merchants / travelers。
outsider_policy 为 suspicious_taxed 或 restricted 时，至少一个群体必须包含 outsider_control 或 security 核心利益。
```

### NamedNPCFormation

输入：

```text
Institution
SocialGroupState
Institution.services 中声明的服务提供者需求
Site / LocationNode
```

输出：

```text
NamedNPCState
```

规则：

```text
每个提供 P0 服务的 Institution 至少有一个 operator NPC，或明确由群体代理提供。
提供 lodging / food 的 inn 必须有 innkeeper 或等价 provider。
guard_post 必须有 guard 或 gatekeeper。
NPC.current_location 必须能解析到其 home_site_id 内部或所属 settlement chunk。
```

`NamedNPCFormation` 读取的是 `Institution.services`，不是尚未生成的 `ServiceState`。它负责确定“谁能提供这些服务”；后续 `ServiceFormation` 再把机构、提供者、政策、经济和压力组合成具体服务状态。

### ServiceFormation

输入：

```text
Institution
NamedNPCState
EconomyState
LawPolicy
SocialPressureState
```

输出：

```text
ServiceState
```

规则：

```text
ServiceState.provider_npc_id 必须引用存在 NPC，除非 service_type 明确允许 unattended。
base_price 必须使用 currency + amount，不能写在 description。
availability 必须由 Institution.status、LawPolicy、stock 或 pressure 支持。
grants 必须属于闭集，并由对应 resolver 映射到权威状态变化。
```

### PolicyAndPressureFormation

输入：

```text
SettlementProfile
danger_pressure
abnormal_pressure
resource_pressure
SocialGroupState
recent world generation facts
```

输出：

```text
LawPolicy
EconomyState
SocialPressureState
```

规则：

```text
curfew_strict 必须生成 curfew LawPolicy。
suspicious_taxed 必须允许 price markup 或 service requirement，但不直接改价格。
high security pressure 必须提高 guard_attention 或 active_patrol_level。
high lodging pressure 必须影响 lodging price_level 或 availability。
```

## 与 AI 社会心智的关系

AI 调度器和 `AgentObservationBuilder` 可以读取以下权威状态，用于构建主体可知快照：

```text
SettlementProfile
SocialGroupState
NamedNPCState
ServiceState
ServiceEntitlementState
LawPolicy
EconomyState
SocialPressureState
主体对应的 KnowledgeState / RumorState / SecretState
已提交 EventLog
```

LLM 本身不得直接读取以上对象或 EventLog。LLM 唯一输入是 [AI 社会心智规则](../04-ai-simulation/ai-social-mind-rules.md) 定义的 `AgentObservationSnapshot`；快照只能投影主体已知内容、允许动作和可引用目标。

AI 输出：

```text
GroupDecisionProposal
NPCActionProposal
```

AI 不能直接写：

```text
SettlementProfile
Institution
SocialGroupState
NamedNPCState
ServiceState
LawPolicy
EconomyState
SocialPressureState
WorldObject
EventLog
```

proposal 必须通过 validator 和 resolver，才可以产生权威变化。示例映射：

| AI proposal 类型 | Resolver 可写目标 |
| --- | --- |
| `spread_rumor` | SocialActionResolver 形成 RumorSpreadRequested StateTransition；KnowledgePropagation 形成 RumorState StateTransition；SocialRumorIndexReducer 形成 SocialPressureState.active_rumor_ids StateTransition；事件统一由 StateTransitionCommitter 生成 |
| `adjust_social_pressure` | SocialPressureState.pressure 中指定键；delta 由规则映射并受单次/每日上限约束，事件由 StateTransitionCommitter 生成 |
| `request_patrol_change` | SocialPressureState.active_patrol_level；每次最多移动一级，事件由 StateTransitionCommitter 生成 |
| `change_group_attitude` | SocialGroupState.attitude_to_player；必须经过 AttitudeTransitionRegistry，事件由 StateTransitionCommitter 生成 |
| `offer_service` | 确定性服务报价、可选 ProposalResourceReservation；不能直接扣款或授予权益，事件由 StateTransitionCommitter 生成 |
| `refuse_service` | 单次服务请求结果，不直接永久关闭 ServiceState |
| `reveal_known_fact` | KnowledgePropagation 输入；不能直接创建 KnowledgeState，事件由 StateTransitionCommitter 生成 |
| `withhold_known_fact` | 单次交互结果；不能删除或修改主体已有 KnowledgeState，事件由 StateTransitionCommitter 生成 |
| `change_npc_attitude` | NamedNPCState.attitude_to_player；必须经过 AttitudeTransitionRegistry，事件由 StateTransitionCommitter 生成 |

P0 不接受 `offer_trade`、`raise_price`、`increase_patrol`、`change_attitude` 等含义重叠的旧名称。交易统一使用 `offer_service(service_type=trade)`，报价由 `offer_service.requested_price_modifier` 表达，巡逻和态度分别使用表中的明确 action_type。

AI proposal 只提出语义行动，不直接提供货币 delta、权益、钥匙、库存扣减或最终压力值。对应状态必须由 `SocialActionResolver`、交易 resolver、权益 resolver 或 `KnowledgePropagation` 按各自 WriteACL 修改。

`SocialRumorIndexReducer` 是 `SocialPressureState.active_rumor_ids` 的唯一运行时写者。它只读取已提交的 `RumorState` 和知识领域 EventLog，按 rumor 的 scope、active/expired 状态增加或移除 ID，并在同一事务增加 `SocialPressureState.state_revision`。AI、KnowledgePropagation 和 SocialActionResolver 都不能直接写 `active_rumor_ids`。

## 与地点/空间规则的关系

规则：

```text
SettlementProfile.settlement_id 必须引用 Settlement.id。
Institution.site_id 必须引用存在 Site。
NamedNPCState.current_location 必须使用地点/空间规则的 actor location。
ServiceState 不能提供不在同一 Settlement 或其关联 Institution 中的服务。
SocialGroupState.home_chunk_ids 必须落在 settlement chunk_ids 内或声明跨聚落关系。
```

Projection 可以读取社会状态，将其转成 UI/DM 可见信息：

```text
当前聚落名
当前区域是否宵禁
附近可交互 NPC
可购买服务
服务价格
群体态度可感知线索
守卫盘问风险
流言或社会压力迹象
```

Projection 不能写社会状态。

## 与经济和权益的关系

P0 只定义服务和价格的社会来源，不定义完整交易系统。

实现时至少需要 resolver 支持：

```text
ServiceRequestResolver
EconomyResolver
EntitlementResolver
```

成功交易必须形成原子状态变化：

```text
玩家失去货币
服务提供者或机构获得货币，或至少写入交易事件
玩家获得 grants 中声明的权益或对象
权益必须写入 ServiceEntitlementState，物品必须写入 WorldObject
NPC / 群体态度可按规则变化
EventLog 记录完整变化
```

禁止：

```text
DM 文本写“你得到了钥匙”但没有 WorldObject 或 entitlement 状态。
AI proposal 直接扣钱或发钥匙。
价格只写在 NPC 台词里。
服务成功但 ServiceState / EventLog 没有记录。
权益过期后仍被当作有效。
```

## Validator 规则

必须增加 `SettlementSocialWorldValidator`，保证：

1. `SettlementProfile.settlement_id` 引用存在的 `Settlement`。
2. `SettlementProfile.chunk_ids` 必须和 `Settlement.chunk_ids` 一致或为其子集。
3. `settlement_type`、`population_band`、`economy_basis`、`governance`、`law_profile`、`outsider_policy` 必须属于闭集。
4. `Institution.settlement_id` 引用存在 `SettlementProfile`。
5. 提供服务的 `Institution.site_id` 必须引用存在 `Site`。
6. `Institution.controlled_by_group_id` 如果存在，必须引用同 settlement 的 `SocialGroupState`。
7. `SocialGroupState.home_chunk_ids` 必须落在聚落 chunk 内，除非字段明确声明跨聚落。
8. `SocialGroupState.pressure` 只能使用 P0 pressure 数值键，数值必须在 0.0 到 1.0。
9. `NamedNPCState.group_id` 必须引用存在 SocialGroupState。
10. `NamedNPCState.current_location` 必须能解析到合法 chunk、Site、LocationNode 或 Zone。
11. `NamedNPCState.institution_ids` 必须引用存在 Institution。
12. `ServiceState.institution_id` 必须引用存在 Institution。
13. `ServiceState.provider_npc_id` 必须引用存在 NamedNPCState，除非该服务允许 unattended。
14. `ServiceState.base_price.amount` 必须为非负整数。
15. `ServiceState.requirements`、`grants`、`risk_modifiers` 必须属于闭集。
16. `ServiceEntitlementState.service_id` 必须引用存在 ServiceState。
17. `ServiceEntitlementState.source_event_id` 必须引用存在 EventLog。
18. `ServiceEntitlementState.valid_until` 必须晚于 `valid_from`，除非显式永久有效。
19. `ServiceEntitlementState.linked_object_ids` 如果存在，必须引用存在 WorldObject。
20. `LawPolicy.settlement_id` 必须引用存在 SettlementProfile。
21. `EconomyState.social_markup_rules` 不能直接改 ServiceState.base_price，只能作为 resolver 输入。
22. `SocialPressureState.pressure` 只能使用 P0 pressure 数值键，数值必须在 0.0 到 1.0。
23. AI proposal 不能直接写任何本文件定义的权威状态。
24. 所有社会状态变化必须通过 StateTransition 提交，并由 StateTransitionCommitter 生成 EventLog。
25. 初始 NamedNPCFormation 不能读取 ServiceState；服务需求只能来自已形成的 Institution.services。
26. 初始 ServiceFormation 必须在 PolicyAndPressureFormation 与 NamedNPCFormation 完成后运行。
27. SettlementSocialFormation 的子阶段结果必须作为同一个待校验输出批次处理；Institution.operator_npc_ids 回填和全部引用校验完成前，不得提交部分社会实体。

## 推荐生成顺序

聚落社会生成应在基础空间和 Site 形成之后运行。下列子阶段构成 `SettlementSocialFormation` 内部 DAG；在第 11 步通过前，它们都是同一待校验输出批次，不是可供其他阶段读取的部分权威状态：

```text
1. Settlement 已由地点/空间规则生成。
2. Site / LocationNode / Zone 已生成，至少包含聚落核心服务地点。
3. OriginEventCandidate 可以作为社会压力、外乡人政策、服务价格和传闻权重输入；权威 OriginEvent 不要求在本阶段已经提交。
4. SettlementProfileFormation 生成 SettlementProfile。
5. InstitutionFormation 生成 Institution 草案；services 已确定，operator_npc_ids 暂为空。
6. SocialGroupFormation 生成 SocialGroupState。
7. PolicyAndPressureFormation 生成 LawPolicy / EconomyState / SocialPressureState。
8. NamedNPCFormation 读取 Institution.services，生成 NamedNPCState，并回填 Institution.operator_npc_ids。
9. ServiceFormation 读取 Institution、NamedNPCState、LawPolicy、EconomyState 和 SocialPressureState，生成 ServiceState。
10. SettlementSocialWorldValidator 校验所有引用、闭集和完整 post-state。
11. 同一 StateTransitionBatch 写入全部社会实体，并由 StateTransitionCommitter 生成对应 EventLog；任一引用失败则整批回滚。
12. 初始 Snapshot 覆盖社会状态。
```

聚落社会生成中涉及候选选择、群体组合、服务提供者或价格倾向的随机，都必须使用确定性随机协议，并在对应 `GeneratorOutputEnvelope.random_draw_refs` 中记录。

如果 Site 尚未完全物化，生成器不能输出权威 `Institution`。必须先完成对应 Site 物化，或延后该机构生成阶段。

## P0 示例：灰石镇与旧炉旅店

生成结果应至少能表达：

```text
灰石镇是 frontier_town。
经济基础包含 hunting、ore_trade、road_service。
治理结构是 guard_council。
宵禁严格。
外乡人政策是 suspicious_taxed。
旧炉旅店是 inn Institution。
店主是 innkeeper NamedNPC。
旧炉旅店提供 food、lodging、rumor 服务。
住宿基础价格为 3 copper。
lodging 成功 grants 包含 legal_bed_for_tonight 和 room_key。
守卫或本地居民群体对外乡人保持 unknown_suspicious。
社会压力包含 curfew、outsider_suspicion、fear_of_monsters。
```

这能支撑以下玩法：

```text
进入灰石镇。
进入旧炉旅店。
和店主讨价还价。
修锅换取低价住宿。
支付铜币。
获得钥匙和今晚合法床位。
夜里因宵禁减少街道行动自由。
第二天通过旅店线索追踪暗夜狼。
```

## 测试清单

```text
test_settlement_profile_requires_existing_settlement
test_settlement_profile_chunk_ids_must_match_settlement
test_institution_service_requires_site
test_social_group_pressure_keys_are_closed
test_social_group_pressure_values_are_0_to_1
test_named_npc_location_must_resolve
test_named_npc_requires_group
test_service_requires_provider_or_unattended_rule
test_named_npc_formation_reads_institution_services_not_service_state
test_service_formation_waits_for_policy_pressure_and_named_npc
test_settlement_social_batch_rejects_partial_institution_npc_commit
test_service_price_must_be_structured_currency
test_service_grants_must_be_closed_set
test_service_success_creates_entitlement_state
test_entitlement_requires_source_event
test_expired_entitlement_cannot_satisfy_requirement
test_curfew_strict_generates_law_policy
test_suspicious_taxed_allows_markup_but_does_not_directly_change_price
test_ai_proposal_cannot_write_social_world_state_directly
test_service_success_writes_money_loss_grant_and_event_log_atomically
test_projection_can_read_but_not_write_social_state
```

## 已确认决策

1. 聚落社会世界是 `WorldState` 的一部分，不是 AI 文本记忆。
2. `Settlement` 仍属于空间模型；`SettlementProfile` 才表达社会画像。
3. 普通人群优先使用 `SocialGroupState`，不逐个生成 NPC。
4. 关键服务和交互人物使用 `NamedNPCState`。
5. 服务、价格、权益、态度、压力必须有权威状态或 EventLog。
6. 服务授予的轻量权益使用 `ServiceEntitlementState`，实体凭证仍使用 `WorldObject`。
7. AI 只能读取社会状态并提出 proposal，不能直接修改社会状态。
8. P0 不做完整政治经济模拟，只做足够支撑聚落试玩的一阶社会后果。
