from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.schemas.llm import LLMModelRecord
from backend.src.services.isekai_intent_schema import ALLOWED_ISEKAI_ACTION_TYPES, IsekaiIntentSchema, LLMIntentPlan
from backend.src.services.model_gateway import ModelGateway


@dataclass(frozen=True)
class IsekaiIntentInterpretation:
    plan: LLMIntentPlan | None
    source: str
    error: str = ""
    raw_response: str = ""


class IsekaiIntentInterpreter:
    def __init__(self, model_gateway: ModelGateway, schema: IsekaiIntentSchema | None = None):
        self.model_gateway = model_gateway
        self.schema = schema or IsekaiIntentSchema()

    def interpret(
        self,
        raw_text: str,
        scene: SceneState,
        model: LLMModelRecord | None,
    ) -> IsekaiIntentInterpretation:
        if model is None:
            return IsekaiIntentInterpretation(plan=None, source="unavailable", error="no_active_model")
        try:
            response = self.model_gateway.chat(model, self._messages(raw_text, scene))
            payload = self._loads_json_object(response)
            if not self._looks_like_intent_plan(payload):
                return IsekaiIntentInterpretation(
                    plan=None,
                    source="unavailable",
                    error="not_intent_payload",
                    raw_response=response,
                )
            return IsekaiIntentInterpretation(
                plan=self.schema.validate(payload, raw_text=raw_text),
                source="active_model",
                raw_response=response,
            )
        except Exception as first_error:
            try:
                repair_response = self.model_gateway.chat(model, self._repair_messages(raw_text, str(first_error)))
                repaired_payload = self._loads_json_object(repair_response)
                if not self._looks_like_intent_plan(repaired_payload):
                    return IsekaiIntentInterpretation(
                        plan=None,
                        source="unavailable",
                        error="not_intent_payload",
                        raw_response=repair_response,
                    )
                return IsekaiIntentInterpretation(
                    plan=self.schema.validate(repaired_payload, raw_text=raw_text),
                    source="active_model",
                    raw_response=repair_response,
                )
            except Exception as repair_error:
                return IsekaiIntentInterpretation(
                    plan=None,
                    source="error",
                    error=f"{first_error}; repair_failed: {repair_error}",
                )

    def _messages(self, raw_text: str, scene: SceneState) -> list[dict[str, str]]:
        payload = {
            "player_input": raw_text,
            "current_scene": {
                "location": scene.location,
                "location_path": scene.location_path,
                "environment": scene.environment,
                "important_objects": scene.important_objects,
                "npcs": scene.npcs,
                "current_objective": scene.current_objective,
                "interactables": scene.interactables,
                "suggested_actions": scene.suggested_actions,
            },
            "allowed_action_types": sorted(ALLOWED_ISEKAI_ACTION_TYPES),
            "rules": {
                "max_steps": self.schema.MAX_STEPS,
                "model_outputs_intent_only": True,
                "state_changes_are_forbidden": True,
                "location_changes_only_by": ["enter_location", "leave_location", "travel"],
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界玩家意图解析器。"
                    "你只把玩家自然语言拆成结构化 IntentPlan，不写旁白，不结算状态。"
                    "只能使用 allowed_action_types 中的 action_type。"
                    "若目标不清、动作不在白名单或一句话超过可安全执行范围，设置 requires_clarification=true。"
                    "只输出 JSON 对象，格式："
                    "{\"schema_version\":\"isekai_intent_v1\",\"raw_text\":\"...\","
                    "\"requires_clarification\":false,\"clarification_question\":\"\","
                    "\"confidence\":\"high|medium|low\",\"steps\":[{\"step_id\":\"s1\","
                    "\"action_type\":\"observe\",\"target_text\":\"\",\"style\":\"\","
                    "\"scope\":\"\",\"intensity\":\"\",\"constraints\":[],\"arguments\":{}}],"
                    "\"deferred_steps\":[]}。"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _repair_messages(self, raw_text: str, error: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界玩家意图解析器的 JSON 修复器。"
                    "上一轮输出不可解析。只输出合法 IntentPlan JSON，不要解释。"
                ),
            },
            {"role": "user", "content": json.dumps({"player_input": raw_text, "error": error}, ensure_ascii=False)},
        ]

    def _looks_like_intent_plan(self, payload: Any) -> bool:
        return isinstance(payload, dict) and (
            "steps" in payload or "requires_clarification" in payload or payload.get("schema_version") == "isekai_intent_v1"
        )

    def _loads_json_object(self, raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("intent payload must be a JSON object")
        return payload
