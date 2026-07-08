# Isekai Action Parser Design

## Goal

Upgrade isekai survival input handling from keyword classification to scene-aware action parsing while keeping deterministic backend settlement authoritative.

## Boundaries

- `IsekaiActionParser` parses player text, binds scene targets, detects ambiguity, and returns a structured action.
- `IsekaiTimeService` receives a parsed `action_type` and only resolves time and survival deltas.
- LLM output can propose narration and state changes, but backend gates those changes by parsed action compatibility.
- `pending_intent` is metadata only. It never triggers inventory, NPC, pressure, or time settlement in the same turn.

## Parsed Action Shape

```json
{
  "action_type": "gather",
  "target_id": "red_berries_01",
  "target_name": "红浆果",
  "arguments": {},
  "time_cost_minutes": 30,
  "advances_time": true,
  "survival_intent": "gather",
  "reason": "角色采集或拾取附近物品。",
  "confidence": "high",
  "confidence_reasons": ["exact_target_name", "affordance_match:gather"],
  "matched_rules": ["intent:gather", "target:red_berries_01"],
  "requires_clarification": false,
  "candidates": [],
  "pending_intent": ""
}
```

Confidence is categorical: `high`, `medium`, or `low`. Reasons must be readable and explain why the parser made its decision.

## Clarification

If a player references multiple plausible scene targets, the parser returns `action_type: "clarification"`, `requires_clarification: true`, and a `candidates` list. Clarification turns do not advance time and cannot apply model state changes.

## Compound Actions

For input such as "先观察红浆果，如果没毒就采一点", the parser resolves the immediate action as `observe` and records `pending_intent: "gather_if_safe"`. The pending intent may appear in metadata or suggested follow-up actions, but it does not add items or trigger a second time cost.

## State Change Gate

State changes are accepted only when compatible with the parsed action:

- `table_talk`, `status_check`, `clarification`: no inventory, NPC, pressure, or scene state changes.
- `observe`: no inventory changes.
- `gather`, `forage`, `cook`, `eat_drink`: may add or remove compatible item resources.
- `manage_inventory`: may remove or reorganize existing inventory.
- `short_dialogue`: may apply NPC updates.
- `sleep`, `travel`, `search`, `seek_shelter`, `rest_short`: may apply scene or pressure changes, but item changes require explicit compatible action evidence.

## Acceptance Tests

- "我不是要睡觉，我只是找个能睡的地方" parses as `seek_shelter`, not `sleep`.
- "先观察红浆果，如果没毒就采一点" parses as `observe` with `pending_intent: "gather_if_safe"` and does not add berries.
- "摘点红浆果" binds to `red_berries_01` when that interactable exists.
- Ambiguous "摘浆果" with multiple berry interactables requires clarification and does not advance time.
- Non-advancing actions cannot apply model inventory, NPC, pressure, or scene changes.
- `observe` cannot apply `add_items`; `gather` can apply compatible `add_items`; `short_dialogue` can apply `npc_updates`.
