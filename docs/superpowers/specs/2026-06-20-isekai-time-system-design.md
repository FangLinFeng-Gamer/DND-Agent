# Isekai Time System Design

## Goal

The isekai survival mode needs an adventure-local time system. Current survival values change directly from coarse action types, while `day` and `time_of_day` stay fixed. This makes the world feel static: the player can avoid urgent threats, ignore nightfall, or repeatedly ask unrelated questions without the world reacting.

This design adds a first version of time progression for `isekai_survival` only. DND mode remains unchanged.

## Current Behavior

Current survival state already stores:

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
- `state`

Only the numeric survival values are updated. The update is based on keyword action classification:

| Action type | Trigger examples | Hunger | Thirst | Fatigue | Sleep need |
| --- | --- | ---: | ---: | ---: | ---: |
| `rest` | `休息`, `睡`, `camp`, `rest` | +2 | +2 | -12 | -18 |
| `forage` | `吃`, `喝`, `食物`, `水`, `food`, `water` | +1 | +2 | +6 | +3 |
| `explore` | `探索`, `走`, `寻找`, `inspect`, `explore`, `move` | +3 | +4 | +8 | +4 |
| `talk` | anything else | +0 | +1 | +1 | +0 |

Problems:

- `day` and `time_of_day` do not change.
- Survival pressure is not tied to elapsed time.
- Asking a rules/status question can still be treated as a world action if keywords match.
- Eating/drinking and searching for supplies are mixed into the same `forage` action.
- Weather, shelter, and time of day do not affect survival.

## Core Rules

1. Time advances only for effective in-world actions.
   Status questions, rule questions, UI clarification, and pure table talk should not advance time.

2. Survival pressure is primarily time-based.
   Hunger, thirst, fatigue, and sleep need grow from elapsed minutes/hours, then action-specific modifiers are applied.

3. Action category and action duration are separate.
   Two actions can both be `explore`, but a quick look around may cost 10 minutes while a long forest search may cost 2 hours.

4. Rest, eating, and drinking are real actions with direct recovery effects.
   Searching for food is not the same as consuming food.

5. Time is adventure-local.
   Every isekai adventure keeps its own clock and survival state. One game cannot affect another game's date, time, or pressure.

6. The player should feel time passing.
   The UI and DM narration should expose day/time changes, nightfall, dawn, and survival consequences in plain language.

## Time Model

Use minutes since the start of the current day as the internal clock. The first implementation can store this in `survival.state.elapsed_minutes` without a database migration.

State fields:

- `day`: integer, starts at 1.
- `time_of_day`: localized label for display, derived from `elapsed_minutes`.
- `state.elapsed_minutes`: integer `0..1439`.
- `state.total_elapsed_minutes`: optional total campaign clock for future use.
- `state.last_time_delta_minutes`: minutes consumed by the last effective action.
- `state.last_time_reason`: short reason such as `quick_action`, `travel`, `rest`, or `table_talk`.

Initial value:

- Keep the existing opening label `黄昏`.
- Set `elapsed_minutes` to `17 * 60`, representing 17:00.

Day rollover:

- If `elapsed_minutes >= 1440`, subtract 1440 and increment `day`.
- Large rests can roll across midnight.

Time labels:

| Range | Label |
| --- | --- |
| 05:00-07:59 | 清晨 |
| 08:00-11:59 | 上午 |
| 12:00-13:59 | 正午 |
| 14:00-16:59 | 下午 |
| 17:00-18:59 | 黄昏 |
| 19:00-22:59 | 夜晚 |
| 23:00-04:59 | 深夜 |

## Action Classification

Introduce an isekai action classification result with at least:

```json
{
  "action_type": "explore",
  "time_cost_minutes": 60,
  "advances_time": true,
  "survival_intent": "travel",
  "reason": "角色进行了会消耗时间的探索行动。"
}
```

Recommended categories:

- `table_talk`: questions about UI/rules/system, no time cost.
- `status_check`: asking current state, inventory, location, no time cost.
- `short_dialogue`: brief conversation, 5-10 minutes.
- `social_scene`: longer negotiation, gathering rumors, 30-60 minutes.
- `observe`: quick look, listening, inspecting nearby details, 10-20 minutes.
- `search`: careful local search, 30-60 minutes.
- `travel`: moving to another nearby place, 60-180 minutes.
- `forage`: searching for food/water, 60-180 minutes.
- `eat_drink`: consuming carried or available supplies, 10-20 minutes.
- `cook`: preparing food, 30-90 minutes.
- `craft`: making, repairing, building, 60-240 minutes.
- `rest_short`: catching breath or short rest, 60 minutes.
- `sleep`: long rest or sleep, 360-480 minutes.

The first implementation can be deterministic keyword classification. It should be structured so an LLM classifier can replace or enrich it later.

## Survival Pressure

Apply survival pressure in two phases:

1. Time pressure based on elapsed minutes.
2. Action modifiers based on effort and outcome.

Recommended base rates per hour:

| Stat | Base change per hour |
| --- | ---: |
| Hunger | +1 |
| Thirst | +2 |
| Fatigue | +1 |
| Sleep need | +1 |

Action effort modifiers:

| Action | Extra effect |
| --- | --- |
| `observe` | small fatigue only |
| `search` | +2 fatigue |
| `travel` | +3 fatigue, +1 thirst |
| `forage` | +4 fatigue, +1 thirst |
| `cook` | +1 fatigue; may reduce hunger if food is available |
| `eat_drink` | reduce hunger/thirst if supplies exist |
| `rest_short` | reduce fatigue; sleep need remains mostly unchanged |
| `sleep` | strongly reduce fatigue and sleep need; hunger/thirst still rise over time |

Clamp all survival numbers to `0..100`.

The first implementation does not need a full inventory-consumption system. If inventory parsing is uncertain, eating/drinking can apply a modest recovery and record a visible event saying supplies were used abstractly. A later inventory system can make this exact.

## Environment Modifiers

Environment should affect pressure without requiring a full world simulation.

Inputs:

- `weather`
- `temperature_risk`
- `shelter`
- `time_of_day`
- current scene/environment text

Initial rules:

- Deep night actions increase fatigue and sleep need more quickly.
- High `temperature_risk` increases thirst pressure.
- Having shelter reduces rest/sleep penalties and improves recovery.
- Bad weather can increase fatigue for travel/search.

If no clear environment modifier applies, use base rates.

## World Events Integration

The existing isekai world event director should use the same action classification result:

- `advances_time: false` means no random world event generation.
- Time-consuming actions can generate local events.
- Night, dawn, market hours, and travel time can affect event probability and knowledge channels.

Examples:

- At night in wilderness: local environmental signs are more likely; merchant news is unlikely.
- In a town during morning/afternoon: rumors, notices, shops, and NPC schedules become available.
- Sleeping through the night may trigger events that happened while the character was unavailable, but only if the character later has a channel to learn them.

First implementation scope:

- Pass time classification into the event director.
- Use `advances_time` and `time_cost_minutes` as inputs.
- Do not build hidden off-screen simulation yet.

## DM Narration And Role Boundaries

The DM model must receive time state as backend truth:

- Current `day`
- Current `time_of_day`
- `elapsed_minutes`
- last action time cost
- survival delta
- whether the action advanced time

The prompt must continue to distinguish:

- User input: player intent.
- System state: backend truth, including time and survival state.
- Tool/rule results: action classification and survival/time deltas.
- Agent narration: not player intent.

The model can narrate time passing, but cannot change the clock or survival numbers.

## Frontend Behavior

The existing isekai room subtitle already shows day, `time_of_day`, and location. Keep that.

Improve the survival panel to include:

- Day
- Time of day
- Last action time cost
- Hunger
- Thirst
- Fatigue
- Sleep need
- Weather
- Shelter

The panel should not explain rules in long text. It should present compact state values.

When an action advances time, DM narration and/or visible events should mention meaningful changes:

- "太阳沉入林线，雾林进入夜晚。"
- "你花了约 2 小时搜寻水源。"
- "睡过深夜后，你在第 2 天清晨醒来。"

## Data And Migration

No database migration is required for the first version if `state_json` stores:

```json
{
  "elapsed_minutes": 1020,
  "total_elapsed_minutes": 1020,
  "last_time_delta_minutes": 60,
  "last_time_reason": "travel"
}
```

When loading older adventures with empty `state`, initialize:

- `elapsed_minutes` from `time_of_day` if possible.
- Existing `黄昏` maps to 17:00.
- If unknown, default to 17:00 to preserve current opening feel.

Persist `day` and `time_of_day` in the existing columns so API responses and UI stay simple.

## Testing

Backend tests:

- Status/table questions do not advance time or increase survival pressure.
- Exploration advances time and increases survival pressure based on elapsed minutes.
- Long sleep rolls the clock into the next day and reduces fatigue/sleep need.
- Eating/drinking is distinct from foraging.
- Time is adventure-local and does not affect another isekai adventure.
- World event director is not triggered for non-time-advancing table talk.
- Night actions produce the expected time label and stronger fatigue pressure.

Frontend tests:

- Isekai survival panel displays day and time of day.
- Last action time cost appears when available.
- Time text updates after a returned adventure payload.
- DND room UI is unchanged.

## Non-Goals

- Do not build a full calendar with months/seasons yet.
- Do not implement exact inventory nutrition accounting yet.
- Do not simulate all NPC schedules yet.
- Do not change DND world-state progression.
- Do not make every player message advance time.

## Open Implementation Choice

The first implementation should use deterministic classification and rules. A later version can add an LLM action classifier after tests establish the rule contract.
