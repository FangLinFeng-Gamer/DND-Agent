import json

from backend.src.schemas.adventure import AdventureCreate, MessageCreate
from backend.src.services.isekai import IsekaiSurvivalService
from backend.src.services.isekai_consequences import IsekaiConsequenceResolver
from backend.src.services.isekai_pressure_events import IsekaiPressureEventService
from backend.src.services.isekai_quests import IsekaiQuestService
from backend.src.services.isekai_rewards import IsekaiRewardService
from test.backend.src.services.test_isekai_survival import (
    StructuredStateChangeIsekaiLLMClient,
    activate_test_model,
    set_character_state,
)


def p1_world_state(**extra):
    state = {"isekai_content": {"active_packs": ["old_furnace_inn_p1"], "activation": "explicit"}}
    state.update(extra)
    return state


def test_quest_service_keeps_only_night_wolf_line():
    service = IsekaiQuestService()
    world_state = p1_world_state(
        isekai_quest={
            "active_quest_id": "merchant_guild_line",
            "stage": "rumor_heard",
            "flags": {"foreign": True},
        }
    )

    next_state, applied = service.ensure_single_quest(world_state)

    assert next_state["isekai_quest"] == {
        "active_quest_id": "night_wolf_line",
        "stage": "not_started",
        "flags": {},
    }
    assert applied["blocked"] == [
        {"quest_id": "merchant_guild_line", "blocked_reason": "p1_single_quest_only"}
    ]


def test_quest_service_blocks_second_quest_proposal():
    service = IsekaiQuestService()
    world_state = service.initial_world_state(p1_world_state())

    next_state, applied = service.apply_quest_proposals(
        world_state,
        [{"quest_id": "temple_relic_line", "stage": "not_started"}],
        action_type="quest_resolution",
    )

    assert next_state["isekai_quest"]["active_quest_id"] == "night_wolf_line"
    assert next_state["isekai_quest"]["stage"] == "not_started"
    assert applied["blocked"] == [
        {"quest_id": "temple_relic_line", "blocked_reason": "p1_single_quest_only"}
    ]


def test_pressure_event_fires_once_and_respects_cooldown():
    service = IsekaiPressureEventService()
    world_state = p1_world_state(
        isekai_quest={"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}},
        isekai_economy={"entitlements": [], "currency": {"copper_total": 10}},
    )
    turn = {"survival": {"time_of_day": "夜晚"}, "time": {"advances_time": True}, "action_type": "travel"}

    fired_state, event = service.evaluate(world_state, turn)
    second_state, second_event = service.evaluate(fired_state, turn)

    assert event["id"] == "curfew_bell_01"
    assert event["type"] == "curfew"
    assert event["state_delta"] == {"curfew_risk": 1}
    assert fired_state["isekai_risks"]["curfew_risk"] == 1
    assert fired_state["isekai_pressure_events"]["cooldowns"]["curfew_bell_01"] == 5
    assert second_event is None
    assert second_state["isekai_pressure_events"]["last_event"] is None


def test_pressure_event_does_not_repeat_for_five_cooldown_turns():
    service = IsekaiPressureEventService()
    world_state = p1_world_state(
        isekai_quest={"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}},
        isekai_economy={"entitlements": [], "currency": {"copper_total": 10}},
    )
    turn = {"survival": {"time_of_day": "夜晚"}, "time": {"advances_time": True}, "action_type": "travel"}

    world_state, first = service.evaluate(world_state, turn)
    events = []
    for _ in range(5):
        world_state, event = service.evaluate(world_state, turn)
        events.append(event)

    assert first["id"] == "curfew_bell_01"
    assert events[:4] == [None, None, None, None]
    assert events[4]["id"] == "curfew_bell_01"


def test_reward_service_writes_items_currency_relationships_and_clues():
    service = IsekaiRewardService()
    character = {"inventory": ["干粮 x1"]}
    world_state = {
        "isekai_economy": {
            "currency": {"copper_total": 10},
            "entitlements": [],
            "transaction_log": [],
            "relationship_changes": [],
        },
        "isekai_clues": [],
    }

    next_character, next_world, applied = service.apply(
        character,
        world_state,
        {
            "items_added": ["暗夜狼牙 x1"],
            "currency_delta": 8,
            "relationship_delta": [{"npc_id": "old_furnace_keeper", "name": "店主", "trust": 10}],
            "clues_added": ["暗夜狼惧怕梦魇草燃烟"],
            "entitlements_added": [],
        },
        reason="任务奖励",
    )

    assert "暗夜狼牙 x1" in next_character["inventory"]
    assert next_world["isekai_economy"]["currency"]["copper_total"] == 18
    assert next_world["isekai_economy"]["transaction_log"][-1] == {
        "lost": "0 铜",
        "gained": "8 铜",
        "reason": "任务奖励",
    }
    assert next_world["isekai_economy"]["relationship_changes"][-1]["npc_id"] == "old_furnace_keeper"
    assert next_world["isekai_clues"] == ["暗夜狼惧怕梦魇草燃烟"]
    assert applied["items_added"] == ["暗夜狼牙 x1"]
    assert applied["currency_delta"] == 8


def test_consequence_resolver_blocks_model_rewards_for_status_check():
    resolver = IsekaiConsequenceResolver()
    character = {"inventory": []}
    world_state = {
        "isekai_economy": {"currency": {"copper_total": 10}, "entitlements": [], "transaction_log": []},
        "isekai_quest": {"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}},
    }

    next_character, next_world, applied = resolver.resolve(
        character,
        world_state,
        {
            "money_changes": [{"copper_delta": -3, "reason": "闲聊扣款"}],
            "item_rewards": ["二楼三号房钥匙"],
            "entitlement_changes": [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}],
            "quest_stage_changes": [{"quest_id": "night_wolf_line", "stage": "resolved"}],
            "npc_relationship_changes": [{"npc_id": "innkeeper_01", "trust": 20}],
        },
        action_type="status_check",
    )

    assert next_character == character
    assert next_world == world_state
    assert applied["blocked"]["money_changes"] == [{"copper_delta": -3, "reason": "闲聊扣款"}]
    assert applied["blocked"]["item_rewards"] == ["二楼三号房钥匙"]
    assert applied["blocked"]["entitlement_changes"] == [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}]
    assert applied["blocked"]["quest_stage_changes"] == [{"quest_id": "night_wolf_line", "stage": "resolved"}]
    assert applied["blocked"]["npc_relationship_changes"] == [{"npc_id": "innkeeper_01", "trust": 20}]


def test_consequence_resolver_blocks_negotiate_from_granting_bed():
    resolver = IsekaiConsequenceResolver()
    character = {"inventory": []}
    world_state = {
        "isekai_economy": {"currency": {"copper_total": 10}, "entitlements": [], "transaction_log": []},
        "isekai_quest": {"active_quest_id": "night_wolf_line", "stage": "not_started", "flags": {}},
    }

    next_character, next_world, applied = resolver.resolve(
        character,
        world_state,
        {"entitlement_changes": [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}]},
        action_type="negotiate",
    )

    assert next_character == character
    assert next_world["isekai_economy"]["entitlements"] == []
    assert applied["blocked"]["entitlement_changes"] == [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}]


def test_model_proposals_are_blocked_in_non_resolution_turn(store):
    activate_test_model(store)
    service = IsekaiSurvivalService(
        store,
        llm_client=StructuredStateChangeIsekaiLLMClient(
            {
                "narration": "模型试图说你获得第二任务、钥匙和奖励。",
                "state_changes": {
                    "quest_stage_changes": [{"quest_id": "merchant_guild_line", "stage": "not_started"}],
                    "item_rewards": ["二楼三号房钥匙"],
                    "money_changes": [{"copper_delta": 99, "reason": "模型奖励"}],
                    "entitlement_changes": [{"id": "inn_room_3_bed", "name": "二楼三号房床位"}],
                    "npc_relationship_changes": [{"npc_id": "innkeeper_01", "trust": 99}],
                },
            }
        ),
    )
    adventure = service.create_adventure(AdventureCreate(title="Proposal Gate", mode="isekai_survival"))
    before_world = adventure.world_state

    response = service.advance(adventure.id, MessageCreate(content="我现在的任务是什么？", locale="zh-CN"))

    state = response.adventure.world_state
    blocked = response.dm_message.metadata["state_changes_applied"]["blocked"]
    assert state["isekai_quest"]["active_quest_id"] is None
    assert state["isekai_quest"]["stage"] == before_world["isekai_quest"]["stage"]
    assert "二楼三号房钥匙" not in response.adventure.isekai_character["inventory"]
    assert state["isekai_economy"]["currency"] == before_world["isekai_economy"]["currency"]
    assert blocked["quest_stage_changes"] == [{"quest_id": "merchant_guild_line", "stage": "not_started"}]
    assert blocked["item_rewards"] == ["二楼三号房钥匙"]


def test_existing_isekai_adventure_read_migrates_missing_world_state_without_p1_content(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Legacy P1 Fields", mode="isekai_survival"))
    world_state = service.adventures.get_world_state(adventure.id)
    world_state.pop("isekai_quest", None)
    world_state.pop("isekai_clues", None)
    world_state.pop("isekai_pressure_events", None)
    world_state.pop("isekai_risks", None)
    service.adventures.update_world_state(adventure.id, world_state)

    migrated = service.adventures.get(adventure.id, include_messages=False)

    assert migrated.world_state["isekai_quest"] == {"active_quest_id": None, "stage": "none", "flags": {}}
    assert migrated.world_state["isekai_clues"] == []
    assert migrated.world_state["isekai_pressure_events"]["cooldowns"] == {}
    assert migrated.world_state["isekai_pressure_events"]["last_event"] is None
    assert migrated.world_state["isekai_risks"] == {}


def test_night_wolf_line_vertical_slice_records_quest_clues_and_reward(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Night Wolf Line", mode="isekai_survival"))
    set_character_state(store, adventure.id, gold=0, inventory=["水囊(2/3)", "干粮 x1"])
    world_state = dict(adventure.world_state)
    world_state["isekai_content"] = {"active_packs": ["old_furnace_inn_p1"], "activation": "explicit"}
    world_state["isekai_economy"] = {"currency": {"copper_total": 10}, "entitlements": [], "transaction_log": []}
    world_state = service.quests.initial_world_state(world_state)
    service.adventures.update_world_state(adventure.id, world_state)

    service.advance(adventure.id, MessageCreate(content="进入灰石镇", locale="zh-CN"))
    service.advance(adventure.id, MessageCreate(content="进入旧炉旅店前厅", locale="zh-CN"))
    service.advance(adventure.id, MessageCreate(content="支付铜币买床位", locale="zh-CN"))
    rumor = service.advance(adventure.id, MessageCreate(content="和店主交谈，打听暗夜狼", locale="zh-CN"))
    night = service.advance(adventure.id, MessageCreate(content="夜里听见狼嚎，我从小窗观察", locale="zh-CN"))
    prepared = service.advance(adventure.id, MessageCreate(content="第二天向店主打听梦魇草和暗夜狼", locale="zh-CN"))
    tracking = service.advance(adventure.id, MessageCreate(content="前往北坡追踪暗夜狼痕迹", locale="zh-CN"))
    observed = service.advance(adventure.id, MessageCreate(content="发现暗夜狼痕迹后先观察", locale="zh-CN"))
    resolved = service.advance(adventure.id, MessageCreate(content="回镇向店主汇报暗夜狼惧怕梦魇草燃烟", locale="zh-CN"))

    assert rumor.adventure.world_state["isekai_quest"]["stage"] == "rumor_heard"
    assert night.adventure.world_state["isekai_quest"]["stage"] == "night_event_seen"
    assert night.adventure.world_state["isekai_pressure_events"]["last_event"]["id"] == "night_wolf_howl_01"
    assert prepared.adventure.world_state["isekai_quest"]["stage"] == "prepared"
    assert tracking.adventure.world_state["isekai_quest"]["stage"] == "tracking"
    assert observed.adventure.world_state["isekai_quest"]["stage"] == "tracking"
    assert resolved.adventure.world_state["isekai_quest"]["stage"] == "resolved"
    assert "暗夜狼惧怕梦魇草燃烟" in resolved.adventure.world_state["isekai_clues"]
    assert "暗夜狼牙 x1" in resolved.adventure.isekai_character["inventory"]
    assert resolved.adventure.world_state["isekai_economy"]["currency"]["copper_total"] == 15
    assert resolved.adventure.world_state["isekai_economy"]["relationship_changes"][-1]["npc_id"] == "old_furnace_keeper"
    assert len({resolved.adventure.world_state["isekai_quest"]["active_quest_id"]}) == 1
    assert json.dumps(resolved.adventure.world_state, ensure_ascii=False).count("night_wolf_line") >= 1
