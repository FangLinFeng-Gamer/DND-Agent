import json

import pytest

from backend.src.services.isekai_preferences import IsekaiPreferenceLearner


class FakePreferenceClient:
    def __init__(self):
        self.calls = []

    def chat(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return json.dumps(
            {
                "themes": ["美食", "开餐厅", "贸易"],
                "playstyle": ["经营", "社交"],
                "goals": ["寻找食材"],
                "confidence": 0.82,
            },
            ensure_ascii=False,
        )


class FailingPreferenceClient:
    def chat(self, model, messages):
        raise RuntimeError("model unavailable")


class PayloadPreferenceClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def chat(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return json.dumps(self.payload, ensure_ascii=False)


class FakeModel:
    model_name = "preference-model"


def test_preference_learner_runs_on_fifth_effective_turn():
    client = FakePreferenceClient()
    learner = IsekaiPreferenceLearner(llm_client=client)
    world_state = {"turn_count": 5}
    messages = [
        {"role": "player", "content": "我想寻找食材，以后开一家餐厅。"},
        {"role": "dm", "content": "你闻到林间蘑菇的气味。"},
    ]

    updated = learner.maybe_update(world_state, messages, FakeModel())

    assert len(client.calls) == 1
    assert updated["player_preferences"]["themes"] == ["美食", "开餐厅", "贸易"]
    assert updated["player_preferences"]["updated_turn"] == 5
    assert updated["player_preferences"]["confidence"] == 0.82


def test_preference_learner_skips_non_cadence_turns():
    client = FakePreferenceClient()
    learner = IsekaiPreferenceLearner(llm_client=client)

    updated = learner.maybe_update({"turn_count": 4}, [], FakeModel())

    assert client.calls == []
    assert "player_preferences" not in updated


def test_preference_learner_keeps_previous_preferences_when_model_fails():
    learner = IsekaiPreferenceLearner(llm_client=FailingPreferenceClient())
    world_state = {
        "turn_count": 10,
        "player_preferences": {
            "themes": ["探索"],
            "playstyle": ["谨慎"],
            "goals": [],
            "confidence": 0.4,
            "updated_turn": 5,
        },
    }

    updated = learner.maybe_update(world_state, [], FakeModel())

    assert updated["player_preferences"]["themes"] == ["探索"]
    assert updated["player_preferences"]["updated_turn"] == 5


@pytest.mark.parametrize("payload", [["not", "a", "dict"], "not a dict"])
def test_preference_learner_keeps_previous_preferences_when_model_returns_non_dict_json(payload):
    learner = IsekaiPreferenceLearner(llm_client=PayloadPreferenceClient(payload))
    world_state = {
        "turn_count": 10,
        "player_preferences": {
            "themes": ["探索"],
            "playstyle": ["谨慎"],
            "goals": [],
            "confidence": 0.4,
            "updated_turn": 5,
        },
    }

    updated = learner.maybe_update(world_state, [], FakeModel())

    assert updated == world_state


def test_preference_learner_keeps_previous_preferences_when_confidence_is_invalid():
    learner = IsekaiPreferenceLearner(
        llm_client=PayloadPreferenceClient(
            {
                "themes": ["美食"],
                "playstyle": ["经营"],
                "goals": ["开店"],
                "confidence": "high",
            }
        )
    )
    world_state = {
        "turn_count": 10,
        "player_preferences": {
            "themes": ["探索"],
            "playstyle": ["谨慎"],
            "goals": [],
            "confidence": 0.4,
            "updated_turn": 5,
        },
    }

    updated = learner.maybe_update(world_state, [], FakeModel())

    assert updated == world_state


def test_preference_learner_keeps_state_when_turn_count_is_invalid():
    client = FakePreferenceClient()
    learner = IsekaiPreferenceLearner(llm_client=client)
    world_state = {"turn_count": "soon"}

    updated = learner.maybe_update(world_state, [], FakeModel())

    assert client.calls == []
    assert updated == world_state


def test_preference_learner_proceeds_when_previous_updated_turn_is_invalid():
    client = FakePreferenceClient()
    learner = IsekaiPreferenceLearner(llm_client=client)
    world_state = {
        "turn_count": 10,
        "player_preferences": {
            "themes": ["探索"],
            "playstyle": ["谨慎"],
            "goals": [],
            "confidence": 0.4,
            "updated_turn": "five",
        },
    }

    updated = learner.maybe_update(world_state, [], FakeModel())

    assert len(client.calls) == 1
    assert updated["player_preferences"]["themes"] == ["美食", "开餐厅", "贸易"]
    assert updated["player_preferences"]["updated_turn"] == 10


def test_preference_learner_filters_string_list_payload_values():
    learner = IsekaiPreferenceLearner(
        llm_client=PayloadPreferenceClient(
            {
                "themes": [
                    " 美食 ",
                    "",
                    None,
                    "探索",
                    42,
                    " ",
                    {"bad": "value"},
                    "贸易",
                    "制作",
                    "社交",
                    "战斗",
                    "建造",
                    "多余",
                ],
                "playstyle": [" 谨慎", 0, " ", "合作 ", False, "探索"],
                "goals": [
                    " 开店 ",
                    "",
                    None,
                    "做饭",
                    ["bad"],
                    "找伙伴",
                    "赚钱",
                    "装修",
                    "扩张",
                    "旅行",
                ],
                "confidence": 0.7,
            }
        )
    )

    updated = learner.maybe_update({"turn_count": 10}, [], FakeModel())

    assert updated["player_preferences"]["themes"] == [
        "美食",
        "探索",
        "贸易",
        "制作",
        "社交",
        "战斗",
    ]
    assert updated["player_preferences"]["playstyle"] == ["谨慎", "合作", "探索"]
    assert updated["player_preferences"]["goals"] == [
        "开店",
        "做饭",
        "找伙伴",
        "赚钱",
        "装修",
        "扩张",
    ]
