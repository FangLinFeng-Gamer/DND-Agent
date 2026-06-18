from collections.abc import Mapping, Sequence

from backend.src.agent.character_creation.rules.models import PHBRuleRecord


def validate_rule_choices(
    rule: PHBRuleRecord,
    choice_values: Mapping[str, Sequence[str]],
    choice_ids: set[str] | None = None,
) -> None:
    choices = [
        choice
        for choice in rule.choices
        if choice_ids is None or choice.id in choice_ids
    ]
    known_choice_ids = {choice.id for choice in choices}
    unknown_choice_ids = set(choice_values) - known_choice_ids
    if unknown_choice_ids:
        unknown = ", ".join(sorted(unknown_choice_ids))
        raise ValueError(f"{rule.id} contains unknown choices: {unknown}.")

    for choice in choices:
        selected = list(choice_values.get(choice.id, []))
        if not choice.minimum <= len(selected) <= choice.maximum:
            raise ValueError(
                f"{choice.id} requires {choice.minimum}-{choice.maximum} choices."
            )
        if len(selected) != len(set(selected)):
            raise ValueError(f"{choice.id} choices must be distinct.")
        if any(value not in choice.option_ids for value in selected):
            raise ValueError(f"{choice.id} contains an invalid choice.")
