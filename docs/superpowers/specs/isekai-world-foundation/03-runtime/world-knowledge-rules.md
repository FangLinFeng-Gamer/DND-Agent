---
doc_id: isekai.world_knowledge_rules
status: active
layer: runtime
owner: architecture
created_at: 2026-07-13
updated_at: 2026-07-14
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.location_space_rules
  - isekai.world_origin_history_rules
  - isekai.static_world_runtime_rules
  - isekai.settlement_social_world_rules
provides:
  - KnowledgeState
  - DiscoveryState
  - RumorState
  - SecretState
  - AgentObservationSnapshot
  - KnowledgePropagation
  - KnowledgeValidator
---

# 异世界模式知识、发现与事件知情规则设计

## 背景

世界里存在三类容易混淆的事实：

```text
OriginEvent：世界生成前已经发生的静态历史事实。
EventLog：存档运行中状态变化的系统账本。
KnowledgeState：某个主体知道、相信、误解或隐藏了什么。
```

如果没有独立知识层，系统会出现两种严重问题：

- NPC 天然全知，能知道玩家没公开的行动、隐藏证据和未发现历史。
- 世界状态已经改变，但 NPC、群体和玩家没有任何认知更新，导致社会反应和调查反馈断裂。

本设计定义运行时知识系统。它不改变 `OriginEvent` 和 `EventLog` 的语义，只记录“谁知道什么、知道到什么程度、是否准确、能否传播、愿不愿说”。

## 目标

- 明确 `OriginEvent` 不等于所有 NPC 都知道的历史。
- 明确 `EventLog` 不等于 NPC 记忆或玩家可见历史。
- 定义 `KnowledgeState`，表达玩家、NPC、社会群体对世界事实、历史事件、运行事件、对象、地点和线索的认知。
- 定义 `DiscoveryState`，表达玩家或主体对对象、Site、危险、历史来源和证据的发现状态。
- 定义 `RumorState` 和 `SecretState`，支撑流言、隐瞒、官方秘密和错误认知。
- 定义 `KnowledgePropagation`，在 EventLog 提交后计算谁直接知道、谁间接听说、谁只能从证据推断。
- 定义 `AgentObservationSnapshot`，防止 AI 读取主体不该知道的事实。

## 非目标

- 不实现完整心理模型。
- 不为每个普通居民生成个人记忆。
- 不让 KnowledgeState 替代 WorldState。
- 不让 EventLog 直接暴露给 NPC 或 AI。
- 不让 AI 通过推理访问隐藏的 OriginEvent、EventLog 或未发现实体。
- 不把所有知识都写成自由文本。

## 核心原则

### 1. 世界事实和认知事实分离

世界事实可以真实存在，但主体可以不知道、误解或只听过传闻。

```text
废弃马车事故真实发生。
店主可能只听过传闻。
守卫队长可能调查过。
玩家可能只看见血迹后做出部分推断。
```

### 2. EventLog 是系统账本，不是游戏内记忆

`EventLogEntry` 记录状态提交顺序和变更内容。它只能被系统、validator、replay 和调试工具读取。NPC 和 AI 只能读取经过 `KnowledgePropagation` 与 `AgentObservationSnapshot` 过滤后的知识。

### 3. 知识有准确度和置信度

主体可以知道错误信息。流言可以部分正确。NPC 可以有高置信度的错误判断。Resolver 不能把 `KnowledgeState` 当成世界真相，只能把它作为社会反应、对话、搜索目标和 AI proposal 输入。

### 4. 知识传播必须有来源

每条知识必须说明来源：

```text
亲眼看见
亲自参与
听见声音
听别人说
观察证据推断
读取文档
机构记录
群体流言
AI proposal 经 resolver 接受
```

没有来源的知识不能进入权威状态。

### 5. 知识可以被隐瞒

主体知道某事，不代表会告诉玩家。是否透露必须由态度、风险、秘密等级、服务关系、交易和 AI proposal 共同决定，再由 resolver 落地。

### 6. 权威状态必须分命名空间

`AuthoritativeWorldState` 可以同时保存世界事实和知识事实，但必须分命名空间存储，不能把主体认知字段塞进世界实体。

```text
AuthoritativeWorldState
├── version_lock
├── world_facts
│   ├── World / Region / WorldChunk / Site / LocationNode / Zone / SiteBoundaryEdge
│   ├── OriginEvent / OriginMetadata
│   ├── WorldObject / ResourceNode / FloraPatch / CreaturePopulation / CreatureGroup / CreatureActor
│   ├── WeatherState / EnvironmentState / EnvironmentResidualEffectState / HazardSource / ObstacleSource
│   └── SettlementProfile / Institution / SocialGroupState / NamedNPCState
├── knowledge_facts
│   ├── KnowledgeState
│   ├── DiscoveryState
│   ├── RumorState
│   └── SecretState
└── system_ledger
    ├── EventLogEntry
    ├── WorldSnapshot
    ├── WorldGenerationManifest
    ├── GenerationStageContract
    ├── GeneratorOutputEnvelope / GeneratorOutputItem
    ├── ContentMaterializationContext
    ├── AIDecisionTick
    ├── GroupDecisionProposal / NPCActionProposal
    └── ProposalResourceReservation
```

`AgentObservationSnapshot` 是 AI 输入快照，属于知识运行时投影，不是新的世界事实。

## 世界事实与知识事实边界

### 世界事实

世界事实回答“世界里实际存在什么、在哪里、状态如何”。

P0 世界事实实体类型：

```text
World
Region
WorldChunkGrid
WorldChunk
ChunkEdge
RegionFeature
Settlement
TerrainFeature
Site
LocationNode
Zone
LocationEdge
SiteBoundaryEdge
ObjectPlacement
ActorLocation
OriginEvent
OriginMetadata
WeatherState
EnvironmentState
EnvironmentResidualEffectState
FloraPatch
CreaturePopulation
CreatureGroup
CreatureActor
NaturalResource
ResourceDeposit
ResourceNode
WorldObject
HazardSource
ObstacleSource
SettlementProfile
Institution
SocialGroupState
NamedNPCState
ServiceState
ServiceEntitlementState
LawPolicy
EconomyState
SocialPressureState
```

世界事实允许表达客观隐藏性，例如：

```text
WorldObject.state.concealment = hidden_under_cloth
LocationNode.visibility.light_level = dim
HazardSource.state.active = true
```

但它不能表达“谁知道了它”。

世界事实实体禁止出现以下主体认知字段：

```text
known_by
known_to_player
unknown_to
discovered_by
seen_by
heard_by
rumored_by
secret_holders
visible_to_subjects
can_tell_player
withholding_reason
npc_memory
player_memory
ai_context
```

### 知识事实

知识事实回答“某个主体知道、相信、发现、误解、传播或隐瞒了什么”。

P0 知识事实实体类型：

```text
KnowledgeState
DiscoveryState
RumorState
SecretState
```

知识事实只能引用世界事实、历史事件或运行事件，不能替代它们。

知识事实禁止携带以下物理世界字段：

```text
placement
location
terrain
water_presence
hydrology
physical
components
container
contents
resource_quantity
passability
travel_cost
weather_type
temperature
light
hit_points
damage_state
```

如果主体知道“门被锁了”，写法必须是：

```text
WorldObject.state.locked = true
KnowledgeState(subject=player, target=door_object, knowledge_level=observed)
```

不能写成：

```text
WorldObject.known_by = [player]
KnowledgeState.target.locked = true
```

### 边界例子

| 情况 | 世界事实 | 知识事实 |
| --- | --- | --- |
| 血迹存在 | `WorldObject(object_type=bloodstain)` | 玩家观察后创建 `DiscoveryState` |
| 马车事故真实发生 | `OriginEvent(origin_type=accident_site)` | 店主听说后创建 `KnowledgeState(knowledge_level=rumor)` |
| 门被锁 | `WorldObject.state.locked=true` | 玩家试门后创建 `KnowledgeState(target=door)` |
| 旅店有宵禁压力 | `LawPolicy` / `SocialPressureState` | NPC 是否知道该压力由 `KnowledgeState` 表达 |
| 某 NPC 隐瞒线索 | 线索本身仍是世界事实或历史事实 | 隐瞒关系写 `SecretState` |

## 总体模型

```text
WorldState / OriginEvent / EventLog
-> KnowledgePropagation
-> KnowledgeState
-> RumorState / SecretState / DiscoveryState
-> AgentObservationSnapshot
-> AI Proposal
-> Resolver
-> EventLog
```

## KnowledgeState

`KnowledgeState` 表示某个主体对某个目标事实的认知。主体可以是玩家、具名 NPC、社会群体、机构或系统测试夹具。

示例：店主听过废弃马车传闻。

```json
{
  "knowledge_id": "knowledge_innkeeper_cart_rumor_001",
  "subject": {
    "kind": "named_npc",
    "id": "innkeeper_01"
  },
  "target": {
    "kind": "origin_event",
    "id": "origin_abandoned_cart_001"
  },
  "knowledge_level": "rumor",
  "accuracy": "partial",
  "confidence": 0.45,
  "source": {
    "kind": "heard_from_group",
    "ref_id": "graystone_travelers"
  },
  "visibility": {
    "can_tell_player": true,
    "withholding_reason": "risk_averse"
  },
  "state": {
    "active": true,
    "last_updated_sequence": 128
  }
}
```

示例：玩家观察血迹后推断事故。

```json
{
  "knowledge_id": "knowledge_player_cart_blood_inference_001",
  "subject": {
    "kind": "player",
    "id": "player"
  },
  "target": {
    "kind": "origin_event",
    "id": "origin_abandoned_cart_001"
  },
  "knowledge_level": "inferred",
  "accuracy": "partial",
  "confidence": 0.55,
  "source": {
    "kind": "observed_evidence",
    "ref_id": "object_dried_blood_001"
  },
  "visibility": {
    "can_tell_player": true,
    "withholding_reason": null
  },
  "state": {
    "active": true,
    "last_updated_sequence": 142
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `knowledge_id` | 知识记录 ID。 |
| `subject.kind` | 知识持有者类型。 |
| `subject.id` | 知识持有者 ID。 |
| `target.kind` | 被认知目标类型。 |
| `target.id` | 被认知目标 ID。 |
| `knowledge_level` | 知道程度。 |
| `accuracy` | 认知准确度。 |
| `confidence` | 主体自身置信度，范围 0.0 到 1.0。 |
| `source` | 知识来源。 |
| `visibility.can_tell_player` | 主体是否允许把该知识透露给玩家。 |
| `visibility.withholding_reason` | 不透露原因。 |
| `state.active` | 当前知识是否仍有效。 |
| `state.last_updated_sequence` | 最近一次更新所对应的 EventLog sequence。 |

P0 `subject.kind` 闭集：

```text
player
named_npc
social_group
institution
settlement
system
```

P0 `target.kind` 闭集：

```text
origin_event
event_log_entry
world_object
site
location_node
hazard_source
obstacle_source
resource_node
creature_group
service_state
law_policy
social_pressure_state
named_npc
social_group
rumor_state
secret_state
```

P0 `knowledge_level` 闭集：

```text
unknown
hinted
rumor
overheard
witnessed
participant
inferred
investigated
documented
official_record
secret_known
misinformed
```

P0 `accuracy` 闭集：

```text
unknown
false
misleading
partial
mostly_true
true
```

P0 `source.kind` 闭集：

```text
participant
witnessed_event
overheard_event
heard_from_npc
heard_from_group
observed_evidence
read_document
official_record
rumor
ai_proposal_resolved
system_initial_knowledge
```

P0 `withholding_reason` 闭集：

```text
none
risk_averse
official_secret
personal_secret
hostile_to_player
wants_payment
protecting_someone
fear_of_punishment
does_not_trust_player
```

## DiscoveryState

`DiscoveryState` 表示主体是否已经发现某个实体、空间事实、路径、阻挡或证据。它比 `KnowledgeState` 更低层，用于空间投影、UI 显示和搜索/观察结算。

示例：

```json
{
  "discovery_id": "discovery_player_blood_stain_001",
  "subject": {
    "kind": "player",
    "id": "player"
  },
  "target": {
    "kind": "world_object",
    "id": "object_dried_blood_001"
  },
  "discovery_level": "visible",
  "source_event_id": "event_000142",
  "state": {
    "active": true
  }
}
```

示例：玩家看见东侧断崖路径被阻挡。

```json
{
  "discovery_id": "discovery_player_edge_cliff_blocked_001",
  "subject": {
    "kind": "player",
    "id": "player"
  },
  "target": {
    "kind": "chunk_edge",
    "id": "edge_chunk_12_08_00_to_13_08_00"
  },
  "discovery_level": "visible",
  "source_event_id": "event_000143",
  "state": {
    "active": true
  }
}
```

P0 `discovery_level` 闭集：

```text
unknown
hinted
visible
identified
misidentified
hidden
lost_track
```

规则：

```text
DiscoveryState 可以触发或更新 KnowledgeState。
DiscoveryState 不等于知道完整真相。
玩家看见血迹只表示发现证据，不表示自动知道完整事故。
玩家发现某个 chunk、site、location edge 或阻挡时，只创建或更新 DiscoveryState / KnowledgeState，不能向对应世界事实写入 known_to_player、known_by 或 discovered_by。
```

## RumorState

`RumorState` 表示在群体或聚落中传播的非权威说法。它可以指向真实 OriginEvent、EventLogEntry 或实体，也可以是错误传闻。

示例：

```json
{
  "rumor_id": "rumor_cart_wolves_001",
  "scope": {
    "kind": "settlement",
    "id": "graystone_town"
  },
  "target": {
    "kind": "origin_event",
    "id": "origin_abandoned_cart_001"
  },
  "claim_type": "cause",
  "accuracy": "partial",
  "spread_level": "local",
  "intensity": 0.5,
  "source": {
    "kind": "social_group",
    "id": "graystone_travelers"
  },
  "state": {
    "active": true,
    "created_sequence": 130
  }
}
```

P0 `claim_type` 闭集：

```text
existence
cause
identity
location
danger
service
law
blame
reward
warning
```

P0 `spread_level` 闭集：

```text
private
small_circle
local
settlement_wide
regional
```

规则：

```text
RumorState 不能改写目标事实。
RumorState 可以产生或更新 KnowledgeState。
RumorState.intensity 必须在 0.0 到 1.0。
AI 可以提出 spread_rumor proposal，但最终 RumorState 必须由 resolver 创建或更新。
```

## SecretState

`SecretState` 表示某些主体刻意隐藏的信息。它不表示世界事实本身，而表示保密关系和泄露风险。

示例：

```json
{
  "secret_id": "secret_guard_cart_report_001",
  "target": {
    "kind": "origin_event",
    "id": "origin_abandoned_cart_001"
  },
  "holders": [
    {
      "kind": "named_npc",
      "id": "guard_captain_01"
    },
    {
      "kind": "social_group",
      "id": "graystone_guards"
    }
  ],
  "secret_type": "official_secret",
  "sensitivity": "medium",
  "leak_risk": 0.2,
  "state": {
    "active": true
  }
}
```

P0 `secret_type` 闭集：

```text
official_secret
personal_secret
trade_secret
crime_coverup
forbidden_knowledge
protective_secret
```

P0 `sensitivity` 闭集：

```text
low
medium
high
critical
```

规则：

```text
SecretState 必须引用目标事实。
SecretState.holders 必须拥有对应 KnowledgeState。
SecretState 可以让 can_tell_player=false 或设置 withholding_reason。
SecretState 泄露必须通过 resolver 形成 StateTransition，并由 StateTransitionCommitter 生成 EventLog。
```

## KnowledgePropagation

`KnowledgePropagation` 在状态提交后运行，决定谁知道刚刚发生的运行事件，或谁通过新证据获得历史/世界知识。

输入：

```text
EventLogEntry
StateTransition changes
事件发生空间
参与者
见证者
可视/可听范围
DiscoveryState
OriginMetadata
SocialGroupState
Institution
SecretState
```

输出：

```text
KnowledgeState
DiscoveryState
RumorState
SecretState 更新
```

### 直接知情

以下主体直接获得知识：

```text
参与行动的主体。
被动作直接影响的主体。
同空间内可见或可听的主体。
负责该机构或服务的 NPC。
明确拥有官方记录权限的群体或机构。
```

### 间接知情

以下主体只能通过传播获得知识：

```text
同一社会群体成员。
机构同事。
聚落中的流言接收者。
守卫、店主、商人等信息节点。
后来观察到证据的主体。
```

### 运行事件传播示例

玩家在旅店支付住宿：

```text
EventLog(ServicePurchased)
-> 玩家 participant
-> 店主 participant
-> 同前厅旅客 overheard
-> 旅店住客 rumor
-> 镇卫队 unknown，除非运行中出现登记、报告或目击事件
```

玩家撬锁失败：

```text
EventLog(ObjectDamaged / NoiseCreated)
-> 玩家 participant
-> 附近 NPC overheard_event
-> 门锁产生 WorldObject 状态变化或 clue
-> 后来观察撬痕的守卫 inferred
```

## AgentObservationSnapshot

`AgentObservationSnapshot` 是 AI 调用前的输入快照。它只包含该主体有权知道的信息。

示例：

```json
{
  "snapshot_id": "obs_innkeeper_001",
  "subject": {
    "kind": "named_npc",
    "id": "innkeeper_01"
  },
  "based_on_event_sequence": 142,
  "visible_space": {
    "site_id": "old_furnace_inn",
    "node_id": "old_furnace_inn_front_hall"
  },
  "known_facts": [
    {
      "knowledge_id": "knowledge_innkeeper_cart_rumor_001",
      "target": {
        "kind": "origin_event",
        "id": "origin_abandoned_cart_001"
      },
      "knowledge_level": "rumor",
      "accuracy": "partial",
      "confidence": 0.45
    }
  ],
  "available_actions": ["offer_service", "refuse_service", "reveal_known_fact"],
  "available_target_refs": [
    {"kind": "actor", "id": "player"},
    {"kind": "service", "id": "old_furnace_lodging"},
    {"kind": "knowledge", "id": "knowledge_innkeeper_cart_rumor_001"}
  ],
  "action_argument_domains": {
    "offer_service": {
      "requested_price_modifier": [null, "markup_minor", "markup_major"]
    },
    "refuse_service": {
      "refusal_reason": ["identity_required", "curfew_restricted", "attitude_hostile"]
    },
    "reveal_known_fact": {
      "disclosure_style": ["direct", "cautious", "partial"]
    }
  },
  "redacted": true
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `snapshot_id` | 本次主体观察快照的唯一 ID。 |
| `subject` | 快照所属社会群体或具名 NPC。 |
| `based_on_event_sequence` | 构建快照时允许读取的 EventLog 序列上限。 |
| `visible_space` | 主体当前可以感知和交互的空间投影。 |
| `known_facts` | 由主体 KnowledgeState / RumorState / SecretState 裁剪出的已知事实。 |
| `available_actions` | 当前主体、位置和交互上下文允许提交的 AI action_type。 |
| `available_target_refs` | 当前 action 可以引用的实体和知识目标闭集。 |
| `action_argument_domains` | 每个可用 action 在当前上下文允许的参数和值域。 |
| `redacted` | 是否已经执行隐藏信息裁剪；AI snapshot 必须为 true。 |

规则：

```text
AI 只能读取 AgentObservationSnapshot。
AgentObservationSnapshot 不能包含主体没有 KnowledgeState 或 DiscoveryState 的隐藏事实。
EventLog.summary 不能直接塞给 AI，必须先转成主体可知的 KnowledgeState。
OriginEvent 不能直接塞给 AI，除非主体有对应 KnowledgeState。
available_actions 必须由主体类型、当前位置、机构职权、当前交互和 AI action policy registry 计算。
available_target_refs 必须是 snapshot 中主体可知、可定位且允许被当前 action_type 引用的目标。
action_argument_domains 必须只列出当前 snapshot 下允许的枚举或 registry 值；不能向 LLM 开放任意状态字段或任意 JSON 参数。
AI proposal 引用的 action_type、target_ref 和 arguments 必须是以上三个字段的子集。
```

## Validator 规则

必须增加 `KnowledgeValidator`，保证：

1. `KnowledgeState.subject` 必须引用存在主体，或为 P0 特例 `player`。
2. `KnowledgeState.target` 必须引用存在目标实体。
3. `knowledge_level`、`accuracy`、`source.kind`、`withholding_reason` 必须属于闭集。
4. `confidence` 必须在 0.0 到 1.0。
5. `KnowledgeState.source.ref_id` 必须能解析，除非 source.kind 明确不需要 ref。
6. `target.kind=event_log_entry` 时，target_id 必须引用存在 EventLogEntry。
7. `target.kind=origin_event` 时，target_id 必须引用存在 OriginEvent。
8. `DiscoveryState.target` 必须引用存在实体。
9. `RumorState.target` 必须引用存在目标或明确标记为 false rumor。
10. `RumorState.intensity` 必须在 0.0 到 1.0。
11. `SecretState.holders` 必须拥有对应 KnowledgeState。
12. `AgentObservationSnapshot` 不能包含主体没有权限知道的目标。
13. AI proposal 不能直接创建 KnowledgeState、RumorState、SecretState 或 DiscoveryState。
14. KnowledgePropagation 写入知识状态必须形成 StateTransition，并由 StateTransitionCommitter 生成 EventLog。
15. 世界事实实体不能包含主体认知字段。
16. 知识事实实体不能包含物理世界字段。
17. `AuthoritativeWorldState.world_facts` 不能存放 KnowledgeState、DiscoveryState、RumorState 或 SecretState。
18. `AuthoritativeWorldState.knowledge_facts` 不能存放世界事实实体。
19. `AgentObservationSnapshot` 不能反向写入世界事实或知识事实。
20. `AgentObservationSnapshot.available_actions` 必须来自 AI action policy registry。
21. `AgentObservationSnapshot.available_target_refs` 不能包含主体未知实体、事件或知识引用。
22. `AgentObservationSnapshot.action_argument_domains` 只能包含已注册值，且必须与 action_type schema 一致。

## 推荐运行顺序

状态提交后：

```text
1. Resolver 生成 StateTransition。
2. StateTransition 通过 Validator。
3. StateTransitionCommitter 原子提交 WorldState 变化并生成 EventLogEntry。
4. KnowledgePropagation 读取 EventLog、空间、参与者、证据和社会关系。
5. KnowledgePropagation 生成 KnowledgeState / DiscoveryState / RumorState / SecretState 更新。
6. 知识更新必须再次形成 StateTransition，并由 StateTransitionCommitter 原子提交。
7. Projection 和 AI Observation 使用更新后的知识状态。
```

规则：

```text
KnowledgePropagation 不能因为自己写入的 KnowledgeCreated / KnowledgeUpdated 事件再次默认触发传播。
如果需要流言继续扩散，必须由明确的 RumorPropagation tick 处理，并声明去重键、冷却和最大传播深度。
```

AI 调用前：

```text
1. 选择 subject。
2. 查询 subject 的 KnowledgeState / DiscoveryState。
3. 查询当前空间投影。
4. 过滤未授权 OriginEvent、EventLogEntry、WorldObject、NPC 和社会状态。
5. 生成 AgentObservationSnapshot。
6. AI 只基于该 snapshot 输出 proposal。
```

## 测试清单

```text
test_origin_event_not_visible_without_knowledge_state
test_event_log_entry_not_visible_without_knowledge_state
test_participant_gets_participant_knowledge
test_witness_gets_witnessed_or_overheard_knowledge
test_distant_group_does_not_auto_know_event
test_observed_evidence_can_create_inferred_knowledge
test_false_rumor_does_not_change_target_fact
test_secret_holder_must_have_corresponding_knowledge
test_agent_observation_snapshot_redacts_unknown_origin_event
test_agent_observation_snapshot_redacts_unknown_event_log
test_ai_proposal_cannot_write_knowledge_state_directly
test_knowledge_propagation_writes_event_log
test_world_fact_rejects_subject_knowledge_fields
test_knowledge_fact_rejects_physical_world_fields
test_world_state_namespaces_separate_world_and_knowledge_facts
test_agent_observation_snapshot_is_projection_not_world_fact
```

## 已确认决策

1. `OriginEvent` 是世界历史事实，不代表谁知道。
2. `EventLog` 是系统账本，不代表游戏内记忆。
3. `KnowledgeState` 才表达主体知道什么。
4. `DiscoveryState` 表达主体发现了什么证据或实体。
5. `RumorState` 表达传播中的说法，可能错误。
6. `SecretState` 表达保密关系和隐瞒原因。
7. AI 只能读取 `AgentObservationSnapshot`，不能读取全量 WorldState、OriginEvent 或 EventLog。
8. 世界事实和知识事实可以同属权威状态，但必须分命名空间、分实体类型、分字段边界。
