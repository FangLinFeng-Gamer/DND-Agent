from __future__ import annotations

from typing import Any


class IsekaiQuestService:
    ALLOWED_QUEST_IDS = {"night_wolf_line"}
    STAGES = ["not_started", "rumor_heard", "night_event_seen", "prepared", "tracking", "resolved"]

    def initial_world_state(self, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = dict(world_state or {})
        state.setdefault("isekai_clues", [])
        next_state, _ = self.ensure_single_quest(state)
        return next_state

    def ensure_single_quest(self, world_state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        state = dict(world_state or {})
        quest = state.get("isekai_quest")
        blocked: list[dict[str, str]] = []
        if isinstance(quest, dict) and quest.get("active_quest_id") in self.ALLOWED_QUEST_IDS:
            stage = str(quest.get("stage") or "not_started")
            if stage not in self.STAGES:
                stage = "not_started"
            state["isekai_quest"] = {
                "active_quest_id": "night_wolf_line",
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
                if quest_id and quest_id not in self.ALLOWED_QUEST_IDS:
                    blocked.append({"quest_id": quest_id, "blocked_reason": "p1_single_quest_only"})

        state["isekai_quest"] = self.default_quest()
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
        for proposal in proposals[:6]:
            if not isinstance(proposal, dict):
                continue
            quest_id = str(proposal.get("quest_id") or proposal.get("active_quest_id") or "")
            stage = str(proposal.get("stage") or "")
            if quest_id != "night_wolf_line":
                blocked.append({"quest_id": quest_id or "unknown", "blocked_reason": "p1_single_quest_only"})
                continue
            if action_type != "quest_resolution" or stage not in self.STAGES:
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
        before = quest["stage"]
        text = str(turn.get("player_input") or "")
        next_stage = before
        flags = dict(quest.get("flags") or {})
        clues = [str(item) for item in state.get("isekai_clues", []) if str(item).strip()]
        added_clues: list[str] = []

        if before == "not_started" and self._mentions_night_wolf_rumor(text, turn):
            next_stage = "rumor_heard"
            added_clues.append("旧炉旅店店主提到夜里镇墙外有异常低嚎")
            flags["rumor_source"] = "old_furnace_keeper"
        elif before == "rumor_heard" and pressure_event and pressure_event.get("id") == "night_wolf_howl_01":
            next_stage = "night_event_seen"
            added_clues.append("夜里狼嚎来自灰石镇北坡方向")
            flags["night_event_seen"] = True
        elif before == "night_event_seen" and "梦魇草" in text:
            next_stage = "prepared"
            added_clues.append("暗夜狼惧怕梦魇草燃烟")
            flags["prepared_with_nightmare_grass"] = True
        elif before == "prepared" and any(word in text for word in ["北坡", "追踪", "痕迹", "前往"]):
            next_stage = "tracking"
            added_clues.append("北坡泥地上有暗夜狼留下的反向趾印")
            flags["tracking_started"] = True
        elif before == "tracking" and any(word in text for word in ["回镇", "汇报", "报告"]):
            next_stage = "resolved"
            flags["reported_to_innkeeper"] = True

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

    def default_quest(self) -> dict[str, Any]:
        return {"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}}

    def _mentions_night_wolf_rumor(self, text: str, turn: dict[str, Any]) -> bool:
        if "暗夜狼" in text or "狼嚎" in text or "低嚎" in text:
            return True
        delta = turn.get("delta") or {}
        return any("暗夜狼" in str(clue) or "低嚎" in str(clue) for clue in delta.get("clues", []))
