# 异世界模式场景对象自动结构化架构设计

## 背景

当前异世界模式已经具备 LLM 意图理解、动作落地、确定性结算、经济账本、压力事件和场景交互面板。但最近的游玩记录暴露出一个核心架构问题：

> DM 旁白里出现了具体对象，系统状态里却没有这些对象。

例如 DM 写出“麋鹿骸骨、折断的铁头箭、血迹、坍塌哨塔”，玩家随后搜索这些对象时，后端找不到结构化目标，只能退回“角色快速观察周围”“角色仔细搜索附近区域”。为止血，代码临时在 `IsekaiInteractableProjector` 中补了一批森林/哨塔关键词，但这不是长期方案。

长期方案不能继续在代码中枚举所有可能出现的物品、地点、线索和 NPC。异世界模式的内容由大模型随机生成，具体对象空间无限，代码只能维护抽象规则。

## 目标

本次架构升级的目标是：

- 让 DM/场景生成器创造的对象进入结构化 `SceneState`。
- 让玩家能搜索、观察、进入、拾取、交谈、购买、加固这些对象，并得到具体反馈。
- 避免在代码里硬编码“麋鹿骸骨、旧火堆、铁头箭”等具体物品名。
- 保持规则结算确定性：模型可以提出对象和描述，但不能直接发奖励、扣钱、改任务阶段。
- 让前端显示的可互动内容与 DM 旁白、当前位置、后端状态保持一致。

## 非目标

本阶段不做以下事情：

- 不开放无限 action_type。动作库仍保持小而稳定。
- 不让 LLM 直接决定最终状态变化。
- 不把所有对象都永久显示在当前场景。
- 不一次性重写整个异世界模式。
- 不把旧 `IsekaiInteractableProjector` 立即删除；它先保留为 legacy fallback。
- 不建立“具体物品名清单”。文档中出现的麋鹿骸骨、铁头箭、旧火堆等只作为示例和回归测试输入，不是实现时要维护的对象列表。

## 当前问题诊断

### 1. 具体物品被写进代码

当前 `IsekaiInteractableProjector` 用文本包含判断生成对象，例如“旅店”“木箱”“麋鹿骸骨”“旧火堆”。这会导致三个问题：

- 写不完：随机生成的世界对象无限。
- 维护困难：每次出新内容都要改后端代码。
- 泛化差：同类对象换个名字就找不到，例如“鹿骨堆”“断裂猎箭”“焦黑篝火圈”。

### 2. DM 旁白和 SceneState 不同步

DM 文本可能出现多个对象，但 `current_scene.interactables` 仍为空或只有“周围环境”。动作解析器只能绑定 `interactables` 中的目标，找不到就退化成泛化行为。

### 3. 对象生命周期不清晰

当前缺少对象的来源、可见性、所在位置、是否当前在场、是否已移除等字段。结果是：

- 旧地点对象可能残留到新地点。
- NPC 记忆和当前在场 NPC 容易混在一起。
- 被拾取或消耗的物品仍可能继续显示。

## 推荐方案：LLM 对象提出 + 后端类型校验 + 确定性落库

推荐采用混合架构：

```text
DM/场景生成器负责创造具体对象
-> SceneObjectMaterializer 提取或接收对象 proposal
-> SceneObjectValidator 校验类型、动作能力、位置、可见性
-> NarrationObjectConsistencyGate 修正最终旁白中的对象引用
-> SceneObjectStore 写入当前 SceneState
-> ActionGrounder 只绑定已落库对象
-> ResolutionEngine 按对象类型和 affordances 结算
```

核心原则：

```text
模型创造对象，规则系统批准对象。
模型描述可能性，规则系统决定能不能操作。
模型不能直接发奖励或扣资源。
最终 DM 旁白中当前可见、可指向的主要对象，必须已经通过校验并进入对象状态。
```

## 方案对比

### 方案 A：继续扩充规则投影器

做法：继续往 `IsekaiInteractableProjector` 加关键词和模板。

优点：

- 实现快。
- 对固定场景可控。
- 不增加 LLM 调用。

缺点：

- 写不完具体对象。
- 适配随机生成内容能力很差。
- 每次新增场景都需要改代码。

结论：只适合作为 legacy fallback，不适合作为主路径。

### 方案 B：完全相信 LLM 输出对象

做法：DM 每轮直接输出 `interactables`，后端原样存储。

优点：

- 内容生成能力强。
- 能覆盖开放世界对象。

缺点：

- LLM 可能给出非法 affordance，例如“传送”“秒杀”“免费获得钥匙”。
- 可能把远处传闻对象显示成当前可互动对象。
- 可能和位置、资源、经济规则矛盾。

结论：不能直接采用，必须有后端校验。

### 方案 C：LLM 提出对象，后端校验和落库

做法：LLM 输出对象 proposal，后端按对象类型、位置、可见性、动作能力集合、物理约束校验后写入状态。

优点：

- 不需要代码枚举所有具体对象。
- 仍保持规则确定性。
- 可测试、可回放、可调试。
- 能支持随机生成环境。

缺点：

- 需要设计对象 schema 和校验器。
- 流式输出下需要处理“正文先到、结构化对象后到”的时序。

结论：推荐采用。

## 核心数据结构

### SceneObject

新增或规范化当前 `interactables` 的结构：

```json
{
  "id": "scene_45_obj_elk_carcass_01",
  "type": "clue",
  "name": "麋鹿骸骨",
  "aliases": ["鹿骨", "骸骨", "尸骸"],
  "description": "肋骨间插着一支折断的铁头箭，周围有被拖拽过的血迹。",
  "state": "可检查",
  "visibility": "visible",
  "presence": "current",
  "scope": "current_node",
  "node_id": "mist_forest_edge",
  "affordances": ["observe", "search"],
  "tags": ["corpse", "trail_clue", "danger_hint"],
  "risk_hint": "靠近尸骸可能暴露气味，也可能接近捕食者路线。",
  "source": "dm_scene_proposal",
  "created_turn": 3,
  "updated_turn": 3,
  "version": 1
}
```

字段说明：

- `id`：稳定对象 ID，不依赖中文名称完全相同。
- `type`：抽象对象类型，只允许后端定义的稳定类型集合。
- `name`：玩家可见名称。
- `aliases`：用于玩家自然语言绑定。
- `visibility`：`visible | hinted | hidden | discovered | removed`。
- `presence`：`current | nearby | remembered | offscreen | inventory | removed`。
- `scope`：`current_node | nearby_node | remote_rumor | world_memory`。
- `affordances`：可尝试动作，必须来自后端允许集合。
- `source`：对象来源，用于调试。

### 对象类型闭集

第一阶段建议支持：

```text
npc
item
container
clue
place
entrance
obstacle
hazard
resource
water_source
shelter
merchant
```

不要按具体内容建类型。例如不要有 `elk_carcass`、`old_firepit`、`magic_altar` 这种类型；这些应由 `name/tags/description` 表达。

对象类型闭集不是内容枚举。只有当系统新增一种不同的规则语义时才扩展类型，例如从 `container` 到 `merchant`；新增“骨笛”“蓝盐水洼”“倒悬铜镜”这类内容时不得扩展类型，只应由模型填充 `name/aliases/tags/description`。

### affordance 能力闭集

内部统一用英文 action key，前端再本地化展示：

```text
observe
search
enter
leave
approach
talk
negotiate
purchase
gather
take
open
force_open
refill_water
eat_meal
secure_shelter
rest_short
hide
avoid
track
read
repair
```

affordance 不是最终成功承诺，只表示“玩家可以合理尝试”。真正能不能成功，仍由 precondition 和 resolution 决定。

affordance 能力闭集也不是具体动作句子清单。玩家可以输入任意自然语言，意图层将其归一到这些稳定能力上；新增“轻轻推开”“蹲下细看”“用斗篷遮住”等说法时，不应新增 affordance，除非出现了新的规则结算语义。

### affordance 到 action_type 的映射

`affordance` 是对象能力，不等同于 `action_type`。ActionGrounder 和 Policy 必须通过固定映射把对象能力接入意图动作白名单，开发不得各自猜测。

| affordance | 对应 action_type | 说明 |
| --- | --- | --- |
| observe | observe | 查看、辨认、听动静、读环境线索 |
| search | search | 翻找、搜寻、深入检查 |
| enter | enter_location | 进入地点、房间、车厢、洞口 |
| leave | leave_location | 离开当前节点或建筑 |
| approach | approach | 靠近但不进入 |
| talk | short_dialogue | 简短交谈、询问、打招呼 |
| negotiate | negotiate | 讨价还价、谈条件 |
| purchase | purchase | 购买商品、服务或权益 |
| gather | gather | 采集、收集资源 |
| take | manage_inventory | 拿起已明确可携带物；是否入包由 resolver 判断 |
| open | search | 普通打开或检查容器；遇到阻碍时转为 blocked 或 force_open 替代 |
| force_open | force_open | 撬开、砸开、强行打开 |
| refill_water | refill_water | 从当前或邻近可用水源补水 |
| eat_meal | eat_meal | 食用已购买或已获得的热食 |
| secure_shelter | secure_shelter | 堵门、加固、封入口 |
| rest_short | rest_short | 在已确认可休整地点短休 |
| hide | hide | 躲藏 |
| avoid | avoid | 规避危险或绕开 |
| track | search | 在当前节点追踪线索；若追踪导致跨节点移动，由 resolver 产出后续 `travel` 建议 |
| read | observe | 阅读文字、符文、告示 |
| repair | repair | 修理设施或对象 |

如果对象给出 affordance，但没有映射到白名单 action_type，该 affordance 必须被 validator 删除，并写入 `blocked_affordances`。

## 类型到 affordance 的默认规则

后端维护抽象映射，不维护具体物品名：

| type | 默认 affordances |
| --- | --- |
| npc | observe, talk |
| merchant | observe, talk, negotiate, purchase |
| item | observe, take |
| container | observe, search, open, force_open |
| clue | observe, search |
| place | observe, approach, enter |
| entrance | observe, enter, force_open |
| obstacle | observe, force_open, repair |
| hazard | observe, avoid, hide |
| resource | observe, gather |
| water_source | observe, refill_water |
| shelter | observe, search, secure_shelter, rest_short |

模型可以提出 affordance，但 validator 必须按类型交集过滤。模型不能发明新 affordance。

这张表是规则能力矩阵，不是可互动内容列表。实现时禁止把具体世界对象追加到这张表里。

示例：

```json
{
  "type": "clue",
  "name": "折断的铁头箭",
  "affordances": ["observe", "search", "take", "teleport"]
}
```

校验后：

```json
{
  "type": "clue",
  "name": "折断的铁头箭",
  "affordances": ["observe", "search"],
  "blocked_affordances": ["take", "teleport"]
}
```

如果要允许拿起线索，需要模型或规则将其标记为 `type=item` 或 `tags=["portable_clue"]`，再由规则允许 `take`。

## 新增服务设计

### IsekaiSceneObjectMaterializer

新增文件：

```text
backend/src/services/isekai_scene_objects.py
```

职责：

- 接收以下输入：
  - 当前 `SceneState`
  - 本轮 DM narration
  - LLM 原始 `scene_update`
  - 已结算的 action result
  - 当前 location_path/node_id
- 输出 `SceneObjectPatch`：
  - `add`
  - `update`
  - `remove`
  - `hide`
  - `reveal`

Materializer 有两个来源：

1. 优先使用模型结构化输出中的 `scene_objects`。
2. 如果模型未提供结构化对象，则调用轻量对象提取器，从本轮已接受的 narration、scene_update、environment 中提取候选对象。

对象提取器约束：

- 不从玩家输入中提取对象，避免把玩家猜测固化成世界事实。
- 不把比喻、氛围词、传闻对象直接变成当前可互动对象。
- fallback 提取出的对象默认 `visibility=hinted`、`affordances=["observe"]`。
- 只有经过 observe/search/reveal 后，hinted 对象才能升级为 `visible/discovered`。

### IsekaiSceneObjectValidator

职责：

- 校验对象 schema。
- 校验 type 抽象闭集。
- 派生或过滤 affordances。
- 校验 `scope/presence/visibility` 是否允许前端显示。
- 拦截经济、奖励、任务类越权字段。
- 为对象生成稳定 id。
- 限制每轮新增对象数量。

关键规则：

- 当前场景最多展示 6 到 10 个主要对象。
- `presence=remembered/offscreen` 的对象不能进入当前可互动列表。
- `visibility=hidden` 的对象不能显示，但可作为搜索结果在成功后 reveal。
- `type=merchant` 必须是当前在场 NPC 或当前地点设施，不允许远方传闻商人直接 purchase。
- `water_source` 必须有 `scope=current_node`，或同时满足 `scope=nearby_node` 且 `presence=nearby`，否则不能 `refill_water`。

### NarrationObjectConsistencyGate

职责：

- 在 DM 文本落库前，比对最终 narration 与 validator 结果。
- 当前可见、玩家可指向的主要对象如果未通过 validator，不得保留在最终 narration 中。
- 被拒绝对象如果只是远景、传闻、比喻或气氛描述，必须改写成不可指向表达，并不得进入当前可互动列表。
- metadata 记录被修正或删除的对象名和原因。

处理顺序：

```text
模型输出 narration + scene_objects
-> Validator 校验 scene_objects
-> ConsistencyGate 检查 narration 中的主要对象
-> 删除、降级或改写未通过校验的当前可见对象
-> Store 写入对象
-> 最终 narration 才允许 append_message
```

硬规则：

- 不允许出现“DM 说有这个当前对象，但 `current_scene.interactables` 和对象记忆里完全没有”的响应。
- 不允许非法对象“只留在旁白里但不能交互”。
- 如果必须保留为氛围或远景，文本要明确它不可立即互动，例如“远处像是有一截塔影，但距离和雾气让你暂时无法确认”。

### IsekaiSceneObjectStore

职责：

- 把当前可互动对象写入 `SceneState.interactables`。
- 把非当前对象、隐藏对象和跨地点记忆写入 `world_state.scene_object_memory_by_node`。
- 维护对象版本。
- 在移动地点时切换 current/offscreen/remembered。
- 处理对象被拾取、消耗、移除。

第一阶段不新增数据库表，但必须从一开始分清两个存储层：

```text
SceneState.interactables:
  只保存当前节点可展示、可绑定、可互动的对象。

world_state.scene_object_memory_by_node:
  保存 hidden、remembered、offscreen、nearby_node、remote_rumor、world_memory 对象。
```

这样可以避免把旧地点对象继续显示在当前界面，也避免进入新地点时把对象记忆直接丢失。等对象历史和跨地点记忆复杂后，再考虑独立表。

### IsekaiSceneObjectProjector

替代当前 `IsekaiInteractableProjector` 的主路径。

职责：

- 从已落库的 `SceneObject` 中选择当前前端可展示对象。
- 根据对象 affordances 生成 suggested_actions。
- 不从具体中文名硬编码生成对象。

当前 `IsekaiInteractableProjector` 保留为：

```text
LegacyKeywordProjector
```

只在以下场景使用：

- 旧存档没有结构化对象。
- 模型结构化输出缺失。
- 需要修复历史坏状态。

## LLM 输出协议

DM 或场景生成模型应输出结构化 payload：

```json
{
  "narration": "你检查麋鹿骸骨，发现箭头残着黑色树脂，血迹拖向坍塌哨塔。",
  "scene_update": {
    "location": "迷雾森林边缘",
    "environment": "潮湿林地里有被拖拽的血迹和远处水声。"
  },
  "scene_objects": {
    "add": [
      {
        "type": "clue",
        "name": "麋鹿骸骨",
        "aliases": ["鹿骨", "骸骨"],
        "description": "肋骨间插着折断的铁头箭。",
        "visibility": "visible",
        "presence": "current",
        "scope": "current_node",
        "tags": ["corpse", "trail_clue"],
        "suggested_affordances": ["observe", "search"]
      },
      {
        "type": "place",
        "name": "坍塌的石砌哨塔",
        "aliases": ["哨塔", "坍塌哨塔"],
        "description": "半截墙壁露在树影里，像是能临时避风。",
        "visibility": "visible",
        "presence": "nearby",
        "scope": "nearby_node",
        "tags": ["shelter_candidate", "danger_hint"],
        "suggested_affordances": ["observe", "approach", "enter"]
      }
    ],
    "update": [],
    "remove": []
  },
  "suggested_actions": [
    {"text": "检查麋鹿骸骨和折断的箭", "target_ref": "麋鹿骸骨", "action_type": "observe"},
    {"text": "沿血迹追踪到哨塔附近", "target_ref": "血迹方向", "action_type": "search", "affordance": "track"}
  ]
}
```

注意：

- `scene_objects` 是 proposal，不是最终状态。
- `suggested_affordances` 是 proposal，validator 可删除或替换。
- 不能在 `scene_objects` 中写 `rewards/currency/quest_stage`。
- 最终 narration 中的当前可见主要对象，必须与通过 validator 的对象状态一致；不一致时由 ConsistencyGate 修正后再落库。

## 行动绑定流程

玩家输入：

```text
我检查麋鹿骸骨上的箭，再沿血迹看向哨塔。
```

流程：

```text
IsekaiIntentInterpreter
-> steps:
   observe target_text=麋鹿骸骨
   observe target_text=血迹方向
   approach target_text=坍塌的石砌哨塔

IsekaiActionGrounder
-> 用 current_scene.interactables + aliases 绑定 target_id

IsekaiActionPreconditionService
-> 检查对象当前可见、在场、动作允许

IsekaiActionResolutionEngine
-> 结算时间、风险、发现、对象 reveal/update

IsekaiNarrationComposer
-> 基于结构化结果生成具体反馈
```

如果目标不在 `interactables` 中：

1. 先检查 `SceneObjectStore` 是否有 remembered/nearby 对象可重新投影。
2. 再检查本轮已接受的 narration、scene_update 或 environment 是否有未 materialize 的对象，可触发一次 object extraction。
3. 仍找不到则返回 clarification，而不是泛化成“观察周围”。

## 对象发现和隐藏对象

搜索不应该要求所有对象一开始都显示。支持 hidden object：

```json
{
  "id": "hidden_cache_01",
  "type": "container",
  "name": "石缝里的油布包",
  "visibility": "hidden",
  "presence": "current",
  "discoverable_by": ["search"],
  "difficulty": "normal"
}
```

玩家搜索对应区域后，resolver 可以 reveal：

```json
{
  "reveal": ["hidden_cache_01"],
  "result": "你在地基缝隙里摸到一只潮湿油布包。"
}
```

这样 DM 不需要提前把所有对象直接摆给玩家，但系统仍知道它存在。

## 对象生命周期

对象状态应随行动变化：

### 进入新地点

- 当前地点对象：`presence=current`
- 旧地点对象：`presence=remembered/offscreen`
- 前端只显示 `presence=current` 且 `visibility in visible/discovered` 的对象。
- `nearby` 对象可以作为提示或建议出现，但不能当作当前节点可直接拾取、购买或补水对象。

### 拾取物品

`take` 成功后：

- 对象 `presence=inventory`
- `visibility=removed`
- 角色背包增加对应物品。
- 前端当前可互动列表必须移除该对象。

### 移除或消耗对象

对象被消耗、破坏或不再存在时：

- `presence=removed`
- `visibility=removed`
- `updated_turn` 更新
- `SceneState.interactables` 不再显示

`presence=removed` 和 `visibility=removed` 必须同时出现，作为对象不再可互动的标准状态。

### 打开容器

`open/search` 成功后：

- 容器 `state=opened/searched`
- hidden objects reveal。

### NPC 离开

当前场景 NPC：

- `presence=offscreen`
- NPC 记忆进入 `npc_memory`，不再显示为当前可互动对象。

## 与确定性结算的边界

LLM 可以提出：

- 场景中有什么对象。
- 对象长什么样。
- 对象可能支持什么互动。
- 搜索后可能 reveal 什么对象。

LLM 不可以直接决定：

- 玩家获得物品。
- 钱币扣除。
- HP 改变。
- 任务阶段推进。
- NPC 信任变化。
- 是否成功进入锁住地点。

这些仍由已有或新增 resolver 决定：

```text
IsekaiResourceService
IsekaiEconomyService
IsekaiQuestService
IsekaiRewardService
IsekaiActionResolutionEngine
```

## 前端展示调整

前端不再把 `important_objects` 当作主要可互动来源。

展示来源优先级：

1. `current_scene.interactables` 中通过 validator 的对象。
2. 对象的 `affordances` 生成行动建议。
3. `important_objects` 只作为场景摘要或备用信息。

建议对象卡片显示：

```text
名称
类型标签
当前状态
风险提示
可尝试动作
```

点击建议仍只填入输入框，不自动发送。

## 旧系统迁移策略

### 第一阶段：兼容接入

- 新增 `IsekaiSceneObjectMaterializer/Validator/Store`。
- DM 结构化输出优先走新对象系统。
- `IsekaiInteractableProjector` 改名或包装为 legacy fallback。
- 旧存档读取时若 `interactables` 为空或只有“周围环境”，尝试 legacy 修复。

### 第二阶段：减少关键词 projector 权重

- 新内容不再往 projector 加具体对象名。
- projector 只保留通用类别：
  - 门/入口
  - 容器
  - 水源
  - NPC
  - 商人
  - 庇护点

### 第三阶段：对象状态独立持久化

当跨地点对象和 NPC 记忆变多后，新增独立表：

```text
isekai_scene_objects
```

字段包括：

```text
id
adventure_id
node_id
object_json
presence
visibility
created_turn
updated_turn
```

P0 阶段可以先不建表，降低改动风险。

## 错误处理

### 模型没有输出 scene_objects

处理：

- 触发对象提取器从已接受的 narration、scene_update、environment 中提取候选。
- fallback 提取对象默认 `visibility=hinted`、`affordances=["observe"]`。
- 不允许从玩家输入中提取对象。
- 如果仍为空，保留原场景对象，不生成“周围环境”泛化对象。
- metadata 记录：

```json
{
  "scene_object_source": "extraction_fallback",
  "scene_object_warning": "model_missing_scene_objects"
}
```

### 模型输出非法对象类型

处理：

- 丢弃该对象。
- metadata 记录 blocked reason。
- 如果最终 narration 将该对象写成当前可见、玩家可指向对象，必须由 ConsistencyGate 删除或改写。
- 不允许保留“旁白里有、状态里没有、玩家不能互动”的当前对象。

### 模型输出非法 affordance

处理：

- 删除非法 affordance。
- 保留对象。
- 如果对象删除非法 affordance 后没有任何可尝试动作，则降级为 `visibility=hinted`，只允许 observe，或不进入当前可互动列表。

### 对象和当前位置冲突

例如当前位置是森林，模型输出“旅店店主正在柜台后”。

处理：

- 如果对象 scope 不是 current node，标记 `presence=offscreen/remembered`。
- 不进入前端当前可互动列表。
- 如果冲突严重，要求 DM 重写或由 NarrationRepairer 删除该句。

### 玩家指向不存在对象

处理：

- 先尝试对象提取。
- 再尝试别名匹配。
- 仍失败则 clarification：

```text
你现在没有看到“银色机关”。你可以先搜索祭坛、观察墙面或检查地面缝隙。
```

不要退回：

```text
角色快速观察周围。
```

## 测试要求

### 单元测试

新增：

```text
test_isekai_scene_objects.py
```

覆盖：

- LLM proposal 转 SceneObject。
- 非法 type 被拒绝。
- 非法 affordance 被过滤。
- aliases 可绑定目标。
- hidden object 不显示但可 reveal。
- 移动地点后旧对象不显示。
- `presence=remembered` 不可被当前动作直接操作。

### 集成测试

新增或扩展：

```text
test_isekai_llm_intent_resolution.py
test_isekai_survival.py
```

必测输入：

- “搜索麋鹿骸骨上的箭”
- “检查我刚才看到的那个焦黑火堆”
- “打开树根下的油布包”
- “沿血迹追踪”
- “进入旁边那座半塌哨塔”
- “我找找附近有没有水源”
- “和刚才那个猎人说话”，但猎人已经离开当前地点

### 随机对象回归

用从未在代码里出现过的对象名测试：

- “发光菌毯”
- “骨笛”
- “倒悬铜镜”
- “虫蚀皮袋”
- “蓝盐水洼”

验收标准：

- 不需要在代码里写这些名字。
- 模型提出对象后，系统能绑定、显示、搜索或澄清。
- 不会退回“周围环境”泛化回复。
- 测试中的具体名词不得被加入 projector、validator 或 parser 的硬编码分支。

## 验收标准

1. 新场景出现的对象不需要手写进 `IsekaiInteractableProjector`。
2. DM 最终旁白中出现的当前可见主要对象，必须在同一次响应返回前进入 `current_scene.interactables` 或 `world_state.scene_object_memory_by_node`。
3. 玩家搜索/观察具体对象时，ActionGrounder 能绑定 target_id。
4. 找不到目标时返回澄清，不再泛化执行。
5. 进入新地点后，前端只显示当前地点对象。
6. 被拾取、消耗、移除的对象不再作为当前可互动对象显示。
7. hidden object 可通过搜索 reveal。
8. 模型不能通过 scene_objects 直接发奖励、扣钱、改任务阶段。
9. 旧 projector 不再新增具体物品名，只保留通用 fallback。
10. 随机对象名回归测试通过。
11. 被 validator 拒绝的当前对象不得保留在最终 DM 旁白里。
12. affordance 必须通过固定映射进入 action_type 权限矩阵。

## 开发顺序建议

### P0.1 对象 schema 和 validator

- 定义 SceneObject schema。
- 定义 type/affordance 抽象闭集。
- 实现 affordance 派生和过滤。
- 单测 validator。

### P0.2 Materializer 接入 DM 输出

- 扩展 DM structured output，支持 `scene_objects`。
- 在 `apply_scene_progression` 后校验并落库对象。
- 接入 NarrationObjectConsistencyGate，确保最终旁白和对象状态一致。
- metadata 记录对象来源和 blocked reason。

### P0.3 Grounder 绑定别名和对象状态

- 支持 `aliases`。
- 支持 target_text 到 current scene object 的绑定。
- 接入 affordance 到 action_type 的固定映射。
- 找不到目标时先触发 object extraction，再 clarification。

### P0.4 前端展示切换

- 前端对象面板以 validator 后的 `interactables` 为准。
- 显示 type/state/risk/affordances。
- 建议行动由 affordances 生成。

### P0.5 legacy projector 降级

- 将现有关键词 projector 标记为 legacy fallback。
- 删除或禁止新增具体场景物品名。
- 保留旧存档修复能力。

## 架构师审视重点

本轮已经确认以下架构决策，开发按此执行：

- 第一阶段不直接建表，但必须拆分 `SceneState.interactables` 与 `world_state.scene_object_memory_by_node`。
- `scene_objects` 优先由 DM 主模型输出；缺失时才用轻量对象提取器兜底。
- 对象提取器不得从玩家输入提取对象。
- hidden object 允许由模型提前 proposal，但只能进入对象记忆，不得直接展示或发奖励。
- affordance 必须先过滤，再通过固定映射接入 action_type 权限矩阵。
- 当前对象、nearby 对象、remembered/offscreen 对象必须按 presence/scope 分层处理。
- 流式输出不能牺牲最终一致性；最终 `final` 响应返回前，narration、metadata、current_scene 必须一致。

## 结论

当前森林/哨塔修复是止血，不是长期架构。长期应将“具体对象”从代码枚举中移出，交给 DM/场景生成器提出，再由后端以类型、affordance、位置、可见性和权限规则进行校验落库。

这样系统可以支持随机生成世界，同时保持可测试、可回放和确定性结算。
