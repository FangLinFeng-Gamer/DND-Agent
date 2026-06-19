# 角色创建 Agent 混合状态与输出设计

## 目标

升级角色创建 Agent，使面向程序的决策使用结构化数据，DND 规则保持确定性，面向玩家的回复使用普通大模型文本，并且每个会话保留足够的消息历史，以理解玩家的后续请求。

## 架构

角色创建流程划分为四项独立职责：

1. `CharacterDraft` 是角色结构化状态的唯一权威数据源。
2. 会话消息保存用户与助手的对话历史。
3. 结构化抽取模块将自然语言转换为建议的状态变更。
4. 状态更新和规则校验完成后，由回复生成器输出最终展示给玩家的文本。

大模型不能直接写入数据库，也不能绕过 DND 规则。

## Agent 模式说明

目标架构将 `CharacterCreationAgent` 的最外层实现为真正的 ReAct Agent。

```text
用户消息
  -> CharacterCreationReActAgent
      -> 调用受控工具
          -> CharacterCreationStateGraph
              -> 执行规则、更新草稿或提交角色
          <- 返回结构化 StateGraphResult
      <- 通过 ToolMessage 感知执行结果
      -> 根据最新结果继续调用工具或生成最终回复
```

外层 ReAct Agent 负责：

- 理解用户意图。
- 决定是否查询规则、读取草稿、更新草稿、校验草稿或确认创建。
- 组合多次工具调用。
- 感知每次 StateGraph 执行后的结构化结果。
- 根据最新结果生成最终玩家回复。

内层 `CharacterCreationStateGraph` 负责：

- 校验工具参数。
- 执行 PHB 规则。
- 更新结构化 `CharacterDraft`。
- 使依赖上游选择的步骤失效。
- 计算当前步骤和下一步骤。
- 校验确认条件。
- 在满足全部条件后提交角色。

ReAct Agent 不能直接修改数据库，也不能跳过 StateGraph 调用修改角色状态。角色创建仍然由确定性的 StateGraph 控制。

当前代码中虽然声明了 `agent_kind = AgentKind.REACT`，但实际实现还是固定流程 StateGraph。本设计完成后，该标记才与真实运行模式一致。

## ReAct 受控工具

外层 ReAct Agent 只能调用以下角色创建工具：

### `get_character_draft`

读取当前会话的角色草稿、revision、完成步骤、失效步骤和下一步骤。

该工具只读，不能修改状态。

### `search_character_rules`

查询角色创建相关规则，包括：

- 种族
- 职业
- 背景
- 属性值
- 熟练项
- 职业特性
- 专长
- 法术
- 起始装备

该工具只读，必须返回规则来源和适用条件。模型不能使用自身记忆替代规则工具的查询结果。

### `explain_character_option`

根据当前草稿和规则查询结果，解释某项选择的作用、限制和后果。

例如玩家询问“战士不能学法术吗”时，该工具应返回：

- 一级纯战士没有职业施法能力。
- 某些种族特性可以提供法术。
- 可通过满足条件的专长获得法术。
- 后续可以通过兼职进入施法职业。
- 当前问题不会自动改变角色职业或提交角色。

### `apply_character_changes`

接受结构化变更建议和 `expected_revision`，调用 StateGraph 更新草稿。

它不能直接执行 SQL。所有变更必须经过 StateGraph 校验和规则计算。

### `validate_character_draft`

调用 StateGraph 检查当前草稿，返回未完成步骤、校验错误、警告和允许执行的下一动作。

该工具只读，不提交角色。

### `confirm_character_creation`

接受玩家的明确确认和 `expected_revision`，调用 StateGraph 执行最终校验。

只有 StateGraph 返回可提交状态时，该工具才允许调用角色持久化服务。该工具是角色创建唯一的提交入口。

## StateGraph 工具结果契约

每个会改变或校验角色状态的工具必须返回统一的 `StateGraphResult`：

```json
{
  "success": true,
  "draft_revision": 8,
  "changed_fields": ["background"],
  "current_step": "review",
  "next_step": "review",
  "validation_errors": [],
  "validation_warnings": [],
  "created_character_id": null,
  "committed": false,
  "facts": ["背景已修改为贵族"],
  "allowed_actions": ["confirm", "update", "ask_rules"]
}
```

字段含义：

- `success`：本次工具执行是否成功。
- `draft_revision`：执行后的最新草稿版本。
- `changed_fields`：本次实际改变的字段。
- `current_step`：当前角色创建步骤。
- `next_step`：下一步需要处理的步骤。
- `validation_errors`：阻止继续或提交的错误。
- `validation_warnings`：不阻止流程的提示。
- `created_character_id`：成功提交后的角色 ID。
- `committed`：角色是否已真实写入角色表。
- `facts`：回复模型必须保留的确定事实。
- `allowed_actions`：ReAct 下一轮允许选择的动作。

StateGraph 结果必须序列化为 `ToolMessage` 返回给 ReAct Agent。ReAct Agent 的下一次推理必须包含该 `ToolMessage`，以便感知最新执行结果。

ReAct Agent 不得仅根据调用工具前的草稿生成回复。

## ReAct 循环与终止条件

单轮用户消息允许 ReAct Agent 执行多个受控工具：

```text
读取草稿
  -> 查询规则
  -> 更新草稿
  -> 校验草稿
  -> 生成回复
```

典型流程：

### 提供角色信息

```text
用户：戴尔，人类战士
ReAct：
  1. get_character_draft
  2. apply_character_changes
  3. 感知 StateGraphResult.next_step == abilities
  4. 回复属性分配规则
```

### 咨询规则

```text
用户：我不能学法术吗
ReAct：
  1. get_character_draft
  2. search_character_rules
  3. explain_character_option
  4. 感知当前角色仍未提交且 next_step 不变
  5. 解释规则并继续原创建步骤
```

### 确认创建

```text
用户：完成
ReAct：
  1. get_character_draft
  2. confirm_character_creation
  3. 感知 committed=true 和 created_character_id
  4. 回复角色创建成功
```

ReAct 循环在以下情况终止：

- 已获得足够事实，可以向玩家提出一个下一步问题。
- 工具返回阻塞性校验错误。
- `committed=true`，角色已经真实创建。
- 达到工具调用次数上限。

单轮默认最多允许 6 次工具调用，防止模型无限循环。

## Revision 与并发控制

所有修改和提交工具必须携带 `expected_revision`。

StateGraph 执行前比较：

```text
expected_revision == current_revision
```

不一致时返回：

```json
{
  "success": false,
  "validation_errors": ["角色草稿已发生变化，请重新读取最新草稿。"],
  "allowed_actions": ["get_draft"]
}
```

ReAct Agent 收到 revision 冲突后必须重新调用 `get_character_draft`，不能使用旧结果继续更新或提交。

## 权限边界

外层 ReAct Agent：

- 可以选择和组合受控工具。
- 可以解释规则。
- 可以根据工具结果生成自然语言回复。
- 不能执行 SQL。
- 不能直接调用角色数据库服务。
- 不能自行修改 `CharacterDraft`。
- 不能自行设置 `committed=true`。

内层 StateGraph：

- 可以校验和更新草稿。
- 可以调用确定性规则服务。
- 不能自由生成最终玩家叙述。
- 只有确认流程可以调用角色持久化入口。

`confirm_character_creation`：

- 是唯一允许创建角色记录的工具。
- 必须收到玩家明确确认。
- 必须使用最新 revision。
- 必须在没有阻塞性错误且 `next_step == review` 时提交。

## ReAct 回复约束

最终回复必须以最近一次 ToolMessage 中的 `StateGraphResult` 为准：

- `committed=false` 时禁止使用“已创建”“已保存”“已定型”“创建完成”等表述。
- `committed=true` 时才能告知玩家角色创建成功。
- `validation_errors` 非空时必须解释错误，不能假装工具执行成功。
- `facts` 中的数字、规则结论和状态事实必须完整保留。
- `next_step` 未变化时不得声称流程已进入其他步骤。
- `allowed_actions` 不包含 `confirm` 时不得引导玩家确认提交。
- 回答 `help` 意图后必须继续原角色创建步骤。

## 状态与持久化

新增 `character_creation_messages` 表，包含以下字段：

- `id`
- `session_id`
- `role`：`user` 或 `assistant`
- `content`
- `metadata_json`
- `created_at`

每次用户请求在 Agent 执行前保存。Agent 成功执行后，再保存最终助手回复。加载会话时，系统读取最近的消息供 Agent 内部使用，同时不改变现有公开 API 的响应结构。

持久化的 `CharacterDraft` 仍然是角色状态的唯一权威数据源。消息历史只用于提供对话上下文，不作为角色状态。

## 结构化抽取

配置了可用模型时，抽取阶段通过大模型的结构化 JSON 输出解析用户输入。结构包含：

- `intent`
- `name`
- `race`
- `class_name`
- `background`
- `alignment`
- `notes`
- `ability_scores`

用户没有提供的值必须省略，不能由模型自行编造。抽取请求中同时包含当前角色草稿、最近的消息历史和本轮用户消息。

对于六项按固定顺序输入的属性值等无歧义格式，继续使用确定性解析器。确定性解析优先于大模型抽取，因为固定格式由程序处理更可靠、成本更低。

如果模型调用或结构化解析失败，系统继续使用中文和英文的确定性 fallback 解析器，保证基础功能可用。

元数据中的 `extractor` 用于说明本轮采用的抽取路径：

- `llm`：大模型结构化抽取
- `ordered_abilities`：程序解析六项属性值
- `fallback`：确定性备用解析

## 规则与状态更新

抽取得到的数据只是建议变更，必须由应用程序校验后才能写入角色草稿。

- 属性值遵循 PHB 27 点购点规则。
- 种族、职业和背景必须能映射到系统支持的标准规则。
- 上游选择变化后，必须使依赖该选择的后续步骤失效。
- 校验失败时保留上一次有效的角色草稿。
- 大模型不能自行将步骤标记为完成。
- 大模型不能自行创建、保存或定型角色。

只有后端状态图进入 `commit` 节点并成功写入角色表，角色才算真正创建完成。

## 普通对话输出

完成状态更新和校验后，回复生成器接收：

- 当前语言 `locale`
- 最近的对话历史
- 当前角色草稿摘要
- 本轮实际修改的字段
- 校验错误
- 下一个必填 slot 及其规则说明
- 确定性模板回复

存在可用模型时，大模型使用普通文本输出，为玩家生成自然语言回复。Prompt 必须要求：

- 使用前端当前选择的语言回答。
- 完整保留所有数字规则和校验事实。
- 需要继续收集信息时，只询问一个明确的下一步问题。
- 不得声称不存在于 `changed_fields` 中的状态变更。
- 不得声称角色已创建、已保存或已定型，除非后端已经成功提交角色。
- 不得输出 JSON 或 Markdown 代码块。

模型不可用、调用失败或返回空文本时，使用现有确定性模板回复。

响应元数据包含：

- `extractor`
- `responder`：`llm` 或 `template`
- `model_name`：存在可用模型时记录模型名称
- `changed_fields`
- `next_step`

## 上下文窗口策略

本阶段每次模型调用接收：

- 当前 `CharacterDraft`
- 最近最多 12 条角色创建消息
- 当前用户消息

长期有效的角色信息由结构化草稿保存，因此每次调用不需要发送全部历史消息。

当角色创建对话增长到超过当前限制时，再增加摘要机制。本阶段暂不实现长期摘要。

## 意图与流程路由

结构化抽取支持以下意图：

- `provide_info`：提供新的角色信息
- `update`：修改已经填写的信息
- `confirm`：确认创建角色
- `help`：咨询规则或询问可选方案

意图必须参与状态图路由：

- `confirm` 只有在 `next_step == "review"` 且没有校验错误时才能进入 `commit`。
- `help` 只能解释规则，不能提交角色，也不能结束角色创建。
- “确认”“确认创建”“完成”等明确表达应由确定性规则识别，避免依赖模型重复理解。
- “我不能学法术吗”等问题应识别为 `help`，解释当前职业的施法规则，并继续停留在当前创建步骤。

## 错误处理

- 结构化抽取失败：记录诊断元数据并使用 fallback。
- 抽取值不合法：返回本地化校验信息，并保留上一次有效状态。
- 普通回复生成失败：使用确定性模板。
- 数据库写入失败：不得保存误导性的助手回复。
- API key 和模型供应商原始错误不得暴露给前端。
- 模型回复与后端状态冲突时，以后端状态为准。

## 测试要求

测试必须证明：

- 最外层角色创建 Agent 使用真实的 ReAct 工具调用循环。
- ReAct Agent 只能访问设计中列出的受控工具。
- `apply_character_changes`、`validate_character_draft` 和
  `confirm_character_creation` 均通过 StateGraph 执行。
- StateGraph 返回的 `StateGraphResult` 被序列化为 `ToolMessage`。
- ReAct 的下一轮模型调用包含上一次 StateGraph 的 `ToolMessage`。
- ReAct 根据 `ToolMessage.next_step` 询问正确的下一项信息。
- ReAct 根据 `ToolMessage.validation_errors` 解释规则错误。
- `committed=false` 时，任何模型输出都不能宣称角色已创建。
- `committed=true` 且存在 `created_character_id` 时，才能回复创建成功。
- revision 冲突会强制 ReAct 重新读取草稿，不能继续使用旧 revision。
- 单轮工具调用超过 6 次时停止循环并使用安全 fallback。
- 用户和助手消息按会话持久化。
- 后续请求能接收之前的消息和当前角色草稿。
- 结构化抽取只更新用户明确提供的字段。
- 六项固定顺序属性值不进行不必要的模型抽取。
- 规则层拒绝不合法的结构化输出。
- 普通回复模型接收的是经过校验的状态和下一步事实。
- 响应元数据能够区分抽取路径和回复路径。
- 没有活动模型时，模板 fallback 仍然可用。
- 中文和英文输出遵循前端选择的语言。
- “完成”能够一次触发确认，不需要重复输入。
- `help` 意图不会提交角色。
- 未提交角色时，回复不得包含“已创建完成”“已定型”或“已保存”等表述。
- 战士询问法术时，应解释一级纯战士没有施法能力，但可通过种族特性、专长或后续兼职获得法术。

## 范围

本次设计只适用于角色创建 Agent。

以下功能仍属于独立需求：

- DM 冒险记忆
- 跨会话用户记忆
- 向量检索
- 长期上下文摘要
- 已创建角色的重新编辑流程
