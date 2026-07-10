# Isekai P0 Playability Fix Design

## Goal

Turn the isekai survival mode from a chat prototype with meters into a playable survival loop:

player intent -> deterministic resource change -> escalating risk -> visible consequence -> next meaningful choice.

This P0 focuses only on the three highest-impact playability problems plus deletion cleanup:

- resource consumption, HP loss, and status effects;
- conservative non-action input handling;
- scene fact locking;
- isekai data cleanup when an adventure is deleted.

World-event content variety and random opening generation are important, but they are P1. Adding more content before the survival loop is trustworthy would hide the core problem instead of fixing it.

## Current Root Causes

`IsekaiTimeService` only updates survival pressure. It does not know or mutate character resources, so eating and drinking reduce hunger/thirst without consuming `干粮` or `水囊`, and severe hunger/thirst/fatigue never damages HP or adds status effects.

`IsekaiTimeService.classify_action()` defaults unknown text to `short_dialogue`, which advances 10 minutes. This means unclear player input and table questions can punish the player.

`IsekaiSurvivalService.apply_scene_progression()` trusts model `scene_update` and falls back to hard-coded input/narration location guesses. It records location history, but it does not strictly protect already-confirmed location facts from contradictory narration.

`AdventureService.delete()` removes shared DND-related rows but leaves `isekai_characters`, `isekai_survival_states`, and `world_events`.

## Design

### 1. Resource And Consequence Closure

Add a focused isekai resource rule layer that runs after time/survival pressure is calculated and before the DM response is persisted.

Responsibilities:

- consume one `干粮` when the action is `eat_drink` and the player mentions eating or food;
- consume one water charge when the action is `eat_drink` and the player mentions drinking or water;
- represent the initial water supply as `水囊(3/3)` so charges can be shown and reduced;
- update `isekai_characters.inventory_json`, `hp_current`, and `status_effects_json`;
- write structured consequences into DM metadata:
  - `hp_delta`
  - `inventory_changes`
  - `status_effects_added`
  - `status_effects_removed`

Penalty thresholds:

- hunger >= 90: add `饥饿虚弱`, HP -1;
- thirst >= 90: add `脱水`, HP -2;
- fatigue >= 90 or sleep_need >= 90: add `极度疲劳`, HP -1.

Status effects are removed when pressure drops below safer bands:

- hunger < 70 removes `饥饿虚弱`;
- thirst < 70 removes `脱水`;
- fatigue < 70 and sleep_need < 70 removes `极度疲劳`.

HP never drops below 0. P0 does not implement death flow UI; if HP reaches 0, it persists as character truth and the DM prompt receives it as backend state.

### 2. Conservative Action Classification

Classification should protect player trust. Only explicit in-world actions advance time.

Non-advancing inputs include:

- short clarification: `什么？`, `什么意思`, `?`, `？`;
- inventory and resource queries: `我有多少钱`, `背包里有什么`, `我还有多少干粮`, `水囊还有多少`;
- location/status queries: `我在哪`, `现在在哪`, `现在几点`, `状态怎么样`;
- UI/rule/system questions.

Unknown text defaults to `table_talk` with `advances_time=False`. This is deliberately conservative. The cost of missing an ambiguous action is lower than punishing a player for asking a question.

### 3. Scene Fact Locking

The backend treats `current_scene.location` and `world_state.confirmed_location` as authoritative facts.

Rules:

- On adventure creation, initialize `confirmed_location` from the opening scene.
- When a time-advancing movement changes location, persist the new location into both scene and `world_state.confirmed_location`.
- Non-time-advancing inputs cannot change location even if the model emits `scene_update.location`.
- If model narration contradicts a confirmed location with phrases like `并未抵达`, `没有抵达`, or `仍在雾林边境`, the backend replaces the narration with a factual correction that keeps the current location.

P0 keeps the existing destination inference but narrows its effect: it can only run for time-advancing actions, and confirmed scene facts override contradictory model text.

### 4. Delete Cleanup

Deleting an adventure must delete:

- `messages`
- `combat_states`
- `adventure_characters`
- `map_combat_tokens`
- `isekai_characters`
- `isekai_survival_states`
- `world_events`
- the `adventures` row

This applies to all adventures. DND world events should also be removed with their adventure.

## Non-Goals

- No random opening generation in this P0.
- No expanded world-event content pool in this P0.
- No full death UI or resurrection logic.
- No precise item database.
- No LLM action classifier yet. Deterministic conservative classification comes first.

## Testing

Backend service tests:

- eating/drinking consumes inventory and records changes;
- severe hunger/thirst damages HP and adds status effects;
- recovered pressure removes status effects;
- `什么？` and `我有多少钱` do not advance time or pressure;
- confirmed location survives contradictory model narration;
- non-action scene updates cannot move the character.

API tests:

- deleting an isekai adventure removes isekai character, survival state, and world events.

Regression tests:

- existing isekai time, event, model, and frontend tests continue to pass.
