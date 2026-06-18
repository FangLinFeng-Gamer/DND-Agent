from pathlib import Path

import pytest

from backend.src.agent.character_creation.derived.spellcasting import (
    spell_selection_requirements,
)
from backend.src.agent.character_creation.slots import missing_required_slots
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character_creation import (
    CharacterCreationGuideOut,
    CharacterCreationSessionOut,
    CharacterDraft,
    CharacterDraftMutation,
)
from backend.src.services.character_drafts import CharacterDraftService


REPOSITORY = PHBRuleRepository.load_builtin()
CLASS_IDS = [record.id for record in REPOSITORY.list("class")]
CLASS_OPTION_CASES = [
    (class_record.id, option_id)
    for class_record in REPOSITORY.list("class")
    for choice in class_record.choices
    for option_id in choice.option_ids
    if option_id.startswith("class_option.")
]
CONDITIONAL_STEPS = {
    "proficiencies",
    "class_features",
    "optional_rules",
    "spells",
    "equipment",
    "adventure_connection",
}


@pytest.mark.parametrize(
    "class_id",
    CLASS_IDS,
    ids=[class_id.removeprefix("class.") for class_id in CLASS_IDS],
)
def test_each_phb_class_can_reach_review_and_confirm_without_stale_steps(
    tmp_path: Path,
    class_id: str,
):
    service = _service(tmp_path)
    session = _start_human_sage(service, class_id)

    session = _complete_proficiencies_if_needed(service, session)
    session = _complete_class_features_if_needed(service, session)
    session = _complete_spells_if_needed(service, session)
    session = _complete_equipment_if_needed(service, session)
    session = _complete_adventure_connection_if_needed(service, session)

    guide = service.guide(session.id, "en")
    required_steps = {slot.step for slot in missing_required_slots(session.draft)}
    confirmed = service.handle_message(session.id, "confirm", "en")

    assert guide.active_step == "review"
    assert not (set(session.draft.invalid_steps) & CONDITIONAL_STEPS)
    assert not (required_steps & CONDITIONAL_STEPS)
    assert confirmed.validation_errors == []
    assert confirmed.created_character is not None


@pytest.mark.parametrize(
    ("class_id", "class_option_id"),
    CLASS_OPTION_CASES,
    ids=[
        f"{class_id.removeprefix('class.')}.{option_id.split('.')[-1]}"
        for class_id, option_id in CLASS_OPTION_CASES
    ],
)
def test_each_class_feature_option_branch_can_reach_review_and_confirm(
    tmp_path: Path,
    class_id: str,
    class_option_id: str,
):
    service = _service(tmp_path)
    session = _start_human_sage(service, class_id)

    session = _complete_proficiencies_if_needed(service, session)
    session = _complete_specific_class_feature_option(
        service,
        session,
        class_option_id,
    )
    session = _complete_spells_if_needed(service, session)
    session = _complete_equipment_if_needed(service, session)
    session = _complete_adventure_connection_if_needed(service, session)

    guide = service.guide(session.id, "en")
    required_steps = {slot.step for slot in missing_required_slots(session.draft)}
    confirmed = service.handle_message(session.id, "confirm", "en")

    assert guide.active_step == "review"
    assert class_option_id in session.draft.selections.class_option_ids
    assert not (set(session.draft.invalid_steps) & CONDITIONAL_STEPS)
    assert not (required_steps & CONDITIONAL_STEPS)
    assert confirmed.validation_errors == []
    assert confirmed.created_character is not None


def _service(tmp_path: Path) -> CharacterDraftService:
    store = SQLiteStore(tmp_path / "test.sqlite")
    store.init_schema()
    return CharacterDraftService(store)


def _start_human_sage(
    service: CharacterDraftService,
    class_id: str,
) -> CharacterCreationSessionOut:
    session = service.create("en")
    for operation, payload in [
        ("identity", {"name": f"Matrix {class_id.removeprefix('class.')}"}),
        ("class", {"class_id": class_id}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 8,
                    "constitution": 8,
                    "intelligence": 8,
                    "wisdom": 8,
                    "charisma": 8,
                }
            },
        ),
    ]:
        session = _mutate(service, session, operation, payload)
    return session


def _complete_proficiencies_if_needed(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
) -> CharacterCreationSessionOut:
    guide = service.guide(session.id, "en")
    if guide.active_step != "proficiencies":
        return session
    payload = {"choice_values": _choice_values_for_proficiencies(guide, session.draft)}
    return _mutate(service, session, "proficiencies", payload)


def _complete_class_features_if_needed(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
) -> CharacterCreationSessionOut:
    guide = service.guide(session.id, "en")
    if guide.active_step != "class_features":
        return session
    choice_values: dict[str, list[str]] = {}
    class_option_ids: list[str] = []
    for group in guide.requirements["choice_groups"]:
        selected = _select_class_feature_options(group)
        choice_values[group["id"]] = selected
        class_option_ids.extend(
            option_id for option_id in selected if option_id.startswith("class_option.")
        )
        for option_id in selected:
            _add_nested_choice_values(choice_values, REPOSITORY.get(option_id), session.draft)
    return _mutate(
        service,
        session,
        "class_features",
        {
            "choice_values": choice_values,
            "class_option_ids": class_option_ids,
        },
    )


def _complete_specific_class_feature_option(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
    class_option_id: str,
) -> CharacterCreationSessionOut:
    guide = service.guide(session.id, "en")
    assert guide.active_step == "class_features"
    choice_values: dict[str, list[str]] = {}
    class_option_ids: list[str] = []
    for group in guide.requirements["choice_groups"]:
        group_option_ids = [option["id"] for option in group["options"]]
        if class_option_id in group_option_ids:
            selected = [class_option_id]
        else:
            selected = _select_class_feature_options(group)
        choice_values[group["id"]] = selected
        class_option_ids.extend(
            option_id for option_id in selected if option_id.startswith("class_option.")
        )
        for option_id in selected:
            _add_nested_choice_values(choice_values, REPOSITORY.get(option_id), session.draft)
    assert class_option_id in class_option_ids
    return _mutate(
        service,
        session,
        "class_features",
        {
            "choice_values": choice_values,
            "class_option_ids": class_option_ids,
        },
    )


def _complete_spells_if_needed(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
) -> CharacterCreationSessionOut:
    guide = service.guide(session.id, "en")
    requirements = spell_selection_requirements(session.draft, REPOSITORY)
    if not requirements:
        assert guide.active_step != "spells"
        return session
    assert guide.active_step == "spells"
    spell_ids = _spell_ids_for(session.draft)
    return _mutate(service, session, "spells", {"spell_ids": spell_ids})


def _complete_equipment_if_needed(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
) -> CharacterCreationSessionOut:
    guide = service.guide(session.id, "en")
    if guide.active_step != "equipment":
        return session
    requirements = guide.requirements
    option_ids = [
        group["options"][0]["id"]
        for group in requirements.get("choice_groups", [])
        if group.get("options")
    ]
    item_choices = {
        group["id"]: [
            option["id"]
            for option in group.get("options", [])[: int(group.get("minimum", 1))]
        ]
        for group in requirements.get("item_choice_groups", [])
    }
    selected = set(option_ids)
    for group in requirements.get("choice_groups", []):
        for option in group.get("options", []):
            if option["id"] not in selected:
                continue
            for selector in option.get("selectors", []):
                item_choices[selector["id"]] = [
                    item["id"]
                    for item in selector.get("options", [])[
                        : int(selector.get("minimum", 1))
                    ]
                ]
    return _mutate(
        service,
        session,
        "equipment",
        {"option_ids": option_ids, "item_choices": item_choices},
    )


def _complete_adventure_connection_if_needed(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
) -> CharacterCreationSessionOut:
    guide = service.guide(session.id, "en")
    if guide.active_step != "adventure_connection":
        return session
    return _mutate(
        service,
        session,
        "adventure_connection",
        {
            "motivation": "Protect the road.",
            "quest_hook": "Hired to investigate the opening scene.",
            "npc_relation": "",
            "prior_knowledge": "",
        },
    )


def _choice_values_for_proficiencies(
    guide: CharacterCreationGuideOut,
    draft: CharacterDraft,
) -> dict[str, list[str]]:
    blocked = _fixed_replaceable_proficiencies(draft)
    chosen = {"skills": set(), "tools": set(), "languages": set()}
    choice_values: dict[str, list[str]] = {}
    for group in guide.requirements["choice_groups"]:
        selected: list[str] = []
        for option in group["options"]:
            category = _replaceable_category(option["rule_type"])
            if category and option["id"] in blocked[category] | chosen[category]:
                continue
            selected.append(option["id"])
            if category:
                chosen[category].add(option["id"])
            if len(selected) == group["minimum"]:
                break
        assert len(selected) == group["minimum"], group["id"]
        choice_values[group["id"]] = selected
    return choice_values


def _select_class_feature_options(group: dict) -> list[str]:
    preferred = [
        option["id"]
        for option in group["options"]
        if not REPOSITORY.get(option["id"]).choices
    ]
    fallback = [option["id"] for option in group["options"]]
    return (preferred or fallback)[: group["minimum"]]


def _add_nested_choice_values(
    choice_values: dict[str, list[str]],
    record,
    draft: CharacterDraft,
) -> None:
    chosen = {"skills": set(), "tools": set(), "languages": set()}
    for choice in record.choices:
        choice_values[choice.id] = _select_choice_options(
            choice.option_ids,
            choice.minimum,
            draft,
            chosen,
        )


def _select_choice_options(
    option_ids: list[str],
    count: int,
    draft: CharacterDraft,
    chosen: dict[str, set[str]],
) -> list[str]:
    blocked = {
        "skills": set(draft.proficiencies["skills"]),
        "tools": set(draft.proficiencies["tools"]),
        "languages": set(draft.proficiencies["languages"]),
    }
    selected: list[str] = []
    for option_id in option_ids:
        category = _replaceable_category(_rule_type(option_id))
        if category and option_id in blocked[category] | chosen[category]:
            continue
        selected.append(option_id)
        if category:
            chosen[category].add(option_id)
        if len(selected) == count:
            break
    assert len(selected) == count, option_ids
    return selected


def _spell_ids_for(draft: CharacterDraft) -> list[str]:
    selected: list[str] = []
    spells = REPOSITORY.list("spell")
    for requirement in spell_selection_requirements(draft, REPOSITORY):
        matching = [
            spell.id
            for spell in spells
            if spell.id not in selected and requirement.matches(spell)
        ]
        assert len(matching) >= requirement.count, requirement.id
        selected.extend(matching[: requirement.count])
    return selected


def _fixed_replaceable_proficiencies(draft: CharacterDraft) -> dict[str, set[str]]:
    values = {"skills": set(), "tools": set(), "languages": set()}
    for rule_id in _selected_rule_ids(draft):
        rule = REPOSITORY.get(rule_id)
        for grant in rule.grants:
            if grant.kind == "skill_proficiency":
                values["skills"].add(grant.target)
            if grant.kind == "tool_proficiency":
                values["tools"].add(grant.target)
            if grant.kind == "language":
                values["languages"].add(grant.target)
    return values


def _selected_rule_ids(draft: CharacterDraft) -> list[str]:
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


def _replaceable_category(rule_type: str) -> str | None:
    return {"skill": "skills", "tool": "tools", "language": "languages"}.get(rule_type)


def _rule_type(rule_id: str) -> str:
    try:
        return REPOSITORY.get(rule_id).rule_type
    except LookupError:
        return rule_id.split(".", 1)[0]


def _mutate(
    service: CharacterDraftService,
    session: CharacterCreationSessionOut,
    operation: str,
    payload: dict,
) -> CharacterCreationSessionOut:
    updated = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation=operation,
            payload=payload,
            locale="en",
        ),
    )
    assert updated.validation_errors == []
    return updated
