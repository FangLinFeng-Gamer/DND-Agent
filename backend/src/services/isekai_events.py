from __future__ import annotations

from typing import Any

from backend.src.schemas.world_event import WorldEventCreate, WorldEventOut
from backend.src.services.world_events import WorldEventService


SCOPE_IMPORTANCE = {
    "local": 1,
    "settlement": 3,
    "regional": 4,
    "national": 4,
    "global": 5,
}


class IsekaiWorldEventDirector:
    def __init__(self, store):
        self.events = WorldEventService(store)

    def evaluate_turn(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        world_state: dict[str, Any],
    ) -> list[WorldEventOut]:
        candidate = self._player_triggered_candidate(turn)
        if candidate is None:
            candidate = self._preference_candidate(turn, world_state)
        if candidate is None:
            candidate = self._random_candidate(turn, world_state)
        if candidate is None:
            return []
        channel = (
            "direct_observation"
            if candidate["source"] == "player_triggered"
            else self._knowledge_channel(turn, candidate["scope"])
        )
        if channel is None:
            return []
        candidate["knowledge_channel"] = channel
        candidate["known_to_character"] = True
        event = self.events.create(adventure_id, self._to_create(candidate, turn))
        return [event]

    def _player_triggered_candidate(self, turn: dict[str, Any]) -> dict[str, Any] | None:
        text = str(turn.get("player_input") or "")
        if not any(keyword in text for keyword in ("做", "烹饪", "煮", "开餐厅", "偷", "帮助", "救", "交易")):
            return None
        if any(keyword in text for keyword in ("做", "烹饪", "煮", "开餐厅")):
            title = "营地记住了陌生料理的香味"
            description = "你亲眼看到周围的人被热食吸引，这件小事开始改变附近营地对你的态度。"
            tags = ["美食", "社交"]
        elif any(keyword in text for keyword in ("偷", "盗")):
            title = "附近商旅提高了警惕"
            description = "你的行动让附近商旅开始互相提醒，看管货物的人明显变多了。"
            tags = ["风险", "贸易"]
        else:
            title = "你的行动改变了附近人的态度"
            description = "你刚才的选择被周围的人看在眼里，附近的态度开始发生细微变化。"
            tags = ["声望"]
        return {
            "event_type": "world",
            "title": title,
            "description": description,
            "scope": "local",
            "source": "player_triggered",
            "affected_area": self._location(turn),
            "preference_tags": tags,
            "triggering_action": text,
        }

    def _preference_candidate(self, turn: dict[str, Any], world_state: dict[str, Any]) -> dict[str, Any] | None:
        preferences = world_state.get("player_preferences") or {}
        tags = [str(tag) for tag in preferences.get("themes", []) + preferences.get("goals", [])]
        if not tags:
            return None
        scope = str(world_state.get("force_event_scope") or "settlement")
        if scope not in SCOPE_IMPORTANCE:
            scope = "settlement"
        if not any(tag in " ".join(tags) for tag in ("美食", "餐厅", "食材", "贸易")):
            return None
        return {
            "event_type": "world",
            "title": "新食材传闻出现在商路上",
            "description": "你从可接触到的消息渠道得知，附近有人正在寻找懂得异域料理的人。",
            "scope": scope,
            "source": "preference_weighted",
            "affected_area": self._location(turn),
            "preference_tags": tags[:4],
            "triggering_action": "",
        }

    def _random_candidate(self, turn: dict[str, Any], world_state: dict[str, Any]) -> dict[str, Any] | None:
        turn_count = int(world_state.get("turn_count", 0))
        if not world_state.get("force_event_scope") and (turn_count <= 0 or turn_count % 3 != 0):
            return None
        scope = str(world_state.get("force_event_scope") or "local")
        if scope not in SCOPE_IMPORTANCE:
            scope = "local"
        return {
            "event_type": "world",
            "title": "附近环境出现变化",
            "description": "你注意到附近的风向、足迹和生物活动发生了变化。",
            "scope": scope,
            "source": "random_world",
            "affected_area": self._location(turn),
            "preference_tags": [],
            "triggering_action": "",
        }

    def _knowledge_channel(self, turn: dict[str, Any], scope: str) -> str | None:
        scene = turn.get("scene")
        text = f"{getattr(scene, 'location', '')} {getattr(scene, 'environment', '')}".lower()
        if scope == "local":
            return "direct_observation" if turn.get("action_type") != "talk" else "environment_sign"
        if any(keyword in text for keyword in ("集市", "市场", "商队", "商人", "旅人", "酒馆", "城", "镇", "村", "market", "merchant", "town")):
            return "merchant_news"
        if any(keyword in text for keyword in ("神殿", "法师塔", "预言", "temple", "mage")):
            return "dream_omen"
        return None

    def _to_create(self, candidate: dict[str, Any], turn: dict[str, Any]) -> WorldEventCreate:
        scope = candidate["scope"]
        return WorldEventCreate(
            event_type=candidate["event_type"],
            title=candidate["title"],
            description=candidate["description"],
            importance=SCOPE_IMPORTANCE[scope],
            metadata={
                "mode": "isekai_survival",
                "scope": scope,
                "source": candidate["source"],
                "knowledge_channel": candidate["knowledge_channel"],
                "known_to_character": candidate["known_to_character"],
                "location": self._location(turn),
                "affected_area": candidate["affected_area"],
                "preference_tags": candidate["preference_tags"],
                "triggering_action": candidate["triggering_action"],
            },
        )

    def _location(self, turn: dict[str, Any]) -> str:
        scene = turn.get("scene")
        return str(getattr(scene, "location", "") or "未知地点")
