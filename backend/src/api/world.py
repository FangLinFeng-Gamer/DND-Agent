from fastapi import APIRouter, Request

from backend.src.schemas.world import WorldSearchOut
from backend.src.services.world import WorldService


router = APIRouter(prefix="/api/world", tags=["world"])


def world_service(request: Request) -> WorldService:
    return WorldService(request.app.state.store)


@router.get("/search", response_model=WorldSearchOut)
def search_world(request: Request, query: str | None = None, category: str | None = None) -> WorldSearchOut:
    return world_service(request).search(query=query, category=category)
