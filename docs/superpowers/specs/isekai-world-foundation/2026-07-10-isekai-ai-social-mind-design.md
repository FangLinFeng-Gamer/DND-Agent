# 异世界模式 AI 社会心智设计

## 背景

地点/空间规则和物品规则已经作为底层世界逻辑确定：世界由 `World -> Region -> WorldChunk -> Site -> LocationNode -> Zone -> WorldObject` 组成，物体、地点、通行、资源和状态变化都必须进入权威 `WorldState`，并由确定性规则结算。

这意味着本模式不应该走“AI 无限叙事，讲到哪里算哪里”的路线。AI 可以生成世界内容和角色反应，但不能直接让叙事成为事实。世界运行规则必须写死，AI 的职责是为世界中有心智的部分提供判断、倾向、对话和决策提案。

本设计只确定新版本方向，不定义完整实现细节。具体字段、调度频率、提示词、数值影响和测试用例后续单独讨论。

## 设计目标

- 让 AI 成为世界社会变化的核心机制，而不是只做意图识别和旁白。
- 避免给世界里每个 NPC 都接入 AI，控制成本和状态复杂度。
- 用“群体心智”模拟大量 NPC 的共同意识、利益、恐惧、偏见和行动倾向。
- 对玩家近距离接触、剧情关键或长期互动的 NPC，使用更细粒度的个体代理模拟。
- 所有 AI 输出都必须是 proposal，不能直接修改 `WorldState`。
- AI 造成的影响必须经过 Validator 和 Deterministic Resolver，最终写入 EventLog。

## 非目标

- 不实现每个 NPC 每回合独立思考。
- 不让 AI 直接移动 NPC、扣钱、发物品、改变地点、生成最终奖励或修改资源。
- 不让 AI 自由改写地点/空间/物品底层规则。
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

输入：

```text
当前 WorldState 摘要
群体状态
最近 EventLog
玩家公开行为
资源压力
地点/时间/风险
其他群体变化
```

输出不是最终事实，而是群体决策提案：

```json
{
  "group_id": "graystone_town_residents",
  "trigger_event_ids": ["event_player_returned_at_night"],
  "interpretation": "外乡人的夜间行动让本地居民感到不安。",
  "proposed_decisions": [
    {
      "type": "spread_rumor",
      "scope": "graystone_town",
      "intensity": 1,
      "target_actor_id": "player"
    },
    {
      "type": "increase_social_pressure",
      "scope": "old_furnace_inn",
      "intensity": 1
    }
  ],
  "confidence": 0.78
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

输入：

```text
NPCState
NPC 记忆摘要
当前空间投影
玩家最近行为
所属群体心智结果
可执行动作集合
当前规则约束
```

输出为 NPC 行为提案：

```json
{
  "npc_id": "innkeeper_01",
  "intent": "offer_room_with_higher_price",
  "reasoning_summary": "玩家是外乡人，且宵禁临近，店主认为风险上升。",
  "dialogue_style": "戒备、谨慎、带试探",
  "proposed_actions": [
    {
      "type": "offer_trade",
      "target_actor_id": "player",
      "terms": {
        "room_price_copper": 5
      }
    }
  ],
  "confidence": 0.82
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
WorldState
-> SocialGroupState / NPCState / EventLog
-> GroupMind AI Proposal
-> GroupDecision Validator
-> SocialWorld Resolver
-> EventLog
-> Space / UI / Narration Projection

Nearby Named NPC
-> NPCMind AI Proposal
-> NPCAction Validator
-> NPC Resolver
-> EventLog
-> Space / UI / Narration Projection
```

AI 只能处于 Proposal 层：

```text
AI Proposal 可以被接受、降级、改写或拒绝。
只有 Resolver 输出的事件才是真实世界变化。
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

## 新版本方向

新版本可以把 AI 使用目标定义为：

```text
AI 驱动的社会心智模拟。
世界底层规则确定，社会判断和个体反应由 AI 根据世界状态生成提案。
玩家的选择会改变群体意识、个体关系和未来世界事件。
```

这比“AI 写旁白”更符合 AI 原生方向，因为没有 AI，群体意识和个体行为的动态生成就无法成立。

## 第一阶段建议

第一阶段只做方向验证，不做完整社会模拟。

建议范围：

```text
2 到 3 个 SocialGroup。
2 到 4 个 Named NPC。
群体心智只影响价格、流言、盘问、庇护意愿四类后果。
个体代理只影响对话、交易报价、是否透露线索、是否拒绝服务。
```

第一阶段必须验证：

```text
AI 输出不会直接改 WorldState。
群体决策能转成 EventLog。
个体行为能经过 Validator。
状态变化能被 UI 和 DM 明确反馈。
玩家行为能改变后续群体和个体反应。
```

## 后续需要讨论的具体问题

后续设计需要逐项确定：

1. `SocialGroupState` 的最小字段。
2. `NPCState` 的最小字段。
3. 群体心智的触发频率。
4. 个体代理的触发条件。
5. AI proposal 的统一 JSON schema。
6. Validator 允许哪些社会后果。
7. 群体影响如何映射到价格、服务、巡逻、流言和态度。
8. NPC 升级和降级的阈值。
9. 记忆摘要如何压缩和保留。
10. 哪些状态进入 UI，哪些只进入 DM 投影。

## 架构决策

1. 世界底层运行规则由确定性系统负责。
2. AI 负责群体心智和近身个体代理的判断提案。
3. 大量普通 NPC 不接 AI 个体模拟。
4. 群体心智负责世界社会气候。
5. 个体代理负责玩家眼前的对话和行为反应。
6. AI proposal 不能直接修改 `WorldState`。
7. 任何 AI 影响必须经过 Validator 和 Resolver。
8. 最终事实以 EventLog 和 Authoritative WorldState 为准。
