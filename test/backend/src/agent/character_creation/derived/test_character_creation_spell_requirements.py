from backend.src.agent.character_creation.derived.spellcasting import (
    validate_spell_selection,
)
from backend.src.agent.character_creation.rules.abilities import calculate_abilities
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository
from backend.src.db.sqlite import SQLiteStore
from backend.src.schemas.character_creation import (
    CharacterDraftMutation,
    CharacterCreationSessionOut,
    CharacterDraft,
)
from backend.src.services.character_creation_guide import CharacterCreationGuideService
from backend.src.services.character_drafts import CharacterDraftService


def test_non_spellcasting_human_fighter_does_not_need_spell_step():
    repo = PHBRuleRepository.load_builtin()
    guide = _guide_for(_ready_draft(repo, class_id="class.fighter"))

    assert guide.active_step == "equipment"
    assert guide.options == []


def test_high_elf_fighter_only_sees_available_wizard_cantrips():
    repo = PHBRuleRepository.load_builtin()
    draft = _ready_draft(
        repo,
        class_id="class.fighter",
        race_id="race.elf",
        subrace_id="race.high-elf",
    )

    guide = _guide_for(draft)

    assert guide.active_step == "spells"
    assert guide.requirements["cantrips"] == 1
    assert guide.requirements["level_one"] == 0
    assert guide.options
    for option in guide.options:
        spell = repo.get(option.id)
        assert spell.metadata["level"] == 0
        assert "wizard" in spell.metadata["classes"]


def test_spell_options_hide_unavailable_cantrips_after_quota_is_filled():
    repo = PHBRuleRepository.load_builtin()
    draft = _ready_draft(
        repo,
        class_id="class.fighter",
        race_id="race.elf",
        subrace_id="race.high-elf",
    )
    draft.selections.spell_ids = ["spell.fire-bolt"]

    guide = _guide_for(draft)

    assert [option.id for option in guide.options] == ["spell.fire-bolt"]


def test_spell_guide_hides_stale_selected_spells_that_are_no_longer_available():
    repo = PHBRuleRepository.load_builtin()
    draft = _ready_draft(
        repo,
        class_id="class.fighter",
        race_id="race.elf",
        subrace_id="race.high-elf",
    )
    draft.selections.spell_ids = ["spell.magic-missile"]

    guide = _guide_for(draft)

    assert "spell.magic-missile" not in {option.id for option in guide.options}
    assert guide.current_value == {"spell_ids": []}


def test_high_elf_fighter_can_select_cantrip_but_not_level_one_spell():
    repo = PHBRuleRepository.load_builtin()
    draft = _ready_draft(
        repo,
        class_id="class.fighter",
        race_id="race.elf",
        subrace_id="race.high-elf",
    )

    validate_spell_selection(draft, ["spell.fire-bolt"], repo)

    try:
        validate_spell_selection(draft, ["spell.magic-missile"], repo)
    except ValueError as exc:
        assert "current spell-choice requirements" in str(exc)
    else:
        raise AssertionError("High elf fighter should not be able to choose level-one spells.")


def test_nature_cleric_requires_extra_druid_cantrip():
    repo = PHBRuleRepository.load_builtin()
    draft = _ready_draft(
        repo,
        class_id="class.cleric",
        class_option_ids=["class_option.cleric.nature"],
        ability_scores={**_STANDARD_SCORES, "wisdom": 15},
    )
    valid_level_one = [
        "spell.bless",
        "spell.cure-wounds",
        "spell.guiding-bolt",
        "spell.healing-word",
    ]

    validate_spell_selection(
        draft,
        [
            "spell.light",
            "spell.sacred-flame",
            "spell.thaumaturgy",
            "spell.druidcraft",
            *valid_level_one,
        ],
        repo,
    )

    try:
        validate_spell_selection(
            draft,
            [
                "spell.light",
                "spell.sacred-flame",
                "spell.spare-the-dying",
                "spell.thaumaturgy",
                *valid_level_one,
            ],
            repo,
        )
    except ValueError as exc:
        assert "current spell-choice requirements" in str(exc)
    else:
        raise AssertionError("Nature cleric should need one druid cantrip.")


def test_magic_initiate_shows_only_chosen_class_spell_list():
    repo = PHBRuleRepository.load_builtin()
    draft = _ready_draft(
        repo,
        class_id="class.fighter",
        feat_ids=["feat.magic-initiate"],
        choice_values={"magic-initiate-class": ["feat_option.class.wizard"]},
    )

    guide = _guide_for(draft)

    assert guide.active_step == "spells"
    assert guide.requirements["cantrips"] == 2
    assert guide.requirements["level_one"] == 1
    assert "spell.fire-bolt" in {option.id for option in guide.options}
    assert "spell.guidance" not in {option.id for option in guide.options}


def test_spell_catalog_uses_phb_effect_summaries_for_selection_cards():
    repo = PHBRuleRepository.load_builtin()
    fire_bolt = repo.get("spell.fire-bolt")
    magic_missile = repo.get("spell.magic-missile")
    cure_wounds = repo.get("spell.cure-wounds")

    assert "1d10" in fire_bolt.description.for_locale("zh-CN")
    assert "火焰" in fire_bolt.description.for_locale("zh-CN")
    assert "1d4+1" in magic_missile.description.for_locale("zh-CN")
    assert "1d8" in cure_wounds.description.for_locale("zh-CN")
    assert "2014 Player's Handbook" not in fire_bolt.description.for_locale("en")

    guide = _guide_for(_ready_draft(repo, class_id="class.wizard"))
    option = next(option for option in guide.options if option.id == "spell.fire-bolt")

    assert option.subtitle == fire_bolt.description.for_locale("zh-CN")


def test_all_character_creation_spells_have_specific_phb_summaries():
    repo = PHBRuleRepository.load_builtin()

    for spell in repo.list("spell"):
        assert "2014 Player's Handbook" not in spell.description.for_locale("en")
        assert "2014版" not in spell.description.for_locale("zh-CN")


def test_structured_spell_selection_can_be_built_incrementally(tmp_path):
    service = _service(tmp_path)
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
                    "constitution": 13,
                    "intelligence": 15,
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
                    "wizard-skills": ["skill.investigation", "skill.medicine"],
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

    partial = service.mutate(
        session.id,
        CharacterDraftMutation(
            expected_revision=session.revision,
            operation="spells",
            payload={"spell_ids": ["spell.fire-bolt"]},
            locale="zh-CN",
        ),
    )

    assert partial.validation_errors == []
    assert partial.draft.selections.spell_ids == ["spell.fire-bolt"]
    assert partial.draft.current_step == "spells"
    assert "spells" not in partial.draft.completed_steps


_STANDARD_SCORES = {
    "strength": 8,
    "dexterity": 14,
    "constitution": 13,
    "intelligence": 12,
    "wisdom": 10,
    "charisma": 8,
}


def _ready_draft(
    repo: PHBRuleRepository,
    *,
    class_id: str,
    race_id: str = "race.human",
    subrace_id: str | None = None,
    class_option_ids: list[str] | None = None,
    feat_ids: list[str] | None = None,
    choice_values: dict[str, list[str]] | None = None,
    ability_scores: dict[str, int] | None = None,
) -> CharacterDraft:
    class_rule = repo.get(class_id)
    race_rule = repo.get(subrace_id or race_id)
    draft = CharacterDraft(
        name="Mira",
        race=race_rule.name.en,
        class_name=class_rule.name.en,
        background="Sage",
        completed_steps=[
            "identity",
            "class",
            "race",
            "background",
            "abilities",
            "proficiencies",
            "class_features",
        ],
    )
    draft.selections.class_id = class_id
    draft.selections.race_id = race_id
    draft.selections.subrace_id = subrace_id
    draft.selections.background_id = "background.sage"
    draft.selections.class_option_ids = class_option_ids or []
    draft.selections.feat_ids = feat_ids or []
    draft.selections.choice_values = choice_values or {}
    if class_id == "class.fighter" and not draft.selections.class_option_ids:
        draft.selections.class_option_ids = ["class_option.fighter.defense"]
        draft.selections.choice_values.setdefault(
            "fighter-style",
            ["class_option.fighter.defense"],
        )
    draft.abilities = calculate_abilities(
        ability_scores or _STANDARD_SCORES,
        race_id=race_id,
        subrace_id=subrace_id,
        choice_values=draft.selections.choice_values,
        feat_ids=draft.selections.feat_ids,
        repository=repo,
    )
    return draft


def _guide_for(draft: CharacterDraft):
    return CharacterCreationGuideService().build(
        CharacterCreationSessionOut(
            id=1,
            locale="zh-CN",
            status="draft",
            revision=draft.revision,
            draft=draft,
            assistant_message="",
        ),
        "zh-CN",
    )


def _service(tmp_path) -> CharacterDraftService:
    store = SQLiteStore(tmp_path / "test.sqlite")
    store.init_schema()
    return CharacterDraftService(store)
