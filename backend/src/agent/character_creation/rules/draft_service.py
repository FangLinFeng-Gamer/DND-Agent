from typing import Any

from backend.src.agent.character_creation.derived.sheet import calculate_derived_sheet
from backend.src.agent.character_creation.derived.spellcasting import (
    calculate_spellcasting,
    validate_spell_selection,
)
from backend.src.agent.character_creation.rules.abilities import calculate_abilities
from backend.src.agent.character_creation.rules.choices import validate_rule_choices
from backend.src.agent.character_creation.rules.grants import resolve_grants
from backend.src.agent.character_creation.rules.equipment import (
    resolve_starting_equipment,
)
from backend.src.agent.character_creation.rules.prerequisites import (
    validate_prerequisites,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft


class DraftRevisionConflict(Exception):
    pass


class CharacterDraftRulesService:
    def __init__(self, repository: PHBRuleRepository | None = None):
        self.repository = repository or PHBRuleRepository.load_builtin()

    def mutate(
        self,
        draft: CharacterDraft,
        operation: str,
        payload: dict[str, Any],
        locale: str = "en",
    ) -> CharacterDraft:
        updated = draft.model_copy(deep=True)
        if operation == "identity":
            self._update_identity(updated, payload)
        elif operation == "race":
            self._update_race(updated, payload)
        elif operation == "class":
            self._update_class(updated, payload)
        elif operation == "abilities":
            self._update_abilities(updated, payload, locale)
        elif operation == "background":
            self._update_background(updated, payload)
        elif operation == "proficiencies":
            self._update_proficiencies(updated, payload)
        elif operation == "class_features":
            self._update_class_features(updated, payload)
        elif operation == "optional_rules":
            self._update_optional_rules(updated, payload)
        elif operation == "spells":
            self._update_spells(updated, payload)
        elif operation == "equipment":
            self._update_equipment(updated, payload)
        elif operation == "adventure_connection":
            self._update_adventure_connection(updated, payload)
        else:
            raise ValueError(f"Unsupported character draft operation: {operation}.")
        self._recalculate_derived(updated)
        return updated

    def _update_identity(self, draft: CharacterDraft, payload: dict[str, Any]) -> None:
        for field in ("name", "alignment", "appearance", "notes"):
            if field in payload:
                setattr(draft, field, str(payload[field]).strip())
        if not draft.name:
            raise ValueError("Character name is required.")
        self._complete_step(draft, "identity", "class")

    def _update_race(self, draft: CharacterDraft, payload: dict[str, Any]) -> None:
        race_id = str(payload.get("race_id") or "")
        if not race_id:
            raise ValueError("Race selection is required.")
        race = self.repository.get(race_id)
        if race.rule_type != "race":
            raise ValueError(f"{race_id} is not a base race.")
        previous_race_id = draft.selections.race_id
        previous_subrace_id = draft.selections.subrace_id
        subrace_id = payload.get("subrace_id")
        if subrace_id:
            subrace = self.repository.get(str(subrace_id))
            if subrace.rule_type != "subrace" or subrace.parent_id != race_id:
                raise ValueError(f"{subrace_id} is not a subrace of {race_id}.")
            draft.selections.subrace_id = subrace.id
            draft.race = subrace.name.en
        else:
            draft.selections.subrace_id = None
            draft.race = race.name.en
        draft.selections.race_id = race.id
        self._remove_rule_choices(
            draft,
            previous_race_id,
            previous_subrace_id,
        )
        draft.selections.choice_values.update({
            str(key): [str(value) for value in values]
            for key, values in (payload.get("choice_values") or {}).items()
        })
        draft.abilities = calculate_abilities(
            draft.abilities.base,
            race_id=draft.selections.race_id,
            subrace_id=draft.selections.subrace_id,
            choice_values=draft.selections.choice_values,
            feat_ids=draft.selections.feat_ids,
            repository=self.repository,
        )
        self._prune_invalid_feats(draft)
        self._complete_step(draft, "race", "background")
        self._invalidate_after(draft, "race")

    def _update_class(self, draft: CharacterDraft, payload: dict[str, Any]) -> None:
        class_id = str(payload.get("class_id") or "")
        if not class_id:
            raise ValueError("Class selection is required.")
        class_rule = self.repository.get(class_id)
        if class_rule.rule_type != "class":
            raise ValueError(f"{class_id} is not a class.")
        self._remove_rule_choices(draft, draft.selections.class_id)
        draft.selections.class_id = class_rule.id
        draft.selections.class_option_ids = []
        draft.selections.spell_ids = []
        draft.selections.equipment_option_ids = []
        draft.inventory = []
        draft.derived.spellcasting = {}
        draft.class_name = class_rule.name.en
        self._prune_invalid_feats(draft)
        self._complete_step(draft, "class", "race")
        self._invalidate_after(draft, "class")

    def _update_abilities(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
        locale: str,
    ) -> None:
        try:
            draft.abilities = calculate_abilities(
                {key: int(value) for key, value in payload["base"].items()},
                race_id=draft.selections.race_id,
                subrace_id=draft.selections.subrace_id,
                choice_values=draft.selections.choice_values,
                feat_ids=draft.selections.feat_ids,
                repository=self.repository,
            )
            self._prune_invalid_feats(draft)
        except (KeyError, TypeError, ValueError) as exc:
            if locale == "zh-CN" and "between 8 and 15" in str(exc):
                raise ValueError("购点属性基础值必须在 8 到 15 之间。") from exc
            raise
        self._complete_step(draft, "abilities", "proficiencies")
        self._invalidate_after(draft, "abilities")

    def _update_background(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        background_id = str(payload.get("background_id") or "")
        if not background_id:
            raise ValueError("Background selection is required.")
        background = self.repository.get(background_id)
        if background.rule_type != "background":
            raise ValueError(f"{background_id} is not a background.")
        self._remove_rule_choices(draft, draft.selections.background_id)
        draft.selections.background_id = background.id
        draft.selections.equipment_option_ids = []
        draft.inventory = []
        draft.background = background.name.en
        for field in ("ideal", "bond", "flaw"):
            if field in payload:
                setattr(draft, field, str(payload[field]).strip())
        if "personality_traits" in payload:
            draft.personality_traits = [
                str(value).strip()
                for value in payload["personality_traits"]
                if str(value).strip()
            ]
        self._complete_step(draft, "background", "abilities")
        self._invalidate_after(draft, "background")

    def _update_proficiencies(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        draft.selections.choice_values.update(
            {
                str(key): [str(value) for value in values]
                for key, values in (payload.get("choice_values") or {}).items()
            }
        )
        resolution = resolve_grants(
            self._selected_rule_ids(draft),
            draft.selections.choice_values,
            self.repository,
        )
        if resolution.conflicts:
            conflict = resolution.conflicts[0]
            raise ValueError(
                f"Duplicate {conflict.category} proficiency {conflict.target}; "
                "choose a replacement."
            )
        draft.proficiencies = resolution.proficiencies
        self._complete_step(draft, "proficiencies", "class_features")
        self._invalidate_after(draft, "proficiencies")

    def _update_class_features(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        if not draft.selections.class_id:
            raise ValueError("Choose a class before class features.")
        class_rule = self.repository.get(draft.selections.class_id)
        draft.selections.choice_values.update(
            {
                str(key): [str(value) for value in values]
                for key, values in (payload.get("choice_values") or {}).items()
            }
        )
        validate_rule_choices(
            class_rule,
            {
                choice.id: draft.selections.choice_values[choice.id]
                for choice in class_rule.choices
                if choice.id in draft.selections.choice_values
            },
        )
        option_ids = [str(value) for value in payload.get("class_option_ids", [])]
        allowed_option_ids = {
            option_id
            for choice in class_rule.choices
            for option_id in choice.option_ids
            if option_id.startswith("class_option.")
        }
        if any(option_id not in allowed_option_ids for option_id in option_ids):
            raise ValueError("Class features contain an invalid class option.")
        selected_from_choices = {
            option_id
            for choice in class_rule.choices
            for option_id in draft.selections.choice_values.get(choice.id, [])
            if option_id.startswith("class_option.")
        }
        if set(option_ids) != selected_from_choices:
            raise ValueError("Class option selections do not match choice values.")
        draft.selections.class_option_ids = option_ids
        for option_id in option_ids:
            option = self.repository.get(option_id)
            validate_rule_choices(
                option,
                {
                    choice.id: draft.selections.choice_values[choice.id]
                    for choice in option.choices
                    if choice.id in draft.selections.choice_values
                },
            )
        resolution = resolve_grants(
            self._selected_rule_ids(draft),
            draft.selections.choice_values,
            self.repository,
        )
        if resolution.conflicts:
            conflict = resolution.conflicts[0]
            raise ValueError(
                f"Duplicate {conflict.category} proficiency {conflict.target}; "
                "choose a replacement."
            )
        draft.proficiencies = resolution.proficiencies
        self._complete_step(draft, "class_features", "optional_rules")
        self._invalidate_after(draft, "class_features")

    def _update_optional_rules(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        feat_ids = [str(value) for value in payload.get("feat_ids", [])]
        if len(feat_ids) != len(set(feat_ids)):
            raise ValueError("Feat selections must be distinct.")
        feat_capacity = sum(
            int(grant.value)
            for rule_id in self._selected_rule_ids(draft, include_feats=False)
            for grant in self.repository.get(rule_id).grants
            if grant.kind == "feat_choice"
        )
        if len(feat_ids) > feat_capacity:
            raise ValueError(
                f"This character does not grant {len(feat_ids)} feat selections."
            )
        choice_values = {
            str(key): [str(value) for value in values]
            for key, values in (payload.get("choice_values") or {}).items()
        }
        for previous_feat_id in draft.selections.feat_ids:
            self._remove_rule_choices(draft, previous_feat_id)
        for feat_id in feat_ids:
            feat = self.repository.get(feat_id)
            if feat.rule_type != "feat":
                raise ValueError(f"{feat_id} is not a feat.")
            validate_prerequisites(feat, draft, self.repository)
            validate_rule_choices(
                feat,
                {
                    choice.id: choice_values[choice.id]
                    for choice in feat.choices
                    if choice.id in choice_values
                },
            )
        draft.selections.feat_ids = feat_ids
        draft.selections.choice_values.update(choice_values)
        self._recalculate_abilities(draft)
        resolution = resolve_grants(
            self._selected_rule_ids(draft),
            draft.selections.choice_values,
            self.repository,
        )
        if resolution.conflicts:
            conflict = resolution.conflicts[0]
            raise ValueError(
                f"Duplicate {conflict.category} proficiency {conflict.target}; "
                "choose a replacement."
            )
        draft.proficiencies = resolution.proficiencies
        self._complete_step(draft, "optional_rules", "spells")
        self._invalidate_after(draft, "optional_rules")

    def _update_spells(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        spell_ids = [str(value) for value in payload.get("spell_ids", [])]
        validate_spell_selection(draft, spell_ids, self.repository)
        draft.selections.spell_ids = spell_ids
        draft.derived.spellcasting = calculate_spellcasting(
            draft,
            spell_ids,
            self.repository,
        )
        self._complete_step(draft, "spells", "equipment")
        self._invalidate_after(draft, "spells")

    def _update_equipment(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        option_ids = [str(value) for value in payload.get("option_ids", [])]
        item_choices = {
            str(key): [str(value) for value in values]
            for key, values in (payload.get("item_choices") or {}).items()
        }
        draft.inventory = resolve_starting_equipment(
            class_id=draft.selections.class_id,
            background_id=draft.selections.background_id,
            option_ids=option_ids,
            item_choices=item_choices,
            repository=self.repository,
        )
        draft.selections.equipment_option_ids = option_ids
        self._complete_step(draft, "equipment", "adventure_connection")
        self._invalidate_after(draft, "equipment")

    def _update_adventure_connection(
        self,
        draft: CharacterDraft,
        payload: dict[str, Any],
    ) -> None:
        draft.adventure_connection = {
            str(key): str(value).strip()
            for key, value in payload.items()
            if str(value).strip()
        }
        self._complete_step(draft, "adventure_connection", "review")

    def _prune_invalid_feats(self, draft: CharacterDraft) -> None:
        if not draft.selections.feat_ids:
            return
        capacity = sum(
            int(grant.value)
            for rule_id in self._selected_rule_ids(draft, include_feats=False)
            for grant in self.repository.get(rule_id).grants
            if grant.kind == "feat_choice"
        )
        kept: list[str] = []
        for feat_id in draft.selections.feat_ids[:capacity]:
            try:
                validate_prerequisites(
                    self.repository.get(feat_id),
                    draft,
                    self.repository,
                )
            except ValueError:
                continue
            kept.append(feat_id)
        if kept == draft.selections.feat_ids:
            return
        removed = set(draft.selections.feat_ids) - set(kept)
        for feat_id in removed:
            self._remove_rule_choices(draft, feat_id)
        draft.selections.feat_ids = kept
        draft.completed_steps = [
            step for step in draft.completed_steps if step != "optional_rules"
        ]
        draft.invalid_steps = sorted(
            set(draft.invalid_steps) | {"optional_rules", "spells", "review"}
        )
        self._recalculate_abilities(draft)

    def _recalculate_abilities(self, draft: CharacterDraft) -> None:
        draft.abilities = calculate_abilities(
            draft.abilities.base,
            race_id=draft.selections.race_id,
            subrace_id=draft.selections.subrace_id,
            choice_values=draft.selections.choice_values,
            feat_ids=draft.selections.feat_ids,
            repository=self.repository,
        )

    def _complete_step(
        self,
        draft: CharacterDraft,
        step: str,
        next_step: str,
    ) -> None:
        if step not in draft.completed_steps:
            draft.completed_steps.append(step)
        if step in draft.invalid_steps:
            draft.invalid_steps.remove(step)
        draft.current_step = next_step

    def _invalidate_after(self, draft: CharacterDraft, changed_step: str) -> None:
        dependencies = {
            "race": {
                "proficiencies",
                "class_features",
                "optional_rules",
                "spells",
                "equipment",
                "adventure_connection",
                "review",
            },
            "class": {
                "proficiencies",
                "class_features",
                "optional_rules",
                "spells",
                "equipment",
                "adventure_connection",
                "review",
            },
            "abilities": {"optional_rules", "spells", "review"},
            "background": {"proficiencies", "equipment", "adventure_connection", "review"},
            "proficiencies": {
                "class_features",
                "optional_rules",
                "spells",
                "equipment",
                "adventure_connection",
                "review",
            },
            "class_features": {
                "optional_rules",
                "spells",
                "equipment",
                "adventure_connection",
                "review",
            },
            "optional_rules": {"spells", "equipment", "adventure_connection", "review"},
            "spells": {"review"},
            "equipment": {"adventure_connection", "review"},
        }
        affected = dependencies.get(changed_step, set())
        draft.completed_steps = [
            step for step in draft.completed_steps if step not in affected
        ]
        draft.invalid_steps = sorted(set(draft.invalid_steps) | affected)

    def _selected_rule_ids(
        self,
        draft: CharacterDraft,
        include_feats: bool = True,
    ) -> list[str]:
        feat_ids = draft.selections.feat_ids if include_feats else []
        return [
            rule_id
            for rule_id in (
                draft.selections.race_id,
                draft.selections.subrace_id,
                draft.selections.class_id,
                draft.selections.background_id,
                *draft.selections.class_option_ids,
                *feat_ids,
            )
            if rule_id
        ]

    def _remove_rule_choices(
        self,
        draft: CharacterDraft,
        *rule_ids: str | None,
    ) -> None:
        for rule_id in rule_ids:
            if not rule_id:
                continue
            for choice in self.repository.get(rule_id).choices:
                draft.selections.choice_values.pop(choice.id, None)

    def _recalculate_derived(self, draft: CharacterDraft) -> None:
        draft.derived = calculate_derived_sheet(draft, self.repository)
        draft.derived.spellcasting = calculate_spellcasting(
            draft,
            draft.selections.spell_ids,
            self.repository,
        )
        race = (
            self.repository.get(draft.selections.race_id)
            if draft.selections.race_id
            else None
        )
        subrace = (
            self.repository.get(draft.selections.subrace_id)
            if draft.selections.subrace_id
            else None
        )
        if race:
            draft.derived.speed = int(
                (subrace.metadata.get("speed") if subrace else None)
                or race.metadata.get("speed", 30)
            )
        feat_rules = [
            self.repository.get(feat_id)
            for feat_id in draft.selections.feat_ids
        ]
        speed_bonus = sum(
            int(grant.value)
            for rule in feat_rules
            for grant in rule.grants
            if grant.kind == "speed_bonus"
        )
        if draft.derived.speed is not None:
            draft.derived.speed += speed_bonus
