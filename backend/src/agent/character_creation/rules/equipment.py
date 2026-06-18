from __future__ import annotations

from collections import Counter

from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


def resolve_starting_equipment(
    *,
    class_id: str | None,
    background_id: str | None,
    option_ids: list[str],
    item_choices: dict[str, list[str]],
    repository: PHBRuleRepository,
) -> list[dict]:
    packages = _packages_for(class_id, background_id, repository)
    selected = set(option_ids)
    allowed_options = {
        option["id"]
        for package in packages
        for group in package.metadata.get("choice_groups", [])
        for option in group["options"]
    }
    foreign = selected - allowed_options
    if foreign:
        raise ValueError(f"Equipment option {sorted(foreign)[0]} does not belong.")

    quantities: Counter[str] = Counter()
    for package in packages:
        _add_grants(quantities, package.metadata.get("fixed", []))
        for selector in package.metadata.get("selectors", []):
            _resolve_selector(quantities, selector, item_choices, repository)
        for group in package.metadata.get("choice_groups", []):
            matches = [
                option for option in group["options"] if option["id"] in selected
            ]
            if len(matches) != 1:
                raise ValueError(f"Choose exactly one option for {group['id']}.")
            option = matches[0]
            _add_grants(quantities, option.get("grants", []))
            for selector in option.get("selectors", []):
                _resolve_selector(quantities, selector, item_choices, repository)

    return [
        {"item_id": item_id, "quantity": quantity}
        for item_id, quantity in sorted(quantities.items())
    ]


def _packages_for(
    class_id: str | None,
    background_id: str | None,
    repository: PHBRuleRepository,
) -> list:
    owner_ids = {value for value in (class_id, background_id) if value}
    packages = [
        record
        for record in repository.list("equipment_option")
        if record.metadata.get("owner_id") in owner_ids
    ]
    found = {record.metadata["owner_id"] for record in packages}
    missing = owner_ids - found
    if missing:
        raise ValueError(f"No starting equipment package for {sorted(missing)[0]}.")
    return packages


def _add_grants(quantities: Counter[str], grants: list[list]) -> None:
    for item_id, quantity in grants:
        quantities[item_id] += int(quantity)


def _resolve_selector(
    quantities: Counter[str],
    selector: dict,
    item_choices: dict[str, list[str]],
    repository: PHBRuleRepository,
) -> None:
    choice_id = selector["id"]
    selected = item_choices.get(choice_id, [])
    expected = int(selector.get("count", 1))
    if len(selected) != expected:
        raise ValueError(f"{choice_id} requires {expected} item choices.")
    required_tags = set(selector.get("tags", []))
    for item_id in selected:
        item = repository.get(item_id)
        if item.rule_type != "equipment" or not required_tags <= set(item.tags):
            raise ValueError(f"{item_id} is not valid for {choice_id}.")
        quantities[item_id] += int(selector.get("quantity_each", 1))
