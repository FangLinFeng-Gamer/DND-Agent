from langgraph.graph.state import CompiledStateGraph

from backend.src.agent.dm.schemas import AgentKind, SupervisorPlan
from backend.src.agent.dm.state import DMGraphState
from backend.src.agent.dm.supervisor import DMSupervisor
from backend.src.agent.dm.workflows import DeterministicWorkflows
from backend.src.services.combat import CombatService


def test_dm_graph_contracts_and_deterministic_workflows_exist(client):
    state: DMGraphState = {
        "adventure_id": 1,
        "action_id": "action-1",
        "player_input": "I inspect the lock.",
        "scene": {},
        "character": {},
        "combat_state": None,
        "context": None,
        "plan": None,
        "subagent_results": [],
        "dice_result": None,
        "scene_patch": {},
        "world_events": [],
        "narration": "",
        "errors": [],
    }
    workflows = DeterministicWorkflows(
        client.app.state.store,
        combat_service=CombatService(rng=lambda sides: 10),
    )

    assert state["action_id"] == "action-1"
    assert isinstance(workflows.ability_check_graph, CompiledStateGraph)
    assert isinstance(workflows.saving_throw_graph, CompiledStateGraph)
    assert isinstance(workflows.combat_graph, CompiledStateGraph)
    assert isinstance(workflows.scene_update_graph, CompiledStateGraph)
    assert isinstance(workflows.memory_graph, CompiledStateGraph)
    assert isinstance(workflows.commit_graph, CompiledStateGraph)


def test_supervisor_is_react_and_has_no_direct_commit_tool(client):
    supervisor = DMSupervisor(client.app.state.store)

    assert supervisor.agent_kind is AgentKind.REACT
    assert "commit_agent" not in supervisor.tool_names
    assert "ability_check_agent" in supervisor.tool_names
    assert "exploration_agent" in supervisor.tool_names
    assert "narration_agent" not in supervisor.tool_names


def test_supervisor_plan_is_structured():
    plan = SupervisorPlan.model_validate(
        {
            "intent": "exploration",
            "steps": [
                {
                    "agent": "exploration_agent",
                    "instruction": "Inspect the locked door.",
                }
            ],
        }
    )

    assert plan.steps[0].agent == "exploration_agent"
