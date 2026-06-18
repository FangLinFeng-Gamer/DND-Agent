from pathlib import Path

from backend.src.agent.character_creation.messages import (
    CharacterCreationMessageRepository,
)
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character_creation import (
    CHARACTER_CREATION_STEPS,
    CharacterDraftMutation,
)
from backend.src.services.character_drafts import CharacterDraftService


def test_phase2_guide_exposes_all_twelve_steps(tmp_path: Path):
    service = _service(tmp_path)
    session = service.create("zh-CN")

    guide = service.guide(session.id, "zh-CN")

    assert [step.id for step in guide.steps] == list(CHARACTER_CREATION_STEPS)
    assert guide.active_step == "identity"
    assert any(step.id == "proficiencies" for step in guide.steps)
    assert any(step.id == "equipment" for step in guide.steps)
    assert any(step.id == "adventure_connection" for step in guide.steps)


def test_phase2_resource_names_follow_phb_chinese_translation():
    repository = PHBRuleRepository.load_builtin()

    expected_names = {
        "tool.artisan.tinker": "修理工具",
        "tool.artisan.weaver": "织布工具",
        "tool.gaming.dice": "整副骰子",
        "tool.gaming.cards": "整副纸牌",
        "tool.gaming.dragonchess": "整套龙棋",
        "tool.gaming.three-dragon-ante": "整副三龙牌",
        "tool.instrument.shawm": "芦笛",
        "tool.vehicles.land": "载具（陆运）",
        "tool.vehicles.water": "载具（水运）",
        "race.stout-halfling": "敦实半身人",
    }

    for rule_id, expected_name in expected_names.items():
        assert repository.get(rule_id).name.for_locale("zh-CN") == expected_name

    dragonborn = repository.get("race.dragonborn")
    assert dragonborn.choices[0].name.for_locale("zh-CN") == "龙族血统"


def test_phase2_paladin_dragonborn_noble_proficiency_guide_has_choices(
    tmp_path: Path,
):
    service = _service(tmp_path)
    session = _paladin_dragonborn_noble_after_abilities(service)

    guide = service.guide(session.id, "zh-CN")

    assert guide.active_step == "proficiencies"
    groups = guide.requirements["choice_groups"]
    group_ids = {group["id"] for group in groups}
    assert {"paladin-skills", "noble-gaming-set", "noble-language"} <= group_ids
    assert all(group["options"] for group in groups)
    assert guide.options == []


def test_phase2_bard_entertainer_disables_duplicate_fixed_proficiencies(
    tmp_path: Path,
):
    service = _service(tmp_path)
    session = _bard_entertainer_after_abilities(service)

    guide = service.guide(session.id, "en")

    assert guide.active_step == "proficiencies"
    bard_skills = next(
        group
        for group in guide.requirements["choice_groups"]
        if group["id"] == "bard-skills"
    )
    options = {option["id"]: option for option in bard_skills["options"]}
    assert options["skill.acrobatics"]["disabled"] is True
    assert options["skill.performance"]["disabled"] is True
    assert options["skill.persuasion"].get("disabled", False) is False


def test_phase2_druid_hermit_duplicate_tool_gets_replacement_choice(
    tmp_path: Path,
):
    service = _service(tmp_path)
    session = _druid_hermit_after_abilities(service)

    guide = service.guide(session.id, "en")

    assert guide.active_step == "proficiencies"
    groups = guide.requirements["choice_groups"]
    replacement = next(
        group
        for group in groups
        if group["id"] == "replacement:tools:tool.herbalism-kit"
    )
    options = {option["id"]: option for option in replacement["options"]}
    assert replacement["minimum"] == 1
    assert replacement["maximum"] == 1
    assert options["tool.herbalism-kit"]["disabled"] is True
    assert options["tool.artisan.alchemist"].get("disabled", False) is False

    updated = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="proficiencies",
            payload={
                "choice_values": {
                    "human-language": ["language.elvish"],
                    "druid-skills": ["skill.nature", "skill.survival"],
                    "hermit-language": ["language.dwarvish"],
                    "replacement:tools:tool.herbalism-kit": [
                        "tool.artisan.alchemist"
                    ],
                }
            },
            locale="en",
        ),
    )

    assert updated.validation_errors == []
    assert "tool.herbalism-kit" in updated.draft.proficiencies["tools"]
    assert "tool.artisan.alchemist" in updated.draft.proficiencies["tools"]


def test_phase2_guide_reaches_proficiency_choices_after_background_and_abilities(
    tmp_path: Path,
):
    service = _service(tmp_path)
    session = _wizard_after_background_and_abilities(service)

    guide = service.guide(session.id, "zh-CN")

    assert guide.active_step == "proficiencies"
    groups = guide.requirements["choice_groups"]
    assert any(group["id"] == "wizard-skills" for group in groups)
    assert any(group["id"] == "sage-languages" for group in groups)
    wizard_skills = next(group for group in groups if group["id"] == "wizard-skills")
    assert wizard_skills["minimum"] == 2
    assert wizard_skills["maximum"] == 2
    assert any(option["id"] == "skill.investigation" for option in wizard_skills["options"])


def test_phase2_structured_proficiency_mutation_persists_choices_and_syncs_chat(
    tmp_path: Path,
):
    service = _service(tmp_path)
    session = _wizard_after_background_and_abilities(service)

    updated = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="proficiencies",
            payload={
                "choice_values": {
                    "human-language": ["language.dwarvish"],
                    "wizard-skills": ["skill.investigation", "skill.medicine"],
                    "sage-languages": ["language.draconic", "language.elvish"],
                }
            },
            locale="zh-CN",
        ),
    )
    messages = CharacterCreationMessageRepository(service.store).list_recent(
        session.id,
        limit=10,
    )

    assert updated.validation_errors == []
    assert "proficiencies" in updated.draft.completed_steps
    assert "skill.arcana" in updated.draft.proficiencies["skills"]
    assert "skill.history" in updated.draft.proficiencies["skills"]
    assert "skill.investigation" in updated.draft.proficiencies["skills"]
    assert "skill.medicine" in updated.draft.proficiencies["skills"]
    assert "language.dwarvish" in updated.draft.proficiencies["languages"]
    assert "language.draconic" in updated.draft.proficiencies["languages"]
    assert any(message.role == "user" and "界面选择" in message.content for message in messages)
    assert any(message.role == "assistant" and "已记录" in message.content for message in messages)


def test_phase2_fighter_class_feature_choice_is_guided_and_persisted(
    tmp_path: Path,
):
    service = _service(tmp_path)
    session = _fighter_after_proficiencies(service)

    guide = service.guide(session.id, "zh-CN")

    assert guide.active_step == "class_features"
    groups = guide.requirements["choice_groups"]
    fighting_style = next(group for group in groups if group["id"] == "fighter-style")
    assert fighting_style["minimum"] == 1
    assert any(
        option["id"] == "class_option.fighter.defense"
        for option in fighting_style["options"]
    )

    updated = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="class_features",
            payload={
                "choice_values": {
                    "fighter-style": ["class_option.fighter.defense"],
                },
                "class_option_ids": ["class_option.fighter.defense"],
            },
            locale="zh-CN",
        ),
    )

    assert updated.validation_errors == []
    assert "class_features" in updated.draft.completed_steps
    assert updated.draft.selections.class_option_ids == [
        "class_option.fighter.defense"
    ]


def _wizard_after_background_and_abilities(
    service: CharacterDraftService,
):
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "米拉"}),
        ("class", {"class_id": "class.wizard"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 14,
                    "intelligence": 15,
                    "wisdom": 10,
                    "charisma": 10,
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )
    return session


def _fighter_after_proficiencies(
    service: CharacterDraftService,
):
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "卡尔"}),
        ("class", {"class_id": "class.fighter"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.sage"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 15,
                    "dexterity": 13,
                    "constitution": 14,
                    "intelligence": 10,
                    "wisdom": 10,
                    "charisma": 8,
                }
            },
        ),
        (
            "proficiencies",
            {
                "choice_values": {
                    "human-language": ["language.dwarvish"],
                    "fighter-skills": ["skill.athletics", "skill.perception"],
                    "sage-languages": ["language.draconic", "language.elvish"],
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )
    return session


def _druid_hermit_after_abilities(
    service: CharacterDraftService,
):
    session = service.create("en")
    for operation, payload in [
        ("identity", {"name": "Tav"}),
        ("class", {"class_id": "class.druid"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.hermit"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 12,
                    "dexterity": 14,
                    "constitution": 12,
                    "intelligence": 8,
                    "wisdom": 15,
                    "charisma": 11,
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="en",
            ),
        )
    return session


def _bard_entertainer_after_abilities(
    service: CharacterDraftService,
):
    session = service.create("en")
    for operation, payload in [
        ("identity", {"name": "Mira"}),
        ("class", {"class_id": "class.bard"}),
        ("race", {"race_id": "race.human"}),
        ("background", {"background_id": "background.entertainer"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 8,
                    "dexterity": 14,
                    "constitution": 13,
                    "intelligence": 10,
                    "wisdom": 10,
                    "charisma": 15,
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="en",
            ),
        )
    return session


def _paladin_dragonborn_noble_after_abilities(
    service: CharacterDraftService,
):
    session = service.create("zh-CN")
    for operation, payload in [
        ("identity", {"name": "戴尔"}),
        ("class", {"class_id": "class.paladin"}),
        ("race", {"race_id": "race.dragonborn"}),
        ("background", {"background_id": "background.noble"}),
        (
            "abilities",
            {
                "base": {
                    "strength": 15,
                    "dexterity": 10,
                    "constitution": 13,
                    "intelligence": 8,
                    "wisdom": 10,
                    "charisma": 15,
                }
            },
        ),
    ]:
        session = service.mutate(
            session.id,
            CharacterDraftMutation(
                expected_revision=session.revision,
                operation=operation,
                payload=payload,
                locale="zh-CN",
            ),
        )
    return session


def _service(tmp_path: Path) -> CharacterDraftService:
    store = SQLiteStore(tmp_path / "test.sqlite")
    store.init_schema()
    return CharacterDraftService(store)
