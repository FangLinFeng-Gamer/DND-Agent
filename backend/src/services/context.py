from pydantic import BaseModel, Field

from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.adventure import MessageOut
from backend.src.schemas.world_event import WorldEventOut
from backend.src.services.adventures import AdventureService
from backend.src.services.world_events import WorldEventService


class ContextBundle(BaseModel):
    summary: str
    party: list[dict] = Field(default_factory=list)
    recent_messages: list[MessageOut]
    important_events: list[WorldEventOut]
    estimated_tokens: int
    summary_updated: bool = False


class ContextService:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.adventures = AdventureService(store)
        self.events = WorldEventService(store)

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def build_context(self, adventure_id: int, recent_message_limit: int = 8) -> ContextBundle:
        adventure = self.adventures.get(adventure_id)
        party = [
            {
                "id": character.id,
                "name": character.name,
                "race": character.race,
                "class_name": character.class_name,
                "level": character.level,
                "experience_points": character.experience_points,
                "next_level_experience": character.next_level_experience,
                "hp_current": character.hp_current,
                "hp_max": character.hp_max,
                "armor_class": character.armor_class,
                "skills": character.skills,
                "inventory": character.inventory,
                "spells": character.spells,
            }
            for character in adventure.party_characters
        ]
        important_events = self.events.list_for_adventure(adventure_id, min_importance=3)
        recent_messages = adventure.messages[-recent_message_limit:]
        text = "\n".join(
            [
                adventure.summary,
                adventure.current_scene.model_dump_json(),
                json_safe_party_summary(party),
                *[f"{event.title}: {event.description}" for event in important_events],
                *[f"{message.role}: {message.content}" for message in recent_messages],
            ]
        )
        return ContextBundle(
            summary=adventure.summary,
            party=party,
            recent_messages=recent_messages,
            important_events=important_events,
            estimated_tokens=self.estimate_tokens(text),
        )

    def summarize_if_needed(self, adventure_id: int, max_context_tokens: int) -> ContextBundle:
        context = self.build_context(adventure_id)
        if context.estimated_tokens <= max_context_tokens:
            return context

        adventure = self.adventures.get(adventure_id)
        summary = self._make_summary(
            existing_summary=adventure.summary,
            events=context.important_events,
            messages=adventure.messages[-6:],
        )
        self.adventures.update_scene(adventure_id, adventure.current_scene, summary=summary)
        updated = self.build_context(adventure_id)
        updated.summary = summary
        updated.summary_updated = True
        return updated

    def _make_summary(
        self,
        existing_summary: str,
        events: list[WorldEventOut],
        messages: list[MessageOut],
    ) -> str:
        parts = []
        if existing_summary:
            parts.append(existing_summary)
        if events:
            parts.append(
                "Important events: "
                + " ".join(f"{event.title}: {event.description}" for event in events[-5:])
            )
        if messages:
            parts.append(
                "Recent flow: "
                + " ".join(f"{message.role}: {message.content}" for message in messages)
            )
        return "\n".join(parts)[-4000:]


def json_safe_party_summary(party: list[dict]) -> str:
    if not party:
        return ""
    return "Party: " + "; ".join(
        f"{character['name']} {character['race']} {character['class_name']} "
        f"level {character['level']} XP {character.get('experience_points', 0)} "
        f"HP {character['hp_current']}/{character['hp_max']} AC {character['armor_class']}"
        for character in party
    )
