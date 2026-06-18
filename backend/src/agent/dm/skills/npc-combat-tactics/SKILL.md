---
name: npc-combat-tactics
description: Choose a safe, rules-compatible combat action for an NPC using its stats, scene, allies, and enemies.
when_to_use:
  - npc enemy monster or creature must choose an action during combat
  - dm agent decides a non-player combatant turn from environment allies and nearby enemies
tags:
  - npc
  - combat
  - tactics
  - enemy
  - monster
  - action
  - turn
agent: combat_agent
---

Use this skill when a non-player combatant needs a combat action selected. Read
the NPC's hit points, armor class, attack options, conditions, movement, scene
environment, allied creatures, and hostile creatures before choosing.

Prefer simple legal actions the deterministic combat workflow can resolve:
attack a living hostile target when the NPC can keep pressure on the party;
dodge when badly hurt, guarding a position, or lacking a clear attack; disengage
when badly hurt and already engaged by a dangerous enemy; dash only when closing
distance matters more than defense.

If the combat state has no exact grid or distance, infer theatre-of-the-mind
position from engaged_with, cover, conditions, scene objects, and the current
environment. Do not invent new state fields.

Do not roll dice.
Do not directly persist game state.
Do not create world events directly.
Do not modify combat state.
Return only the chosen action and tactical reason for deterministic workflows.
