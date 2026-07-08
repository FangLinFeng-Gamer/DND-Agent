from backend.src.services.isekai_time import IsekaiTimeService


def test_status_question_does_not_advance_time():
    service = IsekaiTimeService()

    action = service.classify_action("我现在的状态怎么样？")

    assert action.action_type == "status_check"
    assert action.advances_time is False
    assert action.time_cost_minutes == 0


def test_short_clarification_does_not_advance_time():
    service = IsekaiTimeService()

    for text in ["什么？", "什么意思", "？", "?"]:
        action = service.classify_action(text)

        assert action.action_type == "table_talk"
        assert action.advances_time is False
        assert action.time_cost_minutes == 0


def test_npc_identity_question_is_short_dialogue_when_scene_has_npcs():
    service = IsekaiTimeService()

    action = service.classify_action("你是什么种族的？", scene_context={"has_npcs": True})

    assert action.action_type == "short_dialogue"
    assert action.advances_time is True
    assert action.time_cost_minutes == 10
    assert action.survival_intent == "social"


def test_system_question_stays_table_talk_even_when_scene_has_npcs():
    service = IsekaiTimeService()

    action = service.classify_action("这个系统面板怎么操作？", scene_context={"has_npcs": True})

    assert action.action_type == "table_talk"
    assert action.advances_time is False
    assert action.time_cost_minutes == 0


def test_money_query_does_not_advance_time():
    service = IsekaiTimeService()

    action = service.classify_action("我有多少钱？")

    assert action.action_type == "status_check"
    assert action.advances_time is False
    assert action.time_cost_minutes == 0


def test_unknown_input_defaults_to_table_talk_without_time_cost():
    service = IsekaiTimeService()

    action = service.classify_action("嗯？")

    assert action.action_type == "table_talk"
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


def test_gather_action_advances_time_without_table_talk():
    service = IsekaiTimeService()

    action = service.classify_action("我摘点红浆果。")

    assert action.action_type == "gather"
    assert action.advances_time is True
    assert action.time_cost_minutes == 30
    assert action.survival_intent == "gather"


def test_seek_shelter_does_not_trigger_sleep():
    service = IsekaiTimeService()

    action = service.classify_action("我找个可以过夜的地方。")

    assert action.action_type == "seek_shelter"
    assert action.advances_time is True
    assert action.time_cost_minutes == 45
    assert action.survival_intent == "shelter"


def test_explicit_overnight_sleep_still_sleeps_until_morning():
    service = IsekaiTimeService()

    action = service.classify_action("我在这里睡觉过夜。")

    assert action.action_type == "sleep"
    assert action.advances_time is True


def test_sleep_intent_recognizes_natural_rest_phrases():
    service = IsekaiTimeService()

    for text in [
        "闭上眼睛，放松身体，安心入睡恢复精力",
        "重新躺下，安心入睡，等待真正的天亮",
        "我睡一觉恢复精力",
        "闭眼休息恢复精力",
        "睡到天亮",
        "等待天亮",
    ]:
        action = service.classify_action(text)

        assert action.action_type == "sleep"
        assert action.advances_time is True


def test_manage_inventory_action_is_not_status_check():
    service = IsekaiTimeService()

    action = service.classify_action("我扔掉红浆果。")

    assert action.action_type == "manage_inventory"
    assert action.advances_time is True
    assert action.time_cost_minutes == 5


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
