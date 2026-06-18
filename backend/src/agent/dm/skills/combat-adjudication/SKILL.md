---
name: combat-adjudication
description: Judge improvised combat actions, Ready triggers, Search choices, complex mounted or underwater situations, and NPC death exceptions.
when_to_use:
  - player describes an improvised combat action ready trigger search mounted combat underwater combat or special monster death outcome
tags:
  - combat
  - ready
  - search
  - improvised
  - mounted
  - underwater
  - knockout
  - death
agent: combat_agent
---

Use this skill when the player attempts a combat action that PHB Chapter 9
leaves to the DM or that the current deterministic combat workflow cannot fully
resolve from character and combat state alone. Relevant cases include improvised
actions, choosing whether Search uses Wisdom (Perception) or Intelligence
(Investigation), interpreting a Ready trigger, mounted-combat edge cases,
underwater-combat edge cases, complex spell effects without structured metadata,
and whether an important monster or NPC follows player-style death rules.

Translate the ruling into explicit guidance whenever possible: suggested ability
check, suggested DC, whether the effect should require deterministic attack,
saving throw, damage, movement, or state handling, and what consequence should
be narrated if the attempt succeeds or fails.

Do not roll dice.
Do not directly persist game state.
Do not create world events directly.
Do not modify combat state.
Return only guidance for the DM supervisor and deterministic workflows.
