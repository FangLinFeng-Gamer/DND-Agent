from backend.src.agent.character_creation.derived.abilities import (
    apply_ability_derived_values,
)
from backend.src.agent.character_creation.derived.combat import (
    apply_combat_derived_values,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft, CharacterDerivedSheet


def calculate_derived_sheet(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> CharacterDerivedSheet:
    sheet = CharacterDerivedSheet.model_validate(draft.derived.model_dump())
    sheet = apply_ability_derived_values(draft, sheet, repository)
    return apply_combat_derived_values(draft, sheet, repository)
