from __future__ import annotations

import json
from pathlib import Path

from backend.src.agent.character_creation.rules.models import (
    PHBRuleManifest,
    PHBRuleRecord,
)


class PHBRuleRepository:
    def __init__(self, records: list[PHBRuleRecord]):
        self._records: dict[str, PHBRuleRecord] = {}
        for record in records:
            if record.id in self._records:
                raise ValueError(f"Duplicate PHB rule id: {record.id}")
            self._records[record.id] = record
        self._validate_references()

    @classmethod
    def load_builtin(cls) -> "PHBRuleRepository":
        resource_dir = Path(__file__).resolve().parents[3] / "resources" / "phb2014"
        manifest = PHBRuleManifest.model_validate_json(
            (resource_dir / "manifest.json").read_text(encoding="utf-8")
        )
        return cls.load_files([resource_dir / filename for filename in manifest.files])

    @classmethod
    def load_files(cls, paths: list[str | Path]) -> "PHBRuleRepository":
        records: list[PHBRuleRecord] = []
        for path in paths:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("kind") == "spell_catalog":
                payload = _expand_spell_catalog(payload)
            elif isinstance(payload, dict) and payload.get("kind") == "equipment_catalog":
                payload = _expand_equipment_catalog(payload)
            elif isinstance(payload, dict) and payload.get("kind") == "starting_equipment":
                payload = _expand_starting_equipment(payload)
            records.extend(PHBRuleRecord.model_validate(item) for item in payload)
        return cls(records)

    def get(self, rule_id: str) -> PHBRuleRecord:
        try:
            return self._records[rule_id]
        except KeyError as exc:
            raise LookupError(f"PHB rule {rule_id} was not found.") from exc

    def list(self, rule_type: str | None = None) -> list[PHBRuleRecord]:
        records = list(self._records.values())
        if rule_type:
            records = [record for record in records if record.rule_type == rule_type]
        return sorted(records, key=lambda record: record.id)

    def search(
        self,
        query: str,
        locale: str = "en",
        rule_type: str | None = None,
    ) -> list[PHBRuleRecord]:
        normalized = query.casefold().strip()
        return [
            record
            for record in self.list(rule_type)
            if normalized
            in " ".join(
                (
                    record.id,
                    record.name.for_locale(locale),
                    record.description.for_locale(locale),
                    *record.tags,
                )
            ).casefold()
        ]

    def _validate_references(self) -> None:
        known_ids = set(self._records)
        for record in self._records.values():
            for reference in record.reference_ids():
                if reference not in known_ids:
                    raise ValueError(
                        f"Unresolved PHB rule reference: {record.id} -> {reference}"
                    )


def _expand_spell_catalog(payload: dict) -> list[dict]:
    class_lists = payload["class_lists"]
    descriptions = payload.get("descriptions", {})
    classes_by_spell: dict[str, set[str]] = {}
    for class_name, levels in class_lists.items():
        for spell_ids in levels.values():
            for spell_id in spell_ids:
                classes_by_spell.setdefault(spell_id, set()).add(class_name)

    records = []
    for spell_id, values in payload["spells"].items():
        english_name, chinese_name, level, school = values[:4]
        overrides = values[4] if len(values) > 4 else {}
        metadata = {
            "level": level,
            "school": school,
            "casting_time": "1 action",
            "range": "Varies",
            "duration": "Varies",
            "classes": sorted(classes_by_spell.get(spell_id, set())),
            "ritual": False,
        }
        metadata.update(overrides)
        records.append(
            {
                "id": f"spell.{spell_id}",
                "rule_type": "spell",
                "name": {"en": english_name, "zh-CN": chinese_name},
                "description": descriptions.get(
                    spell_id,
                    {
                        "en": f"{english_name}, a level {level} spell from the 2014 Player's Handbook.",
                        "zh-CN": f"{chinese_name}，出自2014版《玩家手册》的{level}环法术。",
                    },
                ),
                "source": "PHB 2014",
                "metadata": metadata,
            }
        )
    return records


def _expand_equipment_catalog(payload: dict) -> list[dict]:
    records = []
    for item_id, values in payload["items"].items():
        english_name, chinese_name, metadata = values
        records.append(
            {
                "id": f"equipment.{item_id}",
                "rule_type": "equipment",
                "name": {"en": english_name, "zh-CN": chinese_name},
                "description": {
                    "en": f"{english_name}, standard adventuring equipment.",
                    "zh-CN": f"{chinese_name}，标准冒险装备。",
                },
                "source": "PHB 2014",
                "tags": metadata.get("tags", []),
                "metadata": metadata,
            }
        )
    return records


def _expand_starting_equipment(payload: dict) -> list[dict]:
    records = []
    for package_id, metadata in payload["packages"].items():
        owner_id = metadata["owner_id"]
        name = owner_id.split(".", 1)[1].replace("-", " ").title()
        records.append(
            {
                "id": f"equipment_option.{package_id}",
                "rule_type": "equipment_option",
                "name": {
                    "en": f"{name} starting equipment",
                    "zh-CN": f"{name} 起始装备",
                },
                "description": {
                    "en": f"Starting equipment package for {name}.",
                    "zh-CN": f"{name} 的起始装备包。",
                },
                "source": "PHB 2014",
                "metadata": metadata,
            }
        )
    return records
