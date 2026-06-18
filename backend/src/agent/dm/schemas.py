from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentKind(StrEnum):
    REACT = "react"
    STATE_GRAPH = "state_graph"


class PlanStep(BaseModel):
    agent: str
    instruction: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class SupervisorPlan(BaseModel):
    intent: str
    steps: list[PlanStep] = Field(default_factory=list)


class AbilityCheckRequest(BaseModel):
    ability: Literal[
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    ]
    ability_score: int = Field(ge=1, le=30)
    dc: int = Field(ge=1, le=30)
    reason: str = ""


class AbilityCheckResult(BaseModel):
    ability: str
    roll: int
    modifier: int
    total: int
    dc: int
    success: bool
    reason: str = ""


class ScenePatch(BaseModel):
    location: str | None = None
    environment: str | None = None
    important_objects: list[str] | None = None
    npcs: list[str] | None = None
    current_objective: str | None = None
    world_changes: list[str] = Field(default_factory=list)


class SubAgentResult(BaseModel):
    agent: str
    facts: list[str] = Field(default_factory=list)
    dice_result: AbilityCheckResult | None = None
    scene_patch: ScenePatch | None = None
    npc_actions: list[str] = Field(default_factory=list)
    world_events: list[dict[str, Any]] = Field(default_factory=list)
    requires_followup: bool = False
