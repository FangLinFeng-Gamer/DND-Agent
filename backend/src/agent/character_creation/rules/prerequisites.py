from backend.src.agent.character_creation.rules.models import PHBRuleRecord
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft


def validate_prerequisites(
    rule: PHBRuleRecord,
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> None:
    for prerequisite in rule.prerequisites:
        if prerequisite.kind == "ability_minimum":
            ability = str(prerequisite.values[0])
            minimum = int(prerequisite.minimum or 0)
            if draft.abilities.final.get(ability, 0) < minimum:
                raise ValueError(f"{rule.id} requires {ability} {minimum}.")
        elif prerequisite.kind == "ability_any_minimum":
            minimum = int(prerequisite.minimum or 0)
            abilities = [str(value) for value in prerequisite.values]
            if not any(
                draft.abilities.final.get(ability, 0) >= minimum
                for ability in abilities
            ):
                joined = " or ".join(abilities)
                raise ValueError(f"{rule.id} requires {joined} {minimum}.")
        elif prerequisite.kind == "spellcasting":
            if not _has_spellcasting(draft, repository):
                raise ValueError(f"{rule.id} requires spellcasting.")
        elif prerequisite.kind == "proficiency":
            required = {str(value) for value in prerequisite.values}
            owned = {
                value
                for values in draft.proficiencies.values()
                for value in values
            }
            missing = sorted(required - owned)
            if missing:
                raise ValueError(
                    f"{rule.id} requires proficiency {', '.join(missing)}."
                )
        else:
            raise ValueError(
                f"Unsupported prerequisite kind: {prerequisite.kind}."
            )


def _has_spellcasting(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> bool:
    if not draft.selections.class_id:
        return False
    class_rule = repository.get(draft.selections.class_id)
    return bool(class_rule.metadata.get("spellcasting_ability"))
