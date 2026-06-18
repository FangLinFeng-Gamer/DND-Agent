import random
import re
from collections.abc import Callable, Sequence
from typing import Any


DAMAGE_PATTERN = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")
ROLL_MODES = {"normal", "advantage", "disadvantage"}
COVER_BONUS = {"none": 0, "half": 2, "three-quarters": 5}
SIMPLE_ACTIONS = {
    "dash",
    "disengage",
    "dodge",
    "help",
    "hide",
    "ready",
    "search",
    "use_object",
}


class CombatService:
    def __init__(self, rng: Callable[[int], int] | None = None):
        self.rng = rng or (lambda sides: random.randint(1, sides))

    def roll_check(self, modifier: int = 0, dc: int = 10, mode: str = "normal") -> dict[str, Any]:
        if mode not in ROLL_MODES:
            raise ValueError(f"Invalid roll mode: {mode}.")

        rolls = [self.rng(20)]
        if mode in {"advantage", "disadvantage"}:
            rolls.append(self.rng(20))

        kept = max(rolls) if mode == "advantage" else min(rolls) if mode == "disadvantage" else rolls[0]
        total = kept + modifier
        return {
            "rolls": rolls,
            "kept": kept,
            "modifier": modifier,
            "total": total,
            "dc": dc,
            "success": total >= dc,
            "mode": mode,
        }

    def roll_damage(self, damage: str, critical: bool = False) -> dict[str, Any]:
        match = DAMAGE_PATTERN.fullmatch(damage.strip())
        if match is None:
            raise ValueError(f"Invalid dice expression: {damage}.")

        count = int(match.group(1))
        sides = int(match.group(2))
        modifier = int(match.group(3) or 0)
        if count <= 0 or sides <= 0:
            raise ValueError(f"Invalid dice expression: {damage}.")

        roll_count = count * 2 if critical else count
        rolls = [self.rng(sides) for _ in range(roll_count)]
        total = sum(rolls) + modifier
        result = {
            "expression": damage,
            "rolls": rolls,
            "modifier": modifier,
            "total": total,
        }
        if critical:
            result["critical"] = True
        return result

    def start_combat(self, participants: Sequence[dict[str, Any]]) -> dict[str, Any]:
        if not participants:
            raise ValueError("Combat requires at least one participant.")

        normalized = [self._normalize_participant(participant) for participant in participants]
        normalized.sort(key=lambda participant: participant["initiative"], reverse=True)
        state = {
            "participants": normalized,
            "is_active": True,
            "round_number": 1,
            "turn_index": 0,
        }
        if normalized:
            self._start_turn(normalized[0])
        return state

    def resolve_action(self, state: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
        self._ensure_active(state)
        self._normalize_state(state)
        action_type = str(action.get("action_type") or "attack").replace("-", "_")
        actor_name = action.get("actor_name") or action.get("attacker_name")
        if not actor_name:
            raise ValueError("actor_name is required.")

        if action_type == "attack":
            return self.resolve_attack(state, actor_name, action.get("target_name"), action)
        if action_type == "move":
            return self._resolve_move(state, actor_name, action)
        if action_type in SIMPLE_ACTIONS:
            return self._resolve_simple_action(state, actor_name, action_type, action)
        if action_type == "death_save":
            return self._resolve_death_save(state, actor_name)
        if action_type == "grapple":
            return self._resolve_grapple(state, actor_name, action)
        if action_type == "shove":
            return self._resolve_shove(state, actor_name, action)
        if action_type == "cast_spell":
            return self._resolve_cast_spell(state, actor_name, action)
        raise ValueError(f"Unsupported combat action: {action_type}.")

    def resolve_attack(
        self,
        state: dict[str, Any],
        attacker_name: str,
        target_name: str | None,
        action: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_active(state)
        self._normalize_state(state)
        if not target_name:
            raise ValueError("target_name is required for attack actions.")
        action = action or {}
        attacker = self._find_actor_who_can_act(state, attacker_name, "attacker")
        target = self._find_living_participant(state, target_name, "target")

        cover = action.get("cover") or target.get("cover", "none")
        if cover == "total":
            raise ValueError(f"{target_name} has total cover and cannot be targeted directly.")

        attack = self._select_attack(attacker, action.get("attack_id"))
        mode = str(action.get("mode") or "normal")
        if target.get("dodge_active") and mode == "normal":
            mode = "disadvantage"
        dc = target["ac"] + self._cover_bonus(cover)
        attack_roll = self._roll_attack(modifier=attack["attack_bonus"], dc=dc, mode=mode)
        hit = attack_roll["success"]
        damage_roll = None
        damage = 0
        if hit:
            damage_roll = self.roll_damage(attack["damage"], critical=attack_roll["critical"])
            damage = self._apply_damage(
                target,
                max(0, int(damage_roll["total"])),
                attack.get("damage_type", "bludgeoning"),
                critical=attack_roll["critical"],
                nonlethal=bool(action.get("nonlethal", False)),
            )
            if target["defeated"] and self._should_end_combat(state.get("participants", [])):
                self.end_combat(state)

        self._consume_action(attacker)
        return {
            "action_type": "attack",
            "actor": attacker,
            "attack_roll": attack_roll,
            "hit": hit,
            "critical": attack_roll["critical"],
            "damage": damage,
            "damage_roll": damage_roll,
            "target": target,
            "state": state,
            "ends_turn": True,
        }

    def advance_turn(self, state: dict[str, Any]) -> dict[str, Any]:
        self._ensure_active(state)
        self._normalize_state(state)
        participants = state.get("participants", [])
        if not participants:
            raise ValueError("Combat requires at least one participant.")

        if self._should_end_combat(participants):
            return self.end_combat(state)

        start_index = state.get("turn_index", 0)
        wrapped = False
        for step in range(1, len(participants) + 1):
            next_index = (start_index + step) % len(participants)
            if next_index <= start_index and not wrapped:
                state["round_number"] = state.get("round_number", 1) + 1
                wrapped = True
            if not participants[next_index]["defeated"]:
                state["turn_index"] = next_index
                self._start_turn(participants[next_index])
                break

        if self._should_end_combat(participants):
            return self.end_combat(state)
        return state

    def end_combat(self, state: dict[str, Any]) -> dict[str, Any]:
        state["is_active"] = False
        return state

    def _normalize_participant(self, participant: dict[str, Any]) -> dict[str, Any]:
        upgraded = self._upgrade_participant(participant)
        upgraded["initiative"] = self.rng(20) + upgraded["initiative_bonus"]
        return upgraded

    def _normalize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        state["participants"] = [self._upgrade_participant(participant) for participant in state.get("participants", [])]
        state.setdefault("round_number", 1)
        state.setdefault("turn_index", 0)
        state.setdefault("is_active", True)
        return state

    def _upgrade_participant(self, participant: dict[str, Any]) -> dict[str, Any]:
        hp = int(participant.get("hp", 0))
        hp_max = int(participant.get("hp_max") or max(hp, 1))
        speed = int(participant.get("speed_ft", 30))
        conditions = list(participant.get("conditions", []))
        kind = participant.get("kind", "npc")
        defeated = bool(participant.get("defeated", hp == 0 and kind not in {"character", "pc"}))
        if hp == 0 and kind in {"character", "pc"} and not defeated:
            for condition in ("unconscious", "incapacitated"):
                if condition not in conditions:
                    conditions.append(condition)
        return {
            **participant,
            "name": participant["name"],
            "side": participant["side"],
            "hp": hp,
            "hp_max": hp_max,
            "temp_hp": int(participant.get("temp_hp", 0)),
            "ac": int(participant.get("ac", 10)),
            "attack_bonus": int(participant.get("attack_bonus", 0)),
            "damage": participant.get("damage", "1d4"),
            "damage_type": participant.get("damage_type", "bludgeoning"),
            "kind": kind,
            "initiative": int(participant.get("initiative", 0)),
            "initiative_bonus": int(participant.get("initiative_bonus", 0)),
            "speed_ft": speed,
            "reach_ft": int(participant.get("reach_ft", 5)),
            "movement_remaining_ft": int(participant.get("movement_remaining_ft", speed)),
            "action_available": bool(participant.get("action_available", True)),
            "bonus_action_available": bool(participant.get("bonus_action_available", True)),
            "reaction_available": bool(participant.get("reaction_available", True)),
            "conditions": conditions,
            "cover": participant.get("cover", "none"),
            "engaged_with": list(participant.get("engaged_with", [])),
            "surprised": bool(participant.get("surprised", False)),
            "dodge_active": bool(participant.get("dodge_active", "dodge" in conditions)),
            "disengage_active": bool(participant.get("disengage_active", False)),
            "helping": participant.get("helping"),
            "attacks": list(participant.get("attacks", [])),
            "resistances": list(participant.get("resistances", [])),
            "vulnerabilities": list(participant.get("vulnerabilities", [])),
            "immunities": list(participant.get("immunities", [])),
            "athletics_bonus": int(participant.get("athletics_bonus", 0)),
            "acrobatics_bonus": int(participant.get("acrobatics_bonus", 0)),
            "death_saves": dict(participant.get("death_saves", {"successes": 0, "failures": 0})),
            "stable": bool(participant.get("stable", False)),
            "defeated": defeated,
        }

    def _start_turn(self, participant: dict[str, Any]) -> None:
        cannot_act = not self._can_participant_act(participant)
        participant["action_available"] = not participant.get("surprised", False) and not cannot_act
        participant["bonus_action_available"] = not cannot_act
        participant["reaction_available"] = not cannot_act
        participant["movement_remaining_ft"] = participant["speed_ft"]
        participant["disengage_active"] = False
        participant["helping"] = None
        participant["dodge_active"] = False
        participant["conditions"] = [condition for condition in participant["conditions"] if condition != "dodge"]
        if participant.get("surprised", False):
            participant["movement_remaining_ft"] = 0
            participant["surprised"] = False
        if cannot_act:
            participant["movement_remaining_ft"] = 0

    def _resolve_simple_action(
        self,
        state: dict[str, Any],
        actor_name: str,
        action_type: str,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        actor = self._find_actor_who_can_act(state, actor_name, "actor")
        self._consume_action(actor)
        requires_dm = False
        if action_type == "dash":
            actor["movement_remaining_ft"] += actor["speed_ft"]
        elif action_type == "disengage":
            actor["disengage_active"] = True
        elif action_type == "dodge":
            actor["dodge_active"] = True
            self._add_condition(actor, "dodge")
        elif action_type == "help":
            actor["helping"] = action.get("target_name") or True
        elif action_type in {"hide", "ready", "search"}:
            requires_dm = True
        return {
            "action_type": action_type,
            "actor": actor,
            "requires_dm_adjudication": requires_dm,
            "state": state,
            "ends_turn": True,
        }

    def _resolve_move(self, state: dict[str, Any], actor_name: str, action: dict[str, Any]) -> dict[str, Any]:
        actor = self._find_actor_who_can_act(state, actor_name, "actor")
        movement = int(action.get("movement_ft", 0))
        cost = movement * (2 if action.get("difficult_terrain") else 1)
        if cost > actor["movement_remaining_ft"]:
            raise ValueError("Movement exceeds remaining movement.")
        actor["movement_remaining_ft"] -= cost

        opportunity = {"eligible": False}
        leaves_reach_of = action.get("leaves_reach_of")
        if leaves_reach_of and not actor.get("disengage_active", False):
            attacker = self._find_living_participant(state, leaves_reach_of, "opportunity attacker")
            eligible = (
                attacker.get("reaction_available", True)
                and actor_name in attacker.get("engaged_with", [])
                and self._can_participant_act(attacker)
            )
            opportunity = {
                "eligible": eligible,
                "attacker_name": leaves_reach_of,
                "target_name": actor_name,
                "reaction_available": attacker.get("reaction_available", True),
            }
        return {
            "action_type": "move",
            "actor": actor,
            "opportunity_attack": opportunity,
            "state": state,
            "ends_turn": False,
        }

    def _resolve_death_save(self, state: dict[str, Any], actor_name: str) -> dict[str, Any]:
        actor = self._find_participant(state, actor_name, "actor")
        if actor["hp"] > 0:
            raise ValueError("Death saving throws are only available at 0 hit points.")
        roll = self.roll_check(modifier=0, dc=10)
        saves = actor["death_saves"]
        if roll["kept"] == 20:
            actor["hp"] = 1
            actor["stable"] = False
            actor["death_saves"] = {"successes": 0, "failures": 0}
            actor["conditions"] = [
                condition for condition in actor["conditions"] if condition not in {"unconscious", "incapacitated"}
            ]
        elif roll["kept"] == 1:
            saves["failures"] += 2
        elif roll["success"]:
            saves["successes"] += 1
        else:
            saves["failures"] += 1

        if actor["death_saves"]["successes"] >= 3:
            actor["stable"] = True
            actor["death_saves"] = {"successes": 0, "failures": 0}
        if actor["death_saves"]["failures"] >= 3:
            actor["defeated"] = True
            self._add_condition(actor, "dead")
        return {
            "action_type": "death_save",
            "actor": actor,
            "roll": roll,
            "state": state,
            "ends_turn": False,
        }

    def _resolve_grapple(self, state: dict[str, Any], actor_name: str, action: dict[str, Any]) -> dict[str, Any]:
        actor = self._find_actor_who_can_act(state, actor_name, "actor")
        target = self._find_living_participant(state, action.get("target_name"), "target")
        self._consume_action(actor)
        attacker_roll = self.roll_check(modifier=int(actor.get("athletics_bonus", 0)), dc=0)
        defender_bonus = self._defender_opposed_bonus(target, action.get("defender_choice"))
        defender_roll = self.roll_check(modifier=defender_bonus, dc=0)
        success = attacker_roll["total"] >= defender_roll["total"]
        if success:
            self._add_condition(target, "grappled")
            target["grappled_by"] = actor_name
        return {
            "action_type": "grapple",
            "actor": actor,
            "target": target,
            "success": success,
            "attacker_roll": attacker_roll,
            "defender_roll": defender_roll,
            "state": state,
            "ends_turn": True,
        }

    def _resolve_shove(self, state: dict[str, Any], actor_name: str, action: dict[str, Any]) -> dict[str, Any]:
        actor = self._find_actor_who_can_act(state, actor_name, "actor")
        target = self._find_living_participant(state, action.get("target_name"), "target")
        self._consume_action(actor)
        attacker_roll = self.roll_check(modifier=int(actor.get("athletics_bonus", 0)), dc=0)
        defender_bonus = self._defender_opposed_bonus(target, action.get("defender_choice"))
        defender_roll = self.roll_check(modifier=defender_bonus, dc=0)
        success = attacker_roll["total"] >= defender_roll["total"]
        if success and action.get("shove_effect", "prone") == "prone":
            self._add_condition(target, "prone")
        elif success:
            target["pushed_ft"] = int(action.get("pushed_ft", 5))
        return {
            "action_type": "shove",
            "actor": actor,
            "target": target,
            "success": success,
            "attacker_roll": attacker_roll,
            "defender_roll": defender_roll,
            "state": state,
            "ends_turn": True,
        }

    def _resolve_cast_spell(self, state: dict[str, Any], actor_name: str, action: dict[str, Any]) -> dict[str, Any]:
        actor = self._find_actor_who_can_act(state, actor_name, "actor")
        self._consume_action(actor)
        return {
            "action_type": "cast_spell",
            "actor": actor,
            "spell_id": action.get("spell_id"),
            "requires_dm_adjudication": True,
            "state": state,
            "ends_turn": True,
        }

    def _select_attack(self, attacker: dict[str, Any], attack_id: str | None = None) -> dict[str, Any]:
        attacks = attacker.get("attacks") or []
        if attack_id:
            for attack in attacks:
                if attack.get("item_id") == attack_id or attack.get("id") == attack_id:
                    return {
                        "attack_bonus": int(attack.get("attack_bonus", attacker["attack_bonus"])),
                        "damage": attack.get("damage", attacker["damage"]),
                        "damage_type": attack.get("damage_type", attacker.get("damage_type", "bludgeoning")),
                    }
        if attacks:
            attack = attacks[0]
            return {
                "attack_bonus": int(attack.get("attack_bonus", attacker["attack_bonus"])),
                "damage": attack.get("damage", attacker["damage"]),
                "damage_type": attack.get("damage_type", attacker.get("damage_type", "bludgeoning")),
            }
        return {
            "attack_bonus": int(attacker.get("attack_bonus", 0)),
            "damage": attacker.get("damage", "1d4"),
            "damage_type": attacker.get("damage_type", "bludgeoning"),
        }

    def _roll_attack(self, modifier: int, dc: int, mode: str) -> dict[str, Any]:
        rolled = self.roll_check(modifier=modifier, dc=dc, mode=mode)
        natural = rolled["kept"]
        rolled["critical"] = natural == 20
        rolled["natural_one"] = natural == 1
        if natural == 1:
            rolled["success"] = False
        elif natural == 20:
            rolled["success"] = True
        return rolled

    def _apply_damage(
        self,
        target: dict[str, Any],
        amount: int,
        damage_type: str,
        critical: bool = False,
        nonlethal: bool = False,
    ) -> int:
        if damage_type in target.get("immunities", []):
            amount = 0
        elif damage_type in target.get("resistances", []):
            amount //= 2
        elif damage_type in target.get("vulnerabilities", []):
            amount *= 2

        before_hp = target["hp"]
        before_temp = target.get("temp_hp", 0)
        absorbed = min(before_temp, amount)
        target["temp_hp"] = before_temp - absorbed
        remaining = amount - absorbed
        target["hp"] = max(0, target["hp"] - remaining)
        overflow = max(0, remaining - before_hp)
        self._apply_zero_hp_state(target, overflow, critical=critical, nonlethal=nonlethal)
        return min(amount, before_hp + before_temp)

    def _apply_zero_hp_state(
        self,
        target: dict[str, Any],
        overflow: int,
        critical: bool = False,
        nonlethal: bool = False,
    ) -> None:
        if target["hp"] > 0:
            return
        if target.get("kind") in {"character", "pc"}:
            if overflow >= target["hp_max"]:
                target["defeated"] = True
                self._add_condition(target, "dead")
            else:
                self._add_condition(target, "unconscious")
                self._add_condition(target, "incapacitated")
                target["stable"] = False
                if overflow and target.get("death_saves"):
                    target["death_saves"]["failures"] += 2 if critical else 1
            return

        target["defeated"] = True
        if nonlethal:
            target["stable"] = True
            self._add_condition(target, "unconscious")

    def _cover_bonus(self, cover: str | None) -> int:
        normalized = cover or "none"
        if normalized not in COVER_BONUS:
            raise ValueError(f"Invalid cover level: {cover}.")
        return COVER_BONUS[normalized]

    def _consume_action(self, participant: dict[str, Any]) -> None:
        if not participant.get("action_available", True):
            raise ValueError(f"{participant['name']} has already used an action this turn.")
        participant["action_available"] = False

    def _defender_opposed_bonus(self, target: dict[str, Any], defender_choice: str | None) -> int:
        choice = defender_choice or "athletics"
        if choice == "acrobatics":
            return int(target.get("acrobatics_bonus", 0))
        return int(target.get("athletics_bonus", 0))

    def _add_condition(self, participant: dict[str, Any], condition: str) -> None:
        if condition not in participant["conditions"]:
            participant["conditions"].append(condition)

    def _find_participant(self, state: dict[str, Any], name: str, role: str) -> dict[str, Any]:
        for participant in state.get("participants", []):
            if participant["name"] == name:
                return participant
        raise ValueError(f"Missing {role}: {name}.")

    def _find_living_participant(self, state: dict[str, Any], name: str | None, role: str) -> dict[str, Any]:
        if not name:
            raise ValueError(f"Missing {role}: {name}.")
        participant = self._find_participant(state, name, role)
        if participant["defeated"]:
            raise ValueError(f"Missing living {role}: {name}.")
        return participant

    def _find_actor_who_can_act(self, state: dict[str, Any], name: str | None, role: str) -> dict[str, Any]:
        participant = self._find_living_participant(state, name, role)
        if int(participant.get("hp", 0)) <= 0:
            raise ValueError(f"{participant['name']} cannot act at 0 hit points.")
        if self._is_incapacitated(participant):
            raise ValueError(f"{participant['name']} is incapacitated and cannot act.")
        return participant

    def _can_participant_act(self, participant: dict[str, Any]) -> bool:
        return (
            not participant.get("defeated", False)
            and int(participant.get("hp", 0)) > 0
            and not self._is_incapacitated(participant)
        )

    def _is_incapacitated(self, participant: dict[str, Any]) -> bool:
        return "incapacitated" in set(participant.get("conditions", []))

    def _ensure_active(self, state: dict[str, Any]) -> None:
        if not state.get("is_active", False):
            raise ValueError("Cannot act on inactive combat state.")

    def _should_end_combat(self, participants: Sequence[dict[str, Any]]) -> bool:
        living_sides = {participant["side"] for participant in participants if not participant["defeated"]}
        return len(living_sides) <= 1
