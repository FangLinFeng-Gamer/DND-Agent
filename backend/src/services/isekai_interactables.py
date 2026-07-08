from __future__ import annotations

from backend.src.schemas.adventure import SceneState


class IsekaiInteractableProjector:
    def project(self, scene: SceneState, action_type: str) -> tuple[list[dict[str, object]], list[str]]:
        objects = " ".join([scene.location, scene.environment, *scene.important_objects])
        interactables: list[dict[str, object]] = []

        if "灰橡镇" in objects or ("镇门" in objects and "灰橡" in objects):
            interactables.append(
                {
                    "id": "gray_oak_town",
                    "type": "place",
                    "name": "灰橡镇",
                    "affordances": ["进入", "观察"],
                    "risk": "进镇后会被守门人与雨中的镇民注意到外来者身份",
                }
            )
        if "旧炉旅店" in objects or "街边旅店" in objects or "旅店" in objects:
            interactables.append(
                {
                    "id": "town_inn_01",
                    "type": "place",
                    "name": "旧炉旅店" if "旧炉旅店" in objects else "街边旅店",
                    "affordances": ["进入", "观察", "询问价格"],
                    "risk": "住宿会消耗铜币，也可能暴露外来者身份",
                }
            )
        if "告示板" in objects or "告示" in objects:
            interactables.append(
                {
                    "id": "notice_board_01",
                    "type": "object",
                    "name": "镇门口告示板" if "镇门" in objects else "告示板",
                    "affordances": ["观察", "解读"],
                    "risk": "停留太久会引来盘查",
                }
            )
        if "祭坛" in objects:
            interactables.append(
                {
                    "id": "temple_altar_01",
                    "type": "object",
                    "name": "祭坛",
                    "affordances": ["观察", "搜索", "解读"],
                    "risk": "触碰祭坛可能惊动残留的神术痕迹",
                }
            )
        if "圣徽" in objects:
            interactables.append(
                {
                    "id": "broken_holy_symbol_01",
                    "type": "clue",
                    "name": "破损圣徽",
                    "affordances": ["观察", "解读", "拿起"],
                    "risk": "圣徽边缘锋利，背面的符号可能带有禁忌含义",
                }
            )
        if "壁画" in objects:
            interactables.append(
                {
                    "id": "temple_mural_01",
                    "type": "clue",
                    "name": "模糊壁画",
                    "affordances": ["观察", "解读"],
                    "risk": "壁画粉尘会留下触碰痕迹",
                }
            )
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
        if "麋鹿骸骨" in objects or "骸骨" in objects:
            interactables.append(
                {
                    "id": "elk_carcass_01",
                    "type": "clue",
                    "name": "麋鹿骸骨",
                    "affordances": ["观察", "搜索"],
                    "risk": "靠近尸骸可能暴露气味，也可能发现捕食者痕迹",
                }
            )
        if "折断的铁头箭" in objects or "铁头箭" in objects or "折断的箭" in objects:
            interactables.append(
                {
                    "id": "broken_arrow_01",
                    "type": "clue",
                    "name": "折断的铁头箭",
                    "affordances": ["观察", "搜索", "拿起"],
                    "risk": "箭头上的残留物可能有毒或带有异常气味",
                }
            )
        if "血迹" in objects:
            interactables.append(
                {
                    "id": "blood_trail_01",
                    "type": "clue",
                    "name": "血迹方向",
                    "affordances": ["观察", "搜索", "追踪"],
                    "risk": "沿血迹追踪可能接近受伤野兽或魔物",
                }
            )
        if "溪流方向" in objects or "溪流声" in objects:
            interactables.append(
                {
                    "id": "stream_direction_01",
                    "type": "place",
                    "name": "溪流方向",
                    "affordances": ["观察", "搜索"],
                    "risk": "水声会掩盖脚步，也可能引来夜间饮水的生物",
                }
            )
        if "坍塌的石砌哨塔" in objects or "坍塌哨塔" in objects:
            interactables.append(
                {
                    "id": "collapsed_watchtower_01",
                    "type": "place",
                    "name": "坍塌的石砌哨塔",
                    "affordances": ["进入", "观察", "搜索"],
                    "risk": "塔内可避风，但坍塌处可能藏有兽迹或松动石块",
                }
            )
        if "旧火堆" in objects:
            interactables.append(
                {
                    "id": "old_firepit_01",
                    "type": "object",
                    "name": "旧火堆",
                    "affordances": ["观察", "搜索"],
                    "risk": "翻动灰烬可能留下新痕迹，也可能暴露最近有人停留",
                }
            )
        if "地基缝隙" in objects:
            interactables.append(
                {
                    "id": "foundation_crack_01",
                    "type": "hazard",
                    "name": "地基缝隙",
                    "affordances": ["观察", "搜索"],
                    "risk": "冷风和气味可能来自哨塔下方空洞",
                }
            )
        if "避风角落" in objects or "墙角" in objects:
            interactables.append(
                {
                    "id": "sheltered_corner_01",
                    "type": "place",
                    "name": "避风角落",
                    "affordances": ["观察", "搜索", "加固"],
                    "risk": "适合短休，但需要先清理碎石和兽毛",
                }
            )
        if "墙体缺口" in objects or "缺口" in objects:
            interactables.append(
                {
                    "id": "wall_gap_01",
                    "type": "obstacle",
                    "name": "墙体缺口",
                    "affordances": ["观察", "堵门", "加固"],
                    "risk": "不处理会漏风，也可能让火光从外面被看见",
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
                        "type": "container",
                        "name": "旧木箱" if "旧木箱" in objects else "木箱",
                        "affordances": ["搜索", "观察", "打开"],
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
        if ("门" in objects or "入口" in objects) and "镇门" not in objects:
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
            if "解读" in affordances:
                suggestions.append(f"解读{name}")
            if "进入" in affordances:
                suggestions.append(f"进入{name}")
            if "装水" in affordances:
                suggestions.append(f"用水囊在{name}装水")
            if "打开" in affordances:
                suggestions.append(f"打开{name}")
            if "加固" in affordances:
                suggestions.append(f"加固{name}")
            if "堵门" in affordances:
                suggestions.append(f"用{name}堵门")
            if "撬开" in affordances:
                suggestions.append(f"强行撬开{name}")
            if "躲避" in affordances:
                suggestions.append(f"听到动静后躲到{name}")
            if "追踪" in affordances:
                suggestions.append(f"沿着{name}追踪")
            if "离开" in affordances:
                suggestions.append(f"从{name}离开")
        if action_type == "enter_location" and "先听一听屋内动静" not in suggestions:
            suggestions.append("先听一听屋内动静")
        return list(dict.fromkeys(suggestions))
