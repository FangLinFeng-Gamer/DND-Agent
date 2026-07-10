# 异世界结构化可玩性闭环设计

## 背景

异世界模式已经具备独立开局、随机角色、生存数值、时间推进、世界事件、流式 DM 回复和基础资源惩罚。当前主要问题不再是“能不能讲故事”，而是“能不能稳定游玩”：

- 玩家输入的行动意图会被误分类，例如采集被当成闲聊，寻找庇护被当成直接睡觉。
- DM 文本里出现的物品、NPC、地点和风险没有稳定进入真实状态。
- 玩家看见了水桶、伐木工、猎犬、猎网等内容，但系统并不知道这些是可互动对象。
- 压力目标仍偏展示，不像可以推进和反馈的压力时钟。
- 前端缺少“现在能互动什么、可以尝试什么”的即时提示。

本轮目标是把异世界模式从“带数值面板的自由叙事”推进到“玩家选择、状态变化、风险反馈、下一步选择”能闭环的可玩版本。

## 现有代码现实

- `IsekaiTimeService.classify_action()` 仍主要依赖关键词，未知输入默认 `table_talk`，但缺少 `gather`、`seek_shelter`、`manage_inventory`。
- `SceneState` 目前只有 `important_objects: list[str]` 和 `npcs: list[str]`，不能表达对象 ID、状态、可做动作、风险和 NPC 记忆。
- 异世界 DM 模型输出目前只支持 `narration` 和 `scene_update`，没有正式的 `interactables`、`suggested_actions`、`state_changes`。
- `IsekaiResourceService` 已经负责吃喝消耗、高压力扣 HP 和状态效果。新设计应复用它，而不是另起一套资源系统。
- 前端异世界聊天消息下方目前没有展示本轮可互动内容或行动建议。
- `world_state` 已有公开压力目标和调试字段，适合承载冒险本局的 `pressure_clocks`，避免多局共享。

## 目标

1. 重做异世界行动分类，减少误惩罚，补齐采集、寻找庇护和背包管理。
2. 扩展场景状态，让 NPC、物品、地点和风险以结构化方式进入本局冒险状态。
3. 让 DM 输出结构化 JSON，后端只接受校验后的状态变更。
4. 将模型确认的获得、丢弃、消耗物品同步到异世界角色背包。
5. 将模型确认的 NPC 变化同步到当前场景 NPC 状态。
6. 前端在 DM 回复下方展示可互动内容和可尝试行动，帮助玩家知道下一步能做什么。
7. 将压力目标升级为压力时钟，按时间和风险推进，并向玩家可见。
8. 保持 DND 模式现有数据结构和游玩流程不变。

## 非目标

- 不引入 LLM 行动分类器作为主路径。本轮先用确定性分类修复误判，后续可评估模型辅助分类。
- 不实现完整战斗系统。
- 不实现复杂物品数据库。异世界背包仍以中文物品名字符串为主，先保证增删一致。
- 不让模型直接写数据库。模型只能提出 `state_changes`，后端校验后应用。
- 不要求玩家只能点击建议行动。建议只填入输入框，玩家仍可自由修改或输入其他行动。

## 行动分类

新增或修正 `action_type`：

- `gather`：摘、采、捡、拿起、收集、采集具体物品。
- `seek_shelter`：找地方过夜、寻找庇护、找落脚点、找住处。
- `manage_inventory`：扔掉、丢弃、收起、整理、拿出。
- `sleep`：只在明确“睡觉”“在这里过夜”“休息到天亮”“睡到天亮”时触发。

分类顺序要避免误伤：

1. 状态、背包、位置、时间、规则、UI 问题先判为不推进时间。
2. 当前场景存在 NPC 时，“你是谁”“你是什么种族”“你这里有什么规矩”等优先判为 `short_dialogue`。
3. `seek_shelter` 必须早于 `sleep`，因为“找个可以过夜的地方”不是实际入睡。
4. `gather` 必须覆盖“摘点红浆果”“捡起碎片”“拿起猎网”。
5. 模糊短句仍保守判为 `table_talk`，不推进时间。

默认时间成本：

- `gather`: 30 分钟，推进饥渴和疲劳，可触发采集风险。
- `seek_shelter`: 45 分钟，推进时间和压力，但不直接跳到次日。
- `manage_inventory`: 5 分钟，通常推进少量时间；如果只是查看背包则仍是 `status_check`。
- `sleep`: 从当前时间推进到次日清晨，前提是玩家明确开始睡眠。

## 场景结构

在 `SceneState` 中新增字段，同时保留旧字段兼容 DND：

```json
{
  "interactables": [
    {
      "id": "lumberjack_01",
      "type": "npc",
      "name": "戒备的伐木工",
      "state": "戒备",
      "affordances": ["交涉", "请求借宿", "提出帮忙"],
      "risk": "态度恶化可能引来猎犬"
    }
  ],
  "suggested_actions": [
    "向伐木工解释自己只是想找地方避夜",
    "观察猎犬和营地出入口",
    "提出用劳力交换一晚干燥角落"
  ],
  "npc_states": [
    {
      "id": "lumberjack_01",
      "name": "伐木工",
      "attitude": "suspicious",
      "trust": 20,
      "known_facts": ["玩家是外来者", "玩家携带短弓"]
    }
  ]
}
```

字段规则：

- `interactables` 是玩家可感知、可尝试互动的对象。
- `suggested_actions` 是提示，不是固定选项。
- `npc_states` 是系统记忆，用于后续对话连续性。
- 旧的 `important_objects` 和 `npcs` 继续存在，并可由新字段派生或同步，避免旧前端和测试断裂。
- 所有新增字段都属于本局 `adventure.current_scene`，禁止跨局共享。

## DM 结构化输出

异世界 DM prompt 要求模型只输出 JSON：

```json
{
  "narration": "你伸手摘下几颗红浆果，果皮像温热蜡质一样贴在指尖...",
  "scene_update": {
    "location": "灰橡森林东缘",
    "environment": "潮湿林地里有红浆果藤、断木和远处营火烟线。"
  },
  "interactables": [
    {
      "id": "red_berries_01",
      "type": "item",
      "name": "红浆果",
      "state": "少量成熟",
      "affordances": ["采集", "辨认是否有毒", "留下标记"],
      "risk": "未辨认前食用可能中毒"
    }
  ],
  "suggested_actions": [
    "先观察红浆果是否有虫咬痕",
    "采集少量红浆果放进背包",
    "沿烟线寻找可能的营地"
  ],
  "state_changes": {
    "add_items": ["红浆果 x1"],
    "remove_items": [],
    "npc_updates": [],
    "pressure_updates": []
  }
}
```

后端解析规则：

- 非 JSON 或字段缺失时，保留叙事 fallback，但不应用状态变更。
- `narration` 必须是字符串。
- `scene_update` 只能接受 `location`、`environment`、`important_objects`、`current_objective` 和新增场景字段。
- `interactables` 只接受 `id`、`type`、`name`、`state`、`affordances`、`risk`，并限制数量和字符串长度。
- `suggested_actions` 限制 3 到 5 条，过长截断。
- `state_changes` 只接受白名单：`add_items`、`remove_items`、`npc_updates`、`pressure_updates`。
- 后端应用状态变化后，把实际应用结果写入 DM message metadata，便于前端和调试查看。

## 背包同步

背包同步分两层：

1. 规则层：继续由 `IsekaiResourceService` 处理吃喝消耗和生存惩罚。
2. 模型提案层：当 `state_changes` 明确表示获得或丢弃物品，后端校验并应用到 `isekai_characters.inventory_json`。

规则：

- `add_items` 中的空字符串、过长字符串和明显系统字段会被丢弃。
- 重复物品可以先作为字符串追加；若已有同名 `xN` 项，允许合并数量。
- `remove_items` 按规范化名称匹配，移除一个对应物品或减少 `xN` 数量。
- 如果模型叙事说获得物品但 `state_changes.add_items` 为空，后端不应猜测入包；后续可以在 prompt 中要求模型补齐。
- 如果玩家明确“拿起猎网和燧石碎片”，验收要求模型输出并后端应用 `猎网` 和 `燧石碎片`。
- 如果玩家“扔掉浆果”，验收要求背包不再持有该浆果。

## NPC 状态同步

NPC 通过 `npc_updates` 进入场景状态：

```json
{
  "id": "lumberjack_01",
  "name": "伐木工",
  "attitude": "wary",
  "trust_delta": 10,
  "known_facts": ["玩家主动说明来意"]
}
```

后端应用规则：

- 按 `id` 合并已有 NPC；没有 `id` 时用名称生成稳定 ID。
- `trust` 限制在 0 到 100。
- `attitude` 使用白名单或保留短文本：`hostile`、`suspicious`、`wary`、`neutral`、`helpful`、`friendly`。
- `known_facts` 去重并限制数量。
- 同步更新旧字段 `npcs`，让旧展示仍能看到 NPC 名称。

## 压力时钟

在 `world_state.pressure_clocks` 中保存本局压力时钟：

```json
[
  {
    "id": "sunset",
    "label": "日落倒计时",
    "value": 65,
    "max": 100,
    "trend": "rising",
    "description": "天色越暗，寻找安全落脚点越困难。"
  }
]
```

初始时钟：

- `sunset`: 日落倒计时。
- `outsider_suspicion`: 外来者怀疑。
- `curfew_patrol`: 宵禁巡逻。
- `beast_activity`: 野兽活动。
- `weather_thirst`: 口渴/天气压力。

推进规则：

- 时间推进会增加 `sunset`、夜间相关压力和口渴/天气压力。
- 高风险行动、NPC 态度恶化或明显违反当地规则会增加对应压力。
- `seek_shelter` 成功找到临时庇护时，可以降低夜间风险或暂停部分时钟。
- 所有压力时钟只存在于本局 `world_state`，删除冒险时随冒险删除。

## 前端展示

在异世界 DM 文本下方展示两块：

- 可互动内容：显示 NPC、物品、地点、风险和可做动作。
- 可尝试行动：显示 3 到 5 条自然语言建议。

交互规则：

- 点击建议只把文本填入异世界聊天输入框，不自动发送。
- 展示内容优先使用该 DM 消息 metadata 中的结构化字段；如果没有，则使用当前 `adventure.current_scene` 的字段。
- 不在 DND 房间展示这些异世界专属模块。
- 压力时钟在世界事件/环境信息区域展示，使用进度条或紧凑列表，避免挤压聊天窗口。

## 数据流

1. 玩家发送输入。
2. 后端保存玩家消息。
3. 行动分类得到 `action_type` 和时间成本。
4. 生存规则推进时间、饥渴、疲劳、睡眠、HP 和规则资源消耗。
5. 后端把当前角色、可见生存状态、场景、NPC、可互动对象、压力时钟和最近对话发给模型。
6. 模型返回结构化 JSON。
7. 后端校验并应用 `scene_update`、`state_changes`、`interactables`、`suggested_actions`。
8. 后端保存 DM 消息，metadata 记录实际应用结果。
9. 前端流式展示 narration，最终响应后刷新背包、NPC、场景、压力时钟和 DM 下方提示。

## 错误处理

- 模型 JSON 解析失败：使用 fallback narration，不应用模型状态变更。
- 状态变更非法：跳过非法字段，metadata 记录 `state_change_errors`。
- 模型建议过多或过长：截断到限制范围。
- 模型试图移动非行动回合的位置：沿用已有场景锁定规则，不应用位置变化。
- 前端没有结构化字段：正常只显示文本，不报错。

## 测试计划

行动分类测试：

- `摘点红浆果` -> `gather`，推进时间，不是 `table_talk`。
- `找个可以过夜的地方` -> `seek_shelter`，不是 `sleep`。
- `我在这里睡觉过夜` -> `sleep`。
- `扔掉红浆果` -> `manage_inventory`。

后端状态测试：

- 模型输出 `add_items: ["猎网", "燧石碎片"]` 后，背包出现对应物品。
- 模型输出 `remove_items: ["红浆果"]` 后，背包不再持有红浆果。
- 模型输出伐木工 `npc_updates` 后，`current_scene.npc_states` 出现该 NPC，信任或态度变化被保存。
- 旧字段 `npcs` 与结构化 NPC 名称保持兼容。
- 非法 `state_changes` 不落库，并记录错误。

前端测试：

- 异世界 DM 消息下方渲染可互动内容和可尝试行动。
- 点击建议只填入输入框，不发送请求。
- DND 消息不渲染异世界交互提示。
- 世界事件/环境页显示压力时钟。

验收场景：

- 连续 8 到 10 轮后，玩家始终能知道自己在哪、能互动什么、下一步可做什么。
- 系统不会把“找地方过夜”直接替玩家执行成睡到第二天。
- 背包、NPC、场景、压力和 DM 文本保持一致。
- 生存压力会推进，并且玩家能看到压力时钟变化。
