from backend.src.agent.dm.prompts import DND_GAME_LOOP_GUIDANCE, build_dm_messages
from backend.src.schemas.adventure import MessageOut, SceneState
from backend.src.schemas.character import CharacterOut
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
