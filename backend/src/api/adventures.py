import json

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from backend.src.core.errors import api_error
from backend.src.schemas.adventure import (
    AdventureCombatActionRequest,
    AdventureCombatActionResponse,
    AdventureNPCCombatTurnRequest,
    AdventureCombatStartRequest,
    AdventureCreate,
    AdventureOut,
    DMAdvanceResponse,
    MessageCreate,
)
from backend.src.schemas.combat import CombatStateOut
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.dm.locks import AdventureLockService
from backend.src.agent.dm.service import DMService
from backend.src.services.adventures import AdventureService
from backend.src.services.characters import CharacterService
from backend.src.services.combat import CombatService
from backend.src.services.maps import MapAttackRangeError, MapService


router = APIRouter(prefix="/api/adventures", tags=["adventures"])


def adventure_service(request: Request) -> AdventureService:
    return AdventureService(request.app.state.store)


def dm_service(request: Request) -> DMService:
    return DMService(request.app.state.store)


def ndjson_event(event: dict) -> str:
    return json.dumps(jsonable_encoder(event), ensure_ascii=False) + "\n"


def character_to_combat_participant(character) -> dict:
    strength_mod = (character.strength - 10) // 2
    dexterity_mod = (character.dexterity - 10) // 2
    attacks = character_weapon_attacks(character, strength_mod, dexterity_mod)
    primary_attack = attacks[0] if attacks else {}
    attack_bonus = int(primary_attack.get("attack_bonus", max(0, strength_mod + 2)))
    damage = primary_attack.get("damage") or "1d8" + (f"{strength_mod:+d}" if strength_mod else "")
    damage_type = primary_attack.get("damage_type") or "slashing"
    return {
        "name": character.name,
        "side": "player",
        "hp": character.hp_current,
        "hp_max": character.hp_max,
        "ac": character.armor_class,
        "attack_bonus": attack_bonus,
        "damage": damage,
        "damage_type": damage_type,
        "initiative_bonus": dexterity_mod,
        "speed_ft": 30,
        "kind": "character",
        "attacks": attacks,
    }


def character_weapon_attacks(character, strength_mod: int, dexterity_mod: int) -> list[dict]:
    try:
        repository = PHBRuleRepository.load_builtin()
    except Exception:
        repository = None
    attacks = []
    for entry in character.inventory:
        item_id = _inventory_item_id(entry)
        if not item_id or repository is None:
            continue
        try:
            item = repository.get(item_id)
        except LookupError:
            continue
        if item.metadata.get("category") != "weapon":
            continue
        tags = set(item.tags) | set(item.metadata.get("tags", []))
        properties = set(item.metadata.get("properties", []))
        if "ranged" in tags:
            ability_mod = dexterity_mod
        elif "finesse" in properties:
            ability_mod = max(strength_mod, dexterity_mod)
        else:
            ability_mod = strength_mod
        proficiency_bonus = 2
        damage = str(item.metadata.get("damage", "1d4"))
        if ability_mod:
            damage = f"{damage}{ability_mod:+d}"
        attack = {
            "item_id": item.id,
            "attack_bonus": ability_mod + proficiency_bonus,
            "damage": damage,
            "damage_type": item.metadata.get("damage_type", "bludgeoning"),
        }
        if "ranged" in tags and item.metadata.get("range"):
            weapon_range = list(item.metadata["range"])
            attack["attack_kind"] = "ranged"
            attack["normal_range_ft"] = int(weapon_range[0])
            attack["long_range_ft"] = int(weapon_range[1] if len(weapon_range) > 1 else weapon_range[0])
        attacks.append(
            attack
        )
    return attacks


def _inventory_item_id(entry) -> str | None:
    if isinstance(entry, dict):
        if int(entry.get("quantity", 1)) <= 0:
            return None
        item_id = str(entry.get("item_id") or "")
    else:
        item_id = str(entry)
    if not item_id:
        return None
    return item_id if item_id.startswith("equipment.") else f"equipment.{item_id}"


@router.post("", response_model=AdventureOut)
def create_adventure(adventure: AdventureCreate, request: Request) -> AdventureOut:
    return dm_service(request).create_adventure(adventure)


@router.get("", response_model=list[AdventureOut])
def list_adventures(request: Request) -> list[AdventureOut]:
    return adventure_service(request).list()


@router.get("/{adventure_id}", response_model=AdventureOut)
def get_adventure(adventure_id: int, request: Request) -> AdventureOut:
    return adventure_service(request).get(adventure_id)


@router.delete("/{adventure_id}")
def delete_adventure(adventure_id: int, request: Request) -> dict[str, int | bool]:
    adventure_service(request).delete(adventure_id)
    return {"deleted": True, "id": adventure_id}


@router.post("/{adventure_id}/messages", response_model=DMAdvanceResponse)
def append_message(adventure_id: int, message: MessageCreate, request: Request) -> DMAdvanceResponse:
    return dm_service(request).advance(adventure_id, message)


@router.post("/{adventure_id}/messages/stream")
def append_message_stream(adventure_id: int, message: MessageCreate, request: Request) -> StreamingResponse:
    lock_context = AdventureLockService().acquire(adventure_id)
    lock_context.__enter__()

    def stream_events():
        try:
            for event in dm_service(request).advance_stream(adventure_id, message):
                yield ndjson_event(event)
        finally:
            lock_context.__exit__(None, None, None)

    return StreamingResponse(stream_events(), media_type="application/x-ndjson")


@router.post("/{adventure_id}/combat/start", response_model=CombatStateOut)
def start_combat(adventure_id: int, combat_request: AdventureCombatStartRequest, request: Request) -> dict:
    service = adventure_service(request)
    adventure = service.get(adventure_id, include_messages=False)
    existing_state = service.get_combat_state(adventure_id)
    if existing_state and existing_state.get("is_active"):
        raise api_error(400, "combat_already_active", "Combat is already active.")

    party = service.get_party(adventure_id)
    participants = [character_to_combat_participant(character) for character in party]
    participants.extend(enemy.model_dump() for enemy in combat_request.enemies)
    try:
        state = CombatService().start_combat(participants)
    except ValueError as exc:
        raise api_error(400, "validation_error", str(exc)) from exc
    saved_state = service.save_combat_state(adventure_id, state)
    MapService(request.app.state.store).ensure_combat_tokens(adventure_id, saved_state.get("participants", []))
    return saved_state


@router.get("/{adventure_id}/combat", response_model=CombatStateOut | None)
def get_combat_state(adventure_id: int, request: Request) -> dict | None:
    state = adventure_service(request).get_combat_state(adventure_id)
    if state is None or not state.get("is_active"):
        return None
    return state


@router.post("/{adventure_id}/combat/action", response_model=AdventureCombatActionResponse)
def combat_action(adventure_id: int, action: AdventureCombatActionRequest, request: Request) -> dict:
    service = adventure_service(request)
    state = service.get_combat_state(adventure_id)
    if state is None or not state.get("is_active"):
        raise api_error(400, "combat_not_active", "Combat is not active.")

    participants = state.get("participants", [])
    turn_index = state.get("turn_index", 0)
    if not participants or turn_index >= len(participants):
        raise api_error(400, "validation_error", "Combat state is invalid.")
    current_actor = participants[turn_index]
    if current_actor["name"] != action.attacker_name:
        raise api_error(400, "invalid_turn", f"It is {current_actor['name']}'s turn.")
    if current_actor.get("side") != "player":
        raise api_error(
            400,
            "npc_turn_requires_agent",
            "NPC turns must be resolved by the DM agent.",
        )

    combat = CombatService()
    action_payload = action.model_dump(exclude_none=True)
    map_range = None
    try:
        map_range = MapService(request.app.state.store).validate_attack_range(adventure_id, state, action_payload)
        result = combat.resolve_action(state, action_payload)
        if result["state"].get("is_active") and result.get("ends_turn", True):
            combat.advance_turn(result["state"])
    except MapAttackRangeError as exc:
        raise api_error(400, "attack_out_of_range", str(exc)) from exc
    except ValueError as exc:
        raise api_error(400, "validation_error", str(exc)) from exc
    if map_range is not None:
        result["map_range"] = map_range
    service.save_combat_state(adventure_id, result["state"])
    return result


@router.post("/{adventure_id}/combat/npc-turn", response_model=AdventureCombatActionResponse)
def npc_combat_turn(
    adventure_id: int,
    request: Request,
    turn_request: AdventureNPCCombatTurnRequest | None = None,
) -> dict:
    try:
        return dm_service(request).resolve_npc_combat_turn(
            adventure_id,
            locale=(turn_request.locale if turn_request else "en"),
        )
    except ValueError as exc:
        code = str(exc)
        if code == "combat_not_active":
            raise api_error(400, "combat_not_active", "Combat is not active.") from exc
        if code == "not_npc_turn":
            raise api_error(400, "not_npc_turn", "The current combatant is controlled by the player.") from exc
        if code == "invalid_combat_state":
            raise api_error(400, "validation_error", "Combat state is invalid.") from exc
        raise api_error(400, "validation_error", code) from exc


@router.post("/{adventure_id}/combat/end", response_model=CombatStateOut)
def end_combat(adventure_id: int, request: Request) -> dict:
    service = adventure_service(request)
    state = service.get_combat_state(adventure_id)
    if state is None or not state.get("is_active"):
        raise api_error(400, "combat_not_active", "Combat is not active.")
    state = CombatService().end_combat(state)
    return service.save_combat_state(adventure_id, state)
