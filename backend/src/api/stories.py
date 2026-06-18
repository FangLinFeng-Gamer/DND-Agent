from fastapi import APIRouter, Request

from backend.src.schemas.story import StoryCreate, StoryOut, StoryUpdate
from backend.src.services.stories import StoryService


router = APIRouter(prefix="/api/stories", tags=["stories"])


def story_service(request: Request) -> StoryService:
    return StoryService(request.app.state.store)


@router.get("", response_model=list[StoryOut])
def list_stories(request: Request) -> list[StoryOut]:
    return story_service(request).list()


@router.post("", response_model=StoryOut)
def create_story(story: StoryCreate, request: Request) -> StoryOut:
    return story_service(request).create(story)


@router.get("/{story_id}", response_model=StoryOut)
def get_story(story_id: str, request: Request) -> StoryOut:
    return story_service(request).get(story_id)


@router.patch("/{story_id}", response_model=StoryOut)
def update_story(story_id: str, story: StoryUpdate, request: Request) -> StoryOut:
    return story_service(request).update(story_id, story)


@router.delete("/{story_id}")
def delete_story(story_id: str, request: Request) -> dict[str, str | bool]:
    story_service(request).delete(story_id)
    return {"deleted": True, "id": story_id}
