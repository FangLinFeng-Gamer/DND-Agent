from __future__ import annotations

from typing import Any


class IsekaiWorldviewNormalizer:
    STYLE_GUIDANCE = (
        "世界观风格：故事发生在 DND 风格奇幻世界。避免现代商业、现代科技、"
        "或中文街边店铺感过强的表达；需要食物或店铺时，优先使用面包房、"
        "炉饼摊、馅饼铺、旅店厨房、集市摊贩、杂货铺、铁匠铺、药草铺等奇幻城镇表达。"
    )
    SURVIVAL_DM_GUIDANCE = (
        "异世界生存风格：玩家是异界来客，NPC 应持续感知其异常身份。"
        "叙事要突出陌生法则、生存压力、文化隔阂、资源稀缺、地方禁忌和危险预兆。"
        "禁止长期滑向普通小镇日常、普通买卖跑腿或泛奇幻闲聊。"
        "每轮至少体现一个异世界信号：环境异常、种族反应、规则差异、资源压力、危险预兆或世界观信息。"
    )
    OTHERWORLD_SIGNAL_WORDS = (
        "异界",
        "异族",
        "外来者",
        "陌生法则",
        "禁忌",
        "异族税",
        "宵禁",
        "巡逻",
        "神殿",
        "领主",
        "魔灾",
        "灾厄",
        "预兆",
        "资源",
        "缺水",
        "危险",
        "法则",
    )
    PRESSURE_GOALS = (
        {
            "id": "lodging_identity",
            "label": "日落前取得落脚身份",
            "detail": "没有本地落脚身份，夜晚会被旅店、守卫和巡逻队拒绝或盘查。",
            "severity": "urgent",
        },
        {
            "id": "outsider_suspicion",
            "label": "外来者身份被怀疑",
            "detail": "玩家的异界来客气质、口音、衣料和种族特征会持续改变 NPC 态度。",
            "severity": "high",
        },
        {
            "id": "alien_tax",
            "label": "异族食宿价格翻倍",
            "detail": "购买食物、饮水、住宿和工具时，摊主可能按异族税或灾厄标记者附加费用。",
            "severity": "medium",
        },
        {
            "id": "curfew_patrol",
            "label": "夜晚宵禁巡逻",
            "detail": "日落后街面巡逻变密，无法解释身份的外来者会触发警戒、罚款或驱逐。",
            "severity": "high",
        },
    )

    REPLACEMENTS = (
        ("烤饼铺子", "炉饼摊"),
        ("烤饼铺", "炉饼摊"),
        ("烤饼炉", "炉板"),
        ("烤饼", "炉饼"),
        ("烧饼铺子", "炉饼摊"),
        ("烧饼铺", "炉饼摊"),
        ("胖女摊主", "因异族税压低声音的炉饼摊主"),
        ("胖女人", "因异族税压低声音的炉饼摊主"),
        ("小本生意", "异族税下的低声买卖"),
        ("普通小贩", "受领主税吏盯梢的集市摊贩"),
        ("普通集市", "受异族税与宵禁告示压着的集市"),
        ("早餐套餐", "晨食"),
        ("便利店", "杂货铺"),
        ("商业街", "集市街"),
        ("广告牌", "告示牌"),
        ("热销菜单", "招牌菜单"),
        ("菜单牌", "木刻食牌"),
    )

    def normalize_text(self, value: Any) -> str:
        text = str(value or "")
        for source, target in self.REPLACEMENTS:
            text = text.replace(source, target)
        return text

    def pressure_goals(self) -> list[dict[str, str]]:
        return [dict(goal) for goal in self.PRESSURE_GOALS]

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

    def repair_scene_state_payload(self, scene: dict[str, Any]) -> dict[str, Any]:
        original_scene = dict(scene)
        result = dict(scene)
        for key in ("location", "environment", "current_objective"):
            result[key] = self.normalize_text(result.get(key)).strip()
        result["important_objects"] = self.normalize_list(result.get("important_objects"), limit=8)
        result["npcs"] = self.normalize_list(result.get("npcs"), limit=8)
        result["world_changes"] = self.normalize_list(result.get("world_changes"), limit=12)
        if self._looks_like_legacy_town_scene(original_scene, result):
            result["environment"] = self._legacy_environment(result)
            result["important_objects"] = self._merge_unique(
                result.get("important_objects") or [],
                ["异族税告示", "宵禁木牌", "刻着灾厄征兆的护符"],
                limit=8,
            )
            result["npcs"] = self._merge_unique(result.get("npcs") or [], ["戒备的炉饼摊主", "巡逻税吏"], limit=8)
            result["current_objective"] = "在日落前取得落脚身份，并弄清镇民为何把外来者视作灾厄征兆。"
        return result

    def repair_narration(self, narration: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        text = self.normalize_text(narration)
        visible = context.get("visible_survival") or {}
        satiety = self._int_value(visible.get("satiety"), 100)
        if satiety >= 70:
            text = self._remove_high_satiety_hunger_conflict(text)
        if self._ordinary_trade_only(text) or not self.has_otherworld_signal(text):
            text = f"{text}{self._otherworld_signal_sentence(context)}"
        return text.strip()

    def has_otherworld_signal(self, text: str) -> bool:
        return any(word in str(text or "") for word in self.OTHERWORLD_SIGNAL_WORDS)

    def _looks_like_legacy_town_scene(self, original_scene: dict[str, Any], normalized_scene: dict[str, Any]) -> bool:
        original = " ".join(
            str(value)
            for value in [
                original_scene.get("location"),
                original_scene.get("environment"),
                original_scene.get("current_objective"),
                *(original_scene.get("important_objects") or []),
                *(original_scene.get("npcs") or []),
            ]
        )
        normalized = " ".join(
            str(value)
            for value in [
                normalized_scene.get("location"),
                normalized_scene.get("environment"),
                normalized_scene.get("current_objective"),
                *(normalized_scene.get("important_objects") or []),
                *(normalized_scene.get("npcs") or []),
            ]
        )
        legacy_words = ["烤饼", "胖女人", "胖女摊主", "小本生意", "普通买卖", "热销菜单"]
        normalized_legacy_words = ["低声买卖", "普通买卖"]
        return any(word in original for word in legacy_words) or any(word in normalized for word in normalized_legacy_words)

    def _legacy_environment(self, scene: dict[str, Any]) -> str:
        location = str(scene.get("location") or "白石镇炉饼摊").strip()
        return (
            f"{location}被异族税告示和宵禁木牌压得安静。"
            "摊主看见外来者的衣着与气息后立刻压低声音，旁边巡逻税吏正把陌生面孔记进木片名册。"
        )

    def _remove_high_satiety_hunger_conflict(self, text: str) -> str:
        replacements = (
            ("你肚子饿得发慌，", ""),
            ("肚子饿得发慌", "腹中并不空"),
            ("肚子饿", "腹中尚有余力"),
            ("明显饥饿", "并未明显饥饿"),
            ("饥饿感", "补给意识"),
            ("饿得", "被异界空气压得"),
        )
        for source, target in replacements:
            text = text.replace(source, target)
        return text

    def _ordinary_trade_only(self, text: str) -> bool:
        ordinary_words = ["讨价还价", "买卖", "摊贩", "集市", "炉饼摊"]
        return any(word in text for word in ordinary_words) and not self.has_otherworld_signal(text)

    def _otherworld_signal_sentence(self, context: dict[str, Any]) -> str:
        character = context.get("character") or {}
        scene = context.get("scene") or {}
        race = str(character.get("race") or "外来者")
        location = str(scene.get("location") or "此地")
        has_npcs = bool(scene.get("npcs"))
        visible = context.get("visible_survival") or {}
        hydration = self._int_value(visible.get("hydration"), 100)
        if self._is_wilderness_location(location):
            if hydration < 50:
                return f" {location}的湿气带着陌生矿味，喉咙的干涩提醒你：这里的水源也许受异界法则污染。"
            return f" {location}的空气带着异界法则的压迫感，石缝符文和魔物气味让你很难判断下一处庇护是否可靠。"
        if hydration < 50:
            return f" {location}的水井旁挂着领主水税牌，旁人把你这个{race}外来者当成缺水季的危险预兆。"
        if not has_npcs and not any(word in location for word in ["镇", "城", "集市", "村"]):
            return f" {location}的空气带着异界法则的压迫感，你这个{race}外来者很难判断下一处水源或庇护是否可靠。"
        return f" {location}的镇民注意到你这个{race}外来者，异族税和宵禁规条立刻改变了他们的态度。"

    def _is_wilderness_location(self, location: str) -> bool:
        return any(word in location for word in ["洞", "岩", "森林", "林", "荒野", "溪", "河岸", "山", "谷", "沼泽", "废墟"])

    def _merge_unique(self, current: list[str], additions: list[str], limit: int) -> list[str]:
        result: list[str] = []
        for item in [*current, *additions]:
            text = self.normalize_text(item).strip()
            if text and text not in result:
                result.append(text)
        return result[:limit]

    def _int_value(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
