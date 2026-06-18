from json import JSONDecodeError

from fastapi import APIRouter, Request
from pydantic import ValidationError

from backend.src.core.errors import api_error
from backend.src.schemas.character import CharacterCreate, CharacterOut, CharacterUpdate
from backend.src.services.characters import CharacterService


router = APIRouter(prefix="/api/characters", tags=["characters"])


def character_service(request: Request) -> CharacterService:
    return CharacterService(request.app.state.store)


@router.post("", response_model=CharacterOut)
def create_character(character: CharacterCreate, request: Request) -> CharacterOut:
    return character_service(request).create(character)


@router.get("", response_model=list[CharacterOut])
def list_characters(request: Request) -> list[CharacterOut]:
    return character_service(request).list()


@router.get("/{character_id}", response_model=CharacterOut)
def get_character(character_id: int, request: Request) -> CharacterOut:
    return character_service(request).get(character_id)


@router.patch("/{character_id}", response_model=CharacterOut)
async def update_character(character_id: int, request: Request) -> CharacterOut:
    try:
        payload = await request.json()
    except JSONDecodeError as exc:
        raise api_error(400, "validation_error", "Request body must be a JSON object.") from exc

    if not isinstance(payload, dict):
        raise api_error(400, "validation_error", "Request body must be a JSON object.")

    unknown_fields = set(payload) - set(CharacterUpdate.model_fields)
    if unknown_fields:
        field = sorted(unknown_fields)[0]
        raise api_error(400, "validation_error", f"Unsupported character field: {field}.")
    for field, value in payload.items():
        if value is None:
            raise api_error(400, "validation_error", f"{field} cannot be null.")

    try:
        update = CharacterUpdate.model_validate(payload)
    except ValidationError as exc:
        raise api_error(400, "validation_error", "Invalid character update.", {"errors": exc.errors()}) from exc

    return character_service(request).update(character_id, update)


@router.delete("/{character_id}")
def delete_character(character_id: int, request: Request) -> dict[str, int | bool]:
    character_service(request).delete(character_id)
    return {"deleted": True, "id": character_id}
