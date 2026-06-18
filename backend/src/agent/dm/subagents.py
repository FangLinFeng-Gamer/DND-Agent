from dataclasses import dataclass, field
import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool

from backend.src.agent.dm.react import build_react_agent
from backend.src.agent.dm.skill_registry import DMSkill, format_skill_prompt_context
from backend.src.agent.locale import language_instruction, normalize_locale
from backend.src.db.sqlite import SQLiteStore
from backend.src.services.world import WorldService


@dataclass
class SubAgentContext:
    name: str
    adventure_id: int
    role: str
    inputs: dict[str, Any] = field(default_factory=dict)


OPEN_SUBAGENT_PROMPTS = {
    "exploration_agent": "Interpret free-form exploration. Return facts and proposed checks or scene changes. Do not roll dice or persist state.",
    "social_agent": "Analyze social intent, NPC stakes, and proposed checks. Do not roll dice or persist state.",
    "story_agent": "Propose story beats, quests, consequences, and choice points. Do not persist state.",
    "npc_agent": "Propose NPC behavior from personality, goals, relationships, and current facts. Do not persist state.",
    "rules_research_agent": "Research and summarize applicable DND rules. This agent is read-only.",
}


class ReactSubAgentRegistry:
    def __init__(
        self,
        model: BaseChatModel,
        store: SQLiteStore,
        locale: str = "en",
        skill_context: list[DMSkill] | None = None,
    ):
        self.model = model
        self.world = WorldService(store)
        self.locale = normalize_locale(locale)
        self.skill_context = skill_context or []

    def tools(self) -> list[StructuredTool]:
        return [
            StructuredTool.from_function(
                func=self._runner(name, prompt),
                name=name,
                description=prompt,
            )
            for name, prompt in OPEN_SUBAGENT_PROMPTS.items()
        ]

    def _runner(self, name: str, prompt: str):
        def run(instruction: str) -> str:
            agent = build_react_agent(
                self.model,
                self._read_only_tools(),
                (
                    f"{prompt} "
                    f"{format_skill_prompt_context(self.skill_context)} "
                    f"{language_instruction(self.locale)}"
                ),
                name=name,
            )
            result = agent.invoke({"messages": [{"role": "user", "content": instruction}]})
            return str(result["messages"][-1].content)

        return run

    def _read_only_tools(self) -> list[StructuredTool]:
        def world_search(query: str = "", category: str = "") -> str:
            """Search DND rules and world entries without changing game state."""
            result = self.world.search(query=query or None, category=category or None)
            return json.dumps(
                [entry.model_dump() for entry in result.results],
                ensure_ascii=False,
            )

        return [
            StructuredTool.from_function(
                func=world_search,
                name="world_search",
                description="Read-only search for DND rules, races, classes, equipment, lore, and world entries.",
            )
        ]


class NarrationAgent:
    def __init__(
        self,
        model: BaseChatModel,
        locale: str = "en",
        skill_context: list[DMSkill] | None = None,
    ):
        self.model = model
        self.locale = normalize_locale(locale)
        self.skill_context = skill_context or []

    def narrate(self, facts: dict[str, Any]) -> str:
        agent = build_react_agent(
            self.model,
            [],
            (
                "You are the narration agent for a DND game. Turn only the supplied, "
                "already-resolved facts into vivid DM narration. Do not change dice, "
                "damage, state, NPC actions, or world events. End at a clear choice point. "
                f"{format_skill_prompt_context(self.skill_context)} "
                f'{language_instruction(self.locale)} Return JSON: {{"narration": "..."}}'
            ),
            name="narration_agent",
        )
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(facts, ensure_ascii=False),
                    }
                ]
            }
        )
        content = result["messages"][-1].content
        try:
            return str(json.loads(content).get("narration") or "")
        except (json.JSONDecodeError, AttributeError):
            return str(content)
