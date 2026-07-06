from __future__ import annotations

from typing import Any


class IsekaiWorldviewNormalizer:
    STYLE_GUIDANCE = (
        "世界观风格：故事发生在 DND 风格奇幻世界。避免现代商业、现代科技、"
        "或中文街边店铺感过强的表达；需要食物或店铺时，优先使用面包房、"
        "炉饼摊、馅饼铺、旅店厨房、集市摊贩、杂货铺、铁匠铺、药草铺等奇幻城镇表达。"
    )

    REPLACEMENTS = (
        ("烤饼铺子", "炉饼摊"),
        ("烧饼铺子", "炉饼摊"),
        ("烧饼铺", "炉饼摊"),
        ("早餐套餐", "晨食"),
        ("便利店", "杂货铺"),
        ("商业街", "集市街"),
        ("广告牌", "告示牌"),
        ("热销菜单", "招牌菜单"),
    )

    def normalize_text(self, value: Any) -> str:
        text = str(value or "")
        for source, target in self.REPLACEMENTS:
            text = text.replace(source, target)
        return text

    def normalize_list(self, values: Any, limit: int | None = None) -> list[str]:
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for item in values:
            text = self.normalize_text(item).strip()
            if text:
                result.append(text)
        return result[:limit] if limit else result

    def normalize_scene_update(self, scene_update: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(scene_update, dict):
            return {}
        result: dict[str, Any] = {}
        for key in ("location", "environment", "current_objective"):
            if key not in scene_update:
                continue
            value = self.normalize_text(scene_update.get(key)).strip()
            if value:
                result[key] = value
        objects = self.normalize_list(scene_update.get("important_objects"), limit=8)
        if objects:
            result["important_objects"] = objects
        return result
