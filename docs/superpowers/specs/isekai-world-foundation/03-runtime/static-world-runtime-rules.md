---
doc_id: isekai.static_world_runtime_rules
status: active
layer: runtime
owner: architecture
created_at: 2026-07-11
updated_at: 2026-07-18
depends_on:
  - isekai.field_domain_registry_rules
  - isekai.deterministic_random_protocol_rules
  - isekai.location_space_rules
  - isekai.climate_terrain_formation_rules
  - isekai.world_origin_history_rules
  - isekai.world_knowledge_rules
  - isekai.world_object_rules
  - isekai.world_generation_manifest_rules
provides:
  - GameTimeInterval
  - StaticWorldRuntimeState
  - WorldTimeState
  - WorldRuntimeInitialization
  - WeatherState
  - EnvironmentState
  - EnvironmentResidualEffectState
  - HazardSource
  - ObstacleSource
  - PassabilityReducer
  - StateTransition
  - StateTransitionBatch
  - EventLog
  - WorldSnapshot
---

# 异世界模式静态世界运行规则设计

## 背景

地点、空间、物品、气候、地形、生态已经能描述“世界里有什么”。但即使暂时不考虑玩家、不考虑智慧生物、不做动态社会模拟，世界仍然需要一组运行时事实来保证一致性。

本设计定义静态世界的基础运行层：

```text
WorldState
-> WorldTimeState
-> WeatherState
-> EnvironmentState
-> EnvironmentResidualEffectState
-> HazardSource / ObstacleSource
-> PassabilityReducer
-> StateTransition / StateTransitionBatch
-> EventLog
-> WorldSnapshot
```

这里的“静态”不是世界永远不变，而是指世界不会自行进行复杂社会和生态推演。世界状态只会因为确定性生成器、规则 resolver、迁移工具或明确时间推进而改变。

## 目标

- 定义当前世界时间和季节。
- 定义短期天气状态如何随时间确定性变化。
- 定义按空间位置派生或缓存的光照、温度、天气和地表环境。
- 定义危险和障碍如何存在于空间中。
- 定义状态变化必须如何写入事件日志。
- 定义快照如何保存和校验世界状态。
- 明确历史来历由世界模型层 `OriginEvent / OriginMetadata` 定义，运行时只负责校验引用和重放边界。
- 与已有地点/空间、气候地形、自然生态、WorldObject 文档保持字段一致。

## 非目标

- 不定义玩家状态、背包、饥饿、口渴、疲劳、伤势。
- 不定义 NPC、智慧生物、社会组织、任务线。
- 不定义声音、气味、痕迹感知系统。
- 不做复杂材料物理模拟。
- 不允许 LLM 直接修改权威 WorldState。

## 核心原则

### 1. 当前时间是世界事实

时间和季节不是 DM 文案，必须进入全局 `WorldTimeState`。光照、温度、天气和地表效果会随 Region、WorldChunk、Site、LocationNode、Zone 变化，必须进入局部 `EnvironmentState`，不能放在全局时间状态里。

### 2. 危险和障碍必须有来源，通行结论必须单写者

“这里很危险”“不能过去”不能只写在旁白里。必须能落到 `HazardSource`、`ObstacleSource`、`WorldObject` 状态或 Edge 的有效通行结论。

`ChunkEdge`、`LocationEdge` 和 `SiteBoundaryEdge` 的通行状态分为两层：

```text
base_passability / base_traversal
-> 静态地形、水文、道路、结构基础事实生成

passability_override
-> ObstacleSource、portal 状态、环境变化或规则动作产生的覆盖来源

effective_passability / effective_traversal
-> 只能由 PassabilityReducer 从 base + active overrides 聚合写入
```

任何 Deriver、Resolver、内容包或 LLM proposal 都不能直接写 `effective_passability` / `effective_traversal`。

### 3. EventLog 是状态变化账本

事件日志不是玩家看到的叙事日志。它记录权威状态为什么变化、谁触发变化、改了哪些字段。

EventLog 也不是 NPC、玩家或社会群体的记忆。一次状态提交完成后，谁知道这件事必须由 [知识、发现与事件知情规则](./world-knowledge-rules.md) 中的 `KnowledgePropagation` 和 `KnowledgeState` 表达。

### 4. Snapshot 是调试和恢复边界

快照不是剧情存档说明，而是某个 `event_sequence` 对应的完整或可恢复世界状态。

### 5. P0 只做轻量规则

本阶段只定义足够支撑静态探索和一致性验证的规则，不做温度流体模拟、材料破坏模拟、历史年表模拟。

## 数据模型

### GameTimeInterval

`GameTimeInterval` 是运行时所有时间片的通用结构。天气片段、局部环境缓存、残留环境效果都必须使用这个结构表达有效期。

```json
{
  "start_world_minute": 16920,
  "end_world_minute": 17100
}
```

规则：

```text
GameTimeInterval 使用绝对整数世界分钟。
区间语义固定为半开区间：[start_world_minute, end_world_minute)。
start_world_minute 包含在区间内，end_world_minute 不包含在区间内。
end_world_minute 必须大于 start_world_minute。
禁止用 from_day、from_minute_of_day、until_day、until_minute_of_day 表达运行时有效期。
```

### StaticWorldRuntimeState

`StaticWorldRuntimeState` 是世界运行时状态的入口。它挂在 `WorldState` 下，不替代地点、对象、生态等权威表。

```json
{
  "world_id": "isekai_world_001",
  "version_lock": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "runtime_state": {
    "time_state_id": "time_isekai_world_001",
    "active_weather_state_ids": [
      "weather_north_slope_day12_segment03"
    ],
    "active_environment_state_ids": [
      "env_chunk_north_slope_12_08_00",
      "env_node_old_furnace_inn_front_hall"
    ],
    "active_environment_residual_effect_ids": [
      "residual_wet_chunk_north_slope_12_08_00_001"
    ],
    "active_hazard_ids": ["hazard_slippery_ridge_01"],
    "active_obstacle_ids": ["obstacle_east_cliff_01"],
    "latest_event_sequence": 128,
    "latest_snapshot_id": "snapshot_after_world_generation"
  }
}
```

### WorldTimeState

`WorldTimeState` 表示当前世界日期、季节和日内时间。它是全局状态，不表达具体地点的光照、温度或天气。

```json
{
  "id": "time_isekai_world_001",
  "world_id": "isekai_world_001",
  "calendar": {
    "year": 1,
    "day": 12,
    "season": "late_autumn",
    "season_day": 42,
    "calendar_label": "深秋第十二日"
  },
  "clock": {
    "absolute_minute": 16920,
    "minute_of_day": 1080,
    "time_band": "dusk"
  },
  "time_modifiers": {
    "seasonal_daylight_profile": "late_autumn_short_day"
  }
}
```

### WorldRuntimeInitialization

`WorldRuntimeInitialization` 是静态世界生成完成后、初始天气之前的强制阶段。完整空间基础是最低前提，但不能在空间刚物化后立刻启动；P0 的 `GenerationStageContract` 必须直接依赖 `origin_attachment`，从而保证 SettlementAnchor、OriginEventCandidate、静态边与通行、Resource/Flora/Fauna、Site/Location、WorldObject、聚落社会、OriginEvent 物化和 OriginMetadata 附着都已完成。

初始化器读取 `WorldGenerationParameters.initial_time`；下面是该子对象的 schema：

```json
{
  "initial_time": {
    "absolute_minute": 0,
    "year": 1,
    "day": 1,
    "season": "spring",
    "season_day": 1,
    "seasonal_daylight_profile": "spring_standard_day"
  }
}
```

| 字段 | 含义与约束 |
| --- | --- |
| `initial_time.absolute_minute` | 世界开始时的绝对分钟，必须是非负整数。 |
| `initial_time.year` | 初始世界年份，P0 必须大于等于 1。 |
| `initial_time.day` | 初始世界运行日，P0 必须大于等于 1。 |
| `initial_time.season` | 初始季节，必须属于 season 闭集。 |
| `initial_time.season_day` | 初始季节内日序，必须落在季节日历范围。 |
| `initial_time.seasonal_daylight_profile` | 初始季节使用的昼夜长度规则 ID，必须存在于 registry。 |

初始化器必须派生而不能由输入直接指定：

```text
WorldTimeState.clock.minute_of_day = absolute_minute % 1440
WorldTimeState.clock.time_band =
  TimeBandDeriver(minute_of_day, season, seasonal_daylight_profile)
WorldTimeState.calendar.calendar_label =
  CalendarLabelFormatter(year, day, season, season_day)
```

`WorldRuntimeInitialization` 在同一原子提交中创建：

```text
WorldTimeState：当前世界日期和时钟事实。
StaticWorldRuntimeState：运行时入口和当前 active 状态 ID 索引。
```

初始 `StaticWorldRuntimeState` 必须满足：

```text
world_id = 已提交 World.id
version_lock = World.version_lock = WorldGenerationManifest 版本锁
runtime_state.time_state_id = 新建 WorldTimeState.id
active_weather_state_ids = []
active_environment_state_ids = []
active_environment_residual_effect_ids = []
active_hazard_ids = []
active_obstacle_ids = []
latest_event_sequence = 本次原子提交中 TimeInitialized 获得的 sequence
latest_snapshot_id = null
```

提交成功时追加 `TimeInitialized`，并在同一原子提交中把 `runtime_state.latest_event_sequence` 设为该事件的 `sequence`。`WeatherFormation` 必须依赖该阶段，并读取已提交的 `WorldTimeState`；不能自行补造当前时间。

### WeatherState

`WeatherState` 表示一个短期天气时间片。它是权威运行时状态，不是 DM 文案，也不是 `WorldTimeState` 的字段。

P0 常规天气挂在 Region 上。`scope=world_chunk` 只用于明确的局部天气覆盖，例如异常雾、山脊局部强风、局部暴雨；此时必须引用父级 Region 天气。

```json
{
  "id": "weather_north_slope_day12_segment03",
  "world_id": "isekai_world_001",
  "scope": "region",
  "region_id": "north_slope_wilds",
  "chunk_id": null,
  "parent_weather_state_id": null,
  "previous_weather_state_id": "weather_north_slope_day12_segment02",
  "coverage_priority": "base_region",
  "condition": "light_rain",
  "intensity": "normal",
  "temperature_c": 7,
  "wind": "moderate",
  "visibility_modifier": -1,
  "ground_effects": ["wet", "muddy"],
  "valid_for": {
    "start_world_minute": 16920,
    "end_world_minute": 17100
  },
  "generated_by": {
    "system": "WeatherFormation",
    "rule_id": "weather.transition_by_climate_season_terrain",
    "random_draw_ref": {
      "stream_ref": {
        "protocol_version": "drp.v1",
        "domain": "weather_generation",
        "rule_id": "weather.transition_by_climate_season_terrain",
        "scope_id": "region:north_slope_wilds",
        "seed_material_hash": "sha256:seed_material_hash"
      },
      "logical_draw_id": "weather_segment_day12_1080",
      "draw_index": 0,
      "draw_kind": "weighted_choice",
      "candidate_set_hash": "sha256:candidate_set_hash",
      "result_id": "weather_condition:light_rain"
    }
  }
}
```

### EnvironmentState

`EnvironmentState` 表示某个具体空间范围在当前时间下的局部环境。它可以按 Region、WorldChunk、Site、LocationNode 或 Zone 派生，也可以缓存到 WorldState 中。

```json
{
  "id": "env_chunk_north_slope_12_08_00",
  "world_id": "isekai_world_001",
  "scope": "world_chunk",
  "region_id": "north_slope_wilds",
  "chunk_id": "chunk_north_slope_12_08_00",
  "source_time_state_id": "time_isekai_world_001",
  "weather_state_id": "weather_north_slope_day12_segment03",
  "light": {
    "light_level": "dusk",
    "natural_light": "low",
    "visibility_modifier": -1,
    "requires_light_source": false
  },
  "temperature": {
    "ambient_c": 7,
    "temperature_band": "cold"
  },
  "ground_effects": ["wet", "slippery"],
  "derived_from": {
    "terrain_id": "chunk_north_slope_12_08_00",
    "weather_state_id": "weather_north_slope_day12_segment03",
    "time_state_id": "time_isekai_world_001",
    "residual_effect_ids": [
      "residual_wet_chunk_north_slope_12_08_00_001"
    ]
  },
  "valid_for": {
    "start_world_minute": 16920,
    "end_world_minute": 16980
  }
}
```

室内示例：

```json
{
  "id": "env_node_old_furnace_inn_front_hall",
  "world_id": "isekai_world_001",
  "scope": "site_node",
  "site_id": "old_furnace_inn",
  "node_id": "old_furnace_inn_front_hall",
  "source_time_state_id": "time_isekai_world_001",
  "weather_state_id": null,
  "light": {
    "light_level": "dim",
    "natural_light": "none",
    "visibility_modifier": 0,
    "requires_light_source": false
  },
  "temperature": {
    "ambient_c": 16,
    "temperature_band": "cool"
  },
  "ground_effects": [],
  "derived_from": {
    "location_node_id": "old_furnace_inn_front_hall",
    "heat_source_object_ids": ["hearth_01"],
    "light_source_object_ids": ["hearth_01"]
  },
  "valid_for": {
    "start_world_minute": 16920,
    "end_world_minute": 16980
  }
}
```

### EnvironmentResidualEffectState

`EnvironmentResidualEffectState` 表示天气、地形、对象或规则事件结束后仍然留在局部空间里的环境残留。它是权威运行时状态，不是 `WeatherState.ground_effects` 的副本。

示例：小雨结束后，山脊地面仍保持湿滑一段时间。

```json
{
  "id": "residual_wet_chunk_north_slope_12_08_00_001",
  "world_id": "isekai_world_001",
  "scope": "world_chunk",
  "region_id": "north_slope_wilds",
  "chunk_id": "chunk_north_slope_12_08_00",
  "site_id": null,
  "node_id": null,
  "zone_id": null,
  "effect_type": "wet",
  "intensity": "moderate",
  "source": {
    "source_kind": "weather_state",
    "source_entity_id": "weather_north_slope_day12_segment03",
    "source_effect": "light_rain"
  },
  "valid_for": {
    "start_world_minute": 17100,
    "end_world_minute": 17340
  },
  "decay": {
    "decay_rule_id": "environment_residual.rain_wet_decay",
    "mode": "step_down",
    "step_minutes": 60,
    "next_intensity": "light"
  },
  "state": "active"
}
```

### HazardSource

`HazardSource` 表示会造成风险、伤害、污染、状态恶化或失败后果的世界来源。

```json
{
  "id": "hazard_slippery_ridge_01",
  "source_kind": "terrain",
  "source_entity_ids": ["chunk_north_slope_12_08_00", "edge_chunk_12_08_00_to_13_08_00"],
  "generated_by": {
    "system": "TerrainHazardObstacleDeriver",
    "rule_id": "terrain.steep_slope_to_fall_risk",
    "pass": "terrain_hazard_pass"
  },
  "hazard_type": "fall_risk",
  "location": {
    "scope": "chunk_edge",
    "edge_id": "edge_chunk_12_08_00_to_13_08_00"
  },
  "severity": "medium",
  "visibility": "hinted",
  "trigger": {
    "on_actions": ["move", "climb", "search"],
    "conditions": ["rain_or_wet_ground", "low_light"]
  },
  "effects": [
    {
      "effect_type": "injury_risk",
      "magnitude": "medium",
      "reason": "湿滑岩面容易失足"
    }
  ],
  "mitigations": [
    {
      "method": "careful_movement",
      "time_multiplier": 1.5,
      "risk_delta": -1
    }
  ],
  "state": {
    "active": true,
    "depleted": false
  }
}
```

### ObstacleSource

`ObstacleSource` 表示阻挡、限制或改变通行方式的世界来源。

```json
{
  "id": "obstacle_east_cliff_01",
  "source_kind": "terrain",
  "source_entity_ids": ["chunk_north_slope_12_08_00", "edge_chunk_12_08_00_to_13_08_00"],
  "generated_by": {
    "system": "TerrainHazardObstacleDeriver",
    "rule_id": "terrain.cliff_to_obstacle",
    "pass": "terrain_obstacle_pass"
  },
  "obstacle_type": "cliff",
  "location": {
    "scope": "chunk_edge",
    "edge_id": "edge_chunk_12_08_00_to_13_08_00"
  },
  "blocks": ["move"],
  "passability_override": {
    "target_edge_ids": ["edge_chunk_12_08_00_to_13_08_00"],
    "state": "blocked",
    "blocked_reason": "东侧是断崖，不能直接通行",
    "conditions": [],
    "time_delta_minutes": null,
    "risk_tags": ["fall"],
    "priority": 90
  },
  "bypass_options": [
    {
      "action": "绕行",
      "target_edge_id": "edge_chunk_12_08_00_to_12_09_00",
      "extra_time_minutes": 30
    },
    {
      "action": "寻找攀爬点",
      "requires": ["climb_route_discovered"]
    }
  ],
  "state": {
    "active": true,
    "removable": false
  }
}
```

### StateTransition

`StateTransition` 是所有权威状态变化进入 `WorldState` 和 `EventLog` 的唯一提交包络。生成器、resolver、知识传播、AI 社会结算和迁移工具可以先产生内部草稿，但进入 `StateTransitionValidator` 后必须规范化为本节 schema；只有规范化后的 `StateTransition` 可以交给 `StateTransitionCommitter`。

`StateTransition` 不是 DM 叙事、不是 UI 投影，也不是 LLM proposal。它只表达一次确定性的状态变化：在指定前置状态上，按顺序应用一组 change，得到唯一 post-state hash，并生成一条 EventLogEntry。

```json
{
  "transition_id": "st_hazard_slippery_ridge_000128",
  "world_id": "isekai_world_001",
  "timeline_id": "main",
  "command_id": "cmd_worldgen_terrain_hazard_pass_0001",
  "idempotency_key": "sha256:transition-input-hash",
  "producer": {
    "kind": "world_generator",
    "id": "terrain_hazard_pass",
    "rule_id": "terrain.steep_slope_to_fall_risk"
  },
  "caused_by": {
    "kind": "world_generator",
    "id": "terrain_hazard_pass"
  },
  "event_type": "HazardCreated",
  "occurred_at": {
    "absolute_minute": 16920,
    "day": 12,
    "minute_of_day": 1080
  },
  "expected_sequence": 127,
  "expected_entity_revisions": [
    {
      "entity_type": "WorldChunk",
      "entity_id": "chunk_north_slope_12_08_00",
      "version_check": {
        "kind": "state_revision",
        "expected_revision": 4,
        "expected_hash": null
      }
    }
  ],
  "preconditions": [
    {
      "path": "WorldChunk.chunk_north_slope_12_08_00.terrain.slope",
      "operator": "equals",
      "expected": "steep"
    }
  ],
  "ordered_changes": [
    {
      "op": "create",
      "entity_type": "HazardSource",
      "entity_id": "hazard_slippery_ridge_01",
      "path": "",
      "value": {
        "id": "hazard_slippery_ridge_01",
        "source_kind": "terrain",
        "source_entity_ids": [
          "chunk_north_slope_12_08_00",
          "edge_chunk_12_08_00_to_13_08_00"
        ],
        "generated_by": {
          "system": "TerrainHazardObstacleDeriver",
          "rule_id": "terrain.steep_slope_to_fall_risk",
          "pass": "terrain_hazard_pass"
        },
        "hazard_type": "fall_risk",
        "location": {
          "scope": "chunk_edge",
          "edge_id": "edge_chunk_12_08_00_to_13_08_00"
        },
        "severity": "medium",
        "visibility": "hinted",
        "trigger": {
          "on_actions": ["move", "climb", "search"],
          "conditions": ["rain_or_wet_ground", "low_light"]
        },
        "effects": [
          {
            "effect_type": "injury_risk",
            "magnitude": "medium",
            "reason": "湿滑岩面容易失足"
          }
        ],
        "mitigations": [
          {
            "method": "careful_movement",
            "time_multiplier": 1.5,
            "risk_delta": -1
          }
        ],
        "state": {
          "active": true,
          "depleted": false
        }
      }
    }
  ],
  "version_context": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "previous_state_hash": "sha256:previous-state-hash",
  "previous_event_hash": "sha256:event-hash-000127",
  "resulting_state_hash": "sha256:post-state-hash",
  "event_hash": "sha256:event-hash-000128",
  "summary": "在北坡脊线东侧生成湿滑坠落风险"
}
```

规则：

```text
StateTransition 是提交输入的 canonical schema，其他文档只能引用本节，不能重新定义字段。
transition_id 必须在同一 world_id + timeline_id 内唯一。
timeline_id P0 只允许 main；分支世界、回滚沙盒和模拟分支留到后续版本。
command_id 表示上游命令或批次，例如玩家命令、生成阶段输出、AI proposal resolution、知识传播任务或迁移任务。
idempotency_key 必须由 command_id、producer、event_type、preconditions、ordered_changes 和 version_context 的 canonical bytes 计算；相同 key 重试必须返回同一已提交结果或同一拒绝结果，不能重复结算。
producer 表示产生 StateTransition 的系统组件；producer.kind 必须使用 `event_cause_kind` 闭集。知识传播和 AI 社会结算不新增 kind，应使用 `producer.kind=resolver`，并用 `producer.id=KnowledgePropagationResolver` 或 `producer.id=SocialActionResolver` 区分。caused_by 表示写入 EventLogEntry 的事件来源。二者可以相同，也可以不同，例如 SocialActionResolver 作为 producer，accepted AI proposal 作为 caused_by.id。
event_type 必须属于 event_type enum。
occurred_at 必须来自已提交 WorldTimeState，不能由 LLM 或叙事文本决定。
单条独立提交的 expected_sequence 必须等于提交开始时 WorldState.runtime_state.latest_event_sequence；批内 StateTransition 的 expected_sequence 语义由 StateTransitionBatch 规则定义。
expected_entity_revisions 是并发保护集合；被读取并影响结算的权威实体必须列入。实体有 state_revision 时使用 `version_check.kind=state_revision`；没有 state_revision 时使用 `version_check.kind=canonical_hash`，并把 entity_at_expected_sequence 的 canonical hash 写入 expected_hash。
preconditions 是业务前置条件；全部满足后才能应用 ordered_changes。
ordered_changes 必须按执行顺序排列。同一 StateTransition 内后一个 change 可以读取前一个 change 产生的 post-state。
resulting_state_hash 必须由 StateTransitionValidator 在内存应用 ordered_changes 后重算，并与提交后的 WorldState canonical hash 一致。
单条独立提交时，previous_state_hash 由 StateTransitionCommitter 从提交前 WorldState canonical hash 填入。
单条独立提交时，previous_event_hash 由 StateTransitionCommitter 从 expected_sequence 对应的 EventLogEntry.event_hash 填入；expected_sequence=0 时为 null。
event_hash 由 StateTransitionCommitter 在 EventLogEntry 规范化后计算。
summary 只用于审计和调试，不能参与重放。
```

### StateTransitionBatch

`StateTransitionBatch` 用于表达必须全有或全无的多事件提交，例如空间基础物化、生成阶段原子组、迁移前后成组状态变化。普通单事件提交可以直接提交一个 `StateTransition`；任何 `atomic_commit_group_id` 非空的场景必须提交 `StateTransitionBatch`。

```json
{
  "batch_id": "st_batch_spatial_foundation_0001",
  "world_id": "isekai_world_001",
  "timeline_id": "main",
  "command_id": "cmd_generation_stage_spatial_foundation",
  "idempotency_key": "sha256:batch-input-hash",
  "atomic_commit_group_id": "acg_spatial_foundation_0001",
  "expected_sequence": 0,
  "transitions": [
    {
      "transition_id": "st_world_generated_000001",
      "group_order": 1
    },
    {
      "transition_id": "st_region_generated_000002",
      "group_order": 2
    }
  ],
  "version_context": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "final_state_hash": "sha256:post-batch-state-hash"
}
```

规则：

```text
StateTransitionBatch 只引用已经规范化并通过单项 schema 校验的 StateTransition；批内 StateTransition 不按独立提交 CAS 语义校验。
batch.expected_sequence 必须等于提交开始时 WorldState.runtime_state.latest_event_sequence。
batch.transitions 必须按 group_order 升序应用，group_order 从 1 开始且不能跳号。
批内第 N 个 transition.expected_sequence 必须等于 batch.expected_sequence + N - 1。
批内第 N 个 transition 的 EventLog.sequence 由 committer 分配为 batch.expected_sequence + N。
批内第 1 个 transition.previous_state_hash 必须等于 batch 提交前 WorldState canonical hash。
批内第 1 个 transition.previous_event_hash 必须等于 batch.expected_sequence 对应的 EventLogEntry.event_hash；batch.expected_sequence=0 时为 null。
批内第 N 个 transition 在 N > 1 时，previous_state_hash 必须等于第 N-1 个 transition.resulting_state_hash。
批内第 N 个 transition 在 N > 1 时，previous_event_hash 必须等于第 N-1 个 transition.event_hash。
批内第 N 个 transition 的 preconditions 和 expected_entity_revisions 必须以内存中已应用前 N-1 个 transition 后的中间 WorldState 为校验上下文。
批内第 N 个 transition 的 resulting_state_hash 是应用该 transition 后的中间 WorldState hash。
batch.final_state_hash 必须等于最后一个 transition.resulting_state_hash。
批内任一 transition schema 校验、precondition、revision、ACL、post-state validator 或 hash 校验失败，整个 batch 必须失败；不得写入任何批内 WorldState 变化或 EventLogEntry。
```

### EventLogEntry

`EventLogEntry` 是权威状态变更记录。任何生成、迁移、resolver 修改都必须写事件。

`EventLogEntry` 只记录系统内部提交账本。它不能直接作为游戏内知识提供给 NPC 或 AI；若某主体知道这条运行事件，必须存在对应 `KnowledgeState(target.kind=event_log_entry)`。

```json
{
  "event_id": "evt_000128",
  "world_id": "isekai_world_001",
  "sequence": 128,
  "transition_id": "st_hazard_slippery_ridge_000128",
  "event_type": "HazardCreated",
  "occurred_at": {
    "absolute_minute": 16920,
    "day": 12,
    "minute_of_day": 1080
  },
  "caused_by": {
    "kind": "world_generator",
    "id": "terrain_hazard_pass"
  },
  "summary": "在北坡脊线东侧生成湿滑坠落风险",
  "preconditions": [
    {
      "path": "WorldChunk.chunk_north_slope_12_08_00.terrain.slope",
      "operator": "equals",
      "expected": "steep"
    }
  ],
  "changes": [
    {
      "op": "create",
      "entity_type": "HazardSource",
      "entity_id": "hazard_slippery_ridge_01",
      "path": "",
      "value": {
        "id": "hazard_slippery_ridge_01",
        "source_kind": "terrain",
        "source_entity_ids": [
          "chunk_north_slope_12_08_00",
          "edge_chunk_12_08_00_to_13_08_00"
        ],
        "generated_by": {
          "system": "TerrainHazardObstacleDeriver",
          "rule_id": "terrain.steep_slope_to_fall_risk",
          "pass": "terrain_hazard_pass"
        },
        "hazard_type": "fall_risk",
        "location": {
          "scope": "chunk_edge",
          "edge_id": "edge_chunk_12_08_00_to_13_08_00"
        },
        "severity": "medium",
        "visibility": "hinted",
        "trigger": {
          "on_actions": ["move", "climb", "search"],
          "conditions": ["rain_or_wet_ground", "low_light"]
        },
        "effects": [
          {
            "effect_type": "injury_risk",
            "magnitude": "medium",
            "reason": "湿滑岩面容易失足"
          }
        ],
        "mitigations": [
          {
            "method": "careful_movement",
            "time_multiplier": 1.5,
            "risk_delta": -1
          }
        ],
        "state": {
          "active": true,
          "depleted": false
        }
      }
    }
  ],
  "version_context": {
    "schema_version": "isekai-world-foundation@1",
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash"
  },
  "previous_state_hash": "sha256:previous-state-hash",
  "previous_event_hash": "sha256:event-hash-000127",
  "resulting_state_hash": "sha256:post-state-hash",
  "event_hash": "sha256:event-hash-000128"
}
```

### WorldSnapshot

`WorldSnapshot` 表示某个事件序列点上的世界状态快照。

快照可以覆盖世界事实、知识事实和系统账本，但存储结构必须保留命名空间边界：

```text
world_facts
knowledge_facts
system_ledger
```

恢复快照时，`KnowledgeState`、`DiscoveryState`、`RumorState` 和 `SecretState` 不能被还原到 `world_facts`；WorldObject、OriginEvent、Site、WeatherState 等世界事实也不能被还原到 `knowledge_facts`。

`WorldGenerationManifest`、`GenerationStageContract`、`GeneratorOutputEnvelope` 和 `GeneratorOutputItem` 属于 `system_ledger.generation_audit`。恢复快照时不能把这些生成审计实体还原到 `world_facts` 或 `knowledge_facts`，也不能丢弃它们，否则生成结果无法审计和重放。

`GenerationRunState`、`GenerationStageRunState`、`GenerationCheckpoint` 和 `GenerationResumeToken` 属于 `generation_control`。已完成世界的正常快照恢复不依赖它们；未完成生成的调试或断点恢复快照可以保存它们，但它们不进入 WorldStateContentHash。

```json
{
  "snapshot_id": "snapshot_after_world_generation",
  "world_id": "isekai_world_001",
  "event_sequence": 128,
  "created_at": "2026-07-11T00:00:00Z",
  "reason": "after_world_generation",
  "state_hash": "sha256:...",
  "latest_event_hash": "sha256:event-hash-000128",
  "version_lock": {
    "schema_version": "isekai-world-foundation@1",
    "schema_versions": {
      "location_space": "2026-07-18",
      "world_object": "2026-07-18",
      "static_world_runtime": "2026-07-18",
      "content_pack_materialization": "2026-07-18"
    },
    "registry_hash": "sha256:registry_hash",
    "rule_bundle_hash": "sha256:rule_bundle_hash",
    "content_pack_hash": "sha256:content_pack_hash",
    "content_pack_refs": [
      {
        "content_pack_id": "isekai_generic_items_p0",
        "content_pack_version": "2026-07-18.1",
        "kind": "generic_item_catalog",
        "catalog_version": "2026-07-18.1",
        "catalog_hash": "sha256:generic_item_catalog_hash"
      }
    ]
  },
  "storage": {
    "kind": "local_file",
    "ref": "snapshots/isekai_world_001/000128.json"
  },
  "validation_summary": {
    "valid": true,
    "error_count": 0
  },
  "snapshot_hash": "sha256:snapshot-hash"
}
```

### OriginMetadata

`OriginMetadata` 的权威定义见 [历史来历与世界痕迹规则](../02-world-model/world-origin-history-rules.md)。运行时文档只保留最小示例，用于说明 HazardSource、ObstacleSource、WorldSnapshot 和 EventLog 如何校验 origin 引用。

```json
{
  "origin": {
    "origin_event_ids": ["origin_abandoned_cart_001"],
    "origin_role": "evidence",
    "age_band": "recent",
    "visible_as_evidence": true,
    "discovery_state": "hinted",
    "notes": "废弃马车、散落货袋和断裂车轮来自同一事故现场"
  }
}
```

## 字段说明

### StaticWorldRuntimeState 字段

| 字段 | 含义 |
| --- | --- |
| `world_id` | 所属 World ID。 |
| `version_lock` | 当前 WorldState 的版本锁。EventLog 和 Snapshot 必须与它一致。 |
| `version_lock.schema_version` | 世界底座总 schema 版本。 |
| `version_lock.registry_hash` | registry bundle canonical hash。 |
| `version_lock.rule_bundle_hash` | 规则包 canonical hash。 |
| `version_lock.content_pack_hash` | 当前启用内容包集合 canonical hash。 |
| `runtime_state` | 静态世界运行时入口对象。 |
| `runtime_state.time_state_id` | 当前世界时间状态 ID。 |
| `runtime_state.active_weather_state_ids` | 当前处于有效时间片内的 WeatherState ID 列表。 |
| `runtime_state.active_environment_state_ids` | 当前已派生或缓存的局部环境状态 ID 列表。 |
| `runtime_state.active_environment_residual_effect_ids` | 当前仍处于有效时间片内的 EnvironmentResidualEffectState ID 列表。 |
| `runtime_state.active_hazard_ids` | 当前世界中处于激活状态的 HazardSource ID 列表。 |
| `runtime_state.active_obstacle_ids` | 当前世界中处于激活状态的 ObstacleSource ID 列表。 |
| `runtime_state.latest_event_sequence` | 当前 WorldState 已应用的最新事件序号。 |
| `runtime_state.latest_snapshot_id` | 最近一次快照 ID。世界生成最终快照写入前允许为 `null`。 |

### WorldTimeState 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 时间状态 ID。 |
| `world_id` | 所属 World ID。 |
| `calendar` | 日历状态。 |
| `calendar.year` | 当前世界年份。P0 可以从 1 开始。 |
| `calendar.day` | 世界运行第几日。 |
| `calendar.season` | 当前季节，必须属于季节闭集。 |
| `calendar.season_day` | 当前季节内的第几日。 |
| `calendar.calendar_label` | 给 DM/UI 使用的可读日期。 |
| `clock.absolute_minute` | 自世界开始以来经过的绝对整数分钟。它是所有运行时区间和过期判断的唯一时间坐标。 |
| `clock.minute_of_day` | 当前日内分钟数，范围 0 到 1439。 |
| `clock.time_band` | 时间段，例如 dawn、day、dusk、night、midnight。该值必须属于 time_band 闭集，并由 `clock.minute_of_day`、`calendar.season` 和 `time_modifiers.seasonal_daylight_profile` 派生或校验，不能由内容包、LLM proposal 或手工写入直接决定最终值。 |
| `time_modifiers` | 时间对环境推导的辅助修正。它不直接表达某个地点的最终环境。 |
| `time_modifiers.seasonal_daylight_profile` | 当前季节使用的昼夜长度配置。 |

### WeatherState 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 天气状态 ID。P0 建议按 world、region、day、segment 生成稳定 ID。 |
| `world_id` | 所属 World ID。 |
| `scope` | 天气作用范围。P0 支持 region、world_chunk。 |
| `region_id` | 天气所属 Region。 |
| `chunk_id` | 当 `scope=world_chunk` 时引用 WorldChunk；region 天气必须为 null。 |
| `parent_weather_state_id` | 局部天气覆盖的父级 Region WeatherState。region 天气为 null。 |
| `previous_weather_state_id` | 同一 scope 的上一段 WeatherState。初始天气可为 null。 |
| `coverage_priority` | 天气覆盖优先级。Region 基础天气使用 `base_region`；局部覆盖必须使用局部优先级闭集，并按 `weather_coverage_priority` 表中的 rank 做确定性排序。 |
| `condition` | 当前天气类型，必须属于 `weather_condition` 闭集。 |
| `intensity` | 天气强度，必须属于 `weather_intensity` 闭集。 |
| `temperature_c` | 当前摄氏温度。由气候、季节、地形、时间和局部修正形成。 |
| `wind` | 当前风力，必须属于 `wind_level` 闭集。 |
| `visibility_modifier` | 天气对视野的修正值。负数降低可见度。 |
| `ground_effects` | 天气造成的地表效果，例如 wet、muddy、slippery、snow_covered。 |
| `valid_for.start_world_minute` | 天气片段开始的绝对世界分钟，包含在有效区间内。 |
| `valid_for.end_world_minute` | 天气片段结束的绝对世界分钟，不包含在有效区间内。 |
| `generated_by.system` | 生成系统。P0 支持 WeatherFormation、WeatherResolver、TestFixture。 |
| `generated_by.rule_id` | 天气生成规则 ID，例如 weather.initial_by_climate 或 weather.transition_by_climate_season_terrain。 |
| `generated_by.random_draw_ref` | 本段天气使用的 `RandomDrawRef`，必须符合确定性随机协议。 |

### EnvironmentState 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 局部环境状态 ID。 |
| `world_id` | 所属 World ID。 |
| `scope` | 环境状态覆盖范围。P0 支持 region、world_chunk、site、site_node、zone。 |
| `region_id` | 当环境状态覆盖 Region 或由 Region 派生时引用的 Region。 |
| `chunk_id` | 当 `scope=world_chunk` 时引用的 WorldChunk。 |
| `site_id` | 当环境状态覆盖 Site 或 Site 内部节点时引用的 Site。 |
| `node_id` | 当 `scope=site_node` 时引用的 LocationNode。 |
| `zone_id` | 当 `scope=zone` 时引用的 Zone。 |
| `source_time_state_id` | 派生该环境状态使用的 WorldTimeState。 |
| `weather_state_id` | 影响该环境状态的天气状态 ID。室内或不受天气影响的位置可为 null。 |
| `light.light_level` | 该位置的最终光照等级。 |
| `light.natural_light` | 该位置的自然光来源强度。室内可为 none。 |
| `light.visibility_modifier` | 该位置光照和环境对可见度的最终修正。 |
| `light.requires_light_source` | 该位置是否需要额外光源才能正常观察。 |
| `temperature.ambient_c` | 该位置当前环境摄氏温度。 |
| `temperature.temperature_band` | 该位置温度分级，例如 freezing、cold、cool、mild、hot。 |
| `ground_effects` | 当前地表或室内地面效果，例如 wet、muddy、slippery、snow_covered。 |
| `derived_from` | 派生来源说明，用于调试和 validator。 |
| `derived_from.terrain_id` | 参与派生的 WorldChunk 或 terrain 来源 ID。 |
| `derived_from.location_node_id` | 参与派生的 LocationNode ID。 |
| `derived_from.weather_state_id` | 参与派生的 weather_state ID。 |
| `derived_from.time_state_id` | 参与派生的 WorldTimeState ID。 |
| `derived_from.residual_effect_ids` | 参与派生的 EnvironmentResidualEffectState ID 列表。天气结束后的湿滑、泥泞、积雪等残留必须通过这里进入 EnvironmentState。 |
| `derived_from.heat_source_object_ids` | 影响局部温度的对象 ID 列表。 |
| `derived_from.light_source_object_ids` | 影响局部光照的对象 ID 列表。 |
| `valid_for.start_world_minute` | 该环境状态有效起始的绝对世界分钟，包含在有效区间内。 |
| `valid_for.end_world_minute` | 该环境状态有效结束的绝对世界分钟，不包含在有效区间内。超过后必须重新派生或校验。 |

### EnvironmentResidualEffectState 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 环境残留效果 ID。 |
| `world_id` | 所属 World ID。 |
| `scope` | 残留影响范围。P1 支持 region、world_chunk、site、site_node、zone。 |
| `region_id` | 残留所属 Region。 |
| `chunk_id` | 当残留影响 WorldChunk 时引用的 WorldChunk。 |
| `site_id` | 当残留影响 Site 或 Site 内部空间时引用的 Site。 |
| `node_id` | 当残留影响 LocationNode 时引用的 LocationNode。 |
| `zone_id` | 当残留影响 Zone 时引用的 Zone。 |
| `effect_type` | 残留效果类型，必须属于 `environment_residual_effect_type` 闭集。 |
| `intensity` | 残留强度，必须属于 `environment_residual_intensity` 闭集。 |
| `source.source_kind` | 残留来源类别，必须属于 `environment_residual_source_kind` 闭集。 |
| `source.source_entity_id` | 产生残留的权威实体 ID，例如 WeatherState、ResourceNode、WorldObject、HazardSource、EventLogEntry。 |
| `source.source_effect` | 来源实体产生的具体效果名，例如 light_rain、muddy、spill_water。 |
| `valid_for.start_world_minute` | 残留开始生效的绝对世界分钟，包含在有效区间内。 |
| `valid_for.end_world_minute` | 残留结束或进入下一衰减阶段的绝对世界分钟，不包含在有效区间内。 |
| `decay.decay_rule_id` | 残留衰减规则 ID，必须来自环境残留衰减规则表。 |
| `decay.mode` | 衰减模式，必须属于 `environment_residual_decay_mode` 闭集。 |
| `decay.step_minutes` | 当 mode=step_down 时，每次强度下降的分钟数。 |
| `decay.next_intensity` | 当前区间结束后转入的下一强度。没有下一阶段时为 null 或省略。 |
| `state` | 残留状态，必须属于 `environment_residual_state` 闭集。 |

### HazardSource 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 危险源 ID。 |
| `source_kind` | 危险来源类别，必须属于 `hazard_source_kind` 闭集。它回答“危险从哪类世界事实产生”。 |
| `source_entity_ids` | 产生该危险的权威实体 ID 列表，例如 chunk、edge、object、resource、environment state。 |
| `generated_by` | 产生该危险的系统和规则信息。它用于调试；权威审计仍以 EventLog 为准。 |
| `generated_by.system` | 产生系统，例如 WorldGenerator、EnvironmentDeriver、ObjectRuleDeriver、EcologyResourceDeriver、DeterministicResolver。 |
| `generated_by.rule_id` | 产生规则 ID，必须来自本文“危险/障碍产生规则表”。 |
| `generated_by.pass` | 生成阶段或规则 pass 名称。 |
| `hazard_type` | 危险类型，例如 fall_risk、poison_water、poison_risk、cold_exposure、collapse_risk、trap_risk。 |
| `location` | 危险源位置。结构遵循地点/空间规则中的 location 表达。 |
| `location.scope` | 位置范围。P0 支持 chunk、chunk_edge、site_node、zone、object。 |
| `location.edge_id` | 当危险绑定到边时，引用 ChunkEdge、LocationEdge 或 SiteBoundaryEdge。 |
| `severity` | 危险严重程度，例如 low、medium、high、lethal。 |
| `visibility` | 观察系统或未来投影层对危险源的可见性。静态世界也必须记录该事实。 |
| `trigger.on_actions` | 哪些动作会触发危险检测。 |
| `trigger.conditions` | 触发所需环境条件。 |
| `effects` | 危险触发后的效果列表。P0 只定义效果意图，具体应用由 resolver 决定。 |
| `effects[].effect_type` | 效果类型，例如 injury_risk、poison_risk、time_loss、item_damage。 |
| `effects[].magnitude` | 效果强度。 |
| `effects[].reason` | 给 DM/UI 解释后果的原因。 |
| `mitigations` | 可降低危险的处理方式。 |
| `mitigations[].method` | 缓解方式，例如 careful_movement、use_rope、light_source。 |
| `mitigations[].time_multiplier` | 使用该方式后的耗时倍率。 |
| `mitigations[].risk_delta` | 风险修正。负数降低风险。 |
| `state.active` | 危险源当前是否激活。 |
| `state.depleted` | 危险源是否已耗尽或失效。 |

### ObstacleSource 字段

| 字段 | 含义 |
| --- | --- |
| `id` | 障碍源 ID。 |
| `source_kind` | 障碍来源类别，必须属于 `obstacle_source_kind` 闭集。它回答“障碍从哪类世界事实产生”。 |
| `source_entity_ids` | 产生该障碍的权威实体 ID 列表，例如 chunk、edge、object、structure、environment state。 |
| `generated_by` | 产生该障碍的系统和规则信息。它用于调试；权威审计仍以 EventLog 为准。 |
| `generated_by.system` | 产生系统，例如 WorldGenerator、EnvironmentDeriver、ObjectRuleDeriver、EcologyResourceDeriver、DeterministicResolver。 |
| `generated_by.rule_id` | 产生规则 ID，必须来自本文“危险/障碍产生规则表”。 |
| `generated_by.pass` | 生成阶段或规则 pass 名称。 |
| `obstacle_type` | 障碍类型，例如 cliff、locked_door、collapsed_wall、fallen_tree、deep_mud。 |
| `location` | 障碍位置。 |
| `blocks` | 该障碍阻挡的动作列表。 |
| `passability_override` | 对相关边通行状态的覆盖来源。它不是最终结论，只能被 `PassabilityReducer` 消费。 |
| `passability_override.target_edge_ids` | 受该覆盖影响的 ChunkEdge、LocationEdge 或 SiteBoundaryEdge ID 列表。阻挡移动时必须非空。 |
| `passability_override.state` | 覆盖希望表达的通行状态，语义与 `effective_passability.state` 一致。 |
| `passability_override.blocked_reason` | 阻挡原因。 |
| `passability_override.conditions` | 当 state=conditional 时需要满足的条件列表。 |
| `passability_override.time_delta_minutes` | 该覆盖对通过耗时的附加修正。blocked 或未满足条件时为 null。 |
| `passability_override.risk_tags` | 该覆盖带来的移动风险标签。 |
| `passability_override.priority` | 覆盖优先级，用于同级状态的原因排序。数值越高越优先。 |
| `bypass_options` | 绕过或处理障碍的可选方案。 |
| `bypass_options[].action` | 可采取的行动。 |
| `bypass_options[].target_edge_id` | 绕行目标边。 |
| `bypass_options[].extra_time_minutes` | 额外耗时。 |
| `bypass_options[].requires` | 使用该方案需要满足的条件。 |
| `state.active` | 障碍当前是否存在并生效。 |
| `state.removable` | 该障碍是否可被规则移除。 |

### StateTransition 字段

| 字段 | 含义 |
| --- | --- |
| `transition_id` | 状态提交包络 ID。同一 `world_id + timeline_id` 内唯一。 |
| `world_id` | 所属 World ID。 |
| `timeline_id` | 时间线 ID。P0 只允许 `main`。 |
| `command_id` | 上游命令、生成阶段、AI proposal resolution、知识传播任务或迁移任务 ID。用于追踪“为什么产生这次提交”。 |
| `idempotency_key` | 幂等键。相同 key 的重复提交不得重复结算。 |
| `producer` | 产出该 StateTransition 的系统组件。 |
| `producer.kind` | 生产者类型，必须属于 `event_cause_kind` 闭集，例如 world_generator、resolver、ai_runtime、migration_tool、test_fixture。知识传播和 AI 社会结算使用 resolver kind，通过 producer.id 区分。 |
| `producer.id` | 生产者 ID。 |
| `producer.rule_id` | 使用的规则 ID。没有具体规则时可以省略，但 resolver 和 generator P0 必须填写。 |
| `caused_by` | 写入 EventLogEntry 的事件来源。 |
| `caused_by.kind` | 来源类型，必须属于 `event_cause_kind` 闭集。 |
| `caused_by.id` | 来源 ID。 |
| `event_type` | 提交后生成的 EventLogEntry 类型，必须属于 `event_type` 闭集。 |
| `occurred_at` | 事件对应的世界时间。 |
| `occurred_at.absolute_minute` | 绝对世界分钟。 |
| `occurred_at.day` | 世界日。 |
| `occurred_at.minute_of_day` | 当日分钟。 |
| `expected_sequence` | 独立提交时为提交前期望的 `WorldState.runtime_state.latest_event_sequence`；批内提交时为该 transition 应用前的批内逻辑事件边界。 |
| `expected_entity_revisions` | 并发保护集合。列出本次结算读取并依赖的实体版本检查。 |
| `expected_entity_revisions[].entity_type` | 被保护实体类型。 |
| `expected_entity_revisions[].entity_id` | 被保护实体 ID。 |
| `expected_entity_revisions[].version_check` | 并发检查方式。 |
| `expected_entity_revisions[].version_check.kind` | 检查类型。P0 允许 `state_revision` 和 `canonical_hash`。 |
| `expected_entity_revisions[].version_check.expected_revision` | 当 kind=state_revision 时的期望 revision；否则为 null。 |
| `expected_entity_revisions[].version_check.expected_hash` | 当 kind=canonical_hash 时的期望 canonical hash；否则为 null。 |
| `preconditions` | 业务前置条件集合。 |
| `preconditions[].path` | 被检查的权威状态路径。 |
| `preconditions[].operator` | 检查操作符。P0 允许 `equals`、`not_equals`、`exists`、`not_exists`、`in`、`not_in`。 |
| `preconditions[].expected` | 期望值。`exists/not_exists` 可省略。 |
| `ordered_changes` | 按顺序应用的状态变化列表。 |
| `ordered_changes[].op` | 变更操作，必须引用 `change_op` 闭集。 |
| `ordered_changes[].entity_type` | 被创建或修改的实体类型。 |
| `ordered_changes[].entity_id` | 被创建或修改的实体 ID。 |
| `ordered_changes[].path` | 被修改字段路径。`create` 时必须为空字符串。 |
| `ordered_changes[].value` | 新值。`create` 时必须是完整规范化实体；`update/deactivate` 时是目标 path 的完整新值。 |
| `version_context` | 本次提交使用的版本上下文。 |
| `version_context.schema_version` | 世界底座总 schema 版本。 |
| `version_context.registry_hash` | registry bundle canonical hash。 |
| `version_context.rule_bundle_hash` | rule bundle canonical hash。 |
| `version_context.content_pack_hash` | content pack 集合 canonical hash。 |
| `previous_state_hash` | 应用本条 StateTransition 前的 WorldState canonical hash。独立提交时来自提交前 WorldState；批内提交时来自批开始状态或上一条 transition 的 resulting_state_hash。 |
| `previous_event_hash` | 应用本条 StateTransition 前的最新 EventLogEntry.event_hash。独立提交时来自 expected_sequence；批内提交时来自批开始事件 hash 或上一条 transition 的 event_hash。 |
| `resulting_state_hash` | 应用本次 StateTransition 后的 WorldState canonical hash。 |
| `event_hash` | 由最终 EventLogEntry canonical payload 计算出的事件 hash。 |
| `summary` | 调试摘要，不作为状态恢复依据。 |

### StateTransitionBatch 字段

| 字段 | 含义 |
| --- | --- |
| `batch_id` | 原子提交批次 ID。 |
| `world_id` | 所属 World ID。 |
| `timeline_id` | 时间线 ID。P0 只允许 `main`。 |
| `command_id` | 上游批次命令 ID。 |
| `idempotency_key` | 批次级幂等键。 |
| `atomic_commit_group_id` | 原子提交组 ID。所有引用该组的 StateTransition 必须在同一批次内提交。 |
| `expected_sequence` | 批次提交前期望的 `WorldState.runtime_state.latest_event_sequence`，也是批内第 1 条 transition 的 expected_sequence。 |
| `transitions` | 批内 StateTransition 引用列表。 |
| `transitions[].transition_id` | 被引用的 StateTransition ID。 |
| `transitions[].group_order` | 批内应用顺序，从 1 开始连续递增。 |
| `version_context` | 批次提交使用的版本上下文，必须与批内每个 StateTransition 一致。 |
| `final_state_hash` | 批内全部 StateTransition 应用后的最终 WorldState canonical hash。 |

### EventLogEntry 字段

| 字段 | 含义 |
| --- | --- |
| `event_id` | 事件 ID。 |
| `world_id` | 所属 World ID。 |
| `sequence` | 单调递增事件序号。用于回放、快照和调试。 |
| `transition_id` | 产生该事件的 StateTransition ID。由 `StateTransitionCommitter` 写入，不能由 LLM、内容包或上游 resolver 自由指定最终值。 |
| `event_type` | 事件类型。 |
| `occurred_at` | 事件发生时的世界时间。 |
| `occurred_at.absolute_minute` | 事件发生时的绝对世界分钟。运行时回放、天气边界和残留过期判断必须优先使用该字段。 |
| `occurred_at.day` | 发生日。 |
| `occurred_at.minute_of_day` | 发生日内分钟。 |
| `caused_by` | 事件来源。 |
| `caused_by.kind` | 来源类型，例如 world_generator、resolver、migration、test_fixture。 |
| `caused_by.id` | 来源 ID。 |
| `summary` | 事件摘要。用于调试，不作为权威状态。 |
| `preconditions` | 应用事件前必须满足的条件。 |
| `preconditions[].path` | 被检查的状态路径。 |
| `preconditions[].operator` | 检查操作符。P0 允许 `equals`、`not_equals`、`exists`、`not_exists`、`in`、`not_in`。 |
| `preconditions[].expected` | 期望值。 |
| `changes` | 状态变更列表。 |
| `changes[].op` | 状态变更操作类型，必须引用 [字段域与注册表规则](../01-governance/field-domain-registry-rules.md) 的 `change_op` 闭集。P0 只能是 create、update、deactivate、delete_for_migration。 |
| `changes[].entity_type` | 被修改实体类型。 |
| `changes[].entity_id` | 被修改实体 ID。 |
| `changes[].path` | 被修改字段路径。create 全实体时可为空。 |
| `changes[].value` | 新值。 |
| `version_context` | 应用该事件时使用的版本上下文。必须和事件提交后的 `WorldState.version_lock` 一致。 |
| `version_context.schema_version` | 世界底座总 schema 版本。 |
| `version_context.registry_hash` | FieldSpec、enum、registry、schema、FieldOwnership、WriteACL 和 event_type 的 canonical hash。 |
| `version_context.rule_bundle_hash` | 生成器、resolver、validator、materializer、Deriver、AI action policy 和迁移规则版本的 canonical hash。 |
| `version_context.content_pack_hash` | 当前启用内容包和 catalog 集合的 canonical hash。 |
| `previous_state_hash` | 应用事件前的 WorldState canonical hash。 |
| `previous_event_hash` | 上一个 EventLogEntry 的 event_hash。sequence=1 时为 null。 |
| `resulting_state_hash` | 应用事件后的 WorldState 哈希。 |
| `event_hash` | 当前 EventLogEntry 的 canonical hash。 |

`changes` 原则上必须非空。P0 只有 `ServiceRequestRefused`、`KnowledgeDisclosureResolved`、`RumorSpreadRequested` 和可选调试审计 `SnapshotCreated` 可以作为 occurrence-only 领域事件使用空数组；它们分别表达一次已经结算的拒绝、知识披露行为、流言传播请求或快照创建审计，并可作为后续 Projection/KnowledgePropagation/调试恢复的权威输入。空 changes 时 `resulting_state_hash` 必须等于应用该 occurrence-only 事件后的 WorldStateContentHash，其他 event_type 使用空 changes 必须被拒绝。

运行时文档不得重新定义 `change_op`。`move/link/unlink` 等业务动作必须通过 `event_type` 和 `caused_by.id` 表达，并落成一个或多个 `update/create/deactivate` changes。例如 `ContainerObjectTransferred` 可以由 `ContainmentTransferResolver.move_object` 产生，但 EventLog changes 仍只能更新相关容器和对象字段。

EventLogEntry 必须由已经通过 `StateTransitionValidator` 的 StateTransition 生成。EventLogEntry 的 `event_type`、`occurred_at`、`caused_by`、`preconditions`、`changes`、`version_context`、`resulting_state_hash` 和 `summary` 必须逐字段复制或规范化自 StateTransition，不能由 EventLog writer 临时重算另一套业务结果。

EventLogEntry 必须自包含重放所需 payload。`transition_id` 只用于审计和幂等关联，事件重放不能要求额外读取 StateTransition 原始对象；否则旧日志在清理 system_ledger 或迁移后会失去可重放性。

EventLogEntry 的 `event_hash` 必须按本文“Canonical hash 与 replay 规则”计算。计算 `event_hash` 时必须排除 `event_hash` 字段自身，必须包含 `previous_state_hash`、`previous_event_hash`、`resulting_state_hash` 和全部 `changes`。

### StateTransition 提交规则

```text
1. Resolver、Generator、KnowledgePropagation、AI Social Resolver 或 MigrationTool 只能产出 StateTransition 或 StateTransitionBatch，不能直接写 WorldState 或 EventLog。
2. StateTransitionValidator 读取当前已提交 WorldState，校验 world_id、timeline_id、version_context、event_type、producer、caused_by、preconditions、expected_entity_revisions、ordered_changes 和 ACL；批内校验时，每条 transition 使用已应用前序 transition 后的中间 WorldState 作为上下文。
3. Validator 在内存中按 ordered_changes 顺序应用变化，得到 candidate post-state。
4. Candidate post-state 必须通过目标实体 validator、跨实体不变量 validator、命名空间隔离 validator、数量守恒 validator 和字段域 validator。
5. Validator 计算 resulting_state_hash；若 StateTransition 中已有 resulting_state_hash，必须一致；若没有，由 validator 填入规范化 StateTransition。
6. StateTransitionCommitter 使用 CAS 原子提交：独立 StateTransition 只有当前 latest_event_sequence == expected_sequence，且 expected_entity_revisions 全部仍匹配时，才能写入 WorldState 变化、追加 EventLogEntry、推进 latest_event_sequence；StateTransitionBatch 只对 batch.expected_sequence 做一次外部 CAS，批内 transition.expected_sequence 按 group_order 链式校验。
7. 单条 StateTransition 成功后，EventLog.sequence 必须等于 expected_sequence + 1，WorldState.runtime_state.latest_event_sequence 必须等于该 sequence。
8. StateTransitionBatch 成功后，EventLog.sequence 必须连续分配，WorldState.runtime_state.latest_event_sequence 必须等于 batch.expected_sequence + batch.transitions.length。
9. 任一校验、CAS、持久化或 hash 检查失败，必须拒绝整个 StateTransition 或 StateTransitionBatch；不得留下部分 WorldState、部分 EventLogEntry 或推进后的 latest_event_sequence。
10. 相同 idempotency_key 的重复提交必须返回第一次提交或拒绝的结果，不得再次应用 ordered_changes。
```

EventLog append 是 `StateTransitionCommitter` 原子提交包络的一部分，不再为“追加 EventLogEntry 这个行为本身”递归生成新的 EventLogEntry。否则会形成无限自记录。

### StateTransition change payload 规则

```text
op=create:
  path 必须为空字符串。
  value 必须是完整规范化实体，包含目标 schema 的全部必填字段。
  entity_id 在提交前不得已存在。

op=update:
  path 必须指向已注册字段。
  entity_id 必须引用已存在实体。
  value 是该 path 的新值，不是 patch 片段。

op=deactivate:
  path 必须指向目标实体 schema 允许的状态字段，例如 state.active、state.status 或 lifecycle.state。
  value 必须是 schema 允许的非活动状态，例如 false、inactive、expired、depleted。
  不能用 deactivate 删除实体引用；引用清理必须由同一个 StateTransition 中的显式 update 完成。

op=delete_for_migration:
  只允许 migration_tool 使用。
  必须携带 migration rule id，并且只能在 schema migration 提交中出现。
```

数组字段在 P0 不支持隐式 append/remove patch。凡是修改数组字段，`op=update` 的 `value` 必须是修改后的完整数组；validator 必须校验数组元素闭集、排序规则、唯一性和引用完整性。

### 生成 operation lowering 规则

`GeneratorOutputItem.operation` 是生成阶段权限语义，不能直接进入 EventLog `changes[].op`。`GenerationCommitter` 必须先把生成输出降低为 StateTransition `ordered_changes`：

```text
operation=create:
  降低为 ordered_changes[].op=create。
  value 必须是完整规范化实体。

operation=update:
  降低为 ordered_changes[].op=update。
  value 必须是目标 path 的完整新值。

operation=deactivate:
  降低为 ordered_changes[].op=deactivate。
  value 必须是目标状态字段允许的非活动值。

operation=materialize:
  先运行 materializer 纯函数，生成完整 runtime entity candidate。
  通过目标 entity validator 后，降低为 ordered_changes[].op=create。
  EventLog changes 只能记录最终完整实体，不能记录 catalog diff、merge 步骤或 materialize operation。

operation=derive:
  如果输出仍是 Candidate 或 generation_audit，只能留在 system_ledger.generation_audit，不进入 WorldState changes。
  如果输出物化为权威实体字段，必须降低为 create 或 update。
  EventLog changes 只能记录最终字段值，不能记录 derive operation。
```

示例：

```text
GenericItemMaterializer(materialize container_waterskin)
-> GeneratorOutputItem.operation=materialize
-> StateTransition.ordered_changes[0].op=create
-> entity_type=WorldObject
-> value=完整 WorldObject(container)，包含 provenance、placement、physical、components.container 和 state。

ChunkBiomeCandidateDerivation(derive biome_tags)
-> GeneratorOutputItem.operation=derive
-> Candidate 保留在 generation_audit
-> RegionBiomeCandidateAggregation 通过后
-> StateTransition.ordered_changes[0].op=update
-> entity_type=WorldChunk
-> path=WorldChunk.chunk_12_08_00.biome_tags
-> value=最终 biome_tags 完整数组。
```

### 迁移 deletion payload 规则

`delete_for_migration` 只能由 migration_tool 使用，且只能出现在 `event_type=SchemaMigrated` 或明确的内容迁移事件中。普通玩法、生成、resolver、AI 和内容包都不能使用。

`delete_for_migration` 的 `value` 不是新字段值，而是迁移删除审计 payload：

```json
{
  "migration_plan_id": "migration_2026_07_schema_v2",
  "migration_rule_id": "migration.remove_legacy_temperature_offset",
  "delete_scope": "field",
  "old_value_hash": "sha256:old-field-value-hash",
  "reason_code": "field_replaced_by_environment_temperature",
  "replacement": {
    "entity_type": "EnvironmentState",
    "entity_id": "env_chunk_12_08_00_16920",
    "path": "temperature.ambient_c"
  }
}
```

规则：

```text
delete_scope 必须是 field 或 entity。
delete_scope=field 时 path 必须指向迁移前 schema 中存在、迁移后 schema 中删除或废弃的字段。
delete_scope=entity 时 path 必须为空字符串，entity_type 必须是迁移计划允许删除的旧实体类型。
old_value_hash 必须等于删除前目标值或目标实体的 canonical hash。
replacement 可以为 null；非 null 时必须引用同一 StateTransition 或同一 StateTransitionBatch 中 create/update 后存在的替代字段或实体。
preconditions 必须记录迁移前 version_lock 和 old_value_hash，避免重复迁移或误删新字段。
重放 delete_for_migration 时，replay engine 必须先校验 old_value_hash，再删除目标字段或实体，最后应用同一事件中的替代 create/update。
```

### Canonical hash 与 replay 规则

P0 所有状态、事件和快照 hash 都使用同一基础规范，复用 [内容包、Catalog 与物化版本规则](../05-content-packs/content-pack-materialization-rules.md) 的 canonical JSON 协议：

```text
CanonicalBytes(payload) = canonical_json_utf8(payload)
Hash(payload) = "sha256:" + sha256(CanonicalBytes(payload)).hex_lowercase
```

补充规则：

```text
object key 按 Unicode code point 升序排序。
array 默认保留顺序；被 FieldSpec 声明为 set 的数组必须先去重并稳定排序。
number 必须先按 FieldSpec 规范化；守恒数值使用 decimal string。
null、空数组和空对象参与 hash；缺失字段和 null 不是同一状态。
不得把注释、文件路径、mtime、数据库行号、加载顺序、本地化排序或运行环境写入 hash。
```

`WorldStateContentHash` 计算范围：

```text
Hash({
  hash_kind: "AuthoritativeWorldStateContentHash",
  hash_version: "isekai-state-hash@1",
  world_id,
  timeline_id,
  version_lock,
  runtime_state_without_latest_snapshot_id,
  world_facts,
  knowledge_facts,
  system_ledger_without_event_log_entries_world_snapshots_and_generation_control
})
```

说明：

```text
EventLogEntry 和 WorldSnapshot 不进入 WorldStateContentHash，避免 resulting_state_hash、event_hash 和 snapshot_hash 自引用。
runtime_state.latest_event_sequence 必须进入 WorldStateContentHash，因为它表达已应用事件边界。
runtime_state.latest_snapshot_id 是恢复索引，不进入 WorldStateContentHash；更新它不得改变世界内容 hash。
system_ledger 中的 generation_audit、ai_proposal ledger、migration_audit 等非 EventLog/Snapshot/generation_control 账本进入 WorldStateContentHash。
generation_control 只保存未完成世界生成的 RunState、StageRunState、Checkpoint 和 ResumeToken；它不进入 WorldStateContentHash，避免崩溃次数和恢复次数改变最终世界内容 hash。
```

`EventLogEntry.event_hash` 计算范围：

```text
Hash({
  hash_kind: "EventLogEntryHash",
  hash_version: "isekai-event-hash@1",
  event_log_entry_without_event_hash
})
```

`WorldSnapshot.snapshot_hash` 计算范围：

```text
Hash({
  hash_kind: "WorldSnapshotHash",
  hash_version: "isekai-snapshot-hash@1",
  snapshot_without_snapshot_hash
})
```

重放规则：

```text
1. 选择 snapshot.event_sequence <= target_sequence 的最新 WorldSnapshot。
2. 校验 snapshot.snapshot_hash、snapshot.state_hash、snapshot.version_lock 和 snapshot.latest_event_hash。
3. 恢复 snapshot.storage 指向的 WorldState，并运行 foundation validators。
4. 从 snapshot.event_sequence + 1 开始按 sequence 连续读取 EventLogEntry，直到 target_sequence。
5. 每条事件必须满足 previous_state_hash == 当前 WorldStateContentHash。
6. 每条事件必须满足 previous_event_hash == 上一条事件 event_hash；若从 snapshot 后开始，则上一条事件 hash 必须等于 snapshot.latest_event_hash。
7. 按 changes 顺序应用事件，应用后重算 WorldStateContentHash。
8. 重算值必须等于 EventLogEntry.resulting_state_hash。
9. 重算 EventLogEntry.event_hash，必须等于事件内 event_hash。
10. target_sequence 应用完成后的 WorldStateContentHash 必须等于目标 expected hash；若目标是某个 snapshot，则必须等于该 snapshot.state_hash。
```

从 event 0 开始重放时，初始状态是空世界容器：

```text
world_id 已知。
timeline_id = main。
runtime_state.latest_event_sequence = 0。
world_facts、knowledge_facts、system_ledger 均为空集合。
version_lock 使用创世事件 version_context。
previous_event_hash = null。
```

### WorldSnapshot 字段

| 字段 | 含义 |
| --- | --- |
| `snapshot_id` | 快照 ID。 |
| `world_id` | 所属 World ID。 |
| `event_sequence` | 快照对应的最新事件序号。 |
| `created_at` | 快照创建的真实时间戳。 |
| `reason` | 创建快照的原因，例如 after_world_generation、before_migration、debug_checkpoint。 |
| `state_hash` | 快照内 WorldState 的哈希。 |
| `latest_event_hash` | `event_sequence` 对应的 EventLogEntry.event_hash。event_sequence=0 时为 null。 |
| `version_lock` | 快照依赖的完整版本锁。 |
| `version_lock.schema_version` | 世界底座总 schema 版本。 |
| `version_lock.schema_versions` | 各权威文档或 schema 的版本表。 |
| `version_lock.registry_hash` | 当前 registry bundle 的 canonical hash。 |
| `version_lock.rule_bundle_hash` | 当前规则包 canonical hash。 |
| `version_lock.content_pack_hash` | 当前启用内容包集合 canonical hash。 |
| `version_lock.content_pack_refs` | 快照启用的内容包、catalog 版本和 catalog hash 列表。 |
| `storage.kind` | 快照存储方式。 |
| `storage.ref` | 快照存储引用。 |
| `validation_summary.valid` | 快照创建时 validator 是否通过。 |
| `validation_summary.error_count` | validator 错误数量。 |
| `snapshot_hash` | WorldSnapshot 自身 canonical hash。计算时排除 `snapshot_hash` 字段。 |

### SnapshotWriter 规则

`WorldSnapshot` 是恢复检查点，不是游戏内世界事实。SnapshotWriter 只写 snapshot namespace 和恢复索引，不能修改 world_facts、knowledge_facts、EventLogEntry 或 resolver 可见状态。

```text
1. SnapshotWriter 只能读取已经提交的 WorldState 和 EventLog。
2. SnapshotWriter 必须固定一个 committed boundary：event_sequence = 当前 WorldState.runtime_state.latest_event_sequence。
3. SnapshotWriter 计算 WorldStateContentHash，并写入 snapshot.state_hash。
4. SnapshotWriter 读取 event_sequence 对应 EventLogEntry.event_hash，并写入 snapshot.latest_event_hash；event_sequence=0 时为 null。
5. SnapshotWriter 写入 snapshot payload 后计算 snapshot_hash。
6. snapshot payload、snapshot metadata 和 runtime_state.latest_snapshot_id 恢复索引必须原子写入；任一步失败都不得留下半个快照或推进 latest_snapshot_id。
7. runtime_state.latest_snapshot_id 不进入 WorldStateContentHash；更新它不改变 resulting_state_hash。
8. SnapshotWriter 不生成 StateTransition，也不为“创建快照”递归要求新的 Snapshot。
```

`SnapshotCreated` event_type 只允许作为调试审计事件使用。P0 默认不要求创建快照时形成 `SnapshotCreated` StateTransition；如果实现选择审计，必须由调试审计 resolver 形成 occurrence-only StateTransition，`changes=[]`，`resulting_state_hash` 等于该审计事件后的 WorldStateContentHash，且仍不得把 WorldSnapshot payload 写入 EventLog changes。

### OriginMetadata 字段

| 字段 | 含义 |
| --- | --- |
| `origin.origin_event_ids` | 引用的 OriginEvent 列表。 |
| `origin.origin_role` | 当前实体在来源中的角色。 |
| `origin.age_band` | 当前实体表现出的新旧程度。 |
| `origin.visible_as_evidence` | 该实体是否可作为玩家可发现证据。 |
| `origin.discovery_state` | 玩家当前发现状态。 |
| `origin.notes` | 设计说明或调试说明。不能替代权威状态。 |

## 枚举闭集

### season

```text
early_spring
spring
late_spring
early_summer
summer
late_summer
early_autumn
autumn
late_autumn
early_winter
winter
late_winter
abnormal_season
```

### time_band

```text
dawn
day
dusk
night
midnight
```

### weather_condition

```text
clear
cloudy
light_rain
heavy_rain
fog
snow
strong_wind
storm
abnormal_mist
```

### weather_intensity

```text
trace
light
normal
heavy
severe
abnormal
```

### wind_level

```text
calm
light
moderate
strong
gale
abnormal
```

### weather_ground_effect

```text
wet
muddy
slippery
snow_covered
fast_water
```

### weather_coverage_priority

```text
base_region
local_override
abnormal_override
test_fixture_override
```

含义：

| priority | 含义 |
| --- | --- |
| base_region | rank=0。Region 基础天气。每个 Region 在任意绝对分钟必须恰好命中一个 base_region WeatherState。 |
| local_override | rank=10。普通局部覆盖，例如山脊局部强风或溪谷局部雾。 |
| abnormal_override | rank=20。异常压力造成的局部天气覆盖。优先级高于普通局部覆盖。 |
| test_fixture_override | rank=100。自动化测试夹具覆盖。只允许测试环境使用。 |

### light_level

```text
bright
normal
dim
dusk
dark
pitch_dark
abnormal
```

### environment_scope

```text
region
world_chunk
site
site_node
zone
```

### natural_light

```text
none
low
medium
high
abnormal
```

### temperature_band

```text
freezing
cold
cool
mild
warm
hot
extreme
abnormal
```

### environment_residual_effect_type

```text
wet
muddy
slippery
snow_covered
fast_water
ash_covered
smoke_haze
heat_residue
cold_residue
abnormal_residue
```

### environment_residual_intensity

```text
trace
light
moderate
heavy
severe
abnormal
```

### environment_residual_source_kind

```text
weather_state
resource_node
world_object
hazard_source
obstacle_source
resolver_event
test_fixture
```

### environment_residual_decay_mode

```text
none
expire_at_end
step_down
linear
```

### environment_residual_state

```text
active
decaying
expired
```

### hazard_type

```text
fall_risk
collapse_risk
poison_water
poison_risk
toxic_plant
cold_exposure
heat_exposure
fire_risk
trap_risk
drowning_risk
infection_risk
low_visibility_risk
```

### hazard_source_kind

```text
terrain
weather_environment
water
flora
natural_resource
world_object
structure
mechanism
fire
abnormal_field
```

含义：

| source_kind | 含义 | 典型来源 |
| --- | --- | --- |
| terrain | 地形自身产生的危险 | 断崖边、陡坡、松石坡、深坑 |
| weather_environment | 天气和局部环境产生的危险 | 暴雨、浓雾、低温、强风、低可见度 |
| water | 水体产生的危险 | 急流、深水、污染水、薄冰 |
| flora | 植物生态产生的危险 | 毒草、带刺藤蔓、误食风险 |
| natural_resource | 非生命自然资源产生的危险 | 毒矿、瘴气泥沼、腐败资源、尖锐矿渣 |
| world_object | 世界对象产生的危险 | 碎玻璃、尖钉、破损武器、腐坏食物 |
| structure | 建筑或结构状态产生的危险 | 塌陷地板、危墙、腐烂木桥 |
| mechanism | 机关或装置产生的危险 | 捕兽夹、锁具反噬、压力板 |
| fire | 火焰、热源或可燃状态产生的危险 | 明火、余烬、火势蔓延、烫伤 |
| abnormal_field | 异常场影响产生的危险 | 异常雾、空间错位、异常低温 |

### obstacle_type

```text
cliff
blocked_path
locked_door
collapsed_wall
fallen_tree
deep_mud
fast_water
sealed_container
jammed_mechanism
heavy_object
```

### obstacle_source_kind

```text
terrain
water
vegetation
world_object
structure
mechanism
weather_environment
resource_deposit
abnormal_field
```

含义：

| source_kind | 含义 | 典型来源 |
| --- | --- | --- |
| terrain | 地形自身形成阻挡 | 断崖、峭壁、深沟、不可攀岩壁 |
| water | 水体形成阻挡 | 急流、深水、涨水河道、薄冰水面 |
| vegetation | 植被形成阻挡 | 倒木、密灌木、藤蔓墙 |
| world_object | 世界对象形成阻挡 | 上锁箱子、沉重柜子、倒塌马车 |
| structure | 建筑或结构形成阻挡 | 塌墙、封死门洞、坍塌地板 |
| mechanism | 机关或装置形成阻挡 | 锁、闸门、卡死绞盘 |
| weather_environment | 天气和环境形成临时阻挡 | 暴雪封路、浓雾不可辨路、泥泞不可通行 |
| resource_deposit | 资源堆积形成阻挡 | 碎石堆、矿渣堆、厚泥层 |
| abnormal_field | 异常场形成阻挡 | 空间错位、不可穿过的异常雾墙 |

### passability_override_state

```text
open
difficult
conditional
blocked
```

含义：

| state | 含义 | 使用约束 |
| --- | --- | --- |
| open | 覆盖后可直接通行 | 只允许确定性规则创建的新通路或已解除阻挡的 portal 使用；普通 ObstacleSource 不应生成 open。 |
| difficult | 可通行但成本或风险增加 | 必须提供 `time_delta_minutes`、`risk_tags` 或二者之一。 |
| conditional | 满足条件后可通行 | 必须提供 `conditions`。未满足时 reducer 输出 `effective_traversal.time_minutes=null`。 |
| blocked | 当前不可直接通行 | 必须提供 `blocked_reason`。 |

### event_type

```text
WorldGenerated
RegionGenerated
ChunkGenerated
ResourceGenerated
FloraGenerated
FaunaGenerated
SettlementAnchorCreated
ChunkEdgeGenerated
EdgeBaseTraversalDerived
SitePlaced
SiteBoundaryEdgeGenerated
ChunkTravelEvent
SiteEnteredEvent
SiteLeftEvent
LocationChangedEvent
ZoneChangedEvent
ObjectCreated
ObjectMoved
ObjectStateChanged
ObjectDerivedPhysicalChanged
ContainerObjectTransferred
QuantityResourceTransferred
CreaturePopulationCountChanged
CreatureGroupCreated
CreatureGroupCountChanged
CreatureActorMaterialized
CreatureActorLifecycleChanged
EcologyResourceExtracted
EcologyResourceStockChanged
EcologyResourceRecovered
HazardCreated
HazardStateChanged
ObstacleCreated
ObstacleStateChanged
EdgeEffectivePassabilityChanged
EdgeEffectivePassabilityDerived
TimeInitialized
TimeAdvanced
WeatherInitialized
WeatherChanged
EnvironmentStateChanged
EnvironmentResidualEffectCreated
EnvironmentResidualEffectStateChanged
AIDecisionTickCreated
AIDecisionTickStatusChanged
AIProposalRecorded
AIProposalStatusChanged
ProposalReservationCreated
ProposalReservationStateChanged
SocialPressureChanged
PatrolLevelChanged
SocialAttitudeChanged
SocialRumorIndexChanged
SettlementSocialStateCreated
ServiceOfferCreated
ServiceRequestRefused
KnowledgeDisclosureResolved
KnowledgeCreated
KnowledgeUpdated
DiscoveryCreated
ObservationSnapshotCreated
RumorSpreadRequested
RumorCreated
SecretCreated
SecretUpdated
OriginEventCreated
OriginMetadataAttached
SnapshotCreated
SchemaMigrated
```

## 有限来源映射规则

`source_kind` 和 `hazard_type` / `obstacle_type` 都必须是闭集。内容包、世界生成器、LLM proposal 不能新增表外来源；需要新来源时必须先改规则文档和 validator。

### HazardSource 允许映射

| source_kind | 允许 hazard_type |
| --- | --- |
| terrain | fall_risk, collapse_risk, low_visibility_risk |
| weather_environment | cold_exposure, heat_exposure, low_visibility_risk, drowning_risk |
| water | drowning_risk, poison_water, cold_exposure, infection_risk |
| flora | toxic_plant, infection_risk, low_visibility_risk |
| natural_resource | poison_risk, infection_risk, fire_risk, low_visibility_risk |
| world_object | trap_risk, fire_risk, infection_risk, poison_risk |
| structure | collapse_risk, fall_risk, fire_risk |
| mechanism | trap_risk, collapse_risk, fire_risk |
| fire | fire_risk, heat_exposure, low_visibility_risk |
| abnormal_field | low_visibility_risk, cold_exposure, heat_exposure, fall_risk |

规则：

```text
HazardSource.source_kind 必须能解释 hazard_type。
同一个具体对象可以产生多个 HazardSource，但每个 HazardSource 只能有一个 primary hazard_type。
如果一个危险来自 WorldObject，HazardSource.location 必须能追溯到该 WorldObject 或其所在空间。
如果一个危险来自 EnvironmentState，HazardSource.trigger.conditions 必须引用可验证的环境条件。
```

### ObstacleSource 允许映射

| source_kind | 允许 obstacle_type |
| --- | --- |
| terrain | cliff, blocked_path |
| water | fast_water, blocked_path |
| vegetation | fallen_tree, blocked_path |
| world_object | sealed_container, heavy_object, blocked_path, locked_door |
| structure | collapsed_wall, locked_door, blocked_path |
| mechanism | locked_door, jammed_mechanism, sealed_container |
| weather_environment | deep_mud, blocked_path, fast_water |
| resource_deposit | deep_mud, heavy_object, blocked_path |
| abnormal_field | blocked_path, jammed_mechanism |

规则：

```text
ObstacleSource.source_kind 必须能解释 obstacle_type。
ObstacleSource 如果影响移动，只能通过 passability_override 指向目标 edge。
最终通行结论必须由 PassabilityReducer 写入 ChunkEdge、LocationEdge 或 SiteBoundaryEdge 的 effective_passability / effective_traversal。
ObstacleSource 不允许直接表达伤害后果；伤害和风险必须用 HazardSource 表达。
同一个世界事实可以同时生成 HazardSource 和 ObstacleSource，例如腐烂木桥既可能阻挡也可能坍塌。
```

## 环境残留衰减规则

`EnvironmentResidualEffectState` 只能由 `EnvironmentDeriver`、`DeterministicResolver`、`MigrationTool` 或 `TestFixture` 创建和更新。WeatherState 只提供输入事实，不能直接把残留写进 EnvironmentState。

### 环境残留来源映射

| source_kind | 允许 effect_type |
| --- | --- |
| weather_state | wet, muddy, slippery, snow_covered, fast_water, smoke_haze, heat_residue, cold_residue, abnormal_residue |
| resource_node | wet, muddy, slippery, fast_water, cold_residue |
| world_object | wet, muddy, slippery, ash_covered, smoke_haze, heat_residue, cold_residue, abnormal_residue |
| hazard_source | slippery, smoke_haze, heat_residue, cold_residue, abnormal_residue |
| obstacle_source | muddy, slippery, fast_water, abnormal_residue |
| resolver_event | wet, muddy, slippery, ash_covered, smoke_haze, heat_residue, cold_residue, abnormal_residue |
| test_fixture | wet, muddy, slippery, snow_covered, fast_water, ash_covered, smoke_haze, heat_residue, cold_residue, abnormal_residue |

规则：

```text
EnvironmentResidualEffectState.source_kind 必须能解释 effect_type。
source_entity_id 必须引用存在的权威实体。
残留区间必须使用 GameTimeInterval。
残留不能回写 WeatherState.ground_effects。
EnvironmentDeriver 读取当前 WeatherState 和当前有效 EnvironmentResidualEffectState，派生 EnvironmentState.ground_effects。
```

### 环境残留衰减规则表

| decay_rule_id | 输入来源 | 适用 effect_type | 默认区间 | 衰减 |
| --- | --- | --- | --- | --- |
| `environment_residual.light_rain_wet_decay` | light_rain 结束 | wet, slippery | 30-120 分钟 | step_down：moderate -> light -> trace -> expired |
| `environment_residual.heavy_rain_mud_decay` | heavy_rain 结束 | wet, muddy, slippery | 120-360 分钟 | step_down：heavy -> moderate -> light -> trace -> expired |
| `environment_residual.storm_water_decay` | storm 结束 | wet, muddy, fast_water, slippery | 60-240 分钟 | step_down；river/wetland 可保留 fast_water 到下一天气片段 |
| `environment_residual.snow_melt_decay` | snow 结束或升温 | snow_covered, slippery, wet | 120-360 分钟 | `temperature_c <= 0` 时不衰减；升温后 step_down |
| `environment_residual.spill_water_decay` | world_object/resolver_event | wet, slippery | 10-60 分钟 | step_down 或 expire_at_end |
| `environment_residual.fire_smoke_decay` | fire/hazard_source | ash_covered, smoke_haze, heat_residue | 10-180 分钟 | smoke_haze 通常 expire_at_end，heat_residue step_down |
| `environment_residual.abnormal_decay` | abnormal source | abnormal_residue, cold_residue, heat_residue | 由异常规则给出 | 必须显式给出 decay.mode 和 end_world_minute |

硬规则：

```text
残留创建、衰减、过期都必须通过 StateTransition 提交，并由 StateTransitionCommitter 生成 EventLogEntry。
残留到期不能靠 DM 文本自然消失，必须由 EnvironmentResidualEffectState.state 或新的衰减阶段表达。
如果残留影响通行、风险或可见度，EnvironmentDeriver 必须触发 Hazard/Obstacle Deriver 和 PassabilityReducer。
同一 scope、effect_type、source_entity_id 在同一时间不能存在重叠 active 区间。
```

## PassabilityReducer 规则

`PassabilityReducer` 是 `ChunkEdge.effective_passability`、`ChunkEdge.effective_traversal`、`LocationEdge.effective_passability`、`LocationEdge.effective_traversal`、`SiteBoundaryEdge.effective_passability`、`SiteBoundaryEdge.effective_traversal` 的唯一写者。

输入：

```text
Edge.base_passability
Edge.base_traversal
active ObstacleSource.passability_override
active portal / mechanism passability_override
active environment passability_override
```

输出：

```text
Edge.effective_passability
Edge.effective_traversal
EdgeEffectivePassabilityChanged EventLogEntry
```

聚合顺序：

```text
1. 读取 edge 的 base_passability / base_traversal。
2. 收集 target_edge_ids 包含该 edge，且 source state.active=true 的 passability_override。
3. 按状态严重度聚合：blocked > conditional > difficult > open。
4. 如果存在 blocked override，effective_passability.state=blocked，blocked_reason 取排序后的最高优先级原因，effective_traversal.time_minutes=null。
5. 否则如果存在 conditional override，effective_passability.state=conditional，conditions 为所有条件去重后的稳定排序集合；条件未满足时 effective_traversal.time_minutes=null。
6. 否则如果存在 difficult override，effective_passability.state=difficult，effective_traversal.time_minutes=base_time_minutes + 所有 active time_delta_minutes 的和。
7. 否则沿用 base_passability / base_traversal 生成 effective 值。
```

原因稳定排序：

```text
priority DESC
source_kind ASC
obstacle_type ASC
obstacle_id ASC
```

恢复规则：

```text
当某个 override 失效、关闭或条件变化时，PassabilityReducer 必须从 base 值和剩余 active overrides 重新计算 effective 值。
禁止从上一版 effective_passability 反推恢复结果。
Deriver 生成 HazardSource / ObstacleSource 时只能读取 base 值、源实体状态、EnvironmentState 和 WorldObject 状态，不能读取 effective_passability 作为自身存在依据。
RouteResolver、DM Projection 和 UI Projection 只能读取 effective_passability / effective_traversal，不允许自行合成最终通行结论。
```

## 危险/障碍产生规则

HazardSource 和 ObstacleSource 只能由以下 producer 产生或更新。

| producer | 允许场景 | 说明 |
| --- | --- | --- |
| `WorldGenerator` | 初始世界生成 | 生成 terrain、water、flora、resource、structure、object 后运行全量 Deriver。 |
| `EnvironmentDeriver` | 时间、天气、EnvironmentState 改变 | 只重算受影响 Region、WorldChunk、Site、LocationNode、Zone。 |
| `TerrainHazardObstacleDeriver` | 地形和边生成后 | 由 terrain、slope、landform、ChunkEdge、LocationEdge、SiteBoundaryEdge 产生危险/障碍。 |
| `WaterHazardObstacleDeriver` | 水系和水源生成后 | 由 water_presence、ResourceNode、river crossing、water quality 产生危险/障碍。 |
| `EcologyResourceDeriver` | FloraPatch、ResourceDeposit、ResourceNode 生成后 | 由植物风险、自然资源状态、水质和资源堆积产生危险/障碍。 |
| `ObjectRuleDeriver` | WorldObject 创建或状态变化后 | 由 object_type、components、physical.traits、placement 产生危险/障碍。 |
| `StructureRuleDeriver` | Site、LocationNode、LocationEdge、结构对象生成或变化后 | 由建筑结构、门、桥、墙、楼板等状态产生危险/障碍。 |
| `DeterministicResolver` | 规则动作改变世界后 | 创建、关闭、升级、降级危险/障碍。 |
| `MigrationTool` | schema migration | 只用于迁移旧状态，不属于正常玩法来源。 |
| `TestFixture` | 自动化测试 | 只用于测试夹具，不属于正常玩法来源。 |

LLM proposal 不能作为 producer。内容包也不能直接创建最终 HazardSource / ObstacleSource；内容包只能提供 terrain/object/resource/flora 等输入事实。

`generated_by.system` 必须属于上表 producer 闭集。

### HazardSource 产生规则表

| rule_id | producer | 输入事实 | 条件 | 输出 | 失效/更新 |
| --- | --- | --- | --- | --- | --- |
| `terrain.steep_slope_to_fall_risk` | TerrainHazardObstacleDeriver | `WorldChunk.terrain.slope`, `ChunkEdge.base_traversal` | slope=steep 或 base_traversal.risk_tags 包含 fall/slippery | `HazardSource(source_kind=terrain, hazard_type=fall_risk)` | slope 改变、edge 移除、环境干燥后可降级 |
| `terrain.cliff_to_fall_risk` | TerrainHazardObstacleDeriver | `WorldChunk.terrain.landform`, `ChunkEdge.base_passability` | landform=cliff 或 base_passability.blocked_reason 指向断崖 | `HazardSource(source_kind=terrain, hazard_type=fall_risk)` | cliff 地形或边关系被迁移移除 |
| `terrain.ruin_or_cave_to_collapse_risk` | TerrainHazardObstacleDeriver | `terrain.landform`, `terrain_tags`, `LocationNode.tags` | ruin/cave/unstable 相关标签存在 | `HazardSource(source_kind=terrain, hazard_type=collapse_risk)` | 支撑修复、区域封闭或结构稳定后关闭 |
| `terrain.low_visibility_terrain` | TerrainHazardObstacleDeriver | `terrain.visibility`, `terrain_tags` | visibility=low 或 dense_forest/cave/ruin 标签 | `HazardSource(source_kind=terrain, hazard_type=low_visibility_risk)` | 环境或位置变化后重算 |
| `environment.low_temperature` | EnvironmentDeriver | `EnvironmentState.temperature.temperature_band` | freezing/cold 且暴露环境 | `HazardSource(source_kind=weather_environment, hazard_type=cold_exposure)` | 温度升高、进入庇护、热源生效后关闭或降级 |
| `environment.high_temperature` | EnvironmentDeriver | `EnvironmentState.temperature.temperature_band` | hot/extreme | `HazardSource(source_kind=weather_environment, hazard_type=heat_exposure)` | 温度下降或进入遮蔽后关闭或降级 |
| `environment.low_visibility` | EnvironmentDeriver | `EnvironmentState.light`, `weather_state.condition` | light_level=dark/pitch_dark 或 fog/storm/abnormal_mist | `HazardSource(source_kind=weather_environment, hazard_type=low_visibility_risk)` | 光照改善、天气变化、光源生效后关闭或降级 |
| `environment.storm_water_rise` | EnvironmentDeriver | `weather_state.condition`, `terrain.water_presence` | heavy_rain/storm 且 river/stream/wetland | `HazardSource(source_kind=weather_environment, hazard_type=drowning_risk)` | 天气结束或水位状态恢复后关闭 |
| `water.deep_or_fast_water` | WaterHazardObstacleDeriver | `terrain.water_presence`, `ChunkEdge.base_traversal`, `ResourceNode.state` | river/stream/pond/deep/fast crossing | `HazardSource(source_kind=water, hazard_type=drowning_risk)` | 水体消失、桥梁/浅滩可用、crossing 变安全后降级 |
| `water.polluted_water` | WaterHazardObstacleDeriver | `ResourceNode.state.quality`, `water_profile.quality` | polluted/stagnant/uncertain 且可饮用或可装水 | `HazardSource(source_kind=water, hazard_type=poison_water)` | 净化、确认安全、水源耗尽后关闭 |
| `water.cold_water` | WaterHazardObstacleDeriver | `EnvironmentState.temperature`, `water_presence` | cold/freezing 且存在涉水/落水可能 | `HazardSource(source_kind=water, hazard_type=cold_exposure)` | 温度升高或涉水路径关闭后关闭 |
| `water.infection_water` | WaterHazardObstacleDeriver | `ResourceNode.state.quality`, `biome_tags` | stagnant/corpse_remain/marsh 等条件 | `HazardSource(source_kind=water, hazard_type=infection_risk)` | 水源净化或污染来源移除后关闭 |
| `flora.toxic_or_irritant_plant` | EcologyResourceDeriver | `PlantSpecies.risk_tags`, `FloraPatch.state` | toxic/irritant/misidentification | `HazardSource(source_kind=flora, hazard_type=toxic_plant)` | 植物片区被清除、采尽或已明确识别后降级 |
| `flora.dense_thorn_low_visibility` | EcologyResourceDeriver | `PlantSpecies.category`, `FloraPatch.coverage`, `risk_tags` | dense/thorn/vine 且影响穿行或观察 | `HazardSource(source_kind=flora, hazard_type=low_visibility_risk)` | 植被清理、位置变化后关闭 |
| `resource.unstable_deposit` | EcologyResourceDeriver | `ResourceDeposit.resource_id`, `stock.capacity_amount`, `stock.current_amount`, `terrain_tags` | 矿脉、碎石堆、泥沼等不稳定资源 | `HazardSource(source_kind=natural_resource, hazard_type=collapse_risk)` | 资源被加固、库存耗尽或避开后关闭 |
| `resource.toxic_resource` | EcologyResourceDeriver | `NaturalResource.category`, `ResourceDeposit.state` | toxic/abnormal_resource/poisonous_mineral 等有毒资源 | `HazardSource(source_kind=natural_resource, hazard_type=poison_risk)` | 移除污染源、资源耗尽或确认无毒后关闭 |
| `resource.rotten_or_infected_resource` | EcologyResourceDeriver | `NaturalResource.category`, `ResourceDeposit.state` | rotting/corpse_remain/infected_resource 等腐败或感染资源 | `HazardSource(source_kind=natural_resource, hazard_type=infection_risk)` | 移除污染源或资源耗尽后关闭 |
| `resource.flammable_resource` | EcologyResourceDeriver | `ResourceDeposit.resource_id`, `WorldObject.physical.traits` | dry_firewood/peat/oil 等可燃资源聚集 | `HazardSource(source_kind=natural_resource, hazard_type=fire_risk)` | 资源被移走、潮湿、燃尽后关闭 |
| `object.trap_component` | ObjectRuleDeriver | `WorldObject.object_type`, `components.trap_profile` | object_type=trap 且 armed=true | `HazardSource(source_kind=mechanism, hazard_type=trap_risk)` | disarmed/triggered/removed 后关闭 |
| `object.fire_or_heat_source` | ObjectRuleDeriver | `WorldObject.components.light_profile`, `physical.traits`, `state` | 明火、余烬、可燃对象燃烧 | `HazardSource(source_kind=fire, hazard_type=fire_risk)` | 熄灭、燃尽、隔离后关闭 |
| `object.poisonous_item` | ObjectRuleDeriver | `WorldObject.object_type`, `components.consumable`, `state`, `physical.traits` | 有毒容器、poisonous trait、被毒素污染的对象 | `HazardSource(source_kind=world_object, hazard_type=poison_risk)` | 清理、丢弃、净化、耗尽后关闭 |
| `object.infected_item` | ObjectRuleDeriver | `WorldObject.object_type`, `components.consumable`, `state`, `physical.traits` | 腐坏食物、腐败容器、污染布料或尸骸相关对象 | `HazardSource(source_kind=world_object, hazard_type=infection_risk)` | 清理、丢弃、净化、耗尽后关闭 |
| `structure.unstable_structure` | StructureRuleDeriver | `Site.state`, `LocationNode.tags`, `WorldObject.fixture_profile` | 危墙、塌陷地板、腐烂木桥、破损屋顶 | `HazardSource(source_kind=structure, hazard_type=collapse_risk)` | 修复、封闭、拆除后关闭 |
| `structure.fall_exposure` | StructureRuleDeriver | `LocationEdge`, `portal_profile`, `fixture_profile` | 断楼梯、无护栏高处、破口 | `HazardSource(source_kind=structure, hazard_type=fall_risk)` | 修复、封闭或安装防护后关闭 |
| `abnormal.field_low_visibility` | EnvironmentDeriver | `EnvironmentState`, `abnormal_pressure`, `weather_state.condition` | abnormal_mist/space_distortion 等异常场 | `HazardSource(source_kind=abnormal_field, hazard_type=low_visibility_risk)` | 异常场消失或离开区域后关闭 |

### ObstacleSource 产生规则表

| rule_id | producer | 输入事实 | 条件 | 输出 | 失效/更新 |
| --- | --- | --- | --- | --- | --- |
| `terrain.cliff_to_obstacle` | TerrainHazardObstacleDeriver | `WorldChunk.terrain.landform`, `ChunkEdge.base_passability` | landform=cliff 或 slope=impassable | `ObstacleSource(source_kind=terrain, obstacle_type=cliff)`，附带 `passability_override.state=blocked` | 地形迁移或 edge 基础关系改变后关闭 |
| `terrain.impassable_to_blocked_path` | TerrainHazardObstacleDeriver | `terrain.slope`, `ChunkEdge.base_passability` | slope=impassable 或 base_passability.state=blocked 且原因来自地形 | `ObstacleSource(source_kind=terrain, obstacle_type=blocked_path)`，附带 `passability_override.state=blocked` | 可通行路径生成或绕路建立后更新 |
| `water.fast_water_crossing` | WaterHazardObstacleDeriver | `terrain.water_presence`, `ChunkEdge.base_passability`, `WeatherState` | river/stream 且 crossing 需要桥、浅滩、船或条件 | `ObstacleSource(source_kind=water, obstacle_type=fast_water)`，附带 conditional 或 difficult override | 水位下降、桥/浅滩可用后降级 |
| `water.deep_water_blocked_path` | WaterHazardObstacleDeriver | `terrain.water_presence`, `ChunkEdge.base_traversal` | deep pond/river/lake_shore 阻断普通移动 | `ObstacleSource(source_kind=water, obstacle_type=blocked_path)`，附带 `passability_override.state=blocked` | 新路径、船、桥或冰面可通行后更新 |
| `vegetation.fallen_tree` | EcologyResourceDeriver | `FloraPatch`, `WorldObject.physical.traits`, `placement` | 倒木占据路径或门口 | `ObstacleSource(source_kind=vegetation, obstacle_type=fallen_tree)` | 移走、砍断、绕行后关闭 |
| `vegetation.dense_growth_blocked_path` | EcologyResourceDeriver | `FloraPatch.coverage`, `PlantSpecies.growth_form` | dense vine/thicket 阻挡通行 | `ObstacleSource(source_kind=vegetation, obstacle_type=blocked_path)` | 清理、绕行、开路后关闭 |
| `object.heavy_object_blocks_path` | ObjectRuleDeriver | `WorldObject.physical`, `placement`, `fixture_profile` | heavy/portable=false 且位于 doorway/path | `ObstacleSource(source_kind=world_object, obstacle_type=heavy_object)` | 对象移动、拆解或路径改变后关闭 |
| `object.sealed_container` | ObjectRuleDeriver | `WorldObject.object_type`, `components.container`, `mechanism_profile` | 容器封闭且阻挡搜索/取物 | `ObstacleSource(source_kind=world_object, obstacle_type=sealed_container)` | 打开、破坏、解锁后关闭 |
| `object.locked_portal` | ObjectRuleDeriver | `WorldObject.object_type`, `portal_profile`, `mechanism_profile` | portal locked 或对应 LocationEdge 条件不满足 | `ObstacleSource(source_kind=world_object, obstacle_type=locked_door)` | 解锁、打开或权限满足后关闭 |
| `structure.collapsed_wall` | StructureRuleDeriver | `Site.state`, `LocationNode.tags`, `WorldObject.fixture_profile` | 塌墙、堵门、坍塌入口 | `ObstacleSource(source_kind=structure, obstacle_type=collapsed_wall)` | 清理、修复或新入口发现后更新 |
| `structure.blocked_path` | StructureRuleDeriver | `LocationEdge.base_passability`, `portal_profile`, `fixture_profile` | 结构损坏导致路径阻断 | `ObstacleSource(source_kind=structure, obstacle_type=blocked_path)`，附带 `passability_override.state=blocked` | 结构修复或绕路建立后更新 |
| `mechanism.locked_door` | ObjectRuleDeriver | `mechanism_profile`, `portal_profile`, `key_profile` | 锁具生效且阻挡 enter/open | `ObstacleSource(source_kind=mechanism, obstacle_type=locked_door)` | 解锁、破坏、权限满足后关闭 |
| `mechanism.jammed_mechanism` | ObjectRuleDeriver | `mechanism_profile.operable`, `state` | operable=false 或 jammed 状态 | `ObstacleSource(source_kind=mechanism, obstacle_type=jammed_mechanism)` | 修理、强行打开、拆除后关闭 |
| `environment.deep_mud` | EnvironmentDeriver | `EnvironmentState.ground_effects`, `terrain.ground` | muddy/deep_mud 且影响通行 | `ObstacleSource(source_kind=weather_environment, obstacle_type=deep_mud)` | 地面干燥、离开区域或铺设路径后关闭 |
| `environment.weather_blocked_path` | EnvironmentDeriver | `weather_state.condition`, `EnvironmentState` | storm/snow/fog 造成临时不可辨路或封路 | `ObstacleSource(source_kind=weather_environment, obstacle_type=blocked_path)` | 天气变化或路线标记后关闭 |
| `resource.deposit_blocks_path` | EcologyResourceDeriver | `ResourceDeposit.stock.capacity_amount`, `ResourceDeposit.stock.current_amount`, `location`, `terrain_tags` | 碎石堆、矿渣堆、大型资源堆占据路径 | `ObstacleSource(source_kind=resource_deposit, obstacle_type=blocked_path)` | 采集、清理、绕行后关闭 |
| `resource.deposit_heavy_object` | EcologyResourceDeriver | `ResourceDeposit.stock.capacity_amount`, `ResourceDeposit.stock.current_amount`, `location`, `terrain_tags` | 大型矿石、沉重资源堆无法直接搬开 | `ObstacleSource(source_kind=resource_deposit, obstacle_type=heavy_object)` | 采集、分解、清理后关闭 |
| `resource.deposit_deep_mud` | EcologyResourceDeriver | `ResourceDeposit.resource_id`, `terrain.ground`, `EnvironmentState.ground_effects` | 厚泥层、泥炭、湿泥资源阻碍通行 | `ObstacleSource(source_kind=resource_deposit, obstacle_type=deep_mud)` | 干燥、铺路、绕行、清理后关闭 |
| `abnormal.field_blocks_path` | EnvironmentDeriver | `abnormal_pressure`, `EnvironmentState`, `LocationEdge` | 空间错位、异常雾墙阻断路径 | `ObstacleSource(source_kind=abnormal_field, obstacle_type=blocked_path)` | 异常场消失、稳定或绕行后关闭 |
| `abnormal.field_jams_mechanism` | EnvironmentDeriver | `abnormal_pressure`, `EnvironmentState`, `mechanism_profile` | 异常场导致机关卡死 | `ObstacleSource(source_kind=abnormal_field, obstacle_type=jammed_mechanism)` | 异常场消失、修复或稳定后关闭 |

### 产生时机

```text
WorldGenerator 完成地形、水系、生态、对象、结构生成后，必须运行全量 Deriver。
EnvironmentDeriver 只在 WorldTimeState、WeatherState 或 EnvironmentState 改变后运行。
ObjectRuleDeriver 只在 WorldObject 创建、移动、组件变化或 state 变化后运行。
EcologyResourceDeriver 只在 FloraPatch、ResourceDeposit、ResourceNode 创建、stock 变化、derived 变化或 state 变化后运行。
StructureRuleDeriver 只在 Site、LocationNode、LocationEdge 或结构对象变化后运行。
DeterministicResolver 只在动作结算导致世界事实变化后创建、关闭、升级或降级 HazardSource/ObstacleSource。
PassabilityReducer 只在 edge base 值或 active passability_override 集合变化后运行。
MigrationTool 和 TestFixture 产生的 HazardSource/ObstacleSource 必须标记 generated_by.system，且不得出现在正常玩法 producer 中。
```

### 失效和更新规则

```text
HazardSource / ObstacleSource 不直接删除，优先更新 state.active=false，除非执行存档压缩或迁移。
当 source_entity_ids 中任一实体被 removed，相关 HazardSource / ObstacleSource 必须重新校验。
当 EnvironmentState 超出 valid_for，依赖该 EnvironmentState 的临时危险/障碍必须重新派生或关闭。
当 ObstacleSource.state.active 或 passability_override 变化时，必须触发 PassabilityReducer 重算关联 edge。
每次 create/update/deactivate 必须先形成 StateTransition，并由 StateTransitionCommitter 原子提交 WorldState 变化和 EventLogEntry。
```

## 运行规则

### 时间规则

```text
WorldRuntimeInitialization 必须在 SpatialFoundationMaterializer 和全部静态内容/历史阶段成功后、WeatherFormation 前执行，且一个 world_id 只能成功执行一次。
WorldTimeState 必须存在于 WorldState。
clock.absolute_minute 必须是非负整数，并且只能随 TimeAdvanced 单调增加。
minute_of_day 必须在 0 到 1439 之间。
minute_of_day 必须等于 clock.absolute_minute % 1440。
calendar.day、calendar.season_day 和 time_band 必须能由 absolute_minute、calendar 配置和 seasonal_daylight_profile 校验。
time_band 必须属于 time_band 闭集，并由 minute_of_day、season 和 seasonal_daylight_profile 校验。
WorldTimeState 不允许持有最终 light_level、ambient_c、weather_state_id。
light_level、ambient_c、visibility_modifier、ground_effects 必须由 EnvironmentState 表达。
EnvironmentState 必须由 WorldTimeState、weather_state、terrain、LocationNode.environment、WorldObject 光源/热源等输入派生或校验。
WeatherState 字段必须与气候地形形成规则文档的 WeatherFormation 输出保持一致。
时间推进必须形成 TimeAdvanced StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry。
所有运行时有效期必须使用 GameTimeInterval。
时间推进后，受影响的 EnvironmentState 必须重新派生、标记失效，或通过 validator 证明仍在 valid_for 范围内。
时间推进到某个区间的 end_world_minute 时，该区间已经失效，必须读取或生成下一个覆盖当前 absolute_minute 的区间。
初始 WeatherState 只能读取已提交 WorldTimeState，不能读取 initial_time 参数绕过时间实体。
```

### 天气规则

```text
WeatherState 必须存在于 WorldState，并通过 runtime_state.active_weather_state_ids 指向当前有效天气片段。
P0 常规 WeatherState 挂在 Region；scope=world_chunk 只能作为明确的局部覆盖。
WeatherState 不能挂在 WorldTimeState 上。
WeatherState.valid_for 必须使用 GameTimeInterval，并遵守 [start_world_minute, end_world_minute) 半开区间。
每个 Region 在任意 absolute_minute 必须恰好命中一个 coverage_priority=base_region 的 WeatherState。
同一 Region 的 base_region WeatherState 区间必须连续且不重叠。
同一 Region 的相邻 base_region WeatherState 必须满足 previous.end_world_minute = current.start_world_minute。
WeatherState.previous_weather_state_id 不为 null 时，previous_weather_state_id 指向的同 scope 天气片段必须正好在当前片段开始时结束。
scope=world_chunk 的局部天气覆盖必须引用父级 Region WeatherState。
局部天气覆盖的 valid_for 必须完全包含在 parent_weather_state_id 的 valid_for 内，不能早于父级开始，也不能晚于父级结束。
同一空间存在多个局部覆盖时，按 coverage_priority.rank DESC、start_world_minute ASC、id ASC 稳定排序；同优先级同时间重叠必须被 validator 拒绝，除非来源是 test fixture。
当前时间等于 WeatherState.valid_for.end_world_minute 时，该 WeatherState 已失效，必须生成下一段或读取下一段。
WeatherService.advance(time_delta) 是正常时间推进中的天气入口。
WeatherResolver 只处理规则事件或 LLM proposal 触发的天气变化请求。
同样 RandomSeedMaterial、Region、上一段 WeatherState 和目标时间必须得到同样的下一段 WeatherState。
短行动不检查天气变化，除非行动后当前时间跨过天气片段结束时间。
长休、睡觉、赶路或等待跨过多个天气片段时，必须按片段逐段形成 WeatherChanged StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry；DM/UI 可以只总结重要变化。
玩家跨 Region 时读取目标 Region 当前 WeatherState，不把原 Region 天气带到新 Region。
天气变化后，受影响的 EnvironmentState 必须重新派生、标记失效，或通过 validator 证明仍在 valid_for 范围内。
天气结束后仍存在的 wet/muddy/slippery/snow_covered/fast_water 必须创建或更新 EnvironmentResidualEffectState。
天气变化后，依赖 EnvironmentState 的 HazardSource / ObstacleSource 必须重新派生、关闭或降级。
WeatherState 不允许直接创建物品。
LLM proposal 不允许直接创建 WeatherState、修改 WeatherState 或提交 WeatherChanged StateTransition。
```

天气推进流程：

```text
1. TimeService 推进 WorldTimeState。
2. WeatherService.advance 读取每个受影响 Region 当前覆盖目标 absolute_minute 的 base_region WeatherState。
3. 如果目标 absolute_minute 仍满足 start_world_minute <= target < end_world_minute，天气不变。
4. 如果目标 absolute_minute 跨过一个或多个 WeatherState.end_world_minute，按天气转移表逐段生成下一段 WeatherState。
5. 每生成一段新 WeatherState，必须让上一段 end_world_minute 等于下一段 start_world_minute，并形成 WeatherChanged StateTransition。
6. 对上一段天气结束后仍应保留的 ground_effects，EnvironmentDeriver 创建或更新 EnvironmentResidualEffectState，并形成 EnvironmentResidualEffectCreated / EnvironmentResidualEffectStateChanged StateTransition。
7. 由 StateTransitionCommitter 原子更新 runtime_state.active_weather_state_ids、active_environment_residual_effect_ids 和对应 EventLogEntry。
8. EnvironmentDeriver 使用当前 WeatherState、当前有效残留、WorldTimeState 和空间输入重新派生受影响空间的 EnvironmentState。
9. Hazard/Obstacle Deriver 根据新的 EnvironmentState 更新危险和障碍及其 passability_override。
10. PassabilityReducer 重算受影响 edge 的 effective_passability / effective_traversal。
```

天气生成规则表：

| rule_id | 入口 | 允许场景 | 输出 |
| --- | --- | --- | --- |
| `weather.initial_by_climate` | WeatherFormation | 世界生成或 Region 初始化 | 创建第一段 Region WeatherState，`previous_weather_state_id=null`。 |
| `weather.transition_by_climate_season_terrain` | WeatherFormation | 时间推进超过当前天气片段结束时间 | 按天气转移表创建下一段 WeatherState。 |
| `weather.local_override_by_abnormal_pressure` | WeatherFormation | abnormal_pressure 或异常地形明确支持局部天气 | 创建 `scope=world_chunk` 的局部 WeatherState，必须引用父级 Region WeatherState。 |
| `weather.resolver_validated_change` | WeatherResolver | 规则事件或 LLM proposal 请求天气变化，并通过校验 | 创建合法 WeatherState；不合法请求必须拒绝或降级为最近合法天气。 |
| `weather.test_fixture` | TestFixture | 自动化测试 | 只用于测试夹具，不属于正常玩法来源。 |

LLM 天气变更提议只能使用以下结构：

```json
{
  "proposal_type": "weather_change",
  "reason": "dramatic_tension",
  "target_scope": "region",
  "target_region_id": "north_slope_wilds",
  "suggested_condition": "storm",
  "suggested_intensity": "heavy"
}
```

WeatherResolver 必须校验：

```text
目标天气是否属于 weather_condition 闭集。
目标强度是否属于 weather_intensity 闭集。
目标天气是否符合当前 Region 气候、季节、地形或 abnormal_pressure。
目标天气是否符合天气转移表；不符合时只能降级为最近合法天气。
当前天气片段是否已达到最短持续时间。
是否会导致天气变化过密。
新 WeatherState 是否使用合法 GameTimeInterval。
新 WeatherState 是否破坏同 Region base_region 唯一性、连续性或不重叠约束。
局部天气覆盖是否有父级 Region WeatherState，并且生命周期是否完全落在父级区间内。
是否形成 WeatherChanged StateTransition，并由 StateTransitionCommitter 生成 EventLogEntry。
是否触发 EnvironmentState 重算。
```

### 环境状态和残留规则

```text
EnvironmentState.valid_for 必须使用 GameTimeInterval。
EnvironmentState.valid_for 不能超出参与派生的 WeatherState、WorldTimeState 有效推导边界和残留效果边界。
EnvironmentState.ground_effects 只能来自当前 WeatherState.ground_effects、当前有效 EnvironmentResidualEffectState、地形和局部对象状态。
WeatherState 结束后，EnvironmentState 不能继续把旧 weather_state.condition 当作当前天气。
雨停、雪停、风暴结束、泼水、燃烧、异常场消退后仍存在的局部效果，必须进入 EnvironmentResidualEffectState。
EnvironmentResidualEffectState 有效判断固定为 start_world_minute <= current_absolute_minute < end_world_minute。
EnvironmentResidualEffectState 到达 end_world_minute 时必须过期，或按 decay 生成下一阶段残留。
残留创建、衰减、过期必须通过 StateTransition 提交，并由 StateTransitionCommitter 生成 EventLogEntry，同时触发 EnvironmentState 重算。
EnvironmentDeriver 只能读取 active 残留，不能读取过期残留来派生当前环境。
```

### 危险和障碍规则

```text
HazardSource 只表达风险来源，不直接修改状态。
HazardSource.source_kind 必须属于 hazard_source_kind 闭集。
HazardSource.source_kind 和 hazard_type 必须符合 HazardSource 允许映射表。
HazardSource.source_entity_ids 必须引用产生该危险的权威实体。
HazardSource.generated_by.rule_id 必须来自 HazardSource 产生规则表。
ObstacleSource 只表达阻挡来源，不替代 ChunkEdge、LocationEdge 或 SiteBoundaryEdge。
ObstacleSource.source_kind 必须属于 obstacle_source_kind 闭集。
ObstacleSource.source_kind 和 obstacle_type 必须符合 ObstacleSource 允许映射表。
ObstacleSource.source_entity_ids 必须引用产生该障碍的权威实体。
ObstacleSource.generated_by.rule_id 必须来自 ObstacleSource 产生规则表。
如果 ObstacleSource 阻挡移动，必须提供 passability_override.target_edge_ids，最终通行状态只能由 PassabilityReducer 写入相关 Edge 的 effective_passability / effective_traversal。
如果危险来自具体对象，例如捕兽夹，优先使用 WorldObject(object_type=trap) + trap_profile，并可额外挂 HazardSource。
如果障碍来自具体对象，例如门、箱子、倒木，优先使用 WorldObject + placement；ObstacleSource 只记录其阻挡语义。
内容包和 LLM proposal 不允许新增 source_kind、hazard_type 或 obstacle_type。
内容包和 LLM proposal 不允许直接创建最终 HazardSource / ObstacleSource。
HazardSource / ObstacleSource 的 create/update/deactivate 必须通过 StateTransition 提交，并由 StateTransitionCommitter 生成 EventLogEntry。
PassabilityReducer 写入 effective_passability / effective_traversal 时必须通过 StateTransition 提交，并由 StateTransitionCommitter 生成 event_type=EdgeEffectivePassabilityChanged 的 EventLogEntry。
```

### 事件日志规则

```text
所有权威状态变更必须通过 StateTransition 或 StateTransitionBatch 提交，并在同一原子提交中生成 EventLogEntry。
EventLog.sequence 必须单调递增。
EventLog 只能由 StateTransitionCommitter 写入；确定性生成器、resolver、迁移工具或测试夹具只能产出 StateTransition。
LLM proposal 不能直接写 EventLog。
EventLog.summary 不是权威状态，不能作为 resolver 输入。
EventLogEntry 不自动成为任何 NPC、群体或玩家的知识；知情关系必须由 KnowledgePropagation 写入 KnowledgeState。
EventLogEntry.version_context 必须存在，并与事件提交后的 WorldState.version_lock 一致。
SchemaMigrated 事件必须用 preconditions 记录迁移前 `World.version_lock`，用 changes 更新迁移后 `World.version_lock`，并让 `version_context` 等于迁移后的版本锁。
```

### 快照规则

```text
世界生成完成后必须创建一次 WorldSnapshot。
schema migration 前后必须创建 WorldSnapshot。
调试验收流程可以创建 WorldSnapshot。
WorldSnapshot.event_sequence 必须等于创建快照时 WorldState.runtime_state.latest_event_sequence。
WorldSnapshot.state_hash 必须等于创建快照时的 WorldStateContentHash。
WorldSnapshot.latest_event_hash 必须等于 event_sequence 对应 EventLogEntry.event_hash；event_sequence=0 时为 null。
WorldSnapshot.snapshot_hash 必须可由 snapshot payload 重算。
WorldSnapshot.version_lock 必须存在，并与创建快照时 WorldState.version_lock 一致。
WorldSnapshot.version_lock 必须包含 schema_version、registry_hash、rule_bundle_hash、content_pack_hash 和 content_pack_refs。
Snapshot 恢复后必须重新运行 validator。
Snapshot 恢复后必须重新校验 world_facts、knowledge_facts 和 system_ledger 命名空间。
恢复到 target_sequence 时，可以选择 event_sequence <= target_sequence 的最近有效 Snapshot，并从 snapshot.event_sequence + 1 开始重放。
Snapshot.version_lock 与当前运行时 version_lock 不一致时，不能直接恢复到可运行状态，必须通过迁移流程。
迁移流程必须创建 before_migration 和 after_migration 两个 Snapshot，并通过 StateTransitionCommitter 生成 SchemaMigrated EventLogEntry。
```

### 历史来历规则

```text
OriginEvent 和 OriginMetadata 由世界模型层定义。
OriginMetadata 只解释静态世界事实来源，不替代 EventLog。
OriginMetadata.origin_event_ids 引用不存在时 validator 必须拒绝。
OriginEvent.evidence_entity_ids 与实体反向 OriginMetadata 必须保持一致。
```

## 与现有文档关系

| 文档 | 关系 |
| --- | --- |
| 地点与空间规则 | HazardSource、ObstacleSource、EnvironmentState 需要引用 chunk、edge、site、node、zone；`PassabilityReducer` 只写 Edge 的 effective 通行字段。 |
| 世界生成输出清单规则 | WorldRuntimeInitialization 和 WeatherFormation 必须是有依赖关系的独立阶段；StaticWorldRuntimeState 与 WorldTimeState 使用原子生成输出提交。 |
| 气候地形形成规则 | 定义 WeatherFormation、天气闭集、转移表和持续时间范围；本文件定义 WeatherState 的运行时挂载、推进、事件和校验。 |
| 历史来历与世界痕迹规则 | 定义 OriginEvent、OriginMetadata 和证据校验；本文件只负责运行时引用校验和快照覆盖。 |
| 知识、发现与事件知情规则 | 定义 KnowledgeState、KnowledgePropagation 和 AgentObservationSnapshot；本文件的 EventLog 不能直接暴露为游戏内记忆。 |
| 自然生态与资源规则 | 自然资源可能生成 HazardSource，例如毒水、泥潭、腐败资源。 |
| WorldObject 规则 | 具体门、陷阱、容器、火把、倒木等仍是 WorldObject；本文件只定义其危险或障碍语义。 |
| AI 社会心智 | AIDecisionTick、AI proposal 和 reservation 存入 system_ledger；只有通过 validator、冲突处理和 resolver 的 proposal 才能修改权威状态，并且必须形成 StateTransition，由 StateTransitionCommitter 生成 EventLogEntry。 |

## Validator 规则

实现时必须加入 `StaticWorldRuntimeValidator`，保证：

1. `WorldTimeState.world_id` 必须引用存在的 World。
2. `calendar.season`、`clock.time_band` 必须属于闭集。
3. `clock.absolute_minute` 必须是非负整数。
4. `clock.minute_of_day` 必须在 0 到 1439，且等于 `clock.absolute_minute % 1440`。
5. `WorldTimeState` 不允许包含 `light`、`temperature` 或 `weather_state_id`。
6. `runtime_state.active_weather_state_ids` 必须引用存在的 WeatherState。
7. `runtime_state.active_environment_residual_effect_ids` 必须引用存在且当前有效的 EnvironmentResidualEffectState。
8. 所有 `valid_for` 必须使用 `GameTimeInterval(start_world_minute, end_world_minute)`，禁止旧字段 `from_day/from_minute_of_day/until_day/until_minute_of_day`。
9. `GameTimeInterval.end_world_minute` 必须大于 `start_world_minute`。
10. `WeatherState.world_id` 必须引用存在的 World。
11. `WeatherState.scope` 必须是 region 或 world_chunk。
12. `WeatherState.coverage_priority` 必须属于 `weather_coverage_priority` 闭集。
13. `WeatherState.scope=region` 时必须引用存在的 Region，`chunk_id` 和 `parent_weather_state_id` 必须为 null，`coverage_priority` 必须为 `base_region`。
14. 每个 Region 在任意 `absolute_minute` 必须恰好有一个 `coverage_priority=base_region` 的 WeatherState 覆盖。
15. 同一 Region 的 base_region WeatherState 区间必须连续且不重叠。
16. `WeatherState.scope=world_chunk` 时必须引用存在的 Region、WorldChunk 和父级 Region WeatherState。
17. 局部 WeatherState 的 `valid_for` 必须完全落在父级 Region WeatherState 的 `valid_for` 内。
18. 同一空间同优先级的局部 WeatherState 不允许时间区间重叠，除非 `coverage_priority=test_fixture_override`。
19. `WeatherState.condition` 必须属于 `weather_condition` 闭集。
20. `WeatherState.intensity` 必须属于 `weather_intensity` 闭集。
21. `WeatherState.wind` 必须属于 `wind_level` 闭集。
22. `WeatherState.ground_effects[]` 必须属于 `weather_ground_effect` 闭集。
23. `WeatherState.valid_for` 的持续时间必须符合对应 condition 的持续时间范围。
24. `WeatherState.previous_weather_state_id` 不为 null 时，必须引用同 scope 上一段 WeatherState，且上一段 `end_world_minute` 等于当前 `start_world_minute`。
25. `WeatherState.previous_weather_state_id` 不为 null 时，当前 condition 必须符合天气转移表。
26. `WeatherState.generated_by.system` 必须属于 WeatherFormation、WeatherResolver 或 TestFixture。
27. `WeatherState.generated_by.rule_id` 必须来自天气生成规则表。
28. active WeatherState 的有效时间必须覆盖当前 `WorldTimeState.clock.absolute_minute`，或系统必须立即推进生成下一段。
29. `EnvironmentState.world_id` 必须引用存在的 World。
30. `EnvironmentState.source_time_state_id` 必须引用存在的 WorldTimeState。
31. `EnvironmentState.scope` 必须属于 `environment_scope` 闭集。
32. `EnvironmentState` 根据 scope 必须引用存在的 Region、WorldChunk、Site、LocationNode 或 Zone。
33. `EnvironmentState.weather_state_id` 如果不为 null，必须引用存在的 WeatherState。
34. `EnvironmentState.light.light_level` 必须属于闭集。
35. `EnvironmentState.light.natural_light` 必须属于闭集。
36. `EnvironmentState.temperature.temperature_band` 必须属于闭集。
37. `EnvironmentState.valid_for` 必须是合法 GameTimeInterval。
38. `EnvironmentState.derived_from.residual_effect_ids[]` 必须引用存在的 EnvironmentResidualEffectState。
39. `EnvironmentState.ground_effects[]` 必须能由当前 WeatherState、当前有效残留、地形或局部对象状态解释。
40. `EnvironmentResidualEffectState.world_id` 必须引用存在的 World。
41. `EnvironmentResidualEffectState.scope` 必须属于 `environment_scope` 闭集。
42. `EnvironmentResidualEffectState` 根据 scope 必须引用存在的 Region、WorldChunk、Site、LocationNode 或 Zone。
43. `EnvironmentResidualEffectState.effect_type` 必须属于 `environment_residual_effect_type` 闭集。
44. `EnvironmentResidualEffectState.intensity` 必须属于 `environment_residual_intensity` 闭集。
45. `EnvironmentResidualEffectState.source.source_kind` 必须属于 `environment_residual_source_kind` 闭集。
46. `EnvironmentResidualEffectState.source.source_kind + effect_type` 必须符合环境残留来源映射表。
47. `EnvironmentResidualEffectState.source.source_entity_id` 必须引用存在的权威实体。
48. `EnvironmentResidualEffectState.decay.decay_rule_id` 必须来自环境残留衰减规则表。
49. `EnvironmentResidualEffectState.decay.mode` 必须属于 `environment_residual_decay_mode` 闭集。
50. `EnvironmentResidualEffectState.state` 必须属于 `environment_residual_state` 闭集。
51. 同一 scope、effect_type、source_entity_id 的 active 残留区间不允许重叠。
52. `HazardSource.location` 必须引用存在的 chunk、edge、node、zone 或 object。
53. `ObstacleSource.location` 必须引用存在的 chunk、edge、node、zone 或 object。
54. `HazardSource.source_kind` 必须属于 `hazard_source_kind` 闭集。
55. `ObstacleSource.source_kind` 必须属于 `obstacle_source_kind` 闭集。
56. `HazardSource.hazard_type` 必须属于闭集。
57. `ObstacleSource.obstacle_type` 必须属于闭集。
58. `HazardSource.source_kind + hazard_type` 必须符合 HazardSource 允许映射表。
59. `ObstacleSource.source_kind + obstacle_type` 必须符合 ObstacleSource 允许映射表。
60. `HazardSource.source_entity_ids` 和 `ObstacleSource.source_entity_ids` 必须非空，且引用存在实体。
61. `generated_by.system` 必须属于允许 producer 集合。
62. `generated_by.rule_id` 必须存在于 HazardSource 或 ObstacleSource 产生规则表。
63. `generated_by.rule_id` 对应的输出 source_kind 和 type 必须与当前实体一致。
64. 每个产生规则只能声明一个 primary hazard_type 或 obstacle_type，不允许用斜杠或列表表达多个输出。
65. 激活的 `ObstacleSource.passability_override.target_edge_ids` 必须引用存在的 ChunkEdge、LocationEdge 或 SiteBoundaryEdge。
66. 激活的 `ObstacleSource.passability_override.state` 必须属于 passability_override_state 闭集。
67. state=conditional 的 passability_override 必须提供非空 conditions。
68. state=blocked 的 passability_override 必须提供 blocked_reason。
69. state=difficult 的 passability_override 必须提供 time_delta_minutes 或 risk_tags。
70. `ChunkEdge` / `LocationEdge` / `SiteBoundaryEdge` 的 `effective_passability` 和 `effective_traversal` 必须能由 `PassabilityReducer(base, active_overrides)` 重算得到。
71. 除 `PassabilityReducer` 外，任何系统写 `effective_passability` / `effective_traversal` 都必须被拒绝。
72. Hazard/Obstacle Deriver 不能读取 `effective_passability` 作为 HazardSource / ObstacleSource 的生成依据。
73. `EventLog.sequence` 必须连续递增。
74. `EventLog.occurred_at.absolute_minute` 必须存在，并且与 `occurred_at.minute_of_day` 一致。
75. `EventLog.changes[].entity_id` 引用的实体必须存在，除非 `op=create`。
76. `EventLog.version_context` 必须存在，并与提交后的 `WorldState.version_lock` 一致。
77. `EventLog.event_type=SchemaMigrated` 时必须记录迁移前后 version context。
78. 创建 `WorldSnapshot` 时，`WorldSnapshot.event_sequence` 必须等于当前 `WorldState.runtime_state.latest_event_sequence`；恢复到 `target_sequence` 时，恢复器只能选择 `event_sequence <= target_sequence` 的有效 Snapshot。
79. `WorldSnapshot.state_hash`、`latest_event_hash` 和 `snapshot_hash` 必须可由快照内容与对应 EventLog 重算。
80. `WorldSnapshot.version_lock` 必须包含 schema_version、registry_hash、rule_bundle_hash、content_pack_hash 和 content_pack_refs。
81. `WorldSnapshot.version_lock` 必须与快照内容中的 `AuthoritativeWorldState.version_lock` 一致。
82. Snapshot 直接恢复只能发生在 `snapshot.version_lock == runtime.version_lock` 时。
83. 版本不一致时必须存在迁移前后 Snapshot 和 `SchemaMigrated` EventLog。
84. `OriginMetadata.origin_event_ids` 必须引用存在 OriginEvent。
85. `OriginEvent.evidence_entity_ids` 必须引用存在实体，并与证据实体的反向 OriginMetadata 一致。
86. `WorldRuntimeInitialization` 必须读取已经提交的 World；该 World 的空间基础原子提交组和 `origin_attachment` 之前的全部静态生成阶段都必须完成。
87. 同一 `world_id` 只能存在一个 active StaticWorldRuntimeState 和一个当前 WorldTimeState。
88. 初始化输入不能直接提供 `minute_of_day`、`time_band` 或 `calendar_label`；这些字段必须由确定性 deriver 产生。
89. 初始 `StaticWorldRuntimeState.version_lock` 必须等于 `World.version_lock` 和 WorldGenerationManifest 版本锁。
90. 初始 active weather、environment、residual、hazard 和 obstacle ID 集合必须为空。
91. 初始 `runtime_state.time_state_id` 必须引用同一原子提交中创建的 WorldTimeState。
92. 初始 `runtime_state.latest_snapshot_id` 必须为 null，直到 after_world_generation Snapshot 成功写入。
93. WeatherFormation 的 GenerationStageContract 必须依赖 WorldRuntimeInitialization。
94. 初始 WeatherState.valid_for 必须覆盖 `WorldTimeState.clock.absolute_minute`。
95. 初始 `runtime_state.latest_event_sequence` 必须等于同一原子提交中 `TimeInitialized.sequence`，不能使用 0、null 或提交前序号占位。
96. `TimeInitialized.occurred_at.absolute_minute/day/minute_of_day` 必须与新建 WorldTimeState 和 WorldGenerationParameters.initial_time 一致。

## 推荐实现顺序

### P0.1：WorldTimeState

- 增加 `WorldRuntimeInitialization` 阶段和初始化参数 schema。
- 原子创建 `StaticWorldRuntimeState` 与 `WorldTimeState`。
- 增加 `WorldTimeState` schema。
- 增加 `GameTimeInterval` 通用 schema，并禁止旧式 day/minute 有效期字段。
- 增加 `TimeInitialized`、`TimeAdvanced` 事件。
- 增加时间、季节闭集 validator。

验收：

```text
给定 minute_of_day=1080，WorldTimeState.clock.time_band 可以校验为 dusk。
给定 absolute_minute=16920，minute_of_day 必须等于 1080。
minute_of_day=1440 会被 validator 拒绝。
valid_for 使用 from_day/from_minute_of_day/until_day/until_minute_of_day 会被 validator 拒绝。
WorldTimeState 出现 light 或 temperature 字段会被 validator 拒绝。
WorldTimeState 尚未提交时，WeatherFormation 会被阶段依赖校验拒绝。
```

### P0.1.1：WeatherState / WeatherService

- 增加 `WeatherState` schema。
- 增加 `runtime_state.active_weather_state_ids`。
- 增加 `WeatherState.coverage_priority`。
- 增加 `WeatherInitialized`、`WeatherChanged` 事件。
- 增加天气闭集、强度闭集、风力闭集和地面效果闭集 validator。
- 增加天气转移表和持续时间范围 validator。
- 增加同 Region base_region 天气唯一性、连续性和不重叠 validator。
- 增加局部天气父级生命周期 validator。
- 实现 `WeatherService.advance(time_delta)`。
- 实现 `WeatherResolver`，只接受规则事件或 LLM proposal 请求，不允许 LLM 直接写天气。

验收：

```text
同一 RandomSeedMaterial、Region、上一段天气和目标时间必须生成同一段下一天气。
当前天气未过期时，短行动不会生成新的 WeatherState。
长休跨过多个天气片段时，必须生成连续 WeatherChanged StateTransition，并由 StateTransitionCommitter 提交。
当前 absolute_minute 等于 WeatherState.valid_for.end_world_minute 时，必须切到下一段天气。
同一 Region 两个 base_region WeatherState 区间重叠会被 validator 拒绝。
同一 Region base_region WeatherState 中间有时间空洞会被 validator 拒绝。
storm 不能直接转 clear，必须被 validator 拒绝。
WeatherState(scope=world_chunk) 没有 parent_weather_state_id 会被 validator 拒绝。
WeatherState(scope=world_chunk) 生命周期超出父级 Region WeatherState 会被 validator 拒绝。
LLM proposal 直接写 WeatherState 会被 validator 拒绝。
```

### P0.1.2：EnvironmentState

- 增加 `EnvironmentState` schema。
- 增加 `EnvironmentResidualEffectState` schema。
- 增加 `runtime_state.active_environment_residual_effect_ids`。
- 增加 `EnvironmentResidualEffectCreated`、`EnvironmentResidualEffectStateChanged` 事件。
- 支持按 WorldChunk、Site、LocationNode、Zone 派生局部光照、温度、地面效果。
- 增加 EnvironmentState 空间引用、光照闭集、有效期和残留引用 validator。
- 增加环境残留来源映射、衰减规则和重叠区间 validator。
- EnvironmentState 必须消费 WeatherState，不能自己发明天气。

验收：

```text
同一 minute_of_day 下，山脊 chunk 可以是 dusk/cold/wet，旅店前厅 node 可以是 dim/cool/dry。
EnvironmentState 引用不存在的 chunk 或 node 会被 validator 拒绝。
EnvironmentState.valid_for 过期后必须重新派生或标记失效。
WeatherState 从 light_rain 切到 cloudy 后，室外 EnvironmentState 可以保留 wet 残留，但不能保留 weather_state.condition=light_rain。
WeatherState 从 light_rain 切到 cloudy 后，保留 wet 必须有 active EnvironmentResidualEffectState 支撑。
EnvironmentResidualEffectState 到达 end_world_minute 后必须过期或进入下一衰减阶段。
同一 scope、effect_type、source_entity_id 的 active 残留区间重叠会被 validator 拒绝。
```

### P0.2：HazardSource / ObstacleSource

- 增加危险和障碍 schema。
- 增加 `hazard_source_kind`、`obstacle_source_kind` 闭集。
- 增加 source_kind 到 hazard_type / obstacle_type 的映射表 validator。
- 增加危险/障碍产生规则表 validator。
- 强制校验 `source_entity_ids`、`generated_by.system`、`generated_by.rule_id`。
- 允许危险/障碍绑定 chunk、edge、node、zone、object。
- 对阻挡移动的障碍校验 passability_override.target_edge_ids 存在。
- 实现 `PassabilityReducer`，唯一写入 Edge effective 通行字段。
- 校验所有 RouteResolver / DM Projection / UI Projection 只读取 effective 通行字段。

验收：

```text
断崖 ObstacleSource 必须生成 passability_override.state=blocked，并由 PassabilityReducer 输出 ChunkEdge.effective_passability.state=blocked。
湿滑岩面 HazardSource 不直接阻断移动，但会进入风险候选。
HazardSource(source_kind=terrain, hazard_type=poison_water) 会被 validator 拒绝。
ObstacleSource(source_kind=mechanism, obstacle_type=fallen_tree) 会被 validator 拒绝。
内容包新增 source_kind=curse_field 会被 validator 拒绝。
HazardSource.generated_by.rule_id 不在产生规则表中会被 validator 拒绝。
source_entity_ids 为空会被 validator 拒绝。
关闭断崖 override 后，effective_passability 必须从 base 值和剩余 active overrides 重算，不能沿用上一轮 blocked 结果。
除 PassabilityReducer 外的系统写 effective_passability 会被 validator 拒绝。
```

### P0.3：StateTransition / EventLog

- 增加 `StateTransition` 和 `StateTransitionBatch` schema。
- 增加 `StateTransitionValidator`。
- 增加 `StateTransitionCommitter`，唯一负责原子写入 WorldState 和 EventLogEntry。
- 增加事件序列表。
- 所有生成器和 resolver 状态写入必须先产生 StateTransition，再由 committer 生成 EventLogEntry。
- 增加 WorldStateContentHash、EventLogEntry.event_hash 和 replay hash 计算接口。
- 增加 materialize/derive lowering validator。
- 增加 delete_for_migration 迁移 payload validator。

验收：

```text
创建 HazardSource 的 StateTransition 必须包含完整 HazardSource create.value。
创建 HazardSource 后必须由 StateTransitionCommitter 生成 HazardCreated 事件。
事件 sequence 缺号或重复会被 validator 拒绝。
expected_sequence 与当前 latest_event_sequence 不一致时，提交必须被拒绝且不改变 WorldState。
expected_entity_revisions 不匹配时，提交必须被拒绝且不追加 EventLogEntry。
相同 idempotency_key 重试必须返回既有提交结果，不能重复应用 ordered_changes。
StateTransitionBatch 中任一 transition 校验失败时，整个批次必须回滚。
StateTransitionBatch 中第 N 条 transition.expected_sequence 必须等于 batch.expected_sequence + N - 1。
StateTransitionBatch 中每条 transition.previous_state_hash 和 previous_event_hash 必须按批内中间状态链式连接。
materialize operation 进入 EventLog 前必须降低为 create，且 create.value 是完整实体。
derive operation 进入 EventLog 前必须降低为 create/update/deactivate，Candidate 不得进入 world_facts。
delete_for_migration 必须携带 migration_plan_id、migration_rule_id、delete_scope、old_value_hash 和 reason_code。
EventLogEntry.event_hash 必须可重算，并且 previous_event_hash 必须连接上一条事件。
从 event 0 重放到任意 event_sequence，最终 WorldStateContentHash 必须等于最后一条 EventLogEntry.resulting_state_hash。
```

### P0.4：WorldSnapshot

- 增加快照 schema。
- 世界生成完成后自动创建快照。
- 快照恢复后运行所有 foundation validators。
- 快照必须保存 version_lock，并在恢复时校验版本锁。
- 快照必须保存 state_hash、latest_event_hash 和 snapshot_hash。
- SnapshotWriter 必须原子写入 snapshot payload、metadata 和 latest_snapshot_id 恢复索引。

验收：

```text
after_world_generation 快照存在。
snapshot.event_sequence 等于 runtime_state.latest_event_sequence。
snapshot.version_lock 等于 AuthoritativeWorldState.version_lock。
snapshot.state_hash 等于 WorldStateContentHash。
snapshot.latest_event_hash 等于 event_sequence 对应 EventLogEntry.event_hash。
snapshot.snapshot_hash 可以重算。
恢复到 target_sequence 时，恢复器选择 event_sequence <= target_sequence 的最近快照，并从 event_sequence + 1 重放。
从任意有效 Snapshot 重放到 target_sequence，最终 WorldStateContentHash 必须与从 event 0 重放得到的 hash 一致。
version_lock 不一致时恢复流程拒绝直接进入运行态。
```

### P0.5：OriginEvent / OriginMetadata 引用校验

- 接入世界模型层的 OriginEvent / OriginMetadata schema。
- 运行时 validator 校验 `origin.origin_event_ids`。
- Snapshot 必须覆盖 OriginEvent 和所有 origin attachment。

验收：

```text
废弃马车、断轮、血迹可共享同一个 accident_site origin。
origin_event_ids 引用不存在 OriginEvent 会被拒绝。
OriginEvent.evidence_entity_ids 与证据实体反向引用不一致会被拒绝。
```

## 回归测试要求

必须覆盖：

```text
test_world_runtime_initialization_requires_committed_spatial_foundation
test_world_runtime_initialization_requires_completed_origin_attachment_stage
test_world_runtime_initialization_creates_time_and_runtime_index_atomically
test_world_runtime_initialization_rejects_second_initialization_for_world
test_world_runtime_initialization_derives_minute_band_and_label
test_initial_runtime_active_dynamic_ids_are_empty
test_initial_runtime_version_lock_matches_world_and_manifest
test_initial_runtime_latest_event_sequence_matches_time_initialized
test_time_initialized_occurred_at_matches_initial_time_and_world_time_state
test_weather_formation_rejects_missing_world_time_state
test_initial_weather_interval_covers_initial_absolute_minute
test_world_time_rejects_invalid_minute_of_day
test_world_time_rejects_light_or_temperature_fields
test_environment_state_light_and_temperature_are_location_scoped
test_environment_state_location_reference_must_exist
test_game_time_interval_rejects_legacy_valid_for_fields
test_game_time_interval_uses_half_open_interval
test_absolute_minute_matches_minute_of_day
test_weather_base_region_unique_per_region_minute
test_weather_base_region_intervals_are_continuous
test_weather_previous_segment_must_touch_current_start
test_weather_local_override_must_fit_parent_interval
test_weather_local_override_priority_overlap_is_rejected
test_weather_boundary_at_end_minute_advances_to_next_segment
test_environment_state_valid_for_range_is_valid
test_environment_residual_source_mapping_is_valid
test_environment_residual_overlap_is_rejected
test_environment_state_wet_after_rain_requires_residual_effect
test_environment_residual_expiry_triggers_environment_rederive
test_hazard_location_must_exist
test_hazard_rejects_unknown_source_kind
test_hazard_rejects_invalid_source_kind_type_mapping
test_hazard_accepts_valid_source_kind_type_mapping
test_obstacle_rejects_unknown_source_kind
test_obstacle_rejects_invalid_source_kind_type_mapping
test_obstacle_accepts_valid_source_kind_type_mapping
test_hazard_rejects_unknown_generated_by_rule_id
test_obstacle_rejects_unknown_generated_by_rule_id
test_hazard_rejects_empty_source_entity_ids
test_obstacle_rejects_empty_source_entity_ids
test_generated_by_system_must_be_allowed_producer
test_generation_rule_output_must_match_source_kind_and_type
test_generation_rule_must_have_single_primary_output_type
test_obstacle_override_target_edge_must_exist
test_passability_override_state_must_be_known
test_passability_reducer_is_only_effective_writer
test_passability_reducer_blocks_over_conditional_difficult_open
test_passability_reducer_restores_from_base_when_override_removed
test_deriver_cannot_read_effective_passability_for_source_generation
test_route_resolver_reads_effective_passability_only
test_state_transition_requires_registered_event_type_and_change_ops
test_state_transition_create_value_must_be_complete_entity
test_state_transition_rejects_expected_sequence_mismatch
test_state_transition_rejects_entity_revision_mismatch
test_state_transition_commit_is_atomic_with_event_log_append
test_state_transition_idempotency_key_returns_existing_result
test_state_transition_batch_assigns_contiguous_event_sequences
test_state_transition_batch_requires_chained_expected_sequence
test_state_transition_batch_chains_previous_hashes
test_state_transition_batch_rolls_back_on_any_invalid_transition
test_generation_materialize_lowers_to_create_change
test_generation_derive_lowers_to_update_change_or_candidate_audit
test_delete_for_migration_requires_migration_payload
test_delete_for_migration_rejects_non_migration_producer
test_world_state_content_hash_excludes_event_log_and_snapshot
test_event_hash_chains_previous_event_hash
test_event_replay_hash_matches_resulting_state_hash
test_event_replay_from_zero_restores_target_hash
test_event_log_entry_must_reference_state_transition
test_only_state_transition_committer_can_create_event_log_entry
test_event_log_sequence_is_monotonic
test_event_log_absolute_minute_matches_minute_of_day
test_event_change_create_allows_missing_entity_before_apply
test_event_change_update_requires_existing_entity
test_world_snapshot_sequence_matches_runtime_state
test_snapshot_hash_can_be_recomputed
test_snapshot_latest_event_hash_matches_boundary_event
test_snapshot_writer_updates_recovery_index_atomically
test_snapshot_restore_replays_from_sequence_plus_one
test_snapshot_restore_hash_matches_full_event_replay_hash
test_origin_metadata_origin_event_ids_are_validated
test_origin_event_evidence_references_are_bidirectional
```

## 架构决策

1. 静态世界仍然需要全局时间状态，但光照、温度、天气引用和地表效果必须按空间位置进入 `EnvironmentState`。
2. `HazardSource` 和 `ObstacleSource` 不替代 `WorldObject`；具体可交互物仍必须是 WorldObject。
3. `ObstacleSource` 不替代 Edge 的通行结论；它只能提供 `passability_override`，最终 `effective_passability / effective_traversal` 由 `PassabilityReducer` 写入，移动 resolver 只读 effective 字段。
4. `source_kind` 是有限闭集，内容包和 LLM proposal 不允许临时新增危险或障碍来源。
5. `source_kind + hazard_type / obstacle_type` 必须符合映射表，不能只因为叙事合理就绕过 validator。
6. HazardSource / ObstacleSource 的生成入口是有限 producer 集合，必须通过 `generated_by.system` 和 `generated_by.rule_id` 追溯。
7. 每条产生规则只能输出一个 primary hazard_type 或 obstacle_type，避免实现时出现模糊分支。
8. StateTransition 是所有权威状态变化的唯一提交包络；EventLog 是该提交产生的状态账本，不是 DM 叙事。
9. Snapshot 是调试和恢复边界，不是玩家可见剧情。
10. 历史来历使用轻量 `OriginEvent / OriginMetadata`，不做完整历史模拟。
11. `WorldRuntimeInitialization` 是初始天气的强制前置阶段，并原子创建 StaticWorldRuntimeState 与 WorldTimeState。
12. `minute_of_day`、`time_band` 和 `calendar_label` 是初始化派生字段，不能由内容包、LLM 或调用方直接指定最终值。
