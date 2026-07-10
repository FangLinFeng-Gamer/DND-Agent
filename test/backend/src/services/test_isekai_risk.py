from backend.src.services.isekai_action_parser import IsekaiActionParser
from backend.src.services.isekai_risk import IsekaiRiskService
from backend.src.services.isekai_time import IsekaiTimeService
from test.backend.src.services.test_isekai_intent_planner import carriage_scene


def parse(text: str):
    return IsekaiActionParser(IsekaiTimeService()).parse(text, carriage_scene())


def test_careful_approach_reduces_danger_but_costs_opportunity():
    result = IsekaiRiskService().assess(parse("小心靠近马车"), {"time_of_day": "黄昏"})

    assert result.deltas["danger"] == -1
    assert result.deltas["opportunity"] == -1
    assert "风险降低" in result.summary


def test_force_open_increases_noise_and_danger():
    result = IsekaiRiskService().assess(parse("强行撬开车厢门"), {"time_of_day": "夜晚"})

    assert result.deltas["noise"] >= 3
    assert result.deltas["danger"] >= 2
    assert "制造声响" in result.summary


def test_hide_reduces_exposure_without_changing_resources():
    result = IsekaiRiskService().assess(parse("听到动静后躲起来"), {"time_of_day": "夜晚"})

    assert result.deltas["exposure"] < 0
    assert result.deltas["noise"] <= 0
    assert "暴露降低" in result.summary
