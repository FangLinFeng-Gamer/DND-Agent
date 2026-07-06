from __future__ import annotations

import json
import random
from typing import Any

from backend.src.agent.dm.output import chunk_text, extract_narration_text
from backend.src.db.sqlite import SQLiteStore, encode_json
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, DMAdvanceResponse, MessageCreate, SceneState
from backend.src.schemas.llm import LLMModelRecord
from backend.src.schemas.isekai import IsekaiCharacterOut, IsekaiSurvivalStateOut
from backend.src.services.adventures import AdventureService
from backend.src.services.isekai_events import IsekaiWorldEventDirector
from backend.src.services.isekai_preferences import IsekaiPreferenceLearner
from backend.src.services.isekai_time import IsekaiActionResolution, IsekaiTimeService
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
        self.event_director = IsekaiWorldEventDirector(store)
        self.preference_learner = IsekaiPreferenceLearner(llm_client=llm_client)
        self.time = IsekaiTimeService()

    def generate_character(self) -> IsekaiCharacterOut:
        race = random.choice(RACES)
        class_name = random.choice(CLASSES)
        inventory = ["干粮 x2", "水囊", "火绒盒", "旧斗篷"]
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
            gold=random.randint(8, 24),
            inventory=inventory,
            traits=[race, class_name],
            world_reaction_tags=[race.lower(), class_name.lower(), "outsider"],
        )

    def initial_survival_state(self, scene: SceneState) -> IsekaiSurvivalStateOut:
        return IsekaiSurvivalStateOut(location=scene.location, weather="薄雾")

    def create_adventure(self, request: AdventureCreate) -> AdventureOut:
        character = self.generate_character()
        scene = SceneState(
            location="雾林边境",
            environment="你在一片潮湿针叶林边缘醒来，远处有微弱火光，脚下泥土留下陌生车辙。",
            important_objects=["潮湿脚印", "微弱火光", "旧猎径"],
            npcs=[],
            current_objective="找到夜间避难处，并确认附近是否有水源或食物。",
            world_changes=[],
        )
        survival = self.initial_survival_state(scene)
        adventure = self.adventures.create_isekai_shell(request, scene)
        self.save_character(adventure.id, character)
        self.save_survival_state(adventure.id, survival)
        self.adventures.append_message(
            adventure.id,
            "dm",
            self.opening_text(character, scene, survival),
            {"kind": "opening", "mode": "isekai_survival"},
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

    def opening_text(
        self,
        character: IsekaiCharacterOut,
        scene: SceneState,
        survival: IsekaiSurvivalStateOut,
    ) -> str:
        return (
            f"{character.name}，{character.race} {character.class_name}，在{scene.location}醒来。"
            f"{scene.environment} 当前目标：{scene.current_objective}"
            f" 你的金币为 {character.gold}，饥饿 {survival.hunger}，口渴 {survival.thirst}，疲劳 {survival.fatigue}。"
        )

    def advance(self, adventure_id: int, message: MessageCreate) -> DMAdvanceResponse:
        turn = self.prepare_turn(adventure_id, message)
        content, source, scene_update = self.generate_narration(turn, message.locale)
        scene = self.apply_scene_progression(adventure_id, turn, content, scene_update)
        metadata = self.message_metadata(turn, source, scene_update)
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
        metadata = self.message_metadata(turn, source, scene_update)
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
        action = self.time.classify_action(message.content)
        delta, survival = self.apply_delta(adventure_id, action)
        scene = self.adventures.get_scene(adventure_id)
        character = self.get_character(adventure_id)
        fallback = self.narrate(message.content, scene, character, survival, delta)
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action.action_type,
            "action": action,
            "time": {
                "time_cost_minutes": delta["time_cost_minutes"],
                "advances_time": delta["advances_time"],
                "survival_intent": action.survival_intent,
                "reason": action.reason,
            },
            "delta": delta,
            "survival": survival,
            "scene": scene,
            "character": character,
            "recent_messages": [],
            "fallback": fallback,
        }
        turn["world_state"] = self.advance_world_context(adventure_id, turn, learn_preferences=learn_preferences)
        model = self.active_model()
        reserved_payload = self.build_model_payload(turn, message.locale, recent_messages=[])
        turn["recent_messages"] = self.recent_messages_payload(
            adventure_id,
            max_context_tokens=model.max_context_tokens if model else 4096,
            reserved_payload=reserved_payload,
        )
        return turn

    def advance_world_context(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        learn_preferences: bool = True,
    ) -> dict[str, Any]:
        world_state = self.adventures.get_world_state(adventure_id)
        world_state["turn_count"] = int(world_state.get("turn_count", 0)) + 1
        if learn_preferences:
            world_state = self.learn_preferences_for_current_turn(adventure_id, world_state)
        else:
            self.adventures.update_world_state(adventure_id, world_state)
        self.event_director.evaluate_turn(adventure_id, turn, world_state)
        return world_state

    def message_metadata(
        self,
        turn: dict[str, Any],
        source: str,
        scene_update: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata = {
            "mode": "isekai_survival",
            "survival_delta": turn["delta"],
            "time": turn["time"],
            "scene_update": scene_update or {},
            "source": source,
        }
        if turn.get("model_errors"):
            metadata["model_errors"] = turn["model_errors"]
        return metadata

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
        model = self.active_model()
        if model and self.llm_client and hasattr(self.llm_client, "chat"):
            try:
                raw_response = self.model_gateway.chat(model, self.build_model_messages(turn, locale))
                payload = self.parse_model_payload(raw_response, turn["fallback"])
                return payload["narration"], "active_model", payload.get("scene_update")
            except Exception as exc:
                self.record_model_error(turn, "chat", exc)
        return turn["fallback"], "survival_rules", None

    def stream_narration(self, turn: dict[str, Any], locale: str = "zh-CN"):
        model = self.active_model()
        if model and self.llm_client and hasattr(self.llm_client, "stream_chat"):
            try:
                payload = yield from self.stream_model_narration(model, self.build_model_messages(turn, locale))
                return payload["narration"] or turn["fallback"], "active_model", payload.get("scene_update")
            except Exception as exc:
                self.record_model_error(turn, "stream_chat", exc)

        content, source, scene_update = self.generate_narration(turn, locale)
        for chunk in chunk_text(content):
            yield {"type": "delta", "content": chunk}
        return content, source, scene_update

    def stream_model_narration(self, model, messages: list[dict[str, str]]):
        payload, raw_narration = yield from self.model_gateway.stream_json_payload(model, messages)
        return self.parse_model_payload(json.dumps(payload, ensure_ascii=False), raw_narration)

    def active_model(self) -> LLMModelRecord | None:
        return self.model_gateway.active_model()

    def build_model_payload(
        self,
        turn: dict[str, Any],
        locale: str = "zh-CN",
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "role_boundaries": {
                "player_input": "用户本轮输入，只能视为玩家行动意图。",
                "system_state": "后端规则已经结算的真实状态，不能被模型改写。",
                "tool_results": "后端工具/规则提供的数据，不是玩家发言。",
            },
            "player_input": turn["player_input"],
            "recent_messages": recent_messages if recent_messages is not None else turn.get("recent_messages", []),
            "system_state": {
                "scene": turn["scene"].model_dump(),
                "character": turn["character"],
                "survival": turn["survival"],
                "survival_delta": turn["delta"],
                "action_type": turn["action_type"],
                "time": turn.get("time", {}),
                "world_state": turn.get("world_state", {}),
                "day": turn["survival"].get("day"),
                "time_of_day": turn["survival"].get("time_of_day"),
                "survival_state_json": turn["survival"].get("state", {}),
            },
            "fallback_narration": turn["fallback"],
            "locale": locale,
        }

    def build_model_messages(self, turn: dict[str, Any], locale: str = "zh-CN") -> list[dict[str, str]]:
        payload = self.build_model_payload(turn, locale)
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界生存模拟器 DM。你负责根据玩家行动、生存状态和环境生成下一段剧情。"
                    "后端已经结算时间、饥饿、口渴、疲劳、睡眠需求等数值，你不能修改这些数值。"
                    "你必须区分用户信息、系统状态和工具结果，不要把系统状态当成玩家发言。"
                    "recent_messages 是本局真实对话历史，必须用于保持地点、NPC、目标和剧情连续性。"
                    "如果叙事导致角色位置、环境、可交互物或当前目标改变，必须输出 scene_update。"
                    "只输出 JSON 对象，格式为 {\"narration\":\"...\",\"scene_update\":{\"location\":\"...\","
                    "\"environment\":\"...\",\"important_objects\":[\"...\"],\"current_objective\":\"...\"}}。"
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
            return {"narration": extract_narration_text(raw_response) or fallback}
        if isinstance(payload, dict):
            narration = str(payload.get("narration") or "").strip()
            scene_update = payload.get("scene_update")
            result: dict[str, Any] = {"narration": narration or fallback}
            if isinstance(scene_update, dict):
                result["scene_update"] = scene_update
            return result
        return {"narration": fallback}

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

    def apply_scene_progression(
        self,
        adventure_id: int,
        turn: dict[str, Any],
        narration: str,
        scene_update: dict[str, Any] | None,
    ) -> SceneState:
        scene = turn["scene"]
        patch = self.clean_scene_update(scene_update)
        inferred_location = self.infer_location_from_turn(turn, narration)
        if inferred_location and not patch.get("location"):
            patch["location"] = inferred_location
        if not patch:
            return scene

        old_location = scene.location
        new_location = str(patch.get("location") or scene.location).strip() or scene.location
        important_objects = patch.get("important_objects")
        if not isinstance(important_objects, list):
            important_objects = scene.important_objects

        world_changes = list(scene.world_changes)
        if new_location != old_location:
            world_changes.append(f"位置从{old_location}推进到{new_location}。")

        next_scene = SceneState(
            location=new_location,
            environment=str(patch.get("environment") or scene.environment),
            important_objects=[str(item) for item in important_objects if str(item).strip()],
            npcs=scene.npcs,
            current_objective=str(patch.get("current_objective") or scene.current_objective),
            world_changes=world_changes[-12:],
        )
        self.adventures.update_scene(adventure_id, next_scene)
        if new_location != old_location:
            history_entry = self.location_history_entry(old_location, new_location, turn, narration)
            self.update_survival_location(adventure_id, new_location, history_entry)
            self.update_world_location_history(adventure_id, history_entry)
        return next_scene

    def clean_scene_update(self, scene_update: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(scene_update, dict):
            return {}
        patch: dict[str, Any] = {}
        for key in ["location", "environment", "current_objective"]:
            value = str(scene_update.get(key) or "").strip()
            if value:
                patch[key] = value
        objects = scene_update.get("important_objects")
        if isinstance(objects, list):
            cleaned = [str(item).strip() for item in objects if str(item).strip()]
            if cleaned:
                patch["important_objects"] = cleaned[:8]
        return patch

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
                return candidate[:20]
        return ""

    def location_history_entry(
        self,
        old_location: str,
        new_location: str,
        turn: dict[str, Any],
        narration: str,
    ) -> dict[str, Any]:
        return {
            "from": old_location,
            "to": new_location,
            "triggering_action": turn.get("player_input", ""),
            "day": turn.get("survival", {}).get("day"),
            "time_of_day": turn.get("survival", {}).get("time_of_day"),
            "summary": narration[:160],
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
        self.adventures.update_world_state(adventure_id, world_state)

    def apply_delta(self, adventure_id: int, action: IsekaiActionResolution) -> tuple[dict[str, Any], dict[str, Any]]:
        current = self.adventures.get(adventure_id, include_messages=False).survival_state or {}
        updated, delta = self.time.apply_time_and_survival(current, action)
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
        return delta, updated

    def get_character(self, adventure_id: int) -> dict[str, Any]:
        adventure = self.adventures.get(adventure_id, include_messages=False)
        return adventure.isekai_character or {}

    def narrate(
        self,
        player_input: str,
        scene: SceneState,
        character: dict[str, Any],
        survival: dict[str, Any],
        delta: dict[str, Any],
    ) -> str:
        name = character.get("name") or "你"
        event_text = " ".join(delta.get("visible_events") or [])
        return (
            f"{name}继续在{scene.location}行动：{player_input}"
            f"{event_text} 当前是第 {survival['day']} 天{survival['time_of_day']}。"
            f" 当前饥饿 {survival['hunger']}，口渴 {survival['thirst']}，"
            f"疲劳 {survival['fatigue']}，睡眠需求 {survival['sleep_need']}。"
        )
