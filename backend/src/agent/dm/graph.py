from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.language_models.chat_models import BaseChatModel

from backend.src.agent.dm.schemas import SupervisorPlan
from backend.src.agent.dm.skill_registry import DMSkill
from backend.src.agent.dm.supervisor import DMSupervisor
from backend.src.agent.locale import normalize_locale
from backend.src.db.sqlite import SQLiteStore


class RuntimeState(TypedDict):
    player_input: str
    locale: str
    plan: SupervisorPlan | None
    resolver: Callable[[SupervisorPlan], dict[str, Any]] | None
    result: dict[str, Any] | None
    model: BaseChatModel | None
    skill_context: list[DMSkill]


class DMGraphRunner:
    def __init__(self, store: SQLiteStore, supervisor: DMSupervisor | None = None):
        self.supervisor = supervisor or DMSupervisor(store)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(RuntimeState)

        def plan(state: RuntimeState):
            supervisor = DMSupervisor(self.supervisor.store, model=state.get("model"))
            return {
                "plan": supervisor.plan(
                    state["player_input"],
                    state["locale"],
                    skills=state.get("skill_context") or [],
                )
            }

        def resolve(state: RuntimeState):
            resolver = state.get("resolver")
            return {"result": resolver(state["plan"]) if resolver else {}}

        graph.add_node("plan", plan)
        graph.add_node("resolve", resolve)
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "resolve")
        graph.add_edge("resolve", END)
        return graph.compile(name="dm_multi_agent_graph")

    def run(
        self,
        player_input: str,
        resolver: Callable[[SupervisorPlan], dict[str, Any]],
        model: BaseChatModel | None = None,
        locale: str = "en",
        skill_context: list[DMSkill] | None = None,
    ) -> dict[str, Any]:
        state = self.graph.invoke(
            {
                "player_input": player_input,
                "locale": normalize_locale(locale),
                "plan": None,
                "resolver": resolver,
                "result": None,
                "model": model,
                "skill_context": skill_context or [],
            }
        )
        return state["result"]

    def plan(
        self,
        player_input: str,
        model: BaseChatModel | None = None,
        locale: str = "en",
        skill_context: list[DMSkill] | None = None,
    ) -> SupervisorPlan:
        return DMSupervisor(self.supervisor.store, model=model).plan(
            player_input,
            locale,
            skills=skill_context or [],
        )
