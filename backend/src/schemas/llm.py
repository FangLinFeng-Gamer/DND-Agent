from typing import Literal

from pydantic import BaseModel, Field


ProviderName = Literal["openai_compatible"]


class LLMModelCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: ProviderName = "openai_compatible"
    base_url: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_context_tokens: int = Field(default=4096, ge=512)


class LLMModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    provider: ProviderName | None = None
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    model_name: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_context_tokens: int | None = Field(default=None, ge=512)


class LLMModelConnectionTest(BaseModel):
    existing_model_id: int | None = None
    name: str = Field(default="Connectivity Test", min_length=1)
    provider: ProviderName = "openai_compatible"
    base_url: str = Field(min_length=1)
    api_key: str | None = None
    model_name: str = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_context_tokens: int = Field(default=4096, ge=512)


class LLMModelConnectionResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int
    model_name: str


class LLMModelOut(BaseModel):
    id: int
    name: str
    provider: ProviderName
    base_url: str
    api_key_masked: str
    model_name: str
    temperature: float
    max_context_tokens: int
    is_active: bool
    created_at: str
    updated_at: str


class LLMModelRecord(LLMModelOut):
    api_key: str
