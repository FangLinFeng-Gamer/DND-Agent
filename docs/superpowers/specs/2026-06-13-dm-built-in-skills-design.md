# DM Built-In Skills Design

## Goal

Add backend-only project skills for the DM agent, following the useful parts of Claude Code skills: a skill is a small directory with a `SKILL.md`, frontmatter describes when it applies, and the full guidance is loaded only when the current player action matches it. The feature must not give skills any direct state-writing, dice-rolling, or database access.

## Scope

This design covers only built-in project skills committed with the backend. It does not add a frontend editor, user-uploaded skills, runtime skill installation, marketplace support, or external skill execution.

## Safety Model

DM skills are read-only guidance. A skill may describe how to judge a player action, what DND rule concepts are relevant, what checks may be appropriate, and what outcomes should be considered. A skill must not define executable tools, call write-capable tools, persist scene state, create world events, modify combat state, or roll dice.

Strong-rule and safety-sensitive work remains in deterministic code:

- Ability checks and saving throws use `DeterministicWorkflows`.
- Combat resolution uses `combat_agent` and `CombatService`.
- Scene changes are represented as structured data and validated by existing schemas.
- Persistence continues to go through `commit_graph`.
- Narration can use skill guidance only after facts are resolved, and cannot change those facts.

The registry rejects skills that declare tool fields in frontmatter or contain direct state-writing instructions such as calling `commit_agent` or writing to the database. This is a guardrail, not the only safety layer; the runtime never exposes write tools to skills.

## Skill File Format

Built-in skills live under:

`backend/src/agent/dm/skills/<skill-name>/SKILL.md`

Each skill uses simple frontmatter:

```md
---
name: lockpicking
description: Handle lock picking, traps, and suspicious mechanisms.
when_to_use:
  - player tries to open, inspect, pick, force, bypass, or disarm a lock or trap
tags:
  - exploration
  - lock
  - trap
  - thieves-tools
agent: exploration_agent
---

Guidance text for the DM supervisor and subagents.
```

The first version supports scalar string fields and list fields. Unknown fields are ignored except forbidden tool-declaration fields, which fail loading.

## Matching

`DMSkillRegistry` loads built-in skills at service startup. For each player action, it scores skills using the player text against skill name, tags, description, and `when_to_use` text. The first version is deterministic keyword and phrase matching rather than model-based selection. This keeps behavior testable and avoids using a model to decide which instructions a model should see.

The registry returns a small ordered list of `DMSkill` objects. If no skill matches, the DM flow receives an empty list and behaves exactly as before.

## DM Flow Integration

The runtime flow becomes:

1. `DMService.advance` or `advance_stream` normalizes locale and loads the current adventure.
2. `DMSkillRegistry.match(player_input, locale)` returns relevant read-only skill contexts.
3. `DMGraphRunner` passes skill context into `DMSupervisor.plan`.
4. `DMSupervisor` includes matched skill names and guidance in the planning prompt, while still stating that skills are read-only and cannot roll dice or modify state.
5. `ReactSubAgentRegistry` includes the same read-only context in open subagent prompts.
6. `build_dm_messages` includes the matched skills in the JSON payload used by the resolution model.
7. `NarrationAgent` receives matched skills only as context for tone and rule-aware explanation, not as authority to alter resolved state.
8. Existing deterministic workflows and `commit_graph` remain the only state-changing route.

## Data Shape

The prompt payload exposes skills as:

```json
[
  {
    "name": "lockpicking",
    "description": "Handle lock picking, traps, and suspicious mechanisms.",
    "when_to_use": ["player tries to open, inspect, pick, force, bypass, or disarm a lock or trap"],
    "tags": ["exploration", "lock", "trap", "thieves-tools"],
    "agent": "exploration_agent",
    "guidance": "..."
  }
]
```

The payload is intentionally descriptive. It contains no callable function names, tool schemas, or permission grants.

## Initial Built-In Skill

The first built-in skill is `lockpicking`, because it exercises the important boundaries:

- It often requires a Dexterity check or thieves' tools proficiency.
- It may involve traps and failure consequences.
- It can suggest possible scene outcomes, but the actual check and scene write must remain deterministic and structured.

Future built-in skills can cover social negotiation, stealth exploration, travel, investigation, and combat tactics using the same read-only contract.

## Testing

Tests must prove:

- The built-in registry loads `SKILL.md` files.
- Lock/trap input matches `lockpicking`; unrelated input does not.
- A skill declaring write tools is rejected.
- `DMSupervisor` receives matched skill context without gaining direct commit tools.
- `build_dm_messages` includes skill context in the model payload.
- Synchronous and streaming DM model paths pass matched skills into the resolver prompt.
- Existing DM LangGraph architecture tests still pass.

## Non-Goals

- No frontend skill editor.
- No user-supplied skill files.
- No direct skill execution.
- No skill-specific write tools.
- No model-based skill selection in the first version.
