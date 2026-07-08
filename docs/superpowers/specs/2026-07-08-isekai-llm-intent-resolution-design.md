# 异世界模式 LLM 意图理解与确定性结算设计

## 目标

下一版不再把规则分类作为玩家意图理解主路径。

新的架构目标是：

```text
LLM 负责听懂玩家。
规则系统负责约束世界、校验条件、结算状态、拦截越权。
```

玩家可以输入自然语言、复合动作、否定约束、条件意图。系统先把输入解析为结构化行动计划，再由确定性系统绑定目标、校验条件、计算时间、结算状态，并基于已结算结果生成 DM 文本。

## 非目标

本阶段不做以下内容：

- 不让规则 parser 继续作为主意图分类器。
- 不允许模型直接扣钱、发钥匙、发床位、改任务阶段、改 NPC 关系。
- 不开放模型临时创造 action_type。
- 不在解析失败时强行推进时间或改变状态。
- 不在 P0 地点、经济、时间、权益未稳定前扩多条 P1 任务线。

## 总体流程

```text
玩家输入
-> IsekaiIntentInterpreter 使用 LLM 输出 IntentPlan
-> IsekaiIntentSchema 校验 JSON 与白名单
-> IsekaiActionGrounder 绑定 target_text 到当前场景 target_id
-> IsekaiPreconditionService 检查物理、资源、地点条件
-> IsekaiActionPolicyService 检查动作权限
-> IsekaiTimeCostService 计算细粒度时间
-> IsekaiConsequenceResolver 确定性结算状态
-> IsekaiNarrationComposer 基于结算结果生成 DM 文本
-> 更新 UI 面板和 metadata
```

核心原则：

- LLM 输出的是意图计划，不是最终事实。
- 模型返回的状态变化一律视为 proposal。
- 只有 resolver 和各确定性服务能写入钱、物品、地点、权益、NPC、任务阶段。
- fallback 规则只处理低风险动作，不处理复杂复合动作和关键状态变更。

## 模块设计

### IsekaiIntentInterpreter

新增文件：

```text
backend/src/services/isekai_intent_interpreter.py
```

职责：

- 调用 LLM。
- 把玩家输入解析为 `IntentPlan`。
- 提供 JSON repair 重试。
- 在失败时返回 clarification 或 fallback 候选。

不负责：

- 不绑定真实 target_id。
- 不计算时间。
- 不扣钱。
- 不发物品。
- 不改变地点。
- 不推进任务阶段。

### IsekaiIntentSchema

新增文件：

```text
backend/src/services/isekai_intent_schema.py
```

职责：

- 定义 `IntentPlan`、`IntentStep`、`DeferredStep`。
- 校验 action_type 白名单。
- 校验 steps 数量。
- 校验 constraints、scope、intensity、style。
- 将无效 plan 转为 clarification。

### IsekaiActionGrounder

新增文件：

```text
backend/src/services/isekai_action_grounder.py
```

职责：

- 将 `target_text` 绑定到当前 `SceneState.interactables`。
- 支持 exact match、alias match、affordance match。
- 目标歧义时返回 clarification。
- 目标不存在时允许进入 precondition 阶段，由世界规则给出替代方案。

示例：

```json
{
  "target_text": "马车",
  "target_id": "wagon_01",
  "target_name": "侧翻马车"
}
```

### IsekaiActionPolicyService

新增文件：

```text
backend/src/services/isekai_action_policy.py
```

职责：

- 定义 action_type 权限矩阵。
- 判断某一步是否允许改钱、改物品、改地点、改权益、改任务、改 NPC。
- 拦截模型 proposal 中越权状态变更。

### IsekaiTimeCostService

新增文件：

```text
backend/src/services/isekai_time_cost.py
```

职责：

- 使用 `action_type + scope + intensity + environment_modifiers` 计算时间。
- 替代单纯按 action_type 固定时间的方案。
- 输出玩家可理解的时间解释。

### IsekaiConsequenceResolver

新增或强化文件：

```text
backend/src/services/isekai_action_resolution.py
```

职责：

- 顺序执行 IntentPlan steps。
- 保留已执行步骤结果。
- 当前步骤 blocked 后，后续步骤 marked skipped。
- 汇总时间、资源、风险、奖励、权益、线索、关系、任务状态。
- 输出 NarrationComposer 所需的结构化 facts。

## IntentPlan 结构

LLM 必须只输出 JSON。基础结构如下：

```json
{
  "schema_version": "1.0",
  "raw_text": "喝水，然后小心靠近马车，看看里面但先别翻",
  "requires_clarification": false,
  "clarification_question": "",
  "confidence": "high",
  "steps": [
    {
      "step_id": "s1",
      "action_type": "drink_water",
      "target_text": "水囊",
      "style": "normal",
      "scope": "self",
      "intensity": "quick",
      "constraints": []
    },
    {
      "step_id": "s2",
      "action_type": "approach",
      "target_text": "马车",
      "style": "careful",
      "scope": "local",
      "intensity": "careful",
      "constraints": []
    },
    {
      "step_id": "s3",
      "action_type": "observe",
      "target_text": "车厢内部",
      "style": "careful",
      "scope": "local",
      "intensity": "normal",
      "constraints": ["no_search", "no_loot"]
    }
  ],
  "deferred_steps": []
}
```

硬性限制：

- `steps` 最多 3 个可执行步骤。
- 超过 3 个动作必须放入 `deferred_steps`。
- 不确定目标时返回 `requires_clarification=true`。
- LLM 不允许输出 `add_items`、`remove_money`、`quest_stage=resolved` 这类最终状态。

## action_type 白名单

P0/P1 允许 action_type 固定为：

```text
status_check
table_talk
clarification
drink_water
eat_food
eat_meal
refill_water
observe
search
approach
enter_location
leave_location
travel
short_dialogue
negotiate
purchase
repair
manage_inventory
rest_short
sleep
hide
avoid
force_open
```

处理规则：

- 不在白名单内的 action_type 不得执行。
- schema 层将未知 action_type 转为 `clarification`。
- 不允许模型临时创造新动作，例如 `befriend_owner`、`unlock_quest`、`obtain_key`。
- 这类表达应被解释为已有动作组合，例如 `short_dialogue`、`negotiate`、`purchase`、`repair`。

## 状态权限矩阵

研发必须按矩阵实现，不允许绕过。

```text
purchase:
允许扣钱、发商品、发购买权益。

repair:
允许改变 NPC 态度、解锁折扣、设置任务 flag。
不允许直接扣钱，除非 repair step 中包含明确材料费用且经过 EconomyService。

negotiate:
允许改变报价、NPC 态度。
不允许直接发钥匙、床位、物品。

enter_location / leave_location / travel:
允许改变地点。
不允许扣钱、发奖励、推进任务完成。

observe:
允许发现线索、刷新可互动。
不允许获得物品入包。

search:
允许发现物品、风险、隐藏入口。
是否入包由 resolver 根据目标 affordance 和 action result 判断。

drink_water / eat_food / eat_meal:
允许消耗对应资源，恢复状态。

short_dialogue:
允许轻微 NPC 态度变化、获得信息线索。
不允许扣钱、发钥匙、发床位。

table_talk / status_check / clarification:
不允许改钱、物品、地点、权益、任务阶段、NPC 关系。
```

## 复合动作执行策略

复合动作按 steps 顺序执行。

规则：

- 已执行步骤保留结果。
- 当前步骤失败则标记 `blocked=true`。
- blocked 后的后续步骤标记 `skipped=true`。
- 返回 blocked reason 和 alternatives。

示例：

玩家输入：

```text
喝水，然后进入侧翻车厢，不翻东西。
```

如果车门被压住：

```text
drink_water 执行成功。
enter_location 被阻断。
no_search/no_loot 约束保留在 blocked step 上。
系统给替代方案：从破口观察、撬开木板、绕到车尾。
```

返回结构示例：

```json
{
  "resolved_steps": [
    {
      "step_id": "s1",
      "action_type": "drink_water",
      "status": "executed",
      "time_cost_minutes": 5,
      "resource_changes": ["水囊(3/3) -> 水囊(2/3)"]
    },
    {
      "step_id": "s2",
      "action_type": "enter_location",
      "status": "blocked",
      "blocked_reason": "车门被泥土压住，无法直接进入。",
      "alternatives": ["从破口观察", "撬开木板", "绕到车尾"]
    }
  ],
  "skipped_steps": []
}
```

## fallback 规则

规则 parser 降级为 fallback，只在以下情况使用：

1. LLM 调用失败。
2. LLM JSON 无法修复。
3. LLM 输出 action_type 不在白名单。
4. LLM 置信度为 low 且无法澄清。

fallback 只允许识别低风险动作：

```text
status_check
table_talk
drink_water
eat_food
rest_short
sleep
observe
```

fallback 禁止：

```text
扣钱
发钥匙
发床位
推进任务阶段
改变 NPC 关系
执行复杂复合动作
```

LLM 输出失败处理固定为：

```text
第一次解析失败
-> JSON repair prompt 重试一次
-> 仍失败则返回 clarification
```

返回文案示例：

```text
我没能稳定判断你要先做哪件事。你是想先观察、靠近，还是直接行动？
```

解析失败时不得推进时间或改变状态。

## 时间系统接入

`IntentStep` 必须带：

```text
action_type
scope
intensity
style
environment_modifiers
```

时间计算由 `IsekaiTimeCostService` 负责。

基础参考：

```text
observe + indoor + quick = 1-3 分钟
observe + indoor + careful = 5-10 分钟
repair + indoor + normal = 10-20 分钟
search + indoor + thorough = 20-30 分钟
travel + settlement + normal = 10-20 分钟
travel + wilderness + normal = 60-90 分钟
sleep = 按小时推进到目标时段
```

DM 必须解释时间：

```text
你花了约 15 分钟修好锅把，天色只是暗了一点。
```

## 经济与权益接入

货币内部统一使用铜币：

```text
1 金 = 10 银
1 银 = 10 铜
1 金 = 100 铜
```

真实字段只存：

```json
{
  "currency": {
    "copper_total": 137
  }
}
```

UI 展示换算为：

```text
137 铜 = 1 金 3 银 7 铜
45 铜 = 4 银 5 铜
8 铜 = 8 铜
```

规则：

- 扣钱只允许通过 `IsekaiEconomyService`。
- 发床位、钥匙、住宿有效期只允许通过 `IsekaiEntitlementService` 或 `IsekaiConsequenceResolver`。
- `gold/silver/copper` 只能作为展示，不得作为三份真实来源。
- 异世界初始资产应使用低额铜币或银币，不再直接使用旧的 `gold=13` 作为经济压力来源。

## 地点与目标绑定

地点真实状态应使用结构化层级，旧 `location` 只作为展示兼容字段。

建议结构：

```json
{
  "location_path": {
    "region": "灰石镇",
    "site": "旧炉旅店",
    "sublocation": "前厅",
    "node_id": "inn_front_hall",
    "parent_id": "old_furnace_inn",
    "display_name": "灰石镇 / 旧炉旅店 / 前厅"
  }
}
```

地点改变只能由以下动作触发：

```text
enter_location
leave_location
travel
```

`observe`、`search`、`short_dialogue` 不允许改变当前位置。

## P1 任务线门禁

P1 只能实现一条纵切：

```text
night_wolf_line
```

阶段固定为：

```text
not_started
rumor_heard
night_event_seen
prepared
tracking
resolved
```

规则：

- 同一局内只能存在 `night_wolf_line` 一条 P1 任务线。
- 模型试图创建第二条任务线时，丢弃并记录 `blocked_reason=p1_single_quest_only`。
- 任务阶段只能由 `IsekaiConsequenceResolver` 在条件满足后推进。
- `table_talk`、`status_check`、`clarification` 不允许推进任务阶段。

## 测试要求

必须新增或扩展以下测试。

### LLM 结构化解析测试

输入：

```text
喝水，然后小心靠近马车，看看里面但先别翻。
```

断言：

- steps 顺序为 `drink_water`、`approach`、`observe`。
- observe step 包含 `no_search` 或 `no_loot`。
- approach step style 或 intensity 为 cautious/careful。

### 否定约束测试

输入：

```text
进入车厢但不翻东西。
```

断言：

- action_type 包含 `enter_location`。
- constraints 包含 `no_search` 或 `no_loot`。
- 不产生 search step。

### 状态闸门测试

模拟模型在 observe 中 proposal：

```json
{"add_items": ["房间钥匙"]}
```

断言：

- 物品不进入背包。
- 权益不变化。
- metadata 记录 blocked reason。

### 经济权限测试

断言：

- 只有 `purchase` 可以扣铜币并发购买权益。
- `negotiate` 不能直接发床位。
- 余额不足时返回 `condition_failed`。

### 任务阶段测试

断言：

- 只有 resolver 满足条件后才能推进 `night_wolf_line.stage`。
- 模型直接返回 `stage=resolved` 被拦截。
- 第二条任务线被丢弃。

### fallback 测试

模拟 LLM 失败。

断言：

- fallback 只能执行低风险动作。
- fallback 不得扣钱、发权益、改任务阶段、改 NPC 关系。
- 复杂复合输入返回 clarification。

### 端到端验收

固定流程：

```text
进入旅店
和店主讨价还价
去后厨修锅把
回前厅
支付铜币
获得钥匙和床位
吃炖菜
夜里听见暗夜狼动静
第二天准备追踪
```

每一步检查：

- IntentPlan 是否正确。
- target_id 是否正确。
- 地点是否正确。
- 钱币是否正确。
- 物品、权益、线索是否入账。
- 时间是否合理。
- DM 文本是否基于已结算状态。
- UI 面板是否同步。

## 交付顺序

### 阶段 1：Schema 与 mock 解析

- 新增 `IsekaiIntentSchema`。
- 定义 action_type 白名单。
- 使用 mock LLM 输出完成解析测试。
- 不接入真实状态落库。

### 阶段 2：Interpreter 接入

- 新增 `IsekaiIntentInterpreter`。
- 接入真实 LLM。
- 实现 JSON repair 一次重试。
- 解析失败返回 clarification。
- 只写 metadata，不改状态主流程。

### 阶段 3：Grounder 与 Policy

- 新增 `IsekaiActionGrounder`。
- 新增 `IsekaiActionPolicyService`。
- 实现目标绑定、歧义澄清、权限矩阵。
- 增加状态闸门测试。

### 阶段 4：TimeCost 与 Resolver

- 新增 `IsekaiTimeCostService`。
- 强化 `IsekaiActionResolutionEngine`。
- 实现复合 steps 顺序执行、blocked、skipped、alternatives。
- 接入资源、风险、经济、权益、地点变更。

### 阶段 5：替换主路径

- 修改 `IsekaiSurvivalService.prepare_turn`。
- 主路径改为 LLM IntentPlan。
- 旧 `IsekaiActionParser` 降级为 fallback。
- metadata 输出 intent_plan、resolved_steps、blocked_proposals。

### 阶段 6：P0/P1 验收

- 跑 P0 地点、经济、时间、权益验收。
- P0 不通过，不允许合入 P1 内容。
- P1 只允许实现 `night_wolf_line` 一条纵切。

## 合入规则

任何相关 PR 必须满足：

- 不新增未登记 action_type。
- 不让模型直接写最终状态。
- 不绕过 EconomyService 扣钱。
- 不绕过 EntitlementService 发钥匙、床位。
- 不绕过 Resolver 改任务阶段。
- 不让 observe/search 随意改变地点。
- 不让 fallback 执行高风险状态变更。
- 不在 P0 验收失败时合入 P1 内容扩展。

## 最终结论

异世界模式下一版必须从“规则理解玩家”改为“LLM 理解玩家，系统约束世界”。

规则分类不再是主方案，只保留兜底和安全闸门。所有关键状态，包括地点、钱、物品、钥匙、床位、NPC 态度、任务阶段，都必须由确定性 resolver 写入，不能由模型直接决定。
