from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.src.agent.dm.schemas import AbilityCheckRequest, AbilityCheckResult, ScenePatch
from backend.src.agent.dm.memory import AgentMemoryManager
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.adventure import SceneState
from backend.src.services.adventures import AdventureService
from backend.src.services.combat import CombatService
from backend.src.services.world_events import WorldEventService


class AbilityState(TypedDict):
    request: AbilityCheckRequest
    result: AbilityCheckResult | None


class SceneUpdateState(TypedDict):
    scene: dict[str, Any]
    patch: ScenePatch
    result: SceneState | None


class CombatWorkflowState(TypedDict, total=False):
    combat_state: dict[str, Any]
    actor_name: str
    attacker_name: str
    target_name: str
    action: dict[str, Any]
    result: dict[str, Any] | None


class MemoryState(TypedDict):
    adventure_id: int
    max_context_tokens: int
    result: Any


class CommitState(TypedDict):
    adventure_id: int
    scene: SceneState | None
    world_events: list[dict[str, Any]]
    committed: bool


class DeterministicWorkflows:
    agent_kind = "state_graph"

    def __init__(self, store: SQLiteStore, combat_service: CombatService | None = None):
        self.combat = combat_service or CombatService()
        self.adventures = AdventureService(store)
        self.world_events = WorldEventService(store)
        self.memory = AgentMemoryManager(store)
        self.ability_check_graph = self._build_ability_check_graph()
        self.saving_throw_graph = self._build_ability_check_graph(name="saving_throw_agent")
        self.combat_graph = self._build_combat_graph()
        self.scene_update_graph = self._build_scene_update_graph()
        self.memory_graph = self._build_memory_graph()
        self.commit_graph = self._build_commit_graph()

    def _build_ability_check_graph(self, name: str = "ability_check_agent"):
        graph = StateGraph(AbilityState)

        def roll(state: AbilityState):
            request = state["request"]
            modifier = (request.ability_score - 10) // 2
            rolled = self.combat.roll_check(modifier=modifier, dc=request.dc)
            return {
                "result": AbilityCheckResult(
                    ability=request.ability,
                    roll=rolled["kept"],
                    modifier=modifier,
                    total=rolled["total"],
                    dc=request.dc,
                    success=rolled["success"],
                    reason=request.reason,
                )
            }

        graph.add_node("roll", roll)
        graph.add_edge(START, "roll")
        graph.add_edge("roll", END)
        return graph.compile(name=name)

    def _build_combat_graph(self):
        graph = StateGraph(CombatWorkflowState)

        def resolve(state: CombatWorkflowState):
            combat_state = {
                **state["combat_state"],
                "participants": [
                    dict(participant)
                    for participant in state["combat_state"].get("participants", [])
                ],
            }
            action = dict(state.get("action") or {})
            if not action:
                action = {
                    "actor_name": state.get("actor_name") or state.get("attacker_name"),
                    "attacker_name": state.get("attacker_name"),
                    "target_name": state.get("target_name"),
                    "action_type": "attack",
                }
            return {
                "result": self.combat.resolve_action(combat_state, action)
            }

        graph.add_node("resolve", resolve)
        graph.add_edge(START, "resolve")
        graph.add_edge("resolve", END)
        return graph.compile(name="combat_agent")

    def _build_scene_update_graph(self):
        graph = StateGraph(SceneUpdateState)

        def apply_patch(state: SceneUpdateState):
            scene = dict(state["scene"])
            patch = state["patch"]
            for field in ("location", "environment", "important_objects", "npcs", "current_objective"):
                value = getattr(patch, field)
                if value is not None:
                    scene[field] = value
            scene["world_changes"] = [*(scene.get("world_changes") or []), *patch.world_changes]
            return {"result": SceneState.model_validate(scene)}

        graph.add_node("apply_patch", apply_patch)
        graph.add_edge(START, "apply_patch")
        graph.add_edge("apply_patch", END)
        return graph.compile(name="scene_update_agent")

    def _build_memory_graph(self):
        graph = StateGraph(MemoryState)

        def load_and_summarize(state: MemoryState):
            return {
                "result": self.memory.summarize_if_needed(
                    state["adventure_id"],
                    state["max_context_tokens"],
                )
            }

        graph.add_node("load_and_summarize", load_and_summarize)
        graph.add_edge(START, "load_and_summarize")
        graph.add_edge("load_and_summarize", END)
        return graph.compile(name="memory_agent")

    def _build_commit_graph(self):
        graph = StateGraph(CommitState)

        def commit(state: CommitState):
            if state.get("scene") is not None:
                self.adventures.update_scene(state["adventure_id"], state["scene"])
            if state.get("world_events"):
                from backend.src.schemas.world_event import WorldEventCreate

                for event in state["world_events"]:
                    self.world_events.create(
                        state["adventure_id"],
                        WorldEventCreate.model_validate(event),
                    )
            return {"committed": True}

        graph.add_node("commit", commit)
        graph.add_edge(START, "commit")
        graph.add_edge("commit", END)
        return graph.compile(name="commit_agent")

    def run_ability_check(self, request: AbilityCheckRequest) -> AbilityCheckResult:
        return self.ability_check_graph.invoke({"request": request, "result": None})["result"]

    def run_scene_update(self, scene: dict[str, Any], patch: ScenePatch) -> SceneState:
        return self.scene_update_graph.invoke({"scene": scene, "patch": patch, "result": None})["result"]

    def run_memory(self, adventure_id: int, max_context_tokens: int):
        return self.memory_graph.invoke(
            {
                "adventure_id": adventure_id,
                "max_context_tokens": max_context_tokens,
                "result": None,
            }
        )["result"]

    def commit(
        self,
        adventure_id: int,
        scene: SceneState | None,
        world_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self.commit_graph.invoke(
            {
                "adventure_id": adventure_id,
                "scene": scene,
                "world_events": world_events or [],
                "committed": False,
            }
        )
