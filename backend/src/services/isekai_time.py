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
    def classify_action(self, content: str) -> IsekaiActionResolution:
        text = str(content or "").strip().lower()
        if self._is_status_check(text):
            return IsekaiActionResolution("status_check", 0, False, "none", "玩家查看状态，不推进时间。")
        if self._is_table_talk(text):
            return IsekaiActionResolution("table_talk", 0, False, "none", "玩家询问系统或规则，不推进时间。")
        if any(word in text for word in ["睡觉", "睡到", "过夜", "长休", "sleep"]):
            return IsekaiActionResolution("sleep", 480, True, "sleep", "角色进行长时间睡眠。")
        if any(word in text for word in ["短休", "小憩", "休息", "rest"]):
            return IsekaiActionResolution("rest_short", 60, True, "rest", "角色短暂休整。")
        if any(word in text for word in ["吃干粮", "吃饭", "吃掉", "喝水", "喝一口", "饮水", "eat", "drink"]):
            return IsekaiActionResolution("eat_drink", 15, True, "consume", "角色消耗食物或饮水。")
        if any(word in text for word in ["做汤", "做饭", "做菜", "做一锅", "热汤", "烹饪", "料理", "煮", "cook"]):
            return IsekaiActionResolution("cook", 60, True, "cook", "角色花时间准备食物。")
        if any(word in text for word in ["寻找食物", "寻找水", "找水", "觅食", "采集", "打猎", "forage"]):
            return IsekaiActionResolution("forage", 120, True, "forage", "角色搜寻食物或水源。")
        if any(
            word in text
            for word in ["前往", "赶路", "走到", "移动到", "去往", "探索", "前进", "沿着", "走", "travel", "move"]
        ):
            return IsekaiActionResolution("travel", 90, True, "travel", "角色移动到新的地点。")
        if self._is_travel_intent(text):
            return IsekaiActionResolution("travel", 90, True, "travel", "角色移动到新的地点。")
        if any(word in text for word in ["搜索", "搜寻", "调查", "仔细找", "寻找", "search"]):
            return IsekaiActionResolution("search", 45, True, "search", "角色仔细搜索附近区域。")
        if any(word in text for word in ["观察", "查看", "聆听", "听", "inspect", "look"]):
            return IsekaiActionResolution("observe", 15, True, "observe", "角色快速观察周围。")
        if any(word in text for word in ["交谈", "询问", "问", "说", "talk"]):
            return IsekaiActionResolution("short_dialogue", 10, True, "social", "角色进行了简短对话。")
        return IsekaiActionResolution("short_dialogue", 10, True, "social", "角色进行了简短行动。")

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
            "cook": {"fatigue": 1, "hunger": -2},
            "eat_drink": {"hunger": -8, "thirst": -12},
            "rest_short": {"fatigue": -8, "sleep_need": -2},
            "sleep": {"fatigue": -25, "sleep_need": -35, "morale": 3},
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
                "属性",
                "生命值",
                "hp",
                "现在几点",
                "第几天",
                "现在在哪",
                "当前位置",
                "不是已经",
                "已经到",
                "到过",
            ]
        )

    def _is_table_talk(self, text: str) -> bool:
        return any(word in text for word in ["规则", "怎么操作", "怎么玩", "系统", "面板", "按钮", "ui"])

    def _is_travel_intent(self, text: str) -> bool:
        if any(marker in text for marker in ["?", "？", "吗"]):
            return False
        return any(word in text for word in ["去", "到达", "进入", "出发", "上路", "继续"])

    def _clamp(self, value: int) -> int:
        return max(0, min(100, value))
