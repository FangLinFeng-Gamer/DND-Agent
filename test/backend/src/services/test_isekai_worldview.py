from backend.src.services.isekai_worldview import IsekaiWorldviewNormalizer


def test_normalizes_out_of_setting_food_shop_terms():
    normalizer = IsekaiWorldviewNormalizer()

    text = normalizer.normalize_text("镇上新开了一家烤饼铺子，老板还卖早餐套餐。")

    assert "烤饼铺子" not in text
    assert "早餐套餐" not in text
    assert "炉饼摊" in text
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
