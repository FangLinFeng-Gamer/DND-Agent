from backend.src.services.isekai_time_cost import IsekaiTimeCostService


def test_indoor_movement_costs_one_to_five_minutes():
    cost = IsekaiTimeCostService().minutes("enter_location", {"scope": "indoor", "intensity": "normal"}, {})

    assert 1 <= cost <= 5
    assert cost == 3


def test_simple_repair_costs_ten_to_twenty_minutes():
    cost = IsekaiTimeCostService().minutes("repair", {"scope": "indoor", "intensity": "careful"}, {})

    assert 10 <= cost <= 20
    assert cost == 15


def test_town_and_wilderness_travel_have_different_cost_ranges():
    service = IsekaiTimeCostService()

    town = service.minutes("travel", {"scope": "town", "intensity": "normal"}, {})
    wilderness = service.minutes("travel", {"scope": "wilderness", "intensity": "normal"}, {})

    assert 10 <= town <= 20
    assert 60 <= wilderness <= 90


def test_environment_modifier_changes_time_cost_within_reason():
    cost = IsekaiTimeCostService().minutes(
        "search",
        {"scope": "room", "intensity": "careful"},
        {"dark": True, "crowded": False},
    )

    assert 15 <= cost <= 35
    assert cost == 30
