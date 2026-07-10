# 异世界生成模拟器模式设计

## 背景

当前游戏开局准备和游玩页面只支持 DND 模式：玩家先选择剧本和队伍角色，再创建冒险；进入房间后展示 DND 角色、队伍、战斗、地图、骰盘、剧本目标和 DM 聊天。

新模式名为“异世界生成模拟器”。它仍然发生在 DND 世界观中，可以复用种族、职业、物品和世界反应概念，但玩法系统与 DND 模式完全独立。它是单角色生存探险模式：角色由系统随机生成，初始环境由大模型随机生成，核心体验围绕生存数值、资源、环境事件和世界叙事推进。

## 已确认决策

- DND 模式现有内容禁止修改：开局准备、DND 游玩页面、DND 剧本/队伍/战斗/地图/骰盘流程保持原样。
- 开局准备标题旁新增模式选择器，默认选择 DND 模式。
- 模式选择是整个开局准备模块的总开关：选 DND 显示现有 DND 准备内容；选异世界只显示异世界创建新冒险和已有异世界冒险。
- 已有冒险列表按当前模式过滤：DND 只显示 DND 存档，异世界只显示异世界存档。
- 异世界首版每局只有一个随机角色，不支持 DND 式组队。
- 异世界首版创建新冒险只填写标题；角色和初始环境全部随机生成。
- 异世界首版不使用剧本，不绑定 story，不绑定默认剧本地图。
- 异世界首版不显示 DND 战斗模块、DND 地图 token、骰盘、队伍切换和剧本模块。
- 生存数值由后端确定性规则系统推进；大模型负责环境、叙事、事件建议，不直接随意改核心数值。

## 目标

1. 在开局准备中新增模式选择，并保证 DND 模式内容保持原样。
2. 为异世界模式提供独立创建流程：标题输入、创建中提示、随机角色生成、随机初始环境生成、生成完成后展示角色信息并进入冒险。
3. 为异世界模式提供独立游玩页面：随机角色、生存状态、背包金币、当前环境、当前目标、DM/世界叙事聊天、世界事件记录。
4. 后端为每局冒险保存 `mode`，旧冒险默认归为 `dnd`，异世界冒险归为 `isekai_survival`。
5. 异世界角色和 DND 角色数据独立，异世界角色状态与本局冒险绑定，不进入 DND 角色库。
6. 生存规则确定性更新饥饿、口渴、疲劳、睡眠需求、HP、金币、物品和状态效果。

## 非目标

- 不重做或调整现有 DND 开局准备布局。
- 不重做或调整现有 DND 游玩房间布局。
- 不在首版实现异世界战斗系统。
- 不在首版实现异世界地图或地图 token。
- 不在首版支持多角色队伍、同伴管理或角色切换。
- 不在首版支持玩家选择出身、难度、环境倾向或随机种子。
- 不把异世界随机角色写入 DND `characters` 表。

## 推荐方案

采用“同一套 Adventure 外壳 + 按 mode 分流玩法服务”。

`adventures` 继续作为会话外壳，承载标题、状态、当前场景、世界状态和消息记录。新增 `mode` 字段区分玩法。DND 冒险继续走现有 `DMService.create_adventure`、DND 角色、剧本、战斗和地图逻辑。异世界冒险走新的 `IsekaiSurvivalService`，使用独立的角色状态和生存规则。

这样可以复用已有 `/game/:id` 路由、冒险列表、消息表、删除冒险、场景展示和流式聊天基础设施，同时避免把异世界角色、生存数值和 DND 角色/战斗耦合。

## 数据模型

### Adventure 模式

为 `adventures` 增加字段：

- `mode TEXT NOT NULL DEFAULT 'dnd'`

取值：

- `dnd`
- `isekai_survival`

旧数据迁移后默认为 `dnd`。后端列表和详情 API 返回 `mode`，前端据此选择渲染 DND 页面或异世界页面。

### 异世界角色状态

新增表 `isekai_characters`，一局异世界冒险一条角色记录：

- `id`
- `adventure_id`
- `name`
- `race`
- `class_name`
- `background`
- `alignment`
- `level`
- `hp_current`
- `hp_max`
- `armor_class`
- `strength`
- `dexterity`
- `constitution`
- `intelligence`
- `wisdom`
- `charisma`
- `gold`
- `inventory_json`
- `traits_json`
- `world_reaction_tags_json`
- `status_effects_json`
- `created_at`
- `updated_at`

种族和职业可以参考 DND 角色创建的现有候选：例如 Human、Elf、Half-Elf、Dwarf、Halfling、Tiefling，以及 Fighter、Ranger、Rogue、Wizard、Cleric、Druid 等。它们不是 DND 角色库实例，而是异世界角色的随机属性。

### 生存状态

新增表 `isekai_survival_states`，一局异世界冒险一条状态记录：

- `adventure_id`
- `day`
- `time_of_day`
- `hunger`
- `thirst`
- `fatigue`
- `sleep_need`
- `temperature_risk`
- `morale`
- `weather`
- `location`
- `shelter`
- `last_action_type`
- `state_json`
- `updated_at`

数值约定：

- `hunger`、`thirst`、`fatigue`、`sleep_need`：0 到 100，越高越危险。
- `temperature_risk`：0 到 100，越高表示越冷/越热等环境危险越强。
- `morale`：0 到 100，越低越危险。
- HP 仍保存在角色表中，规则系统可以根据生存状态造成 HP 变化。

### 事件记录

异世界可以复用现有 `messages` 表记录玩家输入和世界叙事，也可以复用当前冒险的 `world_state_json` 存放公开世界事件摘要。首版不新增复杂事件表，避免过早扩展。

每次异世界行动的规则结果写入 DM 消息 metadata：

```json
{
  "mode": "isekai_survival",
  "survival_delta": {
    "hunger": 3,
    "thirst": 5,
    "fatigue": 8,
    "sleep_need": 4,
    "hp_delta": 0,
    "inventory_changes": []
  },
  "visible_events": ["雾林温度下降，衣物变得更潮湿。"]
}
```

## 后端服务

### 创建异世界冒险

新增异世界创建入口，使用同一个 `/api/adventures` 资源也可以接受 `mode`：

```json
{
  "title": "雾林边境求生",
  "mode": "isekai_survival",
  "locale": "zh-CN"
}
```

当 `mode=dnd` 或未传 mode 时，保持现有 DND 创建逻辑。

当 `mode=isekai_survival` 时：

1. 后端校验 title。
2. 随机生成异世界角色，不读取 DND `characters`。
3. 初始化生存状态。
4. 使用大模型生成初始环境和开场叙事；如果模型失败，使用后端模板 fallback。
5. 创建 adventure，`mode=isekai_survival`，`story_id` 写入兼容标记值 `isekai_survival`，`story_snapshot_json` 保持 `{}`，并且所有剧本读取、地图绑定和 DND 剧本逻辑都跳过该模式。
6. 写入 `isekai_characters` 和 `isekai_survival_states`。
7. 追加 opening DM message，metadata 标记 `mode=isekai_survival`。
8. 返回 AdventureOut，附带 `isekai_character` 和 `survival_state`。

### 异世界行动推进

异世界冒险的消息接口可以继续使用 `/api/adventures/{id}/messages/stream`。DMService 在处理消息前检查 adventure mode：

- `dnd`：走现有 DMService 流程。
- `isekai_survival`：转发到 `IsekaiSurvivalService.advance_stream`。

异世界推进顺序：

1. 追加玩家消息。
2. 分类玩家行动，例如探索、移动、采集、休息、交谈、查看状态、规则外闲聊。
3. 后端生存规则根据行动类型、当前环境和状态计算确定性 delta。
4. 大模型基于当前角色、环境、生存结果、历史消息生成叙事和下一环境变化建议。
5. 后端只接受模型的叙事、环境描述和事件建议；核心数值以规则系统为准。
6. 保存角色状态、生存状态、场景和消息。
7. 流式返回 delta 和 final payload。

## 生存规则

首版规则保持简单可预测：

- 探索/移动：疲劳、口渴、饥饿上升，可能推进时间。
- 寻找食物/水：疲劳上升；成功时增加物品或降低饥饿/口渴压力，失败时消耗时间。
- 休息/睡觉：睡眠需求和疲劳下降；如果无庇护所，可能增加温度风险或触发事件。
- 进食/饮水：消耗背包物品，降低饥饿/口渴。
- 长时间不睡：疲劳和睡眠需求过高后影响行动，严重时扣 HP。
- 饥饿/口渴过高：持续扣 HP 或施加状态效果。
- 温度风险过高：施加寒冷/炎热等状态，严重时扣 HP。

规则系统输出结构化 delta，前端显示在世界事件记录和消息 metadata 中。

## 大模型职责

大模型不负责直接决定核心生存数值。它负责：

- 随机生成首个环境和开场叙事。
- 根据角色种族、职业、世界反应标签描述 NPC/世界反应。
- 根据后端提供的 survival_delta 叙述行动后果。
- 提供下一步可观察环境、目标、风险和可尝试行动。
- 生成世界事件建议，供后端保存为公开事件摘要。

异世界 prompt 必须明确区分：

- 用户输入：玩家意图。
- 后端工具状态：生存状态、角色状态、规则 delta。
- 模型输出：叙事、环境建议、事件建议。

## 前端开局准备

新增 `state.selectedGameMode`，默认 `dnd`。

开局准备标题旁放模式切换器：

- DND 模式
- 异世界生成模拟器

切换规则：

- `dnd`：渲染现有 DND 开局准备，内容保持原样。
- `isekai_survival`：整块替换为异世界创建准备，不显示 DND 剧本和 DND 角色选择。

异世界开局准备包含：

- 冒险标题输入。
- 创建按钮。
- 创建中状态文案：“角色正在创建中...”。
- 生成完成后的角色信息卡。
- 已有异世界冒险列表。

已有冒险列表按当前 mode 过滤。

## 前端异世界游玩页面

当选中的 adventure `mode=isekai_survival` 时，`/game/:id` 使用异世界页面。DND 页面代码路径不改变。

异世界页面区域：

- 房间标题：冒险名、当前天数、时间、地点、模式标签。
- 随机角色：姓名、种族、职业、等级、HP、AC、金币、世界反应标签。
- 生存状态：饥饿、口渴、疲劳、睡眠需求、温度风险、士气、状态效果。
- 背包：初始物品、消耗品、获得物品。
- 当前环境与目标：地点、天气、环境描述、当前目标。
- DM / 世界叙事聊天：玩家输入和世界回应，保持固定高度滚动。
- 世界事件记录：最近状态变化、规则结果、公开事件。

首版不显示：

- DND 战斗行动按钮。
- DND 战斗日志。
- DND 地图舞台。
- DND 骰盘。
- DND 队伍列表和角色切换。
- 剧本/任务日志中的 DND 剧本信息。

## API 输出

AdventureOut 增加可选字段：

- `mode`
- `isekai_character`
- `survival_state`

DND adventure 的 `isekai_character` 和 `survival_state` 为空。

异世界 adventure 的 `party_characters` 可以为空，前端不得用 DND party 渲染异世界角色。

## 兼容性

- 旧 DND 冒险通过 `mode` 默认值继续被识别为 DND。
- 现有 DND API 请求不传 mode，行为保持不变。
- 现有测试中的 DND `AdventureCreate` 不需要改请求体。
- DND 战斗 API 对异世界冒险应拒绝，返回结构化错误，例如 `mode_not_supported`。
- 地图绑定逻辑只对 DND 模式执行。

## 错误处理

- 异世界创建时模型失败：使用模板生成初始环境，仍然创建冒险。
- 随机角色生成失败：返回创建失败，不写入半成品 adventure。
- 生存规则更新失败：不提交状态变化，返回错误。
- 异世界冒险调用 DND combat/map-only 接口：返回 400 `mode_not_supported`。
- 前端创建中按钮禁用，防止重复提交。

## 测试计划

### 后端

- 创建 DND 冒险不传 mode，返回 `mode=dnd`，现有字段保持。
- 创建异世界冒险只传 title 和 mode，返回 `mode=isekai_survival`、随机角色、生存状态、opening message。
- 异世界角色不写入 DND `characters` 列表。
- 列表 API 返回 mode，前端可过滤。
- 异世界行动推进会更新 survival_state，并把 survival_delta 写入消息 metadata。
- DND combat API 对异世界冒险返回 `mode_not_supported`。
- 旧数据库初始化会为 adventures 补 `mode` 字段，默认 `dnd`。

### 前端

- 开局准备有模式选择器，默认 DND。
- DND 模式下原有 DND 准备元素仍存在并走原创建请求。
- 异世界模式下 DND 剧本和角色选择区域隐藏，只显示异世界创建和异世界冒险列表。
- 冒险列表按 mode 过滤。
- 异世界创建时显示“角色正在创建中...”并禁用提交。
- 异世界冒险详情渲染异世界页面，不渲染 DND 战斗、地图、骰盘、队伍切换。
- DND 冒险详情仍渲染原 DND 页面。

## 验收标准

- 用户打开 `/game` 时默认看到原 DND 开局准备，视觉和流程不变。
- 用户切换到“异世界生成模拟器”时，开局准备整块切换，不显示 DND 剧本和 DND 角色选择。
- 用户输入标题并创建异世界冒险时，前端显示角色创建中；完成后展示随机角色和生存状态。
- 用户进入异世界冒险后看到独立生存探险页面。
- 异世界行动后，饥饿、口渴、疲劳、睡眠需求等数值由后端规则变化，并能在页面感知到。
- DND 存档和异世界存档不会混在同一个已有冒险列表中。
- DND 模式的现有测试和核心流程继续通过。
