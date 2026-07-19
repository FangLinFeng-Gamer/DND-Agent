---
doc_id: isekai.ai_social_mind_rules
status: active
layer: ai-simulation
owner: architecture
created_at: 2026-07-10
updated_at: 2026-07-14
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.static_world_runtime_rules
  - isekai.world_knowledge_rules
provides:
  - AIDecisionTick
  - AIActionPolicyRegistry
  - AIProposalEnvelope
  - GroupDecisionProposal
  - NPCActionProposal
  - ProposalResourceReservation
  - ai_proposal_boundary
---

# 异世界模式 AI 社会心智设计

## 背景

地点/空间规则和物品规则已经作为底层世界逻辑确定：世界由 `World -> Region -> WorldChunk -> Site -> LocationNode -> Zone -> WorldObject` 组成，物体、地点、通行、资源和状态变化都必须进入权威 `WorldState`，并由确定性规则结算。

这意味着本模式不应该走“AI 无限叙事，讲到哪里算哪里”的路线。AI 可以生成世界内容和角色反应，但不能直接让叙事成为事实。世界运行规则必须写死，AI 的职责是为世界中有心智的部分提供判断、倾向、对话和决策提案。

本设计锁定新版本的 AI 使用边界和权威状态关系。未在本文闭合的实现项必须拆成 P1 开发票据，不允许开发在实现时临时增加自由规则或绕过 Validator。

## 设计目标

- 让 AI 成为世界社会变化的核心机制，而不是只做意图识别和旁白。
- 避免给世界里每个 NPC 都接入 AI，控制成本和状态复杂度。
- 用“群体心智”模拟大量 NPC 的共同意识、利益、恐惧、偏见和行动倾向。
- 对玩家近距离接触、剧情关键或长期互动的 NPC，使用更细粒度的个体代理模拟。
- 所有 AI 输出都必须是 proposal，不能直接修改 `WorldState`。
- AI 造成的影响必须经过 Validator 和 Deterministic Resolver，最终写入 EventLog。
- AI 只能读取主体可知的 `AgentObservationSnapshot`，不能直接读取全量 WorldState、OriginEvent 或 EventLog。

## 非目标

- 不实现每个 NPC 每回合独立思考。
- 不让 AI 直接移动 NPC、扣钱、发物品、改变地点、生成最终奖励或修改资源。
- 不让 AI 自由改写地点/空间/物品底层规则。
- 不让 AI 读取主体不知道的历史事件、运行事件、隐藏对象或系统账本。
- 不在本阶段设计完整政治、经济、战斗、阵营战争系统。
- 不把群体心智写成每回合固定旁白；群体影响必须通过事件、价格、流言、巡逻、服务门槛、态度变化等世界后果体现。

## 核心判断

本模式的 AI 使用方式应定义为：

```text
AI 负责世界中具有心智属性的判断与提案。
规则系统负责世界状态的合法性、结算和持久化。
```

换句话说：

```text
AI 可以判断“这群人会怎么想、可能怎么做”。
AI 不能直接宣布“世界已经发生了什么”。
```

这能同时满足两个要求：

- AI 原生：社会反应、群体意识、个体行为不是静态脚本，而是由 AI 根据世界状态动态生成。
- 强一致性：所有实际后果都由 `WorldState / Validator / Resolver / EventLog` 管控。

## NPC 智能分层

### 1. 背景人群

背景人群不建立独立 NPC，不接入 AI 个体模拟。

适用对象：

- 街上的普通镇民。
- 市场人流。
- 旅店普通客人。
- 路边围观者。
- 某个区域里的无名劳工、居民、旅人。

表达方式：

```text
Population / SocialGroup / SettlementState
```

它们只在群体层产生影响，例如区域是否紧张、服务是否变贵、陌生人是否被排斥、守卫是否增加巡逻。

### 2. 社会群体

社会群体是 AI 社会模拟的主要单位。

示例：

```text
灰石镇本地居民
旧炉旅店住客
镇卫队
外乡劳工
北坡猎人
异族商贩
旧信仰信众
```

每个群体至少应能表达：

```text
群体身份
意识形态
核心利益
恐惧
资源压力
对玩家态度
对其他群体态度
当前议题
行动倾向
影响范围
```

AI 不回答“每个人怎么想”，而是回答：

```text
在当前世界状态下，这个群体会形成什么判断？
他们会推动什么社会后果？
```

### 3. 近身个体 NPC

只有玩家附近、频繁互动、承担剧情功能或被玩家主动关注的人，才升级为个体代理。

适用对象：

```text
当前交谈对象
店主
守卫队长
同伴
长期交易对象
追踪玩家的人
掌握关键线索的人
```

个体 NPC 可以拥有：

```text
性格
记忆摘要
目标
关系
短期计划
当前情绪
风险判断
对玩家的个人态度
```

AI 可以为他们生成对话、反应和短期行为提案，但仍不能直接改状态。

### 4. 关键智能体

关键智能体是少量高权重 NPC 或组织代表。它们可以影响更大范围的世界状态。

适用对象：

```text
主要盟友
主要敌对者
组织首领
长期竞争者
区域权力核心
```

关键智能体的 AI 提案可以涉及布局、谈判、追踪、封锁、交易、背叛、庇护等，但必须经过更严格的 validator。

## 群体心智

群体心智是新版本 AI 使用的核心。

调度器构建输入时可以读取群体权威状态和知识状态，但 LLM 最终只能接收该群体的 `AgentObservationSnapshot`。快照至少投影以下信息：

```text
群体身份、利益、恐惧和当前压力摘要
群体可知的 KnowledgeState / RumorState / SecretState 摘要
群体已知的最近事件
玩家公开行为或群体已知行为
群体可感知的资源压力、地点、时间和风险
群体已知的其他群体变化
本次允许选择的 action_type、target_ref 和参数值域
```

LLM 输出不是最终事实，也不负责生成 proposal 元数据。LLM 只输出单步语义行动 payload，系统再用 `AIProposalEnvelope` 包装为 `GroupDecisionProposal`：

```json
{
  "action_type": "spread_rumor",
  "target_refs": [
    {"kind": "actor", "id": "player"},
    {"kind": "settlement", "id": "graystone_town"}
  ],
  "arguments": {
    "knowledge_id": "knowledge_graystone_night_return_001",
    "intensity_band": "minor"
  },
  "reasoning_summary": "外乡人的夜间行动会被本地居民视为新的不安来源。",
  "confidence_basis_points": 7800
}
```

群体心智能影响的后果类型：

```text
流言传播
价格倾向
服务门槛
盘问概率
巡逻密度
区域紧张度
群体态度
交易折扣或加价
是否愿意提供庇护
是否愿意透露线索
是否封锁或开放某些社会路径
```

这些后果必须落到明确的状态字段或事件中，不能只存在于 DM 文本。

## 个体代理

个体代理只用于近身和关键 NPC。

调度器构建输入时可以读取 NPC 权威状态和知识状态，但 LLM 最终只能接收该 NPC 的 `AgentObservationSnapshot`。快照至少投影以下信息：

```text
NPC 的角色、人格、关系、情绪和短期目标摘要
NPC 可知的 KnowledgeState / SecretState 摘要
当前空间投影
NPC 已知的玩家最近行为
NPC 已知的所属群体心智结果
本次允许选择的 action_type、target_ref 和参数值域
```

LLM 只输出单步语义行动 payload，系统再用 `AIProposalEnvelope` 包装为 `NPCActionProposal`：

```json
{
  "action_type": "offer_service",
  "target_refs": [
    {"kind": "actor", "id": "player"},
    {"kind": "service", "id": "old_furnace_lodging"}
  ],
  "arguments": {
    "requested_price_modifier": "markup_minor"
  },
  "reasoning_summary": "玩家是外乡人，且宵禁临近，店主认为接待风险上升。",
  "confidence_basis_points": 8200
}
```

规则系统必须校验：

```text
NPC 是否存在。
NPC 是否在当前可交互空间。
NPC 是否有权提供该服务。
价格是否在内容包或经济规则允许范围内。
NPC 态度和群体压力是否支持该行为。
该行为是否会修改货币、权益、对象、地点或任务状态。
所有状态变化是否写入 EventLog。
```

## P0 协议边界

P0 只允许 AI 提出一次可以立即校验和结算的单步社会行动。

允许：

```text
形成或传播一条流言。
调整一个社会压力维度。
请求提高或降低一级巡逻强度。
改变一次群体或 NPC 态度。
对当前服务请求报价、提供服务或拒绝服务。
向当前交互对象透露或隐瞒一条主体已知事实。
```

P0 不允许：

```text
创建跨小时或跨地点的长期计划。
创建 GoalState、PlanState 或 PlanStep。
让 AI 自己安排未来再次执行的动作。
在一个 proposal 中顺序执行多个动作。
用自由文本声明状态变化。
```

需要长期目标、分步计划、中断、重规划和跨地点执行时，必须另建智能体计划协议；不得扩展 P0 proposal 的 `arguments` 临时承载。

## 组件与职责

| 组件 | 输入 | 唯一职责 | 禁止事项 |
| --- | --- | --- | --- |
| `AISocialScheduler` | EventLog、时间、空间、主体状态 | 创建 `AIDecisionTick`，选择需要思考的主体 | 不调用 resolver，不改社会状态 |
| `AgentObservationBuilder` | 权威状态、主体知识 | 生成主体可知的 `AgentObservationSnapshot` | 不暴露主体未知事实 |
| `LLMDecisionAdapter` | `AgentObservationSnapshot` | 让 LLM 选择一个单步语义行动 payload | 不生成权威元数据，不写 WorldState |
| `AIProposalRecorder` | decision tick、snapshot、LLM payload | 用系统字段包装并记录 proposal | 不判断行动是否合法 |
| `AIProposalValidator` | proposal、当前权威状态 | 校验 schema、知识、revision、前置条件和数值域 | 不直接修改世界事实 |
| `AIProposalConflictResolver` | 同一 tick 的已验证 proposal | 计算冲突键、排序和资源预留 | 不让 AI 提供优先级 |
| `AIProposalAuditWriter` | AI ledger mutation | 在同一事务追加限定类型 EventLog | 不决定或改写 proposal 内容、校验结果和社会后果 |
| `AIProposalExpiryResolver` | WorldTimeState、非终态 proposal、active reservation | 将到期 proposal 和预留改为 expired 并写审计事件 | 不延长有效期，不修改资源本体 |
| `SocialActionResolver` | 已接受 proposal、预留、当前状态 | 生成确定性的 StateTransition 和 EventLog | 不读取 reasoning 作为规则输入 |
| `SocialFallbackResolver` | trigger、snapshot、当前权威状态 | LLM 不可用或两次尝试均失败时给出确定性最低行为 | 不模拟人格，不产生额外社会奖励或惩罚 |

## AIDecisionTick

`AIDecisionTick` 是一次 AI 社会决策批次，存入 `AuthoritativeWorldState.system_ledger`。它决定本次为什么调用 AI、哪些主体可以参与以及所有 proposal 使用哪个状态截面。

```json
{
  "decision_tick_id": "ai_tick_000142",
  "world_id": "isekai_world_001",
  "trigger": {
    "type": "service_request",
    "event_ids": ["evt_player_requested_lodging_001"],
    "scope_ref": {"kind": "site", "id": "old_furnace_inn"}
  },
  "based_on_event_sequence": 142,
  "scheduled_game_time": {"day": 12, "minute_of_day": 1160},
  "subject_refs": [
    {"kind": "named_npc", "id": "innkeeper_01"}
  ],
  "status": "collecting",
  "result": null
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `decision_tick_id` | 决策批次 ID，由系统生成。 |
| `world_id` | 所属世界。 |
| `trigger` | 触发类型、来源事件和影响范围。 |
| `based_on_event_sequence` | 本批次统一读取的 EventLog 序列上限。 |
| `scheduled_game_time` | 调度发生的游戏时间。 |
| `subject_refs` | 本次允许调用的群体或 NPC。 |
| `status` | `collecting / validating / resolving / completed / cancelled`。 |
| `result` | tick 终态结果；completed 时必须记录 `proposal_resolved / fallback / no_op`、关联 proposal、事件和原因码。 |

`trigger` 子字段：

| 字段 | 含义 |
| --- | --- |
| `type` | P0 触发类型闭集。 |
| `event_ids` | 触发该 tick 的已提交 EventLogEntry；periodic pulse 可以为空。 |
| `scope_ref` | 受影响的 settlement、site 或 location scope。 |

`result` 非空时必须符合：

```json
{
  "kind": "proposal_resolved",
  "proposal_id": "proposal_innkeeper_001",
  "event_ids": ["evt_service_offer_created_001"],
  "reason_codes": []
}
```

`result.kind` 闭集：

```text
proposal_resolved
fallback
no_op
```

`proposal_resolved` 必须提供 proposal_id；`fallback` 可以引用失败 proposal；`no_op` 的 event_ids 必须为空。`reason_codes` 只能使用 proposal validation reason code 闭集。

状态只能按以下方向推进：

```text
collecting -> validating -> resolving -> completed
collecting / validating / resolving -> cancelled
```

`completed` 和 `cancelled` 是终态。

P0 `trigger.type` 闭集及系统优先级：

| trigger.type | 触发条件 | `trigger_priority` |
| --- | --- | ---: |
| `direct_interaction` | 玩家直接与当前 NPC 交互 | 400 |
| `service_request` | 玩家或其他主体提出当前服务请求 | 350 |
| `emergency_event` | 影响主体安全、机构或聚落秩序的已提交事件 | 300 |
| `relevant_committed_event` | 主体已知且命中其利益、恐惧或职责的已提交事件 | 200 |
| `periodic_social_pulse` | 没有直接事件时的低频群体刷新 | 100 |

调度规则：

```text
群体心智：每个群体最多每 60 游戏分钟执行一次 periodic_social_pulse。
近身 NPC：只在当前或相邻可交互空间内，且发生 direct_interaction、service_request 或 relevant event 时执行。
近身 NPC 的环境型 relevant event 冷却为 10 游戏分钟；新的玩家直接交互不受该时间冷却限制，但必须按 trigger event 去重。
emergency_event 可以绕过时间冷却，但同一 subject_id + event_id 只能触发一次。
调度器只能读取已经提交的 EventLog；未提交 StateTransition 不能触发 AI。
AIDecisionTickStatusChanged、AIProposalRecorded、AIProposalStatusChanged、ProposalReservationCreated 等审计事件不能触发新的 AIDecisionTick。
```

## AIProposalEnvelope

`AIProposalEnvelope` 是 `GroupDecisionProposal` 和 `NPCActionProposal` 共用的 canonical schema 片段。LLM 只填写 `action` 中允许的 payload 字段；其余字段必须由系统生成或校验器写入。

```json
{
  "proposal_id": "proposal_innkeeper_001",
  "proposal_kind": "npc_action",
  "decision_tick_id": "ai_tick_000142",
  "decision_slot_key": "named_npc:innkeeper_01:ai_tick_000142",
  "attempt_no": 1,
  "subject": {"kind": "named_npc", "id": "innkeeper_01"},
  "subject_state_revision": 7,
  "observation_snapshot_id": "obs_innkeeper_142",
  "based_on_event_sequence": 142,
  "read_set": [
    {
      "entity_type": "ServiceState",
      "entity_id": "old_furnace_lodging",
      "revision_or_hash": "sha256:service-state-142"
    },
    {
      "entity_type": "Institution",
      "entity_id": "old_furnace_inn_business",
      "revision_or_hash": "sha256:institution-state-142"
    },
    {
      "entity_type": "EconomyState",
      "entity_id": "graystone_economy",
      "revision_or_hash": "sha256:economy-state-142"
    },
    {
      "entity_type": "LawPolicy",
      "entity_id": "graystone_curfew_policy",
      "revision_or_hash": "sha256:law-policy-state-142"
    },
    {
      "entity_type": "ActorLocation",
      "entity_id": "player",
      "revision_or_hash": "sha256:player-location-142"
    }
  ],
  "idempotency_key": "sha256:decision-slot-and-payload",
  "valid_until_game_time": {"day": 12, "minute_of_day": 1170},
  "causal_context": {
    "chain_id": "social_chain_evt_000140",
    "root_event_ids": ["evt_player_requested_lodging_001"],
    "parent_proposal_id": null,
    "depth": 0
  },
  "action": {
    "action_type": "offer_service",
    "target_refs": [
      {"kind": "actor", "id": "player"},
      {"kind": "service", "id": "old_furnace_lodging"}
    ],
    "arguments": {
      "requested_price_modifier": "markup_minor"
    },
    "reasoning_summary": "宵禁临近，接待外乡人的风险较高。",
    "confidence_basis_points": 8200
  },
  "computed_policy": {
    "trigger_priority": 350,
    "conflict_keys": ["service:old_furnace_lodging:player"],
    "required_preconditions": [
      "subject_is_service_provider",
      "service_is_available",
      "subject_can_interact_with_target"
    ],
    "resource_claims": [
      {"kind": "service_use", "id": "old_furnace_lodging", "quantity": 1}
    ]
  },
  "status": "accepted",
  "validation": {
    "result": "accepted",
    "reason_codes": [],
    "applied_action": null
  },
  "resolution": null
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `proposal_id` | proposal 唯一 ID，由 decision slot、尝试次数和 canonical payload 生成。 |
| `proposal_kind` | 群体决策或 NPC 行动判别类型。 |
| `decision_tick_id` | 产生该 proposal 的 AIDecisionTick。 |
| `decision_slot_key` | 同一 tick 中同一主体唯一可结算槽位。 |
| `attempt_no` | 当前 decision slot 的 LLM 尝试次数，P0 为 1 或 2。 |
| `subject` | 作出决策的 SocialGroupState 或 NamedNPCState 引用。 |
| `subject_state_revision` | snapshot 构建时的主体 revision，用于拒绝过期决策。 |
| `observation_snapshot_id` | 本次 LLM 实际读取的 AgentObservationSnapshot。 |
| `based_on_event_sequence` | proposal 所基于的已提交 EventLog 序列上限。 |
| `read_set` | 决策依赖实体及其 revision 或 canonical state hash。 |
| `idempotency_key` | 相同决策槽位和相同 payload 的重复提交去重键。 |
| `valid_until_game_time` | proposal 最晚可接受或结算的游戏时间；P0 不得晚于生成后 10 游戏分钟。 |
| `causal_context` | 因果链、根事件、父 proposal 和当前深度。 |
| `action` | LLM 选择的单步语义行动。 |
| `computed_policy` | validator 依据 action policy 计算的优先级、冲突键、强制前置条件和资源声明。 |
| `status` | proposal 当前生命周期状态。 |
| `validation` | 校验结果、原因码以及部分接受后的实际行动。 |
| `resolution` | resolver 结果；成功时至少包含 `state_transition_id`、`event_ids` 和 `resolved_at_sequence`。 |

`action` 子字段说明：

| 字段 | 含义 |
| --- | --- |
| `action_type` | P0 社会行动闭集中的一个值。 |
| `target_refs` | 该行动引用的实体或知识目标，必须来自 snapshot。 |
| `arguments` | action_type 专属参数对象，不允许额外字段。 |
| `reasoning_summary` | LLM 的简短解释，只用于审计和叙事风格，不参与结算。 |
| `confidence_basis_points` | 模型对其语义选择的置信度整数，范围 0 到 10000；不能作为状态 delta 或系统优先级。 |

P0 LLM 响应必须且只能包含 `action_type`、`target_refs`、`arguments`、`reasoning_summary` 和 `confidence_basis_points` 五个字段，且只能返回一个 action。缺少字段、出现额外字段、返回动作数组或在 `arguments` 中增加未登记字段，均以 `schema_invalid` 拒绝。

`computed_policy` 子字段说明：

| 字段 | 含义 |
| --- | --- |
| `trigger_priority` | 由 trigger.type 映射的系统排序值。 |
| `conflict_keys` | 系统派生的互斥资源或状态维度键。 |
| `required_preconditions` | action policy 强制要求 resolver 前检查的条件。 |
| `resource_claims` | 系统从 action 和目标状态计算的资源预留请求。 |

`validation.result` 闭集：

```text
accepted
accepted_with_adjustment
rejected
expired
```

`validation.reason_codes` P0 闭集：

```text
schema_invalid
unknown_action_type
invalid_target_reference
target_not_in_snapshot
hidden_knowledge_reference
subject_revision_mismatch
read_set_changed
proposal_expired
precondition_failed
policy_forbidden
resource_unavailable
conflict_lost
cooldown_active
causal_limit_reached
daily_change_cap_reached
duplicate_decision_slot
```

字段所有者：

| 字段 | 写入者 | 约束 |
| --- | --- | --- |
| `action.action_type / target_refs / arguments / reasoning_summary / confidence_basis_points` | LLM payload，经 `LLMDecisionAdapter` 映射 | 必须符合快照下发的闭集 schema；自由文本不能驱动规则 |
| `proposal_id / proposal_kind / decision_tick_id / decision_slot_key / attempt_no / subject / subject_state_revision / observation_snapshot_id / based_on_event_sequence / read_set / idempotency_key / valid_until_game_time / causal_context` | `AIProposalRecorder` | LLM 输出任一同名字段时，当前 payload 必须以 `schema_invalid` 拒绝并记录违规 |
| `computed_policy` | `AIProposalValidator` | 必须从 action policy registry 派生，不能采用 LLM 提供值 |
| `status / validation` | `AIProposalValidator`、冲突处理器 | 只能按状态机推进 |
| `resolution` | `SocialActionResolver` | 必须引用实际 EventLog 和 StateTransition |

`proposal_kind` 闭集：

```text
group_decision
npc_action
```

`subject.kind` 必须与 `proposal_kind` 对应：

```text
group_decision -> social_group
npc_action -> named_npc
```

`target_ref.kind` P0 闭集：

```text
actor
social_group
named_npc
settlement
institution
service
knowledge
rumor
world_object
entitlement
pressure_state
```

`status` 状态机：

```text
recorded -> validated -> accepted -> resolved
recorded -> rejected
validated -> accepted_with_adjustment -> resolved
validated -> rejected
recorded / validated / accepted -> expired
```

`resolved`、`rejected`、`expired` 是终态。终态 proposal 不得再次结算。

## Proposal ledger 与 EventLog

decision tick、proposal 和 reservation 虽然不属于世界事实，但必须可存档和重放。它们的每次创建或状态变化必须在同一原子事务中通过 `AIProposalAuditWriter` 追加以下限定事件：

```text
AIDecisionTickCreated
AIDecisionTickStatusChanged
AIProposalRecorded
AIProposalStatusChanged
ProposalReservationCreated
ProposalReservationStateChanged
```

规则：

```text
AIProposalAuditWriter 只能为 system_ledger 中 AIDecisionTick、GroupDecisionProposal、NPCActionProposal 和 ProposalResourceReservation 的 mutation 追加审计事件。
AIProposalAuditWriter 不能改变 mutation 内容，不能修改 world_facts、knowledge_facts，也不能代替 SocialActionResolver 结算社会后果。
AIProposalRecorded 必须保存 canonical action payload 或其可恢复引用及 canonical hash，确保 replay 不需要重新调用 LLM。
AIProposalStatusChanged 必须保存 previous_status、new_status 和 validation.reason_codes。
AIDecisionTickStatusChanged 必须保存 previous_status、new_status 和终态 result。
ProposalReservationStateChanged 必须保存 consumed、released 或 expired 的原因和关联 resolver event。
以上审计事件的 caused_by.kind 必须是 ai_runtime，caused_by.id 必须引用实际 scheduler、recorder、validator、conflict resolver、expiry resolver 或 audit writer 组件。
以上审计事件不能进入 AISocialScheduler 的触发集合。
```

`SocialActionResolver` 成功后必须另外写对应领域事件，例如 `SocialPressureChanged`、`PatrolLevelChanged`、`SocialAttitudeChanged`、`ServiceOfferCreated`、`ServiceRequestRefused` 或 `KnowledgeDisclosureResolved`。审计事件不能替代领域事件。

`offer_service` 成功结算后的 `resolution` 示例：

```json
{
  "state_transition_id": "transition_service_offer_001",
  "event_ids": ["evt_service_offer_created_001"],
  "resolved_at_sequence": 145,
  "result": {
    "kind": "service_offer",
    "service_id": "old_furnace_lodging",
    "price": {"currency": "copper", "amount": 5},
    "reservation_id": "proposal_reservation_001",
    "valid_until_game_time": {"day": 12, "minute_of_day": 1170}
  }
}
```

`resolution.result` 由对应 deterministic resolver 按 action_type schema 生成。LLM 不能提交 `result`、最终价格、货币 delta、权益、钥匙或 EventLog ID。

## GroupDecisionProposal 与 NPCActionProposal

两个类型共用 `AIProposalEnvelope`，只通过判别字段和 action policy 区分，不重复定义两套元数据：

```text
GroupDecisionProposal = AIProposalEnvelope(proposal_kind=group_decision, subject.kind=social_group)
NPCActionProposal = AIProposalEnvelope(proposal_kind=npc_action, subject.kind=named_npc)
```

### AIActionPolicyRegistry

每个 `action_type` 必须且只能对应一条 `AIActionPolicyEntry`。该 registry 随规则版本发布，不属于内容包，LLM 和运行时不能新增或修改条目。

```json
{
  "policy_id": "ai_action.npc.offer_service.v1",
  "proposal_kind": "npc_action",
  "action_type": "offer_service",
  "subject_kind": "named_npc",
  "required_targets": [
    {"kind": "service", "count": 1, "relation": "subject_is_provider_or_authorized"},
    {"kind": "actor", "count": 1, "relation": "currently_interactable"}
  ],
  "argument_schema_id": "ai_action_args.offer_service.v1",
  "required_precondition_ids": [
    "subject_is_service_provider",
    "service_is_available",
    "subject_can_interact_with_target"
  ],
  "conflict_key_rule_id": "ai_conflict.service_actor.v1",
  "resource_claim_rule_id": "ai_resource_claim.service_use.v1",
  "resolver_id": "social_action.offer_service.v1",
  "partial_acceptance_policy_id": "ai_partial.price_modifier_clamp.v1",
  "allowed_event_types": ["ServiceOfferCreated"],
  "version": "2026-07-14"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `policy_id` | action policy 唯一规则 ID。 |
| `proposal_kind` | 允许使用该 action 的 proposal 类型。 |
| `action_type` | LLM 可以选择的动作值。 |
| `subject_kind` | 可以提交该 action 的主体类型。 |
| `required_targets` | 目标类型、精确数量和主体/交互关系。 |
| `argument_schema_id` | 对应参数 schema registry 条目。 |
| `required_precondition_ids` | validator 必须执行的前置条件规则。 |
| `conflict_key_rule_id` | 生成冲突键的确定性规则。 |
| `resource_claim_rule_id` | 生成资源声明的确定性规则；不需要资源时必须显式引用 `ai_resource_claim.none.v1`。 |
| `resolver_id` | 唯一允许结算该 action 的 resolver。 |
| `partial_acceptance_policy_id` | 部分接受规则；不允许调整时必须显式引用 `ai_partial.reject_on_difference.v1`。 |
| `allowed_event_types` | resolver 可以产生的领域事件闭集。 |
| `version` | policy 版本，参与 rule bundle hash 和 replay。 |

规则：

```text
AIActionPolicyRegistry 缺少 action_type 时，AgentObservationBuilder 不得把它加入 available_actions。
同一 action_type 存在多个 active policy 时启动失败，不能按加载顺序选择。
argument schema、precondition、conflict、resource claim、resolver、partial acceptance 和 event type 引用必须全部可解析。
LLM 不能输出 policy_id、resolver_id 或任意 rule_id 来改变结算路径。
```

P0 `action_type` 闭集：

| proposal_kind | action_type | 必要目标 | 参数 | 确定性落点 |
| --- | --- | --- | --- | --- |
| `group_decision` | `spread_rumor` | knowledge、settlement 或 social_group | `intensity_band` | SocialActionResolver 写 RumorSpreadRequested；KnowledgePropagation 写 RumorState；SocialRumorIndexReducer 写 active_rumor_ids |
| `group_decision` | `adjust_social_pressure` | pressure_state | `pressure_key`、`direction`、`intensity_band` | SocialPressureState、EventLog |
| `group_decision` | `request_patrol_change` | settlement | `direction` | SocialPressureState.active_patrol_level、EventLog |
| `group_decision` | `change_group_attitude` | social_group、actor | `target_attitude` | SocialGroupState.attitude_to_player、EventLog |
| `npc_action` | `offer_service` | service、actor | `requested_price_modifier` 可空 | 确定性服务报价、可选资源预留、EventLog |
| `npc_action` | `refuse_service` | service、actor | `refusal_reason` | 单次服务请求结果、EventLog；不永久关闭 ServiceState |
| `npc_action` | `reveal_known_fact` | knowledge、actor | `disclosure_style` | KnowledgePropagation 输入、EventLog |
| `npc_action` | `withhold_known_fact` | knowledge、actor | `withholding_reason` | 单次交互结果、EventLog；不删除 KnowledgeState |
| `npc_action` | `change_npc_attitude` | named_npc、actor | `target_attitude` | NamedNPCState.attitude_to_player、EventLog |

目标数量和归属规则：

```text
spread_rumor 必须且只能引用一个 knowledge 和一个 settlement 或 social_group scope。
adjust_social_pressure 必须且只能引用一个 pressure_state。
request_patrol_change 必须且只能引用一个 settlement。
change_group_attitude 必须引用 subject 自身 social_group 和一个 actor。
offer_service / refuse_service 必须引用一个 service 和一个 actor，且 subject 必须是该服务 provider 或具有机构授权。
reveal_known_fact / withhold_known_fact 必须引用一个 subject 已知 knowledge 和一个当前可交互 actor。
change_npc_attitude 必须引用 subject 自身 named_npc 和一个 actor。
多余、缺失、重复或归属不匹配的 target_ref 必须拒绝，不能由 validator 猜测或补全。
```

通用参数闭集：

```text
intensity_band: minor | moderate | major
direction: increase | decrease
requested_price_modifier: null | discount_minor | discount_major | markup_minor | markup_major | require_barter
refusal_reason: policy_blocked | resource_unavailable | attitude_hostile | identity_required | curfew_restricted | provider_unavailable
disclosure_style: direct | cautious | partial | misleading
withholding_reason: risk_averse | official_secret | personal_secret | hostile_to_player | wants_payment | protecting_someone | fear_of_punishment | does_not_trust_player
```

`pressure_key` 必须来自 `SocialPressureState.pressure` 闭集。`target_attitude` 必须来自对应 attitude 闭集。`knowledge` 目标必须存在于当前主体 snapshot；`misleading` 只能传播主体已经持有的错误或不完整知识，不能凭空创建世界事实。

每个 action 的 `arguments` 必须精确包含 P0 action_type 表中列出的参数，不得缺省或增加参数。`offer_service.requested_price_modifier` 是必填 nullable 字段；不申请修正时必须显式输出 `null`。

## 前置条件与过期校验

AI 不能自行决定必须检查哪些前置条件。`AIProposalValidator` 根据 `action_type` 派生 `required_preconditions`，至少依次执行：

```text
1. proposal schema、枚举、registry 和 reference 全部合法。
2. decision_tick、subject 和 observation_snapshot 相互匹配。
3. snapshot.based_on_event_sequence 等于 proposal.based_on_event_sequence。
4. subject_state_revision 与当前主体 revision 一致。
5. read_set 中所有 revision 或 canonical state hash 与当前值一致。
6. 当前游戏时间未超过 valid_until_game_time。
7. action_type 位于 snapshot.available_actions。
8. target_refs 位于 snapshot 可引用目标集合，且主体对知识目标具有对应 KnowledgeState。
9. 主体空间、机构职权、服务权限、LawPolicy、资源和 cooldown 满足 action policy。
10. action 不能通过 reasoning_summary 或自由文本请求任何额外状态变化。
```

任一强前置条件失败时，proposal 必须进入 `rejected` 或 `expired`，且不得产生世界状态变化。不得把旧 proposal 自动套用到新 revision。

`read_set.revision_or_hash` 优先使用实体已有 `state_revision`；没有 revision 的实体使用 `sha256(CanonicalBytes(entity_at_based_on_event_sequence))`。`CanonicalBytes` 必须复用确定性随机协议中的 canonical JSON 规则，不能使用数据库行序、语言默认对象序或本地化序列化。

`read_set` 必须由 `AIProposalRecorder` 根据 snapshot 和 `AIActionPolicyEntry` 自动覆盖全部 target_refs，以及 validator 将读取的空间、机构、服务、LawPolicy、EconomyState、SocialPressureState、知识和资源实体。LLM 不能删减 read_set；任一 action policy 无法枚举其读取依赖时，该 policy 不得启用。

## 幂等与重试

```text
decision_slot_key = sha256(CanonicalBytes({decision_tick_id, subject_kind, subject_id}))
idempotency_key = sha256(CanonicalBytes({decision_slot_key, canonical_action_payload}))
proposal_id = sha256(CanonicalBytes({decision_slot_key, attempt_no, canonical_action_payload}))
```

`canonical_action_payload` 只包含 `action_type`、按 `AIActionPolicyEntry.required_targets` 顺序规范化的 `target_refs` 和按 key 排序的 `arguments`。`reasoning_summary` 与 `confidence_basis_points` 不进入语义幂等键，避免模型只改变措辞或置信度就获得第二次结算机会；它们仍保存在 proposal 审计记录中。

规则：

```text
相同 idempotency_key 的重复传输返回已有结果，不再次结算。
每个 decision_slot_key 最多只能有一个 accepted、accepted_with_adjustment 或 resolved proposal。
schema 或引用错误允许 LLM 在同一 decision slot 重试一次；attempt_no 最大为 2。
一旦某次尝试进入 accepted、accepted_with_adjustment 或 resolved，后续尝试全部拒绝。
超时、网络重试和进程恢复必须复用原 decision_tick_id，不能创建新的决策机会。
```

### 失败回退

LLM 超时、输出无法解析，或两次尝试都被拒绝时，不得卡住当前交互，也不得让 DM 自由补写状态。`SocialFallbackResolver` 按 trigger 执行固定回退：

| trigger.type | 确定性回退 |
| --- | --- |
| `service_request` | 服务合法可用时按无 AI modifier 的规则价格生成一次报价；否则按真实失败前置条件生成 `ServiceRequestRefused` |
| `direct_interaction` | 生成无状态变化的中性回应结果，不改变态度、知识、资源或地点 |
| `emergency_event` | 只执行已有 LawPolicy、Hazard 或守卫规则，不生成 AI 社会增益 |
| `relevant_committed_event` | 本 tick no-op，保留已提交世界事件 |
| `periodic_social_pulse` | 本 tick no-op |

失败 proposal 保留自身 `validation.reason_codes`；回退结果写入 `AIDecisionTick.result.kind=fallback`，不能伪装成已接受或已结算的 AI proposal。若回退产生服务报价或拒绝，仍必须经过对应服务 resolver 并写领域 EventLog。回退不能创建新的 AI decision tick。

## 冲突键与确定性排序

冲突键只能由系统按 action policy 计算：

| action_type | conflict_key |
| --- | --- |
| `spread_rumor` | `rumor:{scope_id}:{knowledge_id}` |
| `adjust_social_pressure` | `pressure:{pressure_state_id}:{pressure_key}` |
| `request_patrol_change` | `patrol:{settlement_id}` |
| `change_group_attitude` | `attitude:group:{group_id}:{actor_id}` |
| `offer_service / refuse_service` | `service:{service_id}:{actor_id}` |
| `reveal_known_fact / withhold_known_fact` | `knowledge_disclosure:{subject_id}:{knowledge_id}:{actor_id}` |
| `change_npc_attitude` | `attitude:npc:{npc_id}:{actor_id}` |

同一 decision tick 内按以下键升序处理，其中 priority 数值按降序：

```text
trigger_priority DESC
trigger_event_sequence ASC
subject_kind_rank ASC        # named_npc=0, social_group=1
subject_id ASC
proposal_id ASC
```

`trigger_priority` 和 `subject_kind_rank` 都由系统生成。AI 输出 priority 字段必须被拒绝。相同 conflict_key 的前序 proposal 接受后，后序 proposal 必须在更新后的临时状态和预留集合上重新校验。

`trigger_event_sequence` 取 `trigger.event_ids` 中最大的 EventLog sequence；`periodic_social_pulse` 没有 event_id 时取 `AIDecisionTick.based_on_event_sequence`。字符串比较统一使用 Unicode code point 升序，不允许使用数据库默认 collation 或本地化排序。

## ProposalResourceReservation

`ProposalResourceReservation` 存入 `system_ledger`，只用于防止同一服务名额、物品或权益槽位被多个已接受 proposal 重复承诺。它不代表玩家已经获得资源。

```json
{
  "reservation_id": "proposal_reservation_001",
  "proposal_id": "proposal_innkeeper_001",
  "decision_tick_id": "ai_tick_000142",
  "resource_ref": {
    "kind": "service_use",
    "id": "old_furnace_lodging"
  },
  "quantity": 1,
  "created_from_event_sequence": 142,
  "valid_until_game_time": {"day": 12, "minute_of_day": 1170},
  "status": "active"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `reservation_id` | 预留记录唯一 ID。 |
| `proposal_id` | 申请该预留的已接受 proposal。 |
| `decision_tick_id` | 创建预留的决策批次。 |
| `resource_ref` | 被预留资源的类型和 ID。 |
| `quantity` | 预留数量，必须为大于 0 的整数且不超过可用量。 |
| `created_from_event_sequence` | 创建预留时已提交的 EventLog sequence。 |
| `valid_until_game_time` | 预留自动过期时间。 |
| `status` | 预留当前状态。 |

P0 `resource_ref.kind` 闭集：

```text
service_use
world_object
entitlement_slot
subject_action_slot
```

P0 `reservation.status` 闭集：

```text
active
consumed
released
expired
```

规则：

```text
reservation 只能由 AIProposalConflictResolver 创建，由对应 resolver 消耗或释放。
reservation 有效期不得晚于 proposal.valid_until_game_time，且最长为 10 游戏分钟。
proposal 被拒绝、过期或 resolver 失败时必须在同一事务释放 reservation。
WorldTimeState 到达 valid_until_game_time 时，AIProposalExpiryResolver 必须在同一时间推进事务中将非终态 proposal 和 active reservation 改为 expired。
服务购买或资源转移时仍要重新校验当前状态；reservation 不能绕过交易、货币或所有权规则。
同一资源的 active reservation 总量不得超过当前可用量。
```

## 部分接受与确定性调整

允许 `accepted_with_adjustment` 的范围必须闭合：

```text
adjust_social_pressure：minor=0.02、moderate=0.05、major=0.10；达到上限时只能缩小绝对值。
offer_service：discount/markup 只能按 major -> minor -> null 缩小到 LawPolicy、EconomyState 和服务规则共同允许的最强修正；require_barter 是离散条款，不允许时必须拒绝而不是改成价格修正。
```

以下内容不能被“部分接受”改写：

```text
action_type
subject
target_refs
knowledge_id
service_id
resource_ref
```

这些字段非法或不可用时必须拒绝 proposal。调整前的 `action` 和实际采用的 `validation.applied_action` 必须同时保留，Narration/UI 只能描述实际采用结果。

当 24 小时累计压力变化仍有非零余量时，`adjust_social_pressure` 可以缩小到剩余余量并标记 `accepted_with_adjustment`；剩余余量为 0 时必须以 `daily_change_cap_reached` 拒绝，不能接受一个零效果行动。

`request_patrol_change` 必须按 direction 精确移动一级；已经位于边界时拒绝。态度 proposal 的 `target_attitude` 必须是当前态度的一条直接 registry 边；不存在直接边时拒绝。二者都不能由 validator 猜测中间状态后部分接受。

P0 `AttitudeTransitionRegistry`：

```text
unknown -> neutral | unknown_suspicious
unknown_suspicious -> cautious | hostile
neutral -> cautious | friendly | exploitative
cautious -> neutral | friendly | hostile | fearful
friendly -> neutral | trusting | protective
trusting -> friendly | protective
hostile -> cautious | fearful
fearful -> cautious | hostile
protective -> friendly | trusting
exploitative -> neutral | cautious | hostile
```

## 反馈循环限制

每个 proposal 必须携带系统生成的 `causal_context`。AI 引发的社会事件再次触发 AI 时，沿用同一 `chain_id` 并将 `depth + 1`。

```text
最大 causal depth 为 4；超过时不再调度 AI。
每深入一层，允许的 pressure delta 和 rumor intensity 乘以 0.5，并按 0.01 精度向 0 截断；结果为 0 时以 causal_limit_reached 拒绝，不再产生下游触发。
同一群体、action_type、target 的冷却为 60 游戏分钟。
同一 NPC 的环境型 action_type + target 冷却为 10 游戏分钟。
同一 rumor 在同一 social_group 内 6 游戏小时内最多接受一次，最大传播深度为 3。
AI 对同一 settlement + pressure_key 在连续 24 游戏小时内造成的累计绝对变化不得超过 0.20。
P0 阈值档位只有 normal（开启 0.70、关闭 0.60）和 emergency（开启 0.90、关闭 0.80）；每条 action policy 必须选择一个档位，禁止自定义阈值或在同一阈值反复开关。
proposal 审计事件、reservation 事件和 KnowledgeCreated / KnowledgeUpdated 不得默认触发同链 AI。
```

这些限制由 scheduler、validator 和 resolver 使用 system ledger 与 EventLog 计算，不能让 LLM 自报 causal depth、冷却或累计变化。

## NPC 升降级机制

为了避免 AI 成本失控，NPC 必须支持升降级。

升级条件：

```text
玩家主动交谈。
玩家多次接触。
NPC 持有关键线索。
NPC 与玩家建立交易、冲突、救助、庇护或追踪关系。
NPC 出现在当前关键事件里。
```

升级结果：

```text
从背景群体成员变成 Named NPC。
生成 NPCState。
记录群体来源。
建立短期记忆摘要。
加入近身个体代理调度。
```

降级条件：

```text
长期远离玩家。
事件重要性结束。
不再参与当前目标。
没有持续关系。
```

降级结果：

```text
保留摘要记忆。
移出个体代理调度。
回归所属群体。
必要时保留可重新激活的 npc_id。
```

## 数据流

整体数据流：

```text
已提交的 AuthoritativeWorldState / EventLog
-> AISocialScheduler
-> AIDecisionTick
-> AgentObservationBuilder
-> AgentObservationSnapshot
-> LLMDecisionAdapter
-> AIProposalRecorder
-> GroupDecisionProposal / NPCActionProposal
-> AIProposalValidator
-> AIProposalConflictResolver / ProposalResourceReservation
-> AIProposalAuditWriter（提交 system_ledger 变化）
-> SocialActionResolver
-> StateTransition
-> EventLog
-> KnowledgePropagation
-> Space / UI / Narration Projection
```

AI 只能处于 Proposal 层：

```text
AI Proposal 可以被接受、在闭合范围内调整、拒绝或过期。
只有 Resolver 输出的事件才是真实世界变化。
Proposal、decision tick 和 reservation 只进入 system_ledger，不进入 world_facts 或 knowledge_facts。
```

## 与地点和物品规则的关系

地点/空间规则负责回答：

```text
NPC 在哪里？
玩家能不能接触这个 NPC？
某个群体影响哪个 Region / Chunk / Site？
社会事件影响哪些地点？
```

物品规则负责回答：

```text
NPC 能不能交出某个物品？
交易物品是否真实存在？
货币是否足够？
权益、钥匙、容器、食物是否写入 WorldObject 或玩家状态？
```

AI 不能绕过这两套规则。

例如：

```text
AI 可以提出“店主愿意给玩家房间”。
Resolver 必须检查房间、钥匙、价格、住宿权益是否存在并可用。
通过后才扣钱、发钥匙、写入住宿状态。
```

## 与知识规则的关系

AI 不能直接读取完整 EventLog、OriginEvent、SocialGroupState、NamedNPCState 或隐藏 WorldState。每次调用 AI 前，系统必须先为对应主体生成 `AgentObservationSnapshot`。调度器和 snapshot builder 可以读取权威状态，但传给 LLM 的内容只能来自 snapshot。

规则：

```text
群体心智读取群体可知的 KnowledgeState / RumorState / SecretState。
个体代理读取 NPC 可知的 KnowledgeState / DiscoveryState / SecretState。
OriginEvent 只有在主体存在对应 KnowledgeState 时才能进入 snapshot。
EventLogEntry 只有在主体存在对应 KnowledgeState 时才能进入 snapshot。
隐藏对象、未发现证据、官方秘密和玩家私密行动必须被 redacted。
```

AI 输出不能直接创建知识状态。流言、透露秘密、误导玩家、传播消息等 proposal 必须由 resolver 接受后，才能通过 KnowledgePropagation 写入 `KnowledgeState`、`RumorState` 或 `SecretState`。

## 新版本方向

新版本可以把 AI 使用目标定义为：

```text
AI 驱动的社会心智模拟。
世界底层规则确定，社会判断和个体反应由 AI 根据世界状态生成提案。
玩家的选择会改变群体意识、个体关系和未来世界事件。
```

这比“AI 写旁白”更符合 AI 原生方向，因为没有 AI，群体意识和个体行为的动态生成就无法成立。

## 第一阶段建议

第一阶段只实现本文件定义的单步社会行动协议，不做长期计划或完整社会模拟。

建议范围：

```text
2 到 3 个 SocialGroup。
2 到 4 个 Named NPC。
群体心智只使用 GroupDecisionProposal P0 action_type。
个体代理只使用 NPCActionProposal P0 action_type。
每个主体每个 decision tick 最多结算一个 proposal。
```

第一阶段必须验证：

```text
AI 输出不会直接改 WorldState。
AI 输入不会包含主体未知事实。
群体决策能转成 EventLog。
群体决策能按规则转成 KnowledgeState / RumorState。
个体行为能经过 Validator。
旧 revision、过期 proposal 和重复重试不会重复改变状态。
冲突 proposal 按固定顺序处理，不会重复承诺同一资源。
AI 反馈链在 depth、冷却、传播和累计变化上存在硬上限。
状态变化能被 UI 和 DM 明确反馈。
玩家行为能改变随后的群体和个体反应。
```

## P0 实现任务与测试

开发任务：

1. 实现 `AIDecisionTick`、`AIProposalEnvelope`、`GroupDecisionProposal`、`NPCActionProposal` 和 `ProposalResourceReservation` schema。
2. 实现 `AISocialScheduler` 的事件触发、周期触发、冷却和去重。
3. 扩展 `AgentObservationBuilder`，在 snapshot 中下发 action schema 和可引用目标。
4. 实现 `AIProposalRecorder` 和 `AIProposalAuditWriter`，由系统补齐 proposal 元数据、拒绝 LLM 伪造字段并原子记录 ledger 事件。
5. 实现 action policy registry、`AIProposalValidator`、冲突键计算和确定性排序。
6. 实现 reservation 的创建、消费、释放和过期事务。
7. 实现 P0 action_type 对应的确定性 resolver、SocialFallbackResolver 和 EventLog 写入。
8. 实现 causal depth、冷却、衰减、滞回和累计变化上限。
9. 实现 proposal、reservation 和 resolution 的 replay 与存档恢复。

必须通过的测试：

```text
test_group_and_npc_proposals_share_ai_proposal_envelope
test_each_p0_action_type_has_exactly_one_action_policy
test_action_policy_references_resolve_and_join_rule_bundle_hash
test_llm_cannot_supply_system_owned_proposal_fields
test_proposal_rejects_unknown_action_type_target_kind_and_argument
test_proposal_rejects_subject_revision_mismatch
test_proposal_rejects_changed_read_set_hash
test_proposal_rejects_expired_game_time
test_proposal_rejects_target_not_visible_in_snapshot
test_proposal_rejects_hidden_knowledge_reference
test_duplicate_idempotency_key_returns_existing_resolution
test_one_decision_slot_resolves_at_most_once
test_invalid_ai_output_retries_once_then_uses_trigger_fallback
test_fallback_cannot_change_attitude_pressure_knowledge_or_inventory
test_decision_tick_conflicts_use_deterministic_order
test_resource_reservation_prevents_double_commit
test_rejected_or_expired_proposal_releases_reservation
test_partial_acceptance_only_changes_pressure_or_price_modifier
test_partial_acceptance_preserves_requested_and_applied_action
test_social_pressure_delta_and_daily_cap_are_enforced
test_attitude_change_requires_registered_transition_edge
test_ai_causal_depth_stops_after_four
test_ai_chain_intensity_decays_by_half_per_depth
test_ai_audit_events_do_not_retrigger_scheduler
test_accepted_rumor_creates_knowledge_propagation_input_not_knowledge_directly
test_resolved_proposal_writes_event_log_before_projection
test_rejected_proposal_does_not_change_world_or_knowledge_facts
```

P1 才处理：

```text
GoalState、PlanState、PlanStep 和跨地点长期计划。
NPC 升降级阈值自动调优。
记忆摘要压缩策略和 token 预算优化。
多聚落政治、组织战争和完整供需经济。
```

## 架构决策

1. 世界底层运行规则由确定性系统负责。
2. AI 负责群体心智和近身个体代理的判断提案。
3. 大量普通 NPC 不接 AI 个体模拟。
4. 群体心智负责世界社会气候。
5. 个体代理负责玩家眼前的对话和行为反应。
6. AI proposal 不能直接修改 `WorldState`。
7. 任何 AI 影响必须经过 Validator 和 Resolver。
8. 最终事实以 EventLog 和 Authoritative WorldState 为准。
9. P0 proposal 只表达一个可立即结算的单步行动，不承载长期计划。
10. LLM 只拥有 action payload 字段；ID、revision、sequence、优先级、冲突键和资源预留全部由系统生成。
11. GroupDecisionProposal 与 NPCActionProposal 共用 AIProposalEnvelope。
12. proposal、decision tick 和 reservation 存入 system_ledger，不属于世界事实或主体知识。
13. 同一 decision slot 最多结算一次，所有冲突和资源竞争必须确定性处理。
14. AI 反馈链必须受因果深度、冷却、衰减、滞回和累计变化上限约束。
