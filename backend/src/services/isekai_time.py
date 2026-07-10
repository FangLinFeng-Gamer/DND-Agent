from __future__ import annotations

from dataclasses import dataclass
from typing import Any


START_MINUTES = 17 * 60
MINUTES_PER_DAY = 24 * 60
MORNING_MINUTES = 6 * 60


@dataclass(frozen=True)
class IsekaiActionResolution:
    action_type: str
    time_cost_minutes: int
    advances_time: bool
    survival_intent: str
    reason: str


class IsekaiTimeService:
    def classify_action(self, content: str, scene_context: dict[str, Any] | None = None) -> IsekaiActionResolution:
        from backend.src.services.isekai_action_parser import IsekaiActionParser

        return IsekaiActionParser(self).parse(content, scene_context=scene_context)

    def resolve_action_type(self, action_type: str) -> IsekaiActionResolution:
        actions = {
            "manage_inventory": IsekaiActionResolution("manage_inventory", 5, True, "inventory", "角色整理、取出或丢弃物品。"),
            "status_check": IsekaiActionResolution("status_check", 0, False, "none", "玩家查看状态，不推进时间。"),
            "table_talk": IsekaiActionResolution("table_talk", 0, False, "none", "玩家询问系统或规则，不推进时间。"),
            "clarification": IsekaiActionResolution("clarification", 0, False, "none", "输入目标存在歧义，需要玩家澄清。"),
            "condition_failed": IsekaiActionResolution("condition_failed", 0, False, "none", "当前行动缺少必要前置条件。"),
            "short_dialogue": IsekaiActionResolution("short_dialogue", 10, True, "social", "角色进行了简短对话。"),
            "seek_shelter": IsekaiActionResolution("seek_shelter", 45, True, "shelter", "角色寻找可过夜或避险的庇护点。"),
            "sleep": IsekaiActionResolution("sleep", 480, True, "sleep", "角色进行长时间睡眠。"),
            "rest_short": IsekaiActionResolution("rest_short", 60, True, "rest", "角色短暂休整。"),
            "eat_drink": IsekaiActionResolution("eat_drink", 15, True, "consume", "角色消耗食物或饮水。"),
            "drink_water": IsekaiActionResolution("drink_water", 5, True, "drink", "角色饮用随身饮水。"),
            "eat_food": IsekaiActionResolution("eat_food", 10, True, "eat", "角色食用随身干粮。"),
            "refill_water": IsekaiActionResolution("refill_water", 15, True, "refill", "角色从可用水源补充水囊。"),
            "cook": IsekaiActionResolution("cook", 60, True, "cook", "角色花时间准备食物。"),
            "gather": IsekaiActionResolution("gather", 30, True, "gather", "角色采集或拾取附近物品。"),
            "forage": IsekaiActionResolution("forage", 120, True, "forage", "角色搜寻食物或水源。"),
            "travel": IsekaiActionResolution("travel", 90, True, "travel", "角色移动到新的地点。"),
            "enter_location": IsekaiActionResolution("enter_location", 10, True, "move", "角色进入明确地点。"),
            "leave_location": IsekaiActionResolution("leave_location", 10, True, "move", "角色离开当前地点。"),
            "secure_shelter": IsekaiActionResolution("secure_shelter", 20, True, "shelter", "角色加固或封堵庇护点。"),
            "approach": IsekaiActionResolution("approach", 15, True, "position", "角色靠近明确目标。"),
            "hide": IsekaiActionResolution("hide", 10, True, "stealth", "角色隐藏身形以规避危险。"),
            "avoid": IsekaiActionResolution("avoid", 15, True, "stealth", "角色绕开或规避危险。"),
            "force_open": IsekaiActionResolution("force_open", 20, True, "force", "角色强行打开障碍物。"),
            "negotiate": IsekaiActionResolution("negotiate", 12, True, "social", "角色讨价还价或打听价格。"),
            "purchase": IsekaiActionResolution("purchase", 5, True, "trade", "角色支付货币购买物品或权益。"),
            "repair": IsekaiActionResolution("repair", 15, True, "repair", "角色进行简单修理。"),
            "eat_meal": IsekaiActionResolution("eat_meal", 20, True, "meal", "角色花时间吃热食。"),
            "search": IsekaiActionResolution("search", 45, True, "search", "角色仔细搜索附近区域。"),
            "observe": IsekaiActionResolution("observe", 15, True, "observe", "角色快速观察周围。"),
        }
        return actions.get(action_type, actions["table_talk"])

    def time_label(self, elapsed_minutes: int) -> str:
        minute = int(elapsed_minutes) % MINUTES_PER_DAY
        if 5 * 60 <= minute < 8 * 60:
            return "清晨"
        if 8 * 60 <= minute < 12 * 60:
            return "上午"
        if 12 * 60 <= minute < 14 * 60:
            return "正午"
        if 14 * 60 <= minute < 17 * 60:
            return "下午"
        if 17 * 60 <= minute < 18 * 60 + 30:
            return "黄昏"
        if 18 * 60 + 30 <= minute < 23 * 60:
            return "夜晚"
        return "深夜"

    def elapsed_minutes_from_survival(self, survival: dict[str, Any]) -> int:
        state = survival.get("state") or {}
        if isinstance(state, dict) and isinstance(state.get("elapsed_minutes"), int):
            return max(0, min(MINUTES_PER_DAY - 1, state["elapsed_minutes"]))
        label = str(survival.get("time_of_day") or "")
        return {
            "清晨": 5 * 60,
            "上午": 8 * 60,
            "正午": 12 * 60,
            "下午": 14 * 60,
            "黄昏": START_MINUTES,
            "夜晚": 19 * 60,
            "深夜": 23 * 60,
        }.get(label, START_MINUTES)

    def apply_time_and_survival(
        self,
        survival: dict[str, Any],
        action: IsekaiActionResolution,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        current = dict(survival)
        state = dict(current.get("state") or {})
        before_elapsed = self.elapsed_minutes_from_survival(current)
        before_day = int(current.get("day") or 1)
        minutes = self._time_cost_for_action(before_elapsed, action)
        total = before_elapsed + minutes
        day_delta, elapsed = divmod(total, MINUTES_PER_DAY)
        updated = {
            **current,
            "day": before_day + day_delta,
            "time_of_day": self.time_label(elapsed),
            "last_action_type": action.action_type,
        }
        state["elapsed_minutes"] = elapsed
        state["total_elapsed_minutes"] = (
            int(state.get("total_elapsed_minutes", (before_day - 1) * MINUTES_PER_DAY + before_elapsed)) + minutes
        )
        state["last_time_delta_minutes"] = minutes
        state["last_time_reason"] = action.survival_intent
        updated["state"] = state

        delta = self.survival_delta(current, action, minutes)
        for key in ["hunger", "thirst", "fatigue", "sleep_need", "temperature_risk", "morale"]:
            updated[key] = self._clamp(int(current.get(key, 0)) + int(delta.get(key, 0)))
        delta["time_cost_minutes"] = minutes
        delta["advances_time"] = action.advances_time
        delta["time_label"] = updated["time_of_day"]
        delta["visible_events"] = self.visible_events_for_time(before_day, before_elapsed, updated, action, minutes)
        return updated, delta

    def survival_delta(
        self,
        survival: dict[str, Any],
        action: IsekaiActionResolution,
        resolved_minutes: int | None = None,
    ) -> dict[str, Any]:
        minutes = self._time_cost_for_action(self.elapsed_minutes_from_survival(survival), action)
        if resolved_minutes is not None:
            minutes = resolved_minutes
        delta = {
            "hunger": int(minutes * 1 / 60),
            "thirst": int(minutes * 2 / 60),
            "fatigue": int(minutes * 1 / 60),
            "sleep_need": int(minutes * 1 / 60),
            "temperature_risk": 0,
            "morale": 0,
        }
        extras = {
            "observe": {"fatigue": 1},
            "search": {"fatigue": 2},
            "travel": {"fatigue": 3, "thirst": 1},
            "forage": {"fatigue": 4, "thirst": 1},
            "gather": {"fatigue": 2, "thirst": 1},
            "seek_shelter": {"fatigue": 1, "morale": 1},
            "manage_inventory": {"fatigue": 0},
            "cook": {"fatigue": 1, "hunger": -2},
            "eat_drink": {"hunger": -8, "thirst": -12},
            "drink_water": {"thirst": -12},
            "eat_food": {"hunger": -8},
            "refill_water": {"fatigue": 1},
            "rest_short": {"fatigue": -8, "sleep_need": -2},
            "sleep": {"fatigue": -25, "sleep_need": -35, "morale": 3},
            "enter_location": {"fatigue": 1},
            "leave_location": {"fatigue": 1},
            "secure_shelter": {"fatigue": 2, "morale": 1},
            "approach": {"fatigue": 1},
            "hide": {"fatigue": 1, "morale": -1},
            "avoid": {"fatigue": 2},
            "force_open": {"fatigue": 3, "thirst": 1},
            "negotiate": {"fatigue": 1},
            "purchase": {},
            "repair": {"fatigue": 2, "thirst": 1, "morale": 1},
            "eat_meal": {"hunger": -10, "fatigue": -1, "morale": 2},
        }
        for key, value in extras.get(action.action_type, {}).items():
            delta[key] = delta.get(key, 0) + value
        if action.advances_time and self.time_label(self.elapsed_minutes_from_survival(survival)) in {"夜晚", "深夜"} and action.action_type not in {"rest_short", "sleep"}:
            delta["fatigue"] += 2
            delta["sleep_need"] += 1
        if int(survival.get("temperature_risk", 0)) >= 60 and action.advances_time:
            delta["thirst"] += max(1, int(minutes / 120))
        return delta

    def visible_events_for_time(
        self,
        before_day: int,
        before_elapsed: int,
        updated: dict[str, Any],
        action: IsekaiActionResolution,
        resolved_minutes: int | None = None,
    ) -> list[str]:
        events: list[str] = []
        minutes = resolved_minutes if resolved_minutes is not None else self._time_cost_for_action(before_elapsed, action)
        if minutes > 0:
            events.append(f"时间推进了约 {self.format_minutes(minutes)}。")
        before_label = self.time_label(before_elapsed)
        after_label = str(updated.get("time_of_day") or "")
        if int(updated.get("day", before_day)) > before_day:
            events.append(f"时间进入第 {updated['day']} 天{after_label}。")
        elif before_label != after_label:
            events.append(f"天色变化为{after_label}。")
        return events

    def format_minutes(self, minutes: int) -> str:
        if minutes >= 60 and minutes % 60 == 0:
            return f"{minutes // 60} 小时"
        if minutes >= 60:
            return f"{minutes // 60} 小时 {minutes % 60} 分钟"
        return f"{minutes} 分钟"

    def _time_cost_for_action(self, before_elapsed: int, action: IsekaiActionResolution) -> int:
        if not action.advances_time:
            return 0
        if action.action_type != "sleep":
            return action.time_cost_minutes
        minutes_to_morning = (MINUTES_PER_DAY - before_elapsed + MORNING_MINUTES) % MINUTES_PER_DAY
        if minutes_to_morning == 0:
            minutes_to_morning = MINUTES_PER_DAY
        return max(action.time_cost_minutes, minutes_to_morning)

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
            for word in [
                "规则",
                "怎么操作",
                "怎么玩",
                "系统",
                "面板",
                "按钮",
                "ui",
                "什么意思",
                "解释一下",
                "这是什么意思",
            ]
        )

    def _is_npc_dialogue_intent(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "你是什么",
                "你是谁",
                "你这里",
                "你们",
                "你知道",
                "你见过",
                "你能",
                "请问",
                "打听",
            ]
        )

    def _is_sleep_intent(self, text: str) -> bool:
        if "找" in text and any(word in text for word in ["过夜", "落脚", "庇护", "住处", "睡觉的地方"]):
            return False
        if any(
            word in text
            for word in [
                "睡觉",
                "睡到",
                "睡一觉",
                "入睡",
                "安心睡",
                "睡下",
                "躺下睡",
                "长休",
                "sleep",
            ]
        ):
            return True
        if any(word in text for word in ["等待天亮", "等待真正的天亮", "等到天亮"]):
            return True
        if any(word in text for word in ["闭眼", "闭上眼睛"]) and any(
            word in text for word in ["休息", "恢复精力", "放松身体", "天亮"]
        ):
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
        return any(
            word in text
            for word in [
                "扔掉",
                "丢掉",
                "丢弃",
                "放下",
                "收起",
                "整理",
                "拿出",
                "取出",
                "掏出",
                "放进背包",
                "放入背包",
            ]
        )

    def _is_gather(self, text: str) -> bool:
        return any(
            word in text
            for word in [
                "摘",
                "采",
                "采摘",
                "捡",
                "拾起",
                "捡起",
                "拿起",
                "收集",
                "采集",
            ]
        )

    def _is_travel_intent(self, text: str) -> bool:
        if any(marker in text for marker in ["?", "？", "吗"]):
            return False
        return any(word in text for word in ["去", "到达", "进入", "出发", "上路", "继续"])

    def _clamp(self, value: int) -> int:
        return max(0, min(100, value))
