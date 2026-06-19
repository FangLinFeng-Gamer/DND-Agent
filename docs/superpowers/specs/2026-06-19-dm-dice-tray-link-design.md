# DM Dice Tray Link Design

## 目标

把现有“命运骰盘”和 DM agent 的检定流程连接起来。DM 判断需要玩家进行能力检定时，不再在后台直接完成掷骰，而是创建一个待处理检定请求。前端在聊天记录中展示这个请求，并使用已有骰盘完成 d20 掷骰。掷骰结果提交回后端后，DM agent 再根据结果继续叙事。

这个改动要解决当前体验割裂：DM 文本说“你需要进行敏捷检定”，但后端已经把结果写进 `metadata.dice_result`。玩家应当看到、执行并承担这次掷骰。

## 设计原则

- DM 负责提出检定，玩家负责掷骰。
- 前端复用现有命运骰盘，不新增第二套骰子视觉系统。
- 后端保存检定请求和结果，不能只存在前端内存里。
- 后端重新计算 modifier、total 和 success，前端只提交原始 d20 点数。
- 一次待检定必须绑定本局冒险、当前角色和触发它的 DM 消息。
- 检定完成前，DM 不应继续自动裁决这个检定的成功或失败。
- 普通闲聊、规则询问、角色状态询问不应触发待检定。

## 范围

本阶段实现：

- DM 回复中生成 `pending_check`，而不是直接生成 `dice_result`。
- 前端在 DM 消息下方显示待检定控件。
- 待检定控件触发现有骰盘动画，得到 d20 原始点数。
- 新增后端接口提交检定结果。
- 后端根据当前冒险内角色状态计算属性修正、总值、成功失败，并保存到消息 metadata。
- 检定完成后自动向 DM agent 发送一条 tool/context 类型的结果输入，让 DM 继续叙事。
- 流式和非流式 DM 消息都支持待检定。

本阶段不实现：

- 优势/劣势选择 UI。
- 熟练项、工具熟练、豁免熟练的完整规则选择。
- 私聊掷骰、隐藏掷骰或 DM 暗骰。
- 多个玩家同时抢答同一个检定。
- 复杂的检定队列和多人协作检定。

## 数据模型

DM 消息 metadata 增加 `pending_check`：

```json
{
  "pending_check": {
    "id": "check_91_dexterity_12",
    "status": "pending",
    "ability": "dexterity",
    "dc": 12,
    "reason": "翻越铁匠铺后院栅栏",
    "character_id": 1,
    "character_name": "测试",
    "source_message_id": 91
  }
}
```

玩家完成后，metadata 更新为：

```json
{
  "pending_check": {
    "id": "check_91_dexterity_12",
    "status": "resolved",
    "ability": "dexterity",
    "dc": 12,
    "reason": "翻越铁匠铺后院栅栏",
    "character_id": 1,
    "character_name": "测试",
    "source_message_id": 91
  },
  "dice_result": {
    "rolls": [14],
    "kept": 14,
    "modifier": -1,
    "total": 13,
    "dc": 12,
    "success": true,
    "mode": "normal",
    "ability": "dexterity",
    "reason": "翻越铁匠铺后院栅栏",
    "source": "player_dice_tray"
  }
}
```

`pending_check.status` 可选值：

- `pending`：等待玩家掷骰。
- `resolved`：玩家已提交结果。
- `cancelled`：后续状态变化导致检定失效。

## 后端流程

### 创建待检定

DM 模型仍然返回 `requires_check` 和 `check`。但 `DMService` 不再立即调用 `_roll_requested_check`。它改为：

1. 读取当前行动角色。
2. 根据模型返回的 `check` 创建 `pending_check`。
3. 把 `pending_check` 写入本条 DM 消息 metadata。
4. `DMAdvanceResponse.dice_result` 保持 `null`。

为了避免旧逻辑残留，`_model_payload_to_response` 需要返回 `pending_check` 或一个包含待检定的结果对象，而不是直接返回 `dice_result`。

### 提交检定

新增接口：

`POST /api/adventures/{adventure_id}/checks/{check_id}/resolve`

请求：

```json
{
  "message_id": 91,
  "roll": 14,
  "locale": "zh-CN"
}
```

后端处理：

1. 校验冒险、消息和 pending check 存在且属于同一局。
2. 校验 `roll` 是 1 到 20 的整数。
3. 根据 `character_id` 读取冒险内角色状态。
4. 根据 `ability` 计算 modifier。
5. 得出 total 和 success。
6. 更新消息 metadata：`pending_check.status = resolved`，写入 `dice_result`。
7. 将检定结果作为 tool/context 事件传给 DM agent，让它继续叙事。
8. 返回最新 `DMAdvanceResponse`，前端刷新消息、场景、角色和世界状态。

继续叙事的输入不应伪装成玩家自由文本。建议内部传入结构化内容：

```json
{
  "source": "tool",
  "type": "ability_check_result",
  "check": {"ability": "dexterity", "dc": 12, "reason": "翻越铁匠铺后院栅栏"},
  "result": {"roll": 14, "modifier": -1, "total": 13, "success": true}
}
```

DM prompt 必须明确这不是新玩家命令，而是工具返回的检定结果。DM 只能基于这个结果继续裁决刚才的行动。

## 前端流程

`renderMessages` 检测 DM 消息 metadata：

- 如果存在 `pending_check.status === "pending"`，在该 DM 消息下方渲染检定控件。
- 控件显示能力、DC、角色和原因。
- 控件提供一个主要按钮：`掷 d20`。
- 点击后调用骰盘模块的可编程掷骰方法，而不是直接复制随机逻辑。
- 骰盘动画完成后，前端把原始 d20 点数提交给后端。
- 提交中禁用按钮。
- 返回后更新 `state.selectedAdventure`，重新渲染消息和场景。

`dice.js` 需要把内部 `rollDie` 改造成可复用 API：

- `rollDie(sides, options)`：返回 Promise，动画结束后 resolve 掷骰 entry。
- `rollD20ForCheck(check)`：调用 `rollDie(20)`，并标记历史用途。
- 手动点击普通骰子仍然保持原行为。

骰盘历史里可以显示检定用途，例如：

`d20 · 14 · 敏捷检定`

## 错误处理

- 玩家重复提交同一个已完成检定：返回 409 或幂等返回已有结果。
- 待检定消息不存在：返回 404。
- 待检定不属于当前冒险：返回 404。
- `roll` 超出 1 到 20：返回 400。
- 角色已不存在或不属于本局：返回 400。
- DM 继续叙事失败：检定结果仍应保存，前端提示“检定已保存，DM 续写失败”，允许重试继续叙事。

## 兼容性

已有历史消息里的 `dice_result` 继续正常显示，不需要迁移。

已有自动检定逻辑不能直接删除，因为战斗、NPC 或后端暗骰以后可能仍需要后端掷骰。本次只改变“玩家能力检定”的默认路径：由 pending check 交给前端骰盘完成。

如果没有可用前端，非流式 API 仍可以返回 pending check；调用方需要再调用 resolve 接口。

## 测试计划

后端测试：

- LLM 返回 `requires_check=true` 时，DM 消息 metadata 包含 `pending_check`，不包含 `dice_result`。
- resolve 接口提交 d20 点数后，后端根据角色属性计算 total 和 success。
- resolve 接口拒绝重复提交、错误冒险、错误 roll。
- resolve 完成后，DM agent 收到 tool/context 检定结果并生成后续叙事。
- 流式接口 final payload 包含 pending check。

前端测试：

- `renderMessages` 为 pending check 渲染检定控件。
- 点击检定按钮调用骰盘 API，而不是绕过骰盘。
- resolve 成功后刷新冒险消息和场景。
- resolved check 不再显示可点击按钮，只显示结果。
- 普通手动骰盘按钮行为保持不变。

回归测试：

- 现有战斗掷骰不受影响。
- 已有 dice history 仍限制最大条数。
- DM 流式输出仍能正常显示增量文本。

## 验收标准

- 在 `/game/25` 类似场景中，玩家输入“翻过去”后，DM 如果需要敏捷检定，只显示待检定，不后台生成成功失败。
- 玩家点击“掷 d20”后，命运骰盘动画运行并记录历史。
- 后端保存该 d20 的真实结果，并计算角色 modifier、total、success。
- DM 基于检定结果继续描述“翻墙成功/失败/代价”。
- 刷新页面后，待检定或已完成检定状态仍然存在。
