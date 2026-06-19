# World State Progression Design

## 目标

为每一局冒险增加独立的世界状态推进系统，让世界不会停下来等待玩家推进主线。玩家进行会消耗时间、制造风险或改变局势的角色行动时，剧本威胁、NPC 计划、地点状态和社会局势可以推进；玩家只是询问规则、确认状态或澄清信息时，不推进世界状态。

这个系统的核心体验目标是：玩家能感觉到自己可以自由行动，但每个耗时选择都有代价；世界状态变化会被 DM 叙事、NPC 对话、场景描述、任务日志和轻量 UI 明确表现出来。

## 设计原则

- 按角色行动推进，不按玩家消息数量推进。
- 信息询问、规则问题、状态确认不消耗世界时间。
- 模糊行动先给玩家选择：快速处理不推进或少推进，仔细处理可能推进并带来更多收益。
- 世界状态是每局冒险独立状态，不能污染角色模板或其他冒险。
- 后台状态可以精确，前台展示保持沉浸：玩家看到阶段、异象和 NPC 反应，而不是只看到内部计数。
- DM agent 必须区分用户输入、agent 分析和 tool 状态，不能把后台状态当成新的玩家命令。

## 范围

本阶段实现：

- 冒险级 `world_state` 持久化。
- 行动分类器，判断玩家输入是否是世界内行动、规则问题、状态问题、澄清问题或纯对话。
- 世界推进服务，根据行动分类、当前世界状态、剧本快照和 DM 结果推进时钟。
- 默认剧本“月井节的失窃银铃”的主威胁时钟和阶段效果。
- DM prompt 注入世界状态、可见变化、隐藏变化和推进原因。
- DM 回复后保存新的世界状态，并把玩家可感知变化写入场景和世界事件。
- 前端在游戏房间展示轻量“世界局势”模块。
- 同步接口和流式接口都返回最新世界状态。

本阶段不实现：

- 真实时间倒计时。
- 多人实时同步或 WebSocket。
- 完整剧情编辑器里的可视化时钟配置 UI。
- 复杂日历、小时制、天气模拟。
- 自动生成大型支线剧情树。

## 数据模型

新增冒险级世界状态，优先存入 `adventures.world_state_json`，避免第一阶段增加过多表。后续如果需要查询历史阶段，再拆成独立表。

`world_state` 结构：

```json
{
  "turn_count": 0,
  "phase": "festival_evening",
  "phase_label": "节庆黄昏",
  "threat_clocks": [
    {
      "id": "moonwell_curse",
      "label": "月井危机",
      "value": 0,
      "max": 6,
      "visible": true,
      "severity": "calm"
    }
  ],
  "pressure_clocks": [
    {
      "id": "village_suspicion",
      "label": "村民怀疑",
      "value": 0,
      "max": 4,
      "visible": true,
      "severity": "low"
    },
    {
      "id": "guard_alert",
      "label": "巡逻警觉",
      "value": 0,
      "max": 4,
      "visible": false,
      "severity": "low"
    }
  ],
  "npc_states": {
    "村长玛拉": {
      "location": "月井旁",
      "attitude": "anxious",
      "agenda": "维持秩序并找回银铃"
    }
  },
  "location_states": {
    "柳溪村广场": {
      "mood": "uneasy_festival",
      "details": ["灯笼仍亮着", "村民压低声音议论月井"]
    }
  },
  "visible_events": [],
  "hidden_events": [],
  "last_advance": {
    "advanced": false,
    "reason": "adventure_start",
    "time_cost": 0,
    "affected_clocks": []
  }
}
```

`visible_events` 是已经发生且玩家可以直接感知的变化。`pending_visible_events` 是本次行动导致、应在当前 DM 回复中表现的变化。`hidden_events` 是 NPC 或威胁在幕后发生的变化，只能影响后续场景，不应直接泄露。

## 行动分类

每次玩家输入先生成 `ActionClassification`，再决定是否推进世界状态。

分类结果：

```json
{
  "message_type": "in_world_action",
  "time_cost": 1,
  "risk_level": "medium",
  "advance_world": true,
  "needs_clarification": false,
  "reason": "角色潜入铁匠铺并搜查后院，会消耗时间并制造被发现风险。"
}
```

`message_type` 可选值：

- `status_question`：询问角色、物品、HP、任务、当前状态。
- `rule_question`：询问规则、检定、系统解释。
- `clarification`：询问刚才发生了什么、可见选项、地点出口。
- `table_talk`：非角色行动的玩家闲聊或元讨论。
- `in_world_dialogue`：角色在当前场景内短对话。
- `in_world_action`：角色移动、调查、潜入、偷窃、交易、战斗准备、等待、休息等行动。
- `ambiguous_action`：可能是快速查看，也可能是耗时调查，需要 DM 给出选择。

推进规则：

- `status_question`、`rule_question`、`clarification`、`table_talk` 不推进。
- `in_world_dialogue` 默认不推进，但长时间交涉、反复讨价还价或社交失败可以推进压力时钟。
- `ambiguous_action` 不立即推进。DM 应回复一个选择点，例如“快速扫视不花太多时间，仔细搜查可能找到更多东西但会推进时间”。
- `in_world_action` 根据时间成本和风险推进一个或多个时钟。

行动分类第一版使用确定性规则加 LLM 结构化输出的混合方式：

1. 确定性规则先识别明显的状态/规则/澄清问题，避免误推进。
2. 其余输入交给 `world_progression_agent` 产生结构化分类。
3. 结构化输出失败时保守处理：不推进，并让 DM 给出澄清选择。

## 世界推进

新增 `WorldStateService`，职责是读取、初始化、推进和保存每局世界状态。

核心方法：

- `initialize_for_adventure(adventure_id, story_snapshot)`：创建初始世界状态。
- `get(adventure_id)`：读取当前世界状态。
- `classify_action(adventure, scene, party, player_input, context)`：返回行动分类。
- `preview_advance(world_state, classification, scene)`：计算本次行动的待提交世界变化，供 DM 在当前回复中叙事。
- `commit_advance(adventure_id, pending_delta, dm_result)`：校验并保存时钟、NPC 状态和地点状态。
- `public_view(world_state)`：返回前端和 DM 可展示的玩家可见状态。

推进算法：

1. 从当前 `world_state` 和剧本快照加载可用时钟。
2. 根据 `classification` 先生成 `pending_world_delta`，包括待推进的时钟、阶段变化、可见事件、隐藏事件和遭遇触发候选。
3. 将当前 `world_state` 与 `pending_world_delta` 一起放入 DM tool context，让本次回复能表现“世界刚刚发生了什么”。
4. DM 输出后，`commit_advance` 根据已确认的分类、pending delta 和 DM 结构化结果保存最终状态。
5. 如果阶段变化触发遭遇，将触发信息交给现有遭遇/战斗流程处理。

这样玩家在同一条 DM 回复中就能感知行动代价。例如玩家偷完装备再翻墙，回复里可以立即出现“广场方向传来尖叫，节庆音乐停止”，而不是等到下一次输入。

主威胁不是每次都推进同样幅度。默认规则：

- `time_cost = 0`：不推进。
- `time_cost = 1`：普通耗时行动，主威胁 +1 或压力时钟 +1。
- `time_cost = 2`：等待、长时间搜索、休息、绕远路，主威胁 +2。
- 高风险失败：相关压力时钟 +1，例如 `guard_alert` 或 `village_suspicion`。
- 主线有效行动：可以降低、冻结或转移威胁，而不是一律推进。

## 默认剧本阶段

“月井节的失窃银铃”第一版使用 `moonwell_curse` 作为主威胁时钟，范围 0/6。

- 0/6 `festival_evening`：节庆仍在维持，村民不安但克制。
- 1/6 `uneasy_omens`：井边低语、牲畜拒水，NPC 更焦虑。
- 2/6 `public_fear`：村民聚集到月井旁，流言开始扩散。
- 3/6 `festival_panic`：节庆混乱，NPC 开始互相怀疑，守夜人巡逻加强。
- 4/6 `curse_spreads`：井水异象扩散到街巷，旧磨坊或井下线索变得危险。
- 5/6 `seal_breaking`：封印接近破裂，关键 NPC 采取极端行动。
- 6/6 `breach`：危机爆发，触发强制危机场景或高难度遭遇。

阶段影响必须进入场景和 NPC 对话。例如 `festival_panic` 阶段：

- 广场音乐停止，摊主收摊，村民围在月井旁争吵。
- 外乡人更容易被怀疑。
- 守夜人布伦巡逻路线覆盖铁匠铺和旧磨坊道路。
- 与 NPC 对话时，他们不应像初始阶段那样平静。

## DM 上下文

`build_dm_messages` 增加 `world_state` 和 `action_classification` 输入，并放入 `tool_context`：

```json
{
  "tool_context": {
    "world_state": {
      "phase": "festival_panic",
      "phase_label": "节庆混乱",
      "public_clocks": [
        {"label": "月井危机", "value": 3, "max": 6, "severity": "danger"}
      ],
      "visible_events": [
        "广场音乐停止，村民围在月井旁争吵。"
      ],
      "pending_visible_events": [
        "守夜人布伦带人离开月井旁，开始沿铁匠铺方向巡逻。"
      ],
      "location_states": {},
      "npc_states": {}
    },
    "action_classification": {
      "message_type": "in_world_action",
      "advance_world": true,
      "time_cost": 1
    }
  }
}
```

Prompt 规则：

- `world_state` 是 tool 状态，不是玩家新命令。
- `visible_events` 可以直接表现给玩家。
- `pending_visible_events` 是本次行动刚导致的玩家可感知变化，必须自然融入当前回复。
- `hidden_events` 只能影响 NPC 行为和后续局势，不能直接说出。
- DM 必须让当前场景、NPC 语气和可选行动符合当前阶段。
- 如果 `needs_clarification` 为 true，DM 不推进场景结算，只给玩家选择快速/仔细/放弃等行动方式。

DM 输出 schema 增加可选 `world_state_hints`：

```json
{
  "world_state_hints": {
    "action_tags": ["theft", "trespass"],
    "main_threat_reduced": false,
    "prevented_advance_reason": "",
    "suggested_visible_events": []
  }
}
```

这些 hints 不能直接写库，必须经过 `WorldStateService.advance` 校验。

## API 和响应

现有冒险详情响应增加 `world_state` 的玩家可见视图。

受影响接口：

- `GET /api/adventures/{id}` 返回 `world_state`。
- `POST /api/adventures/{id}/messages` 返回 `world_state`。
- `POST /api/adventures/{id}/messages/stream` 的 final event 返回 `world_state`。

内部保存仍由 DMService 统一事务流程完成：

1. 保存玩家消息。
2. 分类玩家输入。
3. 根据分类预计算 `pending_world_delta`。
4. 根据当前状态和 pending delta 构建 DM 上下文。
5. 调用模型或模板 fallback。
6. 校验并提交世界状态变化。
7. 保存场景、世界事件、角色更新和 DM 消息。
8. 返回最新 adventure、scene、combat_state、world_state。

如果模型调用失败，模板 fallback 也必须使用世界状态生成基本叙事，至少表现当前阶段和最近可见变化。

## 前端

游戏房间增加轻量“世界局势”展示，优先放在现有房间状态区域或任务日志上方，避免抢占聊天主体。

展示内容：

- 当前阶段：如“节庆混乱”。
- 公开时钟：如“月井危机 3/6”，也可以显示为“平静 / 不安 / 混乱 / 失控”。
- 最近变化：最多 3 条可见事件。
- 当前地点影响：如果有与当前场景匹配的状态，展示一句简短提示。

前端不展示：

- 隐藏事件。
- NPC 完整计划。
- 内部分类器 JSON。

当世界状态更新时，前端刷新：

- 房间状态条。
- 任务日志。
- 当前场景文本。
- DM 聊天消息。

## 错误处理

- 行动分类失败：不推进世界状态，DM 询问玩家行动意图。
- world_state 缺失：根据 adventure 的 story_snapshot 重新初始化。
- story_snapshot 没有时钟定义：使用通用世界状态，只记录 `turn_count` 和最近变化，不强制推进主威胁。
- 推进后超过最大值：钳制到最大值，并触发终局阶段一次。
- 重复提交同一条消息：通过消息 ID 或 action ID 避免重复推进。
- 流式输出中断：只有 final commit 成功后才保存世界状态；中途 delta 不改变状态。

## 测试

后端测试：

- 新冒险会初始化独立世界状态。
- 状态问题不推进时钟，例如“我现在有什么装备？”。
- 规则问题不推进时钟，例如“这个需要掷什么骰？”。
- 明确耗时行动推进世界状态，例如“我去铁匠铺搜查后院”。
- 模糊行动不推进，并要求 DM 给出快速/仔细选择。
- 默认剧本在 3/6 进入“节庆混乱”，场景和 NPC 上下文包含该阶段效果。
- 每局冒险世界状态隔离。
- 流式接口 final 返回最新 world_state。
- 模型失败时 fallback 不推进或只按已确认分类推进一次。
- 重复处理同一 action 不会重复推进。

前端测试：

- 游戏房间存在世界局势模块。
- adventure payload 中的 `world_state` 会渲染阶段、公开时钟和最近变化。
- 隐藏事件不会出现在 DOM 中。
- 流式 final 更新会刷新世界局势模块。

浏览器验证：

- 打开一局默认剧本。
- 连续做耗时支线行动，确认世界局势阶段推进。
- 问装备/规则/当前位置，确认世界局势不推进。
- 推进到“节庆混乱”后，与 NPC 对话和场景描述符合混乱状态。

## 实施顺序

1. 添加 world state schema、数据库列和 AdventureOut 字段。
2. 实现 `WorldStateService` 初始化、读取、保存和 public view。
3. 实现行动分类器，先覆盖确定性不推进类型，再接入结构化 LLM 分类。
4. 实现默认剧本阶段定义和推进规则。
5. 将 world_state 和 action_classification 注入 DM prompt。
6. 在 DMService 同步和流式流程中接入分类、推进和 final payload。
7. 前端增加世界局势模块并处理响应更新。
8. 补齐测试和浏览器验证。

## 验收标准

- 玩家问状态、问规则、问澄清信息时，世界状态不推进。
- 玩家执行移动、搜查、偷窃、等待、休息等耗时行动时，世界状态按规则推进。
- 世界状态推进后，玩家能在 UI 和 DM 叙事中感知阶段变化。
- NPC 对话和场景描述会遵守当前世界阶段。
- 默认剧本能从节庆黄昏推进到节庆混乱，并改变村民和守夜人的行为。
- 每局冒险的世界状态互相隔离。
- 全量测试通过。
