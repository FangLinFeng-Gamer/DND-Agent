from typing import Any

from pydantic import BaseModel, Field

from backend.src.schemas.character import CharacterOut
from backend.src.schemas.combat import CombatActionRequest, CombatParticipantInput, CombatStateOut


class AdventureCreate(BaseModel):
    title: str = Field(min_length=1)
    character_id: int | None = None
    party_character_ids: list[int] | None = None
    world_id: str = "default"
    story_id: str = "mistbell_tower"
    locale: str = "en"

    def effective_party_character_ids(self) -> list[int]:
        if self.party_character_ids is not None:
            return list(self.party_character_ids)
        if self.character_id is not None:
            return [self.character_id]
        return []


class SceneState(BaseModel):
    location: str
    environment: str
    important_objects: list[str] = Field(default_factory=list)
    npcs: list[str] = Field(default_factory=list)
    current_objective: str
    world_changes: list[str] = Field(default_factory=list)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    locale: str = "en"
    character_id: int | None = None


class MessageOut(BaseModel):
    id: int
    adventure_id: int
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AdventureOut(BaseModel):
    id: int
    title: str
    world_id: str
    story_id: str
    character_id: int
    party_character_ids: list[int] = Field(default_factory=list)
    party_characters: list[CharacterOut] = Field(default_factory=list)
    status: str
    summary: str
    current_scene: SceneState
    world_state: dict[str, Any] = Field(default_factory=dict)
    messages: list[MessageOut] = Field(default_factory=list)


class DMAdvanceResponse(BaseModel):
    adventure: AdventureOut
    dm_message: MessageOut
    scene: SceneState
    messages: list[MessageOut]
    world_state: dict[str, Any] = Field(default_factory=dict)
    combat_state: CombatStateOut | None = None
    dice_result: dict[str, Any] | None = None


class CombatEnemyInput(CombatParticipantInput):
    side: str = "enemy"
    kind: str = "npc"


class AdventureCombatStartRequest(BaseModel):
    enemies: list[CombatEnemyInput]


class AdventureCombatActionRequest(CombatActionRequest):
    pass


class AdventureNPCCombatTurnRequest(BaseModel):
    locale: str = "en"


class AdventureCombatActionResponse(BaseModel):
    action_type: str = "attack"
    actor: dict[str, Any] | None = None
    attack_roll: dict[str, Any] | None = None
    hit: bool | None = None
    critical: bool | None = None
    damage: int | None = None
    damage_roll: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    roll: dict[str, Any] | None = None
    success: bool | None = None
    opportunity_attack: dict[str, Any] | None = None
    requires_dm_adjudication: bool = False
    ends_turn: bool = True
    decision_source: str | None = None
    decision_reason: str | None = None
    decision: dict[str, Any] | None = None
    map_movement: dict[str, Any] | None = None
    map_range: dict[str, Any] | None = None
    state: CombatStateOut
