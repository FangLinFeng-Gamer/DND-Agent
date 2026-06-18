from backend.src.db.sqlite import SQLiteStore
from backend.src.services.adventures import AdventureService
from backend.src.services.characters import CharacterService
from backend.src.services.combat import CombatService
from backend.src.services.llm_models import LLMModelService
from backend.src.services.stories import StoryService
from backend.src.services.world import WorldService


class DMAgentTools:
    def __init__(self, store: SQLiteStore, combat_service: CombatService | None = None):
        self.adventures = AdventureService(store)
        self.characters = CharacterService(store)
        self.world = WorldService(store)
        self.stories = StoryService(store)
        self.models = LLMModelService(store)
        self.combat = combat_service or CombatService(rng=lambda sides: min(10, sides))
