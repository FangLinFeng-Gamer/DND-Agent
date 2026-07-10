from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.src.schemas.adventure import SceneState


AFFORDANCE_LABELS = {
    "observe": "观察",
    "search": "搜索",
    "enter": "进入",
    "leave": "离开",
    "approach": "靠近",
    "talk": "交谈",
    "negotiate": "询问价格",
    "purchase": "支付",
    "gather": "采集",
    "take": "拿起",
    "open": "打开",
    "force_open": "撬开",
    "refill_water": "装水",
    "eat_meal": "食用",
    "secure_shelter": "加固",
    "hide": "躲避",
    "avoid": "躲避",
    "track": "追踪",
    "read": "解读",
    "repair": "修理",
}


TYPE_AFFORDANCES = {
    "npc": ["observe", "talk"],
    "merchant": ["observe", "talk", "negotiate", "purchase"],
    "item": ["observe", "take"],
    "container": ["observe", "search", "open", "force_open"],
    "clue": ["observe", "search"],
    "place": ["observe", "approach", "enter"],
    "entrance": ["observe", "enter", "force_open"],
    "obstacle": ["observe", "force_open", "repair"],
    "hazard": ["observe", "avoid", "hide"],
    "resource": ["observe", "search", "gather"],
    "water_source": ["observe", "refill_water"],
    "shelter": ["observe", "search", "secure_shelter"],
    "object": ["observe", "search"],
    "entitlement": ["observe"],
}


class IsekaiContentService:
    DEFAULT_PACKS: list[str] = []

    def builtin_pack(self, pack_id: str) -> dict[str, Any]:
        if pack_id == "old_furnace_inn_p1":
            return deepcopy(self._old_furnace_pack())
        if pack_id == "baseline_exploration_discoveries":
            return deepcopy(self._baseline_exploration_pack())
        return {}

    def ensure_world_state(self, world_state: dict[str, Any] | None) -> dict[str, Any]:
        state = dict(world_state or {})
        content = dict(state.get("isekai_content") or {})
        packs = [str(item) for item in content.get("active_packs", []) if str(item).strip()]
        for pack_id in self.DEFAULT_PACKS:
            if pack_id not in packs:
                packs.append(pack_id)
        content["active_packs"] = packs
        state["isekai_content"] = content
        return state

    def location_nodes(self, world_state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {}
        for pack in self._active_packs(world_state):
            for node in pack.get("locations", []):
                if isinstance(node, dict) and node.get("node_id"):
                    nodes[str(node["node_id"])] = deepcopy(node)
        return nodes

    def discovery_tables(self, world_state: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
        tables: dict[str, list[dict[str, Any]]] = {}
        for pack in self._active_packs(world_state):
            for table in pack.get("discovery_tables", []):
                if not isinstance(table, dict):
                    continue
                target_id = str(table.get("target_object_id") or "")
                if not target_id:
                    continue
                entries = self._discovery_entries_with_table_metadata(table)
                tables.setdefault(target_id, []).extend(entries)
        content = dict((world_state or {}).get("isekai_content") or {})
        for target_id, entries in (content.get("discovery_tables") or {}).items():
            if isinstance(entries, list):
                tables.setdefault(str(target_id), []).extend(deepcopy(entries))
        return tables

    def _discovery_entries_with_table_metadata(self, table: dict[str, Any]) -> list[dict[str, Any]]:
        entries = table.get("entries") if isinstance(table.get("entries"), list) else []
        aliases = [str(item).strip() for item in table.get("target_aliases", []) if str(item).strip()] if isinstance(table.get("target_aliases"), list) else []
        scene_aliases = [str(item).strip() for item in table.get("scene_aliases", []) if str(item).strip()] if isinstance(table.get("scene_aliases"), list) else []
        target_id = str(table.get("target_object_id") or "")
        result: list[dict[str, Any]] = []
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            entry = deepcopy(raw)
            entry.setdefault("_target_object_id", target_id)
            if aliases:
                entry.setdefault("_target_aliases", aliases)
            if scene_aliases:
                entry.setdefault("_scene_aliases", scene_aliases)
            result.append(entry)
        return result

    def merchant_offers(self, world_state: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
        offers: dict[str, list[dict[str, Any]]] = {}
        for pack in self._active_packs(world_state):
            for inventory in pack.get("merchant_inventories", []):
                if not isinstance(inventory, dict):
                    continue
                merchant_id = str(inventory.get("merchant_id") or "")
                if not merchant_id:
                    continue
                entries = inventory.get("offers") if isinstance(inventory.get("offers"), list) else []
                offers.setdefault(merchant_id, []).extend(deepcopy(entries))
        content = dict((world_state or {}).get("isekai_content") or {})
        for merchant_id, entries in (content.get("merchant_offers") or {}).items():
            if isinstance(entries, list):
                offers.setdefault(str(merchant_id), []).extend(deepcopy(entries))
        return offers

    def pressure_events(self, world_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for pack in self._active_packs(world_state):
            for event in pack.get("pressure_events", []):
                if isinstance(event, dict) and event.get("id"):
                    events.append(deepcopy(event))
        content = dict((world_state or {}).get("isekai_content") or {})
        custom = content.get("pressure_events")
        if isinstance(custom, list):
            events.extend(deepcopy([event for event in custom if isinstance(event, dict) and event.get("id")]))
        return events

    def offer_by_id(self, offer_id: str, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        target = str(offer_id or "")
        if not target:
            return {}
        for entries in self.merchant_offers(world_state).values():
            for offer in entries:
                if isinstance(offer, dict) and str(offer.get("offer_id") or "") == target:
                    return deepcopy(offer)
        return {}

    def repair_reward(self, reward_id: str, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        target = str(reward_id or "")
        for pack in self._active_packs(world_state):
            for reward in pack.get("repair_rewards", []):
                if isinstance(reward, dict) and str(reward.get("reward_id") or "") == target:
                    return deepcopy(reward)
        return {}

    def repair_reward_for_target(self, target_id: str, target_name: str, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        target = str(target_id or "")
        name = str(target_name or "")
        for pack in self._active_packs(world_state):
            for reward in pack.get("repair_rewards", []):
                if not isinstance(reward, dict):
                    continue
                ids = [str(item) for item in reward.get("target_ids", []) if str(item).strip()]
                aliases = [str(item) for item in reward.get("target_aliases", []) if str(item).strip()]
                if target and target in ids:
                    return deepcopy(reward)
                if name and any(alias and alias in name for alias in aliases):
                    return deepcopy(reward)
        return {}

    def repair_reward_for_action(
        self,
        *,
        target_id: str,
        target_name: str,
        action_text: str,
        scene: SceneState,
        world_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        direct = self.repair_reward_for_target(target_id, target_name, world_state)
        if direct:
            return direct
        text = " ".join([str(action_text or ""), str(target_name or "")])
        scene_entries = [entry for entry in scene.interactables if isinstance(entry, dict)]
        for pack in self._active_packs(world_state):
            for reward in pack.get("repair_rewards", []):
                if not isinstance(reward, dict):
                    continue
                if self._repair_reward_matches_scene(reward, scene_entries, text):
                    return deepcopy(reward)
        return {}

    def scene_supports_repair_reward_context(
        self,
        scene: SceneState,
        world_state: dict[str, Any] | None = None,
    ) -> bool:
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects, scene.current_objective])
        for pack in self._active_packs(world_state):
            for reward in pack.get("repair_rewards", []):
                if not isinstance(reward, dict):
                    continue
                if self._repair_reward_matches_scene(reward, [entry for entry in scene.interactables if isinstance(entry, dict)], scene_text):
                    return True
        return False

    def repair_reward_cleanup_fragments(self, world_state: dict[str, Any] | None = None) -> list[str]:
        fragments: list[str] = []
        for pack in self._active_packs(world_state):
            for reward in pack.get("repair_rewards", []):
                if not isinstance(reward, dict):
                    continue
                fragments.extend(str(item) for item in reward.get("pending_clues", []) if str(item).strip())
                fragments.extend(str(item) for item in reward.get("rewards", []) if str(item).strip())
            for line in pack.get("quest_lines", []):
                if not isinstance(line, dict):
                    continue
                for transition in line.get("transitions", []):
                    if isinstance(transition, dict):
                        fragments.extend(str(item) for item in transition.get("adds_clues", []) if str(item).strip())
        return list(dict.fromkeys(fragments))

    def quest_flag_values(self, world_state: dict[str, Any] | None = None) -> set[str]:
        values: set[str] = set()
        for pack in self._active_packs(world_state):
            for line in pack.get("quest_lines", []):
                if not isinstance(line, dict):
                    continue
                for transition in line.get("transitions", []):
                    if isinstance(transition, dict):
                        values.update(str(value) for value in (transition.get("flags") or {}).values() if str(value).strip())
        return values

    def _repair_reward_matches_scene(
        self,
        reward: dict[str, Any],
        scene_entries: list[dict[str, Any]],
        text: str,
    ) -> bool:
        ids = {str(item).strip() for item in reward.get("target_ids", []) if str(item).strip()} if isinstance(reward.get("target_ids"), list) else set()
        aliases = [str(item).strip() for item in reward.get("target_aliases", []) if str(item).strip()] if isinstance(reward.get("target_aliases"), list) else []
        repairable_matches: list[dict[str, Any]] = []
        for entry in scene_entries:
            entry_id = str(entry.get("id") or "").strip()
            if ids and entry_id not in ids:
                continue
            affordances = "".join(str(item) for item in entry.get("affordances", []))
            if "修" not in affordances and "维修" not in affordances:
                continue
            repairable_matches.append(entry)
            name = str(entry.get("name") or "").strip()
            entry_aliases = [str(item).strip() for item in entry.get("aliases", []) if str(item).strip()] if isinstance(entry.get("aliases"), list) else []
            if name and name in text:
                return True
            if any(alias and alias in text for alias in [*aliases, *entry_aliases]):
                return True
        return len(repairable_matches) == 1 and bool(text)

    def destination_template(self, target_name: str, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        text = str(target_name or "")
        for pack in self._active_packs(world_state):
            for template in pack.get("destination_templates", []):
                if not isinstance(template, dict):
                    continue
                aliases = [str(item) for item in template.get("target_aliases", []) if str(item).strip()]
                if any(alias and alias in text for alias in aliases):
                    return deepcopy(template)
        return {}

    def quest_line(self, quest_id: str, world_state: dict[str, Any] | None = None) -> dict[str, Any]:
        for pack in self._active_packs(world_state):
            for line in pack.get("quest_lines", []):
                if isinstance(line, dict) and str(line.get("quest_id") or "") == quest_id:
                    return deepcopy(line)
        return {}

    def allowed_active_quest_ids(self, world_state: dict[str, Any] | None = None) -> set[str]:
        ids: set[str] = set()
        for pack in self._active_packs(world_state):
            for line in pack.get("quest_lines", []):
                if isinstance(line, dict) and line.get("allowed_as_active_p1"):
                    quest_id = str(line.get("quest_id") or "").strip()
                    if quest_id:
                        ids.add(quest_id)
        return ids

    def quest_reward_for_stage(
        self,
        quest_id: str,
        stage: str,
        world_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        line = self.quest_line(quest_id, world_state)
        for reward in line.get("rewards", []):
            if isinstance(reward, dict) and str(reward.get("stage") or "") == stage:
                return deepcopy(reward.get("payload") if isinstance(reward.get("payload"), dict) else reward)
        return {}

    def scene_objects_from_names(self, names: list[str]) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        for index, name in enumerate(names[:10]):
            clean = str(name or "").strip()
            if not clean:
                continue
            objects.append(
                {
                    "id": f"destination_object_{index + 1}",
                    "type": "object",
                    "name": clean,
                    "suggested_affordances": ["observe", "search"],
                    "source": "destination_object_list",
                }
            )
        return objects

    def materialize_scene_objects(self, scene: SceneState, proposals: Any) -> tuple[SceneState, dict[str, Any]]:
        if not isinstance(proposals, dict):
            return scene, {}
        raw_items = proposals.get("add")
        if not isinstance(raw_items, list):
            return scene, {}
        existing = [dict(entry) for entry in scene.interactables if isinstance(entry, dict)]
        index_by_id = {str(entry.get("id") or ""): index for index, entry in enumerate(existing) if str(entry.get("id") or "")}
        existing_keys = {str(entry.get("id") or entry.get("name") or "") for entry in existing}
        added: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        blocked: list[dict[str, str]] = []
        for index, raw in enumerate(raw_items[:10]):
            obj, reason = self._validate_scene_object(raw, scene, index)
            if reason:
                blocked.append({"name": str(raw.get("name") or "unknown") if isinstance(raw, dict) else "unknown", "reason": reason})
                continue
            key = str(obj.get("id") or obj.get("name") or "")
            obj_id = str(obj.get("id") or "")
            if obj_id and obj_id in index_by_id:
                existing[index_by_id[obj_id]] = {**existing[index_by_id[obj_id]], **obj}
                updated.append(obj)
                continue
            if key in existing_keys:
                continue
            existing_keys.add(key)
            added.append(obj)
        if not added and not updated:
            return scene, {"source": "llm_proposal", "added": [], "updated": [], "blocked": blocked}
        suggestions = list(scene.suggested_actions)
        for obj in added:
            suggestions.extend(self._suggestions_for(obj))
        next_scene = scene.model_copy(
            update={
                "interactables": [*existing, *added],
                "suggested_actions": list(dict.fromkeys([str(item) for item in suggestions if str(item).strip()]))[:8],
            }
        )
        return next_scene, {"source": "llm_proposal", "added": added, "updated": updated, "blocked": blocked}

    def materialize_scene_from_content(
        self,
        scene: SceneState,
        world_state: dict[str, Any] | None = None,
    ) -> tuple[SceneState, dict[str, Any]]:
        template = self.destination_template(scene.location, world_state)
        if not template:
            return scene, {"source": "content_pack", "added": [], "updated": [], "blocked": []}
        scene_objects = template.get("scene_objects") if isinstance(template.get("scene_objects"), list) else []
        if not scene_objects:
            return scene, {"source": "content_pack", "added": [], "updated": [], "blocked": []}
        base_scene = self._without_generic_placeholders(scene)
        if not self._should_materialize_template(base_scene, scene_objects):
            return base_scene, {"source": "content_pack", "added": [], "updated": [], "blocked": []}
        next_scene, metadata = self.materialize_scene_objects(base_scene, {"add": scene_objects})
        return next_scene, {**metadata, "source": "content_pack"}

    def _without_generic_placeholders(self, scene: SceneState) -> SceneState:
        placeholders = {"", "门口", "周围环境"}
        filtered = [
            dict(entry)
            for entry in scene.interactables
            if isinstance(entry, dict) and str(entry.get("name") or "").strip() not in placeholders
        ]
        if len(filtered) == len(scene.interactables):
            return scene
        suggestions = [
            str(item)
            for item in scene.suggested_actions
            if not any(placeholder and placeholder in str(item) for placeholder in placeholders)
        ]
        return scene.model_copy(update={"interactables": filtered, "suggested_actions": suggestions})

    def _should_materialize_template(self, scene: SceneState, scene_objects: list[dict[str, Any]]) -> bool:
        if not scene.interactables:
            return True
        object_ids = {str(item.get("id") or "").strip() for item in scene_objects if isinstance(item, dict)}
        object_names = {str(item.get("name") or "").strip() for item in scene_objects if isinstance(item, dict)}
        existing_ids = {str(item.get("id") or "").strip() for item in scene.interactables if isinstance(item, dict)}
        existing_names = {str(item.get("name") or "").strip() for item in scene.interactables if isinstance(item, dict)}
        if object_ids & existing_ids or object_names & existing_names:
            return True
        important_text = " ".join(str(item) for item in scene.important_objects)
        return any(name and name in important_text for name in object_names)

    def _active_packs(self, world_state: dict[str, Any] | None) -> list[dict[str, Any]]:
        state = self.ensure_world_state(world_state)
        pack_ids = [str(item) for item in state["isekai_content"].get("active_packs", [])]
        return [self.builtin_pack(pack_id) for pack_id in pack_ids if self.builtin_pack(pack_id)]

    def _validate_scene_object(self, raw: Any, scene: SceneState, index: int) -> tuple[dict[str, Any], str]:
        if not isinstance(raw, dict):
            return {}, "not_object"
        obj_type = str(raw.get("type") or "object").strip()
        if obj_type not in TYPE_AFFORDANCES:
            return {}, "invalid_type"
        name = str(raw.get("name") or "").strip()
        if not name:
            return {}, "missing_name"
        if obj_type == "water_source" and self._scene_blocks_water_source(scene):
            return {}, "scene_blocks_water_source"
        aliases = [str(item).strip() for item in raw.get("aliases", []) if str(item).strip()] if isinstance(raw.get("aliases"), list) else []
        suggested = raw.get("suggested_affordances") or raw.get("affordances") or []
        affordances = self._normalize_affordances(obj_type, suggested)
        obj_id = str(raw.get("id") or "").strip() or self._object_id(scene, name, index)
        result = {
            "id": obj_id,
            "type": obj_type,
            "name": name,
            "aliases": aliases,
            "description": str(raw.get("description") or "").strip(),
            "state": str(raw.get("state") or "").strip(),
            "visibility": str(raw.get("visibility") or "visible").strip(),
            "presence": str(raw.get("presence") or "current").strip(),
            "scope": str(raw.get("scope") or "current_node").strip(),
            "affordances": affordances,
            "tags": [str(item).strip() for item in raw.get("tags", []) if str(item).strip()] if isinstance(raw.get("tags"), list) else [],
            "source": "llm_scene_object",
        }
        risk = str(raw.get("risk") or raw.get("risk_hint") or "").strip()
        if risk:
            result["risk"] = risk
        return result, ""

    def _scene_blocks_water_source(self, scene: SceneState) -> bool:
        scene_text = " ".join([scene.location, scene.environment, *scene.important_objects, scene.current_objective])
        return any(marker in scene_text for marker in ["没有任何水源", "没有水源", "无水源"])

    def _normalize_affordances(self, obj_type: str, raw_affordances: Any) -> list[str]:
        allowed = TYPE_AFFORDANCES.get(obj_type, TYPE_AFFORDANCES["object"])
        proposed = [str(item).strip() for item in raw_affordances if str(item).strip()] if isinstance(raw_affordances, list) else []
        normalized: list[str] = []
        for item in proposed or allowed:
            key = self._affordance_key(item)
            if key in allowed:
                label = AFFORDANCE_LABELS.get(key, item)
                if label not in normalized:
                    normalized.append(label)
        if not normalized:
            normalized = [AFFORDANCE_LABELS[key] for key in allowed if key in AFFORDANCE_LABELS]
        return normalized

    def _affordance_key(self, value: str) -> str:
        for key, label in AFFORDANCE_LABELS.items():
            if value == key or value == label:
                return key
        return value

    def _object_id(self, scene: SceneState, name: str, index: int) -> str:
        node_id = str((scene.location_path or {}).get("node_id") or scene.location or "scene")
        safe_node = "".join(ch if ch.isalnum() else "_" for ch in node_id)[:24] or "scene"
        return f"{safe_node}_obj_{index + 1}"

    def _suggestions_for(self, obj: dict[str, Any]) -> list[str]:
        name = str(obj.get("name") or "")
        suggestions: list[str] = []
        affordances = [str(item) for item in obj.get("affordances", [])]
        if "观察" in affordances:
            suggestions.append(f"观察{name}")
        if "搜索" in affordances:
            suggestions.append(f"搜索{name}")
        if "打开" in affordances:
            suggestions.append(f"打开{name}")
        if "进入" in affordances:
            suggestions.append(f"进入{name}")
        if "拿起" in affordances:
            suggestions.append(f"拿起{name}")
        if "装水" in affordances:
            suggestions.append(f"用水囊在{name}装水")
        return suggestions

    def _old_furnace_pack(self) -> dict[str, Any]:
        return {
            "content_pack_id": "old_furnace_inn_p1",
            "locations": [
                {
                    "node_id": "graystone_town",
                    "region": "灰石镇",
                    "site": "镇门街",
                    "sublocation": "",
                    "parent_id": "graystone_region",
                    "aliases": ["灰石镇", "镇门街", "镇门"],
                    "objective": "在日落前找到能承认你身份的落脚点。",
                    "environment": "雨后的灰石镇门街挤着商队和巡逻民兵，旧炉旅店的招牌在前方冒着煤烟。",
                    "important_objects": ["旧炉旅店", "巡逻民兵", "泥水街道"],
                    "interactables": [
                        {"id": "old_furnace_inn", "type": "place", "name": "旧炉旅店", "affordances": ["进入", "观察"]},
                        {"id": "town_notice", "type": "object", "name": "宵禁告示", "affordances": ["观察"]},
                    ],
                    "suggested_actions": ["进入旧炉旅店前厅", "查看宵禁告示"],
                    "neighbors": ["inn_front_hall"],
                },
                {
                    "node_id": "inn_front_hall",
                    "region": "灰石镇",
                    "site": "旧炉旅店",
                    "sublocation": "前厅",
                    "parent_id": "old_furnace_inn",
                    "aliases": ["旧炉旅店前厅", "旅店前厅", "旧炉旅店", "前厅"],
                    "objective": "和店主谈妥住宿、食物或可交换的帮助。",
                    "environment": "旧炉旅店前厅低矮温热，火塘边有几名旅人，店主站在柜台后打量外来者。",
                    "important_objects": ["店主", "火塘", "后厨门", "二楼木梯"],
                    "npcs": ["店主"],
                    "interactables": [
                        {
                            "id": "innkeeper_01",
                            "type": "npc",
                            "name": "店主",
                            "state": "戒备",
                            "affordances": ["交涉", "询问价格", "支付"],
                            "risk": "外来者身份会让报价更硬",
                        },
                        {"id": "kitchen_door", "type": "place", "name": "后厨", "affordances": ["进入", "观察"]},
                        {"id": "room_stairs", "type": "place", "name": "二楼客房", "affordances": ["进入", "观察"]},
                    ],
                    "suggested_actions": ["和店主讨价还价", "去后厨看看能否帮忙", "支付铜币买床位"],
                    "neighbors": ["graystone_town", "inn_kitchen", "inn_room_3", "inn_stable"],
                },
                {
                    "node_id": "inn_kitchen",
                    "region": "灰石镇",
                    "site": "旧炉旅店",
                    "sublocation": "后厨",
                    "parent_id": "old_furnace_inn",
                    "aliases": ["旧炉旅店后厨", "旅店后厨", "后厨", "厨房"],
                    "objective": "确认能否通过修好锅把换取住宿权益。",
                    "environment": "后厨蒸汽贴着低梁翻滚，一只炖锅的锅把松脱，厨娘焦急地护着炉火。",
                    "important_objects": ["松动锅把", "炖锅", "炉火"],
                    "npcs": ["厨娘"],
                    "interactables": [
                        {
                            "id": "broken_pot_handle",
                            "type": "object",
                            "name": "松动锅把",
                            "affordances": ["修理", "观察"],
                            "risk": "拖太久会耽误晚餐，店主会失去耐心",
                        },
                        {"id": "kitchen_exit", "type": "place", "name": "前厅", "affordances": ["进入", "离开"]},
                    ],
                    "suggested_actions": ["修好松动锅把", "回到前厅"],
                    "neighbors": ["inn_front_hall"],
                },
                {
                    "node_id": "inn_room_3",
                    "region": "灰石镇",
                    "site": "旧炉旅店",
                    "sublocation": "二楼三号房",
                    "parent_id": "old_furnace_inn",
                    "aliases": ["二楼三号房", "二楼客房", "客房", "三号房"],
                    "objective": "确认床位、钥匙和夜间安全。",
                    "environment": "二楼三号房狭窄但干燥，床架上铺着粗毯，窗外能听见镇墙方向的犬吠。",
                    "important_objects": ["床位", "粗毯", "小窗"],
                    "interactables": [
                        {"id": "inn_room_3_bed", "type": "entitlement", "name": "二楼三号房床位", "affordances": ["休息", "睡觉"]},
                        {"id": "small_window", "type": "place", "name": "小窗", "affordances": ["观察"]},
                    ],
                    "suggested_actions": ["检查床位", "从小窗听夜里动静"],
                    "neighbors": ["inn_front_hall"],
                },
                {
                    "node_id": "inn_stable",
                    "region": "灰石镇",
                    "site": "旧炉旅店",
                    "sublocation": "马厩",
                    "parent_id": "old_furnace_inn",
                    "aliases": ["旧炉旅店马厩", "旅店马厩", "马厩"],
                    "objective": "查看马厩是否适合暂避或听取夜间动静。",
                    "environment": "马厩里铺着潮草，牲口不安地刨地，外墙缝里传来远处低嚎。",
                    "important_objects": ["潮草", "外墙缝", "不安的马"],
                    "interactables": [
                        {"id": "stable_wall_gap", "type": "place", "name": "外墙缝", "affordances": ["观察", "聆听"]},
                    ],
                    "suggested_actions": ["听听外墙外的动静", "回到前厅"],
                    "neighbors": ["inn_front_hall"],
                },
            ],
            "merchant_inventories": [
                {
                    "merchant_id": "innkeeper_01",
                    "offers": [
                        {
                            "offer_id": "inn_bed",
                            "kind": "entitlement",
                            "name": "二楼三号房床位",
                            "aliases": ["床位", "住宿", "客房"],
                            "price_copper": 3,
                            "grants": {
                                "items": ["二楼三号房钥匙"],
                                "entitlements": [
                                    {
                                        "id": "inn_room_3_bed",
                                        "name": "二楼三号房床位",
                                        "item": "二楼三号房钥匙",
                                        "status": "今晚有床位",
                                        "identity": "旧炉旅店临时住客",
                                    }
                                ],
                                "relationship_changes": [
                                    {"npc_id": "innkeeper_01", "name": "店主", "attitude": "愿意交易", "delta": 5}
                                ],
                            },
                            "alternatives": ["帮后厨修锅把换取床位", "询问是否能赊账", "去马厩换更便宜的落脚处"],
                        },
                        {
                            "offer_id": "stew_meal",
                            "kind": "meal",
                            "name": "热炖菜一碗",
                            "aliases": ["炖菜", "热食"],
                            "price_copper": 2,
                        },
                    ],
                }
            ],
            "discovery_tables": [
                {
                    "target_object_id": "broken_pot_handle",
                    "entries": [
                        {
                            "entry_id": "repair_lodging_reward",
                            "trigger": {"action_type": "repair"},
                            "result": {"clues": ["店主提到夜里镇墙外有异常低嚎"]},
                        }
                    ],
                }
            ],
            "repair_rewards": [
                {
                    "reward_id": "lodging_for_repair",
                    "target_ids": ["broken_pot_handle"],
                    "result_text": "你花了约 15 分钟修好松动锅把，后厨蒸汽重新稳定，店主愿意用住宿权抵这次帮忙。",
                    "pending_rewards": ["修好松动锅把", "店主愿意兑现住宿报酬"],
                    "pending_clues": ["店主提到夜里镇墙外有异常低嚎"],
                    "items": ["二楼三号房钥匙"],
                    "rewards": ["二楼三号房钥匙", "二楼三号房床位", "店主透露夜里镇墙外有异常低嚎"],
                    "transaction": {"lost": "0 铜", "gained": "二楼三号房钥匙、二楼三号房床位", "reason": "修好后厨锅把"},
                    "entitlements": [
                        {
                            "id": "inn_room_3_bed",
                            "name": "二楼三号房床位",
                            "item": "二楼三号房钥匙",
                            "status": "今晚有床位",
                            "identity": "旧炉旅店临时住客",
                        }
                    ],
                    "relationship_changes": [
                        {"npc_id": "innkeeper_01", "name": "店主", "attitude": "愿意交易", "delta": 12}
                    ],
                }
            ],
            "quest_lines": [
                {
                    "quest_id": "night_wolf_line",
                    "allowed_as_active_p1": True,
                    "stages": ["not_started", "rumor_heard", "night_event_seen", "prepared", "tracking", "resolved"],
                    "transitions": [
                        {
                            "from": "not_started",
                            "to": "rumor_heard",
                            "trigger": {
                                "text_contains_any": ["暗夜狼", "狼嚎", "低嚎"],
                                "delta_clue_contains_any": ["暗夜狼", "低嚎"],
                            },
                            "adds_clues": ["旧炉旅店店主提到夜里镇墙外有异常低嚎"],
                            "flags": {"rumor_source": "old_furnace_keeper"},
                        },
                        {
                            "from": "rumor_heard",
                            "to": "night_event_seen",
                            "trigger": {"pressure_event_id": "night_wolf_howl_01"},
                            "adds_clues": ["夜里暗夜狼嚎来自灰石镇北坡方向"],
                            "flags": {"night_event_seen": True},
                        },
                        {
                            "from": "night_event_seen",
                            "to": "prepared",
                            "trigger": {"text_contains_any": ["梦魇草"]},
                            "adds_clues": ["暗夜狼惧怕梦魇草燃烟"],
                            "flags": {"prepared_with_nightmare_grass": True},
                        },
                        {
                            "from": "prepared",
                            "to": "tracking",
                            "trigger": {"text_contains_any": ["北坡", "追踪", "痕迹", "前往"]},
                            "adds_clues": ["北坡泥地上有暗夜狼留下的反向趾印"],
                            "flags": {"tracking_started": True},
                        },
                        {
                            "from": "tracking",
                            "to": "resolved",
                            "trigger": {"text_contains_any": ["回镇", "汇报", "报告"]},
                            "flags": {"reported_to_innkeeper": True},
                        },
                    ],
                    "rewards": [
                        {
                            "stage": "resolved",
                            "reason": "night_wolf_line",
                            "payload": {
                                "items_added": ["暗夜狼牙 x1"],
                                "currency_delta": 8,
                                "relationship_delta": [
                                    {
                                        "npc_id": "old_furnace_keeper",
                                        "name": "旧炉旅店店主",
                                        "trust": 10,
                                        "attitude": "更信任",
                                    }
                                ],
                                "clues_added": ["暗夜狼惧怕梦魇草燃烟"],
                                "entitlements_added": [],
                            },
                        }
                    ],
                }
            ],
            "pressure_events": [
                {
                    "id": "night_wolf_howl_01",
                    "type": "night_wolf",
                    "cooldown_turns": 5,
                    "state_delta": {"night_wolf_attention": 1},
                    "visible_text": "半夜的窗纸忽然一颤，镇墙外传来压得很低的狼嚎，像是有什么东西在逆着风嗅人味。",
                    "conditions": {
                        "time_of_day": "night",
                        "lodging_identity": True,
                        "quest": {"active_quest_id": "night_wolf_line", "stage": "rumor_heard"},
                        "cue_contains_any": ["夜里", "夜晚", "半夜", "深夜", "狼嚎", "低嚎", "暗夜狼"],
                    },
                },
                {
                    "id": "curfew_bell_01",
                    "type": "curfew",
                    "cooldown_turns": 5,
                    "state_delta": {"curfew_risk": 1},
                    "visible_text": "远处钟声响起，街上的巡逻灯火开始变密。",
                    "conditions": {
                        "time_of_day": "night",
                        "lodging_identity": False,
                    },
                },
            ],
        }

    def _baseline_exploration_pack(self) -> dict[str, Any]:
        return {
            "content_pack_id": "baseline_exploration_discoveries",
            "scope": "adventure",
            "source": "built_in_content",
            "locations": [],
            "merchant_inventories": [],
            "destination_templates": [
                {
                    "target_aliases": ["废弃神庙", "神庙"],
                    "environment": "半坍塌的石砌神庙被常春藤和苔藓覆盖，内部阴暗潮湿，祭坛、旧木箱、破损圣徽和模糊壁画都值得确认。",
                    "important_objects": ["旧木箱", "祭坛", "破损圣徽", "模糊壁画"],
                    "scene_objects": [
                        {"id": "wooden_crate_01", "type": "container", "name": "旧木箱", "suggested_affordances": ["observe", "search", "open"]},
                        {"id": "temple_altar_01", "type": "object", "name": "祭坛", "suggested_affordances": ["observe", "search"]},
                        {"id": "temple_broken_emblem_01", "type": "clue", "name": "破损圣徽", "suggested_affordances": ["observe"]},
                        {"id": "temple_faded_mural_01", "type": "clue", "name": "模糊壁画", "suggested_affordances": ["observe", "read"]},
                    ],
                },
                {
                    "target_aliases": ["小屋"],
                    "environment": "小屋内空气潮湿，角落里有木箱和接雨水的木桶，倒塌木柜与黑暗角落都可能藏着风险。",
                    "important_objects": ["木箱", "雨水桶", "倒塌木柜", "半开的地窖门", "黑暗角落", "墙上的抓痕"],
                    "scene_objects": [
                        {"id": "wooden_crate_01", "type": "container", "name": "木箱", "suggested_affordances": ["observe", "search", "open"]},
                        {"id": "rain_barrel_01", "type": "water_source", "name": "雨水桶", "suggested_affordances": ["observe", "refill_water"]},
                        {"id": "collapsed_cabinet_01", "type": "container", "name": "倒塌木柜", "suggested_affordances": ["observe", "search"]},
                        {"id": "cellar_door_01", "type": "entrance", "name": "半开的地窖门", "suggested_affordances": ["observe", "enter", "force_open"]},
                    ],
                },
                {
                    "target_aliases": ["灰橡镇西门"],
                    "environment": "灰橡镇西门前泥路湿滑，镇门口告示板斜挂在门柱上，门内屋檐下挤着避雨的人影。",
                    "important_objects": ["灰橡镇", "镇门口告示板", "断裂的马车轮"],
                    "scene_objects": [
                        {"id": "gray_oak_town_gate_01", "type": "place", "name": "灰橡镇", "suggested_affordances": ["observe", "enter"]},
                        {"id": "gray_oak_notice_board_01", "type": "object", "name": "镇门口告示板", "suggested_affordances": ["observe", "read"]},
                        {"id": "broken_wagon_wheel_01", "type": "object", "name": "断裂的马车轮", "suggested_affordances": ["observe", "search"]},
                    ],
                },
                {
                    "target_aliases": ["灰橡镇"],
                    "environment": "灰橡镇门内的泥街被阴雨压得发暗，低矮屋檐下挤着避雨的旅人，街边旅店的烟囱正冒出潮湿柴烟。",
                    "important_objects": ["街边旅店", "镇门口告示板", "守门棚", "避雨屋檐"],
                    "scene_objects": [
                        {"id": "street_inn_01", "type": "place", "name": "街边旅店", "suggested_affordances": ["observe", "enter", "negotiate"]},
                        {"id": "gate_notice_board_01", "type": "object", "name": "镇门口告示板", "suggested_affordances": ["observe", "read"]},
                        {"id": "guard_shed_01", "type": "place", "name": "守门棚", "suggested_affordances": ["observe"]},
                    ],
                },
                {
                    "target_aliases": ["镇"],
                    "environment": "镇门内街道潮湿拥挤，旅店招牌、告示板和巡逻身影都能立刻看见。",
                    "important_objects": ["街边旅店", "镇门口告示板", "巡逻民兵", "避雨屋檐"],
                    "scene_objects": [
                        {"id": "town_inn_01", "type": "place", "name": "街边旅店", "suggested_affordances": ["observe", "enter", "negotiate"]},
                        {"id": "town_notice_board_01", "type": "object", "name": "镇门口告示板", "suggested_affordances": ["observe", "read"]},
                    ],
                },
                {
                    "target_aliases": ["迷雾森林", "森林的边界"],
                    "environment": "迷雾森林边界潮湿压抑，麋鹿骸骨、折断的铁头箭和拖向哨塔的血迹都指向同一条危险路线，溪流声从旁边传来。",
                    "important_objects": ["麋鹿骸骨", "折断的铁头箭", "血迹方向", "坍塌的石砌哨塔", "溪流方向"],
                    "scene_objects": [
                        {"id": "forest_elk_carcass_01", "type": "clue", "name": "麋鹿骸骨", "suggested_affordances": ["observe", "search"]},
                        {"id": "forest_broken_arrow_01", "type": "clue", "name": "折断的铁头箭", "aliases": ["折断箭"], "suggested_affordances": ["observe", "search"]},
                        {"id": "forest_blood_trail_01", "type": "clue", "name": "血迹方向", "suggested_affordances": ["observe", "track"]},
                        {"id": "forest_watchtower_route_01", "type": "place", "name": "坍塌的石砌哨塔", "suggested_affordances": ["observe", "enter", "track"]},
                        {"id": "forest_stream_direction_01", "type": "water_source", "name": "溪流方向", "suggested_affordances": ["observe", "refill_water"]},
                    ],
                },
                {
                    "target_aliases": ["哨塔"],
                    "environment": "坍塌的石砌哨塔内部漏着冷风，旧火堆旁有灰烬，地基缝隙透出潮气，避风角落和墙体缺口都需要确认。",
                    "important_objects": ["旧火堆", "地基缝隙", "避风角落", "墙体缺口", "墙角兽毛"],
                    "scene_objects": [
                        {"id": "old_firepit_01", "type": "object", "name": "旧火堆", "suggested_affordances": ["observe", "search"]},
                        {"id": "foundation_crack_01", "type": "hazard", "name": "地基缝隙", "suggested_affordances": ["observe", "search"]},
                        {"id": "sheltered_corner_01", "type": "shelter", "name": "避风角落", "suggested_affordances": ["observe", "search", "secure_shelter"]},
                        {"id": "wall_gap_01", "type": "obstacle", "name": "墙体缺口", "suggested_affordances": ["observe", "secure_shelter"]},
                    ],
                },
            ],
            "discovery_tables": [
                {
                    "target_object_id": "cargo_bag_01",
                    "target_aliases": ["货袋"],
                    "entries": [
                        {
                            "entry_id": "cargo_bag_food",
                            "trigger": {"action_type": "search"},
                            "result": {
                                "narration_fact": "你搜索货袋，找到一小份还能入口的潮湿干粮，但翻动布袋制造了细碎声响。",
                                "items_added": ["潮湿干粮 x1"],
                            },
                        }
                    ],
                },
                {
                    "target_object_id": "wooden_crate_01",
                    "target_aliases": ["旧木箱", "木箱"],
                    "scene_aliases": ["神庙", "祭坛", "圣徽"],
                    "entries": [
                        {
                            "entry_id": "abandoned_temple_crate",
                            "trigger": {"action_type": "search"},
                            "result": {
                                "narration_fact": "你翻开旧木箱，里面没有能立刻入口的补给；箱底滚着一只干裂的空香瓶，旁边压着包蜡布的断银链，银链末端刻着锁链女神的小符号。",
                                "reveal_objects": [
                                    {"id": "temple_empty_incense_bottle", "type": "clue", "name": "木箱里的空香瓶", "suggested_affordances": ["observe"]},
                                    {"id": "temple_broken_silver_chain", "type": "clue", "name": "包着蜡布的断银链", "suggested_affordances": ["observe"]},
                                    {"id": "temple_chained_goddess_mark", "type": "clue", "name": "箱底刻着锁链女神的小符号", "suggested_affordances": ["observe"]},
                                ],
                                "clues": ["旧木箱里有锁链女神相关符号"],
                            },
                        }
                    ],
                },
                {
                    "target_object_id": "scene:forest_wounded_trail",
                    "target_aliases": ["麋鹿骸骨", "折断的箭", "折断箭", "铁头箭", "血迹", "血迹方向"],
                    "scene_aliases": ["迷雾森林", "麋鹿骸骨", "坍塌的石砌哨塔"],
                    "entries": [
                        {
                            "entry_id": "forest_wounded_trail",
                            "trigger": {"action_type": "observe"},
                            "result": {
                                "narration_fact": "你检查麋鹿骸骨和折断的铁头箭：箭头残着黑色树脂，肋骨上的咬痕窄长，不像普通狼吻；血迹断断续续拖向坍塌哨塔，溪流边还压着几枚浅脚印。",
                                "reveal_objects": [
                                    {"id": "black_resin_on_arrow", "type": "clue", "name": "铁头箭上的黑色树脂", "suggested_affordances": ["observe"]},
                                    {"id": "narrow_bite_marks", "type": "clue", "name": "不像狼的窄长咬痕", "suggested_affordances": ["observe"]},
                                    {"id": "blood_trail_to_watchtower", "type": "clue", "name": "拖向哨塔的血迹", "suggested_affordances": ["observe", "track"]},
                                    {"id": "shallow_stream_footprints", "type": "clue", "name": "溪流边的浅脚印", "suggested_affordances": ["observe"]},
                                ],
                                "clues": ["麋鹿不是普通野兽袭击，血迹一路拖向坍塌哨塔"],
                            },
                        },
                        {
                            "entry_id": "forest_wounded_trail_search",
                            "trigger": {"action_type": "search"},
                            "result": {
                                "narration_fact": "你检查麋鹿骸骨和折断的铁头箭：箭头残着黑色树脂，肋骨上的咬痕窄长，不像普通狼吻；血迹断断续续拖向坍塌哨塔，溪流边还压着几枚浅脚印。",
                                "reveal_objects": [
                                    {"id": "black_resin_on_arrow", "type": "clue", "name": "铁头箭上的黑色树脂", "suggested_affordances": ["observe"]},
                                    {"id": "narrow_bite_marks", "type": "clue", "name": "不像狼的窄长咬痕", "suggested_affordances": ["observe"]},
                                    {"id": "blood_trail_to_watchtower", "type": "clue", "name": "拖向哨塔的血迹", "suggested_affordances": ["observe", "track"]},
                                    {"id": "shallow_stream_footprints", "type": "clue", "name": "溪流边的浅脚印", "suggested_affordances": ["observe"]},
                                ],
                                "clues": ["麋鹿不是普通野兽袭击，血迹一路拖向坍塌哨塔"],
                            },
                        },
                    ],
                },
                {
                    "target_object_id": "scene:stream_safety",
                    "target_aliases": ["溪流方向", "溪流", "水源", "脚印"],
                    "scene_aliases": ["迷雾森林", "溪流", "坍塌的石砌哨塔"],
                    "entries": [
                        {
                            "entry_id": "stream_safety_observe",
                            "trigger": {"action_type": "observe"},
                            "result": {
                                "narration_fact": "你沿着溪流方向查看，水面清澈但上游漂来几缕粗硬兽毛，泥边有浅脚印；这水可以处理后饮用，直接喝仍有风险。",
                                "reveal_objects": [
                                    {"id": "stream_shallow_footprints", "type": "clue", "name": "溪流边的浅脚印", "suggested_affordances": ["observe"]},
                                    {"id": "upstream_coarse_fur", "type": "clue", "name": "上游漂来的兽毛", "suggested_affordances": ["observe"]},
                                    {"id": "boilable_stream_water", "type": "water_source", "name": "需要煮沸的溪水", "suggested_affordances": ["observe", "refill_water"]},
                                ],
                                "clues": ["溪水可以处理后饮用，直接喝仍有风险"],
                            },
                        },
                        {
                            "entry_id": "stream_safety_search",
                            "trigger": {"action_type": "search"},
                            "result": {
                                "narration_fact": "你沿着溪流方向查看，水面清澈但上游漂来几缕粗硬兽毛，泥边有浅脚印；这水可以处理后饮用，直接喝仍有风险。",
                                "reveal_objects": [
                                    {"id": "stream_shallow_footprints", "type": "clue", "name": "溪流边的浅脚印", "suggested_affordances": ["observe"]},
                                    {"id": "upstream_coarse_fur", "type": "clue", "name": "上游漂来的兽毛", "suggested_affordances": ["observe"]},
                                    {"id": "boilable_stream_water", "type": "water_source", "name": "需要煮沸的溪水", "suggested_affordances": ["observe", "refill_water"]},
                                ],
                                "clues": ["溪水可以处理后饮用，直接喝仍有风险"],
                            },
                        },
                    ],
                },
                {
                    "target_object_id": "scene:watchtower_interior",
                    "target_aliases": ["哨塔内部", "哨塔", "旧火堆", "地基缝隙", "避风角落"],
                    "scene_aliases": ["坍塌的石砌哨塔", "旧火堆", "地基缝隙"],
                    "entries": [
                        {
                            "entry_id": "watchtower_camp_findings",
                            "trigger": {"action_type": "search"},
                            "result": {
                                "narration_fact": "你搜索哨塔内部：旧火堆里还有潮湿灰烬，避风角落能挡住一半夜风，地基缝隙却不断透出冷气；墙角的粗硬兽毛说明这里最近有东西停留过。",
                                "reveal_objects": [
                                    {"id": "watchtower_damp_ashes", "type": "clue", "name": "旧火堆里的潮湿灰烬", "suggested_affordances": ["observe"]},
                                    {"id": "watchtower_foundation_cold_air", "type": "clue", "name": "地基缝隙里的冷风", "suggested_affordances": ["observe"]},
                                    {"id": "watchtower_sheltered_corner", "type": "shelter", "name": "能挡住夜风的避风角落", "suggested_affordances": ["observe", "secure_shelter"]},
                                    {"id": "watchtower_coarse_fur", "type": "clue", "name": "墙角里的粗硬兽毛", "suggested_affordances": ["observe"]},
                                ],
                                "clues": ["哨塔能临时避风，但墙体缺口和兽毛说明夜里并不完全安全"],
                            },
                        }
                    ],
                },
            ],
        }
