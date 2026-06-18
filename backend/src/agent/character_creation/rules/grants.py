from pydantic import BaseModel, Field

from backend.src.agent.character_creation.rules.choices import validate_rule_choices
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


class ProficiencyConflict(BaseModel):
    category: str
    target: str
    sources: list[str]


class GrantResolution(BaseModel):
    proficiencies: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "skills": [],
            "tools": [],
            "languages": [],
            "armor": [],
            "weapons": [],
        }
    )
    sources: dict[str, list[str]] = Field(default_factory=dict)
    conflicts: list[ProficiencyConflict] = Field(default_factory=list)
    other_grants: list[dict[str, object]] = Field(default_factory=list)


_FIXED_PROFICIENCY_KINDS = {
    "skill_proficiency": "skills",
    "tool_proficiency": "tools",
    "language": "languages",
    "armor_proficiency": "armor",
    "weapon_proficiency": "weapons",
}

_CHOICE_PROFICIENCY_KINDS = {
    "skill_proficiency_choice": "skills",
    "tool_proficiency_choice": "tools",
    "language_choice": "languages",
}

_REPLACEABLE_CATEGORIES = {"skills", "tools", "languages"}
_REPLACEMENT_CHOICE_PREFIX = "replacement:"
_REPLACEMENT_RULE_TYPES = {
    "skills": "skill",
    "tools": "tool",
    "languages": "language",
}
_REPLACEMENT_CATEGORIES = {
    rule_type: category
    for category, rule_type in _REPLACEMENT_RULE_TYPES.items()
}


def proficiency_replacement_choice_id(category: str, target: str) -> str:
    return f"{_REPLACEMENT_CHOICE_PREFIX}{category}:{target}"


def replacement_rule_type_for_category(category: str) -> str:
    return _REPLACEMENT_RULE_TYPES[category]


def fixed_replaceable_proficiency_conflicts(
    rule_ids: list[str],
    repository: PHBRuleRepository,
) -> list[ProficiencyConflict]:
    result = GrantResolution()
    for rule_id in rule_ids:
        rule = repository.get(rule_id)
        for grant in rule.grants:
            category = _FIXED_PROFICIENCY_KINDS.get(grant.kind)
            if category not in _REPLACEABLE_CATEGORIES:
                continue
            _add_proficiency(
                result,
                category,
                grant.target,
                grant.source or rule.id,
            )
    return result.conflicts


def resolve_grants(
    rule_ids: list[str],
    choice_values: dict[str, list[str]],
    repository: PHBRuleRepository,
) -> GrantResolution:
    result = GrantResolution()
    rules = [repository.get(rule_id) for rule_id in rule_ids]
    for rule in rules:
        proficiency_choice_ids = {
            grant.target
            for grant in rule.grants
            if grant.kind in _CHOICE_PROFICIENCY_KINDS
            or grant.kind == "mixed_proficiency_choice"
        }
        validate_rule_choices(
            rule,
            {
                choice.id: choice_values[choice.id]
                for choice in rule.choices
                if choice.id in choice_values
                and choice.id in proficiency_choice_ids
            },
            proficiency_choice_ids,
        )
        for grant in rule.grants:
            if grant.kind in _FIXED_PROFICIENCY_KINDS:
                _add_proficiency(
                    result,
                    _FIXED_PROFICIENCY_KINDS[grant.kind],
                    grant.target,
                    grant.source or rule.id,
                )
            elif grant.kind in _CHOICE_PROFICIENCY_KINDS:
                category = _CHOICE_PROFICIENCY_KINDS[grant.kind]
                for target in choice_values.get(grant.target, []):
                    _add_proficiency(
                        result,
                        category,
                        target,
                        grant.source or rule.id,
                    )
            elif grant.kind == "mixed_proficiency_choice":
                for target in choice_values.get(grant.target, []):
                    rule_type = repository.get(target).rule_type
                    category = {
                        "language": "languages",
                        "skill": "skills",
                        "tool": "tools",
                    }.get(rule_type)
                    if category is None:
                        raise ValueError(
                            f"{grant.target} contains unsupported proficiency "
                            f"type {rule_type}."
                        )
                    _add_proficiency(
                        result,
                        category,
                        target,
                        grant.source or rule.id,
                    )
            else:
                result.other_grants.append(grant.model_dump())
    _apply_proficiency_replacements(result, choice_values, repository)
    for values in result.proficiencies.values():
        values.sort()
    return result


def _apply_proficiency_replacements(
    result: GrantResolution,
    choice_values: dict[str, list[str]],
    repository: PHBRuleRepository,
) -> None:
    conflicts = list(result.conflicts)
    if not conflicts:
        return
    result.conflicts = []
    for conflict in conflicts:
        choice_id = proficiency_replacement_choice_id(
            conflict.category,
            conflict.target,
        )
        replacements = list(choice_values.get(choice_id, []))
        if not replacements:
            result.conflicts.append(conflict)
            continue
        required = max(1, len(conflict.sources) - 1)
        if len(replacements) != required:
            raise ValueError(f"{choice_id} requires {required} replacement choices.")
        if len(replacements) != len(set(replacements)):
            raise ValueError(f"{choice_id} replacement choices must be distinct.")

        source_key = f"{conflict.category}:{conflict.target}"
        result.sources[source_key] = conflict.sources[:1]
        for index, replacement in enumerate(replacements):
            if replacement == conflict.target:
                raise ValueError(f"{choice_id} cannot replace a proficiency with itself.")
            replacement_rule = repository.get(replacement)
            replacement_category = _REPLACEMENT_CATEGORIES.get(
                replacement_rule.rule_type
            )
            if replacement_category != conflict.category:
                raise ValueError(
                    f"{choice_id} must choose a {conflict.category} replacement."
                )
            source = (
                conflict.sources[index + 1]
                if index + 1 < len(conflict.sources)
                else f"replacement:{conflict.target}"
            )
            _add_proficiency(result, conflict.category, replacement, source)


def _add_proficiency(
    result: GrantResolution,
    category: str,
    target: str,
    source: str,
) -> None:
    source_key = f"{category}:{target}"
    sources = result.sources.setdefault(source_key, [])
    if source not in sources:
        sources.append(source)

    selected = result.proficiencies[category]
    if target not in selected:
        selected.append(target)
        return
    if category not in _REPLACEABLE_CATEGORIES:
        return

    conflict = next(
        (
            item
            for item in result.conflicts
            if item.category == category and item.target == target
        ),
        None,
    )
    if conflict is None:
        result.conflicts.append(
            ProficiencyConflict(
                category=category,
                target=target,
                sources=list(sources),
            )
        )
    else:
        conflict.sources = list(sources)
