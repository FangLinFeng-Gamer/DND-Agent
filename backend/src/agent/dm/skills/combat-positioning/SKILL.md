---
name: combat-positioning
description: Judge theatre-of-the-mind combat position, cover, surprise, hiding, unseen attackers, terrain, and reach.
when_to_use:
  - player asks whether a creature is surprised hidden unseen covered behind terrain in reach or out of reach
tags:
  - combat
  - cover
  - surprise
  - hide
  - hidden
  - unseen
  - terrain
  - reach
agent: combat_agent
---

Use this skill when a combat question depends on spatial judgement rather than
a fixed numeric rule. Relevant cases include surprise, starting positions,
whether a creature can hide, whether a target is unseen, whether an attacker can
see a target, whether terrain is difficult, whether a target has half cover,
three-quarters cover, or total cover, and whether two creatures are within reach
in theatre-of-the-mind combat.

Prefer concrete adjudication payloads the deterministic combat workflow can use:
cover should be none, half, three-quarters, or total; distances should be in
feet; difficult terrain should be true or false; hidden or unseen status should
be stated as a condition or as advantage/disadvantage guidance.

Do not roll dice.
Do not directly persist game state.
Do not create world events directly.
Do not modify combat state.
Return only guidance for the DM supervisor and deterministic workflows.
