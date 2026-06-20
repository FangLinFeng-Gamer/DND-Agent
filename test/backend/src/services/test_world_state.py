from backend.src.services.stories import DEFAULT_STORY
from backend.src.services.world_state import WorldStateService, initial_world_state_for_story


def moonwell_clock(state):
    return next(clock for clock in state["threat_clocks"] if clock["id"] == "moonwell_curse")


def test_status_question_does_not_advance_world_state():
    service = WorldStateService(None)

    classification = service.classify_action("equipment.steel-longsword是什么")
    state = initial_world_state_for_story(DEFAULT_STORY)
    delta = service.preview_advance(state, classification)
    committed = service.commit_advance(state, delta)

    assert classification["message_type"] == "status_question"
    assert classification["advance_world"] is False
    assert moonwell_clock(committed)["value"] == 0
    assert committed["last_advance"]["advanced"] is False


def test_rule_question_does_not_advance_world_state():
    service = WorldStateService(None)

    classification = service.classify_action("这个需要掷什么骰？")

    assert classification["message_type"] == "rule_question"
    assert classification["advance_world"] is False
    assert classification["time_cost"] == 0


def test_explicit_time_cost_action_advances_moonwell_clock():
    service = WorldStateService(None)
    state = initial_world_state_for_story(DEFAULT_STORY)

    classification = service.classify_action("我去铁匠铺搜查后院")
    delta = service.preview_advance(state, classification)
    committed = service.commit_advance(state, delta)

    assert classification["message_type"] == "in_world_action"
    assert classification["advance_world"] is True
    assert moonwell_clock(committed)["value"] == 1
    assert committed["turn_count"] == 1
    assert committed["last_advance"]["affected_clocks"] == ["moonwell_curse"]


def test_high_risk_action_advances_pressure_clock():
    service = WorldStateService(None)
    state = initial_world_state_for_story(DEFAULT_STORY)

    classification = service.classify_action("我偷偷撬开铁匠铺的门")
    delta = service.preview_advance(state, classification)
    committed = service.commit_advance(state, delta)
    guard_alert = next(clock for clock in committed["pressure_clocks"] if clock["id"] == "guard_alert")

    assert classification["risk_level"] == "high"
    assert guard_alert["value"] == 1
    assert "guard_alert" in committed["last_advance"]["affected_clocks"]


def test_ambiguous_action_requires_clarification_and_does_not_advance():
    service = WorldStateService(None)
    state = initial_world_state_for_story(DEFAULT_STORY)

    classification = service.classify_action("我看看有没有其他东西")
    delta = service.preview_advance(state, classification)
    committed = service.commit_advance(state, delta)

    assert classification["message_type"] == "ambiguous_action"
    assert classification["needs_clarification"] is True
    assert classification["advance_world"] is False
    assert moonwell_clock(committed)["value"] == 0


def test_moonwell_clock_reaches_festival_panic_at_three():
    service = WorldStateService(None)
    state = initial_world_state_for_story(DEFAULT_STORY)

    for content in ["我去铁匠铺", "我搜查后院", "我翻过后院栅栏离开"]:
        classification = service.classify_action(content)
        delta = service.preview_advance(state, classification)
        state = service.commit_advance(state, delta)

    assert moonwell_clock(state)["value"] == 3
    assert state["phase"] == "festival_panic"
    assert state["phase_label"] == "节庆混乱"
    assert any("音乐停了" in event for event in state["visible_events"])
