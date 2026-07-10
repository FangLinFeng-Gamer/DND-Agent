from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.src.schemas.story import StoryOut


DEFAULT_PHASES = [
    {"value": 0, "phase": "festival_evening", "phase_label": "节庆黄昏", "severity": "calm"},
    {"value": 1, "phase": "uneasy_omens", "phase_label": "异兆初现", "severity": "uneasy"},
    {"value": 2, "phase": "public_fear", "phase_label": "公众恐慌", "severity": "warning"},
    {"value": 3, "phase": "festival_panic", "phase_label": "节庆混乱", "severity": "danger"},
    {"value": 4, "phase": "curse_spreads", "phase_label": "诅咒扩散", "severity": "danger"},
    {"value": 5, "phase": "seal_breaking", "phase_label": "封印将破", "severity": "critical"},
    {"value": 6, "phase": "breach", "phase_label": "危机爆发", "severity": "critical"},
]


def initial_world_state_for_story(story: StoryOut | None) -> dict[str, Any]:
    if story and story.id == "mistbell_tower":
        return _mistbell_initial_state()
    return {
        "turn_count": 0,
        "phase": "open_play",
        "phase_label": "自由探索",
        "threat_clocks": [],
        "pressure_clocks": [],
        "npc_states": {},
        "location_states": {},
        "visible_events": [],
        "hidden_events": [],
        "last_advance": {
            "advanced": False,
            "reason": "adventure_start",
            "time_cost": 0,
            "affected_clocks": [],
        },
    }


def _mistbell_initial_state() -> dict[str, Any]:
    return {
        "turn_count": 0,
        "phase": "festival_evening",
        "phase_label": "节庆黄昏",
        "threat_clocks": [
            {
                "id": "moonwell_curse",
                "label": "月井危机",
                "value": 0,
                "max": 6,
                "visible": True,
                "severity": "calm",
            }
        ],
        "pressure_clocks": [
            {
                "id": "village_suspicion",
                "label": "村民怀疑",
                "value": 0,
                "max": 4,
                "visible": True,
                "severity": "low",
            },
            {
                "id": "guard_alert",
                "label": "巡逻警觉",
                "value": 0,
                "max": 4,
                "visible": False,
                "severity": "low",
            },
        ],
        "npc_states": {
            "村长玛拉": {
                "location": "月井旁",
                "attitude": "anxious",
                "agenda": "维持秩序并找回银铃",
            },
            "守夜人布伦": {
                "location": "月井旁",
                "attitude": "alert",
                "agenda": "巡查湿泥脚印和村外道路",
            },
        },
        "location_states": {
            "柳溪村广场": {
                "mood": "uneasy_festival",
                "details": ["灯笼仍亮着", "村民压低声音议论月井"],
            }
        },
        "visible_events": [],
        "hidden_events": [],
        "last_advance": {
            "advanced": False,
            "reason": "adventure_start",
            "time_cost": 0,
            "affected_clocks": [],
        },
    }


def normalize_world_state(state: dict[str, Any] | None, story: StoryOut | None = None) -> dict[str, Any]:
    if not state:
        return initial_world_state_for_story(story)
    normalized = deepcopy(state)
    normalized.setdefault("turn_count", 0)
    normalized.setdefault("phase", "open_play")
    normalized.setdefault("phase_label", "自由探索")
    normalized.setdefault("threat_clocks", [])
    normalized.setdefault("pressure_clocks", [])
    normalized.setdefault("npc_states", {})
    normalized.setdefault("location_states", {})
    normalized.setdefault("location_history", [])
    normalized.setdefault("event_impacts", [])
    normalized.setdefault("visible_events", [])
    normalized.setdefault("hidden_events", [])
    normalized.setdefault(
        "last_advance",
        {
            "advanced": False,
            "reason": "loaded_existing_state",
            "time_cost": 0,
            "affected_clocks": [],
        },
    )
    return normalized


def public_world_state_view(world_state: dict[str, Any]) -> dict[str, Any]:
    state = normalize_world_state(world_state)
    return {
        "turn_count": state.get("turn_count", 0),
        "phase": state.get("phase"),
        "phase_label": state.get("phase_label"),
        "threat_clocks": [clock for clock in state.get("threat_clocks", []) if clock.get("visible", True)],
        "pressure_clocks": [clock for clock in state.get("pressure_clocks", []) if clock.get("visible", False)],
        "visible_events": list(state.get("visible_events", []))[-3:],
        "location_states": state.get("location_states", {}),
        "confirmed_location": state.get("confirmed_location"),
        "location_history": list(state.get("location_history", []))[-20:],
        "event_impacts": list(state.get("event_impacts", []))[-12:],
        "last_advance": state.get("last_advance", {}),
        "last_pressure_advance": state.get("last_pressure_advance", {}),
        "isekai_economy": state.get("isekai_economy", {}),
        "isekai_quest": state.get("isekai_quest", {}),
        "isekai_clues": list(state.get("isekai_clues", []))[-20:],
        "isekai_pressure_events": state.get("isekai_pressure_events", {}),
        "isekai_risks": state.get("isekai_risks", {}),
        "scene_graph": _public_scene_graph(state),
        "pending_lodging_reward": state.get("pending_lodging_reward", False),
    }


def _public_scene_graph(state: dict[str, Any]) -> dict[str, Any]:
    graph = state.get("scene_graph") if isinstance(state.get("scene_graph"), dict) else {}
    nodes = [
        dict(node)
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("known_to_player", True) is not False
    ] if isinstance(graph.get("nodes"), list) else []
    edges = []
    for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        if edge.get("known_to_player", True) is False:
            continue
        if str(edge.get("access") or "") == "hidden":
            continue
        edges.append(dict(edge))
    return {"nodes": nodes, "edges": edges} if nodes or edges else {}


def public_world_delta_view(pending_delta: dict[str, Any]) -> dict[str, Any]:
    return {
        "advanced": bool(pending_delta.get("advanced")),
        "time_cost": int(pending_delta.get("time_cost", 0)),
        "affected_clocks": list(pending_delta.get("affected_clocks", [])),
        "pending_visible_events": list(pending_delta.get("pending_visible_events", [])),
        "reason": pending_delta.get("reason", ""),
    }


class WorldStateService:
    def __init__(self, store):
        self.store = store

    def classify_action(self, player_input: str) -> dict[str, Any]:
        text = player_input.strip()
        normalized = text.lower()
        if self._is_rule_question(normalized):
            return self._classification("rule_question", text, advance=False)
        if self._is_status_question(normalized):
            return self._classification("status_question", text, advance=False)
        if self._is_clarification(normalized):
            return self._classification("clarification", text, advance=False)
        if self._is_ambiguous_action(normalized):
            return self._classification(
                "ambiguous_action",
                text,
                advance=False,
                needs_clarification=True,
                reason="玩家描述可能是快速查看，也可能是耗时调查，需要先选择处理方式。",
            )
        if self._is_in_world_action(normalized):
            risk_level = self._risk_level(normalized)
            time_cost = 2 if self._is_long_action(normalized) else 1
            return self._classification(
                "in_world_action",
                text,
                advance=True,
                time_cost=time_cost,
                risk_level=risk_level,
                reason="角色进行了会消耗时间或改变局势的世界内行动。",
            )
        if self._is_dialogue(normalized):
            return self._classification(
                "in_world_dialogue",
                text,
                advance=False,
                reason="角色短对话默认不推进世界状态。",
            )
        return self._classification("table_talk", text, advance=False)

    def preview_advance(
        self,
        world_state: dict[str, Any],
        classification: dict[str, Any],
        scene: Any | None = None,
    ) -> dict[str, Any]:
        if not classification.get("advance_world"):
            return {
                "advanced": False,
                "time_cost": 0,
                "affected_clocks": [],
                "pending_visible_events": [],
                "pending_hidden_events": [],
                "reason": classification.get("reason", ""),
            }

        state = normalize_world_state(world_state)
        time_cost = max(0, int(classification.get("time_cost", 0)))
        affected: list[str] = []
        pending_visible_events: list[str] = []
        phase_before = state.get("phase")

        threat_delta = min(time_cost, self._remaining_clock_capacity(state, "threat_clocks", "moonwell_curse"))
        if threat_delta > 0:
            affected.append("moonwell_curse")

        pressure_deltas: dict[str, int] = {}
        if classification.get("risk_level") == "high":
            pressure_deltas["guard_alert"] = 1
            affected.append("guard_alert")

        preview_state = deepcopy(state)
        self._apply_clock_delta(preview_state, "threat_clocks", "moonwell_curse", threat_delta)
        for clock_id, delta in pressure_deltas.items():
            self._apply_clock_delta(preview_state, "pressure_clocks", clock_id, delta)
        self._apply_moonwell_phase(preview_state)

        if preview_state.get("phase") != phase_before:
            pending_visible_events.append(self._phase_visible_event(preview_state.get("phase")))
        elif threat_delta > 0:
            pending_visible_events.append("月井方向传来一阵低沉回响，节庆的喧闹短暂地停了一拍。")
        if "guard_alert" in pressure_deltas:
            pending_visible_events.append("远处传来守夜人巡逻的脚步声，铁匠铺附近变得更危险。")

        return {
            "advanced": True,
            "time_cost": time_cost,
            "threat_deltas": {"moonwell_curse": threat_delta} if threat_delta else {},
            "pressure_deltas": pressure_deltas,
            "affected_clocks": affected,
            "pending_visible_events": [event for event in pending_visible_events if event],
            "pending_hidden_events": [],
            "reason": classification.get("reason", ""),
        }

    def commit_advance(
        self,
        world_state: dict[str, Any],
        pending_delta: dict[str, Any],
        dm_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = normalize_world_state(world_state)
        if not pending_delta.get("advanced"):
            state["last_advance"] = {
                "advanced": False,
                "reason": pending_delta.get("reason", ""),
                "time_cost": 0,
                "affected_clocks": [],
            }
            return state

        for clock_id, delta in pending_delta.get("threat_deltas", {}).items():
            self._apply_clock_delta(state, "threat_clocks", clock_id, int(delta))
        for clock_id, delta in pending_delta.get("pressure_deltas", {}).items():
            self._apply_clock_delta(state, "pressure_clocks", clock_id, int(delta))

        state["turn_count"] = int(state.get("turn_count", 0)) + max(1, int(pending_delta.get("time_cost", 1)))
        self._apply_moonwell_phase(state)
        state["visible_events"] = [
            *state.get("visible_events", []),
            *pending_delta.get("pending_visible_events", []),
        ][-10:]
        state["hidden_events"] = [
            *state.get("hidden_events", []),
            *pending_delta.get("pending_hidden_events", []),
        ][-10:]
        state["last_advance"] = {
            "advanced": True,
            "reason": pending_delta.get("reason", ""),
            "time_cost": int(pending_delta.get("time_cost", 0)),
            "affected_clocks": list(pending_delta.get("affected_clocks", [])),
        }
        return state

    def public_view(self, world_state: dict[str, Any]) -> dict[str, Any]:
        return public_world_state_view(world_state)

    def public_delta_view(self, pending_delta: dict[str, Any]) -> dict[str, Any]:
        return public_world_delta_view(pending_delta)

    def _classification(
        self,
        message_type: str,
        text: str,
        *,
        advance: bool,
        time_cost: int = 0,
        risk_level: str = "none",
        needs_clarification: bool = False,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "message_type": message_type,
            "time_cost": time_cost,
            "risk_level": risk_level,
            "advance_world": advance,
            "needs_clarification": needs_clarification,
            "reason": reason or "玩家没有声明会消耗世界时间的角色行动。",
            "original_input": text,
        }

    def _is_rule_question(self, text: str) -> bool:
        return any(keyword in text for keyword in ("规则", "掷什么骰", "掷骰", "dc", "检定", "saving throw", "rule"))

    def _is_status_question(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in (
                "equipment.",
                "是什么",
                "有什么装备",
                "我的装备",
                "背包",
                "hp",
                "生命",
                "经验",
                "等级",
                "状态",
                "inventory",
                "what is",
            )
        )

    def _is_clarification(self, text: str) -> bool:
        return any(keyword in text for keyword in ("我在哪", "现在在哪", "刚才", "能看到哪些", "出口", "where am i"))

    def _is_ambiguous_action(self, text: str) -> bool:
        ambiguous = ("看看", "看一眼", "观察一下", "扫一眼", "瞄一眼", "look around", "glance")
        explicit = ("搜查", "仔细", "翻找", "search carefully")
        return any(keyword in text for keyword in ambiguous) and not any(keyword in text for keyword in explicit)

    def _is_in_world_action(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in (
                "我去",
                "前往",
                "走向",
                "进入",
                "离开",
                "搜查",
                "调查",
                "撬",
                "偷",
                "等待",
                "休息",
                "翻过",
                "翻墙",
                "购买",
                "买",
                "潜入",
                "search",
                "travel",
                "go to",
                "wait",
                "rest",
                "steal",
            )
        )

    def _is_dialogue(self, text: str) -> bool:
        return any(keyword in text for keyword in ("我问", "我说", "告诉", "询问", "ask", "tell"))

    def _is_long_action(self, text: str) -> bool:
        return any(keyword in text for keyword in ("长时间", "仔细搜查", "等待", "休息", "等到", "long rest", "short rest"))

    def _risk_level(self, text: str) -> str:
        if any(keyword in text for keyword in ("偷", "撬", "潜入", "闯入", "steal", "pick", "break in")):
            return "high"
        if any(keyword in text for keyword in ("搜查", "调查", "翻墙", "search", "investigate")):
            return "medium"
        return "low"

    def _remaining_clock_capacity(self, state: dict[str, Any], collection: str, clock_id: str) -> int:
        for clock in state.get(collection, []):
            if clock.get("id") == clock_id:
                return max(0, int(clock.get("max", 0)) - int(clock.get("value", 0)))
        return 0

    def _apply_clock_delta(self, state: dict[str, Any], collection: str, clock_id: str, delta: int) -> None:
        if delta <= 0:
            return
        for clock in state.get(collection, []):
            if clock.get("id") == clock_id:
                current = int(clock.get("value", 0))
                maximum = int(clock.get("max", current + delta))
                clock["value"] = min(maximum, current + delta)
                if clock_id == "moonwell_curse":
                    clock["severity"] = self._phase_for_value(clock["value"])["severity"]
                return

    def _apply_moonwell_phase(self, state: dict[str, Any]) -> None:
        clock = next((clock for clock in state.get("threat_clocks", []) if clock.get("id") == "moonwell_curse"), None)
        if clock is None:
            return
        phase = self._phase_for_value(int(clock.get("value", 0)))
        state["phase"] = phase["phase"]
        state["phase_label"] = phase["phase_label"]
        clock["severity"] = phase["severity"]
        if phase["phase"] == "festival_panic":
            state.setdefault("location_states", {})["柳溪村广场"] = {
                "mood": "festival_panic",
                "details": ["音乐停了", "村民围在月井旁争吵", "守夜人开始巡逻"],
            }

    def _phase_for_value(self, value: int) -> dict[str, Any]:
        selected = DEFAULT_PHASES[0]
        for phase in DEFAULT_PHASES:
            if value >= phase["value"]:
                selected = phase
        return selected

    def _phase_visible_event(self, phase: str | None) -> str:
        events = {
            "uneasy_omens": "月井边传来低低的回声，几只牲畜惊慌地避开井水。",
            "public_fear": "更多村民聚到月井旁，关于银铃失窃的流言开始扩散。",
            "festival_panic": "广场上的音乐停了，村民围在月井旁争吵，节庆陷入混乱。",
            "curse_spreads": "井水的冷光沿着石缝蔓延，旧磨坊方向传来细碎钟声。",
            "seal_breaking": "月井下方传来裂响，封印似乎正在松动。",
            "breach": "月井危机爆发，井下的威胁不再等待。",
        }
        return events.get(phase, "")
