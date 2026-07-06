from backend.src.services.isekai_time import IsekaiTimeService


def test_status_question_does_not_advance_time():
    service = IsekaiTimeService()

    action = service.classify_action("我现在的状态怎么样？")

    assert action.action_type == "status_check"
    assert action.advances_time is False
    assert action.time_cost_minutes == 0


def test_cooking_is_time_advancing_action():
    service = IsekaiTimeService()

    action = service.classify_action("我给路边营地的人做一锅热汤。")

    assert action.action_type == "cook"
    assert action.advances_time is True
    assert action.time_cost_minutes == 60
    assert action.survival_intent == "cook"


def test_city_travel_inputs_are_time_advancing_actions():
    service = IsekaiTimeService()

    for text in ["我要去城镇", "去白石镇", "继续去城镇"]:
        action = service.classify_action(text)

        assert action.action_type == "travel"
        assert action.advances_time is True
        assert action.time_cost_minutes == 90


def test_time_label_for_minutes():
    service = IsekaiTimeService()

    assert service.time_label(5 * 60) == "清晨"
    assert service.time_label(12 * 60) == "正午"
    assert service.time_label(17 * 60) == "黄昏"
    assert service.time_label(18 * 60 + 30) == "夜晚"
    assert service.time_label(22 * 60) == "夜晚"
    assert service.time_label(23 * 60) == "深夜"
    assert service.time_label(3 * 60) == "深夜"


def test_advance_clock_rolls_into_next_day():
    service = IsekaiTimeService()
    survival = {"day": 1, "time_of_day": "夜晚", "state": {"elapsed_minutes": 22 * 60}}
    action = service.classify_action("我睡觉过夜。")

    updated, delta = service.apply_time_and_survival(survival, action)

    assert updated["day"] == 2
    assert updated["time_of_day"] == "清晨"
    assert updated["state"]["elapsed_minutes"] == 6 * 60
    assert updated["state"]["last_time_delta_minutes"] == 480
    assert delta["time_cost_minutes"] == 480


def test_sleep_until_morning_from_dusk():
    service = IsekaiTimeService()
    survival = {"day": 1, "time_of_day": "黄昏", "state": {"elapsed_minutes": 17 * 60}}
    action = service.classify_action("我睡觉过夜。")

    updated, delta = service.apply_time_and_survival(survival, action)

    assert updated["day"] == 2
    assert updated["time_of_day"] == "清晨"
    assert updated["state"]["elapsed_minutes"] == 6 * 60
    assert updated["state"]["last_time_delta_minutes"] == 13 * 60
    assert delta["time_cost_minutes"] == 13 * 60


def test_eat_drink_reduces_hunger_and_thirst():
    service = IsekaiTimeService()
    survival = {
        "day": 1,
        "time_of_day": "黄昏",
        "hunger": 30,
        "thirst": 35,
        "fatigue": 15,
        "sleep_need": 20,
        "temperature_risk": 10,
        "morale": 70,
        "shelter": "none",
        "state": {"elapsed_minutes": 17 * 60},
    }
    action = service.classify_action("我吃干粮并喝水。")

    updated, delta = service.apply_time_and_survival(survival, action)

    assert updated["hunger"] < survival["hunger"]
    assert updated["thirst"] < survival["thirst"]
    assert updated["time_of_day"] == "黄昏"
    assert delta["hunger"] < 0
    assert delta["thirst"] < 0
