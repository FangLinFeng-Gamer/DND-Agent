from time import perf_counter

from fastapi import APIRouter, Request

from backend.src.agent.llm.client import OpenAICompatibleClient
from backend.src.schemas.llm import (
    LLMModelConnectionResult,
    LLMModelConnectionTest,
    LLMModelCreate,
    LLMModelOut,
    LLMModelUpdate,
)
from backend.src.services.llm_models import LLMModelService


router = APIRouter(prefix="/api/models", tags=["models"])


def model_service(request: Request) -> LLMModelService:
    return LLMModelService(request.app.state.store)


def model_probe_client(request: Request):
    return getattr(request.app.state, "llm_client", None) or OpenAICompatibleClient()


@router.get("", response_model=list[LLMModelOut])
def list_models(request: Request) -> list[LLMModelOut]:
    return model_service(request).list()


@router.post("", response_model=LLMModelOut)
def create_model(model: LLMModelCreate, request: Request) -> LLMModelOut:
    return model_service(request).create(model)


@router.post("/test", response_model=LLMModelConnectionResult)
def test_model_connection(model: LLMModelConnectionTest, request: Request) -> LLMModelConnectionResult:
    record = model_service(request).build_connection_test_record(model)
    started = perf_counter()
    try:
        response = model_probe_client(request).chat_message(
            record,
            [
                {"role": "system", "content": "You are a connectivity probe. Reply briefly."},
                {"role": "user", "content": "Reply with exactly: pong"},
            ],
            json_mode=False,
            timeout=15,
        )
        content = response.get("content") if isinstance(response, dict) else ""
        if not str(content or "").strip():
            raise RuntimeError("Model response did not include message content.")
    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        return LLMModelConnectionResult(
            ok=False,
            message=f"Model connectivity test failed: {exc}",
            latency_ms=latency_ms,
            model_name=record.model_name,
        )

    latency_ms = int((perf_counter() - started) * 1000)
    return LLMModelConnectionResult(
        ok=True,
        message=f"Connected to {record.model_name} in {latency_ms} ms.",
        latency_ms=latency_ms,
        model_name=record.model_name,
    )


@router.patch("/{model_id}", response_model=LLMModelOut)
def update_model(model_id: int, update: LLMModelUpdate, request: Request) -> LLMModelOut:
    return model_service(request).update(model_id, update)


@router.post("/{model_id}/activate", response_model=LLMModelOut)
def activate_model(model_id: int, request: Request) -> LLMModelOut:
    return model_service(request).activate(model_id)


@router.delete("/{model_id}")
def delete_model(model_id: int, request: Request) -> dict[str, int | bool]:
    model_service(request).delete(model_id)
    return {"deleted": True, "id": model_id}
