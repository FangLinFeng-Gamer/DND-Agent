---
doc_id: isekai.generation_recovery_rules
status: active
layer: architecture
owner: architecture
created_at: 2026-07-19
updated_at: 2026-07-19
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.world_generation_manifest_rules
  - isekai.formation_rule_contract_rules
  - isekai.executable_numeric_algorithm_rules
  - isekai.static_world_runtime_rules
provides:
  - GenerationRunState
  - GenerationStageRunState
  - GenerationCheckpoint
  - GenerationResumeToken
  - GenerationRecoveryManager
  - GenerationRunValidator
---

# 异世界模式生成失败恢复与断点续生成规则

## 背景

世界生成已经拆成多个阶段，并定义了 `WorldGenerationManifest`、`GenerationStageContract`、`GeneratorOutputEnvelope`、`GeneratorOutputItem`、`StateTransition`、`EventLog` 和 `WorldSnapshot`。正常路径已经足够描述“生成成功后世界是什么”，但还不能描述以下情况：

- 生成器进程在某个阶段中途崩溃。
- 输出 envelope 已写入，但还没校验。
- 校验通过，但提交前崩溃。
- StateTransition 已提交，但生成控制状态没更新。
- `atomic_commit_group_id` 中某一步失败。
- 用户或后台任务重复提交同一阶段。
- 规则版本、内容包版本或算法版本变化后继续旧 run。
- manifest、checkpoint 或 output hash 损坏。

本文件解决 P1-08：定义可恢复、幂等、可拒绝、可审计的世界生成运行协议。

## 目标

- 定义 `GenerationRunState`、`GenerationStageRunState`、`GenerationCheckpoint` 和 `GenerationResumeToken`。
- 定义生成阶段状态机、checkpoint 写入时机、resume 协议、重试规则和回滚/拒绝规则。
- 保证任意崩溃点恢复后，系统只能回到“提交前”或“提交后”，不能出现半提交状态。
- 保证相同 seed、版本锁、输入和阶段输出，在失败重试后得到相同 canonical 世界。
- 明确哪些恢复控制记录不进入最终 `WorldStateContentHash`，避免崩溃次数污染世界内容。

## 非目标

- 不支持 P1 在生成完成后回滚已发布世界事实到旧阶段继续编辑。
- 不支持在版本锁变化后原地续跑已提交阶段。
- 不支持边生成边让玩家进入世界。
- 不支持跨机器分布式事务协议；P1 只要求单世界生成 run 的持久化和恢复。
- 不把恢复控制记录暴露给玩家、NPC、DM 叙事或 AI proposal。

## 核心原则

### 1. 控制账本和权威审计分离

生成过程中有两类持久记录：

```text
generation_control：恢复控制记录，例如 RunState、StageRunState、Checkpoint、ResumeToken。
generation_audit：最终审计记录，例如 WorldGenerationManifest、GeneratorOutputEnvelope、GeneratorOutputItem。
```

`generation_control` 用于断点续跑，不进入最终 `WorldStateContentHash`。它可以记录失败、重试、恢复 token 和 checkpoint 链。

`generation_audit` 是世界生成结果的 canonical 审计，必须进入最终 `WorldStateContentHash`。它只记录实际被接受的 manifest、envelope、output、random draw、algorithm_ref 和 value_hash。

规则：

```text
相同世界生成逻辑下，崩溃次数和恢复次数不同，最终 generation_audit 和 WorldStateContentHash 必须相同。
generation_control 可以被 WorldSnapshot 捕获用于恢复未完成生成，但不作为世界内容 hash 的一部分。
完成后的世界只能依赖 generation_audit、EventLog 和 WorldSnapshot 重放，不能依赖 generation_control。
```

### 2. checkpoint 只写在稳定边界

P1 不做行级、循环级或单个 random draw 级 checkpoint。checkpoint 只允许写在以下稳定边界：

```text
run_created
stage_claimed
stage_output_persisted
stage_output_validated
stage_commit_prepared
stage_committed
stage_rejected
stage_failed
run_completed
run_failed
```

如果进程在稳定边界之间崩溃，恢复器必须回到上一个稳定 checkpoint，然后按幂等规则继续。

### 3. 提交幂等键不能包含 attempt_no

同一个 stage、同一个 scope、同一个 input_hash 和同一个 output_hash，重复提交必须使用同一个 `idempotency_key`。`attempt_no` 只用于控制账本审计，不得进入 StateTransition 或 StateTransitionBatch 的幂等键。

### 4. 已提交阶段不重跑

恢复时如果发现某个阶段已经通过 EventLog 或 StateTransitionBatch 提交，并且 resulting hash 与 checkpoint 匹配，则该阶段只能标记为 `committed` 或 `skipped_idempotent`，不能再次执行生成器。

### 5. 未提交输出可以丢弃重算

未提交的 `GeneratorOutputEnvelope` 不是权威世界事实。恢复时如果 envelope 缺失、hash 不匹配或校验状态不完整，恢复器可以丢弃它，并用同一 input_hash、rule_id、algorithm_id 和 RandomDrawRef 重新生成。

### 6. 版本锁变化不原地续跑

`schema_version`、`registry_hash`、`rule_bundle_hash`、`content_pack_hash`、FormationRule 版本、NumericAlgorithm 版本或生成计划变化时，旧 run 不能直接 resume。

如果旧 run 尚未提交任何世界事实，可以创建新 run 从头生成。如果旧 run 已提交世界事实，必须进入 migration、branch 或 repair 流程，不能在同一 run 上继续。

## GenerationRunState

`GenerationRunState` 描述一次世界生成 run 的整体控制状态。它属于 `generation_control`，不属于 `world_facts`、`knowledge_facts` 或最终 `generation_audit`。

示例：

```json
{
  "run_id": "generation_run_isekai_world_001_main_001",
  "world_id": "isekai_world_001",
  "timeline_id": "main",
  "manifest_id": "manifest_isekai_world_001",
  "generation_plan_id": "worldgen_plan_p1_static_foundation",
  "seed_material_hash": "sha256:seed_material_hash",
  "run_input_hash": "sha256:run_input_hash",
  "version_lock": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "status": "running",
  "current_stage_contract_id": "stage_contract_terrain_candidate_formation",
  "latest_checkpoint_id": "gen_ckpt_000014",
  "latest_checkpoint_hash": "sha256:checkpoint_hash_000014",
  "completed_stage_run_ids": [
    "stage_run_region_climate_north_slope_wilds"
  ],
  "blocked_stage_run_ids": [],
  "failure": null,
  "resume_generation": {
    "resume_token_hash": "sha256:resume_token_hash",
    "resume_allowed": true
  },
  "control_hash": "sha256:generation_run_state_hash"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `run_id` | 生成 run ID。由 `world_id + timeline_id + generation_plan_id + seed_material_hash + run_input_hash` 稳定派生。 |
| `world_id` | 目标世界 ID。 |
| `timeline_id` | 目标时间线。P1 固定为 `main`。 |
| `manifest_id` | 本 run 最终要形成或引用的 WorldGenerationManifest ID。 |
| `generation_plan_id` | 生成计划 ID。 |
| `seed_material_hash` | RandomSeedMaterial 的 canonical hash。 |
| `run_input_hash` | 世界生成参数、内容包引用和生成计划的 canonical hash。 |
| `version_lock` | 本 run 的版本锁。必须与 Manifest、Snapshot 和 StateTransition version_context 对齐。 |
| `status` | run 状态，必须属于 `generation_run_status` 闭集。 |
| `current_stage_contract_id` | 当前调度到的 stage contract。未开始时为 `null`。完成后为最后阶段 ID。 |
| `latest_checkpoint_id` | 最新有效 checkpoint ID。 |
| `latest_checkpoint_hash` | 最新 checkpoint 的 hash。 |
| `completed_stage_run_ids` | 已完成且通过校验的 stage run ID 稳定有序列表。 |
| `blocked_stage_run_ids` | 因依赖、版本或人工修复阻塞的 stage run ID 稳定有序列表。 |
| `failure` | run 级失败摘要。没有失败时为 `null`。 |
| `resume_generation` | resume token 的控制引用。 |
| `control_hash` | `GenerationRunState` 自身 canonical hash。计算时排除 `control_hash` 字段。 |

P1 `generation_run_status` 闭集：

```text
created
running
paused
completed
failed
repair_required
aborted
```

规则：

```text
GenerationRunState 不记录真实时间、进程 ID、机器 ID、线程 ID 或日志路径。
真实时间和机器信息只能进入外部 telemetry，不能进入 control_hash 或 WorldStateContentHash。
status=completed 时，WorldGenerationManifest、EventLog 和 after_world_generation Snapshot 必须全部可验证。
status=repair_required 时，系统不能自动继续，也不能静默从头跑。
```

## GenerationStageRunState

`GenerationStageRunState` 描述一个 stage 在一个 scope 上的执行控制状态。

示例：

```json
{
  "stage_run_id": "stage_run_terrain_candidate_chunk_north_slope_12_08_00",
  "run_id": "generation_run_isekai_world_001_main_001",
  "stage_contract_id": "stage_contract_terrain_candidate_formation",
  "stage_index": 50,
  "scope": {
    "kind": "world_chunk",
    "id": "chunk_north_slope_12_08_00"
  },
  "status": "generated",
  "attempt_no": 2,
  "attempt_id": "attempt_stage_run_terrain_candidate_000002",
  "input_hash": "sha256:stage_input_hash",
  "output_id": "output_terrain_candidate_chunk_north_slope_12_08_00",
  "output_hash": "sha256:generator_output_envelope_hash",
  "validation_hash": null,
  "commit": {
    "commit_kind": "candidate_only",
    "idempotency_key": null,
    "atomic_commit_group_id": null,
    "event_sequence_start": null,
    "event_sequence_end": null,
    "resulting_state_hash": null
  },
  "failure": null,
  "control_hash": "sha256:stage_run_state_hash"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `stage_run_id` | stage + 阶段分区 scope 的稳定 ID。由 `run_id + stage_contract_id + scope.kind + scope.id` 派生。这里的 scope 必须来自 `GenerationStageContract.execution_scope` 的调度分区，不得使用 `FormationRuleContract.target_scope`。 |
| `run_id` | 所属 GenerationRunState。 |
| `stage_contract_id` | 对应 GenerationStageContract。 |
| `stage_index` | 阶段顺序，必须与 StageContract 一致。 |
| `scope` | 本 stage 分区 scope，由 `GenerationStageContract.execution_scope` 和当前分区 ID 决定。它不是 `FormationRuleContract.target_scope`。 |
| `status` | stage 状态，必须属于 `generation_stage_status` 闭集。 |
| `attempt_no` | 控制层尝试次数，从 1 开始。不得进入提交幂等键。 |
| `attempt_id` | 本次尝试 ID。由 `stage_run_id + attempt_no` 派生。 |
| `input_hash` | `GeneratorOutputEnvelope.input_refs` 的 canonical hash。 |
| `output_id` | 本 stage 产出的 GeneratorOutputEnvelope ID。未产出时为 `null`。 |
| `output_hash` | 产出 envelope 的 canonical hash。未产出时为 `null`。 |
| `validation_hash` | validator 结果摘要 hash。未校验时为 `null`。 |
| `commit` | 提交信息。candidate-only 阶段可为空提交；world_fact/knowledge_fact/event_draft 阶段必须填。 |
| `failure` | stage 级失败。没有失败时为 `null`。 |
| `control_hash` | StageRunState 自身 canonical hash。计算时排除 `control_hash` 字段。 |

P1 `generation_stage_status` 闭集：

```text
pending
claimed
running
generated
validated
commit_prepared
committing
committed
skipped_idempotent
rejected
failed
rolled_back
repair_required
```

状态语义：

| 状态 | 语义 | resume 行为 |
| --- | --- | --- |
| `pending` | 依赖未满足或尚未调度。 | 等待依赖。 |
| `claimed` | scope 已被本 run 占用，尚未执行生成器。 | 可重新进入 running。 |
| `running` | 生成器正在执行，未持久化完整输出。 | 丢弃临时结果，重新执行。 |
| `generated` | envelope 已持久化，但未完成 validator。 | 校验 output_hash，继续 validator；不匹配则重算。 |
| `validated` | envelope 通过 validator，尚未准备提交。 | 准备提交或跳过 candidate-only。 |
| `commit_prepared` | StateTransition/Batch 已规范化，尚未写 EventLog。 | 用同一 idempotency_key 重试提交。 |
| `committing` | 提交流程已开始，控制状态可能落后于 EventLog。 | 先查 EventLog 幂等结果，再决定标记 committed 或重试。 |
| `committed` | 权威提交完成，hash 匹配。 | 不重跑。 |
| `skipped_idempotent` | 重复执行发现已有等价提交。 | 视为 committed。 |
| `rejected` | validator 按确定规则拒绝。 | 同版本同输入不能重试；需要新 run 或修复输入。 |
| `failed` | 系统错误、进程崩溃或 IO 失败。 | 可按重试上限重试。 |
| `rolled_back` | 未提交控制记录已丢弃，权威状态未变。 | 可重新进入 pending。 |
| `repair_required` | hash 冲突、部分提交或账本损坏。 | 停止自动恢复。 |

## GenerationCheckpoint

`GenerationCheckpoint` 是恢复边界记录。它只描述控制状态，不替代 `WorldSnapshot`，也不包含完整 WorldState。

示例：

```json
{
  "checkpoint_id": "gen_ckpt_000014",
  "run_id": "generation_run_isekai_world_001_main_001",
  "checkpoint_index": 14,
  "checkpoint_kind": "stage_output_persisted",
  "stage_run_id": "stage_run_terrain_candidate_chunk_north_slope_12_08_00",
  "previous_checkpoint_hash": "sha256:checkpoint_hash_000013",
  "run_control_hash": "sha256:generation_run_state_hash",
  "stage_control_hash": "sha256:stage_run_state_hash",
  "input_hash": "sha256:stage_input_hash",
  "output_hash": "sha256:generator_output_envelope_hash",
  "event_sequence_boundary": 128,
  "state_hash_boundary": "sha256:world_state_hash_before_stage_commit",
  "checkpoint_hash": "sha256:checkpoint_hash_000014"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `checkpoint_id` | checkpoint ID。由 `run_id + checkpoint_index` 派生。 |
| `run_id` | 所属 run。 |
| `checkpoint_index` | 从 1 开始的连续整数。 |
| `checkpoint_kind` | checkpoint 类型，必须属于闭集。 |
| `stage_run_id` | 关联 stage run；run 级 checkpoint 可为 `null`。 |
| `previous_checkpoint_hash` | 前一个 checkpoint hash；第一个 checkpoint 为 `null`。 |
| `run_control_hash` | 写 checkpoint 时的 GenerationRunState.control_hash。 |
| `stage_control_hash` | 写 checkpoint 时的 GenerationStageRunState.control_hash；run 级 checkpoint 可为 `null`。 |
| `input_hash` | 当前 stage 输入 hash；不适用时为 `null`。 |
| `output_hash` | 当前 envelope 输出 hash；不适用时为 `null`。 |
| `event_sequence_boundary` | checkpoint 时已提交 EventLog sequence。没有 WorldState 时为 0。 |
| `state_hash_boundary` | checkpoint 时的 WorldStateContentHash。生成前可为空世界 hash。 |
| `checkpoint_hash` | checkpoint 自身 canonical hash。计算时排除 `checkpoint_hash` 字段。 |

P1 `generation_checkpoint_kind` 闭集：

```text
run_created
stage_claimed
stage_output_persisted
stage_output_validated
stage_commit_prepared
stage_committed
stage_rejected
stage_failed
run_completed
run_failed
```

规则：

```text
checkpoint_index 必须连续递增。
previous_checkpoint_hash 必须形成单链，不能分叉。
event_sequence_boundary 必须等于 checkpoint 写入时 WorldState.runtime_state.latest_event_sequence。
state_hash_boundary 必须能由 checkpoint 写入时 WorldStateContentHash 重算。
checkpoint 本身不是 EventLogEntry，不生成 StateTransition。
```

## GenerationResumeToken

`GenerationResumeToken` 是恢复入口指针。它不是权限令牌，不决定权威状态；恢复器必须重新校验 checkpoint 链、run state、stage state、manifest、EventLog 和 hash。

示例：

```json
{
  "resume_token_id": "resume_generation_run_isekai_world_001_000014",
  "run_id": "generation_run_isekai_world_001_main_001",
  "checkpoint_id": "gen_ckpt_000014",
  "checkpoint_hash": "sha256:checkpoint_hash_000014",
  "expected_run_control_hash": "sha256:generation_run_state_hash",
  "expected_version_lock": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "resume_token_hash": "sha256:resume_token_hash"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `resume_token_id` | resume token ID。 |
| `run_id` | 要恢复的 run。 |
| `checkpoint_id` | 恢复起点 checkpoint。 |
| `checkpoint_hash` | 恢复起点 checkpoint hash。 |
| `expected_run_control_hash` | token 生成时的 run control hash。 |
| `expected_version_lock` | token 生成时的版本锁。 |
| `resume_token_hash` | token 自身 canonical hash。计算时排除该字段。 |

规则：

```text
resume_token_hash 匹配不代表可以恢复，只代表 token 未损坏。
expected_version_lock 必须与当前加载的 registry/rule/content/numeric algorithm 版本锁完全一致。
expected_run_control_hash 不匹配时，恢复器必须重新读取最新 checkpoint；如果 checkpoint 链分叉，进入 repair_required。
```

## 幂等键与 ID 规则

### stage_run_id

```text
stage_run_id = stable_id("stage_run", {
  run_id,
  stage_contract_id,
  scope_kind,
  scope_id
})
```

`scope_kind` 和 `scope_id` 必须来自 `GenerationStageRunState.scope`，也就是阶段调度分区。`FormationRuleContract.target_scope.kind` 只描述规则输出目标，不能参与 `stage_run_id` 或 `output_id` 派生。

### output_id

```text
output_id = stable_id("generator_output", {
  run_id,
  stage_contract_id,
  scope_kind,
  scope_id,
  input_hash
})
```

同一 stage/scope/input 反复执行必须得到同一 output_id。如果生成器得出不同 output_hash，必须进入 `repair_required`，不能覆盖旧 envelope。

### attempt_id

```text
attempt_id = stable_id("generation_attempt", {
  stage_run_id,
  attempt_no
})
```

attempt_id 只用于控制账本。它不进入 `GeneratorOutputEnvelope`、`StateTransition`、EventLog 或最终 manifest hash。

### commit idempotency_key

```text
idempotency_key = sha256(CanonicalBytes({
  run_id,
  stage_contract_id,
  scope,
  input_hash,
  output_hash,
  operation_kind,
  version_lock
}))
```

规则：

```text
idempotency_key 不包含 attempt_no。
candidate-only 阶段可以没有 commit idempotency_key，但 output envelope 的 output_id 和 output_hash 仍必须幂等。
world_fact、knowledge_fact、event_draft 或 snapshot_ref 阶段必须有提交幂等键。
相同 idempotency_key 的重复提交必须返回已有提交结果或已有拒绝结果。
```

## checkpoint 写入时机

生成器必须按以下顺序写控制记录：

```text
1. 创建 GenerationRunState(status=created)，写 run_created checkpoint。
2. 满足依赖后，为每个 scope 创建 GenerationStageRunState(status=claimed)，写 stage_claimed checkpoint。
3. 执行生成器。输出完整 GeneratorOutputEnvelope 后，持久化 envelope 和 value payload，写 stage_output_persisted checkpoint。
4. 运行 GenerationOutputValidator。通过后写 validation_hash 和 stage_output_validated checkpoint；拒绝后写 stage_rejected checkpoint。
5. 对需要权威提交的 output，规范化 StateTransition 或 StateTransitionBatch，写 stage_commit_prepared checkpoint。
6. 调用 StateTransitionCommitter。提交开始后 status=committing。
7. 提交成功或发现幂等成功后，写 stage_committed checkpoint。
8. 所有 stage 完成后，生成最终 WorldGenerationManifest、world_fact_validation、initial_knowledge 和 after_world_generation Snapshot，写 run_completed checkpoint。
```

规则：

```text
stage_output_persisted 必须在 validator 前写入完整 envelope，否则恢复时只能重算，不能读取半个 envelope。
stage_commit_prepared 必须在 StateTransitionCommitter 前写入，确保崩溃后能用同一 idempotency_key 查询或重试。
stage_committed 必须在 EventLog 提交成功并重算 resulting_state_hash 后写入。
run_completed 必须在 after_world_generation Snapshot 创建和校验后写入。
```

## resume 协议

`GenerationRecoveryManager.resume(token)` 必须执行：

```text
1. 校验 GenerationResumeToken.resume_token_hash。
2. 读取 GenerationRunState、最新 GenerationCheckpoint 和 checkpoint 链。
3. 校验 checkpoint_hash、previous_checkpoint_hash、checkpoint_index 连续性。
4. 校验当前 version_lock 与 token.expected_version_lock、run.version_lock 完全一致。
5. 校验已持久化 WorldGenerationManifest、GeneratorOutputEnvelope、RandomDrawRef、algorithm_ref 和 value_hash 可重算。
6. 校验已提交 EventLog 的 sequence、event_hash、previous_event_hash 和 resulting_state_hash。
7. 对每个 StageRunState 按状态执行恢复动作。
8. 找到最早未完成且依赖已满足的 stage/scope，从稳定 checkpoint 继续。
```

状态恢复动作：

| stage 状态 | 恢复动作 |
| --- | --- |
| `pending` / `claimed` | 检查依赖，依赖满足后执行生成器。 |
| `running` | 丢弃未完成临时输出，attempt_no + 1 后重新执行生成器。 |
| `generated` | 校验 output_hash；匹配则运行 validator，不匹配则进入 repair_required。 |
| `validated` | 重新计算 validation_hash；匹配则准备提交，不匹配则进入 repair_required。 |
| `commit_prepared` | 使用同一 idempotency_key 重试 StateTransitionCommitter。 |
| `committing` | 先按 idempotency_key 查询 EventLog；已提交则标记 committed，未提交则重试提交。 |
| `committed` / `skipped_idempotent` | 校验 event range 和 resulting_state_hash，跳过执行。 |
| `rejected` | 返回确定性拒绝，不自动重试。 |
| `failed` | 如果 failure_code 属于可重试集合且未超重试上限，重新执行；否则 run failed。 |
| `rolled_back` | 权威状态未变，重新进入 pending。 |
| `repair_required` | 停止自动恢复，要求人工修复或丢弃 run。 |

## 失败分类

P1 `generation_failure_code` 闭集：

```text
generator_crash
io_write_failed
schema_invalid
validator_rejected
hash_mismatch
version_lock_mismatch
missing_checkpoint
checkpoint_chain_broken
missing_output_payload
output_hash_conflict
event_log_conflict
partial_atomic_commit_detected
state_hash_mismatch
retry_limit_exceeded
manual_abort
```

可自动重试：

```text
generator_crash
io_write_failed
missing_output_payload（仅 output 未提交且可重算时）
```

不可自动重试，必须拒绝或修复：

```text
schema_invalid
validator_rejected
hash_mismatch
version_lock_mismatch
checkpoint_chain_broken
output_hash_conflict
event_log_conflict
partial_atomic_commit_detected
state_hash_mismatch
retry_limit_exceeded
manual_abort
```

重试上限：

```text
同一个 stage_run_id 的自动重试上限为 3。
达到上限后 StageRunState.status=failed，GenerationRunState.status=failed。
如果 failure_code 是 hash、version、event 或 checkpoint 相关，不能消耗重试次数，直接 repair_required。
```

## 一个阶段失败后如何处理输出和随机 draw

规则：

```text
GeneratorOutputEnvelope 已通过 output_hash 校验时，可以保留并继续 validator 或提交。
GeneratorOutputEnvelope 缺失、payload 缺失或 output_hash 不匹配时，如果该 output 尚未提交，必须丢弃并重算。
已提交 output 对应的 RandomDrawRef 必须保留在 generation_audit 中，不能重抽。
未提交 output 的 RandomDrawRef 可以随 envelope 一起丢弃；重算时使用同一 logical_draw_id，结果必须一致。
不能因为某个候选被 validator 拒绝而消耗其他 logical_draw_id。
不能保留单个 RandomDrawRef 但丢弃其 CandidateSet 或 output payload；它们必须作为 envelope 整体保留或整体丢弃。
```

## atomic_commit_group_id 恢复规则

`atomic_commit_group_id` 非空时，提交必须通过 `StateTransitionBatch`。

恢复规则：

```text
1. 使用 batch.idempotency_key 查询提交结果。
2. 如果 batch 已完整提交，校验 event_sequence_start/end、final_state_hash 和每条 EventLogEntry.event_hash，标记 committed。
3. 如果 batch 未提交，且 WorldStateContentHash 仍等于 stage_commit_prepared 的 state_hash_boundary，则用同一 batch 重试。
4. 如果检测到组内部分 EventLogEntry 已存在但 batch final_state_hash 不存在或不匹配，状态改为 repair_required，failure_code=partial_atomic_commit_detected。
5. 不允许通过反向 StateTransition 自动回滚部分提交；部分提交代表底层原子提交器违反约束，必须人工修复或从 Snapshot 恢复。
```

## 重复执行判定

重复执行同一 stage/scope 时，按顺序判定：

```text
1. stage_run_id 不存在：创建新 StageRunState。
2. stage_run_id 存在且 status=committed：校验 output_hash 和 event hash；匹配则返回 skipped_idempotent。
3. stage_run_id 存在且 output_id 相同、output_hash 相同、未提交：继续后续 validator 或 commit。
4. stage_run_id 存在且 output_id 相同、output_hash 不同：repair_required，failure_code=output_hash_conflict。
5. stage_run_id 存在但 input_hash 不同：旧 stage run 不可复用；如果旧输出未提交可 rolled_back 后新建 stage run；如果已提交则 version/run 冲突，repair_required。
6. 相同 idempotency_key 的 StateTransition 已存在：返回第一次提交或拒绝结果。
```

## 版本变化后的复用规则

可复用要求：

```text
schema_version 完全一致。
registry_hash 完全一致。
rule_bundle_hash 完全一致。
content_pack_hash 完全一致。
FormationRuleContract.rule_version 完全一致。
NumericAlgorithmSpec.algorithm_version 完全一致。
GenerationStageContract.stage_contract_id 和 stage_index 完全一致。
```

处理：

```text
未提交任何权威事实的旧 run：可以标记 aborted，创建新 run 从头开始。
已提交权威事实但未完成的旧 run：不能原地 resume，必须进入 repair_required。
已完成旧 run：只能通过迁移流程升级，不能修改旧 manifest。
```

## 审计损坏与修复边界

自动恢复只能修复“控制状态落后于权威提交”的情况，例如 EventLog 已提交但 StageRunState 还停在 `committing`。

以下情况禁止自动修复：

```text
checkpoint 链断裂。
同 checkpoint_index 出现两个不同 checkpoint_hash。
output_hash 与 payload 重算结果不一致。
value_hash 与 value_ref 重算结果不一致。
EventLog.previous_event_hash 链断裂。
EventLog.resulting_state_hash 与重放结果不一致。
atomic commit group 出现部分提交。
version_lock 不一致。
```

这些情况必须进入 `repair_required`，由人工选择：

```text
从最近有效 WorldSnapshot 恢复。
丢弃未提交 run 并从头生成。
创建迁移或修复补丁。
保留旧世界只读，另起新 world_id。
```

## 与其他文档关系

| 文档 | 关系 |
| --- | --- |
| 世界生成输出清单规则 | `GeneratorOutputEnvelope` 和 `GeneratorOutputItem` 是可恢复阶段的输出单位；本文件定义运行状态和恢复控制。 |
| FormationRule 合约与注册表规则 | stage resume 必须使用同一 rule_id/rule_version，不能在旧 run 中换规则。 |
| 可执行数值算法规则 | ready 数值算法必须可重放；恢复时用 algorithm_ref 校验 output 是否可复算。 |
| 确定性随机协议 | 恢复重算必须使用同一 RandomSeedMaterial、RandomStreamRef、RandomDrawRef 和 CandidateSet。 |
| 静态世界运行规则 | 权威提交仍由 StateTransitionCommitter 和 EventLog 负责；checkpoint 不是 EventLog。 |
| 字段域与注册表规则 | GenerationRunState、StageRunState、Checkpoint、ResumeToken 字段必须有 FieldSpec；状态和 failure_code 是闭集。 |

## 推荐实现顺序

1. 实现 `GenerationRunStore`，持久化 `GenerationRunState`、`GenerationStageRunState`、`GenerationCheckpoint` 和 `GenerationResumeToken`。
2. 实现 `GenerationCheckpointWriter`，按稳定边界写 checkpoint 链。
3. 实现 `GenerationRunValidator`，校验 control hash、checkpoint 链、output hash、value hash 和版本锁。
4. 在 generation scheduler 中引入 stage 状态机。
5. 在 `GenerationOutputValidator` 后写 `stage_output_validated` checkpoint。
6. 在 `StateTransitionCommitter` 前写 `stage_commit_prepared` checkpoint，并使用稳定 idempotency_key。
7. 实现 `GenerationRecoveryManager.resume(token)`。
8. 为 atomic commit group 增加 batch 幂等查询和部分提交检测。
9. 增加崩溃注入测试。

## 测试清单

```text
test_generation_run_state_has_stable_run_id
test_stage_run_id_uses_execution_scope_not_target_scope
test_generation_checkpoint_chain_hashes_are_contiguous
test_generation_resume_token_does_not_bypass_checkpoint_validation
test_generation_running_stage_reruns_with_same_output_hash_after_crash
test_generated_stage_reuses_persisted_envelope_when_hash_matches
test_generated_stage_hash_conflict_enters_repair_required
test_validated_stage_resumes_to_commit_prepared
test_committing_stage_queries_event_log_before_retry
test_committed_stage_is_not_rerun_on_resume
test_stage_attempt_no_not_in_commit_idempotency_key
test_duplicate_stage_commit_returns_existing_result
test_atomic_commit_group_resume_retries_when_no_event_written
test_atomic_commit_group_partial_event_log_enters_repair_required
test_version_lock_mismatch_rejects_resume
test_uncommitted_version_mismatch_can_start_new_run
test_committed_version_mismatch_enters_repair_required
test_missing_output_payload_reruns_only_if_uncommitted
test_rejected_stage_does_not_auto_retry_same_input
test_generation_control_not_in_final_world_state_content_hash
test_generation_crash_injection_at_each_checkpoint_boundary_recovers_or_rejects_deterministically
```

## 已确认决策

1. P1 支持断点续生成，不把 P1-08 降级为只支持一次性原型。
2. 恢复控制记录属于 `generation_control`，不进入最终 WorldStateContentHash。
3. 最终可审计世界依赖 `generation_audit`、EventLog 和 Snapshot，不依赖 generation_control。
4. checkpoint 只写在稳定边界，不做循环级 checkpoint。
5. 已提交阶段不重跑，未提交输出可以整体丢弃重算。
6. 版本锁变化不原地续跑。
7. atomic commit group 出现部分提交时不自动反向回滚，必须进入 repair_required。
