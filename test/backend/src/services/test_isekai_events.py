from backend.src.schemas.adventure import AdventureCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_events import IsekaiWorldEventDirector
from backend.src.services.world_events import WorldEventService


def create_isekai_adventure(store):
    return IsekaiSurvivalService(store).create_adventure(
        AdventureCreate(title="Event Road", mode="isekai_survival", locale="zh-CN")
    )


def test_player_triggered_event_is_recorded_with_action_and_direct_observation(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "我给路边营地的人做一锅热汤。",
        "action_type": "talk",
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(adventure.id, turn, {"turn_count": 1, "player_preferences": {}})

    assert len(events) == 1
    event = events[0]
    assert event.metadata["source"] == "player_triggered"
    assert event.metadata["knowledge_channel"] == "direct_observation"
    assert event.metadata["known_to_character"] is True
    assert event.metadata["triggering_action"] == "我给路边营地的人做一锅热汤。"
    persisted = WorldEventService(store).list_known_for_adventure(adventure.id)
    assert persisted[-1].id == event.id


def test_open_restaurant_input_is_player_triggered_with_direct_observation(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "开餐厅",
        "action_type": "talk",
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(adventure.id, turn, {"turn_count": 1, "player_preferences": {}})

    assert len(events) == 1
    assert events[0].metadata["source"] == "player_triggered"
    assert events[0].metadata["knowledge_channel"] == "direct_observation"
    assert events[0].metadata["triggering_action"] == "开餐厅"
    assert "美食" in events[0].metadata["preference_tags"]


def test_empty_wilderness_blocks_large_news_without_channel(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "我在无人的森林里继续前进。",
        "action_type": "explore",
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(
        adventure.id,
        turn,
        {
            "turn_count": 4,
            "player_preferences": {},
            "force_event_scope": "global",
        },
    )

    assert events == []
    assert WorldEventService(store).list_known_for_adventure(adventure.id) == []


def test_random_event_does_not_generate_at_turn_zero_without_forced_scope(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "我观察周围环境。",
        "action_type": "explore",
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(adventure.id, turn, {"turn_count": 0, "player_preferences": {}})

    assert events == []
    assert WorldEventService(store).list_known_for_adventure(adventure.id) == []


def test_preference_weighted_event_uses_merchant_channel_when_channel_exists(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    scene = adventure.current_scene.model_copy(update={"location": "灰桥镇集市", "environment": "镇上的集市挤满商队、摊贩和旅人。"})
    turn = {
        "player_input": "我打听附近有没有稀有食材。",
        "action_type": "forage",
        "scene": scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(
        adventure.id,
        turn,
        {
            "turn_count": 6,
            "player_preferences": {
                "themes": ["美食", "开餐厅", "贸易"],
                "playstyle": ["经营"],
                "goals": ["寻找食材"],
                "confidence": 0.8,
            },
            "force_event_scope": "settlement",
        },
    )

    assert len(events) == 1
    assert events[0].metadata["source"] == "preference_weighted"
    assert events[0].metadata["knowledge_channel"] == "merchant_news"
    assert "美食" in events[0].metadata["preference_tags"]
