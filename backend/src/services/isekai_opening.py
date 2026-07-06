from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.src.schemas.adventure import AdventureCreate, SceneState
from backend.src.schemas.isekai import IsekaiCharacterOut
from backend.src.schemas.llm import LLMModelRecord
from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer
from backend.src.services.model_gateway import ModelGateway


@dataclass(frozen=True)
class IsekaiOpeningResult:
    scene: SceneState
    weather: str
    narration: str
    source: str


class IsekaiOpeningGenerator:
    FALLBACKS = [
        {
            "location": "灰桥镇外废弃马厩",
            "environment": "斜雨敲打着破损屋顶，泥地上残留着新鲜车辙，远处镇门的灯火在雾里摇晃。",
            "important_objects": ["破马灯", "新鲜车辙", "潮湿干草堆"],
            "current_objective": "弄清是谁刚刚离开马厩，并找到可以过夜的干燥角落。",
            "weather": "冷雨",
            "opening_narration": "你在灰桥镇外废弃马厩醒来，雨水顺着木梁滴落，空气里有马汗和湿草味。",
        },
        {
            "location": "盐风海崖旧哨塔",
            "environment": "海风从破裂的箭窗灌入，旧哨塔下方传来潮水拍击礁石的回声。",
            "important_objects": ["生锈号角", "断裂绳梯", "海鸟羽毛"],
            "current_objective": "确认哨塔是否安全，并找到离开海崖的路径。",
            "weather": "强风",
            "opening_narration": "你在盐风海崖的旧哨塔中醒来，咸湿风声像低语一样穿过石缝。",
        },
        {
            "location": "鹿角林边猎人营地",
            "environment": "营火只剩红炭，周围挂着半干的兽皮，林中有细碎枝响。",
            "important_objects": ["将熄营火", "半干兽皮", "猎人留下的刻痕"],
            "current_objective": "判断猎人营地为何空无一人，并寻找可用补给。",
            "weather": "寒雾",
            "opening_narration": "你在鹿角林边的猎人营地醒来，灰烬还温着，却看不到任何守夜人。",
        },
    ]

    def __init__(self, model_gateway: ModelGateway, worldview: IsekaiWorldviewNormalizer):
        self.model_gateway = model_gateway
        self.worldview = worldview

    def generate(
        self,
        request: AdventureCreate,
        character: IsekaiCharacterOut,
        model: LLMModelRecord | None,
    ) -> IsekaiOpeningResult:
        if model is not None:
            try:
                raw_response = self.model_gateway.chat(model, self._messages(request, character))
                return self._parse_payload(json.loads(raw_response), source="active_model")
            except Exception:
                pass
        return self._fallback(request)

    def _messages(self, request: AdventureCreate, character: IsekaiCharacterOut) -> list[dict[str, str]]:
        payload = {
            "title": request.title,
            "locale": request.locale,
            "character": character.model_dump(mode="json"),
            "constraints": {
                "core_resources_controlled_by_backend": True,
                "required_fields": [
                    "location",
                    "environment",
                    "important_objects",
                    "current_objective",
                    "weather",
                    "opening_narration",
                ],
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界开局生成器。"
                    f"{self.worldview.STYLE_GUIDANCE}"
                    "生成 DND 风格奇幻生存开局，只输出 JSON 对象。"
                    "不得设置 HP、金币、物品、饥饿、口渴、疲劳或睡眠需求。"
                    "格式为 {\"location\":\"...\",\"environment\":\"...\","
                    "\"important_objects\":[\"...\"],\"current_objective\":\"...\","
                    "\"weather\":\"...\",\"opening_narration\":\"...\"}。"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _parse_payload(self, payload: Any, source: str) -> IsekaiOpeningResult:
        if not isinstance(payload, dict):
            raise ValueError("opening payload must be a JSON object")
        location = self.worldview.normalize_text(payload.get("location")).strip()
        environment = self.worldview.normalize_text(payload.get("environment")).strip()
        objective = self.worldview.normalize_text(payload.get("current_objective")).strip()
        weather = self.worldview.normalize_text(payload.get("weather")).strip()
        narration = self.worldview.normalize_text(payload.get("opening_narration")).strip()
        objects = self.worldview.normalize_list(payload.get("important_objects"), limit=6)
        if not all([location, environment, objective, weather, narration]) or not objects:
            raise ValueError("opening payload is missing required fields")
        return IsekaiOpeningResult(
            scene=SceneState(
                location=location,
                environment=environment,
                important_objects=objects,
                npcs=[],
                current_objective=objective,
                world_changes=[],
            ),
            weather=weather,
            narration=narration,
            source=source,
        )

    def _fallback(self, request: AdventureCreate) -> IsekaiOpeningResult:
        index = sum(ord(char) for char in request.title) % len(self.FALLBACKS)
        return self._parse_payload(self.FALLBACKS[index], source="fallback_template")
