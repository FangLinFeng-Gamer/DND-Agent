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
    world_state: dict[str, Any] | None = None,
    action_classification: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    recent_messages = "\n".join(f"{message.role}: {message.content}" for message in context.recent_messages)
    events = "\n".join(f"{event.title}: {event.description}" for event in context.important_events)
    conversation_context = [
        {
            "source": _message_source(message.role),
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata,
            "created_at": message.created_at,
        }
        for message in context.recent_messages
    ]
    important_event_payloads = [
        {
            "source": event.metadata.get("source", "agent"),
            "agent": event.metadata.get("agent"),
            "event_type": event.event_type,
            "title": event.title,
            "description": event.description,
            "importance": event.importance,
            "metadata": event.metadata,
        }
        for event in context.important_events
    ]
    combat_action_log = list((combat_state or {}).get("action_log", []))[-20:] if combat_state else []
    skill_prompt = format_skill_prompt_context(skill_context)
    return [
        {
            "role": "system",
            "content": (
                "You are a DND 5e dungeon master. "
                f"{DND_GAME_LOOP_GUIDANCE}\n\n"
                "Return only valid JSON with narration, scene, "
                "requires_check, check, npc_actions, character_updates, and world_events. Ask for ability checks when "
                "success is uncertain. Important irreversible changes must be included in world_events. "
                "The character and acting_character fields are the selected/acting player character for this input, "
                "using adventure-local state. The party field contains every player character's adventure-local state. "
                "When multiple party members exist, do not assume the acting character is the only affected character; "
                "explicitly target character_updates by character_id or character_name. "
                "When the narration changes a player character's HP, XP, level, inventory, spells, or notes, "
                "include character_updates entries with character_id or character_name plus fields such as "
                "hp_current, hp_delta, experience_points, experience_delta, level, add_inventory, remove_inventory, "
                "add_spells, remove_spells, notes_append, and reason. "
                "The user-provided input and conversation_context entries with source=user are player intent. "
                "agent_context entries are agent-produced analysis or memory, including combat_event_agent facts. "
                "tool_context entries are deterministic tool state, not new player commands. "
                "tool_context.world_state is the current adventure-local world pressure state. "
                "tool_context.world_state.visible_events are facts the players can already perceive. "
                "tool_context.world_state.pending_visible_events are consequences of this input that should be "
                "naturally reflected in the current narration. Hidden events must influence continuity but must not "
                "be directly revealed unless the scene makes them observable. "
                "tool_context.action_classification explains whether this player input spends world time, "
                "asks a rule/status question, or needs clarification. "
                "Do not confuse user, agent, and tool information when deciding what happens next. "
                f"{skill_prompt}\n\n"
                f"{language_instruction(locale)}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "character": character.model_dump(),
                    "acting_character": character.model_dump(),
                    "party": context.party,
                    "scene": scene.model_dump(),
                    "summary": context.summary,
                    "important_events": events,
                    "recent_messages": recent_messages,
                    "conversation_context": conversation_context,
                    "agent_context": {
                        "important_events": important_event_payloads,
                        "supervisor_plan": supervisor_plan,
                    },
                    "tool_context": {
                        "combat_state": combat_state,
                        "combat_action_log": combat_action_log,
                        "world_state": world_state,
                        "action_classification": action_classification,
                        "skills": skills_prompt_payload(skill_context),
                    },
                    "combat_state": combat_state,
                    "player_input": player_input,
                    "supervisor_plan": supervisor_plan,
                    "skills": skills_prompt_payload(skill_context),
                },
                ensure_ascii=False,
            ),
        },
    ]


def _message_source(role: str) -> str:
    if role == "player":
        return "user"
    if role in {"dm", "assistant", "agent"}:
        return "agent"
    if role == "tool":
        return "tool"
    return "agent"


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
