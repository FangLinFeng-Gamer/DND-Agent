from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.src.schemas.adventure import SceneState


@dataclass(frozen=True)
class ParsedIsekaiAction:
    action_type: str
    time_cost_minutes: int
    advances_time: bool
    survival_intent: str
    reason: str
    target_id: str = ""
    target_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    confidence: str = "medium"
    confidence_reasons: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    requires_clarification: bool = False
    candidates: list[dict[str, Any]] = field(default_factory=list)
    pending_intent: str = ""


class IsekaiActionParser:
    def __init__(self, time_service: Any):
        self.time = time_service

    def parse(
        self,
        content: str,
        scene: SceneState | None = None,
        scene_context: dict[str, Any] | None = None,
    ) -> ParsedIsekaiAction:
        text = str(content or "").strip().lower()
        context = scene_context or self._scene_context(scene)
        action_type, matched_rules, pending_intent = self._intent(text, context)
        target_candidates = self._target_candidates(text, scene, action_type)
        implicit_single_target = False
        if not target_candidates:
            target_candidates = self._implicit_affordance_targets(scene, action_type)
            implicit_single_target = len(target_candidates) == 1
        if len(target_candidates) > 1:
            return self._build(
                "clarification",
                confidence="low",
                confidence_reasons=["ambiguous_target"],
                matched_rules=[*matched_rules, "target:ambiguous"],
                requires_clarification=True,
                candidates=target_candidates,
            )

        target = target_candidates[0] if target_candidates else {}
        confidence_reasons = self._confidence_reasons(action_type, target)
        if implicit_single_target:
            confidence_reasons.append(f"single_affordance_target:{action_type}")
        if target:
            matched_rules = [*matched_rules, f"target:{target['id']}"]
        arguments = self._arguments(text, action_type)
        return self._build(
            action_type,
            target_id=str(target.get("id") or ""),
            target_name=str(target.get("name") or ""),
            arguments=arguments,
            confidence="high" if target or action_type in {"status_check", "table_talk", "sleep", "seek_shelter"} else "medium",
            confidence_reasons=confidence_reasons,
            matched_rules=matched_rules,
            pending_intent=pending_intent,
        )

    def _intent(self, text: str, context: dict[str, Any]) -> tuple[str, list[str], str]:
        if self._is_manage_inventory(text):
            return "manage_inventory", ["intent:manage_inventory"], ""
        if self._is_status_check(text):
            return "status_check", ["intent:status_check"], ""
        if self._is_table_talk(text):
            return "table_talk", ["intent:table_talk"], ""
        if self._is_compound_observe_then_gather(text):
            return "observe", ["intent:observe", "compound:observe_then_gather_if_safe"], "gather_if_safe"
        if self._is_negated_sleep_seek_shelter(text):
            return "seek_shelter", ["intent:seek_shelter", "negated_sleep"], ""
        if self._is_negotiate(text):
            return "negotiate", ["intent:negotiate"], ""
        if self._is_eat_meal(text):
            return "eat_meal", ["intent:eat_meal"], ""
        if self._is_purchase(text):
            return "purchase", ["intent:purchase"], ""
        if self._is_repair(text):
            return "repair", ["intent:repair"], ""
        if context.get("has_npcs") and self._is_npc_dialogue_intent(text):
            return "short_dialogue", ["intent:short_dialogue", "scene_has_npc"], ""
        if self._is_refill_water(text):
            return "refill_water", ["intent:refill_water"], ""
        if self._is_secure_shelter(text):
            return "secure_shelter", ["intent:secure_shelter"], ""
        if self._is_force_open(text):
            return "force_open", ["intent:force_open"], ""
        if self._is_hide(text):
            return "hide", ["intent:hide"], ""
        if self._is_avoid(text):
            return "avoid", ["intent:avoid"], ""
        if self._is_approach(text):
            return "approach", ["intent:approach"], ""
        if self._is_enter_location(text):
            return "enter_location", ["intent:enter_location"], ""
        if self._is_seek_shelter(text):
            return "seek_shelter", ["intent:seek_shelter"], ""
        if self._is_sleep_intent(text):
            return "sleep", ["intent:sleep"], ""
        if any(word in text for word in ["短休", "小憩", "休息", "rest"]):
            return "rest_short", ["intent:rest_short"], ""
        if self._is_drink_water(text) and self._is_eat_food(text):
            return "eat_drink", ["intent:eat_drink"], ""
        if self._is_drink_water(text):
            return "drink_water", ["intent:drink_water"], ""
        if self._is_eat_food(text):
            return "eat_food", ["intent:eat_food"], ""
        if any(word in text for word in ["做汤", "做饭", "做菜", "做一锅", "热汤", "烹饪", "料理", "煮", "cook"]):
            return "cook", ["intent:cook"], ""
        if self._is_gather(text):
            return "gather", ["intent:gather"], ""
        if any(word in text for word in ["寻找食物", "寻找水", "找水", "觅食", "采集", "打猎", "forage"]):
            return "forage", ["intent:forage"], ""
        if self._is_travel(text):
            return "travel", ["intent:travel"], ""
        if any(word in text for word in ["搜索", "搜寻", "调查", "仔细找", "寻找", "search"]):
            return "search", ["intent:search"], ""
        if any(word in text for word in ["观察", "查看", "聆听", "听", "inspect", "look"]):
            return "observe", ["intent:observe"], ""
        if any(word in text for word in ["交谈", "询问", "问", "说", "talk"]):
            return "short_dialogue", ["intent:short_dialogue"], ""
        return "table_talk", ["intent:table_talk", "fallback:no_time_action"], ""

    def _build(
        self,
        action_type: str,
        *,
        target_id: str = "",
        target_name: str = "",
        arguments: dict[str, Any] | None = None,
        confidence: str,
        confidence_reasons: list[str],
        matched_rules: list[str],
        requires_clarification: bool = False,
        candidates: list[dict[str, Any]] | None = None,
        pending_intent: str = "",
    ) -> ParsedIsekaiAction:
        resolution = self.time.resolve_action_type(action_type)
        return ParsedIsekaiAction(
            action_type=resolution.action_type,
            time_cost_minutes=resolution.time_cost_minutes,
            advances_time=resolution.advances_time,
            survival_intent=resolution.survival_intent,
            reason=resolution.reason,
            target_id=target_id,
            target_name=target_name,
            arguments=arguments or {},
            confidence=confidence,
            confidence_reasons=confidence_reasons,
            matched_rules=matched_rules,
            requires_clarification=requires_clarification,
            candidates=candidates or [],
            pending_intent=pending_intent,
        )

    def _scene_context(self, scene: SceneState | None) -> dict[str, Any]:
        if scene is None:
            return {"has_npcs": False}
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects, *scene.npcs])
        has_npcs = bool(scene.npcs) or any(
            word in scene_text for word in ["摊主", "守卫", "商人", "旅人", "镇民", "祭司", "老板", "铁匠", "小贩", "巡逻"]
        )
        return {"has_npcs": has_npcs}

    def _target_candidates(self, text: str, scene: SceneState | None, action_type: str) -> list[dict[str, Any]]:
        if scene is None or action_type in {"table_talk", "status_check", "sleep", "rest_short", "clarification"}:
            return []
        interactables = [entry for entry in scene.interactables if isinstance(entry, dict)]
        exact_matches = [self._candidate(entry) for entry in interactables if str(entry.get("name") or "").strip() in text]
        if exact_matches:
            supported = [entry for entry in exact_matches if self._supports_action(entry, action_type)]
            if supported:
                return supported
            if action_type not in {"repair", "force_open", "purchase", "refill_water", "gather", "secure_shelter"}:
                return exact_matches
        loose_matches = [
            self._candidate(entry)
            for entry in interactables
            if self._loose_target_match(text, str(entry.get("name") or ""))
            and self._supports_action(entry, action_type)
        ]
        return loose_matches

    def _implicit_affordance_targets(self, scene: SceneState | None, action_type: str) -> list[dict[str, Any]]:
        if scene is None or action_type not in {"refill_water"}:
            return []
        return [
            self._candidate(entry)
            for entry in scene.interactables
            if isinstance(entry, dict) and self._supports_action(self._candidate(entry), action_type)
        ]

    def _candidate(self, entry: dict[str, Any]) -> dict[str, Any]:
        result = {
            "id": str(entry.get("id") or ""),
            "name": str(entry.get("name") or ""),
            "type": str(entry.get("type") or "object"),
            "affordances": [str(item) for item in entry.get("affordances", []) if str(item).strip()],
        }
        risk = str(entry.get("risk") or "").strip()
        if risk:
            result["risk"] = risk
        return result

    def _supports_action(self, candidate: dict[str, Any], action_type: str) -> bool:
        affordances = "".join(candidate.get("affordances") or [])
        expected = {
            "gather": ["采集", "拾取", "摘", "拿起"],
            "refill_water": ["装水", "取水", "补水"],
            "observe": ["观察", "检查", "查看"],
            "short_dialogue": ["交涉", "交谈", "询问"],
            "enter_location": ["进入", "查看"],
            "approach": ["靠近", "接近", "观察", "绕行"],
            "hide": ["躲避", "隐藏", "藏身", "规避"],
            "avoid": ["躲避", "避开", "绕开", "规避", "绕行"],
            "force_open": ["撬开", "撬锁", "强行打开", "破坏", "打开"],
            "negotiate": ["交涉", "询问价格", "支付"],
            "purchase": ["支付", "购买", "买"],
            "repair": ["修理", "修好", "维修"],
            "eat_meal": ["食用", "吃", "购买"],
            "search": ["搜索", "调查", "检查"],
            "manage_inventory": ["拾取", "拿起", "整理"],
            "secure_shelter": ["堵门", "加固", "封堵"],
        }.get(action_type)
        if not expected:
            return True
        return any(word in affordances for word in expected)

    def _loose_target_match(self, text: str, name: str) -> bool:
        if not name:
            return False
        if name in text:
            return True
        for token in [
            "浆果",
            "水囊",
            "水桶",
            "雨水桶",
            "小屋",
            "门板",
            "门",
            "马车",
            "车厢",
            "车厢门",
            "锁",
            "门锁",
            "货袋",
            "暗格",
            "破口",
            "猎网",
            "燧石",
            "伐木工",
            "摊主",
            "守卫",
            "店主",
            "后厨",
            "厨房",
            "锅把",
            "热炖菜",
            "炖菜",
            "床位",
            "客房",
            "前厅",
        ]:
            if token in text and token in name:
                return True
        return False

    def _confidence_reasons(self, action_type: str, target: dict[str, Any]) -> list[str]:
        reasons = [f"intent:{action_type}"]
        if target:
            reasons.append("exact_target_name")
            if self._supports_action(target, action_type):
                reasons.append(f"affordance_match:{action_type}")
        return reasons

    def _arguments(self, text: str, action_type: str) -> dict[str, Any]:
        if action_type == "drink_water":
            return {"consumes": ["water"]}
        if action_type == "eat_food":
            return {"consumes": ["food"]}
        if action_type == "eat_drink":
            return {"consumes": ["food", "water"]}
        if action_type == "refill_water":
            return {"resource": "water"}
        if action_type == "enter_location":
            return {
                "caution": any(word in text for word in ["不急", "小心", "谨慎", "悄悄", "先不"]),
                "constraints": self._constraints(text),
                "scope": self._scope(text, action_type),
                "target_node_id": self._target_node_id(text),
            }
        if action_type in {"approach", "hide", "avoid", "force_open"}:
            return {
                "style": self._style(text, action_type),
                "constraints": self._constraints(text),
            }
        if action_type == "negotiate":
            return {"scope": self._scope(text, action_type), "topic": self._negotiate_topic(text), "intensity": self._intensity(text)}
        if action_type == "purchase":
            return {"scope": self._scope(text, action_type), "item_id": self._purchase_item_id(text), "intensity": self._intensity(text)}
        if action_type == "repair":
            return {"scope": self._scope(text, action_type), "intensity": self._intensity(text), "target_node_id": self._target_node_id(text)}
        if action_type == "eat_meal":
            return {"scope": self._scope(text, action_type), "item_id": "stew_meal", "intensity": self._intensity(text)}
        return {}

    def _scope(self, text: str, action_type: str) -> str:
        if any(word in text for word in ["后厨", "厨房", "前厅", "客房", "旅店", "屋内", "室内", "店主", "床位", "炖菜", "锅把"]):
            return "indoor"
        if any(word in text for word in ["镇内", "镇上", "灰石镇", "镇门", "街"]):
            return "town"
        if any(word in text for word in ["镇外", "荒野", "森林", "赶路"]):
            return "wilderness"
        if action_type in {"negotiate", "purchase", "repair", "eat_meal"}:
            return "indoor"
        return ""

    def _intensity(self, text: str) -> str:
        if any(word in text for word in ["小心", "仔细", "谨慎", "认真"]):
            return "careful"
        if any(word in text for word in ["快速", "赶紧", "立刻"]):
            return "quick"
        return "normal"

    def _target_node_id(self, text: str) -> str:
        if "灰石镇" in text and "旅店" not in text:
            return "graystone_town"
        if "旧炉旅店" in text or "旅店前厅" in text or "前厅" in text:
            return "inn_front_hall"
        if "后厨" in text or "厨房" in text:
            return "inn_kitchen"
        if "客房" in text or "床位" in text or "三号房" in text:
            return "inn_room_3"
        if "马厩" in text:
            return "inn_stable"
        return ""

    def _negotiate_topic(self, text: str) -> str:
        if any(word in text for word in ["住宿", "床位", "房"]):
            return "lodging"
        if any(word in text for word in ["炖菜", "饭", "吃"]):
            return "meal"
        return "general"

    def _purchase_item_id(self, text: str) -> str:
        if any(word in text for word in ["床位", "住宿", "钥匙", "房"]):
            return "inn_bed"
        if any(word in text for word in ["炖菜", "热食", "饭"]):
            return "stew_meal"
        return ""

    def _style(self, text: str, action_type: str) -> str:
        if any(word in text for word in ["悄悄", "潜行", "无声", "安静"]):
            return "quiet"
        if any(word in text for word in ["小心", "谨慎", "慢慢", "试探"]):
            return "careful"
        if any(word in text for word in ["快速", "立刻", "马上", "冲过去"]):
            return "quick"
        if any(word in text for word in ["强行", "用力", "猛地", "硬"]):
            return "forceful"
        if action_type == "hide":
            return "quiet"
        if action_type == "force_open":
            return "forceful"
        return "normal"

    def _constraints(self, text: str) -> list[str]:
        constraints: list[str] = []
        if any(word in text for word in ["不急着翻", "不翻", "不搜", "不搜索", "不搜刮", "先不翻", "先不搜", "只观察"]):
            constraints.extend(["no_loot", "no_search"])
        if any(word in text for word in ["保持距离", "别靠太近", "不贴近"]):
            constraints.append("keep_distance")
        return list(dict.fromkeys(constraints))

    def _is_status_check(self, text: str) -> bool:
        return any(
            word in text
            for word in [
                "我的状态",
                "当前状态",
                "状态怎么样",
                "生存状态",
                "背包",
                "库存",
                "包里",
                "属性",
                "生命值",
                "hp",
                "金币",
                "多少钱",
                "多少干粮",
                "多少水",
                "水囊还有",
                "现在几点",
                "第几天",
                "现在在哪",
                "我在哪",
                "当前位置",
                "不是已经",
                "已经到",
                "到过",
            ]
        )

    def _is_table_talk(self, text: str) -> bool:
        stripped = text.strip()
        if stripped in {"?", "？", "什么", "什么?", "什么？", "嗯?", "嗯？"}:
            return True
        return any(
            word in text
            for word in ["规则", "怎么操作", "怎么玩", "系统", "面板", "按钮", "ui", "什么意思", "解释一下", "这是什么意思"]
        )

    def _is_npc_dialogue_intent(self, text: str) -> bool:
        return any(phrase in text for phrase in ["你是什么", "你是谁", "你这里", "你们", "你知道", "你见过", "你能", "请问", "打听"])

    def _is_compound_observe_then_gather(self, text: str) -> bool:
        return any(word in text for word in ["观察", "查看", "检查"]) and any(
            word in text for word in ["如果没毒", "没毒", "安全", "能吃"]
        ) and self._is_gather(text)

    def _is_negated_sleep_seek_shelter(self, text: str) -> bool:
        negated_sleep = any(marker in text for marker in ["不是要睡", "不是睡觉", "不睡觉", "不是要入睡"])
        shelter = any(word in text for word in ["找", "寻找"]) and any(word in text for word in ["能睡", "过夜", "落脚", "庇护", "住处"])
        return negated_sleep and shelter

    def _is_sleep_intent(self, text: str) -> bool:
        if "找" in text and any(word in text for word in ["过夜", "落脚", "庇护", "住处", "睡觉的地方", "能睡"]):
            return False
        if any(word in text for word in ["睡觉", "睡到", "睡一觉", "入睡", "安心睡", "睡下", "躺下睡", "长休", "sleep"]):
            return True
        if any(word in text for word in ["等待天亮", "等待真正的天亮", "等到天亮"]):
            return True
        if any(word in text for word in ["闭眼", "闭上眼睛"]) and any(word in text for word in ["休息", "恢复精力", "放松身体", "天亮"]):
            return True
        if "过夜" in text:
            return any(word in text for word in ["在这里", "原地", "就在", "这里", "营地", "休息"])
        return False

    def _is_seek_shelter(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "找个可以过夜",
                "找一个可以过夜",
                "找地方过夜",
                "找个能睡",
                "找一个能睡",
                "寻找庇护",
                "找庇护",
                "找落脚",
                "寻找落脚",
                "找住处",
                "寻找住处",
                "找睡觉的地方",
                "找安全地方",
                "找安全的地方",
            ]
        )

    def _is_manage_inventory(self, text: str) -> bool:
        return any(word in text for word in ["扔掉", "丢掉", "丢弃", "放下", "收起", "整理", "拿出", "取出", "掏出", "放进背包", "放入背包"])

    def _is_drink_water(self, text: str) -> bool:
        return any(word in text for word in ["喝水", "喝一口", "饮水", "drink water"]) or ("喝" in text and "水" in text)

    def _is_eat_food(self, text: str) -> bool:
        return any(word in text for word in ["吃干粮", "吃饭", "吃掉", "吃一份", "食用", "eat food"]) or (
            "吃" in text and any(word in text for word in ["干粮", "食物", "粮"])
        )

    def _is_refill_water(self, text: str) -> bool:
        return any(word in text for word in ["装水", "取水", "补水", "灌满水囊", "把水囊装满"])

    def _is_enter_location(self, text: str) -> bool:
        return any(word in text for word in ["进入", "进到", "走进", "钻进", "回前厅", "回到前厅"])

    def _is_secure_shelter(self, text: str) -> bool:
        return any(word in text for word in ["堵门", "封门", "加固门", "把门堵上", "封堵入口"])

    def _is_negotiate(self, text: str) -> bool:
        return any(word in text for word in ["讨价还价", "讲价", "谈住宿", "打听价格", "询问价格", "问价格"])

    def _is_purchase(self, text: str) -> bool:
        return any(word in text for word in ["支付", "付钱", "付铜币", "买床位", "买住宿", "买炖菜", "购买"])

    def _is_repair(self, text: str) -> bool:
        return any(word in text for word in ["修锅把", "修好锅把", "修理", "维修", "修好"])

    def _is_eat_meal(self, text: str) -> bool:
        return any(word in text for word in ["吃已购买", "吃炖菜", "吃热食", "吃饭"]) or ("吃" in text and "炖菜" in text)

    def _is_approach(self, text: str) -> bool:
        return any(word in text for word in ["靠近", "接近", "凑近", "靠过去", "走近"])

    def _is_hide(self, text: str) -> bool:
        return any(word in text for word in ["躲起来", "藏起来", "隐藏", "躲进", "藏身"])

    def _is_avoid(self, text: str) -> bool:
        return any(word in text for word in ["躲避", "避开", "绕开", "规避"])

    def _is_force_open(self, text: str) -> bool:
        return any(word in text for word in ["撬开", "撬锁", "强行打开", "硬打开", "砸开", "撞开", "破开"])

    def _is_gather(self, text: str) -> bool:
        return any(word in text for word in ["摘", "采", "采摘", "捡", "拾起", "捡起", "拿起", "收集", "采集"])

    def _is_travel(self, text: str) -> bool:
        if any(marker in text for marker in ["?", "？", "吗"]):
            return False
        return any(word in text for word in ["前往", "赶路", "走到", "移动到", "去往", "探索", "前进", "沿着", "走", "travel", "move", "去", "到达", "进入", "出发", "上路", "继续"])
