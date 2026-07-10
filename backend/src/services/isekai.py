from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, is_dataclass, replace
from typing import Any

from backend.src.agent.dm.output import chunk_text, extract_narration_text
from backend.src.db.sqlite import SQLiteStore, encode_json
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, DMAdvanceResponse, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelRecord
from backend.src.schemas.isekai import IsekaiCharacterOut, IsekaiSurvivalStateOut
from backend.src.services.isekai_action_parser import IsekaiActionParser
from backend.src.services.isekai_action_grounder import IsekaiActionGrounder
from backend.src.services.isekai_action_policy import IsekaiActionPolicyService
from backend.src.services.isekai_action_preconditions import IsekaiActionPreconditionService
from backend.src.services.isekai_action_resolution import IsekaiActionResolutionEngine
from backend.src.services.adventures import AdventureService
from backend.src.services.isekai_consequences import IsekaiConsequenceResolver
from backend.src.services.isekai_content import IsekaiContentService
from backend.src.services.isekai_economy import IsekaiEconomyService
from backend.src.services.isekai_events import IsekaiWorldEventDirector
from backend.src.services.isekai_fallback_narrator import IsekaiFallbackNarrator
from backend.src.services.isekai_interactables import IsekaiInteractableProjector
from backend.src.services.isekai_intent_interpreter import IsekaiIntentInterpreter
from backend.src.services.isekai_intent_planner import IsekaiIntentPlan, IsekaiIntentPlanner
from backend.src.services.isekai_intent_schema import IsekaiIntentSchema, LLMIntentPlan
from backend.src.services.isekai_locations import IsekaiLocationService
from backend.src.services.isekai_narration_composer import IsekaiNarrationComposer
from backend.src.services.isekai_opening import IsekaiOpeningGenerator
from backend.src.services.isekai_preferences import IsekaiPreferenceLearner
from backend.src.services.isekai_pressure_events import IsekaiPressureEventService
from backend.src.services.isekai_quests import IsekaiQuestService
from backend.src.services.isekai_rewards import IsekaiRewardService
from backend.src.services.isekai_resources import IsekaiResourceService
from backend.src.services.isekai_risk import IsekaiRiskService
from backend.src.services.isekai_scene_generation import IsekaiSceneGenerationAgent, apply_scene_generation_payload
from backend.src.services.isekai_scene_navigation import IsekaiSceneNavigationService
from backend.src.services.isekai_state_changes import IsekaiStateChangeService
from backend.src.services.isekai_time import IsekaiActionResolution, IsekaiTimeService
from backend.src.services.isekai_time_cost import IsekaiTimeCostService
from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer
from backend.src.services.model_gateway import ModelGateway


RACES = ["Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"]
CLASSES = ["Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"]
NAMES = ["艾瑞克", "莉娅", "诺恩", "米拉", "赛兰", "塔维"]


class IsekaiSurvivalService:
    def __init__(self, store: SQLiteStore, llm_client=None):
        self.store = store
        self.adventures = AdventureService(store)
        self.llm_client = llm_client
        self.model_gateway = ModelGateway(store, llm_client=llm_client)
        self.worldview = IsekaiWorldviewNormalizer()
        self.openings = IsekaiOpeningGenerator(self.model_gateway, self.worldview)
        self.event_director = IsekaiWorldEventDirector(store)
        self.preference_learner = IsekaiPreferenceLearner(llm_client=llm_client)
        self.time = IsekaiTimeService()
        self.action_parser = IsekaiActionParser(self.time)
        self.intent_planner = IsekaiIntentPlanner(self.action_parser)
        self.intent_schema = IsekaiIntentSchema()
        self.intent_interpreter = IsekaiIntentInterpreter(self.model_gateway, self.intent_schema)
        self.action_grounder = IsekaiActionGrounder(self.time)
        self.action_policy = IsekaiActionPolicyService()
        self.preconditions = IsekaiActionPreconditionService(self.time)
        self.resources = IsekaiResourceService()
        self.state_changes = IsekaiStateChangeService(store)
        self.content = IsekaiContentService()
        self.interactable_projector = IsekaiInteractableProjector()
        self.fallback_narrator = IsekaiFallbackNarrator()
        self.risk = IsekaiRiskService()
        self.quests = IsekaiQuestService(self.content)
        self.pressure_events = IsekaiPressureEventService(self.content)
        self.rewards = IsekaiRewardService()
        self.consequences = IsekaiConsequenceResolver(self.rewards, self.quests)
        self.locations = IsekaiLocationService(self.content)
        self.navigation = IsekaiSceneNavigationService()
        self.scene_generation_agent = IsekaiSceneGenerationAgent(self.model_gateway)
        self.economy = IsekaiEconomyService(self.content)
        self.time_cost = IsekaiTimeCostService()
        self.narration_composer = IsekaiNarrationComposer()
        self.action_resolution = IsekaiActionResolutionEngine(
            self.time,
            self.preconditions,
            self.resources,
            self.risk,
            self.interactable_projector,
            self.locations,
            self.economy,
            self.time_cost,
            self.content,
            self.navigation,
        )

    def generate_character(self) -> IsekaiCharacterOut:
        race = random.choice(RACES)
        class_name = random.choice(CLASSES)
        inventory = ["干粮 x2", "水囊(3/3)", "火绒盒", "旧斗篷"]
        if class_name == "Ranger":
            inventory.append("短弓")
        elif class_name == "Wizard":
            inventory.append("旅行法术书")
        else:
            inventory.append("匕首")
        return IsekaiCharacterOut(
            name=random.choice(NAMES),
            race=race,
            class_name=class_name,
            gold=0,
            inventory=self.worldview.normalize_list(inventory),
            traits=[race, class_name],
            world_reaction_tags=[race.lower(), class_name.lower(), "outsider"],
        )

    def initial_survival_state(self, scene: SceneState, weather: str = "薄雾") -> IsekaiSurvivalStateOut:
        return IsekaiSurvivalStateOut(location=scene.location, weather=weather)

    def create_adventure(self, request: AdventureCreate) -> AdventureOut:
        character = self.generate_character()
        opening = self.openings.generate(request, character, self.active_model())
        scene = opening.scene
        survival = self.initial_survival_state(scene, opening.weather)
        starting_copper = self.economy.starting_copper()
        adventure = self.adventures.create_isekai_shell(request, scene)
        self.initialize_scene_facts(adventure.id, scene)
        self.initialize_economy(adventure.id, starting_copper)
        self.save_character(adventure.id, character)
        self.save_survival_state(adventure.id, survival)
        self.adventures.append_message(
            adventure.id,
            "dm",
            self.opening_text(character, scene, survival, opening.narration, starting_copper),
            {"kind": "opening", "mode": "isekai_survival", "opening_source": opening.source},
        )
        return self.adventures.get(adventure.id)

    def save_character(self, adventure_id: int, character: IsekaiCharacterOut) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO isekai_characters (
                    adventure_id, name, race, class_name, background, alignment, level,
                    hp_current, hp_max, armor_class, strength, dexterity, constitution,
                    intelligence, wisdom, charisma, gold, inventory_json, traits_json,
                    world_reaction_tags_json, status_effects_json
                )
                VALUES (
                    :adventure_id, :name, :race, :class_name, :background, :alignment, :level,
                    :hp_current, :hp_max, :armor_class, :strength, :dexterity, :constitution,
                    :intelligence, :wisdom, :charisma, :gold, :inventory_json, :traits_json,
                    :world_reaction_tags_json, :status_effects_json
                )
                """,
                {
                    **character.model_dump(
                        exclude={"id", "adventure_id", "inventory", "traits", "world_reaction_tags", "status_effects"}
                    ),
                    "adventure_id": adventure_id,
                    "inventory_json": encode_json(character.inventory),
                    "traits_json": encode_json(character.traits),
                    "world_reaction_tags_json": encode_json(character.world_reaction_tags),
                    "status_effects_json": encode_json(character.status_effects),
                },
            )

    def save_survival_state(self, adventure_id: int, survival: IsekaiSurvivalStateOut) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO isekai_survival_states (
                    adventure_id, day, time_of_day, hunger, thirst, fatigue, sleep_need,
                    temperature_risk, morale, weather, location, shelter, last_action_type, state_json
                )
                VALUES (
                    :adventure_id, :day, :time_of_day, :hunger, :thirst, :fatigue, :sleep_need,
                    :temperature_risk, :morale, :weather, :location, :shelter, :last_action_type, :state_json
                )
                """,
                {
                    **survival.model_dump(exclude={"adventure_id", "state"}),
                    "adventure_id": adventure_id,
                    "state_json": encode_json(survival.state),
                },
            )

    def initialize_scene_facts(self, adventure_id: int, scene: SceneState) -> None:
        world_state = self.adventures.get_world_state(adventure_id)
        world_state["confirmed_location"] = scene.location
        world_state["isekai_pressure_goals"] = self.worldview.pressure_goals(scene, world_state)
        world_state["pressure_clocks"] = self.ensure_pressure_clocks(world_state.get("pressure_clocks"), scene, world_state)
        world_state.setdefault("location_history", [])
        world_state = self.content.ensure_world_state(world_state)
        world_state = self.quests.initial_world_state(world_state)
        world_state = self.pressure_events.ensure_state(world_state)
        self.adventures.update_world_state(adventure_id, world_state)

    def initialize_economy(self, adventure_id: int, copper_total: int) -> None:
        world_state = self.adventures.get_world_state(adventure_id)
        world_state["isekai_economy"] = self.economy.initial_state(copper_total)
        self.adventures.update_world_state(adventure_id, world_state)

    def opening_text(
        self,
        character: IsekaiCharacterOut,
        scene: SceneState,
        survival: IsekaiSurvivalStateOut,
        narration: str | None = None,
        copper_total: int | None = None,
    ) -> str:
        opening = narration or f"{character.name}，{character.race} {character.class_name}，在{scene.location}醒来。{scene.environment}"
        opening = self._repair_opening_inventory_contradictions(opening, character, scene)
        currency_text = self.currency_text(copper_total if copper_total is not None else 0)
        inventory_text = "、".join(character.inventory) if character.inventory else "无"
        return self.worldview.normalize_text(
            f"{opening} 当前目标：{scene.current_objective}"
            f" 随身物品：{inventory_text}。"
            f" 你的随身钱币为 {currency_text}，饥饿 {survival.hunger}，口渴 {survival.thirst}，疲劳 {survival.fatigue}。"
        )

    def _repair_opening_inventory_contradictions(
        self,
        opening: str,
        character: IsekaiCharacterOut,
        scene: SceneState,
    ) -> str:
        if not self._opening_conflicts_with_inventory(opening, character.inventory):
            return opening
        return f"{character.name}在{scene.location}醒来。{scene.environment}"

    def _opening_conflicts_with_inventory(self, opening: str, inventory: list[str]) -> bool:
        text = str(opening or "")
        if not text:
            return False
        item_names = self._opening_inventory_item_names(inventory)
        negative_words = (
            "遗失",
            "丢失",
            "丢了",
            "弄丢",
            "失去",
            "不见",
            "没有",
            "没了",
            "空了",
            "耗尽",
            "用尽",
            "只剩",
        )
        for item in item_names:
            if item not in text:
                continue
            pattern = rf"({re.escape(item)}.{{0,12}}({'|'.join(map(re.escape, negative_words))})|({'|'.join(map(re.escape, negative_words))}).{{0,12}}{re.escape(item)})"
            if re.search(pattern, text):
                return True
        return False

    def _opening_inventory_item_names(self, inventory: list[str]) -> list[str]:
        names: list[str] = []
        aliases = {
            "水囊": ["水囊", "水袋", "饮水", "清水"],
            "干粮": ["干粮", "口粮", "食物"],
        }
        for raw in inventory:
            name = re.sub(r"[\(（].*?[\)）]", "", str(raw or ""))
            name = re.sub(r"\s*x\s*\d+\s*$", "", name, flags=re.IGNORECASE).strip()
            for item_name in aliases.get(name, [name]):
                if item_name and item_name not in names:
                    names.append(item_name)
        return names

    def currency_text(self, copper_total: int) -> str:
        display = self.economy.display_currency(copper_total)
        parts = []
        if display["gold"]:
            parts.append(f"{display['gold']} 金")
        if display["silver"]:
            parts.append(f"{display['silver']} 银")
        if display["copper"] or not parts:
            parts.append(f"{display['copper']} 铜")
        return f"{' '.join(parts)}（共 {display['copper_total']} 铜）"

    def advance(self, adventure_id: int, message: MessageCreate) -> DMAdvanceResponse:
        turn = self.prepare_turn(adventure_id, message)
        content, source, scene_update = self.generate_narration(turn, message.locale)
        scene = self.apply_scene_progression(adventure_id, turn, content, scene_update)
        scene = self.apply_structured_state_changes(adventure_id, turn, scene)
        metadata = self.message_metadata(turn, source, scene_update, scene)
        dm_message = self.adventures.append_message(
            adventure_id,
            "dm",
            content,
            metadata,
        )
        updated = self.adventures.get(adventure_id)
        return DMAdvanceResponse(
            adventure=updated,
            dm_message=dm_message,
            scene=scene,
            messages=updated.messages,
            world_state=updated.world_state,
            combat_state=None,
            dice_result=None,
        )

    def advance_stream(self, adventure_id: int, message: MessageCreate):
        yield {"type": "status", "message": "dm_thinking"}
        turn = self.prepare_turn(adventure_id, message, learn_preferences=False)
        yield {"type": "player_message", "message": turn["player_message"]}
        content, source, scene_update = yield from self.stream_narration(turn, message.locale)
        scene = self.apply_scene_progression(adventure_id, turn, content, scene_update)
        scene = self.apply_structured_state_changes(adventure_id, turn, scene)
        metadata = self.message_metadata(turn, source, scene_update, scene)
        dm_message = self.adventures.append_message(
            adventure_id,
            "dm",
            content,
            metadata,
        )
        turn["world_state"] = self.learn_preferences_for_current_turn(adventure_id)
        updated = self.adventures.get(adventure_id)
        yield {
            "type": "final",
            "adventure": updated,
            "dm_message": dm_message,
            "scene": scene,
            "messages": updated.messages,
            "world_state": updated.world_state,
            "combat_state": None,
            "dice_result": None,
        }

    def prepare_turn(
        self,
        adventure_id: int,
        message: MessageCreate,
        learn_preferences: bool = True,
    ) -> dict[str, Any]:
        player_message = self.adventures.append_message(
            adventure_id,
            "player",
            message.content,
            {"mode": "isekai_survival"},
        )
        scene = self.repair_legacy_scene_if_needed(adventure_id, self.adventures.get_scene(adventure_id))
        scene, scene_structure = self.ensure_scene_structured(adventure_id, scene, message.content)
        llm_intent_turn = self.prepare_llm_intent_turn(
            adventure_id,
            message,
            player_message,
            scene,
            learn_preferences=learn_preferences,
        )
        if llm_intent_turn is not None:
            if scene_structure:
                llm_intent_turn["scene_structure"] = scene_structure
            return llm_intent_turn
        plan = self.intent_planner.plan(message.content, scene)
        if self.should_resolve_action_plan(plan, self.adventures.get_world_state(adventure_id), scene):
            turn = self.prepare_resolved_turn(
                adventure_id,
                message,
                player_message,
                scene,
                plan,
                learn_preferences=learn_preferences,
            )
            if scene_structure:
                turn["scene_structure"] = scene_structure
            return turn
        action = self.preconditions.check(self.action_parser.parse(message.content, scene), scene)
        delta, survival = self.apply_delta(adventure_id, action)
        character = self.get_character(adventure_id)
        resource_result = self.resources.apply(character, survival, action, message.content)
        character = self.update_character_resources(adventure_id, resource_result.character)
        delta.update(resource_result.delta)
        fallback = self.narrate(message.content, scene, character, survival, delta)
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action.action_type,
            "action": action,
            "parsed_action": self.parsed_action_payload(action),
            "time": {
                "time_cost_minutes": delta["time_cost_minutes"],
                "advances_time": delta["advances_time"],
                "survival_intent": action.survival_intent,
                "reason": action.reason,
            },
            "delta": delta,
            "survival": survival,
            "visible_survival": self.visible_survival_state(survival),
            "scene": scene,
            "character": character,
            "recent_messages": [],
            "fallback": fallback,
        }
        if scene_structure:
            turn["scene_structure"] = scene_structure
        turn["world_state"] = self.advance_world_context(adventure_id, turn, learn_preferences=learn_preferences)
        model = self.active_model()
        reserved_payload = self.build_model_payload(turn, message.locale, recent_messages=[])
        turn["recent_messages"] = self.recent_messages_payload(
            adventure_id,
            max_context_tokens=model.max_context_tokens if model else 4096,
            reserved_payload=reserved_payload,
        )
        return turn

    def ensure_scene_structured(self, adventure_id: int, scene: SceneState, player_action: str) -> tuple[SceneState, dict[str, Any]]:
        if self._scene_is_structured(scene) or not self._input_needs_scene_structure(player_action, scene):
            return scene, {}
        world_state = self.adventures.get_world_state(adventure_id)
        next_scene, next_world_state, metadata = self.generate_scene_structure(
            adventure_id,
            scene,
            player_action,
            world_state,
            generation_reason="repair_current",
        )
        if metadata.get("success"):
            self.adventures.update_scene(adventure_id, next_scene)
            self.adventures.update_world_state(adventure_id, next_world_state)
            return next_scene, metadata
        return scene, metadata

    def generate_scene_structure(
        self,
        adventure_id: int,
        scene: SceneState,
        player_action: str,
        world_state: dict[str, Any],
        *,
        generation_reason: str,
    ) -> tuple[SceneState, dict[str, Any], dict[str, Any]]:
        model = self.active_model()
        result = self.scene_generation_agent.generate(
            adventure_id=adventure_id,
            scene=scene,
            world_state=world_state,
            model=model,
            generation_reason=generation_reason,
            player_action=player_action,
        )
        if not result.success:
            return scene, world_state, {"source": "scene_generation_agent", "success": False, "errors": result.errors}
        next_scene, next_world_state, metadata = apply_scene_generation_payload(scene, world_state, result.payload)
        return next_scene, next_world_state, {**metadata, "success": True, "generation_reason": generation_reason}

    def _input_needs_scene_structure(self, player_action: str, scene: SceneState) -> bool:
        if self._text_has_concrete_exploration_cue(player_action, scene):
            return True
        action = self.action_parser.parse(player_action, scene)
        if action.action_type in {"table_talk", "status_check", "clarification"}:
            return False
        if action.action_type == "observe":
            return self._has_concrete_observation_target(player_action)
        if action.action_type in {"search", "gather", "force_open", "refill_water", "secure_shelter"}:
            return self._has_concrete_scene_interaction_target(player_action, scene)
        if action.action_type == "enter_location":
            return self._has_concrete_local_entry_target(player_action)
        return False

    def _llm_plan_needs_scene_structure(self, plan: LLMIntentPlan, scene: SceneState) -> bool:
        if self._scene_is_structured(scene):
            return False
        for step in plan.steps:
            action_type = str(step.action_type or "").strip()
            target_text = str(step.target_text or "").strip() or plan.raw_text
            if action_type == "observe" and self._has_concrete_observation_target(target_text):
                return True
            if action_type in {"search", "gather", "force_open", "refill_water", "secure_shelter"} and self._has_concrete_scene_interaction_target(
                target_text
            ):
                return True
        return False

    def _text_has_concrete_exploration_cue(self, player_action: str, scene: SceneState | None = None) -> bool:
        text = str(player_action or "").strip().lower()
        if not text:
            return False
        if any(word in text for word in ["状态", "属性", "背包", "金币", "多少钱"]):
            return False
        observe_verbs = [
            "观察",
            "查看",
            "检查",
            "研究",
            "解读",
            "辨认",
            "翻看",
            "摸",
            "看看",
        ]
        search_verbs = [
            "搜索",
            "搜查",
            "调查",
            "寻找",
        ]
        if any(verb in text for verb in observe_verbs) and self._has_concrete_observation_target(text):
            return True
        return any(verb in text for verb in search_verbs) and self._has_concrete_scene_interaction_target(text, scene)

    def _has_concrete_scene_interaction_target(self, player_action: str, scene: SceneState | None = None) -> bool:
        text = str(player_action or "").strip().lower()
        if not text:
            return False
        generic_targets = ["周围", "四周", "附近", "这里", "环境", "情况", "一圈", "一下"]
        if any(word in text for word in generic_targets) and len(text) <= 8:
            return False
        generic_resource_terms = ["食材", "食物", "水源", "饮水", "补给", "材料"]
        if any(word in text for word in generic_resource_terms) and scene and not self._mentions_scene_specific_target(text, scene):
            return False
        return len(self._scene_interaction_residue(text)) >= 2

    def _mentions_scene_specific_target(self, text: str, scene: SceneState) -> bool:
        candidates: list[str] = []
        candidates.extend(str(item) for item in scene.important_objects)
        for entry in scene.interactables:
            if not isinstance(entry, dict):
                continue
            candidates.append(str(entry.get("name") or ""))
            candidates.extend(str(item) for item in entry.get("aliases", []) if str(item).strip())
        for candidate in candidates:
            clean = str(candidate or "").strip().lower()
            if len(clean) >= 2 and (clean in text or any(fragment in text for fragment in self._scene_target_fragments(clean))):
                return True
        return False

    def _scene_target_fragments(self, text: str) -> list[str]:
        fragments: set[str] = set()
        for size in range(min(5, len(text)), 1, -1):
            for start in range(0, len(text) - size + 1):
                fragment = text[start : start + size]
                if not any(ch in fragment for ch in ["的", "了", "着", "和", "与", "及"]):
                    fragments.add(fragment)
        return sorted(fragments, key=len, reverse=True)[:8]

    def _has_concrete_observation_target(self, player_action: str) -> bool:
        text = str(player_action or "").strip().lower()
        residue = self._scene_interaction_residue(text)
        ambient_targets = {"雾", "雾气", "空气", "天色", "天气", "光线", "声音", "风", "风声", "气味"}
        if residue in ambient_targets:
            return False
        concrete_verbs = ["检查", "查看", "翻看", "对照", "解读", "研究", "辨认", "摸", "看看", "寻找"]
        if any(verb in text for verb in concrete_verbs):
            return len(residue) >= 2
        list_markers = ["、", "，", ",", "和", "并", "以及", "再"]
        if any(marker in text for marker in list_markers):
            return len(residue) >= 4
        return len(residue) >= 4

    def _scene_interaction_residue(self, text: str) -> str:
        residue = text
        for word in [
            "我",
            "想",
            "要",
            "先",
            "然后",
            "搜索",
            "搜查",
            "调查",
            "查看",
            "检查",
            "辨认",
            "翻看",
            "摸一摸",
            "摸",
            "看看",
            "寻找",
            "观察",
            "打开",
            "撬开",
            "强行",
            "采集",
            "摘",
            "捡",
            "拿起",
            "装水",
            "取水",
            "堵门",
            "加固",
            "使用",
            "一下",
            "一点",
            "周围",
            "四周",
            "附近",
            "这里",
            "环境",
        ]:
            residue = residue.replace(word, "")
        return residue.strip(" ，。,.!?！？")

    def _has_concrete_local_entry_target(self, player_action: str) -> bool:
        text = str(player_action or "").strip().lower()
        if not text:
            return False
        if any(word in text for word in ["回城", "回到城镇", "回镇", "去白石镇", "前往", "赶路"]):
            return False
        local_entry_words = ["进入", "钻进", "走进", "进到", "进屋", "门", "洞", "缝", "车厢", "小屋", "房间", "走廊", "通道"]
        return any(word in text for word in local_entry_words) and len(self._scene_interaction_residue(text)) >= 2

    def _scene_is_structured(self, scene: SceneState) -> bool:
        if not scene.interactables:
            return False
        names = {str(entry.get("name") or "").strip() for entry in scene.interactables if isinstance(entry, dict)}
        return bool(names) and not names <= {"", "门口", "周围环境"}

    def _resolved_scene_needs_generation(self, scene: SceneState, steps: list[Any]) -> bool:
        if self._scene_is_structured(scene):
            return False
        return any(getattr(step.action, "action_type", "") in {"enter_location", "travel", "leave_location"} for step in steps)

    def prepare_llm_intent_turn(
        self,
        adventure_id: int,
        message: MessageCreate,
        player_message: Any,
        scene: SceneState,
        learn_preferences: bool = True,
    ) -> dict[str, Any] | None:
        model = self.active_model()
        if not model or not self.llm_client or not hasattr(self.llm_client, "chat"):
            return None
        if not getattr(self.llm_client, "supports_intent_interpretation", False):
            return None
        interpretation = self.intent_interpreter.interpret(message.content, scene, model)
        if interpretation.plan is not None:
            plan = interpretation.plan
            if plan.requires_clarification:
                return self.prepare_intent_clarification_turn(
                    adventure_id,
                    message,
                    player_message,
                    scene,
                    plan.clarification_question,
                    intent_source="active_model",
                    intent_plan=plan,
                    intent_error=interpretation.error,
                    learn_preferences=learn_preferences,
                )
            scene_structure: dict[str, Any] = {}
            if self._llm_plan_needs_scene_structure(plan, scene):
                world_state = self.adventures.get_world_state(adventure_id)
                structured_scene, structured_world_state, scene_structure = self.generate_scene_structure(
                    adventure_id,
                    scene,
                    message.content,
                    world_state,
                    generation_reason="repair_current_from_intent",
                )
                if scene_structure.get("success"):
                    self.adventures.update_scene(adventure_id, structured_scene)
                    self.adventures.update_world_state(adventure_id, structured_world_state)
                    scene = structured_scene
            grounded = self.action_grounder.ground(plan, scene)
            if grounded.steps and grounded.steps[0].action.requires_clarification:
                return self.prepare_intent_clarification_turn(
                    adventure_id,
                    message,
                    player_message,
                    scene,
                    grounded.steps[0].action.arguments.get("clarification_question") or grounded.steps[0].action.reason,
                    intent_source="active_model",
                    intent_plan=plan,
                    candidates=grounded.steps[0].action.candidates,
                    learn_preferences=learn_preferences,
                )
            if grounded.steps:
                turn = self.prepare_resolved_turn(
                    adventure_id,
                    message,
                    player_message,
                    scene,
                    grounded,
                    learn_preferences=learn_preferences,
                )
                turn["intent_source"] = "active_model"
                turn["intent_plan"] = plan.payload()
                if scene_structure:
                    turn["scene_structure"] = scene_structure
                if interpretation.raw_response:
                    turn["intent_raw_response"] = interpretation.raw_response
                return turn

        if interpretation.source == "error":
            fallback_plan = self.intent_planner.plan(message.content, scene)
            if self.should_block_fallback_intent(fallback_plan):
                return self.prepare_intent_clarification_turn(
                    adventure_id,
                    message,
                    player_message,
                    scene,
                    "模型暂时没能可靠拆解这个复合行动。为了避免误操作，请把要执行的第一步单独说清楚。",
                    intent_source="fallback_blocked",
                    intent_error=interpretation.error,
                    learn_preferences=learn_preferences,
                )
        return None

    def should_block_fallback_intent(self, plan: IsekaiIntentPlan) -> bool:
        allowed = {"status_check", "table_talk", "drink_water", "eat_food", "rest_short", "sleep", "observe"}
        if plan.truncated:
            return True
        if len(plan.steps) > 1:
            return any(step.action.action_type not in allowed for step in plan.steps)
        return any(step.action.action_type not in allowed for step in plan.steps)

    def prepare_intent_clarification_turn(
        self,
        adventure_id: int,
        message: MessageCreate,
        player_message: Any,
        scene: SceneState,
        question: str,
        *,
        intent_source: str,
        intent_plan: LLMIntentPlan | None = None,
        intent_error: str = "",
        candidates: list[dict[str, Any]] | None = None,
        learn_preferences: bool = True,
    ) -> dict[str, Any]:
        action = self.action_parser._build(
            "clarification",
            arguments={"clarification_question": question},
            confidence="low",
            confidence_reasons=["llm_intent:clarification"],
            matched_rules=[f"intent_source:{intent_source}"],
            requires_clarification=True,
            candidates=candidates or [],
        )
        delta, survival = self.apply_delta(adventure_id, action)
        character = self.get_character(adventure_id)
        fallback = question or self.clarification_narration({"parsed_action": self.parsed_action_payload(action)})
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action.action_type,
            "action": action,
            "parsed_action": self.parsed_action_payload(action),
            "time": {
                "time_cost_minutes": delta["time_cost_minutes"],
                "advances_time": delta["advances_time"],
                "survival_intent": action.survival_intent,
                "reason": action.reason,
            },
            "delta": delta,
            "survival": survival,
            "visible_survival": self.visible_survival_state(survival),
            "scene": scene,
            "character": character,
            "recent_messages": [],
            "fallback": fallback,
            "intent_source": intent_source,
            "intent_error": intent_error,
        }
        if intent_plan is not None:
            turn["intent_plan"] = intent_plan.payload()
        turn["world_state"] = self.advance_world_context(adventure_id, turn, learn_preferences=learn_preferences)
        return turn

    def should_resolve_action_plan(
        self,
        plan: IsekaiIntentPlan,
        world_state: dict[str, Any] | None = None,
        scene: SceneState | None = None,
    ) -> bool:
        if not plan.steps:
            return False
        deterministic_actions = {
            "approach",
            "hide",
            "avoid",
            "force_open",
            "enter_location",
            "leave_location",
            "negotiate",
            "purchase",
            "repair",
            "eat_meal",
        }
        if any(step.action.action_type in deterministic_actions for step in plan.steps):
            return True
        resource_actions = {"eat_food", "drink_water", "eat_drink", "refill_water", "rest_short", "sleep", "secure_shelter"}
        if len(plan.steps) > 1 and any(step.action.action_type in resource_actions for step in plan.steps):
            return True
        if scene and self.plan_has_scene_scoped_discovery(plan, world_state or {}, scene):
            return True
        if any(step.action.action_type == "search" and step.action.target_name in {"货袋"} for step in plan.steps):
            return True
        if any(step.action.action_type == "travel" for step in plan.steps) and any(marker in plan.original_text for marker in ["连夜", "夜里", "夜晚"]):
            return True
        if self.plan_mentions_active_quest(plan, world_state or {}):
            return True
        return False

    def plan_mentions_active_quest(self, plan: IsekaiIntentPlan, world_state: dict[str, Any]) -> bool:
        quest = world_state.get("isekai_quest") if isinstance(world_state.get("isekai_quest"), dict) else {}
        quest_id = str(quest.get("active_quest_id") or "")
        line = self.content.quest_line(quest_id, world_state)
        markers: list[str] = []
        for transition in line.get("transitions", []):
            if not isinstance(transition, dict):
                continue
            trigger = transition.get("trigger") if isinstance(transition.get("trigger"), dict) else {}
            markers.extend(str(item) for item in trigger.get("text_contains_any", []) if str(item).strip())
        return bool(markers) and any(marker in plan.original_text for marker in markers)

    def plan_has_scene_scoped_discovery(
        self,
        plan: IsekaiIntentPlan,
        world_state: dict[str, Any],
        scene: SceneState,
    ) -> bool:
        discovery_tables = self.content.discovery_tables(world_state)
        for step in plan.steps:
            action = step.action
            if action.action_type not in {"search", "observe"}:
                continue
            entries = discovery_tables.get(action.target_id, []) if action.target_id else []
            if not entries:
                target_text = action.target_name or ""
                entries = [
                    entry
                    for table_entries in discovery_tables.values()
                    for entry in table_entries
                    if self.discovery_entry_matches_target_text(entry, target_text)
                ]
            if any(self.discovery_entry_matches_scene(entry, scene) and self.discovery_entry_matches_action(entry, action.action_type) for entry in entries):
                return True
        return False

    def discovery_entry_matches_target_text(self, entry: dict[str, Any], target_text: str) -> bool:
        aliases = entry.get("_target_aliases") if isinstance(entry.get("_target_aliases"), list) else []
        return any(str(alias).strip() and str(alias).strip() in target_text for alias in aliases)

    def discovery_entry_matches_scene(self, entry: dict[str, Any], scene: SceneState) -> bool:
        aliases = entry.get("_scene_aliases") if isinstance(entry.get("_scene_aliases"), list) else []
        if not aliases:
            return True
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects])
        return any(str(alias).strip() and str(alias).strip() in scene_text for alias in aliases)

    def discovery_entry_matches_action(self, entry: dict[str, Any], action_type: str) -> bool:
        trigger = entry.get("trigger") if isinstance(entry.get("trigger"), dict) else {}
        expected = str(trigger.get("action_type") or "").strip()
        return not expected or expected == action_type

    def prepare_resolved_turn(
        self,
        adventure_id: int,
        message: MessageCreate,
        player_message: Any,
        scene: SceneState,
        plan: IsekaiIntentPlan,
        learn_preferences: bool = True,
    ) -> dict[str, Any]:
        survival = self.adventures.get(adventure_id, include_messages=False).survival_state or {}
        character = self.get_character(adventure_id)
        world_state = self.adventures.get_world_state(adventure_id)
        result = self.action_resolution.resolve(plan, scene, survival, character, world_state)
        post_scene_structure: dict[str, Any] = {}
        if self._resolved_scene_needs_generation(result.scene, result.steps):
            expanded_scene, expanded_world_state, post_scene_structure = self.generate_scene_structure(
                adventure_id,
                result.scene,
                message.content,
                result.world_state,
                generation_reason="enter_stub",
            )
            if post_scene_structure.get("success"):
                expanded_survival = dict(result.survival)
                expanded_survival["location"] = expanded_scene.location
                result = replace(result, scene=expanded_scene, world_state=expanded_world_state, survival=expanded_survival)
        self.persist_survival_snapshot(adventure_id, result.survival)
        character = self.update_character_resources(adventure_id, result.character)
        self.adventures.update_scene(adventure_id, result.scene)
        self.adventures.update_world_state(adventure_id, result.world_state)
        if result.scene.location != scene.location:
            history_entry = self.location_history_entry(scene.location, result.scene.location, {"player_input": message.content, "survival": result.survival}, result.steps[-1].result_text if result.steps else "")
            self.update_world_location_history(adventure_id, history_entry)
        content = self.worldview.normalize_text(self.narration_composer.compose(result, result.scene))
        step_types = [step.action.action_type for step in result.steps]
        action_type = step_types[0] if step_types and len(set(step_types)) == 1 else ("compound" if step_types else "table_talk")
        parsed_action = self.resolved_plan_payload(result, action_type)
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action_type,
            "action": result.steps[0].action if result.steps else self.time.resolve_action_type("table_talk"),
            "parsed_action": parsed_action,
            "time": {
                "time_cost_minutes": result.delta["time_cost_minutes"],
                "advances_time": result.delta["advances_time"],
                "survival_intent": "compound" if len(result.steps) > 1 else (result.steps[0].action.survival_intent if result.steps else "none"),
                "reason": "复合行动结算" if len(result.steps) > 1 else (result.steps[0].action.reason if result.steps else ""),
            },
            "delta": result.delta,
            "survival": result.survival,
            "visible_survival": self.visible_survival_state(result.survival),
            "scene": scene,
            "resolved_scene": result.scene,
            "character": character,
            "recent_messages": [],
            "fallback": content,
            "resolved_turn": True,
            "resolved_content": content,
            "resolved_steps": [step.payload() for step in result.steps],
            "model_payload": {
                "narration": content,
                "interactables": result.scene.interactables,
                "suggested_actions": result.scene.suggested_actions,
            },
            "state_changes_applied": {},
        }
        if post_scene_structure:
            turn["scene_structure"] = post_scene_structure
        turn["world_state"] = self.advance_world_context(adventure_id, turn, learn_preferences=learn_preferences)
        return turn

    def resolved_plan_payload(self, result: Any, action_type: str) -> dict[str, Any]:
        first = result.steps[0].action if result.steps else self.time.resolve_action_type("table_talk")
        payload = self.parsed_action_payload(first)
        if action_type == "compound":
            payload.update(
                {
                    "action_type": "compound",
                    "time_cost_minutes": result.delta.get("time_cost_minutes", 0),
                    "advances_time": result.delta.get("advances_time", False),
                    "survival_intent": "compound",
                    "reason": "复合行动结算",
                    "subactions": [step.payload() for step in result.steps],
                    "truncated": result.plan.truncated,
                }
            )
        return payload

    def scene_action_context(self, scene: SceneState) -> dict[str, Any]:
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects, *scene.npcs])
        has_npcs = bool(scene.npcs) or any(
            word in scene_text
            for word in ["摊主", "守卫", "商人", "旅人", "镇民", "祭司", "老板", "铁匠", "小贩", "巡逻"]
        )
        return {"has_npcs": has_npcs}

    def visible_survival_state(self, survival: dict[str, Any]) -> dict[str, Any]:
        satiety = self._positive_meter(100 - int(survival.get("hunger", 0)))
        hydration = self._positive_meter(100 - int(survival.get("thirst", 0)))
        energy = self._positive_meter(100 - int(survival.get("fatigue", 0)))
        sleep_sufficiency = self._positive_meter(100 - int(survival.get("sleep_need", 0)))
        summary_parts = [self._satiety_summary(satiety), self._hydration_summary(hydration)]
        if energy < 40:
            summary_parts.append("精力偏低，应体现疲惫和行动代价。")
        if sleep_sufficiency < 40:
            summary_parts.append("睡眠不足明显，夜间行动风险更高。")
        return {
            "satiety": satiety,
            "hydration": hydration,
            "energy": energy,
            "sleep_sufficiency": sleep_sufficiency,
            "status_summary": "".join(summary_parts),
            "narration_thresholds": {
                "satiety_70_plus": "不写饿，只可写闻到食物香气或补给意识。",
                "satiety_40_to_70": "可写轻微饥饿。",
                "satiety_20_to_40": "可写明显饥饿。",
                "satiety_below_20": "可写虚弱、判断力下降和 HP 风险。",
            },
        }

    def _positive_meter(self, value: int) -> int:
        return max(0, min(100, value))

    def _satiety_summary(self, satiety: int) -> str:
        if satiety >= 70:
            return "饱腹度较高，不应描写明显饥饿；"
        if satiety >= 40:
            return "饱腹度中等，可描写轻微饥饿；"
        if satiety >= 20:
            return "饱腹度偏低，可描写明显饥饿；"
        return "饱腹度危险，角色虚弱且可能承受 HP 风险；"

    def _hydration_summary(self, hydration: int) -> str:
        if hydration >= 70:
            return "水分充足，不应描写明显口渴。"
        if hydration >= 40:
            return "水分偏低，可轻微口渴。"
        if hydration >= 20:
            return "水分不足，应体现寻找水源的压力。"
        return "水分危险，脱水会影响判断并带来 HP 风险。"

    def repair_legacy_scene_if_needed(self, adventure_id: int, scene: SceneState) -> SceneState:
        repaired_payload = self.worldview.repair_scene_state_payload(scene.model_dump())
        repaired_scene = SceneState.model_validate(repaired_payload)
        world_state = self.adventures.get_world_state(adventure_id)
        repaired_scene, _metadata = self.content.materialize_scene_from_content(repaired_scene, world_state)
        if repaired_scene.model_dump() != scene.model_dump():
            self.adventures.update_scene(adventure_id, repaired_scene)
        return repaired_scene

    def advance_world_context(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        learn_preferences: bool = True,
    ) -> dict[str, Any]:
        world_state = self.adventures.get_world_state(adventure_id)
        world_state = self.quests.initial_world_state(world_state)
        world_state = self.pressure_events.ensure_state(world_state)
        world_state["turn_count"] = int(world_state.get("turn_count", 0)) + 1
        pressure_scene = turn.get("resolved_scene") or turn.get("scene")
        world_state["isekai_pressure_goals"] = self.worldview.pressure_goals(pressure_scene, world_state)
        world_state["pressure_clocks"] = self.ensure_pressure_clocks(world_state.get("pressure_clocks"), pressure_scene, world_state)
        world_state = self.advance_pressure_clocks(world_state, turn, pressure_scene)
        world_state, pressure_event = self.pressure_events.evaluate(world_state, turn)
        turn["pressure_event"] = pressure_event
        turn["pressure_event_fired"] = bool(pressure_event)
        if pressure_event:
            turn.setdefault("delta", {}).setdefault("visible_events", [])
            turn["delta"]["visible_events"].append(pressure_event["visible_text"])
            risk_change = dict(turn["delta"].get("risk_change") or {})
            for key, value in (pressure_event.get("state_delta") or {}).items():
                risk_change[key] = int(risk_change.get(key, 0)) + int(value)
            turn["delta"]["risk_change"] = risk_change
        world_state, quest_update = self.quests.advance_for_turn(world_state, turn, pressure_event)
        turn["quest_update"] = quest_update
        if quest_update.get("clues_added"):
            turn.setdefault("delta", {}).setdefault("clues", [])
            for clue in quest_update["clues_added"]:
                if clue not in turn["delta"]["clues"]:
                    turn["delta"]["clues"].append(clue)
        world_state = self.apply_rule_rewards_for_turn(adventure_id, turn, world_state, quest_update)
        if learn_preferences:
            world_state = self.learn_preferences_for_current_turn(adventure_id, world_state)
        else:
            self.adventures.update_world_state(adventure_id, world_state)
        self.event_director.evaluate_turn(adventure_id, turn, world_state)
        self.adventures.update_world_state(adventure_id, world_state)
        return world_state

    def apply_rule_rewards_for_turn(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        world_state: dict[str, Any],
        quest_update: dict[str, Any],
    ) -> dict[str, Any]:
        character = dict(turn.get("character") or self.get_character(adventure_id))
        reward_payload: dict[str, Any] = {"clues_added": list((turn.get("delta") or {}).get("clues") or [])}
        quest = world_state.get("isekai_quest") if isinstance(world_state.get("isekai_quest"), dict) else {}
        quest_id = str(quest.get("active_quest_id") or "")
        stage_reward = self.content.quest_reward_for_stage(quest_id, str(quest_update.get("after") or ""), world_state)
        if stage_reward and quest_update.get("changed"):
            reward_payload = {
                **stage_reward,
                "clues_added": [*reward_payload["clues_added"], *list(stage_reward.get("clues_added") or [])],
            }
        if not any(reward_payload.get(key) for key in ["items_added", "currency_delta", "relationship_delta", "clues_added", "entitlements_added"]):
            return world_state

        next_character, next_world, applied = self.rewards.apply(
            character,
            world_state,
            reward_payload,
            reason=str(stage_reward.get("reason") or "quest_reward") if stage_reward else "行动线索",
        )
        turn["reward_applied"] = applied
        turn["character"] = self.update_character_resources(adventure_id, next_character)
        if applied.get("items_added"):
            turn.setdefault("delta", {}).setdefault("inventory_changes", [])
            turn["delta"]["inventory_changes"].extend([f"获得{item}" for item in applied["items_added"]])
        if applied.get("currency_delta"):
            turn.setdefault("delta", {}).setdefault("rewards", [])
            turn["delta"]["rewards"].append(f"{applied['currency_delta']} 铜")
        if applied.get("relationship_delta"):
            turn.setdefault("delta", {}).setdefault("relationship_changes", [])
            turn["delta"]["relationship_changes"].extend(applied["relationship_delta"])
        if applied.get("clues_added"):
            turn.setdefault("delta", {}).setdefault("clues", [])
            for clue in applied["clues_added"]:
                if clue not in turn["delta"]["clues"]:
                    turn["delta"]["clues"].append(clue)
        if turn.get("resolved_turn") and quest_update.get("after") == "resolved":
            turn["resolved_content"] = self.append_reward_text(
                str(turn.get("resolved_content") or turn.get("fallback") or ""),
                applied,
            )
            turn["fallback"] = turn["resolved_content"]
        return next_world

    def append_reward_text(self, content: str, applied: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in applied.get("items_added", []):
            parts.append(f"获得{item}")
        if applied.get("currency_delta"):
            parts.append(f"获得{applied['currency_delta']} 铜")
        for clue in applied.get("clues_added", []):
            parts.append(f"线索：{clue}")
        for relationship in applied.get("relationship_delta", []):
            if isinstance(relationship, dict):
                name = relationship.get("name") or relationship.get("npc_id") or "NPC"
                trust = relationship.get("trust")
                parts.append(f"{name}信任提升{trust}" if trust is not None else f"{name}态度改善")
        if not parts:
            return content
        return self.worldview.normalize_text(f"{content} 任务奖励已入账：{'，'.join(parts)}。")

    def message_metadata(
        self,
        turn: dict[str, Any],
        source: str,
        scene_update: dict[str, Any] | None,
        applied_scene: SceneState | None = None,
    ) -> dict[str, Any]:
        visible_survival = turn.get("visible_survival") or self.visible_survival_state(turn["survival"])
        scene_update_applied = False
        if applied_scene is not None:
            scene_update_applied = applied_scene.model_dump() != turn["scene"].model_dump()
        metadata = {
            "mode": "isekai_survival",
            "action_type": turn["action_type"],
            "parsed_action": turn.get("parsed_action") or {},
            "survival_delta": turn["delta"],
            "visible_survival": visible_survival,
            "time": turn["time"],
            "scene_update": scene_update or {},
            "scene_update_applied": scene_update_applied,
            "debug": {
                "mode": "isekai_survival",
                "source": source,
                "action_type": turn["action_type"],
                "raw_survival": {
                    "hunger": int(turn["survival"].get("hunger", 0)),
                    "thirst": int(turn["survival"].get("thirst", 0)),
                    "fatigue": int(turn["survival"].get("fatigue", 0)),
                    "sleep_need": int(turn["survival"].get("sleep_need", 0)),
                },
                "visible_survival": visible_survival,
                "scene_update_applied": scene_update_applied,
            },
            "source": source,
        }
        metadata["pressure_clocks"] = list((turn.get("world_state") or {}).get("pressure_clocks") or [])
        model_payload = turn.get("model_payload") or {}
        if isinstance(model_payload.get("interactables"), list):
            metadata["interactables"] = model_payload["interactables"]
        if isinstance(model_payload.get("suggested_actions"), list):
            metadata["suggested_actions"] = model_payload["suggested_actions"]
            metadata["suggested_action_details"] = self.suggested_action_details(turn)
        visible_edges = self.visible_scene_edges(turn.get("world_state") or {}, applied_scene or turn.get("resolved_scene") or turn.get("scene"))
        if visible_edges:
            metadata["visible_edges"] = visible_edges
        if turn.get("state_changes_applied"):
            metadata["state_changes_applied"] = turn["state_changes_applied"]
        if turn.get("resolved_steps"):
            metadata["resolved_steps"] = turn["resolved_steps"]
        world_state = turn.get("world_state") or {}
        if isinstance(world_state.get("isekai_quest"), dict):
            metadata["isekai_quest"] = world_state["isekai_quest"]
        if isinstance(world_state.get("isekai_clues"), list):
            metadata["isekai_clues"] = world_state["isekai_clues"]
        metadata["pressure_event_fired"] = bool(turn.get("pressure_event_fired"))
        if isinstance(turn.get("pressure_event"), dict):
            metadata["pressure_event"] = turn["pressure_event"]
        if isinstance(turn.get("quest_update"), dict):
            metadata["quest_update"] = turn["quest_update"]
        if isinstance(turn.get("reward_applied"), dict):
            metadata["reward_applied"] = turn["reward_applied"]
        if isinstance((turn.get("delta") or {}).get("risk_change"), dict):
            metadata["risk_change"] = turn["delta"]["risk_change"]
        for key in ["outcome_level", "rewards", "entitlements", "relationship_changes", "clues", "shortfall_copper"]:
            if key in (turn.get("delta") or {}):
                metadata[key] = turn["delta"][key]
        if turn.get("scene_update_blocked_reason"):
            metadata["scene_update_blocked_reason"] = turn["scene_update_blocked_reason"]
        if turn.get("model_errors"):
            metadata["model_errors"] = turn["model_errors"]
        if turn.get("intent_source"):
            metadata["intent_source"] = turn["intent_source"]
        if turn.get("intent_plan"):
            metadata["intent_plan"] = turn["intent_plan"]
        if turn.get("intent_error"):
            metadata["intent_error"] = turn["intent_error"]
        if turn.get("scene_object_source"):
            metadata["scene_object_source"] = turn["scene_object_source"]
        if turn.get("scene_objects_applied"):
            metadata["scene_objects_applied"] = turn["scene_objects_applied"]
        if turn.get("scene_structure"):
            metadata["scene_structure"] = turn["scene_structure"]
        return metadata

    def visible_scene_edges(self, world_state: dict[str, Any], scene: SceneState | None) -> list[dict[str, Any]]:
        if scene is None:
            return []
        node_id = str((scene.location_path or {}).get("node_id") or "")
        if not node_id:
            return []
        graph = world_state.get("scene_graph") if isinstance(world_state.get("scene_graph"), dict) else {}
        edges = []
        for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
            if not isinstance(edge, dict):
                continue
            if str(edge.get("from_node_id") or "") != node_id:
                continue
            if edge.get("known_to_player", True) is False or str(edge.get("access") or "") == "hidden":
                continue
            edges.append(dict(edge))
        return edges[:6]

    def parsed_action_payload(self, action: Any) -> dict[str, Any]:
        if is_dataclass(action):
            return asdict(action)
        return {
            "action_type": getattr(action, "action_type", ""),
            "time_cost_minutes": getattr(action, "time_cost_minutes", 0),
            "advances_time": getattr(action, "advances_time", False),
            "survival_intent": getattr(action, "survival_intent", ""),
            "reason": getattr(action, "reason", ""),
        }

    def suggested_action_details(self, turn: dict[str, Any]) -> list[dict[str, Any]]:
        model_payload = turn.get("model_payload") or {}
        actions = model_payload.get("suggested_actions")
        if not isinstance(actions, list):
            return []
        interactables = model_payload.get("interactables") if isinstance(model_payload, dict) else []
        has_model_npcs = any(
            isinstance(entry, dict) and str(entry.get("type") or "").strip().lower() == "npc"
            for entry in (interactables if isinstance(interactables, list) else [])
        )
        scene = turn.get("scene")
        detail_scene = scene
        if isinstance(scene, SceneState) and isinstance(interactables, list) and interactables:
            detail_scene = scene.model_copy(update={"interactables": interactables})
        has_npcs = bool(getattr(detail_scene, "npcs", [])) or has_model_npcs
        details: list[dict[str, Any]] = []
        for action_text in actions[:5]:
            text = str(action_text or "").strip()
            if not text:
                continue
            action = self.action_parser.parse(text, detail_scene, {"has_npcs": has_npcs})
            details.append({**self.parsed_action_payload(action), "text": text, "risk": "" if action.advances_time else "当前分类不会推进时间"})
        return details

    def ensure_pressure_clocks(
        self,
        clocks: Any,
        scene: SceneState | None = None,
        world_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.worldview.pressure_clocks(clocks, scene, world_state)

    def default_pressure_clocks(
        self,
        scene: SceneState | None = None,
        world_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.worldview.default_pressure_clocks(scene, world_state)

    def advance_pressure_clocks(
        self,
        world_state: dict[str, Any],
        turn: dict[str, Any],
        scene: SceneState | None = None,
    ) -> dict[str, Any]:
        action_type = str(turn.get("action_type") or "")
        time_state = turn.get("time") or {}
        if not time_state.get("advances_time"):
            world_state["last_pressure_advance"] = {"advanced": False, "reason": action_type}
            return world_state

        minutes = int(time_state.get("time_cost_minutes") or 0)
        base_delta = max(1, minutes // 30)
        clocks = self.ensure_pressure_clocks(world_state.get("pressure_clocks"), scene, world_state)
        affected: list[dict[str, Any]] = []
        threshold_events: list[dict[str, Any]] = []
        visible_events = [str(event) for event in world_state.get("visible_events", []) if str(event).strip()]

        def record_threshold(clock_id: str, before: int, after: int, maximum: int) -> None:
            if before >= maximum or after < maximum:
                return
            event = self.pressure_threshold_event(clock_id)
            if not event:
                return
            threshold_events.append({"id": clock_id, "value": after, "event": event})
            visible_events.append(event)

        def set_clock(clock_id: str, value: int) -> None:
            for clock in clocks:
                if clock.get("id") != clock_id:
                    continue
                before = int(clock.get("value", 0))
                maximum = int(clock.get("max", 100))
                clock["value"] = self._clamp_clock(value, maximum)
                if clock["value"] != before:
                    affected.append({"id": clock_id, "delta": clock["value"] - before, "value": clock["value"]})
                break

        def bump(clock_id: str, delta: int) -> None:
            for clock in clocks:
                if clock.get("id") != clock_id:
                    continue
                before = int(clock.get("value", 0))
                maximum = int(clock.get("max", 100))
                clock["value"] = self._clamp_clock(before + delta, maximum)
                if clock["value"] != before:
                    affected.append({"id": clock_id, "delta": clock["value"] - before, "value": clock["value"]})
                record_threshold(clock_id, before, int(clock["value"]), maximum)
                break

        if action_type == "sleep":
            set_clock("sunset", 8)
            set_clock("curfew_patrol", 5)
            set_clock("shelter_security", 20)
            has_curfew_clock = any(clock.get("id") == "curfew_patrol" for clock in clocks)
            if has_curfew_clock:
                visible_events.append("你熬过夜色，新一天的日落与宵禁压力重新计时。")
            else:
                visible_events.append("你熬过夜色，新一天的日落与庇护压力重新计时。")
            world_state["pressure_clocks"] = clocks
            world_state["visible_events"] = visible_events[-12:]
            world_state["last_pressure_advance"] = {
                "advanced": bool(affected),
                "reason": action_type,
                "time_cost_minutes": minutes,
                "affected_clocks": affected,
                "threshold_events": threshold_events,
                "overnight_reset": True,
            }
            return world_state

        bump("sunset", base_delta)
        bump("weather_thirst", max(1, minutes // 60))
        if action_type in {"gather", "forage", "search", "travel"}:
            bump("beast_activity", 2)
        if action_type in {"observe", "search", "gather", "forage", "travel", "enter_location", "leave_location"}:
            bump("environmental_hazard", 1)
        if action_type in {"short_dialogue", "seek_shelter"}:
            bump("outsider_suspicion", 1)
            bump("shelter_security", 1)
        if str(turn.get("survival", {}).get("time_of_day") or "") in {"夜晚", "深夜"}:
            bump("curfew_patrol", base_delta)
            bump("shelter_security", base_delta)

        world_state["pressure_clocks"] = clocks
        world_state["visible_events"] = visible_events[-12:]
        world_state["last_pressure_advance"] = {
            "advanced": bool(affected),
            "reason": action_type,
            "time_cost_minutes": minutes,
            "affected_clocks": affected,
            "threshold_events": threshold_events,
            "overnight_reset": False,
        }
        return world_state

    def _clamp_clock(self, value: int, maximum: int) -> int:
        return max(0, min(maximum, value))

    def pressure_threshold_event(self, clock_id: str) -> str:
        return {
            "sunset": "日落压力达到临界点，安全庇护点变少，继续拖延会让下一次移动和休息更危险。",
            "outsider_suspicion": "外来者怀疑达到临界点，附近 NPC 会提高价格、拒绝帮助或要求证明身份。",
            "curfew_patrol": "宵禁巡逻达到临界点，公开行动可能立刻遭遇巡逻盘查。",
            "beast_activity": "野兽活动达到临界点，附近留下新鲜爪印和低吼声，继续采集或赶路可能触发袭击。",
            "weather_thirst": "天气与口渴压力达到临界点，缺水和温差开始影响判断与行动效率。",
            "shelter_security": "庇护安全达到临界点，当前休息点不再可靠，需要加固、转移或承担夜间危险。",
            "environmental_hazard": "环境危险达到临界点，异常痕迹和地形风险开始限制搜索、采集和移动。",
        }.get(clock_id, "")

    def apply_structured_state_changes(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        scene: SceneState,
    ) -> SceneState:
        if turn.get("resolved_turn"):
            return scene
        result = self.state_changes.apply(
            adventure_id,
            self.get_character(adventure_id),
            scene,
            self.model_payload_for_state_changes(turn),
            parsed_action=turn.get("parsed_action"),
        )
        turn["character"] = result.character
        turn["state_changes_applied"] = result.applied
        consequence_character, consequence_world, consequence_applied = self.consequences.resolve(
            result.character,
            self.adventures.get_world_state(adventure_id),
            self.model_consequence_proposals(turn.get("model_payload") or {}),
            action_type=str(turn.get("action_type") or ""),
        )
        if consequence_applied.get("blocked") or consequence_applied.get("applied"):
            turn["state_changes_applied"] = self.merge_state_change_applied(result.applied, consequence_applied)
        if consequence_character != result.character:
            turn["character"] = self.update_character_resources(adventure_id, consequence_character)
        if consequence_world != self.adventures.get_world_state(adventure_id):
            self.adventures.update_world_state(adventure_id, consequence_world)
        if result.scene is not None:
            self.adventures.update_scene(adventure_id, result.scene)
            return result.scene
        return scene

    def model_consequence_proposals(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        state_changes = payload.get("state_changes") if isinstance(payload.get("state_changes"), dict) else {}
        result: dict[str, Any] = {}
        for key in [
            "money_changes",
            "item_rewards",
            "entitlement_changes",
            "quest_stage_changes",
            "npc_relationship_changes",
        ]:
            if key in payload:
                result[key] = payload[key]
            elif key in state_changes:
                result[key] = state_changes[key]
        return result

    def merge_state_change_applied(self, current: dict[str, Any], consequence_applied: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current or {})
        blocked = dict(merged.get("blocked") or {})
        for key, value in (consequence_applied.get("blocked") or {}).items():
            blocked[key] = value
        if blocked:
            merged["blocked"] = blocked
        applied = dict(merged.get("consequence_applied") or {})
        for key, value in (consequence_applied.get("applied") or {}).items():
            if value:
                applied[key] = value
        if applied:
            merged["consequence_applied"] = applied
        return merged

    def model_payload_for_state_changes(self, turn: dict[str, Any]) -> dict[str, Any]:
        payload = dict(turn.get("model_payload") or {})
        if (turn.get("time") or {}).get("advances_time"):
            return payload
        if not self._contains_time_transition(payload):
            return payload
        payload.pop("interactables", None)
        payload.pop("suggested_actions", None)
        turn["model_payload"] = payload
        turn["scene_update_blocked_reason"] = turn.get("scene_update_blocked_reason") or "non_advancing_time_transition"
        return payload

    def record_model_error(self, turn: dict[str, Any], stage: str, exc: Exception) -> None:
        errors = list(turn.get("model_errors") or [])
        errors.append({"stage": stage, "message": str(exc)})
        turn["model_errors"] = errors

    def learn_preferences_for_current_turn(
        self,
        adventure_id: int,
        world_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = dict(world_state or self.adventures.get_world_state(adventure_id))
        messages = [
            {"role": message.role, "content": message.content}
            for message in self.adventures.list_messages(adventure_id)
        ]
        updated = self.preference_learner.maybe_update(current, messages, self.active_model())
        self.adventures.update_world_state(adventure_id, updated)
        return updated

    def generate_narration(self, turn: dict[str, Any], locale: str = "zh-CN") -> tuple[str, str, dict[str, Any] | None]:
        if turn.get("resolved_turn"):
            return str(turn.get("resolved_content") or turn.get("fallback") or ""), "action_resolution", None
        if (turn.get("parsed_action") or {}).get("requires_clarification"):
            narration = self.clarification_narration(turn)
            turn["model_payload"] = {"narration": narration}
            return narration, "action_parser", None
        if turn.get("action_type") == "condition_failed":
            narration = self.condition_failed_narration(turn)
            turn["model_payload"] = {"narration": narration}
            return narration, "action_parser", None
        model = self.active_model()
        if model and self.llm_client and hasattr(self.llm_client, "chat"):
            try:
                raw_response = self.model_gateway.chat(model, self.build_model_messages(turn, locale))
                payload = self.parse_model_payload(raw_response, turn["fallback"])
                turn["model_payload"] = payload
                narration = self.reconcile_narration_with_scene_facts(
                    turn,
                    payload["narration"],
                )
                narration = self.repair_narration_for_turn(turn, narration)
                return narration, "active_model", payload.get("scene_update")
            except Exception as exc:
                self.record_model_error(turn, "chat", exc)
        fallback = self.reconcile_narration_with_scene_facts(turn, turn["fallback"])
        turn["model_payload"] = {}
        return self.repair_narration_for_turn(turn, fallback), "survival_rules", None

    def stream_narration(self, turn: dict[str, Any], locale: str = "zh-CN"):
        if turn.get("resolved_turn"):
            content = str(turn.get("resolved_content") or turn.get("fallback") or "")
            for chunk in chunk_text(content):
                yield {"type": "delta", "content": chunk}
            return content, "action_resolution", None
        if (turn.get("parsed_action") or {}).get("requires_clarification"):
            narration = self.clarification_narration(turn)
            turn["model_payload"] = {"narration": narration}
            for chunk in chunk_text(narration):
                yield {"type": "delta", "content": chunk}
            return narration, "action_parser", None
        if turn.get("action_type") == "condition_failed":
            narration = self.condition_failed_narration(turn)
            turn["model_payload"] = {"narration": narration}
            for chunk in chunk_text(narration):
                yield {"type": "delta", "content": chunk}
            return narration, "action_parser", None
        model = self.active_model()
        if model and self.llm_client and hasattr(self.llm_client, "stream_chat"):
            try:
                payload = yield from self.stream_model_narration(model, self.build_model_messages(turn, locale))
                turn["model_payload"] = payload
                narration = self.reconcile_narration_with_scene_facts(
                    turn,
                    payload["narration"] or turn["fallback"],
                )
                narration = self.repair_narration_for_turn(turn, narration)
                return narration, "active_model", payload.get("scene_update")
            except Exception as exc:
                self.record_model_error(turn, "stream_chat", exc)

        content, source, scene_update = self.generate_narration(turn, locale)
        for chunk in chunk_text(content):
            yield {"type": "delta", "content": chunk}
        return content, source, scene_update

    def clarification_narration(self, turn: dict[str, Any]) -> str:
        parsed = turn.get("parsed_action") or {}
        question = ((parsed.get("arguments") or {}) if isinstance(parsed, dict) else {}).get("clarification_question")
        if question:
            return str(question)
        candidates = parsed.get("candidates") if isinstance(parsed, dict) else []
        names = [str(candidate.get("name") or "").strip() for candidate in candidates if isinstance(candidate, dict)]
        names = [name for name in names if name]
        if names:
            return f"你需要先明确目标：你指的是{'、'.join(names)}中的哪一个？"
        return "你需要先把目标说清楚，当前行动存在歧义。"

    def condition_failed_narration(self, turn: dict[str, Any]) -> str:
        parsed = turn.get("parsed_action") or {}
        code = ((parsed.get("arguments") or {}) if isinstance(parsed, dict) else {}).get("failed_precondition")
        if code == "missing_water_source":
            return "你检查了周围，但这里没有可用水源，水囊无法装水。你需要先找到雨水桶、水井、溪流或其他可取水对象。"
        if code == "missing_location_target":
            return "你需要先明确要进入的地点。当前场景里没有可确认的入口目标。"
        return "当前行动缺少必要条件，暂时不能执行。"

    def stream_model_narration(self, model, messages: list[dict[str, str]]):
        payload, raw_narration = yield from self.model_gateway.stream_json_payload(model, messages)
        return self.parse_model_payload(json.dumps(payload, ensure_ascii=False), raw_narration)

    def repair_narration_for_turn(self, turn: dict[str, Any], narration: str) -> str:
        scene_payload = turn["scene"].model_dump()
        model_payload = turn.get("model_payload") if isinstance(turn.get("model_payload"), dict) else {}
        scene_update = model_payload.get("scene_update") if isinstance(model_payload, dict) else {}
        if isinstance(scene_update, dict):
            for key in ["location", "environment", "current_objective"]:
                value = scene_update.get(key)
                if isinstance(value, str) and value.strip():
                    scene_payload[key] = value.strip()
            if isinstance(scene_update.get("important_objects"), list):
                scene_payload["important_objects"] = [
                    str(item).strip() for item in scene_update["important_objects"] if str(item).strip()
                ][:8]
        return self.worldview.repair_narration(
            narration,
            {
                "visible_survival": turn.get("visible_survival") or self.visible_survival_state(turn["survival"]),
                "character": turn.get("character") or {},
                "scene": scene_payload,
                "world_state": turn.get("world_state") or {},
                "action_type": turn.get("action_type"),
            },
        )

    def active_model(self) -> LLMModelRecord | None:
        return self.model_gateway.active_model()

    def build_model_payload(
        self,
        turn: dict[str, Any],
        locale: str = "zh-CN",
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        visible_survival = turn.get("visible_survival") or self.visible_survival_state(turn["survival"])
        raw_recent_messages = recent_messages if recent_messages is not None else turn.get("recent_messages", [])
        return {
            "role_boundaries": {
                "player_input": "用户本轮输入，只能视为玩家行动意图。",
                "system_state": "后端规则已经结算的真实状态，不能被模型改写。",
                "tool_results": "后端工具/规则提供的数据，不是玩家发言。",
                "legacy_context_policy": "早期 source=survival_rules 的机械回复可信度低；以 current_scene、confirmed_location、event_impacts 和 visible_survival 为准。",
            },
            "player_input": turn["player_input"],
            "recent_messages": self.sanitize_recent_messages(raw_recent_messages),
            "system_state": {
                "scene": turn["scene"].model_dump(),
                "character": turn["character"],
                "survival": turn["survival"],
                "visible_survival": visible_survival,
                "satiety": visible_survival["satiety"],
                "hydration": visible_survival["hydration"],
                "energy": visible_survival["energy"],
                "sleep_sufficiency": visible_survival["sleep_sufficiency"],
                "status_summary": visible_survival["status_summary"],
                "survival_delta": turn["delta"],
                "action_type": turn["action_type"],
                "parsed_action": turn.get("parsed_action") or {},
                "time": turn.get("time", {}),
                "world_state": turn.get("world_state", {}),
                "active_quest": (turn.get("world_state") or {}).get("isekai_quest", {}),
                "known_clues": (turn.get("world_state") or {}).get("isekai_clues", []),
                "pressure_event_fired": bool(turn.get("pressure_event_fired")),
                "pressure_event": turn.get("pressure_event") or None,
                "pressure_goals": self.worldview.pressure_goals(turn.get("resolved_scene") or turn.get("scene"), turn.get("world_state") or {}),
                "day": turn["survival"].get("day"),
                "time_of_day": turn["survival"].get("time_of_day"),
                "survival_state_json": turn["survival"].get("state", {}),
                "model_permission_policy": {
                    "money_changes": "proposal_only",
                    "item_rewards": "proposal_only",
                    "entitlement_changes": "proposal_only",
                    "quest_stage_changes": "proposal_only",
                    "npc_relationship_changes": "proposal_only",
                    "final_state_owner": "IsekaiConsequenceResolver",
                },
            },
            "fallback_narration": turn["fallback"],
            "locale": locale,
        }

    def sanitize_recent_messages(self, recent_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for message in recent_messages:
            if not isinstance(message, dict):
                continue
            metadata = dict(message.get("metadata") or {})
            content = self.worldview.normalize_text(message.get("content"))
            if metadata.get("source") == "survival_rules":
                metadata["context_weight"] = "low"
                metadata["context_note"] = "legacy_survival_rules_downweighted"
            sanitized.append({**message, "content": content, "metadata": metadata})
        return sanitized

    def build_model_messages(self, turn: dict[str, Any], locale: str = "zh-CN") -> list[dict[str, str]]:
        payload = self.build_model_payload(turn, locale)
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界生存模拟器 DM。你负责根据玩家行动、生存状态和环境生成下一段剧情。"
                    f"{self.worldview.STYLE_GUIDANCE}"
                    f"{self.worldview.SURVIVAL_DM_GUIDANCE}"
                    "后端已经结算时间、饥饿、口渴、疲劳、睡眠需求等数值，你不能修改这些数值。"
                    "你叙事时必须使用 system_state.visible_survival 的玩家可见口径：satiety 是饱腹度，hydration 是水分，energy 是精力，sleep_sufficiency 是睡眠充足度。"
                    "当 satiety >= 70 时，禁止描写肚子饿、明显饥饿或饿得发慌，只能描写食物气味、补给意识或社交诱因。"
                    "你必须区分用户信息、系统状态和工具结果，不要把系统状态当成玩家发言。"
                    "recent_messages 是本局真实对话历史，必须用于保持地点、NPC、目标和剧情连续性。"
                    "如果 recent_messages 与 system_state.scene、confirmed_location 或 event_impacts 冲突，以 system_state 为准。"
                    "system_state.pressure_goals 是当前场景必须维持的生存压力；按其中的 label 和 detail 影响 NPC、探索、资源与选择后果。"
                    "压力事件只能在 system_state.pressure_event_fired=true 时写进旁白；否则不要重复写“宵禁压力”“外来者被排斥”“异族税压力”等系统解释句。"
                    "任务线以 system_state.active_quest 为准；如果 active_quest_id 为空，不要创建、推进或提及任务线。"
                    "回复内部必须满足：状态是否变化、场景可交互对象、NPC 态度、生存压力是否合理，并给玩家 2-3 个自然行动钩子。"
                    "如果叙事导致角色位置、环境、可交互物或当前目标改变，必须输出 scene_update。"
                    "只输出 JSON 对象，格式为 {\"narration\":\"...\",\"scene_update\":{\"location\":\"...\","
                    "\"environment\":\"...\",\"important_objects\":[\"...\"],\"current_objective\":\"...\"},"
                    "\"interactables\":[{\"id\":\"...\",\"type\":\"npc|item|place|hazard\",\"name\":\"...\","
                    "\"state\":\"...\",\"affordances\":[\"交涉\",\"采集\"],\"risk\":\"...\"}],"
                    "\"suggested_actions\":[\"...\",\"...\",\"...\"],"
                    "\"state_changes\":{\"add_items\":[],\"remove_items\":[],\"npc_updates\":[],\"pressure_updates\":[]}}。"
                    "money_changes、item_rewards、entitlement_changes、quest_stage_changes、npc_relationship_changes 全部只是 proposal，后端可能拦截；不要在 narration 宣称未由 system_state 或 fallback_narration 确认入账的奖励。"
                    "当 narration 明确确认玩家获得、丢弃或消耗物品时，必须在 state_changes.add_items 或 remove_items 写出物品中文名。"
                    "当 NPC 态度、信任或已知事实变化时，必须在 state_changes.npc_updates 写出 id、name、attitude、trust_delta 或 known_facts。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]

    def parse_model_payload(self, raw_response: str, fallback: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError:
            return {"narration": self.worldview.normalize_text(extract_narration_text(raw_response) or fallback)}
        if isinstance(payload, dict):
            narration = self.worldview.normalize_text(payload.get("narration")).strip()
            scene_update = payload.get("scene_update")
            result: dict[str, Any] = {"narration": narration or self.worldview.normalize_text(fallback)}
            if isinstance(scene_update, dict):
                result["scene_update"] = self.worldview.normalize_scene_update(scene_update)
            for key in [
                "interactables",
                "suggested_actions",
                "state_changes",
                "money_changes",
                "item_rewards",
                "entitlement_changes",
                "quest_stage_changes",
                "npc_relationship_changes",
                "scene_objects",
            ]:
                if key in payload:
                    result[key] = payload[key]
            return result
        return {"narration": self.worldview.normalize_text(fallback)}

    def parse_model_narration(self, raw_response: str, fallback: str) -> str:
        return self.parse_model_payload(raw_response, fallback)["narration"]

    def recent_messages_payload(
        self,
        adventure_id: int,
        max_context_tokens: int = 4096,
        reserved_payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.model_gateway.recent_message_payloads(
            adventure_id,
            max_context_tokens=max_context_tokens,
            reserved_payload=reserved_payload,
        )

    def reconcile_narration_with_scene_facts(self, turn: dict[str, Any], narration: str) -> str:
        scene = turn["scene"]
        world_state = turn.get("world_state") or {}
        confirmed_location = str(world_state.get("confirmed_location") or scene.location or "").strip()
        if not confirmed_location:
            return narration
        contradiction_markers = ["并未抵达", "没有抵达", "仍在雾林边境", "还在雾林边境"]
        if any(marker in narration for marker in contradiction_markers) and confirmed_location not in narration:
            return (
                f"你重新确认方位：当前位于{confirmed_location}。"
                "先前已经发生的位置变化不会被抹掉；你可以在这里继续观察、交谈，或明确前往新的地点。"
            )
        return narration

    def apply_scene_progression(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        narration: str,
        scene_update: dict[str, Any] | None,
    ) -> SceneState:
        if turn.get("resolved_turn") and isinstance(turn.get("resolved_scene"), SceneState):
            return turn["resolved_scene"]
        scene = turn["scene"]
        patch = self.clean_scene_update(scene_update)
        model_payload = turn.get("model_payload") if isinstance(turn.get("model_payload"), dict) else {}
        if not (turn.get("time") or {}).get("advances_time"):
            if patch:
                turn["scene_update_blocked_reason"] = (
                    "non_advancing_time_transition"
                    if self._contains_time_transition(patch)
                    else "non_advancing_scene_update"
                )
                return scene
        inferred_location = self.infer_location_from_turn(turn, narration)
        if inferred_location and not patch.get("location"):
            patch["location"] = inferred_location
        if not patch:
            scene_with_objects = self.materialize_scene_objects_for_turn(scene, turn)
            if scene_with_objects.model_dump() != scene.model_dump():
                self.adventures.update_scene(adventure_id, scene_with_objects)
            return scene_with_objects

        old_location = scene.location
        new_location = str(patch.get("location") or scene.location).strip() or scene.location
        if new_location != old_location and not self.action_allows_location_change(turn):
            turn["scene_update_blocked_reason"] = "location_change_requires_movement_action"
            return scene
        important_objects = patch.get("important_objects")
        if not isinstance(important_objects, list):
            important_objects = scene.important_objects

        world_changes = list(scene.world_changes)
        location_changed = new_location != old_location
        if location_changed:
            world_changes.append(f"位置从{old_location}推进到{new_location}。")

        next_scene = SceneState(
            location=new_location,
            environment=str(patch.get("environment") or scene.environment),
            important_objects=[str(item) for item in important_objects if str(item).strip()],
            npcs=[] if location_changed else scene.npcs,
            current_objective=str(patch.get("current_objective") or scene.current_objective),
            world_changes=world_changes[-12:],
            interactables=[] if location_changed else scene.interactables,
            suggested_actions=[] if location_changed else scene.suggested_actions,
            npc_states=scene.npc_states,
        )
        next_scene = self.project_interactables_if_needed(next_scene, turn)
        next_scene = self.materialize_scene_objects_for_turn(next_scene, turn)
        self.adventures.update_scene(adventure_id, next_scene)
        if location_changed:
            history_entry = self.location_history_entry(old_location, new_location, turn, narration)
            self.update_survival_location(adventure_id, new_location, history_entry)
            self.update_world_location_history(adventure_id, history_entry)
        return next_scene

    def materialize_scene_objects_for_turn(self, scene: SceneState, turn: dict[str, Any]) -> SceneState:
        model_payload = turn.get("model_payload") if isinstance(turn.get("model_payload"), dict) else {}
        next_scene, metadata = self.content.materialize_scene_objects(scene, model_payload.get("scene_objects"))
        if metadata:
            turn["scene_object_source"] = metadata.get("source")
            turn["scene_objects_applied"] = metadata
        suggested = model_payload.get("suggested_actions")
        if isinstance(suggested, list):
            explicit = [str(item) for item in suggested if str(item).strip()]
            next_scene = next_scene.model_copy(update={"suggested_actions": list(dict.fromkeys(explicit))[:8]})
        return next_scene

    def action_allows_location_change(self, turn: dict[str, Any]) -> bool:
        return str(turn.get("action_type") or "") in {"travel", "enter_location", "leave_location"}

    def project_interactables_if_needed(self, scene: SceneState, turn: dict[str, Any]) -> SceneState:
        if scene.interactables:
            return scene
        interactables, suggestions = self.interactable_projector.project(scene, str(turn.get("action_type") or ""))
        if not interactables and not suggestions:
            return scene
        return scene.model_copy(update={"interactables": interactables, "suggested_actions": suggestions})

    def clean_scene_update(self, scene_update: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(scene_update, dict):
            return {}
        scene_update = self.worldview.normalize_scene_update(scene_update)
        patch: dict[str, Any] = {}
        for key in ["location", "environment", "current_objective"]:
            value = self.worldview.normalize_text(scene_update.get(key)).strip()
            if value:
                patch[key] = value
        objects = scene_update.get("important_objects")
        if isinstance(objects, list):
            cleaned = self.worldview.normalize_list(objects, limit=8)
            if cleaned:
                patch["important_objects"] = cleaned
        return patch

    def _contains_time_transition(self, value: Any) -> bool:
        markers = ["清晨", "天亮", "真正的天亮", "早晨", "日出", "黄昏", "日落", "夜晚", "深夜"]
        if isinstance(value, dict):
            return any(self._contains_time_transition(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_time_transition(item) for item in value)
        return any(marker in str(value or "") for marker in markers)

    def infer_location_from_turn(self, turn: dict[str, Any], narration: str) -> str:
        if not (turn.get("time") or {}).get("advances_time"):
            return ""
        combined = f"{turn.get('player_input', '')}\n{narration}"
        if "白石镇外" in combined and "木质哨站" in combined:
            return "白石镇外木质哨站"
        if "木质哨站" in combined:
            return "木质哨站"
        if "白石镇" in combined and any(word in combined for word in ["矮墙", "镇外", "城墙"]):
            return "白石镇外"
        if "白石镇" in combined:
            return "白石镇"
        if "营地" in combined and any(word in combined for word in ["抵达", "来到", "到达"]):
            return "路边营地"

        destination = self.destination_from_input(str(turn.get("player_input") or ""))
        if destination in {"城镇", "镇子", "镇上"}:
            return f"前往{destination}的路上"
        return destination

    def destination_from_input(self, player_input: str) -> str:
        text = str(player_input or "").strip()
        for marker in ["继续去", "前往", "去往", "移动到", "走到", "赶往", "进入", "去"]:
            if marker not in text:
                continue
            candidate = text.split(marker, 1)[1]
            for stop in ["，", "。", "！", "？", ",", ".", "!", "?", " "]:
                candidate = candidate.split(stop, 1)[0]
            candidate = candidate.strip()
            if candidate:
                return self.worldview.normalize_text(candidate[:20])
        return ""

    def location_history_entry(
        self,
        old_location: str,
        new_location: str,
        turn: dict[str, Any],
        narration: str,
    ) -> dict[str, Any]:
        return {
            "from": self.worldview.normalize_text(old_location),
            "to": self.worldview.normalize_text(new_location),
            "triggering_action": turn.get("player_input", ""),
            "day": turn.get("survival", {}).get("day"),
            "time_of_day": turn.get("survival", {}).get("time_of_day"),
            "summary": self.worldview.normalize_text(narration[:160]),
        }

    def update_survival_location(
        self,
        adventure_id: int,
        location: str,
        history_entry: dict[str, Any],
    ) -> None:
        current = self.adventures.get(adventure_id, include_messages=False).survival_state or {}
        state = dict(current.get("state") or {})
        history = list(state.get("location_history") or [])
        history.append(history_entry)
        state["location_history"] = history[-20:]
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE isekai_survival_states
                SET location = :location, state_json = :state_json, updated_at = CURRENT_TIMESTAMP
                WHERE adventure_id = :adventure_id
                """,
                {
                    "adventure_id": adventure_id,
                    "location": location,
                    "state_json": encode_json(state),
                },
            )

    def update_world_location_history(self, adventure_id: int, history_entry: dict[str, Any]) -> None:
        world_state = self.adventures.get_world_state(adventure_id)
        history = list(world_state.get("location_history") or [])
        history.append(history_entry)
        world_state["location_history"] = history[-20:]
        world_state["confirmed_location"] = history_entry["to"]
        self.adventures.update_world_state(adventure_id, world_state)

    def apply_delta(self, adventure_id: int, action: IsekaiActionResolution) -> tuple[dict[str, Any], dict[str, Any]]:
        current = self.adventures.get(adventure_id, include_messages=False).survival_state or {}
        updated, delta = self.time.apply_time_and_survival(current, action)
        self.persist_survival_snapshot(adventure_id, updated)
        return delta, updated

    def persist_survival_snapshot(self, adventure_id: int, updated: dict[str, Any]) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE isekai_survival_states
                SET day = :day, time_of_day = :time_of_day,
                    hunger = :hunger, thirst = :thirst, fatigue = :fatigue, sleep_need = :sleep_need,
                    temperature_risk = :temperature_risk, morale = :morale,
                    weather = :weather, location = :location, shelter = :shelter,
                    last_action_type = :last_action_type, state_json = :state_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE adventure_id = :adventure_id
                """,
                {**updated, "adventure_id": adventure_id, "state_json": encode_json(updated.get("state") or {})},
            )

    def get_character(self, adventure_id: int) -> dict[str, Any]:
        adventure = self.adventures.get(adventure_id, include_messages=False)
        return adventure.isekai_character or {}

    def update_character_resources(self, adventure_id: int, character: dict[str, Any]) -> dict[str, Any]:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE isekai_characters
                SET hp_current = :hp_current,
                    inventory_json = :inventory_json,
                    status_effects_json = :status_effects_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE adventure_id = :adventure_id
                """,
                {
                    "adventure_id": adventure_id,
                    "hp_current": int(character.get("hp_current", 0)),
                    "inventory_json": encode_json(character.get("inventory") or []),
                    "status_effects_json": encode_json(character.get("status_effects") or []),
                },
            )
        return self.get_character(adventure_id)

    def narrate(
        self,
        player_input: str,
        scene: SceneState,
        character: dict[str, Any],
        survival: dict[str, Any],
        delta: dict[str, Any],
    ) -> str:
        return self.worldview.normalize_text(
            self.fallback_narrator.narrate(player_input, scene, character, survival, delta)
        )
