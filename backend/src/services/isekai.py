from __future__ import annotations

import random

from backend.src.db.sqlite import SQLiteStore, encode_json
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, SceneState
from backend.src.schemas.isekai import IsekaiCharacterOut, IsekaiSurvivalStateOut
from backend.src.services.adventures import AdventureService


RACES = ["Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Tiefling"]
CLASSES = ["Fighter", "Ranger", "Rogue", "Wizard", "Cleric", "Druid"]
NAMES = ["艾瑞克", "莉娅", "诺恩", "米拉", "赛兰", "塔维"]


class IsekaiSurvivalService:
    def __init__(self, store: SQLiteStore, llm_client=None):
        self.store = store
        self.adventures = AdventureService(store)
        self.llm_client = llm_client

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
