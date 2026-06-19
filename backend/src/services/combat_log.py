from typing import Any


def append_combat_log_entry(
    state: dict[str, Any],
    result: dict[str, Any],
    *,
    source: str,
    round_number: int,
    turn_index: int,
) -> dict[str, Any]:
    entry = build_combat_log_entry(
        result,
        source=source,
        round_number=round_number,
        turn_index=turn_index,
    )
    action_log = state.setdefault("action_log", [])
    last_id = max([int(item.get("id", 0)) for item in action_log] or [0])
    entry["id"] = last_id + 1
    action_log.append(entry)
    return entry


def build_combat_log_entry(
    result: dict[str, Any],
    *,
    source: str,
    round_number: int,
    turn_index: int,
) -> dict[str, Any]:
    actor = result.get("actor") or {}
    target = result.get("target") or {}
    action_type = str(result.get("action_type") or "action")
    entry: dict[str, Any] = {
        "id": 0,
        "round_number": round_number,
        "turn_index": turn_index,
        "source": source,
        "actor_name": actor.get("name") or result.get("actor_name") or "-",
        "actor_side": actor.get("side") or "",
        "actor_kind": actor.get("kind") or "",
        "action_type": action_type,
        "target_name": target.get("name") or result.get("target_name"),
        "target_side": target.get("side"),
        "target_kind": target.get("kind"),
        "hit": result.get("hit"),
        "critical": result.get("critical"),
        "damage": result.get("damage"),
        "damage_type": target.get("damage_type") or result.get("damage_type"),
        "attack_roll_total": _roll_total(result.get("attack_roll")),
        "target_hp": target.get("hp"),
        "target_hp_max": target.get("hp_max"),
        "target_defeated": target.get("defeated"),
        "target_conditions": list(target.get("conditions", [])),
        "actor_hp": actor.get("hp"),
        "actor_hp_max": actor.get("hp_max"),
        "actor_defeated": actor.get("defeated"),
        "actor_conditions": list(actor.get("conditions", [])),
        "ends_turn": bool(result.get("ends_turn", True)),
        "decision_source": result.get("decision_source"),
        "decision_reason": result.get("decision_reason"),
        "map_range": result.get("map_range"),
        "map_movement": result.get("map_movement"),
    }
    entry["summary"] = _summary(entry)
    entry["effect"] = _effect(entry)
    return entry


def _roll_total(roll: dict[str, Any] | None) -> int | None:
    if not roll:
        return None
    return roll.get("total") or roll.get("value")


def _summary(entry: dict[str, Any]) -> str:
    actor = entry.get("actor_name") or "-"
    action = str(entry.get("action_type") or "action").replace("_", " ")
    target = entry.get("target_name")
    if target:
        return f"{actor} uses {action} on {target}."
    return f"{actor} uses {action}."


def _effect(entry: dict[str, Any]) -> str:
    action_type = entry.get("action_type")
    if action_type == "attack":
        if entry.get("hit") is False:
            return "The attack misses."
        damage = entry.get("damage") or 0
        target = entry.get("target_name") or "target"
        hp = entry.get("target_hp")
        hp_max = entry.get("target_hp_max")
        hp_text = f" {target} is at {hp}/{hp_max} HP." if hp is not None and hp_max is not None else ""
        defeated = " The target is defeated." if entry.get("target_defeated") else ""
        return f"The attack deals {damage} damage.{hp_text}{defeated}"
    if action_type == "end_turn":
        return "The combatant ends their turn."
    return "The action changes the combatant's combat state."
