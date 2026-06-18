from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import (
    ABILITY_NAMES,
    CharacterAbilityState,
    default_abilities,
)


POINT_BUY_COSTS = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}


def point_buy_cost(score: int) -> int:
    try:
        return POINT_BUY_COSTS[score]
    except KeyError as exc:
        raise ValueError("Point-buy ability scores must be between 8 and 15.") from exc


def validate_point_buy(base_scores: dict[str, int]) -> int:
    missing = set(ABILITY_NAMES) - set(base_scores)
    extra = set(base_scores) - set(ABILITY_NAMES)
    if missing or extra:
        raise ValueError("Point-buy scores must include exactly the six abilities.")
    spent = sum(point_buy_cost(base_scores[ability]) for ability in ABILITY_NAMES)
    if spent > 27:
        raise ValueError(f"Point-buy cost {spent} exceeds 27.")
    return spent


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def calculate_abilities(
    base_scores: dict[str, int],
    race_id: str | None,
    repository: PHBRuleRepository,
    subrace_id: str | None = None,
    choice_values: dict[str, list[str]] | None = None,
    feat_ids: list[str] | None = None,
) -> CharacterAbilityState:
    spent = validate_point_buy(base_scores)
    racial_bonuses = default_abilities(0)
    feat_bonuses = default_abilities(0)
    sources: dict[str, list[dict[str, object]]] = {
        ability: [
            {
                "source": "point_buy",
                "value": base_scores[ability],
            }
        ]
        for ability in ABILITY_NAMES
    }
    choice_values = choice_values or {}
    rule_ids = [rule_id for rule_id in (race_id, subrace_id) if rule_id]
    rules = [repository.get(rule_id) for rule_id in rule_ids]
    if rules and rules[-1].metadata.get("replaces_parent_grants"):
        rules = rules[-1:]

    _apply_ability_grants(
        rules,
        racial_bonuses,
        sources,
        choice_values,
    )
    feat_rules = [
        repository.get(feat_id)
        for feat_id in (feat_ids or [])
    ]
    _apply_ability_grants(
        feat_rules,
        feat_bonuses,
        sources,
        choice_values,
    )

    final = {
        ability: (
            base_scores[ability]
            + racial_bonuses[ability]
            + feat_bonuses[ability]
        )
        for ability in ABILITY_NAMES
    }
    modifiers = {
        ability: ability_modifier(final[ability])
        for ability in ABILITY_NAMES
    }
    return CharacterAbilityState(
        base=dict(base_scores),
        racial_bonuses=racial_bonuses,
        feat_bonuses=feat_bonuses,
        final=final,
        modifiers=modifiers,
        point_buy_spent=spent,
        point_buy_remaining=27 - spent,
        sources=sources,
    )


def _apply_ability_grants(
    rules: list,
    bonuses: dict[str, int],
    sources: dict[str, list[dict[str, object]]],
    choice_values: dict[str, list[str]],
) -> None:
    for rule in rules:
        for grant in rule.grants:
            if grant.kind == "ability_bonus_all":
                value = int(grant.value)
                for ability in ABILITY_NAMES:
                    _add_bonus(bonuses, sources, ability, value, grant.source)
            elif grant.kind == "ability_bonus":
                value = int(grant.value)
                ability = _ability_name(grant.target)
                _add_bonus(bonuses, sources, ability, value, grant.source)
            elif grant.kind == "ability_bonus_choice":
                value = int(grant.value)
                choice = next(
                    (
                        option
                        for option in rule.choices
                        if option.id in choice_values
                    ),
                    None,
                )
                if choice is None:
                    raise ValueError(f"Missing ability choices for {rule.id}.")
                selected = choice_values[choice.id]
                if len(selected) != choice.maximum:
                    raise ValueError(
                        f"{choice.id} requires {choice.maximum} ability choices."
                    )
                if len(set(selected)) != len(selected):
                    raise ValueError(f"{choice.id} ability choices must be distinct.")
                if any(option_id not in choice.option_ids for option_id in selected):
                    raise ValueError(f"{choice.id} contains an invalid ability choice.")
                for option_id in selected:
                    _add_bonus(
                        bonuses,
                        sources,
                        _ability_name(option_id),
                        value,
                        grant.source,
                    )


def _ability_name(rule_id: str) -> str:
    ability = rule_id.removeprefix("ability.")
    if ability not in ABILITY_NAMES:
        raise ValueError(f"Unknown ability id: {rule_id}")
    return ability


def _add_bonus(
    bonuses: dict[str, int],
    sources: dict[str, list[dict[str, object]]],
    ability: str,
    value: int,
    source: str,
) -> None:
    bonuses[ability] += value
    sources[ability].append({"source": source, "value": value})
