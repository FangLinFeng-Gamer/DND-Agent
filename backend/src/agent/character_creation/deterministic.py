from dataclasses import dataclass
import re
from typing import Any

from backend.src.schemas.character_creation import CharacterDraft


CORE_FIELDS = (
    "name",
    "race",
    "class_name",
    "background",
    "alignment",
    "notes",
)

DEPENDENCIES = {
    "race": {
        "abilities",
        "background",
        "proficiencies",
        "class_features",
        "optional_rules",
        "spells",
        "equipment",
        "adventure_connection",
        "review",
    },
    "class_name": {
        "abilities",
        "proficiencies",
        "class_features",
        "optional_rules",
        "spells",
        "equipment",
        "adventure_connection",
        "review",
    },
    "background": {
        "proficiencies",
        "equipment",
        "adventure_connection",
        "review",
    },
    "abilities": {
        "optional_rules",
        "spells",
        "review",
    },
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
    "optional_rules": {
        "spells",
        "equipment",
        "adventure_connection",
        "review",
    },
    "spells": {
        "review",
    },
    "equipment": {
        "adventure_connection",
        "review",
    },
    "adventure_connection": {
        "review",
    },
}


@dataclass(frozen=True)
class DraftValidationIssue:
    code: str
    value: str = ""


def changed_core_fields(
    before: CharacterDraft | dict[str, Any],
    after: CharacterDraft,
) -> list[str]:
    values = before.model_dump() if isinstance(before, CharacterDraft) else before
    return [
        field
        for field in CORE_FIELDS
        if values.get(field) != getattr(after, field)
    ]


def invalidate_changed_dependencies(
    before: CharacterDraft | dict[str, Any] | None,
    draft: CharacterDraft,
    changed_fields: list[str],
) -> None:
    invalidated: set[str] = set()
    for field in changed_fields:
        previous_value = _previous_value(before, field)
        if before is not None and _was_unset(field, previous_value):
            continue
        invalidated.update(DEPENDENCIES.get(field, set()))
    if not invalidated:
        return
    draft.invalid_steps = sorted(set(draft.invalid_steps) | invalidated)
    draft.completed_steps = [
        step for step in draft.completed_steps if step not in invalidated
    ]


def basic_draft_issues(
    draft: CharacterDraft,
    *,
    valid_races: set[str],
    valid_classes: set[str],
    valid_backgrounds: set[str] | None = None,
) -> list[DraftValidationIssue]:
    issues: list[DraftValidationIssue] = []
    if not draft.name:
        issues.append(DraftValidationIssue("missing_name"))
    if not draft.race:
        issues.append(DraftValidationIssue("missing_race"))
    elif draft.race not in valid_races:
        issues.append(DraftValidationIssue("unsupported_race", draft.race))
    if not draft.class_name:
        issues.append(DraftValidationIssue("missing_class"))
    elif draft.class_name not in valid_classes:
        issues.append(DraftValidationIssue("unsupported_class", draft.class_name))
    if (
        valid_backgrounds is not None
        and draft.background
        and draft.background != "Adventurer"
        and draft.background not in valid_backgrounds
    ):
        issues.append(
            DraftValidationIssue("unsupported_background", draft.background)
        )
    return issues


def format_basic_issue(issue: DraftValidationIssue) -> str:
    messages = {
        "missing_name": "Character name is required.",
        "missing_race": "Race is required.",
        "unsupported_race": f"Unsupported race: {issue.value}.",
        "missing_class": "Class is required.",
        "unsupported_class": f"Unsupported class: {issue.value}.",
        "unsupported_background": f"Unsupported background: {issue.value}.",
    }
    return messages[issue.code]


def localize_validation_error(error: str, locale: str) -> str:
    if locale != "zh-CN":
        return error
    point_buy = re.search(r"Point-buy cost (\d+) exceeds 27", error)
    if point_buy:
        return (
            f"六项属性共花费 {point_buy.group(1)} 点，超过可用的 27 点。"
            "请按照购点花费表重新分配。"
        )
    if "between 8 and 15" in error:
        return "每项基础属性必须在 8 到 15 之间，请重新输入六项属性值。"
    return error


def _previous_value(
    before: CharacterDraft | dict[str, Any] | None,
    field: str,
) -> Any:
    if before is None:
        return None
    if isinstance(before, CharacterDraft):
        if field == "abilities":
            return before.abilities
        if field == "proficiencies":
            return before.proficiencies
        if field == "class_features":
            return before.selections.class_option_ids
        if field == "optional_rules":
            return before.selections.feat_ids
        if field == "spells":
            return before.selections.spell_ids
        if field == "equipment":
            return before.inventory
        if field == "adventure_connection":
            return before.adventure_connection
        return getattr(before, field)
    if field == "optional_rules":
        selections = before.get("selections", {})
        return selections.get("feat_ids", [])
    if field == "spells":
        selections = before.get("selections", {})
        return selections.get("spell_ids", [])
    if field == "equipment":
        return before.get("inventory", [])
    if field == "adventure_connection":
        return before.get("adventure_connection", {})
    if field == "class_features":
        selections = before.get("selections", {})
        return selections.get("class_option_ids", [])
    if field == "proficiencies":
        return before.get("proficiencies", {})
    return before.get(field)


def _was_unset(field: str, value: Any) -> bool:
    if field == "background":
        return not value or value == "Adventurer"
    if field == "abilities":
        if isinstance(value, dict):
            return value.get("point_buy_spent", 0) == 0
        return getattr(value, "point_buy_spent", 0) == 0
    return not value
