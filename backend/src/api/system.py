from fastapi import APIRouter

from backend.src.services.system import SystemService


router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/capabilities")
def capabilities() -> dict[str, list[str]]:
    return SystemService().capabilities()
