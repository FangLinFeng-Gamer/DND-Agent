import json
from typing import Any, Protocol

from pydantic import ValidationError

from backend.src.agent.dm.memory import AgentMemoryManager
from backend.src.agent.dm.output import chunk_text, extract_narration_text
from backend.src.agent.dm.prompts import (
    build_dm_messages,
    build_npc_combat_action_messages,
    build_opening_scene_messages,
)
from backend.src.agent.dm.graph import DMGraphRunner
from backend.src.agent.dm.schemas import AbilityCheckRequest
from backend.src.agent.dm.skill_registry import (
    DMSkill,
    DMSkillRegistry,
    skills_prompt_payload,
)
from backend.src.agent.dm.subagents import CombatEventAgent, NarrationAgent
from backend.src.agent.dm.workflows import DeterministicWorkflows
from backend.src.agent.dm.tools import DMAgentTools
from backend.src.agent.locale import normalize_locale
from backend.src.agent.llm.client import OpenAICompatibleClient
from backend.src.agent.llm.langchain_model import OpenAICompatibleChatModel
from backend.src.schemas.adventure import AdventureCreate, AdventureOut, DMAdvanceResponse, MessageCreate, SceneState
from backend.src.schemas.character import CharacterOut
from backend.src.schemas.llm import LLMModelRecord
from backend.src.schemas.story import StoryOut
from backend.src.schemas.world import WorldEntryOut
from backend.src.schemas.world_event import WorldEventCreate
from backend.src.services.combat import CombatService
from backend.src.services.combat_log import append_combat_log_entry
from backend.src.services.character_state import CharacterStateService
from backend.src.services.context import ContextBundle
from backend.src.services.maps import MapAttackRangeError, MapService
from backend.src.services.world_state import WorldStateService


COMBAT_INTENT_KEYWORDS = (
    "attack",
    "fight",
    "combat",
    "strike",
    "shoot",
    "stab",
    "slash",
    "charge",
    "ambush",
    "攻击",
    "战斗",
    "开打",
    "打它",
    "冲向",
    "砍",
    "射击",
    "伏击",
)


class LLMProvider(Protocol):
    def opening_scene(
        self,
        character: CharacterOut,
        world_entries: list[WorldEntryOut],
        story: StoryOut | None = None,
        locale: str = "en",
    ) -> tuple[SceneState, str]:
        ...

    def advance(
        self,
        scene: SceneState,
        player_input: str,
        dice_result: dict[str, Any] | None,
        combat_state: dict[str, Any] | None,
        locale: str = "en",
    ) -> tuple[SceneState, str]:
        ...


class TemplateDMProvider:
    def opening_scene(
        self,
        character: CharacterOut,
        world_entries: list[WorldEntryOut],
        story: StoryOut | None = None,
        locale: str = "en",
    ) -> tuple[SceneState, str]:
        locale = normalize_locale(locale)
        if story:
            scene = SceneState(
                location=story.opening_location,
                environment=story.opening_environment,
                important_objects=story.important_objects,
                npcs=story.npcs,
                current_objective=story.opening_objective,
                world_changes=[],
            )
            if locale == "zh-CN":
                content = (
                    f"世界背景：{story.world_background}\n\n"
                    f"主线任务：{story.main_quest}\n\n"
                    f"当前环境：{story.opening_environment}\n\n"
                    f"当前目标：{story.opening_objective}"
                )
            else:
                content = (
                    f"World background: {story.world_background}\n\n"
                    f"Main quest: {story.main_quest}\n\n"
                    f"Current environment: {story.opening_environment}\n\n"
                    f"Immediate objective: {story.opening_objective}"
                )
            return scene, content

        setting = next((entry.name for entry in world_entries if entry.category == "setting"), "Borderlands")
        scene = SceneState(
            location="Old Road Watchtower",
            environment=f"A wind-scoured ruin on the edge of the {setting}.",
            important_objects=["weathered door", "fallen banner", "stone stair"],
            npcs=[],
            current_objective="Find a safe way into the watchtower.",
            world_changes=[],
        )
        if locale == "zh-CN":
            content = (
                f"{character.name}来到古道守望塔。"
                "一扇饱经风霜的门挡住了下层大厅，空气中弥漫着雨水落在石头上的气味。"
            )
        else:
            content = (
                f"{character.name} arrives at the Old Road Watchtower. "
                "A weathered door blocks the lower hall, and the air carries the smell of rain on stone."
            )
        return scene, content

    def advance(
        self,
        scene: SceneState,
        player_input: str,
        dice_result: dict[str, Any] | None,
        combat_state: dict[str, Any] | None,
        locale: str = "en",
    ) -> tuple[SceneState, str]:
        locale = normalize_locale(locale)
        normalized = player_input.lower()
        changes = list(scene.world_changes)
        objective = scene.current_objective

        if dice_result is not None:
            focus = scene.important_objects[0] if scene.important_objects else scene.location
            if locale == "zh-CN":
                outcome = "成功" if dice_result["success"] else "部分成功"
                content = (
                    f"你的谨慎检定取得了{outcome}：你从{focus}发现了一条有用的线索。"
                    f"{scene.location}的局势随之发生变化，你现在有了更清晰的前进方向。"
                )
                objective = f"利用在{scene.location}发现的新信息，或选择另一种行动方式。"
                changes.append(f"在{scene.location}发现了一条有用线索。")
            else:
                outcome = "success" if dice_result["success"] else "partial success"
                content = (
                    f"Your careful check is a {outcome}: {focus} reveals a useful detail. "
                    f"The situation at {scene.location} shifts as you gain a clearer path forward."
                )
                objective = f"Use the new information at {scene.location} or choose another approach."
                changes.append(f"A useful detail was discovered at {scene.location}.")
        elif combat_state and combat_state.get("is_active"):
            if locale == "zh-CN":
                content = "武器已经出鞘，局势骤然进入战斗。接下来的行动将按照先攻顺序进行。"
                objective = "在战斗中存活并控制当前区域。"
                changes.append("当前场景进入了战斗状态。")
            else:
                content = "Steel is drawn and the scene tightens into combat. The next move belongs to the initiative order."
                objective = "Survive the fight and secure the road."
                changes.append("Combat has started near the watchtower.")
        elif "fight" in normalized or "attack" in normalized or "combat" in normalized:
            if locale == "zh-CN":
                content = "你做好了迎战准备，但目前还没有敌人真正发动攻击。"
                objective = "在出手前确认威胁。"
            else:
                content = "You ready yourself for danger, but no foe commits to the fight yet."
                objective = "Identify the threat before striking."
        else:
            if locale == "zh-CN":
                content = f"你谨慎地在{scene.location}中行动。{scene.environment}"
                objective = f"决定如何从{scene.location}继续前进。"
            else:
                content = f"You move carefully through {scene.location}. {scene.environment}"
                objective = f"Choose how to press forward from {scene.location}."

        next_scene = SceneState(
            location=scene.location,
            environment=scene.environment,
            important_objects=scene.important_objects,
            npcs=scene.npcs,
            current_objective=objective,
            world_changes=changes,
        )
        return next_scene, content


class DMService:
    def __init__(
        self,
        store,
        provider: LLMProvider | None = None,
        combat_service: CombatService | None = None,
        llm_client: Any | None = None,
    ):
        self.store = store
        self.tools = DMAgentTools(store, combat_service=combat_service)
        self.memory = AgentMemoryManager(store)
        self.adventures = self.tools.adventures
        self.characters = self.tools.characters
        self.world = self.tools.world
        self.stories = self.tools.stories
        self.models = self.tools.models
        self.context = self.memory.context
        self.world_events = self.memory.world_events
        self.world_state = WorldStateService(store)
        self.provider = provider or TemplateDMProvider()
        self.combat = self.tools.combat
        self.maps = MapService(store)
        self.llm_client = llm_client or OpenAICompatibleClient()
        self.graph_runner = DMGraphRunner(store)
        self.workflows = DeterministicWorkflows(store, combat_service=self.combat)
        self.skill_registry = DMSkillRegistry.load_builtin()

    def create_adventure(self, request: AdventureCreate) -> AdventureOut:
        locale = normalize_locale(request.locale)
        party = self.adventures.validate_party(request.effective_party_character_ids())
        character = party[0]
        story = self.stories.get(request.story_id)
        world_entries = self.world.search(category=None).results
        scene, opening_message = self.provider.opening_scene(
            character,
            world_entries,
            story,
            locale,
        )
        active_model = self.models.get_active_record()
        if active_model:
            try:
                scene, opening_message = self._opening_with_model(
                    active_model,
                    character,
                    world_entries,
                    story,
                    scene,
                    opening_message,
                    locale,
                )
            except Exception:
                pass
        opening_message = self._with_party_opening(opening_message, party, locale)
        adventure = self.adventures.create(request, scene, story)
        self.maps.bind_story_scenes_to_adventure(story_id=story.id, adventure_id=adventure.id)
        self.adventures.append_message(adventure.id, "dm", opening_message, {"kind": "opening"})
        return self.adventures.get(adventure.id)

    def _with_party_opening(self, opening_message: str, party: list[CharacterOut], locale: str) -> str:
        if len(party) <= 1:
            return opening_message
        names = ", ".join(character.name for character in party)
        if locale == "zh-CN":
            return f"本局队伍：{names}。\n\n{opening_message}"
        return f"Party: {names}.\n\n{opening_message}"

    def _opening_with_model(
        self,
        model: LLMModelRecord,
        character: CharacterOut,
        world_entries: list[WorldEntryOut],
        story: StoryOut | None,
        template_scene: SceneState,
        template_opening: str,
        locale: str,
    ) -> tuple[SceneState, str]:
        raw_response = self.llm_client.chat(
            model,
            build_opening_scene_messages(
                character,
                story,
                world_entries,
                template_scene,
                template_opening,
                locale=locale,
            ),
        )
        payload = json.loads(raw_response)
        scene = SceneState.model_validate(payload.get("scene") or template_scene.model_dump())
        narration = str(payload.get("narration") or "") or template_opening
        return scene, narration

    def advance(self, adventure_id: int, message: MessageCreate) -> DMAdvanceResponse:
        locale = normalize_locale(message.locale)
        skill_context = self.skill_registry.match(message.content, locale=locale)
        adventure = self.adventures.get(adventure_id, include_messages=False)
        combat_state = self.adventures.get_combat_state(adventure_id)
        current_world_state = self.adventures.get_world_state(adventure_id)
        action_classification = self.world_state.classify_action(message.content)
        pending_world_delta = self.world_state.preview_advance(
            current_world_state,
            action_classification,
            adventure.current_scene,
        )
        world_context = self._world_state_context(current_world_state, pending_world_delta)
        acting_character = self._resolve_acting_character(
            adventure_id,
            adventure,
            message.character_id,
            combat_state,
        )
        self.adventures.append_message(
            adventure_id,
            "player",
            message.content,
            self._acting_character_metadata(acting_character),
        )

        active_model = self.models.get_active_record()
        if active_model:
            try:
                context = self.workflows.run_memory(adventure_id, active_model.max_context_tokens)
                next_scene, dm_content, dice_result = self._advance_with_model(
                    active_model,
                    context,
                    adventure_id,
                    adventure.current_scene,
                    acting_character,
                    message.content,
                    combat_state,
                    locale,
                    skill_context,
                    world_context,
                    action_classification,
                )
            except Exception:
                dice_result = self._maybe_roll(message.content)
                next_scene, dm_content = self.provider.advance(
                    adventure.current_scene,
                    message.content,
                    dice_result,
                    combat_state,
                    locale,
                )
        else:
            dice_result = self._maybe_roll(message.content)
            next_scene, dm_content = self.provider.advance(
                adventure.current_scene,
                message.content,
                dice_result,
                combat_state,
                locale,
            )
        dm_content = self._append_world_state_narration(dm_content, pending_world_delta, locale)
        combat_state, combat_decision, dm_content = self._maybe_start_combat(
            adventure_id,
            adventure,
            message.content,
            next_scene,
            dm_content,
            combat_state,
            locale,
        )
        updated_world_state = self.world_state.commit_advance(current_world_state, pending_world_delta)
        self.adventures.update_world_state(adventure_id, updated_world_state)
        public_world_delta = self.world_state.public_delta_view(pending_world_delta)
        public_updated_world_state = self.world_state.public_view(updated_world_state)
        self.workflows.commit(adventure_id, next_scene)
        metadata = {
            "world_state": {
                "classification": action_classification,
                "pending_delta": public_world_delta,
            }
        }
        if dice_result:
            metadata["dice_result"] = dice_result
        if combat_decision:
            metadata["combat_decision"] = combat_decision
        dm_message = self.adventures.append_message(
            adventure_id,
            "dm",
            dm_content,
            metadata,
        )
        updated = self.adventures.get(adventure_id)
        return DMAdvanceResponse(
            adventure=updated,
            dm_message=dm_message,
            scene=next_scene,
            messages=updated.messages,
            world_state=public_updated_world_state,
            combat_state=combat_state,
            dice_result=dice_result,
        )

    def advance_stream(self, adventure_id: int, message: MessageCreate):
        locale = normalize_locale(message.locale)
        skill_context = self.skill_registry.match(message.content, locale=locale)
        adventure = self.adventures.get(adventure_id, include_messages=False)
        combat_state = self.adventures.get_combat_state(adventure_id)
        current_world_state = self.adventures.get_world_state(adventure_id)
        action_classification = self.world_state.classify_action(message.content)
        pending_world_delta = self.world_state.preview_advance(
            current_world_state,
            action_classification,
            adventure.current_scene,
        )
        world_context = self._world_state_context(current_world_state, pending_world_delta)
        acting_character = self._resolve_acting_character(
            adventure_id,
            adventure,
            message.character_id,
            combat_state,
        )
        player_message = self.adventures.append_message(
            adventure_id,
            "player",
            message.content,
            self._acting_character_metadata(acting_character),
        )
        yield {"type": "status", "message": "dm_thinking"}
        yield {"type": "player_message", "message": player_message}

        active_model = self.models.get_active_record()
        if active_model:
            try:
                context = self.workflows.run_memory(adventure_id, active_model.max_context_tokens)
                model_stream = self._stream_with_model(
                    active_model,
                    context,
                    adventure_id,
                    adventure.current_scene,
                    acting_character,
                    message.content,
                    combat_state,
                    locale,
                    skill_context,
                    world_context,
                    action_classification,
                )
                while True:
                    try:
                        event = next(model_stream)
                    except StopIteration as stop:
                        next_scene, dm_content, dice_result = stop.value
                        break
                    yield event
            except Exception:
                dice_result = self._maybe_roll(message.content)
                next_scene, dm_content = self.provider.advance(
                    adventure.current_scene,
                    message.content,
                    dice_result,
                    combat_state,
                    locale,
                )
                for chunk in chunk_text(dm_content):
                    yield {"type": "delta", "content": chunk}
        else:
            dice_result = self._maybe_roll(message.content)
            next_scene, dm_content = self.provider.advance(
                adventure.current_scene,
                message.content,
                dice_result,
                combat_state,
                locale,
            )
            for chunk in chunk_text(dm_content):
                yield {"type": "delta", "content": chunk}

        previous_content = dm_content
        dm_content = self._append_world_state_narration(dm_content, pending_world_delta, locale)
        combat_state, combat_decision, dm_content = self._maybe_start_combat(
            adventure_id,
            adventure,
            message.content,
            next_scene,
            dm_content,
            combat_state,
            locale,
        )
        if dm_content != previous_content:
            yield {"type": "delta", "content": dm_content.removeprefix(previous_content)}
        updated_world_state = self.world_state.commit_advance(current_world_state, pending_world_delta)
        self.adventures.update_world_state(adventure_id, updated_world_state)
        public_world_delta = self.world_state.public_delta_view(pending_world_delta)
        public_updated_world_state = self.world_state.public_view(updated_world_state)
        self.workflows.commit(adventure_id, next_scene)
        metadata = {
            "world_state": {
                "classification": action_classification,
                "pending_delta": public_world_delta,
            }
        }
        if dice_result:
            metadata["dice_result"] = dice_result
        if combat_decision:
            metadata["combat_decision"] = combat_decision
        dm_message = self.adventures.append_message(
            adventure_id,
            "dm",
            dm_content,
            metadata,
        )
        updated = self.adventures.get(adventure_id)
        yield {
            "type": "final",
            "adventure": updated,
            "dm_message": dm_message,
            "scene": next_scene,
            "messages": updated.messages,
            "world_state": public_updated_world_state,
            "combat_state": combat_state,
            "dice_result": dice_result,
        }

    def _resolve_acting_character(
        self,
        adventure_id: int,
        adventure: AdventureOut,
        requested_character_id: int | None,
        combat_state: dict[str, Any] | None,
    ) -> CharacterOut:
        party = self.adventures.get_party(adventure_id)
        if not party:
            return self.characters.get(adventure.character_id)

        if combat_state and combat_state.get("is_active"):
            actor = self._safe_current_combat_actor(combat_state)
            if actor and actor.get("side") == "player":
                matched = self._match_party_character(party, actor.get("character_id"), actor.get("name"))
                if matched is not None:
                    return matched

        if requested_character_id is not None:
            matched = self._match_party_character(party, requested_character_id, None)
            if matched is not None:
                return matched

        matched = self._match_party_character(party, adventure.character_id, None)
        return matched or party[0]

    def _safe_current_combat_actor(self, state: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self._current_combat_actor(state)
        except ValueError:
            return None

    def _match_party_character(
        self,
        party: list[CharacterOut],
        character_id: int | None,
        name: str | None,
    ) -> CharacterOut | None:
        if character_id is not None:
            try:
                normalized_id = int(character_id)
            except (TypeError, ValueError):
                normalized_id = None
            for character in party:
                if normalized_id is not None and character.id == normalized_id:
                    return character
        if name:
            normalized = name.strip().lower()
            for character in party:
                if character.name.strip().lower() == normalized:
                    return character
        return None

    def _acting_character_metadata(self, character: CharacterOut) -> dict[str, Any]:
        return {
            "character_id": character.id,
            "character_name": character.name,
            "source": "user",
        }

    def _world_state_context(self, world_state: dict[str, Any], pending_delta: dict[str, Any]) -> dict[str, Any]:
        context = self.world_state.public_view(world_state)
        context["pending_visible_events"] = list(pending_delta.get("pending_visible_events", []))
        return context

    def _append_world_state_narration(self, dm_content: str, pending_delta: dict[str, Any], locale: str) -> str:
        events = [str(event) for event in pending_delta.get("pending_visible_events", []) if event]
        if not events:
            return dm_content
        if locale == "zh-CN":
            return f"{dm_content}\n\n世界局势变化：" + " ".join(events)
        return f"{dm_content}\n\nWorld state shifts: " + " ".join(events)

    def _maybe_start_combat(
        self,
        adventure_id: int,
        adventure: AdventureOut,
        player_input: str,
        scene: SceneState,
        dm_content: str,
        combat_state: dict[str, Any] | None,
        locale: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
        if combat_state and combat_state.get("is_active"):
            return combat_state, None, dm_content

        story = self.stories.get(adventure.story_id)
        decision = self._story_combat_decision(story, player_input)
        if decision is None:
            decision = self._dynamic_combat_decision(scene, player_input, locale)
        if decision is None:
            return combat_state, None, dm_content

        participants = [
            self._character_to_combat_participant(character)
            for character in self.adventures.get_party(adventure_id)
        ]
        participants.extend(decision["enemies"])
        state = self.combat.start_combat(participants)
        saved_state = self.adventures.save_combat_state(adventure_id, state)
        self.maps.ensure_combat_tokens(adventure_id, saved_state.get("participants", []))
        return saved_state, decision, self._append_combat_narration(dm_content, decision, locale)

    def _story_combat_decision(self, story: StoryOut, player_input: str) -> dict[str, Any] | None:
        normalized = player_input.lower()
        for encounter in story.encounters:
            keywords = [keyword.lower() for keyword in encounter.trigger_keywords if keyword.strip()]
            if not keywords or not any(keyword in normalized for keyword in keywords):
                continue
            enemies = [enemy.model_dump() for enemy in encounter.enemies]
            if not enemies:
                continue
            return {
                "start_combat": True,
                "source": "story",
                "encounter_id": encounter.id,
                "encounter_title": encounter.title,
                "reason": encounter.description or f"Triggered by player action: {player_input}",
                "enemies": enemies,
            }
        return None

    def _dynamic_combat_decision(self, scene: SceneState, player_input: str, locale: str) -> dict[str, Any] | None:
        normalized = player_input.lower()
        if not any(keyword in normalized for keyword in COMBAT_INTENT_KEYWORDS):
            return None
        enemy_name = self._dynamic_enemy_name(scene, player_input, locale)
        return {
            "start_combat": True,
            "source": "dm_generated",
            "encounter_id": "dm-generated-threat",
            "encounter_title": enemy_name,
            "reason": (
                "The player action turns the current scene threat into a direct fight."
                if locale != "zh-CN"
                else "玩家行动使当前场景威胁升级为直接战斗。"
            ),
            "enemies": [
                {
                    "name": enemy_name,
                    "side": "enemy",
                    "hp": 9,
                    "hp_max": 9,
                    "ac": 12,
                    "attack_bonus": 3,
                    "damage": "1d6+1",
                    "damage_type": "bludgeoning",
                    "kind": "npc",
                }
            ],
        }

    def _dynamic_enemy_name(self, scene: SceneState, player_input: str, locale: str) -> str:
        haystack = " ".join([player_input, scene.environment, *scene.important_objects, *scene.npcs]).lower()
        if locale == "zh-CN":
            if "影" in haystack or "shadow" in haystack:
                return "敌意水影"
            if scene.npcs:
                return f"{scene.npcs[0]}的敌对化身"
            return f"{scene.location}威胁"
        if "shadow" in haystack:
            return "Hostile Shadow"
        if "sprite" in haystack or "spirit" in haystack:
            return "Hostile Spirit"
        if scene.npcs:
            return f"Hostile {scene.npcs[0]}"
        return f"{scene.location} Threat"

    def _append_combat_narration(self, dm_content: str, decision: dict[str, Any], locale: str) -> str:
        enemy_names = ", ".join(enemy["name"] for enemy in decision["enemies"])
        if locale == "zh-CN":
            return (
                f"{dm_content}\n\n"
                f"战斗触发：{decision['reason']} 敌人出现：{enemy_names}。接下来按先攻顺序行动。"
            )
        return (
            f"{dm_content}\n\n"
            f"Combat starts: {decision['reason']} Enemies: {enemy_names}. The next actions follow initiative order."
        )

    def _character_to_combat_participant(self, character: CharacterOut) -> dict[str, Any]:
        strength_mod = (character.strength - 10) // 2
        dexterity_mod = (character.dexterity - 10) // 2
        return {
            "character_id": character.id,
            "name": character.name,
            "side": "player",
            "hp": character.hp_current,
            "hp_max": character.hp_max,
            "ac": character.armor_class,
            "attack_bonus": max(0, strength_mod + 2),
            "damage": "1d8" + (f"{strength_mod:+d}" if strength_mod else ""),
            "damage_type": "slashing",
            "initiative_bonus": dexterity_mod,
            "speed_ft": 30,
            "kind": "character",
        }

    def resolve_npc_combat_turn(self, adventure_id: int, locale: str = "en") -> dict[str, Any]:
        locale = normalize_locale(locale)
        adventure = self.adventures.get(adventure_id, include_messages=False)
        state = self.adventures.get_combat_state(adventure_id)
        if state is None or not state.get("is_active"):
            raise ValueError("combat_not_active")

        actor = self._current_combat_actor(state)
        if not self._is_npc_actor(actor):
            raise ValueError("not_npc_turn")
        action_round = int(state.get("round_number", 1))
        action_turn = int(state.get("turn_index", 0))

        decision = None
        active_model = self.models.get_active_record()
        if active_model:
            try:
                decision = self._npc_decision_with_model(active_model, adventure_id, adventure.current_scene, state, actor, locale)
            except Exception:
                decision = None
        if decision is None:
            decision = self._fallback_npc_decision(adventure_id, state, actor)

        result = self._execute_npc_decision(adventure_id, state, actor, decision)
        entry = append_combat_log_entry(
            result["state"],
            result,
            source="npc",
            round_number=action_round,
            turn_index=action_turn,
        )
        CombatEventAgent(self.store).record_important_events(adventure_id, result["state"], [entry])
        CharacterStateService(self.store).sync_party_hp_from_combat_state(adventure_id, result["state"])
        self.adventures.save_combat_state(adventure_id, result["state"])
        return result

    def _npc_decision_with_model(
        self,
        model: LLMModelRecord,
        adventure_id: int,
        scene: SceneState,
        state: dict[str, Any],
        actor: dict[str, Any],
        locale: str,
    ) -> dict[str, Any]:
        skill_context = self.skill_registry.match(
            "npc combat action tactics enemy monster turn environment allies nearby enemies",
            locale=locale,
            agent="combat_agent",
            limit=3,
        )
        raw_response = self.llm_client.chat(
            model,
            build_npc_combat_action_messages(
                self._npc_combat_context(adventure_id, scene, state, actor),
                locale=locale,
                skill_context=skill_context,
            ),
        )
        payload = json.loads(raw_response)
        decision = self._normalize_npc_decision(payload, state, actor)
        decision["source"] = "model"
        return decision

    def _npc_combat_context(
        self,
        adventure_id: int,
        scene: SceneState,
        state: dict[str, Any],
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        map_context = self.maps.get_map_context(adventure_id).model_dump()
        actor_distances = map_context.get("distances", {}).get(actor.get("name"), {})
        allies = [
            self._summarize_combatant(participant)
            for participant in state.get("participants", [])
            if participant.get("name") != actor.get("name")
            and participant.get("side") == actor.get("side")
            and not participant.get("defeated", False)
        ]
        enemies = []
        for participant in self._hostile_targets(state, actor):
            enemy = self._summarize_combatant(participant)
            if enemy["name"] in actor_distances:
                enemy["distance_ft"] = actor_distances[enemy["name"]]
            enemies.append(enemy)
        enemies.sort(key=lambda enemy: (enemy.get("distance_ft", 999999), int(enemy.get("hp", 0)), str(enemy.get("name", ""))))
        return {
            "current_npc": self._summarize_combatant(actor),
            "scene": scene.model_dump(),
            "combat": {
                "round_number": state.get("round_number", 1),
                "turn_index": state.get("turn_index", 0),
                "participants": [
                    self._summarize_combatant(participant)
                    for participant in state.get("participants", [])
                ],
                "recent_action_log": list(state.get("action_log", []))[-10:],
            },
            "nearby_allies": allies,
            "nearby_enemies": enemies,
            "map": map_context,
            "available_actions": ["attack", "dodge", "dash", "disengage"],
        }

    def _summarize_combatant(self, participant: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": participant.get("name"),
            "side": participant.get("side"),
            "kind": participant.get("kind", "npc"),
            "hp": participant.get("hp", 0),
            "hp_max": participant.get("hp_max", participant.get("hp", 1)),
            "temp_hp": participant.get("temp_hp", 0),
            "ac": participant.get("ac", 10),
            "attack_bonus": participant.get("attack_bonus", 0),
            "damage": participant.get("damage", "1d4"),
            "damage_type": participant.get("damage_type", "bludgeoning"),
            "speed_ft": participant.get("speed_ft", 30),
            "reach_ft": participant.get("reach_ft", 5),
            "movement_remaining_ft": participant.get("movement_remaining_ft", participant.get("speed_ft", 30)),
            "action_available": participant.get("action_available", True),
            "conditions": list(participant.get("conditions", [])),
            "cover": participant.get("cover", "none"),
            "engaged_with": list(participant.get("engaged_with", [])),
            "resistances": list(participant.get("resistances", [])),
            "vulnerabilities": list(participant.get("vulnerabilities", [])),
            "immunities": list(participant.get("immunities", [])),
            "defeated": participant.get("defeated", False),
        }

    def _normalize_npc_decision(
        self,
        payload: dict[str, Any],
        state: dict[str, Any],
        actor: dict[str, Any],
    ) -> dict[str, Any]:
        action_type = str(payload.get("action_type") or "").replace("-", "_").lower()
        if action_type not in {"attack", "dodge", "dash", "disengage"}:
            raise ValueError("unsupported_npc_action")

        decision: dict[str, Any] = {
            "action_type": action_type,
            "reason": str(payload.get("reason") or ""),
        }
        if payload.get("attack_id"):
            decision["attack_id"] = str(payload["attack_id"])
        if payload.get("movement_ft") is not None:
            decision["movement_ft"] = int(payload["movement_ft"])

        if action_type == "attack":
            target_name = str(payload.get("target_name") or "")
            living_hostiles = {target["name"] for target in self._hostile_targets(state, actor)}
            if target_name not in living_hostiles:
                raise ValueError("invalid_npc_target")
            decision["target_name"] = target_name
        return decision

    def _fallback_npc_decision(self, adventure_id: int, state: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        if not actor.get("action_available", True):
            return {
                "action_type": "end_turn",
                "source": "fallback",
                "reason": "NPC has no remaining action.",
            }

        targets = self._hostile_targets(state, actor)
        hp = int(actor.get("hp", 0))
        hp_max = max(1, int(actor.get("hp_max") or hp or 1))
        badly_hurt = hp / hp_max <= 0.25
        if badly_hurt and actor.get("engaged_with"):
            return {
                "action_type": "disengage",
                "source": "fallback",
                "reason": "NPC is badly hurt and engaged.",
            }
        if badly_hurt:
            return {
                "action_type": "dodge",
                "source": "fallback",
                "reason": "NPC is badly hurt and takes a defensive action.",
            }

        nearest = self.maps.nearest_hostile_token(adventure_id, actor, targets)
        if nearest is not None:
            target, distance_ft = nearest
            reach_ft = float(actor.get("reach_ft", 5))
            if distance_ft > reach_ft:
                movement_ft = float(actor.get("speed_ft", 30)) * 2
                return {
                    "action_type": "dash",
                    "target_name": target["name"],
                    "movement_ft": movement_ft,
                    "source": "fallback",
                    "reason": f"NPC is {distance_ft:g} ft from the nearest hostile and dashes closer.",
                }
        else:
            target = self._select_npc_target(actor, targets)
        if target:
            return {
                "action_type": "attack",
                "target_name": target["name"],
                "source": "fallback",
                "reason": "NPC attacks the most vulnerable hostile target.",
            }
        return {
            "action_type": "dodge",
            "source": "fallback",
            "reason": "NPC has no clear hostile target.",
        }

    def _select_npc_target(
        self,
        actor: dict[str, Any],
        targets: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not targets:
            return None
        engaged = set(actor.get("engaged_with", []))
        return sorted(
            targets,
            key=lambda target: (
                target.get("name") not in engaged,
                int(target.get("hp", 0)),
                str(target.get("name", "")),
            ),
        )[0]

    def _execute_npc_decision(
        self,
        adventure_id: int,
        state: dict[str, Any],
        actor: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        action_type = decision.get("action_type", "dodge")
        map_movement = self._resolve_decision_map_movement(adventure_id, actor, decision)
        if action_type == "end_turn":
            result = {
                "action_type": "end_turn",
                "actor": actor,
                "state": state,
                "ends_turn": True,
            }
        else:
            action = {
                "actor_name": actor["name"],
                "action_type": action_type,
            }
            for key in ("target_name", "attack_id", "movement_ft"):
                if decision.get(key) is not None:
                    action[key] = decision[key]
            map_range = None
            try:
                map_range = self.maps.validate_attack_range(adventure_id, state, action)
                result = self.combat.resolve_action(state, action)
            except (MapAttackRangeError, ValueError):
                if decision.get("source") == "fallback":
                    raise
                fallback = self._fallback_npc_decision(adventure_id, state, actor)
                return self._execute_npc_decision(adventure_id, state, actor, fallback)
            if map_range is not None:
                result["map_range"] = map_range

        if result["state"].get("is_active") and result.get("ends_turn", True):
            self.combat.advance_turn(result["state"])
        if map_movement is not None:
            result["map_movement"] = map_movement
        result["decision_source"] = decision.get("source", "fallback")
        result["decision_reason"] = decision.get("reason") or ""
        result["decision"] = {
            key: value
            for key, value in decision.items()
            if key in {"action_type", "target_name", "attack_id", "movement_ft", "reason", "source"}
        }
        return result

    def _resolve_decision_map_movement(
        self,
        adventure_id: int,
        actor: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any] | None:
        target_name = decision.get("target_name")
        if not target_name:
            return None
        action_type = decision.get("action_type")
        if action_type not in {"dash", "disengage", "dodge"}:
            return None
        movement_ft = float(decision.get("movement_ft") or actor.get("speed_ft", 30))
        try:
            return self.maps.move_combat_token_toward_target(
                adventure_id,
                str(actor.get("name") or ""),
                str(target_name),
                movement_ft,
            )
        except Exception:
            return None

    def _current_combat_actor(self, state: dict[str, Any]) -> dict[str, Any]:
        participants = state.get("participants", [])
        turn_index = int(state.get("turn_index", 0))
        if not participants or turn_index < 0 or turn_index >= len(participants):
            raise ValueError("invalid_combat_state")
        return participants[turn_index]

    def _is_npc_actor(self, actor: dict[str, Any]) -> bool:
        return actor.get("side") != "player"

    def _hostile_targets(self, state: dict[str, Any], actor: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            participant
            for participant in state.get("participants", [])
            if participant.get("side") != actor.get("side")
            and int(participant.get("hp", 0)) > 0
            and not participant.get("defeated", False)
        ]

    def _stream_with_model(
        self,
        model: LLMModelRecord,
        context: ContextBundle,
        adventure_id: int,
        scene: SceneState,
        character: CharacterOut,
        player_input: str,
        combat_state: dict[str, Any] | None,
        locale: str,
        skill_context: list[DMSkill] | None = None,
        world_state: dict[str, Any] | None = None,
        action_classification: dict[str, Any] | None = None,
    ):
        react_model = self._react_model(model)
        if react_model is not None:
            plan = self.graph_runner.plan(
                player_input,
                model=react_model,
                locale=locale,
                skill_context=skill_context,
            )
            messages = build_dm_messages(
                context,
                scene,
                character,
                player_input,
                combat_state,
                supervisor_plan=plan.model_dump(),
                locale=locale,
                skill_context=skill_context,
                world_state=world_state,
                action_classification=action_classification,
            )
            try:
                payload, streamed_narration = yield from self._stream_model_json_payload(model, messages)
            except Exception:
                next_scene, narration, dice_result, event_payloads = self._resolve_with_model(
                    model,
                    context,
                    adventure_id,
                    scene,
                    character,
                    player_input,
                    combat_state,
                    plan.model_dump(),
                    locale,
                    skill_context,
                    world_state,
                    action_classification,
                    use_narration_agent=False,
                )
                for chunk in chunk_text(narration):
                    yield {"type": "delta", "content": chunk}
            else:
                next_scene, narration, dice_result, event_payloads = self._model_payload_to_response(
                    adventure_id,
                    scene,
                    character,
                    payload,
                    locale,
                )
                yield from self._reconcile_streamed_narration(streamed_narration, narration)
            self._record_world_events(context, event_payloads)
            return next_scene, narration, dice_result
        plan = self.graph_runner.plan(
            player_input,
            model=react_model,
            locale=locale,
            skill_context=skill_context,
        )
        messages = build_dm_messages(
            context,
            scene,
            character,
            player_input,
            combat_state,
            supervisor_plan=plan.model_dump(),
            locale=locale,
            skill_context=skill_context,
        )
        if hasattr(self.llm_client, "stream_chat"):
            try:
                payload, streamed_narration = yield from self._stream_model_json_payload(model, messages)
            except Exception:
                if not hasattr(self.llm_client, "chat"):
                    raise
            else:
                next_scene, narration, dice_result, event_payloads = self._model_payload_to_response(
                    adventure_id,
                    scene,
                    character,
                    payload,
                    locale,
                )
                yield from self._reconcile_streamed_narration(streamed_narration, narration)
                self._record_world_events(context, event_payloads)
                return (
                    next_scene,
                    narration or self._fallback_narration(locale),
                    dice_result,
                )
        if hasattr(self.llm_client, "chat"):
            raw_response = self.llm_client.chat(model, messages)
            payload = json.loads(raw_response)
            next_scene, narration, dice_result, event_payloads = self._model_payload_to_response(
                adventure_id,
                scene,
                character,
                payload,
                locale,
            )
            for chunk in chunk_text(narration):
                yield {"type": "delta", "content": chunk}
            self._record_world_events(context, event_payloads)
            return (
                next_scene,
                narration or self._fallback_narration(locale),
                dice_result,
            )
        raise RuntimeError("LLM client does not support chat or stream_chat.")

    def _stream_model_json_payload(
        self,
        model: LLMModelRecord,
        messages: list[dict[str, str]],
    ):
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
        return json.loads(raw_response), extract_narration_text(raw_response)

    def _model_payload_to_response(
        self,
        adventure_id: int,
        scene: SceneState,
        character: CharacterOut,
        payload: dict[str, Any],
        locale: str,
    ) -> tuple[SceneState, str, dict[str, Any] | None, list[dict[str, Any]]]:
        next_scene = SceneState.model_validate(payload.get("scene") or scene.model_dump())
        dice_result = self._roll_requested_check(payload.get("check"), character) if payload.get("requires_check") else None
        narration = str(payload.get("narration") or "")
        npc_actions = payload.get("npc_actions") or []
        if npc_actions:
            narration = f"{narration}\n\nNPC actions: " + " ".join(str(action) for action in npc_actions)
        event_payloads = payload.get("world_events") or []
        self._apply_character_updates(adventure_id, payload)
        return next_scene, narration or self._fallback_narration(locale), dice_result, event_payloads

    def _reconcile_streamed_narration(self, streamed_narration: str, final_narration: str):
        if not final_narration or final_narration == streamed_narration:
            return
        if final_narration.startswith(streamed_narration):
            delta = final_narration[len(streamed_narration) :]
            if delta:
                yield {"type": "delta", "content": delta}
            return
        if not streamed_narration:
            for chunk in chunk_text(final_narration):
                yield {"type": "delta", "content": chunk}

    def _fallback_narration(self, locale: str) -> str:
        return (
            "场景发生了变化，但 DM 没有提供更多细节。"
            if locale == "zh-CN"
            else "The scene changes, but the DM gives no further detail."
        )

    def _advance_with_model(
        self,
        model: LLMModelRecord,
        context: ContextBundle,
        adventure_id: int,
        scene: SceneState,
        character: CharacterOut,
        player_input: str,
        combat_state: dict[str, Any] | None,
        locale: str,
        skill_context: list[DMSkill] | None = None,
        world_state: dict[str, Any] | None = None,
        action_classification: dict[str, Any] | None = None,
    ) -> tuple[SceneState, str, dict[str, Any] | None]:
        react_model = self._react_model(model)
        result = self.graph_runner.run(
            player_input,
            lambda plan: {
                "value": self._resolve_with_model(
                    model,
                    context,
                    adventure_id,
                    scene,
                    character,
                    player_input,
                    combat_state,
                    plan.model_dump(),
                    locale,
                    skill_context,
                    world_state,
                    action_classification,
                )
            },
            model=react_model,
            locale=locale,
            skill_context=skill_context,
        )
        next_scene, narration, dice_result, event_payloads = tuple(result["value"])
        self._record_world_events(context, event_payloads)
        return next_scene, narration, dice_result

    def _resolve_with_model(
        self,
        model: LLMModelRecord,
        context: ContextBundle,
        adventure_id: int,
        scene: SceneState,
        character: CharacterOut,
        player_input: str,
        combat_state: dict[str, Any] | None,
        supervisor_plan: dict[str, Any],
        locale: str,
        skill_context: list[DMSkill] | None = None,
        world_state: dict[str, Any] | None = None,
        action_classification: dict[str, Any] | None = None,
        use_narration_agent: bool = True,
    ) -> tuple[SceneState, str, dict[str, Any] | None, list[dict[str, Any]]]:
        raw_response = self.llm_client.chat(
            model,
            build_dm_messages(
                context,
                scene,
                character,
                player_input,
                combat_state,
                supervisor_plan=supervisor_plan,
                locale=locale,
                skill_context=skill_context,
                world_state=world_state,
                action_classification=action_classification,
            ),
        )
        payload = json.loads(raw_response)
        next_scene, narration, dice_result, event_payloads = self._model_payload_to_response(
            adventure_id,
            scene,
            character,
            payload,
            locale,
        )
        npc_actions = payload.get("npc_actions") or []
        react_model = self._react_model(model)
        if react_model is not None and use_narration_agent:
            narrated = NarrationAgent(
                react_model,
                locale=locale,
                skill_context=skill_context,
            ).narrate(
                {
                    "resolved_narration": narration,
                    "scene": next_scene.model_dump(),
                    "dice_result": dice_result,
                    "npc_actions": npc_actions,
                    "world_events": payload.get("world_events") or [],
                    "supervisor_plan": supervisor_plan,
                    "skills": skills_prompt_payload(skill_context),
                }
            )
            if narrated:
                narration = narrated
        return (
            next_scene,
            narration or self._fallback_narration(locale),
            dice_result,
            event_payloads,
        )

    def _apply_character_updates(self, adventure_id: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
        character_updates = payload.get("character_updates") or payload.get("character_state_changes") or []
        if not isinstance(character_updates, list):
            return []
        return CharacterStateService(self.store).apply_changes(adventure_id, character_updates)

    def _react_model(self, model: LLMModelRecord) -> OpenAICompatibleChatModel | None:
        if not hasattr(self.llm_client, "chat_message"):
            return None
        return OpenAICompatibleChatModel(model_record=model, client=self.llm_client)

    def _record_world_events(self, context: ContextBundle, event_payloads: list[dict[str, Any]]) -> None:
        if not event_payloads:
            return
        adventure_id = context.recent_messages[-1].adventure_id
        validated = []
        for event_payload in event_payloads:
            try:
                validated.append(WorldEventCreate.model_validate(event_payload).model_dump())
            except ValidationError:
                continue
        if not validated:
            return
        self.workflows.commit(adventure_id, scene=None, world_events=validated)

    def _roll_requested_check(self, check: dict[str, Any] | None, character: CharacterOut) -> dict[str, Any] | None:
        if not check:
            return None
        ability = str(check.get("ability") or "strength").lower()
        score = getattr(character, ability, 10) if ability in {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        } else 10
        dc = int(check.get("dc") or 10)
        fixed = self.workflows.run_ability_check(
            AbilityCheckRequest(
                ability=ability,
                ability_score=score,
                dc=dc,
                reason=str(check.get("reason") or ""),
            )
        )
        return {
            "rolls": [fixed.roll],
            "kept": fixed.roll,
            "modifier": fixed.modifier,
            "total": fixed.total,
            "dc": fixed.dc,
            "success": fixed.success,
            "mode": "normal",
            "ability": fixed.ability,
            "reason": fixed.reason,
        }

    def _maybe_roll(self, content: str) -> dict[str, Any] | None:
        normalized = content.lower()
        if any(term in normalized for term in ("inspect", "check", "search", "examine", "investigate")):
            return self.combat.roll_check(modifier=2, dc=10)
        return None
