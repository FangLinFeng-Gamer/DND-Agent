from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    kind: str = Field(min_length=1)
    subject_id: str | None = None
    description: str = Field(min_length=1)


class ImageResponse(BaseModel):
    id: int
    kind: str
    subject_id: str | None = None
    prompt: str
    status: str
    result_uri: str | None = None
