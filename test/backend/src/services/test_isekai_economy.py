from backend.src.services.isekai_economy import IsekaiEconomyService


def p1_world_state():
    return {"isekai_content": {"active_packs": ["old_furnace_inn_p1"]}}


def test_economy_does_not_convert_character_gold_into_real_currency():
    state = IsekaiEconomyService().ensure_state({}, {"gold": 13})

    assert state["currency"] == {"copper_total": 0}
    assert state["transaction_log"] == []
    assert state["entitlements"] == []


def test_currency_display_uses_decimal_gold_silver_copper_breakdown():
    service = IsekaiEconomyService()

    assert service.display_currency(137) == {"gold": 1, "silver": 3, "copper": 7, "copper_total": 137}
    assert service.display_currency(45) == {"gold": 0, "silver": 4, "copper": 5, "copper_total": 45}
    assert service.display_currency(8) == {"gold": 0, "silver": 0, "copper": 8, "copper_total": 8}


def test_price_config_converts_to_copper_total():
    service = IsekaiEconomyService()

    assert service.price_to_copper({"copper": 2}) == 2
    assert service.price_to_copper({"silver": 1, "copper": 5}) == 15
    assert service.price_to_copper({"gold": 1, "silver": 3, "copper": 7}) == 137


def test_purchase_bed_deducts_copper_records_transaction_and_entitlement():
    service = IsekaiEconomyService()
    state = service.ensure_state({"currency": {"copper_total": 10}}, {"gold": 0})

    result = service.purchase(
        state,
        item_id="inn_bed",
        buyer_note="住宿费",
        valid_until="第1天清晨",
        world_state=p1_world_state(),
    )

    assert result.success is True
    assert result.state["currency"]["copper_total"] == 7
    assert result.state["transaction_log"][-1] == {
        "lost": "3 铜",
        "gained": "二楼三号房钥匙、二楼三号房床位",
        "reason": "住宿费",
    }
    assert result.state["entitlements"][-1]["id"] == "inn_room_3_bed"
    assert result.state["entitlements"][-1]["valid_until"] == "第1天清晨"
    assert result.state["relationship_changes"][-1] == {
        "npc_id": "innkeeper_01",
        "name": "店主",
        "attitude": "愿意交易",
        "delta": 5,
    }


def test_purchase_fails_when_copper_is_insufficient():
    service = IsekaiEconomyService()
    state = service.ensure_state({"currency": {"copper_total": 1}}, {"gold": 0})

    result = service.purchase(
        state,
        item_id="inn_bed",
        buyer_note="住宿费",
        valid_until="第1天清晨",
        world_state=p1_world_state(),
    )

    assert result.success is False
    assert result.state["currency"]["copper_total"] == 1
    assert result.error_code == "insufficient_funds"
    assert result.shortfall_copper == 2
    assert "帮后厨修锅把换取床位" in result.alternatives


def test_repair_reward_grants_lodging_entitlement_without_charging_money():
    service = IsekaiEconomyService()
    state = service.ensure_state({"currency": {"copper_total": 1}}, {"gold": 0})

    result = service.grant_repair_reward(state, valid_until="第1天清晨", world_state=p1_world_state())

    assert result.success is True
    assert result.state["currency"]["copper_total"] == 1
    assert result.state["entitlements"][-1]["id"] == "inn_room_3_bed"
    assert result.state["transaction_log"][-1]["lost"] == "0 铜"
    assert result.state["relationship_changes"][-1]["attitude"] == "愿意交易"
