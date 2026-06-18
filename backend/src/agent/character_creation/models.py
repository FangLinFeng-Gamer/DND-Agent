from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.src.schemas.character import CharacterOut
from backend.src.schemas.character_creation import ABILITY_NAMES
from backend.src.schemas.character_creation import CharacterDraft


class CharacterCreationHistoryMessage(BaseModel):
    id: int | None = None
    role: Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class CharacterExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: Literal["provide_info", "update", "confirm", "help"] = "provide_info"
    name: str | None = None
    race: str | None = None
    class_name: str | None = None
    background: str | None = None
    alignment: str | None = None
    notes: str | None = None
    ability_scores: dict[Literal[
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    ], int] | None = None

    def draft_changes(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"intent", "ability_scores"},
            exclude_none=True,
        )

    def complete_ability_scores(self) -> dict[str, int] | None:
        if self.ability_scores is None:
            return None
        if set(self.ability_scores) != set(ABILITY_NAMES):
            raise ValueError("Ability scores must include exactly the six abilities.")
        return {ability: self.ability_scores[ability] for ability in ABILITY_NAMES}


class StateGraphResult(BaseModel):
    success: bool
    draft_revision: int
    changed_fields: list[str] = Field(default_factory=list)
    current_step: str
    next_step: str
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    created_character_id: int | None = None
    committed: bool = False
    facts: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    draft: CharacterDraft

    @model_validator(mode="after")
    def validate_consistency(self) -> "StateGraphResult":
        if self.draft_revision != self.draft.revision:
            raise ValueError("draft_revision must match draft.revision.")
        if self.current_step != self.draft.current_step:
            raise ValueError("current_step must match draft.current_step.")
        if self.committed and self.created_character_id is None:
            raise ValueError("A committed result requires created_character_id.")
        if not self.committed and self.created_character_id is not None:
            raise ValueError("created_character_id requires committed=true.")
        if self.committed and not self.success:
            raise ValueError("A committed result requires success=true.")
        return self

    def to_tool_content(self) -> str:
        return self.model_dump_json(exclude={"draft"})


class CharacterCreationTurnResult(BaseModel):
    assistant_text: str
    draft: CharacterDraft
    created_character: CharacterOut | None = None
    validation_errors: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
