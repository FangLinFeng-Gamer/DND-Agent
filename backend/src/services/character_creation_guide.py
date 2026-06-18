from __future__ import annotations

from typing import Any

from backend.src.agent.character_creation.derived.spellcasting import (
    can_add_spell_selection,
    spell_selection_requirements,
    valid_partial_spell_ids,
)
from backend.src.agent.character_creation.rules.abilities import POINT_BUY_COSTS
from backend.src.agent.character_creation.rules.grants import (
    fixed_replaceable_proficiency_conflicts,
    proficiency_replacement_choice_id,
    replacement_rule_type_for_category,
)
from backend.src.agent.character_creation.rules.prerequisites import (
    validate_prerequisites,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.locale import normalize_locale
from backend.src.schemas.character_creation import (
    ABILITY_NAMES,
    CHARACTER_CREATION_STEPS,
    CharacterCreationGuideOption,
    CharacterCreationGuideOut,
    CharacterCreationGuideStep,
    CharacterCreationSessionOut,
    CharacterDraft,
)


WIZARD_STEPS = CHARACTER_CREATION_STEPS


class CharacterCreationGuideService:
    def __init__(self, repository: PHBRuleRepository | None = None):
        self.repository = repository or PHBRuleRepository.load_builtin()

    def build(
        self,
        session: CharacterCreationSessionOut,
        locale: str,
        validation_errors: list[str] | None = None,
        step: str | None = None,
    ) -> CharacterCreationGuideOut:
        normalized_locale = normalize_locale(locale)
        draft = session.draft
        actual_step = self.active_step(draft)
        editable_steps = self._editable_steps(draft, actual_step)
        active_step = step if step in editable_steps else actual_step
        return CharacterCreationGuideOut(
            session_id=session.id,
            locale=normalized_locale,
            actual_step=actual_step,
            active_step=active_step,
            editable_steps=editable_steps,
            steps=self._steps(draft, active_step, actual_step, normalized_locale),
            options=self._options(draft, active_step, normalized_locale),
            current_value=self._current_value(draft, active_step),
            requirements=self._requirements(draft, active_step, normalized_locale),
            validation_errors=validation_errors or [],
        )

    def active_step(self, draft: CharacterDraft) -> str:
        if not draft.name:
            return "identity"
        if not draft.class_name and not draft.selections.class_id:
            return "class"
        if not draft.race and not draft.selections.race_id:
            return "race"
        if not draft.background or draft.background == "Adventurer":
            return "background"
        if (
            "abilities" not in draft.completed_steps
            or "abilities" in draft.invalid_steps
        ):
            return "abilities"
        if self._needs_proficiencies(draft):
            return "proficiencies"
        if self._needs_class_features(draft):
            return "class_features"
        if self._needs_optional_rules(draft):
            return "optional_rules"
        if self._needs_spells(draft):
            return "spells"
        if self._needs_equipment(draft):
            return "equipment"
        if self._needs_adventure_connection(draft):
            return "adventure_connection"
        return "review"

    def _steps(
        self,
        draft: CharacterDraft,
        active_step: str,
        actual_step: str,
        locale: str,
    ) -> list[CharacterCreationGuideStep]:
        actual_index = WIZARD_STEPS.index(actual_step)
        invalid = set(draft.invalid_steps)
        return [
            CharacterCreationGuideStep(
                id=step,
                label=self._step_label(step, locale),
                status=(
                    "active"
                    if step == active_step
                    else "invalid"
                    if step in invalid
                    else "completed"
                    if step in draft.completed_steps or index < actual_index
                    else "pending"
                ),
            )
            for index, step in enumerate(WIZARD_STEPS)
        ]

    def _options(
        self,
        draft: CharacterDraft,
        active_step: str,
        locale: str,
    ) -> list[CharacterCreationGuideOption]:
        if active_step == "class":
            return self._class_options(draft, locale)
        if active_step == "race":
            return self._race_options(draft, locale)
        if active_step == "background":
            return self._background_options(draft, locale)
        if active_step == "optional_rules":
            return self._feat_options(draft, locale)
        if active_step == "spells":
            return self._spell_options(draft, locale)
        return []

    def _class_options(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[CharacterCreationGuideOption]:
        selected_id = draft.selections.class_id
        options = []
        for record in self.repository.list("class"):
            metadata = record.metadata
            badges = [
                f"d{metadata.get('hit_die')}",
                self._ability_list(metadata.get("primary_abilities", []), locale),
            ]
            if metadata.get("spell_selection"):
                badges.append("施法者" if locale == "zh-CN" else "Spellcaster")
            options.append(
                CharacterCreationGuideOption(
                    id=record.id,
                    title=record.name.for_locale(locale),
                    subtitle=record.description.for_locale(locale),
                    badges=[badge for badge in badges if badge],
                    selected=selected_id == record.id,
                    metadata={
                        "operation": "class",
                        "payload": {"class_id": record.id},
                    },
                )
            )
        return options

    def _race_options(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[CharacterCreationGuideOption]:
        selected_id = draft.selections.subrace_id or draft.selections.race_id
        options = []
        for record in self.repository.list("race"):
            metadata = record.metadata
            badges = [
                self._source_badge(record.source),
                self._speed_badge(metadata),
                self._size_badge(metadata, locale),
                self._darkvision_badge(metadata, locale),
            ]
            options.append(
                CharacterCreationGuideOption(
                    id=record.id,
                    title=record.name.for_locale(locale),
                    subtitle=record.description.for_locale(locale),
                    badges=[badge for badge in badges if badge],
                    selected=selected_id == record.id,
                    metadata={
                        "operation": "race",
                        "payload": {"race_id": record.id},
                    },
                )
            )
        return options

    def _background_options(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[CharacterCreationGuideOption]:
        selected_id = draft.selections.background_id
        options = []
        for record in self.repository.list("background"):
            if record.metadata.get("custom"):
                continue
            badges = [
                self._source_badge(record.source),
                *self._grant_badges(record.grants, locale),
            ]
            options.append(
                CharacterCreationGuideOption(
                    id=record.id,
                    title=record.name.for_locale(locale),
                    subtitle=record.description.for_locale(locale),
                    badges=badges[:5],
                    selected=selected_id == record.id,
                    metadata={
                        "operation": "background",
                        "payload": {"background_id": record.id},
                    },
                )
            )
        return options

    def _spell_options(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[CharacterCreationGuideOption]:
        requirements = spell_selection_requirements(draft, self.repository)
        if not requirements:
            return []
        selected_ids = valid_partial_spell_ids(draft, self.repository)
        option_draft = draft.model_copy(deep=True)
        option_draft.selections.spell_ids = selected_ids
        selected = set(selected_ids)
        options = []
        for record in self.repository.list("spell"):
            if record.id not in selected and not can_add_spell_selection(
                option_draft,
                record.id,
                self.repository,
            ):
                continue
            level = int(record.metadata["level"])
            options.append(
                CharacterCreationGuideOption(
                    id=record.id,
                    title=record.name.for_locale(locale),
                    subtitle=record.description.for_locale(locale),
                    badges=[
                        "戏法" if level == 0 and locale == "zh-CN" else "Cantrip" if level == 0 else "1环" if locale == "zh-CN" else "Level 1",
                        str(record.metadata.get("school") or ""),
                    ],
                    selected=record.id in selected,
                    metadata={
                        "operation": "spells",
                        "payload": {"spell_ids": [record.id]},
                        "level": level,
                        "classes": list(record.metadata.get("classes", [])),
                    },
                )
            )
        return options

    def _current_value(self, draft: CharacterDraft, active_step: str) -> Any:
        if active_step == "identity":
            return {"name": draft.name}
        if active_step == "abilities":
            return draft.abilities.model_dump(mode="json")
        if active_step == "spells":
            return {
                "spell_ids": valid_partial_spell_ids(draft, self.repository)
            }
        if active_step == "optional_rules":
            return {
                "feat_ids": list(draft.selections.feat_ids),
                "choice_values": dict(draft.selections.choice_values),
            }
        if active_step == "equipment":
            return {
                "option_ids": list(draft.selections.equipment_option_ids),
                "inventory": list(draft.inventory),
            }
        if active_step == "adventure_connection":
            return dict(draft.adventure_connection)
        return None

    def _requirements(
        self,
        draft: CharacterDraft,
        active_step: str,
        locale: str,
    ) -> dict[str, Any]:
        if active_step == "identity":
            return {"prompt": "请输入角色名称。" if locale == "zh-CN" else "Enter a character name."}
        if active_step == "abilities":
            return {
                "mode": "point_buy",
                "abilities": list(ABILITY_NAMES),
                "costs": dict(POINT_BUY_COSTS),
                "budget": 27,
                "spent": draft.abilities.point_buy_spent,
                "remaining": draft.abilities.point_buy_remaining,
                "prompt": "使用27点购点分配六项属性。" if locale == "zh-CN" else "Use 27 point-buy points for the six abilities.",
            }
        if active_step == "spells":
            return self._spell_requirements(draft, locale)
        if active_step == "proficiencies":
            return {
                "mode": "choice_groups",
                "choice_groups": self._proficiency_choice_groups(draft, locale),
                "prompt": (
                    "请选择需要的技能、工具或语言熟练项。"
                    if locale == "zh-CN"
                    else "Choose the required skill, tool, or language proficiencies."
                ),
            }
        if active_step == "class_features":
            return {
                "mode": "choice_groups",
                "choice_groups": self._class_feature_choice_groups(draft, locale),
                "prompt": (
                    "请选择一级职业特性选项。"
                    if locale == "zh-CN"
                    else "Choose the required level-one class feature options."
                ),
            }
        if active_step == "optional_rules":
            return self._optional_rule_requirements(draft, locale)
        if active_step == "equipment":
            return self._equipment_requirements(draft, locale)
        if active_step == "adventure_connection":
            return self._adventure_connection_requirements(draft, locale)
        if active_step == "review":
            return self._review_requirements(draft, locale)
        return {}

    def _proficiency_choice_groups(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[dict[str, Any]]:
        groups = []
        blocked = self._fixed_replaceable_proficiencies(draft)
        for rule_id in self._selected_rule_ids(draft):
            record = self.repository.get(rule_id)
            proficiency_choice_ids = {
                grant.target
                for grant in record.grants
                if grant.kind
                in {
                    "skill_proficiency_choice",
                    "tool_proficiency_choice",
                    "language_choice",
                    "mixed_proficiency_choice",
                }
            }
            for choice in record.choices:
                if choice.id not in proficiency_choice_ids:
                    continue
                groups.append(
                    {
                        "id": choice.id,
                        "title": choice.name.for_locale(locale),
                        "minimum": choice.minimum,
                        "maximum": choice.maximum,
                        "selected": list(
                            draft.selections.choice_values.get(choice.id, [])
                        ),
                        "options": [
                            self._choice_option(
                                option_id,
                                locale,
                                disabled=option_id
                                in blocked.get(
                                    self.repository.get(option_id).rule_type,
                                    set(),
                                ),
                            )
                            for option_id in choice.option_ids
                        ],
                        "source": record.id,
                    }
                )
        groups.extend(
            self._proficiency_replacement_choice_groups(draft, locale, blocked)
        )
        return groups

    def _proficiency_replacement_choice_groups(
        self,
        draft: CharacterDraft,
        locale: str,
        blocked: dict[str, set[str]],
    ) -> list[dict[str, Any]]:
        groups = []
        for conflict in fixed_replaceable_proficiency_conflicts(
            self._selected_rule_ids(draft),
            self.repository,
        ):
            rule_type = replacement_rule_type_for_category(conflict.category)
            choice_id = proficiency_replacement_choice_id(
                conflict.category,
                conflict.target,
            )
            target = self.repository.get(conflict.target)
            required = max(1, len(conflict.sources) - 1)
            groups.append(
                {
                    "id": choice_id,
                    "title": self._replacement_choice_title(target, locale),
                    "minimum": required,
                    "maximum": required,
                    "selected": list(
                        draft.selections.choice_values.get(choice_id, [])
                    ),
                    "options": [
                        self._choice_option(
                            option.id,
                            locale,
                            disabled=option.id in blocked.get(rule_type, set()),
                        )
                        for option in self.repository.list(rule_type)
                    ],
                    "source": "proficiency_replacement",
                    "replacement_for": conflict.target,
                }
            )
        return groups

    def _replacement_choice_title(self, target, locale: str) -> str:
        name = target.name.for_locale(locale)
        if locale == "zh-CN":
            return f"替换重复的{name}"
        return f"Replace duplicate {name}"

    def _choice_option(
        self,
        option_id: str,
        locale: str,
        *,
        disabled: bool = False,
    ) -> dict[str, Any]:
        record = self.repository.get(option_id)
        option = {
            "id": record.id,
            "title": record.name.for_locale(locale),
            "description": record.description.for_locale(locale),
            "rule_type": record.rule_type,
        }
        if disabled:
            option["disabled"] = True
            option["disabled_reason"] = (
                "已由其他来源获得。"
                if locale == "zh-CN"
                else "Already granted by another source."
            )
        return option

    def _class_feature_choice_groups(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[dict[str, Any]]:
        if not draft.selections.class_id:
            return []
        record = self.repository.get(draft.selections.class_id)
        class_feature_choice_ids = {
            grant.target
            for grant in record.grants
            if grant.kind == "class_option_choice"
        }
        groups = []
        for choice in record.choices:
            if choice.id not in class_feature_choice_ids:
                continue
            groups.append(
                {
                    "id": choice.id,
                    "title": choice.name.for_locale(locale),
                    "minimum": choice.minimum,
                    "maximum": choice.maximum,
                    "selected": list(
                        draft.selections.choice_values.get(choice.id, [])
                    ),
                    "options": [
                        self._choice_option(option_id, locale)
                        for option_id in choice.option_ids
                    ],
                    "source": record.id,
                }
            )
        return groups

    def _feat_options(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[CharacterCreationGuideOption]:
        selected = set(draft.selections.feat_ids)
        options = []
        for record in self.repository.list("feat"):
            disabled = False
            reason = ""
            try:
                validate_prerequisites(record, draft, self.repository)
            except ValueError as exc:
                disabled = True
                reason = str(exc)
            badges = [self._source_badge(record.source)]
            if record.choices:
                badges.append("choices")
            if record.prerequisites:
                badges.append("prerequisite")
            options.append(
                CharacterCreationGuideOption(
                    id=record.id,
                    title=record.name.for_locale(locale),
                    subtitle=record.description.for_locale(locale),
                    badges=[badge for badge in badges if badge],
                    selected=record.id in selected,
                    disabled=disabled,
                    metadata={
                        "operation": "optional_rules",
                        "payload": {"feat_ids": [record.id]},
                        "disabled_reason": reason,
                        "choice_groups": [
                            choice.id for choice in record.choices
                        ],
                    },
                )
            )
        return options

    def _optional_rule_requirements(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> dict[str, Any]:
        choice_groups = []
        for feat_id in draft.selections.feat_ids:
            feat = self.repository.get(feat_id)
            for choice in feat.choices:
                choice_groups.append(
                    {
                        "id": choice.id,
                        "title": choice.name.for_locale(locale),
                        "minimum": choice.minimum,
                        "maximum": choice.maximum,
                        "selected": list(
                            draft.selections.choice_values.get(choice.id, [])
                        ),
                        "options": [
                            self._choice_option(option_id, locale)
                            for option_id in choice.option_ids
                        ],
                        "source": feat.id,
                    }
                )
        return {
            "mode": "optional_rules",
            "feat_slots": self._feat_capacity(draft),
            "selected_feat_ids": list(draft.selections.feat_ids),
            "choice_groups": choice_groups,
            "prompt": (
                "Choose any feat granted by optional rules."
                if locale == "en"
                else "选择可选规则授予的专长。"
            ),
        }

    def _equipment_requirements(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> dict[str, Any]:
        packages = self._starting_equipment_packages(draft)
        choice_groups = []
        item_choice_groups = []
        fixed_items = []
        for package in packages:
            source = str(package.metadata.get("owner_id") or package.id)
            fixed_items.extend(
                self._equipment_item(item_id, quantity, locale)
                for item_id, quantity in package.metadata.get("fixed", [])
            )
            for selector in package.metadata.get("selectors", []):
                item_choice_groups.append(
                    self._equipment_selector_group(selector, source, locale)
                )
            for group in package.metadata.get("choice_groups", []):
                option_ids = {option["id"] for option in group.get("options", [])}
                options = []
                for option in group.get("options", []):
                    options.append(
                        {
                            "id": option["id"],
                            "title": self._title_from_id(option["id"]),
                            "description": self._equipment_option_description(
                                option,
                                locale,
                            ),
                            "selected": option["id"]
                            in draft.selections.equipment_option_ids,
                            "grants": [
                                self._equipment_item(item_id, quantity, locale)
                                for item_id, quantity in option.get("grants", [])
                            ],
                            "selectors": [
                                self._equipment_selector_group(
                                    selector,
                                    option["id"],
                                    locale,
                                )
                                for selector in option.get("selectors", [])
                            ],
                        }
                    )
                choice_groups.append(
                    {
                        "id": group["id"],
                        "title": self._title_from_id(group["id"]),
                        "minimum": 1,
                        "maximum": 1,
                        "selected": [
                            option_id
                            for option_id in draft.selections.equipment_option_ids
                            if option_id in option_ids
                        ],
                        "options": options,
                        "source": source,
                    }
                )
        return {
            "mode": "equipment",
            "fixed_items": fixed_items,
            "choice_groups": choice_groups,
            "item_choice_groups": item_choice_groups,
            "selected_option_ids": list(draft.selections.equipment_option_ids),
            "inventory": list(draft.inventory),
            "prompt": (
                "Choose starting equipment from your class and background."
                if locale == "en"
                else "选择职业和背景提供的起始装备。"
            ),
        }

    def _adventure_connection_requirements(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> dict[str, Any]:
        labels = {
            "en": {
                "motivation": "Motivation",
                "quest_hook": "Quest Hook",
                "npc_relation": "NPC Relation",
                "prior_knowledge": "Prior Knowledge",
            },
            "zh-CN": {
                "motivation": "动机",
                "quest_hook": "任务钩子",
                "npc_relation": "NPC 关系",
                "prior_knowledge": "已知线索",
            },
        }
        active_labels = labels.get(locale, labels["en"])
        return {
            "mode": "adventure_connection",
            "fields": [
                {
                    "id": field_id,
                    "label": active_labels[field_id],
                    "value": draft.adventure_connection.get(field_id, ""),
                }
                for field_id in (
                    "motivation",
                    "quest_hook",
                    "npc_relation",
                    "prior_knowledge",
                )
            ],
            "prompt": (
                "Connect the character to the opening adventure."
                if locale == "en"
                else "将角色和开场冒险建立关联。"
            ),
        }

    def _review_requirements(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> dict[str, Any]:
        return {
            "mode": "review",
            "can_confirm": True,
            "summary": {
                "name": draft.name,
                "race": self._localized_rule_name(
                    draft.selections.subrace_id or draft.selections.race_id,
                    draft.race,
                    locale,
                ),
                "class_name": self._localized_rule_name(
                    draft.selections.class_id,
                    draft.class_name,
                    locale,
                ),
                "background": self._localized_rule_name(
                    draft.selections.background_id,
                    draft.background,
                    locale,
                ),
                "abilities": draft.abilities.model_dump(mode="json"),
                "derived": draft.derived.model_dump(mode="json"),
                "proficiencies": draft.proficiencies,
                "inventory": self._localized_inventory(draft.inventory, locale),
                "spells": list(draft.selections.spell_ids),
                "feats": list(draft.selections.feat_ids),
                "adventure_connection": dict(draft.adventure_connection),
            },
            "prompt": (
                "Review the final derived sheet before confirmation."
                if locale == "en"
                else "确认前检查最终角色卡。"
            ),
        }

    def _spell_requirements(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> dict[str, Any]:
        requirements = spell_selection_requirements(draft, self.repository)
        if not requirements:
            return {}
        cantrips = sum(
            requirement.count
            for requirement in requirements
            if requirement.level == 0
        )
        level_one = sum(
            requirement.count
            for requirement in requirements
            if requirement.level == 1
        )
        selected_records = [
            self.repository.get(spell_id)
            for spell_id in valid_partial_spell_ids(draft, self.repository)
        ]
        selected_cantrips = sum(
            spell.metadata.get("level") == 0 for spell in selected_records
        )
        selected_level_one = sum(
            spell.metadata.get("level") == 1 for spell in selected_records
        )
        if locale == "zh-CN":
            prompt = f"当前角色需要选择 {cantrips} 个戏法和 {level_one} 个1环法术。"
        else:
            prompt = f"This character must select {cantrips} cantrips and {level_one} level-one spells."
        return {
            "mode": "requirements",
            "cantrips": cantrips,
            "level_one": level_one,
            "selected_cantrips": selected_cantrips,
            "selected_level_one": selected_level_one,
            "spell_requirements": [
                requirement.model_dump() for requirement in requirements
            ],
            "prompt": prompt,
        }

    def _equipment_item(
        self,
        item_id: str,
        quantity: int,
        locale: str,
    ) -> dict[str, Any]:
        item = self.repository.get(item_id)
        return {
            "id": item.id,
            "title": item.name.for_locale(locale),
            "description": item.description.for_locale(locale),
            "quantity": int(quantity),
            "tags": list(item.tags),
        }

    def _localized_rule_name(
        self,
        rule_id: str | None,
        fallback: str,
        locale: str,
    ) -> str:
        if not rule_id:
            return fallback
        try:
            return self.repository.get(rule_id).name.for_locale(locale)
        except LookupError:
            return fallback

    def _localized_inventory(
        self,
        inventory: list[dict[str, Any]],
        locale: str,
    ) -> list[dict[str, Any]]:
        localized: list[dict[str, Any]] = []
        for entry in inventory:
            item_id = str(entry.get("item_id") or entry.get("id") or "")
            quantity = int(entry.get("quantity") or 1)
            enriched = dict(entry)
            enriched["quantity"] = quantity
            if item_id:
                enriched["item_id"] = item_id
                try:
                    item = self.repository.get(item_id)
                except LookupError:
                    enriched.setdefault("title", item_id)
                else:
                    enriched["id"] = item.id
                    enriched["title"] = item.name.for_locale(locale)
                    enriched["description"] = item.description.for_locale(locale)
                    enriched["tags"] = list(item.tags)
            localized.append(enriched)
        return localized

    def _equipment_selector_group(
        self,
        selector: dict[str, Any],
        source: str,
        locale: str,
    ) -> dict[str, Any]:
        required_tags = set(selector.get("tags", []))
        options = [
            self._choice_option(record.id, locale)
            for record in self.repository.list("equipment")
            if required_tags <= set(record.tags)
        ]
        return {
            "id": selector["id"],
            "title": self._title_from_id(selector["id"]),
            "minimum": int(selector.get("count", 1)),
            "maximum": int(selector.get("count", 1)),
            "selected": [],
            "options": options,
            "source": source,
            "tags": sorted(required_tags),
        }

    def _equipment_option_description(
        self,
        option: dict[str, Any],
        locale: str,
    ) -> str:
        grants = [
            self.repository.get(item_id).name.for_locale(locale)
            for item_id, _ in option.get("grants", [])
        ]
        selectors = [
            self._title_from_id(selector["id"])
            for selector in option.get("selectors", [])
        ]
        return ", ".join([*grants, *selectors])

    def _starting_equipment_packages(self, draft: CharacterDraft) -> list:
        owner_ids = {
            rule_id
            for rule_id in (draft.selections.class_id, draft.selections.background_id)
            if rule_id
        }
        return [
            record
            for record in self.repository.list("equipment_option")
            if record.metadata.get("owner_id") in owner_ids
        ]

    def _title_from_id(self, value: str) -> str:
        return value.replace("-", " ").replace("_", " ").title()

    def _feat_capacity(self, draft: CharacterDraft) -> int:
        capacity = 0
        for rule_id in self._selected_rule_ids(draft):
            for grant in self.repository.get(rule_id).grants:
                if grant.kind == "feat_choice":
                    capacity += int(grant.value)
        return capacity

    def _needs_spells(self, draft: CharacterDraft) -> bool:
        return bool(
            spell_selection_requirements(draft, self.repository)
            and ("spells" not in draft.completed_steps or "spells" in draft.invalid_steps)
        )

    def _needs_optional_rules(self, draft: CharacterDraft) -> bool:
        return bool(
            self._feat_capacity(draft) > 0
            and (
                "optional_rules" not in draft.completed_steps
                or "optional_rules" in draft.invalid_steps
            )
        )

    def _needs_equipment(self, draft: CharacterDraft) -> bool:
        return bool(
            self._starting_equipment_packages(draft)
            and (
                "equipment" not in draft.completed_steps
                or "equipment" in draft.invalid_steps
            )
        )

    def _needs_adventure_connection(self, draft: CharacterDraft) -> bool:
        return bool(
            "adventure_connection" not in draft.completed_steps
            or "adventure_connection" in draft.invalid_steps
        )

    def _needs_proficiencies(self, draft: CharacterDraft) -> bool:
        return bool(
            self._proficiency_choice_groups(draft, "en")
            and (
                "proficiencies" not in draft.completed_steps
                or "proficiencies" in draft.invalid_steps
            )
        )

    def _needs_class_features(self, draft: CharacterDraft) -> bool:
        return bool(
            self._class_feature_choice_groups(draft, "en")
            and (
                "class_features" not in draft.completed_steps
                or "class_features" in draft.invalid_steps
            )
        )

    def _selected_rule_ids(self, draft: CharacterDraft) -> list[str]:
        return [
            rule_id
            for rule_id in (
                draft.selections.race_id,
                draft.selections.subrace_id,
                draft.selections.class_id,
                draft.selections.background_id,
                *draft.selections.class_option_ids,
                *draft.selections.feat_ids,
            )
            if rule_id
        ]

    def _fixed_replaceable_proficiencies(
        self,
        draft: CharacterDraft,
    ) -> dict[str, set[str]]:
        values = {"skill": set(), "tool": set(), "language": set()}
        for rule_id in self._selected_rule_ids(draft):
            rule = self.repository.get(rule_id)
            for grant in rule.grants:
                if grant.kind == "skill_proficiency":
                    values["skill"].add(grant.target)
                if grant.kind == "tool_proficiency":
                    values["tool"].add(grant.target)
                if grant.kind == "language":
                    values["language"].add(grant.target)
        return values

    def _editable_steps(
        self,
        draft: CharacterDraft,
        actual_step: str,
    ) -> list[str]:
        actual_index = WIZARD_STEPS.index(actual_step)
        completed = set(draft.completed_steps)
        invalid = set(draft.invalid_steps)
        return [
            step
            for index, step in enumerate(WIZARD_STEPS)
            if step != "review"
            and (
                step == actual_step
                or step in completed
                or (step in invalid and index <= actual_index)
            )
        ]

    def _step_label(self, step: str, locale: str) -> str:
        labels = {
            "zh-CN": {
                "identity": "名称",
                "class": "职业",
                "race": "种族",
                "background": "背景",
                "abilities": "属性",
                "proficiencies": "熟练项",
                "class_features": "职业特性",
                "optional_rules": "可选规则",
                "spells": "法术",
                "equipment": "装备",
                "adventure_connection": "冒险关联",
                "review": "确认",
            },
            "en": {
                "identity": "Name",
                "class": "Class",
                "race": "Race",
                "background": "Background",
                "abilities": "Abilities",
                "proficiencies": "Proficiencies",
                "class_features": "Class Features",
                "optional_rules": "Optional Rules",
                "spells": "Spells",
                "equipment": "Equipment",
                "adventure_connection": "Adventure Hook",
                "review": "Review",
            },
        }
        return labels[locale][step]

    def _ability_list(self, ability_ids: list[str], locale: str) -> str:
        return "、".join(self._ability_name(ability, locale) for ability in ability_ids)

    def _ability_name(self, ability: str, locale: str) -> str:
        zh = {
            "strength": "力量",
            "dexterity": "敏捷",
            "constitution": "体质",
            "intelligence": "智力",
            "wisdom": "感知",
            "charisma": "魅力",
        }
        return zh.get(ability, ability) if locale == "zh-CN" else ability.title()

    def _source_badge(self, source: str) -> str:
        return source.replace(" 2014", "")

    def _speed_badge(self, metadata: dict[str, Any]) -> str:
        speed = metadata.get("speed")
        return f"{speed} ft" if speed else ""

    def _size_badge(self, metadata: dict[str, Any], locale: str) -> str:
        size = metadata.get("size")
        if not size:
            return ""
        if locale == "zh-CN":
            return {"small": "小型", "medium": "中型"}.get(size, str(size))
        return str(size).title()

    def _darkvision_badge(self, metadata: dict[str, Any], locale: str) -> str:
        value = metadata.get("darkvision")
        if not value:
            return ""
        return f"黑暗视觉 {value}尺" if locale == "zh-CN" else f"Darkvision {value} ft"

    def _grant_badges(self, grants, locale: str) -> list[str]:
        badges = []
        for grant in grants:
            if grant.kind == "skill_proficiency":
                badges.append(self._record_name(grant.target, locale))
            elif grant.kind == "language_choice":
                badges.append("语言选择" if locale == "zh-CN" else "Language choice")
            elif grant.kind == "tool_proficiency":
                badges.append(self._record_name(grant.target, locale))
        return badges

    def _record_name(self, rule_id: str, locale: str) -> str:
        try:
            return self.repository.get(rule_id).name.for_locale(locale)
        except LookupError:
            return rule_id
