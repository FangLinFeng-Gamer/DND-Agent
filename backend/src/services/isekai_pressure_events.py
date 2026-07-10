from __future__ import annotations

from typing import Any

from backend.src.services.isekai_content import IsekaiContentService


class IsekaiPressureEventService:
    def __init__(self, content: IsekaiContentService | None = None):
        self.content = content or IsekaiContentService()

    def evaluate(
        self,
        world_state: dict[str, Any],
        turn: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        state = self.ensure_state(world_state)
        pressure_state = dict(state["isekai_pressure_events"])
        pressure_state["last_event"] = None
        cooldowns = self._advance_cooldowns(pressure_state.get("cooldowns") or {}, bool((turn.get("time") or {}).get("advances_time")))
        pressure_state["cooldowns"] = cooldowns
        state["isekai_pressure_events"] = pressure_state

        if not (turn.get("time") or {}).get("advances_time"):
            return state, None

        for event in self.content.pressure_events(state):
            event_id = event["id"]
            if int(cooldowns.get(event_id, 0)) > 0:
                continue
            if not self._triggered(event, state, turn):
                continue
            fired = dict(event)
            state = self._apply_event(state, fired)
            return state, fired
        return state, None

    def ensure_state(self, world_state: dict[str, Any]) -> dict[str, Any]:
        state = dict(world_state or {})
        existing = dict(state.get("isekai_pressure_events") or {})
        state["isekai_pressure_events"] = {
            "cooldowns": {
                str(key): max(0, int(value))
                for key, value in (existing.get("cooldowns") or {}).items()
                if str(key)
            },
            "last_event": existing.get("last_event") if isinstance(existing.get("last_event"), dict) else None,
            "history": [dict(item) for item in existing.get("history", []) if isinstance(item, dict)][-12:],
        }
        state["isekai_risks"] = {
            str(key): int(value)
            for key, value in (state.get("isekai_risks") or {}).items()
            if str(key)
        }
        return state

    def _advance_cooldowns(self, cooldowns: dict[str, Any], advances_time: bool) -> dict[str, int]:
        result: dict[str, int] = {}
        for key, value in cooldowns.items():
            remaining = max(0, int(value))
            if advances_time and remaining > 0:
                remaining -= 1
            if remaining > 0:
                result[str(key)] = remaining
        return result

    def _triggered(self, event: dict[str, Any], world_state: dict[str, Any], turn: dict[str, Any]) -> bool:
        conditions = event.get("conditions") if isinstance(event.get("conditions"), dict) else {}
        if conditions.get("time_of_day") == "night" and not self._is_night(turn):
            return False
        if "lodging_identity" in conditions and self._has_lodging_identity(world_state) != bool(conditions["lodging_identity"]):
            return False
        if not self._quest_matches(conditions.get("quest"), world_state):
            return False
        return self._has_event_cue(conditions, turn)

    def _has_event_cue(self, event: dict[str, Any], turn: dict[str, Any]) -> bool:
        cues = [str(item) for item in event.get("cue_contains_any", []) if str(item).strip()] if isinstance(event.get("cue_contains_any"), list) else []
        if not cues:
            return True
        text = str(turn.get("player_input") or "")
        return any(cue in text for cue in cues)

    def _quest_matches(self, expected: Any, world_state: dict[str, Any]) -> bool:
        if not isinstance(expected, dict):
            return True
        quest = world_state.get("isekai_quest") if isinstance(world_state.get("isekai_quest"), dict) else {}
        quest_id = str(expected.get("active_quest_id") or "")
        stage = str(expected.get("stage") or "")
        if quest_id and quest.get("active_quest_id") != quest_id:
            return False
        if stage and quest.get("stage") != stage:
            return False
        return True

    def _apply_event(self, world_state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        state = dict(world_state)
        pressure_state = dict(state["isekai_pressure_events"])
        cooldowns = dict(pressure_state.get("cooldowns") or {})
        cooldowns[event["id"]] = int(event.get("cooldown_turns") or 0)
        pressure_state["cooldowns"] = cooldowns
        pressure_state["last_event"] = event
        history = [dict(item) for item in pressure_state.get("history", []) if isinstance(item, dict)]
        history.append({"id": event["id"], "type": event["type"], "visible_text": event["visible_text"]})
        pressure_state["history"] = history[-12:]
        risks = dict(state.get("isekai_risks") or {})
        for key, value in (event.get("state_delta") or {}).items():
            risks[str(key)] = int(risks.get(str(key), 0)) + int(value)
        state["isekai_risks"] = risks
        state["isekai_pressure_events"] = pressure_state
        return state

    def _is_night(self, turn: dict[str, Any]) -> bool:
        survival = turn.get("survival") or {}
        text = str(turn.get("player_input") or "")
        return str(survival.get("time_of_day") or "") in {"夜晚", "深夜"} or any(
            word in text for word in ["夜里", "夜晚", "半夜", "深夜", "狼嚎"]
        )

    def _has_lodging_identity(self, world_state: dict[str, Any]) -> bool:
        economy = world_state.get("isekai_economy") if isinstance(world_state.get("isekai_economy"), dict) else {}
        entitlements = economy.get("entitlements") if isinstance(economy, dict) else []
        for entitlement in entitlements if isinstance(entitlements, list) else []:
            if not isinstance(entitlement, dict):
                continue
            if entitlement.get("identity") or entitlement.get("id") == "inn_room_3_bed":
                return True
        return False
