from dataclasses import dataclass, field
import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool

from backend.src.agent.dm.react import build_react_agent
from backend.src.agent.dm.skill_registry import DMSkill, format_skill_prompt_context
from backend.src.agent.locale import language_instruction, normalize_locale
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.world_event import WorldEventCreate
from backend.src.services.world import WorldService
from backend.src.services.world_events import WorldEventService


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


class CombatEventAgent:
    def __init__(self, store: SQLiteStore):
        self.events = WorldEventService(store)

    def record_important_events(
        self,
        adventure_id: int,
        combat_state: dict[str, Any],
        new_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        existing = self.events.list_for_adventure(adventure_id)
        existing_keys = {
            (event.metadata.get("combat_log_entry_id"), event.metadata.get("event_key"))
            for event in existing
            if event.metadata.get("source") == "combat_event_agent"
        }
        previous_round = max(1, int(combat_state.get("round_number", 1)) - 1)
        previous_round_records = [
            entry
            for entry in combat_state.get("action_log", [])
            if int(entry.get("round_number", 0)) == previous_round
        ]
        created = []
        for entry in new_entries:
            for event in self._events_from_entry(entry, combat_state, previous_round_records):
                key = (event.metadata.get("combat_log_entry_id"), event.metadata.get("event_key"))
                if key in existing_keys:
                    continue
                created_event = self.events.create(adventure_id, event)
                created.append(created_event.model_dump())
                existing_keys.add(key)
        return created

    def _events_from_entry(
        self,
        entry: dict[str, Any],
        combat_state: dict[str, Any],
        previous_round_records: list[dict[str, Any]],
    ) -> list[WorldEventCreate]:
        metadata_base = {
            "source": "combat_event_agent",
            "agent": "combat_event_agent",
            "combat_log_entry_id": entry.get("id"),
            "round_number": entry.get("round_number"),
            "previous_round_record_count": len(previous_round_records),
        }
        events: list[WorldEventCreate] = []
        if entry.get("action_type") == "attack" and entry.get("target_hp") == 0:
            target = entry.get("target_name") or "A combatant"
            actor = entry.get("actor_name") or "A combatant"
            target_side = entry.get("target_side")
            target_kind = entry.get("target_kind")
            conditions = set(entry.get("target_conditions") or [])
            defeated = bool(entry.get("target_defeated"))
            is_player_character = target_side == "player" or target_kind in {"character", "pc"}
            if is_player_character and ("dead" in conditions or defeated):
                title = f"{target} died in combat"
                description = f"{target} died after an attack by {actor} in round {entry.get('round_number')}."
                importance = 5
                event_key = "character_dead"
            elif is_player_character:
                title = f"{target} fell in combat"
                description = f"{target} was reduced to 0 HP by {actor} and is down in combat."
                importance = 5
                event_key = "character_zero_hp"
            elif defeated:
                title = f"{target} defeated"
                description = f"{target} was reduced to 0 HP by {actor} and defeated."
                importance = 3
                event_key = "combatant_defeated"
            else:
                title = f"{target} fell to 0 HP"
                description = f"{target} was reduced to 0 HP by {actor}."
                importance = 3
                event_key = "combatant_zero_hp"
            events.append(
                WorldEventCreate(
                    event_type="combat",
                    title=title,
                    description=description,
                    importance=importance,
                    metadata={**metadata_base, "event_key": event_key},
                )
            )
        if entry.get("action_type") == "death_save" and entry.get("actor_defeated"):
            actor = entry.get("actor_name") or "A combatant"
            events.append(
                WorldEventCreate(
                    event_type="combat",
                    title=f"{actor} died in combat",
                    description=f"{actor} failed death saves and died in combat.",
                    importance=5,
                    metadata={**metadata_base, "event_key": "death_save_dead"},
                )
            )
        if not combat_state.get("is_active"):
            events.append(
                WorldEventCreate(
                    event_type="combat",
                    title="Combat ended",
                    description=f"Combat ended after {entry.get('actor_name') or 'a combatant'} used {entry.get('action_type')}.",
                    importance=4,
                    metadata={**metadata_base, "event_key": "combat_ended"},
                )
            )
        return events
