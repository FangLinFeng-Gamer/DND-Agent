# Isekai Time System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an adventure-local, action-duration-driven time system to isekai survival mode so survival pressure, world events, narration, and UI reflect real time passing.

**Architecture:** Put deterministic time classification, clock math, and survival-pressure math in a focused `IsekaiTimeService`. `IsekaiSurvivalService` will call that service during turn preparation, persist updated clock/survival fields through the existing `isekai_survival_states` table, and pass the resolved time facts to the event director and DM prompt. The frontend will keep using the existing adventure payload and render new compact time fields from `survival_state`.

**Tech Stack:** Python 3.12, FastAPI service layer, SQLite JSON state column, pytest, browser/static frontend JavaScript, Node `--test`/`--check`.

---

## File Map

- Create `backend/src/services/isekai_time.py`
  - Owns action classification, clock normalization, time labels, day rollover, and time-based survival deltas.
- Create `test/backend/src/services/test_isekai_time.py`
  - Unit tests for classification, clock labels, rollover, and survival delta math.
- Modify `backend/src/services/isekai.py`
  - Calls `IsekaiTimeService`, persists `day`, `time_of_day`, `state_json`, and time-aware survival values.
  - Adds time/action facts to turn dict, DM metadata, fallback narration, and active-model prompt payload.
- Modify `backend/src/services/isekai_events.py`
  - Skips random/background event generation when a turn does not advance time.
  - Can still use direct player-triggered events for time-advancing actions.
- Modify `test/backend/src/services/test_isekai_survival.py`
  - Integration tests for adventure-local time, no-time status checks, sleep rollover, and distinct eat/drink behavior.
- Modify `test/backend/src/services/test_isekai_events.py`
  - Regression test that table/status checks do not generate random world events.
- Modify `frontend/static/js/game.js`
  - Shows day, time of day, last action time cost, shelter, and existing survival stats in the isekai survival panel.
- Modify `frontend/static/js/locales/en.js` and `frontend/static/js/locales/zh-CN.js`
  - Adds compact labels for last time cost and shelter.
- Modify `test/frontend/static/js/test_frontend_isekai_mode.py`
  - Static test that the isekai survival panel renders time-related values.

---

### Task 1: Add Deterministic Isekai Time Rules

**Files:**
- Create: `backend/src/services/isekai_time.py`
- Create: `test/backend/src/services/test_isekai_time.py`

- [ ] **Step 1: Write failing unit tests for action classification and clock labels**

Add `test/backend/src/services/test_isekai_time.py`:

```python
from backend.src.services.isekai_time import IsekaiTimeService


def test_status_question_does_not_advance_time():
    service = IsekaiTimeService()

    action = service.classify_action("我现在的状态怎么样？")

    assert action.action_type == "status_check"
    assert action.advances_time is False
    assert action.time_cost_minutes == 0


def test_cooking_is_time_advancing_action():
    service = IsekaiTimeService()

    action = service.classify_action("我给路边营地的人做一锅热汤。")

    assert action.action_type == "cook"
    assert action.advances_time is True
    assert action.time_cost_minutes == 60
    assert action.survival_intent == "cook"


def test_time_label_for_minutes():
    service = IsekaiTimeService()

    assert service.time_label(5 * 60) == "清晨"
    assert service.time_label(12 * 60) == "正午"
    assert service.time_label(17 * 60) == "黄昏"
    assert service.time_label(22 * 60) == "夜晚"
    assert service.time_label(23 * 60) == "深夜"
    assert service.time_label(3 * 60) == "深夜"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_time.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.src.services.isekai_time'`.

- [ ] **Step 3: Implement the minimal time service**

Create `backend/src/services/isekai_time.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


START_MINUTES = 17 * 60
MINUTES_PER_DAY = 24 * 60


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
        if any(word in text for word in ["做汤", "做饭", "烹饪", "料理", "煮", "cook"]):
            return IsekaiActionResolution("cook", 60, True, "cook", "角色花时间准备食物。")
        if any(word in text for word in ["寻找食物", "寻找水", "找水", "觅食", "采集", "打猎", "forage"]):
            return IsekaiActionResolution("forage", 120, True, "forage", "角色搜寻食物或水源。")
        if any(word in text for word in ["前往", "赶路", "走到", "移动到", "去往", "travel", "move"]):
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
        if 17 * 60 <= minute < 19 * 60:
            return "黄昏"
        if 19 * 60 <= minute < 23 * 60:
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

    def _is_status_check(self, text: str) -> bool:
        return any(word in text for word in ["我的状态", "当前状态", "生存状态", "背包", "库存", "属性", "生命值", "hp", "现在几点", "第几天"])

    def _is_table_talk(self, text: str) -> bool:
        return any(word in text for word in ["规则", "怎么操作", "怎么玩", "系统", "面板", "按钮", "ui"])
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_time.py
```

Expected: PASS.

- [ ] **Step 5: Add clock rollover and survival delta tests**

Append to `test/backend/src/services/test_isekai_time.py`:

```python
def test_advance_clock_rolls_into_next_day():
    service = IsekaiTimeService()
    survival = {"day": 1, "time_of_day": "夜晚", "state": {"elapsed_minutes": 22 * 60}}
    action = service.classify_action("我睡觉过夜。")

    updated, delta = service.apply_time_and_survival(survival, action)

    assert updated["day"] == 2
    assert updated["time_of_day"] == "清晨"
    assert updated["state"]["elapsed_minutes"] == 6 * 60
    assert updated["state"]["last_time_delta_minutes"] == 480
    assert delta["time_cost_minutes"] == 480


def test_eat_drink_reduces_hunger_and_thirst():
    service = IsekaiTimeService()
    survival = {
        "day": 1,
        "time_of_day": "黄昏",
        "hunger": 30,
        "thirst": 35,
        "fatigue": 15,
        "sleep_need": 20,
        "temperature_risk": 10,
        "morale": 70,
        "shelter": "none",
        "state": {"elapsed_minutes": 17 * 60},
    }
    action = service.classify_action("我吃干粮并喝水。")

    updated, delta = service.apply_time_and_survival(survival, action)

    assert updated["hunger"] < survival["hunger"]
    assert updated["thirst"] < survival["thirst"]
    assert updated["time_of_day"] == "黄昏"
    assert delta["hunger"] < 0
    assert delta["thirst"] < 0
```

- [ ] **Step 6: Run tests to verify RED**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_time.py::test_advance_clock_rolls_into_next_day test/backend/src/services/test_isekai_time.py::test_eat_drink_reduces_hunger_and_thirst
```

Expected: FAIL with `AttributeError: 'IsekaiTimeService' object has no attribute 'apply_time_and_survival'`.

- [ ] **Step 7: Implement clock rollover and survival math**

Add these methods to `IsekaiTimeService` in `backend/src/services/isekai_time.py`:

```python
    def apply_time_and_survival(
        self,
        survival: dict[str, Any],
        action: IsekaiActionResolution,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        current = dict(survival)
        state = dict(current.get("state") or {})
        minutes = action.time_cost_minutes if action.advances_time else 0
        before_elapsed = self.elapsed_minutes_from_survival(current)
        before_day = int(current.get("day") or 1)
        total = before_elapsed + minutes
        day_delta, elapsed = divmod(total, MINUTES_PER_DAY)
        updated = {
            **current,
            "day": before_day + day_delta,
            "time_of_day": self.time_label(elapsed),
            "last_action_type": action.action_type,
        }
        state["elapsed_minutes"] = elapsed
        state["total_elapsed_minutes"] = int(state.get("total_elapsed_minutes", before_elapsed)) + minutes
        state["last_time_delta_minutes"] = minutes
        state["last_time_reason"] = action.survival_intent
        updated["state"] = state

        delta = self.survival_delta(current, action)
        for key in ["hunger", "thirst", "fatigue", "sleep_need", "temperature_risk", "morale"]:
            updated[key] = self._clamp(int(current.get(key, 0)) + int(delta.get(key, 0)))
        delta["time_cost_minutes"] = minutes
        delta["advances_time"] = action.advances_time
        delta["time_label"] = updated["time_of_day"]
        delta["visible_events"] = self.visible_events_for_time(before_day, before_elapsed, updated, action)
        return updated, delta

    def survival_delta(self, survival: dict[str, Any], action: IsekaiActionResolution) -> dict[str, Any]:
        minutes = action.time_cost_minutes if action.advances_time else 0
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
    ) -> list[str]:
        events: list[str] = []
        minutes = action.time_cost_minutes if action.advances_time else 0
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

    def _clamp(self, value: int) -> int:
        return max(0, min(100, value))
```

- [ ] **Step 8: Run all time service tests**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_time.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
git add backend/src/services/isekai_time.py test/backend/src/services/test_isekai_time.py
git commit -m "Add isekai time rules"
```

---

### Task 2: Integrate Time Into Isekai Survival Turns

**Files:**
- Modify: `backend/src/services/isekai.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing integration tests**

Append to `test/backend/src/services/test_isekai_survival.py`:

```python
def test_isekai_status_question_does_not_advance_time_or_pressure(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Status", mode="isekai_survival"))
    before = adventure.survival_state

    response = service.advance(adventure.id, MessageCreate(content="我现在的状态怎么样？", locale="zh-CN"))

    after = response.adventure.survival_state
    assert after["day"] == before["day"]
    assert after["time_of_day"] == before["time_of_day"]
    assert after["hunger"] == before["hunger"]
    assert after["thirst"] == before["thirst"]
    assert after["fatigue"] == before["fatigue"]
    assert after["sleep_need"] == before["sleep_need"]
    assert after["state"]["last_time_delta_minutes"] == 0
    assert response.dm_message.metadata["time"]["advances_time"] is False


def test_isekai_exploration_advances_time_and_pressure(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Road", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我前往远处火光所在的营地。", locale="zh-CN"))

    survival = response.adventure.survival_state
    assert survival["state"]["last_time_delta_minutes"] == 90
    assert survival["time_of_day"] == "夜晚"
    assert survival["thirst"] > adventure.survival_state["thirst"]
    assert survival["fatigue"] > adventure.survival_state["fatigue"]
    assert "时间推进了约" in response.dm_message.content


def test_isekai_sleep_rolls_to_next_day(store):
    service = IsekaiSurvivalService(store)
    adventure = service.create_adventure(AdventureCreate(title="Clock Sleep", mode="isekai_survival"))

    response = service.advance(adventure.id, MessageCreate(content="我睡觉过夜。", locale="zh-CN"))

    survival = response.adventure.survival_state
    assert survival["day"] == 2
    assert survival["time_of_day"] == "清晨"
    assert survival["fatigue"] < adventure.survival_state["fatigue"]
    assert survival["sleep_need"] < adventure.survival_state["sleep_need"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py::test_isekai_status_question_does_not_advance_time_or_pressure test/backend/src/services/test_isekai_survival.py::test_isekai_exploration_advances_time_and_pressure test/backend/src/services/test_isekai_survival.py::test_isekai_sleep_rolls_to_next_day
```

Expected: FAIL because `state.last_time_delta_minutes` is missing and `time_of_day` does not advance.

- [ ] **Step 3: Wire `IsekaiTimeService` into `IsekaiSurvivalService`**

Modify imports and constructor in `backend/src/services/isekai.py`:

```python
from backend.src.services.isekai_time import IsekaiActionResolution, IsekaiTimeService
```

```python
        self.time = IsekaiTimeService()
```

Replace the action/delta section of `prepare_turn` with:

```python
        action = self.time.classify_action(message.content)
        delta, survival = self.apply_delta(adventure_id, action)
        scene = self.adventures.get_scene(adventure_id)
        character = self.get_character(adventure_id)
        fallback = self.narrate(message.content, scene, character, survival, delta)
        turn = {
            "player_input": message.content,
            "player_message": player_message,
            "action_type": action.action_type,
            "action": action,
            "time": {
                "time_cost_minutes": action.time_cost_minutes,
                "advances_time": action.advances_time,
                "survival_intent": action.survival_intent,
                "reason": action.reason,
            },
            "delta": delta,
            "survival": survival,
            "scene": scene,
            "character": character,
            "fallback": fallback,
        }
```

Replace old `survival_delta_for_action` and `apply_delta` methods with:

```python
    def apply_delta(self, adventure_id: int, action: IsekaiActionResolution) -> tuple[dict[str, Any], dict[str, Any]]:
        current = self.adventures.get(adventure_id, include_messages=False).survival_state or {}
        updated, delta = self.time.apply_time_and_survival(current, action)
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE isekai_survival_states
                SET day = :day, time_of_day = :time_of_day,
                    hunger = :hunger, thirst = :thirst, fatigue = :fatigue, sleep_need = :sleep_need,
                    temperature_risk = :temperature_risk, morale = :morale,
                    weather = :weather, location = :location, shelter = :shelter,
                    last_action_type = :last_action_type, state_json = :state_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE adventure_id = :adventure_id
                """,
                {
                    **updated,
                    "adventure_id": adventure_id,
                    "state_json": encode_json(updated.get("state") or {}),
                },
            )
        return delta, updated
```

Update `advance` and `advance_stream` DM metadata to include time:

```python
{"mode": "isekai_survival", "survival_delta": turn["delta"], "time": turn["time"], "source": source}
```

- [ ] **Step 4: Update narration to mention time events**

Modify `narrate` in `backend/src/services/isekai.py`:

```python
        event_text = " ".join(delta.get("visible_events") or [])
        return (
            f"{name}继续在{scene.location}行动：{player_input}"
            f"{event_text} 当前是第 {survival['day']} 天{survival['time_of_day']}。"
            f" 当前饥饿 {survival['hunger']}，口渴 {survival['thirst']}，"
            f"疲劳 {survival['fatigue']}，睡眠需求 {survival['sleep_need']}。"
        )
```

- [ ] **Step 5: Update model prompt payload**

In `build_model_messages`, add `time` to `system_state`:

```python
                "time": turn.get("time", {}),
                "day": turn["survival"].get("day"),
                "time_of_day": turn["survival"].get("time_of_day"),
                "survival_state_json": turn["survival"].get("state", {}),
```

Update the system prompt sentence:

```python
                    "后端已经结算时间、饥饿、口渴、疲劳、睡眠需求等数值，你不能修改这些数值。"
```

- [ ] **Step 6: Run integration tests**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py
```

Expected: PASS.

- [ ] **Step 7: Run isekai backend suite**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_time.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_preferences.py test/backend/src/api/test_isekai_mode.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add backend/src/services/isekai.py test/backend/src/services/test_isekai_survival.py
git commit -m "Apply time to isekai survival turns"
```

---

### Task 3: Gate Isekai World Events By Effective Time Actions

**Files:**
- Modify: `backend/src/services/isekai_events.py`
- Modify: `test/backend/src/services/test_isekai_events.py`
- Modify: `test/backend/src/services/test_isekai_survival.py`

- [ ] **Step 1: Write failing event director test**

Append to `test/backend/src/services/test_isekai_events.py`:

```python
def test_table_talk_does_not_generate_random_world_event(store):
    adventure = create_isekai_adventure(store)
    director = IsekaiWorldEventDirector(store)
    turn = {
        "player_input": "我现在的状态怎么样？",
        "action_type": "status_check",
        "time": {"advances_time": False, "time_cost_minutes": 0},
        "scene": adventure.current_scene,
        "character": adventure.isekai_character,
        "survival": adventure.survival_state,
        "delta": {"visible_events": []},
    }

    events = director.evaluate_turn(
        adventure.id,
        turn,
        {
            "turn_count": 3,
            "player_preferences": {},
            "force_event_scope": "local",
        },
    )

    assert events == []
    assert WorldEventService(store).list_known_for_adventure(adventure.id) == []
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_events.py::test_table_talk_does_not_generate_random_world_event
```

Expected: FAIL because forced local event currently generates despite `advances_time: False`.

- [ ] **Step 3: Add time gate in event director**

At the start of `IsekaiWorldEventDirector.evaluate_turn` in `backend/src/services/isekai_events.py`, add:

```python
        time_context = turn.get("time") or {}
        if time_context.get("advances_time") is False:
            return []
```

This keeps status/table turns from producing random or preference-weighted events.

- [ ] **Step 4: Add survival integration assertion**

In `test/backend/src/services/test_isekai_survival.py`, extend `test_isekai_status_question_does_not_advance_time_or_pressure`:

```python
    assert response.adventure.world_events == []
```

- [ ] **Step 5: Run event and survival tests**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_survival.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/src/services/isekai_events.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_survival.py
git commit -m "Gate isekai events by time actions"
```

---

### Task 4: Render Time Fields In Isekai Survival Panel

**Files:**
- Modify: `frontend/static/js/game.js`
- Modify: `frontend/static/js/locales/en.js`
- Modify: `frontend/static/js/locales/zh-CN.js`
- Modify: `test/frontend/static/js/test_frontend_isekai_mode.py`

- [ ] **Step 1: Write failing frontend static test**

Append to `test/frontend/static/js/test_frontend_isekai_mode.py`:

```python
def test_isekai_survival_panel_renders_time_fields():
    game_js = (FRONTEND_DIR / "js/game.js").read_text(encoding="utf-8")
    i18n = (FRONTEND_DIR / "js/locales/en.js").read_text(encoding="utf-8") + (
        FRONTEND_DIR / "js/locales/zh-CN.js"
    ).read_text(encoding="utf-8")

    survival_block = game_js.split("function renderIsekaiSurvival", 1)[1].split("function", 1)[0]
    assert "survival.day" in survival_block
    assert "survival.time_of_day" in survival_block
    assert "last_time_delta_minutes" in survival_block
    assert "survival.shelter" in survival_block
    assert '"lastTimeCost"' in i18n
    assert '"shelter"' in i18n
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py::test_isekai_survival_panel_renders_time_fields
```

Expected: FAIL because `renderIsekaiSurvival` does not include these fields yet.

- [ ] **Step 3: Add locale labels**

In `frontend/static/js/locales/zh-CN.js`, add near the isekai survival labels:

```javascript
  "lastTimeCost": "上次耗时",
  "noTimeCost": "未推进时间",
  "minutesShort": "{minutes} 分钟",
  "hoursShort": "{hours} 小时",
  "shelter": "庇护所",
  "shelter.none": "无",
```

In `frontend/static/js/locales/en.js`, add:

```javascript
  "lastTimeCost": "Last Time Cost",
  "noTimeCost": "No time advanced",
  "minutesShort": "{minutes} min",
  "hoursShort": "{hours} hr",
  "shelter": "Shelter",
  "shelter.none": "None",
```

- [ ] **Step 4: Render time fields**

In `frontend/static/js/game.js`, add helper near `renderIsekaiSurvival`:

```javascript
function formatIsekaiTimeCost(minutes) {
  const value = Number(minutes || 0);
  if (!value) {
    return t("noTimeCost");
  }
  if (value >= 60 && value % 60 === 0) {
    return t("hoursShort", { hours: value / 60 });
  }
  return t("minutesShort", { minutes: value });
}

function localizeShelter(value) {
  const key = `shelter.${value || "none"}`;
  const localized = t(key);
  return localized === key ? String(value || t("notSet")) : localized;
}
```

Update `renderIsekaiSurvival` rows:

```javascript
  const stateData = survival?.state || {};
  renderIsekaiPanel(els.isekaiSurvivalPanel, t("isekaiSurvivalState"), survival ? [
    [t("isekaiDay", { day: survival.day || 1 }), survival.time_of_day || t("notSet")],
    [t("lastTimeCost"), formatIsekaiTimeCost(stateData.last_time_delta_minutes)],
    [t("hunger"), survival.hunger],
    [t("thirst"), survival.thirst],
    [t("fatigue"), survival.fatigue],
    [t("sleepNeed"), survival.sleep_need],
    [t("morale"), survival.morale],
    [t("weather"), survival.weather],
    [t("shelter"), localizeShelter(survival.shelter)],
  ] : []);
```

- [ ] **Step 5: Run frontend tests and syntax checks**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py
find frontend/static -name '*.js' -print0 | xargs -0 -n1 node --check
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/static/js/game.js frontend/static/js/locales/en.js frontend/static/js/locales/zh-CN.js test/frontend/static/js/test_frontend_isekai_mode.py
git commit -m "Show isekai time in survival panel"
```

---

### Task 5: End-To-End Verification And Manual Browser Check

**Files:**
- Modify only if previous tasks reveal a narrow bug.

- [ ] **Step 1: Run focused backend suite**

Run:

```bash
uv run pytest test/backend/src/services/test_isekai_time.py test/backend/src/services/test_isekai_survival.py test/backend/src/services/test_isekai_events.py test/backend/src/services/test_isekai_preferences.py test/backend/src/api/test_isekai_mode.py
```

Expected: PASS.

- [ ] **Step 2: Run focused frontend checks**

Run:

```bash
uv run pytest test/frontend/static/js/test_frontend_isekai_mode.py test/frontend/static/js/test_frontend_modularization.py
node --test test/frontend/isekai_world_events.test.mjs
find frontend/static -name '*.js' -print0 | xargs -0 -n1 node --check
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: `517 passed` or higher if new tests increase the count. The existing `StarletteDeprecationWarning` may remain.

- [ ] **Step 4: Restart local service on port 5002**

If a previous uvicorn session is running, stop it with Ctrl-C. Then run:

```bash
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 5002
```

Expected: Uvicorn reports `Uvicorn running on http://127.0.0.1:5002`.

- [ ] **Step 5: Browser manual check**

Open:

```text
http://127.0.0.1:5002/game/30
```

Check these flows:

- Send `我现在的状态怎么样？`
  - Expected: day/time and hunger/thirst/fatigue/sleep need do not change.
  - Expected: survival panel says last time cost is no time advanced.
- Send `我前往远处火光所在的营地。`
  - Expected: time moves from `黄昏` to `夜晚`.
  - Expected: thirst/fatigue increase.
  - Expected: DM narration mentions the elapsed time or time label.
- Send `我睡觉过夜。`
  - Expected: day increments to the next day.
  - Expected: time label becomes `清晨`.
  - Expected: fatigue and sleep need decrease.

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short
```

Expected: no uncommitted source/test changes, except deliberately generated local database changes outside git tracking.

---

## Self-Review Checklist

- Spec coverage:
  - Adventure-local clock: Task 1 and Task 2.
  - Effective actions only: Task 1, Task 2, Task 3.
  - Time-based survival pressure: Task 1 and Task 2.
  - Eating/drinking distinct from foraging: Task 1 and Task 2.
  - Environment modifiers: Task 1 includes night and temperature modifiers for first version.
  - World event integration: Task 3.
  - DM role boundaries and prompt truth: Task 2.
  - Frontend display: Task 4.
  - Testing and browser verification: Task 5.
- Open item scan:
  - No unresolved open items are intentionally left in this plan.
- Type consistency:
  - `IsekaiActionResolution`, `IsekaiTimeService.classify_action`, and `IsekaiTimeService.apply_time_and_survival` are introduced in Task 1 and used consistently in later tasks.
