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
    SETTLEMENT_PRESSURE_GOALS = (
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
    SETTLEMENT_CLOCKS = (
        {
            "id": "sunset",
            "label": "日落倒计时",
            "value": 55,
            "max": 100,
            "visible": True,
            "trend": "rising",
            "description": "天色越暗，寻找安全落脚点越困难。",
        },
        {
            "id": "outsider_suspicion",
            "label": "外来者怀疑",
            "value": 20,
            "max": 100,
            "visible": True,
            "trend": "rising",
            "description": "当地人越怀疑异界来客，交涉和交易越困难。",
        },
        {
            "id": "curfew_patrol",
            "label": "宵禁巡逻",
            "value": 10,
            "max": 100,
            "visible": True,
            "trend": "rising",
            "description": "夜色和守卫巡逻会限制公开行动。",
        },
        {
            "id": "beast_activity",
            "label": "野兽活动",
            "value": 15,
            "max": 100,
            "visible": True,
            "trend": "rising",
            "description": "荒野里的声响和气味会吸引危险生物。",
        },
        {
            "id": "weather_thirst",
            "label": "天气与口渴",
            "value": 20,
            "max": 100,
            "visible": True,
            "trend": "rising",
            "description": "潮湿、闷热或寒冷天气会加重补水和保暖压力。",
        },
    )
    ENVIRONMENTAL_PLACE_WORDS = (
        "森林",
        "林地",
        "荒野",
        "岗哨",
        "哨塔",
        "矿道",
        "洞穴",
        "神庙",
        "遗迹",
        "山脚",
        "山坡",
        "营地",
        "海崖",
        "溪",
        "沟渠",
        "污染",
        "硫磺",
        "瘴气",
    )
    SETTLEMENT_PLACE_WORDS = (
        "旅店",
        "客栈",
        "酒馆",
        "集市",
        "街",
        "镇门",
        "城门",
        "前厅",
        "后厨",
        "客房",
        "店主",
        "摊",
        "镇上",
        "城内",
        "村里",
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

    def pressure_goals(self, scene: Any | None = None, world_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
        if self._uses_settlement_pressure(scene, world_state):
            return [dict(goal) for goal in self.SETTLEMENT_PRESSURE_GOALS]
        return self._environmental_pressure_goals(scene)

    def pressure_clocks(
        self,
        clocks: Any,
        scene: Any | None = None,
        world_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        current = [dict(clock) for clock in clocks] if isinstance(clocks, list) else []
        defaults = self.default_pressure_clocks(scene, world_state)
        allowed_ids = {str(clock.get("id") or "") for clock in defaults}
        by_id = {
            str(clock.get("id") or ""): clock
            for clock in current
            if isinstance(clock, dict) and str(clock.get("id") or "") in allowed_ids
        }
        for clock in defaults:
            existing = by_id.get(clock["id"])
            if existing is None:
                by_id[clock["id"]] = dict(clock)
                continue
            merged = {**clock, **existing}
            merged["label"] = clock["label"]
            merged["description"] = clock["description"]
            merged["value"] = self._clamp_clock(int(merged.get("value", clock["value"])), int(merged.get("max", 100)))
            by_id[clock["id"]] = merged
        return [by_id[clock["id"]] for clock in defaults if clock["id"] in by_id]

    def default_pressure_clocks(
        self,
        scene: Any | None = None,
        world_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self._uses_settlement_pressure(scene, world_state):
            return [dict(clock) for clock in self.SETTLEMENT_CLOCKS]
        return self._environmental_pressure_clocks(scene)

    def uses_settlement_pressure(self, scene: Any | None = None, world_state: dict[str, Any] | None = None) -> bool:
        return self._uses_settlement_pressure(scene, world_state)

    def _uses_settlement_pressure(self, scene: Any | None, world_state: dict[str, Any] | None) -> bool:
        place_text = self._scene_place_text(scene)
        scene_text = self._scene_text(scene)
        if any(word in place_text for word in self.SETTLEMENT_PLACE_WORDS):
            return True
        if any(marker in place_text for marker in ["镇外", "城外", "村外"]) and any(
            word in scene_text for word in self.ENVIRONMENTAL_PLACE_WORDS
        ):
            return False
        if any(word in scene_text for word in self.ENVIRONMENTAL_PLACE_WORDS):
            return False
        return any(word in place_text for word in ["镇", "城", "村"])

    def _environmental_pressure_goals(self, scene: Any | None) -> list[dict[str, str]]:
        scene_text = self._scene_text(scene)
        hazard_label = "确认环境风险"
        hazard_detail = "当前区域的地形、气味、痕迹或异常法则会影响探索、扎营和采集。"
        if any(word in scene_text for word in ["污染", "毒", "硫磺", "腐臭", "瘴气"]):
            hazard_label = "确认污染风险"
            hazard_detail = "当前场景存在污染或刺鼻异味，饮水、采集和扎营前都需要确认安全。"
        elif any(word in scene_text for word in ["遗迹", "神庙", "祭坛", "符文"]):
            hazard_label = "确认遗迹法则"
            hazard_detail = "遗迹中的符文、祭坛或空间异常可能改变搜索、开门和休息的风险。"
        elif any(word in scene_text for word in ["森林", "荒野", "岗哨", "矿道", "洞穴"]):
            hazard_label = "确认荒野危险"
            hazard_detail = "荒野中的魔物痕迹、陌生植物和地形遮蔽会改变移动与观察风险。"
        return [
            {
                "id": "environmental_hazard",
                "label": hazard_label,
                "detail": hazard_detail,
                "severity": "high",
            },
            {
                "id": "safe_water",
                "label": "确认可饮水源",
                "detail": "水源必须来自当前场景可见对象或已发现线索；污染、异味或未知法则会影响饮用和装水。",
                "severity": "high",
            },
            {
                "id": "shelter_route",
                "label": "确认庇护与退路",
                "detail": "扎营、进入子场景或离开当前区域前，需要确认可用庇护、通道和返回路线。",
                "severity": "medium",
            },
            {
                "id": "supply_pacing",
                "label": "管理体力与补给",
                "detail": "时间、疲劳、食物和水会随行动消耗；谨慎行动更安全但会失去时间。",
                "severity": "medium",
            },
        ]

    def _environmental_pressure_clocks(self, scene: Any | None) -> list[dict[str, Any]]:
        hazard = self._environmental_hazard_clock(scene)
        return [
            {
                "id": "sunset",
                "label": "日落倒计时",
                "value": 55,
                "max": 100,
                "visible": True,
                "trend": "rising",
                "description": "天色越暗，确认安全庇护点和退路越困难。",
            },
            {
                "id": "beast_activity",
                "label": "野兽活动",
                "value": 15,
                "max": 100,
                "visible": True,
                "trend": "rising",
                "description": "荒野里的声响、气味和血迹会吸引危险生物。",
            },
            {
                "id": "weather_thirst",
                "label": "天气与口渴",
                "value": 20,
                "max": 100,
                "visible": True,
                "trend": "rising",
                "description": "潮湿、闷热、寒冷或污染会加重补水和保暖压力。",
            },
            {
                "id": "shelter_security",
                "label": "庇护安全",
                "value": 25,
                "max": 100,
                "visible": True,
                "trend": "rising",
                "description": "临时庇护越不可靠，扎营、休息和处理伤势越危险。",
            },
            hazard,
        ]

    def _environmental_hazard_clock(self, scene: Any | None) -> dict[str, Any]:
        scene_text = self._scene_text(scene)
        label = "环境危险"
        description = "当前区域的地形、痕迹和异常法则会改变观察、搜索、扎营与移动风险。"
        if any(word in scene_text for word in ["污染", "毒", "硫磺", "腐臭", "瘴气"]):
            label = "污染风险"
            description = "污染、刺鼻异味或不明粉末会影响饮水、采集、搜索和扎营。"
        elif any(word in scene_text for word in ["遗迹", "神庙", "祭坛", "符文"]):
            label = "遗迹法则"
            description = "符文、祭坛或空间异常会改变搜索、开门和休息的风险。"
        elif any(word in scene_text for word in ["森林", "荒野", "岗哨", "矿道", "洞穴"]):
            label = "环境危险"
            description = "荒野中的魔物痕迹、陌生植物和地形遮蔽会改变移动与观察风险。"
        return {
            "id": "environmental_hazard",
            "label": label,
            "value": 20,
            "max": 100,
            "visible": True,
            "trend": "rising",
            "description": description,
        }

    def _clamp_clock(self, value: int, maximum: int) -> int:
        return max(0, min(maximum, value))

    def _scene_place_text(self, scene: Any | None) -> str:
        if scene is None:
            return ""
        path = getattr(scene, "location_path", None) or {}
        parts = [getattr(scene, "location", "")]
        if isinstance(path, dict):
            parts.extend(str(path.get(key) or "") for key in ["region", "site", "sublocation", "display_name"])
        return " ".join(parts)

    def _scene_text(self, scene: Any | None) -> str:
        if scene is None:
            return ""
        parts = [
            getattr(scene, "location", ""),
            getattr(scene, "environment", ""),
            getattr(scene, "current_objective", ""),
        ]
        parts.extend(str(item) for item in getattr(scene, "important_objects", []) or [])
        path = getattr(scene, "location_path", None) or {}
        if isinstance(path, dict):
            parts.extend(str(path.get(key) or "") for key in ["region", "site", "sublocation", "display_name"])
        return " ".join(parts)

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
