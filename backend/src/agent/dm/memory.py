from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.world_event import WorldEventCreate, WorldEventOut
from backend.src.services.context import ContextBundle, ContextService
from backend.src.services.world_events import WorldEventService


class AgentMemoryManager:
    def __init__(self, store: SQLiteStore):
        self.context = ContextService(store)
        self.world_events = WorldEventService(store)

    def summarize_if_needed(self, adventure_id: int, max_context_tokens: int) -> ContextBundle:
        return self.context.summarize_if_needed(adventure_id, max_context_tokens)

    def record_world_event(self, adventure_id: int, event: WorldEventCreate) -> WorldEventOut:
        return self.world_events.create(adventure_id, event)

    def list_important_events(self, adventure_id: int, min_importance: int = 3) -> list[WorldEventOut]:
        return self.world_events.list_for_adventure(adventure_id, min_importance=min_importance)
