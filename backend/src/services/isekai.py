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
from backend.src.services.llm_models import LLMModelService


RACES = ["Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"]
CLASSES = ["Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"]
NAMES = ["艾瑞克", "莉娅", "诺恩", "米拉", "赛兰", "塔维"]


class IsekaiSurvivalService:
    def __init__(self, store: SQLiteStore, llm_client=None):
        self.store = store
        self.adventures = AdventureService(store)
        self.models = LLMModelService(store)
        self.llm_client = llm_client
        self.event_director = IsekaiWorldEventDirector(store)
        self.preference_learner = IsekaiPreferenceLearner(llm_client=llm_client)

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
        content, source = self.generate_narration(turn, message.locale)
        dm_message = self.adventures.append_message(
            adventure_id,
            "dm",
            content,
            {"mode": "isekai_survival", "survival_delta": turn["delta"], "source": source},
        )
        updated = self.adventures.get(adventure_id)
        return DMAdvanceResponse(
            adventure=updated,
            dm_message=dm_message,
            scene=turn["scene"],
            messages=updated.messages,
            world_state=updated.world_state,
            combat_state=None,
            dice_result=None,
        )

    def advance_stream(self, adventure_id: int, message: MessageCreate):
        yield {"type": "status", "message": "dm_thinking"}
        turn = self.prepare_turn(adventure_id, message, learn_preferences=False)
        yield {"type": "player_message", "message": turn["player_message"]}
        content, source = yield from self.stream_narration(turn, message.locale)
        dm_message = self.adventures.append_message(
            adventure_id,
            "dm",
            content,
            {"mode": "isekai_survival", "survival_delta": turn["delta"], "source": source},
        )
        turn["world_state"] = self.learn_preferences_for_current_turn(adventure_id)
        updated = self.adventures.get(adventure_id)
        yield {
            "type": "final",
            "adventure": updated,
            "dm_message": dm_message,
            "scene": turn["scene"],
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
        action_type = self.classify_action(message.content)
        delta = self.survival_delta_for_action(action_type)
        survival = self.apply_delta(adventure_id, action_type, delta)
        scene = self.adventures.get_scene(adventure_id)
        character = self.get_character(adventure_id)
        fallback = self.narrate(message.content, scene, character, survival, delta)
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action_type,
            "delta": delta,
            "survival": survival,
            "scene": scene,
            "character": character,
            "fallback": fallback,
        }
        turn["world_state"] = self.advance_world_context(adventure_id, turn, learn_preferences=learn_preferences)
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

    def generate_narration(self, turn: dict[str, Any], locale: str = "zh-CN") -> tuple[str, str]:
        model = self.active_model()
        if model and self.llm_client and hasattr(self.llm_client, "chat"):
            try:
                raw_response = self.llm_client.chat(model, self.build_model_messages(turn, locale))
                return self.parse_model_narration(raw_response, turn["fallback"]), "active_model"
            except Exception:
                pass
        return turn["fallback"], "survival_rules"

    def stream_narration(self, turn: dict[str, Any], locale: str = "zh-CN"):
        model = self.active_model()
        if model and self.llm_client and hasattr(self.llm_client, "stream_chat"):
            try:
                content = yield from self.stream_model_narration(model, self.build_model_messages(turn, locale))
                return content or turn["fallback"], "active_model"
            except Exception:
                pass

        content, source = self.generate_narration(turn, locale)
        for chunk in chunk_text(content):
            yield {"type": "delta", "content": chunk}
        return content, source

    def stream_model_narration(self, model: LLMModelRecord, messages: list[dict[str, str]]):
        chunks: list[str] = []
        emitted_narration_length = 0
        for chunk in self.llm_client.stream_chat(model, messages):
            chunks.append(chunk)
            narration = extract_narration_text("".join(chunks))
            if len(narration) > emitted_narration_length:
                delta = narration[emitted_narration_length:]
                emitted_narration_length = len(narration)
                yield {"type": "delta", "content": delta}
        raw_response = "".join(chunks)
        return self.parse_model_narration(raw_response, extract_narration_text(raw_response))

    def active_model(self) -> LLMModelRecord | None:
        return self.models.get_active_record()

    def build_model_messages(self, turn: dict[str, Any], locale: str = "zh-CN") -> list[dict[str, str]]:
        payload = {
            "role_boundaries": {
                "player_input": "用户本轮输入，只能视为玩家行动意图。",
                "system_state": "后端规则已经结算的真实状态，不能被模型改写。",
                "tool_results": "后端工具/规则提供的数据，不是玩家发言。",
            },
            "player_input": turn["player_input"],
            "system_state": {
                "scene": turn["scene"].model_dump(),
                "character": turn["character"],
                "survival": turn["survival"],
                "survival_delta": turn["delta"],
                "action_type": turn["action_type"],
            },
            "fallback_narration": turn["fallback"],
            "locale": locale,
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是异世界生存模拟器 DM。你负责根据玩家行动、生存状态和环境生成下一段剧情。"
                    "后端已经结算饥饿、口渴、疲劳、睡眠需求等数值，你不能修改这些数值。"
                    "你必须区分用户信息、系统状态和工具结果，不要把系统状态当成玩家发言。"
                    "只输出 JSON 对象，格式为 {\"narration\":\"...\"}。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]

    def parse_model_narration(self, raw_response: str, fallback: str) -> str:
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError:
            return extract_narration_text(raw_response) or fallback
        if isinstance(payload, dict):
            narration = str(payload.get("narration") or "").strip()
            if narration:
                return narration
        return fallback

    def classify_action(self, content: str) -> str:
        text = content.lower()
        if any(word in text for word in ["休息", "睡", "camp", "rest"]):
            return "rest"
        if any(word in text for word in ["吃", "喝", "食物", "水", "food", "water"]):
            return "forage"
        if any(word in text for word in ["探索", "走", "寻找", "inspect", "explore", "move"]):
            return "explore"
        return "talk"

    def survival_delta_for_action(self, action_type: str) -> dict[str, Any]:
        if action_type == "rest":
            return {
                "hunger": 2,
                "thirst": 2,
                "fatigue": -12,
                "sleep_need": -18,
                "visible_events": ["你短暂休整，疲劳有所缓解。"],
            }
        if action_type == "forage":
            return {
                "hunger": 1,
                "thirst": 2,
                "fatigue": 6,
                "sleep_need": 3,
                "visible_events": ["寻找资源消耗了体力。"],
            }
        if action_type == "explore":
            return {
                "hunger": 3,
                "thirst": 4,
                "fatigue": 8,
                "sleep_need": 4,
                "visible_events": ["探索让你更加疲惫和口渴。"],
            }
        return {"hunger": 0, "thirst": 1, "fatigue": 1, "sleep_need": 0, "visible_events": []}

    def apply_delta(self, adventure_id: int, action_type: str, delta: dict[str, Any]) -> dict[str, Any]:
        current = self.adventures.get(adventure_id, include_messages=False).survival_state or {}
        updated = dict(current)
        for key in ["hunger", "thirst", "fatigue", "sleep_need", "temperature_risk", "morale"]:
            updated[key] = max(0, min(100, int(updated.get(key, 0)) + int(delta.get(key, 0))))
        updated["last_action_type"] = action_type
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE isekai_survival_states
                SET hunger = :hunger, thirst = :thirst, fatigue = :fatigue, sleep_need = :sleep_need,
                    temperature_risk = :temperature_risk, morale = :morale,
                    last_action_type = :last_action_type, updated_at = CURRENT_TIMESTAMP
                WHERE adventure_id = :adventure_id
                """,
                {**updated, "adventure_id": adventure_id},
            )
        return updated

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
            f"{event_text} 当前饥饿 {survival['hunger']}，口渴 {survival['thirst']}，"
            f"疲劳 {survival['fatigue']}，睡眠需求 {survival['sleep_need']}。"
        )
