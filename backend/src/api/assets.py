from fastapi import APIRouter, Request

from backend.src.schemas.assets import ImageRequest, ImageResponse
from backend.src.services.assets import ImageService


router = APIRouter(prefix="/api/assets", tags=["assets"])


def image_service(request: Request) -> ImageService:
    return ImageService(request.app.state.store)


@router.post("/images", response_model=ImageResponse)
def request_image(image: ImageRequest, request: Request) -> ImageResponse:
    return image_service(request).request_image(image)
