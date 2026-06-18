from typing import Any, TypedDict

from backend.src.schemas.character import CharacterOut
from backend.src.schemas.character_creation import CharacterDraft


class CharacterCreationState(TypedDict):
    draft: CharacterDraft
    content: str
    locale: str
    recent_messages: list[dict[str, Any]]
    extracted_changes: dict[str, Any]
    confirmed: bool
    changed_fields: list[str]
    next_step: str
    missing_slots: list[dict[str, Any]]
    assistant_message: str
    metadata: dict[str, Any]
    validation_errors: list[str]
    created_character: CharacterOut | None
