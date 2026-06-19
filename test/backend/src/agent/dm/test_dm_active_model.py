import json

from backend.src.agent.dm.service import DMService
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.schemas.character import CharacterCreate
from backend.src.schemas.llm import LLMModelCreate
from backend.src.services.character_state import CharacterStateService
from backend.src.services.characters import CharacterService
from backend.src.services.llm_models import LLMModelService
from backend.src.services.stories import DEFAULT_STORY_ID, StoryService


class FakeOpeningLLMClient:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return json.dumps(
            {
                "scene": {
                    "location": "Model-Forged Wayhouse",
                    "environment": "The active model frames the rain, map, and waiting mayor.",
                    "important_objects": ["model lantern", "wet road map"],
                    "npcs": ["Mayor Elira Voss"],
                    "current_objective": "Choose which lead to follow first.",
                    "world_changes": [],
                },
                "narration": "The active model opens the adventure with rain and agency.",
            }
        )


class FakeNonStreamingDMClient:
    def __init__(self):
        self.chat_calls = 0
        self.stream_calls = 0

    def chat(self, model, messages):
        self.chat_calls += 1
        return json.dumps(
            {
                "scene": {
                    "location": "Ravenford Wayhouse",
                    "environment": "The model answers without relying on provider streaming.",
                    "important_objects": ["wet road map", "tower bell"],
                    "npcs": ["Mayor Elira Voss"],
                    "current_objective": "Ask Mayor Elira Voss what changed.",
                    "world_changes": ["The DM answered through non-streaming chat."],
                },
                "narration": "模型回复：钟声刚刚再次响起，镇长正等待你的决定。",
                "requires_check": False,
                "check": None,
                "npc_actions": [],
                "world_events": [],
            }
        )

    def stream_chat(self, model, messages):
        self.stream_calls += 1
        raise AssertionError("provider streaming should not be required for DM replies")


class FakeDMClientWithInvalidWorldEvent:
    def chat(self, model, messages):
        return json.dumps(
            {
                "scene": {
                    "location": "神龛后方",
                    "environment": "你已经绕到神龛背面，看见铁链正拖过湿滑石面。",
                    "important_objects": ["拖行的铁链", "半掩的石门"],
                    "npcs": [],
                    "current_objective": "检查铁链连接着什么。",
                    "world_changes": ["玩家到达神龛后方。"],
                },
                "narration": "你绕到神龛后方，终于看见摩擦声来自一条被拖动的铁链。",
                "requires_check": False,
                "check": None,
                "npc_actions": [],
                "world_events": [{"title": "玩家到达神龛后方"}],
            }
        )


class FakeDMClientWithCharacterUpdates:
    def chat(self, model, messages):
        user_payload = json.loads(messages[-1]["content"])
        character_id = user_payload["character"]["id"]
        return json.dumps(
            {
                "scene": {
                    "location": "Well Chamber",
                    "environment": "Cold water churns around the broken stair.",
                    "important_objects": ["silver bell"],
                    "npcs": [],
                    "current_objective": "Catch your breath and secure the bell.",
                    "world_changes": ["The silver bell was recovered."],
                },
                "narration": "你夺回银铃，但被冰冷水流撞伤。",
                "requires_check": False,
                "check": None,
                "npc_actions": [],
                "character_updates": [
                    {
                        "character_id": character_id,
                        "hp_delta": -4,
                        "experience_delta": 300,
                        "add_inventory": [{"item_id": "equipment.healing-potion", "quantity": 1}],
                        "add_spells": ["spell.magic-missile"],
                        "reason": "recovered_bell",
                    }
                ],
                "world_events": [],
            }
        )


class FakeCaptureActingCharacterClient:
    def __init__(self):
        self.payloads = []

    def chat(self, model, messages):
        self.payloads.append(json.loads(messages[-1]["content"]))
        return json.dumps(
            {
                "scene": {
                    "location": "Shared Hall",
                    "environment": "The party waits beside a sealed door.",
                    "important_objects": ["sealed door"],
                    "npcs": [],
                    "current_objective": "Choose who acts next.",
                    "world_changes": [],
                },
                "narration": "Dale steps forward and studies the sealed door.",
                "requires_check": False,
                "check": None,
                "npc_actions": [],
                "world_events": [],
            }
        )


def initialized_store(tmp_path):
    store = SQLiteStore(tmp_path / "dnd-agent.sqlite3")
    store.init_schema()
    StoryService(store).seed_defaults()
    return store


def test_create_adventure_uses_active_model_for_opening_scene(tmp_path):
    store = initialized_store(tmp_path)
    character = CharacterService(store).create(CharacterCreate(name="Mira"))
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Active DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="active-dm-model",
        )
    )
    model_service.activate(model.id)

    llm_client = FakeOpeningLLMClient()
    adventure = DMService(store, llm_client=llm_client).create_adventure(
        AdventureCreate(
            title="Model Opening",
            character_id=character.id,
            story_id=DEFAULT_STORY_ID,
            locale="en",
        )
    )

    assert len(llm_client.calls) == 1
    assert llm_client.calls[0]["model"].model_name == "active-dm-model"
    assert adventure.current_scene.location == "Model-Forged Wayhouse"
    assert adventure.messages[0].content == "The active model opens the adventure with rain and agency."


def test_advance_stream_uses_non_streaming_model_response_when_active_model_is_configured(tmp_path):
    store = initialized_store(tmp_path)
    character = CharacterService(store).create(CharacterCreate(name="Mira"))
    adventure = DMService(store).create_adventure(
        AdventureCreate(
            title="Streaming Reply",
            character_id=character.id,
            story_id=DEFAULT_STORY_ID,
            locale="zh-CN",
        )
    )
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Active DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="active-dm-model",
        )
    )
    model_service.activate(model.id)

    llm_client = FakeNonStreamingDMClient()
    events = list(
        DMService(store, llm_client=llm_client).advance_stream(
            adventure.id,
            MessageCreate(content="发生了什么事", locale="zh-CN"),
        )
    )

    delta_text = "".join(event.get("content", "") for event in events if event["type"] == "delta")
    assert llm_client.chat_calls == 1
    assert llm_client.stream_calls == 0
    assert "模型回复" in delta_text
    assert events[-1]["type"] == "final"
    assert events[-1]["dm_message"].content == "模型回复：钟声刚刚再次响起，镇长正等待你的决定。"


def test_invalid_model_world_event_does_not_replace_model_narration_with_template(tmp_path):
    store = initialized_store(tmp_path)
    character = CharacterService(store).create(CharacterCreate(name="Mira"))
    adventure = DMService(store).create_adventure(
        AdventureCreate(
            title="Invalid Event",
            character_id=character.id,
            story_id=DEFAULT_STORY_ID,
            locale="zh-CN",
        )
    )
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Active DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="active-dm-model",
        )
    )
    model_service.activate(model.id)

    events = list(
        DMService(store, llm_client=FakeDMClientWithInvalidWorldEvent()).advance_stream(
            adventure.id,
            MessageCreate(content="直接绕到后方查看", locale="zh-CN"),
        )
    )

    delta_text = "".join(event.get("content", "") for event in events if event["type"] == "delta")
    assert "铁链" in delta_text
    assert "你谨慎地在" not in delta_text
    assert events[-1]["scene"].location == "神龛后方"


def test_dm_character_updates_sync_to_character_card(tmp_path):
    store = initialized_store(tmp_path)
    character = CharacterService(store).create(CharacterCreate(name="Mira"))
    adventure = DMService(store).create_adventure(
        AdventureCreate(
            title="Character Sync",
            character_id=character.id,
            story_id=DEFAULT_STORY_ID,
            locale="zh-CN",
        )
    )
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Active DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="active-dm-model",
        )
    )
    model_service.activate(model.id)

    events = list(
        DMService(store, llm_client=FakeDMClientWithCharacterUpdates()).advance_stream(
            adventure.id,
            MessageCreate(content="我抓住银铃游回岸边", locale="zh-CN"),
        )
    )

    updated_adventure = DMService(store).adventures.get(adventure.id)
    updated = updated_adventure.party_characters[0]
    base_character = CharacterService(store).get(character.id)
    assert events[-1]["type"] == "final"
    assert updated.hp_current == 6
    assert updated.experience_points == 300
    assert updated.level == 2
    assert any(item.get("item_id") == "equipment.healing-potion" for item in updated.inventory if isinstance(item, dict))
    assert "spell.magic-missile" in updated.spells
    assert base_character.hp_current == 10
    assert base_character.experience_points == 0


def test_dm_uses_selected_adventure_character_snapshot_as_acting_character(tmp_path):
    store = initialized_store(tmp_path)
    first = CharacterService(store).create(CharacterCreate(name="Tav"))
    second = CharacterService(store).create(CharacterCreate(name="Dale"))
    adventure = DMService(store).create_adventure(
        AdventureCreate(
            title="Party Acting Character",
            party_character_ids=[first.id, second.id],
            story_id=DEFAULT_STORY_ID,
            locale="en",
        )
    )
    CharacterStateService(store).apply_changes(
        adventure.id,
        [{"character_id": second.id, "hp_current": 3}],
    )
    model_service = LLMModelService(store)
    model = model_service.create(
        LLMModelCreate(
            name="Active DM",
            provider="openai_compatible",
            base_url="https://api.example.test",
            api_key="sk-test-1234567890",
            model_name="active-dm-model",
        )
    )
    model_service.activate(model.id)
    llm_client = FakeCaptureActingCharacterClient()

    events = list(
        DMService(store, llm_client=llm_client).advance_stream(
            adventure.id,
            MessageCreate(content="Dale checks the door.", locale="en", character_id=second.id),
        )
    )

    payload = llm_client.payloads[0]
    dale_party_state = next(character for character in payload["party"] if character["id"] == second.id)
    assert payload["character"]["id"] == second.id
    assert payload["acting_character"]["id"] == second.id
    assert payload["character"]["hp_current"] == 3
    assert dale_party_state["hp_current"] == 3
    assert events[1]["message"].metadata["character_id"] == second.id
    assert events[1]["message"].metadata["character_name"] == "Dale"
