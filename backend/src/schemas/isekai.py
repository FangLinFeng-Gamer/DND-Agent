from typing import Any

from pydantic import BaseModel, Field


class IsekaiCharacterOut(BaseModel):
    id: int | None = None
    adventure_id: int | None = None
    name: str
    race: str
    class_name: str
    background: str = "Wanderer"
    alignment: str = "Neutral"
    level: int = 1
    hp_current: int = 10
    hp_max: int = 10
    armor_class: int = 12
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    gold: int = 10
    inventory: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    world_reaction_tags: list[str] = Field(default_factory=list)
    status_effects: list[str] = Field(default_factory=list)


class IsekaiSurvivalStateOut(BaseModel):
    adventure_id: int | None = None
    day: int = 1
    time_of_day: str = "黄昏"
    hunger: int = 10
    thirst: int = 10
    fatigue: int = 15
    sleep_need: int = 20
    temperature_risk: int = 10
    morale: int = 70
    weather: str = "薄雾"
    location: str = "未知边境"
    shelter: str = "none"
    last_action_type: str = "start"
    state: dict[str, Any] = Field(default_factory=dict)


class IsekaiSurvivalDelta(BaseModel):
    hunger: int = 0
    thirst: int = 0
    fatigue: int = 0
    sleep_need: int = 0
    temperature_risk: int = 0
    morale: int = 0
    hp_delta: int = 0
    inventory_changes: list[str] = Field(default_factory=list)
    visible_events: list[str] = Field(default_factory=list)
