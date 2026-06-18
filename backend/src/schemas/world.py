from pydantic import BaseModel, Field


class WorldEntryOut(BaseModel):
    id: int
    category: str
    name: str
    content: str
    tags: list[str]
    source: str | None = None
    page: int | None = None
    metadata: dict = Field(default_factory=dict)


class WorldSearchOut(BaseModel):
    query: str | None
    category: str | None
    results: list[WorldEntryOut]
    message: str
