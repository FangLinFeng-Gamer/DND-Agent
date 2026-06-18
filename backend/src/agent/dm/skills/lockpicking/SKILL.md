---
name: lockpicking
description: Handle lock picking, traps, and suspicious mechanisms.
when_to_use:
  - player tries to open, inspect, pick, force, bypass, or disarm a lock or trap
tags:
  - exploration
  - lock
  - locked
  - pick
  - trap
  - disarm
  - thieves-tools
agent: exploration_agent
---

Use this skill when a player interacts with a lock, trapped container, sealed gate,
or suspicious mechanism.

The DM should first clarify what the character is doing: inspecting, picking,
forcing, bypassing, or disarming. Simple visible details can be described without
a roll. Uncertain or risky attempts may call for a Dexterity check using thieves'
tools, an Intelligence investigation-style check to understand the mechanism, or
a Strength check when the character forces the object.

Consider consequences before narration: noise, broken tools, jammed locks,
triggered traps, lost time, guards alerted, or partial progress. Reward relevant
proficiencies and good preparation in the structured check request.

Do not roll dice.
Do not directly persist game state.
Do not create world events directly.
Do not modify combat state.
Return only guidance for the DM supervisor and deterministic workflows.
