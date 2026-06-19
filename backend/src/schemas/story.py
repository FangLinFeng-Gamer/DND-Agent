from pydantic import BaseModel, Field

from backend.src.schemas.combat import CombatParticipantInput


class StoryEnemyInput(CombatParticipantInput):
    side: str = "enemy"
    kind: str = "npc"


class StoryEncounter(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    enemies: list[StoryEnemyInput] = Field(default_factory=list)


class StoryCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    world_background: str = Field(min_length=1)
    main_quest: str = Field(min_length=1)
    opening_location: str = Field(min_length=1)
    opening_environment: str = Field(min_length=1)
    opening_objective: str = Field(min_length=1)
    important_objects: list[str] = Field(default_factory=list)
    npcs: list[str] = Field(default_factory=list)
    encounters: list[StoryEncounter] = Field(default_factory=list)


class StoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    world_background: str | None = Field(default=None, min_length=1)
    main_quest: str | None = Field(default=None, min_length=1)
    opening_location: str | None = Field(default=None, min_length=1)
    opening_environment: str | None = Field(default=None, min_length=1)
    opening_objective: str | None = Field(default=None, min_length=1)
    important_objects: list[str] | None = None
    npcs: list[str] | None = None
    encounters: list[StoryEncounter] | None = None


class StoryOut(StoryCreate):
    id: str
