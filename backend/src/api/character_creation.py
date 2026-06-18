from fastapi import APIRouter, Request

from backend.src.core.errors import api_error
from backend.src.schemas.character_creation import (
    CharacterCreationGuideOut,
    CharacterDraftMutation,
    CharacterCreationMessage,
    CharacterCreationSessionOut,
    CharacterCreationStart,
)
from backend.src.agent.character_creation.rules.draft_service import (
    DraftRevisionConflict,
)
from backend.src.services.character_drafts import CharacterDraftService


router = APIRouter(prefix="/api/character-creation", tags=["character-creation"])


def service(request: Request) -> CharacterDraftService:
    return CharacterDraftService(request.app.state.store)


@router.post("/sessions", response_model=CharacterCreationSessionOut)
def create_session(payload: CharacterCreationStart, request: Request) -> CharacterCreationSessionOut:
    return service(request).create(payload.locale)


@router.get("/sessions/{session_id}", response_model=CharacterCreationSessionOut)
def get_session(session_id: int, request: Request) -> CharacterCreationSessionOut:
    try:
        return service(request).get(session_id)
    except LookupError as exc:
        raise api_error(404, "not_found", str(exc)) from exc


@router.get(
    "/sessions/{session_id}/guide",
    response_model=CharacterCreationGuideOut,
)
def get_guide(
    session_id: int,
    request: Request,
    locale: str = "en",
    step: str | None = None,
) -> CharacterCreationGuideOut:
    try:
        return service(request).guide(session_id, locale, step=step)
    except LookupError as exc:
        raise api_error(404, "not_found", str(exc)) from exc


@router.post("/sessions/{session_id}/messages", response_model=CharacterCreationSessionOut)
def append_message(
    session_id: int,
    payload: CharacterCreationMessage,
    request: Request,
) -> CharacterCreationSessionOut:
    try:
        return service(request).handle_message(session_id, payload.content, payload.locale)
    except DraftRevisionConflict as exc:
        raise api_error(
            409,
            "draft_revision_conflict",
            str(exc),
        ) from exc
    except LookupError as exc:
        raise api_error(404, "not_found", str(exc)) from exc


@router.patch(
    "/sessions/{session_id}/draft",
    response_model=CharacterCreationSessionOut,
)
def mutate_draft(
    session_id: int,
    payload: CharacterDraftMutation,
    request: Request,
) -> CharacterCreationSessionOut:
    try:
        return service(request).mutate(session_id, payload)
    except DraftRevisionConflict as exc:
        raise api_error(
            409,
            "draft_revision_conflict",
            str(exc),
        ) from exc
    except LookupError as exc:
        raise api_error(404, "not_found", str(exc)) from exc
    except ValueError as exc:
        raise api_error(400, "validation_error", str(exc)) from exc
