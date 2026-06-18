import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


DAMAGE_PATTERN = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


class CombatParticipantInput(BaseModel):
    name: str = Field(min_length=1)
    side: str = Field(min_length=1)
    hp: int = Field(ge=0)
    hp_max: int | None = Field(default=None, ge=1)
    temp_hp: int = Field(default=0, ge=0)
    ac: int = Field(ge=1)
    attack_bonus: int = 0
    damage: str = "1d4"
    damage_type: str = "bludgeoning"
    initiative_bonus: int = 0
    speed_ft: int = Field(default=30, ge=0)
    reach_ft: int = Field(default=5, ge=0)
    kind: str = "npc"
    attacks: list[dict[str, Any]] = Field(default_factory=list)
    resistances: list[str] = Field(default_factory=list)
    vulnerabilities: list[str] = Field(default_factory=list)
    immunities: list[str] = Field(default_factory=list)
    athletics_bonus: int = 0
    acrobatics_bonus: int = 0

    @field_validator("damage")
    @classmethod
    def validate_damage(cls, value: str) -> str:
        match = DAMAGE_PATTERN.fullmatch(value.strip())
        if match is None or int(match.group(1)) <= 0 or int(match.group(2)) <= 0:
            raise ValueError("Invalid dice expression.")
        return value


class CombatStartRequest(BaseModel):
    enemies: list[CombatParticipantInput]


class CombatActionRequest(BaseModel):
    attacker_name: str | None = Field(default=None, min_length=1)
    actor_name: str | None = Field(default=None, min_length=1)
    target_name: str | None = Field(default=None, min_length=1)
    action_type: str = "attack"
    attack_id: str | None = None
    movement_ft: int = Field(default=0, ge=0)
    difficult_terrain: bool = False
    leaves_reach_of: str | None = None
    cover: str | None = None
    mode: str = "normal"
    nonlethal: bool = False
    defender_choice: str | None = None
    shove_effect: str | None = None
    spell_id: str | None = None
    dc: int | None = Field(default=None, ge=1, le=30)

    @model_validator(mode="after")
    def normalize_actor(self) -> "CombatActionRequest":
        if self.actor_name is None and self.attacker_name is not None:
            self.actor_name = self.attacker_name
        if self.attacker_name is None and self.actor_name is not None:
            self.attacker_name = self.actor_name
        if not self.actor_name:
            raise ValueError("actor_name is required.")
        if self.action_type == "attack" and not self.target_name:
            raise ValueError("target_name is required for attack actions.")
        return self


class CombatParticipantOut(BaseModel):
    name: str
    side: str
    hp: int
    hp_max: int = 1
    temp_hp: int = 0
    ac: int
    attack_bonus: int
    damage: str
    damage_type: str = "bludgeoning"
    kind: str
    initiative: int
    initiative_bonus: int = 0
    speed_ft: int = 30
    reach_ft: int = 5
    movement_remaining_ft: int = 30
    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    conditions: list[str] = Field(default_factory=list)
    cover: str = "none"
    engaged_with: list[str] = Field(default_factory=list)
    resistances: list[str] = Field(default_factory=list)
    vulnerabilities: list[str] = Field(default_factory=list)
    immunities: list[str] = Field(default_factory=list)
    death_saves: dict[str, int] = Field(default_factory=lambda: {"successes": 0, "failures": 0})
    stable: bool = False
    defeated: bool


class CombatStateOut(BaseModel):
    participants: list[CombatParticipantOut]
    is_active: bool
    round_number: int
    turn_index: int
