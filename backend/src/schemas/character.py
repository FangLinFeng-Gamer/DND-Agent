from typing import Any

from pydantic import BaseModel, Field


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1)
    race: str = "Human"
    class_name: str = "Fighter"
    experience_points: int = Field(default=0, ge=0)
    background: str = "Adventurer"
    alignment: str = "Neutral"
    notes: str = ""


class CharacterDraftCommit(BaseModel):
    draft_revision: int = Field(ge=0)
    name: str = Field(min_length=1)
    race: str
    class_name: str
    background: str
    alignment: str
    hp_current: int = Field(ge=0)
    hp_max: int = Field(gt=0)
    armor_class: int = Field(ge=1, le=30)
    strength: int = Field(ge=1, le=30)
    dexterity: int = Field(ge=1, le=30)
    constitution: int = Field(ge=1, le=30)
    intelligence: int = Field(ge=1, le=30)
    wisdom: int = Field(ge=1, le=30)
    charisma: int = Field(ge=1, le=30)
    skills: dict[str, int] = Field(default_factory=dict)
    proficiencies: dict[str, list[str]] = Field(default_factory=dict)
    inventory: list[str | dict[str, Any]] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)
    notes: str = ""


class CharacterUpdate(BaseModel):
    name: str | None = None
    race: str | None = None
    class_name: str | None = None
    level: int | None = None
    experience_points: int | None = None
    background: str | None = None
    alignment: str | None = None
    hp_current: int | None = None
    hp_max: int | None = None
    armor_class: int | None = None
    strength: int | None = None
    dexterity: int | None = None
    constitution: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    charisma: int | None = None
    skills: dict[str, int] | None = None
    inventory: list[str | dict[str, Any]] | None = None
    spells: list[str] | None = None
    notes: str | None = None


class CharacterOut(BaseModel):
    id: int
    name: str
    race: str
    class_name: str
    level: int
    experience_points: int = 0
    next_level_experience: int | None = None
    experience_to_next_level: int = 0
    level_progress: float = 0.0
    background: str
    alignment: str
    hp_current: int
    hp_max: int
    armor_class: int
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    skills: dict[str, int]
    proficiencies: dict[str, list[str]] = Field(default_factory=dict)
    inventory: list[str | dict[str, Any]]
    spells: list[str]
    notes: str
