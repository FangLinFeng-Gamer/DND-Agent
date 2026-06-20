# Isekai World Events Design

## Goal

The isekai survival mode needs a real world-event system. The current world events panel incorrectly displays recent DM narration. It should instead show adventure-local world events that the player character has actually learned through an in-world channel.

This feature is scoped to `isekai_survival`. Existing DND world-state and world-event behavior stays unchanged unless shared storage helpers can be reused without changing DND behavior.

## Core Rules

1. The UI only shows known events.
   The character can only see an event after the system determines a plausible knowledge channel exists.

2. World events are adventure-local.
   Events, learned events, and learned player preferences belong to one adventure. They must not leak into other adventures.

3. Event scale controls probability.
   Larger events affect more NPCs and locations, but are rarer. Local events are common. World-shaping events are very rare.

4. Player actions can create special events.
   Some events are consequences of what the player did. These are not random background events.

5. Player preference changes event attention, not world truth.
   If the player is clearly pursuing cooking, trade, or running a restaurant, related events become more likely to be learned or generated nearby. The whole world should not become only cooking-related.

## Event Model

World events should be persisted using the existing `world_events` table through `WorldEventService`. New isekai-specific semantics live in `metadata`.

Required event metadata:

- `mode`: `isekai_survival`
- `scope`: `local`, `settlement`, `regional`, `national`, or `global`
- `source`: `random_world`, `player_triggered`, or `preference_weighted`
- `knowledge_channel`: `direct_observation`, `npc_rumor`, `merchant_news`, `notice_board`, `tavern_gossip`, `magic_message`, `dream_omen`, or `environment_sign`
- `known_to_character`: boolean
- `location`: current or affected location name
- `affected_area`: short human-readable area label
- `preference_tags`: list of matching preference tags
- `triggering_action`: player text when source is `player_triggered`

`importance` maps to scale:

- 1: local color or minor nearby change
- 2: local actionable change
- 3: settlement or route-level event
- 4: regional or national event
- 5: global, world-shaping, or campaign-defining event

## Generation Probability

The event director runs only after effective in-world actions, not after every table question or UI/status question. The initial implementation should run after each isekai `advance` turn that changes survival pressure or location context, then internally decide whether an event is produced.

Base probabilities:

- `local`: common
- `settlement`: occasional
- `regional`: uncommon
- `national`: rare
- `global`: very rare

Environment modifies both probability and knowledge channels:

- Wilderness or empty ruins: high chance for local environmental events, very low chance for regional/global news.
- Road, campsite, border crossing: medium chance for merchant or traveler news.
- Village, town, market, tavern: high chance for settlement and regional news.
- Temple, mage tower, noble court: allows special channels like omen, magic message, or political news.

If no valid knowledge channel exists, the event is not shown in the panel. The director may skip creation, or create a hidden event only if future discovery is explicitly needed. For the first implementation, hidden background events can be skipped to keep scope controlled.

## Player-Triggered Events

Player-triggered events are generated when the player's action plausibly changes the world. Examples:

- Stealing from a merchant may create "merchant caravan increases guard patrols".
- Helping hunters may create "local hunters share food routes with the character".
- Cooking for a camp may create "travelers spread rumors about an unfamiliar dish".

These events should be marked with `source: player_triggered` and include `triggering_action`.

Player-triggered events can bypass random probability if the consequence is direct and visible. They still require a knowledge channel. If the player directly caused or witnessed the consequence, `knowledge_channel` should be `direct_observation`.

## Preference Learning

Every fixed number of effective in-world turns, the system asks the active LLM to summarize the current player preference for this adventure.

Default cadence:

- Learn every 5 effective isekai turns.
- Store results in `world_state.player_preferences`.
- Store `updated_turn`, `themes`, `playstyle`, `goals`, and `confidence`.

Example:

```json
{
  "player_preferences": {
    "themes": ["美食", "开餐厅", "贸易"],
    "playstyle": ["经营", "社交", "探索食材"],
    "goals": ["寻找食材", "建立餐厅"],
    "confidence": 0.72,
    "updated_turn": 10
  }
}
```

The preference learner must receive role-separated context:

- Player messages are user actions and stated goals.
- DM messages are agent narration.
- System state is backend truth.
- World events are tool/system records.

If no active model exists or the model fails, keep the previous preferences and continue gameplay.

## Event Director

Add an isekai event director service with three responsibilities:

1. Classify the current environment for available channels.
2. Generate or select event candidates with scale-aware probability.
3. Persist only known events for display.

The first implementation can use deterministic templates plus optional active-model enrichment. It should not require the model for basic operation.

The active model can be used to turn a selected event seed into natural Chinese event text. The output must be structured JSON, for example:

```json
{
  "title": "新香料商人抵达灰桥镇",
  "description": "你从一支经过营地的商队那里听说，灰桥镇来了一个出售异域香料的新商人，正在寻找懂得陌生菜式的人。",
  "scope": "settlement",
  "source": "preference_weighted",
  "knowledge_channel": "merchant_news",
  "affected_area": "灰桥镇",
  "preference_tags": ["美食", "贸易"]
}
```

Invalid or unparseable model output should be ignored or replaced with a deterministic fallback event.

## API And Data Flow

The existing adventure detail response should expose known isekai world events so the frontend does not need a second request.

Recommended response addition:

- Add `world_events: list[WorldEventOut]` to `AdventureOut`.
- Populate it with recent known events for the adventure.
- For `isekai_survival`, the frontend event panel reads `adventure.world_events`.
- For existing DND screens, no visible behavior changes are required.

Turn flow:

1. Player sends isekai message.
2. Survival state updates.
3. Preference learner runs if cadence is reached.
4. Event director evaluates the turn, environment, preferences, and player action.
5. Known events are persisted through `WorldEventService`.
6. DM narration is generated.
7. Final response returns adventure, messages, survival state, and known world events.

## Frontend Behavior

The isekai world events panel should render event cards from `adventure.world_events`, not from `adventure.messages`.

Each event card should show:

- Title
- Description
- Impact scope label
- Knowledge channel label
- Source label for player-triggered or preference-weighted events

Empty state:

- If no known events exist, show a quiet empty state such as "暂无已知世界事件".

The panel remains scrollable and must not expand indefinitely.

## Testing

Backend tests:

- Isekai adventure detail includes known world events and does not include unrelated adventure events.
- World event generation stores `known_to_character: true` events with scope and knowledge channel metadata.
- Empty wilderness strongly limits large-news channels.
- Player-triggered events include `source: player_triggered` and `triggering_action`.
- Preference learning stores adventure-local preferences and does not affect another adventure.
- LLM failure in preference learning or event text generation does not block the turn.

Frontend tests:

- Isekai events panel reads `adventure.world_events`, not messages.
- Event cards show scope and knowledge channel.
- Empty state appears when no known events exist.
- Long event descriptions wrap and the list scrolls.

## Non-Goals

- Do not build a full hidden global simulation yet.
- Do not change DND mode event progression.
- Do not expose events the character has no channel to know.
- Do not make every generated event match the player's preference.
