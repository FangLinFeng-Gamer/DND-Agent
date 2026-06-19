from typing import Any

from pydantic import BaseModel, Field


class CharacterStateChange(BaseModel):
    character_id: int | None = None
    character_name: str | None = None
    hp_current: int | None = Field(default=None, ge=0)
    hp_delta: int | None = None
    hp_max: int | None = Field(default=None, gt=0)
    experience_points: int | None = Field(default=None, ge=0)
    experience_delta: int | None = None
    level: int | None = Field(default=None, ge=1, le=20)
    add_inventory: list[str | dict[str, Any]] = Field(default_factory=list)
    remove_inventory: list[str | dict[str, Any]] = Field(default_factory=list)
    add_spells: list[str] = Field(default_factory=list)
    remove_spells: list[str] = Field(default_factory=list)
    notes_append: str | None = None
    reason: str = ""
