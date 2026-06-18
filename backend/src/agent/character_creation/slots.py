from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.src.agent.character_creation.derived.spellcasting import (
    spell_selection_requirements,
)
from backend.src.agent.character_creation.rules.grants import (
    fixed_replaceable_proficiency_conflicts,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CHARACTER_CREATION_STEPS, CharacterDraft


SlotKind = Literal["single", "multi", "structured"]


class SlotRequirement(BaseModel):
    id: str
    step: str
    kind: SlotKind
    required: bool = True
    question: str
    options: list[str] = Field(default_factory=list)
    min_count: int | None = None
    max_count: int | None = None
    current_value: Any = None


def missing_required_slots(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> list[SlotRequirement]:
    slots: list[SlotRequirement] = []
    if not draft.name:
        slots.append(
            SlotRequirement(
                id="identity.name",
                step="identity",
                kind="single",
                question="What is your character's name?",
            )
        )
    if not draft.class_name:
        slots.append(
            SlotRequirement(
                id="class.base",
                step="class",
                kind="single",
                question="Which class do you want to play?",
            )
        )
    if not draft.race:
        slots.append(
            SlotRequirement(
                id="race.base",
                step="race",
                kind="single",
                question="Which race do you want to play?",
            )
        )
    if draft.name and draft.race and draft.class_name and _is_background_missing(draft):
        slots.append(
            SlotRequirement(
                id="background.base",
                step="background",
                kind="single",
                question="Which background do you want?",
            )
        )
    if (
        draft.name
        and draft.race
        and draft.class_name
        and not _is_background_missing(draft)
        and ("abilities" not in draft.completed_steps or "abilities" in draft.invalid_steps)
    ):
        slots.append(
            SlotRequirement(
                id="abilities.base",
                step="abilities",
                kind="structured",
                question=(
                    "Enter six ability scores manually: Strength, Dexterity, "
                    "Constitution, Intelligence, Wisdom, and Charisma. You may spend "
                    "up to 27 points. Each base score must be between 8 and 15, and "
                    "racial bonuses are applied separately. Point costs: 8=0, 9=1, "
                    "10=2, 11=3, 12=4, 13=5, 14=7, 15=9."
                ),
            )
        )
    if _needs_proficiencies(draft, repository):
        slots.append(
            SlotRequirement(
                id="proficiencies.choices",
                step="proficiencies",
                kind="multi",
                question="Choose the required skill, tool, or language proficiencies.",
                min_count=1,
            )
        )
    if _needs_class_features(draft, repository):
        slots.append(
            SlotRequirement(
                id="class_features.options",
                step="class_features",
                kind="multi",
                question="Choose the required level-one class feature options.",
                min_count=1,
            )
        )
    if _needs_optional_rules(draft, repository):
        slots.append(
            SlotRequirement(
                id="optional_rules.feats",
                step="optional_rules",
                kind="multi",
                question="Choose optional feat selections granted by your rules.",
                min_count=1,
            )
        )
    if _needs_level_one_spells(draft, repository):
        slots.append(
            SlotRequirement(
                id="spells.known",
                step="spells",
                kind="multi",
                question="Choose your level-one spell selections for this class.",
                min_count=1,
            )
        )
    if _needs_equipment(draft, repository):
        slots.append(
            SlotRequirement(
                id="equipment.starting",
                step="equipment",
                kind="structured",
                question="Choose starting equipment packages and item choices.",
            )
        )
    if _needs_adventure_connection(draft, repository):
        slots.append(
            SlotRequirement(
                id="adventure_connection.hook",
                step="adventure_connection",
                kind="structured",
                question="Connect the character to the opening adventure.",
            )
        )
    return slots


def first_missing_step(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> tuple[str, list[SlotRequirement]]:
    missing = missing_required_slots(draft, repository)
    if not missing:
        return "review", []
    ordered_steps = {step: index for index, step in enumerate(CHARACTER_CREATION_STEPS)}
    next_step = min(missing, key=lambda slot: ordered_steps.get(slot.step, 999)).step
    return next_step, [slot for slot in missing if slot.step == next_step]


def mark_completed_steps(draft: CharacterDraft, next_step: str) -> None:
    ordered_steps = list(CHARACTER_CREATION_STEPS)
    next_index = ordered_steps.index(next_step) if next_step in ordered_steps else len(ordered_steps)
    draft.completed_steps = [
        step for step in ordered_steps[:next_index] if step not in draft.invalid_steps
    ]
    draft.current_step = next_step


def _needs_level_one_spells(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> bool:
    rules = repository or PHBRuleRepository.load_builtin()
    if _needs_class_features(draft, rules):
        return False
    if _needs_optional_rules(draft, rules):
        return False
    return (
        _phase_two_base_ready(draft)
        and not _needs_proficiencies(draft, rules)
        and spell_selection_requirements(draft, rules)
        and ("spells" not in draft.completed_steps or "spells" in draft.invalid_steps)
    )


def _is_background_missing(draft: CharacterDraft) -> bool:
    return not draft.background or draft.background == "Adventurer"


def _needs_proficiencies(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> bool:
    if (
        not draft.name
        or not draft.race
        or not draft.class_name
        or _is_background_missing(draft)
        or "abilities" not in draft.completed_steps
        or "abilities" in draft.invalid_steps
    ):
        return False
    if "proficiencies" in draft.completed_steps and "proficiencies" not in draft.invalid_steps:
        return False
    rules = repository or PHBRuleRepository.load_builtin()
    for rule_id in _selected_rule_ids(draft):
        record = rules.get(rule_id)
        if any(
            grant.kind
            in {
                "skill_proficiency_choice",
                "tool_proficiency_choice",
                "language_choice",
                "mixed_proficiency_choice",
            }
            for grant in record.grants
        ):
            return True
    return bool(
        fixed_replaceable_proficiency_conflicts(_selected_rule_ids(draft), rules)
    )


def _needs_class_features(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> bool:
    if (
        not draft.name
        or not draft.race
        or not draft.class_name
        or _is_background_missing(draft)
        or "abilities" not in draft.completed_steps
        or "abilities" in draft.invalid_steps
    ):
        return False
    if _needs_proficiencies(draft, repository):
        return False
    if "class_features" in draft.completed_steps and "class_features" not in draft.invalid_steps:
        return False
    rules = repository or PHBRuleRepository.load_builtin()
    class_id = draft.selections.class_id
    if not class_id:
        return False
    class_rule = rules.get(class_id)
    return any(grant.kind == "class_option_choice" for grant in class_rule.grants)


def _needs_optional_rules(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> bool:
    rules = repository or PHBRuleRepository.load_builtin()
    if not _phase_two_base_ready(draft):
        return False
    if _needs_proficiencies(draft, rules) or _needs_class_features(draft, rules):
        return False
    if "optional_rules" in draft.completed_steps and "optional_rules" not in draft.invalid_steps:
        return False
    return _feat_capacity(draft, rules) > 0


def _needs_equipment(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> bool:
    rules = repository or PHBRuleRepository.load_builtin()
    if not _phase_two_base_ready(draft):
        return False
    if (
        _needs_proficiencies(draft, rules)
        or _needs_class_features(draft, rules)
        or _needs_optional_rules(draft, rules)
        or _needs_level_one_spells(draft, rules)
    ):
        return False
    if "equipment" in draft.completed_steps and "equipment" not in draft.invalid_steps:
        return False
    owner_ids = {
        rule_id
        for rule_id in (draft.selections.class_id, draft.selections.background_id)
        if rule_id
    }
    return any(
        record.metadata.get("owner_id") in owner_ids
        for record in rules.list("equipment_option")
    )


def _needs_adventure_connection(
    draft: CharacterDraft,
    repository: PHBRuleRepository | None = None,
) -> bool:
    rules = repository or PHBRuleRepository.load_builtin()
    if not _phase_two_base_ready(draft):
        return False
    if (
        _needs_proficiencies(draft, rules)
        or _needs_class_features(draft, rules)
        or _needs_optional_rules(draft, rules)
        or _needs_level_one_spells(draft, rules)
        or _needs_equipment(draft, rules)
    ):
        return False
    return (
        "adventure_connection" not in draft.completed_steps
        or "adventure_connection" in draft.invalid_steps
    )


def _phase_two_base_ready(draft: CharacterDraft) -> bool:
    return bool(
        draft.name
        and draft.race
        and draft.class_name
        and not _is_background_missing(draft)
        and "abilities" in draft.completed_steps
        and "abilities" not in draft.invalid_steps
    )


def _feat_capacity(
    draft: CharacterDraft,
    repository: PHBRuleRepository,
) -> int:
    capacity = 0
    for rule_id in _selected_rule_ids(draft):
        for grant in repository.get(rule_id).grants:
            if grant.kind == "feat_choice":
                capacity += int(grant.value)
    return capacity


def _selected_rule_ids(draft: CharacterDraft) -> list[str]:
    return [
        rule_id
        for rule_id in (
            draft.selections.race_id,
            draft.selections.subrace_id,
            draft.selections.class_id,
            draft.selections.background_id,
            *draft.selections.class_option_ids,
            *draft.selections.feat_ids,
        )
        if rule_id
    ]
