import pytest

from backend.src.agent.character_creation.rules.prerequisites import (
    validate_prerequisites,
)
from backend.src.agent.character_creation.rules.draft_service import (
    CharacterDraftRulesService,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.schemas.character_creation import CharacterDraft


def test_ability_prerequisite_uses_final_ability_score():
    repository = PHBRuleRepository.load_builtin()
    draft = CharacterDraft()
    draft.abilities.final["strength"] = 12

    with pytest.raises(ValueError, match="strength 13"):
        validate_prerequisites(
            repository.get("feat.grappler"),
            draft,
            repository,
        )

    draft.abilities.final["strength"] = 13
    validate_prerequisites(repository.get("feat.grappler"), draft, repository)


def test_spellcasting_and_armor_prerequisites_use_draft_rules():
    repository = PHBRuleRepository.load_builtin()
    draft = CharacterDraft()

    with pytest.raises(ValueError, match="spellcasting"):
        validate_prerequisites(
            repository.get("feat.war-caster"),
            draft,
            repository,
        )

    draft.selections.class_id = "class.wizard"
    validate_prerequisites(repository.get("feat.war-caster"), draft, repository)

    with pytest.raises(ValueError, match="armor.medium"):
        validate_prerequisites(
            repository.get("feat.heavily-armored"),
            draft,
            repository,
        )

    draft.proficiencies["armor"] = ["armor.medium"]
    validate_prerequisites(
        repository.get("feat.heavily-armored"),
        draft,
        repository,
    )


def test_variant_human_can_select_legal_feat_and_apply_derived_effects(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()

    race = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": 0,
            "operation": "race",
            "payload": {
                "race_id": "race.human",
                "subrace_id": "race.variant-human",
                "choice_values": {
                    "variant-human-abilities": [
                        "ability.dexterity",
                        "ability.wisdom",
                    ],
                    "variant-human-skill": ["skill.perception"],
                    "human-language": ["language.elvish"],
                },
            },
        },
    ).json()
    character_class = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": race["revision"],
            "operation": "class",
            "payload": {"class_id": "class.fighter"},
        },
    ).json()
    proficiencies = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": character_class["revision"],
            "operation": "proficiencies",
            "payload": {
                "choice_values": {
                    "fighter-skills": [
                        "skill.athletics",
                        "skill.survival",
                    ]
                }
            },
        },
    ).json()

    response = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": proficiencies["revision"],
            "operation": "optional_rules",
            "payload": {"feat_ids": ["feat.alert"]},
        },
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["selections"]["feat_ids"] == ["feat.alert"]
    assert draft["derived"]["initiative"] == 4


def test_feat_selection_rejects_missing_grant_and_unmet_prerequisite(client):
    session = client.post(
        "/api/character-creation/sessions",
        json={"locale": "en"},
    ).json()

    no_grant = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": 0,
            "operation": "optional_rules",
            "payload": {"feat_ids": ["feat.alert"]},
        },
    )
    assert no_grant.status_code == 200
    no_grant_payload = no_grant.json()
    assert "does not grant" in " ".join(no_grant_payload["validation_errors"])
    assert no_grant_payload["revision"] == 0

    race = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": 0,
            "operation": "race",
            "payload": {
                "race_id": "race.human",
                "subrace_id": "race.variant-human",
                "choice_values": {
                    "variant-human-abilities": [
                        "ability.dexterity",
                        "ability.wisdom",
                    ],
                    "variant-human-skill": ["skill.perception"],
                    "human-language": ["language.elvish"],
                },
            },
        },
    ).json()
    unmet = client.patch(
        f"/api/character-creation/sessions/{session['id']}/draft",
        json={
            "expected_revision": race["revision"],
            "operation": "optional_rules",
            "payload": {"feat_ids": ["feat.grappler"]},
        },
    )

    assert unmet.status_code == 200
    assert "strength 13" in " ".join(unmet.json()["validation_errors"])


def test_half_feat_bonus_is_separate_from_race_bonus_and_updates_modifier():
    service = CharacterDraftRulesService()
    draft = CharacterDraft()
    draft.selections.race_id = "race.human"
    draft.selections.subrace_id = "race.variant-human"
    draft.selections.class_id = "class.fighter"
    draft.selections.choice_values = {
        "variant-human-abilities": ["ability.dexterity", "ability.wisdom"],
        "variant-human-skill": ["skill.perception"],
        "human-language": ["language.elvish"],
        "fighter-skills": ["skill.athletics", "skill.survival"],
    }
    draft.abilities.base["dexterity"] = 15

    updated = service.mutate(
        draft,
        "optional_rules",
        {
            "feat_ids": ["feat.athlete"],
            "choice_values": {"athlete-ability": ["ability.dexterity"]},
        },
    )

    assert updated.abilities.racial_bonuses["dexterity"] == 1
    assert updated.abilities.feat_bonuses["dexterity"] == 1
    assert updated.abilities.final["dexterity"] == 17
    assert updated.abilities.modifiers["dexterity"] == 3
    assert updated.abilities.sources["dexterity"][-1] == {
        "source": "feat.athlete",
        "value": 1,
    }


def test_skilled_feat_adds_selected_skill_and_tool_proficiencies():
    service = CharacterDraftRulesService()
    draft = CharacterDraft()
    draft.selections.race_id = "race.human"
    draft.selections.subrace_id = "race.variant-human"
    draft.selections.class_id = "class.fighter"
    draft.selections.choice_values = {
        "variant-human-abilities": ["ability.dexterity", "ability.wisdom"],
        "variant-human-skill": ["skill.perception"],
        "human-language": ["language.elvish"],
        "fighter-skills": ["skill.athletics", "skill.survival"],
    }

    updated = service.mutate(
        draft,
        "optional_rules",
        {
            "feat_ids": ["feat.skilled"],
            "choice_values": {
                "skilled-proficiencies": [
                    "skill.arcana",
                    "tool.herbalism-kit",
                    "tool.thieves-tools",
                ]
            },
        },
    )

    assert "skill.arcana" in updated.proficiencies["skills"]
    assert "tool.herbalism-kit" in updated.proficiencies["tools"]
    assert "tool.thieves-tools" in updated.proficiencies["tools"]


def test_upstream_change_clears_feat_when_grant_or_prerequisite_is_lost():
    service = CharacterDraftRulesService()
    draft = CharacterDraft()
    draft.selections.race_id = "race.human"
    draft.selections.subrace_id = "race.variant-human"
    draft.selections.class_id = "class.fighter"
    draft.selections.feat_ids = ["feat.grappler"]
    draft.selections.choice_values = {
        "variant-human-abilities": ["ability.strength", "ability.wisdom"],
        "variant-human-skill": ["skill.perception"],
        "human-language": ["language.elvish"],
        "fighter-skills": ["skill.athletics", "skill.survival"],
    }
    draft.abilities.base["strength"] = 12

    lowered = service.mutate(
        draft,
        "abilities",
        {"base": {**draft.abilities.base, "strength": 11}},
    )

    assert lowered.selections.feat_ids == []
    assert "optional_rules" in lowered.invalid_steps

    draft.selections.feat_ids = ["feat.alert"]
    changed_race = service.mutate(
        draft,
        "race",
        {
            "race_id": "race.elf",
            "subrace_id": "race.wood-elf",
            "choice_values": {},
        },
    )

    assert changed_race.selections.feat_ids == []
    assert "optional_rules" in changed_race.invalid_steps


def test_resilient_adds_ability_and_matching_saving_throw_proficiency():
    service = CharacterDraftRulesService()
    draft = CharacterDraft()
    draft.selections.race_id = "race.human"
    draft.selections.subrace_id = "race.variant-human"
    draft.selections.class_id = "class.fighter"
    draft.selections.choice_values = {
        "variant-human-abilities": ["ability.dexterity", "ability.wisdom"],
        "variant-human-skill": ["skill.perception"],
        "human-language": ["language.elvish"],
        "fighter-skills": ["skill.athletics", "skill.survival"],
    }
    draft.abilities.base["dexterity"] = 14

    updated = service.mutate(
        draft,
        "optional_rules",
        {
            "feat_ids": ["feat.resilient"],
            "choice_values": {
                "resilient-ability": ["ability.dexterity"],
            },
        },
    )

    assert updated.abilities.final["dexterity"] == 16
    assert updated.derived.saving_throws["dexterity"] == 5
    assert updated.derived.sources["saving_throw.dexterity"][-1] == {
        "source": "feat.resilient",
        "value": 2,
    }
