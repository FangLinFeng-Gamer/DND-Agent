from __future__ import annotations

from dataclasses import replace
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import IsekaiActionParser, ParsedIsekaiAction
from backend.src.services.isekai_intent_planner import IsekaiIntentPlan, PlannedIsekaiStep
from backend.src.services.isekai_intent_schema import LLMIntentPlan, LLMIntentStep


class IsekaiActionGrounder:
    def __init__(self, time_service: Any):
        self.time = time_service
        self.parser = IsekaiActionParser(time_service)

    def ground(self, plan: LLMIntentPlan, scene: SceneState | None = None) -> IsekaiIntentPlan:
        if plan.requires_clarification:
            return IsekaiIntentPlan(original_text=plan.raw_text, steps=[], truncated=plan.truncated)

        steps: list[PlannedIsekaiStep] = []
        for index, intent_step in enumerate(plan.steps):
            action = self._action(intent_step, scene)
            if action.requires_clarification:
                return IsekaiIntentPlan(
                    original_text=plan.raw_text,
                    steps=[PlannedIsekaiStep(index=1, text=plan.raw_text, action=action)],
                    truncated=plan.truncated,
                )
            steps.append(
                PlannedIsekaiStep(
                    index=index + 1,
                    text=self._step_text(intent_step),
                    action=action,
                )
            )
        return IsekaiIntentPlan(original_text=plan.raw_text, steps=self._coalesce_repeated_observe_steps(steps), truncated=plan.truncated)

    def _coalesce_repeated_observe_steps(self, steps: list[PlannedIsekaiStep]) -> list[PlannedIsekaiStep]:
        result: list[PlannedIsekaiStep] = []
        for step in steps:
            if result and result[-1].action.action_type == "observe" and step.action.action_type == "observe":
                previous = result[-1]
                result[-1] = PlannedIsekaiStep(
                    index=previous.index,
                    text=self._join_observe_text(previous.text, step.text),
                    action=self._merge_observe_action(previous.action, step.action),
                )
                continue
            result.append(step)
        return [PlannedIsekaiStep(index=index + 1, text=step.text, action=step.action) for index, step in enumerate(result)]

    def _join_observe_text(self, first: str, second: str) -> str:
        values = [str(first or "").strip(), str(second or "").strip()]
        return "，".join(value for value in values if value)

    def _merge_observe_action(self, first: ParsedIsekaiAction, second: ParsedIsekaiAction) -> ParsedIsekaiAction:
        target_names = [
            name
            for name in [str(first.target_name or "").strip(), str(second.target_name or "").strip()]
            if name
        ]
        merged_target = "、".join(dict.fromkeys(target_names))
        return replace(
            first,
            target_id=first.target_id if first.target_id == second.target_id else "",
            target_name=merged_target or first.target_name,
            confidence="medium" if first.confidence != "low" and second.confidence != "low" else "low",
            confidence_reasons=list(dict.fromkeys([*first.confidence_reasons, *second.confidence_reasons, "coalesced_observe"])),
            matched_rules=list(dict.fromkeys([*first.matched_rules, *second.matched_rules, "coalesced:observe"])),
        )

    def _action(self, step: LLMIntentStep, scene: SceneState | None) -> ParsedIsekaiAction:
        action_type = self._normalized_action_type(step)
        candidates = self._candidates(step, scene, action_type)
        if len(candidates) > 1:
            grouped = self._grouped_exploration_target(step, candidates, action_type)
            if grouped:
                candidates = [grouped]
            else:
                return self._build(
                    "clarification",
                    arguments={"clarification_question": f"你指的是哪一个{step.target_text or '目标'}？"},
                    requires_clarification=True,
                    candidates=candidates,
                    confidence="low",
                    matched_rules=["llm_intent", "grounder:ambiguous_target"],
                )
        target = candidates[0] if candidates else {}
        arguments = self._arguments(step, target, action_type)
        return self._build(
            action_type,
            target_id=str(target.get("id") or ""),
            target_name=str(target.get("name") or step.target_text or ""),
            arguments=arguments,
            confidence="high" if target or action_type in {"drink_water", "eat_food", "rest_short", "sleep", "status_check", "table_talk"} else "medium",
            confidence_reasons=self._confidence_reasons(step, target, action_type),
            matched_rules=self._matched_rules(step, target, action_type),
        )

    def _build(
        self,
        action_type: str,
        *,
        target_id: str = "",
        target_name: str = "",
        arguments: dict[str, Any] | None = None,
        confidence: str = "medium",
        confidence_reasons: list[str] | None = None,
        matched_rules: list[str] | None = None,
        requires_clarification: bool = False,
        candidates: list[dict[str, Any]] | None = None,
    ) -> ParsedIsekaiAction:
        resolution = self.time.resolve_action_type(action_type)
        return ParsedIsekaiAction(
            action_type=resolution.action_type,
            time_cost_minutes=resolution.time_cost_minutes,
            advances_time=resolution.advances_time,
            survival_intent=resolution.survival_intent,
            reason=resolution.reason,
            target_id=target_id,
            target_name=target_name,
            arguments=arguments or {},
            confidence=confidence,
            confidence_reasons=confidence_reasons or [],
            matched_rules=matched_rules or [],
            requires_clarification=requires_clarification,
            candidates=candidates or [],
        )

    def _candidates(self, step: LLMIntentStep, scene: SceneState | None, action_type: str) -> list[dict[str, Any]]:
        if not scene or not step.target_text or action_type in {"status_check", "table_talk", "sleep", "rest_short"}:
            return []
        interactables = [self._candidate(entry) for entry in scene.interactables if isinstance(entry, dict)]
        exact = [item for item in interactables if item["name"] == step.target_text or step.target_text in item["aliases"]]
        if exact:
            return self._supported_or_all(exact, action_type)
        contains = [
            item
            for item in interactables
            if self._target_text_matches_candidate(step.target_text, item)
        ]
        if contains:
            supported = [item for item in contains if self.parser._supports_action(item, action_type)]
            if supported:
                return supported
            return contains if action_type not in {"purchase", "refill_water", "force_open", "gather", "repair"} else []
        loose = [
            item
            for item in interactables
            if (
                self.parser._loose_target_match(step.target_text, item["name"])
                or any(self.parser._loose_target_match(step.target_text, alias) for alias in item["aliases"])
            )
            and self.parser._supports_action(item, action_type)
        ]
        if loose:
            return loose
        virtual = self._virtual_scene_target(step, scene, action_type)
        return [virtual] if virtual else []

    def _virtual_scene_target(self, step: LLMIntentStep, scene: SceneState, action_type: str) -> dict[str, Any] | None:
        if action_type != "enter_location":
            return None
        target = step.target_text.strip()
        if not target:
            return None
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects, scene.current_objective])
        if target not in scene_text:
            return None
        return {
            "id": f"virtual_location:{target}",
            "name": target,
            "type": "place",
            "affordances": ["进入", "观察"],
            "virtual": True,
        }

    def _supported_or_all(self, candidates: list[dict[str, Any]], action_type: str) -> list[dict[str, Any]]:
        supported = [item for item in candidates if self.parser._supports_action(item, action_type)]
        return supported or candidates

    def _candidate(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(entry.get("id") or ""),
            "name": str(entry.get("name") or ""),
            "type": str(entry.get("type") or "object"),
            "aliases": [str(item) for item in entry.get("aliases", []) if str(item).strip()],
            "affordances": [str(item) for item in entry.get("affordances", []) if str(item).strip()],
        }

    def _target_text_matches_candidate(self, target_text: str, item: dict[str, Any]) -> bool:
        if target_text in item["name"] or item["name"] in target_text:
            return True
        return any(target_text in alias or alias in target_text for alias in item.get("aliases", []))

    def _grouped_exploration_target(
        self,
        step: LLMIntentStep,
        candidates: list[dict[str, Any]],
        action_type: str,
    ) -> dict[str, Any] | None:
        if action_type not in {"observe", "search"} or not step.target_text:
            return None
        mentioned = [item for item in candidates if self._candidate_mentioned_by_text(step.target_text, item)]
        if len(mentioned) < 2:
            return None
        return {
            "id": "",
            "name": step.target_text,
            "type": "object",
            "aliases": [],
            "affordances": ["观察" if action_type == "observe" else "搜索"],
            "grouped_target_ids": [str(item.get("id") or "") for item in mentioned if item.get("id")],
        }

    def _candidate_mentioned_by_text(self, target_text: str, item: dict[str, Any]) -> bool:
        name = str(item.get("name") or "").strip()
        if name and name in target_text:
            return True
        return any(str(alias).strip() and str(alias).strip() in target_text for alias in item.get("aliases", []))

    def _arguments(self, step: LLMIntentStep, target: dict[str, Any], action_type: str) -> dict[str, Any]:
        arguments = dict(step.arguments)
        if step.style:
            arguments["style"] = step.style
        if step.scope:
            arguments["scope"] = step.scope
        if step.intensity:
            arguments["intensity"] = step.intensity
        if step.constraints:
            arguments["constraints"] = list(step.constraints)
        if action_type == "drink_water":
            arguments.setdefault("consumes", ["water"])
        if action_type == "eat_food":
            arguments.setdefault("consumes", ["food"])
        if action_type == "purchase":
            item_id = self._infer_purchase_item_id(step)
            if item_id:
                arguments.setdefault("item_id", item_id)
        if target.get("id"):
            arguments.setdefault("target_type", target.get("type", "object"))
        if target.get("grouped_target_ids"):
            arguments.setdefault("grouped_target_ids", list(target["grouped_target_ids"]))
        if target.get("virtual"):
            arguments["virtual_entry"] = True
        return arguments

    def _confidence_reasons(self, step: LLMIntentStep, target: dict[str, Any], action_type: str) -> list[str]:
        reasons = [f"llm_intent:{step.action_type}"]
        if action_type != step.action_type:
            reasons.append(f"normalized_action:{action_type}")
        if target:
            reasons.append("grounded_target")
            if self.parser._supports_action(target, action_type):
                reasons.append(f"affordance_match:{action_type}")
        return reasons

    def _matched_rules(self, step: LLMIntentStep, target: dict[str, Any], action_type: str) -> list[str]:
        rules = [f"llm_intent:{step.action_type}"]
        if action_type != step.action_type:
            rules.append(f"normalized_action:{action_type}")
        if step.target_text:
            rules.append(f"target_text:{step.target_text}")
        if target.get("id"):
            rules.append(f"target:{target['id']}")
        if target.get("grouped_target_ids"):
            rules.append("target:grouped")
        return rules

    def _step_text(self, step: LLMIntentStep) -> str:
        action_type = self._normalized_action_type(step)
        if step.target_text:
            return f"{action_type}:{step.target_text}"
        return action_type

    def _normalized_action_type(self, step: LLMIntentStep) -> str:
        if step.action_type != "repair":
            return step.action_type
        text = " ".join(
            [
                step.target_text,
                str(step.arguments.get("item") or ""),
                str(step.arguments.get("target") or ""),
                str(step.arguments.get("purpose") or ""),
            ]
        )
        if any(word in text for word in ["封住", "挡住", "加固", "堵住", "扎营"]):
            return "secure_shelter"
        return "repair"

    def _infer_purchase_item_id(self, step: LLMIntentStep) -> str:
        text = " ".join(
            [
                step.target_text,
                str(step.arguments.get("item") or ""),
                str(step.arguments.get("goods") or ""),
                str(step.arguments.get("cost") or ""),
            ]
        )
        return ""
