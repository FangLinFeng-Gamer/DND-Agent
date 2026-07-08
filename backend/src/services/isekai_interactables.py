from __future__ import annotations

from backend.src.schemas.adventure import SceneState


class IsekaiInteractableProjector:
    def project(self, scene: SceneState, action_type: str) -> tuple[list[dict[str, object]], list[str]]:
        objects = " ".join([scene.location, scene.environment, *scene.important_objects])
        interactables: list[dict[str, object]] = []

        if "雨水桶" in objects or "水桶" in objects:
            interactables.append(
                {
                    "id": "rain_barrel_01",
                    "type": "water_source",
                    "name": "雨水桶",
                    "affordances": ["装水", "观察"],
                    "risk": "未确认水质前直接饮用可能有风险",
                }
            )
        if "货袋" in objects:
            interactables.append(
                {
                    "id": "cargo_bag_01",
                    "type": "item",
                    "name": "货袋",
                    "affordances": ["搜索", "观察"],
                    "risk": "翻动可能制造声响，也可能有寄生虫或腐坏气味",
                }
            )
        if "破损木箱" in objects:
            interactables.append(
                {
                    "id": "broken_crate_01",
                    "type": "container",
                    "name": "破损木箱",
                    "affordances": ["搜索", "观察", "撬开"],
                    "risk": "木刺和暗藏夹层都可能造成伤害",
                }
            )
        if "木箱" in objects or "箱" in objects:
            if not any(entry.get("id") == "broken_crate_01" for entry in interactables):
                interactables.append(
                    {
                        "id": "wooden_crate_01",
                        "type": "object",
                        "name": "木箱",
                        "affordances": ["搜索", "观察"],
                        "risk": "翻动可能制造声响",
                    }
                )
        if "黑暗角落" in objects:
            interactables.append(
                {
                    "id": "dark_corner_01",
                    "type": "hazard",
                    "name": "黑暗角落",
                    "affordances": ["观察", "躲避"],
                    "risk": "里面可能藏着小型魔物或尖锐杂物",
                }
            )
        if "狭窄破口" in objects or "破口" in objects:
            interactables.append(
                {
                    "id": "narrow_breach_01",
                    "type": "place",
                    "name": "狭窄破口",
                    "affordances": ["离开", "观察"],
                    "risk": "快速通过可能刮伤或卡住装备",
                }
            )
        if "门" in objects or "入口" in objects:
            interactables.append(
                {
                    "id": "door_01",
                    "type": "object",
                    "name": "门口",
                    "affordances": ["堵门", "离开", "观察"],
                }
            )

        if not interactables and action_type in {"enter_location", "search"}:
            interactables.append(
                {
                    "id": "surroundings_01",
                    "type": "place",
                    "name": "周围环境",
                    "affordances": ["观察", "搜索"],
                }
            )

        suggested = self._suggestions(interactables, action_type)
        return interactables[:6], suggested[:5]

    def _suggestions(self, interactables: list[dict[str, object]], action_type: str) -> list[str]:
        suggestions: list[str] = []
        for entry in interactables:
            name = str(entry.get("name") or "")
            affordances = [str(item) for item in entry.get("affordances", [])]
            if "观察" in affordances:
                suggestions.append(f"观察{name}")
            if "搜索" in affordances:
                suggestions.append(f"搜索{name}")
            if "装水" in affordances:
                suggestions.append(f"用水囊在{name}装水")
            if "堵门" in affordances:
                suggestions.append(f"用{name}堵门")
            if "撬开" in affordances:
                suggestions.append(f"强行撬开{name}")
            if "躲避" in affordances:
                suggestions.append(f"听到动静后躲到{name}")
            if "离开" in affordances:
                suggestions.append(f"从{name}离开")
        if action_type == "enter_location" and "先听一听屋内动静" not in suggestions:
            suggestions.append("先听一听屋内动静")
        return list(dict.fromkeys(suggestions))
