from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_ISEKAI_ACTION_TYPES = {
    "status_check",
    "table_talk",
    "clarification",
    "drink_water",
    "eat_food",
    "eat_meal",
    "refill_water",
    "observe",
    "search",
    "approach",
    "enter_location",
    "leave_location",
    "travel",
    "short_dialogue",
    "negotiate",
    "purchase",
    "repair",
    "secure_shelter",
    "manage_inventory",
    "rest_short",
    "sleep",
    "hide",
    "avoid",
    "force_open",
}


@dataclass(frozen=True)
class LLMIntentStep:
    step_id: str
    action_type: str
    target_text: str = ""
    style: str = ""
    scope: str = ""
    intensity: str = ""
    constraints: list[str] = field(default_factory=list)
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMIntentPlan:
    raw_text: str
    steps: list[LLMIntentStep] = field(default_factory=list)
    deferred_steps: list[LLMIntentStep] = field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str = ""
    confidence: str = "medium"
    schema_version: str = "isekai_intent_v1"

    @property
    def truncated(self) -> bool:
        return bool(self.deferred_steps)

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "raw_text": self.raw_text,
            "requires_clarification": self.requires_clarification,
            "clarification_question": self.clarification_question,
            "confidence": self.confidence,
            "steps": [self._step_payload(step) for step in self.steps],
            "deferred_steps": [self._step_payload(step) for step in self.deferred_steps],
        }

    def _step_payload(self, step: LLMIntentStep) -> dict[str, Any]:
        return {
            "step_id": step.step_id,
            "action_type": step.action_type,
            "target_text": step.target_text,
            "style": step.style,
            "scope": step.scope,
            "intensity": step.intensity,
            "constraints": list(step.constraints),
            "arguments": dict(step.arguments),
        }


class IsekaiIntentSchema:
    MAX_STEPS = 3
    ALLOWED_CONFIDENCE = {"low", "medium", "high"}
    ALLOWED_STYLES = {"", "normal", "careful", "quick", "quiet", "forceful"}
    ALLOWED_SCOPES = {"", "indoor", "town", "wilderness", "nearby", "social"}
    ALLOWED_INTENSITIES = {"", "normal", "careful", "quick", "light", "thorough"}
    ALLOWED_CONSTRAINTS = {"no_search", "no_loot", "keep_distance", "no_attack", "no_noise"}

    def validate(self, payload: Any, raw_text: str = "") -> LLMIntentPlan:
        if not isinstance(payload, dict):
            return self.clarification(raw_text, "我没有正确理解你的行动，请换一种更具体的说法。")

        text = str(payload.get("raw_text") or raw_text or "").strip()
        confidence = self._confidence(payload.get("confidence"))
        if bool(payload.get("requires_clarification")):
            return self.clarification(
                text,
                str(payload.get("clarification_question") or "这个行动需要你再明确一下目标。"),
                confidence=confidence,
            )

        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return self.clarification(text, "我需要先确认你想让角色做什么。", confidence=confidence)

        parsed_steps: list[LLMIntentStep] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                return self.clarification(text, "意图步骤格式不正确，需要重新说明行动。", confidence="low")
            action_type = str(raw_step.get("action_type") or "").strip()
            if action_type not in ALLOWED_ISEKAI_ACTION_TYPES:
                return self.clarification(text, f"未登记动作：{action_type or '空动作'}。请换成更明确的行动。", confidence="low")
            parsed_steps.append(self._step(raw_step, index))

        return LLMIntentPlan(
            raw_text=text,
            steps=parsed_steps[: self.MAX_STEPS],
            deferred_steps=parsed_steps[self.MAX_STEPS :],
            requires_clarification=False,
            clarification_question="",
            confidence=confidence,
            schema_version=str(payload.get("schema_version") or "isekai_intent_v1"),
        )

    def clarification(self, raw_text: str, question: str, confidence: str = "low") -> LLMIntentPlan:
        return LLMIntentPlan(
            raw_text=str(raw_text or "").strip(),
            steps=[],
            requires_clarification=True,
            clarification_question=str(question or "这个行动需要你再明确一下。"),
            confidence=self._confidence(confidence),
        )

    def _step(self, raw_step: dict[str, Any], index: int) -> LLMIntentStep:
        constraints = [
            str(item).strip()
            for item in raw_step.get("constraints", [])
            if str(item).strip() in self.ALLOWED_CONSTRAINTS
        ]
        arguments = raw_step.get("arguments") if isinstance(raw_step.get("arguments"), dict) else {}
        return LLMIntentStep(
            step_id=str(raw_step.get("step_id") or f"s{index + 1}"),
            action_type=str(raw_step.get("action_type") or "").strip(),
            target_text=str(raw_step.get("target_text") or "").strip(),
            style=self._choice(raw_step.get("style"), self.ALLOWED_STYLES),
            scope=self._choice(raw_step.get("scope"), self.ALLOWED_SCOPES),
            intensity=self._choice(raw_step.get("intensity"), self.ALLOWED_INTENSITIES),
            constraints=list(dict.fromkeys(constraints)),
            arguments={str(key): value for key, value in arguments.items()},
        )

    def _choice(self, value: Any, allowed: set[str]) -> str:
        text = str(value or "").strip()
        return text if text in allowed else ""

    def _confidence(self, value: Any) -> str:
        text = str(value or "medium").strip().lower()
        return text if text in self.ALLOWED_CONFIDENCE else "medium"
