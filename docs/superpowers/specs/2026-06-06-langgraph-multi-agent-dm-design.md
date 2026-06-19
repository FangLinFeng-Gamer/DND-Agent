# LangGraph Multi-Agent DM Design

## 目标

使用 LangChain 和 LangGraph 重构 DM Agent。主 DM Agent 使用 ReAct 进行意图分析、任务规划和结果聚合；规则确定、执行顺序固定的子 Agent 使用显式 StateGraph；剧情、探索、社交、NPC 和角色创建引导等开放任务使用受限 ReAct。最终叙事统一由 narration agent 生成。

现有 FastAPI 路由、SQLite 数据、前端 NDJSON 流式协议和 `TemplateDMProvider` 离线降级保持兼容。

## 权限模型

主 DM ReAct Agent只能调用注册的子 Agent 工具并聚合结构化结果，不能投骰、不能直接写数据库、不能生成最终叙事。

开放式 ReAct 子 Agent可以查询上下文和规则，并提出结构化计划或 patch，但不能持久化状态：

- story agent：主线、支线、任务与选择点。
- exploration agent：解释自由探索动作并决定需要调用的确定性流程。
- social agent：社交目标、NPC 反应与可能的检定。
- npc agent：按 NPC 性格、目标、关系和环境生成行为提案。
- rules research agent：只读查询规则与世界资料。
- character creation agent：通过自然语言引导玩家创建角色草稿。
- narration agent：根据已经确认的事实生成最终 DM 文本。

确定性子 Agent使用 StateGraph，只接受结构化输入并返回结构化结果：

- ability check agent。
- saving throw agent。
- combat agent。
- character validation agent。
- scene update agent。
- memory agent。
- commit agent。

`commit agent` 是游戏状态写入的唯一入口。角色创建只有在固定校验通过且玩家明确确认后才调用角色持久化服务。

## DM 执行图

每次玩家动作建立 `DMGraphState`：

1. `load_context` 加载冒险、角色、场景、战斗状态、摘要和重要事件。
2. `plan` 由主 ReAct Agent 选择开放式或确定性子 Agent。
3. `execute_plan` 按计划执行工具，使用 `action_id` 防止同一动作重复结算。
4. `validate_patches` 验证检定、战斗、场景、NPC 和世界事件结果。
5. `narrate` 将已确定事实交给 narration agent。
6. `commit` 事务性保存场景、消息、世界事件和记忆。

同步和流式调用共用同一个 graph runner。流式接口继续产生 `status`、`player_message`、`delta` 和 `final`。只有 narration agent 的自然语言内容产生 `delta`。

## 角色创建图

角色创建使用独立会话和草稿：

1. character creation ReAct agent读取用户消息与当前草稿。
2. Agent查询种族、职业、背景和规则，并更新结构化草稿。
3. character validation StateGraph检查必填字段、合法种族和职业、属性范围、生命值及装备/技能约束。
4. 系统向玩家展示完整角色卡与校验问题。
5. 只有收到明确确认后，commit agent创建角色。

第一版草稿保存在 SQLite，支持中断后继续。缺少的 PHB 数据必须报告为暂不支持，不能由模型编造。

## 模型适配

保留现有 OpenAI-compatible 模型配置。新增 LangChain `BaseChatModel` 适配层，使 `create_agent` 和 StateGraph 节点可以复用当前模型配置、同步调用和流式调用。

所有 Agent 输出使用 Pydantic schema。结构化输出失败、模型请求失败或图执行失败时：

1. 不提交任何未验证 patch。
2. DM 对话回退到 `TemplateDMProvider`。
3. narration agent 失败时，根据确定性结果生成模板叙事。

## 测试要求

- 主 Agent只能访问子 Agent工具，不能访问写数据库工具。
- 固定子 Agent确实由 `StateGraph` 编译。
- 检定结果来自 `CombatService`，不是模型输出。
- scene/world event 只有 commit agent可持久化。
- ReAct 失败和 StateGraph 失败均触发离线模板。
- 同步和流式接口保持现有响应结构。
- 角色草稿可继续、非法角色不会创建、确认后才创建。
- 现有测试全部通过。
