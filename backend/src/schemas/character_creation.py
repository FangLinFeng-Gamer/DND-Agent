from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.src.schemas.character import CharacterOut


CHARACTER_CREATION_STEPS = (
    "identity",
    "class",
    "race",
    "background",
    "abilities",
    "proficiencies",
    "class_features",
    "optional_rules",
    "spells",
    "equipment",
    "adventure_connection",
    "review",
)

ABILITY_NAMES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)


class CharacterCreationStart(BaseModel):
    locale: str = "en"


class CharacterCreationMessage(BaseModel):
    content: str = Field(min_length=1)
    locale: str = "en"


class CharacterDraftMutation(BaseModel):
    expected_revision: int = Field(ge=0)
    operation: Literal[
        "identity",
        "race",
        "class",
        "abilities",
        "background",
        "proficiencies",
        "class_features",
        "optional_rules",
        "spells",
        "equipment",
        "adventure_connection",
    ]
    payload: dict[str, Any]
    locale: str = "en"


def default_abilities(value: int) -> dict[str, int]:
    return {ability: value for ability in ABILITY_NAMES}


class CharacterAbilityState(BaseModel):
    base: dict[str, int] = Field(default_factory=lambda: default_abilities(8))
    racial_bonuses: dict[str, int] = Field(default_factory=lambda: default_abilities(0))
    feat_bonuses: dict[str, int] = Field(default_factory=lambda: default_abilities(0))
    final: dict[str, int] = Field(default_factory=lambda: default_abilities(8))
    modifiers: dict[str, int] = Field(default_factory=lambda: default_abilities(-1))
    point_buy_spent: int = 0
    point_buy_remaining: int = 27
    sources: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class CharacterSelections(BaseModel):
    race_id: str | None = None
    subrace_id: str | None = None
    class_id: str | None = None
    class_option_ids: list[str] = Field(default_factory=list)
    background_id: str | None = None
    feat_ids: list[str] = Field(default_factory=list)
    spell_ids: list[str] = Field(default_factory=list)
    equipment_option_ids: list[str] = Field(default_factory=list)
    choice_values: dict[str, list[str]] = Field(default_factory=dict)


class CharacterDerivedSheet(BaseModel):
    proficiency_bonus: int = 2
    hp_max: int | None = None
    armor_class: int | None = None
    initiative: int | None = None
    speed: int | None = None
    saving_throws: dict[str, int] = Field(default_factory=dict)
    skills: dict[str, int] = Field(default_factory=dict)
    passive_perception: int | None = None
    attacks: list[dict[str, Any]] = Field(default_factory=list)
    spellcasting: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class CharacterAgentSuggestion(BaseModel):
    summary: str
    reasoning: str = ""
    proposed_changes: dict[str, Any] = Field(default_factory=dict)
    consequences: list[str] = Field(default_factory=list)
    affects_later_steps: bool = False


class CharacterDraft(BaseModel):
    schema_version: int = 2
    revision: int = 0
    current_step: str = "identity"
    completed_steps: list[str] = Field(default_factory=list)
    invalid_steps: list[str] = Field(default_factory=list)
    name: str = ""
    race: str = ""
    class_name: str = ""
    background: str = "Adventurer"
    alignment: str = "Neutral"
    notes: str = ""
    appearance: str = ""
    personality_traits: list[str] = Field(default_factory=list)
    ideal: str = ""
    bond: str = ""
    flaw: str = ""
    selections: CharacterSelections = Field(default_factory=CharacterSelections)
    abilities: CharacterAbilityState = Field(default_factory=CharacterAbilityState)
    derived: CharacterDerivedSheet = Field(default_factory=CharacterDerivedSheet)
    proficiencies: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "skills": [],
            "tools": [],
            "languages": [],
            "armor": [],
            "weapons": [],
        }
    )
    inventory: list[dict[str, Any]] = Field(default_factory=list)
    adventure_connection: dict[str, Any] = Field(default_factory=dict)
    validation_errors_by_step: dict[str, list[str]] = Field(default_factory=dict)
    validation_warnings_by_step: dict[str, list[str]] = Field(default_factory=dict)
    pending_suggestion: CharacterAgentSuggestion | None = None


class CharacterCreationSessionOut(BaseModel):
    id: int
    locale: str
    status: str
    revision: int = 0
    draft: CharacterDraft
    assistant_message: str
    validation_errors: list[str] = Field(default_factory=list)
    created_character: CharacterOut | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterCreationGuideStep(BaseModel):
    id: str
    label: str
    status: Literal["pending", "active", "completed", "invalid"] = "pending"


class CharacterCreationGuideOption(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    description: str = ""
    badges: list[str] = Field(default_factory=list)
    selected: bool = False
    disabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterCreationGuideOut(BaseModel):
    session_id: int
    locale: str
    active_step: str
    actual_step: str | None = None
    editable_steps: list[str] = Field(default_factory=list)
    steps: list[CharacterCreationGuideStep]
    options: list[CharacterCreationGuideOption] = Field(default_factory=list)
    current_value: Any = None
    requirements: dict[str, Any] = Field(default_factory=dict)
    validation_errors: list[str] = Field(default_factory=list)
