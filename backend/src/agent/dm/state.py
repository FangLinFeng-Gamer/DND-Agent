from typing import Any, TypedDict


class DMGraphState(TypedDict):
    adventure_id: int
    action_id: str
    player_input: str
    locale: str
    scene: dict[str, Any]
    character: dict[str, Any]
    combat_state: dict[str, Any] | None
    context: Any
    plan: Any
    subagent_results: list[Any]
    dice_result: dict[str, Any] | None
    scene_patch: dict[str, Any]
    world_events: list[dict[str, Any]]
    narration: str
    errors: list[str]
