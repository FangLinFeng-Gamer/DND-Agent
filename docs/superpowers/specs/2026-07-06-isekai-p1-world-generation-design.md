# Isekai P1 World Generation Design

## Goal

Improve isekai mode from a stable survival loop into a replayable exploration prototype. P1 adds:

- randomized opening scene generation;
- richer known world events;
- persistent event impacts that affect future DM context.

P1 deliberately avoids a full hidden world simulator. The goal is to make each new adventure and each world-event card feel less repetitive while keeping backend truth deterministic.

## Scope

### Random Opening Generation

Creating an `isekai_survival` adventure should no longer always start at `雾林边境`.

Creation flow:

1. Generate the random character as before.
2. If an active model is configured, ask it for a structured opening payload.
3. Validate and normalize the model payload.
4. If the model is unavailable or invalid, use a deterministic backend template chosen from a small opening pool.
5. Persist the resulting scene, survival weather/location, confirmed location, and opening DM message.

The model may generate:

- `location`
- `environment`
- `important_objects`
- `current_objective`
- `weather`
- `opening_narration`

The model cannot set HP, inventory, gold, hunger, thirst, fatigue, or other core resources.

### Event Content Pool

The event director should stop using the generic title `附近环境出现变化` for random events.

P1 introduces an event seed catalog with several categories:

- local wilderness signs;
- road and camp activity;
- settlement rumors;
- resource pressure;
- NPC attitude or security changes;
- preference-related food/trade hooks.

Each seed defines:

- title template;
- description template;
- scope;
- allowed knowledge channels;
- impact payload.

### Event Impacts

Known events should have lightweight mechanical memory. When the director persists an event, it also stores an impact summary under `world_state.event_impacts`.

Example:

```json
{
  "event_impacts": [
    {
      "title": "猎径旁发现新鲜爪痕",
      "scope": "local",
      "affected_area": "雾林边境",
      "tags": ["danger", "wildlife"],
      "dm_context": "附近野兽活动增强，夜间旅行更危险。"
    }
  ]
}
```

`event_impacts` is included in the isekai model payload through existing `world_state`, so future DM replies can respect these facts.

## Non-Goals

- No hidden global simulation.
- No country-scale war model.
- No economy simulation.
- No frontend redesign.
- No LLM-controlled core resource changes.
- No database migration; impacts live in `world_state_json`.

## Error Handling

- Invalid opening model JSON falls back to backend templates.
- Invalid event seed data is skipped.
- Event impact persistence failure should not block DM narration.
- If no knowledge channel is available, the event is not shown and no impact is stored.

## Testing

Backend tests:

- Model-generated opening scene is persisted and replaces fixed `雾林边境`.
- Invalid opening model output falls back to a valid template.
- Random world events use specific event catalog titles instead of the old generic title.
- Event metadata includes an `impact` payload.
- `world_state.event_impacts` is updated after known events.
- Isekai model payload includes persisted event impacts.

Regression tests:

- Existing P0 survival loop still passes.
- DND mode behavior is unchanged.
