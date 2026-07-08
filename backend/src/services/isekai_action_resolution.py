from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import ParsedIsekaiAction
from backend.src.services.isekai_intent_planner import IsekaiIntentPlan
from backend.src.services.isekai_resources import IsekaiResourceService
from backend.src.services.isekai_risk import IsekaiRiskResult, IsekaiRiskService


@dataclass(frozen=True)
class IsekaiResolvedStep:
    text: str
    action: ParsedIsekaiAction
    delta: dict[str, Any] = field(default_factory=dict)
    risk: IsekaiRiskResult | None = None
    result_text: str = ""
    blocked: bool = False
    alternatives: list[str] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
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
        steps: list[IsekaiResolvedStep] = []
        total_delta = self._empty_delta()
        stopped = False

        for planned in plan.steps:
            action = self.preconditions.check(planned.action, current_scene)
            if action.action_type in {"condition_failed", "clarification"}:
                step = IsekaiResolvedStep(
                    text=planned.text,
                    action=action,
                    delta={"time_cost_minutes": 0, "advances_time": False, "visible_events": []},
                    result_text=action.reason,
                    blocked=True,
                    alternatives=[str(item) for item in action.arguments.get("alternatives", [])],
                )
                steps.append(step)
                stopped = True
                break

            action = self._with_resolved_time(action, current_scene, current_survival)
            updated_survival, delta = self.time.apply_time_and_survival(current_survival, action)
            resource_result = self.resources.apply(current_character, updated_survival, action, planned.text)
            delta.update(resource_result.delta)
            current_character, deterministic_changes = self._deterministic_inventory_changes(resource_result.character, action)
            if deterministic_changes:
                delta.setdefault("inventory_changes", [])
                delta["inventory_changes"].extend(deterministic_changes)
            current_world_state, current_economy, current_character, economy_delta, economy_block = self._apply_economy(
                current_world_state,
                current_economy,
                current_character,
                action,
                planned.text,
                current_survival,
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
            risk = self.risk.assess(action, updated_survival)
            current_scene = self._scene_after_action(current_scene, action, planned.text)
            current_scene, discovery_text, discovery_delta = self._apply_discovery_table(
                current_scene,
                action,
                current_world_state,
            )
            delta = self._append_delta(delta, discovery_delta)
            current_survival = updated_survival
            total_delta = self._merge_delta(total_delta, delta, risk)
            steps.append(
                IsekaiResolvedStep(
                    text=planned.text,
                    action=action,
                    delta=delta,
                    risk=risk,
                    result_text=discovery_text or self._result_text(action, current_scene),
                )
            )

        total_delta["time_cost_minutes"] = sum(int(step.delta.get("time_cost_minutes", 0)) for step in steps)
        total_delta["advances_time"] = any(bool(step.delta.get("advances_time")) for step in steps)
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

    def _scene_after_action(self, scene: SceneState, action: ParsedIsekaiAction, text: str = "") -> SceneState:
        if self.locations:
            target_node_id = str(action.arguments.get("target_node_id") or self.locations.node_id_for_text(text, ""))
            if action.action_type in {"enter_location", "travel", "repair"} and target_node_id:
                moved = self.locations.move(scene, target_node_id)
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

    def _apply_discovery_table(
        self,
        scene: SceneState,
        action: ParsedIsekaiAction,
        world_state: dict[str, Any],
    ) -> tuple[SceneState, str, dict[str, Any]]:
        if action.action_type not in {"search", "observe"} or not action.target_id:
            return scene, "", {}
        tables = self.content.discovery_tables(world_state) if self.content else {}
        entries = self._discovery_entries_for_action(tables, action, scene)
        if not entries:
            return scene, "", {}
        entry = self._matching_discovery_entry(entries, action.action_type)
        if not entry:
            return scene, "", {}
        result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
        narration = str(result.get("narration_fact") or "").strip()
        reveal_objects = result.get("reveal_objects") if isinstance(result.get("reveal_objects"), list) else []
        next_scene = scene
        if reveal_objects and self.content:
            next_scene, _metadata = self.content.materialize_scene_objects(next_scene, {"add": reveal_objects})
        clues = [str(item).strip() for item in result.get("clues", []) if str(item).strip()] if isinstance(result.get("clues"), list) else []
        rewards = [str(item).strip() for item in result.get("rewards", []) if str(item).strip()] if isinstance(result.get("rewards"), list) else []
        delta: dict[str, Any] = {}
        if clues:
            delta["clues"] = clues
        if rewards:
            delta["rewards"] = rewards
        if narration or clues or rewards or reveal_objects:
            delta["outcome_level"] = "partial_success"
            delta["narration_style"] = "exploration_discovery"
        return next_scene, narration, delta

    def _discovery_entries_for_action(
        self,
        tables: dict[str, list[dict[str, Any]]],
        action: ParsedIsekaiAction,
        scene: SceneState,
    ) -> list[dict[str, Any]]:
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

    def _matching_discovery_entry(self, entries: list[dict[str, Any]], action_type: str) -> dict[str, Any] | None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            trigger = entry.get("trigger") if isinstance(entry.get("trigger"), dict) else {}
            expected = str(trigger.get("action_type") or "").strip()
            if not expected or expected == action_type:
                return entry
        return None

    def _apply_economy(
        self,
        world_state: dict[str, Any],
        economy_state: dict[str, Any],
        character: dict[str, Any],
        action: ParsedIsekaiAction,
        text: str,
        survival: dict[str, Any],
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
            result = self.economy.quote_bed(next_economy)
            next_economy = result.state
            delta.update({"rewards": result.rewards, "relationship_changes": result.relationship_changes})
        elif action.action_type == "repair" and self._is_inn_repair_action(action, text):
            next_world["pending_lodging_reward"] = True
            delta.update(
                {
                    "outcome_level": "key_success",
                    "rewards": ["修好松动锅把", "店主愿意兑现住宿报酬"],
                    "relationship_changes": [{"npc_id": "innkeeper_01", "name": "店主", "attitude": "愿意交易", "delta": 8}],
                    "clues": ["店主提到夜里镇墙外有异常低嚎"],
                }
            )
        elif action.action_type == "enter_location" and "领取住宿权" in text and next_world.get("pending_lodging_reward"):
            result = self.economy.grant_repair_reward(next_economy, valid_until=valid_until)
            next_economy = result.state
            next_world["pending_lodging_reward"] = False
            next_character = self._add_inventory(next_character, "二楼三号房钥匙")
            delta.update(
                {
                    "outcome_level": "key_success",
                    "rewards": result.rewards,
                    "entitlements": result.entitlements,
                    "relationship_changes": result.relationship_changes,
                    "inventory_changes": ["获得二楼三号房钥匙"],
                    "clues": ["夜里镇墙外有异常低嚎"],
                }
            )
        elif action.action_type == "purchase":
            offer = self._purchase_offer(action, world_state, text)
            item_id = self._purchase_item_id(action, text) if not offer else ""
            buyer_note = self._buyer_note_for_offer(offer) if offer else ("住宿费" if item_id == "inn_bed" else "热食")
            result = (
                self.economy.purchase_offer(next_economy, offer=offer, buyer_note=buyer_note, valid_until=valid_until)
                if offer
                else self.economy.purchase(next_economy, item_id=item_id, buyer_note=buyer_note, valid_until=valid_until)
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
                        "result_text": "你还没有明确要购买床位、热炖菜，还是别的东西；店主没有收钱。",
                        "alternatives": result.alternatives,
                    }
                    return next_world, next_economy, next_character, delta, block
                block = {
                    "result_text": f"你的铜币不够，还差 {result.shortfall_copper} 铜。",
                    "alternatives": result.alternatives,
                }
            else:
                if item_id == "inn_bed":
                    next_character = self._add_inventory(next_character, "二楼三号房钥匙")
                    delta.setdefault("inventory_changes", []).append("获得二楼三号房钥匙")
                for item in self._offer_inventory_items(offer):
                    next_character = self._add_inventory(next_character, item)
                    delta.setdefault("inventory_changes", []).append(f"获得{item}")
                delta.update(
                    {
                        "outcome_level": "key_success" if item_id == "inn_bed" else "normal_success",
                        "rewards": result.rewards,
                        "entitlements": result.entitlements,
                        "relationship_changes": result.relationship_changes,
                    }
                )
        elif action.action_type == "eat_meal":
            delta.update({"rewards": ["吃下一碗热炖菜"], "outcome_level": "normal_success"})
        elif "暗夜狼" in text:
            delta.update({"clues": ["暗夜狼的低嚎来自镇墙外北侧"], "outcome_level": "partial_success"})

        return next_world, next_economy, next_character, delta, block

    def _is_inn_repair_action(self, action: ParsedIsekaiAction, text: str = "") -> bool:
        combined = " ".join(
            [
                text,
                action.target_name,
                str(action.arguments.get("item") or ""),
                str(action.arguments.get("target") or ""),
                str(action.arguments.get("target_node_id") or ""),
            ]
        )
        return any(word in combined for word in ["锅把", "后厨", "厨房"]) and not any(
            word in combined for word in ["斗篷", "缺口", "避风", "临时营地", "扎营"]
        )

    def _purchase_item_id(self, action: ParsedIsekaiAction, text: str = "") -> str:
        explicit = str(action.arguments.get("item_id") or "").strip()
        if explicit:
            return explicit
        combined = " ".join(
            [
                text,
                action.target_name,
                str(action.arguments.get("item") or ""),
                str(action.arguments.get("goods") or ""),
                str(action.arguments.get("cost") or ""),
            ]
        )
        if any(word in combined for word in ["床位", "住宿", "钥匙", "客房", "房间"]):
            return "inn_bed"
        if any(word in combined for word in ["炖菜", "热食", "饭", "餐"]):
            return "stew_meal"
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

    def _add_inventory(self, character: dict[str, Any], item: str) -> dict[str, Any]:
        inventory = [str(value) for value in character.get("inventory", [])]
        if item not in inventory:
            inventory.append(item)
        return {**character, "inventory": inventory}

    def _deterministic_inventory_changes(
        self,
        character: dict[str, Any],
        action: ParsedIsekaiAction,
    ) -> tuple[dict[str, Any], list[str]]:
        if action.action_type != "search" or action.target_name != "货袋":
            return character, []
        inventory = [str(item) for item in character.get("inventory", [])]
        item = "潮湿干粮 x1"
        if item not in inventory:
            inventory.append(item)
            return {**character, "inventory": inventory}, [f"获得{item}"]
        return character, []

    def _enter_location(self, scene: SceneState, action: ParsedIsekaiAction) -> SceneState:
        target = self._target(scene, action.target_id) or {}
        target_name = action.target_name or str(target.get("name") or "新地点")
        destination_objects = target.get("destination_objects")
        if not isinstance(destination_objects, list) or not destination_objects:
            destination_objects = self._default_destination_objects(target_name)
        environment = str(target.get("destination_environment") or self._default_destination_environment(target_name))
        next_scene = SceneState(
            location=target_name,
            environment=environment,
            important_objects=[str(item) for item in destination_objects if str(item).strip()],
            npcs=[],
            current_objective=f"确认{target_name}内有哪些可用资源和危险。",
            world_changes=[*scene.world_changes, f"位置从{scene.location}推进到{target_name}。"][-12:],
            interactables=[],
            suggested_actions=[],
            npc_states=scene.npc_states,
        )
        return self._project_if_needed(next_scene, action.action_type)

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

    def _default_destination_objects(self, target_name: str) -> list[str]:
        if "灰橡镇" in target_name:
            return ["街边旅店", "镇门口告示板", "守门棚", "避雨屋檐"]
        if "镇" in target_name:
            return ["街边旅店", "镇门口告示板", "巡逻民兵", "避雨屋檐"]
        if "车厢" in target_name or "马车" in target_name:
            return ["货袋", "破损木箱", "黑暗角落", "狭窄破口"]
        if "哨塔" in target_name:
            return ["旧火堆", "地基缝隙", "避风角落", "墙体缺口", "墙角兽毛"]
        if "小屋" in target_name:
            return ["木箱", "雨水桶", "倒塌木柜", "半开的地窖门", "黑暗角落", "墙上的抓痕"]
        return ["周围环境"]

    def _default_destination_environment(self, target_name: str) -> str:
        if "灰橡镇" in target_name:
            return "灰橡镇门内的泥街被阴雨压得发暗，低矮屋檐下挤着避雨的旅人，街边旅店的烟囱正冒出潮湿柴烟。"
        if "镇" in target_name:
            return f"{target_name}门内街道潮湿拥挤，旅店招牌、告示板和巡逻身影都能立刻看见。"
        if "车厢" in target_name or "马车" in target_name:
            return "侧翻车厢内部潮湿狭窄，座椅下压着货袋，破损木箱旁有黑暗角落。"
        if "哨塔" in target_name:
            return "坍塌的石砌哨塔内部漏着冷风，旧火堆旁有灰烬，地基缝隙透出潮气，避风角落和墙体缺口都需要确认。"
        if "小屋" in target_name:
            return "小屋内空气潮湿，角落里有木箱和接雨水的木桶，倒塌木柜与黑暗角落都可能藏着风险。"
        return f"{target_name}内部光线复杂，能看见几处尚未确认的物件。"

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
            return "你和店主讨价还价，确认今晚床位报价为 3 铜；他仍戒备，但愿意谈交易。"
        if action.action_type == "purchase":
            return "你支付铜币，换取明确的住宿权益和钥匙。"
        if action.action_type == "secure_shelter":
            return f"你处理{target}，用能找到的遮挡物压住漏风处，临时营地比刚才更稳，但火光仍需要控制。"
        if action.action_type == "repair" and self._is_inn_repair_action(action):
            return "你花了约 15 分钟修好松动锅把，后厨蒸汽重新稳定，店主愿意用住宿权抵这次帮忙。"
        if action.action_type == "repair":
            return f"你修整{target}，让它暂时可用，但没有触发额外报酬。"
        if action.action_type == "eat_meal":
            return "你坐在火塘边吃下热炖菜，胃里暖起来，疲惫稍微退开。"
        if "暗夜狼" in str(action.arguments):
            return "你捕捉到暗夜狼的动静。"
        if action.action_type == "search" and target == "货袋":
            return "你搜索货袋，找到一小份还能入口的潮湿干粮，但翻动布袋制造了细碎声响。"
        if action.action_type == "travel":
            return "你连夜赶路，距离推进更快，但黑暗让迷路、野兽和巡逻风险上升。"
        return action.reason
