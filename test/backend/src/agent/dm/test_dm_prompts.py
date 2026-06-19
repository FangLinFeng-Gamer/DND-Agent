import json

from backend.src.agent.dm.prompts import DND_GAME_LOOP_GUIDANCE, build_dm_messages
from backend.src.schemas.adventure import MessageOut, SceneState
from backend.src.schemas.character import CharacterOut
from backend.src.schemas.world_event import WorldEventOut
from backend.src.services.context import ContextBundle


def test_dm_prompt_includes_core_dnd_game_loop_guidance():
    guidance = DND_GAME_LOOP_GUIDANCE.lower()

    assert "describe the environment" in guidance
    assert "players describe what they do" in guidance
    assert "dm describes the results" in guidance
    assert "return to a new choice point" in guidance
    assert "simple actions can simply happen" in guidance
    assert "uncertain or challenging actions require dice" in guidance
    assert "do not require strict turns outside combat" in guidance
    assert "combat uses turn order" in guidance


def test_dm_system_prompt_uses_core_dnd_game_loop_guidance():
    context = ContextBundle(
        summary="",
        recent_messages=[
            MessageOut(
                id=1,
                adventure_id=1,
                role="player",
                content="I inspect the door.",
                metadata={},
                created_at="2026-05-23 00:00:00",
            )
        ],
        important_events=[],
        estimated_tokens=1,
    )
    scene = SceneState(
        location="Gate",
        environment="A wet stone gate.",
        important_objects=["door"],
        npcs=[],
        current_objective="Enter safely.",
        world_changes=[],
    )
    character = CharacterOut(
        id=1,
        name="Mira",
        race="Human",
        class_name="Fighter",
        level=1,
        background="Soldier",
        alignment="Neutral",
        hp_current=10,
        hp_max=10,
        armor_class=12,
        strength=14,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        skills={},
        inventory=[],
        spells=[],
        notes="",
    )

    messages = build_dm_messages(context, scene, character, "I inspect the door.", None)

    assert DND_GAME_LOOP_GUIDANCE in messages[0]["content"]


def test_dm_prompt_separates_user_agent_and_tool_context():
    context = ContextBundle(
        summary="",
        recent_messages=[
            MessageOut(
                id=1,
                adventure_id=1,
                role="player",
                content="I strike the goblin.",
                metadata={},
                created_at="2026-05-23 00:00:00",
            ),
            MessageOut(
                id=2,
                adventure_id=1,
                role="dm",
                content="The goblin staggers.",
                metadata={},
                created_at="2026-05-23 00:00:01",
            ),
        ],
        important_events=[
            WorldEventOut(
                id=1,
                adventure_id=1,
                event_type="combat",
                title="Goblin defeated",
                description="The goblin dropped to 0 HP.",
                importance=3,
                metadata={"source": "combat_event_agent", "agent": "combat_event_agent"},
                created_at="2026-05-23 00:00:02",
            )
        ],
        estimated_tokens=1,
    )
    scene = SceneState(
        location="Gate",
        environment="A wet stone gate.",
        important_objects=["door"],
        npcs=[],
        current_objective="Enter safely.",
        world_changes=[],
    )
    character = CharacterOut(
        id=1,
        name="Mira",
        race="Human",
        class_name="Fighter",
        level=1,
        background="Soldier",
        alignment="Neutral",
        hp_current=10,
        hp_max=10,
        armor_class=12,
        strength=14,
        dexterity=10,
        constitution=10,
        intelligence=10,
        wisdom=10,
        charisma=10,
        skills={},
        inventory=[],
        spells=[],
        notes="",
    )
    combat_state = {
        "is_active": True,
        "round_number": 2,
        "turn_index": 0,
        "participants": [],
        "action_log": [
            {
                "id": 1,
                "round_number": 1,
                "actor_name": "Mira",
                "source": "player",
                "action_type": "attack",
                "target_name": "Goblin",
                "damage": 4,
            }
        ],
    }

    messages = build_dm_messages(context, scene, character, "I look at the fallen goblin.", combat_state)
    payload = json.loads(messages[1]["content"])

    assert "user-provided input" in messages[0]["content"]
    assert payload["conversation_context"][0]["source"] == "user"
    assert payload["conversation_context"][1]["source"] == "agent"
    assert payload["agent_context"]["important_events"][0]["source"] == "combat_event_agent"
    assert payload["agent_context"]["important_events"][0]["agent"] == "combat_event_agent"
    assert payload["tool_context"]["combat_state"]["round_number"] == 2
    assert payload["tool_context"]["combat_action_log"][0]["actor_name"] == "Mira"
