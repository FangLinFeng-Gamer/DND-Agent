from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import ParsedIsekaiAction
from backend.src.services.isekai_intent_planner import IsekaiIntentPlan
from backend.src.services.isekai_resources import IsekaiResourceService
from backend.src.services.isekai_risk import IsekaiRiskResult, IsekaiRiskService
from backend.src.services.isekai_scene_navigation import NavigationResult


@dataclass(frozen=True)
class IsekaiResolvedStep:
    text: str
    action: ParsedIsekaiAction
    delta: dict[str, Any] = field(default_factory=dict)
    risk: IsekaiRiskResult | None = None
    result_text: str = ""
    blocked: bool = False
    alternatives: list[str] = field(default_factory=list)
    navigation: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        payload = {
            "text": self.text,
            "action_type": self.action.action_type,
            "target_id": self.action.target_id,
            "target_name": self.action.target_name,
            "arguments": self.action.arguments,
            "time_cost_minutes": int(self.delta.get("time_cost_minutes", 0)),
            "survival_delta": self.delta,
            "risk": asdict(self.risk) if self.risk else {"deltas": {}, "summary": "", "tags": []},
            "result": self.result_text,
            "blocked": self.blocked,
            "alternatives": list(self.alternatives),
        }
        if self.navigation:
            payload["navigation"] = dict(self.navigation)
        return payload


@dataclass(frozen=True)
class IsekaiActionResolutionResult:
    plan: IsekaiIntentPlan
    steps: list[IsekaiResolvedStep]
    scene: SceneState
    survival: dict[str, Any]
    character: dict[str, Any]
    world_state: dict[str, Any]
    delta: dict[str, Any]
    stopped: bool = False


class IsekaiActionResolutionEngine:
    def __init__(
        self,
        time_service: Any,
        preconditions: Any,
        resources: IsekaiResourceService,
        risk: IsekaiRiskService,
        projector: Any,
        locations: Any = None,
        economy: Any = None,
        time_cost: Any = None,
        content: Any = None,
        navigation: Any = None,
    ):
        self.time = time_service
        self.preconditions = preconditions
        self.resources = resources
        self.risk = risk
        self.projector = projector
        self.locations = locations
        self.economy = economy
        self.time_cost = time_cost
        self.content = content
        self.navigation = navigation

    def resolve(
        self,
        plan: IsekaiIntentPlan,
        scene: SceneState,
        survival: dict[str, Any],
        character: dict[str, Any],
        world_state: dict[str, Any] | None = None,
    ) -> IsekaiActionResolutionResult:
        current_scene = scene
        current_survival = dict(survival)
        current_character = dict(character)
        current_world_state = dict(world_state or {})
        current_economy = self.economy.ensure_state(current_world_state.get("isekai_economy"), current_character) if self.economy else {}
        active_locations = (
            self.locations.for_world_state(current_world_state)
            if self.locations and hasattr(self.locations, "for_world_state")
            else self.locations
        )
        steps: list[IsekaiResolvedStep] = []
        total_delta = self._empty_delta()
        stopped = False

        for planned in plan.steps:
            action, navigation_payload = self._resolve_navigation(planned.action, planned.text, current_scene, current_world_state)
            action = self.preconditions.check(action, current_scene)
            if action.action_type in {"condition_failed", "clarification"}:
                step = IsekaiResolvedStep(
                    text=planned.text,
                    action=action,
                    delta={"time_cost_minutes": 0, "advances_time": False, "visible_events": []},
                    result_text=action.reason,
                    blocked=True,
                    alternatives=[str(item) for item in action.arguments.get("alternatives", [])],
                    navigation=navigation_payload,
                )
                steps.append(step)
                stopped = True
                break

            action = self._with_resolved_time(action, current_scene, current_survival)
            updated_survival, delta = self.time.apply_time_and_survival(current_survival, action)
            resource_result = self.resources.apply(current_character, updated_survival, action, planned.text)
            delta.update(resource_result.delta)
            risk = self.risk.assess(action, updated_survival)
            current_scene = self._scene_after_action(current_scene, action, planned.text, active_locations, current_world_state)
            current_scene, current_character, discovery_text, discovery_delta = self._apply_discovery_table(
                current_scene,
                action,
                current_world_state,
                resource_result.character,
            )
            delta = self._append_delta(delta, discovery_delta)
            current_world_state, current_economy, current_character, economy_delta, economy_block = self._apply_economy(
                current_world_state,
                current_economy,
                current_character,
                action,
                planned.text,
                current_survival,
                current_scene,
            )
            delta.update(economy_delta)
            if economy_block:
                step = IsekaiResolvedStep(
                    text=planned.text,
                    action=action,
                    delta=delta,
                    result_text=economy_block["result_text"],
                    blocked=True,
                    alternatives=economy_block.get("alternatives", []),
                )
                total_delta = self._merge_delta(total_delta, delta, IsekaiRiskResult())
                steps.append(step)
                stopped = True
                break
            current_survival = updated_survival
            total_delta = self._merge_delta(total_delta, delta, risk)
            result_text = discovery_text or str(delta.pop("_result_text", "") or "") or self._result_text(action, current_scene)
            steps.append(
                IsekaiResolvedStep(
                    text=planned.text,
                    action=action,
                    delta=delta,
                    risk=risk,
                    result_text=result_text,
                    navigation=navigation_payload,
                )
            )

        total_delta["time_cost_minutes"] = sum(int(step.delta.get("time_cost_minutes", 0)) for step in steps)
        total_delta["advances_time"] = any(bool(step.delta.get("advances_time")) for step in steps)
        total_delta["visible_events"] = self._summarized_visible_events(total_delta)
        state = dict(current_survival.get("state") or {})
        state["last_time_delta_minutes"] = total_delta["time_cost_minutes"]
        state["last_time_reason"] = "compound" if len(steps) > 1 else (steps[0].action.survival_intent if steps else "none")
        current_survival["state"] = state
        current_survival["last_action_type"] = "compound" if len(steps) > 1 else (steps[0].action.action_type if steps else "table_talk")
        current_survival["location"] = current_scene.location
        return IsekaiActionResolutionResult(
            plan=plan,
            steps=steps,
            scene=current_scene,
            survival=current_survival,
            character=current_character,
            world_state={**current_world_state, "isekai_economy": current_economy},
            delta=total_delta,
            stopped=stopped,
        )

    def _summarized_visible_events(self, delta: dict[str, Any]) -> list[str]:
        events = [str(event) for event in delta.get("visible_events", []) if str(event).strip()]
        non_time_events = [
            event
            for event in events
            if not event.startswith("时间推进了约 ")
        ]
        result: list[str] = []
        minutes = int(delta.get("time_cost_minutes", 0))
        if minutes > 0:
            result.append(f"时间推进了约 {self.time.format_minutes(minutes)}。")
        result.extend(dict.fromkeys(non_time_events))
        return result

    def _empty_delta(self) -> dict[str, Any]:
        return {
            "hunger": 0,
            "thirst": 0,
            "fatigue": 0,
            "sleep_need": 0,
            "temperature_risk": 0,
            "morale": 0,
            "hp_delta": 0,
            "inventory_changes": [],
            "status_effects_added": [],
            "status_effects_removed": [],
            "visible_events": [],
            "risk_change": {"noise": 0, "danger": 0, "exposure": 0, "opportunity": 0},
            "rewards": [],
            "entitlements": [],
            "relationship_changes": [],
            "clues": [],
            "outcome_level": "normal_success",
        }

    def _merge_delta(self, total: dict[str, Any], delta: dict[str, Any], risk: IsekaiRiskResult) -> dict[str, Any]:
        merged = dict(total)
        for key in ["hunger", "thirst", "fatigue", "sleep_need", "temperature_risk", "morale", "hp_delta"]:
            merged[key] = int(merged.get(key, 0)) + int(delta.get(key, 0))
        for key in ["inventory_changes", "status_effects_added", "status_effects_removed", "visible_events"]:
            merged[key] = [*merged.get(key, []), *delta.get(key, [])]
        for key in ["rewards", "entitlements", "relationship_changes", "clues"]:
            merged[key] = [*merged.get(key, []), *delta.get(key, [])]
        if delta.get("outcome_level") == "failure":
            merged["outcome_level"] = "failure"
        elif delta.get("outcome_level") == "key_success" and merged.get("outcome_level") != "failure":
            merged["outcome_level"] = "key_success"
        elif delta.get("outcome_level") == "partial_success" and merged.get("outcome_level") == "normal_success":
            merged["outcome_level"] = "partial_success"
        if "shortfall_copper" in delta:
            merged["shortfall_copper"] = delta["shortfall_copper"]
        if delta.get("narration_style"):
            merged["narration_style"] = delta["narration_style"]
        risk_change = dict(merged.get("risk_change") or {})
        for key, value in risk.deltas.items():
            risk_change[key] = int(risk_change.get(key, 0)) + int(value)
        merged["risk_change"] = risk_change
        return merged

    def _append_delta(self, base: dict[str, Any], addition: dict[str, Any]) -> dict[str, Any]:
        if not addition:
            return base
        merged = dict(base)
        for key in ["inventory_changes", "status_effects_added", "status_effects_removed", "visible_events"]:
            if key in addition:
                merged[key] = [*merged.get(key, []), *addition.get(key, [])]
        for key in ["rewards", "entitlements", "relationship_changes", "clues"]:
            if key in addition:
                merged[key] = [*merged.get(key, []), *addition.get(key, [])]
        for key, value in addition.items():
            if key in {
                "inventory_changes",
                "status_effects_added",
                "status_effects_removed",
                "visible_events",
                "rewards",
                "entitlements",
                "relationship_changes",
                "clues",
            }:
                continue
            merged[key] = value
        return merged

    def _resolve_navigation(
        self,
        action: ParsedIsekaiAction,
        text: str,
        scene: SceneState,
        world_state: dict[str, Any],
    ) -> tuple[ParsedIsekaiAction, dict[str, Any]]:
        if not self.navigation or action.action_type not in {"enter_location", "travel", "leave_location"}:
            return action, {}
        action_with_text = replace(action, arguments={**action.arguments, "raw_text": text})
        result: NavigationResult = self.navigation.resolve(action_with_text, scene, world_state)
        if result.status == "not_navigation":
            return action_with_text, {}
        payload = result.payload()
        if result.status != "resolved":
            return self._navigation_failure(action_with_text, result), payload
        return self._action_with_route_plan(action_with_text, result), payload

    def _navigation_failure(self, action: ParsedIsekaiAction, result: NavigationResult) -> ParsedIsekaiAction:
        resolution = self.time.resolve_action_type("condition_failed")
        alternatives = list(result.alternatives)
        reason = result.reason or "当前移动目标无法被解析为合法路径。"
        if alternatives:
            reason = f"{reason} 可尝试：{'、'.join(alternatives)}。"
        return replace(
            action,
            action_type=resolution.action_type,
            time_cost_minutes=resolution.time_cost_minutes,
            advances_time=resolution.advances_time,
            survival_intent=resolution.survival_intent,
            reason=reason,
            arguments={
                **action.arguments,
                "failed_precondition": result.status,
                "navigation": result.payload(),
                "alternatives": alternatives,
            },
            confidence="high",
            confidence_reasons=[*action.confidence_reasons, f"navigation:{result.status}"],
            matched_rules=[*action.matched_rules, f"navigation:{result.status}"],
        )

    def _action_with_route_plan(self, action: ParsedIsekaiAction, result: NavigationResult) -> ParsedIsekaiAction:
        route_plan = {
            "navigation_intent": result.navigation_intent,
            "target_node_id": result.target_node_id,
            "target_name": result.target_name,
            "edge_ids": list(result.edge_ids),
            "status": result.status,
        }
        return replace(
            action,
            target_name=action.target_name or result.target_name,
            arguments={
                **action.arguments,
                "target_node_id": action.arguments.get("target_node_id") or result.target_node_id,
                "route_plan": route_plan,
                "navigation": result.payload(),
            },
            confidence_reasons=[*action.confidence_reasons, "navigation:resolved"],
            matched_rules=[*action.matched_rules, f"navigation:{result.navigation_intent}"],
        )

    def _with_resolved_time(
        self,
        action: ParsedIsekaiAction,
        scene: SceneState,
        survival: dict[str, Any],
    ) -> ParsedIsekaiAction:
        if not self.time_cost or not action.advances_time:
            return action
        scope = str(action.arguments.get("scope") or "")
        if not scope:
            return action
        modifiers = {
            "dark": any(word in scene.environment for word in ["黑", "暗", "夜"]) or str(survival.get("time_of_day") or "") in {"夜晚", "深夜"},
            "crowded": any(word in scene.environment for word in ["挤", "人群", "旅人"]),
        }
        minutes = self.time_cost.minutes(action.action_type, action.arguments, modifiers)
        return replace(action, time_cost_minutes=minutes)

    def _scene_after_action(
        self,
        scene: SceneState,
        action: ParsedIsekaiAction,
        text: str = "",
        locations: Any = None,
        world_state: dict[str, Any] | None = None,
    ) -> SceneState:
        locations = locations or self.locations
        route_plan = action.arguments.get("route_plan") if isinstance(action.arguments.get("route_plan"), dict) else {}
        route_target_node_id = str(route_plan.get("target_node_id") or "").strip()
        if action.action_type in {"enter_location", "travel", "leave_location"} and route_target_node_id:
            from_world = self._scene_from_world_node(scene, route_target_node_id, world_state or {})
            if from_world is not None:
                return from_world
            if route_target_node_id.startswith("scene_object:") and locations:
                content_node_id = locations.node_id_for_text(" ".join([text, action.target_name]), "")
                if content_node_id:
                    moved = locations.move(scene, content_node_id)
                    if moved.location != scene.location or moved.location_path != scene.location_path:
                        return moved
            if locations:
                moved = locations.move(scene, route_target_node_id)
                if moved.location != scene.location or moved.location_path != scene.location_path:
                    return moved
        if locations:
            target_node_id = str(action.arguments.get("target_node_id") or "")
            if action.action_type == "repair" and not target_node_id:
                target_node_id = str(locations.node_id_for_text(text, "") or "")
            if action.action_type in {"enter_location", "travel", "repair"} and target_node_id:
                moved = locations.move(scene, target_node_id)
                if moved.location != scene.location or moved.location_path != scene.location_path:
                    return moved
        if action.action_type == "enter_location":
            return self._enter_location(scene, action)
        if action.action_type == "approach":
            return self._mark_target_state(scene, action, "已靠近")
        if action.action_type == "force_open":
            return self._mark_target_state(scene, action, "已被强行打开", add_affordances=["进入", "观察"])
        if action.action_type in {"search", "observe"}:
            return self._project_if_needed(scene, action.action_type)
        return scene

    def _scene_from_world_node(
        self,
        previous_scene: SceneState,
        target_node_id: str,
        world_state: dict[str, Any],
    ) -> SceneState | None:
        node = self._world_node(world_state, target_node_id)
        if not node:
            return None
        path = self._node_location_path(node, target_node_id)
        location = str(path.get("display_name") or node.get("location") or node.get("name") or target_node_id)
        interactables = self._node_interactables(node)
        return SceneState(
            location=location,
            location_path=path,
            environment=str(node.get("environment") or previous_scene.environment),
            important_objects=[
                str(item)
                for item in node.get("important_objects", [])
                if str(item).strip()
            ]
            if isinstance(node.get("important_objects"), list)
            else [],
            npcs=[str(item) for item in node.get("npcs", []) if str(item).strip()] if isinstance(node.get("npcs"), list) else [],
            current_objective=str(node.get("current_objective") or node.get("objective") or "确认当前位置的可互动对象。"),
            world_changes=[*previous_scene.world_changes, f"位置从{previous_scene.location}推进到{location}。"][-12:],
            interactables=interactables,
            suggested_actions=[str(item) for item in node.get("suggested_actions", []) if str(item).strip()]
            if isinstance(node.get("suggested_actions"), list)
            else [],
            npc_states=previous_scene.npc_states,
        )

    def _world_node(self, world_state: dict[str, Any], target_node_id: str) -> dict[str, Any]:
        graph = world_state.get("scene_graph") if isinstance(world_state.get("scene_graph"), dict) else {}
        sources = [graph.get("nodes"), world_state.get("scene_nodes"), world_state.get("known_locations")]
        for source in sources:
            if isinstance(source, dict):
                iterable = source.values()
            elif isinstance(source, list):
                iterable = source
            else:
                iterable = []
            for raw in iterable:
                if isinstance(raw, dict) and str(raw.get("node_id") or "") == target_node_id:
                    return dict(raw)
        return {}

    def _node_location_path(self, node: dict[str, Any], target_node_id: str) -> dict[str, Any]:
        raw = node.get("location_path") if isinstance(node.get("location_path"), dict) else {}
        path = dict(raw)
        path.setdefault("node_id", target_node_id)
        if not path.get("display_name"):
            display_parts = [
                str(node.get("region") or ""),
                str(node.get("site") or ""),
                str(node.get("sublocation") or ""),
            ]
            display = " / ".join(part for part in display_parts if part)
            path["display_name"] = display or str(node.get("name") or node.get("location") or target_node_id)
        for key in ["region", "site", "sublocation", "parent_id"]:
            if key not in path and node.get(key):
                path[key] = str(node.get(key) or "")
        return path

    def _node_interactables(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ["interactables", "visible_objects"]:
            value = node.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, dict)]
        return []

    def _apply_discovery_table(
        self,
        scene: SceneState,
        action: ParsedIsekaiAction,
        world_state: dict[str, Any],
        character: dict[str, Any],
    ) -> tuple[SceneState, dict[str, Any], str, dict[str, Any]]:
        if action.action_type not in {"search", "observe"}:
            return scene, character, "", {}
        tables = self.content.discovery_tables(world_state) if self.content else {}
        entries = self._discovery_entries_for_action(tables, action, scene)
        if not entries:
            return self._fallback_object_discovery(scene, character, action)
        matching_entries = self._matching_discovery_entries(entries, action.action_type)
        if not matching_entries:
            return self._fallback_object_discovery(scene, character, action)
        narrations: list[str] = []
        reveal_objects: list[Any] = []
        reveal_edges: list[str] = []
        clues: list[str] = []
        rewards: list[str] = []
        items_added: list[str] = []
        for entry in matching_entries[:6]:
            result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
            narration = str(result.get("narration_fact") or "").strip()
            if narration:
                narrations.append(narration)
            if isinstance(result.get("reveal_objects"), list):
                reveal_objects.extend(result["reveal_objects"])
            if isinstance(result.get("reveal_edges"), list):
                reveal_edges.extend(str(item).strip() for item in result["reveal_edges"] if str(item).strip())
            if isinstance(result.get("clues"), list):
                clues.extend(str(item).strip() for item in result["clues"] if str(item).strip())
            if isinstance(result.get("rewards"), list):
                rewards.extend(str(item).strip() for item in result["rewards"] if str(item).strip())
            if isinstance(result.get("items_added"), list):
                items_added.extend(str(item).strip() for item in result["items_added"] if str(item).strip())
        narration_text = " ".join(dict.fromkeys(narrations))
        reveal_edges = list(dict.fromkeys(reveal_edges))
        clues = list(dict.fromkeys(clues))
        rewards = list(dict.fromkeys(rewards))
        items_added = list(dict.fromkeys(items_added))
        next_scene = scene
        reveal_payloads = self._discovery_reveal_object_payloads(reveal_objects, world_state)
        if reveal_payloads and self.content:
            next_scene, _metadata = self.content.materialize_scene_objects(next_scene, {"add": reveal_payloads})
        if reveal_edges:
            self._reveal_scene_edges(world_state, reveal_edges)
        next_character = dict(character)
        delta: dict[str, Any] = {}
        if clues:
            delta["clues"] = clues
        if rewards:
            delta["rewards"] = rewards
        for item in items_added:
            next_character = self._add_inventory(next_character, item)
        if items_added:
            delta["inventory_changes"] = [f"获得{item}" for item in items_added]
        if narration_text or clues or rewards or reveal_payloads or reveal_edges or items_added:
            delta["outcome_level"] = "partial_success"
            delta["narration_style"] = "exploration_discovery"
        return next_scene, next_character, narration_text, delta

    def _fallback_object_discovery(
        self,
        scene: SceneState,
        character: dict[str, Any],
        action: ParsedIsekaiAction,
    ) -> tuple[SceneState, dict[str, Any], str, dict[str, Any]]:
        detail = self._target_detail_text(action, scene)
        if not detail:
            return scene, character, "", {}
        target = action.target_name or "当前目标"
        verb = "逐项检查" if action.action_type == "observe" else "仔细搜索"
        return scene, character, f"你{verb}{target}：{detail}", {
            "outcome_level": "partial_success",
            "narration_style": "exploration_discovery",
        }

    def _discovery_reveal_object_payloads(self, reveal_objects: list[Any], world_state: dict[str, Any]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for item in reveal_objects:
            if isinstance(item, dict):
                payload = dict(item)
            else:
                payload = self._scene_object_by_id(world_state, str(item).strip())
            if not payload:
                continue
            payload["visibility"] = "visible"
            payload.setdefault("presence", "current")
            payloads.append(payload)
        return payloads

    def _scene_object_by_id(self, world_state: dict[str, Any], object_id: str) -> dict[str, Any]:
        if not object_id:
            return {}
        objects = world_state.get("scene_objects")
        candidates = objects.values() if isinstance(objects, dict) else objects if isinstance(objects, list) else []
        for item in candidates:
            if isinstance(item, dict) and str(item.get("id") or "") == object_id:
                return dict(item)
        return {}

    def _reveal_scene_edges(self, world_state: dict[str, Any], edge_ids: list[str]) -> None:
        edge_id_set = set(edge_ids)
        graph = world_state.get("scene_graph") if isinstance(world_state.get("scene_graph"), dict) else {}
        edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
        for edge in edges:
            if isinstance(edge, dict) and str(edge.get("id") or "") in edge_id_set:
                edge["known_to_player"] = True
                if str(edge.get("access") or "") == "hidden":
                    edge["access"] = "open"

    def _discovery_entries_for_action(
        self,
        tables: dict[str, list[dict[str, Any]]],
        action: ParsedIsekaiAction,
        scene: SceneState,
    ) -> list[dict[str, Any]]:
        grouped_ids = [
            str(item).strip()
            for item in action.arguments.get("grouped_target_ids", [])
            if str(item).strip()
        ] if isinstance(action.arguments.get("grouped_target_ids"), list) else []
        if grouped_ids:
            grouped_entries: list[dict[str, Any]] = []
            for target_id in grouped_ids:
                grouped_entries.extend(
                    entry
                    for entry in tables.get(target_id, [])
                    if self._discovery_entry_matches_scene(entry, scene)
                )
            if grouped_entries:
                return grouped_entries
        if action.target_id and action.target_id in tables:
            return [entry for entry in tables[action.target_id] if self._discovery_entry_matches_scene(entry, scene)]
        target_text = action.target_name or ""
        if not target_text:
            return []
        matches: list[dict[str, Any]] = []
        for entries in tables.values():
            for entry in entries:
                if self._discovery_entry_matches_target_text(entry, target_text) and self._discovery_entry_matches_scene(entry, scene):
                    matches.append(entry)
        return matches

    def _discovery_entry_matches_target_text(self, entry: dict[str, Any], target_text: str) -> bool:
        aliases = entry.get("_target_aliases") if isinstance(entry.get("_target_aliases"), list) else []
        return any(str(alias).strip() and str(alias).strip() in target_text for alias in aliases)

    def _discovery_entry_matches_scene(self, entry: dict[str, Any], scene: SceneState) -> bool:
        aliases = entry.get("_scene_aliases") if isinstance(entry.get("_scene_aliases"), list) else []
        if not aliases:
            return True
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects])
        return any(str(alias).strip() and str(alias).strip() in scene_text for alias in aliases)

    def _matching_discovery_entries(self, entries: list[dict[str, Any]], action_type: str) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            trigger = entry.get("trigger") if isinstance(entry.get("trigger"), dict) else {}
            expected = str(trigger.get("action_type") or "").strip()
            if not expected or expected == action_type:
                matched.append(entry)
        return matched

    def _apply_economy(
        self,
        world_state: dict[str, Any],
        economy_state: dict[str, Any],
        character: dict[str, Any],
        action: ParsedIsekaiAction,
        text: str,
        survival: dict[str, Any],
        scene: SceneState,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        if not self.economy:
            return world_state, economy_state, character, {}, None
        delta: dict[str, Any] = {}
        block: dict[str, Any] | None = None
        next_world = dict(world_state)
        next_economy = dict(economy_state)
        next_character = dict(character)
        valid_until = f"第{int(survival.get('day') or 1)}天清晨"

        if action.action_type == "negotiate":
            result = self.economy.quote_bed(next_economy, world_state=world_state)
            next_economy = result.state
            delta.update({"rewards": result.rewards, "relationship_changes": result.relationship_changes})
        elif action.action_type == "repair":
            repair_reward = (
                self.content.repair_reward_for_action(
                    target_id=action.target_id,
                    target_name=action.target_name,
                    action_text=text,
                    scene=scene,
                    world_state=world_state,
                )
                if self.content
                else {}
            )
            if repair_reward:
                next_world["pending_repair_reward_id"] = str(repair_reward.get("reward_id") or "")
                relationship_changes = [
                    dict(item)
                    for item in repair_reward.get("relationship_changes", [])
                    if isinstance(item, dict)
                ]
                clues = [str(item) for item in repair_reward.get("pending_clues", []) if str(item).strip()]
                rewards = [str(item) for item in repair_reward.get("pending_rewards", []) if str(item).strip()]
                delta.update(
                    {
                        "outcome_level": "key_success",
                        "rewards": rewards,
                        "relationship_changes": relationship_changes,
                        "clues": clues,
                        "_result_text": str(repair_reward.get("result_text") or ""),
                    }
                )
        elif action.action_type in {"enter_location", "short_dialogue", "negotiate"} and next_world.get("pending_repair_reward_id"):
            reward_id = str(next_world.get("pending_repair_reward_id") or "")
            delta.update(
                {"outcome_level": "key_success"}
            )
            result = self.economy.grant_repair_reward(
                next_economy,
                reward_id=reward_id,
                valid_until=valid_until,
                world_state=world_state,
            )
            next_economy = result.state
            next_world["pending_repair_reward_id"] = ""
            for item in self._repair_reward_items(reward_id, world_state):
                next_character = self._add_inventory(next_character, item)
            delta.update(
                {
                    "outcome_level": "key_success",
                    "rewards": result.rewards,
                    "entitlements": result.entitlements,
                    "relationship_changes": result.relationship_changes,
                    "inventory_changes": [f"获得{item}" for item in self._repair_reward_items(reward_id, world_state)],
                }
            )
        elif action.action_type == "purchase":
            offer = self._purchase_offer(action, world_state, text)
            item_id = self._purchase_item_id(action, text) if not offer else ""
            buyer_note = self._buyer_note_for_offer(offer) if offer else "购买"
            result = (
                self.economy.purchase_offer(next_economy, offer=offer, buyer_note=buyer_note, valid_until=valid_until)
                if offer
                else self.economy.purchase(
                    next_economy,
                    item_id=item_id,
                    buyer_note=buyer_note,
                    valid_until=valid_until,
                    world_state=world_state,
                )
            )
            next_economy = result.state
            if not result.success:
                delta.update(
                    {
                        "outcome_level": "failure",
                        "shortfall_copper": result.shortfall_copper,
                        "rewards": [],
                    }
                )
                if result.error_code == "unknown_item":
                    block = {
                        "result_text": "你还没有明确要购买的商品或服务；对方没有收钱。",
                        "alternatives": result.alternatives,
                    }
                    return next_world, next_economy, next_character, delta, block
                block = {
                    "result_text": f"你的铜币不够，还差 {result.shortfall_copper} 铜。",
                    "alternatives": result.alternatives,
                }
            else:
                if item_id and not offer and self.content:
                    offer = self.content.offer_by_id(item_id, world_state)
                for item in self._offer_inventory_items(offer):
                    next_character = self._add_inventory(next_character, item)
                    delta.setdefault("inventory_changes", []).append(f"获得{item}")
                delta.update(
                    {
                        "outcome_level": "key_success" if result.entitlements else "normal_success",
                        "rewards": result.rewards,
                        "entitlements": result.entitlements,
                        "relationship_changes": result.relationship_changes,
                    }
                )
        elif action.action_type == "eat_meal":
            offer = self.content.offer_by_id(str(action.arguments.get("item_id") or ""), world_state) if self.content else {}
            meal_name = str(offer.get("name") or action.target_name or "这份热食").strip()
            delta.update(
                {
                    "outcome_level": "normal_success",
                    "_result_text": f"你吃完{meal_name}，身体状态稍微稳定下来。",
                }
            )

        return next_world, next_economy, next_character, delta, block

    def _purchase_item_id(self, action: ParsedIsekaiAction, text: str = "") -> str:
        explicit = str(action.arguments.get("item_id") or "").strip()
        if explicit:
            return explicit
        return ""

    def _purchase_offer(self, action: ParsedIsekaiAction, world_state: dict[str, Any], text: str = "") -> dict[str, Any]:
        if not self.content:
            return {}
        offers_by_owner = self.content.merchant_offers(world_state)
        offer_id = str(action.arguments.get("offer_id") or "").strip()
        if offer_id:
            for offers in offers_by_owner.values():
                for offer in offers:
                    if isinstance(offer, dict) and str(offer.get("offer_id") or "") == offer_id:
                        return dict(offer)
            return {}
        target_text = " ".join(
            [
                text,
                action.target_name,
                str(action.arguments.get("item") or ""),
                str(action.arguments.get("goods") or ""),
            ]
        )
        owner_ids = [action.target_id] if action.target_id else list(offers_by_owner.keys())
        for owner_id in owner_ids:
            for offer in offers_by_owner.get(owner_id, []):
                if not isinstance(offer, dict):
                    continue
                name = str(offer.get("name") or offer.get("item") or "").strip()
                aliases = [str(item).strip() for item in offer.get("aliases", []) if str(item).strip()] if isinstance(offer.get("aliases"), list) else []
                if name and name in target_text:
                    return dict(offer)
                if any(alias and alias in target_text for alias in aliases):
                    return dict(offer)
        return {}

    def _buyer_note_for_offer(self, offer: dict[str, Any]) -> str:
        name = str((offer or {}).get("name") or (offer or {}).get("item") or "").strip()
        return f"购买{name}" if name else "购买"

    def _offer_inventory_items(self, offer: dict[str, Any]) -> list[str]:
        grants = offer.get("grants") if isinstance(offer, dict) and isinstance(offer.get("grants"), dict) else {}
        return [str(item).strip() for item in grants.get("items", []) if str(item).strip()] if isinstance(grants.get("items"), list) else []

    def _repair_reward_items(self, reward_id: str, world_state: dict[str, Any]) -> list[str]:
        reward = self.content.repair_reward(reward_id, world_state) if self.content else {}
        return [str(item).strip() for item in reward.get("items", []) if str(item).strip()] if isinstance(reward.get("items"), list) else []

    def _add_inventory(self, character: dict[str, Any], item: str) -> dict[str, Any]:
        inventory = [str(value) for value in character.get("inventory", [])]
        if item not in inventory:
            inventory.append(item)
        return {**character, "inventory": inventory}

    def _enter_location(self, scene: SceneState, action: ParsedIsekaiAction) -> SceneState:
        target = self._target(scene, action.target_id) or {}
        target_name = action.target_name or str(target.get("name") or "新地点")
        template = self.content.destination_template(target_name) if self.content else {}
        destination_objects = self._destination_scene_objects(target, template)
        important_objects = self._destination_important_objects(target, template, destination_objects)
        environment = str(
            target.get("destination_environment")
            or template.get("environment")
            or f"{target_name}内部光线复杂，能看见几处尚未确认的物件。"
        )
        next_scene = SceneState(
            location=target_name,
            environment=environment,
            important_objects=important_objects,
            npcs=[],
            current_objective=f"确认{target_name}内有哪些可用资源和危险。",
            world_changes=[*scene.world_changes, f"位置从{scene.location}推进到{target_name}。"][-12:],
            interactables=[],
            suggested_actions=[],
            npc_states=scene.npc_states,
        )
        if destination_objects and self.content:
            next_scene, _metadata = self.content.materialize_scene_objects(next_scene, {"add": destination_objects})
        return self._project_if_needed(next_scene, action.action_type)

    def _destination_scene_objects(self, target: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
        explicit = target.get("destination_scene_objects")
        if isinstance(explicit, list) and explicit:
            return [dict(item) for item in explicit if isinstance(item, dict)]
        template_objects = template.get("scene_objects") if isinstance(template, dict) else None
        if isinstance(template_objects, list) and template_objects:
            return [dict(item) for item in template_objects if isinstance(item, dict)]
        names = target.get("destination_objects")
        if isinstance(names, list) and self.content:
            return self.content.scene_objects_from_names([str(item) for item in names])
        return []

    def _destination_important_objects(
        self,
        target: dict[str, Any],
        template: dict[str, Any],
        scene_objects: list[dict[str, Any]],
    ) -> list[str]:
        explicit = target.get("destination_objects")
        if isinstance(explicit, list) and explicit:
            return [str(item) for item in explicit if str(item).strip()]
        template_important = template.get("important_objects") if isinstance(template, dict) else None
        if isinstance(template_important, list) and template_important:
            return [str(item) for item in template_important if str(item).strip()]
        names = [str(item.get("name") or "") for item in scene_objects if isinstance(item, dict)]
        return [name for name in names if name]

    def _mark_target_state(
        self,
        scene: SceneState,
        action: ParsedIsekaiAction,
        state: str,
        add_affordances: list[str] | None = None,
    ) -> SceneState:
        next_interactables: list[dict[str, Any]] = []
        for entry in scene.interactables:
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            if str(item.get("id") or "") == action.target_id:
                existing = str(item.get("state") or "").strip()
                item["state"] = f"{state}；{existing}" if existing else state
                affordances = [str(value) for value in item.get("affordances", [])]
                for affordance in add_affordances or []:
                    if affordance not in affordances:
                        affordances.append(affordance)
                if affordances:
                    item["affordances"] = affordances
            next_interactables.append(item)
        return scene.model_copy(update={"interactables": next_interactables or scene.interactables})

    def _project_if_needed(self, scene: SceneState, action_type: str) -> SceneState:
        interactables, suggestions = self.projector.project(scene, action_type)
        if not interactables and not suggestions:
            return scene
        return scene.model_copy(update={"interactables": interactables or scene.interactables, "suggested_actions": suggestions or scene.suggested_actions})

    def _target(self, scene: SceneState, target_id: str) -> dict[str, Any] | None:
        for entry in scene.interactables:
            if isinstance(entry, dict) and str(entry.get("id") or "") == target_id:
                return entry
        return None

    def _result_text(self, action: ParsedIsekaiAction, scene: SceneState | None = None) -> str:
        target = action.target_name or "当前目标"
        if action.action_type == "drink_water":
            return "你喝了水，水囊里的水减少，水分压力缓解。"
        if action.action_type == "eat_food":
            return "你吃下干粮，饱腹压力缓解，但随身补给减少。"
        if action.action_type == "approach":
            style = str(action.arguments.get("style") or "normal")
            if style == "careful":
                return f"你小心靠近{target}，优先确认落脚点和声响。"
            if style == "quiet":
                return f"你压低声响靠近{target}，尽量不暴露自己。"
            return f"你靠近{target}，后续可以更直接互动。"
        if action.action_type == "enter_location":
            if "no_search" in action.arguments.get("constraints", []):
                return f"你进入{target}，但克制住翻找冲动，只先确认站位。"
            return f"你进入{target}。"
        if action.action_type == "hide":
            return "你听到动静后先隐藏身形，避免立刻暴露。"
        if action.action_type == "avoid":
            return "你选择避开危险动线，放弃直接接触。"
        if action.action_type == "force_open":
            return f"你强行处理{target}，更快打开障碍，但声响明显。"
        if action.action_type == "negotiate":
            return "你确认了当前报价和交易条件，对方的态度仍取决于你的身份、筹码和现场压力。"
        if action.action_type == "purchase":
            return "你支付铜币，换取明确的住宿权益和钥匙。"
        if action.action_type == "secure_shelter":
            return f"你处理{target}，用能找到的遮挡物压住漏风处，临时营地比刚才更稳，但火光仍需要控制。"
        if action.action_type == "repair":
            return f"你修整{target}，让它暂时可用，但没有触发额外报酬。"
        if action.action_type == "eat_meal":
            return "你完成了用餐，身体状态稍微稳定下来。"
        if action.action_type == "travel":
            return "你连夜赶路，距离推进更快，但黑暗让迷路、野兽和巡逻风险上升。"
        if action.action_type in {"observe", "search"} and action.target_name:
            verb = "逐项检查" if action.action_type == "observe" else "仔细搜索"
            detail = self._target_detail_text(action, scene)
            if detail:
                return f"你{verb}{target}：{detail}"
            return f"你{verb}{target}，暂时没有发现可以立即入账的新线索。"
        return action.reason

    def _target_detail_text(self, action: ParsedIsekaiAction, scene: SceneState | None = None) -> str:
        if scene is None:
            return ""
        targets: list[dict[str, Any]] = []
        grouped_ids = [
            str(item).strip()
            for item in action.arguments.get("grouped_target_ids", [])
            if str(item).strip()
        ] if isinstance(action.arguments.get("grouped_target_ids"), list) else []
        if grouped_ids:
            for target_id in grouped_ids:
                target = self._target(scene, target_id)
                if target:
                    targets.append(target)
        elif action.target_id:
            target = self._target(scene, action.target_id)
            if target:
                targets.append(target)
        details: list[str] = []
        for target in targets[:4]:
            name = str(target.get("name") or "").strip()
            description = str(target.get("description") or target.get("state") or "").strip()
            if name and description:
                details.append(f"{name}：{description}")
            elif name:
                details.append(f"{name}没有立刻呈现新的变化")
        return "；".join(details)
