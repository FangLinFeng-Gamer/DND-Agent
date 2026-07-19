---
doc_id: isekai.world_origin_history_rules
status: active
layer: world-model
owner: architecture
created_at: 2026-07-13
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.location_space_rules
  - isekai.climate_terrain_formation_rules
  - isekai.natural_ecology_rules
  - isekai.world_object_rules
  - isekai.world_knowledge_rules
provides:
  - OriginEvent
  - OriginMetadata
  - OriginEvidence
  - OriginEventCandidate
  - OriginHistoryCandidateFormation
  - OriginHistoryMaterialization
  - OriginHistoryValidator
---

# 异世界模式历史来历与世界痕迹规则设计

## 背景

现有文档已经多次使用“历史事件”“事故”“废弃”“遗迹”“污染”“魔物痕迹”等概念，但这些概念目前大多只是生成条件或说明文本：

```text
废弃马车需要事故或历史事件。
遗迹需要 history event、abnormal 或 abandoned 标签。
corpse_remain 需要战斗、捕食或历史事件支持。
历史来源过去只作为说明字段存在。
```

这会导致一个问题：世界里出现了废弃马车、断轮、血迹、散落货袋、尸骸、异常水源和旅店传闻，但系统无法确定它们是否来自同一件事，也无法校验这些痕迹是否互相支持。

本设计将“历史来历”从解释性文本升级成轻量静态世界事实。它不做完整历史模拟，不按年表推演战争、人口和经济，只为世界生成提供可验证的因果痕迹。

## 目标

- 定义 `OriginEvent`，表达世界中静态历史来源。
- 定义 `OriginMetadata`，让 Site、WorldObject、HazardSource、ObstacleSource、ResourceDeposit、FloraPatch、CreatureGroup、SettlementProfile 等实体能追溯来源。
- 定义 `OriginEvidence` 规则，要求来源必须有可见或可发现证据。
- 让废弃马车、遗迹、尸骸、异常污染、猎人小屋、旧旅店、守卫巡逻和资源开发都能有合法来源。
- 让资源、生态、SitePlacement、WorldObject、危险和社会状态可以消费历史来历，但不能手填历史标签。
- 保持 P0 轻量，不实现完整历史年表和动态历史模拟。

## 非目标

- 不模拟完整王朝、战争、人口迁移和多代家族史。
- 不按每一年推进历史。
- 不生成所有历史人物。
- 不让 LLM 或 DM 文本直接创建最终历史事实。
- 不用 `origin.notes` 替代权威字段。
- 不要求每颗石子、每片叶子都有历史来源。
- 不把玩家游玩后的 EventLog 混同为静态历史来历。

## 核心原则

### 1. OriginEvent 是静态世界事实

`OriginEvent` 表示世界生成之前已经发生、并在当前世界留下痕迹的事件。它不是运行时 `EventLog`。

```text
OriginEvent：这个地点为什么变成现在这样。
EventLog：当前存档从生成开始之后发生过什么状态变化。
```

世界生成创建 `OriginEvent` 时，仍必须写生成阶段 EventLog，但二者语义不同。

### 2. 历史必须留下证据

一个历史来源如果影响当前可玩世界，必须至少留下一种证据：

```text
Site
WorldObject
HazardSource
ObstacleSource
ResourceDeposit
FloraPatch
CreatureGroup
SocialGroupState
SettlementProfile
Clue-like WorldObject
```

没有证据的纯背景故事不能进入 P0 权威 WorldState。

### 3. 证据必须反向引用来源

如果 `OriginEvent` 声明产生了废弃马车、血迹和断轮，这些实体也必须通过 `OriginMetadata.origin_event_ids` 反向引用该事件。Validator 必须检查双向一致。

### 4. 历史只解释静态初始状态

P0 历史来历只解释世界初始状态，例如遗迹为什么存在、马车为什么侧翻、水源为什么污染。玩家行动之后产生的新变化必须走 EventLog，不写成新的静态历史。

### 5. AI 可以提候选，不能定事实

AI 可以提出 `OriginEventCandidate`，用于丰富世界来历。但候选必须通过 `OriginHistoryValidator`，并由确定性生成器物化为 `OriginEvent` 后才能进入 WorldState。

### 6. 历史事实不等于公共知识

`OriginEvent` 只表示世界里确实发生过什么，不表示玩家、NPC 或社会群体知道它。谁知道、知道多少、是否误解、是否愿意说，必须由运行时层 `KnowledgeState`、`RumorState`、`SecretState` 和 `DiscoveryState` 表达。

```text
OriginEvent 存在：世界真相存在。
OriginMetadata 存在：当前实体可以证明或体现该真相。
KnowledgeState 存在：某个主体知道、误解或听说该真相。
```

## 总体模型

```text
WorldGenerationParameters
-> terrain / hydrology / biome / resources / settlement / danger pressure
-> OriginHistoryFormation
-> OriginEvent
-> Site / WorldObject / Ecology / Hazard / Obstacle / SettlementSocialWorld
-> OriginMetadata attachment
-> OriginHistoryValidator
-> EventLog
-> WorldSnapshot
```

## OriginEvent

`OriginEvent` 是静态历史来源实体。它表达“发生了什么”“发生在哪”“有多旧”“为什么当前世界会留下这些实体”。

最小 schema：

```json
{
  "origin_event_id": "origin_abandoned_cart_001",
  "world_id": "isekai_world_001",
  "region_id": "north_slope_wilds",
  "scope": {
    "kind": "chunk_cluster",
    "chunk_ids": ["chunk_north_slope_12_08_00"]
  },
  "origin_type": "accident_site",
  "age_band": "recent",
  "cause_tags": ["mudslide", "trade_route", "ambush_suspected"],
  "severity": "medium",
  "participants": [
    {
      "kind": "social_group",
      "ref_id": "graystone_merchants",
      "role": "victim"
    },
    {
      "kind": "creature_species",
      "ref_id": "wolf",
      "role": "scavenger"
    }
  ],
  "expected_outputs": [
    {
      "entity_type": "Site",
      "role": "primary_site"
    },
    {
      "entity_type": "WorldObject",
      "role": "evidence"
    },
    {
      "entity_type": "HazardSource",
      "role": "risk"
    }
  ],
  "evidence_entity_ids": [
    "site_abandoned_cart_001",
    "object_broken_wheel_001",
    "object_dried_blood_001"
  ],
  "generated_by": {
    "system": "OriginHistoryFormation",
    "rule_id": "origin.accident_site_from_trade_route_and_danger"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `origin_event_id` | 静态历史来源 ID。 |
| `world_id` | 所属 World。 |
| `region_id` | 所属 Region。 |
| `scope` | 来源影响的空间范围。 |
| `origin_type` | 来源类型闭集。 |
| `age_band` | 来源新旧程度。 |
| `cause_tags` | 来源原因标签，必须来自 origin cause registry。 |
| `severity` | 来源影响强度。 |
| `participants` | 参与者引用，可以是社会群体、物种、机构、未知主体或异常力量。 |
| `expected_outputs` | 该来源应该产生或支持的实体类型与角色。 |
| `evidence_entity_ids` | 当前世界中支撑该来源的证据实体。 |
| `generated_by` | 生成系统和规则来源。 |

P0 `scope.kind` 闭集：

```text
region
chunk
chunk_cluster
site
location_node
zone
object
```

P0 `origin_type` 闭集：

```text
natural_formation
settlement_foundation
road_trade_activity
resource_discovery
resource_extraction
hunter_activity
guard_or_patrol_activity
inn_or_service_history
accident_site
abandoned_camp
abandoned_vehicle
predator_kill_site
monster_attack_trace
battle_or_skirmish
fire_damage
flood_or_mudslide
structural_collapse
ruin_decay
ritual_failure
abnormal_contamination
burial_or_corpse_site
plague_or_sickness
crime_scene
```

P0 `age_band` 闭集：

```text
fresh
recent
old
ancient
timeless
```

P0 `severity` 闭集：

```text
trace
minor
medium
major
catastrophic
```

P0 `participant.kind` 闭集：

```text
social_group
named_npc
institution
creature_species
creature_group
settlement
unknown_actor
abnormal_force
natural_force
```

P0 `participant.role` 闭集：

```text
founder
builder
resident
victim
attacker
scavenger
witness
owner
abandoner
polluter
discoverer
extractor
protector
unknown
```

P0 `expected_outputs.role` 闭集：

```text
primary_site
supporting_site
evidence
resource
hazard
obstacle
ecology_change
social_state
clue
```

## OriginMetadata

`OriginMetadata` 是挂在当前实体上的轻量来源链接。它不替代 `OriginEvent`，只说明该实体在来源事件中的角色。

最小 schema：

```json
{
  "origin": {
    "origin_event_ids": ["origin_abandoned_cart_001"],
    "origin_role": "evidence",
    "age_band": "recent",
    "visible_as_evidence": true,
    "discovery_state": "hinted",
    "notes": "断轮和血迹共同指向一次商路事故"
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `origin.origin_event_ids` | 引用的 OriginEvent 列表。 |
| `origin.origin_role` | 当前实体在来源中的角色。 |
| `origin.age_band` | 当前实体表现出的新旧程度，必须与 OriginEvent.age_band 相容。 |
| `origin.visible_as_evidence` | 该实体是否可作为玩家可发现证据。 |
| `origin.discovery_state` | 玩家当前发现状态。 |
| `origin.notes` | 调试或展示说明，不能驱动规则。 |

P0 `origin_role` 闭集：

```text
cause
result
evidence
remnant
owner_mark
victim_mark
hazard_source
obstacle_source
resource_trace
social_trace
clue
```

P0 `discovery_state` 闭集：

```text
unknown
hinted
visible
identified
misidentified
hidden
```

允许携带 `OriginMetadata` 的 P0 实体：

```text
Site
LocationNode
Zone
WorldObject
HazardSource
ObstacleSource
ResourceDeposit
ResourceNode
FloraPatch
CreatureGroup
SettlementProfile
Institution
SocialGroupState
NamedNPCState
ServiceState
```

## OriginEvidence

`OriginEvidence` 不是必须单独落库的实体，而是一组 validator 规则。它定义某类 `OriginEvent` 至少需要哪些证据。

P0 最小证据规则：

| origin_type | 必要空间条件 | 最少证据 | 合法输出示例 |
| --- | --- | --- | --- |
| `settlement_foundation` | settlement chunk | 1 个 SettlementProfile 或 Institution | 聚落画像、老井、祠堂、市场 |
| `road_trade_activity` | road 或 trade_route | 1 个 Site 或 Institution | 旅店、马厩、货栈、路标 |
| `resource_discovery` | 对应资源存在 | 1 个 ResourceDeposit 或 Institution | 矿点、采集点、矿工营地 |
| `resource_extraction` | 资源点或矿脉 | 1 个 ResourceDeposit + 1 个痕迹对象或 Site | 矿坑、木支架、矿渣 |
| `hunter_activity` | forest/ridge/prey 支持 | 1 个 Site 或 WorldObject | 猎人小屋、捕兽夹、剥皮架 |
| `guard_or_patrol_activity` | settlement/law/security 支持 | 1 个 Institution 或 SocialGroupState | 卫所、路卡、巡逻路线 |
| `inn_or_service_history` | road_service/settlement 支持 | 1 个 Institution + 1 个 ServiceState | 旅店、床位、柜台 |
| `accident_site` | road/slope/water/danger 支持 | 2 个证据 | 废弃马车、断轮、血迹、散落货袋 |
| `abandoned_vehicle` | road/trade_route 支持 | 1 个 Site + 1 个对象 | 侧翻马车、破箱、车辙 |
| `abandoned_camp` | shelter/firewood/road/wild 支持 | 2 个证据 | 灰烬、破毯、营地 |
| `predator_kill_site` | predator 或 scavenger 支持 | 1 个尸骸/骨堆 + 1 个生物痕迹 | 骨堆、爪痕、狼群气味 |
| `monster_attack_trace` | abnormal/danger 支持 | 2 个证据 | 异常爪痕、腐化血迹、恐慌流言 |
| `battle_or_skirmish` | social/guard/road/ruin 支持 | 2 个证据 | 断矛、血迹、遗体、烧焦墙 |
| `fire_damage` | combustible/object/structure 支持 | 1 个烧毁痕迹 | 焦木、灰烬、烧塌屋顶 |
| `flood_or_mudslide` | water/slope/heavy_rain history 支持 | 1 个地形/障碍证据 | 淤泥、塌方、堵路 |
| `structural_collapse` | ruin/cave/unstable structure 支持 | 1 个障碍或危险 | 塌墙、坍塌地板、落石 |
| `ruin_decay` | ruin/abandoned/ancient 支持 | 2 个证据 | 断柱、残墙、旧符文 |
| `ritual_failure` | temple/ruin/abnormal 支持 | 2 个证据 | 仪式圈、异常雾、低语石 |
| `abnormal_contamination` | abnormal_pressure 支持 | 1 个异常资源或危险 | 蓝盐、黑血结晶、异常水源 |
| `burial_or_corpse_site` | corpse_remain/battle/predator 支持 | 1 个尸骸或墓标 | 坟堆、骨堆、腐肉 |
| `plague_or_sickness` | settlement/corpse/water 支持 | 2 个证据 | 封门标记、污染水、病床 |
| `crime_scene` | settlement/road/service 支持 | 2 个证据 | 血迹、破锁、缺失货物 |

规则：

```text
证据必须是权威实体，不能只是 description 文本。
证据实体必须反向引用对应 OriginEvent。
同一个证据可以支持多个 OriginEvent，但必须声明不同 origin_role。
origin.notes 不能计入证据数量。
```

## 生成规则

### OriginHistoryCandidateFormation

输入：

```text
WorldGenerationParameters.default_history_years
Region climate_profile
WorldChunk terrain / water / slope / road / civilization_pressure / danger_pressure / abnormal_pressure
RegionFeature / Settlement / TerrainFeature 空间锚点
resource_pressure / ecology_pressure / prey_pressure
```

输出：

```text
OriginEventCandidate
```

规则：

```text
default_history_years 只影响来源新旧和候选权重，不表示逐年模拟。
road + trade_route + danger_pressure 可以产生 accident_site / abandoned_vehicle。
ruin + abnormal_pressure 可以产生 ritual_failure / abnormal_contamination。
settlement anchor + road_service 可以产生 inn_or_service_history。
forest + prey_pressure + danger_pressure 可以产生 predator_kill_site。
resource_pressure + civilization_pressure 可以产生 resource_discovery / resource_extraction。
settlement anchor + civilization_pressure/danger_pressure 可以产生 guard_or_patrol_activity 候选；后续 SettlementSocialFormation 再决定具体 law_profile、LawPolicy 和巡逻压力。
```

`OriginHistoryCandidateFormation` 发生在聚落社会状态之前，不能读取 `SettlementProfile`、`LawPolicy`、`EconomyState`、`SocialPressureState`、`NamedNPCState` 或 `ServiceState`。否则历史候选与社会形成会构成依赖环。

`OriginEventCandidate` 只影响后续 ResourceFormation、EcologyFormation、SitePlacement、ObjectMaterialization 和 SettlementSocialFormation 的候选权重。它不是权威历史事实，不能进入运行时 resolver、AI 输入或 UI 投影。

`OriginEventCandidate` 的候选选择必须使用确定性随机协议。每个候选集合必须有稳定 `candidate_id`、整数 `weight_uint`、`candidate_set_hash` 和 `RandomDrawRef`。validator 拒绝某个候选不能触发全局重抽。

### OriginHistoryMaterialization

输入：

```text
OriginEventCandidate
已物化的 Site / LocationNode / WorldObject / Resource / Ecology / Hazard / Obstacle / Social entities
```

输出：

```text
OriginEvent
OriginMetadata attachment plan
```

规则：

```text
只有当候选声明的最小证据实体已经物化，并且证据位置落在 OriginEvent.scope 内时，才能提交权威 OriginEvent。
不能为了提交 OriginEvent 临时创建未经过对应生成器和 validator 的证据实体。
OriginEventMaterialization 必须输出待附着 OriginMetadata 的实体列表。
```

### OriginAttachment

输入：

```text
OriginEvent
已物化的 Site / WorldObject / Resource / Ecology / Hazard / Obstacle / Social entities
```

输出：

```text
OriginMetadata
```

规则：

```text
被 OriginEvent.expected_outputs 声明的输出实体，必须携带 OriginMetadata。
OriginMetadata.origin_event_ids 必须引用存在 OriginEvent。
OriginMetadata.discovery_state 只表示玩家对证据的发现状态，不决定来源是否真实。
```

### OriginEvidenceValidation

输入：

```text
OriginEvent
OriginMetadata
所有 evidence_entity_ids
```

输出：

```text
validator pass/fail
```

规则：

```text
每个 OriginEvent 必须满足 origin_type 对应最小证据数量。
每个 evidence_entity_id 必须引用存在实体。
每个证据实体必须反向引用该 OriginEvent。
OriginEvent.scope 必须覆盖所有 evidence entity 的位置。
```

## 与其他系统的关系

### 与 SitePlacement

历史来历可以支持 Site 的出现，但不能绕过空间规则。

```text
abandoned_vehicle 可以支持废弃马车 Site。
ruin_decay 可以支持遗迹 Site。
hunter_activity 可以支持猎人小屋 Site。
inn_or_service_history 可以支持旧旅店 Site。
```

所有 Site 仍必须满足：

```text
Site.parent_chunk_id 存在。
Site 所在 chunk 容量规则通过。
Site 入口和 LocationNode 合法。
```

### 与 ResourceFormation

历史来历可以支持资源和异常资源，但不能凭空生成违反地形条件的资源。

```text
resource_extraction 支持矿坑、矿渣和废弃支架。
abnormal_contamination 支持蓝盐、黑血结晶和污染水源。
burial_or_corpse_site 支持 corpse_remain 类资源。
```

### 与 Ecology

历史来历可以支持异常生态、尸骸生态和捕食痕迹。

```text
predator_kill_site 支持 scavenger、wolf signs、bone_pile。
monster_attack_trace 支持 abnormal_beast 活动痕迹。
abnormal_contamination 支持 abnormal_flora。
```

### 与 WorldObject

历史证据优先用 `WorldObject` 表达。

```text
断轮、血迹、旧旗帜、破锁、符文石、烧焦木梁、散落货袋都应该是 WorldObject 或 clue-like object。
```

对象的描述可以写得丰富，但 resolver 和 validator 只能使用 `object_type`、components、tags、placement 和 `OriginMetadata`。

### 与 HazardSource / ObstacleSource

历史来历可以解释危险和障碍来源。

```text
flood_or_mudslide -> ObstacleSource(blocked_path/deep_mud)
structural_collapse -> HazardSource(collapse_risk) + ObstacleSource(collapsed_wall)
abnormal_contamination -> HazardSource(poison_risk / low_visibility_risk)
```

危险和障碍仍必须满足静态世界运行规则中的允许映射表。

### 与 Settlement Social World

历史来历可以支持聚落制度、群体恐惧和服务来源。

```text
settlement_foundation 支持 SettlementProfile。
road_trade_activity 支持旅店、马厩、货栈。
monster_attack_trace 支持 fear_of_monsters 和宵禁压力。
guard_or_patrol_activity 支持 Guard group、checkpoint 和 curfew。
```

AI 社会心智可以读取历史来历摘要，但不能直接新增或修改 OriginEvent。

AI 社会心智只能读取主体可知的历史来历摘要。若某 NPC 或群体没有对应 `KnowledgeState`，`AgentObservationSnapshot` 不能向 AI 暴露该 `OriginEvent`。

## Validator 规则

必须增加 `OriginHistoryValidator`，保证：

1. `OriginEvent.origin_event_id` 唯一。
2. `OriginEvent.origin_type`、`age_band`、`severity` 必须属于闭集。
3. `OriginEvent.scope` 必须引用存在空间。
4. `OriginEvent.cause_tags` 必须来自 origin cause registry。
5. `OriginEvent.participants[].kind` 和 `role` 必须属于闭集。
6. `participants[].ref_id` 如果不是 `unknown_actor` 或 `abnormal_force`，必须能解析到对应实体或 catalog。
7. `OriginEvent.expected_outputs[].entity_type` 必须属于允许实体类型。
8. `OriginEvent.evidence_entity_ids` 必须引用存在实体。
9. 每个证据实体必须通过 `OriginMetadata.origin_event_ids` 反向引用该 OriginEvent。
10. 每个 OriginEvent 必须满足 `origin_type` 对应的最小证据规则。
11. `OriginMetadata.origin_event_ids` 必须引用存在 OriginEvent。
12. `OriginMetadata.origin_role`、`age_band`、`discovery_state` 必须属于闭集。
13. `OriginMetadata.age_band` 必须与引用的 OriginEvent.age_band 相容；例如 fresh 证据不能引用 ancient 事件，除非 `origin_role=clue` 且对应 `OriginEvent.expected_outputs` 明确允许线索跨年代保存。
14. `OriginEvent.scope` 必须覆盖证据实体的位置。
15. LLM proposal 不能直接写 OriginEvent 或 OriginMetadata。
16. 生成 OriginEvent、附加 OriginMetadata 和创建证据实体必须写 EventLog。
17. OriginHistoryCandidateFormation 的输入清单不能包含 SettlementProfile、LawPolicy、EconomyState、SocialPressureState、NamedNPCState 或 ServiceState。

## 推荐生成顺序

P0 推荐：

```text
1. 基础空间、地形、水文、聚落空间锚点以及资源/生态/猎物/文明/危险/异常压力已生成；权威 Resource、Ecology 和社会实体尚未生成。
2. OriginHistoryCandidateFormation 生成 OriginEventCandidate，不提交权威 OriginEvent。
3. ResourceFormation / EcologyFormation / SitePlacement / ObjectMaterialization / SettlementSocialFormation 可以消费 OriginEventCandidate 调整候选权重。
4. Site / LocationNode / WorldObject / Resource / Ecology / Social evidence 实体完成物化。
5. OriginHistoryMaterialization 读取 OriginEventCandidate 和已物化证据，提交权威 OriginEvent。
6. OriginAttachment 为相关实体附加 OriginMetadata。
7. OriginHistoryValidator 校验双向引用、证据数量和空间范围。
8. 写 EventLog。
9. 初始 Snapshot 覆盖 OriginEvent 和所有 origin attachment。
```

如果对应证据实体尚未物化，生成器不能提交权威 OriginEvent。必须延后 `OriginHistoryMaterialization`，或先完成证据实体物化。

## P0 示例

### 废弃马车

```text
road + trade_route + danger_pressure=medium
-> OriginEvent(origin_type=accident_site, cause_tags=[trade_route, ambush_suspected])
-> Site(type=abandoned_vehicle_site)
-> WorldObject(object_type=vehicle, state=damaged)
-> WorldObject(object_type=clue, tags=[blood_stain])
-> HazardSource(hazard_type=trap_risk 或 infection_risk，按具体证据决定)
```

验收：

```text
废弃马车、断轮和血迹共享同一个 OriginEvent。
删除血迹后，OriginEvent 仍必须满足最小证据数量；否则 validator 报错。
```

### 遗迹异常污染

```text
ruin + abnormal_pressure=high
-> OriginEvent(origin_type=ritual_failure)
-> OriginEvent(origin_type=abnormal_contamination)
-> Site(type=ruin_site)
-> WorldObject(object_type=clue, tags=[rune])
-> ResourceNode(resource_id=blue_salt)
-> HazardSource(source_kind=abnormal_field)
```

验收：

```text
蓝盐不能只因为 name 或 description 出现而生成，必须有 abnormal_contamination 或等价来源支持。
```

### 灰石镇宵禁

```text
settlement + monster_attack_trace + guard_or_patrol_activity
-> SettlementProfile(law_profile=curfew_strict)
-> SocialPressureState(fear_of_monsters high)
-> LawPolicy(policy_type=curfew)
-> SocialGroupState(kind=guards)
```

验收：

```text
宵禁不能只是旁白设定，必须由 LawPolicy 和社会压力表达。
```

## 测试清单

```text
test_origin_event_requires_valid_scope
test_origin_type_must_be_closed_set
test_origin_cause_tags_must_be_registered
test_origin_evidence_ids_must_exist
test_origin_evidence_must_reference_origin_back
test_origin_event_requires_minimum_evidence
test_origin_scope_must_cover_evidence_locations
test_abandoned_vehicle_requires_road_or_trade_route
test_abnormal_resource_requires_abnormal_contamination_origin
test_ruin_decay_requires_ruin_or_abandoned_support
test_origin_metadata_notes_do_not_count_as_evidence
test_origin_history_candidate_formation_rejects_social_world_inputs
test_llm_proposal_cannot_write_origin_event
test_origin_event_generation_writes_event_log
test_deleted_evidence_invalidates_or_reconciles_origin_event
```

## 已确认决策

1. 历史来历是轻量静态世界事实，不是完整历史模拟。
2. `OriginEvent` 解释当前世界事实，`EventLog` 记录存档运行后的状态变化。
3. 能影响玩法的历史必须留下权威证据。
4. 证据实体必须反向引用来源，不能只靠 description。
5. 历史来历可以支持 Site、资源、生态、对象、危险、障碍和社会状态。
6. AI 可以提出历史候选，但不能直接写 OriginEvent 或 OriginMetadata。
7. P0 不要求每个小物件都有来源，只要求重要 Site、危险、异常、社会压力和核心线索可追溯。
