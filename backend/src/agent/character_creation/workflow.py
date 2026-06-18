from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.src.agent.character_creation.deterministic import (
    CORE_FIELDS,
    basic_draft_issues,
    changed_core_fields,
    format_basic_issue,
    invalidate_changed_dependencies,
    localize_validation_error,
)
from backend.src.agent.character_creation.models import StateGraphResult
from backend.src.agent.character_creation.derived.spellcasting import (
    calculate_spellcasting,
    spell_selection_requirements,
    validate_spell_selection,
)
from backend.src.agent.character_creation.rules.abilities import calculate_abilities
from backend.src.agent.character_creation.rules.grants import (
    fixed_replaceable_proficiency_conflicts,
    resolve_grants,
)
from backend.src.agent.character_creation.rules.draft_service import (
    CharacterDraftRulesService,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.agent.character_creation.slots import (
    first_missing_step,
    mark_completed_steps,
    missing_required_slots,
)
from backend.src.agent.locale import normalize_locale
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character import CharacterDraftCommit
from backend.src.schemas.character_creation import (
    ABILITY_NAMES,
    CHARACTER_CREATION_STEPS,
    CharacterDraft,
)
from backend.src.services.characters import CharacterCommitConflict, CharacterService


Operation = Literal["read", "apply", "validate", "confirm"]
ACTIONABLE_WORKFLOW_STEPS = {
    "identity",
    "class",
    "race",
    "background",
    "abilities",
    "proficiencies",
    "class_features",
    "optional_rules",
    "spells",
    "equipment",
    "adventure_connection",
}

STRUCTURED_OPERATION_STEPS = ACTIONABLE_WORKFLOW_STEPS


class CharacterWorkflowState(TypedDict, total=False):
    operation: Operation
    draft: CharacterDraft
    original_draft: CharacterDraft
    expected_revision: int
    locale: str
    changes: dict[str, Any]
    explicit_confirmation: bool
    commit_key: str | None
    changed_fields: list[str]
    validation_errors: list[str]
    validation_warnings: list[str]
    next_step: str
    success: bool
    committed: bool
    created_character_id: int | None
    facts: list[str]
    allowed_actions: list[str]
    revision_conflict: bool
    result: StateGraphResult


class CharacterCreationStateGraph:
    """Deterministic character draft operations exposed to agent tools."""

    def __init__(self, store: SQLiteStore):
        self.characters = CharacterService(store)
        self.rules = PHBRuleRepository.load_builtin()
        self.draft_rules = CharacterDraftRulesService(self.rules)
        self.graph = self._build_graph()

    def read(
        self,
        *,
        draft: CharacterDraft,
        expected_revision: int,
        locale: str = "en",
    ) -> StateGraphResult:
        return self._invoke("read", draft, expected_revision, locale)

    def apply_changes(
        self,
        *,
        draft: CharacterDraft,
        expected_revision: int,
        changes: dict[str, Any],
        locale: str = "en",
    ) -> StateGraphResult:
        return self._invoke(
            "apply",
            draft,
            expected_revision,
            locale,
            changes=changes,
        )

    def validate(
        self,
        *,
        draft: CharacterDraft,
        expected_revision: int,
        locale: str = "en",
    ) -> StateGraphResult:
        return self._invoke("validate", draft, expected_revision, locale)

    def confirm(
        self,
        *,
        draft: CharacterDraft,
        expected_revision: int,
        locale: str = "en",
        explicit_confirmation: bool,
        commit_key: str | None = None,
    ) -> StateGraphResult:
        return self._invoke(
            "confirm",
            draft,
            expected_revision,
            locale,
            explicit_confirmation=explicit_confirmation,
            commit_key=commit_key,
        )

    def _invoke(
        self,
        operation: Operation,
        draft: CharacterDraft,
        expected_revision: int,
        locale: str,
        *,
        changes: dict[str, Any] | None = None,
        explicit_confirmation: bool = False,
        commit_key: str | None = None,
    ) -> StateGraphResult:
        original = draft.model_copy(deep=True)
        state = self.graph.invoke(
            {
                "operation": operation,
                "draft": original.model_copy(deep=True),
                "original_draft": original,
                "expected_revision": expected_revision,
                "locale": normalize_locale(locale),
                "changes": changes or {},
                "explicit_confirmation": explicit_confirmation,
                "commit_key": commit_key,
                "changed_fields": [],
                "validation_errors": [],
                "validation_warnings": [],
                "success": True,
                "committed": False,
                "created_character_id": None,
                "facts": [],
                "allowed_actions": [],
                "revision_conflict": False,
            }
        )
        return state["result"]

    def _build_graph(self):
        graph = StateGraph(CharacterWorkflowState)
        graph.add_node("check_revision", self._check_revision)
        graph.add_node("apply_operation", self._apply_operation)
        graph.add_node("validate_draft", self._validate_draft)
        graph.add_node("commit_character", self._commit_character)
        graph.add_node("build_result", self._build_result)
        graph.add_edge(START, "check_revision")
        graph.add_conditional_edges(
            "check_revision",
            self._route_after_revision,
            {"continue": "apply_operation", "result": "build_result"},
        )
        graph.add_edge("apply_operation", "validate_draft")
        graph.add_conditional_edges(
            "validate_draft",
            self._route_after_validation,
            {"commit": "commit_character", "result": "build_result"},
        )
        graph.add_edge("commit_character", "build_result")
        graph.add_edge("build_result", END)
        return graph.compile(name="character_creation_state_graph")

    def _check_revision(self, state: CharacterWorkflowState) -> dict[str, Any]:
        # This compares the supplied authoritative snapshot only. Session-row
        # database CAS is intentionally handled by the session persistence layer.
        draft = state["draft"]
        if state["expected_revision"] == draft.revision:
            return {}
        return {
            "success": False,
            "revision_conflict": True,
            "validation_errors": [
                (
                    f"Expected revision {state['expected_revision']}, "
                    f"but the draft is revision {draft.revision}."
                )
            ],
            "allowed_actions": ["get_draft"],
            "facts": ["The draft changed before this operation was applied."],
        }

    def _route_after_revision(self, state: CharacterWorkflowState) -> str:
        return "result" if state.get("revision_conflict") else "continue"

    def _apply_operation(self, state: CharacterWorkflowState) -> dict[str, Any]:
        if state["operation"] != "apply":
            return {}
        original = state["original_draft"]
        candidate = original.model_copy(deep=True)
        try:
            changed_fields = self._apply_structured_changes(
                candidate,
                state["changes"],
                state["locale"],
            )
        except (LookupError, TypeError, ValueError) as exc:
            return {
                "draft": original.model_copy(deep=True),
                "success": False,
                "changed_fields": [],
                "validation_errors": [
                    localize_validation_error(str(exc), state["locale"])
                ],
                "facts": ["No draft changes were applied."],
                "allowed_actions": ["update", "ask_rules"],
            }
        if changed_fields:
            candidate.revision += 1
        return {
            "draft": candidate,
            "changed_fields": changed_fields,
            "facts": [
                f"Updated character draft fields: {', '.join(changed_fields)}."
            ]
            if changed_fields
            else ["The submitted values already match the character draft."],
        }

    def _validate_draft(self, state: CharacterWorkflowState) -> dict[str, Any]:
        draft = state["draft"].model_copy(deep=True)
        errors = list(state.get("validation_errors", []))
        if state.get("success", True):
            errors.extend(self._core_validation_errors(draft))

        self._prune_inactive_invalid_steps(draft)
        next_step = self._next_step(draft)
        if state["operation"] == "apply" and state.get("success", True):
            mark_completed_steps(draft, next_step)
        elif state["operation"] == "confirm":
            errors.extend(
                self._recalculate_ability_errors(draft, state["locale"])
            )
            commit_key = state.get("commit_key")
            missing_commit_key = (
                not isinstance(commit_key, str) or not commit_key.strip()
            )
            if missing_commit_key:
                errors.append(
                    "A non-empty commit_key is required for character confirmation."
                )
            if draft.current_step == "completed":
                errors.append("Character creation has already been completed.")
            elif draft.current_step != "review":
                errors.append("Character draft must be on the review step.")
            blocking_steps = [
                step
                for step in draft.invalid_steps
                if step != "review" and step in ACTIONABLE_WORKFLOW_STEPS
            ]
            if blocking_steps:
                errors.append(
                    "Resolve invalidated steps before confirmation: "
                    + ", ".join(blocking_steps)
                    + "."
                )
            if not state["explicit_confirmation"]:
                errors.append("Explicit confirmation is required.")
            if next_step != "review":
                errors.append(
                    f"Character draft is not ready for confirmation; next step is {next_step}."
                )

        warnings = [
            warning
            for values in draft.validation_warnings_by_step.values()
            for warning in values
        ]
        operation_succeeded = state.get("success", True)
        if state["operation"] in {"validate", "confirm"}:
            operation_succeeded = operation_succeeded and not errors
        return {
            "draft": draft,
            "next_step": next_step,
            "validation_errors": errors,
            "validation_warnings": warnings,
            "success": operation_succeeded,
            "allowed_actions": (
                ["confirm", "get_draft"]
                if state["operation"] == "confirm" and missing_commit_key
                else self._allowed_actions(
                    state["operation"],
                    next_step,
                    errors,
                )
            ),
        }

    def _route_after_validation(self, state: CharacterWorkflowState) -> str:
        if (
            state["operation"] == "confirm"
            and state.get("success", False)
            and state["explicit_confirmation"]
            and state["next_step"] == "review"
        ):
            return "commit"
        return "result"

    def _commit_character(self, state: CharacterWorkflowState) -> dict[str, Any]:
        draft = state["draft"].model_copy(deep=True)
        scores = draft.abilities.final
        hp_max = draft.derived.hp_max or 10
        character_data = CharacterDraftCommit(
            draft_revision=draft.revision,
            name=draft.name,
            race=draft.race,
            class_name=draft.class_name,
            background=draft.background,
            alignment=draft.alignment,
            hp_current=hp_max,
            hp_max=hp_max,
            armor_class=draft.derived.armor_class or 12,
            strength=scores["strength"],
            dexterity=scores["dexterity"],
            constitution=scores["constitution"],
            intelligence=scores["intelligence"],
            wisdom=scores["wisdom"],
            charisma=scores["charisma"],
            skills=draft.derived.skills,
            proficiencies=draft.proficiencies,
            inventory=draft.inventory,
            spells=draft.selections.spell_ids,
            notes=draft.notes,
        )
        commit_key = state["commit_key"].strip()
        try:
            character = self.characters.create_idempotent(
                character_data,
                commit_key,
            )
        except CharacterCommitConflict as exc:
            return {
                "success": False,
                "committed": False,
                "created_character_id": None,
                "validation_errors": [str(exc)],
                "facts": ["Character confirmation was rejected."],
                "allowed_actions": ["get_draft", "confirm"],
            }
        draft.revision += 1
        draft.current_step = "completed"
        if "review" not in draft.completed_steps:
            draft.completed_steps.append("review")
        return {
            "draft": draft,
            "next_step": "completed",
            "committed": True,
            "created_character_id": character.id,
            "facts": [
                *state.get("facts", []),
                f"Created character {character.name} with id {character.id}.",
            ],
            "allowed_actions": [],
        }

    def _build_result(self, state: CharacterWorkflowState) -> dict[str, Any]:
        draft = state["draft"]
        next_step = state.get("next_step") or self._next_step(draft)
        result = StateGraphResult(
            success=state.get("success", True),
            draft_revision=draft.revision,
            changed_fields=state.get("changed_fields", []),
            current_step=draft.current_step,
            next_step=next_step,
            validation_errors=state.get("validation_errors", []),
            validation_warnings=state.get("validation_warnings", []),
            created_character_id=state.get("created_character_id"),
            committed=state.get("committed", False),
            facts=state.get("facts", []),
            allowed_actions=state.get("allowed_actions", []),
            draft=draft,
        )
        return {"result": result}

    def _apply_structured_changes(
        self,
        draft: CharacterDraft,
        changes: dict[str, Any],
        locale: str,
    ) -> list[str]:
        if self._is_step_operation_changes(changes):
            return self._apply_step_operation_changes(draft, changes, locale)

        unsupported = set(changes) - {
            *CORE_FIELDS,
            "abilities",
            "proficiencies",
            "class_features",
            "spells",
            "optional_rules",
            "equipment",
            "adventure_connection",
        }
        if unsupported:
            raise ValueError(
                "Unsupported character draft fields: "
                + ", ".join(sorted(unsupported))
                + "."
            )
        before = draft.model_copy(deep=True)
        completed_fields: list[str] = []
        for field in ("name", "alignment", "notes"):
            if field in changes:
                setattr(draft, field, str(changes[field]).strip())
                completed_fields.append(field)
        if "race" in changes:
            previous_race_id = draft.selections.race_id
            previous_subrace_id = draft.selections.subrace_id
            race = self._canonical_rule(str(changes["race"]), {"race", "subrace"})
            draft.race = race.name.en
            if race.rule_type == "subrace":
                draft.selections.race_id = race.parent_id
                draft.selections.subrace_id = race.id
            else:
                draft.selections.race_id = race.id
                draft.selections.subrace_id = None
            if (
                previous_race_id != draft.selections.race_id
                or previous_subrace_id != draft.selections.subrace_id
            ):
                self._remove_rule_choices(
                    draft,
                    previous_race_id,
                    previous_subrace_id,
                )
            completed_fields.append("race")
        if "class_name" in changes:
            previous_class_id = draft.selections.class_id
            previous_class_option_ids = list(draft.selections.class_option_ids)
            class_rule = self._canonical_rule(
                str(changes["class_name"]),
                {"class"},
            )
            draft.class_name = class_rule.name.en
            draft.selections.class_id = class_rule.id
            if previous_class_id != class_rule.id:
                self._remove_rule_choices(
                    draft,
                    previous_class_id,
                    *previous_class_option_ids,
                )
                draft.selections.class_option_ids = []
                draft.selections.spell_ids = []
                draft.selections.equipment_option_ids = []
                draft.inventory = []
                draft.derived.spellcasting = {}
            completed_fields.append("class_name")
        if "background" in changes:
            previous_background_id = draft.selections.background_id
            background = self._canonical_rule(
                str(changes["background"]),
                {"background"},
            )
            draft.background = background.name.en
            draft.selections.background_id = background.id
            if previous_background_id != background.id:
                self._remove_rule_choices(draft, previous_background_id)
                draft.selections.equipment_option_ids = []
                draft.inventory = []
            completed_fields.append("background")
        if "abilities" in changes:
            ability_payload = changes["abilities"]
            if not isinstance(ability_payload, dict):
                raise ValueError("Abilities must be a mapping of all six scores.")
            self._hydrate_race_selection(draft)
            base = ability_payload.get("base", ability_payload)
            draft.abilities = calculate_abilities(
                {ability: int(base[ability]) for ability in ABILITY_NAMES},
                race_id=draft.selections.race_id,
                subrace_id=draft.selections.subrace_id,
                choice_values=draft.selections.choice_values,
                feat_ids=draft.selections.feat_ids,
                repository=self.rules,
            )
            completed_fields.append("abilities")
        if "proficiencies" in changes:
            self._apply_proficiencies_change(draft, changes["proficiencies"])
            completed_fields.append("proficiencies")
        if "class_features" in changes:
            self._apply_rules_service_change(
                draft,
                "class_features",
                changes["class_features"],
                locale,
            )
            completed_fields.append("class_features")
        if "optional_rules" in changes:
            self._apply_rules_service_change(
                draft,
                "optional_rules",
                changes["optional_rules"],
                locale,
            )
            completed_fields.append("optional_rules")
        if "spells" in changes:
            self._apply_spells_change(draft, changes["spells"])
            completed_fields.append("spells")
        if "equipment" in changes:
            self._apply_rules_service_change(
                draft,
                "equipment",
                changes["equipment"],
                locale,
            )
            completed_fields.append("equipment")
        if "adventure_connection" in changes:
            self._apply_rules_service_change(
                draft,
                "adventure_connection",
                changes["adventure_connection"],
                locale,
            )
            completed_fields.append("adventure_connection")

        changed_fields = changed_core_fields(before, draft)
        if before.abilities != draft.abilities:
            changed_fields.append("abilities")
        if before.proficiencies != draft.proficiencies:
            changed_fields.append("proficiencies")
        if before.selections.class_option_ids != draft.selections.class_option_ids:
            changed_fields.append("class_features")
        if before.selections.feat_ids != draft.selections.feat_ids:
            changed_fields.append("optional_rules")
        if before.selections.spell_ids != draft.selections.spell_ids:
            changed_fields.append("spells")
        if (
            before.inventory != draft.inventory
            or before.selections.equipment_option_ids
            != draft.selections.equipment_option_ids
        ):
            changed_fields.append("equipment")
        if before.adventure_connection != draft.adventure_connection:
            changed_fields.append("adventure_connection")
        invalidate_changed_dependencies(before, draft, changed_fields)
        fields_to_complete = []
        for field in completed_fields:
            if field not in fields_to_complete:
                fields_to_complete.append(field)
        self._mark_changed_steps_complete(draft, fields_to_complete)
        return changed_fields

    def _is_step_operation_changes(self, changes: dict[str, Any]) -> bool:
        if not changes:
            return False
        for key, value in changes.items():
            if key not in STRUCTURED_OPERATION_STEPS or not isinstance(value, dict):
                return False
            if key == "abilities" and "base" not in value:
                return False
        return True

    def _apply_step_operation_changes(
        self,
        draft: CharacterDraft,
        changes: dict[str, Any],
        locale: str,
    ) -> list[str]:
        before = draft.model_copy(deep=True)
        completed_steps: list[str] = []
        for operation, payload in changes.items():
            normalized_payload = dict(payload)
            if operation == "abilities" and "base" not in normalized_payload:
                normalized_payload = {"base": normalized_payload}
            if operation == "spells":
                self._apply_spells_change(draft, normalized_payload)
            else:
                self._apply_rules_service_change(
                    draft,
                    operation,
                    normalized_payload,
                    locale,
                )
            completed_steps.append(operation)

        changed_fields = self._changed_fields_for_steps(before, draft)
        self._mark_changed_steps_complete(draft, completed_steps)
        return changed_fields

    def _changed_fields_for_steps(
        self,
        before: CharacterDraft,
        draft: CharacterDraft,
    ) -> list[str]:
        changed_fields = changed_core_fields(before, draft)
        if before.abilities != draft.abilities:
            changed_fields.append("abilities")
        if before.proficiencies != draft.proficiencies:
            changed_fields.append("proficiencies")
        if before.selections.class_option_ids != draft.selections.class_option_ids:
            changed_fields.append("class_features")
        if before.selections.feat_ids != draft.selections.feat_ids:
            changed_fields.append("optional_rules")
        if before.selections.spell_ids != draft.selections.spell_ids:
            changed_fields.append("spells")
        if (
            before.inventory != draft.inventory
            or before.selections.equipment_option_ids
            != draft.selections.equipment_option_ids
        ):
            changed_fields.append("equipment")
        if before.adventure_connection != draft.adventure_connection:
            changed_fields.append("adventure_connection")
        return changed_fields

    def _apply_spells_change(self, draft: CharacterDraft, payload: Any) -> None:
        if isinstance(payload, dict):
            values = payload.get("spell_ids", [])
        elif isinstance(payload, list):
            values = payload
        else:
            raise ValueError("Spells must be a list or a mapping with spell_ids.")
        spell_ids = [self._canonical_spell_id(str(value)) for value in values]
        self._hydrate_class_selection(draft)
        validate_spell_selection(draft, spell_ids, self.rules, partial=True)
        draft.selections.spell_ids = spell_ids
        if self._spell_selection_complete(draft):
            draft.derived.spellcasting = calculate_spellcasting(
                draft,
                spell_ids,
                self.rules,
            )
        else:
            draft.derived.spellcasting = {}

    def _apply_proficiencies_change(
        self,
        draft: CharacterDraft,
        payload: Any,
    ) -> None:
        if not isinstance(payload, dict):
            raise ValueError("Proficiencies must be a mapping.")
        choice_values = payload.get("choice_values", payload)
        if not isinstance(choice_values, dict):
            raise ValueError("Proficiency choice_values must be a mapping.")
        draft.selections.choice_values.update(
            {
                str(choice_id): [str(value) for value in values]
                for choice_id, values in choice_values.items()
            }
        )
        resolution = resolve_grants(
            self._selected_rule_ids(draft),
            draft.selections.choice_values,
            self.rules,
        )
        if resolution.conflicts:
            conflict = resolution.conflicts[0]
            raise ValueError(
                f"Duplicate {conflict.category} proficiency {conflict.target}; "
                "choose a replacement."
            )
        draft.proficiencies = resolution.proficiencies

    def _apply_rules_service_change(
        self,
        draft: CharacterDraft,
        operation: str,
        payload: dict[str, Any],
        locale: str,
    ) -> None:
        updated = self.draft_rules.mutate(draft, operation, payload, locale)
        for field_name in CharacterDraft.model_fields:
            setattr(draft, field_name, getattr(updated, field_name))

    def _hydrate_race_selection(self, draft: CharacterDraft) -> None:
        if draft.selections.race_id or not draft.race:
            return
        race = self._canonical_rule(draft.race, {"race", "subrace"})
        if race.rule_type == "subrace":
            draft.selections.race_id = race.parent_id
            draft.selections.subrace_id = race.id
        else:
            draft.selections.race_id = race.id
            draft.selections.subrace_id = None

    def _hydrate_class_selection(self, draft: CharacterDraft) -> None:
        if draft.selections.class_id or not draft.class_name:
            return
        draft.selections.class_id = self._canonical_rule(
            draft.class_name,
            {"class"},
        ).id

    def _canonical_rule(self, value: str, rule_types: set[str]):
        normalized = value.strip().casefold()
        for record in self.rules.list():
            if record.rule_type not in rule_types:
                continue
            if normalized in {
                record.id.casefold(),
                record.name.en.casefold(),
                record.name.zh_cn.casefold(),
            }:
                return record
        label = "/".join(sorted(rule_types))
        raise ValueError(f"Unsupported {label}: {value.strip()}.")

    def _canonical_spell_id(self, value: str) -> str:
        normalized = value.strip().casefold()
        for record in self.rules.list("spell"):
            if normalized in {
                record.id.casefold(),
                record.name.en.casefold(),
                record.name.zh_cn.casefold(),
            }:
                return record.id
        raise ValueError(f"Unsupported spell: {value.strip()}.")

    def _remove_rule_choices(
        self,
        draft: CharacterDraft,
        *rule_ids: str | None,
    ) -> None:
        for rule_id in rule_ids:
            if not rule_id:
                continue
            for choice in self.rules.get(rule_id).choices:
                draft.selections.choice_values.pop(choice.id, None)

    def _mark_changed_steps_complete(
        self,
        draft: CharacterDraft,
        changed_fields: list[str],
    ) -> None:
        completed_by_field = {
            "identity": "identity",
            "class": "class",
            "race": "race",
            "background": "background",
            "name": "identity",
            "class_name": "class",
            "abilities": "abilities",
            "proficiencies": "proficiencies",
            "class_features": "class_features",
            "optional_rules": "optional_rules",
            "spells": "spells",
            "equipment": "equipment",
            "adventure_connection": "adventure_connection",
        }
        for field in changed_fields:
            step = completed_by_field.get(field)
            if not step:
                continue
            if field == "spells" and not self._spell_selection_complete(draft):
                draft.completed_steps = [
                    completed
                    for completed in draft.completed_steps
                    if completed != "spells"
                ]
                continue
            if step not in draft.completed_steps:
                draft.completed_steps.append(step)
            if step in draft.invalid_steps:
                draft.invalid_steps.remove(step)

    def _spell_selection_complete(self, draft: CharacterDraft) -> bool:
        try:
            validate_spell_selection(
                draft,
                draft.selections.spell_ids,
                self.rules,
            )
        except (LookupError, ValueError):
            return False
        return True

    def _core_validation_errors(self, draft: CharacterDraft) -> list[str]:
        valid_races = {
            record.name.en
            for record in self.rules.list()
            if record.rule_type in {"race", "subrace"}
        }
        valid_classes = {
            record.name.en
            for record in self.rules.list()
            if record.rule_type == "class"
        }
        valid_backgrounds = {
            record.name.en
            for record in self.rules.list()
            if record.rule_type == "background"
        }
        return [
            format_basic_issue(issue)
            for issue in basic_draft_issues(
                draft,
                valid_races=valid_races,
                valid_classes=valid_classes,
                valid_backgrounds=valid_backgrounds,
            )
        ]

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

    def _recalculate_ability_errors(
        self,
        draft: CharacterDraft,
        locale: str,
    ) -> list[str]:
        try:
            self._hydrate_race_selection(draft)
            draft.abilities = calculate_abilities(
                dict(draft.abilities.base),
                race_id=draft.selections.race_id,
                subrace_id=draft.selections.subrace_id,
                choice_values=draft.selections.choice_values,
                feat_ids=draft.selections.feat_ids,
                repository=self.rules,
            )
        except (KeyError, LookupError, TypeError, ValueError) as exc:
            return [localize_validation_error(str(exc), locale)]
        return []

    def _prune_inactive_invalid_steps(self, draft: CharacterDraft) -> None:
        if not draft.invalid_steps:
            return
        conditional_steps = {
            "proficiencies",
            "class_features",
            "optional_rules",
            "spells",
            "equipment",
            "adventure_connection",
        }
        draft.invalid_steps = [
            step
            for step in draft.invalid_steps
            if step not in conditional_steps
            or self._step_can_be_required(draft, step)
        ]

    def _step_can_be_required(self, draft: CharacterDraft, step: str) -> bool:
        if step == "proficiencies":
            has_choice_grants = any(
                grant.kind
                in {
                    "skill_proficiency_choice",
                    "tool_proficiency_choice",
                    "language_choice",
                    "mixed_proficiency_choice",
                }
                for rule_id in self._selected_rule_ids(draft)
                for grant in self.rules.get(rule_id).grants
            )
            return has_choice_grants or bool(
                fixed_replaceable_proficiency_conflicts(
                    self._selected_rule_ids(draft),
                    self.rules,
                )
            )
        if step == "class_features":
            return bool(
                draft.selections.class_id
                and any(
                    grant.kind == "class_option_choice"
                    for grant in self.rules.get(draft.selections.class_id).grants
                )
            )
        if step == "optional_rules":
            return any(
                grant.kind == "feat_choice"
                for rule_id in self._selected_rule_ids(draft)
                for grant in self.rules.get(rule_id).grants
            )
        if step == "spells":
            return bool(spell_selection_requirements(draft, self.rules))
        if step == "equipment":
            owner_ids = {
                rule_id
                for rule_id in (
                    draft.selections.class_id,
                    draft.selections.background_id,
                )
                if rule_id
            }
            return any(
                record.metadata.get("owner_id") in owner_ids
                for record in self.rules.list("equipment_option")
            )
        if step == "adventure_connection":
            return bool(draft.name or draft.class_name or draft.race)
        return False

    def _next_step(self, draft: CharacterDraft) -> str:
        missing_step, _ = first_missing_step(draft, self.rules)
        if missing_step != "review":
            return missing_step
        ordered_invalid = [
            step
            for step in CHARACTER_CREATION_STEPS
            if (
                step in draft.invalid_steps
                and step != "review"
                and step in ACTIONABLE_WORKFLOW_STEPS
            )
        ]
        return ordered_invalid[0] if ordered_invalid else "review"

    def _allowed_actions(
        self,
        operation: Operation,
        next_step: str,
        errors: list[str],
    ) -> list[str]:
        if errors:
            return ["update", "ask_rules"]
        actions = ["update", "validate", "ask_rules"]
        if next_step == "review":
            actions.insert(0, "confirm")
        if operation == "read":
            actions.insert(0, "get_draft")
        return actions
