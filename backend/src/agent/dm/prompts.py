import json
from typing import Any

from backend.src.agent.locale import language_instruction
from backend.src.agent.dm.skill_registry import (
    DMSkill,
    format_skill_prompt_context,
    skills_prompt_payload,
)
from backend.src.schemas.adventure import SceneState
from backend.src.schemas.character import CharacterOut
from backend.src.schemas.story import StoryOut
from backend.src.schemas.world import WorldEntryOut
from backend.src.services.context import ContextBundle


DND_GAME_LOOP_GUIDANCE = """
Run the game through the core DND loop:
1. The DM must describe the environment: where the party is, what surrounds them,
   important exits, objects, creatures, NPCs, and clear action options.
2. The players describe what they do. Listen to every declared action. Simple actions can simply happen.
   Uncertain or challenging actions require dice,
   ability checks, saving throws, or combat rules as appropriate.
3. The DM describes the results. Explain consequences clearly, update the
   scene, then return to a new choice point so the players know what can be
   attempted next.

Do not require strict turns outside combat. Multiple characters may act in a
flexible order during exploration or social scenes. Combat uses turn order and
formal actions. Keep continuity, describe sensory details, portray NPCs through
their behavior and voice, and use maps or positions only when they clarify the
scene.
""".strip()


def build_dm_messages(
    context: ContextBundle,
    scene: SceneState,
    character: CharacterOut,
    player_input: str,
    combat_state: dict[str, Any] | None,
    supervisor_plan: dict[str, Any] | None = None,
    locale: str = "en",
    skill_context: list[DMSkill] | None = None,
) -> list[dict[str, str]]:
    recent_messages = "\n".join(f"{message.role}: {message.content}" for message in context.recent_messages)
    events = "\n".join(f"{event.title}: {event.description}" for event in context.important_events)
    skill_prompt = format_skill_prompt_context(skill_context)
    return [
        {
            "role": "system",
            "content": (
                "You are a DND 5e dungeon master. "
                f"{DND_GAME_LOOP_GUIDANCE}\n\n"
                "Return only valid JSON with narration, scene, "
                "requires_check, check, npc_actions, and world_events. Ask for ability checks when "
                "success is uncertain. Important irreversible changes must be included in world_events. "
                f"{skill_prompt}\n\n"
                f"{language_instruction(locale)}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "character": character.model_dump(),
                    "party": context.party,
                    "scene": scene.model_dump(),
                    "summary": context.summary,
                    "important_events": events,
                    "recent_messages": recent_messages,
                    "combat_state": combat_state,
                    "player_input": player_input,
                    "supervisor_plan": supervisor_plan,
                    "skills": skills_prompt_payload(skill_context),
                },
                ensure_ascii=False,
            ),
        },
    ]


def build_opening_scene_messages(
    character: CharacterOut,
    story: StoryOut | None,
    world_entries: list[WorldEntryOut],
    template_scene: SceneState,
    template_opening: str,
    locale: str = "en",
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a DND 5e dungeon master starting a new adventure. "
                f"{DND_GAME_LOOP_GUIDANCE}\n\n"
                "Create the opening DM narration and initial scene. Return only valid JSON "
                "with narration and scene. The scene object must include location, environment, "
                "important_objects, npcs, current_objective, and world_changes. End the narration "
                "at a clear choice point without resolving player actions. "
                f"{language_instruction(locale)}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "character": character.model_dump(),
                    "story": story.model_dump() if story else None,
                    "world_entries": [entry.model_dump() for entry in world_entries[:20]],
                    "template_scene": template_scene.model_dump(),
                    "template_opening": template_opening,
                },
                ensure_ascii=False,
            ),
        },
    ]


def build_narration_messages(
    facts: dict[str, Any],
    locale: str = "en",
    skill_context: list[DMSkill] | None = None,
) -> list[dict[str, str]]:
    payload = {**facts, "skills": skills_prompt_payload(skill_context)}
    skill_prompt = format_skill_prompt_context(skill_context)
    return [
        {
            "role": "system",
            "content": (
                "You are the narration agent for a DND game. Turn only the supplied, "
                "already-resolved facts into vivid DM narration. Do not change dice, "
                "damage, state, NPC actions, or world events. End at a clear choice point. "
                f"{skill_prompt}\n\n"
                f'{language_instruction(locale)} Return only JSON: {{"narration": "..."}}'
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def build_npc_combat_action_messages(
    npc_context: dict[str, Any],
    locale: str = "en",
    skill_context: list[DMSkill] | None = None,
) -> list[dict[str, str]]:
    skill_prompt = format_skill_prompt_context(skill_context)
    payload = {**npc_context, "skills": skills_prompt_payload(skill_context)}
    return [
        {
            "role": "system",
            "content": (
                "You choose one DND 5e combat action for the current NPC. "
                "Use the supplied NPC stats, scene environment, nearby enemies, "
                "nearby allies, map token positions, distances, and read-only DM skills. Do not roll dice, do not "
                "modify state, and do not narrate outcomes. The deterministic "
                "combat workflow will execute the chosen action. "
                "Return only valid JSON with action_type, target_name, attack_id, "
                "movement_ft, and reason. action_type must be one of attack, dodge, "
                "dash, or disengage. target_name is required for attack. "
                f"{skill_prompt}\n\n"
                f"{language_instruction(locale)}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
