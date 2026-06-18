import json

import pytest

from backend.src.agent.character_creation.rules.models import PHBRuleRecord
from backend.src.agent.character_creation.rules.repository import PHBRuleRepository


def test_repository_loads_bilingual_canonical_rules():
    repository = PHBRuleRepository.load_builtin()

    mountain_dwarf = repository.get("race.mountain-dwarf")

    assert mountain_dwarf.rule_type == "subrace"
    assert mountain_dwarf.name.en == "Mountain Dwarf"
    assert mountain_dwarf.name.zh_cn == "山地矮人"
    assert mountain_dwarf.source == "PHB 2014"
    assert mountain_dwarf.grants


def test_repository_searches_in_selected_language():
    repository = PHBRuleRepository.load_builtin()

    results = repository.search("矮人", locale="zh-CN")

    assert {record.id for record in results} >= {
        "race.dwarf",
        "race.mountain-dwarf",
    }


def test_repository_rejects_duplicate_ids(tmp_path):
    rule = {
        "id": "race.human",
        "rule_type": "race",
        "name": {"en": "Human", "zh-CN": "人类"},
        "description": {"en": "Human.", "zh-CN": "人类。"},
        "source": "PHB 2014",
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps([rule, rule]), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate PHB rule id"):
        PHBRuleRepository.load_files([path])


def test_repository_rejects_unresolved_references(tmp_path):
    rule = {
        "id": "race.missing-child",
        "rule_type": "subrace",
        "name": {"en": "Missing", "zh-CN": "缺失"},
        "description": {"en": "Missing.", "zh-CN": "缺失。"},
        "source": "PHB 2014",
        "parent_id": "race.unknown",
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps([rule]), encoding="utf-8")

    with pytest.raises(ValueError, match="Unresolved PHB rule reference"):
        PHBRuleRepository.load_files([path])


def test_rule_record_rejects_missing_translation():
    with pytest.raises(ValueError):
        PHBRuleRecord.model_validate(
            {
                "id": "race.invalid",
                "rule_type": "race",
                "name": {"en": "Invalid"},
                "description": {"en": "Invalid.", "zh-CN": "无效。"},
                "source": "PHB 2014",
            }
        )
