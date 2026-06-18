from typing import Any

from pydantic import BaseModel, Field


class WorldEventCreate(BaseModel):
    event_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    importance: int = Field(default=3, ge=1, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldEventOut(WorldEventCreate):
    id: int
    adventure_id: int
    created_at: str
