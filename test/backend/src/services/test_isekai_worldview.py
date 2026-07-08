from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer


def test_normalizes_out_of_setting_food_shop_terms():
    normalizer = IsekaiWorldviewNormalizer()

    text = normalizer.normalize_text("镇上新开了一家烤饼铺子，胖女人说这只是小本生意，还卖早餐套餐。")

    assert "烤饼铺子" not in text
    assert "胖女人" not in text
    assert "小本生意" not in text
    assert "早餐套餐" not in text
    assert "炉饼摊" in text
    assert "异族税" in text
    assert "晨食" in text


def test_normalizes_nested_scene_payload():
    normalizer = IsekaiWorldviewNormalizer()
    payload = {
        "location": "商业街",
        "environment": "街边有烤饼铺子和便利店。",
        "important_objects": ["广告牌", "热销菜单"],
    }

    result = normalizer.normalize_scene_update(payload)

    assert result["location"] == "集市街"
    assert result["environment"] == "街边有炉饼摊和杂货铺。"
    assert result["important_objects"] == ["告示牌", "招牌菜单"]


def test_repairs_high_satiety_hunger_contradiction_with_otherworld_signal():
    normalizer = IsekaiWorldviewNormalizer()

    result = normalizer.repair_narration(
        "你肚子饿得发慌，只能和普通小贩讨价还价。",
        {
            "visible_survival": {"satiety": 88, "hydration": 45},
            "character": {"race": "Tiefling", "world_reaction_tags": ["tiefling", "outsider"]},
            "scene": {"location": "白石镇炉饼摊", "npcs": ["炉饼摊主"]},
        },
    )

    assert "肚子饿" not in result
    assert "普通小贩" not in result
    assert any(signal in result for signal in ["异族", "异界", "外来者", "禁忌", "税", "预兆", "法则"])
