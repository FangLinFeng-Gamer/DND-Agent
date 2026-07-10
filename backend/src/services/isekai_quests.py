from __future__ import annotations

from typing import Any

from backend.src.services.isekai_content import IsekaiContentService


class IsekaiQuestService:
    NO_ACTIVE_QUEST = {"active_quest_id": None, "stage": "none", "flags": {}}

    def __init__(self, content: IsekaiContentService | None = None):
        self.content = content or IsekaiContentService()

    def initial_world_state(self, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = dict(world_state or {})
        state.setdefault("isekai_clues", [])
        next_state, _ = self.ensure_single_quest(state)
        return next_state

    def ensure_single_quest(self, world_state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        state = dict(world_state or {})
        allowed_ids = self.content.allowed_active_quest_ids(state)
        quest = state.get("isekai_quest")
        blocked: list[dict[str, str]] = []
        if isinstance(quest, dict) and quest.get("active_quest_id") in allowed_ids:
            quest_id = str(quest.get("active_quest_id") or "")
            stage = self._valid_stage(quest_id, str(quest.get("stage") or "not_started"), state)
            state["isekai_quest"] = {
                "active_quest_id": quest_id,
                "stage": stage,
                "flags": dict(quest.get("flags") or {}),
            }
            return state, {"blocked": blocked}

        if isinstance(quest, dict) and quest.get("active_quest_id"):
            blocked.append(
                {
                    "quest_id": str(quest.get("active_quest_id")),
                    "blocked_reason": "p1_single_quest_only",
                }
            )
        elif isinstance(quest, list):
            for entry in quest:
                quest_id = str(entry.get("quest_id") or entry.get("active_quest_id") or "") if isinstance(entry, dict) else ""
                if quest_id and quest_id not in allowed_ids:
                    blocked.append({"quest_id": quest_id, "blocked_reason": "p1_single_quest_only"})

        state["isekai_quest"] = self.default_quest(state)
        return state, {"blocked": blocked}

    def apply_quest_proposals(
        self,
        world_state: dict[str, Any],
        proposals: Any,
        *,
        action_type: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        state, applied = self.ensure_single_quest(world_state)
        blocked = list(applied.get("blocked") or [])
        if not isinstance(proposals, list):
            return state, {"blocked": blocked, "applied": []}

        applied_updates: list[dict[str, str]] = []
        allowed_ids = self.content.allowed_active_quest_ids(state)
        for proposal in proposals[:6]:
            if not isinstance(proposal, dict):
                continue
            quest_id = str(proposal.get("quest_id") or proposal.get("active_quest_id") or "")
            stage = str(proposal.get("stage") or "")
            if quest_id not in allowed_ids:
                blocked.append({"quest_id": quest_id or "unknown", "blocked_reason": "p1_single_quest_only"})
                continue
            if action_type != "quest_resolution" or stage not in self._stages(quest_id, state):
                blocked.append({"quest_id": quest_id, "blocked_reason": "quest_stage_change_not_allowed"})
                continue
            state["isekai_quest"] = {**state["isekai_quest"], "stage": stage}
            applied_updates.append({"quest_id": quest_id, "stage": stage})
        return state, {"blocked": blocked, "applied": applied_updates}

    def advance_for_turn(
        self,
        world_state: dict[str, Any],
        turn: dict[str, Any],
        pressure_event: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        state, applied = self.ensure_single_quest(world_state)
        quest = dict(state["isekai_quest"])
        quest_id = str(quest.get("active_quest_id") or "")
        before = str(quest.get("stage") or "not_started")
        next_stage = before
        flags = dict(quest.get("flags") or {})
        clues = [str(item) for item in state.get("isekai_clues", []) if str(item).strip()]
        added_clues: list[str] = []
        if not quest_id:
            state["isekai_clues"] = clues[-20:]
            return state, {
                "before": before,
                "after": next_stage,
                "changed": False,
                "clues_added": [],
                "blocked": applied.get("blocked") or [],
            }

        transition = self._matching_transition(quest_id, before, state, turn, pressure_event)
        if transition:
            next_stage = str(transition.get("to") or before)
            flags.update({str(key): value for key, value in (transition.get("flags") or {}).items()})
            added_clues.extend(str(item) for item in transition.get("adds_clues", []) if str(item).strip())

        for clue in added_clues:
            if clue not in clues:
                clues.append(clue)
        quest = {**quest, "stage": next_stage, "flags": flags}
        state["isekai_quest"] = quest
        state["isekai_clues"] = clues[-20:]
        update = {
            "before": before,
            "after": next_stage,
            "changed": before != next_stage,
            "clues_added": added_clues,
            "blocked": applied.get("blocked") or [],
        }
        return state, update

    def default_quest(self, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        allowed = self.content.allowed_active_quest_ids(world_state)
        if not allowed:
            return dict(self.NO_ACTIVE_QUEST)
        quest_id = sorted(allowed)[0]
        return {"active_quest_id": quest_id, "stage": "not_started", "flags": {}}

    def _matching_transition(
        self,
        quest_id: str,
        stage: str,
        world_state: dict[str, Any],
        turn: dict[str, Any],
        pressure_event: dict[str, Any] | None,
    ) -> dict[str, Any]:
        line = self.content.quest_line(quest_id, world_state)
        for transition in line.get("transitions", []):
            if not isinstance(transition, dict):
                continue
            if str(transition.get("from") or "") != stage:
                continue
            if self._triggered(transition.get("trigger"), turn, pressure_event):
                return dict(transition)
        return {}

    def _triggered(self, trigger: Any, turn: dict[str, Any], pressure_event: dict[str, Any] | None) -> bool:
        if not isinstance(trigger, dict):
            return False
        event_id = str(trigger.get("pressure_event_id") or "")
        if event_id and (not pressure_event or pressure_event.get("id") != event_id):
            return False
        matched = bool(event_id)
        text = str(turn.get("player_input") or "")
        text_markers = [str(item) for item in trigger.get("text_contains_any", []) if str(item).strip()]
        if text_markers and any(marker in text for marker in text_markers):
            matched = True
        clue_markers = [str(item) for item in trigger.get("delta_clue_contains_any", []) if str(item).strip()]
        if clue_markers:
            delta = turn.get("delta") or {}
            if any(any(marker in str(clue) for marker in clue_markers) for clue in delta.get("clues", [])):
                matched = True
        return matched

    def _valid_stage(self, quest_id: str, stage: str, world_state: dict[str, Any]) -> str:
        return stage if stage in self._stages(quest_id, world_state) else "not_started"

    def _stages(self, quest_id: str, world_state: dict[str, Any]) -> list[str]:
        line = self.content.quest_line(quest_id, world_state)
        stages = [str(item) for item in line.get("stages", []) if str(item).strip()]
        return stages or ["not_started", "rumor_heard", "night_event_seen", "prepared", "tracking", "resolved"]
