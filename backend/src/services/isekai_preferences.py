from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


class IsekaiPreferenceLearner:
    CADENCE = 5

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def maybe_update(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        model: Any | None,
    ) -> dict[str, Any]:
        updated = deepcopy(world_state)
        try:
            turn_count = int(updated.get("turn_count", 0))
        except (TypeError, ValueError):
            return updated
        if turn_count <= 0 or turn_count % self.CADENCE != 0:
            return updated
        current = updated.get("player_preferences") or {}
        if not isinstance(current, dict):
            current = {}
        try:
            updated_turn = int(current.get("updated_turn", 0))
        except (TypeError, ValueError):
            updated_turn = None
        if updated_turn == turn_count:
            return updated
        if not model or not self.llm_client or not hasattr(self.llm_client, "chat"):
            return updated
        try:
            raw = self.llm_client.chat(model, self._messages(messages, updated))
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return updated
            preferences = {
                "themes": self._string_list(payload.get("themes")),
                "playstyle": self._string_list(payload.get("playstyle")),
                "goals": self._string_list(payload.get("goals")),
                "confidence": max(0.0, min(1.0, float(payload.get("confidence", 0.5)))),
                "updated_turn": turn_count,
            }
        except Exception:
            return updated
        updated["player_preferences"] = preferences
        return updated

    def _messages(
        self,
        messages: list[dict[str, Any]],
        world_state: dict[str, Any],
    ) -> list[dict[str, str]]:
        recent = [
            {
                "role": str(message.get("role") or ""),
                "content": str(message.get("content") or ""),
            }
            for message in messages[-12:]
        ]
        payload = {
            "role_boundaries": {
                "player": "用户控制的角色行动和目标。",
                "dm": "agent 生成的叙事，不等同于用户偏好。",
                "system_state": "后端记录的本局状态。",
            },
            "recent_messages": recent,
            "system_state": {"turn_count": world_state.get("turn_count", 0)},
        }
        return [
            {
                "role": "system",
                "content": (
                    "你负责总结异世界生存游戏中玩家当前的游玩偏好。"
                    "只根据玩家消息判断偏好，DM 消息只能作为上下文。"
                    "只输出 JSON：{\"themes\":[],\"playstyle\":[],\"goals\":[],\"confidence\":0.0}"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item:
                result.append(item)
            if len(result) == 6:
                break
        return result
