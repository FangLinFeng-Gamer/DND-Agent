import json

from langchain_core.language_models.chat_models import BaseChatModel

from backend.src.agent.dm.react import build_react_agent
from backend.src.agent.dm.schemas import AgentKind, PlanStep, SupervisorPlan
from backend.src.agent.dm.skill_registry import DMSkill, format_skill_prompt_context
from backend.src.agent.dm.subagents import ReactSubAgentRegistry
from backend.src.agent.locale import language_instruction, normalize_locale
from backend.src.db.sqlite import SQLiteStore


class DMSupervisor:
    agent_kind = AgentKind.REACT
    tool_names = (
        "exploration_agent",
        "social_agent",
        "story_agent",
        "npc_agent",
        "rules_research_agent",
        "ability_check_agent",
        "saving_throw_agent",
        "combat_agent",
        "scene_update_agent",
        "memory_agent",
    )

    def __init__(self, store: SQLiteStore, model: BaseChatModel | None = None):
        self.store = store
        self.model = model

    def plan(
        self,
        player_input: str,
        locale: str = "en",
        skills: list[DMSkill] | None = None,
    ) -> SupervisorPlan:
        locale = normalize_locale(locale)
        if self.model is None:
            return self.fallback_plan(player_input)
        try:
            skill_prompt = format_skill_prompt_context(skills)
            tools = ReactSubAgentRegistry(
                self.model,
                self.store,
                locale=locale,
                skill_context=skills,
            ).tools()
            agent = build_react_agent(
                self.model,
                tools,
                (
                    "You are the DM supervisor. Plan only; do not narrate, roll dice, "
                    "or modify state. Return JSON with intent and steps. Each step must "
                    f"use one of: {', '.join(self.tool_names)}. "
                    f"{skill_prompt} "
                    f"{language_instruction(locale)}"
                ),
                name="dm_supervisor",
            )
            result = agent.invoke({"messages": [{"role": "user", "content": player_input}]})
            content = result["messages"][-1].content
            return SupervisorPlan.model_validate(json.loads(content))
        except Exception:
            return self.fallback_plan(player_input)

    def fallback_plan(self, player_input: str) -> SupervisorPlan:
        normalized = player_input.lower()
        if any(term in normalized for term in ("attack", "fight", "combat")):
            intent, agent = "combat", "combat_agent"
        elif any(term in normalized for term in ("talk", "persuade", "deceive", "intimidate")):
            intent, agent = "social", "social_agent"
        elif any(term in normalized for term in ("quest", "story", "plot")):
            intent, agent = "story", "story_agent"
        else:
            intent, agent = "exploration", "exploration_agent"
        return SupervisorPlan(
            intent=intent,
            steps=[PlanStep(agent=agent, instruction=player_input)],
        )
