from backend.src.agent.dm.schemas import AbilityCheckRequest, ScenePatch
from backend.src.agent.dm.workflows import DeterministicWorkflows
from backend.src.services.combat import CombatService


def test_ability_check_graph_uses_combat_service(client):
    workflows = DeterministicWorkflows(
        client.app.state.store,
        combat_service=CombatService(rng=lambda sides: 12),
    )

    result = workflows.run_ability_check(
        AbilityCheckRequest(
            ability="wisdom",
            ability_score=14,
            dc=12,
            reason="Notice the hidden latch",
        )
    )

    assert result.roll == 12
    assert result.modifier == 2
    assert result.total == 14
    assert result.success is True
    assert result.reason == "Notice the hidden latch"


def test_combat_graph_routes_non_attack_action(client):
    workflows = DeterministicWorkflows(
        client.app.state.store,
        combat_service=CombatService(rng=lambda sides: 10),
    )
    state = CombatService(rng=lambda sides: 10).start_combat(
        [
            {"name": "Hero", "side": "player", "hp": 10, "hp_max": 10, "ac": 12},
            {"name": "Goblin", "side": "enemy", "hp": 7, "hp_max": 7, "ac": 13},
        ]
    )

    result = workflows.combat_graph.invoke(
        {
            "combat_state": state,
            "actor_name": "Hero",
            "action": {"actor_name": "Hero", "action_type": "dodge"},
            "attacker_name": "",
            "target_name": "",
            "result": None,
        }
    )["result"]

    assert result["action_type"] == "dodge"
    assert "dodge" in result["actor"]["conditions"]


def test_scene_update_graph_applies_validated_patch(client):
    workflows = DeterministicWorkflows(client.app.state.store)
    scene = {
        "location": "Gate",
        "environment": "A closed stone gate.",
        "important_objects": ["gate"],
        "npcs": [],
        "current_objective": "Enter.",
        "world_changes": [],
    }

    result = workflows.run_scene_update(
        scene,
        ScenePatch(
            environment="The gate is open.",
            current_objective="Cross the threshold.",
            world_changes=["The stone gate was opened."],
        ),
    )

    assert result.environment == "The gate is open."
    assert result.current_objective == "Cross the threshold."
    assert result.world_changes == ["The stone gate was opened."]


def test_memory_graph_returns_context_bundle(client):
    workflows = DeterministicWorkflows(client.app.state.store)
    character = client.post(
        "/api/characters",
        json={"name": "Memory Hero", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Memory Test", "character_id": character["id"]},
    ).json()

    context = workflows.run_memory(adventure["id"], 2048)

    assert context.recent_messages
