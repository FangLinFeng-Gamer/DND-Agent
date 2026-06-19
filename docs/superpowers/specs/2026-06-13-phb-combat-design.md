# PHB Chapter 9 Combat Design

Status: approved for theatre-of-the-mind positioning.

## Source Scope

Primary source is `docs/5eDnD_玩家手册PHB_中译v1.72版.pdf`, Chapter 9
Combat, PDF pages 189-200. Combat references from adjacent rules are used only
where Chapter 9 requires them:

- Chapter 5 equipment data for weapon damage, ranges, armor, and shields.
- Chapter 10/11 spell data for combat spell timing, attack/save shape, damage,
  healing, and ongoing effects when the project has structured spell metadata.
- Appendix A style conditions when Chapter 9 creates or depends on common
  conditions such as prone, grappled, unconscious, incapacitated, or restrained.

The implementation must not treat DM judgement text as deterministic code unless
the rule gives a clear mechanical outcome.

## Design Choice

Use theatre-of-the-mind abstract positioning, not a grid map.

Combat state tracks movement and tactical relations with compact fields such as
`speed_ft`, `movement_remaining_ft`, `reach_ft`, `engaged_with`, `cover`,
`conditions`, and optional `distance_ft` supplied by the current action. This is
enough for PHB turn order, action economy, movement cost, opportunity attacks,
reach checks, and cover modifiers without adding a tactical-map UI.

## Architecture

Keep the existing combat surface and deepen it:

- `backend/src/services/combat.py` remains the deterministic PHB rule service.
  It performs dice rolls, validates action economy, applies damage/healing, and
  mutates a copied combat state.
- `backend/src/agent/dm/workflows.py` keeps `combat_graph`, but the graph becomes
  an action router instead of a one-node attack wrapper.
- `backend/src/api/adventures.py` keeps combat endpoints and expands the action
  payload while preserving the current attack-only request shape.
- `backend/src/schemas/combat.py` defines action, participant, state, roll, and
  result schemas. Existing response fields stay compatible for basic attacks.
- `backend/src/agent/dm/skills/*/SKILL.md` contains read-only combat judgement
  skills for cases the rules explicitly leave to the DM.

No database migration is required for the first implementation. Persistent combat
state remains JSON in `combat_states.participants_json` plus the existing active,
round, and turn fields. Extra participant state is stored inside each participant.

## Combat State

Each participant should normalize to:

- Identity: `name`, `side`, `kind`.
- Core combat stats: `hp`, `hp_max`, `temp_hp`, `ac`, `initiative_bonus`,
  `initiative`, `speed_ft`, `reach_ft`.
- Attacks: `attack_bonus`, `damage`, `damage_type`, plus optional `attacks`
  copied from character creation derived data.
- Defenses: `resistances`, `vulnerabilities`, `immunities`.
- Action economy: `action_available`, `bonus_action_available`,
  `reaction_available`, `movement_remaining_ft`.
- Tactical flags: `conditions`, `cover`, `engaged_with`, `surprised`,
  `dodge_active`, `disengage_active`, `helping`.
- Death state: `defeated`, `stable`, `death_saves`.

Existing old states without these fields must be upgraded in memory during
normalization so old tests and saved combats keep working.

## Deterministic PHB Rules

The LangGraph combat workflow routes fixed actions through deterministic nodes:

- `start_combat`: normalize participants, roll initiative as `d20 +
  initiative_bonus`, sort descending, mark surprise if supplied by a DM
  adjudication result.
- `start_turn`: reset action, bonus action, movement, and reaction timing
  according to PHB round/turn rules; handle surprised first turns.
- `move`: spend movement, apply difficult terrain multiplier when supplied,
  update engagement, and trigger opportunity attack eligibility when leaving
  reach without Disengage.
- `attack`: choose target, apply cover AC bonus, apply advantage/disadvantage,
  handle natural 1/20, roll damage, double damage dice on a critical hit, and
  apply resistance/vulnerability/immunity.
- `dash`, `disengage`, `dodge`, `help`, `hide`, `ready`, `search`,
  `use_object`: consume the correct action slot and set the appropriate state or
  `requires_dm_adjudication` flag where the rule asks the DM to decide.
- `grapple` and `shove`: run opposed Strength (Athletics) against the target's
  Strength (Athletics) or Dexterity (Acrobatics), with the defender choice
  supplied by the request or DM judgement.
- `cast_spell`: consume the action/bonus/reaction slot from spell metadata. If a
  spell has structured attack, save, damage, healing, or AC metadata, resolve the
  deterministic part; otherwise return a DM-adjudication requirement with the
  spell description as context.
- `apply_damage` and `heal`: support temporary hit points, 0 HP, instant death,
  unconscious/stable state, death saving throw counters, and nonlethal melee
  knockouts.
- `advance_turn`: skip dead/defeated combatants, wrap rounds, clear turn-scoped
  effects, and end combat when only one side can still fight.

## DM Judgement Skills

Add read-only built-in skills for combat judgement. They must follow the current
DM skill safety rules: no tools, no direct writes, no dice rolls, no persistence.

`combat-positioning` handles:

- surprise and starting positions;
- whether a creature can hide;
- unseen attackers and unseen targets;
- cover grade: none, half, three-quarters, total;
- difficult terrain and environmental constraints;
- theatre-of-the-mind distance/reach decisions.

`combat-adjudication` handles:

- improvised actions not listed in PHB action options;
- Search action ability/DC choice;
- Ready trigger interpretation;
- complex mounted and underwater scenes;
- complex spell effects when project metadata is not structured enough;
- monster/NPC death exceptions where the PHB says the DM may decide.

The DM may use these skills to produce an adjudication payload, but the
deterministic combat graph still performs any resulting rolls or state changes.

## API Compatibility

`POST /api/adventures/{id}/combat/action` remains valid with the current payload:

```json
{"attacker_name": "Hero", "target_name": "Goblin"}
```

The new payload also supports:

```json
{
  "actor_name": "Hero",
  "action_type": "attack",
  "target_name": "Goblin",
  "attack_id": "equipment.battleaxe",
  "movement_ft": 10,
  "cover": "half",
  "mode": "normal",
  "nonlethal": false
}
```

If `action_type` is omitted, the request is treated as `attack` for backward
compatibility. If `actor_name` is omitted, `attacker_name` is used.

## Character Data Integration

Starting combat must prefer character creation derived combat data:

- AC and HP from the saved character.
- Initiative from Dexterity modifier and derived feat bonuses where available.
- Weapon attack list from derived inventory data.
- Damage type from equipment metadata.
- Spell attack/DC data from derived spellcasting where available.

The current hard-coded API fallback (`max(3, strength modifier)` and `1d8+2`)
is only kept as a last-resort fallback when older characters lack derived attack
data.

## Error Handling

Return structured API errors for:

- inactive combat;
- invalid turn actor;
- missing living actor or target;
- action slot already spent;
- movement beyond available movement;
- target protected by total cover for direct attacks/spells;
- unsupported spell/effect requiring DM adjudication;
- malformed dice expressions or invalid combat state.

The service should raise clear `ValueError` messages; API routes translate them
into existing `api_error` responses.

## Testing Plan

Add focused tests before implementation:

- Combat service tests for initiative bonus, turn reset, action economy, dash,
  disengage, dodge, help, cover, critical hits, natural 1, damage resistance,
  vulnerability, immunity, temporary HP, 0 HP, death saves, nonlethal knockout,
  grapple, shove, and opportunity attack eligibility.
- API tests for old attack payload compatibility and new action payloads.
- LangGraph workflow tests proving combat actions route through
  `DeterministicWorkflows.combat_graph`.
- DM skill tests proving combat judgement skills load, match combat prompts, and
  reject direct write/tool instructions.
- Regression tests confirming character-derived attack and initiative data are
  used when starting combat.

## Acceptance Criteria

- Basic combat still works through the existing API.
- PHB Chapter 9 fixed mechanics are deterministic and test-covered.
- DM judgement cases are represented as read-only skills and never directly
  mutate state.
- Theatre-of-the-mind positioning supports movement, reach, engagement,
  difficult terrain, cover, and opportunity attack decisions without a grid UI.
- Character combat stats come from PHB-derived character data where available.
